# The UI server in a container, and the repositories folder: implementation plan

**Goal:** In a container the UI server prints a true note instead of the "open to other
machines" warning, `lado ui` prints only the link for the host's browser, the issue report
says `in a container`; `LADO_REPOS` gives the New session window and a clone their start
folder.

**Architecture:** `server/run.Listening.of` gets a `container` flag from its callers
(`update.in_container()`) and a `note` field; `doctor.report` words the server line by
`System.container`. `clone.repos_folder()` is the one reader of `LADO_REPOS`, used by
`clone.default_folder`, a new `GET /api/repos-folder` and a `lado doctor` check; the
window's `WhereField` takes the folder as the parent of an empty field.

**Tech Stack:** Python 3.10+ (FastAPI, pytest, Playwright), React + TypeScript (vitest).

**Spec:** `docs/superpowers/specs/2026-10-14-ui-server-in-container-design.md`,
`openspec/changes/ui-server-in-container/` (design.md D1-D9, deltas `container`,
`bug-report`, `session-clone`, `repos-folder`); mockup
`task/lad-63/mockup-where-start.html`, variant 2.

## Global Constraints

- The note, verbatim (`{host}`, `{port}` filled): `the LADO server runs in a container and
  listens on {host}:{port} inside it; who reaches it depends on how the container
  publishes the port (127.0.0.1:{port}:{port}: this computer only). Published to other
  machines, the token travels unencrypted (plain HTTP).` Printed as `lado: note: <note>`
  on stderr.
- `lado ui`'s second line in a container without `--no-open`: `Open it in your browser on
  the host.` (stdout).
- The report's place in a container: `in a container` (`running, in a container`; with an
  uptime `in a container, up <time>`).
- The variable: `LADO_REPOS`; unset, empty or relative after `~` is no folder.
- The doctor check's name: `Repositories folder`; texts in D7 of design.md.
- The window's row: `Repositories folder:`; placeholders `<folder>/…` (Where) and
  `<folder>/<repo>` (Clone into).
- Outside a container and without `LADO_REPOS`, every existing test passes unchanged.
- `tests/conftest.py` clears `LADO_REPOS` for the test run, as it clears
  `LADO_CONTAINER` (D9).
- Commit messages: a plain sentence ending in `(LAD-63)`, the body says why.

## Review Focus

- `LADO_REPOS=/` (or with a trailing `/`): the window's parent must be `/`, not `//`
  (Task 6 vitest).
- `LADO_REPOS` naming a missing folder: the window shows no list and no error; the first
  clone makes the folder (`clone` already makes parents); `lado doctor` says `info`
  (Tasks 4, 6).
- A developer whose shell has `LADO_REPOS` set: the unit, integration and UI tests must not
  see it (Task 3, conftest).
- `lado ui` in a container against a server on `127.0.0.1` inside the container: no note,
  no second link, the link as today (Task 1 test).
- The UI e2e test's server must start with `LADO_REPOS` already in its environment: the
  fixture that sets it runs before `server` (Task 7).

---

### Task 1: The server's note and `lado ui` in a container

**Files:**
- Modify: `src/lado/server/run.py` (`Listening`, `serve`)
- Modify: `src/lado/cli.py` (`cmd_ui`)
- Test: `tests/test_server.py`

**Interfaces:**
- Produces: `run.CONTAINER_NOTE: str` (a format string with `{host}`, `{port}`),
  `run.Listening(url, remote, warning, note=None)`, `Listening.of(host: str, port: int,
  container: bool = False) -> Listening`; `cli.OPEN_ON_HOST = "Open it in your browser on
  the host."`.

- [ ] **Step 1: Failing tests** (append beside the existing `Listening` and `lado ui` tests)

