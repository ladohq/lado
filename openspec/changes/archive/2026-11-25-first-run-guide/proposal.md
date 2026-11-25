Task: LAD-311

## Why

At first start LADO may not be able to work: no agent CLI is logged in, no model server is
saved and nobody signs commits. The screens that fix it exist (Settings → Agent CLIs, Model
servers, Git servers → Commit author, LAD-312), but a person has to guess where to go, and a
person who is not a developer does not. The task's goal: on a clean LADO with no login, no
model server and no commit author, a person reaches their first session by following the
guide, without opening the documentation.

Root cause: LADO's first screen assumes a set-up machine. Nothing in the UI says that a model
must be connected first, where, or with what, and nothing explains the session page, a gate,
an agent's question or a terminal on first sight.

Options weighed (agreed with the human on 23–24.11.2026, design flow `ui-design/lad-311-guide`):

- A (taken): a guide drawn over the unchanged UI: guiding spotlights on the main path that
  wait for the real action, and one-time tips at first encounters; all hints as data in one
  file, aimed at stable `data-guide` markers. Costs one engine and a marker per target; new
  screens stay free of onboarding elements.
- B: a welcome page or a checklist on Home. Rejected by the human: new elements on screens,
  and a second place that describes the same settings.
- C: documentation only. Rejected: the person the task is for does not read it.

## What Changes

Stage 1 of two (stage 2, a later task: the projects chain, "connect more models", the git
access chain, Kits):

- **The main guide** on a fresh LADO, after the statistics question is answered: a centred
  welcome, then guiding steps to connect a model (Settings → Agent CLIs: Claude Code's row,
  then Codex CLI's, each through its login window's choices; then Model servers → Add server →
  the form), with a centred "Don't have any of these yet?" card (links to Claude plans,
  ChatGPT plans, OpenRouter keys and Qwen (Alibaba Cloud) keys, and a line to ask the
  company's IT team); then, only when nobody signs commits, Git servers → Set author → the
  form; then New session, whose opening completes the guide. Steps done in the system are
  skipped; CLI steps exist only for providers the guide file has texts for.
- **Login window steps** inside Claude Code's and Codex CLI's login windows: which choice,
  the token or key, a generic "Paste it and press Save" step for any other paste choice
  (Codex's Pay per use and access token), a refused value, Codex's one-time code.
- **Five tips**, each once: the New session window, the session page, the first gate, the
  first agent question, the first terminal; Got it and Don't show tips like this.
- **Not now / Esc** closes the main guide until the next page load; it comes back until
  completed. A LADO that already has a model connected when the guide first runs never sees
  the welcome.
- **Help → Getting started**: the only new element on any screen; restarts the guide and
  turns tips back on.
- **The guide's marks on the server**: `LADO_HOME/guide.json` (completed, shown hints, tips
  off), read by `GET /api/guide` once per page load and written by `POST /api/guide`; the
  same in every browser.
- **Upkeep**: every hint is data in `web/src/guide/hints.ts`; targets are `data-guide`
  markers on existing elements; a unit test checks every marker exists; a marker missing at
  run time skips its hint and goes to LADO's error journal; one UI e2e walks the main path
  with the guide on.
- **`LADO_GUIDE=0`** in LADO's environment: the guide never starts by itself (for recording
  videos on a live LADO, and for every other test); Help → Getting started still starts it.
- Version: minor (a feature and a new API).

## Out of scope

- Stage 2's hints (projects chain, more models, Add git server on an access error, Kits): a
  later task, as agreed with the human.
- The Home chat of LAD-310 as the last step: until it exists, the last step is New session;
  LAD-310 moves the step when it lands.
- Free models or a demo of LADO at work for a person with no subscription and no key: the
  human decided against free models; a demo is a separate idea.
- Localisation: the UI is English; the guide's texts are English like the rest.
- A guide for the command line (`lado start`): the guide is the web UI's.
- Changing the screens the guide points at: the guide adapts to them; only markers and the
  Help line are added.

## Capabilities

### New Capabilities

- `first-run-guide`: the guide's main path, tips, marks, restart, upkeep rules.

### Modified Capabilities

- `rail-help`: the Help menu gets Getting started.

## Impact

- Server: `src/lado/guide.py` (new: the record, facts), `server/app.py` (two routes),
  `server/models.py` (`GuideInfo`, `GuideAction`), `web/openapi.json`, `web/src/api.gen.ts`.
- Web: `web/src/guide/` (new: `hints.ts`, `facts.ts`, `conditions.ts`, `place.ts`,
  `Guide.tsx`, tests), `tokens.css` (two tokens), `styles.css` (a Guide section), `Shell.tsx`
  (mount, Help line), markers in `Providers.tsx`, `LoginSheet.tsx`, `ModelSources.tsx`,
  `GitServers.tsx`, `Settings.tsx`/`settingsSections.ts`, `Launch.tsx`, the session page's
  tabs, `WaitingCard.tsx`, `Terminals.tsx`, `icons.tsx` (compass).
- Tests: `tests/conftest.py` (`LADO_GUIDE=0`), `tests/test_guide.py`, `tests/test_server_guide.py`
  (or the server tests' file of its kind), vitest under `web/src/guide/`,
  `tests/ui/test_first_run_guide.py`.
- Docs: `docs/install.md` (`LADO_GUIDE=0`), `docs/design/ui.md`, `docs/design/modules.md`, `docs/testing.md`, `AGENTS.md`
  (Layout line), `CHANGELOG.md`.
- No schema change, no MCP tool, no CLI change, no provider change.
