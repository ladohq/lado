# Plan: Model and power choice for agents (LAD-154)

## State
Phase: plan · Epic run: epic/epic-models · Branch: base (`main`)
In work: none · Next: S1 · Open checks: none
Standing rules of the human:
- Every step merges into `main` on its own and leaves the product working; unset means today's behaviour (D2).
- Each step's task gets the label `component lado` (kit sdlc's: `component kit-sdlc`) and is linked to LAD-154; LAD-80 is not touched.
Last review: none yet, base at ca7548fc

## Steps

Statement steps 1–9 map to S1–S9; S3, S5 and S9 split in two (each part merges alone),
S7 gains S7b for kit sdlc's own repository (D6). Statement step 10 is in "Later" (D3).
Every step is a minor (schema, MCP tool or CLI change). One rule for all steps: the
session's choice is stored in the power table's format from S2 on (all rows the same
model), so S5 and S6 add levels, not a second format.

### S1 — The agent's model is visible (M)
Status: planned
Check:
- Unit and integration tests with the fake agent: each agent in `lado.db` has a model,
  an effort and their source; `list_agents`, `GET` of the session's agents in the API
  and the UI card show them; unset, the card says the CLI's default, and names the model
  where the CLI reports it in its events (Codex's Stop input carries `model`; Claude and
  OpenCode/Kilo checked by the analyst against `docs/design/agents.md`); for Codex the
  model carried from the user's `config.toml` shows with that source.
- The schema migration from `tests/agent_helpers.previous_schema`; the way back: an
  `lado update` rollback restores `lado.db`; an older LADO on a newer database is the
  existing refusal of `state.py` (checked, not changed).
- UI e2e of the card, a mockup at `design_ok`; `docs/design/ui.md`, `docs/cli.md` (where
  `lado ls` or `lado log` show it), `docs/design/agents.md` describe what was built.
- `make lint`, `make test`, `make web`, the changed tests with their markers, CI green.
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
- A model the CLI cannot take (not an alias, not in the CLI's list where the CLI gives
  one) is refused or warned loudly before the start; an agent of another CLI in the same
  session keeps its default and says so (no silent drop).
- Smoke per provider (CI): the model reaches the real CLI's argv or config.
- UI e2e and mockup; `docs/cli.md`, `docs/design/ui.md` describe what was built.
Notes: walking skeleton: choose → reaches the CLI → visible. A model is a CLI + a model;
which CLI's models the field offers comes from the session's provider. Free input with a
check, no catalogue of LADO's own. Way back: a rollback drops the session's model
column with the restored `lado.db`.

### S3a — Find out what a model server is (M)
Status: planned
Touches: a new module for probing, `server/` (one endpoint), `cli.py` (one command)
Check:
- Against fake servers in tests (an OpenAI-compatible `/v1/models`, Ollama, LM Studio, an
  Anthropic-compatible one): given only an address (and a key by name, D4), LADO names
  the server's type, its models and the CLIs that can use it; an address that does not
  answer, a 401 and an unknown server give a clear message.
- In Docker, `localhost`/`127.0.0.1` that does not answer gives the loud hint
  `host.docker.internal:<port>` (D5); never a silent rewrite; no network scan.
- `docs/cli.md` describes the command.
Notes: no session uses the result yet; S3b does. Parallel candidate with S4.

### S3b — A session on a model server through OpenCode/Kilo (L)
Status: planned
Check:
- A session started with a server address and one of its models runs OpenCode and Kilo
  agents on it: the server goes into each agent's config content as an OpenAI-compatible
  provider; the key's value reaches the agent only through its environment, never the
  config file (the canary approach of LAD-116); before the start LADO checks the server
  answers and the model is there, and refuses loudly otherwise; Claude and Codex agents
  in that session are refused or warned until S9a/S9b.
- Integration test with the fake agent and a fake server; S1's card shows the model with
  the server as its source.
- The human's manual check on a real server (D7: which, they will add) before the merge.
- `docs/install.md` (local models, Docker), `docs/cli.md`, `docs/design/ui.md`.
Notes: the core value of the epic with S1–S2. Where the server is kept before S5a: the
session (an address and a key name in the launch window and `lado start`).

