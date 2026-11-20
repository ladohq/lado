# LAD-302 codex-model-smoke-waits-for-list: review report

Pull request #348 `fix/lad-302-codex-model-smoke-waits-for-list` → `main`. Scale: tweak, review
depth: precision. Head reviewed: `ffa1acfb`. After `/model`,
`test_model_of_a_codex_agent_on_a_server_shows_its_model_alone[codex]` (`tests/smoke/test_smoke.py`)
waits for `On Шлюз`, LADO's own text that shows only in Codex's list of models, instead of the
model's name, which Codex's status line shows before `/model` too. Tests only: no `src/`, `web/`,
schema or API change, no CHANGELOG.md line, no delta.

## Rounds

1. Local, precision and a check against the design, `origin/main...ffa1acfb`. External 1, Claude
   Code GitHub Action: no blockers, one finding (F1); every risky file read, `.openspec.yaml` not
   read (two lines of metadata).

External rounds used: 1 of 1. Stand-ins: 0.

## The human's decisions

- **Gate `merge_ok`, approved** with no comment.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | — | external: a narrow pane could wrap `On Шлюз` onto two lines and the wait would time out | refuted: not a new risk, the same text was asserted before the change (`test_smoke.py:920`); the list's line is short |

## Checked against the code

- AC-1: the wait after `/model` checks `"On Шлюз" in tmux.capture(...)` (`test_smoke.py:916`);
  the assertions after it are unchanged. `On Шлюз` is `f"On {server.name}"` of
  `src/lado/providers/codex.py:959`, the server named `Шлюз` at `test_smoke.py:852`.
- The race is confirmed by the code: `CODEX_MODEL = "Шлюз GPT"` (`test_smoke.py:838`) is in
  Codex's status line before `/model`.
- Every task of `tasks.md` checked; nothing out of scope done.

## Checks

| Check | Result |
|---|---|
| `make lint` | exit 0 |
| `openspec validate codex-model-smoke-waits-for-list --strict` | valid |
| Trial archive (`--skip-specs`) and `openspec validate --specs --strict` | 87 passed, 0 failed |
| CI run 44700537185 on `ffa1acfb` | green after `rerun --failed` of `integration (3.10, 3)` (a flake, below) |
| `smoke macos-latest codex` | green five times in a row (four in the build, one on `ffa1acfb`) |

## Metrics

Rounds: local 1, external 1, stand-ins 0. Confirmed: 0. Refuted: external 1 (F1). Findings in
code changed by the developer's clean-up: 0.

## Found on the way

- Flake `tests/integration/test_clone_start.py::test_ctrl_c_during_the_clone_leaves_nothing`
  (Python 3.10, shard 3): after Ctrl+C the child git is still alive at the check (`:90`).
  Outside the task; handed to the supervisor.

## Not verified (residual risk)

- The probe of AC-2 and the local smoke runs were done by the developer only.
- The flake is rare: five green runs show no regression; the cause is shown by the probe.
- The external reviewer is the same model family: its "nothing found" weighs accordingly.

No change in `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
`tests/live/`.