```python
@pytest.mark.parametrize(
    ("address", "url"),
    [
        ("0.0.0.0", "http://127.0.0.1:8765"),
        ("192.0.2.7", "http://192.0.2.7:8765"),
    ],
)
def test_in_a_container_a_server_on_another_address_notes_the_publication(address, url):
    listening = server_run.Listening.of(address, 8765, container=True)
    assert listening.url == url
    assert listening.remote is None and listening.warning is None
    assert listening.note == (
        f"the LADO server runs in a container and listens on {address}:8765 inside it; who "
        "reaches it depends on how the container publishes the port (127.0.0.1:8765:8765: "
        "this computer only). Published to other machines, the token travels unencrypted "
        "(plain HTTP)."
    )


def test_in_a_container_a_loopback_server_has_no_note():
    listening = server_run.Listening.of("127.0.0.1", 8765, container=True)
    assert (listening.url, listening.remote, listening.warning, listening.note) == (
        "http://127.0.0.1:8765",
        None,
        None,
        None,
    )


def test_outside_a_container_there_is_no_note(monkeypatch):
    monkeypatch.setattr(socket, "gethostname", lambda: "box")
    assert server_run.Listening.of("0.0.0.0", 8001).note is None


def test_ui_in_a_container_prints_only_the_link(capsys, monkeypatch):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    with server_run.take_lock():
        write_info(8765, host="0.0.0.0")
        assert cli.main(["ui", "--no-open"]) == 0
        out, err = capsys.readouterr()
    assert out == f"http://127.0.0.1:8765/?token={auth.token()}\n"
    assert "lado: note: the LADO server runs in a container" in err
    assert "open to other machines" not in err


def test_ui_in_a_container_opens_no_browser(capsys, monkeypatch):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    opened = []
    monkeypatch.setattr("webbrowser.open", opened.append)
    with server_run.take_lock():
        write_info(8765, host="0.0.0.0")
        assert cli.main(["ui"]) == 0
        out, _ = capsys.readouterr()
    assert opened == []
    assert out.splitlines() == [
        f"http://127.0.0.1:8765/?token={auth.token()}",
        "Open it in your browser on the host.",
    ]


def test_ui_in_a_container_against_a_loopback_server_is_as_outside(capsys, monkeypatch):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    with server_run.take_lock():
        write_info(8001)
        assert cli.main(["ui", "--no-open"]) == 0
        out, err = capsys.readouterr()
    assert out == f"http://127.0.0.1:8001/?token={auth.token()}\n"
    assert "note" not in err
```

- [ ] **Step 2: Run them, expect failures** — `uv run pytest -n0 tests/test_server.py -k
  "container"`: `TypeError: of() got an unexpected keyword argument 'container'`.

- [ ] **Step 3: `Listening`** (`src/lado/server/run.py`)

```python
CONTAINER_NOTE = (
    "the LADO server runs in a container and listens on {host}:{port} inside it; who "
    "reaches it depends on how the container publishes the port "
    "(127.0.0.1:{port}:{port}: this computer only). Published to other machines, the "
    "token travels unencrypted (plain HTTP)."
)


@dataclass(frozen=True)
class Listening:
    """Where a server listening on an address is reached: `url` from this machine (what
    server.json keeps), `remote` from others with the `warning` that says so, or None
    for a loopback address. In a container (`container`, the caller's
    `update.in_container()`) only the port's publication decides who reaches it: no
    `remote` and no `warning`, but a `note` that says so."""

    url: str
    remote: str | None
    warning: str | None
    note: str | None = None

    @classmethod
    def of(cls, host: str, port: int, container: bool = False) -> "Listening":
        """For the address the socket took (`getsockname`), not the name it was given."""
        ip = ipaddress.ip_address(host)
        if ip.is_loopback:
            return cls(f"http://{host}:{port}", None, None)
        local = f"http://127.0.0.1:{port}" if ip.is_unspecified else f"http://{host}:{port}"
        if container:
            return cls(local, None, None, CONTAINER_NOTE.format(host=host, port=port))
        warning = ...  # as today
        if ip.is_unspecified:
            return cls(local, f"http://{socket.gethostname()}:{port}", warning)
        return cls(local, local, warning)
```

