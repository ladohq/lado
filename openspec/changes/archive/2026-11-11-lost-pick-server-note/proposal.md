Task: LAD-259

## Why

Found as minor finding F1 in the review of PR #269 (LAD-255). In the New session window the
human picks a model for one agent CLI (`kilo/large` for Kilo CLI), then switches Agent to Claude
Code or Codex that is not logged in and has exactly one saved model of a server (`CloudClaude`).
The Model field takes `CloudClaude` by itself, as LAD-255 made it, but the note under it reads
`kilo/large belongs to Kilo CLI, so the model is back to Claude Code's default.`: the opposite
of what the field holds. Start works; only the text is wrong.

Cause, in `web/src/LaunchModel.tsx`: the change of agent CLI writes the "lost pick" note at once,
as text, and sets the field to the CLI's default; the field's taking of the one server model
(LAD-255) runs a step later and does not touch that note, while its own note
(`For this session only: <CLI> is not logged in, so it runs on your server's model.`) is shown
only when no lost-pick note stands. The two features were written apart and never met in a test.

Options weighed (the human's answer #5790):

- Taken: the lost-pick note names both facts, `<name> belongs to <CLI>. For this session only:
  <new CLI> is not logged in, so it runs on your server's model.` The dropped pick stays named,
  as the requirement "A pick follows its agent CLI" asks, and the second sentence is the one the
  window already shows for the one server model. Long-term cost: none beyond one more branch of
  the note's text.
- The server-model note alone, the lost pick unnamed: shorter, but an exception to "A pick
  follows its agent CLI" that a later reader has to keep in mind.

## What Changes

- After a change of Agent that drops a pick, when the field then takes the new CLI's one saved
  model of a server by itself, the note under Model reads `<name> belongs to <CLI>. For this
  session only: <new CLI> is not logged in, so it runs on your server's model.` instead of
  `… so the model is back to <new CLI>'s default.`
- Every other note of the window, the field's value and what Start sends stay as they are.
- A patch (0.46.1): a fix of a text, no MCP tool, CLI or schema change.

## Scope

- `web/src/LaunchModel.tsx`: the lost-pick note is made from the dropped pick and the CLI it
  belonged to, its second part chosen at render by whether the field took the server model.
- `web/src/Launch.test.tsx`: a vitest test of the note in that switch.
- `docs/design/ui.md` (Launch and session control), CHANGELOG.md under `## 0.46.1 (unreleased)`.

## Out of scope

- The Resume window: a resumed session never takes the one server model by itself
  (`resuming === null` is a condition of it), so its note cannot be wrong this way.
- A switch to a CLI without its login and with several saved models: the field stays at the
  CLI's settings and is refused with `pick one`; the lost-pick note's `back to <CLI>'s default`
  stays true there.
- A UI e2e test: the note is pure rendering of state in one component; vitest catches it
  (AGENTS.md, Testing: the lowest layer).
