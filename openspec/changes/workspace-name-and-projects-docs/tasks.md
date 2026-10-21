## 1. The concept as a design document

- [ ] 1.1 `docs/design/projects.md`, in English, from the session artifact
  `/projects-concept-fc4e5ae7.md` read whole (the only source of decisions; where anything
  else differs, the concept wins), in the concept's order: Why; Words (workspace, project,
  project folder `<workspace>/projects/<id>`, repository folder: a git subfolder of a
  project folder, never the project folder itself) with the concept's tree; The project;
  How LADO knows a project's repositories; The session; Variables and secrets (the layers
  `login shell → outside (Docker: /run/secrets) → project variables → LADO and the agent
  CLI`); Where a project's data lives; The security boundary; Deleting; The UI; The
  architectural frame (with how the LADO manager hands variables to a project); Not now;
  How it is built (the steps S1–S7 of `docs/epics/lad-116/plan.md`, linked). A note at the
  top says what is built: only the workspace's name (S1); everything else is steps S2–S7,
  each section marked "not built yet" where it describes one; until S2 the workspace is
  `LADO_REPOS` alone, with no `~/workspace` default. It says in plain sentences: the
  projects of one LADO are not isolated, and clients that must not mix need a separate
  LADO; LADO is not a store; a backup of LADO's home volume holds the secrets;
  `lado uninstall` deletes `LADO_HOME` with the secrets (unless `--keep-data`) and never
  touches the workspace; in Docker, `docker volume rm` of the home volume deletes them.
  Check: the human reads it against the concept at `merge_ok` (AC-1).
- [ ] 1.2 AGENTS.md, Read more: one line for `docs/design/projects.md` (the file stays
  within 200 lines: `uv run pytest tests/test_agents_md.py -n0`). `docs/design/modules.md`:
  where it describes `LADO_REPOS` (`clone.repos_folder`, `doctor.check_repos_folder`), the
  workspace's name and a link to `docs/design/projects.md`.

## 2. ROADMAP, BACKLOG and the UI's design

- [ ] 2.1 ROADMAP.md, "Later (after stage 7)" → Projects (keep the item in that section:
  the UI's placeholder links to its anchor `#later-after-stage-7`): what a project is
  (a folder `<workspace>/projects/<id>` and its environment variables, so sessions for
  different clients get different keys), links to `docs/design/projects.md` and the epic's
  plan (LAD-116), the steps S1–S7 as checkbox sub-items (S1 checked by this change).
  Removed: "a named configuration (its repos, tracker filters, default kit and flow)" and
  "deleting a project removes its clones too, or says what it leaves". Kept lessons of
  2026-10-03: a session refers to its project by a real reference, not a name found in its
  path; the CLI can do what the UI does (`lado start --project`); LADO itself makes each
  worker's worktree. Deleting in the concept's words: a project's folder goes after LADO
  shows the unpushed work; nothing outside `projects/` is ever deleted. Sessions over
  several repositories and the tracker tie-in stay as the concept's "Not now" (AC-3).
- [ ] 2.2 BACKLOG.md: "Flows cannot work on another repository": `Why here:` points at
  sessions over several repositories of a project (`docs/design/projects.md`, Not now),
  not at "Projects" as a configuration of repositories; the body stays. "Artifacts end
  with their session": `Why here:` and `Wanted:` name a project's artifacts that outlive
  sessions (the same "Not now"). New entry in P3, by the file's template (title, `Size:`
  and `Why here:` lines, body, `Wanted:`, `Found: 2026-10-21, design of LAD-117`):
  "Managing workspace folders outside projects": LADO manages only `projects/` of the
  workspace; the human's other folders there (sessions without a project, clones) are
  cleaned on the host; wanted: listing and removing them from LADO, if ever (AC-3).
- [ ] 2.3 `docs/design/ui.md`: the Placeholders rule's "Projects is ROADMAP's Later"
  stays true (the plan item is rewritten); the Projects placeholder's sentence is the new
  one of 3.4. `repos` in the session head: one item, the session's repository; a session
  in a project (step S3) shows its project there, its look decided with a mockup at S3;
  the list form of several repositories only with sessions over several repositories
  (concept, Not now). New session window: "so Projects can add theirs" → a session in a
  project is the window's fourth way (step S6, `docs/design/projects.md`). The Where hint:
  "With a workspace (`LADO_REPOS`, which LADO's image sets to the workspace mounted at the
  host's path …)", the row **Workspace:**, the warning `⚠ Outside the workspace (<folder>):
  …`; the decision lines (LAD-63, LAD-83) stay, with "renamed LAD-117" added (AC-3).

## 3. The rename in the code and the Docker files

- [ ] 3.1 `src/lado/doctor.py`: the check's name `Workspace` (was `Repositories
  folder`); its docstring "the workspace". `src/lado/runtime.py`: `OUTSIDE_REPOS` reads
  `Outside the workspace ({folder}): this folder is only in the container, your computer
  does not see it or the agents' work in it`; the docstring of `outside_repos` "the
  workspace". `src/lado/clone.py`: `default_parent`'s docstring "the workspace, else
  ~/lado"; `repos_folder`'s too if it says "repositories". Tests: `tests/test_doctor.py`,
  `tests/test_runtime.py` expected texts only. `make test` (AC-2, AC-4).
