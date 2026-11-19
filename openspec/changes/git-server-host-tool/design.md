## Context

A saved git server (`lado.git_servers`) gives git, through `GIT_CONFIG_*` laid over an
agent's launch, LADO's credential helper, ssh rewrites, a commit author and `sslCAInfo` for
its certificate. `gh` gets its own empty folder (`GH_CONFIG_DIR`) and the tokens of the
github.com and GitHub Enterprise entries in its variables (`gh_variables`); every GitHub
variable of the layers is dropped (`agent_env.GITHUB_VARIABLES`). A kind module
(`git_kinds/`) already names its tool (`tool`: `gh`, `glab`). Nothing tells an agent which
kind of server its repository is on, and nothing signs `glab` in; the image has no `glab`.

Root cause: LADO's knowledge of the server stops at git. The tool that opens a change
request is left to the kit (which may name the wrong one) and to the human's own login
(which LADO's container does not have, and which may be another account).

Options weighed for giving `glab` the token (all checked by hand against glab 1.80–1.131):

1. **`GITLAB_TOKEN` in the agent's environment**, as `GH_TOKEN`. glab sends an environment
   token to every host of its configuration and to `GITLAB_HOST`: one token for all GitLab
   servers, so two saved GitLabs cannot both work. Rejected.
2. **The token in the agent's own `config.yml`** (`hosts.<host>.token`). Works on every glab;
   but it is a second copy of the token on disk, outside `git-servers/<id>/token`, which the
   git-servers capability keeps the only one, and it goes stale until the agent restarts.
3. **A header from LADO's helper** (`hosts.<host>.custom_headers`, `PRIVATE-TOKEN`,
   `valueFromCommand`): the token is read from its one file at each call, as git's helper
   reads it; a replaced token works at once. Needs glab ≥ 1.114.0 (older ones send no header,
   silently); `glab auth status` says logged in, with a note `No token found` of its own.
   **Chosen**, with the version check (D6) against the silent case.

Held against ROADMAP's coming stages: a new kind (Bitbucket, Gitea) names its tool and word in
its module and gets the line and the checks with no other change; `gh`'s certificate later
takes the same file. Against AGENTS.md: neutral core (the line and the variables are the same
for every provider: instructions and environment, no provider code); one source of truth (the
token file and `ca.pem`, read by git and glab alike; the tool from the kind); no silent drop
(the dropped GitLab variables, the human's own glab login, a missing or old glab: each named
by doctor or the launch); only what is used (no option to turn the line off).

## Goals / Non-Goals

Goals: glab in the image; the agents' glab signed in to each saved GitLab with its token and
certificate, per host; every agent told its repository's server and tool; a missing or old
tool said loudly; a live test of a push through a saved server.

Non-Goals: `gh`'s certificate, an agent's own https, installing glab outside Docker, kits'
texts, ssh.

## Decisions

### D1. glab's configuration is a file of the agent's own folder

