# Git servers: Implementation Plan

**Goal:** `lado git-server add|list|remove` keeps GitLab and GitHub Enterprise servers with
their tokens; agents and LADO's own git clone and push there over https with no prompt, ssh
forms included; every other host goes as before.

**Architecture:** kinds in `src/lado/git_kinds/`; the address, probe, store, git variables
and old-git check in `src/lado/git_servers.py`; the helper in `src/lado/git_credential.py`;
the table in `state.py`; the variables laid in `runtime._ours` and `agent_env.for_git`; the
command in `cli.py`; the way back in `self_update.py`.

**Tech Stack:** Python 3.10+ (standard library only), pytest (`-n auto`, `-m integration`,
`-m smoke`), the fake agent, `git http-backend`, `openssl` for a test certificate.

**Spec:** `openspec/changes/git-servers/` and
`docs/superpowers/specs/2026-11-15-git-servers-design.md`.

## Global Constraints

- No new dependency, no MCP tool, no server API, no screen. One CLI command, schema 41.
- The global (`~/.gitconfig`) and system git configs are never written; no test may write
  the user's. Tests set `HOME` and `GIT_CONFIG_SYSTEM`/`GIT_CONFIG_GLOBAL` to their own files.
- A token appears in no output, log, error journal, `lado.db`, git config, worktree, or file of
  `LADO_HOME` but its token file: every test that sets one uses a canary value and greps.
- With no server saved, an agent's environment and LADO's git environment are byte for byte
  as before: a test holds it.
- github.com is refused by `add`; the image's `gh` helper for github.com is untouched.
- Nothing in code, docs, specs or output names the work's stages or `docs/epics/`.
- Codex's sandbox: if it blocks the helper or the token file, stop and bring options to the
  human (do not work around it silently).
- The pull request carries the manual check from the start (task 8).

## Review Focus

