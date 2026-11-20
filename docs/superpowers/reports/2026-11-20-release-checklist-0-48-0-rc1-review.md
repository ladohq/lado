# LAD-306 release-checklist-0-48-0-rc1: review report

Pull request #353 `fix/lad-306-release-checklist-0-48-0-rc1` → `main`. Scale: tweak. Depth:
precision. Head reviewed: `6e95e98a`. The rest of `docs/releases/0.48.0.md`'s section
`## 0.48.0rc1` (before you start, the upgrade to schema 43 with the GitHub login taken into
Settings, New session's fixes, going back to 0.47.0, the map of the 18 CHANGELOG items),
CHANGELOG's `### Upgrade` group, and `tests/test_rc_check.py`'s real-file test over
`0.48.0rc1`.

## Rounds

1. Local, precision over `origin/main...bf4c8d48`: every exact line of the checklist compared
   with the code, and the 35 test files of the map checked to exist and cover their items.
   Found F1.
2. Local, precision over the delta `bf4c8d48..6e95e98a`, and external 1, Claude Code GitHub
   Action (request 2026-11-20T10:56:01Z, finished 10:57:12Z): read CHANGELOG.md,
   docs/releases/0.48.0.md, tests/test_rc_check.py and the code lines quoted; not the
   change's proposal.md, tasks.md and .openspec.yaml, which repeat the checklist and were
   compared locally. Found E1, E2.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | The GitHub takeover item quoted, for a `gh auth login` login, a source and a doctor line the code does not print (`github_takeover.py:33`, `doctor.py:1001-1007`) | fixed in `6e95e98a`: both ways named by the code's lines |
| E1 | — | Item 15: `tests/test_runtime.py` holds no "judge" | refuted: `test_runtime.py:130-139` covers `manual` taken as `default`; the mode's words are `tests/test_providers.py`'s |
| E2 | — | Item 11: `web/src/InfoTip.test.tsx` is thin | refuted: the test exists and sends `resize` (`InfoTip.test.tsx:91`); the phone is a hand check |

## Checks

- `tests/test_rc_check.py`: 84 passed; developer's `make test` on `6e95e98a`: 6088 passed,
  14 skipped; `make lint` green; `release_notes.py v0.48.0rc1` prints 18 items;
  `openspec validate release-checklist-0-48-0-rc1 --strict` valid.
- CI on `6e95e98a` (run 44723252598) green on its second attempt, `ci-ok` success.
- Flake: `container (amd64, 2)`, step `Container tests`,
  `tests/container/test_toolchains.py::test_python3_is_the_images_313_unless_a_project_names_its_own`:
  `mise install` got 403 from github.com's releases; rerun once with `--failed`, passed.

## Not checked

- Integration, UI, smoke, live and container tests locally: CI ran them; live runs on the RC.
- `scripts/rc_check.py` itself: it installs from PyPI; `test_rc_check.py` checks its list.
- The checklist's hand checks: the human makes them on the RC.

No change to `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
`tests/live/`: no live tests needed before the merge.
