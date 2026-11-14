# LAD-271 ui-test-time-limit: review report

Pull request #303 `fix/lad-271-ui-test-time-limit` → `main`. Scale: tweak, depth precision.
Head reviewed: `f659d7c2` (the code as of `dcb501b5`, then the archive and a merge of `main`). A CI cell `ui (<k>)` sometimes hung until GitHub cancelled the whole
job, which kept neither the pytest log nor the junit report, so nobody knew which test hung. Each
UI test now has a limit of 120 s (pytest-timeout, method `thread`, with faulthandler's thread
stacks written 5 s before it) set in `tests/time_limit.py` for `tests/ui/` alone, and the `ui`
job's pytest step has `timeout-minutes: 12` under the job's 25.

## Rounds

1. Local, precision, over `origin/main...075c5e40`, with a probe on a real Chromium.
2. Local, precision, over the delta `075c5e40..dcb501b5`: F1–F3 resolved, nothing new.
3. External 1, Claude Code GitHub Action (request 18:39:41Z, "Claude finished" 18:40:37Z). It
   read every code and test file, `ci.yml`, `pyproject.toml` and `docs/testing.md`; not
   `uv.lock` or the openspec files (checked locally).
4. Local, precision, over the archive `28bc7ae8` and the merge of `main` `f659d7c2`: the conflict in
   the living spec `continuous-integration` kept both requirements whole (this one and "A smoke
   cell runs its tests on three workers"), only the markers removed (`git show --remerge-diff`);
   no code, test or CI change since round 3. Nothing new.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | local: the method `signal` did not end a hang inside a Playwright wait; the exception landed in Playwright's event loop and the `page` fixture's teardown hung with no limit, no test name and no junit | fixed in `dcb501b5`: method `thread` (approved by the human), faulthandler stacks 5 s before the limit; `tests/ui/test_time_limit.py` (real Chromium) and `tests/test_ui_time_limit.py`, both seen red under `signal` |
| F2 | minor | local: the test's ast parsing of the conftest broke on a tuple or subscript target | fixed in `dcb501b5`: the hook lives in `tests/time_limit.py`, imported |
| F3 | minor | local: the test claimed "no other layer" but collected only integration | fixed in `dcb501b5`: it collects all of `tests/` and checks unit, integration, live, smoke and container carry no limit |
| E1 | minor | external: without xdist a hung test ends the whole run (`os._exit`) | partly confirmed, declined: `make test-ui` and CI run under xdist; only a serial debug run (`-n0`) stops, the test still named by the stack dump; "the run goes on" holds under xdist only |
| E2 | minor | external: faulthandler's one timer per process, shared with `faulthandler_timeout`, may kill a process hung in an early fixture's setup before the dump | declined: nobody sets `faulthandler_timeout`; the test is still named by xdist and junit, only the stacks are missing |
| E3 | minor | external: importing the test module by file name relies on the `prepend` import mode | declined: the whole repository does so (`agent_helpers`, `leftovers`) |

Checked and not a finding: a hung test's leftover processes are reaped by
`leftovers.reap_dead_runs()` at the next run; the private pytest key `fault_handler_stderr_fd_key`
exists in pytest 9.2.0 of `uv.lock`; the hook and fixture act only under `tests/ui/`.

## Metrics

Rounds: 3 local, 1 external, 0 stand-ins. Findings: local 3 confirmed (1 important, 2 minor),
0 refuted; external 3 confirmed (all minor, one only partly), all declined; findings in code
changed by the developer's cleanup: 0.

## Checks

- `make lint`: green.
- `uv run pytest -n0 tests/test_ui_time_limit.py tests/test_ci_workflow.py`: 55 passed.
- `uv run pytest -m ui -n 2 tests/ui/test_time_limit.py tests/ui/test_tabs.py`: 3 passed.
- `openspec validate ui-test-time-limit --strict`: valid.
- CI on `dcb501b5`: 27 of 27 checks pass, the four `ui` cells and the smoke among them.
- Round 4: `openspec validate --specs --strict`: 84 passed; `uv lock --check`: ok; CI on
  `f659d7c2`: 27 of 27 pass.

## Residual risk

- The full UI suite and `make test` were not run locally by the reviewer; CI covers them (the
  integrator reports 6142 passed, 0 failed, after the merge of `main`).
- A hang inside Playwright shows only Playwright's event loop in the stacks, not the test's line;
  the test's name is in the log and junit.
- A hung test's teardown does not run.
- A private pytest key: a loud ImportError if pytest renames it.
- No real hang has happened in CI since; the mechanism is proven by artificial hangs only.
- No change to `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
  `tests/live/`: no live tests needed.

Found on the way: none.
