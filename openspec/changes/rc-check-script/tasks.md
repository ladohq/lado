Plan: `docs/superpowers/plans/2026-10-14-rc-check.md` (each task's tests and steps). Design
doc: `docs/superpowers/specs/2026-10-14-rc-check-design.md`.

## 1. Versions and the checklist (D2, D7, D8)

- [ ] 1.1 `scripts/rc_check.py` frame: versions from PyPI's JSON, the default version, the
  checklist; `release_notes.section`. Check:
  `uv run pytest tests/test_rc_check.py tests/test_release_notes.py -n0`.

## 2. The sandbox (D3, D4)

- [ ] 2.1 `sandbox`: the folder, the environment, the checks, the UI, the end; a failure
  keeps the folder; Ctrl-C cleans up. Check: `uv run pytest tests/test_rc_check.py -n0 -k
  sandbox`.

## 3. Upgrade (D1, D5)

- [ ] 3.1 `upgrade`: `lado update` on the terminal, the copy in `~/.lado-rc/`, the
  refusals. Check: `uv run pytest tests/test_rc_check.py -n0 -k upgrade`.

## 4. Rollback (D6)

- [ ] 4.1 `rollback`: the plan, the question, stop, update, restore, resume; the
  refusals. Check: `uv run pytest tests/test_rc_check.py -n0 -k rollback`.

## 5. Docs (D9)

- [ ] 5.1 docs/release.md section 4 as the approved draft; AGENTS.md Layout; LAD-50's
  documentation test moved onto the script when LAD-50 is on main. Check: read against
  the design doc's appendix; `uv run pytest tests/test_telemetry.py -n auto`.

## 6. Acceptance and regression (D10)

- [ ] 6.1 `python3 scripts/rc_check.py sandbox 0.37.0rc2 --no-ui`: output and exit status
  in the build report; no `lado-rc-*` folder or tmux socket left; `~/.lado` untouched.
- [ ] 6.2 `make lint`, `make test` (counts), `openspec validate rc-check-script --strict`,
  `openspec validate --specs --strict`. Check: all green, counts in `build-report`.
