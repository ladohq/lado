## 1. Where keeps the last place (A)

- [x] 1.1 `Launch.tsx`: `Draft.placeChosen`, written on close; `placeTouched` starts from it
  (D1). Check: a new case in `web/src/Launch.test.tsx`: the recent places pending, Esc, open
  again, answer: Where shows the last place and Task the text; a second case where New empty
  folder was picked before the close stays; `make web`.
- [x] 1.2 UI e2e in `tests/ui/test_launch.py`: a local proxy holds `/api/folders/recent`; open,
  type a task, Esc, open again, release: Where shows the last place, Task the text; close and open
  once more: still the last place (D5). Check: `uv run pytest -m ui tests/ui/test_launch.py -k
  last_place`, run 5 times in a row. Built with `page.route` holding the requests (the
  file's `opened_with_the_recent_places_held`, LAD-281), not a proxy: holding a route needs no
  sleep, so the driver is never blocked.

## 2. Kit refusal texts (C)

- [x] 2.1 `kits.py`: the two texts of D2; `tests/test_kits.py`, `tests/test_runtime.py` follow;
  `docs/design/trackers.md` quotes the new text. Check: `make test`.
- [x] 2.2 UI e2e: a start refused because a kit expects a skill no kit gives shows `…add a kit
  that provides it to the session` and no `--kit`. Check: `uv run pytest -m ui <file> -k
  expects`.

## 3. Permission modes (D)

- [x] 3.1 `base.py`: `permission_mode_aliases`, `resolve_permission_mode`, aliases taken by
  `check_permission_mode`; `claude.py`: `manual` as an alias of `default`, auto's words (D3,
  D4); `runtime.py` resolves the mode before the session is stored. Check: `tests/test_providers.py`
  (`test_the_modes_words` updated, the alias), `tests/test_runtime.py` (start and resume with
  `manual` store `default`), `tests/test_cli.py` (help without `manual`); `make test`.
- [x] 3.2 UI e2e: Claude Code's Permissions list `Let Claude judge the risk`, its description
  when chosen, Team `Permissions Claude judges the risk`, no `auto` or `manual` row. Check: `uv
  run pytest -m ui tests/ui/test_launch.py -k permissions`.

## 4. Docs and CHANGELOG

- [x] 4.1 `docs/design/ui.md`: the draft line says a Where nobody chose is not kept and the
  last place is applied then; the Permissions line says aliases are not listed. `docs/cli.md`:
  `--permission-mode` takes Claude Code's `manual` as `default`. CHANGELOG.md 0.48.0
  (unreleased), Fixed: one line per finding (A: the last place after a window closed early; C:
  the kit advice fits the window; D: Claude Code's auto mode named in words, manual the same as
  Ask before changes). Check: read them.
- [x] 4.2 Screenshots of the Permissions list and the refusal as run artifacts, named in
  `build-report`; the items for the 0.48.0 RC's manual check (A on a slow network in Firefox,
  the texts of C and D) listed in the build report for the integrator.

## 5. Regression run

- [x] 5.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_launch.py`,
  `openspec validate last-place-mode-words-kit-advice --strict`, the trial archive.
