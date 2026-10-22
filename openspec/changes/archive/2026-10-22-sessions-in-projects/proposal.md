Task: LAD-125

## Why

Step S3 of the epic LAD-116 (`docs/epics/lad-116/plan.md`; the model is
`docs/design/projects.md` and the concept `projects-concept`, sections "The session" and
"How LADO knows a project's repositories"). Step S2 made a project a record in `lado.db`
with its folder `<workspace>/projects/<id>`, but a session knows nothing of projects:
`lado start` starts anywhere, a session inside a project's folder is an ordinary session,
and deleting the project removes the folder from under it. Step S5a will give a session in
a project the project's variables; for that a session must refer to its project, and no
session without a project may start in a project's folder (one repository would get two
sets of keys; deleting the project would delete the folder under another session).

The root cause: the session's record has no project, so the only way to know one would be
to guess it from the folder's path, which the concept forbids ("a session's project is a
reference in the database"), and nothing stops a start inside `projects/`.

## What Changes

- **A session in a project.** `lado start --project <id> --repo <name>` starts in
  `<workspace>/projects/<id>/<name>`. The session's record refers to the project
  (`sessions.project`, schema 33); the project never changes while the session exists. A
  new session in a project is named `<id>-<name>` unless `--name` is given.
- **A project's repositories from the disk.** A repository of a project is a direct
  subfolder of its folder that is the root of a git repository (not a symbolic link, not
  hidden: a clone's temporary folder is hidden), with its branch and remote read from git.
  The project folder itself is never one. The list is stored nowhere.
  `lado project show` lists them; `GET /api/projects/{id}` gives the project with them
  (for step S6). `--repo` with a name not in the list refuses and lists what is there.
- **Inheritance.** A session the supervisor starts with `start_session` starts in its
  parent's project and repository; a resume (CLI, UI, the container's start) keeps the
  project. No change of the agents' protocol: `start_session` keeps its arguments.
