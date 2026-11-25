# First-run guide, stage 1: Implementation Plan

**Goal:** a guide over LADO's unchanged web UI that leads a person on a fresh LADO from the
welcome to connecting a model, setting a commit author and opening New session, plus five
one-time tips and Help → Getting started; its marks kept by the server.

**Architecture:** a new module `lado.guide` keeps `LADO_HOME/guide.json` and computes the
facts (D1, D3); `server/app.py` serves `GET`/`POST /api/guide` (D2). In the web UI,
`web/src/guide/hints.ts` is the data (D7), `facts.ts` a store the Settings pages publish to
(D4), `conditions.ts` the named conditions, `place.ts` the pure placement (D10) and
`Guide.tsx` the lazy engine (D7); existing components only get `data-guide` markers (D5) and
the Help line.

**Tech Stack:** Python 3.10+ standard library, FastAPI/pydantic as the server uses them,
pytest (`-n auto`, `-m ui`), React + TypeScript, vitest, Playwright.

**Spec:** `openspec/changes/first-run-guide/` (proposal, delta, `design.md` D1–D14) and
`docs/superpowers/specs/2026-11-25-first-run-guide-design.md` (behaviour, placement, every
text, markers, look, accessibility). Screens: `ui-design/lad-311-guide/mockup.html` and the
run's `mockup-guide-stage1.html` (the "none of these" card, the paste step, Getting started).

## Global Constraints

- The texts are the design doc's §6, word for word; another wording needs a reason in the
  build report. No text in a component: all in `hints.ts`.
- English only in the guide; no Cyrillic (the marker test checks).
- No orange (`--human`) in the guide; only `--guide-dim`, `--guide-ring` are new tokens.
- `LADO_GUIDE=0` in `tests/conftest.py` for every test; only `tests/ui/test_first_run_guide.py`
  removes it.
- No request of the guide's own on Agent CLIs, Model servers or Git servers (D4); one `GET
  /api/guide` per page load; `POST /api/guide` only on a mark.
- The engine (`Guide.tsx`, `place.ts`, `conditions.ts`) is a lazy chunk: check `make web`'s
  build output lists it as its own file.
- `make web-types` after the API models; commit `web/openapi.json` and `web/src/api.gen.ts`.
- CHANGELOG: `## 0.49.0 (unreleased)`, New: “**A guide for the first start.** A fresh LADO
  shows where to connect an AI model, set the commit author and start the first session, with
  short tips the first time you meet a session, a gate, a question or a terminal. Help →
  Getting started shows it again.”

## Review Focus

1. Two tabs marking hints at once: both ids end in `shown` (the union, D1). Test in Task 1.
2. A broken `guide.json` (bad JSON, a list instead of an object): treated as missing, journaled,
   never as completed, never a 500. Test in Task 1.
3. The first `GET` on a server whose check has not run: it starts one check and waits up to
   20 s; a second `GET` meanwhile does not start a second check. Test in Task 2.
