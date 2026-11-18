# Checking a saved git server: Implementation Plan

**Goal:** a saved git server is checked again from `lado git-server check` and from `Check` in
Settings → Git servers, the token's rights among the findings; Add and Replace token warn of
a missing right; the page follows the approved layout; the edge cases of the earlier git
server work are closed.

**Architecture:** `model_servers.Answer.headers` (D2); `Kind.needs`/`Kind.rights` per kind
(D3); `git_servers.check` with outcomes and two texts (D1), saving the login on `ok` (D5); a
lock of `LADO_HOME` around save and remove (D9); the command (D6) and the route (D7) on the
same core; the page rebuilt from panels (D16) with `InfoTip`'s `place` (D17).

**Tech Stack:** Python 3.10+ (standard library), FastAPI/pydantic (existing), React +
TypeScript (existing), pytest (`-n auto`, `-m integration`, `-m ui`), vitest, Playwright's
Chromium, git ≥ 2.36 in the test environments.

**Spec:** `openspec/changes/git-server-check/` (proposal, deltas, `design.md` D1–D18) and
`docs/superpowers/specs/2026-11-17-git-server-check-design.md` (outputs, tests per
requirement, docs, manual check). Mockups: the session's `ui-design/lad-292-v2/mockup.html`
and spec, the run's `mockup-check-cases.html` (A1, B, C, D, E).

## Global Constraints

- No schema migration: a passing check writes the existing login column; nothing else of a
  check is stored. A change that seems to need one: stop and tell the supervisor.
- The token reaches LADO's server only in `POST /api/git-servers`' body; the check route
  reads the token file and puts the token in no answer and no log line (canary tests).
- A check follows no redirect and sends no request to a redirect's target.
- The page's texts are those of the page spec and D18, word for word; any other change of a
  text needs a reason in the build report.
- Never write `~/.gitconfig`, the system git config or a repository's `.git/config`.
- Nothing in code, docs, specs or the UI names the work's stages or `docs/epics/`; the
  github.com block and the certificate row are not built and not announced as "coming".
- CHANGELOG: extend the 0.48.0 git servers entry; no new version.
- The pull request carries the design doc's manual check from the start.

## Review Focus

1. The outcome table of D1: a TLS failure told as `cert_untrusted`, not `no_answer`; a
   redirect of any kind's request wins over "another kind".
2. Rights: GitHub's absent header (not checked) vs empty header (no scopes); GitLab's
   `api`.
3. The lock: no network request under it; the 10 s refusal; a removal racing a replacement.
4. The page: one result line at a time; the focus table; the canary token in the DOM.

## Task 1: Small fixes of the core (D8–D14)

