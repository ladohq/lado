# LAD-126 phone-card-field-expands: review report

Pull request #139 `hotfix/lad-126-phone-card-keyboard` → `main`. Scale: hotfix, reviewed
by precision. Head reviewed last: `1255d33` (= the remote head). Only the web UI (the
card's focus handler, two CSS rules of the section "Phone layout"), its tests and the
documents changed; `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
`agent_env.py` and `tests/live/` did not, so no live tests were needed.

## Rounds

- **Round 1, local** (`498f07c..e94d37d`, the whole pull request): the diff read by hand,
  the change's spec held against the code (every requirement and scenario has code and a
  test), `tasks.md` all checked, D1-D4 kept, the screenshots against the mockup. No
  findings.
- **Round 1, external** (Claude Code GitHub Action; request 12:20:55Z, "Claude finished"
  12:21:20Z, reply with the triage in the pull request): no blockers, four notes (E1-E4).
  It is of the same model family, so its "nothing more" weighs less; it says it ran no
  tests and did not read openspec, the documents or the UI tests.
- **Round 2, local** (`e94d37d..1255d33`, `openspec/changes/phone-card-field-expands/`
  only): a return from merge, where the archive's `openspec validate --specs --strict`
  failed: two modified requirements grew past openspec's 500 characters. The modified
  "On a phone the composer stays at hand" is now word for word the living spec but for
  the THEN of "The expanded card"; hiding the tabs and the Team row moved to the added
  "On a phone an expanded card hides the session's tabs and the Team row". A trial
  archive in a scratch copy: 45 of 45 valid. L1.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| E1 | ext 1 | external | the ref `fromField` may stay set when the `[expanded]` effect does not run | refuted: it is set only with `setExpanded(true)` on a collapsed card (`WaitingCard.tsx:522-524`), and the effect (`WaitingCard.tsx:258-264`) always clears it; it goes with the component on unmount | — | dropped |
| E2 | ext 1 | external | `:has()` needs iOS 15.4 or later | refuted for this change: the expanded card already hides the feed and the composer with `:has()` (`styles.css:3976`); without it the old layout stays | — | dropped |
| E3 | ext 1 | external | the card does not fold when the field loses the focus | not a finding: the human's decision (D4, answer #834) | — | dropped |
| E4 | ext 1 | external | unit tests with stubbed `scrollIntoView`/`ResizeObserver` check logic only; an iPhone check is needed | not a finding: that is AC-5 | — | residual risk |
| L1 | 2 | local (precision) | the modified requirement's scenario "The expanded card" repeats the rule of the new added requirement | confirmed | minor | declined: duplication without contradiction; dropping the scenario would lose its updated THEN |

Metrics: 2 local rounds, 1 external, 0 substitutes. Local confirmed 1 (L1), refuted 0;
external confirmed 0, refuted 2 (E1, E2), not findings 2 (E3, E4). Findings in code
changed by the developer's cleanup: 0.

## Checks

- `make web`: 53 files, 984 passed, the build ok.
- `uv run pytest -m ui tests/ui/test_phone.py -n auto`: 27 passed.
- `openspec validate phone-card-field-expands --strict`: valid; `openspec validate
  --specs --strict`: 45 of 45 after the archive.
- CI on `1255d33`: 15 jobs success, `ci-ok` green; the smoke skipped (every file of the
  diff on ci.yml's skip list).
- Not run locally: `make lint` and `make test` (no Python changed; CI green).

## Not checked

- AC-5: an iPhone in Safari, where iOS moves the visible part of the window and scrolls
  to the field by itself; Chromium with a fake visual viewport cannot show it. The
  human's check by hand.
- That the tests were red before the fix rests on the developer's word; the reviewer is
  read-only and did not revert the code.
- The skip's comment field has no test of its own (the same selector and component as
  the own answer's).