1. The token escaping: a message built from headers, a traceback with the helper's args, a
   `ps` line (the helper's argv holds no token: only ids), a worktree file. Tests: 1, 4, 6.
2. A host not in the list or an empty list changing behaviour (`GIT_CONFIG_*` appearing, the
   gh helper dropped). Tests: 3, 6.
3. Another helper storing the token (osxkeychain, store). Test: 6.
4. The helper not found without `lado` on PATH, or importing from the agent's cwd. Test: 6.
5. A launch refused for old git when no server is saved. Test: 5.

## Task 1: Kinds and the probe

Layer: unit. Files: `src/lado/git_kinds/{__init__,base,github,gitlab}.py`,
`src/lado/git_servers.py` (address, probe), `src/lado/model_servers.py` (renames of D2),
`tests/fake_git_api.py`, `tests/test_git_kinds.py`, `tests/test_git_servers.py`.

- `tests/fake_git_api.py`: an in-process HTTP(S) server with profiles: GitLab (200 user, 401,
  403 insufficient_scope), GitHub Enterprise (200 user, 401), both, neither (404 / HTML),
  redirect, hanging; records each request with its headers.
- Requirement "The kind of a server is told by its API": each profile's verdict; both
  requests sent at once (the hanging profile on one path does not delay the other's verdict
  beyond 5 s); no request follows a redirect; the token is in `PRIVATE-TOKEN` for GitLab and
  `Authorization: token` for GitHub and in no other header or URL.
- "Each kind of git server is a module of its own": `KINDS` names `github` and `gitlab`; each
  has `git_user`, `tool`, `token_page`.
- "A server that cannot be checked is not saved without --kind": name not found, connection
  refused, timeout, TLS not trusted (a self-signed cert the test does not trust), 401, 403,
  neither, two kinds — each line and hint of the design doc's table.
- "A git server's address": no scheme, trailing `/`, path kept, default port dropped,
  userinfo/query/fragment/ssh refused, `http://` warning text; "github.com is not added".
- `model_servers` regression: `uv run pytest -n auto tests/test_model_servers.py` green
  after the renames.

## Task 2: The store and the migration

Layer: unit. Files: `src/lado/state.py`, `src/lado/git_servers.py` (store),
`tests/agent_helpers.py`, `tests/test_state.py`, `tests/test_git_servers.py`.

- "The saved git servers are kept in lado.db": migration 40→41 (`previous_schema` then
  `state.connect`), no server, sessions/agents/model servers unchanged; `SCHEMA_VERSION = 41`.
- "A git server's token is asked and kept in its own file": modes 700/600 with umask 0,
  a link on the way refused, the canary nowhere else under `LADO_HOME`.
- "One git server per host": a second save of the same host keeps the id and replaces the
  token; a failed row write leaves no folder for a new server, the old token for a replaced
  one.
- "lado git-server remove removes a server and its token": row and folder gone.

## Task 3: The git variables and the helper

Layer: unit (the variables); unit with a real `git credential fill` subprocess (the helper:
cheap, no tmux). Files: `src/lado/git_servers.py` (`variables`, `check_git`),
`src/lado/git_credential.py`, `tests/test_git_credential.py`, `tests/test_git_servers.py`.

- "LADO's git variables only add to the agent's": no server → `{}`; an existing
  `GIT_CONFIG_COUNT=1` kept, LADO's from index 1; a non-number count.
- "Agents and LADO's own git reach a listed server over https with its token": the order of
  the five entries per server; `git credential fill` with the variables prints the canary;
  `git credential approve` with a temp `HOME` whose `.gitconfig` has `credential.helper=store`
  writes no `.git-credentials`.
- "ssh addresses of a listed server go over https": with the variables,
  `git ls-remote --get-url <address>` (no network) prints the https URL for the scp form,
  `ssh://git@host/`, `ssh://git@host:22/` and a path-prefixed root; `ssh://git@host:2222/`
  is printed unchanged.
- "LADO's credential helper": run with a cwd holding a `lado/` package and a `json.py` (the
  helper still works: no cwd import); `store`/`erase` print nothing; it never opens `lado.db`
  (a `LADO_HOME` without one).
- "The helper stops git when it has no token": no file → `quit=1`, the stderr line, git exit
  128 with no prompt (`GIT_TERMINAL_PROMPT` unset, stdin not a terminal).

## Task 4: The command

Layer: unit (`tests/test_cli_git_server.py`), the fake API. Files: `src/lado/cli.py`.

- "lado git-server add checks a server and saves it": GitLab and GitHub outputs, exit 0, the
  restart line.
- "--kind saves a server that could not be checked": warning, `not checked` in list; `--kind`
  against the answer refused; 401 with `--kind` refused.
- "The token is asked, never taken from the command line": `--token glpat-abc` refused without
  the value in output; empty stdin refused; parser errors name no argv word.
- "lado git-server list shows the saved servers without asking them": columns, `not checked`,
  `no` without the token file, the empty text; no request reaches the fake API.
- "lado git-server remove …": by address with or without scheme; unknown refused exit 1.
- "git older than 2.31 is refused where a git server is needed" (add): a fake `git` on PATH
  printing `git version 2.30.2`.

## Task 5: Agents and LADO's own git

Layer: unit for the wiring; integration in task 6. Files: `src/lado/runtime.py` (`_ours`, the
pre-launch check), `src/lado/agent_env.py` (`for_git(project, remote)`),
`src/lado/gitcache.py`, `src/lado/clone.py`, `src/lado/doctor.py`,
`tests/test_runtime*.py`, `tests/test_agent_env.py`, `tests/test_gitcache.py`,
`tests/test_doctor.py`.

- The launch env has the variables when a server is saved, and is equal to before when none
  is (compare with a launch before the change's code path: the dict without `GIT_CONFIG_*`).
- `LADO_LAUNCH_VARS` lists LADO's `GIT_CONFIG_*` names.
- Old git at a launch with a server saved: refused before any tmux call; without a server: no
  `git --version` call at all.
- `for_git` with a remote of a saved host gets the variables; of another host too (the list is
  laid whole), and the old-git refusal only for the saved host.
- doctor (MODIFIED "lado doctor checks git"): the hint names git servers.

## Task 6: End to end with a real https git server

Layer: integration (`-m integration`), the fake agent, real tmux, git, `lado` processes.
Files: `tests/fake_git_server.py`, `tests/integration/test_git_servers.py`.

`tests/fake_git_server.py`: `git http-backend` as CGI behind `http.server` over TLS (a cert by
`openssl req -x509` in the test's folder; skip naming `openssl` when missing), Basic auth
required with the token as password (401 + `WWW-Authenticate` otherwise), a fake
`/api/v4/user`; trusted only through `SSL_CERT_FILE` and `GIT_SSL_CAINFO` of the test's
processes; records each request's user.

Tests (each with its own `LADO_HOME`, `HOME`, `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_SYSTEM`
files whose bytes are compared at the end; the global one has `credential.helper=store`):

1. `lado git-server add https://127.0.0.1:<port> --token` (token piped) → `GitLab, signed in
   as …`; the canary in the token file only (grep of `LADO_HOME`, the worktree, `$HOME`).
2. A session with the fake agent: the agent runs `git clone`, commits, `git push` to the
   server; both succeed; the server saw the token; no prompt (the agent's stdin is a tmux
   pane: a prompt would hang the step past its timeout, so the test sets a short timeout).
3. The same agent: `git ls-remote git@127.0.0.1:team/app.git` and `ssh://git@127.0.0.1/…`
   reach the https server (its request log).
4. LADO's own git: `lado start https://127.0.0.1:<port>/team/app.git` clones with the token.
5. A host not in the list (a second server on another port, not added): the agent's
   `git ls-remote` fails as without LADO (`terminal prompts disabled` / 401), and the helper
   was not called (the first server's log has no request from it).
6. `lado git-server remove`, then a new agent: no `GIT_CONFIG_*` in its environment, the
   clone fails as for a host not in the list; the agent started before the removal fails with
   the `no token` line.
7. Old git: a `git` wrapper first on the agents' PATH printing 2.30.2 for `--version` → the
   session start is refused naming 2.31.
8. Without `lado` on PATH: the agents' PATH holds git and coreutils only; the clone still
   succeeds.
9. `~/.git-credentials` absent; the global and system config files byte for byte unchanged.

## Task 7: Codex's sandbox and the way back

Layer: smoke (real Codex, no model) and integration (the update process).

- Smoke, `tests/smoke/test_smoke.py` (Codex branch) or a new `tests/smoke/test_git_servers.py`:
  with a saved server and the variables of `git_servers.variables`, `codex sandbox -- git
  credential fill` (cwd a LADO worktree, the agent's `CODEX_HOME` and LADO's profile)
  prints the token; `codex sandbox -- git ls-remote https://127.0.0.1:<port>/team/app.git`
  succeeds where the sandbox allows loopback, else the test records Codex's network refusal
  and passes on the helper check alone. Skip naming why when `codex sandbox -- true` fails.
  If the helper cannot run or read the token inside the sandbox: stop (Global Constraints).
- The way back (requirement of `update-database`): unit in `tests/test_self_update.py` (the
  loss lists `git servers`; the token folders listed; none; unreadable folder), and
  `tests/integration/test_update_process.py` gets a case: schema 41 with a server, `lado update`
  to a schema-40 copy prints the token folder and, after the copy is back, `git_servers` is
  gone and git to that host goes as without LADO.
- Claude Code: the manual check in the pull request (no live test: a real model costs money
  and needs the human's yes).

## Task 8: Docs, manual check, regression

- Docs as the design doc's "Docs" list; CHANGELOG under the next minor `(unreleased)`.
- The pull request's manual check: the branch `feature/lad-289-git-servers`, from a clean
  folder: `env | grep -E '^(GIT_|GH_)'` and `unset` of what is left; `export
  LADO_HOME=$(mktemp -d) LADO_TMUX_SOCKET=lado-check`; `uv run lado git-server add gitlab.com
  --token` (a real gitlab.com token with `read_api`, `read_repository`, `write_repository`) →
  `GitLab, signed in as <you>`; `uv run lado start git@gitlab.com:<you>/<repo>.git` → the
  clone works over https; in a Claude Code agent: `git push` of a branch; `lado git-server
  remove gitlab.com`; `cat ~/.gitconfig` unchanged.
- Regression: `make lint`; `make test`; `uv run pytest -m integration -n auto
  tests/integration/test_git_servers.py tests/integration/test_update_process.py
  tests/integration/test_clone_start.py tests/integration/test_outside_variables.py`;
  `openspec validate git-servers --strict`; the trial archive of `.lado/sdlc.md`; CI's smoke
  cells for task 7.
