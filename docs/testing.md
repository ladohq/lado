# Testing

The test infrastructure (parallel runs, the lock, the fake agent, the live, smoke and
container tests, CI, the Windows probe) and the test layers. Moved from AGENTS.md's
Commands and Testing (LAD-82).

## Test infrastructure

Unit and integration tests run in parallel, one pytest-xdist worker per CPU; each test has
its own `LADO_HOME`, tmux server and repos, so tests must not share a fixed path, port or
file. To debug serially, with output in order: `make test PYTEST_ARGS=-n0` (`PYTEST_ARGS`
replaces `-n auto` and takes any pytest options, e.g. `PYTEST_ARGS="-n0 -k gate -x"`), or
`uv run pytest` without `-n`. Live tests always run serially.

`make check` runs the unit, integration and UI tests as three pytest runs, one after another
(`scripts/check_groups.py`): in one run xdist hands the integration tests, collected first,
to two workers while the others wait idle. Each group runs also after one that failed, a
group that collects no tests (pytest's exit 5) is no failure, `PYTEST_ARGS` applies to each,
and the last line names the groups that failed (`check: failed: integration, ui`).

One heavy test run per machine at a time: `make check`, `make test`, `make test-integration`
and `make test-ui` run under a lock (`scripts/check_lock.py`, an flock on
`/tmp/lado-check-<uid>.lock`, shared by every worktree, session and `LADO_HOME`). A second
run waits and prints once whose run it waits for (`check lock: waiting for the run in
<worktree> (pid N)`). The lock is the helper process's: it goes when the run ends, also on a
failure, Ctrl-C or a kill, and a process the run leaves behind does not hold it. The command
gets `LADO_CHECK_LOCK_HELD`, so `make check` takes it once for its parts.
`LADO_CHECK_LOCK=0` runs without the lock (a parallel run on purpose); CI calls pytest
directly and takes no lock. A plain `uv run pytest` takes none either.

Integration tests (`tests/integration/`) run a fake agent (`fake_agent.py`, provider "fake")
instead of a real agent CLI; it keeps its logs (`inputs.jsonl`, `seen.json`) in
`agent_helpers.fake_logs`, outside its config folder, so they outlive the agent. It talks to
`lado mcp` through its own small stdio JSON-RPC client, not the MCP SDK's (whose import
alone took a third of a second per launch). Like a real agent, it gets its task as a
message: in its first input, a line from `lado` with more to read makes it call
`read_messages` and run the bodies of LADO's messages as commands (later bodies it only
reads when told to). `FAKE_AGENT_CRASH_AT_START=1` in its environment makes it exit before
its first hook. A test keeps it busy with its `pause` command
and ends that pause itself (`agent_helpers.release`), never with a `sleep` it must act
within. They use a temp `LADO_HOME` and their own tmux server
(`LADO_TMUX_SOCKET=lado-test-...`), and refuse to run otherwise. They run LADO's timers
short, `LADO_LOOP_INTERVAL=0.25` and `LADO_RETRY_DELAYS=2,0.5,0.5`, set for each test in
`tests/integration/conftest.py` (docs/design/agents.md; the first delay outlasts a prompt-submit
hook's confirmation under `-n auto`, the comment there says by how much); only tests set
either. Tests never use the default
`lado` tmux socket. `tests/conftest.py` clears `LADO_AGENT`, `LADO_SESSION`, `LADO_HOME`,
`LADO_TMUX_SOCKET`, `TMUX`, `LADO_CONTAINER` and `LADO_REPOS` for the test run, so the
tests run in an agent's shell (or LADO's image) as is,
and sets `LADO_AGENT_ENV=inherit`: agents get the test run's environment, not the user's
login shell (tests of the shell set their own `SHELL`). It also sets
`LADO_NO_UPDATE_CHECK=1`, so no test looks on PyPI; the tests of the update check switch it
on with the `published` fixture, a local index (`LADO_UPDATE_INDEX`). Likewise
`LADO_TELEMETRY=0` (and no `DO_NOT_TRACK` or `LADO_TELEMETRY_URL`), so no test sends
statistics: `telemetry_on` switches sending on towards a closed local port and stores the
yes, `telemetry_endpoint` adds a local endpoint that keeps each request. An autouse guard
(`_no_statistics`) fails a test when sending is not off by `LADO_TELEMETRY=0` before it, or
when, after a test without `telemetry_on`, its `LADO_HOME` holds `telemetry/sent.json` or a
file in `telemetry/outbox/`; the live and smoke tests, under `tests/`, get it too. And
`BROWSER=true`, so no test opens a browser (`lado bug-report`'s `y`: `webbrowser` runs
`true <url>`), a test that forgot to replace `webbrowser.open` neither
(`tests/test_cli_bug_report.py` checks it is set).

