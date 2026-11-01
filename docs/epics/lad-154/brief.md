# Brief: Model and power choice for agents (LAD-154)

## The human's statement

> «Прочитай эпик LAD-154 и покажи план работы», then «Запускай эпик» (2026-11-01).

The statement is the description of the tracker task LAD-154 «Эпик: выбор модели и
мощности для агентов», quoted in short:

> **Проблема.** LADO не выбирает и не знает модель агентов: каждый CLI работает на своей
> модели по умолчанию. Пользователь не может перевести агентов на свою модель, в том
> числе на сервер моделей в сети (Ollama, LM Studio, vLLM, корпоративный gateway), и не
> может дать тяжёлым ролям сильную модель, а лёгким — дешёвую.
>
> **Цель.** Удобная и гибкая настройка моделей, которая не требует настройки: без неё всё
> работает как сейчас. Главный сценарий — агенты на модели с сервера в сети.

Sources, attached to LAD-154 (in Russian): `lad-154-concept.md` (the concept, v2: the
power table, its levels, what each layer of today's code gives), `lad-154-research.md`
(how other orchestrators and the four CLIs choose a model and effort, local models, silent
drops), `lad-154-profiles.md` (why a model set is not LAD-80's profile; option B: a
connection names its key's variable). Where they differ, the task's description and the
decisions below win.

The statement's decisions:
- Unset, every agent runs on its CLI's default model, as today.
- A model is a CLI + a model + a reasoning effort.
- A power table maps light / normal / heavy work to a model, on three levels: the user
  (Settings → Models) → the project → the session (once, in the launch window's
  Advanced). Each level overrides the previous one only where it says something; an empty
  row is the CLI's default model.
- A kit names no model, only how heavy a role's or a flow step's work is. The supervisor
  gives a worker a power, not a model. The human does not start workers directly. With no
  one choosing, the power is "normal".
- A model server: the user enters only its address (and a key, D4); LADO itself finds the
  server's type, its models and the CLIs that can use it; it does not scan the network;
  before a start it checks that the server answers and the model is there.
- LADO keeps no model catalogue of its own: the CLIs' aliases, the model lists of the CLIs
  and servers, free input with a check.
- Each agent shows its resulting model, effort and where they came from. No silent
  substitution: a loud warning or a refusal when a CLI or a server cannot do something.
- Profiles and named sets (LAD-80) are not made now; the table's format lets them come
  later as a "saved table".

The statement's proposed steps: 1 the agent's model is visible (card, `list_agents`, API);
2 one model per session (`lado start --model`, Advanced); 3 a model server through
OpenCode/Kilo (type, models, compatibility, a check before the start); 4 effort with the
model; 5 the user's power table (Settings → Models); 6 the project's table; 7 power on
roles and flow steps, kit sdlc marked, ready-made tables; 8 power when the supervisor
spawns a worker; 9 a model server for Claude Code and Codex; 10 a model for one role, if
needed.

Known thin places (statement, checked against the code on 2026-11-01):
- An agent has no model in `lado.db` (`agents` table, `state.py`, `SCHEMA_VERSION` 35):
  a migration.
- The server has no store of user settings: UI preferences are in the browser's
  localStorage (`web/src/prefs.ts`).
- Role and flow-step keys are strict (`kits.AGENT_KEYS`, `flows.STATE_KEYS`): a kit with a
  new field fails to load in an older LADO; `dependencies.lado: ">=x.y"` is the guard
  (`expects` is not a version).
- Codex carries `model`, `model_provider`, `model_providers`, `oss_provider`, `profile`,
  `profiles`, `model_reasoning_effort` from the user's config into the agent's
  `CODEX_HOME` (`providers/codex.py`, `CARRIED`): LADO's value must go on top; unset, the
  carried value stays and is the "CLI default" with its source.
- LADO may run in Docker, where `localhost` is not the user's machine; compose already
  maps `host.docker.internal`.
- No provider reads the model from its events today; Codex's Stop input carries `model`
  (a comment in `providers/codex.py`), Claude and OpenCode/Kilo are to be checked.
- `AgentSpec` (`providers/base.py`) has no model or effort; each provider already writes
  its own per-agent config (`--settings`, `CODEX_HOME`, `*_CONFIG_CONTENT`), where a model
  fits without touching the user's global config.

## Goal and "done"

Goal: models are chosen conveniently and flexibly, and nothing needs setting: unset,
everything works as today. The main scenario: agents on a model of a model server on the
network.

Done when statement steps 1–9 are merged into `main`, each on its own, leaving the product
working (D2, D3):
- every agent shows its model, effort and their source in the UI card, `list_agents` and
  the API;
- a session runs on one chosen model and effort (`lado start`, the launch window);
- a session runs on a model server given by its address through OpenCode/Kilo, and through
  Claude Code and Codex where the server speaks their protocol, with a check before the
  start and a loud refusal otherwise;
- power tables at the user, project and session levels resolve per agent from the role,
  the flow step or `spawn_worker`, kit sdlc's roles and steps are marked (D6);
- no value is dropped silently on any of the four CLIs.

Statement step 10 goes to "Later" (D3).

## Readiness checklist

| Topic | Verdict |
|---|---|
| Goal and "done" | Covered: the statement's goal, "done" above (D3). |
| Users and how they use it | Covered: the human running sessions on their CLIs' logins who wants a local or corporate model server, or heavy roles on a strong model and light ones on a cheap one; kit authors marking power; the supervisor choosing a worker's power. |
| Scope and what is out | Covered: out are profiles (LAD-80), automatic power by task complexity, fallback models on error, statement step 10 (D3), network scanning, LADO's own model catalogue. |
| Data and migrations | Covered by S1, S2, S3b, S5a, S6, Check: "the schema migration from `tests/agent_helpers.previous_schema`; the way back: an `lado update` rollback restores `lado.db` from its backup, an older LADO refuses a newer database" (the plan's rule for every step that changes the schema, named in each one's Check). |
| Secrets and credentials | Covered by S3a, S3b, S5a, S9a, S9b, Check: "the key's value reaches the agent only through its environment, never the config file (the canary approach of LAD-116)" (S3b); the key is a reference by name (D4). |
| Update and rollback | Covered by S1, S2, S5a, S6 (way back by `lado update`'s restore of `lado.db`) and S7, Check: "the kit docs say a kit with the field needs `dependencies.lado`, and `kits.warnings()` asks for it"; every LADO step is a minor; S7b is released by kit sdlc's own version. |
| Removal | Covered by S5a, Check: "removing a server a session uses: the session's next agent refuses loudly at start; removing the secret a server names: S3b's refusal before the start"; `lado uninstall` removes the settings with `LADO_HOME` (S5a); an empty table row is the CLI's default (S5c). |
| Platforms | Covered by S2, S4 (all four CLIs, smoke per provider), S3b (OpenCode/Kilo), S9a/S9b (Claude, Codex), S3a, Check: "in Docker, `localhost` that does not answer gives the loud hint `host.docker.internal:<port>`" (D5); macOS, Linux, WSL as today. |
| Observability | Covered by S1, Check: "`list_agents`, the API and the UI card show model, effort and source"; S3b's pre-start check, S2/S4's loud warnings, S5a's `lado doctor` check of saved servers; the model check's thresholds (plan, rules for every step). |
| Tests and what only a human can check | Covered by every step's Check (unit, integration with the fake agent, fake servers, smoke per provider in S2, S4, S9a, S9b); by hand: a real model server in S3b, S9a, S9b (D7; which server: open question Q2 of the plan); mockups at `design_ok` of the UI steps. |
| Documentation | Covered by every step's Check ("docs describe what was built": `docs/cli.md`, `docs/design/ui.md`, `docs/design/agents.md`, `docs/install.md` in S3b, the kit format in S7, CHANGELOG and the capability's spec in `openspec/specs/` per step, by the plan's rules for every step); BACKLOG's entry replaced in S1 (D8). |

## Branch strategy

Every step merges into `main` on its own and leaves the product working; unset means
today's behaviour, so no feature flag (D2). No epic branch. A release may come between
steps; while main is frozen for an RC, steps wait for the final.

## Epic tracker task

LAD-154 «Эпик: выбор модели и мощности для агентов» (label `component lado`); each step's
task is linked to it. Kit sdlc's marking is a task with `component kit-sdlc` (D6).

## Verdict

Ready to plan. Open on purpose: which model server the human checks steps 3 and 9 on, and
its address (D7), needed before step 3's check, not before the plan.
