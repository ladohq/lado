The plan with each task's tests: `docs/superpowers/plans/2026-11-25-first-run-guide.md`.

## 1. The record

- [x] 1.1 `lado.guide`: `LADO_HOME/guide.json`, the union of `shown`, `complete`, `tips_off`,
  `restart`, a broken file treated as missing and journaled (D1). Check: `tests/test_guide.py`.

## 2. The server

- [x] 2.1 Facts (a model connected, an author in effect), the first record after the first
  login check, `GET`/`POST /api/guide`, `missing` to the error journal, `LADO_GUIDE=0` in
  `tests/conftest.py`, the API types (D2, D3, D9, D11). Check: `tests/test_server_guide.py`,
  `make web` (stale-types).

## 3. Markers and Help

- [x] 3.1 `data-guide` markers on the elements of the design doc's §7, the login sheet's and
  Model servers' state attributes, Help → Getting started with its compass (D5, `rail-help`).
  Check: vitest of `LoginSheet`, `Shell`.

## 4. The guide's data

- [x] 4.1 `web/src/guide/hints.ts` with every stage-1 hint and text, `facts.ts` and the
  Settings pages publishing to it, the marker test (D4, D7, D8). Check:
  `web/src/guide/hints.test.ts`.

## 5. Placement

- [x] 5.1 `web/src/guide/place.ts`, every rule of the design doc's §4 (D10). Check:
  `web/src/guide/place.test.ts`.

## 6. The engine

- [x] 6.1 `conditions.ts`, `Guide.tsx` (lazy), the shell's mount, tokens and the Guide
  section of `styles.css`; the generic paste step; completion; Not now; tips; a missing marker;
  restart; accessibility (D3, D6, D9, D12, D13). Check: the vitest files of the plan's Task 6.

## 7. The browser

- [x] 7.1 `tests/ui/test_first_run_guide.py`: the main path with the guide on, the restart, the
  phone (D14). Check: `uv run pytest -m ui tests/ui/test_first_run_guide.py`, then every UI e2e
  with the guide off.

## 8. Docs

- [x] 8.1 `docs/install.md` (`LADO_GUIDE=0`), `docs/design/ui.md`, `docs/design/modules.md`, `docs/testing.md`, `AGENTS.md`'s
  Layout, `CHANGELOG.md`. Check: `tests/test_agents_md.py`, `openspec validate first-run-guide
  --strict`.

## 9. Manual check

- [x] 9.1 The design doc's §13; screenshots of the changed screens as run artifacts. Done in a
  browser driven by Playwright on a fresh `LADO_HOME` (no login, no key, no author): light at
  1440 and 390 px, dark at 1440, 768 and 390 px, to the key's refusal and on to New session.
  Not by hand: the statistics question (the test servers have no statistics endpoint; its
  wait is vitest's, `Guide.test.tsx`) and the restart with a model connected (no welcome:
  `tests/test_server_guide.py`).
