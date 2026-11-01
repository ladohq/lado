# Plan: Model and power choice for agents (LAD-154)

## State
Rejected at `plan_ok` (gate #191, 2026-11-01): «я передумал. Давай сделаем epic-ветку и будем вести разработку в ней. Я могу попросить тебя после некоторых задач помочь мне сделать ручную проверку, чтобы оценить как задача реализована визуально»
Rejected at `plan_ok` (gate #190, 2026-11-01): «я не планирую делать релизы между задачами. Я думаю следующий релиз будет включать весь эпик целиком или мы примем решение о релизе в ходе работы над эпиком.»
Phase: steps · Epic run: epic/epic-models · Branch: epic/lad-154-models
In work: S1 (LAD-169) · Next: S2 · Open checks: none
Standing rules of the human:
- Every step merges into the epic branch `epic/lad-154-models` and leaves it working; unset means today's behaviour; the epic reaches `main` by one final pull request (D10, replacing D2).
- No release between steps: the next release carries the whole epic, unless the human decides on a release during the epic (gate #190, D9).
- After some steps the human may ask the lead to help with a manual check of how the step looks; the lead then gives the branch, the folder, the commands and what to look at (gate #191, D10).
- Each step's task gets the label `component lado` (kit sdlc's: `component kit-sdlc`) and is linked to LAD-154; LAD-80 is not touched.
Last review: none yet, base at ca7548fc

## Steps

Statement steps 1–9 map to S1–S9; S3 and S9 split in two, S5 in four (each part merges
alone), S7 gains S7b for kit sdlc's own repository (D6). Statement step 10 is in "Later"
(D3). Every step targets the epic branch `epic/lad-154-models`; after each step the lead
brings `main` into it (D10). A conflict of that merge (migration numbers in `state.py` and
`tests/agent_helpers.previous_schema`, CHANGELOG's heading) is aborted and put to the human
with a recommendation, usually a small sdlc task that brings `main` in and renumbers the
epic's migrations on top of `main`'s (critic P19). No two steps run at once: S3a and S4 both change `cli.py` and the server's API
(`web/openapi.json`, `web/src/api.gen.ts`), the others build on each other.

Rules for every step of LADO (not S7b, which is kit sdlc's own release):
- Its Check includes: a CHANGELOG line under the current `## X.Y.Z (unreleased)` heading
  (one minor for the whole epic, D9; a step adds no heading of its own while that one is
  unreleased); the spec of its capability in `openspec/specs/` (a new one for
  agent models, session models, model servers, power tables) and `openspec validate
  --specs --strict`; `make lint`, `make test`, `make web` when `web/` or the API changed,
  the changed tests with their markers; CI green.
- A step that changes the schema has in its Check: the migration from
  `tests/agent_helpers.previous_schema`; the way back: an `lado update` rollback restores
  `lado.db` from its backup, an older LADO refuses a newer database (`state.py`).
- The session's choice is stored in the power table's format from S2 on (all rows the same
  model), so later steps add levels and rows, not a second format.
- Thresholds of the model check (all steps that take a model): a model that is neither
  one of the CLI's aliases nor in the CLI's or server's list starts with a loud warning
  when the CLI gives no list; it is refused before the start when the CLI or the server
  gives a list and the model is not in it.

### S1 — The agent's model is visible (M)
Status: in progress (LAD-169)
Check:
- Unit and integration tests with the fake agent: each agent in `lado.db` has a model,
  an effort and their source; `list_agents`, `GET` of the session's agents in the API
  and the UI card show them; unset, the card says the CLI's default, and names the model
  where the CLI reports it in its events (Codex's Stop input carries `model`; Claude and
  OpenCode/Kilo checked by the analyst against `docs/design/agents.md`); for Codex the
  model carried from the user's `config.toml` shows with that source.
- Codex's carried model and effort are read by the same rule as `_model_provider`
  (`providers/codex.py`): the chosen profile's, else the top level's.
- The schema migration and the way back (rules above).
- UI e2e of the card, a mockup at `design_ok`; `docs/design/ui.md`, `docs/cli.md` (where
  `lado ls` or `lado log` show it), `docs/design/agents.md` describe what was built.
Notes: no model is chosen yet; this step only learns and shows. No terminal reading
(Events, not screens): a CLI that reports nothing shows "CLI default" without a name.
BACKLOG's "Choose the model per agent" is replaced by a link to LAD-154 here (D8).
The analyst may split the UI card off when the design cannot take it in one round.

### S2 — One model per session (M)
Status: planned
Check:
- `lado start --model <model>` and a field in the launch window's Advanced; the session
  keeps it (in the table's format); every agent of the session's CLI starts on it through
  the CLI's own way (Claude `--settings`/`--model`, Codex `CODEX_HOME` on top of the
  carried user value, OpenCode/Kilo config content); S1's card shows it with the source
  "session".
- The model check by the thresholds above; an agent of another CLI in the same session
  (a worker started with another provider) keeps its CLI's default and its card and
  `spawn_worker`'s warnings say so (no silent drop).
- Smoke per provider (CI): the model reaches the real CLI's argv or config.
- The schema migration and the way back (rules above).
- UI e2e and mockup; `docs/cli.md`, `docs/design/ui.md` describe what was built.
Notes: walking skeleton: choose → reaches the CLI → visible. A model is a CLI + a model;
which CLI's models the field offers comes from the session's provider. Free input with a
check, no catalogue of LADO's own.

### S3a — Find out what a model server is (M)
Status: planned
Check:
- Against fake servers in tests (an OpenAI-compatible `/v1/models`, Ollama, LM Studio, an
  Anthropic-compatible one): given only an address (and a key by name, D4), LADO names
  the server's type, its models and the CLIs that can use it; an address that does not
  answer, a 401 and an unknown server give a clear message.
- Compatibility rule: an OpenAI-compatible server (chat completions) is named usable by
  OpenCode and Kilo; one that answers the Responses API by Codex; one that answers the
  Anthropic Messages API by Claude Code; the fake servers prove each yes and each no
  (which request proves each API is the analyst's call).
- In Docker, `localhost`/`127.0.0.1` that does not answer gives the loud hint
  `host.docker.internal:<port>` (D5); never a silent rewrite; no network scan.
- `docs/cli.md` describes the command.
Notes: no session uses the result yet; S3b does; S9a and S9b rest on its rule.

### S3b — A session on a model server through OpenCode/Kilo (L)
Status: planned
Check:
- A session started with a server address and one of its models runs OpenCode and Kilo
  agents on it: the server goes into each agent's config content as an OpenAI-compatible
  provider; the key's value reaches the agent only through its environment, never the
  config file (the canary approach of LAD-116); before the start LADO checks the server
  answers and the model is there, and refuses loudly otherwise; a key named but found
  neither in LADO's nor in the project's secrets refuses before the start, naming where
  to create it; an agent of a CLI the server does not suit (a Claude or Codex worker in
  that session) is refused at its start with a text naming the server's CLIs.
- The session keeps the server's address and the key's name: the schema migration and the
  way back (rules above).
- Integration test with the fake agent and a fake server; S1's card shows the model with
  the server as its source.
- The human's manual check on a real server (D7: which, they will add) before the merge.
- `docs/install.md` (local models, Docker), `docs/cli.md`, `docs/design/ui.md`.
Notes: the core value of the epic with S1–S2. Where the server is kept before S5a: the
session (an address and a key name in the launch window and `lado start`).

### S4 — Effort with the model (S)
Status: planned
Check:
- The session's model takes an effort; Claude (`--effort`/settings), Codex
  (`model_reasoning_effort` on top of the carried value), OpenCode/Kilo (variant) get it;
  where the CLI or the model cannot take it, a loud warning before the start; S1's card
  shows it.
- Unit tests per provider, smoke per provider (CI); `docs/cli.md`, `docs/design/ui.md`.
Notes: the CLIs' scales differ (research §1.3); LADO passes the CLI's own value and keeps
no common scale.

### S5a — The user's settings store and model servers in the CLI (M)
Status: planned
Check:
- A store of the user's settings on the server (in `lado.db` or `LADO_HOME`; the
  analyst's call); a `lado` command adds a model server by address (S3a's probe, a key by
  name), lists and removes it; `lado start` takes a saved server by name; `lado doctor`
  checks the saved servers (answers, the key's secret exists).
- Removing a server a session uses: the session's next agent refuses loudly at start;
  removing the secret a server names: S3b's refusal before the start.
- The schema migration (or the new file) and the way back (rules above); `lado
  uninstall` removes the settings with `LADO_HOME`.
- `docs/cli.md`, `docs/design/modules.md` describe what was built.

### S5b — Model servers in Settings and the launch window (M)
Status: planned
Check:
- Settings → Models lists the saved servers: add by address with S3a's result shown, a
  key by name with the offer to create the secret, remove; the launch window chooses a
  saved server.
- UI e2e, mockup at `design_ok`; `docs/design/ui.md`.

### S5c — The user's power table (M)
Status: planned
Check:
- The user's table light / normal / heavy → CLI + model + effort, set in Settings →
  Models and by a `lado` command; an empty row is the CLI's default; with no one choosing
  a row an agent takes "normal"; S1's card names the row and the level ("normal work,
  user table").
- What a row's CLI does against the agent's provider: as Q3 decides, in the Check of
  S5c and S8; the login check before the start goes by the CLI the agent resolves to;
  with (a), only a provider the human chose counts as the session's (Q3).
- The table is kept in S5a's store: the schema is unchanged when S5a's store holds it,
  else the migration and the way back (rules above).
- Unit tests of the resolution; UI e2e, mockup; `docs/design/ui.md`, `docs/cli.md`.
Notes: light and heavy take effect from S7/S8, when roles, steps and the supervisor choose
a row. Ready-made tables («Claude: haiku / sonnet / opus», «Всё на сервере»): Q1.

### S5d — The session's table row by row (S)
Status: planned
Check:
- The launch window's Advanced and `lado start` set the session's table row by row (S2's
  one model fills every row); an empty session row takes the user's; S1's card names the
  level.
- The launch window tells a provider the human picked from the default it shows, so a
  default never overrides the rows of the user's or the project's table (Q3, critic P17).
- UI e2e, mockup; `docs/design/ui.md`, `docs/cli.md`.
Notes: the statement's session level is a table (critic P6); S2's one model stays its
shortcut.

### S6 — The project's power table (S)
Status: planned
Check:
- The project page and `lado project` set the project's table next to its variables;
  user → project → session resolve row by row; the card names the level.
- The schema migration and the way back (rules above).
- UI e2e, mockup; `docs/design/projects.md`, `docs/design/ui.md`, `docs/cli.md`.

### S7 — Power on roles and flow steps (M)
Status: planned
Check:
- A role (`agents/<role>.md`) and a flow step take a power (light / normal / heavy); an
  agent of that role or step gets that row; a value outside the three is a load error; the
  kit docs say a kit with the field needs `dependencies.lado: ">=<this release>"`, and
  `kits.warnings()` asks for it as it does for `expects`.
- Unit tests of the kit and flow loaders, integration test with the fake agent: a role's
  power reaches the agent's model; docs of the kit format.
Notes: the strict keys (`kits.AGENT_KEYS`, `flows.STATE_KEYS`) mean an older LADO refuses
such a kit; `dependencies.lado` makes the refusal clear.

### S7b — Kit sdlc's roles and steps marked (S)
Status: planned
Check: kit sdlc (its own repository) marks its roles and steps with a power and
`dependencies.lado` on the LADO release that ships S7; a session with that kit shows each
role's row on its cards (checked against LADO's epic branch before that release).
Status of its check: open until the LADO release that carries the epic (D9): kit sdlc's
pull request merges and is released by kit sdlc's own rules only after it.
Notes: tracker task with `component kit-sdlc` (D6). With no LADO release mid-epic (D9) it
is built during the epic and waits for that release to merge.

### S8 — Power when the supervisor spawns a worker (S)
Status: planned
Check:
- `spawn_worker` takes a power, not a model; it overrides the role's and the step's; the
  card names the source ("supervisor"); a model name passed there is refused loudly;
  a row's CLI against the provider passed to `spawn_worker`: as Q3 decides.
- Integration test with the fake agent through `lado mcp`; `docs/design/agents.md`, the
  MCP tool's description.

### S9a — A model server for Claude Code (M)
Status: planned
Check:
- An Anthropic-compatible server (S3a names it) runs Claude Code agents through
  `ANTHROPIC_BASE_URL` in the agent's own environment, the key only by name; a server that
  is not Anthropic-compatible refuses Claude loudly before the start.
- Smoke (CI) with a fake Anthropic-compatible endpoint; the human's manual check on a real
  server (D7); `docs/install.md`, `docs/design/agents.md`.

### S9b — A model server for Codex (M)
Status: planned
Check:
- A Responses-compatible server runs Codex agents through a `model_providers` entry in the
  agent's `CODEX_HOME` (on top of the carried user values), the key only by name; a server
  without the Responses API refuses Codex loudly before the start.
- Smoke (CI) with a fake endpoint; the human's manual check (D7); `docs/install.md`,
  `docs/design/agents.md`.

## Open questions

- Q1 (decided at `plan_ok` #194: in S5c). Ready-made tables («Claude: haiku / sonnet / opus», «Всё на сервере») go with the
  user's table in S5c, not with S7 as the statement had it: they are the table's UI and
  need nothing of S7. Recommended: in S5c.
- Q2. Which model server the human checks S3b, S9a and S9b on, and its address (D7).
  Needed before S3b's merge.
- Q3 (decided at `plan_ok` #194: (a) with P15 and P17). A table row names a CLI (heavy → Claude opus); the agent's provider may come from
  elsewhere (the session's `--provider`, `spawn_worker`'s provider). Options: (a) the
  row's CLI decides the agent's CLI; an explicit `--provider` of the session (only one
  the human chose: `lado start --provider`, or a provider picked in the launch window
  rather than its default; not the value the session keeps for its resume; critic P17)
  is the session level and overrides the CLI of the user's and the project's rows (each level
  overrides only where it says something; critic P15); without it the session's provider
  is only the default for agents whose row is empty; the login check goes by the CLI the
  agent resolves to; a provider passed explicitly to `spawn_worker` that differs from the
  row is refused loudly, naming both; (b) the provider always wins and the row
  is used only when its CLI matches, otherwise the CLI's default with a loud warning;
  (c) any mismatch is refused. Recommended: (a): the row is a model and a model is a CLI
  + a model (statement), the explicit conflict is the only one a human or supervisor made
  on purpose, and nothing is replaced silently.

## Later

- A model for one role (statement step 10) — not needed yet (D3) — LAD-154 — after S7, if
  a power row is too coarse.
- Profiles with a default model set — LAD-80 — the table's format is the "saved table"
  they would name (`lad-154-profiles.md`, option B).
- Named model sets («Экономный», «Максимум», «Локально») — out of the statement — none —
  the user table of S5c is the one set until profiles come.
- Automatic power by task complexity; fallback models on an error — out of the epic
  (statement).