4. A step whose target sits in a scrolled container (Agent CLIs' rows on a phone): the ring
   follows the scroll. Test in Task 7 (UI e2e at 390 px).
5. `inert` left behind: after Not now, after a step completes, after navigation, no element
   outside the layer keeps an `inert` the guide set. Test in Task 6.

## Tests per requirement

| Requirement | Layer | Test |
|---|---|---|
| The guide starts on a LADO with no model | unit (py) + vitest + UI e2e | `tests/test_guide.py` (record made completed with a model), `guide/Guide.test.tsx` (welcome waits for `telemetry_asked`), `tests/ui/test_first_run_guide.py` |
| Guiding steps wait for the real action | vitest + UI e2e | `Guide.test.tsx` (a press outside the hole is swallowed), e2e walk |
| The main path connects a model, then an author, then New session | vitest + UI e2e | `Guide.test.tsx` (part skipping, counter), e2e walk |
| Login window steps | vitest | `Guide.login.test.tsx` with rendered `LoginSheet` rows of claude and codex |
| A card for a person with no subscription and no key | vitest | `Guide.test.tsx` (links, Back) |
| New session completes the guide | vitest + UI e2e | `Guide.test.tsx`, e2e |
| Not now closes until the next page load | vitest + UI e2e | `Guide.test.tsx`, e2e reload |
| Tips show once and never over the guide | vitest + UI e2e | `Guide.tips.test.tsx`, e2e (the New session tip) |
| The guide's marks are kept by the server | unit (py) | `tests/test_guide.py`, `tests/test_server_guide.py` |
| Help restarts the guide | vitest + UI e2e | `Shell.test.tsx` (the line), `Guide.test.tsx`, e2e |
| The guide costs nothing once done | vitest | `guide/mount.test.tsx` (no chunk import, one fetch) |
| Hints are data aimed at markers | vitest + unit (py) | `guide/hints.test.ts` (the marker test), `tests/test_server_guide.py` (missing → journal) |
| LADO_GUIDE=0 keeps the guide from starting by itself | unit (py) + vitest + UI e2e | `tests/test_server_guide.py` (`auto: false`, no record, no facts), `mount.test.tsx` (no import until Getting started, then the welcome), every other UI e2e passes unchanged |
| A hint stands beside its target | vitest | `guide/place.test.ts` (all §4 rules over rectangles) |
| The guide works by keyboard and screen reader | vitest | `Guide.a11y.test.tsx` |
| `rail-help`: Getting started | vitest + UI e2e | `Shell.test.tsx`, e2e |

Regression run: `make lint`, `make test`, `make web`, `make test-js` not needed (no plugin),
`uv run pytest -m ui tests/ui/test_first_run_guide.py` and `uv run pytest -m ui -n auto
tests/ui` (every UI e2e with the guide off), `openspec validate first-run-guide --strict`.

## Tasks

### Task 1: the record (`lado.guide`, D1)

Files: create `src/lado/guide.py`, `tests/test_guide.py`.

Interfaces (produces): `Record(completed: bool, shown: tuple[str, ...], tips_off: bool)`;
`read() -> Record | None` (None: no file, or unreadable, journaled); `write(record)`;
`change(action: str, ids: Sequence[str] = ()) -> Record` under a module lock (`shown` union,
`complete`, `tips_off`, `restart`); `ID_RE = r"[a-z0-9-]{1,64}"`; `off(environ) -> bool`
(`LADO_GUIDE == "0"`; `auto = not off(environ)`).

- [ ] Test: no file → `read()` None; `change("shown", ["a"])` then `change("shown", ["b"])`
  from two threads → both ids; `complete`; `tips_off`; `restart` keeps `shown`, clears
  `completed` and `tips_off`; a bad id refused (`ValueError`); bad JSON → None and one
  `errors.jsonl` line (`telemetry.record("guide:read", …)`); the file replaced atomically
  (a temporary file in `LADO_HOME`, `os.replace`).
- [ ] Implement; `make lint`; `uv run pytest tests/test_guide.py -n0`.
- [ ] Commit `Keep the first-run guide's marks in LADO_HOME (LAD-311)`.

### Task 2: facts and the API (D2, D3, D9, D11)

Files: `src/lado/guide.py` (`facts(wait: float = 20.0) -> Facts`, `first(...)`),
`src/lado/server/models.py` (`GuideInfo`, `GuideFacts`, `GuideAction`), `src/lado/server/app.py`
(`GET`/`POST /api/guide`), `tests/conftest.py` (`os.environ["LADO_GUIDE"] = "0"` beside
`LADO_TELEMETRY`), `tests/test_server_guide.py`, `web/openapi.json`, `web/src/api.gen.ts`,
`web/src/api.ts` (`getGuide`, `postGuide`).

Interfaces: `GuideInfo{auto, completed, shown, tips_off, telemetry_asked, facts: GuideFacts |
None}`, `GuideFacts{model: bool | None, author: bool}`, `GuideAction{action, ids = [], marker =
""}`; `facts.model` from `state.model_servers()` (only when lado.db exists) and
`provider_check.snapshot()` rows logged in; `provider_check` gets `ran() -> bool` and
`wait(timeout) -> bool` for the first check; `facts.author` as `git_entries.listing` computes
`author`/`git_author`.

- [ ] Tests (FastAPI test client as the server's other tests): `LADO_GUIDE=0` → `auto: false`,
  no facts and nothing written; `POST restart` under it still answers the record; no record + a model server saved → `completed: true` written; no record
  + nothing → `completed: false`, `facts.model: false`; the check not ended within the wait
  (a fake `provider_check` that never ends, `wait=0.1`) → `completed: true` in the answer,
  nothing written, `facts.model: null`; two GETs start one check; `POST shown` ids merged;
  `POST missing` → one journal line with id and marker, a second for the same id none; a
  bad action or id → 422/400; `facts` null when completed; `telemetry_asked` follows
  `telemetry.state().ask`.
- [ ] Implement; `make web-types`; `make lint`; `uv run pytest tests/test_server_guide.py
  tests/test_guide.py -n0`; `make test`.
- [ ] Commit `Serve the guide's record and facts at /api/guide (LAD-311)`.

### Task 3: markers and the Help line (D5, rail-help)

Files: `web/src/Shell.tsx` (`rail-menu`, `rail-settings`, `rail-new-session`, Help →
Getting started with `help-getting-started`), `web/src/icons.tsx` (`CompassIcon`, 16 px stroke),
`web/src/Settings.tsx`/`settingsSections.ts`/`SettingsPage.tsx` (`agent-clis-link`,
`model-servers-link`, `git-servers-link`, `settings-back`), `web/src/Providers.tsx`
(`cli-row-${name}`, the sentence → `model-servers-link`), `web/src/LoginSheet.tsx`
(`login-sheet` + `data-guide-cli`, `login-choices`, `data-guide-choice`, `login-secret`,
`login-action`, `login-refusal`), `web/src/ModelSources.tsx` (`model-server-add`,
`model-server-form`, `model-server-error` + `data-guide-refusal`), `web/src/GitServers.tsx`
(`author-row`, `author-form`), `web/src/Launch.tsx` (`launch-task`), the session tabs
(`session-tabs`), `web/src/WaitingCard.tsx` (`gate-card`, `question-card`),
`web/src/Terminals.tsx` (`terminal-panel`); tests beside each changed component where a
marker depends on state (the chosen choice, the refusal kind).

- [ ] Test (vitest): `LoginSheet` with codex's rows: picking Pay per use puts
  `data-guide-choice="usage"` on its box and `login-secret` inside it; a refusal shows
  `login-refusal`. `Shell`: Help's menu lists Documentation, GitHub, Getting started, Report a
  bug in that order, Getting started after the divider, and calls the guide's `restart`
  (a prop or the facts store's `restart` event; no guide chunk needed).
- [ ] Implement; `make web`.
- [ ] Commit `Mark the elements the first-run guide points at (LAD-311)`.

### Task 4: the guide file, facts store and marker test (D4, D7, D8)

Files: create `web/src/guide/hints.ts`, `web/src/guide/facts.ts`, `web/src/guide/hints.test.ts`;
publish from `Providers.tsx`, `useModelSettings.ts`/`ModelSources.tsx`, `GitServers.tsx`.

Interfaces: `type Hint = {id; kind: "guiding" | "info"; part?: "model" | "author" | "start";
target?: string; anchor?: string; when: Cond[]; done?: Cond[]; prefer?: Side[]; phoneOnly?:
boolean; texts: Texts; providers?: Record<string, Texts>}`; `Cond = [name: string, ...args:
string[]]`; `HINTS: Hint[]` in the design doc's order; `TIP_IDS`; facts store `publish(part:
"logins" | "servers" | "author", value)`, `subscribe(fn)`, `current()`.

- [ ] Test: the marker test of D8 over `import.meta.glob("../**/*.tsx", {query: "?raw"})`
  (excluding tests and `guide/`); unique ids; every `Cond` name in `conditions.ts`'s list;
  non-empty texts without `/[Ѐ-ӿ]/`; provider keys ⊂ {"claude", "codex"}. A
  publish from `Providers` (rendered with a fake page) reaches `current()`.
- [ ] Implement all stage-1 hints with the design doc's texts.
- [ ] Commit `Write the first-run guide's hints as data (LAD-311)`.

### Task 5: placement (D10)

Files: create `web/src/guide/place.ts`, `web/src/guide/place.test.ts`.

Interfaces: `type Rect = {x; y; w; h}`; `place({card: {w, h}, target: Rect, anchor?: Rect,
dialog?: Rect, viewport: Rect, phone: boolean, kind, prefer?: Side[], obstacles: Rect[]}) →
{x, y, side: Side | "edge" | "free" | "on-target", arrow?: {x, y, side}, ring: "solid" |
"dashed" | "none", cutAnchor: boolean, dim: boolean}`.

- [ ] Tests, one per rule of the design doc §4: phone below then above; wide prefer then
  right/below/above/left; inside a dialog beside the dialog at the anchor's height; a tip
  never over an obstacle; tip fallbacks (free place + dashed ring, a tall target's lower
  part, beside after all); guiding fallbacks (cut the anchor, then the bottom edge); a target
  over 70 % of a phone → no dim, card at the bottom; the arrow 12 px from corners; margins 16
  and 12.
- [ ] Implement; `make web`.
- [ ] Commit `Place the guide's cards beside their targets (LAD-311)`.

### Task 6: the engine (D3, D6, D9, D12, D13)

Files: create `web/src/guide/conditions.ts`, `web/src/guide/Guide.tsx`, `web/src/guide/mount.tsx`
(the shell's lazy mount), tests `Guide.test.tsx`, `Guide.login.test.tsx`,
`Guide.tips.test.tsx`, `Guide.a11y.test.tsx`, `mount.test.tsx`; `web/src/Shell.tsx` mounts
`GuideMount`; `web/src/tokens.css` two tokens; `web/src/styles.css` a Guide section.

- [ ] Tests: the welcome after `telemetry_asked` false; Show me → Open Settings; parts skipped
  by facts and by published facts; the counter; I have neither on each row; every login step
  by the chosen choice, `login-paste` for codex's `usage` and `token`; the guide hides while a
  second window is on top; the none-of-these card's four links (`target="_blank"`) and the IT
  line; New session completes (`POST complete`); Not now / Esc and a remount (new page
  load) shows it again; tips: one at a time, order, `POST shown` on appearance, tips off; a
  missing marker → `POST missing` after 2 s (fake timers) and the next hint; `restart`;
  a11y: dialog roles, focus moves and returns, Tab cycle, `inert` set and removed on every
  end (Review Focus 5), the live region for tips, reduced motion; `mount.test.tsx`: completed
  with every tip shown → no dynamic import, one `GET`; `auto: false` → no import and nothing shown until Getting started, then the welcome.
- [ ] Implement; `make web` (check the lazy chunk in the build output).
- [ ] Commit `Run the first-run guide over the UI (LAD-311)`.

### Task 7: the UI e2e (D14)

Files: create `tests/ui/test_first_run_guide.py`.

- [ ] One test, guide on (`monkeypatch.delenv("LADO_GUIDE")` before `server`), fake providers,
  `GIT_CONFIG_GLOBAL` an empty file, `tests/fake_endpoint.py` as the model server: answer the
  statistics banner; welcome → Show me → Open Settings → (Agent CLIs skipped) Model servers →
  Add server → the form (a refused key first: The key wasn't accepted, then a good one) →
  Git servers → Set author → the form → New session → the New session tip → Got it; reload:
  no guide. A screenshot of each hint (`shot`). Then Help → Getting started: the welcome again
  and Show me leads to New session. A second test at 390 px: `open-menu` before Settings,
  `settings-back` before Git servers, the ring following a scroll (Review Focus 4).
- [ ] Run `uv run pytest -m ui tests/ui/test_first_run_guide.py -n0`, then every UI e2e
  `uv run pytest -m ui -n auto tests/ui` (all with the guide off).
- [ ] Commit `Walk the first-run guide's main path in the browser (LAD-311)`.

### Task 8: docs

Files: `docs/install.md` (`LADO_GUIDE=0` beside `LADO_NO_UPDATE_CHECK=1`), `docs/design/ui.md` (a "First-run guide" section pointing to `web/src/guide/hints.ts`,
Help's Getting started), `docs/design/modules.md` (`guide.py`, the routes), `docs/testing.md`
(`LADO_GUIDE=0`, the guide's e2e), `AGENTS.md` Layout (`guide.py`: the first-run guide's
record and facts), `CHANGELOG.md` (the line of Global Constraints).

- [ ] `uv run pytest tests/test_agents_md.py -n0`; `openspec validate first-run-guide --strict`.
- [ ] Commit `Document the first-run guide (LAD-311)`.

### Task 9: the manual check

- [ ] The design doc's §13 on a fresh `LADO_HOME`, light and dark, 390/768/1440 px;
  screenshots of each changed screen as run artifacts listed in `build-report`.
