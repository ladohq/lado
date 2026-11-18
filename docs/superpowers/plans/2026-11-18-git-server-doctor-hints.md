# lado doctor checks git servers, and a failed clone names its server: Implementation Plan

**Goal:** `lado doctor` prints a line per saved git server by the same check as `lado
git-server check`; a failed clone, listing or kit fetch names the saved server to check, or
suggests adding an unsaved host; the UI's clone notes open Settings → Git servers; the
page's leftovers are fixed.

**Architecture:** `git_servers.check(at, save_login=False)` for doctor (D1), one line per
server asked in a pool beside the model servers (D2); `clone._told` looks up the server git
took the token of (D3), a new kind `access_denied` (D4), the texts of D5, and
`CloneError.server` → `CloneRefused.git_server` (D6) for a link note in the UI (D7); the page
reads `?check=`/`?add=` (D8), keeps one Replace token (D9), places its tips after a layout
switch (D10) and disables Remove/Undo while they ask (D11).

**Tech Stack:** Python 3.10+ (standard library), FastAPI/pydantic (existing), React +
TypeScript + react-router (existing), pytest (`-n auto`, `-m integration`, `-m ui`), vitest,
Playwright's Chromium, git ≥ 2.36 in the test environments.

**Spec:** `openspec/changes/git-server-doctor-hints/` (proposal, deltas, `design.md` D1–D12)
and `docs/superpowers/specs/2026-11-18-git-server-doctor-hints-design.md` (outputs, tests
per requirement, docs, manual check). Mockup: the run's `mockup-git-server-hints.html`
(sections 2, 3, 4 variant A).

## Global Constraints

