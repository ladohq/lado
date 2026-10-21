# Plan: Projects in LADO (LAD-116)

## State
Phase: steps · Epic run: epic/epic-projects · Branch: base (`main`)
In work: none · Next: S2 · Open checks: none
Standing rules of the human:
- The concept `projects-concept` (2026-10-21) is the only source of decisions; where anything else differs, the concept wins.
- Every step merges into `main` on its own and leaves the product working (D2).
- Each phase task gets the label `component lado` and is linked to LAD-116; LAD-80 is not touched.
- Questions to the human go as question cards (`ask_human`) with choices, not only as text messages (the human's remark #521, 2026-10-21).
Last review: 2026-10-21 (after S1b), base at 0fadd64

## Steps

The concept's phases 0–5 map to S1–S7 (phase 2 split into S5a and S5b). One change against
the concept's order, for the human's explicit yes (Q1): the session in a project (concept
phase 3, S3) comes before variables and secrets (phase 2, S5a/S5b), so S5a's check is end to
end. No two steps run at once: S3–S5b all change `runtime.py` and `state.py`.

### S1 — Docs rewrite and the rename to Workspace (M)
Status: done (LAD-117, PR https://github.com/ladohq/lado/pull/126)
Check:
- `grep -rniE "projects folders?|repositories folders?"` (the old names only; "project folder" and "repository folder" are the new model's terms) over the tree, outside CHANGELOG.md, `docs/research/`, `docs/superpowers/`, `openspec/changes/archive/`, `docs/epics/`: no hit (the reviewer).
- These places are rewritten to the new model or removed, checked one by one: ROADMAP.md "Later → Projects" (lines 139–148 at b687caf: "a project is a named configuration (its repos, tracker filters, default kit and flow)", "deleting a project removes its clones too"); BACKLOG.md "Flows cannot work on another repository" and "Artifacts end with their session"; the Projects stub, `repos` in the session header, "Projects can add theirs" and the repositories-folder hint in `docs/design/ui.md`.
- BACKLOG.md has the entry "managing workspace folders outside projects".
- `make lint`, `make test`, `make web`, the changed UI tests with `-m ui`, `openspec validate --specs --strict`, CI green.
- The human reads `docs/design/projects.md` against the concept at the merge gate.
Result: PR #126 merged 2026-10-21 (6c2336e), LAD-117 Done; the change `workspace-name-and-projects-docs` archived; CI 23/23; `make test` 3614 passed (developer); one merge_ok rejection (F1, leftover "projects" meaning the workspace). CHANGELOG line under `## 0.42.1 (unreleased)`.
Notes: concept phase 0. Texts only: no name an installation sees changes (environment variables, paths, API keys), so no behaviour changes; one patch-level CHANGELOG line for the renamed labels. Compose's `LADO_PROJECTS` keeps its name here; only its message says "workspace" (whether a new name comes is Q2, in S2). `docs/design/projects.md` describes the target model, says which parts are not built yet, and says plainly: projects of one LADO are not isolated; LADO is not a store; a volume backup holds the secrets; `lado uninstall` deletes `LADO_HOME` with the secrets and never touches the workspace.

### S1b — Warnings and refusals in the New session window stand out (S)
Status: done (LAD-120, PR https://github.com/ladohq/lado/pull/128)
Check: mockup approved at `design_ok`; UI e2e: a warning (e.g. "Outside the workspace" in the container) and a refusal (a folder that cannot be used) render in their own styles, distinct from the grey hints, and the Start button is disabled while a refusal shows; `docs/design/ui.md` names the three levels; `make web`, the changed UI tests with `-m ui`, CI green.
Result: PR #128 merged 2026-10-21 (0fadd64), LAD-120 Done; change `launch-note-levels` archived (new capability `launch-notes`); tokens `--warn`, `--warn-ground`, `--danger-ground` (contrast ≥ 5.4:1); the kit list's load error shown as a warning (#587); on a 390px phone Start goes below the edge with a warning box, accepted (#594). Found on the way: the Resume window's provider refusal does not disable Resume; `make test` leaves a `sleep 60` (BACKLOG P2).
Notes: added on the human's word (#525, 2026-10-21): today every note under a field is `field-note`, 12px grey; a warning differs from a hint only by its text colour, a refusal by a thin left bar, so users skip them. Three levels, only the top two change: hints stay small and grey; a warning becomes a box with a light warm background, an icon and 13px text in the normal colour; a refusal that blocks the start becomes the same box in the error colour. No new elements; only the look of the existing `warn` and `bad` notes (`web/src/styles.css`, `web/src/Launch.tsx`). Before S3, whose refusal "this folder belongs to project <title>: start the session in the project" must be seen. After S1 merges (both touch `Launch.tsx`). Patch.

### S2 — The project in the core and the default workspace (M)
Status: planned
Check:
- Integration tests: `lado project create/list/show/rename/delete` against a temp workspace and `LADO_HOME`; the folder `<workspace>/projects/<id>` made and removed; refusals: the folder exists, `projects/` is the human's own folder, a bad id; refused from inside an agent (`LADO_SESSION`/`LADO_AGENT` set).
- `lado doctor`: the workspace line with and without `LADO_REPOS` (incl. a default `~/workspace` not made yet), a foreign folder in `projects/`, a project whose folder is missing, `projects/` owned by the human.
- D3: without `LADO_REPOS` a clone with no folder given lands in `~/workspace/<repo>` (unit and `test_server_launch`), and the New session window's Where: no hints while `~/workspace` is not made yet, hints from it once it exists.
- The schema migration from `tests/agent_helpers.previous_schema`; an `lado update` rollback test is not needed beyond the existing one (it restores `lado.db`; the folders stay, see brief "Data and migrations").
Notes: concept phase 1, plus D3. The id: `[a-z0-9][a-z0-9-]*`, 1–40 characters, lowercase only (case-insensitive file systems). One function gives the workspace (`LADO_REPOS`, else `~/workspace`) for the clone default, the server, `lado doctor` and projects. Changes the specs `repos-folder` (the requirement "unset: no folder, no doctor line, no Where hints" becomes "unset: `~/workspace`") and `session-clone` (default `~/lado/<repo>` becomes `<workspace>/<repo>`). Making `~/workspace`: Q3. Leftovers of S1 (`openspec/changes/archive/2026-10-21-workspace-name-and-projects-docs`, proposal "Out of scope"; S1 review): the Where placeholder `~/projects/app` used without a workspace becomes the `~/workspace` form; the code names `repos_folder`, `check_repos_folder`, `OUTSIDE_REPOS`, `ReposFolder`, `DEFAULT_PARENT` and the capability `repos-folder` are reshaped by the one workspace function (renaming them is S2's call); "the projects' toolchains" (meaning the code in general) in `docker/Dockerfile:46,65`, `docs/install.md:241`, `docs/design/modules.md:983` and the docstring of `tests/container/test_toolchains.py` say "the repositories' toolchains". CHANGELOG: S1's line sits under `## 0.42.1 (unreleased)`; S2's minor bump renames that heading to `## 0.43.0 (unreleased)` unless 0.42.1 is released first. CHANGELOG: existing sessions keep their folders. Compose's `LADO_WORKSPACE`, if Q2 says so, is its own small step S2b, not part of S2. `delete` covers a project that has no sessions yet: it shows uncommitted or unpushed work in the repositories of its folder and refuses without `--yes`; S3 extends it to sessions, S5b to secrets. Minor bump.

### S2b — Compose's `LADO_WORKSPACE` (S)
Status: planned
Check: `tests/test_docker.py` and the container tests (CI): `LADO_WORKSPACE` names the host folder; an installed `.env` with only `LADO_PROJECTS` still works; with neither, compose names `LADO_WORKSPACE` in its error; `docs/install.md`, `docs/release.md`, `docs/testing.md`, `openspec/specs/container` name `LADO_WORKSPACE` first and the old name as still accepted.
Notes: independent of S2's core; `LADO_REPOS` inside the container keeps its name (concept). Past a compose version that cannot nest interpolation defaults, stop and ask the human.

### S3 — A session in a project (L)
Status: planned
Check:
- Integration tests with the fake agent: `lado start --project <id> --repo <name>` starts in `<workspace>/projects/<id>/<name>`; the session's project is a reference in `lado.db`, shown by `lado ls` and in the session's API; a session from `start_session` gets the same project and repository.
- A session without a project under `projects/` is refused on every path: `lado start <folder>`, `lado start <git-url>` with a target there, `lado start --new` there, the server's launch API (folder, clone, from scratch), and `start_session` from a session without a project; each refusal names the project and offers the session in it.
- The Where hints of New session never offer `projects/` (server test and `tests/ui`).
- The session header in the UI shows the project (mockup at `design_ok`, `docs/design/ui.md`, UI e2e).
- The project's repositories are listed from disk: git subfolders with branch and remote; a folder without git and an unfinished clone are not listed.
- `lado project delete` refuses while a session of the project runs, and forgets the stopped ones.
Notes: concept phase 3 without adding repositories (S4). Repositories for the check are made by hand (`git init`/`git clone` into the project folder).

### S4 — Adding and removing a project's repositories (M)
Status: planned
Check: integration tests: a repository added by clone (into a temporary folder, renamed at the end) and from scratch, through LADO's existing clone and scratch paths, landing in the project folder; removing a repository refuses while its sessions run, shows unpushed work including workers' worktrees, needs `--yes`, forgets its sessions and removes its folder; nothing outside `projects/` is ever removed.
Notes: the CLI shape (e.g. `lado project repo add/remove`) is the analyst's.

### S5a — Plain project variables reach the whole session (M)
Status: planned
Check:
- Integration with the fake agent: two sessions of two projects with the same variable get each its own value in the supervisor, a worker, a flow run's worker and a session from `start_session`; layers login shell → `LADO_ENV_DIR` → project → LADO/CLI, the project winning over the outside folder; a name LADO or the CLI sets keeps LADO's value, with the warning as for the outside folder.
- Kit keys: `kits.ResolvedAgent.mcp_servers` checks each `${VAR}` of a kit's MCP server against the agent's environment before the agent starts (today's refusal "… environment variable X is not set"); a key set only in the project passes it and reaches the server through `mcp_exec`, the same key in a session without a project is refused.
- `lado project set/unset` (plain); a secret-like name (`*TOKEN*`, `*KEY*`, `*SECRET*`, `*PASSWORD*`) refused as plain; reserved names (`LADO_*`, `PATH`, `HOME`, `CLAUDE_CONFIG_DIR` and the like, from one list) refused; refused from inside an agent.
- Smoke per provider (CI, D5): a test MCP server of a kit writes whether it sees a project variable to a file the test reads (the current smoke has no such server: S5a adds it).
Notes: concept phase 2, plain half. Minor bump (migration, new CLI). Open check after merge: one live run with models on the four CLIs before the release that ships S5a (Claude only with the human's yes) — goes to the release checklist at the review.

### S5b — Project secrets (M)
Status: planned
Check:
- `lado project set <id> NAME --secret` reads the value hidden; one file per secret in `<LADO_HOME>/projects/<id>/secrets/`, 700/600, written atomically; read by the same function as `LADO_ENV_DIR` with its limits; a secret reaches the agents as in S5a; replace and delete, never read back.
- `lado doctor` names an unusable secret file of a project by name, never by content.
- `lado project delete` removes `<LADO_HOME>/projects/<id>/`; delete then create with the same id: no secrets.
- The canary test: a secret's value is in no API answer, UI feed, log, LADO's error journal, `lado log`, bug report or telemetry.
Notes: concept phase 2, secrets half.

### S6 — UI: Projects section, variables, the Project way of New session (L)
Status: planned
Check: mockups approved at `design_ok`; UI e2e: the project list with title, number of repositories and of running sessions; create a project; set a plain variable; replace and delete a secret (its value never shown or returned); the mark of the outside value a variable overrides (`LADO_ENV_DIR` with the same name); the security-boundary warning and "new values reach new agents" with the running sessions listed; New session's Project way: project, then the repository list (always shown) with "+ new repository" (clone or from scratch). All through the documented token API (`docs/design/ui.md`, OpenAPI). The canary test of S5b extended to the new endpoints and the feed.
Notes: concept phase 4. The Projects stub goes away here.

### S7 — UI: project page, removing a repository and a project (M)
Status: planned
Check: mockups approved; UI e2e: the project page lists repositories with branch and remote, sessions, variables; renaming the title; removing a repository and a project shows the unpushed work (incl. workers' worktrees) and asks for the id typed; refused while sessions run.
Notes: concept phase 5.

## Open questions

None open. Decided at `plan_ok` (gate #33, 2026-10-21), all as recommended: Q1 — S3 before S5a/S5b; Q2 — (a), step S2b adds `LADO_WORKSPACE`, `LADO_PROJECTS` kept working; Q3 — LADO makes `~/workspace` on first need, `lado doctor` says it is not made yet, Where hints once it exists; Q4 — S5 split into S5a and S5b (`decisions.md`).

## Later

- LAD-121 `make test` red with every test passed (a `sleep 60` left) — outside the epic, born in S1b; run as its own task (run task/lad-121) alongside S2 on the human's word at gate #44.
- LAD-122 the Resume window's provider refusal does not disable Resume — outside the epic, born in S1b; any time.

- Database extras for repositories (order, description, role, address to re-clone; "missing, clone again?") — concept option C — after this epic, when multi-repo sessions need them.
- Sessions and tasks over several repositories; the "all repositories" item of the list — concept "Не сейчас".
- Tracker integration and shared kit settings per project — concept "Не сейчас".
- Project artifacts that outlive sessions — concept "Не сейчас" (BACKLOG "Artifacts end with their session").
- Isolation between projects; per-project outside secrets (`/run/secrets/projects/<id>/NAME`) for the LADO manager — concept, "Архитектурные рамки".
- Managing workspace folders outside projects — a BACKLOG entry made in S1.
