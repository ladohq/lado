## 1. The verdict

- [x] 1.1 `scripts/ci_rerun.py`: `verdict(...)` (design D3, D4) and the command
  `ci_rerun.py <run-id> [--rerun]` (D5), standard library and `gh` only, module docstring
  as `ci_ok.py`'s. Check: `tests/test_ci_rerun.py`, one test per scenario of the delta plus
  a green run and a job cancelled after it started; `make test`.
- [x] 1.2 Run `uv run python scripts/ci_rerun.py <id>` without `--rerun` on 41529673835,
  41496744121, 41522042790 and one green run; put the four printed verdicts into
  `build-report` (AC-3).

## 2. The workflow

- [x] 2.1 `.github/workflows/ci-rerun.yml` (D1, D2, D5, D6). Check: tests of the file
  (trigger, `if`, permissions, the command, no checkout of the pull request's code);
  `make lint`, `make test`.

## 3. Docs

- [x] 3.1 `docs/testing.md`, the CI section: the runner-less macOS cells (cause,
  annotation) and `ci-rerun.yml`; `scripts/` line of AGENTS.md's layout only if it lists
  scripts by name (it does not today: leave it). Check: by reading against AC-4.
- [x] 3.2 `.lado/sdlc.md`, Review traps, the entry "A CI job red with no cause in the
  work": the sentence of D8. Check: `git diff origin/main -- .lado/sdlc.md` shows only it.
- [x] 3.3 `openspec validate ci-rerun-runnerless-jobs --strict` and
  `openspec validate --specs --strict`.
