# LAD-101 changelog-0-41-0-order: review report

Pull request #101 `fix/lad-101-changelog-0-41-0-order` → `main`. Scale: tweak, reviewed
for precision only: the diff touches CHANGELOG.md and openspec documents, no code or user
data. Head reviewed last: `29e3fe4` (= the remote head). `providers/`, `hooks.py`,
`mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not change: no live
tests needed.

## Rounds

- **Round 1, local** (precision over `a93d366..29e3fe4`): L1.
- **Round 1, external** (Claude Code GitHub Action, request at 19:15:23Z, "Claude
  finished" at 19:16:09Z): "No blocking findings"; E1.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| L1 | 1 | local (precision) | one line of the item on the phone layout is 91 characters (> 90) | confirmed | minor | declined: the line is older than this change, and `scripts/release_notes.py` joins wrapped lines, so users never see it |
| E1 | 1 | external | `lado update` in the `Upgrade: schema 31` item has no backticks | confirmed | minor | declined: it follows the sample of `docs/release.md` and the 0.38–0.40 sections word for word; the reviewer itself suggested leaving it |

Metrics: 1 local round, 1 external, 0 substitutes. Local confirmed 1 (minor), refuted 0;
external confirmed 1 (minor), refuted 0. Findings in code changed by the developer's
cleanup: 0.

## Spec and design

- No spec delta (`skip_specs: true`), as the design decided; archived with
  `--skip-specs`.
- The section's text matches the proposal's What Changes word for word; all 4 tasks
  checked.
- Order: nine user items, then two `Upgrade:` items, then three `API:` items; no `MCP:`
  item (`src/lado/mcp_server.py` unchanged since v0.40.0). No user item contains `API:`,
  `/api/` or `schema`.
- Facts checked against the code: the routes in `src/lado/server/app.py`, the models
  `AccessInfo`, `ScratchTarget`, `FolderInfo.scratch`, `GateInfo.answer_attachments` in
  `src/lado/server/models.py`, `SCHEMA_VERSION` 30 (v0.40.0) → 31, `docker/compose.yaml`
  changed in v0.40.0..main only for `LADO_LISTEN`/`LADO_PUBLIC_HOST`. No earlier fact
  lost but `gates.answer_note` (the design's decision 2).

## Checks

- `python3 scripts/release_notes.py v0.41.0rc1`: exit 0, the order right, each item one
  line.
- `openspec validate --specs --strict`: 39 passed, 0 failed.
- `make lint`: clean. `make test`: 3602 passed (the developer's run).
- CI of PR #101 on `29e3fe4`: `ci-ok` pass; unit, integration ×6, ui ×2, js, container
  amd64/arm64 pass; smoke skipped by the skip list (Markdown and `openspec/` only).

## Not checked (residual risk)

- `make test` not rerun by the reviewer (no code changed; CI unit green).
- The external reviewer ran no `release_notes.py` and did not check routes or schema
  itself; the local round did. It is of the same model family, so its "nothing found"
  weighs less.

## Found on the way

None.