- **No session without a project inside `projects/`.** Once `<workspace>/projects` holds a
  project's folder (it is LADO's, not the human's own), a new session without a project
  whose folder is inside it is refused on every path: `lado start <folder>`,
  `lado start <git-url>` with a target there, `lado start --new` there, the server's
  folder check, clone target, fresh-start target and start, and `start_session` from a
  session without a project. The refusal names the project ("<path> belongs to the project
  Shop: start a session in the project") and offers `lado start --project shop --repo
  <name>`; in the New session window it is the refusal box of S1b with that command and
  Copy. A folder in `projects/` that is no project's folder is refused too, pointing at
  `lado project list`. A resume of an existing session is never refused by this rule.
- **The New session window's Where hints** leave out `projects/` of the workspace, and its
  recent folders leave out folders inside it.
- **Where the project shows**: `lado ls` (`  project <id>` after the folder), the session's
  API (`SessionInfo.project`, the id; `SessionAbout.project`, the id and the title read
  now) and the session's head in the UI: the first of its facts, `project <title>`,
  tooltip `Project <id>` (mockup `task/lad-125/mockup-session-project.html`, variant A);
  on a phone a line of the session's details.
- **`lado project delete`** refuses while any session of the project is not stopped, and
  lists the stopped sessions it will forget (with their open runs) before the unpushed
  work; with `--yes` it removes the folder, forgets those sessions as `lado forget
  --force` does, then removes the record.
- **Docs**: `docs/cli.md` (`lado start --project/--repo`, the refusal, `lado ls`, `lado
  project show/delete`), `docs/design/projects.md` (the session, the repositories and
  deleting with sessions marked built), `docs/design/ui.md` (Session head, Where hints,
  the refusal), `docs/design/modules.md` (`projects.py`, `state.py`).
- **CHANGELOG**: one line under `## 0.43.0 (unreleased)`.

## Acceptance criteria

- **AC-1** With project `shop` and a git repository `frontend` in its folder,
  `lado start --project shop --repo frontend` starts the session `shop-frontend` in
  `<ws>/projects/shop/frontend`; `lado.db` has `project = 'shop'` for it, and `lado ls`
  prints `project shop` on its line.
- **AC-2** `--repo` with an unknown name, a symbolic link, a hidden folder or a folder
  without its own git refuses and lists the project's repositories; `--project` with an
  unknown id refuses; `--project` without `--repo`, `--repo` without `--project`, and
  `--project` with a folder, a git URL or `--new` are usage errors.
- **AC-3** `lado project show shop` lists each repository with its branch and remote, and
  `GET /api/projects/shop` gives the same; a clone's temporary folder, a plain folder, a
  link and the project folder itself are not listed.
- **AC-4** A session the supervisor of `shop-frontend` starts with `start_session` is in
  project `shop` and in the same folder; stopping and resuming either keeps its project.
- **AC-5** A new session without a project inside `<ws>/projects/` is refused, naming the
  project and offering the command, by `lado start <folder>`, `lado start <git-url>
  <folder>`, `lado start --new <folder>`, `GET /api/folders`, `GET /api/clone-target`,
  `POST /api/clones`, `GET /api/scratch-target`, `POST /api/sessions` (folder and
  scratch), and `start_session` from a session without a project; nothing is cloned or
  made.
- **AC-6** The New session window shows that refusal in the refusal box with the command
  and Copy, and Start stays off; its Where hints of the workspace do not list `projects`.
- **AC-7** The session's head shows `project Shop` as its first fact for a session in a
  project, and nothing new for a session without one.
- **AC-8** `lado project delete shop` refuses while a session of `shop` is running (naming
  it and `lado stop`); with only stopped sessions it lists them, and `--yes` forgets them,
  removes the folder and the record.
- **AC-9** An older `lado.db` (schema 32) upgrades to 33 with its backup; its sessions have
  no project and keep working, a resume included.

## Out of scope

- Adding and removing a project's repositories through LADO (clone and from scratch into
  the project's folder): step S4. Until then repositories are made by hand (`git clone`,
  `git init` in the project's folder); a refused clone or fresh start into `projects/`
  points at `lado start --project`, whose refusal lists the repositories.
- The project's variables and secrets: steps S5a, S5b.
- The Projects section, the project's page and the window's Project way (`Launch` gets no
  `project` field; the head's project is text, not a link): steps S6, S7.
- `GET /api/projects` (the list): S6 adds it with the section that uses it.
- S2's findings about the check before deleting (F2, E3, F3, F5): step S7.
- Binding sessions started under `projects/<id>/` before this step to the project: they
  keep no project and keep working (question #808); 0.43.0 is not released, so only
  installations running `main` between S2 and S3 can have them.
- Sessions over several repositories ("all repositories"): not now (the concept).
- A symbolic link as a repository of a project (question #806): the project's work would
  lie outside its folder, which deleting the project never touches.

## Impact

- Code: `src/lado/projects.py` (repositories, the refusal, delete with sessions),
  `runtime.py` (`start_session`'s project, `start_approved_session`), `state.py`
  (schema 33), `cli.py` (`start`, `ls`, `project show/delete`), `clone.py` and
  `scratch.py` (target state `in_project`), `server/app.py`, `server/models.py`,
  `server/launch.py`, `server/clones.py`; `web/src/Sessions.tsx`,
  `web/src/SessionDetails.tsx`, `web/src/Launch.tsx`, `web/src/api.ts`,
  `web/openapi.json`, `web/src/api.gen.ts`.
- Not changed: `mcp_server.py` (beyond nothing: `start_session` keeps its arguments),
  `hooks.py`, `providers/`.
- Tests: unit, server, integration with the fake agent, UI e2e.
- Users: new CLI options, a schema migration, a refusal of sessions inside `projects/`.
  Version: **minor** (0.43.0 is already the unreleased minor).
