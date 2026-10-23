# The Project's Page Implementation Plan

**Goal:** The project's page lists its repositories and sessions, adds a repository by a
clone (with progress and cancel) or from scratch, deletes one after showing what goes, and
renames the project; the leftovers F2 and F3 (the shared unpushed check), X3, E2, M1, E1 and the
clone/scratch refusal's way to the page close with it.

**Architecture:** The page uses S4's routes as they are and one new route, `PATCH
/api/projects/{id}` (the CLI's `projects.rename`). The clone job client moves out of
`Launch.tsx` into `web/src/cloneJob.ts` (`useCloneJob`), used by the New session window and
the new Add repository dialog. The Repositories and Sessions blocks and the two dialogs
live in a new `web/src/ProjectRepos.tsx`; sessions come from the change feed. The core's
`_checkout_lines` (F2) and `removal`/`remove_repo` (X3) change for the CLI and the API at
once.

**Tech Stack:** Python 3.10+, FastAPI/pydantic, React/TypeScript (Vite, vitest), pytest
(unit, UI with Playwright's Chromium and the fake provider).

**Spec:** `openspec/changes/project-page/` (proposal AC-1..AC-16, `design.md` D1-D17, the
delta of `projects`) and `docs/superpowers/specs/2026-10-23-project-page-design.md` (the
human's view and the manual check). Mockup: the run's artifact `mockup-project-page.html`.

## Global Constraints

- Texts, verbatim (the spec's): `Repositories`, `+ Add repository`, `Start session`,
  `Delete`, `branch <branch>`, `detached HEAD`, `no remote`, `No repositories yet. A session
  works in one of the project's repositories: clone one or start one from scratch.`,
  `Sessions`, `No sessions in this project yet.`, `running <time>`, `stopped <time> ago`,
  `New session…`, `Rename`, `Add a repository to <title>`, `Clone from URL`, `From
  scratch`, `Git URL`, `Name`, `Branch`, `Clone`, `Create`, `Cancel clone`, `the clone was
  cancelled`, `Delete repository <name>?`, `Its folder <folder> is deleted with everything
  in it. This cannot be undone.`, `Work that is not on the remote`, `Sessions that are
  forgotten`, `— no project, started in this folder before projects`, `Delete repository`,
  `Type <name> to delete it`, `All its work is on the remote.`, `No session is
  forgotten.`, `Close`, `Tab takes the id · Enter to save · Esc to cancel`,
  `Enter to save · Esc to cancel`, `Deleting the project: not built yet (Projects, step S7b). Meanwhile: lado
  project delete <id>.`, `The title gives no id: type one.`, `⚠ No project <id> any more:
  choose one.`, `⚠ No repository <name> in <title> any more: choose one.`, `Open the project
  <title>`; the core's `detached HEAD with <n> commit[s] on no branch`, `<n> stash[es]`,
  ` (no project)`, `the project's folder`.
