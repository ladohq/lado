# LAD-194 waiting-card-pinned-footer: review report

Pull request #218 `feature/lad-194-waiting-card-pinned-footer` → `main`. Scale: full, review
depth: breadth first. Head reviewed: `bb9589a3` (= the remote head). A tab of the waiting card
is split into a title (up to two lines), a context, the only part that scrolls, with a fade and
"↓ more", and a footer always in sight: the recommendation, the comment or choices, the
buttons. The title and the context together take at most 40 % of the chat. On Needs you the
card is whole, the page scrolls and nothing expands. While an own answer is open the composer
folds into a line. The web UI alone: no API, schema, MCP or CLI change. Delta: 24 requirements
added, 14 modified, 3 removed in `artifact-panel`, `chat-question-card`, `lead-recommendation`
and `phone-layout`.

## Rounds

- **Round 1** (local, breadth, `ae840669..153e2b75`): the lenses of spec, tests, silent
  failures, comments and a general one, and the architecture against AGENTS.md; types skipped,
  no new types. Found F1 to F15.
- **Round 2** (local, precision, `153e2b75..9efde252`): found F16 to F19.
- **External 1** (Claude Code GitHub Action, 30 s): requested too early, the request lacked
  F16, corrected on the pull request. Read `waitingParts.tsx`, `Recommendation.tsx` and about
  400 lines of `WaitingCard.tsx`. Found F20, F21, both refuted.
- **Round 3** (local, precision, `9efde252..7b5fb63a`): F16 to F19 closed, found F22.
- **External 2** (the whole `ae840669..7b5fb63a`, 1 min 7 s): read `WaitingCard.tsx`,
  `Recommendation.tsx` and the `.waiting-*` and phone rules of `styles.css`; no test, spec,
  `Chat.tsx`, `Composer.tsx`, `GateCard.tsx`, `Splitter.tsx`, `attachFiles.tsx` or
  `fieldHeight.ts`; ran nothing. Found F23 to F26.
- **Design QA** (`ui-review` run `lad-194-qa`, at `7b5fb63a`): verdict "to rework", 3 fix (C1 to
  C3) and 11 consider (C4 to C14).
