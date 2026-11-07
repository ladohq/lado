# LAD-227 refuse-delivery-to-stopped-session: review report

Pull request #245 `hotfix/lad-227-stopped-session-delivery` → `main`. Scale: hotfix, review depth:
precision by the design, widened to breadth in round 1, as the change is in `runtime.py` and
`tmux.py`, which all delivery rests on, and the supervisor asked for it. Head reviewed: `e2be3244`.
A message whose delivery a session's end cuts off is refused with one sentence and a 400, not a
500; a real tmux failure in a running session stays an error; `send_text`, `new_window` and
`capture` name the session and window exactly. No schema, API model or `web/src` change. Delta:
three requirements added to `stopped-session`.

## Rounds

1. Local, breadth, `be3e5821..c02cea6b`: every way through `_deliver` and every call of
   `send_text`, `new_window` and `capture`. External 1, Claude Code GitHub Action: "no blocking
   findings", it read `runtime.py` and `tmux.py` by the diff, not the tests or documents. CI red:
   F3.
2. Local, precision, `c02cea6b..e2be3244` (`24f16795`, `e2be3244`): `_to_running` and `_deliver`
   give the sentence only for a session with `stopped_at` or with its tmux gone; an unknown session
   gets `no running agent` or `unknown session`. A stopped session whose recipient never was in it
   gets the sentence too: `state.stop_session` forgets the agents, so `_check_running` cannot tell
   them apart, and D3 holds. No external round: the cap of 1 was used.

External rounds used: 1 of 1. Stand-ins: 0.

## The human's decisions

- **Design:** no "not delivered" mark on the dropped message in the feed, decided on 2026-11-07.
- **Gate `merge_ok`, approved** with no comment: F1, F2 and F5 stay declined, and no live tests
  were asked for.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F3 | important | CI, integration shard 3 on Python 3.10 and 3.13: `_to_running` gave the sentence for a session not in the database too, promising Resume for a session that cannot be resumed | fixed in `24f16795`; `test_fake_agent` passes unchanged, two new tests |
| F1 | minor | "Send it again after Resume" also reaches a flow step LADO sent itself, where `runs.resume` picks the step up | declined: needs a stop during the typing, and one text for all callers is out of scope in the proposal |
| F2 | minor | AC-2 names an integration test for tmux gone without a stop; there is only a unit test | declined: a hand probe on tmux 3.3a shows `tmux_gone` True on `can't find session` and `no server running`, False on `can't find window` |
| F5 | minor | the new BACKLOG entry names `runtime.finish_worker`, the hint is in `close_worker`; long lines left in `docs/design/agents.md` and D3 of `design.md` | declined: no effect on behaviour, and a minor of the last round starts no new round |
| F4 | — | external: `tmux.window_size(target)` may get a target without `=` | refuted: all three calls pass `=` (`terminal.py`) |

## Checks

| Check | Head | Result |
|---|---|---|
| CI of the pull request, required `ci-ok` | `e2be3244` | green: run 42370655782, 23 of 23 |
| smoke | `e2be3244` | passed in CI |
| `make lint` | `e2be3244` | clean |
| `make test` | `e2be3244` | 4845 passed, 7 skipped |
| `uv run pytest -m integration -n auto tests/integration/test_fake_agent.py tests/integration/test_human_messages.py` | `e2be3244` | 15 passed |
| `openspec validate refuse-delivery-to-stopped-session --strict` | `e2be3244` | valid |
| `openspec validate --specs --strict`; trial archive | `e2be3244` | 67 and 67 passed |

`make check` and `make test-integration` as a whole were not run locally: CI ran what they hold.
`make web` and the UI tests were not run locally in the review: `web/src` did not change, and CI's
UI jobs are green. The live tests were not run: `runtime.py` changed, and the human was told so at
the gate; `providers/`, `hooks.py`, `mcp_server.py`, `agent_env.py` and `tests/live/` did not.

## Metrics

Rounds: 2 local, 1 external, 0 stand-in. Confirmed: 3 local (F1, F2, F5), 1 by CI (F3), 0 external
in the table; its hint on `kill-window` held and went to BACKLOG.md. Refuted: 0 local, 1 external
(F4). Findings in code changed by the developer's cleanup: 1 (F3: the line came from `8b5e3597`,
though D2 of the design already counted an unknown session as ended).

## What was not checked

- The fix `24f16795` was seen by no external reviewer, as the cap was used; only the reviewer read
  it, and the external round of the same model family had judged the wrong behaviour right.
- The reviewer saw the unknown session in round 1, took it for negligible and asked for the external
  round before CI's result; only CI caught it.
- No lasting check says "no 500 in the browser" in the UI tests. The developer measured it with a
  temporary plugin: 0 in 3 runs with the fix, 1, 1 and 3 without it.

## Found on the way

All in BACKLOG.md at `e2be3244`; no tracker task was created.

- The hints for a manual `kill` name their target without `=`.
- `tmux.capture` is called only from tests.