`<agent config>/glab/config.yml`, folder 700, file 600 (glab refuses another mode: `has the
permissions 644, but glab requires 600`), written whole by a rename at every launch, as the
author files; `GLAB_CONFIG_DIR` names the folder. It is written even with no GitLab saved
(no `hosts`), so the human's own glab configuration is never read. Keys: `check_update:
false`, `telemetry: false` (glab sends usage to the GitLab instance otherwise),
`git_protocol: https`, `no_prompt: true`, and per server `hosts.<key>` with `api_protocol`
(`https`/`http`), `subfolder` (the address's path without `/`, only when there is one),
`ca_cert` (the absolute path of `ca.pem`, only when the file exists), `custom_headers:
[{name: PRIVATE-TOKEN, valueFromCommand: <command>}]`. `<key>` is the server's
`host[:port]` (`state.GitServer.host`). Written with `yaml.safe_dump` (PyYAML is already a dependency of
LADO's); the command is one `shlex.join` string (glab splits it as a shell does: checked with
a quoted `-c` argument).

### D2. The header's command is git's helper in a `token` mode

`lado.git_credential --home H --server ID token`: prints the token and a newline, exit 0;
with none it can read, stdout empty, `lado: no token for <address>; add it again: lado
git-server add <address> --token` on stderr (`--address` given as for git), exit 1. Same
reader (`read_token`), so the link refusal and size limit hold. LADO's Python by absolute
path (`interpreter.run_module`), no lado.db, no `lado` on PATH. glab sends no header when the
command fails and shows nothing: the agent's line (D4) and git's own helper message are where
the human learns it.

### D3. GitLab variables of the layers are dropped

`agent_env.GITLAB_VARIABLES = ("GITLAB_TOKEN", "GITLAB_ACCESS_TOKEN", "GITLAB_HOST",
"GITLAB_URI", "GL_HOST", "GLAB_CONFIG_DIR")`, dropped in `merge` beside `GITHUB_VARIABLES`.
`GITLAB_HOST` would make glab refuse a repository whose remote is another host; the tokens
would reach every host of the configuration (checked: LADO's header still wins for a saved
host, but a token of the shell must not reach a listed server unasked). Generic names glab
also reads (`OAUTH_TOKEN`, `CA_CERT`, `API_PROTOCOL`) are left: they belong to other tools
too, and LADO's per-host entries win over them for a saved server. `for_git` (LADO's own git)
does not run glab and is unchanged.

### D4. The agent's line is part of its instructions

Built at the spawn (`runtime` where `CONTAINER_INSTRUCTIONS` is added), from
`remote(agent.cwd)` and `git_servers.server_for`, by `git_servers.tool_line(server, env)`;
English, as all of LADO's instructions. Texts:

- ok: ``The repository's origin is on {title} ({host}), a git server LADO signs you in to:
  use `{tool}` for its {changes}; it is logged in already.``
- missing: ``… a git server LADO signs you in to, but its tool `{tool}` is not installed
  here, so you cannot open its {changes}; tell the human.``
- old: ``… but `{tool}` here is {version}, older than {oldest}, which LADO needs to sign it
  in, so you cannot open its {changes}; tell the human.``
- no token: ``… but LADO has no token for it, so `{tool}` is not logged in and git cannot
  push there; tell the human.``
- `gh` and a certificate: the ok line, then `` `gh` does not get the server's certificate and
  cannot reach it; git can.``

`{host}` is the server's `host[:port]`. The line is fixed for the agent's life, as its tokens
are; a server added later reaches agents started from then on (RESTART's words already say
so).

### D5. The kind names its oldest tool version and its word

`Kind.tool_oldest: str = ""` (`"1.114.0"` for GitLab, none for GitHub) and `Kind.changes:
str` (`"merge requests"`, `"pull requests"`). The version is read with `<tool> --version`
and the first `\d+\.\d+\.\d+` (glab: `glab 1.130.0 (hash)`; gh: `gh version 2.x.y (date)`),
once per launch and only for the origin's saved server, cut at doctor's `VERSION_TIMEOUT`; a
version it cannot read counts as fit (the tool runs; a guess would be a false alarm).

### D6. A missing or old tool is a launch warning and a doctor line

The launch's warning (`_git_server_warnings`) and the agent's line come from one check
(`git_servers.tool_state(kind, env) -> (found, version)`), so they never disagree. doctor
gets one line per distinct tool of the saved servers' kinds, by the agents' PATH
(`agent_env` layers, as the providers' lines), named by the tool, `ok` with the
`--version` line, `warn` missing or old with the hint `install glab 1.114.0 or newer` /
`update glab`; never `fail`.

### D7. The human's own glab login is named, not used

doctor's `GitLab login outside LADO`: `warn` for each dropped variable of a layer or a
project's secret (as `github_takeover.unused` names GitHub's, by name only); `info` when the
human's own glab configuration (glab's `config path` without LADO's `GLAB_CONFIG_DIR`, read
as text) has a host with a non-empty `token:` or `use_keyring: true`. No glab call against a
server, no network. No takeover of that login: a GitLab is added in Settings.

### D8. glab in the image

`ARG GLAB_VERSION=1.130.0` and `ARG GLAB_SHA256_AMD64`/`_ARM64` (from the release's
`checksums.txt`: `ce06313b…d822c`, `062d53ac…22767`), `TARGETARCH` picks one; the archive
from GitLab's package registry of `gitlab-org/cli`, `sha256sum -c`, `bin/glab` into
`/opt/tools/bin` (on PATH before mise's shims, as openspec), `glab --version` at build. One
layer. `GLAB_CHECK_UPDATE=false`, `GLAB_SEND_TELEMETRY=false` in `ENV` and `profile.sh`, for
`docker exec` too. 1.130.0, nine days old at design, not 1.131.0 (two days). The binary is
56.3 MB on amd64, 52.6 MB on arm64, statically linked; the container test measures the
growth against the image without it.

### D9. Tests

Unit (`tests/test_git_servers.py`, `test_git_credential.py`, `test_agent_env.py`,
`test_doctor.py`, `test_runtime_git_servers.py`, `test_docker.py`): the config's text per
case, the helper's token mode, the dropped variables, the line's five texts, the warnings,
doctor's lines, the pins. Integration with the fake agent (`tests/integration/
test_git_server_host_tool.py`): a session on a repository of the fake GitLab server
(`tests/fake_git_server.py`) gets the line naming `glab`, github.com's `gh`, another host
none, a fake `glab` script missing or reporting 1.80.0 gives the warning; when a real `glab`
is on PATH the same test runs `glab auth status`/`glab api user` with the fake agent's
environment against the fake server (skipped otherwise; the container test runs it always).
Container (`tests/container/test_glab.py`): version, auth status against the fake server under
a test CA, another host refused, `~/.config/glab-cli` and `~/.gitconfig` unchanged, the size.
Live (`tests/live/test_live.py`): Claude Code and Codex agents push to a saved fake server.

### D11. A GitLab token without `api` is told it leaves glab without merge requests

GitLab's `read_api` reads the API only: `glab mr create` with a token of `read_repository,
write_repository, read_api` gets 403; `api` holds all of them. `Kind.tool_needs` (`("api",)`
for GitLab, `()` for GitHub, whose `repo` opens pull requests) is checked by the same
`granted`/`missing` logic as `needs`, only when the server told the rights. The outcome stays
`ok` (the server works for git, the login is saved, the page's note and the exit status are
as today), its line gets `; glab cannot open merge requests: the token lacks api` before the
full stop; doctor's line of that server is `warn` with the hint `replace it with a token with
the scope api: lado git-server add <address> --token`. GitLab's `scopes` text (the token
page's hint and the replace hint) becomes `scope api`. The human chose this (#7541).

### D10. Versions

A feature in 0.48.0 (unreleased, already a minor bump); no schema change, no new MCP tool or
CLI command.