In `serve`, beside the warning (import `update` inside `serve`, as `uvicorn` is):

```python
        from lado import update

        listening = Listening.of(listens, bound, update.in_container())
        if listening.warning:
            print(f"lado: warning: {listening.warning}", file=sys.stderr, flush=True)
        if listening.note:
            print(f"lado: note: {listening.note}", file=sys.stderr, flush=True)
```

- [ ] **Step 4: `cmd_ui`** (`src/lado/cli.py`; `OPEN_ON_HOST` at the module's top beside
  the other texts; `update` imported inside the command, as `cli.py`'s lazy imports
  require)

```python
    from lado import update

    container = update.in_container()
    listening = server_run.Listening.of(info["host"], info["port"], container)
    if listening.warning:
        print(f"lado: warning: {listening.warning}", file=sys.stderr)
    if listening.note:
        print(f"lado: note: {listening.note}", file=sys.stderr)
    token = auth.token()
    url = f"{info['url']}/?token={token}"
    if args.no_open or container:  # a container has no browser: the host's opens the link
        print(url)
        if not args.no_open:
            print(OPEN_ON_HOST)
    else:
        print(f"Opening {url}")
        webbrowser.open(url)
    if listening.remote:
        print(f"From another machine: {listening.remote}/?token={token} (or this host's address)")
    return 0
```

- [ ] **Step 5: Pass** — `uv run pytest -n0 tests/test_server.py`, all green (old tests
  unchanged); `make lint`; `uv run pytest -n0 tests/test_lazy_imports.py`.

- [ ] **Step 6: Commit** — `git add src/lado/server/run.py src/lado/cli.py
  tests/test_server.py`; message `In a container the UI server notes how its port is
  published and lado ui prints only the host's link (LAD-63)`.

### Task 2: The note in a real server's log (integration)

**Files:**
- Test: `tests/integration/test_server_process.py`

**Interfaces:**
- Consumes: Task 1's note text.

- [ ] **Step 1: Test** (beside `test_a_server_on_every_address_warns_...`)

```python
def test_a_server_in_a_container_notes_the_publication_and_no_other_machines(monkeypatch):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    first = lado_cli("ui", "--no-open", "--host", "0.0.0.0", "--port", "0")
    assert first.returncode == 0, first.stderr
    info = server_run.running()
    assert first.stdout.splitlines() == [f"{info['url']}/?token={auth.token()}"]
    log = (state.home() / "server.log").read_text()
    for text in (log, first.stderr):
        assert f"listens on 0.0.0.0:{info['port']} inside it" in text
        assert "open to other machines" not in text
    stopped = lado_cli("server", "stop")
    assert stopped.returncode == 0, stopped.stderr
    assert gone(info["pid"])
```

