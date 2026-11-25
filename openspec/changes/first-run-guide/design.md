## Context

LADO's screens for a first start exist: Settings → Agent CLIs (Log in… opens a CLI's login
window, `LoginSheet`), Model servers (Add server and its form), Git servers (LADO's commit
author, LAD-312) and the New session window. Nothing leads a person to them.

What the web UI knows today, read in the code (0.49.0 unreleased, `main` at 632af7f4):

- The change feed (`web/src/live.ts`, `server/feed.py`) carries sessions, agents, messages,
  runs, gates, notes, events, artifacts, kits and marketplaces. It carries **no** logins,
  model servers or commit author.
- Agent CLIs reads `GET /api/providers/logins`, the server's last check
  (`server/provider_check.py`: kept for the server's lifetime, empty after a start until a
  `POST /api/providers/check` runs one; a check runs every CLI's version and the login shell,
  seconds). Model servers reads `GET /api/model-settings` (lado.db, asks no server). Git
  servers reads `GET /api/git-servers` (LADO's author and git's own). Each page keeps its
  data in its own component state.
- There is no "settings" load at page start. Per page load the UI reads `/api/health`,
  `/api/update`, `/api/telemetry` (the statistics banner, `ask`) and the feed.
- The UI has no way to write to LADO's error journal; `telemetry.record(where, exc, …)` is the
  server's.