- The core's refusals are shown as the server's `detail`, never re-worded.
- One core function per action: the page adds through `POST /api/clones` / `POST
  /api/projects/{id}/repos`, removes through `DELETE …/repos/{name}`, renames through
  `projects.rename`; no second implementation (the brief's threshold: stop and ask).
- Nothing outside `projects/` is removed; nothing follows a link (S4's checks unchanged).
- `mcp_server.py`, `hooks.py`, `runtime.py`, `providers/` and the schema do not change.
- UI tests wait for states, never times (LAD-127).

## Review Focus

- A clone that ends while the dialog's poll fails or the server answers 404 (the
  window's rule moved into the hook): the folder there is reported, not lost (Task 4).
- A `DELETE` refused after a clean preview (a session started meanwhile): the dialog shows
  the refusal and keeps nothing removed (Task 6).
- A rename to the same text, to spaces only, or to a text over the limit: nothing sent,
  cleared, or the core's refusal under the field (Task 5).
- The feed's sessions of another project, or none, never show in the block (Task 6).
- `Launch.tsx`'s clone (Clone and start, Cancel clone, the beacon) behaves as before the
  move (Task 4: the window's tests unchanged).

## Task 1: The core: detached HEAD, stashes, the project folder as a repository, a worktree once (D10)

**Files:** Modify `src/lado/projects.py` (`_checkout_lines`). Test:
`tests/test_project_repos.py`.

Requirement → tests: "The unpushed check names commits on a detached HEAD and stashes" (a
repository with a detached HEAD and two commits no ref holds → `notes: detached HEAD with 2
commits on no branch`; one commit → `1 commit`; a detached HEAD on a commit `origin/main`
holds → no line; one stash → `backend: 1 stash`, two → `2 stashes`; joined with the other
findings by `; ` in the order uncommitted, branches, detached, stashes; a worktree on a
detached HEAD with a commit no ref holds → `<repo> (worktree <path>): detached HEAD with 1
commit on no branch`; `projects.unpushed` (the project's delete) shows the same); "lado project delete shows
unpushed work and needs --yes" (a project folder that is itself a repository with a commit
on a branch with no upstream → first line `the project's folder: …; branch main not
pushed`; `frontend-fix`, a worktree of `frontend` inside the project folder with an
uncommitted file → `frontend (worktree frontend-fix): uncommitted changes` once and no line
starting `frontend-fix:`; a worktree inside the folder of a repository outside it keeps its
own line).

- [ ] Tests first on real repositories in `tmp_path` (`git init`, `git commit
  --allow-empty`, `git checkout --detach`, `git stash push --include-untracked`), each
  failing; implement with `_git(entry, "symbolic-ref", "-q", "HEAD")` (a `_GitFailed` there
  means detached), `rev-list --count HEAD --not --branches --remotes` and `stash list`;
  `make test PYTEST_ARGS="-n0 tests/test_project_repos.py tests/test_projects_core.py"`;
  commit `The unpushed check names commits on a detached HEAD, stashes and a project folder
  that is a repository, and a worktree once (LAD-138)`.

## Task 2: The core and CLI: sessions without a project in a removed repository (D9)

**Files:** Modify `src/lado/projects.py` (`Removal.sessions` as `(name, open_runs,
project)`, `removal`, `remove_repo`), `src/lado/cli.py` (`_remove_repo`'s line),
`src/lado/server/models.py` (`SessionToForget.project: str | None`),
`src/lado/server/launch.py` (`repo_removal`). Test: `tests/test_project_repos.py`,
`tests/test_server_projects.py`.

Requirements → tests: "Removing a repository forgets its sessions without a project" (a
stopped session with `project=None` and its folder in the repository is in `removal().sessions`
with project None and is forgotten by `remove_repo(..., True)`; one whose folder is outside
the repository is not; a running one still refuses); "lado project repo remove shows what
goes and needs --yes" (the CLI prints `Sessions to forget: old-backend (no project)`, and
`shop-frontend (1 open run)` as before); "The server removes a project's repository" (the
preview's `sessions` carries `project`).

- [ ] Tests first; implement; `make test PYTEST_ARGS="-n0 -k 'repo'"`; commit `Removing a
  repository names and forgets its sessions from before projects (LAD-138)`.

## Task 3: The server: rename, the remote's repository name, gone, the refusals' project (D2, D4, D7, D12)

**Files:** Modify `src/lado/server/models.py` (`ProjectTitle`, `RemoteInfo.repo_name`,
`ProjectLaunch.gone`, `CloneTarget.project`, `ScratchTarget.project`),
`src/lado/server/app.py` (`PATCH /api/projects/{id}`), `src/lado/server/launch.py`
(`project_launch`'s `gone`, `scratch_target`), `src/lado/server/clones.py`
(`remote_info`, `target_info`); `web/openapi.json`, `web/src/api.gen.ts` by `make
web-types`. Test: `tests/test_server_projects.py`, `tests/test_server_clones.py`,
`tests/test_server_project_launch.py`, `tests/test_server_launch.py`.

Requirements → tests: "The server renames a project" (set `Shop EU` → answer and `projects.get`
agree; `""` and null clear; unknown 404; a title over `runtime`'s limit 400 with the core's
text; without the change token refused; the id and folder unchanged); "The Project way says
when the project or repository asked is gone" (`?project=gone` → `gone: "project"` and the
server's choice; `?project=shop&repo=gone` → `gone: "repo"`; both present → null; nothing
asked → null); "Folder's refusal inside a project leads to the project" (`GET
/api/clone-target` and `GET /api/scratch-target` for `<ws>/projects/shop/admin` carry
`project: {id: "shop", title: "Shop", repo: null}`; outside `projects/` null);
`POST /api/remote-branches` for `file://…/admin.git` answers `repo_name: "admin"`.

- [ ] Tests first; implement; `make web-types`; `make web`; commit `The server renames a
  project and tells the page what it needs (LAD-138)`.

## Task 4: The clone job hook out of New session (D3)

**Files:** Create `web/src/cloneJob.ts`, `web/src/cloneJob.test.ts`; modify
`web/src/Launch.tsx` (Clone and start uses the hook).

**Interfaces:** `useCloneJob(): { job: CloneJob | null; run(start: CloneStart, isThere:
(job: CloneJob) => Promise<boolean>): Promise<{ done: CloneJob } | { ended: "cancelled" |
"failed" | "away" | "gone"; job: CloneJob }>; cancel(): Promise<void> }` — `run` starts the
job, polls every 500 ms, asks again after a failed poll, and on a 404 asks `isThere(job)`
(`away` when the clone is there, `gone` else); the `pagehide` beacon is bound while `job`
runs. The window's `isThere` is today's `getCloneTarget(url, path)` with state `same_repo`;
the dialog's is `getProject(id)` listing the name (a target inside `projects/` answers
`in_project` to `clone-target`, so the window's check would not do for it).

Tests: the hook with fake `startClone`/`getClone` and `isThere`, and fake timers: done,
failed, cancelled, a failed poll then done, a 404 with the clone there (`away`) and not
(`gone`), the beacon sent on `pagehide` while running and not after.

- [ ] Tests first; move the code; `web/src/Launch.test.tsx` passes unchanged; `make web`;
  `uv run pytest -m ui tests/ui/test_launch.py -k clone`; commit `The clone job client is
  one hook (LAD-138)`.

## Task 5: The page's head: rename and New session… (D2, D6, D15)

**Files:** Modify `web/src/TitleEdit.tsx` (generic: `name`, `title`, `save`, the hints;
its session callers in `Sessions.tsx` and `SessionDetails.tsx` pass `setSessionTitle`),
`web/src/Projects.tsx` (the head with `TitleEdit`, the S7b line, the S6a stub gone),
`web/src/Launch.tsx` (`LaunchMode`'s `repo`), `web/src/api.ts` (`renameProject`),
`web/src/styles.css`. Test: `web/src/TitleEdit.test.tsx`, `web/src/Projects.test.tsx`.

- [ ] First, alone: `TitleEdit` made generic; `TitleEdit.test.tsx` and
  `tests/ui/test_session_head.py` green unchanged but for the props; commit `The title
  field takes any name and save (LAD-138)`.

Requirements → tests: "The project's page shows the project and what is not built yet" (the
head, the facts line, the S7b line naming `lado project delete shop`; no `Not built yet:
the repositories`); "The project's page opens New session on its project" (`New session…`
→ `launch({kind: "new", project: "shop"})`); "The project's page renames the project in
place" (Rename and a click on the title open the field; Enter sends `PATCH` and shows the
answer; blur saves; Esc sends nothing; the same text sends nothing; empty sends `""` and
shows the id; a 400 shows its text under the field, the field open; the list is reloaded);
"Tab takes the project's id into the title field" (untitled `shop-eu`: `sh` → grey `op-eu`,
the hint `Tab takes the id · Enter to save · Esc to cancel`, Tab and → take it, nothing
sent; a titled project opens selected without grey).

- [ ] Tests first; implement; `make web`; commit `The project's page renames the project
  (LAD-138)`.

## Task 6: Repositories, sessions, Add repository and Delete (D5, D8, D11, D15)

**Files:** Create `web/src/ProjectRepos.tsx`, `web/src/ProjectRepos.test.tsx`; modify
`web/src/Projects.tsx` (uses it), `web/src/api.ts` (new: `addProjectRepo`, `getRepoRemoval`,
`removeProjectRepo`), `web/src/projectFakes.ts`, `web/src/styles.css`.

Requirements → tests: "The project's page lists its repositories" (rows with branch,
`detached HEAD`, remote, `no remote`; the empty state with the primary button); "Start
session opens New session on the repository" (`launch({kind: "new", project: "shop",
repo: "backend"})`); "The project's page lists its sessions" (from a fake feed: only this
project's, running first by `running_since`, then stopped by `stopped_at`; title and name;
folder's last part; the empty line; a feed change shows without a read); "The UI adds a
repository by a clone or from scratch" (scratch → `POST …/repos` with `{name}`, the dialog
closes and the project is read; a 400 under Name, the dialog kept); "Add repository clones a
URL into the project" (branches listed → Name from `repo_name` until edited, Clone off until
listed; the body `{url, project, name, branch}`); "Add repository shows a running clone and
can cancel it" (fields off, Esc/Cancel/× do nothing while running, `Cancel clone` → `the
clone was cancelled`, a failed clone's text and hint); "The UI deletes a repository after
showing what goes" (the preview's lines and sessions, the `no project` mark, `Delete
repository` → `DELETE` and the page updated from the answer; with unpushed lines the field
`Type backend to delete it` shows and the button is off until `backend` is typed exactly
(`Backend`, `backend ` keep it off); with none no field and the button on; a preview 400 and
a `DELETE` 400 → the text and only Close).

- [ ] Tests first; implement as frames 1, 4–9 and 13–14 of the mockup; `make web`; commit
  `The project's page adds, lists and deletes repositories and lists sessions (LAD-138)`.

## Task 7: E1, the refusals' button, E2 and M1 (D7, D12, D13, D14)

**Files:** Modify `web/src/LaunchProject.tsx` (the `gone` warning), `web/src/Launch.tsx`
(`Open the project <title>` for Clone into and Create in), `web/src/Projects.tsx`
(`NewProjectDialog`'s note, `NoProject`), `web/src/styles.css` (`.projects` at ≤ 900 px).
Test: `web/src/LaunchProject.test.tsx`, `web/src/Launch.test.tsx`,
`web/src/Projects.test.tsx`.

Requirements → tests: "The Project way says when the project or repository asked is gone"
(both texts; none when `gone` is null); "Folder's refusal inside a project leads to the
project" (Clone into's and Create in's refusal with `project` shows the button; it closes
the window and navigates to `/projects/shop`; without `project` no button); "New project's
id follows the title until edited" (`!!!` → `The title gives no id: type one.`, Create off);
"A narrow desktop window stacks the Projects section" (`NoProject` renders nothing under a
matched 900 px query).

- [ ] Tests first; implement; `make web`; commit `New session says when a project is gone
  and its refusals lead to the project's page (LAD-138)`.

## Task 8: End to end in the browser (D16)

**Files:** Create `tests/ui/test_project_page.py`; move the slow clone fixture from
`tests/ui/test_launch.py` to `tests/ui/conftest.py`.

Tests (Chromium, the fake provider, a bare repository by `agent_helpers.bare_remote`,
temp `LADO_HOME`/`LADO_REPOS`): the rows with branch and remote (AC-1); From scratch `web`
(AC-4); a clone from the bare repository with progress, the row with its branch (AC-5);
Cancel clone with the slow clone, no folder left (AC-6); Start session on a row → `Start in
Shop` → the session's head reads `project Shop` and `lado ls` shows it in `shop` (AC-2);
the Sessions block shows it running, then stopped after Stop (AC-3); Delete of a repository
with an unpushed commit: the line in the dialog, the button off until the name is typed,
then the folder gone (AC-7); Delete of a clean repository without typing (AC-7); Delete while
its session runs: the refusal and Close (AC-7); rename to `Shop EU` in the head, the list
and the session's head, and Tab taking the id in an untitled project (AC-11); `!!!` in New project (AC-12); a 390 px desktop window
without touch: no `Select a project` (AC-13); E1 after the project is deleted by the core
while the page is open (AC-14); Clone into `<ws>/projects/shop/admin` → `Open the project
Shop` opens the page (AC-15); the phone at 390 px, light and dark, a screenshot each.

- [ ] Write; `uv run pytest -m ui tests/ui/test_project_page.py tests/ui/test_launch.py`;
  commit `UI tests of the project's page (LAD-138)`.

## Task 9: Docs and the regression run (D17)

**Files:** Modify `docs/design/ui.md` (Projects: the page, its blocks and dialogs, the S6a
stub gone; Launch: E1 and the clone/scratch refusal's button), `docs/design/projects.md`
(S7a built, S7b next; "The UI", the step table), `docs/cli.md` (`project repo remove`'s
` (no project)`), `CHANGELOG.md` (one Features line under `## 0.43.0 (unreleased)`).

- [ ] Write; `make lint`; `openspec validate project-page --strict`; commit `Docs of the
  project's page (LAD-138)`.
- [ ] The regression run, the settings' Checks: `make lint`; `make test`; `make web`;
  `uv run pytest -m ui` on `tests/ui/test_project_page.py`, `tests/ui/test_launch.py`,
  `tests/ui/test_launch_project.py`, `tests/ui/test_projects_section.py`; `openspec validate
  --specs --strict`; the trial archive (`openspec archive project-page -y` in a scratch copy,
  then `openspec validate --specs --strict` there); CI's `ci-ok`.