- **Round 4** (local, precision, with a browser, `7b5fb63a..ef82e9b9`, in place of a second
  design QA, #3566): C1 to C4, F22, F23 checked, found F27, F28.
- **Round 5** (local, precision, with a browser, `ef82e9b9..bbdf1680`): F27, F28 closed, found
  F29. The external cap was reached; the human answered in #3584.
- **Round 6** (local, precision, with a browser, `bbdf1680..c5cc33d1`): F29 closed, no findings.
- **Gate `merge_ok`, refused:** the human's check on an iPhone found H1.
- **Round 7** (local, precision, with a browser, `c5cc33d1..3b2b1f34`): H1 closed in an
  imitation of the keyboard, found F30, F31. The human's #3637 changed the approach for Needs you.
- **Round 8** (local, precision, with a browser, `3b2b1f34..e44babaf`): Needs you checked, the
  chat's measures at 768 repeated and unchanged. Found F32, F33.
- **Round 9** (local, precision, `e44babaf..5b379c9c`, one spec file): F32 closed, no findings.
- **Refused archive** (integrator, at `5b379c9c`): after the archive `openspec validate --specs
  --strict` gave 55 passed, 3 failed (F34); undone before any commit.
- **Round 10** (local, precision, `5b379c9c..bb9589a3`, three spec files, no code): F34 closed, a
  trial archive in a copy gave 58 passed, no findings. No external round: the cap was reached.

External rounds used: 2 of 2. The external reviewer is of the same model family and saw no test
or spec; everything after `7b5fb63a` (C1 to C4, F22, F23, F27 to F29, H1, Needs you) it did not
see at all.

## The human's decisions

- **#3514:** F2, while a field has the focus on a phone the session's tabs hide too, the
  difference from frame g3-390-kbd accepted. F9, the height stays by content; 292 px was an
  example for a short note. F10, run `ui-review` against the g3 frames.
- **#3536:** F16, while a field of the footer has the focus on a phone the choices hide and come
  back on blur; a departure from the spec's priority, accepted.
- **#3551:** C1 for the card only, normal and expanded, 768×700 and 768×1024 included; the cut
  composer at 768 stays with LAD-193. C2, C3 fixed; C4, a fade at the bottom of an opened
  recommendation. C5 to C14 accepted unchanged.
- **#3552:** F43 closed: the choices on a desktop are limited to 4 rows, about 160 px.
- **#3584:** F29 fixed here, and the consequences of C1 in windows up to 900 px accepted: the
  card covers the feed until the page is scrolled to its end, the expanded card locks the page,
  and under a long open list of sessions or below about 400 px the footer comes up by the
  page's scroll.
- **Refusal at `merge_ok`:** fix Needs you by the report `pr218-phone-check-report-d0eb2d46.md`,
  add a keyboard test on Needs you.
- **#3637** (changes decision 6 of #3495 for Needs you): no 40 % limit, no fade and no "↓ more"
  there, the whole context, the page scrolls, no Expand; the browser leads the keyboard, so the
  buttons below the field may lie under it and are reached by scrolling.
- **Gate `merge_ok`, approved:** the second look on an iPhone done, nothing to remark.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | phone, several questions: a focused field left the view when the keyboard opened | fixed in `facdc34e` |
| F2 | important | phone, a focused field and little height: the buttons were cut | the human's #3514; fixed in `facdc34e`, `9efde252`, a question with a recommendation in F16 |
| F3 | important | `oneLine` removed every `*`, `_`, `` ` ``, `~` | fixed in `facdc34e` |
| F4 | important | phone, an expanded card: a focused field hid the context | fixed in `facdc34e` |
| F5 | important | the change differed from the code in three places | fixed in `facdc34e`, the rest in F19 |
| F6 | minor | the context's focus ring was cut on three sides | fixed in `facdc34e` |
| F7 | minor | a dead line `max-height … 40vh` | fixed in `facdc34e` |
| F8 | — | Android: Back closes the keyboard without `blur`, `typing` stays, the session's tabs and the choices stay hidden | unverifiable without a device; a residual risk, in `design.md` and the pull request |
| F9 | — | a gate at 1440×900 takes 363 px, AC-2 said about 292 | the human's #3514; the texts fixed in `facdc34e` |
| F10 | — | `ui-review` against the g3 frames had not run | the human's #3514; run `lad-194-qa`, its findings are C1 to C14 |
| F11 | minor | a file dropped on the chat with the composer folded is lost without a word | declined: follows from the approved D9, described in `docs/design/ui.md` |
| F12 | minor | the folded composer's line on a phone with a question is 44 px, not 40 | declined: its text is given word for word |
| F13 | — | `RecommendationBar` may carry `opened` to another tab | refuted: `key={shown.key}` on the panels |
| F14 | — | `useGrow` would not remeasure when the limit goes from 4 to 8 | refuted: `most` is among the effect's dependencies |
| F15 | — | a question with no choices and no free answer gives an empty area | refuted: `runtime.ask_human` refuses such a question |
| F16 | important | phone, a question with a two-line recommendation: Send cut with less than about 378 px above the keyboard | the human's #3536; fixed in `e2f0eb4f` |
| F17 | minor | `oneLine` left or broke part of the markup | fixed in `e2f0eb4f` |
| F18 | minor | the placeholder's rule reached the gate's field in Flows | fixed in `e2f0eb4f` |
| F19 | minor | two texts lagged behind the code | fixed in `e2f0eb4f`, `79cafe19` |
| F20 | — | external: the effect `setTyping(false)` has no dependency array | refuted: it runs on each render on purpose, a field may go with its question |
| F21 | — | external: `useLaidOut` watches only `firstElementChild` | refuted: the context is wrapped in one block |
| F22 | minor | `FENCE` took a first line with inline code for a fence, the line was lost | fixed in `c0768efc` |
| F23 | minor | external: U+E000 and U+E001 stood as raw bytes in the source | fixed in `c0768efc` |
| F24 | — | external, claimed important: `oneLine` rewrites every digit | refuted by a run: the mark is enclosed in U+E000 and U+E001 |
| F25 | — | external: the choices are hidden while Other… is open | accepted by the human with F16 |
| F26 | — | external: the choices' fade may not recount after `display: none` | refuted: the `ResizeObserver` is on the block itself |
| F27 | important | an expanded card, the window narrowed to 900 px or less: the footer outside the window, the page locked | fixed in `1f7c0f5f` |
| F28 | important | a card higher than the room from the chat's top to the window's bottom: the footer outside the window | fixed in `1f7c0f5f` |
| F29 | important | `--chat-top` went stale when the chat moved without a resize (the list of sessions opened) | the human's #3584; fixed in `c5cc33d1` |
| H1 | important | the human, on an iPhone: Needs you, an expanded card, a focused field: the card shrank to its tabs, the field and buttons hidden | fixed in `b1eccaeb` by #3637: no expanded card on Needs you |
| F30 | important | Needs you, a normal card: the buttons went under the keyboard as the field grew | dropped by #3637 with the code it was in |
| F31 | minor | the spec's "SHALL keep its context" against a context of 14 px | dropped by #3637 with the code it was in |
| F32 | important | the living spec `artifact-panel` still described an expanded card on Needs you | fixed in `5b379c9c`, the delta only |
| F33 | minor | the context on Needs you stays a needless Tab stop | declined: it needs a branch in `CardContext`; recorded in D17 |
| F34 | important | integrator: five requirements over 500 characters (930, 610, 599, 540, 506), so `openspec validate --specs --strict` failed after the archive | archive undone before any commit; fixed in `bb9589a3`, the specs' text only |
| C1 | important | design QA: at 768 the card's footer left the window | the human's #3551; fixed in `c0768efc`, `1f7c0f5f` |
| C2 | important | design QA: the placeholder in the dark theme had 3.74:1 | fixed in `c0768efc`; measured 6.63:1 dark, 6.13:1 light |
| C3 | important | design QA: at 390 the card's tabs did not fit | fixed in `c0768efc` |
| C4 | important | design QA: an opened recommendation was cut with no sign of more | fixed in `c0768efc` |
| C5 to C14 | — | design QA's points of consideration, not checked by the reviewer | accepted by the human, #3551 |

F34 passed every round because `openspec validate <change>` does not measure the length of a
modified requirement, and `validate --specs` does not see it before the archive. It is the third
such case after F6 of LAD-199 and A1 of LAD-192; a trial archive in a copy catches it.

## Checks

At `bb9589a3`: the archive itself and `openspec validate --specs --strict` 58 passed, 0 failed;
`ci-ok` green at the first attempt, every job passed, the smoke skipped as the pull request is
within CI's skip list.

At `e44babaf`, `web`, `src` and `tests` unchanged since: 19 measuring probes in Chromium passed;
`tsc` clean; vitest 62 files, 1234 passed; `make lint` clean.

Not run locally by the reviewer: `make test`, the whole `make test-ui`, `make test-integration`
(CI ran them), `make test-live` (at a release).

CI failures with no cause in the diff, on earlier heads:

- `3b2b1f34`, run 42095153328, `unit (3.10)`,
  `tests/test_server_providers.py::test_a_saved_key_replaces_lados_token_and_beats_the_outside_folders`,
  `KeyError: 'ANTHROPIC_API_KEY'`; one rerun passed. LAD-206.
- `c5cc33d1`, run 42071479238, `ui (1)`, `Run make dist`, `src/LoginSheet.test.tsx:238`,
  `TypeError: Cannot read properties of undefined (reading 'url')`; one rerun passed. Whether it
  has a task of its own is not clear from the reports.
- `ef82e9b9`, `integration (3.10, 2)`, `test_a_project_secret_is_found_nowhere_else`, a timeout
  of `start_session`; passed on the next heads, that head was not rerun: one case, not a proven
  flake.

## Metrics

Rounds: 10 local, 2 external, 0 stand-in, one design QA and two checks by the human on an iPhone.
Confirmed: 23 local, 2 external, 4 by the design QA with 10 accepted by the human unchecked, 1 by
the human, 1 at the archive. Refuted: 3 local, 4 external. Unverifiable: 1 (F8). Findings in code
changed by earlier fixes: 9 (F16, F17, F22, F27, F28, F29, F30, F31, F33). `providers/`,
`hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not change, so no
live test was needed.

## What was not checked

- The frames as the keyboard opens and closes (Minor of the iPhone report): whether the eye sees
  them is unknown; a risk in `design.md`.
- F8, Android's Back without `blur`: it needs a device.
- A tablet at 768 with a real keyboard: `sticky` and `dvh` may behave otherwise than in Chromium.
- Windows below 420 px have no test.
- The design QA was not repeated (#3566): C1 to C4 were checked by the reviewer, the other frames
  at 768 and 390 by the developer's eye. C5 to C14 were not checked.
- `usePageTop` will not see a shift when a block above the chat grows by exactly what a block
  below it loses; no such case was found in the layout.
- The flaky card test: the developer reproduced its failure on a copy of `main` under load (4 and
  7 of 160) and named a race of the test with a scroll frame, the new test 0 of 160; these runs
  were not repeated by the reviewer.
- The search for what is left about Needs you in the living specs went by words; not all specs
  were read whole. Repeated on the archived copy, nothing left.
