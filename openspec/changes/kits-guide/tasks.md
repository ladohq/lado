## 1. The guide

- [x] 1.1 Write `docs/kits.md` with the eight sections of the proposal's Scope, moving every
  fact of README's old Kits section into it (AC-2, AC-3). Check: a list of the old
  section's facts, each found in the guide.
- [x] 1.2 The Flows section from `src/lado/flows.py` (docstring, `parse`, `lint`) and the
  create section from `kits.KIT_KEYS`, `kits.AGENT_KEYS`, `kits.MCP_KEYS` (AC-6). Check:
  each key and command named is in the code or `--help`.
- [x] 1.3 Read-only roles as AGENTS.md "Read-only roles" says today, Codex included (AC-5).
  Check: `grep -n "Codex" docs/kits.md README.md`.

## 2. README

- [x] 2.1 Replace `## Kits` with the approved text of the proposal (AC-1). Check:
  `grep -n "lado-dev\|yaml\|json" README.md` finds nothing in the section.
- [x] 2.2 "What works now" and "Planned" (AC-4). Check: by reading.
- [x] 2.3 Links: every relative link in README.md and docs/kits.md resolves, anchors
  included; docs that pointed at README's Kits section point at the guide (AC-6). Check:
  `grep -rn "README.md#kits" docs README.md` and each link opened.

## 3. Release notes

- [x] 3.1 One line in CHANGELOG.md under the next patch's `## X.Y.Z (unreleased)`.
- [x] 3.2 `openspec validate kits-guide --strict` and `make lint` pass.
