# glab for the agents and the line about the repository's server: Implementation Plan

**Goal:** LADO's image carries glab; each agent's glab is signed in to the saved GitLab
servers with their tokens and certificates, per host; every agent is told its repository's
server and tool; a missing or old tool, the GitLab variables and the human's own glab login
are named; a live test pushes through a saved server.

**Architecture:** the kind modules name the tool's oldest version, its word and the right
it needs (D5, D11); `git_credential` gets a `token` mode (D2); `git_servers` writes glab's
`config.yml` (D1), checks the tool (D6) and builds the agent's line (D4); `agent_env` drops
the GitLab variables (D3); `runtime` lays `GLAB_CONFIG_DIR`, adds the line to the
instructions and the warning to the launch notes; `doctor` gets the tool and the outside
login lines (D6, D7); the Dockerfile installs glab (D8); tests at each layer (D9).

**Tech Stack:** Python 3.10+ standard library, pytest (`-n auto`, `-m integration`,
`-m container`, `-m live`), Docker, glab 1.130.0, git ≥ 2.31, openssl for the tests' CA.

**Spec:** `openspec/changes/git-server-host-tool/` and
`docs/superpowers/specs/2026-11-19-git-server-host-tool-design.md` (texts, the table of tests
per requirement, docs, the manual check).

## Global Constraints

- No token in any file but `<LADO_HOME>/git-servers/<id>/token`: not in glab's
  `config.yml`, not in a log, not on a `ps` line (the helper gets ids only).