- [ ] **Step 2: Run** — `uv run pytest -m integration -n0
  tests/integration/test_server_process.py -k container`: passes with Task 1 (fails
  without it: run it once on Task 1's parent to see red).

- [ ] **Step 3: Commit** — message `An integration test of the container's note in the
  server's log (LAD-63)`.

### Task 3: The report's server line, and LADO_REPOS cleared for the tests

**Files:**
- Modify: `src/lado/doctor.py` (`_server_line`, `report`)
- Modify: `tests/conftest.py` (clear `LADO_REPOS`)
- Test: `tests/test_doctor.py`, `tests/test_cli_bug_report.py`

**Interfaces:**
- Produces: `doctor._server_line(server: ServerState | None, container: bool = False) ->
  str`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_doctor.py, beside test_report_server_line
@pytest.mark.parametrize(
    ("server", "line"),
    [
        (doctor.ServerState(True, 60), "- Server: in a container, up 1 min, schema "),
        (doctor.ServerState(True, None), "- Server: running, in a container, schema "),
        (doctor.ServerState(False, None), "- Server: running, in a container, schema "),
        (None, "- Server: not running, schema "),
    ],
)
def test_report_server_line_in_a_container(server, line):
    system = dataclasses.replace(doctor.system_info(which=lambda cmd: None), container=True)
    [found] = [t for t in doctor.report(system, server).splitlines() if t.startswith("- Server: ")]
    assert found.startswith(line)
```

```python
# tests/test_cli_bug_report.py, beside test_a_running_server_open_to_the_network
def test_a_running_server_in_a_container(capsys, monkeypatch):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    state.home()
    server_run.info_path().write_text(
        json.dumps({"url": "http://127.0.0.1:8765", "host": "0.0.0.0", "port": 8765, "pid": 1})
    )
    lock = server_run.take_lock()
    try:
        assert _run() == 0
    finally:
        lock.close()
    out = capsys.readouterr().out
    assert "- Server: running, in a container, schema " in out
    assert "open to the network" not in out
```

- [ ] **Step 2: Red** — `uv run pytest -n0 tests/test_doctor.py tests/test_cli_bug_report.py
  -k container`.

- [ ] **Step 3: Code** (`src/lado/doctor.py`)

```python
def _server_line(server: ServerState | None, container: bool = False) -> str:
    if server is None:
        return "not running"
    if container:  # the port's publication, not the address, decides who reaches it
        place = "in a container"
    else:
        place = "open to the network" if server.open_to_network else "loopback only"
    if server.up_seconds is None:
        return f"running, {place}"
    return f"{place}, up {_duration(server.up_seconds)}"
```

and in `report`: `f"- Server: {_server_line(server, system.container)}, schema ..."`.

`tests/conftest.py`: add `"LADO_REPOS"` to the cleared variables, and to the comment:
`LADO's image sets LADO_CONTAINER and LADO_REPOS: a test that wants either sets it itself.`

- [ ] **Step 4: Green** — the two files, then `make test`.

- [ ] **Step 5: Commit** — message `In a container the issue report says the server runs
  there instead of open to the network (LAD-63)`.

### Task 4: The repositories folder in the core: clone and doctor

**Files:**
- Modify: `src/lado/clone.py` (`REPOS`, `repos_folder`, `default_parent`,
  `default_folder`)
- Modify: `src/lado/doctor.py` (`check_repos_folder`, `run_checks`)
- Modify: `src/lado/cli.py` (`lado start`'s folder help)
- Test: `tests/test_clone.py`, `tests/test_doctor.py`, `tests/test_server_clones.py`

**Interfaces:**
- Produces: `clone.REPOS = "LADO_REPOS"`, `clone.repos_folder() -> Path | None`,
  `clone.default_parent() -> Path`; `doctor.check_repos_folder() -> Check | None`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_clone.py
@pytest.mark.parametrize("value", [None, "", "code", "./code"])
def test_no_repositories_folder(value, monkeypatch):
    if value is None:
        monkeypatch.delenv("LADO_REPOS", raising=False)
    else:
        monkeypatch.setenv("LADO_REPOS", value)
    assert clone.repos_folder() is None


def test_the_repositories_folder_expands_the_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LADO_REPOS", "~/code")
    assert clone.repos_folder() == tmp_path / "code"
    monkeypatch.setenv("LADO_REPOS", "/srv/repos")
    assert clone.repos_folder() == Path("/srv/repos")


def test_the_default_folder_is_in_the_repositories_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "repos"))
    assert clone.default_folder("git@github.com:acme/app.git") == tmp_path / "repos" / "app"
    monkeypatch.setenv("LADO_REPOS", "code")  # relative: ignored
    assert clone.default_folder("git@github.com:acme/app.git") == tmp_path / "lado" / "app"