No test leaves a process alive (`tests/leftovers.py`). Every process a test starts carries
the test's `LADO_HOME` in its environment: the tmux server, the agents, their hooks and
`lado mcp`, the session loop, `lado server`, a real CLI and its children. After killing the
test's tmux server, the `isolated` fixtures of the integration, UI, smoke and live tests
wait up to 10 s for those processes to end (no longer than they take), then kill the rest
and fail the test, naming each by pid and command. Before that the integration tests check
that each session loop ended by itself within the same 10 s ("session loops still running
10s after the test"); one pass of a loop can take seconds on a loaded runner, and no test is
retried. The UI `server` fixture kills its `lado server` itself when it does not stop.
Each pytest process (each xdist worker too) also sets `LADO_TEST_PID` to its own pid, which
every process it starts inherits: a run's start kills the processes whose `LADO_TEST_PID`
names a pid no longer alive (a run killed from outside, a crashed worker), from any worktree
of the machine, and removes the `lado-test-*` tmux sockets no server answers on; a living
run's processes are never touched. At its end, each pytest process kills what still carries
its own mark and fails the run under "processes left by the test run, killed"; an xdist
controller checks after xdist has stopped its workers, which carry its mark from their start
(the environment a process was started with is what is read), and each worker hands it what
it left. From the start of a test's setup to the end of its teardown, the pytest process
also sets `LADO_TEST_ID` to the test's node id, so the report names each process with the
test it was started in (`<pid> <command>, started in <node id>`); a process started outside
a test is named by pid and command alone. The environment is read from `/proc` on Linux and
with `ps -E` on macOS. `LADO_TEST_PID` and `LADO_TEST_ID` are marks of the test suite only:
LADO itself neither sets nor reads them.

Live tests (`tests/live/`) run the real CLIs with the same isolation, every provider on one
remote endpoint, set up by its entry in `live_models.SETUPS`, with nobody's login:
`LADO_LIVE_ENDPOINT` (its base URL, ending in `/v1`; no default), `LADO_LIVE_API_KEY` (its key,
only ever in the environment) and `LADO_LIVE_MODEL` (the model, with tools and, for the image
test, vision), each CLI's own `LADO_LIVE_<CLI>_MODEL` winning (for OpenCode and Kilo with the
prefix `endpoint/`, as `LADO_LIVE_KILO_MODEL=endpoint/<model>`: without it the CLI goes past the
endpoint). A test skips, naming what to
set, when any of them is unset or its CLI is missing, so a run of skips proves nothing: `make
test-live` without them ends with no failure. E.g. `LADO_LIVE_ENDPOINT=https://openrouter.ai/api/v1
LADO_LIVE_API_KEY=<key> LADO_LIVE_MODEL=<model> LADO_LIVE_IMAGE=1 make test-live PROVIDER=codex`.
A local server can serve as the endpoint, when it has the APIs below. The models CI uses are
in `live.yml`'s matrix, one per provider; the trial that chose them:
`docs/superpowers/reports/2026-11-07-cloud-live-tests-trial.md`.
A paid model only with a limited key and the human's yes; the schedule in CI is that yes,
given once by LAD-231.

Each provider has one source of the model, in the environment every LADO process of the test
inherits. OpenCode and Kilo reach the endpoint as a chat completions API, by a config file of
the test as `OPENCODE_CONFIG` / `KILO_CONFIG` (the `endpoint` provider and `model`, the key as
`{env:LADO_LIVE_API_KEY}`), with a state folder of the test's own (`XDG_STATE_HOME`: their TUI
takes the model an agent used last over the config's), the model each recorded checked after
the run. Codex reaches it as a Responses API, by the test's own user Codex config, which LADO
carries (`model`, `model_provider = "endpoint"`, the key by its `env_key`); the endpoint must
keep the MCP tools Codex sends. Claude Code reaches it as an Anthropic API:
`ANTHROPIC_BASE_URL` is the endpoint without its `/v1`, the key goes as `ANTHROPIC_AUTH_TOKEN`
(a token it takes without asking; a new `ANTHROPIC_API_KEY` is a question) and the model as
`ANTHROPIC_MODEL` and `ANTHROPIC_DEFAULT_HAIKU_MODEL`, as its background calls name a haiku of
their own; each answer in its transcripts is checked to be on that model. The key is a value
there, as Claude Code has no reference to a variable. A failed test's evidence has the key
redacted, and the tests check that no agent config holds it. The image test skips before it
sends an image unless `LADO_LIVE_IMAGE=1` (unset or another value: the model takes none), and
fails when a model that declares it does not see the image.

No live test uses a Claude subscription. Unit tests cover the login check's logic and
`CLAUDE_CODE_OAUTH_TOKEN`, the smoke trust, onboarding and the start without a dialog on Linux
and macOS, the live tests a whole turn with real tools. A real subscription login end to end
is left to the human's daily use of LADO: the keychain and the macOS graphical session
(`gui_session.py`), a real token's refresh, a human's own `.claude.json`, and Anthropic's API
itself with its limits, as the endpoint stands between.

