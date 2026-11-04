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

Scope cut at S3d's review (2026-11-04, the human asked for it; D31, step_ok gate #266):
this epic delivers statement steps 1–4 and 9 (the agent's model visible, one model per
session, models and model servers in Settings → Models, agents of all four CLIs on a model
server, effort) and ships in 0.45.0; steps 5–8 (the power tables, power on roles, flow steps
and the supervisor's spawn) go to a second epic. Unset still means today's behaviour.