```

```python
# tests/test_server_clones.py, beside test_the_clone_target_by_default
def test_the_clone_target_in_the_repositories_folder(client, tmp_path, monkeypatch):
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "repos"))
    monkeypatch.setattr(launch, "_installed", lambda provider: False)
    answer = client.get("/api/clone-target", params={"url": "git@github.com:acme/app.git"})
    assert answer.status_code == 200
    assert answer.json()["path"] == str(tmp_path / "repos" / "app")
```

```python
# tests/test_doctor.py
def test_no_repositories_folder_line_without_the_variable(monkeypatch):
    monkeypatch.delenv("LADO_REPOS", raising=False)
    assert doctor.check_repos_folder() is None
    monkeypatch.setenv("LADO_REPOS", "")
    assert doctor.check_repos_folder() is None


def test_the_repositories_folder_line(tmp_path, monkeypatch):
    name = "Repositories folder"
    monkeypatch.setenv("LADO_REPOS", str(tmp_path))
    assert doctor.check_repos_folder() == doctor.Check(name, doctor.OK, f"{tmp_path} (LADO_REPOS)")
    missing = tmp_path / "repos"
    monkeypatch.setenv("LADO_REPOS", str(missing))
    assert doctor.check_repos_folder() == doctor.Check(
        name, doctor.INFO, f"{missing} (LADO_REPOS), not made yet: the first clone makes it"
    )
    afile = tmp_path / "file"
    afile.write_text("")
    monkeypatch.setenv("LADO_REPOS", str(afile))
    assert doctor.check_repos_folder() == doctor.Check(
        name, doctor.WARN, f"LADO_REPOS is not a folder: {afile}"
    )
    monkeypatch.setenv("LADO_REPOS", "code")
    assert doctor.check_repos_folder() == doctor.Check(
        name,
        doctor.WARN,
        "LADO_REPOS is not an absolute path: code; LADO ignores it",
        "set it to a full path, e.g. ~/repos or /Users/me/repos",
    )
```

Also assert in one test that `doctor.run_checks` holds the line when set and none when
unset (by name).

- [ ] **Step 2: Red** — `uv run pytest -n0 tests/test_clone.py tests/test_doctor.py
  tests/test_server_clones.py -k "repositor"`.

- [ ] **Step 3: Code**

```python
# src/lado/clone.py
DEFAULT_PARENT = "~/lado"  # a clone's folder is <parent>/<repo> unless given: default_parent
REPOS = "LADO_REPOS"  # the folder of the human's repositories (LADO's image sets it)


def repos_folder() -> Path | None:
    """The folder of the human's repositories, `LADO_REPOS` with `~` expanded; None when it
    is unset, empty or not a full path (`lado doctor` says why it is ignored)."""
    value = os.environ.get(REPOS, "")
    folder = Path(os.path.expanduser(value)) if value else None
    return folder if folder is not None and folder.is_absolute() else None


def default_parent() -> Path:
    """Where a clone goes when the human gives no folder: the repositories folder, else
    ~/lado."""
    return repos_folder() or Path(os.path.expanduser(DEFAULT_PARENT))
```

`default_folder`: its docstring says `<parent>/<repo>` (`default_parent`), and it returns
`default_parent() / name`.

```python
# src/lado/doctor.py (import clone with the other lado modules)
def check_repos_folder() -> Check | None:
    """LADO_REPOS when it is set: the folder the New session window and a clone start
    from, or why LADO ignores it."""
    value = os.environ.get(clone.REPOS, "")
    if not value:
        return None
    name = "Repositories folder"
    folder = clone.repos_folder()
    if folder is None:
        return Check(
            name,
            WARN,
            f"LADO_REPOS is not an absolute path: {value}; LADO ignores it",
            "set it to a full path, e.g. ~/repos or /Users/me/repos",
        )
    if not folder.exists():
        return Check(name, INFO, f"{folder} (LADO_REPOS), not made yet: the first clone makes it")
    if not folder.is_dir():
        return Check(name, WARN, f"LADO_REPOS is not a folder: {folder}")
    return Check(name, OK, f"{folder} (LADO_REPOS)")
