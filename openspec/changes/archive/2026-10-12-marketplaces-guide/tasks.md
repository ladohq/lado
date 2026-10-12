## 1. The guide

- [x] 1.1 Write `docs/marketplaces.md` with the five sections of the proposal's Scope (AC-2),
  moving the `marketplace.yaml` example and the `index.json` format 1 from `docs/kits.md`
  (AC-3). Check: each fact of the old kits.md text found in the new guide.
- [x] 1.2 Hold every fact against the code and the official marketplace (AC-4):
  `src/lado/marketplaces.py`, `kits.py` (`needs_confirmation`), `gitcache.py`
  (`GIT_TERMINAL_PROMPT`), github.com/ladohq/marketplace's README, `scripts/` and
  `.github/workflows/`. Check: `uv run lado marketplaces --help`, `uv run lado kits add
  --help` for each command named.

## 2. README and the Kits guide

- [x] 2.1 Add README's `## Marketplaces` after `## Kits` with the approved text (AC-1).
  Check: `grep -n "yaml\|json" README.md` finds nothing in the section.
- [x] 2.2 Cut `docs/kits.md` section 7 to its steps with a link to the new guide (AC-3).
  Check: `grep -n "index.json\|\"index\"" docs/kits.md` finds no format.
- [x] 2.3 Point AGENTS.md (`marketplaces.py`'s line) and docs/design/ui.md (Kits,
  Available) at docs/marketplaces.md for the format (AC-5). Check: `grep -rn "docs/kits.md"
  AGENTS.md docs/design/ui.md` names no `index.json` format.
- [x] 2.4 Every relative link in README.md, docs/kits.md and docs/marketplaces.md resolves,
  anchors included (AC-5). Check: each link opened.

## 3. Release notes

- [x] 3.1 One line in CHANGELOG.md under `## 0.36.0 (unreleased)` (AC-6).
- [x] 3.2 `openspec validate marketplaces-guide --strict` and `make lint` pass.
