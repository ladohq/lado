# Settings → Git servers: design

Task: LAD-290. Change: `openspec/changes/git-servers-page/` (proposal, delta, `design.md`
with decisions D1–D8). Mockup: the run's artifact `mockup-git-servers.html` (frames 1–8; frame
2′ and frame 8's option B were not taken).

## What the human sees

Settings gets a section **Git servers** between Model servers and Statistics, icon `GitIcon`,
address `/settings/git-servers`. The page is built like Model servers (docs/design/ui.md, Model
servers): no frames, rows between thin lines, a form under the list, the launch window's
fields and notes, no colour of its own.

### The list

- Heading `Servers <n>` (the count once one is saved), then the lead: `Your GitLab or GitHub
  Enterprise: agents clone and push there with its token. github.com uses gh's login. Running
  agents get a change after a restart.`
- A row per saved server, in `lado git-server list`'s order (by host): the address (whole,
  wrapped, never cut), the kind as a `badge` (`GitLab`, `GitHub`; an unknown kind by its
  name), and a second line: `signed in as <login>`; `⚠ not checked: saved without a check`
  (`--warn`) for a login of None; `⚠ its token file is missing: add it again` (`--warn`)
  when `has_token` is false, in place of either. At the right only 🗑 (`mx-icon
  mx-icon-danger`, `aria-label="Remove <address>"`, titled `Remove`). No chevron, no ✎.
- Then `+ Add server` (`quiet mx-add`). With no server: no heading count, the lead and the
  button only.

### The add form

Opens in the place of `+ Add server` (`mx-form`, `launch-grid`, fields `launch-wide`):

| Field | Content |
|---|---|
| Address | `https://gitlab.com`, selected and focused, while no saved server has the host `gitlab.com`; else empty and focused. Placeholder `gitlab.example.com or https://host/path`. |
| (hint) | `Looks like <Kind>; the token tells for sure.` under Address, once the check found a kind. |
| Kind | Only when the check says `choose_kind`: segments `GitHub` `GitLab`, none chosen. |
| Token | The project page's secret field (`SecretField`), placeholder `Paste the token`. Under it: `Make one at <link> with the <scopes>.` (the hint's or the chosen kind's page on this address: `<root>/-/user_settings/personal_access_tokens`, `scopes read_repository, write_repository, read_api`; `<root>/settings/tokens`, `scope repo`), then `Only LADO reads it; never shown again.` With no kind known yet, only the second line. |
| Buttons | `Add server` (primary), or `Add without a check` while the kind choice shows; `Cancel`. |

The check (`POST /api/git-servers/check`, no token) runs once the address's typing settles
(`MODEL_DEBOUNCE`), and at once for the filled-in gitlab.com. Under Address meanwhile:
`checking <address> …` with the spinner (`mx-check`). Then, under Address: its refusals
(`field-note bad`, hint under it), the plain-http warning (`field-note warn`), the hint
line, and `Already saved: Add server replaces its token.` for a saved address. An older
check's answer is dropped.

Add server is on when the address's check has no refusal, a token is typed, and, while the
kind choice shows, a kind is chosen. It sends `{address, token, kind}` (kind only when chosen),
saying `checking the server…` on the button meanwhile. Done: the form closes, the new or
replaced row takes its place with the focus on it, and above it (`mx-saved`) `Saved git server
<address>: <Kind>, signed in as <login>.` (`Replaced …` for a replaced one; without a login
`Saved git server <address> as <Kind> without a check (<why>).`), then `Agents started from
now on reach it; restart running agents to give it to them.`, and the warnings (http). These
lines go with the human's next change on the page.

A refusal shows under its field (D2 of design.md) until that field is edited; one of no field
under the buttons. The token is emptied when Add is done or refused for anything but the
token, on Cancel and when the form closes; a refused token stays, Add off until it is edited.

### Remove

🗑 opens under the row (`mx-confirm`, `role=alertdialog`, the focus on Cancel): `Remove
<address>?` then `Its token is deleted too. This cannot be undone. Running agents keep
reaching it until they restart.`, with `Remove server` (`danger`) and `Cancel`; Esc cancels.
Done: `Removed <address>.` in the row's place (`mx-done`), the focus on `+ Add server`. A
refusal (`field-note bad`, `role=alert`) under the buttons, the list read again.

### Narrow windows

As Model servers below 600 px: fields one under the other, 🗑 and buttons 44 px, the address
wrapped whole, no sideways scroll. On a phone the page stands alone under `‹ Settings`.

### Lines of the page

The command's lines with no command in them (design.md D2). Examples, by case:

