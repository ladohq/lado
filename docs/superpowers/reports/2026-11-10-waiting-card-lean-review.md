# LAD-266 waiting-card-lean: review report

Pull request #276 `feature/lad-266-waiting-card-lean` → `main`. Scale: full, depth breadth first.
Head reviewed: `a7f97751`. The waiting card goes back to LADO 0.44's look with only the approved
mockup's changes (`ui-design/gate-card-lean-3`): the question is a one-line head with its full
text in a tooltip, only the report scrolls in the chat, the supervisor's recommendation is a block
with a splitter, a choice gate shows its outcomes as pills with one Send, and Needs you and Flows
show cards at full height. The 0.45 work on the card's frame (Retry on a lost connection, the
stopped session's note, the 601–900 layout, the phone keyboard) is kept. New API field
`GateInfo.note_by`. Delta: changes to `chat-question-card`, `flows-overview`,
`lead-recommendation` and `phone-layout`.

## Rounds

1. Local, breadth, `origin/main...a49444fa`: F1–F12, R1–R3.
2. Local, precision, `8a04a252..f3c83e0d`: F13.
3. Local, precision, `f3c83e0d..7567c2a1`, and external 1 (Claude Code GitHub Action): E1–E4.
4. External 2, aimed at the files round 3 did not read: E5–E8.
5. After the human sent the change back from merge_ok with six remarks (fixed in `26a0aeec`):
   local, precision, `7567c2a1..8162e5e9`: the six fixes hold; F14.
6. Local, precision, `8162e5e9..a7f97751`: F14 closed, no new findings.

External rounds used: 2 of 2; none after the return from merge_ok. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | a question without options: after minimizing on a phone, Skip with a comment became an answer | fixed in `8d902ca4` |
| F2 | important | without a report the recommendation's splitter ignored the feed's room | fixed in `8d902ca4` |
| F3 | important | the `lead-recommendation` delta contradicted the code | fixed in `f3c83e0d` |
| F4 | important | the living spec kept "the field, 4 lines high" after archive | fixed in `f3c83e0d` |
| F5 | important | conflict with `main`, CI did not run | fixed in `8a04a252` |
| F6–F9 | minor | requirement names, the quote's margins, the gate tab's width test, a file in `tasks.md` | fixed in `f3c83e0d` |
| F10 | minor | the phone's splitter tested with a mouse, not a finger | declined |
| F11 | minor | the splitters' hover tested only as "the colour changed" | declined |
| F12 | minor | some scenarios without a browser test | declined: covered by vitest |
| F13 | important | expanded card without a report: the splitter did not rise above the window | fixed in `7567c2a1` |
| F14 | important | a choice gate's pick was lost on a tab change or minimizing, and Send sent the recommended outcome | fixed in `a7f97751`: the card keeps picks by gate id, like comments |
| E1 | minor | `gate_info` reads the note for every gate | declined |
| E2 | minor | `runs.recommendation_by`'s docstring speaks only of disagreement | declined |
| E3 | — | the tab's tooltip shows an internal state name | refuted: the spec asks for `step <state>` |
| E4 | minor | `touch-action` untested | declined: same as F10 |
| E5 | minor | a gate's busy and error state is lost on a tab change | declined: older than this change, see Found on the way |
| E6 | — | phone, choice gate with long labels | withdrawn: pills and one Send since `26a0aeec` |
| E7, E8 | — | `typing` reset after each render; `Splitter` with `hint={false}` | refuted |
| R1–R3 | — | the run page's comment field when stopped; "supervisor" hardcoded; no line without a report | refuted |

The human's six merge_ok remarks, fixed in `26a0aeec` and checked in round 5: no splitter for a
one-line recommendation; the grip over its line; the wheel over the recommendation's block; the
open gate's note whole; a choice gate picked then sent; a phone's whole recommendation on Needs
you.

## Found on the way

- E5: the card's gate panel keeps its busy state and upload error locally, so a tab change while
  files upload enables the buttons again and allows a second send. Older than this change; P2,
  size S: keep it in the card by gate id, as `gatePicks` now does.

## Checks

On `a7f97751`:
- vitest `WaitingCard`, `Chat`, `connection`: 251 passed (reviewer, round 6).
- UI suite (developer): 622 passed, 1 failure of `test_tab_brings_each_tab_clear_of_the_bars_ends`,
  the known flake LAD-267, green on rerun.
- CI: `ci-ok` green (run 42887096792), the pull request `MERGEABLE`/`CLEAN`.
- At archive: `openspec validate --specs --strict` 82 passed.

## Not checked

- The external reviewer did not see `26a0aeec`, `8162e5e9`, `a7f97751`: the round cap was spent;
  local rounds 5 and 6 and CI covered them.
- Integration, smoke and live tests were not run locally; CI ran integration and smoke.
  `providers/`, `hooks.py`, `mcp_server.py`, `agent_env.py` did not change.
- The phone's real keyboard: the human checks it in a simulator.