- No schema migration; doctor writes nothing to lado.db (`save_login=False`).
- The System panel (`SystemPanel.tsx`, `/api/system`, `doctor.report`) is not changed
  (#7332 q1).
- github.com's existing texts and hints stay word for word; only the new kind
  `access_denied` is added for it.
- The texts are those of the deltas and D5, word for word; another wording needs a reason
  in the build report.
- No token in any text, answer, log line or URL; a URL reaches a text only through
  `runtime.public_remote`.
- Tests use no network: `tests/fake_git_api.py`, `tests/fake_git_server.py`, closed local
  ports.
- Nothing in code, docs, specs or the UI names the work's stages or `docs/epics/`.
- CHANGELOG: extend the 0.48.0 git servers entry; no new version.
- The pull request carries the design doc's manual check from the start.

## Review Focus

1. A saved server whose stored address the address rule now refuses: doctor's line says so
   and the other lines follow (Task 1's `test_a_saved_address_no_longer_taken_is_its_own_warning`).
2. Two servers that hang: doctor waits about one check's time, not two
   (`test_servers_are_asked_at_once`).
3. An ssh URL of a saved server (`git@host:group/repo.git`): it gets the check hint, as git
   used the server's token (`test_an_ssh_address_of_a_saved_server_gets_the_check_hint`).
4. A host saved as `https://` asked as `http://` or on another port: no server hint and no
   add hint (`test_a_host_saved_under_another_scheme_gets_no_server_hint`).
5. A lado.db at another schema while a clone fails: the clone's text is today's, no crash
   (`test_a_clone_failure_with_lado_db_at_another_schema`).

## Task 1: doctor's git server lines (D1, D2)

**Files:** `src/lado/git_servers.py` (`check`'s `save_login`), `src/lado/doctor.py`
(`check_git_servers`, `run_checks`), `tests/test_doctor.py`, `tests/test_git_servers.py`.

**Interfaces:**
- Produces: `git_servers.check(at: Address, save_login: bool = True) -> Check`;
  `doctor.check_git_servers() -> list[Check]`, lines named `git server <address>` or one
  `git servers` line.

- [ ] Failing tests in `tests/test_doctor.py`, each with a temp `LADO_HOME` and servers saved
  against `fake_git_api`: `test_a_working_and_a_refused_server` (levels, details, the
  refused one's hint), `test_no_saved_server_prints_no_line`,
  `test_lado_db_at_another_schema_asks_no_server`, `test_a_server_that_does_not_answer_is_a_warning`
  (a closed port; the other line follows), `test_a_missing_token_file_sends_nothing`,
  `test_a_saved_address_no_longer_taken_is_its_own_warning` (row written by hand),
  `test_servers_are_asked_at_once` (two delayed fakes, wall time below 1.5 × one delay),
  `test_git_server_lines_never_change_the_exit_status` (`main()`),
  `test_doctor_saves_no_login`; in `tests/test_git_servers.py`
  `test_a_check_without_save_login_writes_nothing`.
- [ ] Run `uv run pytest -n0 tests/test_doctor.py tests/test_git_servers.py -k "git_server
  or save_login or asked_at_once"`: they fail.
- [ ] Implement D1 and D2: the pool starts before `check_model_servers` in `run_checks`, its
  lines are placed after `git author`.
- [ ] Run the tests: pass; `make test`.
- [ ] Commit `lado doctor checks each saved git server (LAD-297)`.

## Task 2: the clone's git server texts (D3–D6, core and API)

**Files:** `src/lado/clone.py` (`KINDS`, `ServerWay`, `CloneError.server`, `_told`,
`_reason`, `failure`, `explain`), `src/lado/server/models.py` (`GitServerWay`,
`CloneRefused.git_server`), `src/lado/server/clones.py` (`refused`), `web/openapi.json`,
`web/src/api.gen.ts`, `tests/test_clone.py`, `tests/test_server_clones.py`,
`tests/integration/test_git_server_access.py`.

**Interfaces:**
- Consumes: `git_servers.server_for`, `git_servers.address`, `git_servers.GITHUB_COM`,
  `state.git_servers`.
- Produces: `clone.ServerWay(way: Literal["check", "add"], host: str, address: str, page:
  str)`; `CloneError.server: ServerWay | None`; API `CloneRefused.git_server:
  GitServerWay | None` with `way`, `host`, `address`, `text`.

- [ ] Failing unit tests in `tests/test_clone.py`: `test_a_403_is_access_denied`,
  `test_github_403_points_at_gh_auth_status`,
  `test_a_saved_server_refusing_its_token_gets_the_check_hint` (login_needed,
  access_denied, not_found: reasons and hint per D5),
  `test_an_ssh_address_of_a_saved_server_gets_the_check_hint`,
  `test_an_unsaved_host_asking_for_a_login_gets_the_add_hint` (login_needed and
  access_denied; the root with a port), `test_an_unsaved_host_not_found_gets_no_hint`,
  `test_an_unreachable_unsaved_host_gets_no_hint`,
  `test_a_host_saved_under_another_scheme_gets_no_server_hint`,
  `test_github_texts_are_unchanged` (each existing github.com case),
  `test_a_kits_failure_carries_the_add_hint` (`explain`),
  `test_a_clone_failure_with_lado_db_at_another_schema`.
- [ ] Failing tests in `tests/test_server_clones.py`: `git_server` for both ways on a
  listing's 400 and in a job's error; null for other kinds.
- [ ] Failing integration tests in `tests/integration/test_git_server_access.py`:
  `test_a_listing_with_a_refused_saved_token_names_the_server` (real git, `fake_git_server`,
  a saved server with a wrong token), `test_a_listing_of_an_unsaved_host_suggests_adding_it`.
- [ ] Run each layer alone (`-n0`, `-m integration` for the last file): they fail.
- [ ] Implement D3–D6; `make web-types`.
- [ ] Run: pass; `make test`; `uv run pytest -m integration -n auto
  tests/integration/test_git_server_access.py`; `make web`.
- [ ] Commit `A failed clone names its git server, or suggests adding one (LAD-297)`.

## Task 3: the UI's note and the page's address (D7, D8)

**Files:** `web/src/LaunchWhere.tsx` (`GitServerNote`), `web/src/Launch.tsx`,
`web/src/ProjectRepos.tsx`, `web/src/GitServers.tsx` (`?check=`, `?add=`),
`web/src/styles.css`, `web/src/Launch.test.tsx`, `web/src/ProjectRepos.test.tsx`,
`web/src/GitServers.test.tsx`, `tests/ui/test_launch.py`.

**Interfaces:**
- Consumes: `CloneRefused.git_server` of Task 2.
- Produces: `GitServerNote({ way }: { way: GitServerWay })`; the routes
  `/settings/git-servers?check=<host>` and `?add=<address>`.

- [ ] Failing vitest: the four places show the note's sentence and the link (`Check <host>
  ↗` / `Add git server ↗`, `href`, `target="_blank"`, `rel` with `noopener`), no Copy;
  without `git_server` they show `FolderHint` as before. `GitServers.test.tsx`: `?check=`
  opens the panel and posts the check once, `?add=` fills Address and focuses Token, an
  unknown host opens nothing, the query is dropped.
- [ ] Failing UI e2e in `tests/ui/test_launch.py`: Clone from URL on a URL of
  `fake_git_server` with a saved wrong token shows the check note; pressing the link opens a
  page on Settings → Git servers whose check line says the token is refused; with no saved
  server the add note, its link opening the add form. Screenshots `clone-check-note`,
  `clone-add-note`, `settings-opened-to-check`.
- [ ] Implement; at ≤ 760 px the link is 44 px high.
- [ ] Run `make web`; `uv run pytest -m ui tests/ui/test_launch.py`.
- [ ] Commit `The clone window's git server note opens Settings (LAD-297)`.

## Task 4: the page's leftovers (D9–D11)

**Files:** `web/src/GitServers.tsx`, `web/src/InfoTip.tsx` and/or `web/src/Menu.tsx`,
`web/src/styles.css`, `web/src/GitServers.test.tsx`, `tests/ui/test_git_servers_section.py`.

- [ ] Failing vitest: after `token_refused`, `scopes_missing`, and a save with a missing
  right (Sign-in and the panel's top), exactly one `Replace the token of <address>`, with
  class `primary`; a `Works:` line has no `✓`, `Author saved.` keeps it; a pending author
  removal disables Remove and a second click sends nothing; the same for Undo.
- [ ] Failing UI e2e in `tests/ui/test_git_servers_section.py`:
  `test_an_open_tip_follows_its_button_across_the_layouts` (Token tip at 390 px, resize to
  900 px, the tip's box beside its button's; screenshot `tip-after-widening`).
- [ ] Find D10's cause (write it in the commit message), fix it in `useBelow` or `InfoTip`.
- [ ] Implement D9 and D11.
- [ ] Run `make web`; `uv run pytest -m ui tests/ui/test_git_servers_section.py`.
- [ ] Commit `One Replace token, tips that follow a layout switch, busy author buttons
  (LAD-297)`.

## Task 5: docs and housekeeping (D12)

**Files:** `docs/cli.md`, `docs/design/ui.md`, `docs/design/modules.md`, `CHANGELOG.md`,
`BACKLOG.md`.

- [ ] Write the docs of the design doc's "Docs" section, true to the code.
- [ ] Remove BACKLOG.md's "Flaky: the Kilo smoke on macOS times out on `kilo models`".
- [ ] Run `make lint`, `openspec validate git-server-doctor-hints --strict` and the trial
  archive of `.lado/sdlc.md`.
- [ ] Commit `Document doctor's git servers and the clone's server hints (LAD-297)`.

## Regression run (before the build report)

`make lint`; `make test`; `uv run pytest -m integration -n auto
tests/integration/test_git_server_access.py`; `uv run pytest -m ui tests/ui/test_launch.py
tests/ui/test_git_servers_section.py`; `make web`; `openspec validate --specs --strict`;
the trial archive.