| Case | Field | Line (hint) |
|---|---|---|
| github.com | Address | `github.com is reached through gh's login (GH_TOKEN or gh auth login); LADO keeps no token for it` |
| Another port of a saved host name | Address | `git.corp.example already has a git server, https://git.corp.example; LADO keeps one server per host name, as git's ssh addresses (git@git.corp.example:…) carry no port` (`Remove it first if the server moved to this address.`) |
| Does not answer | Address (warn) + Kind | `git.internal.example does not answer: it did not answer in 5 s` (`If the server is there for git but its API is not reachable from here, choose its kind to save it without a check.`) |
| Answers as neither | Address (warn) + Kind | `<root> answers as neither GitHub nor GitLab` (the same hint) |
| Sends elsewhere | Address | `<root> sends to <location>; give the server's own address` |
| Refuses the token | Token | `GitLab at <root> refuses the token` (`make a token at <page> (<scopes>)`) |
| Lacks read_api | Token | `GitLab at <root> takes the token, but it lacks the scope read_api` (the same hint) |
| Plain http | Address (warn) | `the token goes to <host> over plain http://, unencrypted; use https:// if the server has it` |
| git too old | buttons | `git 2.30.1 is older than 2.31, which git servers need; update git` |

## Server API

As `design.md` D4. Every route: `guard` for reading, `guard.changes` for a change; refusals
are 400 with `EntryRefused`; a body LADO cannot read on these routes gets a 422 that repeats
none of it (`SECRET_ROUTE`).

## Tests per requirement

| Requirement | Tests |
|---|---|
| git-servers: One git server per host | unit `test_git_servers.py` (refused before any request, in `add` and `check`; same key replaces), `test_cli_git_server.py` (exit 1 before the token is read, the hint) |
| git-servers: lado git-server remove … | unit `test_git_servers.py` (folder gone with the last, kept with another; an add at the same moment keeps its folder) |
| settings-pages: Settings is a page per section | UI `test_settings_pages.py` (the section in the list and its heading), vitest `Settings.test.tsx` |
| The page lists the saved git servers | unit `test_server_git_servers.py` (listing equals the command's rows; no lado.db), UI `test_git_servers_section.py` |
| The add form starts with gitlab.com | vitest `GitServers.test.tsx`, UI |
| The add form checks the address without the token | unit `test_git_servers.py` (`hint` per profile, no credential header), `test_server_git_servers.py` (check refusals, warning, saved note), vitest, UI |
| Add server saves as lado git-server add does | unit `test_server_git_servers.py`, UI (gitlab.com, own server; list equals `lado git-server list`) |
| A refusal shows under its field | unit `test_git_servers.py` (field and page words of each), vitest, UI (wrong token) |
| The kind is chosen by hand only … | unit (`hint` silent/neither/both/moved), vitest, UI (silent server) |
| Remove asks first | vitest, UI (remove) |
| The token never leaves the request | unit `test_server_git_servers.py` (canary in no answer, 422 without it), UI (canary not in answers, DOM, `server.log`, `LADO_HOME` files) |

Regression: `make test`, `make lint`, `make web` (stale types), `uv run pytest -m ui
tests/ui/test_git_servers_section.py tests/ui/test_settings_pages.py tests/ui/test_models_section.py`,
the openspec checks of `.lado/sdlc.md`.

## Docs

- `docs/design/ui.md`: Settings' pages list (`Git servers /settings/git-servers`, `GitIcon`),
  the routes line, and a new section **Git servers** after Model servers with this page.
- `docs/cli.md`: the same-host refusal and the folder removed with the last server.
- `docs/design/modules.md`: `server/git_entries.py`, `git_servers.add`, `hint`, `check_host`.
- AGENTS.md: `git_entries.py` in the `server/` line.
- CHANGELOG.md: the 0.48.0 git servers entry says they are also in Settings → Git servers.

## Manual check (for the pull request)

Branch `feature/lad-290-git-servers-page`, from the repository's folder: `env | grep -E
'^(GIT_|GH_|LADO_)'`, `unset` what a previous check left; `uv sync`; `LADO_HOME=$(mktemp -d)
LADO_TMUX_SOCKET=lado-check uv run lado ui`. On the page: Settings → Git servers, empty;
`+ Add server` shows gitlab.com and its token link; **[human: token]** paste a gitlab.com
token, Add, the row says `signed in as <you>`; `LADO_HOME=… uv run lado git-server list`
shows the same; type `github.com` (refused), `http://example.com` (warning), a host that does
not answer (`10.255.255.1`, kind choice); remove gitlab.com (asks, then `Removed …`), and
`ls $LADO_HOME` has no `git-servers/`.
