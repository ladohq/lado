# LAD-212 tui-input-ready: review report

Pull request #225 `hotfix/lad-212-tui-input-ready` → `epic/lad-154-models`. Scale: hotfix, with the
first round breadth first at the supervisor's request, as it changes the start of OpenCode and Kilo,
`hooks.handle` and `runtime.py`. Head reviewed: `f5a53dea` (= the remote head). An OpenCode or Kilo agent
stays `starting` until its TUI's prompt has focus, reported by a TUI plugin of its own; a TUI that stays
silent is ready after 30 s; a server's refusal for context reads in LADO's words; the body of a stopped
turn's message no longer repeats its line; the launch window links `docs/install.md`. No schema migration,
no MCP, CLI or API model change. Delta: `session-first-message` gets two requirements, `model-context`
one, and two of its requirements change.

Outcome: converged, no blocker or important finding left.

## Rounds

- **Round 1** (local, breadth first, `origin/epic/lad-154-models...4fd0b805`): spec, tests, silent
  failures, comments, general, architecture against AGENTS.md. The types lens was skipped: no new types.
- **Round 2** (local, precision, `4fd0b805..f5a53dea`), with reverse mutations.
- **External round 1** (Claude Code GitHub Action, requested 09:02:33 UTC, answered 09:03:59 UTC): no
  blockers, F1-F4 taken as closed.

External rounds used: 1 of 1. It read the risky files `hooks.py`, `state.py`, `runtime.py`, `base.py`,
`opencode_family.py`, both plugins, `kilo.py` and `opencode.py`. It did not open the tests, the documents,
the spec or `web/src/LaunchModel.tsx`, and says that closing F1 and F2 rests on the sources and on our
description; the reviewer read and probed the tests and the spec. It is of the same model family and took
56 s, so its "no findings" weighs little.

Metrics: confirmed 5 local, 0 new external (its point 3 was F5); refuted 0 local, 2 external;
unverifiable 1 (external); findings in code changed by a cleanup pass: 0. The cleanup touched only a
docstring; the fallback path did not go through it, and F1 was found there.

## Findings

| ID | Round | Source | Finding | Verdict | Level | Fate | Status |
|---|---|---|---|---|---|---|---|
| F1 | 1 | breadth: the fallback path | `tui.ready` arriving while an agent is `busy` with a lost paste left it `busy` for good and the message `sent` (probe: `('sent', 1, 'busy')` after 15 s) | confirmed | blocker | fix | resolved in `f5a53dea`, `test_a_tui_that_opens_while_a_paste_is_unconfirmed_gets_it` (both orders) and a unit test |
| F2 | 1 | breadth: tests, spec | The scenario "Lines given on the command line" had no test | confirmed | important | fix | resolved in `f5a53dea`, `test_lines_on_the_command_line_taken_before_the_report_change_nothing` |
| F3 | 1 | breadth: comments | `docs/design/agents.md` promised the 30 s reason only when the CLI is wholly silent, while `check_starts` fires before the plugin's timer | confirmed | minor | fix | resolved in `f5a53dea` |
| F4 | 1 | breadth: comments | The head of `opencode_plugin.js` lacked `tuiWait`, the map in `AGENTS.md` lacked the TUI plugin | confirmed | minor | fix | resolved in `f5a53dea` |
| F5 | 2 | precision + external point 3 | A paste of two lines, one confirmed by a real turn, then `tui.ready`: the agent is `idle` in mid-turn, so "A real turn has nothing unconfirmed" is false in this case | confirmed | minor | decline | declined, see below |
| F6 | 3 | external point 1 | Without `tuiWait` the timer fires almost at once | refuted | - | drop | `tui.silent` and `tuiWait` are written by the same `config()` in `opencode_family.py`, rewritten at each launch; no other path |
| F7 | 3 | external point 2 | `watch` fires on any focus, not only the prompt's: a dialog on the first frame would report early | unverifiable | - | residual risk | needs a real CLI with such a dialog |
| F8 | 3 | external point 4 | `typed_alone` is computed before `_wait_for_mcp` | refuted | - | drop | only the OpenCode family sets `ready`, and its `hold_first_turn` is `False`: never together |

**F1, how it closed.** `state.restart_typed` starts an unconfirmed paste over as a first attempt from this
hook, and an agent `busy` only because of it becomes idle. After one delay the message returns to the queue
through the ordinary `_plan`, which did not change. A late `tui.silent` leaves before `state.seen`.

**Reverse mutations of round 2**, on a `git archive` copy outside the repository; each went red:

