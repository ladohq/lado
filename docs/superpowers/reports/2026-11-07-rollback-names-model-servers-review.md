# LAD-235 rollback-names-model-servers: review report

Pull request #251 `fix/lad-235-rollback-model-servers` → `epic/lad-154-models`. Scale: tweak,
review depth: precision, widened to breadth for round 1 (the diff advises removing the user's
key files). Head reviewed: `d9d033f2`. The way back now names saved model servers, models and
default models among what is lost, and lists each key folder under `model-servers/` whose server
the copy of `lado.db` lacks. `docs/install.md` says what stays and how to remove it, Docker
included. No schema migration, no MCP or CLI change, no change of the way back's mechanics.
Delta: 2 requirements added to `update-database`.

## Rounds

1. Local, breadth, `c4609876..57630778`: lenses spec, tests, silent failures, comments and
   descriptions, general, architecture by `AGENTS.md`. 4 minor (F1 to F4 with the external note).
2. External 1, Claude Code GitHub Action, head `57630778`: no blocker, one note taken as F4. It
   read every code, test and document file of the diff; not the openspec files. It is the same
   model family as the kit's agents.
3. Local, precision, `57630778..d9d033f2`, the return from `merge_ok`: one file,
   `docs/design/modules.md`, 2 lines. F1 closed, one new minor (F5).

External rounds used: 1 of 1, on `57630778`; none on `d9d033f2`, by the human's decision at the
gate and by the cap. Stand-ins: 0.

## The human's decisions

- **Question #4718:** the warning itself lists the key folders, not the documentation alone.
- **Question #4725:** Claude Code joins the live run, as the reviewer learned from the developer's
  reports.
- **Gate `merge_ok`:** returned once, "fix F1 in docs/design/modules.md, without a new external
  round", then approved on `d9d033f2`.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | the description of `Restore` in `docs/design/modules.md` lacked the new field `keys` | fixed in `d9d033f2` by the human's decision at the gate |
| F2 | minor | `_server_ids` takes any `sqlite3.OperationalError` for a missing table, so a disk error right after reading `sessions` would list every key as staying | declined: extra lines in the list, no data lost; the behaviour stands in D2 |
| F3 | minor | `os.path.lexists` gives False for a server folder that cannot be entered, and that key goes unlisted | declined: LADO makes these folders with mode 700, so it takes a manual change of rights; the spec speaks of an unreadable `model-servers/` |
| F4 | minor | external: with `model-servers/` unreadable, the warning names the whole folder under "remove them", which on a way back to a version that knows servers holds the keys of saved servers too | declined: the scenario "The folder cannot be read" asks for this text, no older version knows servers yet, and `docs/install.md` warns of it |
| F5 | minor | the fix of F1 left one line of about 130 characters in `docs/design/modules.md:214` | declined: no effect on the text or how it shows |

Refuted: 0. The external reviewer's statement that the `except` in `_server_ids` covers only a
missing table is inexact; it is counted in F2, not as a finding of its own.

## Checks

On `57630778`; after it only `docs/design/modules.md` changed.

| Check | Result |
|---|---|
| `make lint` | clean, 1431 files |
| `make test` | 5980 passed, 7 skipped |
| `uv run pytest -m integration -n auto tests/integration/test_update_process.py` | 12 passed |
| `openspec validate rollback-names-model-servers --strict` | valid |
| `openspec validate --specs --strict` | 78 passed |
| Trial archive in a copy | clean, then 78 passed |
| The pull request's manual check on its own `LADO_HOME` | the warning as expected; after removing `model-servers/`, no line about keys |

On `d9d033f2`: CI 23 checks, `ci-ok` green; the developer's `make test` 5980 passed, 7 skipped,
and a clean `make lint`.

## Not checked

- `make test-live` was not repeated by the reviewer: it is paid and needs the human's yes. Its
  results on the four providers, with OpenCode's failure from the model and the repeat that
  passed, come only from the build report.
- The human's yes on Claude Code in the live run (#4725) and the text of the gate's refusal were
  seen only in the developer's reports, not in the answers themselves.
- `live.yml` did not run on the epic's code: the environment `live` does not admit this branch.
- The real way back was not repeated, as the brief allows; the manual check stopped at the answer
  `n`.
- `make check` and `make test-smoke` did not run locally; CI covers them.
- An unreadable `model-servers/` was checked only by a unit test with `os.listdir` replaced, not
  with real rights.

## Notes

- The diff touches `providers/` only with a comment in `codex.py`; `hooks.py`, `mcp_server.py`,
  `runtime.py`, `agent_env.py` and `tests/live/` did not change.
- The comment in `providers/codex.py` names the existing `tests/live_models.py`, which holds no
  note on LM Studio: AC-6 asks for this and D7 records it.
- The developer reported making some edits by script and `sed -i`, against `.lado/sdlc.md`. The
  result was read in the ordinary diff.
- Found on the way: nothing outside the task.
