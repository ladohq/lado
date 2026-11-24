# Commit authors on three levels: design

Task: LAD-312. Change: `openspec/changes/commit-author-levels/` (proposal, a new capability
`commit-authors`, deltas of `git-servers`, `session-scratch`, `doctor`, `projects`,
`container`, `git-servers-page`, `folder-setup`, `new-session-window`, and `design.md` with decisions D1–D12). The
screens come from the design flow `ui-design/lad-312-ui` (mockup, handoff spec, critique);
this document names what the core gives them and every text outside the UI. The flow's
critic approved its third round with no open findings; its artifacts are
`ui-design/lad-312-ui/mockup.html` (screens A1–A9, B1–B5, C1–C5, D1–D3), `spec` (the
handoff: states, texts, accessible names, focus, responsive), `design-system` and
`critique`.

The human's answers: three levels set in the UI, priority project → git server → LADO's →
git's own, stored in LADO (the task, 24.11.2026); no fields in the New session window, a
link to Settings instead (#8080); the server's and the project's author less visible
(#8080); the UI through the design flow (#8080); LADO's authors win over a repository's own
`.git/config` (#8086).

## What the human sees

### Settings → Git servers

A block **Commit author** above Servers with one row, **LADO's author**: the author, or the
author agents commit as without it (`from your git config`), or that nobody signs and agents
cannot commit; Set author, Edit, Remove with Undo; the variables of the agents' environment
that win over it, named. A server's own author becomes a minor line until set. Exact
screens, texts and states: the flow's spec and mockup, copied into `docs/design/ui.md`'s Git
servers section by the developer.

### The project page

A line **Commit author** under the project's facts: the author agents of each repository
commit as and where it comes from, `Set one for this project`, or the project's own with
Edit and Remove. Screens: the flow's spec, into `docs/design/ui.md`'s Projects section.

### Starting from scratch with nobody known

New session → New empty folder, a plain folder's set-up and a project's Add repository →
From scratch show one note (`AuthorMissing`): agents need a name and email, a link **Set it
in Settings ↗** (`/settings/git-servers?author`, a new tab, the form open) and **Check
again**; the window checks again when it gets the focus back. No fields in the dialog.

### The command line

```
$ lado git-server author --name "Ann Lee" --email ann@example.com
Agents commit as Ann Lee <ann@example.com> where no project or git server has an author of its own.
Agents started from now on commit so; restart running agents to give it to them.

$ lado git-server author
Ann Lee <ann@example.com>

$ lado git-server author --clear
LADO has no commit author now.
LADO has no commit author: agents commit as Alex Home <alex@home.example> from your git config.
Agents started from now on commit so; restart running agents to give it to them.

$ lado git-server author          # nobody anywhere
LADO has no commit author and git knows none: agents cannot commit.
Set one: lado git-server author --name "Your Name" --email you@example.com

$ lado git-server list
LADO's commit author: Ann Lee <ann@example.com>
ADDRESS                      KIND    LOGIN   TOKEN  CERTIFICATE  AUTHOR
https://gitlab.corp.example  GitLab  ivan    yes    -            Ivan Petrov <ivan.petrov@corp.example>

$ lado git-server author gitlab.corp.example --clear
Agents commit to https://gitlab.corp.example with LADO's commit author, or your own git author without one.
Agents started from now on commit so; restart running agents to give it to them.

$ lado project author shop --name "Shop Bot" --email bot@shop.example
Agents of project shop commit as Shop Bot <bot@shop.example>.
Agents started from now on commit so; restart running agents to give it to them.

$ lado project author shop --clear
Project shop has no commit author now: its agents commit as LADO's or a git server's.

$ lado project show shop
…
Commit author: Shop Bot <bot@shop.example>
```

Inside an agent, setting or clearing LADO's author is refused as the human's command
(`lado git-server author is for the human; agent "<name>" cannot use it`), as `lado project`
already is.

### Refusals and warnings

- A fresh start, a set-up, a project's repository from scratch with nobody known:
  `nobody signs the agents' commits: LADO has no commit author and git has no user.name or
  user.email`, hint `Set the commit author in Settings → Git servers, or run:` + `lado
  git-server author --name "Your Name" --email you@example.com` (the container too).
- A launch with git older than 2.31 while LADO's author applies: `git 2.30.2 is older than
  2.31, which LADO's commit author needs; update git, or clear it (lado git-server author
  --clear)`; for a project's: `… (lado project author <id> --clear)`.
- The launch's warning: `GIT_AUTHOR_EMAIL is set for <agent>: it wins over LADO's commit
  authors`.
- `lado doctor`: `[ok  ] git author: LADO's commit author set` /
  `[ok  ] git author: user.name and user.email set` / `[warn] git author: no LADO commit
  author and no user.name or user.email: agents cannot commit` with the hint.
- The container's log: `lado: warning: git has no user.name or user.email; set
  LADO_GIT_NAME and LADO_GIT_EMAIL, or the commit author in Settings → Git servers`.

## How it works

At an agent's launch LADO lays `GIT_CONFIG_*` entries (command scope, above every git config
file): LADO's `user.name`/`user.email`, then each saved server's entries with its author's
conditional include, then the project's `user.name`/`user.email`. The later wins, so the
order of priority is git's own (D3). LADO's own first commits pass the same author with
`-c user.name -c user.email` (D4). Both authors live in lado.db (D1); `lado.commit_authors`
holds the levels and answers the author in effect for a place, which the pages, the
refusals and doctor share (D2, D5).

## The architectural frame

- **Neutral core.** git reads the entries whatever the agent CLI: Claude Code, Codex,
  OpenCode and Kilo alike, in Codex's sandbox too (the entries are environment variables,
  as the servers' already are).
- **One source of truth.** lado.db holds the authors; nothing is written into git config
  files; the author in effect is computed from the same levels the launch lays.
- **No silent drops.** An old git is refused loudly; author variables that win are named at
  the launch and on the page.
- **Never touch the user's global agent config**, nor git's: option B of the proposal
  rejected for that.
- **Only what is used.** No author per session or agent; no settings table.
- **Coming stages.** LAD-311's guide points at `/settings/git-servers?author`; a LADO
  manager can set LADO's author through `PUT /api/git-author` as it sets a project's
  variables through the API (docs/design/projects.md); a project's author lives in its row
  and moves with it.

## Tests per requirement

| Requirement (capability) | Layer | Test |
|---|---|---|
| LADO keeps its own commit author and a project's in lado.db | unit | `tests/test_state.py`, `tests/test_commit_authors.py` |
| The commit author follows one order | unit + integration | `tests/test_commit_authors.py` (entries under a real `git config --get`, every pair of levels); `tests/integration/test_commit_authors.py` (fake agent: LADO's author with no git config and no remote; server's over LADO's; project's over the server's in a project session's clone; repository's own config loses) |
| LADO's own first commits take the same author | unit + integration | `tests/test_scratch.py`, `tests/test_setup.py`, `tests/test_project_repos.py`; `tests/integration/test_commit_authors.py` (`lado start --new` with `GIT_CONFIG_GLOBAL=/dev/null`) |
| A launch needs git 2.31 … | unit | `tests/test_runtime_git_servers.py` (a fake git on PATH) |
| lado git-server author without an address …, list names LADO's author first | unit | `tests/test_cli_git_server.py` |
| lado project author … | unit | `tests/test_cli.py` (the `lado project` cases), `tests/test_projects_core.py` |
| The server's API sets LADO's and a project's author | unit | `tests/test_server_git_servers.py`, `tests/test_server_projects.py` |
| The launch names author variables … | unit + integration | `tests/test_runtime_git_servers.py`; the integration test's `GIT_AUTHOR_EMAIL` case |
| lado.db of schema 43 is migrated to 44 | unit | `tests/test_state.py` |
| git-servers: list, author, agents commit as a server's author (modified) | unit + integration | the existing `tests/test_cli_git_server.py`, `tests/integration/test_git_server_author.py` updated |
| session-scratch, projects: the author check and its hint (modified) | unit | `tests/test_scratch.py`, `tests/test_project_repos.py`, `tests/test_server_launch.py` |
| doctor: git author (modified) | unit | `tests/test_doctor.py` |
| container: the warning; a clean container starts a project with LADO's author | container | `tests/container/test_access.py` (beside the git identity cases) |
| git-servers-page, projects page, folder-setup, New session (UI, from the flow) | vitest + UI e2e | `web/src/GitServers.test.tsx`, `web/src/Projects.test.tsx`, `web/src/Launch.test.tsx`, `LaunchSetup.test.tsx`, `ProjectRepos.test.tsx`; `tests/ui/test_commit_authors.py` (new), `tests/ui/test_git_servers_section.py`, `tests/ui/test_project_page.py` (the main scenario: New empty folder with nobody → Settings in a new tab → save → back → Create and start) |

Regression run: `make lint`, `make test`, the changed integration files with `-m
integration`, the changed UI files with `-m ui`, `make web`, `openspec validate
commit-author-levels --strict` and the trial archive; CI runs the rest (container, smoke).

## Docs

- `docs/cli.md`: `lado git-server author` without an address, `lado git-server list`'s
  first line, `lado project author`, `lado project show`'s line.
- `docs/design/ui.md`: Git servers (LADO's author, the minor server line, `?author`),
  Projects (the author line), Launch and session control (the note `AuthorMissing`).
- `docs/design/projects.md`: a project's commit author (The project; Not now loses nothing).
- `docs/design/agents.md`: the author entries in an agent's environment.
- `docs/design/modules.md`: `commit_authors.py`.
- `docker/compose.yaml`'s header: `LADO_GIT_NAME`/`LADO_GIT_EMAIL` or the commit author in
  Settings.
- CHANGELOG.md: `## 0.49.0 (unreleased)` (Added: commit author for all of LADO and per
  project, set in Settings).

## Manual check (for the pull request)

1. `LADO_HOME=$(mktemp -d) GIT_CONFIG_GLOBAL=/dev/null uv run lado ui`: New session → New
   empty folder → a name: the note and the link; Set it in Settings ↗ → save Ann Lee → back
   → the note goes; Create and start; `git log -1 --format='%an <%ae>'` in the new folder
   prints `Ann Lee <ann@example.com>`.
2. A project with an author and a repository whose remote is on a server with another
   author: an agent's commit carries the project's.
3. `lado doctor` prints `git author: LADO's commit author set`.
