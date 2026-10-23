# Deleting a Project Implementation Plan

**Goal:** A project is deleted from its page after the human sees what goes and types its
id, through the core function `lado project delete` uses; the delete path's leftovers of
S2–S7a (F5, G1, E3, X3, S5a's F5, S7a's F2 and F1) close with it, and the canary covers
the delete.

**Architecture:** The core gets one preview, `projects.deletion(id) -> Deletion`, which
`projects.delete` acts on, `lado project delete` prints and two new routes expose (`GET
/api/projects/{id}/deletion`, `DELETE /api/projects/{id}`). The page's bottom gets a block
and a dialog in a new `web/src/ProjectDelete.tsx`, built as S7a's `DeleteRepoDialog`. The
leftovers are fixed where they live: `unpushed`/`_checkout_lines` (E3, F2), `deletion`'s
session rule (G1, X3), `set_variable`/`set_secret` (S5a's F5), `useCloneJob` (F1).

**Tech Stack:** Python 3.10+, FastAPI/pydantic, React/TypeScript (Vite, vitest), pytest
(unit, integration with the fake agent, UI with Playwright's Chromium and the fake
provider).

**Spec:** `openspec/changes/project-delete/` (proposal AC-1..AC-13, `design.md` D1-D13,
the delta of `projects`) and `docs/superpowers/specs/2026-10-23-project-delete-design.md`
(the human's view and the manual check). Mockup: the run's artifact
`mockup-project-delete.html`.

## Global Constraints

- Texts, verbatim (the spec's): `Delete project`, `Delete project…`, `Deletes its folder
  with every repository in it, its sessions, variables and secrets. Refused while a
  session of the project runs.`, `Delete project <title>?`, `Its folder <folder> is
  deleted with everything in it, and so are its sessions, variables and secrets. This
  cannot be undone.`, `Its folder <folder> is a link to <target>: only the link is
  deleted, <target> and everything in it stay. Its sessions, variables and secrets are
  deleted. This cannot be undone.`, `Its folder <folder> is not found. Its sessions,
  variables and secrets are deleted. This cannot be undone.`, `Work that is not on the
  remote`, `All its work is on the remote.`, `Sessions that are forgotten`, `No session is
  forgotten.`, `— no project, started in this folder before projects`, `Variables and
  secrets that are deleted`, `— secret`, `No variables or secrets.`, `Type <id> to delete
  it`, `Cancel`, `Close`; the core's `deleting project <id> removes the link <folder> only,
  not its target <target>`, `deleting project <id> removes its record (its folder <folder>
  is not found)`, `the project's folder: could not check: <reason>`, `unknown project
  "<id>"`, ` (no project)`.
- The core's refusals are shown as the server's `detail`, never re-worded.
- One core function: the API and the CLI preview through `projects.deletion` and delete
  through `projects.delete`; no second implementation (the brief's threshold: stop and
  ask).
- Nothing is removed outside `<workspace>/projects/<id>` and `<LADO_HOME>/projects/<id>`;
  nothing follows a link (a folder that is a link loses the link only; the data folder's
  link check stays first).
- `mcp_server.py`, `hooks.py`, `runtime.py`, `providers/` and the schema do not change.
- No secret's value in any answer, line or log: the preview carries secret names only.
- UI tests wait for states, never times (LAD-127).
- `tests/ui/test_launch.py`, `web/src/Launch.test.tsx` and the `ProjectRepos` tests change
  only for F1, and the PR says why.

## Review Focus

- A project folder that is a link to another project's folder: `delete --yes` unlinks
  only, the neighbour's folder, sessions and repositories stay (Task 1).
- A session started between the preview and `Delete project`: the `DELETE` is 400, the
  dialog shows the refusal, nothing is removed (Tasks 3, 4).
- A project whose folder is missing (workspace changed): the preview says `not found`,
  `Delete project` after the id removes the record, sessions and secrets only (Tasks 1, 4).
- An id typed with a trailing space or another case (`Shop`): the button stays off
  (Task 4).
- The delete of a project whose data folder holds a link: the core refuses before
  anything goes; the dialog shows that text with Close, and the folder stays (Tasks 1, 4).

---

## Task 1: The core preview and the delete it acts on (D1–D5)

**Files:** Modify `src/lado/projects.py` (`Deletion`, `deletion`, `delete`, `unpushed`;
remove `sessions_to_forget`), `src/lado/cli.py` (`cmd_project`'s delete branch). Test:
`tests/test_projects_core.py`, `tests/test_cli.py`.

**Interfaces:**
- Produces: `projects.Deletion` (frozen dataclass: `id: str`, `path: Path`, `kind:
  Literal["folder", "link", "missing"]`, `target: str | None`, `sessions: list[tuple[str,
  int, str | None]]`, `unpushed: list[str]`, `variables: list[str]`, `secrets:
  list[str]`); `projects.deletion(id: str) -> Deletion` (NoSuchProject; ProjectError
  while busy); `projects.delete(id: str, yes: bool) -> None` unchanged in signature.

Requirements → tests:
- "lado project delete shows unpushed work and needs --yes": the existing scenarios kept;
  a stopped session with `project=None` in `<ws>/projects/shop/site` → `Sessions to
  forget: old-site (no project)`; an unreadable folder (`chmod 000`, `pytest.skip` when
  `os.geteuid() == 0`) → `  the project's folder: could not check: Permission denied`,
  exit 1, no `Traceback` in stderr.
- "lado project delete --yes removes the folder, then the record": `old-site` forgotten
  by `delete(..., True)`; a session with `project=None` outside the folder stays.
- "lado project delete removes nothing outside the project folder": a link to
  `home/srv-shop` → `deletion().kind == "link"`, `target` as written, `unpushed == []`
  even with a dirty repository in the target; `delete("shop", False)` raises `deleting
  project shop removes the link <folder> only, not its target <target>; run again with
  --yes`; a running session with `project=None` in the target neither refuses nor is
  forgotten; a project's own running session still refuses; a link to another project's
  folder: after `delete --yes` that project's folder and record are intact.
- "lado project delete refuses while a session in the project's folder runs": unchanged
  scenarios green on `deletion` and `delete`.
- Missing folder: `kind == "missing"`, the text `removes its record (its folder <folder>
  is not found)`.
- `deletion` lists `variables` and `secrets` by name; no value in `repr(deletion(...))`.

- [ ] **Step 1: Tests first**, each failing (rename the old `sessions_to_forget` test to
  `deletion`'s).
- [ ] **Step 2: Implement.** The sessions rule (D2):

```python
def deletion(id: str) -> Deletion:
    get(id)
    path = folder(id)
    if path.is_symlink():
        kind, target = "link", os.readlink(path)
    elif os.path.lexists(path):
        kind, target = "folder", None
    else:
        kind, target = "missing", None
    real = Path(os.path.realpath(path))

    def inside(sess: state.Session) -> bool:
        # Never through a link: its target is not deleted.
        return kind == "folder" and Path(os.path.realpath(sess.repo)).is_relative_to(real)

    every = state.list_sessions()
    busy = [
        s.name
        for s in every
        if (s.project == id or inside(s))
        and runtime.session_status(s) != runtime.SessionStatus.STOPPED
    ]
    if busy:
        raise ProjectError(
            f"project {id} has sessions not stopped: {names(busy)}; stop them first with "
            "lado stop <name>"
        )
    # The project's own, and those of no project in its folder: the path is a safety
    # check, never how LADO learns another project's session.
    sessions = sorted(
        (s.name, len(state.list_runs(s.name, open_only=True)), s.project)
        for s in every
        if s.project == id or (s.project is None and inside(s))
    )
    return Deletion(
        id,
        path,
        kind,
        target,
        sessions,
        unpushed(path) if kind == "folder" else [],
        sorted(state.project_variables(id)),
        project_secrets.names(id) or [],
    )
```

  `delete` starts with `found = deletion(id)`, builds the refusal text by `found.kind`
  (D3), forgets `found.sessions`' names; the rest of its order is unchanged. `unpushed`
  wraps `sorted(project_folder.iterdir())` in `try`/`except OSError as error` and returns
  `lines + [f"the project's folder: could not check: {error.strerror or error}"]`. The CLI
  prints from `found` (` (no project)` as `_remove_repo`).
- [ ] **Step 3:** `make test PYTEST_ARGS="-n0 tests/test_projects_core.py tests/test_cli.py"`.
- [ ] **Step 4: Commit** `One preview of a project's delete for the CLI and the API; a
  linked or unreadable folder says what is true (LAD-139)`.

## Task 2: The core's leftovers: F2 and S5a's F5 (D6, D7)

**Files:** Modify `src/lado/projects.py` (`_checkout_lines`, `unpushed`, `set_variable`,
`set_secret`). Test: `tests/test_project_repos.py`, `tests/test_projects_core.py`,
`tests/test_project_variables_core.py`.

**Interfaces:**
- Consumes: `projects.unpushed(project_folder: Path) -> list[str]` (Task 1's E3 kept).
- Produces: `_checkout_lines(entry, base, label=None, skip: list[str] = [])`.

Requirements → tests:
- "The unpushed check does not count a project's repositories as its folder's changes":
  `<ws>/projects/shop` a clean repository with one commit pushed to a bare remote, holding
  the repositories `frontend` and `backend` (each pushed) → `unpushed()` is `[]`; an
  uncommitted `README.md` in the root → `["the project's folder: uncommitted changes"]`; a
  root that tracks `frontend` as a gitlink and `frontend` moved on a pushed commit → no
  root line.
- "A change to a project deleted meanwhile is refused as unknown": monkeypatch
  `projects.check_variable` to delete the record (`state.delete_project`) before the write
  → `set_variable` raises `NoSuchProject('unknown project "shop"')` and
  `state.project_variables("shop") == {}`; monkeypatch `project_secrets.write` to write
  then delete the record → `set_secret` raises `NoSuchProject` and the file is gone; the
  CLI `lado project set` prints `lado: unknown project "shop"`, exit 1, no `Traceback`.

- [ ] **Step 1: Tests first**, each failing.
- [ ] **Step 2: Implement.** In `unpushed`, the root's call:

```python
if own:
    repos = [e.name for e in entries_of_the_folder if os.path.lexists(e / ".git")]
    lines += _checkout_lines(project_folder, project_folder, "the project's folder", skip=repos)
```

  and in `_checkout_lines` the status call
  `_git(entry, "status", "--porcelain", "--untracked-files=normal", "--", ".",
  *(f":(exclude){name}" for name in skip))`. In `set_variable`:

```python
try:
    state.set_project_variable(id, name, value)
except sqlite3.IntegrityError:
    raise NoSuchProject(f'unknown project "{id}"') from None  # deleted meanwhile
```

  In `set_secret`, after the write: `if state.get_project(id) is None:
  _remove_secret(id, name); raise NoSuchProject(f'unknown project "{id}"')`.
- [ ] **Step 3:** `make test PYTEST_ARGS="-n0 tests/test_project_repos.py tests/test_projects_core.py tests/test_project_variables_core.py"`.
- [ ] **Step 4: Commit** `A project folder that is a repository does not count its
  repositories as changes; a set racing a delete is an unknown project (LAD-139)`.

## Task 3: The server's preview and delete (D8)

**Files:** Modify `src/lado/server/models.py` (`ProjectDeletion`),
`src/lado/server/launch.py` (`project_deletion`), `src/lado/server/app.py` (two routes);
`web/openapi.json`, `web/src/api.gen.ts` by `make web-types`. Test:
`tests/test_server_projects.py`.

**Interfaces:**
- Consumes: `projects.deletion`, `projects.delete` (Task 1).
- Produces: `ProjectDeletion {id: str, folder: str, kind: "folder" | "link" | "missing",
  target: str | None, sessions: SessionToForget[], unpushed: str[], variables: str[],
  secrets: str[]}`; `GET /api/projects/{id}/deletion` → `ProjectDeletion`; `DELETE
  /api/projects/{id}` → 204.

```python
@app.get("/api/projects/{id}/deletion", dependencies=[Depends(guard)], responses=project_refused)
def project_deletion(id: str, has_db: bool = Depends(database)) -> ProjectDeletion:
    """What deleting the project does; nothing changes."""
    return launch.project_deletion(project_core(id, has_db, projects.deletion))


@app.delete(
    "/api/projects/{id}",
    dependencies=[Depends(guard.changes)],
    responses=project_refused,
    status_code=204,
)
def delete_project(id: str, has_db: bool = Depends(database)) -> None:
    """Delete the project as `lado project delete --yes` does."""
    project_core(id, has_db, projects.delete, True)
```

Requirement → tests: "The server previews and deletes a project" (the preview's fields
for a folder, a link, a missing folder; no secret value in the body; `DELETE` 204, then
the folder, the data folder, the sessions and the record gone; 400 with the core's text
while a session runs, for both routes, nothing changed; 404 unknown and without a
database; `DELETE` without the change token refused; spies on `projects.deletion` and
`projects.delete` called once each); "A change to a project deleted meanwhile is refused
as unknown" (`PUT …/variables/X` and `…/secrets/X` with the racing monkeypatch → 404).

- [ ] **Step 1:** tests first; **Step 2:** implement; `make web-types`; **Step 3:**
  `make test PYTEST_ARGS="-n0 tests/test_server_projects.py"` and `make web`; **Step 4:**
  commit `The server previews and deletes a project through the CLI's core (LAD-139)`.

## Task 4: The page's block and dialog (D9, D11)

**Files:** Create `web/src/ProjectDelete.tsx`, `web/src/ProjectDelete.test.tsx`; modify
`web/src/Projects.tsx` (the block in place of the not-built line), `web/src/api.ts`
(`getProjectDeletion(id)`, `deleteProject(id)`), `web/src/styles.css` (`button.quiet.danger-text`,
`.project-delete`), `web/src/Projects.test.tsx`.

**Interfaces:**
- Consumes: `ProjectDeletion` from `api.gen.ts` (Task 3).
- Produces: `ProjectDelete({project}: {project: ProjectInfo})`, rendered last in
  `ProjectPage`; on success `reload()` from the outlet's context and
  `navigate("/projects")`.

Requirement → tests (vitest with a mocked `api`): "The project's page shows the project and
its delete" (the block, no `not built yet`); "The UI deletes a project after showing what
goes" (the three lists by name, `— secret`, `(1 open run)`, `— no project…`; `All its work
is on the remote.`, `No session is forgotten.`, `No variables or secrets.`; the sentence by
kind for folder, link, missing; `Delete project` off until the id is typed exactly — off
for `shop `, `Shop`, `sho`; a refusal of the preview and of the `DELETE` → the text and
only Close; success → `deleteProject` called once, `/projects` shown; Esc while the
`DELETE` is in flight keeps the dialog).

- [ ] **Step 1:** tests first; **Step 2:** implement by the mockup's frames 1–6, 8, 9;
  **Step 3:** `cd web && npx vitest run src/ProjectDelete.test.tsx src/Projects.test.tsx`,
  `make web`; **Step 4:** commit `The project's page deletes the project after showing what
  goes (LAD-139)`.

## Task 5: F1: leaving the page cancels Add repository's clone (D10)

**Files:** Modify `web/src/cloneJob.ts` (`useCloneJob`'s unmount cleanup). Test:
`web/src/cloneJob.test.ts`; `web/src/ProjectRepos.test.tsx` gets one case.

```ts
useEffect(() => {
  alive.current = true; // again after StrictMode's trial unmount
  return () => {
    alive.current = false;
    // The screen went away inside the app (Back, another section): no one follows the
    // job, so it is cancelled now rather than by the server's ABANDONED.
    const running = current.current;
    if (running?.state === "running") void cancelClone(running.id).catch(() => {});
  };
}, []);
```

Requirement → tests: "Leaving the page cancels Add repository's clone" (unmount of a hook
whose job runs → `cancelClone(id)` once; unmount after the job ended → none; the dialog in
`ProjectRepos.test.tsx` unmounted mid-clone → `cancelClone` called).

- [ ] **Step 1:** tests first; **Step 2:** implement; **Step 3:** `cd web && npx vitest run
  src/cloneJob.test.ts src/ProjectRepos.test.tsx src/Launch.test.tsx` (Launch's unchanged
  and green); **Step 4:** commit `Leaving the project's page cancels Add repository's
  clone (LAD-139)`.

## Task 6: End to end in the browser and the canary (D12)

**Files:** Modify `tests/ui/test_project_page.py`,
`tests/integration/test_project_secrets_canary.py`.

UI tests (Chromium, the fake provider, temp `LADO_HOME`/`LADO_REPOS`): AC-4 — a running
session of `shop`: `Delete project…` → the refusal and Close only; AC-3 — stop it, `Delete
project…`, type `shop`, `Delete project` → the URL is `/projects`, no `Shop` row, the
folder, `<LADO_HOME>/projects/shop` and the session gone (`state`); AC-2 — an unpushed
commit on a branch of `backend` → its line in the dialog; AC-9 — `<ws>/projects/shop`
made a repository holding `frontend`: no `the project's folder: uncommitted changes`;
screenshots of the block and the dialog, light and dark, desktop and phone 390 px.

Canary (AC-12): after the existing checks, stop `shop-frontend` and `fix-login`; one
`DELETE /api/projects/shop` while a session still runs first → 400 into `said`; then `GET
/api/projects/shop/deletion` (assert `API_NAME` and `CLI_NAME` in `secrets`) and `DELETE
/api/projects/shop` → 204 into `said`; then `project_secrets.data_folder("shop")` does not
exist, the feed and `lado log` read again into `said`, and `files_holding(home, value,
[home / "fake-agents"])` is empty for every canary.

- [ ] **Step 1:** write; **Step 2:** `uv run pytest -m ui tests/ui/test_project_page.py
  tests/ui/test_launch.py` and `uv run pytest -m integration -n0
  tests/integration/test_project_secrets_canary.py`; **Step 3:** commit `UI tests and the
  canary over deleting a project (LAD-139)`.

## Task 7: Docs and the regression run (D13)

**Files:** Modify `docs/design/ui.md` (Projects: the block and the dialog in place of the
not-built line; Add repository: leaving the page cancels the clone), `docs/design/projects.md`
("Deleting": the UI built, the id always typed, the link and missing texts, sessions without
a project; "The UI": S7b built, the not-built list without it), `docs/cli.md` (`project
delete`'s texts and ` (no project)`), `CHANGELOG.md` (one Features line under `## 0.43.0
(unreleased)`).

- [ ] Write; `make lint`; `openspec validate project-delete --strict`; commit `Docs of
  deleting a project (LAD-139)`.
- [ ] The regression run, the settings' Checks: `make lint`; `make test`; `make web`;
  `uv run pytest -m ui tests/ui/test_project_page.py tests/ui/test_launch.py
  tests/ui/test_projects_section.py`; `uv run pytest -m integration -n auto
  tests/integration/test_project_secrets_canary.py tests/integration/test_project_secrets.py`;
  `openspec validate --specs --strict`; the trial archive (`openspec archive project-delete
  -y` in a scratch copy, then `openspec validate --specs --strict` there); CI's `ci-ok`.
