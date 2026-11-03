# LAD-181 project-set-unechoed-refusal: review report

Pull request #207 `hotfix/lad-181-project-set-secret-echo` → `main`. Scale: hotfix, review
depth: precision. Head reviewed: `aa836218` (= the remote head). Any refusal by argparse of
the command line of `lado project set` now prints the command's usage and one fixed text
that names no word of the command line, exit 1: a quiet parser class whose `error()`
ignores argparse's message, and `cli.main` parsing with `parse_known_args`, sending the
leftovers of `project set` to that same `error()`. `lado`'s own parser takes no
abbreviation (`allow_abbrev=False`), so `--=<secret>` is no longer quoted as ambiguous on
Python 3.10. Delta: one requirement added to `projects`.

## Rounds

- **Round 1** (local, `origin/main...662f38d7`): precision, with argparse probed by hand
  on 3.13 and 3.10. Found F1 and F2.
- **Round 2** (local, `662f38d7..aa836218`): F1 and F2 resolved; a leak search over 168
  command lines on Python 3.10, 3.11, 3.12 and 3.13 found no echo. New: F3 only.
- **External round 1** (Claude Code GitHub Action, 2026-11-02 23:43Z → 23:45Z): no
  blockers; read `src/lado/cli.py` (the risky file), not the tests, docs or openspec; it
  could not run the probes, so its findings come from reading.

External rounds used: 1 of 1 (the hotfix cap). The external reviewer is of the same model
family, so its "no findings" weighs less.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | on Python 3.10 `lado`'s parser matched prefixes of its `--help`/`--version` against every word, so `--=<secret>` after `project set` was refused as ambiguous and quoted (exit 2) | fixed in `aa836218` (`allow_abbrev=False`), with three `--=` cases in `test_project_set_refusal_unechoed` |
| F2 | minor | the paragraph of `lado project set` in `docs/cli.md` not wrapped | fixed in `aa836218` |
| F3 | minor | CHANGELOG.md does not say that `lado --vers` and `lado --he` (abbreviations of `lado`'s own options) are no longer taken | declined: said in `docs/cli.md` and the pull request; subcommand options keep their abbreviations; left to the human at the merge gate, who approved without it |
| E1 | — | external: a word in the subcommand's place (`lado project <word>`) is still quoted (`invalid choice`) | refuted as a defect of the change: the place of a command's typo, not of a value; out of scope |
| E2 | — | external: `project set` exits 1, other commands 2 | refuted: design D4, approved at design_ok |
| E3 | — | external: short-prefix matching (`-hX`) does not depend on `allow_abbrev` | refuted: the 168-line search on 3.10–3.13 found no echo; `-hs3cr3t` green on 3.10 in CI |

## Checks

- `make lint`: green.
- `tests/test_cli.py`: 282 passed on 3.13 and on 3.10; the developer's `make test` 4758
  passed, 7 skipped.
- `openspec validate project-set-unechoed-refusal --strict` valid; tasks 8/8;
  `openspec validate --specs --strict` 56 passed.
- CI on head `aa836218` (run 41547347729): all 23 checks pass, `ci-ok` among them.
- Not run: live tests (no change to `providers/`, `hooks.py`, `mcp_server.py`,
  `runtime.py`, `agent_env.py` or `tests/live/`); Python 3.11/3.12 are not in CI, covered
  by the hand search only.

Found on the way: none.