```

In `run_checks`, after `check_git()`: `*([repos] if repos else [])` with `repos =
check_repos_folder()` computed at the top as `graphical` is.

`cli.py`, `lado start`'s `folder` help: `"with a git URL: the folder to clone into
(default: $LADO_REPOS/<repo>, else ~/lado/<repo>); it must be new or empty"`.

- [ ] **Step 4: Green** — the three files; `make test`; `make lint`.

- [ ] **Step 5: Commit** — message `LADO_REPOS names the repositories folder a clone goes
  to by default, and lado doctor shows it (LAD-63)`.

### Task 5: `GET /api/repos-folder`

**Files:**
- Modify: `src/lado/server/models.py` (`ReposFolder`), `src/lado/server/app.py`
- Modify: `web/openapi.json`, `web/src/api.gen.ts` (`make web-types`), `web/src/api.ts`
- Test: `tests/test_server_launch.py`

**Interfaces:**
- Produces: `GET /api/repos-folder` → `{"path": str | null}`; `api.ts`: `export type
  ReposFolder = components["schemas"]["ReposFolder"]`, `export const getReposFolder = () =>
  get<ReposFolder>("/api/repos-folder")`.

- [ ] **Step 1: Failing test**

```python
def test_the_repositories_folder(client, tmp_path, monkeypatch):
    monkeypatch.delenv("LADO_REPOS", raising=False)
    assert client.get("/api/repos-folder").json() == {"path": None}
    monkeypatch.setenv("LADO_REPOS", str(tmp_path))
    assert client.get("/api/repos-folder").json() == {"path": str(tmp_path)}
    monkeypatch.setenv("LADO_REPOS", "code")
    assert client.get("/api/repos-folder").json() == {"path": None}
```

- [ ] **Step 2: Red** — 404.

- [ ] **Step 3: Code**

```python
# models.py, after RecentFolder
class ReposFolder(BaseModel):
    """The folder of the human's repositories (LADO_REPOS, clone.repos_folder): the New
    session window's start folder, or None."""

    path: str | None
```

```python
# app.py, after /api/folders/recent
    @app.get("/api/repos-folder", dependencies=[Depends(guard)])
    def repos_folder() -> ReposFolder:
        """The folder the New session window starts Where from (LADO_REPOS), or none."""
        folder = clone.repos_folder()
        return ReposFolder(path=str(folder) if folder else None)
```

(import `clone` and `ReposFolder` where `app.py` imports its peers.) Then `make
web-types`; add `ReposFolder` and `getReposFolder` to `web/src/api.ts` beside
`RecentFolder` and `getRecentFolders`.

- [ ] **Step 4: Green** — `uv run pytest -n0 tests/test_server_launch.py`; `make web`
  (stale-types check passes).

- [ ] **Step 5: Commit** — the Python files, `web/openapi.json`, `web/src/api.gen.ts`,
  `web/src/api.ts`; message `The UI server answers the repositories folder for the New
  session window (LAD-63)`.

### Task 6: The New session window

