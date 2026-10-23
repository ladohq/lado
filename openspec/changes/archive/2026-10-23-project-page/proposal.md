Task: LAD-138

## Why

Step S7a of the epic LAD-116 (`docs/epics/lad-116/plan.md`, step S7; the model is
`docs/design/projects.md` and the concept `projects-concept`, sections "UI" and
"Deletion"). After S6b a project is made, given its variables and secrets, and started in
from the browser, but its page is still the S6a stub: it does not list the project's
repositories or sessions, and a repository is added to a project, removed from it, or the
project renamed only from the CLI. Since the human's amendment #1282 the New session window
only chooses a repository, so a human who runs LADO from the browser (or in LADO's image)
cannot put a repository into a project at all: an empty project is a dead end.

The root cause: the core and the API for adding and removing a project's repositories exist
(S4), but no screen uses them, and there is no API to rename a project.

The human split S7 at its design (#1347, option 1): **S7a** (this change) is the project's
page with its repositories, its sessions, adding and removing a repository, and renaming
the project; **S7b** (LAD-139, derived from LAD-138) is deleting the project.

## What Changes

- **The project's page** (`/projects/<id>`), in place of the S6a stub line:
  - the head: the title with **Rename** in place (the id and folder stay), the id, and a
    button `New session…` that opens New session in Project with this project;
  - a block **Repositories**: each repository of the project as the disk has it (name,
    branch or `detached HEAD`, remote or `no remote`), with **Start session** (New session
    in Project with this project and repository chosen) and **Delete**, and `+ Add
    repository`; an empty project shows `No repositories yet…` and a primary `+ Add
    repository` in the block;
  - a block **Sessions**: the project's sessions from the change feed, running first, each
    a link with its status mark, its repository and its time;
  - the warning, the line on who gets new values, Variables and Secrets as in S6a;
  - at the bottom, until S7b, `Deleting the project: not built yet (Projects, step S7b).
    Meanwhile: lado project delete <id>.`
- **Add a repository**, a dialog with **Clone from URL | From scratch**: a clone takes Git
  URL, Name (the URL's repository name until edited) and Branch (the remote's branches) and
  runs as the New session window's clone does (progress, `Cancel clone`, the beacon on a
  page that goes away) through `POST /api/clones` with `project` and `name`; from scratch
  takes Name and calls `POST /api/projects/{id}/repos`. The core's refusals show verbatim.
  On success the dialog closes and the page shows the repository.
- **Delete a repository**, a dialog that reads `GET …/repos/{name}/removal` and shows the
  folder, the work not on the remote and the sessions forgotten, then `Delete repository`
  sends `DELETE …/repos/{name}`; when there is work not on the remote the button is on only
  once the repository's name is typed (#1352); a refusal (a running session) shows verbatim
  with Close.
- **Rename**: `PATCH /api/projects/{id}` with `{title}` (new) renames through
  `projects.rename`, the function of `lado project rename`; the page edits the title in
  place as a session's title is edited (Enter or leaving saves, Esc cancels, empty clears,
  Tab takes the project's id as the session's field takes its name, #1352).
- **Leftovers of earlier steps** (`docs/epics/lad-116/plan.md`, S7's notes):
  - S2's F2 and F3 in the shared unpushed check (#1352: closed here, S7b only shows them):
    commits on a detached HEAD that no branch or remote holds, and stashes, for both
    removals; for the project's delete also a project folder that is itself a repository,
    and a worktree inside the project folder listed once, not twice;
  - S4's X3: removing a repository names and forgets the stopped sessions without a project
    whose folder is in it (from before S3), as it does the project's own;
  - S6a's E2: New project says why Create is off when the title gives no id;
  - S6a's M1: in a desktop window of at most 900 px the Projects section stacks as Sessions
    does, without the squeezed `Select a project` pane;
  - S6b's E1: New session opened for a project or repository that is gone says so instead
    of silently choosing another;
  - S6b's leftover: the refusals of Clone into and Create in inside a project gain `Open the
    project <title>`, which opens the project's page, where the repository is added.
- **Docs**: `docs/design/ui.md` (Projects: the page; Launch: E1 and the clone and scratch
  refusals), `docs/design/projects.md` (what is built, the step table), `docs/cli.md`
  (`project repo remove` names sessions without a project), CHANGELOG under `## 0.43.0
  (unreleased)`.

## Acceptance criteria

- AC-1. `/projects/shop` lists the repositories of `GET /api/projects/shop` by name, each
  with its branch (`detached HEAD` without one) and remote (`no remote` without one), and
  the buttons `Start session` and `Delete`.
- AC-2. `Start session` on `frontend` opens New session in Project with `Shop` and
  `frontend` chosen; its start makes a session of project `shop` in that repository.
- AC-3. The block Sessions lists the feed's sessions whose `project` is `shop`, running
  first (latest started first), then stopped (latest stopped first), each a link to the session with its status mark and its
  repository's folder name; it follows the feed without a reload; with none it says `No
  sessions in this project yet.`
- AC-4. `+ Add repository` → From scratch → Name `web` → Create makes
  `<ws>/projects/shop/web` with one empty commit; the dialog closes and the row `web` shows.
  A taken or invalid name shows the core's text under Name, and nothing is made.
- AC-5. `+ Add repository` → Clone from URL with a reachable URL lists its branches, fills
  Name with the URL's repository name until edited, and `Clone` clones into
  `<ws>/projects/shop/<name>` with progress; the dialog closes and the row shows with the
  branch chosen.
- AC-6. `Cancel clone` stops the clone: no folder is left, the dialog stays open and says
  `the clone was cancelled`; while the clone runs the dialog cannot be closed by Esc or
  Cancel, and a page that goes away cancels it.
- AC-7. `Delete` on a repository opens a dialog with its folder, every line of the
  removal's `unpushed` and every session it forgets (one without a project marked so); the
  dialog's `Delete repository` removes the folder and forgets those sessions, and the row
  goes. With unpushed lines the button is off until the repository's name is typed; with
  none it is on at once. A running session in the repository shows the core's refusal and
  only Close.
- AC-8. The removal's unpushed lines name `detached HEAD with <n> commit[s] on no branch`
  and `<n> stash[es]`, for `lado project repo remove` and `lado project delete` alike;
  `lado project delete` also lists a project folder that is itself a repository (`the
  project's folder: …`) and a worktree inside the project folder once.
- AC-9. A stopped session without a project whose folder is inside the repository is named
  by `lado project repo remove` (`Sessions to forget: old-backend (no project)`) and by the
  removal API, and is forgotten with `--yes` / `DELETE`.
- AC-10. `PATCH /api/projects/shop` with `{title: "Shop EU"}` and the change token stores
  the title as `lado project rename` does and answers the project; an empty or null title
  clears it; an unknown project is 404, a refused title 400 with the core's text; without
  the token it is refused.
- AC-11. Renaming on the page shows the new title in the head, the project list and the
  head of the project's sessions; Esc keeps the old title; in an untitled project Tab takes
  the id into the field.
- AC-12. New project with the title `!!!` shows under Id why Create is off.
- AC-13. A desktop window 390 px wide without touch shows the Projects list over the
  project, without a `Select a project` pane beside it.
- AC-14. New session opened for a project that is gone (or a repository that is gone) shows
  `⚠ No project <id> any more: choose one.` (`⚠ No repository <name> in <title> any more:
  choose one.`) under the field, with the server's choice below it.
- AC-15. Clone into or Create in a folder inside a project shows the refusal with `Open the
  project <title>`, which closes the window and opens `/projects/<id>`.
- AC-16. `docs/design/ui.md`, `docs/design/projects.md`, `docs/cli.md` and CHANGELOG say
  it; the settings' checks and CI are green.

## Out of scope

- **Deleting the project** (its API, dialog with the id typed, the refusal while sessions
  run) and the leftovers that live in that path: F5 and S3's G1 (a
  project folder that is a link), E3 (an unreadable project folder), S5a's F5 (`set` racing
  `delete`), X3 for the project, and the canary over the delete: step S7b (#1347), LAD-139,
  derived from LAD-138. S7b only checks that its dialog shows F2's and F3's lines.
- **Links in the project's folder**: not repositories, not listed, and not removed from the
  page; they are made only by hand, and `lado project repo remove` removes one.
- **Sessions over several repositories** and the "all repositories" item: the concept's
  "Not now".
- **Repository extras in the database** (order, description, "clone again?"): concept
  option C, after the epic.
- **Starting a session from Add repository** in one step: Start session is on the row the
  dialog leaves; the window's start and the dialog stay apart (#1282).
- **A name check while typing** in Add repository: the core's refusal comes at once with
  the request (the clone job checks the folder before git runs), so a second request per
  keystroke buys nothing.

## Impact

- Code: `src/lado/projects.py` (`unpushed`, `_checkout_lines`, `removal`, `remove_repo`),
  `src/lado/cli.py` (`_remove_repo`'s line), `src/lado/server/app.py` (`PATCH
  /api/projects/{id}`), `src/lado/server/models.py` (`ProjectTitle`, `RemoteInfo.repo_name`,
  `SessionToForget.project`, `ProjectLaunch.gone`, `CloneTarget.project`,
  `ScratchTarget.project`), `src/lado/server/launch.py`, `src/lado/server/clones.py`;
  `web/src/Projects.tsx`, a new `web/src/ProjectRepos.tsx` (the blocks and dialogs), a
  shared clone-job hook out of `web/src/Launch.tsx`, `web/src/LaunchProject.tsx`,
  `web/src/api.ts`, `web/src/styles.css`, `web/openapi.json`, `web/src/api.gen.ts`.
- No schema migration; no change to the agents' protocol, `mcp_server.py`, `hooks.py`,
  `runtime.py` or `providers/`.
- Version: minor (a new API route), already `0.43.0 (unreleased)`.