- lado.db may not exist on a fresh LADO (`server/app.py`'s `database` dependency: "no lado.db
  made").
- Tests switch LADO's background features off by environment variables set in
  `tests/conftest.py` (`LADO_TELEMETRY=0`, `LADO_NO_UPDATE_CHECK=1`); UI e2e servers inherit
  the test's environment (`tests/ui/conftest.py`, `_serve`).
- Login choices are the providers' data (`Provider.login_choices`): Claude Code has
  Subscription (`claude setup-token` token) and Pay per use (key); Codex CLI has ChatGPT plan
  (sign-in code action), access token and Pay per use (key).

The human's decisions: the task and `/lad-311-proposal` (24.11.2026), the design flow
`ui-design/lad-311-guide` (critique round 2: done), the step's decisions of 25.11.2026, and
the answers in this design's dialogue (see the artifact `design`).

## Goals / Non-Goals

Goals: stage 1 of the guide as `docs/superpowers/specs/2026-11-25-first-run-guide-design.md`
describes: the engine, the main path, five tips, Help → Getting started, the record on the
server, the marker test and one UI e2e of the main path. Non-goals: the proposal's Out of
scope.

## Decisions

### D1. The record: `LADO_HOME/guide.json`, not lado.db

`{"completed": false, "shown": [], "tips_off": false}`, read and written by a new module
`lado.guide`. lado.db may not exist at first start, and a table would need a schema
migration for three values; the statistics choice is a file under `LADO_HOME` for the same
reason. Writes go through one process lock and an atomic replace (a temporary file, then
`os.replace`). `shown` is merged as a union, so two tabs marking different hints lose
neither. A record that cannot be read (bad JSON) is written to the error journal and treated
as missing (D3), never as completed.

Options: lado.db (rejected: migration, and a lado.db made on first start only for this);
the browser's storage (rejected by the human: one record for every browser).

### D2. The API: `GET /api/guide` and `POST /api/guide`

`GuideInfo`: `auto` (bool, D11), `completed`, `shown` (ids), `tips_off`, `telemetry_asked` (the
statistics banner still asks: `telemetry.state().ask`; the welcome waits for it), `facts`
(`{model: bool | null, author: bool}` while not completed, else null). `POST` takes
`GuideAction {action: "shown" | "complete" | "tips_off" | "restart" | "missing", ids:
[str] = [], marker: str = ""}` and answers `GuideInfo`. Both under the usual guard (`guard`,
`guard.changes`). Ids are free strings checked only for length and characters (the server
keeps no list of hints: the guide file is the one source, D7).

`telemetry_asked` rides here instead of the guide reading `/api/telemetry` a second time.

### D3. Facts and the first record

`facts.model`: true when an agent CLI has a model to work on: a configured model (a model of
a saved model server ticked for an agent CLI, lado.db's `models`, when it exists) or a
provider's row in `provider_check`'s snapshot logged in. A server saved with no model ticked
is none: the agents would start on their CLI's own settings (the human's manual check, 25.11). When the snapshot has not been read since
the server started, the server starts one check (`provider_check.start()`) and waits for it
up to 20 s before it answers; past that it answers `model: null` and the check goes on, and
the next page load reads its result. The guide shows nothing while its `GET` has not
answered, so the slow first answer costs no request more. `facts.author`: LADO's author or git's own, as Git servers' listing computes
them (`commit_authors.lado()`, `commit_authors.git_own`).

With no `guide.json`, the server creates the record only once `model` is known: completed
when a model is connected (an existing set-up LADO never sees the welcome), else not. While
`model` is null and no record exists, `GET` answers `completed: true` without writing, so
nothing shows; a check whose pass raised counts as not ended (null), never as "no model".
A mark made while there is no record (a tip shown meanwhile) starts from that completed
record, so it never starts the main guide on a LADO that may be set up; only `restart`
makes a record not completed. A `GET` that finds a record not completed with a model and an
author both in effect makes it completed (D12). Facts are computed only while not completed: a completed
guide costs one file read.

Options: put logins and model servers into the change feed (rejected: a feed kind for data
no table holds goes through `DERIVED`, which runs on every batch; much more than the guide
needs); always show the welcome and let the person dismiss it (rejected by the critique F4).

### D4. Live facts on the Settings pages: the pages publish, the guide listens

`web/src/guide/facts.ts`: a small store (`publish(part, value)`, `subscribe`), outside the
lazy engine. `Providers.tsx` publishes its rows (installed, logged in, per provider),
`useModelSettings` the number of configured models, `GitServers.tsx` its author and
git's own, each when it loads or changes them. The engine takes a published value over the
server's `facts` (it is newer). No request of the guide's own on these pages.

### D5. Component state is read from markers

Forms and windows already render their parts only while open; the guide reads "open" as "a
visible element carries the marker". The login sheet adds `data-guide-cli="<provider>"`, the
chosen choice's box `data-guide-choice="<choice id>"`, and Model servers' refusal line
`data-guide-refusal="key" | "unreachable"`. No component gets a callback or a context for the
guide: the markers are the whole interface, and the marker test (D8) keeps them honest.

### D6. One generic paste step (critique F12; the human's answer)

`login-paste` shows in any login window whose chosen choice is a field to paste into and has
no step of its own: Codex's Pay per use and access token today, any later CLI's choices
without texts. Claude Code keeps its own two steps. The window's own line already says where
the value comes from.

### D7. The guide file is data; the engine is a lazy chunk

`web/src/guide/hints.ts` holds every hint: `id`, `kind`, `target`, `anchor`, `when` (named
conditions with arguments), `done`, `prefer`, `part`, the texts, and per-provider texts keyed
by the provider's name. It is in the main bundle (a few kB of data): the shell needs the ids
to decide whether anything is left (`!completed`, or `!tips_off` and a tip id not in
`shown`). `web/src/guide/Guide.tsx` and the placement code load with `React.lazy` only then.
No guide text is written in a component.

### D8. The marker test

A vitest unit test reads `web/src/**/*.tsx` (not tests, not `guide/`) and checks that every
`target` and `anchor` of `hints.ts` appears as `data-guide="…"` (or as a template whose
prefix matches, for `cli-row-${name}`), that every condition and completion name is known to
the engine, that ids are unique, that every text is non-empty and has no Cyrillic, and that
every provider key of the texts is a provider the server knows (from `api.gen.ts`'s provider
names in a fixture). A marker added in the code but used by no hint is no failure.

### D9. A marker missing at run time

The engine waits 2 s for a visible target; then it skips the hint for this page load and
posts `{action: "missing", ids: [id], marker}`. The server records it with
`telemetry.record("ui:guide", GuideMarkerMissing(f"{id}: {marker}"))`, once per id per
server lifetime. Nothing is shown to the person.

### D10. Placement is a pure function

`web/src/guide/place.ts`: `place(card, hole, anchor, window, options) → {x, y, side, arrow,
pointingRing}` over plain rectangles, with the obstacle list passed in: a hint's `keep`
markers (text its card must leave in sight: a login window's choices, the task in the session,
the author just saved; the human's manual check, 25.11) and, for a tip, the focusable
elements. All rules of the design doc's §4 are unit tests over rectangles; the engine only
measures (each rectangle cut to the boxes that clip it, a list that scrolls) and calls it. A
card at the edge over its target gets room at the end of what scrolls the target, which
scrolls the target's end clear of the card (a server form grown tall on a phone).

### D11. One switch for videos and tests: `LADO_GUIDE=0`

The human records videos on a live LADO, where the guide would get in the way; the menu line
must stay for a realistic picture. With `LADO_GUIDE=0` in the server's environment,
`GuideInfo.auto` is false: a `GET` computes no facts and makes no record, and the UI starts
nothing by itself and loads no engine. Help → Getting started still works: it posts
`restart`, which writes the record, and the engine runs for that page load (the human's alternative, a stub, was not
needed: the line is pressed only on purpose, and a video of the guide itself stays
possible). `tests/conftest.py` sets it for every test, beside `LADO_TELEMETRY=0`, since no
other test presses Getting started; the guide's UI e2e test removes it before its server
starts. Documented for users in `docs/install.md` beside `LADO_NO_UPDATE_CHECK=1` (and the
container's `.env` example when it lists such variables), and in `docs/testing.md`.
Option rejected: a Settings toggle (a new element on a screen, against the human's
"no new elements").

### D12. "Not now" lives for the page load

Not now and Esc are kept in the engine's memory only; a reload brings the guide back, as the
human decided, while a model or an author is missing: with both, only New session is left,
which needs no guide, and the next `GET` completes the record (D3). So the guide restarted
from Help and closed on a set-up LADO does not come back by itself (the human's decision
after the manual check, 25.11). Chains (stage 2) will use the same.

### D13. Completion

The engine posts `complete` when `launch-task` becomes visible while the main guide is not
completed, whichever step shows. The welcome's condition also needs `facts.model === false`
unless the guide was restarted from Help in this page load.

### D14. The UI e2e path

The UI e2e server runs the fake providers, whose names have no texts in the guide file, so
the e2e path is: welcome → Open Settings → Model servers (the CLI steps are skipped by the
neutral-core rule) → Add server → the form, against `tests/fake_endpoint.py` → the server's
model → its tick for an agent CLI → Git servers →
Set author → the form → New session → the New session tip. The CLI and login-window steps are
covered by vitest over the engine with rendered `Providers`/`LoginSheet` and fake facts. The
test sets `GIT_CONFIG_GLOBAL` to an empty file so that nobody signs commits.

## Risks / Trade-offs

- A login check at first start costs seconds of CLI runs, once per server start while the
  guide is not completed: the same check Agent CLIs starts on open.
- The marker test checks presence, not place: a marker moved to another element passes. The
  review trap in `.lado/sdlc.md` (added on `main` for LAD-311) covers it.
- Spotlighting a target inside a scrolled container: the layer follows by a capture scroll
  listener; tested in the UI e2e on a phone width.

## Migration Plan

None: no schema change. A LADO updated to this version with a model connected gets a
completed record on its first `GET /api/guide` and never sees the welcome.