**Files:**
- Modify: `web/src/Launch.tsx` (`Launch`, `WhereField`, Clone into's placeholder)
- Test: `web/src/Launch.test.tsx`

**Interfaces:**
- Consumes: `getReposFolder`, `ReposFolder` (Task 5).
- Produces: `WhereField` prop `repos: string | null`.

- [ ] **Step 1: Failing vitest** — in `beforeEach` add `let repos: string | null` (`null`)
  and in the fake fetch `if (url.pathname === "/api/repos-folder") return json({ path:
  repos });`. Tests (open the window as the file's other tests do):
  - with `repos = "/Users/me/repos"` and `folders["/Users/me/repos/"] =
    folder("/Users/me/repos/", { ok: false, subfolders: ["api", "app", "site"] })`: Where
    is empty, its placeholder `/Users/me/repos/…`, no `/api/folders` call before focus;
    focus lists `api/`, `app/`, `site/`; a click on `app/` sets the value
    `/Users/me/repos/app`; the row `Repositories folder:` has a button `/Users/me/repos`
    whose click sets `/Users/me/repos/` and lists the three;
  - `repos = "/"`: focus asks `/api/folders?path=%2F` (never `//`);
  - Resume mode with `repos` set: no `Repositories folder:` row;
  - Clone from URL with `repos` set: Clone into's placeholder `/Users/me/repos/<repo>`;
  - `repos = null`: placeholder `~/projects/app`, no row, focus of the empty field asks no
    folder (the existing tests stay green).

- [ ] **Step 2: Red** — `cd web && npx vitest run src/Launch.test.tsx`.

- [ ] **Step 3: Code**

In `Launch`: `const repos = valueOf(useOnce(getReposFolder))?.path ?? null;`, passed to
`WhereField` as `repos={repos}`; Clone into's `placeholder={repos ? `${withSlash(repos)}<repo>` :
"~/lado/<repo>"}`.

```tsx
// The repositories folder as a parent: "/" stays "/", "/a/b" becomes "/a/b/".
const withSlash = (folder: string) => (folder.endsWith("/") ? folder : `${folder}/`);
```

In `WhereField`:

```tsx
  const empty = path.trim() === "";
  // An empty field suggests the repositories folder's subfolders (LADO_REPOS).
  const split = empty && repos ? { parent: withSlash(repos), prefix: "" } : parentOf(path);
```

the input gets `placeholder={repos ? `${withSlash(repos)}…` : "~/projects/app"}` and
`onFocus={() => { if (empty && repos) setOpen(true); }}`; before the Recent row:

```tsx
      {repos && !disabled && (
        <div className="recent">
          Repositories folder:
          <button
            type="button"
            className="chip-button"
            onClick={() => {
              onPath(withSlash(repos));
              setOpen(true);
            }}
          >
            {repos}
          </button>
        </div>
      )}
```

The folder check is unchanged: it runs on what is typed or picked, never on the empty
field.

- [ ] **Step 4: Green** — `make web`.

- [ ] **Step 5: Commit** — message `The New session window suggests the repositories
  folder's subfolders in an empty Where (LAD-63)`.

### Task 7: UI e2e of the window

**Files:**
- Test: `tests/ui/test_launch.py`

- [ ] **Step 1: Test** — a fixture `repos` that makes `<tmp>/repos/api` and
  `<tmp>/repos/app` with `agent_helpers.init_repo` and sets `LADO_REPOS` with
  `monkeypatch`; the test takes it **before** `server` in its arguments, so the server
  process (started by the `server` fixture with `env=os.environ`) inherits the variable:

```python
@pytest.fixture
def repos(tmp_path, monkeypatch):
    folder = tmp_path / "repos"
    agent_helpers.init_repo(folder / "api")
    agent_helpers.init_repo(folder / "app")
    monkeypatch.setenv("LADO_REPOS", str(folder))
    return folder


def test_where_starts_in_the_repositories_folder(page: Page, repos, server, shot):
    log_in(page, server)
    page.get_by_role("navigation", name="Sections").get_by_role("button", name="Launch").click()
    dialog = page.get_by_role("dialog", name="New session")
    where = dialog.get_by_role("combobox", name=re.compile("Where"))
    expect(where).to_have_value("")
    expect(where).to_have_attribute("placeholder", f"{repos}/…")
    expect(dialog).to_contain_text(f"Repositories folder: {repos}")
    where.focus()
    folders = dialog.get_by_role("listbox", name="Folders")
    expect(folders.get_by_role("option")).to_have_text(["api/", "app/"])
    shot(page, "list")
    folders.get_by_role("option", name="app/").click()
    expect(where).to_have_value(f"{repos}/app")
    expect(dialog).to_contain_text("✓ git repository · branch main")
    dialog.get_by_role("button", name="Clone from URL").click()
    dialog.get_by_role("textbox", name=re.compile("Where")).fill(
        "https://example.invalid/acme/site.git"
    )
    # Clone into follows /api/clone-target, which needs no network; the branch listing fails.
    expect(dialog.get_by_role("textbox", name="Clone into")).to_have_value(f"{repos}/site")
    shot(page, "clone")
```

- [ ] **Step 2: Run** — `uv run pytest -m ui tests/ui/test_launch.py -k repositories`;
  attach the two screenshots from `<temp dir>/lado-ui-shots/` as run artifacts.

- [ ] **Step 3: Commit** — message `A UI test of the New session window's repositories
  folder (LAD-63)`.

### Task 8: Docs, CHANGELOG, and the check by hand

**Files:**
- Modify: `AGENTS.md`, `docs/design/ui.md`, `CHANGELOG.md`

- [ ] **Step 1: AGENTS.md** — Layout: `clone.py` names `repos_folder` and
  `default_parent` (`LADO_REPOS`); `server/`'s `run.py` names `Listening`'s `note` in a
  container; the launch endpoints list `GET /api/repos-folder` (`ReposFolder`); `update.py`'s
  `in_container` lists its new users (`run.serve`, `cli.cmd_ui`, the report's server line);
  `doctor.py` names the `Repositories folder` check; the conftest paragraph (Commands)
  names `LADO_REPOS` beside `LADO_CONTAINER`. Try it locally: `lado start <git-url>`'s
  default folder `$LADO_REPOS/<repo>`, else `~/lado/<repo>`.
- [ ] **Step 2: docs/design/ui.md** — Server, Host: in a container (`LADO_CONTAINER`) the
  note instead of the warning, no `From another machine`, `lado ui` prints the link and
  opens no browser; the report's server line `in a container`. Launch and session control,
  New session window: Where's repositories folder (suggestions of an empty field,
  placeholder, the `Repositories folder:` row, hidden in Resume), Clone into's default and
  placeholder; the API's `GET /api/repos-folder`.
- [ ] **Step 3: CHANGELOG.md** under `## 0.39.0 (unreleased)`, one item: in a container the
  UI server no longer warns that it is open to other machines but notes that the port's
  publication decides who reaches it, `lado ui` prints only the link for the host's
  browser and opens none, and the issue report says the server runs in a container;
  `LADO_REPOS` names the folder of your repositories: the New session window suggests its
  subfolders, a clone by URL goes there by default, and `lado doctor` shows it.
- [ ] **Step 4: By hand in LAD-52's prototype** (`docs/research/docker-install/`; its files
  stay unchanged in the commits): the image built with this branch's LADO (a wheel from
  `uv build` copied into a scratch build context, or `uv tool install` from the checkout
  inside a running container), `LADO_CONTAINER=1`, `LADO_REPOS` set to the projects folder
  mounted at the same path as on the host. Record in the build report: `docker logs lado`
  (the note, no warning), `docker exec lado lado ui --no-open` (one line; the host's
  browser opens it), New session's Where lists the projects folder's subfolders, Clone into
  defaults to `$LADO_REPOS/<repo>`, `docker exec lado lado doctor` shows the Repositories
  folder line, `lado bug-report` says `running, in a container`.
- [ ] **Step 5: Regression** — `make lint`, `make test`, `uv run pytest -m integration -n
  auto tests/integration/test_server_process.py`, `uv run pytest -m ui
  tests/ui/test_launch.py`, `make web`, `openspec validate ui-server-in-container
  --strict`, `openspec validate --specs --strict`.
- [ ] **Step 6: Commit** — `AGENTS.md docs/design/ui.md CHANGELOG.md`; message `AGENTS.md,
  the UI design and the CHANGELOG describe the container's note and LADO_REPOS (LAD-63)`.
