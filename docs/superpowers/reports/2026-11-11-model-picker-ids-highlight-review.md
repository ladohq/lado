# LAD-202 model-picker-ids-highlight: review report

Pull request #285 `hotfix/lad-202-model-picker-ids-highlight` → `main`. Scale: hotfix, depth
precision, the cascade of the shared `.mono` rule checked in breadth. Head reviewed: `9bf3c0c2`.
Model ids in the model picker and the other elements marked `mono` now show in the mono face
through one rule `.mono, .field input.mono { font-family: var(--mono) }`; the picker keeps its
highlight as a row's key, so a failed read that adds `Read again` no longer moves it to another
model. Delta: two added requirements of `model-settings-page`.

## Rounds

1. Local, head `b38c9bbf`. The diff `origin/main...b38c9bbf` in precision, and the cascade of
   `.mono` at all 17 places marked `mono` by computed style in Chromium. Findings F1, F2.
2. Local over the delta `b38c9bbf..9bf3c0c2`, and external 1, Claude Code GitHub Action: no
   blockers; E1 and E2 refuted. It read the risky files `web/src/ModelPicker.tsx` and
   `web/src/styles.css`; tests, docs and openspec were left to the local round.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | local: the field `Model id` of Model servers stayed in Inter: `.field input { font: inherit }` (0,1,1) beat `.mono` (0,1,0) | fixed in `9bf3c0c2`: the rule is `.mono, .field input.mono`; the UI e2e test checks the field, seen red before the rule |
| F2 | minor | local: the new paragraph of `docs/design/ui.md` was one unwrapped line | fixed in `9bf3c0c2` |
| E1 | — | external: the fallback to the selected row repeated in the effect (`Math.max`) | refuted: the effect sets `rows.find(selected)?.key ?? null`; `Math.max` is only in the render's index for a gone key |
| E2 | — | external: two rows with one key would take the highlight to the first | refuted: keys are unique by construction (`external:` from saved ids, `builtin:` from a `Set`, `extra` only when not built) |

## Found on the way

None.

## Checks

- Round 1: vitest `src/ModelPicker.test.tsx` 51 passed; `ruff format --check` green;
  `openspec validate model-picker-ids-highlight --strict` valid; the trial archive and
  `openspec validate --specs --strict` 82/82.
- Round 2: UI e2e `-m ui -k mono_face` on `9bf3c0c2` 1 passed.
- CI on `9bf3c0c2` green with `ci-ok`: unit 3.10/3.13, integration 6 shards, web, ui 4 shards,
  container amd64/arm64. Smoke skipped: every file on the skip list.

## Residual risk

- The face is tested in UI e2e only in the picker and Model servers (address, field Model id);
  Projects, Delete, Add repo, `Other name…` and a server's list ids were checked once in
  Chromium, with no lasting test.
- Rows widened by the mono face were checked only on the screenshots at 390 and 1280 px.
- No change to `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
  `tests/live/`: no live tests needed.
