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

## 10. The human's manual check (25.11.2026)

- [x] 10.1 A model is a model ticked for an agent CLI, or a login: `guide.facts`, the
  published `models` fact, and Model servers' steps after Add server (`model-pick`,
  `model-clis`, `model-id`, `model-no-cli`, `model-server-row`). Check: `tests/test_server_guide.py`,
  `Guide.test.tsx`, the UI e2e's main path.
- [x] 10.2 The guide starts by itself only while a model or an author is missing. Check:
  `tests/test_server_guide.py`, the UI e2e's reload after Getting started and Esc.
- [x] 10.3 A press on the login window's choice chosen by default is a pick. Check:
  `LoginSheet.test.tsx`, `Guide.login.test.tsx`.
- [x] 10.4 `docker/compose.yaml` passes `LADO_GUIDE`; `docs/install.md` says so. Check:
  `tests/test_docker.py`.
- [x] 10.5 A tall form on a phone scrolls its end clear of the card; hints keep their `keep`
  text in sight; the terminal's tip at its bar. Check: `place.test.ts`, the UI e2e.
- [x] 10.6 The ring dashed, the card without a focus ring, Not now on one line, the focus to
  the page's heading after Not now. Check: the UI e2e, `Guide.a11y.test.tsx`.
- [x] 10.7 The texts of the server form's refusals and the highlighted element's name. Check:
  `hints.test.ts`, `Guide.login.test.tsx`, `Guide.a11y.test.tsx`.

## 11. The human's second manual check (25.11.2026)

- [x] 11.1 Not now and Esc complete the main guide for good; the welcome and every step say
  Help → Getting started brings it back (D12). Check: `Guide.test.tsx`, the UI e2e's reload
  after Esc.
- [x] 11.2 The engine stays once loaded, so the last tip left stays on screen. Check:
  `mount.test.tsx`.
- [x] 11.3 The focus after Not now goes to the first of where it was, the target, the page's
  heading that takes it. Check: `Guide.a11y.test.tsx`.
- [x] 11.4 The done line of the model part claims no working model. Check: `Guide.test.tsx`,
  the UI e2e.
- [x] 11.5 Short names of the highlighted rows and forms (Git servers, Model servers);
  `model-no-cli` without dim, its advice by `data-guide-refusal="no-install"`; the welcome by
  what is left; the counter on the whole path; the question's tip names Send answer to….
  Check: `GitServers.test.tsx`, `ModelSources.test.tsx`, `Guide.test.tsx`, `hints.test.ts`,
  the UI e2e's step names.
- [x] 11.6 The card's edge `--guide-edge`, 3:1 against the dim; the ring 4 px off its target.
  Check: `tokens.test.ts`, `place.test.ts`, the UI e2e.
