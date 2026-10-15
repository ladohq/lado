# LAD-70 waiting-card-answer-field: review report

Pull request #71 `fix/lad-70-answer-field-height` → `main`. Scale: tweak, reviewed for
precision (not widened: only the web UI changed, the fields' height, CSS and a rule taken
out of the composer). Head reviewed last: `afb463b` (= the remote head): the archive
commit `c391ead` and a merge of `main`. `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
`agent_env.py` and `tests/live/` did not change, so live tests are not needed before the
merge.

## Rounds

- **Round 1, local** (precision and the spec over `e8ac00c..126ffcc`): F1. `make lint`
  0, vitest 824 passed, UI e2e `test_chat.py` + `test_gates.py` 26 passed, openspec
  validate clean.
- **Round 1, external** (Claude Code GitHub Action, request 19:40:56Z, "Claude finished"
  19:41:59Z): E1 to E4, "ready to merge". CI on `126ffcc`: `ci-ok` pass. At the gate
  `merge_ok` the human sent F1 and E2 back.
- **Round 2, local** (precision over the delta `126ffcc..aecc899`): F1 and E2 resolved,
  F2 new. No second external round: a tweak has one, and the delta is a comment and a
  BACKLOG entry. The external reviewer is of the same model family, so its "nothing
  blocking" weighs less.
- **Round 3, local** (precision over `aecc899..afb463b`, back from `conflicts`): the
  archive `c391ead` moved the change unchanged and added its requirement to
  `openspec/specs/chat-question-card/spec.md`; the merge of `main` in `afb463b` keeps
  both CHANGELOG lines (LAD-70's and main's "One-line texts…", "Upgrade: schema 29"
  last), and `docs/design/ui.md` merged by itself. No new findings.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (comments) | `AgentPanel`'s doc comment stood over `AnswerField` and described the wrong function | confirmed (the external reviewer too, E3) | minor | fixed in `3c20639` at the human's word |
| E1 | ext 1 | external | `useGrow` would not rerun on mount if the field became conditional | refuted | — | both fields mount with their component (`AnswerField` keyed, `GatePanel`); the effect runs on mount; a finding about hypothetical code |
| E2 | ext 1 | external | a change of width (window resize, expanding or folding the card) does not recompute the height until the next input | confirmed | minor | not fixed here (the composer had the same before); a P3 entry in BACKLOG.md in `aecc899` at the human's word |
| E3 | ext 1 | external | the same as F1 | — | — | merged into F1 |
| E4 | ext 1 | external | the composer would grow by 2 px from the added border | refuted | — | `.composer textarea` has `border: 0` and the page has `box-sizing: border-box` |
| F2 | 2 | local (project rules) | commit `aecc899`'s message lacks the task key `(LAD-70)` at its end | confirmed | minor | declined: fixing it would rewrite pushed history |

Metrics: 3 local rounds, 1 external, 0 substitutes. Local confirmed 2 (F1, F2), refuted
0; external confirmed 1 new (E2) and 1 duplicate (E3), refuted 2 (E1, E4). Findings in
code changed by the developer's cleanup: 0.

## Spec check

The requirement "The card's text fields grow with their text and stay in view" and its
four scenarios: code in `fieldHeight.ts` (`grow`, `useGrow`), `WaitingCard.tsx`
(`AnswerField`), `GateCard.tsx` (`GatePanel`), `styles.css`; tests in
`fieldHeight.test.tsx`, `WaitingCard.test.tsx` and the UI e2e
`test_chat.py::test_an_own_answer_field_grows_to_8_lines_within_the_card_and_the_expanded_card`
and `test_gates.py::test_a_gates_long_comment_grows_to_8_lines_and_stays_above_the_send_row`,
whose screenshots show the card's list scrolled. All nine tasks checked; D1 to D7 kept.

## Checks

CI run 38796682385 on `aecc899`: `ui (1)` failed once on the vitest
`src/Launch.test.tsx > a window whose page goes away during a clone cancels it at once
with a beacon` (no beacon sent), outside the diff; `gh run rerun --failed` passed it, and
`ci-ok` passed. A flake, handed to the supervisor for the tracker. No code changed for it.
CI on `afb463b` (after the archive and the merge of `main`): `ci-ok` passed at once.

## Residual risk (not checked)

- After the merge of `main` the reviewer ran no local checks (the PR's code did not
  change); CI ran them green.
- The smoke was skipped by CI's `changes` rule.
- `scrollIntoView({ block: "nearest" })` on a narrow window and with the composer
  focused was checked only by reading (the e2e runs at 1280×900).
- The Skip field was not checked in a browser on its own (the same component, vitest).

Found on the way: E2 (BACKLOG.md P3), the `Launch.test.tsx` flake (to the supervisor).
