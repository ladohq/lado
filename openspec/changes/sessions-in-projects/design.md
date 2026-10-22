## Context

S2 (`projects-in-core`) built `lado.projects`: the workspace, the project's id, title and
record (table `projects`, schema 32), its derived folder `<workspace>/projects/<id>`,
`owned_by_human()` (the rule of `projects/` being the human's own folder), the unpushed
scan and `delete`. A session (`state.Session`, table `sessions`) has a `repo` (the real
path of its repository's root) and no project.

Sessions start through one core function, `runtime.start_session(path, name, …,
resume)`: `lado start <folder>` and its clone (`cli._start_clone`) and fresh start
(`cli._start_new`) paths, the server's `POST /api/sessions` (folder and scratch) and
`POST /api/sessions/{name}/resume`, the container's resume at start
(`runtime.resume_at_start`) and the supervisor's `start_session` tool
(`runtime.start_approved_session`, which passes the parent's `repo`, kits, provider and
settings). Clones and fresh starts check their target first (`clone.check_target`,
`scratch.check_target`), before anything is cloned or made; the server's folder check is
`server/launch.folder_info` over `runtime.check_repo`. The window's Where hints are the
`subfolders` of `folder_info`, its recent folders `launch.recent_folders`.

Model and decisions: `docs/design/projects.md`, the concept `projects-concept`, the
epic's plan (S3) and the brief of gate #62. The human's answers of this step: questions
#802–#810 (session name, `--repo` always, links, sessions from before S3, the head).

## Goals / Non-Goals

Goals: the session's project as a reference; `lado start --project --repo`; inheritance
and resume; the refusal on every start path; repositories from the disk in `lado project
show` and the project's API; `lado ls`, the session's API and head; delete with sessions.

Non-goals: adding repositories (S4), variables (S5a/S5b), the UI of projects (S6/S7).

## Options

For the session's project:
1. **A column `sessions.project` referring to `projects(id)`** (chosen). One source of
   truth, set once at the start; the foreign key keeps a project with sessions from being
   deleted by mistake. Cost: one migration (one column), within the brief.
2. Derive it from `sessions.repo` under `<workspace>/projects/<id>/`. No migration, but it
   guesses from the path (the concept forbids it), breaks when the workspace changes, and
   cannot tell a session started there before S3.

For the refusal inside `projects/`:
1. **One core function `projects.refusal(path)`, asked by `start_session`, the clone's
   and the fresh start's target checks, and the server's folder check** (chosen). Every
   path refuses with the same text; S4 and S6 reuse it. Cost: `clone` and `scratch` get one
   more target state.
2. A check in each caller (CLI, server). Shorter now, but six places to keep alike and
   `start_session` from an agent would stay open.

For the repositories:
1. **Read from the disk each time** (`projects.repositories(id)`, chosen; the concept).
2. A table of repositories: a second truth that drifts from the disk; the concept keeps
   additions for later, never the existence.

## Decisions

**D1. The column.** `SESSIONS_PROJECT = "ALTER TABLE sessions ADD COLUMN project TEXT
REFERENCES projects(id)"`, appended to `SCHEMA` and `MIGRATIONS[32] = [SESSIONS_PROJECT]`
(the step from 32), `SCHEMA_VERSION = 33`; `tests/agent_helpers.schema_before` undoes it
(drop the column; SQLite ≥ 3.35, as for earlier steps, or rebuild as they do).
`state.Session.project: str | None = None`; `add_session` writes it, `_session` reads it,
`resume_session` and `_set_settings` never change it. `state.project_sessions(id) ->
list[Session]`. No ON DELETE: with `PRAGMA foreign_keys = ON` a project that still has
sessions cannot lose its record; delete forgets them first (D9). Existing rows get NULL:
the sessions from before S3 keep no project (#808).

**D2. Repositories.** `projects.Repository(name, path, branch, remote)`;
`projects.repositories(id) -> list[Repository]` sorted by name: each entry of
`folder(id)` whose name does not start with `.`, that is a directory and not a symbolic
link (`#806`), and whose `git rev-parse --show-toplevel` is the entry's own real path (so
a plain folder inside a project folder that is itself a repository is not one, and the
project folder never is). Branch: `runtime.branch` (None on a detached HEAD); remote:
`runtime.remote` through `runtime.public_remote`. A missing project folder gives `[]`.
git runs as `projects._git` does (no prompt, English, a timeout); an entry git cannot
read is left out (it is no repository LADO can start in).

**D3. `--project`/`--repo` in the CLI.** `lado start --project ID --repo NAME`: both or
neither (usage error, exit 2: `--project needs --repo NAME` / `--repo needs --project
ID`); with `--project` no positional folder, no git URL, no `--new`, no `--branch`, no
second folder (exit 2: `--project takes no folder, git URL or --new: the folder is the
project's repository`). Not refused inside an agent: starting sessions is not changing
projects. The CLI calls `runtime.start_session(None, name, …, project=ID, repo=NAME)`.

**D4. `start_session(path, …, project=None, repo=None)`.** With `project`:
`projects.get(project)` (unknown: `unknown project "<id>"`), then the repository by
`repo` among `projects.repositories(project)`; not found: `project <id> has no repository
<name>; its repositories: <a, b>` or `project <id> has no repositories yet: a repository
is a git folder in <folder>` (a link, hidden or non-git entry of that name is not
special-cased: it is not a repository). `path` is then the repository's path, checked by
`check_repo` as any (no commits: its hint). The default name is
`slug(f"{project}-{repo}")` (#802). For an existing session of that name: same project →
resume; another project or none → refused `session "<name>" is in project <p>` / `is not
in a project; a session's project never changes: give another name with --name`. A new
session stores `project`. Without `project`, a resume keeps `old.project`; a new session
has none and goes through D5.

**D5. The refusal.** `projects.refusal(path) -> runtime.FolderProblem | None`, kind
`in_project` (added to `runtime.FolderProblemKind`), by real paths
(`os.path.realpath`), when `projects/` is LADO's (`projects_folder()` is a folder and
`owned_by_human()` is None) and the path is inside it:
- below a project's folder (`<ws>/projects/<id>/<name>/…`, `<id>` in `lado.db`): text
  `<path> belongs to the project <title or id>: start a session in the project`, hint
  `Start a session in the project:` / `lado start --project <id> --repo <name>`;
- the project's folder itself: the same text, hint `See the project's repositories:` /
  `lado project show <id>`;
- `projects/` itself, or a folder in it that is no project's: text `<path> is in
  <ws>/projects, which holds LADO's projects only: start a session in a project, or move
  the folder out of projects/`, hint `See the projects:` / `lado project list`.
`<path>` is the path as given (expanded). When `projects/` is the human's own folder (no
project's folder in it, S2), nothing is refused: LADO does not own it yet.

**D6. Where the refusal is asked.**
- `start_session` without `project`: `refusal(path)` first; when `check_repo` fails and a
  refusal holds, the refusal is raised instead (so `lado start` on a non-git folder in a
  project says the project, not `git init`); after the session's name is known, a
  refusal holds and no session of that name exists → raised. A resume is never refused
  by it (#808). `start_approved_session` from a session without a project into a folder in
  `projects/` is thus refused by `start_session` itself.
- `clone.check_target` and `scratch.check_target`: a new state `in_project`, checked
  first, with the refusal's text and a `hint`; not in `CAN_CLONE`/`CAN_START`, so the CLI,
  `POST /api/clones` and `scratch.make` refuse before cloning or making anything. The CLI
  prints `lado: <text>` and `lado: <hint line>`.
- `launch.folder_info`: `refusal(path)` before `check_repo`: `ok: false`,
  `problem_kind: "in_project"`, `hint`, `scratch: false`, no subfolders.
- `CloneTarget` and `ScratchTarget` get `hint: HintInfo | None` (null but for
  `in_project`); the window shows it as the folder check's hint (`FolderHint`).

**D7. Inheritance.** `start_approved_session` passes `project=sess.project` and, when it
is set, `repo=Path(sess.repo).name` and `path=None`, so the new session is checked as any
session in the project (its repository must still be listed). `mcp_server.py`,
`hooks.py` and `providers/` do not change.

**D8. Where hints and recent folders.** `launch.folder_info`'s `subfolders` leave out
`projects` when the folder's real path is the workspace's and `projects/` is LADO's (D5's
condition); a folder inside LADO's `projects/` has no subfolders (it is refused).
`launch.recent_folders` leaves out folders inside LADO's `projects/` (they would be
refused; a stopped session there is resumed from its own page).

**D9. Delete.** `projects.delete(id, yes)`: first the sessions
(`state.project_sessions`): any whose `runtime.session_status` is not STOPPED refuses,
exit 1, nothing changed: `project <id> has sessions not stopped: <names>; stop them first
with lado stop <name>`. The CLI then prints `Sessions to forget: <name> (<n> open
run[s]), …` when there are stopped ones, then the unpushed work as in S2; without
`--yes` the refusal names the sessions too: `deleting project <id> removes its folder
<folder> with everything in it and forgets its <n> session[s]; run again with --yes`.
With `--yes`: the folder (as in S2) → each session by `runtime.forget_session(name,
force=True)` → the record. A failed folder removal keeps everything; a failed forget
keeps the record (the foreign key holds it) and names the session; running it again
goes on.

**D10. `lado ls` and `lado project show`.** `lado ls`: `<name>[ "<title>"]  <repo>  project
<id><status>` (after the folder, so the title's line rule of `session-title` holds).
`lado project show` adds, after `made:`, `  repositories:` and one line per repository
`    <name>  <branch or (detached)>  <remote or (no remote)>`, names and branches padded;
none: `  repositories: none`.

**D11. API.** `SessionInfo.project: str | None` (the id, in the feed: it never changes).
`SessionAbout.project: ProjectRef | None`, `ProjectRef{id, title}` read when asked (a
rename shows on the next look, as the head's git facts). `GET /api/projects/{id}` →
`ProjectInfo{id, title, folder, found, repos: list[ProjectRepo]}`,
`ProjectRepo(RepoInfo){name}`; 404 for an unknown id. `make web-types`.

**D12. The head.** Variant A of the mockup (#810): in `HeadLine` the first fact of
`.session-meta`, a `session-fact` with the muted word `project` and the title (else the
id) in the ink colour, tooltip `Project <id>`, no icon (the folder's icon is the Projects
icon); it wraps with the facts and goes to the second line in a narrow window. The phone's
details sheet: a line `Project <title>` above the folder. Nothing for a session without a
project; the facts of `useAbout` load as today, the project with them.

**D13. Docs and version.** `docs/cli.md`, `docs/design/projects.md` (the "What is built"
box: S3; the session, the repositories and deleting with sessions built; S4 still open),
`docs/design/ui.md` (Session head, Where hints, the refusal), `docs/design/modules.md`.
CHANGELOG: one line under `## 0.43.0 (unreleased)`, Added. Minor (already).

## Risks / Trade-offs

- A start racing a delete: a session started after the delete's check makes the forget
  fail and keeps the record (D9); running the delete again names it.
- A workspace changed after a session started: the session keeps its `repo` and project;
  its resume is not refused (the record is the truth), while the new workspace's
  `projects/` decides refusals of new sessions.
- Sessions from before S3 under `projects/` (only on `main`) keep no project: deleting
  the project removes their folder; their resume then fails as a missing folder.
