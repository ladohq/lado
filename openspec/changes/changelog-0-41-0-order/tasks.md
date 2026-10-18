## 1. The section `## 0.41.0 (unreleased)`

- [x] 1.1 CHANGELOG.md: take the sentences `API: …` out of the Start from scratch item,
  `(POST /api/access/new-token)` and the `compose.yaml` parenthesis out of the item on
  opening LADO on a phone, and "The API's …" and "lado.db goes to schema 31 …" out of the
  item on answering with files, as the proposal's What Changes words them; rewrap each at
  90 columns. Check: `git diff CHANGELOG.md` touches only that section, and every fact
  taken out appears in 1.2.
- [x] 1.2 CHANGELOG.md: after the nine user items, the two `Upgrade:` items and the three
  `API:` items of the proposal, in its order. Check: `grep -n '^- \(Upgrade\|API\|MCP\):'
  CHANGELOG.md` lists the five new lines first, before line 152's 0.40.0 ones, and none
  of the section's user items contains `API:`, `/api/` or `schema`.

## 2. Checks

- [x] 2.1 `python3 scripts/release_notes.py v0.41.0rc1` from the repository's root exits
  0; its notes read user items, then `Upgrade:`, then `API:`, each item one line.
- [x] 2.2 `make lint` and `make test` green (counts in the build report); no code changed,
  so no integration or UI run.
