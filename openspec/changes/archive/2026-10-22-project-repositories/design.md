## Context

S2 (`projects-in-core`) made a project a record with its folder `<workspace>/projects/<id>`
and the unpushed scan (`projects.unpushed`) of `lado project delete`. S3
(`sessions-in-projects`) reads a project's repositories from the disk
(`projects.repositories`, `projects.links`, `projects.repository`), starts sessions in them
and refuses a new session without a project inside LADO's `projects/`
(`projects.refusal`, kind `in_project`), on every start path: `runtime.start_session`,
`clone.check_target`, `scratch.check_target` and the server's `launch.folder_info`. Its
D9 made `lado project delete` refuse while a session working in the project's folder (by
path) is not stopped, and forget the project's stopped sessions after removing the folder.

LADO makes repositories two ways: `clone.clone(url, path, branch, on_progress, cancelled)`
(a hidden temporary folder `.<name>.clone-*` beside the target, renamed at the end; Ctrl-C
and SIGTERM end git's group and remove it; the server runs it as a job,
`server/clones.Jobs`) and `scratch.make(path, name)` (checks the session name, the target
and git's author, then `git init` and an empty commit, removing what it made on failure).
Both refuse any folder inside LADO's `projects/` (state `in_project`), so neither can
serve a project today.

Model and decisions: `docs/design/projects.md`, the concept `projects-concept`, the epic's
plan (S4) and the brief of gate #72. The human's answers of this step: question #892 (the
CLI's shape, what `remove` removes, the name rule).

## Goals / Non-Goals

Goals: add a repository to a project by a clone or from scratch through the existing
paths; remove one with the checks of a project's delete; the server's API for both; the
hint of S3's remnant E3.

Non-goals: variables (S5a/S5b), any screen (S6/S7), a session started in a new repository
at once (#892), removing plain folders (#892), additions to repositories in the database.

## Options

For where a clone or fresh start into a project is allowed:
1. **`clone.clone` and `scratch.make` take a `project`, and skip the `in_project` refusal
   only for a path directly in that project's folder; `lado.projects` checks the project
   and the name first** (chosen). One clone path and one fresh-start path, with the
   temporary folder, cancellation, progress, author check and cleanup they already have;
   every other path stays refused. Cost: one keyword in each.
2. A clone and an init of their own in `lado.projects`. Shorter to read, but a second copy
   of the temporary folder, the signals, the progress and the cleanup that would drift
   from `lado.clone`'s (the brief asks for the same paths).
3. Lift the refusal for a path inside `projects/` when it does not exist yet. Then `lado
   start <git-url> <ws>/projects/shop/web` would clone into a project and start a session
   without the project, which S3 forbids.

For the server's clone into a project:
1. **The existing clone job (`POST /api/clones`) with `project` and `name`** (chosen): the
   UI of S6 gets progress, cancel, the beacon and the abandoned-job sweep for free.
2. A synchronous `POST /api/projects/{id}/repos` with a URL: a request that lasts minutes,
   with no progress and no cancel.

For removing:
1. **One core pair: `projects.removal(id, name)` (what it does, refusing first) and
   `projects.remove_repo(id, name, yes)`**, the CLI and the server only print or return
   it (chosen); the same shape as `sessions_to_forget` and `delete`.
2. Reuse `projects.delete` with a sub-path: its rules (the record, every session of the
   project) do not fit a repository.

## Decisions

**D1. The name rule.** `projects.REPO_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*")`,
`MAX_REPO_NAME = 100`; `projects.check_repo_name(name)` raises `ProjectError("the
repository name <name> is not valid: Latin letters, digits, ., _ and -, not starting with
. or -, at most 100 characters")`. Case is kept (as `git clone` keeps it); on a
case-insensitive disk `Frontend` beside `frontend` is caught by the taken check (D2),
which asks the disk. No transliteration in the CLI (#892).

**D2. The target of an add.** `projects.new_repo_folder(id, name) -> Path`: `get(id)`
(`unknown project "<id>"`, `NoSuchProject`); `folder(id).is_dir()` or `ProjectError("the
folder of project <id> is not found: <folder>")`; `check_repo_name`; then
`os.path.lexists(folder(id) / name)` → `ProjectError("<folder>/<name> already exists in
project <id>: choose another name with --name")`. A clone's name is `name` or
`clone.Address.parse(url).repo_name` (empty → `clone.default_folder`'s `no_repo_name`
text). The check runs before anything is cloned or made, and `clone.clone` and
`scratch.make` check the target again at their end.

**D3. Clone into a project.** `clone.check_target(url, path, project=None)` and
`clone.clone(…, project=None)`: with `project`, the `in_project` refusal is skipped when
the real path's parent is the real `projects.folder(project)`; any other path is refused as
before. `projects.add_clone(id, url, name, branch, on_progress, cancelled) -> Repository`:
D2, then `clone.clone(url, str(target), branch, on_progress, cancelled, project=id)`, then
the `Repository` read from git (as `repositories` makes it). The lazy import of
`lado.clone` in `projects` stays (clone builds on projects).

**D4. Fresh start into a project.** `scratch.check_target(path, project=None)` and
`scratch.make(path, name, project=None)`: with `project`, the refusal is skipped as in D3,
and `runtime.check_name` (a session's name) is not asked: no session is made. The author
check, `git init`, the branch and the empty commit, and the cleanup stay. A project folder
that is itself a git repository makes the target `inside_repo` (refused, as today): a
project folder is never a repository. `projects.add_new(id, name) -> Repository`: D2,
then `scratch.make(str(target), name, project=id)`.

**D5. The CLI.** `lado project repo add <id> [<git-url>] [--new NAME] [--name NAME]
[--branch BRANCH]` and `lado project repo remove <id> <name> [--yes]` (a subparser `repo`
under `project`; `lado project repo` alone prints its help). Usage errors (exit 2): both a
URL and `--new`, neither, `--name` or `--branch` with `--new`, a URL that `clone.is_url`
does not take. `_human_only("project repo add")` / `("project repo remove")` first. The
clone prints `Cloning <which> of <public url> into <folder>` and the progress on stderr
through `_CloneProgress` and `_ended_by_signals`, as `_start_clone`: Ctrl-C → `lado: clone
cancelled`, exit 130; SIGTERM/SIGHUP → exit 128+n. `--new` prints `Made <folder> a git
repository with an empty first commit`. Both then print `Added repository <name> to
project <id>: <folder>` and `Start a session in it: lado start --project <id> --repo
<name>`.

**D6. What a removal does.** `projects.Removal(name, kind: "repository" | "link", path,
target: str | None, sessions: list[tuple[str, int]], unpushed: list[str])`;
`projects.removal(id, name)`: `get(id)`; the entry `folder(id) / name`:
- missing → `NoSuchRepository` (a `ProjectError`) with `repository`'s texts (`project <id>
  has no repository <name>; its repositories: …` or `no repositories yet: …`, D10);
- a symbolic link → kind `link`, `target = os.readlink`, no sessions, no unpushed lines;
- a folder that is one of `repositories(id)` → kind `repository`;
- anything else (a plain folder, a file, a nested folder of a repository project folder) →
  `ProjectError("<name> in project <id> is not a repository: LADO removes only
  repositories and links")`.
For a repository: every session (`state.list_sessions()`) whose `realpath(repo)` is inside
`realpath(path)` and whose `runtime.session_status` is not STOPPED refuses: `repository
<name> of project <id> has sessions not stopped: <names>; stop them first with lado stop
<name>` (names by `projects.names`). `sessions` are the stopped ones of
`state.project_sessions(id)` in that folder, by name, with their open runs; a stopped
session there without a project is not forgotten (as S3's D9: the path is a safety check,
never how LADO learns a project). `unpushed` is D7's lines of that one repository.

**D7. The unpushed check of one checkout.** The body of `projects.unpushed`'s loop moves
to `projects._checkout_lines(entry: Path, base: Path) -> list[str]` (the repository's
uncommitted changes and branches not pushed, then each worktree with changes, shown
relative to `base`); `unpushed(project_folder)` calls it for each entry as today, with the
same output, and `removal` calls it for the repository with `base = folder(id)`. A
worker's branch not pushed shows through `_not_pushed` (`branch <b> not pushed`), its
worktree with uncommitted changes as `<name> (worktree <path>): uncommitted changes`.
S2's findings (F2 and the rest) stay as they are: step S7.

**D8. Removing.** `projects.remove_repo(id, name, yes) -> Removal`: `removal` first (its
refusals); without `yes` `ProjectError("removing repository <name> of project <id>
deletes its folder <path> with everything in it[ and forgets its <n> session[s]]; run
again with --yes")`, for a link `("removing <name> of project <id> deletes the link only,
not its target <target>; run again with --yes")`. With `yes`: a link → `unlink()`; a
repository → its real path must have the real `folder(id)` as parent and that the real
`projects_folder()` as parent, else `ProjectError("<path> is not in <folder>: LADO removes
nothing outside it")`; `shutil.rmtree` (links inside removed as links); a failure →
`ProjectError("could not remove <path> whole: <error>; its sessions stay")`. Then each
session by `runtime.forget_session(name, force=True)`; a failure → `ProjectError("the
repository is removed, but session <s> could not be forgotten: <error>; forget it with
lado forget <s> --force")`. The CLI prints `Sessions to forget: …` and `Unpushed work in
<path>:` as `project delete` (from `removal`), then calls `remove_repo`, then `Removed
repository <name> from project <id>` or `Removed the link <name> from project <id>`.

**D9. The server.**
- `CloneStart` gets `project: str | None = None` and `name: str | None = None`; with
  `project` a `path` is 400 (`a clone into a project takes no path`), `name` without
  `project` is 400. `Jobs.start` with `project` takes its folder from
  `projects.new_repo_folder` (D2) and the job runs `clone.clone(…, project=…)`; `Busy` by
  real path as today. `clone_core` maps `NoSuchProject` to 404.
- `POST /api/projects/{id}/repos` (`guard.changes`), body `RepoNew{name}` →
  `projects.add_new` → `ProjectRepo`.
- `GET /api/projects/{id}/repos/{name}/removal` (`guard`) → `RepoRemoval{name, kind, path,
  target, sessions: list[SessionToForget{name, open_runs}], unpushed: list[str]}`.
- `DELETE /api/projects/{id}/repos/{name}` (`guard.changes`) → `remove_repo(id, name,
  yes=True)`, answers `ProjectInfo` (`launch.project_info`) as it is after.
- `NoSuchProject` and `NoSuchRepository` → 404; another `ProjectError`, `ScratchError` or
  `CloneError` → 400 with the text (`core`). The server is the human's (its token); it
  does not ask `LADO_AGENT`. `make web-types`.

**D10. E3, the refusal's hints.** `projects.refusal(path, *, url=None, fresh=False)`: for
`<ws>/projects/<id>/<name>/…` the hint is the session's (`lado start --project <id> --repo
<name>`) only when `<name>` is one of `repositories(id)`; else `See the project's
repositories:` / `lado project show <id>`. When the path is exactly `<ws>/projects/<id>/<name>`,
nothing of that name exists (`lexists`) and the name passes D1: with `url` the hint is
`Add a repository to the project:` / `lado project repo add <id> <public url>` plus `
--name <name>` when `<name>` is not the URL's `repo_name`; with `fresh`, `lado project
repo add <id> --new <name>`. Callers: `clone._check_target` passes `url`;
`scratch._check_target` and `launch.folder_info` pass `fresh=True`; `start_session` neither.
`projects.repository`'s text for a project with none becomes `project <id> has no
repositories yet: add one with lado project repo add <id> <git-url> or --new <name>`.

**D11. No schema, no protocol.** Repositories stay on the disk; `lado.db` does not change.
`mcp_server.py`, `hooks.py`, `providers/` do not change; no MCP tool is added (the
concept: only the human changes projects).

**D12. Docs and version.** `docs/cli.md` (`lado project repo add|remove`, the new hints),
`docs/design/projects.md` (the "What is built" box: S4; the paragraph on adding and
"Deleting a repository" built), `docs/design/modules.md` (`projects.py`, `clone.py`,
`scratch.py`, `server/clones.py`, `server/app.py`), `docs/design/ui.md` (the clone job's
`project` and `name`). CHANGELOG: one line under `## 0.43.0 (unreleased)`, Added. Minor
(already).

## Risks / Trade-offs

- A session started in the repository between `removal`'s check and the folder's removal
  loses its folder; the same race as the project's delete (S3), accepted: the human runs
  both.
- A worker's worktree that git keeps outside the repository's folder (LADO puts them in
  `.lado/worktrees/`, inside it) stays on the disk, dangling; `removal` lists it if it has
  changes.
- Stopped sessions without a project in the repository (from before S3) are not forgotten
  and lose their folder; their resume then fails as a missing folder (as in S3's delete).
- A URL with a secret in it is shown through `runtime.public_remote` in hints and lines,
  so the hint's command may need the secret again; never the secret in a text.