**Files:** `src/lado/git_servers.py`, `src/lado/runtime.py` (the launch's call of
`check_author_git`), `src/lado/cli.py` (the removal's warning), `tests/test_git_servers.py`,
`tests/test_runtime_git_servers.py`, `tests/test_cli_git_server.py`, `tests/fake_git_api.py`
(a `gateway` profile: 401 JSON on every path).

- [ ] Failing tests: `test_a_trailing_dot_is_dropped`, `test_a_host_of_dots_names_no_host`,
  `test_author_globs_match_any_case_and_the_default_port` (real git; `GitLab.Corp.ru`,
  `:443`, `http …:80`; near-miss `gitlab.corp.ru.evil`, `gitlab.corp.rux`; ssh forms as
  before), `test_removal_waits_for_a_save_holding_the_lock`, `test_a_held_lock_refuses_after_10_s`
  (time patched), `test_removal_racing_a_replacement_keeps_row_and_token_in_step`,
  `test_a_folder_that_cannot_be_removed_warns`, `test_old_git_names_every_server_with_an_author`,
  `test_a_failed_author_write_leaves_no_temp_file`, `test_a_gateway_refusal_names_no_kind`,
  `test_add_of_a_server_that_stopped_answering_offers_the_kind`.
- [ ] Run `uv run pytest -n0 tests/test_git_servers.py tests/test_runtime_git_servers.py
  tests/test_cli_git_server.py -k "dot or glob or lock or folder or old_git or temp or
  gateway or stopped"`: they fail.
- [ ] Implement D8–D14. Run: pass; `make test`.
- [ ] Commit `Close the edge cases of saving and removing git servers (LAD-293)`.

## Task 2: The rights of a token (D2–D4)

**Files:** `src/lado/model_servers.py`, `src/lado/git_kinds/base.py`, `github.py`,
`gitlab.py`, `src/lado/git_servers.py` (`probe`, `Checked`, `add`), `src/lado/cli.py` (the
warning), `tests/fake_git_api.py` (scopes per profile: GitLab's token-self, GitHub's header
present, empty, absent), `tests/test_model_servers.py`, `tests/test_git_servers.py`,
`tests/test_cli_git_server.py`.

- [ ] Failing tests: `test_an_answer_keeps_its_headers`; per kind
  `test_rights_<case>` (GitLab all, no `write_repository`, no `read_repository`, `api` alone,
  token-self 404; GitHub `repo`, `read:org`, empty, absent); `test_add_saves_a_token_without_push_and_warns`.
- [ ] Check GitLab's docs on the `api` scope and Git-over-HTTP push; write the result in the
  commit message and keep or drop `api` as both repository rights (D3).
- [ ] Implement. Run: pass; `make test`.
- [ ] Commit `Read a git server token's rights and warn when push is missing (LAD-293)`.

## Task 3: The check (D1, D5–D7, D14)

**Files:** `src/lado/git_servers.py` (`Check`, `check`), `src/lado/cli.py` (`lado git-server
check`), `src/lado/server/git_entries.py`, `src/lado/server/app.py`,
`src/lado/server/models.py` (`GitServerCheck`, `GitServerSaved.warning`, `missing_scopes`,
`EntryRefused.choose_kind`, the removal's `warning`), `web/openapi.json`, `web/src/api.gen.ts`,
`tests/test_git_servers.py`, `tests/test_cli_git_server.py`, `tests/test_server_git_servers.py`.

- [ ] Failing tests: `test_check_<outcome>` per kind (ok, rights not checked, token refused,
  a scope missing, no answer by timeout and by an unknown name, certificate not trusted with
  the fake's own CA, redirect with no request to the target, another kind, neither kind);
  `test_check_of_no_such_server_sends_nothing`, `test_check_with_the_token_missing_sends_nothing`,
  `test_a_passing_check_saves_the_login`, `test_a_failed_check_changes_nothing`; the CLI's
  output and exit codes; the route per outcome, 404, 422, and the canary token in no answer
  and no log line.
- [ ] Implement; `make web-types`. Run: pass; `make test`; `make web`.
- [ ] Commit `Check a saved git server again: lado git-server check and its API (LAD-293)`.

## Task 4: The info tip (D17)

**Files:** `web/src/InfoTip.tsx`, `web/src/InfoTip.test.tsx`, `web/src/styles.css`.

- [ ] Failing vitest: `place="above"` puts the tip above its button within the window;
  default below as before.
- [ ] Implement; the `div.mx-h` wrapper and the phone `.field-head` height in `styles.css`.
- [ ] Run `make web`. Commit `Let an info tip open above its button (LAD-293)`.

## Task 5: The page (D15, D16, D18)

**Files:** `web/src/GitServers.tsx`, `web/src/GitServers.test.tsx`, `web/src/styles.css`.

- [ ] Failing vitest per state: the closed row's lines; the panel's rows and buttons with
  their accessible names; Check's lines per outcome and the row's line 2 after a failure;
  Replace token (done, another user, refused, missing scope, no answer → save without a
  check under the saved kind); the author (saved, removed with Undo, Undo); Remove server's
  question and done; Add (checking, answered, plain http, already saved → Replace its token,
  github.com, no answer, stopped answering, refused, done open with its line, missing
  scope); one result line at a time; the focus after each action.
- [ ] Implement in steps that each keep `make web` green: the panel and Sign-in; Check;
  Replace token; Commit author; Remove server; Add.
- [ ] Commit per step, e.g. `Show a git server's panel with Sign-in and Check (LAD-293)`.

## Task 6: UI e2e (all page requirements)

**Files:** `tests/ui/test_git_servers_section.py` (and its fake API wiring).

- [ ] Write the scenarios of the design doc's table against the fake API, no network; the
  canary token in the DOM; 1440, 768, 390 with no horizontal scroll; at 390 the Token tip
  leaves the token page link pressable and an ⓘ press never focuses its field; a screenshot
  per mockup frame.
- [ ] Run `uv run pytest -m ui tests/ui/test_git_servers_section.py`: pass.
- [ ] Commit `Test Settings → Git servers end to end (LAD-293)`; attach the screenshots to
  the build report.

## Task 7: The author in a worker's worktree (integration)

**Files:** `tests/integration/test_git_server_author.py`.

- [ ] Write `test_a_workers_commit_in_its_worktree_carries_the_author`: a session started on
  `https://git.test:8443/team/app.git` (LADO clones it from the local https server), a
  worker of the fake agent commits in its own worktree; the commit's author and committer
  are the server's; `test_a_remote_in_another_case_carries_the_author` with
  `https://GIT.test:8443/…`.
- [ ] Run `uv run pytest -m integration tests/integration/test_git_server_author.py`: pass.
- [ ] Commit `Test the commit author in a worker's worktree (LAD-293)`.

## Task 8: Docs and the pull request

**Files:** `docs/cli.md`, `docs/design/ui.md`, `docs/design/modules.md`, `CHANGELOG.md`.

- [ ] Write the docs of the design doc's Docs section; `uv run pytest tests/test_agents_md.py`.
- [ ] Regression: `make lint`, `make test`, `uv run pytest -m integration -n auto
  tests/integration/test_git_server_author.py tests/integration/test_git_server_access.py`,
  `uv run pytest -m ui tests/ui/test_git_servers_section.py tests/ui/test_settings_pages.py`,
  `make web`, `openspec validate git-server-check --strict`.
- [ ] Open the pull request from `feature/lad-293-git-server-check` to `main` with the design
  doc's manual check in its description.
