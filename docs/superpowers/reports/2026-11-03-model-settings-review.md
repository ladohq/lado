# LAD-182 model-settings: review report

Pull request #208 `feature/lad-182-model-settings` → `epic/lad-154-models`. Scale: full,
review depth: breadth, then precision. Head reviewed: `6173936a` (= the remote head). Model
servers (name, address, key) and models (name, CLI, the CLI's model, an optional server)
are saved under names: `lado model-server add/list/remove` and `lado model add/list/remove`.
A server is probed before it is saved; a server's key lives in its own file under
`LADO_HOME` (mode 600), never in `lado.db` or LADO's shared `secrets/`. `lado doctor`
checks the saved servers. Schema migration 37→38. `providers/`, `hooks.py`,
`mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not change.

## Rounds

- **Round 1** (`origin/epic/lad-154-models...82644ebc`): a local breadth pass with CLI
  probes and the three checks of gate #228; F1–F5.
- **Round 2** (`82644ebc..37caea78`): local precision pass (no new findings) and external
  1 of 2 (Claude Code GitHub Action); F6–F12.
- **Round 3** (`37caea78..6173936a`): local precision pass (no new findings) and external
  2 of 2, which found nothing new and agreed with the triage of F4 and F8–F12.

External rounds used: 2 of 2. The external reviewer is of the same model family, so its
"no findings" weighs less; it read the code of the delta, not its tests, specs or docs.
One finding (F6, a regression) came from the fix of F3; one (F2) was in code simplified
during cleanup.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | important | An unreadable key file made `lado doctor` fail whole and `model add --server` / `add --replace` print a traceback | fixed in `8d189c99` |
| F2 | minor | `remove_server` raised `IndexError` when the referring model vanished meanwhile | fixed in `8d189c99` |
| F3 | minor | A key over `MAX_VALUE` was silently truncated | fixed in `8d189c99` |
| F4 | minor | The scenario promises exit 1 for `--help=s3cr3t`; Python 3.11+ exits 0 | declined: same wording as the `probe` requirement, the key never shows |
| F5 | minor | The key canary lacked a successful `--replace --key` | fixed in `37caea78` |
| F6 | important | Regression of F3's fix: a non-UTF-8 key from stdin gave `UnicodeEncodeError` (traceback, `errors.jsonl` entry) in `probe` and `add` | fixed in `6173936a`, checked by hand |
| F7 | minor | Cleanup in `add_server` could replace the original error | fixed in `6173936a` |
| F8 | — | No way to drop a server's key without removing the server | refuted: out of scope in the proposal and design |
| F9 | minor | `doctor.probed` catches only `ProbeError`/`Refused` | declined: no path to another error |
| F10 | minor | The plain-http warning fires for CGNAT `100.64/10` and private DNS names | declined: design decision D6 (names are not resolved); an extra warning, not a missed one |
| F11 | minor | `remove_server` raises `IntegrityError` only to reach its `except` | declined: style, behaviour correct and tested |
| F12 | — | `PRAGMA foreign_keys` may be off | refuted: set in `state._open` |

## Gate #228 checks

1. Key canary: the key is in no process argument, output, `lado.db`, error journal, or
   file of `LADO_HOME` and `secrets/`, for `add --key` and a successful `--replace --key`.
2. Permissions: folders 700, file 600, also after `--replace` and under `umask 0`.
3. Migration 37→38 and the way back: tables created empty; an older LADO refuses a
   version-38 database ("made by a newer LADO"); after a rollback `doctor` names the
   remaining key folders as left over.

## Checks at `6173936a`

- `make lint`: 0.
- `make test`: 5095 passed, 7 skipped.
- `uv run pytest -m integration -n auto tests/integration/test_model_settings_process.py
  tests/integration/test_model_server_probe.py`: 9 passed.
- `openspec validate model-settings --strict`: valid; `openspec validate --specs --strict`:
  59 passed.
- CI of PR #208: 23/23, `ci-ok` green, smoke on Linux and macOS included.

## Not checked (residual risk)

- No run against a real LM Studio or LiteLLM; the manual check is in the pull request.
- Not run locally: `make web` (no change to `web/` or the API), UI, live tests and the
  whole `make test-integration` (CI runs it).
- Small leftovers without findings: the doctor line names an unreadable key twice; a
  failed write of a new key leaves an empty folder that `doctor` names as left over.
- Found on the way: none.
