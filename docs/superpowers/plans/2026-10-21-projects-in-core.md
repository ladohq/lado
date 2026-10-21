# Projects in the core and the default workspace Implementation Plan

**Goal:** One workspace function (`LADO_REPOS`, else `~/workspace`) behind every default
folder, the server and `lado doctor`; a project as a record in `lado.db` with its derived
folder `<workspace>/projects/<id>`; `lado project list|create|show|rename|delete`; doctor
checks of the workspace and projects.

**Architecture:** A new core module `lado.projects` holds the workspace, the id rule, the
ownership rule of `projects/`, create, rename, list, the unpushed scan and delete. The CLI
(`cli.py`) and `lado doctor` only print what it says; `clone`, `scratch`, `runtime` and
the server take the workspace from it. `lado.db` gets the table `projects` (schema 32).
The New session window reads `{path, made}` from `GET /api/repos-folder`.

**Tech Stack:** Python 3.10+ (standard library), SQLite, FastAPI/pydantic, React +
TypeScript (vitest), pytest (unit, integration with real processes and git, UI e2e in
Chromium).

**Spec:** `openspec/changes/projects-in-core/` (proposal with AC-1..AC-10, `design.md`
D1-D14, delta specs `projects`, `repos-folder`, `session-clone`, `session-scratch`) and
`docs/superpowers/specs/2026-10-21-projects-in-core-design.md` (the human's view and the
manual check). Mockup: run artifact `task/lad-123/mockup-workspace-where.html`.

## Global Constraints

