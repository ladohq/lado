# LAD-263 codex-model-over-repository-config: review report

Pull request #273 `hotfix/lad-263-codex-model-over-repository-config` → `main`. Scale: hotfix,
depth precision, widened to a general pass over `src/lado/providers/codex.py`. Head reviewed:
`89d2ae15`. A Codex agent whose config carries a model (LADO's choice, else the one carried from the
user's Codex config) is started with `-m <model>`, so the repository's `.codex/config.toml` no
longer overrides it; with no model anywhere else, the repository's model is shown from the launch
with the source `cli` and the detail `the repository's .codex/config.toml`. Delta: `agent-model`
(added), `session-model` (modified).

## Rounds

1. Local, precision plus a general pass over `providers/codex.py`, `f43d6be4..89d2ae15`: every
   scenario of the delta against the code and its unit test in `tests/test_codex.py`; D1 (`-m` read
   from the config LADO wrote, after `_choose_model` and `_on_server`), D2 (the repository's model
   only with no model in the agent's config and a trusted folder, the folder walk shared with the
   hooks), silent errors (an unreadable or invalid TOML counts as naming nothing), the architecture
   against AGENTS.md. No finding.
2. External 1, Claude Code GitHub Action: "No defects found in the delta". It read `codex.py` and
   `tests/smoke/test_smoke.py`, not the unit tests, the docs or openspec; the local round did.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

None, confirmed or refuted, local or external.

## Found on the way

- Nothing.

## Checks

On `89d2ae15`:
- `make lint` green; `make test` 6097 passed, 7 skipped.
- `openspec validate codex-model-over-repository-config --strict` green; `openspec validate --specs
  --strict` 82/82; a trial archive in a copy 82/82.
- CI 27/27, `ci-ok` green, the Codex smoke on Linux and macOS included.
- Integration tests unchanged; run by CI only.

## Not checked

- Live tests: not run, though `providers/codex.py` changed (`make test-live PROVIDER=codex`).
- A worktree without its own `.codex/config.toml` when the main checkout has one: only a worktree
  with its own file was checked by hand. At worst LADO shows an empty model there until the first
  hook, as before this change; the launch is unaffected, `-m` wins regardless.
- Out of scope by the human's decision: the repository's `model_reasoning_effort`, a warning at the
  start, marking the repository `untrusted`.
