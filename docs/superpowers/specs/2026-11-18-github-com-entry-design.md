# github.com in the list of git servers: design

Task: LAD-299. Change: `openspec/changes/github-com-entry/` (proposal, deltas of
`git-servers`, `git-servers-page`, `doctor`, `agent-variables`, `container`,
`session-clone`, `projects`, and `design.md` with decisions D1–D11). Mockup: the run's
`mockup-github-server.html` (three screens), after the human's answers #7395 and #7403:
github.com is an entry like any other, and the page shows nothing of its own for it.

## What the human sees

### After the update

The first `lado ui`, `lado start`, restart after `lado update` or container start of this
version takes the GitHub login over, before any agent starts:

```
$ lado ui
LADO took your GitHub login (GH_TOKEN in /run/secrets) into Settings → Git servers: github.com, signed in as octo.
LADO UI: http://127.0.0.1:8765/…
```

- The source is the first that holds: `GH_TOKEN in <folder>` / `GITHUB_TOKEN in <folder>`
  (the outside folder; `secrets/` in the page's words in the image), `GH_TOKEN of your
  shell`, `the GitHub CLI's login` (`gh auth token --hostname github.com`).
- GitHub does not answer in 5 s: `…: github.com, not checked yet.`; the row says `⚠ not
  checked`, Check later saves the login.
- GitHub refuses the token: `GitHub refused the token of <source>: add github.com in
  Settings → Git servers.`; no entry.
- Nothing found: no line. A UI server writes the line to its log (`lado server` output).
- A github.com entry saved before: left as it is, no line.
- `gh auth token` failing otherwise (a Mac keychain closed to an ssh session, a crash, more
  than 10 s): no line, nothing recorded; the next start tries again; doctor says it is
  pending and why.

Nothing outside LADO changes: `secrets/GH_TOKEN`, the shell's variables, `gh`'s login and a
project's secret stay, for a rollback and for the human's own terminal.

### lado git-server

```
$ lado git-server add github.com --token
Token: ********
GitHub, signed in as octo
Saved git server https://github.com.
Agents started from now on reach it; restart running agents to give it to them.

$ lado git-server list
https://github.com             GitHub  octo         yes  -
https://gitlab.corp.example    GitLab  a.sample     yes  -

$ lado git-server remove github.com
Removed git server https://github.com.
```

`www.github.com` and `api.github.com` are github.com; `github.com:8443` or
`github.com/acme` are refused (`github.com is signed in to at https://github.com`);
`--kind` with github.com is refused. `check` and `author` as for any server.

### lado doctor

```
[ok  ] git server https://github.com: Works: signed in as octo, may clone and push.
[info] GitHub login: taken over from GH_TOKEN in /run/secrets on 2026-11-18
[warn] GitHub login outside LADO: GH_TOKEN in /run/secrets, GH_TOKEN of project shop set but not used: github.com takes its token from Settings → Git servers
[info] GitHub login outside LADO: the GitHub CLI's own login is not used by agents
```

Before the takeover ran: `[info] GitHub login: taken over at the next lado ui or lado start`
(after a failed `gh`: `…; the last try could not read the GitHub CLI's login: <gh's line>`).
A lado.db locked for longer than 10 s: `[warn] git servers: not checked: lado.db is busy`.

### lado project set

```
$ printf x | lado project set shop GH_TOKEN --secret
Set secret GH_TOKEN of project shop.
GH_TOKEN is not given to agents: github.com and GitHub Enterprise take their token from Settings → Git servers.
```

### Settings → Git servers

As the mockup (screens 1–3): github.com is one more row of Servers, nothing of its own.

- Taken over: `https://github.com` `GitHub` `signed in as <login>` (or `⚠ not checked`) in
  Servers, sorted as the others; its panel is any server's (Sign-in with `Check` and
  `Replace token`, Commit author, `Remove server` with its question).
