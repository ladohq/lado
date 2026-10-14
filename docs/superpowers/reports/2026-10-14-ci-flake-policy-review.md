# LAD-61 ci-flake-policy: review report

Pull request #43 `fix/lad-61-flake-policy` → `main`. Scale: tweak, no version bump (the
project's process settings `.lado/sdlc.md` only, no product code), review depth
precision. Head reviewed last: `b991278`; the archive commit follows it. No API, MCP, CLI
or schema change, no CHANGELOG.md line. `providers/`, `hooks.py`, `mcp_server.py`,
`runtime.py`, `agent_env.py` and `tests/live/` are untouched: no live tests needed before
the merge.

## Rounds

- **Round 1** (`origin/main...68de5e4`, local, precision): the diff read against the
  spec (AC-1-AC-7, tasks.md) and against the roles of kit sdlc. Found F1 (important) and
  F2 (minor).
- **Round 2** (`68de5e4..b991278`, local, precision on the delta): F1 and F2 fixed,
  nothing new.
- **External round 1 of 1** (Claude Code Action; request at 19:01:13 UTC, "Claude
  finished" between 19:01:29 and 19:02:04 UTC, delta `4435ba6..b991278`): no blocker;
  3 notes, all refuted, answered in the pull request. The external round cap for a tweak
  (1) is used.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | the flake trap had the reviewer search the tracker and propose a task, but the reviewer has no `tracker` skill, the only way into the tracker | confirmed | important | fixed in `b991278`: the reviewer leaves the search and the proposal to the supervisor with `send_message`; tasks.md 1.1, What Changes and AC-3 alike |
| F2 | 1 | local | the integrator's item ("follows step 3 as written") disagreed with the trap: the kit's step 3 sends a cause outside the work to the supervisor, the trap reruns without asking | confirmed | minor | fixed in `b991278`: "as written, after the Review trap's reruns for a CI job red with no cause in the work"; tasks.md 2.1, What Changes and AC-6 alike |
| E1 | 2 | external | two wordings for a red CI (the integrator's item and the trap) | refuted | — | both lead to the kit's rule: the trap for a job still red after the reruns, the item for what follows them |
| E2 | 2 | external | the limit "at most twice" may add up over rounds | refuted | — | the limit is per CI run (`gh run rerun <id>`); each push is a new run, as designed and approved by the human |
| E3 | 2 | external | the item must change if a local-only check appears later | refuted | — | a note on future upkeep, not a defect of this change |

| Source | Confirmed | Refuted |
|---|---|---|
| local | 2 (F1, F2) | 0 |
| external, Claude Code Action | 0 | 3 (E1-E3) |

## Not checked (residual risk)

- No tests or `make lint` run locally by the reviewer: no code changed; CI ran everything
  and is green on `b991278` (run 38620002312: check 3.10/3.13, js, ui, smoke ×8), with no
  flake and no rerun.
- The flake rule has not been carried out by any agent yet: checked by reading only; the
  first flake will show it in practice.
- The external reviewer is of the same model family as the kit's agents: its "nothing
  found" weighs less.

## Found on the way

None.
