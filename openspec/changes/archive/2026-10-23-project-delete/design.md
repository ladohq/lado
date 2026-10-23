## Context

Steps S2–S7a built projects in the core, the CLI, the API and the page. Deleting a project
lives in the core only: `projects.sessions_to_forget(id)` refuses while a session of the
project, or any session whose real folder is inside the project's real folder, is not
stopped, and lists the project's stopped sessions; `projects.unpushed(folder)` gives the
lines of the work not on the remote (S7a's F2 and F3: detached HEAD, stashes, a project
folder that is a repository, worktrees once); `projects.delete(id, yes)` refuses without
`yes`, checks the data folder for links (`project_secrets.check_removable`), unlinks a
folder that is a link or removes a real one directly in the real `projects/`, forgets the
sessions, removes the data folder (`project_secrets.remove_all`) and the record last.
`lado project delete` (`cli.py`) calls the first two to print, then the third. The page
(`web/src/Projects.tsx`) ends with `Deleting the project: not built yet`; the repository's
delete (`ProjectRepos.tsx`, `DeleteRepoDialog`, S7a) previews by `GET …/removal`, then
`DELETE`s, with the name typed when there is unpushed work (#1352).

Model and decisions: `docs/design/projects.md` ("Deleting"), the concept
`projects-concept` ("Deletion": the UI confirms by the project's id typed), the step's
brief (gate #113: one core function, nothing removed outside `<workspace>/projects/<id>`
and `<LADO_HOME>/projects/<id>`, no link followed), the human's answers #1375, the mockup
`mockup-project-delete.html`.

## Goals / Non-Goals

Goals: delete a project from its page after seeing what goes, through the API and the
CLI's core function; the delete path's leftovers (S2's F5 and E3, S3's G1, S4's X3 for
the project, S5a's F5, S7a's F2) and S7a's F1; the canary over the delete.

Non-goals: a trash or an undo; S7a's minors F3, F4, X3, X5; sessions over several
repositories; repository extras in the database.

## Options

The root cause: the core deletes, but its preview is two calls the CLI strings together,
and no API exposes either.

1. **One preview function in the core, `projects.deletion(id) -> Deletion`, that
   `delete` acts on and the CLI and the API both show; two routes; a new dialog beside the
   repository's** (chosen). Long-term cost: one dataclass and one model; the CLI's output
   and the dialog read the same object, so "what goes" cannot drift between them; the
   leftovers are fixed in that one function.
2. Two routes that call `sessions_to_forget` and `unpushed` separately, as the CLI does.
   Less code moved, but the link rule (G1/F5) and the sessions without a project (X3) would
   have to be applied in each caller: against "one source of truth".
3. A generic "removal" over repositories and projects (`removal(id, name=None)`). One
   dialog in the UI, but the two differ in what goes (variables, secrets, a folder that is
   a link or missing) and in the confirmation (#1352 vs the concept's id), so one function
   would be a switch on its argument.

## Decisions

**D1. `projects.deletion(id) -> Deletion` is the one preview.** `Deletion(id, path, kind,
target, sessions, unpushed, variables, secrets)`: `path` = `folder(id)`; `kind` `"link"`
when it is a symbolic link (`target` = `os.readlink`), `"missing"` when nothing is there
(`os.path.lexists` false), else `"folder"`; `sessions` = `list[tuple[str, int, str |
None]]` (name, open runs, project) as `Removal.sessions`; `unpushed` = `unpushed(path)`
for a `"folder"`, `[]` otherwise; `variables` = the names of `state.project_variables`;
`secrets` = `project_secrets.names(id) or []` (names only, no file is opened). It calls
`get(id)` first (NoSuchProject) and refuses (ProjectError) with today's busy text.
`sessions_to_forget` goes: `deletion` replaces it (its one caller, the CLI, moves over).

**D2. Which sessions** (G1, X3). Busy: any session of the project (`sess.project == id`)
not stopped; and, only for `kind == "folder"`, any session whose real folder is inside the
real project folder, not stopped. Forgotten: the project's sessions, and, only for a
`"folder"`, the stopped sessions with `project is None` inside its real folder (X3, as
`removal` does for a repository). For a `"link"` no path is matched: the target is not
deleted, so nothing working there is in the way or goes (the brief's threshold: no link
followed). A session of another project is never matched by its path (comment kept).

**D3. `delete(id, yes)` acts on `deletion(id)`.** Its order and its guards stay (data
folder's link check first, then the folder, the sessions, the data folder, the record; a
folder whose real path is not directly in the real `projects/` refused). Without `yes`
the refusal says what is true: `"folder"` — `deleting project <id> removes its folder
<path> with everything in it[ and forgets its <n> session(s)]; run again with --yes`
(today's text); `"link"` — `deleting project <id> removes the link <path> only, not its
target <target>[ …]; run again with --yes`; `"missing"` — `deleting project <id> removes
its record (its folder <path> is not found)[ …]; run again with --yes`.

**D4. The CLI prints the preview.** `cmd_project`'s delete: `found = projects.deletion(id)`;
`Sessions to forget: …` with ` (<n> open run[s])` and ` (no project)` as `_remove_repo`
prints them; `Unpushed work in <folder>:` and its lines; then `projects.delete(id,
args.yes)`. Variables and secrets are not printed: `lado project show` lists them, and the
CLI's text stays as the specs have it.

**D5. E3: an unreadable folder is a line, not a traceback.** In `unpushed`, the listing of
`project_folder` (`iterdir`) in `try`/`except OSError`: on failure the result is `["the
project's folder: could not check: <strerror>"]` (with the root's own lines before it when
git read it). `delete --yes` on it fails in `rmtree` and already says `could not remove
<folder> whole: …; the project stays`. The API turns both into 200 with the line and 400
with the text; no route gives 500.

**D6. F2: the project's repositories are not the root's changes.** In `_checkout_lines`
for the project's folder (called by `unpushed` with the label `the project's folder`), the
`git status --porcelain` gets one exclude pathspec per entry directly in the folder that
has a `.git` (`':(exclude)<name>'`), so the untracked or gitlinked repositories inside it
are not `uncommitted changes`; the root's own files still are. Only the root's call takes
excludes: `_checkout_lines` gains a keyword `skip: list[str] = []`, nothing else changes.

**D7. S5a's F5: a write for a project deleted meanwhile.** `set_variable`: the
`state.set_project_variable` call in `try`/`except sqlite3.IntegrityError` (the foreign
key to `projects`) raises `NoSuchProject(f'unknown project "{id}"')`, the text `get`
gives. `set_secret`: after `project_secrets.write`, `state.get_project(id) is None` means
the project went meanwhile: remove the file just written (`project_secrets.remove`) and
raise the same `NoSuchProject`. The CLI prints `lado: unknown project "<id>"`, exit 1; the
API's `project_core` answers 404. A delete that runs after the write removes the file
with the data folder anyway; this covers the order where the delete ran first.

**D8. The API.** `GET /api/projects/{id}/deletion` (`guard`, as the repository's
removal) answers `ProjectDeletion` (`launch.project_deletion(found)`: `id`, `folder`,
`kind: Literal["folder", "link", "missing"]`, `target: str | None`, `sessions:
list[SessionToForget]`, `unpushed: list[str]`, `variables: list[str]`, `secrets:
list[str]`); `DELETE /api/projects/{id}` (`guard.changes`) calls `projects.delete(id,
True)` through `project_core` (404 for NoSuchProject, 400 for any other LadoError) and
answers 204 with no body: the project is gone, and the page goes to the list, which it
reads anew. Both are in `web/openapi.json` and `web/src/api.gen.ts` (`make web-types`).

**D9. The block and the dialog** (`web/src/ProjectDelete.tsx`, mockup frames 1, 2–6, 8,
9; layout A, #1375). `ProjectDelete({project})`: a `.project-section.project-delete` at
the page's bottom (after Secrets, in place of the not-built line) with `h3` `Delete
project`, the button `Delete project…` (`quiet danger-text`) and the sentence `Deletes its
folder with every repository in it, its sessions, variables and secrets. Refused while a
session of the project runs.` The button opens `DeleteProjectDialog`, built as
`DeleteRepoDialog` (S7a, D11): `showModal`, the preview on open, `Loading…`; the sentence by
kind — `"folder"`: `Its folder <folder> is deleted with everything in it, and so are its
sessions, variables and secrets. This cannot be undone.`; `"link"`: `Its folder <folder>
is a link to <target>: only the link is deleted, <target> and everything in it stay. Its
sessions, variables and secrets are deleted. This cannot be undone.`; `"missing"`: `Its
folder <folder> is not found. Its sessions, variables and secrets are deleted. This
cannot be undone.`; then a `.removal-list` with `Work that is not on the remote` (or `All
its work is on the remote.`; nothing for a link or a missing folder), `Sessions that are
forgotten` (`(<n> open run[s])`, `— no project, started in this folder before projects`;
or `No session is forgotten.`), `Variables and secrets that are deleted` (each name, a
secret with `— secret`; or `No variables or secrets.`); the field `Type <id> to delete it`
always (#1375, the concept); `Cancel` and `Delete project` (`danger`), on only while the
field holds the id exactly. `Delete project` sends `DELETE`; on 204 the dialog closes, the
section's list is read anew (`reload()`) and the router goes to `/projects`. A refusal of
the preview or of the `DELETE` replaces the body with the text (`field-note bad`) and only
`Close`; Esc and Cancel close it unless the `DELETE` is in flight.

**D10. F1: the hook cancels on unmount.** `useCloneJob`'s unmount cleanup (the effect
that sets `alive`) sends `cancelClone(current.current.id)` when a job is running
(`current.current?.state === "running"`), catching its failure. React's StrictMode trial
unmount runs before any job starts, so it cancels nothing. The New session window shares
the hook, so a window that unmounts mid-clone cancels too — its clone has no follower
then either. `cloneJob.test.ts` gets the case; `Launch.test.tsx` and `tests/ui/
test_launch.py` stay unchanged unless one asserts the opposite (the PR names any change).

**D11. Projects' list after the delete.** The feed's session deletions (forget) reach
the page as now; the project list is read anew by `reload()` and on the route's change, as
S6a's rule reads it after a change. No feed of projects.

**D12. Tests at the lowest layer.**
- Unit (`tests/test_projects_core.py`, `tests/test_project_repos.py`, `tests/test_cli.py`):
  `deletion` by kind (folder, link, missing);
  G1 — a running session without a project in the link's target does not refuse and is
  not forgotten, the project's running session still refuses; F5's texts without `--yes`
  for a link and a missing folder; E3 — an unreadable folder (chmod 000, skipped as root)
  gives the line and no traceback from the CLI; F2 — a root repository holding clean
  repositories gives no line, a changed root file does; X3 — a stopped session without a
  project in the folder is named `(no project)` and forgotten; S5a's F5 — a variable and a
  secret for a project deleted between check and write (monkeypatched) raise
  `NoSuchProject`, no row, no file; `delete` still refuses without `yes` and removes
  nothing outside.
- Server (`tests/test_server_projects.py`): the preview's fields, no secret value in it;
  `DELETE` 204 and the state after; 400 with a running session; 404 unknown; refused
  without the change token; the variable and secret `PUT` 404 after a delete in between;
  that both routes call `projects.deletion`/`projects.delete` (monkeypatched spies).
- Vitest: a new `web/src/ProjectDelete.test.tsx` (the block, the dialog's lists by kind,
  the id typed with and without unpushed lines, refusal of the preview and of the
  `DELETE`, success navigates to `/projects`); `web/src/cloneJob.test.ts` (unmount during
  a running job sends the cancel; after the end it sends none); `Projects.test.tsx` (no
  not-built line).
- UI e2e (`tests/ui/test_project_page.py`, the fake provider): refused while a session of
  the project runs, Close only; after the stop the id typed, then `/projects` without the
  project, the folder, `<LADO_HOME>/projects/<id>` and the sessions gone; an unpushed
  commit of a repository shown; a project folder that is a repository holding the
  project's repositories shows no `the project's folder: uncommitted changes`; the phone
  at 390 px and the dark theme for the screenshots. Waits for states, never times.
- Integration: the canary goes on after its checks — stop the sessions, `GET …/deletion`
  and `DELETE /api/projects/shop` (and one refused `DELETE` while a session runs, 400)
  into `said`; the secrets' folder gone; no value in `said`, the feed, the logs or any
  file under `LADO_HOME` (now without the `secrets/` skip). No other integration test:
  nothing new crosses processes.

**D13. Version and docs.** New API routes: minor, already `0.43.0 (unreleased)`; one
CHANGELOG line in Features (deleting a project from its page). `docs/design/ui.md`
Projects: the block and the dialog in place of the not-built line, F1 under Add
repository. `docs/design/projects.md`: "Deleting" says the UI is built (the id always
typed, the link and missing texts), "The UI" drops the not-built list's S7b item, the
step table unchanged (S7b's row already says it). `docs/cli.md`: `project delete`'s
texts for a link and a missing folder and ` (no project)`.

## Risks / Trade-offs

- **The id always typed is one more step than the repository's** (#1352 asks the name only
  with unpushed work). Chosen with the human (#1375): a project's variables and secrets
  are on no remote.
- **G1 changes who blocks a link folder's delete**: a running session without a project in
  the target no longer blocks. It cannot be harmed: only the link goes.
- **`set_secret` removes the file it just wrote when the project went**: a create of the
  same id between the write and the check would lose that one secret. Two human actions
  in a few milliseconds; the secret's write is refused loudly, never silently kept.
- **Cancel on unmount in a shared hook** also touches New session's clone: guarded by the
  window's tests run unchanged.
- **The preview may be stale at the `DELETE`** (as S7a's X3): the core checks the
  sessions again; new unpushed work between the two is not asked again, as the CLI's
  preview then `--yes`.

The plan with each task's tests: `docs/superpowers/plans/2026-10-23-project-delete.md`.
