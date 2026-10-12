# LAD-27 lead-recommendation: review report

Pull request #10 `feature/lad-27-lead-recommendation` → `main`. Scale: full change, review
depth: breadth. Head reviewed last: `997fd0c`; the archive commit follows it. Core (runs,
runtime, state with schema 26, hooks, the MCP tool `recommend`), the API's models, the web
UI's gate and question cards, `lado answer`, the lead's instructions, docs and the openspec
change; no provider code.

## Rounds

- **Round 1** (`aaaab1c..e310860`): local breadth pass over the whole diff with the lenses
  Spec, Tests, Silent failures, Comments, Types, General and the architecture against
  AGENTS.md (no provider detail above `providers/`, no silent drop, one source of truth but
  F4); the code and tests held against the spec, `tasks.md` and decisions D1–D13; the
  screenshots against docs/design/ui.md and the approved mockup v3. External round by the
  Claude Code Action (request comment 6132219244, "Claude finished" in comment
  6132222495). No blockers, no important findings.
- **Round 2** (return from `merge`, `e310860..997fd0c`): the archive at merge failed
  `openspec validate --specs --strict` (6 passed, 1 failed: the new capability's Purpose
  was the archive's placeholder); `997fd0c` adds `## Purpose` to the delta. Local precision
  pass, the archive tried in a copy outside the repository: 7 passed, 0 failed. External
  round (request comment 6132383017, finished in comment 6132387001): no defects, F5.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local: screenshot, code | When the lead's own step led to the gate, a recommendation with `disagrees` reads "disagrees with supervisor" (card and `lado answer`): `runs.recommendation_by` returns the note's actor without checking for the lead (`src/lado/runs.py`) | confirmed | minor | declined: one-line fix, left to the human |
| F2 | 1 | local | A request whose message ends `failed` leaves its gate or question `asked` ("preparing a recommendation…") until a stop or the lead's end: `state.recommendations_missed` counts only `delivered`/`read` | confirmed | minor | declined: rare (the lead is then `waiting` with its reason); residual risk |
| F3 | 1 | local: spec | No test that a worker's question's attachments go with the request; the code passes them through the same `_attach` the gate's tested path uses | confirmed | minor | declined |
| F4 | 1 | external (Action) | `state.LEAD` repeats `runtime.SUPERVISOR` | confirmed | minor | declined: the codebase's existing pattern (`artifacts.SUPERVISOR`, `kits.LEAD`); state cannot import runtime |
| F5 | 2 | external (Action) | The spec's Purpose says "never as a separate message", which no requirement states (the rule lives in the lead's instructions) | confirmed | minor | declined: a summary, not a rule |

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 3 (F1–F3) | 0 | — |
| external, Claude Code Action | 2 (F4, F5) | 0 | — |

No blocker or important finding.

## Found on the way

Three flaky tests the pull request does not touch, each green on a rerun, for BACKLOG.md:

- `tests/integration/test_agents.py::test_the_turn_that_goes_on_from_the_turn_end_output_reads_its_body`
  (CI check 3.10, run 38305180087: `['read','delivered'] == ['read','sent']`, a race with
  the short retry under load; 3/3 alone with `-n0`).
- vitest `web/src/Launch.test.tsx` (CI ui, run 38306731755: `Unable to find
  role="alert"`; related to the existing entry on Launch's vitest timeouts).
- smoke `tests/smoke/test_smoke.py::test_a_session_starts_takes_messages_and_stops[codex]`
  on macOS (run 38306731755: "the supervisor's turn reached no model API").

## Checks

- Round 1, local on `e310860`: `make lint` clean; `make test` 2540 passed;
  `uv run pytest -m integration -n auto tests/integration/test_flow_runs.py
  tests/integration/test_human_messages.py` 18 passed; `openspec validate --specs
  --strict` and the change valid. The developer's run: `make web` 661 vitest passed, UI
  e2e 51 passed.
- Round 2: the archive and `openspec validate --specs --strict` in a copy, 7 passed. Code
  unchanged since round 1.
- CI of PR #10 on `997fd0c` green: check (3.10, 3.13), js, ui, smoke ubuntu/macos ×
  claude/codex/kilo/opencode (ui and smoke macOS codex after one rerun, see Found on the
  way).
- Not run: live tests (release only). The change touches `runtime.py`, `hooks.py` and
  `mcp_server.py`, but no provider code.

## Residual risk

- F2 as behaviour.
- Codex CLI runs no hook for a turn that ends on an API error: the item stays `asked`
  until the lead's next turn end (by design, in AGENTS.md).
- Kit sdlc's supervisor paragraph "A gate opens…" still asks for a separate message to the
  human until the kit's own change.

## Result

Converged after round 2 (2 of 2 external rounds).
