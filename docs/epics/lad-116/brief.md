# Brief: Projects in LADO (LAD-116)

## The human's statement

> epic: **Projects в LADO: проект — это папка в workspace и переменные окружения.**
>
> Сейчас все сессии одного LADO получают одно и то же окружение. Двум сессиям, которые
> работают для разных клиентов, нужны разные ключи (`YOUGILE_API_KEY`, `GH_TOKEN`). Проект
> решает эту задачу и закладывает основу для будущей работы над несколькими репозиториями.

Sources, attached by the human on 2026-10-21 (session artifacts, in Russian):
- `projects-concept` — the final concept agreed with the human on 2026-10-21, **the only
  source of decisions**; where the epic brief and the concept differ, the concept wins.
- `projects-epic-brief` — the statement: the human's decisions, the mandatory Phase 0
  (a full rewrite of the docs and the rename to Workspace), a draft of phases 0–5, the
  board (LAD-7/8/9 closed as replaced, LAD-80 left alone, phase tasks created by the epic
  on the human's yes, label `component lado`).

## Goal and "done"

A project is an immutable id, an editable title, the folder `<workspace>/projects/<id>`
(derived from the id, made by LADO) and environment variables: plain ones in `lado.db`,
secrets one file each in `<LADO_HOME>/projects/<id>/secrets/` (the `/run/secrets` form,
write-only). A session runs either without a project (as today, anywhere but
`projects/`) or in a project and one of its repositories (`lado start --project --repo`,
the fourth way of the New session window); the whole session gets the project's
variables (layers: login shell → outside (Docker) → project → LADO and the CLI).
Repositories are the project folder's git subfolders, read from disk.

Done when all of the concept's phases 0–5 are merged into `main`, each on its own and
leaving the product working:
- the docs describe the new model only (`docs/design/projects.md`, ROADMAP, BACKLOG,
  `docs/design/ui.md`), "projects folder"/"Repositories folder" renamed to Workspace;
- `lado project list/create/show/rename/delete/set/unset`, `lado start --project --repo`,
  `lado doctor`'s checks, `lado ls` and the session header show the project;
- two sessions of two projects run with different values of the same variable on all
  four CLIs, with and without Docker, kit key checks count project variables;
- the canary test proves a secret's value reaches no API, feed, log, `lado log`, bug
  report or telemetry;
- the UI has the Projects section, the project page, variables, the Project way of New
  session, and repository/project removal that shows unpushed work, through a documented
  token API.

## Readiness checklist

| Topic | Verdict |
|---|---|
| Goal and "done" | Covered: concept "Зачем", above. |
| Users and how they use it | Covered: the human working for several clients; the concept's Session and UI sections; a future LADO manager through the API. |
| Scope and what is out | Covered: concept "Не сейчас" (no global or per-session variables, no profiles/LAD-80, no multi-repo sessions, no tracker or kit config per project, no project artifacts, no isolation, no per-project outside secrets, no workspace folder management outside projects — a BACKLOG entry). |
| Data and migrations | Covered: a schema migration (projects, plain variables, the session's project reference) in phase 1/2/3; secrets on disk; a rollback by `lado update` restores `lado.db` when its schema moved; the older LADO does not know projects, project folders stay in `<workspace>/projects/` and secrets in `LADO_HOME/projects/`; after a later update on the restored database `lado doctor` shows those folders as foreign (S2 checks foreign folders). |
| Secrets and credentials | Covered: concept "Переменные окружения и секреты", "Где хранятся"; the canary test; name guards; agents cannot change projects or variables. Codex hands MCP servers the variables named in the agent's environment (`providers/codex.py`), so project variables reach them; the per-provider smoke test proves it (D5). |
| Update and rollback | Covered: minor version (migration, new CLI); `lado update` backs up and restores `lado.db`. Without `LADO_REPOS` the default clone parent moves from `~/lado` to `~/workspace` (D3): existing sessions keep their folders; CHANGELOG says so. |
| Removal | Covered: project/repository deletion per the concept (refuse while running, show unpushed work incl. workers' worktrees, confirm); `lado uninstall` deletes `LADO_HOME` with the secrets and never touches the workspace (today's behaviour, stated in `docs/design/projects.md` by S1). |
| Platforms | Covered: neutral core, all four CLIs, with and without Docker; macOS, Linux, WSL (native Windows is refused today). |
| Observability | Covered: `lado doctor` (workspace, `projects/` owned by the human, foreign folders, missing project folders, unusable secret files by name); UI says new values reach new agents only. |
| Tests and what only a human can check | Covered: unit + integration with the fake agent per phase; a smoke test per provider that a kit's MCP server sees a project variable (D5, S5a); one live check with models before the release that ships S5a (Claude only with the human's yes); UI e2e and mockups for phases 4–5 approved by the human. |
| Documentation | Covered: Phase 0 is a full rewrite; each later phase keeps `docs/cli.md`, `docs/design/*`, the specs and CHANGELOG true; the docs say plainly that projects are not isolated and that LADO is not a store, and that a volume backup holds secrets. |

## Branch strategy

Every step merges into `main` on its own and leaves the product working (D2). No epic
branch. The UI's Projects section stays a stub until phase 4; no feature flag. A release
may happen between phases (D4).

## Epic tracker task

LAD-116 «Эпик: Projects в LADO — проект = папка в workspace и переменные окружения»
(created 2026-10-21 on the human's yes, label `component lado`); each phase's task is
linked to it.

## Verdict

Ready to plan.
