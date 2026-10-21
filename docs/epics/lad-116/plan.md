# Plan: Projects in LADO (LAD-116)

## State
Phase: plan · Epic run: epic/epic-projects · Branch: base (`main`)
In work: none · Next: S1 · Open checks: none
Standing rules of the human:
- The concept `projects-concept` (2026-10-21) is the only source of decisions; where anything else differs, the concept wins.
- Every step merges into `main` on its own and leaves the product working (D2).
- Each phase task gets the label `component lado` and is linked to LAD-116; LAD-80 is not touched.
Last review: 2026-10-21, base at b687caf

## Steps

The concept's phases 0–5 map to S1–S7. One change against the concept's order: the
session in a project (concept phase 3) comes before variables and secrets (phase 2), so
that S5's check is end to end — two sessions of two projects, each agent seeing its own
value — instead of a store no agent reads yet (open question Q1).

### S1 — Docs rewrite and the rename to Workspace (M)
Status: planned
Check: the reviewer greps the tree (outside CHANGELOG, `docs/research/`, `docs/superpowers/`, `openspec/changes/archive/`, `docs/epics/`) for "projects folder", "Repositories folder", "repositories folder" and the old project model ("named set of repositories", the 2026-10-03 research where it no longer holds): no hit; `make lint`, `make test`, `make web`, the changed UI and container tests with their markers, `openspec validate --specs --strict` green; CI green.
Touches: `docs/design/projects.md` (new), AGENTS.md (Read more), `docs/design/modules.md`, `docs/design/ui.md`, ROADMAP.md, BACKLOG.md, README.md, `docs/install.md`, `docker/*` comments and messages, `openspec/specs/{repos-folder,container,session-clone}`, `src/lado/doctor.py` (the line), `src/lado/clone.py`/`runtime.py` (texts), `web/src/Launch.tsx`, tests that check these texts.
Notes: concept phase 0. Texts and docs only, no behaviour change; patch-level CHANGELOG line for the renamed labels. `docs/design/projects.md` describes the target model and says which parts are not built yet. Open question Q2 (the compose variable `LADO_PROJECTS`).

### S2 — The project in the core (M)
Status: planned
Check: integration tests: `lado project create/list/show/rename/delete` against a temp workspace and `LADO_HOME`; the folder `<workspace>/projects/<id>` made and removed; refusals (folder exists, `projects/` owned by the human, bad id); `lado doctor` shows the workspace, a foreign folder in `projects/` and a project whose folder is missing; schema migration tested from `previous_schema`.
Notes: concept phase 1, plus D3: one function gives the workspace (`LADO_REPOS`, else `~/workspace`), and the default clone parent of a session without a project moves from `~/lado` to it (CHANGELOG says existing sessions keep their folders). `delete` here covers a project that cannot have sessions yet: it shows uncommitted or unpushed work in the repositories of its folder, refuses without `--yes`; S3 extends it to sessions. Agents cannot run the project commands (refused from inside an agent). Minor bump (migration, new CLI).

### S3 — A session in a project (L)
Status: planned
Check: integration tests with the fake agent: `lado start --project <id> --repo <name>` starts in `<workspace>/projects/<id>/<name>`; the session's project is a reference in `lado.db`, shown by `lado ls` and the session header (API); a session from `start_session` gets the same project and repository; `lado start` of a folder under `projects/` without `--project` is refused with the hint naming the project; the project's repositories are listed from disk (git subfolders, branch, remote; a folder without git and an in-progress clone are not listed); `lado project delete` refuses while a session of the project runs and forgets the stopped ones.
Notes: concept phase 3 without adding repositories (S4). Repositories for the check are made by hand (`git init`/`git clone` into the project folder).

### S4 — Adding and removing a project's repositories (M)
Status: planned
Check: integration tests: a repository added by clone (into a temp folder, renamed at the end) and from scratch, both through LADO's existing clone and scratch paths, landing in the project folder; removing a repository refuses while its sessions run, shows unpushed work including workers' worktrees, needs `--yes`, removes its sessions and folder; nothing outside `projects/` is ever removed.
Touches: `clone.py`, `scratch.py`, `cli.py`, `runtime.py` (removal) — a parallel candidate with S5 (overlap only in `cli.py`).
Notes: the CLI shape (e.g. `lado project repo add/remove`) is the analyst's.

### S5 — Variables and secrets (L)
Status: planned
Check: integration: two sessions of two projects with the same variable get each its own value; layers login shell → `LADO_ENV_DIR` → project → LADO/CLI, the project winning over the outside folder; a kit key set only in the project counts as set; `lado project set/unset` (plain, `--secret` read hidden), name guards (secret-like names refused as plain, reserved names refused); secrets one file each, 700/600, atomic writes, read by the same function as `LADO_ENV_DIR`; refused from inside an agent; the canary test: a secret's value is in no API answer, feed, log, `lado log`, bug report or telemetry. Smoke per provider (CI): a kit's MCP server sees a project variable (D5).
Touches: `agent_env.py`, `kits.py`/`mcp_exec.py`, `state.py`, `cli.py`, `doctor.py` — a parallel candidate with S4.
Notes: concept phase 2. Minor bump (migration, new CLI). Open check after merge: one live run with models on the four CLIs before the release that ships S5 (Claude only with the human's yes) — goes to the release checklist at the review.

### S6 — UI: Projects section, variables, the Project way of New session (L)
Status: planned
Check: mockups approved at `design_ok`; UI e2e tests: create a project, set a plain variable and replace/delete a secret (its value never shown or returned), the security-boundary warning and "new values reach new agents" with the running sessions listed; New session's Project way: project, then the repository list (always shown) with "+ new repository" (clone or from scratch); all through the documented token API (`docs/design/ui.md`, OpenAPI).
Notes: concept phase 4. The Projects stub goes away here.

### S7 — UI: project page, removing a repository and a project (M)
Status: planned
Check: mockups approved; UI e2e: the project page lists repositories with branch and remote, sessions, variables; removing a repository and a project shows the unpushed work (incl. workers' worktrees) and asks for the id typed; refused while sessions run.
Notes: concept phase 5.

## Open questions

- **Q1. S3 (session in a project) before S5 (variables)?** Recommended: yes. Each step still stands on its own; S5's check becomes end to end; a release between them ships projects with sessions but no variables, which is harmless. The concept's order would ship a variable store no agent reads.
- **Q2. The compose variable `LADO_PROJECTS`** (`docker/compose.yaml`: "set LADO_PROJECTS to your projects folder") sits next to the new `projects/` and means the workspace. Recommended: S1 adds `LADO_WORKSPACE` as the documented name and keeps `LADO_PROJECTS` working as the old name, so no installed `.env` breaks; `LADO_REPOS` inside the container is unchanged (concept). Alternative: keep `LADO_PROJECTS` and only change its message.

## Later

- Database extras for repositories (order, description, role, address to re-clone; "missing, clone again?") — concept option C — after this epic, when multi-repo sessions need them.
- Sessions and tasks over several repositories; the "all repositories" item of the list — concept "Не сейчас".
- Tracker integration and shared kit settings per project — concept "Не сейчас".
- Project artifacts that outlive sessions — concept "Не сейчас" (BACKLOG "Artifacts end with their session").
- Isolation between projects; per-project outside secrets (`/run/secrets/projects/<id>/NAME`) for the LADO manager — concept, "Архитектурные рамки".
- Managing workspace folders outside projects — a BACKLOG entry made in S1.
