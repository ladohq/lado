# Settings → Git servers: Implementation Plan

**Goal:** the human sees, adds and removes git servers in Settings → Git servers with the
rules and words of `lado git-server`; the token only in one request's body; one server per
host name and no empty `git-servers/` folder, in the command and the page alike.

**Architecture:** the add sequence moves into `git_servers.add` (D1), shared by `cli.py` and
the new `lado.server.git_entries`; `git_servers.Refused` carries a field and page words (D2);
`git_servers.hint` asks the address without a token (D3); four routes in `server/app.py` (D4);
`check_host` (D5); the folder in `_remove_token` (D6); `web/src/GitServers.tsx` on Model
servers' classes (D7).

**Tech Stack:** Python 3.10+ (standard library), FastAPI/pydantic (existing), React +
TypeScript (existing), pytest (`-n auto`, `-m ui`), vitest, Playwright's Chromium.

**Spec:** `openspec/changes/git-servers-page/` (proposal, delta, `design.md` D1–D8) and
`docs/superpowers/specs/2026-11-16-git-servers-page-design.md` (the page's lines, the
tests per requirement, the manual check). Mockup: run artifact `mockup-git-servers.html`.

## Global Constraints

- No new dependency, no MCP tool, no schema change. CHANGELOG: extend the 0.48.0 git servers
  entry; no new version.
- The token reaches LADO's server only in the body of `POST /api/git-servers`; no response
  model has a token field; `SECRET_ROUTE` covers `git-servers`; every test that sets a token
  uses a canary and greps answers, logs and `LADO_HOME`.
- The address check sends no credential header and waits at most `model_servers.TIMEOUT`
  (5 s) a request, as the probe.
- Command lines stay as they are but the new same-host refusal; the page's words name no
  command.
- Nothing in code, docs, specs or the UI names the work's stages or `docs/epics/`.
- No test reaches the network: gitlab.com through the test's local proxy (D8).
- The pull request carries the design doc's manual check from the start (task 7).

## Review Focus

1. The token in a 422 or a 500 of the new routes (a body with a wrong type, an exception in
   the probe): task 3's tests send a canary in a malformed body and force an exception.
2. Two adds of the same host name on two ports at once both saved: task 1's test runs the two
   saves against each other (`save` checks inside its write).
3. A late check answer showing a hint or link of an address no longer typed: task 5's vitest
   types two addresses and resolves the first answer last.
4. The token left in the field or the DOM after a refusal of another field, Cancel or the form
   closing: task 5's vitest and task 6's UI test.
5. `HTTPS_PROXY`/`NO_PROXY` of the human's environment sending the check through a proxy:
   expected, as the command does; task 2 asserts the check uses the same opener as `probe`.

## Task 1: The core: one add, the host-name rule, the folder, the page's words

Layer: unit. Files: `src/lado/git_servers.py`, `src/lado/git_kinds/base.py`,
`src/lado/cli.py`, `tests/test_git_servers.py`, `tests/test_cli_git_server.py`.

- `Refused(text, hint="", field="", page=None, page_hint=None)`; set field and page words of
  every existing refusal as design.md D2 lists them.
- `check_host(at)` (D5) and its second check in `save` (inside the same `state` write: add
  `state.save_git_server(..., refuse_host=...)` or a `git_server_by_hostname` in the
  transaction).
- `add(at, token, kind_name, warn) -> tuple[GitServer, bool, Checked]`: `check_not_github`,
  `check_host`, `check_git(os.environ)`, the plain-http warning through `warn`,
  `check_token`, `probe`, `save`. `cmd_git_server_add` keeps reading the token (after
  `check_not_github` and `check_host`, before `check_token`) and prints as now.
- `_remove_token`: then `git-servers/` when no server is left (D6); `_write_token` retries
  once on a folder gone under it.
- Tests (requirement "One git server per host"): `host` saved, `host:8443` refused before any
  request (the fake API records none) with the line and hint; `http://host:8080` too; the same
  key replaces; two saves of two ports at once: one saved, one refused. CLI: exit 1, no token
  read (stdin left unread), the hint `remove it first: lado git-server remove <address>`.
- Tests ("lado git-server remove …"): the folder gone with the last server, kept with another;
  an add at the same moment keeps its folder (remove's `rmdir` between the add's `open` and
  `mkdir`, simulated by patching).
- Tests (D2): each refusal's `field`, `page`, `page_hint`; no page line holds `lado ` or
  `--`.
- Run: `uv run pytest -n auto tests/test_git_servers.py tests/test_cli_git_server.py`.

## Task 2: The address check without a token

Layer: unit. Files: `src/lado/git_kinds/base.py` (`request(root, token: str | None)`),
`src/lado/git_servers.py` (`Hint`, `hint(at)`), `tests/fake_git_api.py` (profiles that answer
401 without a credential: `gitlab-asks`, `github-asks`; `both-ask`),
`tests/test_fake_git_api.py`, `tests/test_git_servers.py`.

- `Hint(kind: Kind | None, choose: bool, why: str)`: a kind for exactly one kind's 401 or user
  answer; `choose=True` for no answer (`why` from `_silent`) and for neither or both; a
  redirect raises `Refused(..., field="address")` as the probe's line.
