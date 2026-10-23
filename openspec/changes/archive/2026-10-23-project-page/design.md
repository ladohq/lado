## Context

Steps S2–S6b built projects in the core, the CLI and the API: `projects.repositories` reads
a project's repositories from the disk; `projects.add_clone` / `add_new` add one through
`clone.clone` / `scratch.make`; `projects.removal` / `remove_repo` preview and remove one
(the unpushed lines from `_checkout_lines`, the stopped sessions of the project in it);
`projects.rename` sets the title. The server has `POST /api/clones` with `project` and
`name` (a clone job), `POST /api/projects/{id}/repos`, `GET …/repos/{name}/removal`,
`DELETE …/repos/{name}` (S4), but no route to rename. The web UI's project page
(`web/src/Projects.tsx`, S6a) shows the head, a not-built line, the warning and the
variables; the New session window (`web/src/Launch.tsx`, 1585 lines) holds the only clone
job client (start, a poll every 500 ms, the 404 rule, `Cancel clone`, the `pagehide`
beacon), and its Project way (`LaunchProject.tsx`, S6b) only chooses a repository.

The change feed carries each session's `project` (`SessionInfo.project`), its status,
`running_since`, `stopped_at`, `title` and folder (`repo`, the real path of the
repository's root).

Model and decisions: `docs/design/projects.md`, the concept `projects-concept` ("UI",
"Deletion"), the brief of gate #110 (S7), the human's answers #1282, #1283 (repositories
are managed on the project's page only), #1347 (the split: S7a here, project deletion in
S7b) and #1350/#1352 (the round on the page: variant A, X3 forgotten, E1, links not
shown accepted; Tab in the title field, a typed name for unpushed work, F2 and F3 closed
here), the mockup `mockup-project-page.html`.

## Goals / Non-Goals

Goals: the project's page lists its repositories and sessions, adds a repository by a clone
(with progress and cancel) or from scratch, deletes one after showing what goes, renames
the project; the leftovers F2 and F3 (the shared unpushed check), X3, E2, M1, E1 and the clone/scratch
refusal's way to the page.

Non-goals: deleting the project and its leftovers (S7b); links in the project's folder on
the page; sessions over several repositories; repository extras in the database.

## Options

The root cause: the core and API for a project's repositories exist, no screen uses them,
and renaming has no route.

1. **The page uses S4's routes as they are; one new route (`PATCH /api/projects/{id}`); the
   clone job client moves out of `Launch.tsx` into a hook both dialogs use; sessions come
   from the feed** (chosen). Long-term cost: one route, a few optional fields on existing
   models, and one refactor of `Launch.tsx` that the window's tests guard; no rule gets a
   second copy, and S7b adds its dialog beside the repository's.
2. A second clone client in the Add repository dialog, leaving `Launch.tsx` alone. Less risk
   to the window now, but the 404 rule, the poll, the beacon and the cancel would live twice
   and drift: against "one source of
   truth".
3. A route `GET /api/projects/{id}/sessions` for the page's sessions. Exact, but the feed
   already carries every field the block shows and follows starts and stops live; a route
   would need the page's read-anew rule to follow them.

## Decisions