| Mutation | What failed |
|---|---|
| The paste returns to the queue at once, with no wait | `test_a_paste_the_cli_held_is_not_typed_again_when_it_opens` (integration), `test_a_report_after_a_paste_starts_its_wait_again_and_the_paste_goes_in_again` (unit) |
| Any `tui.ready` makes a `busy` agent idle | `test_lines_on_the_command_line_taken_before_the_report_change_nothing`, 2 of 2 |
| A late `tui.silent` is not dropped | `test_a_late_silent_report_is_no_sign_of_the_agent` |
| `restart_typed` removed (the old F1) | `test_a_tui_that_opens_while_a_paste_is_unconfirmed_gets_it`, 2 of 2 |

The unit test `test_a_paste_confirmed_after_the_report_is_not_typed_again` stayed green under the first
mutation, as it counts pastes after the report only; the two others in the table hold that behaviour.

**F5, the probe.** Two lines pasted in one batch, `chat.message` confirms the first, then `tui.ready`:

```
TYPED  busy ['sent', 'sent']
BEFORE busy ['delivered', 'sent']
AFTER  idle ['delivered', 'sent']
```

The second line goes in after a delay, during the turn. It takes four conditions at once: a worker with
`--prompt`, a second message before `tui.silent`, a TUI later than 30 s, `chat.message` before `tui.ready`.

**F5, why declined.** A rare combination whose harm is an `idle` shown for part of a turn and a line typed
during it, not lost. Unfixed, it reaches the agent earlier than a fix would let it. The external round cap
was spent, and a minor finding opens no new round. The phrase "A real turn has nothing unconfirmed" stays
inexact in the pull request's description, `docs/design/agents.md` and `design.md`; the human passed the
gate without asking to correct it.

**F7, what it risks.** A dialog taking focus on the first frame would make the report come before the prompt,
and the dialog would eat the paste. By a reading of `_plan`, the ordinary path follows: no hook after the
paste, so it repeats, then `failed`, the agent `waiting` with the reason "answer the dialog in its window",
and the next hook returns the message. Nothing is lost without a trace. Whether such a dialog can come first
was not checked.

## Accepted deviations

- The fallback path: with hanging network traffic, protection is full for the first 30 s only (the human's
  choice).
- The LM Studio line is cut by 2 characters for `supervisor`; the spec was corrected, the mockup shows it
  whole (the supervisor's decision).
- `hooks.py`, `runtime.py`, `base.py` and `state.py` changed, against AC-9. The supervisor accepted the first
  three; `state.py` came on the second build visit, and the developer took it as an extension of the same
  deviation. No separate decision on it was seen.

Claude Code and Codex are untouched by the code, also after `f5a53dea`: `_not_ready` repeats the old `held`
condition, the early exit needs `event.note` and `restart_typed` needs `event.ready`, which are always empty
for them, as a test holds. `_plan`, the sweep and `_launch_command` did not change. `mcp_server.py`,
`agent_env.py` and `tests/live/` did not change.

## Checks on `f5a53dea`

| Check | Result |
|---|---|
| `make lint` | clean |
| `make test` | 5645 passed, 7 skipped |
| `make test-js` | 38 passed |
| `-m integration` on `test_session_loop.py`, `test_local_model_limits.py` | 16 passed |
| `openspec validate --specs --strict` | 67 passed |
| `openspec validate tui-input-ready --strict` | valid |
| CI | 23 of 23 |

## Not checked, residual risk

- A late TUI on a real CLI: F1 and its fix were checked on the fake agent only.
- The measure under load was not repeated on `f5a53dea`: the last, 10 of 10 with `attempts` 1, was on
  `e2959022`. The fix does not touch an ordinary start, but that is reasoning, not a run.
- A real LM Studio: only by the form of the human's report; the check is in the pull request's manual plan.
- `make web`, `-m ui` and the smoke were not run locally by the reviewer: CI did. The developer ran 4 smoke
  tests on real Kilo and OpenCode. `make test-live` was not run.
- F7: whether a dialog can come on the first frame.
- Double delivery: when a CLI took a paste and no confirmation ever comes, it goes in a second time. Why Kilo
  with hanging traffic once took a paste with no hook is unknown.
- That the loss on the LAD-211 developer's machine has this cause is not proved, as the design says.

## Found on the way

- `.lado/sdlc.md`, **Checks**: the line of `make test-js` names only `opencode_plugin.js`, so a change of
  `opencode_tui_plugin.js` alone falls outside it. The human keeps that file.
