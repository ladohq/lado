# LAD-136 chat-time-edge: review report

Pull request #154 `fix/lad-136-chat-time-edge` → `main`. Scale: tweak, reviewed by
precision. Head reviewed last: `5eb87286` (= the remote head). Only the web UI
(`FeedRow.tsx`, `GateCard.tsx`, `styles.css`), its unit and UI tests, `docs/design/ui.md`,
the spec delta and CHANGELOG.md changed; `providers/`, `hooks.py`, `mcp_server.py`,
`runtime.py`, `agent_env.py` and `tests/live/` did not, so no live tests were needed.

## Rounds

- **Round 1, local** (`origin/main...676ec437`, the whole pull request): found F1
  (important), F2, F3, F4 (minor). No external round requested yet.
- **Round 2, local** (`676ec437..5eb87286`): F1 and F2 fixed, nothing new. The tests'
  selectors `.feed-head time` (a descendant) still find the time inside `.feed-when`; the
  button has `align-self: center` and takes no part in the head's baseline.
- **Round 3, external** (Claude Code GitHub Action, 1 of 1; request
  issuecomment-6365346063, "Claude finished" in issuecomment-6365351448, newer than the
  request): no blockers, two optional notes (E1, E2). It read the risky files
  `FeedRow.tsx`, `GateCard.tsx`, `styles.css`, `Chat.test.tsx`; the UI tests, documents
  and openspec were read locally in rounds 1-2. It is of the same model family, so its
  "nothing more" weighs less.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (CSS, probe in Chromium) | a wrapping head (`flex-wrap: wrap`) could put Copy message and the time on different lines; the time then stood at the next line's left edge, breaking "Every time on the right of a chat row ends on one edge" | confirmed | important | fixed in `5eb87286`: the button and the time in one block `.feed-when` (`margin-left: auto`, `flex: none`); test `test_a_heads_time_stays_on_the_edge_when_the_head_wraps`, red on the old code |
| F2 | 1 | local | on a touch screen a continued row kept 26 px of padding for the hidden button | confirmed | minor | fixed in `5eb87286`: `padding-right: 0` under `@media (hover: none)`; checked in `test_on_a_touch_screen_copy_code_always_shows_and_copy_message_never` |
| F3 | 1 | local (spec) | no UI test that the agent's page hides Copy message on a touch screen; the rule itself is right | confirmed | minor | declined: needs a new UI test; the selector checked by reading |
| F4 | 1 | local | the first build report called CI green while the run of that head was still going | confirmed | minor | declined: wording of a report; CI on `5eb87286` green |
| E1 | 3 | external | `-9px` (`.chat-gate.closed`) and `-6px` (the button) are tied to the head's padding, border and icon size | confirmed | minor | declined: both commented; the UI test (`assert_one_edge`, the 6 ± 1 px check) fails if they drift |
| E2 | 3 | external | `display: none` on a touch screen also hides Copy message from a screen reader | confirmed (mechanism) | minor | declined: what `selection-actions` requires by the human's choice (round 2 of the design) |

Metrics: 2 local rounds, 1 external, 0 substitutes. Local confirmed 4, refuted 0;
external confirmed 2, refuted 0. Findings in code changed by the developer's cleanup: 0.

## Checks

- Round 1: `make lint` green; `openspec validate chat-time-edge --strict` valid;
  `openspec validate --specs --strict` 46 passed.
- Round 2: `uv run pytest -m ui -n0` on the edge, wrap, touch and hover tests of
  `tests/ui/test_chat.py` and `tests/ui/test_selection.py`: 7 passed, 34 deselected, on a
  fresh bundle.
- CI on `5eb87286`: success, `ci-ok` green; the smoke skipped (every file of the diff on
  ci.yml's skip list).
- At archive: `openspec validate --specs --strict` 47 of 47, after writing the Purpose of
  the new capability `chat-feed-times`.

## Not checked

- The agent's page on a touch screen has no test (F3).
- `make test`, `make web` and the full UI tests were not run by the reviewer; CI ran them
  on `5eb87286` (green), and the developer did.
