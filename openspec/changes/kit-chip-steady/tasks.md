## 1. The window

- [x] 1.1 `Launch.tsx` keeps the last kit list with a value and passes it to `LaunchTeam` as
  `known` while the next is asked; `kitsError` follows the current answer only (D1). Check:
  a new case in `web/src/Launch.test.tsx` where the second place's kit list is held pending,
  then answered; `make web`.

## 2. The test

- [x] 2.1 The phone test presses `Remove default` relative to the button, 5 px past its drawn
  right edge, instead of page coordinates (D2). Check: `uv run pytest -m ui
  tests/ui/test_launch.py -k 44_px_target`, run 10 times in a row (`--count` is not installed:
  a shell loop) and once with `-n 2` beside the rest of the file.

## 3. Docs and CHANGELOG

- [ ] 3.1 docs/design/ui.md: Kits' line says that the chips keep the last kit list while the
  next is asked; CHANGELOG 0.48.0 Fixed: a line that a kit chip no longer blinks its version
  when Where changes. Check: read both.

## 4. Regression run

- [ ] 4.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_launch.py`,
  `openspec validate kit-chip-steady --strict`, the trial archive.