- glab's `config.yml` mode 600, its folder 700 (glab refuses another mode).
- The human's own `~/.config/glab-cli`, `~/.gitconfig` and system configs are never read for
  use, never written (doctor reads glab's file as text only, D7).
- `glab` oldest: 1.114.0. Image pin: 1.130.0 with the two SHA-256 of D8. Growth ≤ 60 MB.
- A missing or old tool never refuses a launch and never fails doctor.
- The texts are the deltas' and the design doc's, word for word; another wording needs a
  reason in the build report.
- Tests use no network: the fake git server under a test CA; a real glab only when it is on
  PATH (integration) or in the image (container).
- Nothing in code, docs, specs or the UI names the epic's stages or `docs/epics/`.
- CHANGELOG: extend 0.48.0 (unreleased). No schema change.
- The pull request carries the design doc's manual check from its first push.

## Review Focus

1. A server whose address has a path (`https://host/gitlab`): `subfolder` must be the path
   without slashes, and `server_for` must still find it for a remote under that path.
   Test in Task 2.
2. A server on a non-default port and an IPv6 host: the host key is `host:port` /
   `[::1]:8443` as `state.GitServer.host` has it. Test in Task 2 (port; IPv6 as text only).
3. A repository whose `origin` is an ssh address of a saved server (`git@host:team/app`):
   the line still names it (server_for knows the rewrite). Test in Task 4.
4. Two GitLab servers and a token file missing for one: the other still works, the line of
   a session on the first says `no token`. Test in Tasks 2 and 4.
5. A `glab --version` that hangs or prints no version: cut at doctor's `VERSION_TIMEOUT`,
   counted as fit, no false alarm. Test in Task 3.

## Tasks

### Task 1: the kinds and the helper's token mode (D2, D5, D11)

Files: `src/lado/git_kinds/base.py`, `github.py`, `gitlab.py`, `src/lado/git_credential.py`,
`tests/test_git_kinds.py`, `tests/test_git_credential.py`.

Interfaces — produces: `Kind.tool_oldest: str` (`"1.114.0"`, `""`), `Kind.changes: str`
(`"merge requests"`, `"pull requests"`), `Kind.tool_needs: tuple[str, ...]` (`("api",)`,
`()`); `python -m lado.git_credential --home H --server ID --user U --address R token`.

- [ ] Test: each kind's three fields; the token mode prints `<token>\n` and exits 0; without
  a file, with a link, with an empty file: stdout empty, stderr `lado: no token for <R>; add
  it again: lado git-server add <R> --token`, exit 1; `get` unchanged.
- [ ] Implement; `make lint`, `uv run pytest -n0 tests/test_git_kinds.py
  tests/test_git_credential.py`; commit.

### Task 2: glab's configuration (D1)

Files: `src/lado/git_servers.py` (`glab_command(server) -> str`, `glab_config(servers) ->
str`, `glab_variables(servers, folder: Path) -> dict[str, str]`), `tests/test_git_servers.py`.

Interfaces — consumes Task 1's token mode; produces `glab_variables` returning
`{"GLAB_CONFIG_DIR": str(folder)}` after writing `folder/config.yml`.

- [ ] Test: the text for one GitLab (https, no path, no certificate), with `ca.pem`, with a
  path (`subfolder: "gitlab"`), on port 8443 (`"git.example:8443"`), http (`api_protocol:
  "http"`), two GitLabs, GitHub servers only (`hosts: {}`), none; folder 700, file 600,
  replaced whole by a rename (a previous file with a token line is gone), no token in the
  text; the command's `shlex.split` is LADO's Python, the loader, the module and ids only.
- [ ] Test: parse the written text with `yaml.safe_load` and compare with the dict
  expected (the writer is `yaml.safe_dump`).
- [ ] Implement; commit.

### Task 3: the tool check and the line (D4, D6)

Files: `src/lado/git_servers.py` (`ToolState(found: bool, version: str, too_old: bool)`,
`tool_state(kind, env) -> ToolState`, `tool_line(server, state) -> str`,
`tool_warning(server, state) -> str | None`), `tests/test_git_servers.py`.

- [ ] Test: `tool_state` with no tool on PATH, a script printing `glab 1.80.0 (x)`, `glab
  1.130.0 (y)`, `gh version 2.83.0 (2026-10-01)`, a script that sleeps past the timeout
  (fit, version ""), one printing nothing.
- [ ] Test: the five lines of D4 and the warnings of the design doc, word for word; GitHub
  with `ca.pem` adds the `gh` sentence; no token (no file) gives the no-token line.
- [ ] Implement; commit.

### Task 4: the launch (D3, D4, D6)

Files: `src/lado/agent_env.py` (`GITLAB_VARIABLES`, dropped in `merge`),
`src/lado/runtime.py` (`GLAB_CONFIG = "glab"`; `_ours` adds `glab_variables`; the line in
the spec's instructions; `_git_server_warnings` adds `tool_warning` for the origin's server),
`tests/test_agent_env.py`, `tests/test_runtime_git_servers.py`.

- [ ] Test: `merge` drops each GitLab variable from each layer; `OAUTH_TOKEN` and `CA_CERT`
  stay.
- [ ] Test: an agent spec's prompt holds the GitLab line for an https origin and for an ssh
  origin of the saved server, the github.com line, none for another host and none without an
  origin; `_ours` has `GLAB_CONFIG_DIR` under the agent's config folder; the launch notes hold
  the missing and old warnings and the agent still starts.
- [ ] Implement; commit.

### Task 5: doctor (D6, D7)

Files: `src/lado/doctor.py` (`check_host_tools()`, `check_gitlab_login()`),
`src/lado/github_takeover.py` (`unused` takes the names), `tests/test_doctor.py`.

- [ ] Test: tool lines for a GitLab saved (ok, missing, old), only github.com (a `gh` line,
  no `glab`), none saved (no line); never FAIL, exit status unchanged.
- [ ] Test: `GitLab login outside LADO` warn for the shell, `/run/secrets`, a project
  secret; info for a glab config with `token: glpat-…` and with `use_keyring: true`, under
  `XDG_CONFIG_HOME` and the default path; none otherwise; no value printed.
- [ ] Implement; commit.

### Task 6: the token's right for merge requests (D11)

Files: `src/lado/git_servers.py` (the check's ok line), `src/lado/doctor.py` (its level),
`src/lado/git_kinds/gitlab.py` (`scopes`), `tests/test_git_servers.py`, `tests/test_doctor.py`,
`tests/test_cli_git_server.py`, `tests/ui/test_git_servers_section.py:176` and
`web/src/GitServers.test.tsx:18,567` (the scopes text is `scope api`).

- [ ] Test: a GitLab token with `read_repository, write_repository, read_api`: `Works:
  GitLab, signed in as ann, may clone and push; glab cannot open merge requests: the token
  lacks api.`, exit 0, saved; with `api`: the line as today; rights not told: as today;
  doctor `warn` with the hint `replace it with a token with the scope api: lado git-server
  add <address> --token`.
- [ ] Implement; the kind's `scopes` text becomes `scope api`; `make web` (vitest) and
  `uv run pytest -m ui tests/ui/test_git_servers_section.py`; commit.

### Task 7: integration with the fake agent (D9)

Files: `tests/integration/test_git_server_host_tool.py` (new).

- [ ] Test: a session on a repository of `fake_git_server.Server` saved as GitLab: the fake
  agent's prompt holds the GitLab line, its env has `GLAB_CONFIG_DIR` and no `GITLAB_TOKEN`
  (set in the login shell layer by the test); a fake `glab` script on PATH printing `glab
  1.80.0 (x)` gives the old warning in `lado start`'s output; with no glab, the missing one;
  github.com saved and a github.com origin gives the `gh` line; another host none.
- [ ] Test (skipped without `glab` ≥ 1.114.0 on PATH): `glab auth status` and `glab api user`
  in the agent's environment reach the fake server with the token (its `requests`), over TLS
  with `ca.pem`; a second fake server under the same CA, not saved with it, fails.
- [ ] `uv run pytest -m integration -n auto tests/integration/test_git_server_host_tool.py`;
  commit.

### Task 8: the image (D8)

Files: `docker/Dockerfile`, `docker/profile.sh`, `tests/test_docker.py`,
`tests/container/test_glab.py` (new), the Dockerfile's header comment.

- [ ] Test (unit): `ARG GLAB_VERSION` exact, both SHA-256 64 hex, the install a `RUN` of its
  own with `sha256sum -c` and `glab --version`; `GLAB_CHECK_UPDATE=false` and
  `GLAB_SEND_TELEMETRY=false` in `ENV` and `profile.sh`.
- [ ] Test (container): `glab --version` is the pin; a saved GitLab (fake server in the
  test process, reached from the container as the other container tests reach theirs) under
  a test CA with `ca.pem`: an agent-like shell with LADO's launch variables runs `glab auth
  status` logged in; another host fails; `~/.config/glab-cli` absent and `~/.gitconfig`
  unchanged; the image's size minus the same build without the glab layer ≤ 60 MB (from
  `docker image inspect`, or the layer's size in `docker history`).
- [ ] Implement; `make docker && uv run pytest -m container -n0
  tests/container/test_glab.py`; commit.

### Task 9: the live test (D9)

Files: `tests/live/test_live.py`.

- [ ] Test `test_an_agent_pushes_through_a_saved_git_server` (Claude Code and Codex by the
  live provider fixture): the fake server over TLS with a test CA, saved as GitLab with its
  token and `ca.pem`, an empty repository as the session repository's `origin`; a worker adds
  `pushed.txt`, commits and runs `git push origin HEAD`; the server holds the commit, its
  receive-pack carried the token, and no request went without it after the first 401.
- [ ] Written, not run: say so in the build report (`make test-live` on the RC).
- [ ] Commit.

### Task 10: docs and CHANGELOG

Files: `docs/install.md`, `docs/cli.md`, `docs/design/agents.md`, `docs/design/modules.md`,
`docs/testing.md`, `CHANGELOG.md`.

- [ ] Write the parts the design doc's Docs section names; the GitLab paragraph says to
  choose `api`, that `glab auth status` notes `No token found` (the token comes by header),
  and that outside Docker glab 1.114.0 or newer is installed by the human.
- [ ] `uv run pytest -n0 tests/test_agents_md.py` (AGENTS.md unchanged unless needed);
  commit.

### Task 11: regression

- [ ] `make lint`, `make test`, Task 7's integration file with `-m integration`,
  `openspec validate git-server-host-tool --strict`, `openspec validate --specs --strict`,
  the trial archive in a copy; CI runs the rest (the container tests on amd64 and arm64).
- [ ] The pull request's description carries the manual check of the design doc.
