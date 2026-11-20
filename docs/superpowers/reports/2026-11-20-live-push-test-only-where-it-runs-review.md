# LAD-308 live-push-test-only-where-it-runs: review report

Pull request #354 `fix/lad-308-live-push-test-only-where-it-runs` → `main`. Scale: tweak,
review depth: precision. Head reviewed: `96abcab8`. The live test
`test_an_agent_pushes_through_a_saved_git_server` narrows `live_provider` to Claude Code and
Codex by an indirect parametrization instead of calling `pytest.skip` for the others, so the
live cells of OpenCode and Kilo collect five tests and no skip, and pass under the unchanged
rule "a pass and no skip" of `scripts/smoke_ci.py`. Tests and docs only: no `src/`, `web/`,
schema or API change, no CHANGELOG.md line; a delta to continuous-integration (a new scenario).

## Rounds

1. Local, precision and a check against the design, `39d18386..96abcab8`. External 1,
   Claude Code GitHub Action: no new findings, it confirmed and extended F1; it read
   `tests/live/test_live.py`, `tests/live/conftest.py` and `docs/testing.md`, not the openspec
   files (documents, checked locally).

External rounds used: 1 of 1. Stand-ins: 0.

## The human's decisions

- **Scale tweak**, agreed in the task: tests and the CI docs only.
- **Gate `merge_ok`, approved** with no comment.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | local, confirmed externally: in `docs/testing.md:464-466` the new sentence is spliced mid-line, the line goes past 100 columns and the following "It runs them…" reads ambiguously | declined: style only, the paragraph's meaning is right; a minor in the last round opens no new round |

## Checked against the code

- AC-1: `uv run pytest -m live --collect-only -q -k <p> tests/live/test_live.py` collects 6
  tests for claude and codex, the push test among them, and 5 for opencode and kilo, without
  it; the whole `tests/live` without `test_codex_login.py` (what the cell runs) gives 5 for
  opencode too. The test's body has no `pytest.skip`.
- AC-2: the test's diff is the removed skip, the decorator and a comment; the fixture
  `live_provider` (`tests/live/conftest.py:31`) still checks the CLI and endpoint and sets up
  the environment.
- AC-3: `git diff origin/main...HEAD -- scripts tests/test_smoke_ci.py` is empty.
- The new scenario "A test meant for some providers only" joins the modified requirement; both
  earlier scenarios are kept word for word.
- Every task of `tasks.md` checked; nothing out of scope done.

## Checks

| Check | Result |
|---|---|
| `ruff check`, `ruff format --check` on `tests/live` | exit 0 |
| `openspec validate live-push-test-only-where-it-runs --strict` | valid |
| `openspec validate --specs --strict` after a trial archive | 89 passed |
| CI run 44742762818 on `96abcab8` | success |

## Metrics

Rounds: local 1, external 1, stand-ins 0. Confirmed: local 1 (minor), external 0 new.
Refuted: 0. Findings in code changed by the developer's clean-up: 0.

## Found on the way

Nothing.

## Not verified (residual risk)

- The live tests themselves were not run (real models, paid): the four green cells of
  `live.yml` (AC-5) are the supervisor's run on main's head before the tag `v0.48.0rc1`.
- The reviewer did not run `make test`: the only Python change is a live test, not collected
  without the `live` marker; CI ran the unit tests.

A change in `tests/live/`: named to the human, who may want the live tests before the merge.
