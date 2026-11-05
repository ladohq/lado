# The waiting card with a pinned footer Implementation Plan

**Goal:** the footer of the waiting card (recommendation, comment or choices, buttons) is always
in sight; only the context scrolls; the card is as high as its content.

**Architecture:** `waitingParts.tsx` gives `AgentPanel` and `GatePanel` a top and a foot;
`RecommendationBar` is the line; the card reports a fold that `Chat` shows in the composer's place.
The web UI alone: no API, schema, MCP or CLI change.

**Tech Stack:** React, TypeScript, CSS, vitest, pytest with Playwright.

**Spec:** `openspec/changes/waiting-card-pinned-footer/` (AC-1..AC-16, D1-D15),
`docs/superpowers/specs/2026-11-05-waiting-card-pinned-footer-design.md`, LAD-189 spec §3 and §9.

## Global Constraints

- Colours by tokens only; focus keeps `:focus-visible`, fields their 3 px ring.
- UI texts word for word: `Context of the card`, `Choices`, `↓ more`, `Skip question`, `Supervisor
  recommends <option>:`, `Supervisor's recommendation:`, `· disagrees with <agent>`, `Answering
  question #<id> above · `, `Write to supervisor instead`, `Commenting on gate #<id> above`, `Choose
  an answer first`.
- Do not touch the error and Retry (LAD-195), `PHONE_QUERY` and the widths' layout (LAD-193), the
  stopped bar (LAD-196), the gate's card in Flows.
- Sections "Что работает" of both critiques stay as they are.
- CHANGELOG.md: one item under `## 0.45.0 (unreleased)`, by docs/release.md's rules.
- UI tests with `-m ui`; suites with `-n auto`. Layout claims go to the UI layer: jsdom has none.

## Tests per requirement (capability `chat-question-card` unless named)

| Requirement | vitest (`make web`) | UI e2e (`tests/ui/`) |
|---|---|---|
| footer stays, context scrolls | `WaitingCard.test.tsx`: parts and order, region's name, Needs you | `test_gates.py`: long note at 1440, 768, 390, footer in the window, only the context scrolls; `test_chat.py`: the same for a question |
| card by content, 40 % | none (needs layout) | `test_chat.py`: heights at 1440×900, a short gate; `test_needs_you.py`: 40 % of the window, at 800 px too |
| title, 2 lines, whole text | `WaitingCard.test.tsx`: cut text first in the context | `test_chat.py`: 3-line question |
| fade and "↓ more" | `WaitingCard.test.tsx`: click expands | `test_gates.py`: shown when cut, gone at the end, keys scroll the region |
| footer gives way | none | `test_chat.py`: six long choices, chat 420 px; `test_phone.py`: 440 px |
| single question's choices | `WaitingCard.test.tsx`: in the foot, group name | `test_chat.py`: 4 rows whole, 6 rows about 160 px; `test_phone.py`: 148 px |
| several questions | `WaitingCard.test.tsx`: no title, count in the foot | `test_chat.py`: Send in sight (the old long-questions test) |
| Skip question | `WaitingCard.test.tsx`: the old Skip tests renamed, second click, comment sent | `test_chat.py`: look and the sent skip |
| composer folds | `Chat.test.tsx`: line, link, draft and files, tab switch, stopped, composer's text kept; `Composer.test.tsx`: `folded` | `test_chat.py`: Other… and back, a quote |
| Send's reason | `WaitingCard.test.tsx`: hint on the wrapper, stopped note | `test_chat.py`: tooltip by hover |
| resize, kept height | `WaitingCard.test.tsx`: top's height from given | `test_chat.py`: the edge's test, double click gives the content's height, next card keeps it |
| fields 1 to 4 | `fieldHeight.test.tsx`, `WaitingCard.test.tsx` | `test_gates.py`: 4 lines, 8 expanded, 3 to 8 in Flows |
| ring whole | none | `test_gates.py`: ring tests with the new parts; `IN_WAITING_CARD` follows |
| `lead-recommendation`: the line | `Recommendation.test.tsx`: states, order of the disagreement, label, `oneLine`, no option | `test_gates.py`: the disagreeing gate, opened to 3 lines, expanded whole |
| `lead-recommendation`: ✓ | `WaitingCard.test.tsx`: ✓ goes on an unpick, name stays | none |
| `phone-layout`: field in focus | `WaitingCard.test.tsx`: `typing`, no expansion, fold words | `test_phone.py`: both keyboard tests rewritten at 440 px, blur shows all, a mouse changes nothing |
| `phone-layout`: above the keyboard | none | `test_phone.py`: 440 and 380 px |
| `phone-layout`: 44 px | none | `test_phone.py`: measured on a gate and a question |
| `phone-layout`: the others | none | `test_phone.py`: existing tests with the new wording |

No integration test: nothing crosses a process. Recommendations come from a fake in vitest and, in
UI tests, by `lado` state as `test_a_gate_with_a_recommendation_that_disagrees` does: the fake agent
gives none.

## Tasks

Follow `tasks.md`, in its order. Each task ends in a commit named by the repository's style with
`(LAD-194)`. Write the failing tests of a part first, then the part.

## Regression run

`make lint`, `make web`, `make test`, then `uv run pytest -m ui` on `test_gates.py`, `test_chat.py`,
`test_phone.py`, `test_needs_you.py`, `test_selection.py`, `test_session_head.py`, each changed
file with its marker, then `openspec validate waiting-card-pinned-footer --strict`. A whole `make
test-ui` once before the build report, as the task asks. Screenshots of every changed screen, in
both themes, as run artifacts; the design QA against g3-* comes after.