**D1. S7 is split (#1347).** This change is S7a; deleting the project is S7b, a task derived
from LAD-138. The page keeps a bottom line `Deleting the project: not built yet (Projects,
step S7b). Meanwhile: lado project delete <id>.` until S7b replaces it.

**D2. Rename is `PATCH /api/projects/{id}`** with `ProjectTitle{title: str | None}`,
calling `projects.rename(id, title)` (the CLI's function, `runtime.check_title`'s rule):
`NoSuchProject` 404, any other `LadoError` 400, the answer `launch.project_info(id)`; behind
`guard.changes` like every change route. The page's field is the session's `TitleEdit`
made generic (#1352: Tab as in a session's rename): it takes `name` (the suggestion: the
session's name, the project's id), `title`, `save(title | null)` and the two hints, and
keeps every rule of the `session-title` spec (Enter or blur saves, Esc cancels, empty
clears, the same text sends nothing, a text equal to the name clears, a refusal under the
field with the text kept, Tab and → take the suggestion). The session's head and row pass
`setSessionTitle`; the project's head passes `renameProject`, hints `Enter to save · Esc to
cancel` and `Tab takes the id · Enter to save · Esc to cancel`. One component, so the two
renames cannot drift. A save updates the page from the answer (`drop()` of S6a's
`useLatest`) and reloads the list.

**D3. The clone job client is one hook.** `web/src/cloneJob.ts` gets `useCloneJob()`: start
(`startClone`), the poll every 500 ms with today's rules (a failed poll asked again, a 404
ends it and asks the caller's `isThere(job)` whether the clone is there: the window keeps
its `getCloneTarget` check, the dialog asks whether the project lists the name, as a
target inside `projects/` answers `in_project`), `cancel()` (`DELETE`), and the
`pagehide` beacon (`cancelCloneOnLeave`) bound in a layout effect while a job runs. The
New session window's Clone and start and the Add repository dialog both use it; the window's
own steps after the clone (start the session, switch to Folder) stay in `Launch.tsx`. The
window's existing vitest and UI tests are the guard: they run unchanged.

**D4. Add repository's name.** `RemoteInfo` gains `repo_name: str | None`, the URL's
repository name as `clone.Address.parse(url).repo_name` gives it (None when the URL names
none), so the dialog's Name takes it without a second slug rule in TypeScript. The dialog
sends `name` always (the field's text). No name check while typing: `clones.Jobs.start`
checks `projects.new_repo_folder` and the clone target before git runs and refuses at once
(400 `CloneRefused` or the project's text), which the dialog shows under Name; from scratch
refuses the same way. The folder note under Name is `<project folder>/<name>`, shown, not
checked.

**D5. After an add the dialog closes; it starts no session.** The page re-reads the project
(`GET /api/projects/{id}`; for scratch the `ProjectRepo` answer is not enough as the page
shows the whole project) and the new row shows. Starting is the row's Start session (#1282:
the start and the repositories stay apart).

**D6. Start session is `useLaunch()({kind: "new", project, repo})`.** `LaunchMode` gains
`repo?: string`; the window asks `GET /api/project-launch?project=&repo=`. The head's `New
session…` passes the project only.

**D7. E1 is a field of `ProjectLaunch`.** `gone: Literal["project", "repo"] | None`, set in
`launch.project_launch` when the project asked is not listed, or the repository asked is not
one of the chosen project's; the choice itself is unchanged (the server's rule of S6b). The
Project way shows the warning from it (`field-note warn`), naming the asked id or name from
the window's own request and the chosen project's title. Without `asked` nothing is gone.

**D8. The page's sessions come from the feed** (`useLive().sessions` filtered by `project
=== id`): running ones by `running_since` descending, then the rest by `stopped_at`
descending (starting and other statuses with the running). The repository shown is the last
part of the session's folder (`repo`): a session's folder is a repository directly in the
project's folder, and the feed has no other link from a session to a repository. Times use
the helpers the session list uses. No new route (Options, 3).

**D9. X3 in the core, shared by the CLI and the API.** `projects.removal` adds to `sessions`
the stopped sessions with `project is None` whose real folder is inside the repository's
real path; `remove_repo` forgets them as it forgets the project's (`forget_session(force=
True)`). `Removal.sessions` becomes `list[tuple[str, int, str | None]]` (name, open runs,
project); `SessionToForget` gains `project: str | None`; the CLI prints ` (no project)` after
such a name. A session of another project is never matched by path (comment kept). The
busy check before it is unchanged: it already counts any session by path.

**D10. F2's detached HEAD and stash in `_checkout_lines`.** In the repository: when `git
symbolic-ref -q HEAD` fails (detached), `git rev-list --count HEAD --not --branches
--remotes` gives the commits on no branch, a finding `detached HEAD with <n> commit[s] on no
branch` when `n > 0`; `git stash list` gives `<n> stash[es]`. In each worktree with a
detached HEAD the same rev-list in the worktree, its line `… (worktree <path>): detached HEAD
with …` (joined with `uncommitted changes` by `; ` when both). Every git call goes through
`_git` (timeout, no prompt), so a failure is the existing `could not check` line. In
`unpushed` (the project's delete, #1352: closed here, S7b only shows them): F2's project
folder that is itself a repository's root (`_own_root`) gets its lines first, labelled
`the project's folder`; F3: an entry that is a worktree of a repository listed in the same
folder (its path among that repository's `_checkouts`) gets no line of its own, as it is
listed under its repository. Both are seen in the CLI's `lado project delete` now and in
S7b's dialog later.

**D11. The delete dialog** (`DeleteRepoDialog` in `ProjectRepos.tsx`) reads the preview when
it opens, shows the folder, the lines and the sessions (`(<n> open run[s])`, `— no project,
started in this folder before projects`), and sends `DELETE` with `Delete repository` (the
`danger` button). When `unpushed` is not empty (#1352) a field `Type <name> to delete it`
shows under the lines and the button is on only while the field holds the name exactly;
with no unpushed line the button is on at once, and the dialog says `All its work is on
the remote.` in place of the list (and `No session is forgotten.` when no session is). Sessions alone ask no name: their history
is named and their folder goes either way. A refusal of the preview or of the `DELETE` (a session started meanwhile)
replaces the body with the text and leaves only Close; Esc and Cancel close it unless the
`DELETE` is in flight. The `DELETE`'s answer (the project) updates the page as a variable's
change does. Links are not listed, so the dialog never removes one (proposal, Out of scope).

**D12. The clone and scratch refusals carry the project.** `CloneTarget` and
`ScratchTarget` gain `project: ProjectPlace | None`, set from `projects.place(path)` when
the state is `in_project` (as `FolderInfo.project`, S6b), so the window shows `Open the
project <title>` for Clone into and Create in from the server's answer, never by parsing a
path. The hint and its command stay below it.

**D13. E2 in `NewProjectDialog`:** when the title is not empty, Id is not edited and the
suggestion's id is empty or null, the note under Id is `The title gives no id: type one.`;
`Create project` stays off as now. Only the dialog changes.

**D14. M1 is CSS and `NoProject`.** At `max-width: 900px` `.projects` takes one column as
`.sessions` does (the list over the project, `height: auto`, the list's border at its
bottom), and `NoProject` renders nothing in a window that narrow (a `matchMedia` of the
same width), as on a phone.

**D15. The page's layout** follows mockup variant A (#1350, 1): the head (title with
`Rename`, id, `New session…`), the facts line, Repositories, Sessions, the warning and who
gets new values, Variables, Secrets, the S7b line. The blocks use S6a's `.project-section`;
the repository rows a `.project-repos` table whose actions go under the name at ≤ 760 px.
`ProjectRepos.tsx` holds the Repositories and Sessions blocks and the two dialogs, so
`Projects.tsx` stays the section's frame.

**D16. Tests at the lowest layer.**
- Unit (`tests/test_project_repos.py`, `tests/test_projects_core.py`): F2's findings on real
  git repositories in `tmp_path` (detached HEAD with and without commits on no branch, a
  stash, a worktree on a detached HEAD); F2's project folder that is a repository and F3's
  worktree inside the project folder in `unpushed`; X3's removal and forget; the CLI's
  ` (no project)`.
- Server (`tests/test_server_projects.py`, `tests/test_server_clones.py`,
  `tests/test_server_project_launch.py`): `PATCH` (set, clear, 404, 400, the token),
  `RemoteInfo.repo_name`, `SessionToForget.project`, `ProjectLaunch.gone`,
  `CloneTarget.project` / `ScratchTarget.project`.
- Vitest: `TitleEdit.test.tsx` (unchanged, plus the generic props), `Projects.test.tsx`
  (the project's rename, Tab takes the id, E2's note), a new `ProjectRepos.test.tsx`
  (rows, empty state, sessions' order and links, the add dialog's states with a fake clone
  job, the delete dialog's preview, the typed name with unpushed work, refusal and success), `cloneJob.test.ts` (the hook's
  poll, 404, cancel), `LaunchProject.test.tsx` (E1), `Launch.test.tsx` (the refusals'
  button; the window's clone tests unchanged).
- UI e2e (`tests/ui/test_project_page.py`, the fake provider, a local bare repository by
  `agent_helpers.bare_remote`, the slow clone fixture of `tests/ui/test_launch.py` moved to
  `tests/ui/conftest.py`): repositories with branch and remote; add from scratch; add by a
  clone and its progress; cancel; Start session starts in the project; delete with an
  unpushed commit; delete refused while a session runs; rename in the head, the list and the
  session's head; M1 at 390 px without touch; the phone at 390 px. Waits for states, never
  times (LAD-127).
- No integration test: nothing new crosses processes (the routes call the core in the
  server's process; agents are untouched). The canary does not change in S7a: no route here
  reads or writes a secret; S7b extends it to the delete.

**D17. Version and docs.** A new API route: minor, already `0.43.0 (unreleased)`; one
CHANGELOG line in Features. `docs/design/ui.md` Projects describes the page and its dialogs
and drops the S6a stub; Launch notes E1 and the clone/scratch refusal's button.
`docs/design/projects.md` marks S7a built. `docs/cli.md`'s `project repo remove` names the
sessions without a project.

## Risks / Trade-offs

- **Making `TitleEdit` generic** touches the session's rename. Mitigation: its own commit
  with `TitleEdit.test.tsx` and `tests/ui/test_session_head.py` unchanged and green.
- **Moving the clone client out of `Launch.tsx`** can break the window's clone. Mitigation:
  the move is its own task and commit, before the dialog uses it, with the window's vitest
  and `tests/ui/test_launch.py` clone tests green unchanged; the external round reads
  `cloneJob.ts` and the `Launch.tsx` diff in full (#949).
- **X3 forgets more on a confirmed removal** (sessions without a project). They are named in
  the preview and the CLI's list first; their folder goes with the removal, so they could
  not be resumed anyway.
- **A detached-HEAD check counts commits reachable from HEAD but no ref**: a HEAD on a
  commit a tag holds still counts (tags are not checked); it says more, never less.
- **The session's repository from its folder's last part** misnames a session whose folder
  is deeper (none today: a session in a project starts at a repository's root).

The plan with each task's tests: `docs/superpowers/plans/2026-10-23-project-page.md`.