- Tests (requirement "The add form checks the address without the token", "The kind is chosen
  by hand only …"): every profile's `Hint`; no request carries `PRIVATE-TOKEN` or
  `Authorization`; the hanging profile answers within 5 s plus a margin; a redirect refused.
- Run: `uv run pytest -n auto tests/test_git_servers.py tests/test_fake_git_api.py`.

## Task 3: The server API

Layer: unit. Files: `src/lado/server/git_entries.py` (new), `src/lado/server/models.py`
(`GitServerInfo`, `GitKindInfo`, `GitServers`, `GitServerCheckAsked`, `GitServerCheck`,
`GitServerAdd`, `GitServerAdded`), `src/lado/server/app.py` (four routes, `SECRET_ROUTE`),
`web/openapi.json`, `web/src/api.gen.ts` (`make web-types`), `tests/test_server_git_servers.py`.

- Shapes and routes exactly as design.md D4; `check` returns `saved` when the key is saved,
  `token_page`/`scopes` of the hint's kind; refusals as `EntryRefused` with the page words.
- Tests ("The page lists …"): the listing's rows equal `cli.cmd_git_server_list`'s table
  (address, kind title, login or None, has_token); no lado.db made by `GET` on a fresh home.
- Tests ("Add server saves …", "A refusal shows under its field …"): add GitLab, GitHub,
  replace, `kind` chosen for a silent server (login None), a wrong token (field `token`),
  github.com (field `address`), another port (field `address`), both kinds with no kind (field
  `kind`).
- Tests ("The token never leaves …"): a canary token in no answer of any route; a malformed
  body (`token: 5`, missing `address`) gets a 422 without the canary; an exception in `probe`
  (patched) gets a 500 whose text and the error journal lack the canary.
- Tests (Remove): removes and lists; an unknown host is a 400 `EntryRefused`.
- Run: `uv run pytest -n auto tests/test_server_git_servers.py`, then `make web` (stale-types
  check).

## Task 4: The section in Settings

Layer: vitest + UI. Files: `web/src/settingsSections.ts` (`git-servers`, `Git servers`,
`GitIcon`, after Model servers), `web/src/Settings.tsx` (`PAGES`), `web/src/GitServers.tsx`
(the page with the list only, for now), `web/src/api.ts` (`gitServers`, `checkGitServer`,
`addGitServer`, `removeGitServer`), `web/src/Settings.test.tsx`, `tests/ui/test_settings_pages.py`.

- Tests (settings-pages: "Settings is a page per section …"): the list's five items in order;
  `/settings/git-servers` heads `Git servers`; the phone's list shows it.
- Rows as the design doc's list (address, badge, second line, 🗑).
- Run: `cd web && npx vitest run src/Settings.test.tsx`, `uv run pytest -m ui
  tests/ui/test_settings_pages.py`.

## Task 5: The add form and Remove

Layer: vitest. Files: `web/src/GitServers.tsx`, `web/src/styles.css` (only what the reused
classes lack), `web/src/GitServers.test.tsx`.

- The form as the design doc: gitlab.com filled in and selected unless saved; the check on
  settling (`useDebounced`, `MODEL_DEBOUNCE`); the hint line and Token's link; the kind
  segments only with `choose_kind`, `Add without a check` off until chosen; Add's states;
  refusals under fields; the saved lines; Remove's question, `Removed <address>.`, the focus
  on `+ Add server`; `useScrollAnchor`.
- Tests: each state from fake API answers; a late check answer dropped (Review Focus 3); the
  token emptied on done, on a refusal of the address, on Cancel, when the form closes, and
  kept on a refusal of the token (Review Focus 4); gitlab.com saved → Address empty.
- Run: `cd web && npx vitest run src/GitServers.test.tsx`, `make web`.

## Task 6: The UI e2e test

Layer: UI (`-m ui`). Files: `tests/ui/test_git_servers_section.py`, `tests/ui/conftest.py`
(a fixture for the fake git APIs and the gitlab.com proxy), a small proxy in
`tests/fake_git_api.py` (`GitlabComProxy`: CONNECT `gitlab.com:443` answered by the fake API
over TLS with a certificate for `gitlab.com` from a test CA; `SSL_CERT_FILE` of the lado
server's process; `HTTPS_PROXY` to it, `NO_PROXY=127.0.0.1,localhost`).

- Scenarios: add gitlab.com (filled in, the hint, the link, the canary token, the row
  `signed in as ivan.petrov`); add the human's own server (GitHub profile); a silent server
  with GitLab chosen (`⚠ not checked`); a refused token (the line under Token, nothing saved);
  remove one (the question, `Removed …`). After the adds `lado git-server list` on the same
  `LADO_HOME` prints the rows the page shows. The canary: not in any `/api/git-servers*`
  answer the page received (Playwright's response log), not in `page.content()` after the
  save, not in `server.log`, in no file of `LADO_HOME` but the token file.
- Screenshots of each frame in `<temp dir>/lado-ui-shots/` for the build report (1440 and 390
  px).
- Run: `uv run pytest -m ui tests/ui/test_git_servers_section.py`.

## Task 7: Docs and the pull request's manual check

Files: `docs/design/ui.md`, `docs/cli.md`, `docs/design/modules.md`, `AGENTS.md`,
`CHANGELOG.md`; the pull request description.

- As the design doc's Docs list; `tests/test_agents_md.py` stays green (≤200 lines).
- The pull request's description carries the design doc's manual check, the steps needing the
  human's token marked.
- Regression: `make lint`, `make test`, `make web`, `uv run pytest -m ui
  tests/ui/test_git_servers_section.py tests/ui/test_settings_pages.py
  tests/ui/test_models_section.py`, `openspec validate git-servers-page --strict`, the trial
  archive of `.lado/sdlc.md`.