- [ ] 3.2 `src/lado/server/models.py`: `ReposFolder`'s docstring "The human's workspace
  (LADO_REPOS, clone.repos_folder): the New session window's start folder, or None.";
  `make web-types`, commit `web/openapi.json` and `web/src/api.gen.ts`. Comments that say
  "outside LADO_REPOS" may stay (a variable's name). `tests/test_server_launch.py`: its
  section comment.
- [ ] 3.3 `web/src/Launch.tsx`: the row `Workspace:`; comments "the workspace".
  `web/src/Launch.test.tsx`: expected texts, test names and comments ("Workspace:",
  "Outside the workspace"); no test's steps or assertions change but the text. `make web`
  (AC-2, AC-4).
- [ ] 3.4 `web/src/pages.tsx`: the Projects placeholder's sentence `Each project is a
  folder in your workspace with its repositories and its own environment variables, so
  sessions for different clients get different keys.`; its link stays `PLANS.projects`
  (`web/src/paths.ts`: label "Roadmap, Later: Projects", same anchor; `App.test.tsx`
  unchanged). `make web`.
- [ ] 3.5 `tests/ui/test_launch.py`: the row's and the warning's texts, docstrings.
  `uv run pytest -m ui tests/ui/test_launch.py` (AC-4).
- [ ] 3.6 `docker/compose.yaml`: the refusal `set LADO_PROJECTS to your workspace folder`
  (all three), the header's example `LADO_PROJECTS=/Users/me/workspace`, the volume's
  comment "The human's workspace at the host's own path"; `docker/profile.sh`,
  `docker/mise.toml`: "the workspace" in the comments. `tests/test_docker.py`: the expected
  refusal. `tests/container/*` (`conftest.py`, `test_image.py`, `test_projects.py`,
  `test_access.py`, `test_toolchains.py`): the doctor line `Workspace:` and the words of
  docstrings and comments; CI runs them (AC-2, AC-4).

## 4. The rename in the documents and the specs

- [ ] 4.1 README.md and `docs/install.md`: "your workspace" (the table row, the `.env`
  examples `LADO_PROJECTS=/Users/ann/workspace   # your workspace folder, a full path` and
  README's `/Users/you/workspace`, Launch's Where, the uninstall line, `lado doctor`, the
  troubleshooting lines; "Projects folders of the same owner" → "Workspaces of the same
  owner"). `docs/release.md` ("a test folder of projects" → "a test workspace") and
  `docs/testing.md` ("the projects at the host's path" → "the workspace at the host's
  path") where they mean the folder. Any other `docs/design/*` hit (AC-2).
- [ ] 4.2 The specs `repos-folder`, `container` and `session-clone` change by this
  change's delta at archive; `openspec validate workspace-name-and-projects-docs --strict`
  and `openspec validate --specs --strict` (AC-2).
- [ ] 4.3 CHANGELOG.md: a heading `## 0.42.1 (unreleased)` when there is none, and under
  `### Improved` one line: the folder LADO keeps code in is called the workspace in
  `lado doctor`, the New session window, compose's message and the guide; nothing to
  change in an installation.

## 5. The checks

- [ ] 5.1 `grep -rniE "projects folders?|repositories folders?"` over the tree without
  `.git`, `node_modules`, `.venv`, `src/lado/server/static`, CHANGELOG.md,
  `docs/research/`, `docs/superpowers/`, `openspec/changes/archive/`, `docs/epics/`: hits
  only in this open change's delta (its RENAMED `FROM` and REMOVED lines, which go to the
  archive at merge); after the archive none (AC-2).
- [ ] 5.2 `make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_launch.py`,
  `openspec validate --specs --strict`; CI green, the container tests included (AC-4).
- [ ] 5.3 Screenshots of the New session window's Workspace row and of the warning (from
  the UI test's shots), as run artifacts in `build-report`.