- No line on the page about the takeover, an outside `GH_TOKEN`, `gh`'s login or a refused
  takeover; no "not signed in" state: without an entry github.com is not listed (#7403).
- `+ Add server` with `github.com` (or `www.`/`api.`): `GitHub answers.` (the check without
  the token asks `https://api.github.com/user`, whose 401 is GitHub's), Token's link
  `https://github.com/settings/tokens` with `scope repo`; saved: `✓ Saved: GitHub, signed in
  as <login>.`. `github.com:8443` or `github.com/acme` are refused under Address with the
  command's line.
- Servers' ⓘ: "Your GitLab, gitlab.com, GitHub or GitHub Enterprise: agents clone and push
  there, and run gh, with the token you give. Running agents get a change after they
  restart."
- `?add=github.com` (a clone note's button) opens the Add form with `https://github.com`.
- The author's `Edit` and `Set author` are off while its `Remove` or `Undo` asks.

### Clone hints

- github.com saved, refused: as any saved server, two lines: `Check the git server:` `lado
  git-server check https://github.com`; `If its token expired or was revoked, replace it:`
  `lado git-server add https://github.com --token`.
- github.com not saved, `login_needed`/`access_denied`: as any unsaved host, `Add it as a
  git server with a token:` `lado git-server add https://github.com --token`; the UI's note
  `Add github.com as a git server with a token: LADO and its agents then sign in to it.`
  with `Add git server ↗`.
- `not_found` without an entry: no hint (as any unsaved host).

### Agents

- Every agent and LADO's own git: no `GH_TOKEN`, `GITHUB_TOKEN`, `GH_ENTERPRISE_TOKEN`,
  `GITHUB_ENTERPRISE_TOKEN`, `GH_HOST`, `GH_CONFIG_DIR` from any layer.
- `GH_CONFIG_DIR=<agent config folder>/gh` (LADO's own git: `<LADO_HOME>/gh`), made empty.
- `GH_TOKEN` = github.com's token when saved.
- GitHub Enterprise: `GH_ENTERPRISE_TOKEN` of the server of the session repository's
  `origin`, else of the only one saved; `GH_HOST` for the repository's server only.
- git for github.com: LADO's helper, as for any saved server (the empty helper first).

### Docker

- `docker/Dockerfile`: the two `git config --system credential.https://github.com.helper`
  lines go; its header and `compose.yaml`'s say "GitHub and your other git servers:
  Settings → Git servers (or `lado git-server add`)", keep the secrets folder for other
  variables (example `YOUGILE_API_KEY`), and name neither `GH_TOKEN` nor `gh auth login`.
- `install.sh`'s ssh line: `(https and the git servers of Settings → Git servers still
  work)`.

## Tests per requirement

| Requirement (capability) | Layer | Tests |
|---|---|---|
| github.com is a git server like any other (git-servers) | unit, integration | `test_git_servers.py`: add/remove/list/check github.com through `ConnectProxy`, www./api. taken, port/path/--kind refused; `test_cli.py` |
| The kind of a server is told by its API | unit | `test_git_kinds.py`: github.com request is `https://api.github.com/user`, GHE `/api/v3/user`; one request for github.com |
| The GitHub login is taken over once | unit, integration | `test_github_takeover.py`; integration `test_github_takeover.py` (below) |
| The takeover takes the token agents used | unit | each source in order, the layer named, `gh` stub printing a token, 401, no answer, none |
| A takeover that could not read gh's login runs again | unit | `gh` stub exiting 1 with a keychain line, and sleeping past 10 s: no row, next run takes it |
| The takeover says what it did | unit | the line of `lado start` / `lado ui`, the server's log, the refused line |
| Agents get no GitHub variable from outside LADO | unit, integration | `test_agent_env.py`, `test_runtime.py`: each name dropped from each layer, `for_git` too; integration: the fake agent's environment |
| gh gets the token of the github.com entry | unit, integration, container | integration: `gh` stub records `GH_TOKEN`; container: real `gh auth status` against the fake API through the proxy |
| gh gets the token of a GitHub Enterprise server | unit, integration | origin on a GHE, one GHE, two GHE neither; integration: `gh` stub → `POST repos/team/app/pulls` reaches the fake API with token and host |
| The schema keeps the takeover's record | unit, integration | `test_state.py` migration 42→43 and the copy; `agent_helpers.previous_schema`; `test_update_process.py` rollback |
| A git server's token… (GitHub's in the launch file) | integration | no file under `LADO_HOME` but the token file holds the token after a launch |
| github.com is listed and added as any server (git-servers-page) | vitest, UI e2e | `GitServers.test.tsx`; `tests/ui/test_git_servers_section.py`: github.com in Servers, Check, Commit author, Remove, Add with `github.com` — fake API, no network |
| The add form… (github.com scenario) | vitest, UI e2e | `GitHub answers.`, the token page link |
| The author's Remove and Undo are off… (Edit, Set author) | vitest | |
| lado doctor names the GitHub login outside LADO / the takeover / a busy lado.db | unit | `test_doctor.py` |
| agent-variables (examples moved off GH_TOKEN; GitHub's token from no layer) | unit, integration | existing tests renamed to `YOUGILE_API_KEY` / `GIT_SSH_COMMAND`; a new test for `GH_TOKEN` from no layer |
| container: no helper for github.com; headers | container, unit | `tests/container/`: `git credential fill` with a `gh` login on the home volume prints no password; `tests/test_docker.py` headers |
| session-clone hints | unit, vitest | `test_clone.py`: github.com saved/unsaved, two-line hint, host with port, kit's `explain`; the note's `?add=github.com` |
| projects: a GitHub variable is said to be unused | unit | `test_cli.py` project set |

### The integration test of the update (the brief's)

`tests/integration/test_github_takeover.py`, fake agent, `tests/fake_git_server.py` behind
`ConnectProxy` as `github.com` and the fake API as `api.github.com` (a test CA), a stub `gh`
on the agents' PATH that answers `auth token` from its own `hosts.yml` and records its
environment and arguments for every other call:

1. `GH_TOKEN` in the outside folder, schema 42 left by `previous_schema`: the first launch
   takes it over (entry, login, the record); `lado git-server check github.com` works;
   the agent clones `https://github.com/team/app`, commits, pushes (the server saw the
   entry's token), runs `gh api user` (stub saw `GH_TOKEN` = the entry's, its own
   `GH_CONFIG_DIR`).
2. The outside file then changed, then removed: a new agent still pushes with the entry's
   token and its `gh` sees it; doctor's `GitHub login outside LADO` line follows the file.
3. A second `LADO_HOME`: `gh`'s login only (stub `hosts.yml`): taken over once as `the
   GitHub CLI's login`; after `lado git-server remove github.com` and a restart, nothing is
   taken again and the agent's `gh` has no token.
4. A project's `GH_TOKEN` secret: the project's agent has no `GH_TOKEN` but the entry's;
   doctor names it.
5. No entry, no login: a clone from github.com asks for a login with `lado git-server add
   https://github.com --token`; the agent has no `GH_TOKEN`.
6. GitHub Enterprise `https://ghe.test:8443` saved, the session's repository on it: the
   agent's `gh api -X POST repos/team/app/pulls` reaches the fake API with the token and
   `GH_HOST=ghe.test:8443`.

The rollback: `test_update_process.py` gains the takeover in its schema-restore test: after
`lado update <older>` the restored lado.db has no github.com row, the outside file is there,
and the older LADO's session resumes.

## Docs

- `docs/cli.md`: `lado git-server` (github.com; the takeover; www./api.), `lado doctor`
  (the GitHub lines, busy lado.db), `lado project set` (the warning), the clone hints.
- `docs/design/ui.md` § Git servers: github.com as one more server (the Add form's
  github.com, Servers' ⓘ); the author's buttons off while asking.
- `docs/design/modules.md`: `github_takeover.py`; `git_servers` (github.com, `gh_variables`);
  `agent_env` (the GitHub names dropped).
- `docs/install.md`: GitHub login (was `printf %s "$(gh auth token)" > secrets/GH_TOKEN`,
  the project `GH_TOKEN`): Settings → Git servers, the takeover once, then not used, and
  that only the command's line and `lado doctor` say so; going back (the copy of schema
  42, nothing outside removed).
- `docs/design/projects.md`: a project's `GH_TOKEN` no longer reaches agents.
- `docker/` comments (D6). AGENTS.md: the module line. CHANGELOG.md 0.48.0: one New entry
  "github.com in Settings → Git servers", and the git servers entry no longer says GitHub
  Enterprise only.

## Manual check (in the pull request from the start)

Steps marked **[human]** need the human's token or hand; the agent running the check never
sees a token.

0. `env | grep -E '^(GIT_|GH_|LADO_)'`; `unset` what a previous check left. Snapshot:
   `git config --global --list --show-origin > "$TMPDIR/gitconfig-before.txt" 2>&1`.
1. A fresh clone in a temp folder: `git clone https://github.com/ladohq/lado "$D/lado" && cd
   "$D/lado" && git checkout <branch>`; `uv sync`; `make web`.
2. `export LADO_HOME="$D/home" LADO_TMUX_SOCKET=lado-check-299`; first run the released
   0.47.0 there (`uvx lado@0.47.0 doctor`) so lado.db is at its schema.
3. **[human]** `export GH_TOKEN=<your token>` in the shell that starts LADO (or keep
   `gh auth login` on this machine).
4. `uv run lado ui` — expect the line `LADO took your GitHub login (GH_TOKEN of your
   shell) …: github.com, signed in as <you>.`; Settings → Git servers lists
   `https://github.com` `GitHub` `signed in as <you>` like the other servers, with no other
   line about it. `uv run lado doctor`: `GitHub login: taken over from …` and `GitHub login
   outside LADO: GH_TOKEN of your shell set but not used …`.
5. Check on the row → `Works: signed in as <you>, may clone and push.`
6. `uv run lado start <a test repo URL of yours> --provider <CLI>`; ask the agent to push a
   branch and open a pull request with `gh pr create` — it works; the PR is yours.
7. **[human]** `export GH_TOKEN=garbage` (or `unset GH_TOKEN`), restart the session: the agent
   still pushes and `gh pr view` works; `uv run lado doctor` names the unused `GH_TOKEN`.
8. Remove server on the github.com row, restart the session: the agent's `gh auth status`
   says not logged in, github.com is not listed, and a restart of `lado ui` takes nothing
   over again. **[human]** `+ Add server` with `github.com` and the token: `GitHub
   answers.`, saved, signed in.
9. Rollback: `uv run lado server stop; lado stop --all`; `cd "$LADO_HOME" && rm -f
   lado.db-wal lado.db-shm && cp backups/lado.db.schema-<N> lado.db`; `uvx lado@0.47.0 ui`
   with `LADO_HOME` and the socket as above: no github.com row, the agent's push works with
   the old `GH_TOKEN`/`gh` login as before.
10. `git config --global --list --show-origin > "$TMPDIR/gitconfig-after.txt" 2>&1`; `diff`
    the two snapshots: no change. Remove `$D`.

A short repeat after fixes names the steps by these numbers.

Not verified: the GitHub Enterprise hint of the kind without a token on a real GitHub
Enterprise (unless one is at hand); `gh pr create` (GraphQL) on GitHub Enterprise (only
the REST call against the fake API).