- Python 3.10+, standard library only; no new dependency.
- Texts, verbatim (the spec's):
  - workspace: `<path> (LADO_REPOS)`, `<path> (default)`, `, not made yet: the first clone
    or project makes it`, `LADO_REPOS is not an absolute path: <value>; LADO uses
    <default>`, `<name> is not a folder: <path>`, `cannot look at <name> <path>:
    <reason>`, `LADO may not write in <name> <path>: <reason>` (`<name>` = `LADO_REPOS`
    or `the workspace`);
  - ids: `the project id <id> is not valid: lowercase Latin letters, digits and -,
    starting with a letter or digit, at most 40 characters`;
  - create: `project <id> exists`; `<folder> already exists: LADO makes a project's folder
    itself; choose another id or move that folder away`; `<ws>/projects is your own folder
    (it holds <names>): LADO keeps projects there only; move it away or set LADO_REPOS to
    another workspace`; `Made project <id> "<title>": <folder>`;
  - list/show: `No projects. Make one with: lado project create <id>`; `  (folder not
    found)`; `<id> "<title>"`; `  folder:  <folder>`; `  made:    <YYYY-MM-DD HH:MM>`;
    `unknown project "<id>"`;
  - rename: `<id>: title "<title>"`, `<id>: no title`;
  - delete: `Unpushed work in <folder>:`; `  <repo>: uncommitted changes; branch <b> not
    pushed`; `  <repo>: could not check: <first line>`; `deleting project <id> removes its
    folder <folder> with everything in it; run again with --yes`; `Deleted project <id>`;
  - agents: `lado project <command> is for the human; agent "<agent>" cannot use it`;
  - doctor Projects: `<n> in <ws>/projects`; `<id>: folder not found <folder>`; `foreign
    folder in projects/: <names>`; `<ws>/projects is your own folder (it holds <names>):
    LADO cannot make projects there`; `<ws>/projects is not a folder`.
- The id rule: `[a-z0-9][a-z0-9-]*`, 1-40 characters (`re.fullmatch`).
- Names listed in texts: sorted, at most three, then `…`.
- The API path `/api/repos-folder` and the capability `repos-folder` keep their names.
- Never the user's real home in tests: `HOME` and `LADO_HOME` point into `tmp_path`;
  `tests/conftest.py` already clears `LADO_REPOS`.
- Every schema change: `SCHEMA_VERSION`, `MIGRATIONS`, `tests/agent_helpers.schema_before`.

## Review Focus

- A project folder that is a symbolic link to a folder elsewhere: `delete --yes` removes
  the link only (Task 6 test).
- A `projects/` holding only `.DS_Store`: create works (Task 5 test).
- A dangling symbolic link at `<ws>/projects/<id>`: create refuses it as an existing
  folder (`os.path.lexists`) (Task 5 test).
- A worktree of a project's repository with uncommitted work, inside `.lado/worktrees`:
  delete lists it (Task 6 test).
- `LADO_REPOS=~/code` with `HOME` moved: the workspace follows `HOME` (Task 1 test).

---

### Task 1: The workspace function and the renames

**Files:**
- Create: `src/lado/projects.py`
- Modify: `src/lado/clone.py:30-31,122-145`, `src/lado/scratch.py:90-93`,
  `src/lado/runtime.py:566-588`, `src/lado/cli.py:1324`, `src/lado/server/launch.py:67,84`,
  `src/lado/server/clones.py:50`
- Test: `tests/test_projects.py` (new), `tests/test_clone.py`, `tests/test_scratch.py`,
  `tests/test_runtime.py`, `tests/test_server_clones.py`, `tests/test_server_launch.py`

**Interfaces:**
- Produces: `projects.WORKSPACE_VAR = "LADO_REPOS"`, `projects.DEFAULT_WORKSPACE =
  "~/workspace"`, `projects.workspace() -> Path`, `projects.workspace_source() ->
  Literal["LADO_REPOS", "default", "ignored"]`, `runtime.OUTSIDE_WORKSPACE`,
  `runtime.outside_workspace(path) -> str | None`.

- [ ] **Step 1: Failing tests** in `tests/test_projects.py`:

```python
def test_the_workspace_is_lado_repos_when_absolute(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LADO_REPOS", "~/code")
    assert projects.workspace() == tmp_path / "code"
    assert projects.workspace_source() == "LADO_REPOS"
    monkeypatch.setenv("LADO_REPOS", "/srv/repos")
    assert projects.workspace() == Path("/srv/repos")


@pytest.mark.parametrize("value", [None, "", "code"])
def test_else_the_workspace_is_home_workspace(monkeypatch, tmp_path, value):
    monkeypatch.setenv("HOME", str(tmp_path))
    if value is None:
        monkeypatch.delenv("LADO_REPOS", raising=False)
    else:
        monkeypatch.setenv("LADO_REPOS", value)
    assert projects.workspace() == tmp_path / "workspace"
    assert projects.workspace_source() == ("ignored" if value else "default")
    assert not (tmp_path / "workspace").exists()  # never made by asking
```

  `tests/test_clone.py`: replace the `repos_folder` tests by
  `clone.default_folder("git@github.com:acme/app.git") == tmp_path / "workspace" / "app"`
  without `LADO_REPOS` (HOME = tmp_path), and `/srv/repos/app` with it. Same for
  `scratch.default_folder("shop")`. `tests/test_runtime.py`: rename to
  `outside_workspace`/`OUTSIDE_WORKSPACE`; the test "no workspace, no warning" becomes "in
  a container without `LADO_REPOS`, a folder outside `~/workspace` is warned about".

- [ ] **Step 2: Run** `uv run pytest -n0 tests/test_projects.py tests/test_clone.py
  tests/test_scratch.py tests/test_runtime.py -k "workspace or default or outside"`:
  FAIL (no module `lado.projects`).

- [ ] **Step 3: Implement** `src/lado/projects.py` (docstring: what a project is, the
  link to `docs/design/projects.md`, the openspec capabilities `projects` and
  `repos-folder`):

```python
WORKSPACE_VAR = "LADO_REPOS"  # the workspace's name in an installation (LADO's image sets it)
DEFAULT_WORKSPACE = "~/workspace"


def _given() -> Path:
    return Path(os.path.expanduser(os.environ.get(WORKSPACE_VAR, "")))  # unset: "."


def workspace() -> Path:
    """The folder LADO keeps code in: LADO_REPOS when it is a full path after ~, else
    ~/workspace. Never None and never made here: the first clone, fresh start or
    project makes it."""
    given = _given()
    return given if given.is_absolute() else Path(os.path.expanduser(DEFAULT_WORKSPACE))


def workspace_source() -> str:
    if not os.environ.get(WORKSPACE_VAR):
        return "default"
    return "LADO_REPOS" if _given().is_absolute() else "ignored"
```

  `clone.py`: drop `DEFAULT_PARENT`, `REPOS`, `repos_folder`, `default_parent`;
  `default_folder` returns `projects.workspace() / name` (import `from lado import
  projects`). `scratch.default_folder`: `projects.workspace() / name`. `runtime.py`:
  rename to `OUTSIDE_WORKSPACE`/`outside_workspace`, the lazy import takes `projects`,
  and the condition is only `if not update.in_container(): return None`. Callers:
  `cli.py:1324` help text `(default: <workspace>/<repo>, the workspace being LADO_REPOS
  or ~/workspace)`; `server/launch.py:84` `_author(folder or
  str(projects.workspace()))`; every `outside_repos` call site (grep).

- [ ] **Step 4: Run** the same tests, then `uv run pytest -n auto tests/test_server_clones.py
  tests/test_server_launch.py tests/test_scratch.py`: PASS.

- [ ] **Step 5: Commit** `The workspace is LADO_REPOS, else ~/workspace, from one function
  (LAD-123)`.

### Task 2: lado doctor's Workspace line

**Files:**
- Modify: `src/lado/doctor.py:544-585,622`
- Test: `tests/test_doctor.py:170-250`

**Interfaces:**
- Consumes: `projects.workspace()`, `projects.workspace_source()`, `projects.WORKSPACE_VAR`.
- Produces: `doctor.check_workspace() -> Check` (always a Check);
  `doctor.workspace_problem(folder: Path, name: str) -> str | None` (the reason LADO cannot
  use an existing path, or None; shared with `projects.create` via Task 5).

- [ ] **Step 1: Failing tests**, HOME = tmp_path:
  - unset, missing → `Check("Workspace", INFO, f"{ws} (default), not made yet: the first
    clone or project makes it")`;
  - unset, folder → `Check("Workspace", OK, f"{ws} (default)")`;
  - unset, a file at `~/workspace` → `WARN`, `the workspace is not a folder: {ws}`;
  - `LADO_REPOS=code` → `WARN`, `LADO_REPOS is not an absolute path: code; LADO uses
    {ws}` with the hint `set it to a full path, e.g. ~/repos or /Users/me/repos`;
  - the existing `LADO_REPOS` cases keep their texts (`not made yet: the first clone or
    project makes it` for the missing one);
  - `run_checks` always contains a Workspace check.
- [ ] **Step 2: Run** `uv run pytest -n0 tests/test_doctor.py -k workspace`: FAIL.
- [ ] **Step 3: Implement** `check_workspace` from `check_repos_folder`: source
  `"ignored"` returns the warning first; `label = "LADO_REPOS" if source == "LADO_REPOS"
  else "the workspace"`; `tag = "(LADO_REPOS)" or "(default)"`; the stat/probe code moves
  into `workspace_problem(folder, label)` returning the warn text (not a folder, cannot
  look, may not write) or None, with `FileNotFoundError` handled by the caller. In
  `run_checks`, `check_workspace()` is always in the list.
- [ ] **Step 4: Run** `uv run pytest -n auto tests/test_doctor.py`: PASS.
- [ ] **Step 5: Commit** `lado doctor always names the workspace, ~/workspace by default
  (LAD-123)`.

### Task 3: The server's workspace and the New session window

**Files:**
- Modify: `src/lado/server/models.py:215-219`, `src/lado/server/app.py:94,515,545,585-588`,
  `web/src/api.ts:267,291`, `web/src/Launch.tsx:19,297-300,633,646,670,961-1075`,
  `web/openapi.json`, `web/src/api.gen.ts` (by `make web-types`)
- Test: `tests/test_server_launch.py:218-224`, `web/src/Launch.test.tsx:96,363-470`

**Interfaces:**
- Produces: `models.Workspace(path: str, made: bool)`; `api.getWorkspace()`; Launch's
  props `workspace: string` and `made: boolean` in place of `repos: string | null`.

- [ ] **Step 1: Failing tests.** `tests/test_server_launch.py`:

```python
def test_the_workspace(client, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LADO_REPOS", raising=False)
    ws = str(tmp_path / "workspace")
    assert client.get("/api/repos-folder").json() == {"path": ws, "made": False}
    (tmp_path / "workspace").mkdir()
    assert client.get("/api/repos-folder").json() == {"path": ws, "made": True}
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "code"))
    assert client.get("/api/repos-folder").json() == {"path": str(tmp_path / "code"), "made": False}
```

  plus a clone target and a scratch target without `LADO_REPOS` naming
  `<tmp>/workspace/<repo>` and `<tmp>/workspace/<name>`. `Launch.test.tsx`: the mock
  answers `{path, made}`; with `made: false`: Where's placeholder `/Users/ann/workspace/…`,
  no `Workspace:` row, focus on an empty Where lists nothing; with `made: true`: the row
  and the list as today; Clone into's placeholder `/Users/ann/workspace/<repo>` (replaces
  the `~/lado/<repo>` assertion at line 464), Create in's `/Users/ann/workspace/<name>`.
