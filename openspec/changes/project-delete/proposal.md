Task: LAD-139

## Why

Step S7b of the epic LAD-116 (`docs/epics/lad-116/plan.md`, step S7, split at the design
of S7a by the human's word #1347), the last step of the plan. The model is
`docs/design/projects.md` ("Deleting", "The UI") and the concept `projects-concept`
("Deletion": deleting is confirmed in the UI by typing the project's id; LADO shows first
what will be lost; it refuses while a session of the project runs).

After S7a the project's page lists the project's repositories and sessions, adds and
removes a repository and renames the project, but a project is deleted only with `lado
project delete`: its page ends with `Deleting the project: not built yet`. A human who
runs LADO from the browser (or in LADO's image) cannot delete a project at all.

The root cause: the core deletes a project (`projects.delete`, S2, S3, S5b), but there is
no API that previews or performs it, so no screen can; and the CLI shows its preview from
two calls (`sessions_to_forget`, `unpushed`) that an API would have to repeat. The delete
path also keeps leftovers of earlier steps that a dialog would show the human: a project
folder that is a link is announced as removed "with everything in it" though only the link
goes, and a running session in the link's target blocks it (S2's F5, S3's G1); an
unreadable folder ends in a traceback (S2's E3); a project folder that is itself a
repository always shows `uncommitted changes` (S7a's F2); a set racing the delete ends in
`IntegrityError` (S5a's F5); sessions without a project in the folder are not forgotten
(S4's X3 for the project). S7a's F1 (leaving the page during Add repository's clone does
not cancel it) is the last leftover of the page.

## What Changes

- **One preview in the core**, `projects.deletion(id)`: what deleting the project does —
  its folder (a folder, a link with its target, or not found), the work not on the remote
  of all its repositories (S7a's `unpushed` lines), the sessions forgotten (its own and,
  in a real folder, the stopped sessions without a project inside it), and the names of
  its variables and secrets; refused while a session of the project, or one in its real
  folder, is not stopped. `projects.delete` acts on it, and `lado project delete` prints
  it: one truth for the CLI, the API and the dialog.
- **The API**: `GET /api/projects/{id}/deletion` (the preview, nothing changes) and
  `DELETE /api/projects/{id}` (`projects.delete(id, yes=True)`) behind the change token.
- **The project's page**: a block `Delete project` at its bottom in place of the not-built
  line, its button `Delete project…` opening the dialog `Delete project <title>?`: the
  folder and what goes with it, `Work that is not on the remote`, `Sessions that are
  forgotten`, `Variables and secrets that are deleted` (names only), the field `Type <id>
  to delete it` (always), and `Delete project`; a refusal verbatim with only Close; after
  the delete the list of projects opens.
- **Leftovers**:
  - S2's F5 and S3's G1: a project folder that is a link is announced as a link (`only the
    link is deleted, <target> and everything in it stay`), its target's work is not
    listed, and only the project's own sessions are matched and forgotten; nothing is
    followed through the link;
  - S2's E3: an unreadable project folder gives the line `the project's folder: could not
    check: <reason>` in the preview (and the core's refusal when it cannot be removed),
    never a traceback or a 500;
  - S5a's F5: `lado project set` (and `--secret`, and the API's `PUT`) racing a delete says
    `unknown project "<id>"` (404 in the API), never `IntegrityError`, and leaves no secret
    file of a deleted project behind;
  - S7a's F2: the repositories inside a project folder that is itself a repository are not
    its `uncommitted changes`;
  - S4's X3 for the project: the delete names and forgets the stopped sessions without a
    project inside the project's real folder, as removing a repository does;
  - S7a's F1: Add repository's clone is cancelled when the page goes away inside the app
    (Back, another section), not only when the browser's page does;
  - S2's F2 and F3 (closed in S7a): the dialog shows their lines.
- **The canary** (`tests/integration/test_project_secrets_canary.py`) goes on through the
  delete: the preview's and the delete's answers, the feed and the logs hold no secret's
  value, and the secrets' folder is gone.
- **Docs**: `docs/design/ui.md` (Projects: the block and the dialog, F1),
  `docs/design/projects.md` (Deleting and The UI built, the step table), `docs/cli.md`
  (`project delete`'s texts for a link and a missing folder, sessions without a project),
  CHANGELOG under `## 0.43.0 (unreleased)`.

## Acceptance criteria

- AC-1. The bottom of `/projects/shop` is the block `Delete project` with one sentence
  and the button `Delete project…`; the line `Deleting the project: not built yet` is gone.
- AC-2. `Delete project…` opens `Delete project Shop?` from `GET
  /api/projects/shop/deletion`: the folder, every unpushed line of every repository of the
  project (uncommitted changes, branches not pushed, commits on a detached HEAD, stashes,
  workers' worktrees), every session forgotten (`(<n> open run[s])`; one without a project
  marked so) and every variable and secret by name (a secret marked so, no value).
- AC-3. `Delete project` stays off until `shop` is typed exactly, with or without unpushed
  work; then it sends `DELETE /api/projects/shop`, and the browser shows `/projects` without
  `shop`; the folder, `<LADO_HOME>/projects/shop`, the sessions and the record are gone.
- AC-4. While a session of `shop`, or a session without a project inside its folder, is
  not stopped, the dialog shows `project shop has sessions not stopped: <names>; stop them
  first with lado stop <name>` and only Close; a session started while the dialog is open
  gives the same at `Delete project`, and nothing is deleted.
- AC-5. `GET /api/projects/{id}/deletion` and `DELETE /api/projects/{id}` call the core's
  `projects.deletion` and `projects.delete`, the functions `lado project delete` uses:
  an unknown project is 404, a refusal 400 with the core's text; `DELETE` without the
  change token is refused and changes nothing.
- AC-6. A project folder that is a link to `/srv/shop`: the dialog and `lado project
  delete` say that only the link is deleted and `/srv/shop` stays, list no work of
  `/srv/shop`, are not blocked by a running session without a project in `/srv/shop`, and
  the delete leaves `/srv/shop` and its sessions without a project as they were.
- AC-7. An unreadable project folder gives `the project's folder: could not check:
  <reason>` in the preview and the CLI's list, never a traceback or a 500.
- AC-8. `lado project set` or `PUT …/variables/{name}` or `…/secrets/{name}` for a project
  deleted meanwhile answers `unknown project "<id>"` (exit 1, 404) and leaves no row and no
  secret file of it.
- AC-9. A project folder that is a repository holding the project's repositories, clean
  and pushed, gives no `the project's folder: uncommitted changes` line; a file changed in
  the root repository itself still does.
- AC-10. A stopped session without a project inside the project's folder is named by the
  preview and `lado project delete` (`(no project)`) and forgotten by the delete.
- AC-11. Leaving the project's page (Back, another section) while Add repository's clone
  runs cancels the clone job at once; no folder is left.
- AC-12. The canary: no secret's value in the answers of the preview and the delete, in
  the feed or in the logs; `<LADO_HOME>/projects/shop` is gone after the delete.
- AC-13. `docs/design/ui.md`, `docs/design/projects.md`, `docs/cli.md` and CHANGELOG say
  it; the settings' checks and CI are green.

## Out of scope

- **A trash or an undo of a delete**: new behaviour beyond the concept ("LADO is no
  store": what is valuable is on a remote); a task of its own if wanted.
- **S7a's minors F3, F4, X3, X5** (Cancel clone after the end, `tmux_gone` called running,
  a preview stale at the `DELETE`, Name kept after a failed URL): the plan's Later,
  cosmetic. The same staleness holds for the project's preview, as for the CLI's preview
  then `--yes`: the core checks the sessions again at the delete.
- **Sessions over several repositories**: the concept's "Not now".
- **Repository extras in the database**: concept option C, after the epic.
- **Deleting a link in the project's folder from the page**: links are not listed (S7a);
  the project's delete removes them as links with the folder.
- **Listing the work in a link folder's target**: it is not lost, so it is not shown.

## Impact

- Code: `src/lado/projects.py` (`deletion`, `Deletion`, `delete`, `unpushed`,
  `_checkout_lines`, `set_variable`, `set_secret`; `sessions_to_forget` folded into
  `deletion`), `src/lado/cli.py` (`project delete`'s output), `src/lado/server/app.py`
  (two routes), `src/lado/server/models.py` (`ProjectDeletion`),
  `src/lado/server/launch.py`; `web/src/Projects.tsx`, a new `web/src/ProjectDelete.tsx`,
  `web/src/cloneJob.ts`, `web/src/api.ts`, `web/src/styles.css`, `web/openapi.json`,
  `web/src/api.gen.ts`.
- No schema migration; no change to the agents' protocol, `mcp_server.py`, `hooks.py`,
  `runtime.py` or `providers/`.
- Version: minor (new API routes), already `0.43.0 (unreleased)`.
