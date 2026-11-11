## 1. The note

- [x] 1.1 Vitest, failing first, in `web/src/Launch.test.tsx`: Kilo CLI with `kilo/large` picked,
  then Agent to Claude Code (`login_missing`, `starts_on_server`, one saved model `CloudClaude`):
  the field holds `CloudClaude`; the text `kilo/large belongs to Kilo CLI. For this session
  only: Claude Code is not logged in, so it runs on your server's model.` stands under Model;
  neither `back to Claude Code's default` nor a second `For this session only` note is shown;
  the start sends `model: "CloudClaude"`. Then a change of Agent to a third CLI removes the line.
- [x] 1.2 `web/src/LaunchModel.tsx` by D1-D3: the lost pick kept as `{ name, from }`, the note
  made at render. Check: 1.1 green, and the existing test "another agent CLI takes the field to
  its default, and says what went" still reads `… so the model is back to Claude Code's
  default.`; `make web` green.

## 2. Docs

- [ ] 2.1 `docs/design/ui.md`, Launch and session control: after the sentence on the one saved
  model taken by itself, the note after a change of Agent that dropped a pick (`<name> belongs
  to <CLI>. For this session only: …`). CHANGELOG.md under `## 0.46.1 (unreleased)`, Fixed: the
  note under Model names the server model the field took after a change of Agent (LAD-259).

## 3. Regression

- [ ] 3.1 `make lint`, `make web` (vitest, tsc, build), `uv run pytest -m ui
  tests/ui/` for the launch window's files (`grep -l "New session\|launch" tests/ui/*.py`),
  `openspec validate lost-pick-server-note --strict` and the trial archive of the settings'
  Checks.