- [ ] **Step 2: Run** `uv run pytest -n0 tests/test_server_launch.py -k workspace` and
  `cd web && npx vitest run src/Launch.test.tsx`: FAIL.
- [ ] **Step 3: Implement.** `models.Workspace` (docstring: the workspace,
  `projects.workspace`, and whether it exists); the handler returns
  `Workspace(path=str(ws), made=ws.is_dir())`. Docstrings at app.py:515/545 say
  `<workspace>/<name>`. In `Launch.tsx`: placeholders always `${withSlash(workspace)}…`,
  `<repo>`, `<name>`; the row `{made && !disabled && …}`; `onFocus` opens the list only
  with `empty && made`; `split` uses the workspace only when `made`; `toCheck` keeps its
  skip by path. Then `make web-types`.
- [ ] **Step 4: Run** `make web` and `uv run pytest -n auto tests/test_server_launch.py
  tests/test_server_clones.py`: PASS.
- [ ] **Step 5: Commit** `The New session window starts from ~/workspace once it exists
  (LAD-123)` with both generated files.

### Task 4: Schema 32, the table projects

**Files:**
- Modify: `src/lado/state.py:22, the fresh schema, 915+`, `tests/agent_helpers.py:186-215`
- Test: `tests/test_state.py`

**Interfaces:**
- Produces: `state.PROJECTS_TABLE`; `state.Project(id: str, title: str | None,
  created_at: str)`; `state.add_project(id, title) ` (raises `sqlite3.IntegrityError` on
  a taken id), `state.get_project(id) -> Project | None`, `state.list_projects() ->
  list[Project]` (by id), `state.set_project_title(id, title) -> bool`,
  `state.delete_project(id) -> bool`; `state.creating_project(id, title)` — a context
  manager that inserts in a transaction and commits only when its block ends without
  error (for D6).