### S4 — Effort with the model (S)
Status: planned
Touches: `providers/`, the launch window's model field, `cli.py`
Check:
- The session's model takes an effort; Claude (`--effort`/settings), Codex
  (`model_reasoning_effort` on top of the carried value), OpenCode/Kilo (variant) get it;
  where the CLI or the model cannot take it, a loud warning before the start; S1's card
  shows it.
- Unit tests per provider, smoke per provider (CI); `docs/cli.md`, `docs/design/ui.md`.
Notes: the CLIs' scales differ (research §1.3); LADO passes the CLI's own value and keeps
no common scale. Parallel candidate with S3a.

### S5a — The user's settings and model servers in Settings (M)
Status: planned
Check:
- A store of the user's settings on the server (in `lado.db` or `LADO_HOME`), Settings →
  Models lists the user's model servers (add by address, S3a's probe, a key by name with
  the offer to create the secret, remove); the launch window and `lado start` choose a
  saved server; `lado doctor` checks the saved servers.
- Removing a server a session uses: the session's next agent refuses loudly at start.
- Migration test, the way back by `lado update`'s restore; `lado uninstall` removes the
  settings with `LADO_HOME`; UI e2e, mockup; docs.

### S5b — The user's power table (M)
Status: planned
Check:
- Settings → Models has the table light / normal / heavy → CLI + model + effort, an empty
  row is the CLI's default; with no one choosing a row an agent takes "normal"; the
  session level (S2) overrides only where it says something; S1's card names the row and
  the level ("normal work, user table").
- Unit tests of the resolution; UI e2e, mockup; docs.
Notes: light and heavy take effect from S7/S8, when roles, steps and the supervisor choose
a row. Ready-made tables («Claude: haiku / sonnet / opus», «Всё на сервере»): Q1.

### S6 — The project's power table (S)
Status: planned
Check:
- The project page and `lado project` set the project's table next to its variables;
  user → project → session resolve row by row; the card names the level; migration test
  and the way back; UI e2e, mockup; `docs/design/projects.md`, `docs/cli.md`.

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
role's row on its cards.
Notes: tracker task with `component kit-sdlc` (D6); starts only after that LADO release.

### S8 — Power when the supervisor spawns a worker (S)
Status: planned
Check:
- `spawn_worker` takes a power, not a model; it overrides the role's and the step's; the
  card names the source ("supervisor"); a model name passed there is refused loudly.
- Integration test with the fake agent through `lado mcp`; `docs/design/agents.md`, the
  MCP tool's description.

### S9a — A model server for Claude Code (M)
Status: planned
Check:
- An Anthropic-compatible server (S3a names it) runs Claude Code agents through
  `ANTHROPIC_BASE_URL` in the agent's own environment, the key only by name; a server that
  is not Anthropic-compatible refuses Claude loudly before the start.
- Smoke (CI) with a fake Anthropic-compatible endpoint; the human's manual check on a real
  server (D7); docs.

### S9b — A model server for Codex (M)
Status: planned
Check:
- A Responses-compatible server runs Codex agents through a `model_providers` entry in the
  agent's `CODEX_HOME` (on top of the carried user values), the key only by name; a server
  without the Responses API refuses Codex loudly before the start.
- Smoke (CI) with a fake endpoint; the human's manual check (D7); docs.

## Open questions

- Q1. Ready-made tables («Claude: haiku / sonnet / opus», «Всё на сервере») go with the
  user's table in S5b, not with S7 as the statement had it: they are the table's UI and
  need nothing of S7. Recommended: in S5b.
- Q2. Which model server the human checks S3b, S9a and S9b on, and its address (D7).
  Needed before S3b's merge.

## Later

- A model for one role (statement step 10) — not needed yet (D3) — LAD-154 — after S7, if
  a power row is too coarse.
- Profiles with a default model set — LAD-80 — the table's format is the "saved table"
  they would name (`lad-154-profiles.md`, option B).
- Named model sets («Экономный», «Максимум», «Локально») — out of the statement — none —
  the user table of S5b is the one set until profiles come.
- Automatic power by task complexity; fallback models on an error — out of the epic
  (statement).
