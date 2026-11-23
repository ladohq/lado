## 1. The hook

- [ ] 1.1 `web/src/useScrollAnchor.ts`: `settle` acts on `moved + stopped !== 0`; a target past
  the container's end first grows the section's inline bottom padding by what is missing (D1,
  D2); the hook's header comment says so in place of "a page getting shorter stops the scroll
  earlier by itself". Check: the unit tests of 1.3.
- [ ] 1.2 The container's `scroll` listener trims the padding to the part in view; the
  cleanup empties it (D3, D4). Check: the unit tests of 1.3.
- [ ] 1.3 `web/src/useScrollAnchor.test.tsx`: the browser imitation clamps at the content's
  end and counts the section's padding; the five new tests of design.md, Tests. Check: `make
  web` (vitest) green, the old tests unchanged and green.

## 2. The page's e2e

- [ ] 2.1 `tests/ui/test_models_section.py`,
  `test_a_server_added_ticked_renamed_unticked_refreshed_and_removed`: `margin-bottom` gone
  from the injected style; the page scrolled to its very end before Add server and before the
  Remove confirm; the `stays` checks as now (AC-1). Check: `uv run pytest -m ui
  tests/ui/test_models_section.py -k removed`.
- [ ] 2.2 A new test there: Change of a saved server at the page's end keeps the row's place;
  a scroll up and back to the end leaves no padding (AC-2, AC-3). Check: `uv run pytest -m ui
  tests/ui/test_models_section.py -k <its name>`.

## 3. Docs

- [ ] 3.1 `docs/design/ui.md`, **Nothing moves under the pointer**: the closing sentences on
  the very end of the page say the hook leaves blank room under the section as tall as it
  needs, trimmed to what is in view on each scroll, instead of the limit. Check: read it.
- [ ] 3.2 CHANGELOG.md, under the unreleased patch heading, group Fixed: at the bottom of
  Settings → Model servers and Git servers a form that closes no longer moves the page.
  Check: read it.

## 4. Regression run

- [ ] 4.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui
  tests/ui/test_models_section.py tests/ui/test_git_servers_section.py`, `openspec validate
  page-end-keeps-place --strict`, the trial archive; CI of the pull request green (AC-6).