- [ ] **Step 1: Failing tests:** a fresh `lado.db` has `projects`; `previous_schema()`
  then any command migrates to 32 with `backups/lado.db.schema-31` and the table; the
  CRUD functions; `creating_project` with an exception inside leaves no row.
- [ ] **Step 2: Run** `uv run pytest -n0 tests/test_state.py -k project`: FAIL.
- [ ] **Step 3: Implement:**

```python
PROJECTS_TABLE = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,  -- never changes: the folder <workspace>/projects/<id>
    title TEXT,           -- none: the id is shown
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))  -- UTC
)
"""
MIGRATIONS[32] = [PROJECTS_TABLE]
```

  `SCHEMA_VERSION = 32`; the table in the fresh schema list. `schema_before`: `assert
  state.MIGRATIONS[32] == [state.PROJECTS_TABLE]` and, for 32, `DROP TABLE projects`.
- [ ] **Step 4: Run** `uv run pytest -n auto tests/test_state.py tests/test_update.py`:
  PASS.
- [ ] **Step 5: Commit** `lado.db keeps projects (schema 32) (LAD-123)`.

### Task 5: Projects in the core: ids, titles, ownership, create, rename, list

**Files:**
- Modify: `src/lado/projects.py`
- Test: `tests/test_projects.py`

