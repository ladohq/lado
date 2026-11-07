Task: LAD-199

## Why

Symptom (found in the audit of LAD-189, checked on main 931818bb with a real `lado server`,
real tmux and the fake agent): an open question to the human reads "Closed: the agent left"
after the server's restart in LADO's container. A server outside a container is not
affected: with `LADO_CONTAINER=0` the session, its tmux and the open question all survive
`lado server stop` and a new server. So the audit's doubt about its stand is settled: the
stand ran in the container, and this is how the container works.

Cause: the UI server's end in a container stops every session
(`runtime.stop_for_container`), and every stop closes the session's open questions
(`state._stop_session`, `_close_questions`), as nobody is left to get an answer: a resume
starts a new supervisor in a new conversation, and run workers are spawned anew. The same
path serves `lado stop` and `lado update`, and a resume after tmux went away. Closing is
correct while conversations do not survive a restart; what is wrong is that the loss is
silent:

- the card blames an agent that left, where the session was stopped;
- the resumed supervisor hears of open runs and gates, not of the questions (`runs.resume`):
  a question outside a run is lost to the team;
- Stop's popover and `lado stop` name the agents and messages a stop costs, not the
  questions.

Options weighed:

- A: no code, the task only asked to check. Costs nothing now; every container restart goes
  on losing questions without a word, against "No silent drops".
- B (taken): the question still closes, but says why, the stop warns of it, and the resumed
  supervisor gets each unanswered question to ask again. Small, needs no migration, and
  stays right when conversations survive a restart, which only stops closing them.
- C: keep the question open across a stop and hand the answer to the new agent. The new
  agent has no memory of why it was asked, and a run's new worker repeats its step and may
  ask again, so the human answers twice. ROADMAP's "Conversations survive a restart"
  (Later) removes that cause: the right time for it is then, at no extra cost.

## What Changes

- A question a stop closes gets its own state, `stopped`, and its card reads "Closed: the
  session stopped". A question whose agent ended or was finished keeps `closed` and "Closed:
  the agent left".
- The resumed session's supervisor gets one message from LADO listing the questions the
  stop closed unanswered, each with its asker, text and choices, once.
- Stop's popover and `lado stop` say how many open questions the stop closes.

## Out of scope

- Keeping questions open across a stop: option C, for the reason above.
- A warning before `lado update` or a container's stop: the container's stop has no one to
  ask, and the card and the notice cover both afterwards.
- Questions closed before this change: they keep `closed`, as nothing tells why they closed.
- `lado server stop` by hand inside the container stopping every session of its `LADO_HOME`:
  found on the way, a BACKLOG.md entry, not this task.

## Impact

- `src/lado/state.py`, `runtime.py`, `runs.py`, `cli.py`, `server/app.py`, `server/models.py`.
- `web/src/Question.tsx`, `SessionControl.tsx`, `web/openapi.json`, `web/src/api.gen.ts`.
- `docs/design/ui.md`, `docs/design/agents.md`, `docs/cli.md`, CHANGELOG.md.
- API: `question_state` takes `stopped`; `stop-preview` gains `questions`. No schema
  migration, no MCP or CLI option change: a fix, under `0.45.0 (unreleased)`.
