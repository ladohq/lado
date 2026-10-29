## 1. The failing tests (UI e2e: layout in a real browser, D3)

- [x] 1.1 `tests/ui/test_project_page.py`, beside the phone tests: a test for the scenario
  "A project's page longer than the phone's screen". On the `phone` fixture (UPRIGHT,
  touch), `/projects/shop`; check that the Delete project block is below the screen at
  first, move the mouse over the page and `page.mouse.wheel(0, 3000)` (D2), then the block
  is within the viewport (its bounding box's bottom at most the window's height) and
  `window.scrollY` is 0. No `scroll_into_view_if_needed` and no script scrolling. A
  screenshot of the page's end (light and dark). Fails before 2.1.
- [x] 1.2 `test_on_a_phone_the_delete_block_and_dialog_fit` reaches the Delete block with
  the wheel as 1.1 does, not `scroll_into_view_if_needed` (the false green of the
  proposal's Why).
- [x] 1.3 `tests/ui/test_projects_section.py`: a test for the scenario "A project list
  longer than the phone's screen": enough projects made before `server` (e.g. 30 with
  `projects.create`) that the list is longer than the screen; on the phone, the wheel over
  the list brings the last project's row into the viewport, `window.scrollY` stays 0.
  Fails before 2.1.
- Run: `uv run pytest -m ui tests/ui/test_project_page.py tests/ui/test_projects_section.py`.

## 2. The fix

- [x] 2.1 `web/src/styles.css`, the phone section, `:root[data-phone] .projects`: add
  `height: 100%` (D1); the comment above it says the list or the project scrolls by itself,
  as on Sessions. 1.1 and 1.3 pass; the narrow computer window's test
  (`test_project_page.py`, the 390 px viewport without touch) still passes.

## 3. Docs

- [x] 3.1 `docs/design/ui.md`, Projects, Layout: on a phone the list and the project each
  scroll by themselves under the top bar (LAD-159).
- [x] 3.2 CHANGELOG.md, `## 0.44.0 (unreleased)`, `### Fixed` (added under Added): **A
  project's page scrolls on a phone.** Its variables, secrets and Delete project were cut
  off below the screen; the project list scrolls too.

## 4. Checks

- [x] 4.1 `make lint`, `make web`, `make test`, the UI files of 1.x with `-m ui`,
  `openspec validate phone-projects-scroll --strict`, `openspec validate --specs --strict`.
