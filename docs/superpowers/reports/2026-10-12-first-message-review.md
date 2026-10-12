# LAD-19 first-message: review report

Pull request #8 `feature/lad-19-first-message` → `main`. Scale: full, review depth:
breadth. Head reviewed last: `3aaa26b`; the archive commit follows it.

## Rounds

- **Round 1** (`main..3aaa26b`): local breadth review (spec, tests, silent failures,
  comments and descriptions, types, general, architecture against AGENTS.md; the UI
  checked against its screenshots and `docs/design/ui.md`) and an external round by the
  Claude Code GitHub Action
  (https://github.com/ladohq/lado/pull/8#issuecomment-6124608047): no errors found, one
  minor remark (X1, refuted). No blockers, no important findings; the loop converged
  after one round (1 of 2 external rounds used).

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| m1 | 1 | local: general | `cmd_start` marks the text it read with `hasattr(args, "prompt_text")`, so the second call after a clone does not read stdin again; an attribute flag on the Namespace is not obvious | confirmed | minor | declined: works, local to `cli.py`, covered by `test_a_git_url_reads_stdin_once_before_the_clone`; the external reviewer agreed |
| m2 | 1 | local: types | The window counts the first message's length in UTF-16 (`String.length`), the core in code points | confirmed | minor | declined: the composer does the same (`web/src/Composer.tsx`); UTF-16 is never shorter, so the window can only refuse earlier, never let through what the server refuses |
| X1 | 1 | external (Action) | `Launch.prompt` / `Resume.prompt` take `""`; unclear whether the API answers 400 and whether a test covers it | refuted | — | `tests/test_server_launch.py::test_an_empty_prompt_is_400_with_the_cores_text` checks the 400 with the core's text for start and resume |

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 2 (m1, m2) | 0 | — |
| external, Claude Code Action | 0 | 1 (X1) | — |

Found on the way (outside the task): none.

## Checks

- On `3aaa26b`: `make lint` clean; `make test` 2487 passed;
  `pytest -m integration -n auto tests/integration/test_session_start.py` 4 passed;
  `pytest -m ui tests/ui/test_launch.py` 13 passed; `make web` 647 vitest passed, build
  and type check clean; `openspec validate first-message --strict` valid.
- CI on `3aaa26b`: 12 of 12 jobs green (check 3.10/3.13, js, ui, smoke on Linux and
  macOS for claude, codex, kilo, opencode).
- At archive: `openspec validate --specs --strict` 5 passed, 0 failed.

## Spec coverage

Every requirement and scenario of `session-first-message` has code and a test: the core
(`tests/test_runtime.py`, `tests/test_codex.py`), the CLI (`tests/test_cli.py`, ten
scenarios, stdin read once across a clone and a file that is not UTF-8 included), the API
(`tests/test_server_launch.py`), the UI (seven vitest tests and the e2e tests) and two
integration tests through the real queue, hooks and loop. Every task of `tasks.md` is
checked.

## Residual risk

- `src/lado/runtime.py` changed (`start_session`, `check_prompt`); live tests were not
  run (only at a release, Claude Code with the human's yes). The smoke passed in CI for
  every provider; the first message on a real CLI (Kilo and OpenCode by `--prompt`, Codex
  by `[PROMPT]`) is checked by unit tests of the argv, not with a live model.
- `make check` and `make test-integration` were not run whole locally; CI ran them green.