**Interfaces:**
- Consumes: Task 1's workspace, Task 2's `doctor.workspace_problem` (move it into
  `projects.py` as `workspace_problem` if the import would loop; doctor then imports it),
  Task 4's state functions, `runtime.check_title`, `runtime.LadoError`.
- Produces: `ID = re.compile(r"[a-z0-9][a-z0-9-]*")`, `MAX_ID = 40`,
  `class ProjectError(runtime.LadoError)`, `class NoSuchProject(ProjectError)`,
  `check_id(id) -> None`, `projects_folder() -> Path` (`workspace() / "projects"`),
  `folder(id) -> Path`, `owned_by_human() -> list[str] | None` (the visible entries when
  `projects/` is the human's, else None), `foreign() -> list[str]`, `create(id, title) ->
  state.Project`, `rename(id, text) -> str | None`, `listed() -> list[tuple[state.Project,
  Path, bool]]` (project, folder, found), `names(entries) -> str` (sorted, three, `…`).

- [ ] **Step 1: Failing tests** (HOME = tmp_path, no `LADO_REPOS`):
  - `check_id`: accepts `a`, `shop`, `shop-eu`, `a1`, 40 chars; refuses `Shop`, `-a`,
    `shop_eu`, `ш`, `""`, 41 chars, with the id text;
  - `create("shop", "  Shop ")` makes `<tmp>/workspace/projects/shop` and a row with
    title `Shop`; `create("acme", "acme")` stores no title;
  - refusals, each leaving no row and no new folder: a taken id; an existing folder;
    a dangling link at `projects/shop`; `projects/` with `notes`, `drafts` (text names
    `drafts, notes`); `LADO_REPOS` a file;
  - `projects/` with only `.DS_Store` → create works; with `shop` (a project) and `old` →
    `create("acme")` works and `foreign() == ["old"]`;
  - a failing mkdir (monkeypatch `Path.mkdir` to raise `PermissionError`) → no row;
  - `rename("shop", "Shop EU") == "Shop EU"`, `rename("shop", "") is None`,
    `rename("nope", "x")` raises `NoSuchProject('unknown project "nope"')`;
  - `listed()` marks a project whose folder was removed `found=False`.
- [ ] **Step 2: Run** `uv run pytest -n0 tests/test_projects.py`: FAIL.
- [ ] **Step 3: Implement** in the order of D6:

```python
def create(id: str, title: str | None) -> state.Project:
    check_id(id)
    stored = runtime.check_title(title, id)
    ws = workspace()
    if ws.exists() and (problem := workspace_problem(ws, _label())):
        raise ProjectError(problem)
    if state.get_project(id):
        raise ProjectError(f"project {id} exists")
    target = folder(id)
    if os.path.lexists(target):
        raise ProjectError(
            f"{target} already exists: LADO makes a project's folder itself; "
            "choose another id or move that folder away"
        )
    if (own := owned_by_human()) is not None:
        raise ProjectError(
            f"{projects_folder()} is your own folder (it holds {names(own)}): LADO keeps "
            "projects there only; move it away or set LADO_REPOS to another workspace"
        )
    with state.creating_project(id, stored):
        target.mkdir(parents=True, exist_ok=False)
    return state.get_project(id)
```

  `owned_by_human`: `projects/` not a folder → None (doctor reports a file);
  `visible = sorted(n for n in os.listdir(p) if not n.startswith("."))`; ids =
  `{p.id for p in state.list_projects()}`; return `visible` when `visible and not
  (set(visible) & ids)`, else None. `foreign()`: `visible` minus ids when some id is
  there, else `[]`.
- [ ] **Step 4: Run** `uv run pytest -n auto tests/test_projects.py`: PASS.
- [ ] **Step 5: Commit** `Projects in the core: ids, titles, their folders (LAD-123)`.

### Task 6: The unpushed scan and delete

**Files:**
- Modify: `src/lado/projects.py`
- Test: `tests/test_projects.py` (real git in `tmp_path`; `git_config` fixture of
  `tests/conftest.py` for the author)

**Interfaces:**
- Consumes: `clone.NO_PROMPT` (git's environment), Task 5's functions.
- Produces: `unpushed(folder: Path) -> list[str]` (lines `"<name>: <finding>; <finding>"`,
  `<name>` the repository's folder name, a worktree as `<repo> (worktree <path relative to
  the project folder or absolute>)`), `delete(id: str, yes: bool) -> list[str]` (returns
  the unpushed lines; raises `ProjectError` without `yes`), `GIT_TIMEOUT = 20`.

- [ ] **Step 1: Failing tests:**
  - a clean repository with its branch pushed to a bare remote → `[]`;
  - an untracked file → `["frontend: uncommitted changes"]`;
  - a branch `feature-x` with no upstream → `… branch feature-x not pushed`;
  - a branch ahead of its upstream → `… branch main not pushed`;
  - a worktree (`git worktree add <repo>/.lado/worktrees/s/w -b w`) with a new file →
    a line for the worktree with `uncommitted changes` and `branch w not pushed`;
  - a subfolder with a `.git` file pointing nowhere → `broken: could not check: <first
    line of git's stderr>`;
  - a subfolder without `.git` → nothing;
  - `delete("shop", yes=False)` raises with `deleting project shop removes its folder
    <folder> with everything in it; run again with --yes`; folder and row stay;
  - `delete("shop", yes=True)`: folder gone, row gone, `projects/` stays, a sibling
    `projects/acme` stays;
  - a link `projects/shop -> <tmp>/elsewhere` with files: `delete(yes=True)` removes the
    link only; `<tmp>/elsewhere` and its files stay;
  - a folder whose real path is not a child of `realpath(projects/)` (e.g. `projects`
    itself a link to `/x` while `projects/shop` resolves elsewhere through a link of a
    parent): refused, nothing removed;
  - a project whose folder is gone: `delete(yes=True)` drops the row only;
  - `shutil.rmtree` raising (monkeypatch) → the row stays and the text names the path.
- [ ] **Step 2: Run** `uv run pytest -n0 tests/test_projects.py -k "unpushed or delete"`:
  FAIL.
- [ ] **Step 3: Implement** per D8: repositories are the direct subfolders with `.git`;
  worktrees from `git -C <repo> worktree list --porcelain` (lines `worktree <path>`,
  skipping the repository's own); per checkout `git status --porcelain` and
  `git for-each-ref refs/heads --format=%(refname:short)%00%(upstream)%00%(upstream:track)`
  only for the main checkout (branches are shared by its worktrees); subprocess with
  `env={**os.environ, **clone.NO_PROMPT}`, `timeout=GIT_TIMEOUT`, `capture_output=True`;
  a non-zero exit or `TimeoutExpired` → `could not check: <first line>`. Delete: compute
  `target = folder(id)`; if `os.path.lexists(target)`: when `target.is_symlink()` →
  `target.unlink()`; else check `Path(os.path.realpath(target)).parent ==
  Path(os.path.realpath(projects_folder()))`, refuse otherwise, then `shutil.rmtree(target)`
  (it does not follow links); on `OSError` raise `ProjectError(f"could not remove
  {target} whole: {error}; the project stays")`; then `state.delete_project(id)`.
- [ ] **Step 4: Run** `uv run pytest -n auto tests/test_projects.py`: PASS.
- [ ] **Step 5: Commit** `lado project delete shows unpushed work and removes only the
  project's folder (LAD-123)`.

### Task 7: The command lado project

**Files:**
- Modify: `src/lado/cli.py` (a `cmd_project` and the parser after `title`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: Tasks 5-6; `cli._human_only`.
- Produces: `lado project list|create|show|rename|delete` per `docs/cli.md`.

- [ ] **Step 1: Failing tests** (`main([...])` with `capsys`): each command's output as in
  Global Constraints; `list` with no project; `list` columns padded (ids `a` and
  `shop-eu`); `show` of an unknown id exits 1; `rename` and `delete` of an unknown id
  exit 1; with `LADO_AGENT=w1`, `create`, `rename`, `delete` exit 1 with `lado project
  create is for the human; agent "w1" cannot use it` (and `rename`, `delete`), nothing
  changed, while `list` and `show` work; `lado project` alone prints the help.
- [ ] **Step 2: Run** `uv run pytest -n0 tests/test_cli.py -k project`: FAIL.
- [ ] **Step 3: Implement** the subparsers (`create` with `id` and `--title`; `rename`
  with `id` and `title`; `delete` with `id` and `--yes`); `cmd_project` calls
  `_human_only(f"project {args.sub}")` for the three changing commands first; `show`
  converts `created_at` (UTC) to local `%Y-%m-%d %H:%M`; `delete` prints the unpushed
  lines under `Unpushed work in <folder>:` before refusing or deleting.
- [ ] **Step 4: Run** `uv run pytest -n auto tests/test_cli.py`: PASS.
- [ ] **Step 5: Commit** `lado project: list, create, show, rename, delete (LAD-123)`.

### Task 8: lado doctor's Projects line

**Files:**
- Modify: `src/lado/doctor.py` (`check_projects`, `run_checks`)
- Test: `tests/test_doctor.py`

- [ ] **Step 1: Failing tests:** no project and no `projects/` → None; two projects with
  folders → `OK`, `2 in <ws>/projects`; a missing folder and a foreign `old` → `WARN`
  with both findings joined by `; ` in that order; no project and `projects/` holding
  `notes` → `WARN`, the human's-own text; `projects` a file → `WARN`, `<ws>/projects is
  not a folder`; the check follows Workspace in `run_checks`.
- [ ] **Step 2: Run** `uv run pytest -n0 tests/test_doctor.py -k projects`: FAIL.
- [ ] **Step 3: Implement** from `projects.listed()`, `projects.foreign()`,
  `projects.owned_by_human()`.
- [ ] **Step 4: Run** `uv run pytest -n auto tests/test_doctor.py`: PASS.
- [ ] **Step 5: Commit** `lado doctor checks projects (LAD-123)`.

### Task 9: Integration tests

**Files:**
- Create: `tests/integration/test_projects.py` (`pytestmark = pytest.mark.integration`)

- [ ] **Step 1: Write** tests that run `[sys.executable, str(fake_provider.LADO), ...]` as
  processes with `HOME=tmp_path/home`, the test's `LADO_HOME`, no `LADO_REPOS`:
  - `doctor` → `[info] Workspace: <home>/workspace (default), not made yet: …`, no
    Projects line; with `LADO_REPOS=<tmp>/code` (a folder) → `[ok  ] Workspace: <tmp>/code
    (LADO_REPOS)`;
  - `project create shop --title Shop` → exit 0, the folder exists; `list`, `show`,
    `rename`; `doctor` → `[ok  ] Projects: 1 in …`;
  - every refusal of create (bad id, taken, folder exists, human's `projects/`), each
    exit 1 with its text and no folder made;
  - `doctor` with a foreign folder, with a project whose folder was removed, with the
    human's own `projects/`;
  - from an agent: `LADO_SESSION=s LADO_AGENT=w1` in the environment → create, rename,
    delete exit 1; list and show exit 0;
  - `delete shop` with a repository in the folder holding an uncommitted file and a
    branch with no upstream → exit 1, both listed, the folder stays; `delete shop --yes`
    → exit 0, folder gone, a sibling folder stays;
  - a clone without a folder: `start file://<bare>.git --provider fake --no-attach` →
    `<home>/workspace/<repo>` exists (extend `tests/integration/test_clone_start.py`
    instead if its fixture already does this).
- [ ] **Step 2: Run** `uv run pytest -m integration -n auto tests/integration/test_projects.py
  tests/integration/test_clone_start.py tests/integration/test_scratch_start.py`: PASS.
- [ ] **Step 3: Commit** `Integration tests of lado project and the default workspace
  (LAD-123)`.

### Task 10: UI e2e of Where

**Files:**
- Modify: `tests/ui/test_launch.py`

- [ ] **Step 1: Write** a test with `HOME` in `tmp_path` and no `LADO_REPOS`: the window's
  Where placeholder is `<home>/workspace/…`, no `Workspace:` row, focusing an empty Where
  shows no list; make `<home>/workspace/app`, reopen the window: the row and `app/` in
  the list. Screenshots of both states for the reviewer.
- [ ] **Step 2: Run** `uv run pytest -m ui tests/ui/test_launch.py -n auto`: PASS.
- [ ] **Step 3: Commit** `UI e2e: Where without and with ~/workspace (LAD-123)`.

### Task 11: Documents, S1's leftover, CHANGELOG

**Files:**
- Modify: `docs/cli.md`, `docs/design/modules.md`, `docs/design/projects.md`,
  `docs/design/ui.md:1358-1365,1446,1465`, `docs/install.md:241,628,746`,
  `docker/Dockerfile:46,65`, `tests/container/test_toolchains.py:1`, `AGENTS.md`
  (Layout: `projects.py`), `CHANGELOG.md`

- [ ] **Step 1:** `docs/cli.md`: a section `lado project` (each subcommand, its output and
  refusals, "pushed" meaning the last fetch's view, agents refused); `lado start
  <git-url>` and `--new` defaults `<workspace>/<repo>`; `lado doctor`'s Workspace and
  Projects lines.
- [ ] **Step 2:** `docs/design/modules.md`: `projects.py` (D1-D8); `clone.py`, `scratch.py`,
  `runtime.py`, `doctor.py`, `server/models.py` with the new names; line 983 "the
  repositories' toolchains". `docs/design/projects.md`: remove the "Until S2 the
  workspace is `LADO_REPOS` alone" sentence, mark the workspace default, "The project"
  and its CLI as built in S2 (repositories, sessions, variables, UI still not built).
  `docs/design/ui.md`: Where, Clone into and Create in as in D12. `docs/install.md`: the
  heading "The repositories' toolchains" (and its anchor's links), `~/lado` examples as
  defaults become `~/workspace`.
- [ ] **Step 3:** `docker/Dockerfile:46,65` and the docstring of
  `tests/container/test_toolchains.py`: "the repositories' toolchains".
- [ ] **Step 4:** `CHANGELOG.md`: `## 0.42.1 (unreleased)` → `## 0.43.0 (unreleased)` (if
  0.42.1 was released meanwhile, a new heading on top instead); under `### Added`:
  `- **Projects in the terminal.** \`lado project create|list|show|rename|delete\` keeps a
  project as a folder in your workspace's \`projects/\`; \`lado doctor\` checks them.`;
  under `### Changed`: `- **The workspace is \`~/workspace\` without \`LADO_REPOS\`.** New
  clones and fresh starts go there (was \`~/lado\`); sessions in \`~/lado\` keep working.`
- [ ] **Step 5: The grep by meaning** (AC-10), outside `openspec/changes/archive/`,
  `docs/superpowers/`, `docs/research/`, `docs/epics/` and released CHANGELOG sections:
  `grep -rnE "~/lado/|~/lado\b|DEFAULT_PARENT|repos_folder|check_repos_folder|OUTSIDE_REPOS|ReposFolder|getReposFolder|projects' toolchains|no workspace|without LADO_REPOS|LADO_REPOS.*else" .`
  — each hit is a default-folder claim to fix, or a given-folder example (leave), or
  `~/lado-…` (another name, leave). Then `uv run pytest tests/test_agents_md.py`.
- [ ] **Step 6: Commit** `Docs: projects, the workspace default, the repositories'
  toolchains (LAD-123)`.

### Task 12: Regression run

- [ ] `make lint`
- [ ] `make test` — report the counts; if red only from the leftover check (`sleep 60`,
  LAD-121), say "N passed, exit 2 from the leftover check", never green.
- [ ] `uv run pytest -m integration -n auto tests/integration/test_projects.py
  tests/integration/test_clone_start.py tests/integration/test_scratch_start.py
  tests/integration/test_server_launch_process.py`
- [ ] `uv run pytest -m ui -n auto tests/ui/test_launch.py`
- [ ] `make web`
- [ ] `openspec validate projects-in-core --strict` and `openspec validate --specs
  --strict`; grep `openspec/specs/` for `~/lado`, `repos_folder`, `outside_repos`,
  `no Workspace line`: only the delta's requirements may still differ until archive.
- [ ] CI green on the pull request (`ci-ok`).