The passive supervisor of the live kit is
read-only (no command tools; LADO's run messages to it name the human's ways), and every
live test fails when a `repo_changed` event names it; the test merges only while it is idle.
No Codex agent asks whether to trust the test's repo: LADO's config of each agent trusts
it, and the test fails if Codex asks. `tests/live/test_codex_login.py` runs a Codex session
with a worker on OpenAI's model and a real ChatGPT login, shared by the agents' links, each
agent started on the file made stale so it refreshes it (a running Codex keeps its login in
memory and reads the file again only when its own tokens need a refresh): only with `LADO_LIVE_CODEX_HOME` naming a Codex home the human
logged in to (`CODEX_HOME=<dir> codex login --device-auth`), else it skips.
Unit tests get a `CODEX_HOME` of their own (`codex_home`, `tests/conftest.py`), never the
user's `~/.codex`. If Claude Code's workspace trust dialog shows in a live test, the test
fails with LADO's reason. Every test gets a Claude config of its
own (`claude_config` in `tests/conftest.py`, autouse, `CLAUDE_CONFIG_DIR` outside
`tmp_path`), which trusts the `repo` fixture's folder, never the user's: LADO writes the
trust there; `trust()` with no folder lets a test see the write, `refuse()` the fallback
question.

Smoke tests (`tests/smoke/`, marker `smoke`) run each provider's real CLI with the live
tests' isolation and helpers (`tests/real_clis.py`, shared by both) but no model: each CLI
gets a home of its own (`HOME`, `XDG_*`, `CLAUDE_CONFIG_DIR`, `CODEX_HOME` in the test's
folder; never the user's config, skills or keys) whose config points it at `fake_endpoint`,
a server on `127.0.0.1` that answers every request with 401 (Anthropic's or OpenAI's error
body) and keeps each request. Claude Code: `ANTHROPIC_BASE_URL`, a fake
`ANTHROPIC_AUTH_TOKEN` (an `ANTHROPIC_API_KEY` it has not seen is a question),
`CLAUDE_CODE_MAX_RETRIES=0` (it retries every 401 ten times), and a `.claude.json` that has
the onboarding and the bypass permissions disclaimer done but not the repo's trust, which
LADO records (the test checks the entry and the start's line); Codex: a
`model_provider` at the endpoint (`wire_api = "responses"`, a fake `env_key`); OpenCode and
Kilo: a global config with an OpenAI-compatible provider at it, the model given as
`--model`. One test, per installed provider (a missing CLI skips): the session starts and
the supervisor's session-start hook makes it idle, its CLI lists LADO's MCP tools
(`mcp_ready`), the human's message with a body is delivered by its own hook, its turn ends
on the endpoint's error (`turn_error`), a worker's task is delivered, and `lado stop` leaves
no process. Codex CLI starts its session only on its first input and runs no hook for a
turn that ends on an API error (BACKLOG.md; on a model server LADO reads it from the journal, as
the Responses tests below show): its smoke checks that `runtime.FIRST_INPUT` is
delivered instead of the human's message and the turn error, in code, never a skip. A
failed smoke keeps its evidence as a failed live test does. `make test-smoke
[PROVIDER=...]`; not in `make check`, which has no CLI. The 401 endpoint is
`tests/fake_endpoint.py` (standard library only), also a script, `python fake_endpoint.py
<port> <log file>`, for the container tests. It keeps the names of the tools each request
offers the model (`Endpoint.tools`, and `tools` in the log's line; a namespace's as
`<namespace>.<name>`), so a Codex test checks that an agent on a model whose metadata
brings Codex's own subagents (gpt-6-sol) gets none of them, after a control: a plain
`codex exec` on the same home gets `collaboration.wait_agent`, or the test fails saying the
model no longer brings them. It keeps the model each request asks for too (`Endpoint.models`):
per provider, a session started with a model (`lado start --model`; OpenCode and Kilo
without the test's `--model`, as the CLI itself) asks the endpoint for that model. Its
`Anthropic` and `Responses` servers and `fake_model_server.Server` take a `refusal` once a session
is up: every model request then gets that status and body, with `Retry-After: 1` so that a real
CLI's repeats of a 429 take seconds; the smoke counts the requests per CLI on a 401 and a 429, the
key echoed. `Responses` is the same scripted turn for Codex CLI: a shell call, then LADO's tool in
its `namespace`, with the usage it is told to report. Its tests are the only layer that catches a
Codex update that changes what LADO reads: the journal's format, the catalogue's (real `/model`
shows the agent's one model), the tools of a request, a compaction past LADO's limit.

The model servers of `lado model-server probe`'s tests are `tests/fake_model_server.py`
(standard library only): a `Server` on `127.0.0.1` with a profile (`openai`, `ollama`,
`lmstudio`, `anthropic`, a gateway that answers 400 to every path, a provider's list, a redirect,
one that hangs, one that holds a POST by `Held`, …), optionally behind a key and under a gateway's path, that keeps each request with
its headers and body; also a script, `python fake_model_server.py <profile> <port file>
[<key>]`, for the integration test that runs the real command against it.

Container tests (`tests/container/`, marker `container`) run LADO's image (`docker/`) with
real Docker and no model, driving the `docker` CLI from the host against an image built
already (`make docker`; `LADO_TEST_IMAGE`, else `lado:local`); they skip when Docker does
not run or the image is missing. Each container, volume and compose project a test makes is
named with the test run's own prefix, `lado-test-<run hex>-<hex>` (`container_helpers`), so
a run beside it is never taken for one left behind; it runs with `LADO_TELEMETRY=0` and
`LADO_NO_UPDATE_CHECK=1` and is removed after the test by a finalizer, also on a failure
(the session's teardown fails when a container or volume of the run is left). They
check: one `docker run` serves `/api/health` (the wheel's version) and the UI on its
`LADO_PORT` (8765 without it), with the container note in `docker logs` and `lado ui
--no-open`'s link on that port; `lado doctor` has no `[FAIL]`, says `in a container` and
each of the four agent CLIs `ok`; Node 22 and `npx` in a login shell; a Claude Code
session against the fake endpoint, run inside the container on its own loopback and given
through `~/.profile`, gets its supervisor to idle, the window's process is the `claude`
binary itself (`/proc/<pid>/exe`), and `lado doctor` run with exactly that process's
environment (`/proc/<pid>/environ`) says `in a container`; `docker/compose.yaml` serves on
its `LADO_PORT`, its `lado doctor` names the workspace at the host's path as `LADO_REPOS`,
its `config` takes the workspace from `LADO_WORKSPACE`, else from `LADO_PROJECTS`
(`LADO_WORKSPACE` winning), its `up` refuses without either, naming `LADO_WORKSPACE` and
making no folder on the host, a LADO project made in it is on the host and not outside the
workspace for the UI's folder check, its `config` refuses without `LADO_VERSION` (naming
it), and it runs `ghcr.io/ladohq/lado:<LADO_VERSION>` with it and `LADO_IMAGE` when that is set.
Two LADOs (`test_two_lados.py`): two compose projects, each a folder of its own with a copy
of compose.yaml and its own `.env` (`COMPOSE_PROJECT_NAME`, `LADO_PORT`, `LADO_IMAGE` a tag
of the run's prefix, `LADO_WORKSPACE`), no `-f` or `-p`; a new image reference in the first's
`.env` and its `up -d` leave the second's container id, start time and image as they were;
`docker compose down` of the first leaves the second's session running, its supervisor the
same process, and its `lado.db` with no session stopped; the update's two have each a
`secrets/` of its own (`LADO_SECRETS=./secrets`), the stop's two none. Such a folder is
conftest's `folder(name, **settings)`, the `compose` fixture a project with no
`LADO_SECRETS`.
The installer (`test_install.py`): `docker/install.sh --yes --no-open` with the working
copy's `compose.yaml` (`--source`), the image under test (`--image`) and a folder of the
run's prefix (`--dir`, conftest's `installed`, so its project `lado-<folder>` is the run's),
a home of its own and Docker's own config; its printed link answers 200, a rerun of the
same version changes no file and keeps the token, an `.env` set to `0.0.1` is updated with
`compose.yaml.bak` and the user's line kept, and `--phone` prints the other device's link.
Every other behaviour of the installer is a unit test: `tests/test_install_sh.py` runs it
under dash and bash on a faked host (`tests/install_fakes.py`: a PATH of its own with
links to the base tools and fake `docker`, `curl`, `git`, `uname` and friends that log
their argv and `LADO_*`/`COMPOSE_*` and answer from per-test settings; `sleep` returns at
once), its questions through a pty driven by a process of its own (forking a
multi-threaded pytest worker may deadlock); `tests/test_install_ps1.py` reads
`install.ps1` and, with `pwsh` on PATH (GitHub's Ubuntu runners), parses it and runs it:
under `Invoke-Expression` it leaves the caller's `$ErrorActionPreference`, strict mode and
functions as they were, its script-block form takes the switches, a file run exits with its
code, and with fake `docker` and `wsl.exe` on PATH it runs its version's `install.sh` in
Ubuntu (never `docker-desktop`) with the switches' flags. Its behaviour on a real Windows
is checked by hand (docs/release.md).
The secrets folder (`test_secrets.py`; only fake values): compose with no `LADO_SECRETS`
and no folder starts, `lado doctor` exits 0 with `[info] … /run/secrets: none` and the hint
naming `LADO_SECRETS=./secrets`, a Claude Code session reaches idle, and `docker compose
logs` names neither `/run/secrets` nor `LADO_ENV_DIR`; `LADO_SECRETS=./secrets` and a
fake `GH_TOKEN` in `secrets/` reach the supervisor's process and doctor's `[ok  ]` line;
with the line but no folder `up -d` fails naming the path and makes no folder.
The sessions (`test_sessions.py`): `docker compose stop` with a Claude Code session and one
stopped by hand exits 0 with the stop's line naming only the first, both stopped in
`lado.db` and only the first marked; `start` (and `down`, then `up -d`) resumes it with the
resumed line and its supervisor idle, the other stays stopped, and `lado doctor` warns about
no agent config folder; `docker kill`, then `docker start`, resumes it too; three sessions
stop within Docker's default ten seconds with exit 0, all marked; a new image on a home
volume with a session not stopped (`old_home(running=True)`) prints the upgrade line before
the resumed line.
The workspace (`test_projects.py`): with the test's
folder mounted at its own path, a worker spawned in the container commits in its worktree,
and on the host `git status` works there, `git worktree list` has no `prunable`, the file
and the commit's object belong to the host's user (uid 1001 on GitHub's runner), and the
worker's process has the container's `LADO_REPOS`; a projects volume owned by 2001
(`projects_volume`) makes `lado` uid 2001, its home too, leaves no sudo rule, `docker exec
lado ui` works, and a restart (under 8 s) keeps the uid; the same home volume in a new
container with a workspace of 2002 is 2002's, with `lado doctor` clean and `lado ls` working;
an owner of 0 keeps 1000 and warns in `docker logs`, as does a `LADO_REPOS` not mounted; a
gid of 0 is not taken; with the entrypoint replaced (the sudo rule left), a `setpriv`
first on the PATH its caller hands over does not run as root; with no-new-privileges,
`--cap-drop ALL` or `--read-only` the server starts as uid 1000 and `docker logs` says why.
The agents' access (`test_access.py`; only fake values): a secrets folder of the host at
`/run/secrets` gives a kit role's MCP server its `${TEST_KIT_KEY}` and the supervisor the
variable, `lado doctor` names it, and neither `docker inspect` nor `docker logs` holds the
value; `LADO_GIT_NAME` with an apostrophe and `LADO_GIT_EMAIL` are a commit's author and
committer, a new email on the same home volume replaces the old, and without them
`docker logs` warns; `GH_TOKEN` of the folder is `git credential fill`'s password for
github.com and `gh auth token`; an ssh agent of a sidecar container (OpenSSH's agent
serves only its own uid, so it runs as lado's) on a shared volume, its socket given to
root as Docker Desktop's is, lists its key in an agent's login shell, also after a
restart that found it root's again, with no 0 in `id -G`; one of the workspace's owner
(2001) works as it is and stays 2001's; under no-new-privileges a root socket is the
warning; compose's default (`/dev/null`) gives no `SSH_AUTH_SOCK` and no line; and the
ssh rule refuses an argument and a variable, `sudo -n true` fails.
A new image on an old home volume (`test_migration.py`; `old_home` seeds a volume with a
`lado.db` this checkout's `lado.state` made on the host, a stopped session in it, at the
schema before by `previous_schema`): the server migrates it, `/api/health` answers,
`backups/lado.db.schema-<N>` is there, `docker logs` has the upgrade line and `lado ls`
lists the session; a lado.db whose last step fails (its column there already) exits the
container with the message (the way back: the image of the version before) and no
traceback in `docker logs`, its schema kept; compose's header steps back, run as written
with the version before as `LADO_IMAGE` (a tag of the run's prefix on the image under
test), put the backup's schema back and start that image.
The browser (`test_browser.py`): on a new home volume the Playwright of `uv.lock` (`uv
tool run --from playwright==<version>`) installs its headless shell, whose `ldd` names no
library `not found` (the missing ones in the failure), and launches Chromium, which renders
a page with Latin and Cyrillic text and gives it back, its screenshot in `<temp
dir>/lado-container-shots/` (in CI's artifact `container-<arch>-<k>` of its shard); a new home volume has no
`~/.cache/ms-playwright` and no `chromium`, `chromium-browser` or `google-chrome` on
`PATH`. So the UI tests run in LADO's image after `make browser`. The
toolchains' Go test (`test_toolchains.py`) has mise install Go from a mirror inside the
container (`python3 -m http.server` on its loopback), fed by one download of the archive on
the host per run, checked against its sha256; each install is bounded by `timeout` and its
failure shows both exit codes and mise's debug logs (LAD-178). A
test that fails in its setup or its
call keeps, for each container it started (a compose project's too), `docker logs` and
LADO's logs in `real_clis.EVIDENCE`: the container is registered on the test before
anything can fail, and its finalizer runs after the failure's report. `make test-container`; not in `make
check`.

CI (`.github/workflows/ci.yml`) runs on each pull request, each push to main, daily on main
(03:47 UTC, `schedule`) and by hand (`workflow_dispatch`). Its jobs: `unit (<python>)`,
`ruff format --check`, `ruff check` and the unit tests (in parallel, `-n auto`) on Python
3.10 and 3.13; `integration (<python>, <k>)`, the integration tests in three shards per
Python, each in one process (`-n0 --shard K/3`); `web`, `make dist` (the web UI's
stale-types check, types, unit tests and build, and the bundle in both the sdist and the
wheel) and the Node tests, which no UI job waits for; `ui (<k>)`, the UI e2e tests in four
shards on Python 3.13 (on two workers, `-n 2 --shard K/4`), each building only the bundle;
`changes`, whether the run needs the smoke; `smoke <os> <provider>`, the smoke
tests on Linux and macOS, one cell per (system, provider), none stopping the others;
`container (<arch>, <k>)`, LADO's image on amd64 (`ubuntu-24.04`) and arm64
(`ubuntu-24.04-arm`), each on its native runner, in two shards per architecture, each cell
building its own image: `make docker` (whose build runs each agent CLI's `--version`
once, with a throwaway HOME, so a CLI npm left without its native binary fails it; no
retry) and `docker history lado:local` (each layer's
size, so a new layer's is the image's growth), then `scripts/smoke_ci.py container <out>
K/2` (its shard of the container tests with the smoke cell's pass rule, so a skip or an
empty shard is red; the artifact `container-<arch>-<k>`), on every run whatever it changes,
pushing nothing anywhere. Its build takes the layers from GitHub's Actions cache, scope
`container-<arch>`, through a BuildKit builder of its own (`docker/setup-buildx-action`;
`--load` puts the image into the runner's Docker) and `make docker DOCKER_BUILD_FLAGS=...`:
a pull request reads main's cache and writes none; a push to main reads and writes it
(`mode=min`); the schedule and a dispatch build from nothing (`--no-cache`) and write it
anew, so a broken outside source (Debian, gh's repository, npm) shows within a day. Only
shard 1 of each architecture writes, so two cells never write one scope at once. LADO's
wheel is the Dockerfile's last layer, so a pull request rebuilds only that one; the release
(`release.yml`) builds without any cache. And
`ci-ok`, the one check the ruleset of main requires. Every job has a `timeout-minutes`,
about twice its p90 (a test refuses a job without one): a hung job ends red instead of
running GitHub's six hours. A UI job takes Chromium and the `.deb` files `playwright install
--with-deps` downloads (fonts, from an Ubuntu mirror that is sometimes slow or hangs) from a
GitHub cache keyed by Playwright's version and the runner image's (`$ImageOS`,
`$ImageVersion`): on a hit it installs them with `dpkg -i` and runs `playwright install
chromium`, asking no mirror; on a miss it runs `--with-deps` with apt's retries and a 30 s
network timeout, under the step's own 10 minutes, and keeps the debs apt downloaded. Only a
run outside a pull request (push to main, schedule, dispatch) saves the cache, before the
tests: a pull request's cache would be visible to it alone. `--shard K/N` (`tests/shard.py`, also
locally) keeps the tests whose node id's CRC-32 modulo N is K - 1, so each test is in
exactly one shard, always the same, and deselects the rest. The worker counts are for
GitHub's 4-vCPU runners, where `-n auto` is four workers: four integration tests at once
(each its own tmux, agents and session loop), or four UI tests (each with a Chromium and a
`lado server`), starve each other past LADO's short test timers; the unit tests run mostly
in process and keep `-n auto` (`tests/test_ci_workflow.py` pins the commands). The smoke
runs on every push, schedule and dispatch, and on a pull request unless every file it
changes (`git diff --name-only --no-renames base...head`) is on the skip list in ci.yml
(`web/`, `docs/`, `openspec/`, `tests/ui/`, `tests/js/`, the top-level Markdown documents,
`.github/dependabot.yml`): `scripts/smoke_ci.py needed` answers for `changes`, and the
smoke's job-level `if` skips it, never the triggers' paths (the run and `ci-ok` would not
report). No path of that list may be or hold `src/`, `scripts/`, `tests/` (but `tests/ui/`
and `tests/js/`), `docker/`, `pyproject.toml`, `uv.lock` or `.github/workflows/`
(`tests/test_ci_workflow.py`). `ci-ok` needs every other job and runs whatever their
results (`if: always()`, both kept by a test: a skipped required check counts as passed);
`scripts/ci_ok.py` fails it unless each succeeded, the smoke skipped only when `changes`
said it is not needed, a cancelled job a failure. A pull request's new run cancels its
older one; a run of another event is alone in its group (its run id), never cancelled.
GitHub mails a red scheduled run to whoever last changed its cron line. A cell is
`scripts/smoke_ci.py run <provider> <out>`: it installs the CLI with `npm install -g
--prefix ~/.local` at its pin and runs its `--version`, in up to three attempts (npm drops
an optional dependency that failed to install, a CLI's native binary, and exits 0): after a
failed attempt but the last, a `::warning::` annotation in the run's summary names the
provider and the attempt, then `npm uninstall` and a fresh install; the third failure is a
red cell with no test run. Then it runs `uv run pytest -m smoke -n0 -v -k <provider>` into
`<out>/smoke-<provider>.log`, and passes only on exit 0 with a test passed and none skipped;
a failing cell's evidence goes to `<out>/evidence` (the artifact
`smoke-<os>-<provider>`). `smoke_ci.py`'s `PINS` is the one place a CLI's version is
written for CI: its providers are exactly `lado.providers`' and each pin's version parts are
its provider's `TESTED_VERSION` (`tests/test_smoke_ci.py`); the matrix is the same list
(`tests/test_ci_workflow.py`). No secret anywhere.
A job GitHub finds no hosted runner for is cancelled before any step, with no runner and
GitHub's annotation "The job was not acquired by Runner of type hosted even after multiple
attempts" (`timeout-minutes` does not count that wait): mostly a `smoke macos-latest` cell,
beside the notice that GitHub lacks macOS arm64 capacity, and `ci-ok` fails the run. The
workflow `CI rerun` (`.github/workflows/ci-rerun.yml`, on `workflow_run` of CI, so it runs
main's files and never a pull request's code; `actions: write`, `checks: read`, `contents:
read` only) takes each CI run whose first attempt ended `failure` and runs
`scripts/ci_rerun.py <run-id> --rerun`: it reruns the failed jobs (`gh run rerun --failed`)
once, and only when every job of attempt 1 that did not succeed, `ci-ok` aside, was
cancelled with no step, no runner and that annotation, and, for a pull request's run, no
newer CI run of its branch exists (the rerun would cancel it through the concurrency
group). A superseded run ends `cancelled` and is never looked at; the rerun is attempt 2,
never rerun again. Its log says why it reruns or not; without `--rerun` the script only
prints the verdict on attempt 1, e.g. on a past run (`tests/test_ci_rerun.py`,
`tests/test_ci_rerun_workflow.py`).
Every `uses:` of every workflow, GitHub's own actions too, is a full commit SHA followed by
`# vX.Y.Z`, the release it is (`tests/test_workflow_security.py`); Dependabot
(`.github/dependabot.yml`) updates those pins, the uv and the web UI's npm dependencies and
the base images of `docker/Dockerfile` (pinned by digest) weekly, minor and patch in one
pull request per ecosystem, a release once it is 7 days old.
`claude.yml` (the `@claude` reviewer) starts its job only for an author who is the
repository's `OWNER`, `MEMBER` or `COLLABORATOR`. It checks out the full history and lets
Claude run `git diff`, `git log` and `gh pr diff` besides the Action's own tools, nothing
else; a standing instruction in its `claude_args` (not `prompt`, which would leave the
comment mode and its "Claude finished") has a review read `origin/main...HEAD`, risky code
first (security and secrets, deleting data, agents' environment, the server's API), and end
with the lists `Files read` and `Files not read` (`tests/test_workflow_security.py`). An
`issue_comment` runs the workflow of the default branch, so a change to it takes effect
after its merge. Vulnerability reports: SECURITY.md.
The live tests run in a workflow of their own, `.github/workflows/live.yml`, outside `ci.yml`
and so outside `ci-ok`: a provider's outage looks like a failed test and must not block a
merge. Weekly on main (Monday 04:23 UTC), by hand (`gh workflow run live.yml`) and on each
release candidate, a cell per provider on Linux, each with its model of the matrix:
`scripts/smoke_ci.py live <provider> <out>` installs the CLI at its pin and is red unless the
tests passed and none skipped; `tests/live/test_codex_login.py` is left out, as it needs a
person's login. It runs them for at most 25 minutes outside `<out>` and silently, then redacts
the key, also where a window wrapped it, prints the log to the job's and moves the log and the
evidence to `<out>` for the upload. A test ended by that limit keeps no evidence of its own,
only the log and what the tests before it kept; a job killed before the redaction uploads
nothing. The key is the secret `LADO_LIVE_API_KEY` of the environment `live`, which admits only
`main` and tags `v*`, so no run of a pull request gets it, and only the test step names it.
A run of the four cells costs about $0.07 (the trial's report). The key's limit, $10 a month, is
the hard stop: past it, or with no credits on the OpenRouter
account behind it, a run goes red with a 402. A red run mails as any failed workflow does;
rerun its failed cells by hand (`gh run rerun <id> --failed`), a pass on a rerun being a flake.

A Windows probe, neither in the per-push CI (a run takes 20-25 minutes) nor a release step
(docs/release.md, section 5): the `Windows probe` workflow
(`.github/workflows/windows-shell.yml`) runs weekly on main (Monday 03:17 UTC, its
`schedule`, with the defaults: WSL, tests, smoke; a red run mails the maintainers as any
failed workflow does) and when started, `gh workflow run windows-shell.yml --ref <branch> -f
runner=windows-latest` (`-f wsl=false -f smoke=false`: native only, as the smoke needs WSL;
`-f tests=false`: no tests part; `-f smoke=false`: no smoke;
`-f provider=claude|codex|opencode|kilo`, `all` by default: whose smoke; `-f minutes=N`,
120 by default, at most 360, setup included, per part). Its first job, `settings`, is the
only one that reads the inputs: a scheduled run has none, and each takes its input's default
(`tests/test_windows_shell_workflow.py` keeps both the same). It refuses the smoke without
WSL and a run with neither tests nor smoke, and makes the parts, a JSON list: `tests`, and
`smoke-<provider>` per chosen provider (its list is `smoke_ci.py`'s `PINS`, kept the same by
a test). The job `probe` is a matrix of the parts (`fail-fast: false`): each part runs on a
runner of its own with its own WSL, all at once, so a weekly run is 5 jobs. Each part, with
`wsl`, sets up WSL2 Ubuntu 24.04, the user `lado` and the repo at the run's commit in
`~/lado`, and runs each check in `lado`'s login shell: `uname -m`, `tmux -V`, uv's install,
its `PATH` (`wsl-path.log`), `uv sync`, the agents' PATH by LADO's own
`agent_env.from_shell` (`wsl-agents-path.log`), `lado --version`. Then the part `tests`
installs LADO from the checkout on Windows itself (`native.log`: Python, `lado --version`,
`lado doctor`; expected to fail, only recorded) and runs in WSL `lado doctor` (recorded
only: no agent CLI there), `make test` and `make test-integration`; a part
`smoke-<provider>` installs Node and npm from Ubuntu (the check `node`) and runs a cell of
`smoke_ci.py run` (`wsl-smoke-<provider>.log`), the required check `wsl smoke-<provider>`;
a failing one's evidence folder is in the report as `smoke-evidence-<provider>`. The quick
smoke-only run: `-f tests=false`. A part is red when one of its required WSL checks fails.
The logs are the artifact `windows-probe-<runner>-<part>` (`gh run download <id>`), and each
part's summary has each check's exit code, the PATH lines and the end of each failing log
(`gh run view <id>`, `--log` for all). No shell into the runner: the public tmate servers are gone
from DNS.
`windows-11-arm` runs only with `-f wsl=false -f smoke=false`: setup-wsl's Ubuntu image is
amd64 only.

## Test layers

Seven layers; each change gets tests at the lowest layer that can catch its bugs:

1. **Unit** (`make test`): pure logic, tmux replaced by a recorder. Default for everything.
   The server's API is tested in process with FastAPI's test client; the web UI's
   components with vitest (`make web`), `fetch` mocked. vitest runs in en-US whatever the
   machine's locale (`test.env` in `web/vite.config.ts`, held by `web/src/testLocale.test.ts`):
   the UI formats dates and sorts names in the human's locale, and the tests' expected
   values are en-US's. A test has 30 s (`testTimeout` in `web/vite.config.ts`) and `waitFor`
   and `findBy` wait 10 s (`asyncUtilTimeout` in `web/src/testSetup.ts`), so a loaded machine
   does not fail what only comes late; a test sets no timeout of its own, and waits with
   Testing Library's `waitFor`, not `vi.waitFor`, whose own 1 s no setting changes.
2. **Integration** (`make test-integration`): real tmux, git, hooks, `lado mcp` and SQLite
   with the fake agent instead of an LLM. Required for behaviour that crosses processes,
   also the UI server's (one per home, background start, stop), without a browser.
3. **Plugin tests** (`make test-js`): provider plugins run under Node with a fake client.
4. **UI e2e** (`make test-ui`, marker `ui`): Chromium (pytest-playwright) against a real
   `lado server` on a free port, with sessions of the fake agent, isolated like the
   integration tests; only what needs a browser. Each test saves a screenshot of every
   screen it checks to `<temp dir>/lado-ui-shots/<test>.png` (the `shot` fixture), outside
   the tree, for the reviewer. In `make check` and in CI (four shards; `make dist` in the
   job `web`).
5. **Smoke** (`make test-smoke`, marker `smoke`): each provider's real CLI with real tmux,
   hooks, `lado mcp` and SQLite, and a local endpoint that answers 401 instead of a model
   (Test infrastructure): the platform half of the live tests, without their model half. Needed for a
   change in how LADO starts, configures or talks to a CLI on some system. Never in the
   default run or `make check` (it needs the CLIs); in CI on Linux and macOS (job `smoke`:
   every push to main, daily, and each pull request that changes a file off the skip list;
   Test infrastructure), and in WSL2 in the Windows probe, a job per provider.
6. **Live e2e** (`make test-live`, marker `live`): real agent CLIs and real models, one short
   scenario per provider: a worker commits a file, reports to the supervisor and gets a
   message; then the session stops and no process is left. Never in the default run or
   `ci-ok`: weekly and by hand in `live.yml`, every provider on OpenRouter, on each RC, and a
   provider's after changing it.
   When a live or smoke test fails, its report names a folder
   `<temp dir>/lado-live-evidence/<time>-<test>` that keeps the test session's `lado log`,
   `hooks.log`, each agent's config folder and cwd, and each tmux window's screen, taken
   before teardown. A passing test keeps nothing; the folder is never cleaned by the tests.
   A timed-out wait names what it waited for and the agents' statuses and last messages.
7. **Container** (`make test-container`, marker `container`): LADO's image (`docker/`) as
   one `docker run` starts it, with real Docker and no model (Test infrastructure). Needed for a change
   of `docker/` or of how LADO behaves in a container's environment. Never in the default
   run or `make check`; in CI on amd64 and arm64 (job `container`, every run).

What must be green before a release (CI, `live.yml`): [docs/release.md](release.md).
The Windows probe is not a release step: it runs weekly, and a red run is fixed as any
other regression.
