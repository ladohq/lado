# Open LADO on another device: Implementation Plan

**Goal:** From the UI's system panel, the human opens a dialog with a QR code and the link
(token included) that opens LADO on a phone or another computer, in Docker too, and can
make a new link that logs everyone else out without a restart.

**Architecture:** One rule in `run.Listening` decides the link's address from the
server's address, `LADO_LISTEN` and `LADO_PUBLIC_HOST` (environment only). The server is
its one judge: `GET /api/access` gives it to the UI and to `lado ui`. `POST
/api/access/new-token` renews the token in the running server (`Guard.renew`), ends the
open streams and terminals, and sets this browser's cookie. Compose publishes the port on
`LADO_LISTEN` and passes both settings into the container.

**Tech Stack:** Python 3.10+ (FastAPI, standard library sockets), React + TypeScript
(Vite, vitest), `qrcode-generator` (npm), pytest, Playwright, Docker compose.

**Spec:** `openspec/changes/share-access-link/` (proposal, `specs/share-access/spec.md`,
`specs/container/spec.md`, `design.md` D1–D11) and
`docs/superpowers/specs/2026-10-18-share-access-design.md` (UI texts, docs). Mockup: run
artifact `task/lad-94/mockup-share-access.html`, section 1 (option И3) and sections 2a–2d.

## Global Constraints

- Settings come from the environment only: `LADO_LISTEN`, `LADO_PUBLIC_HOST`. Nothing new
  on disk; no field in the UI to type an address.
- `LADO_PUBLIC_HOST` valid: `^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$`; empty
  counts as unset; invalid warns `lado: warning: LADO_PUBLIC_HOST is not a host name or
  address: <value>; the link for other devices does not use it`.
- Reasons: `loopback`, `no-address`, `unknown`.
- The link: `http://<address>:<port>/?token=<token>`; the remote line:
  `From another machine: <link>` (no `(or this host's address)` suffix any more).
- In a container with `--no-open`, `lado ui`'s stdout is exactly the local link; the remote
  line goes to stderr.
- Compose: `"${LADO_LISTEN:-127.0.0.1}:${LADO_PORT:-8765}:${LADO_PORT:-8765}"`;
  environment `LADO_LISTEN: ${LADO_LISTEN:-127.0.0.1}`, `LADO_PUBLIC_HOST:
  ${LADO_PUBLIC_HOST:-}`.
- UI texts: exactly those of the design doc's UI section, in English.
- Version: minor; CHANGELOG `## 0.41.0 (unreleased)`.
- Commit messages: a plain sentence ending in `(LAD-94)`.

## Review Focus

- A machine with no network (Wi-Fi off) and the server on `0.0.0.0`:
  `network_address()` fails or gives loopback, so the link uses the hostname. Pinned in
  Task 1.
- `LADO_PUBLIC_HOST=" kaos.local "` (spaces from `.env` quoting): invalid with the
  warning, not trimmed silently. Pinned in Task 1.
- A second New link right after the first, from the same tab: the cookie of the first
  answer is the one sent, so the second passes. Pinned in Task 3.
- `lado ui` against a server that does not answer `/api/access` (an older one in the
  moment of an upgrade, or a 500): the local link is still printed, exit 0, no remote
  line. Pinned in Task 4.
- A token whose cut form would show it whole (shorter than 9 characters, only in tests):
  `cutToken` leaves a short token as it is and never throws. Pinned in Task 6.

---

### Task 1: The rule for the link's address

**Files:**
- Modify: `src/lado/server/run.py` (`Listening`, new `network_address`, `public_host`,
  `serve`'s start lines)
- Test: `tests/test_server.py` (the `Listening` tests), `tests/test_server_run.py` if the
  `Listening` tests live there (grep `Listening.of` and add beside them)

**Interfaces:**
- Produces:
  - `network_address() -> str | None`;
  - `public_host(env: Mapping[str, str]) -> tuple[str | None, str | None]` (the host, the
    warning);
  - `Listening.of(host: str, port: int, container: bool = False, env: Mapping[str, str] |
    None = None) -> Listening`, with new fields `reason: str | None = None`, `problems:
    tuple[str, ...] = ()`, `listen: str | None = None`; `remote` is the base URL or None.

- [ ] **Step 1: Write the failing tests** for each row of the spec's table, plus the
  fallbacks:

```python
from lado.server import run as server_run

def of(host, container=False, **env):
    return server_run.Listening.of(host, 8765, container, env)

def test_loopback_has_no_link_even_with_a_public_host():
    assert of("127.0.0.1", LADO_PUBLIC_HOST="kaos.local").reason == "loopback"
    assert of("127.0.0.1").remote is None

def test_every_address_takes_the_public_host(monkeypatch):
    assert of("0.0.0.0", LADO_PUBLIC_HOST="kaos.local").remote == "http://kaos.local:8765"

def test_every_address_finds_this_machines_address(monkeypatch):
    monkeypatch.setattr(server_run, "network_address", lambda: "192.168.1.23")
    assert of("0.0.0.0").remote == "http://192.168.1.23:8765"

def test_without_a_network_the_hostname(monkeypatch):
    monkeypatch.setattr(server_run, "network_address", lambda: None)
    monkeypatch.setattr(server_run.socket, "gethostname", lambda: "box")
    assert of("0.0.0.0").remote == "http://box:8765"

def test_one_address_is_itself_or_the_public_host():
    assert of("192.168.1.23").remote == "http://192.168.1.23:8765"
    assert of("192.168.1.23", LADO_PUBLIC_HOST="kaos.local").remote == "http://kaos.local:8765"

@pytest.mark.parametrize(("env", "remote", "reason"), [
    ({"LADO_LISTEN": "127.0.0.1", "LADO_PUBLIC_HOST": "kaos.local"}, None, "loopback"),
    ({"LADO_LISTEN": "0.0.0.0"}, None, "no-address"),
    ({"LADO_LISTEN": "0.0.0.0", "LADO_PUBLIC_HOST": "kaos.local"}, "http://kaos.local:8765", None),
    ({"LADO_LISTEN": "192.168.1.23"}, "http://192.168.1.23:8765", None),
    ({}, None, "unknown"),
    ({"LADO_LISTEN": "lado.example"}, None, "unknown"),
    ({"LADO_PUBLIC_HOST": "kaos.local"}, "http://kaos.local:8765", None),
])
def test_in_a_container_lado_listen_decides(env, remote, reason):
    found = of("0.0.0.0", True, **env)
    assert (found.remote, found.reason) == (remote, reason)

@pytest.mark.parametrize("value", ["http://kaos.local", "kaos.local:8765", " kaos.local ", "a/b", "-x"])
def test_an_invalid_public_host_warns_and_counts_as_unset(value, monkeypatch):
    monkeypatch.setattr(server_run, "network_address", lambda: "192.168.1.23")
    found = of("0.0.0.0", LADO_PUBLIC_HOST=value)
    assert found.remote == "http://192.168.1.23:8765"
    assert found.problems == (
        f"LADO_PUBLIC_HOST is not a host name or address: {value}; "
        "the link for other devices does not use it",
    )

def test_an_empty_public_host_is_unset_without_a_warning():
    assert of("0.0.0.0", True, LADO_LISTEN="0.0.0.0", LADO_PUBLIC_HOST="").problems == ()

def test_start_lines_in_a_container_follow_lado_listen():
    assert of("0.0.0.0", True).note and not of("0.0.0.0", True).warning
    opened = of("0.0.0.0", True, LADO_LISTEN="0.0.0.0")
    assert opened.warning and "0.0.0.0:8765" in opened.warning and opened.note is None
    closed = of("0.0.0.0", True, LADO_LISTEN="127.0.0.1")
    assert closed.warning is None and closed.note is None
```

  Also update the existing `Listening` tests that expect `http://<hostname>:<port>` for
  `0.0.0.0`: monkeypatch `network_address` to None there, or expect the address.

- [ ] **Step 2: Run them to see them fail**
  Run: `uv run pytest tests/test_server.py -n0 -k "link or listen or public_host or container"`.
  Expected: FAIL (`of()` takes no env; no `reason`).

- [ ] **Step 3: Implement** in `run.py`:

```python
PUBLIC_HOST = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")
PROBE = ("192.0.2.1", 9)  # TEST-NET-1: a UDP connect picks the route and sends nothing


def network_address() -> str | None:
    """This machine's IPv4 address in its network: the source address of the default
    route, found anew at each call; None without one."""
    with contextlib.suppress(OSError):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(PROBE)
            found = probe.getsockname()[0]
            ip = ipaddress.ip_address(found)
            if not (ip.is_loopback or ip.is_unspecified):
                return found
    return None


def public_host(env: Mapping[str, str]) -> tuple[str | None, str | None]:
    """LADO_PUBLIC_HOST when it is a host name or address; otherwise None, with the warning
    for a value that is not one (empty: unset, no warning)."""
    value = env.get("LADO_PUBLIC_HOST", "")
    if not value:
        return None, None
    if PUBLIC_HOST.fullmatch(value):
        return value, None
    return None, (
        f"LADO_PUBLIC_HOST is not a host name or address: {value}; "
        "the link for other devices does not use it"
    )
```

  `Listening.of(host, port, container=False, env=None)`: `env = os.environ if env is
  None else env`; then
  - `named, problem = public_host(env)`; `problems = (problem,) if problem else ()`;
  - `local` as today;
  - outside a container:
    - loopback → `cls(url, None, None, reason="loopback", problems=problems)`;
    - otherwise `address = named or (network_address() or socket.gethostname() if
      ip.is_unspecified else host)`, `remote = f"http://{address}:{port}"`, and the
      warning as today.
  - in a container:
    - `listen = env.get("LADO_LISTEN") or None`, parsed with
      `ipaddress.IPv4Address` in a `try` (ValueError → unknown);
    - unknown: `remote` from `named` or None with `reason="unknown"`, and the
      `CONTAINER_NOTE` as today;
    - loopback: no remote, `reason="loopback"`, no warning, no note;
    - otherwise: `address = named or (None if listen is 0.0.0.0 else listen)`, `reason =
      "no-address"` when None, and the warning text with `listen:port` in place of
      `host:port`.

  `serve`: before the warning line, `for problem in listening.problems: print(f"lado:
  warning: {problem}", file=sys.stderr, flush=True)`. `cli._ui` prints them the same way
  (Task 4 reads them from the server instead, so only the start prints them).

- [ ] **Step 4: Run the tests to see them pass**, and the whole file:
  `uv run pytest tests/test_server.py -n auto`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lado/server/run.py tests/test_server.py
git commit -m "The server knows the link for another device by one rule (LAD-94)"
```

### Task 2: A new token in a running server

**Files:**
- Modify: `src/lado/server/auth.py` (`token`, `Guard.renew`, a `cookie_for` helper shared
  with `login`)
- Test: `tests/test_server.py`

**Interfaces:**
- Produces: `auth.token(new: bool = False) -> str` (atomic); `Guard.renew() -> str`;
  `Guard.set_cookie(response: Response) -> None` (the cookie of the current token, the
  attributes of `login`).

- [ ] **Step 1: Failing tests**

```python
def test_a_new_token_replaces_the_file_whole_and_for_the_owner_only(monkeypatch):
    old = auth.token()
    seen = []
    real_replace = os.replace
    def replace(src, dst):
        seen.append(auth.token_path().read_text().strip())  # the old one is still there
        real_replace(src, dst)
    monkeypatch.setattr(auth.os, "replace", replace)
    new = auth.token(new=True)
    assert seen == [old] and new != old and auth.token() == new
    assert stat.S_IMODE(auth.token_path().stat().st_mode) == 0o600
    assert not auth.token_path().with_suffix(".tmp").exists()

def test_a_stale_tmp_does_not_stop_a_new_token():
    auth.token_path().with_suffix(".tmp").write_text("left\n")
    assert auth.token(new=True) == auth.token()

def test_renew_swaps_the_guards_token():
    guard = auth.Guard(auth.token(), PORT)
    old = guard.token
    new = guard.renew()
    assert guard.token == new == auth.token() and new != old
```

- [ ] **Step 2: Run, expect FAIL** (`renew` missing; `seen` empty since the file is
  unlinked first). `uv run pytest tests/test_server.py -n0 -k "new_token or renew or tmp"`.

- [ ] **Step 3: Implement**

```python
def token(new: bool = False) -> str:
    """The server's token; made on first use, and again with `new`: written whole beside
    the file, then moved over it, so a reader sees the old token or the new one."""
    path = token_path()
    if not new and path.exists():
        return path.read_text().strip()
    value = secrets.token_urlsafe(32)
    written = path.with_suffix(".tmp")
    written.unlink(missing_ok=True)
    fd = os.open(written, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as file:
        file.write(value + "\n")
    os.replace(written, path)
    return value
```

  `Guard.renew`: `self.token = token(new=True); return self.token`. `Guard.set_cookie`
  holds `set_cookie(self.cookie, self.token, httponly=True, samesite="strict",
  path="/")`; `login` calls it.

- [ ] **Step 4: PASS**, `uv run pytest tests/test_server.py -n auto`.
- [ ] **Step 5: Commit** `git add src/lado/server/auth.py tests/test_server.py`, message
  `A new token is written whole and swapped in the running server (LAD-94)`.

### Task 3: The API: /api/access and a new token

**Files:**
- Modify: `src/lado/server/models.py` (`AccessInfo`), `src/lado/server/app.py` (two
  routes; `create_app` keeps `container` and `env`), `src/lado/server/feed.py`
  (`Hub.end_streams`), `src/lado/server/terminals.py` (registry, `close_all`)
- Create: `tests/test_server_access.py`
- Modify: `web/openapi.json`, `web/src/api.gen.ts` (`make web-types`)

**Interfaces:**
- Consumes: `Listening.of(...)` (Task 1), `Guard.renew`, `Guard.set_cookie` (Task 2).
- Produces:
  - `GET /api/access -> AccessInfo`;
  - `POST /api/access/new-token -> AccessInfo`;
  - `AccessInfo{link: str | None, reason: Literal["loopback","no-address","unknown"] |
    None, port: int, container: bool, listen: str | None, note: str | None}`;
  - `create_app(token, port, static=STATIC, host="127.0.0.1", container: bool | None =
    None, env: Mapping[str, str] | None = None)` (None: `update.in_container()` and
    `os.environ`).

- [ ] **Step 1: Failing tests** in `tests/test_server_access.py`:

```python
"""GET /api/access and POST /api/access/new-token (share-access)."""

from fastapi.testclient import TestClient

from lado.server import app as server_app, auth

PORT = 8765
ORIGIN = {"origin": "http://testserver"}

def client_for(host="0.0.0.0", container=False, **env):
    app = server_app.create_app(auth.token(), PORT, host=host, container=container, env=env)
    client = TestClient(app, follow_redirects=False)
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    return client

def test_access_needs_the_token():
    client = client_for()
    client.cookies.clear()
    assert client.get("/api/access").status_code == 401

def test_the_link_holds_the_token_and_is_not_cached():
    answer = client_for(LADO_PUBLIC_HOST="kaos.local").get("/api/access")
    assert answer.json()["link"] == f"http://kaos.local:{PORT}/?token={auth.token()}"
    assert answer.headers["cache-control"] == "no-store"
    assert "access-control-allow-origin" not in answer.headers

def test_on_loopback_no_link_and_no_token():
    answer = client_for(host="127.0.0.1").get("/api/access")
    assert answer.json()["reason"] == "loopback" and answer.json()["link"] is None
    assert auth.token() not in answer.text

def test_in_a_container_without_a_name():
    found = client_for(container=True, LADO_LISTEN="0.0.0.0").get("/api/access").json()
    assert (found["reason"], found["listen"], found["container"]) == ("no-address", "0.0.0.0", True)

def test_unknown_carries_the_note():
    found = client_for(container=True).get("/api/access").json()
    assert found["reason"] == "unknown" and "publishes the port" in found["note"]

def test_a_new_token_logs_others_out_and_keeps_this_browser():
    client = client_for(LADO_PUBLIC_HOST="kaos.local")
    old = auth.token()
    answer = client.post("/api/access/new-token", headers=ORIGIN)
    new = auth.token()
    assert answer.status_code == 200 and new != old
    assert answer.json()["link"].endswith(f"token={new}")
    assert answer.cookies[auth.cookie_name(PORT)] == new
    assert client.get("/api/sessions").status_code == 200  # the client keeps the new cookie
    other = TestClient(client.app)
    other.cookies.set(auth.cookie_name(PORT), old)
    assert other.get("/api/sessions").status_code == 401
    assert other.get("/api/sessions", headers={"authorization": f"Bearer {old}"}).status_code == 401

def test_two_new_tokens_in_a_row_from_one_tab():
    client = client_for()
    assert client.post("/api/access/new-token", headers=ORIGIN).status_code == 200
    assert client.post("/api/access/new-token", headers=ORIGIN).status_code == 200

def test_a_new_token_from_another_origin_is_refused():
    client = client_for()
    old = auth.token()
    answer = client.post("/api/access/new-token", headers={"origin": "http://evil.example"})
    assert answer.status_code == 403 and auth.token() == old

def test_a_new_token_ends_the_streams_and_the_terminals(monkeypatch):
    client = client_for()
    ended = []
    monkeypatch.setattr(client.app.state.hub, "end_streams", lambda: ended.append("feed"))
    monkeypatch.setattr(server_app.terminals, "close_all", lambda: ended.append("terminals"))
    client.post("/api/access/new-token", headers=ORIGIN)
    assert ended == ["feed", "terminals"]
```

  In `tests/test_server_feed.py` (or where `Hub` is tested): `end_streams` puts None in
  every open queue and a later `subscribe` still gets events (unlike `close`). In
  `tests/test_server_terminals.py` (or the terminal tests): a socket accepted is in the
  registry, removed in `finally`, and `close_all` closes each with `ENDED`.

- [ ] **Step 2: Run, expect FAIL** `uv run pytest tests/test_server_access.py -n0`.

- [ ] **Step 3: Implement**
  - `models.py`:

```python
class AccessInfo(BaseModel):
    """The link that opens LADO on another device, or why there is none (share-access)."""

    link: str | None
    reason: Literal["loopback", "no-address", "unknown"] | None
    port: int
    container: bool
    listen: str | None
    note: str | None
```

  - `app.py`, in `create_app`:

```python
    in_container = update.in_container() if container is None else container

    def access() -> JSONResponse:
        listening = Listening.of(host, port, in_container, env)
        link = f"{listening.remote}/?token={guard.token}" if listening.remote else None
        info = AccessInfo(
            link=link, reason=listening.reason, port=port, container=in_container,
            listen=listening.listen,
            note=listening.note if listening.reason == "unknown" else None,
        )
        return JSONResponse(info.model_dump(), headers={"Cache-Control": "no-store"})

    @app.get("/api/access", dependencies=[Depends(guard)])
    def access_info() -> AccessInfo:  # the model names the schema; the answer adds no-store
        """The link for another device (share-access)."""
        return access()

    @app.post("/api/access/new-token", dependencies=[Depends(guard.changes)])
    async def new_token() -> AccessInfo:
        """A new token now: every other browser is logged out, this one gets its cookie."""
        await run_in_threadpool(guard.renew)
        hub.end_streams()
        await terminals.close_all()
        answer = access()
        guard.set_cookie(answer)
        return answer
```

    (`Listening` is imported from `lado.server.run`; `port` is the bound port the app was
    made with. `JSONResponse` with a `-> AccessInfo` annotation keeps the schema; check
    `make web-types` lists `AccessInfo` for both routes, or add
    `response_model=AccessInfo`.)
  - `feed.Hub.end_streams()`: `self._send(None)` without `_closed` or cancelling the task.
  - `terminals`: `OPEN: set[WebSocket] = set()`; in `serve` after `ws.accept()`
    `OPEN.add(ws)`, and in the `finally` `OPEN.discard(ws)`; `async def close_all() ->
    None: for ws in list(OPEN): await _close(ws, ENDED, "a new link: open the terminal
    again")`. The socket's own loop ends on the close, and its `finally` closes the
    terminal viewer as today.

- [ ] **Step 4: PASS**: `uv run pytest tests/test_server_access.py tests/test_server.py -n auto`;
  `make web-types`, then `make web` (the stale-types check).
- [ ] **Step 5: Commit** the server files, the tests, `web/openapi.json`,
  `web/src/api.gen.ts`: `The UI server gives the link for another device and makes a new
  one (LAD-94)`.

### Task 4: lado ui takes the remote link from the server

**Files:**
- Modify: `src/lado/cli.py` (`_ui`; the remote line)
- Test: the unit tests of `lado ui` (grep `From another machine` in `tests/`),
  `tests/integration/test_server_process.py`

**Interfaces:**
- Consumes: `GET /api/access` (Task 3).
- Produces: `server_run.access(url: str, token: str, timeout: float = 2) -> dict | None`
  (None on any error or a non-200).

- [ ] **Step 1: Failing tests**
  - Unit, with `server_run.access` monkeypatched:
    - outside a container a link prints `From another machine: <link>` on stdout after the
      local one;
    - in a container with `--no-open` stdout is exactly the local link and stderr has the
      remote line;
    - in a container without `--no-open` the remote line is on stdout after `Open it in
      your browser on the host.`;
    - `access` None → no remote line, exit 0.
  - Integration, `test_server_process.py`:

```python
def test_ui_prints_the_servers_link_for_another_device(monkeypatch):
    monkeypatch.setenv("LADO_PUBLIC_HOST", "server-side.local")
    started = server_run.start_background("0.0.0.0", 0)
    info = server_run.wait_ready(started)
    monkeypatch.setenv("LADO_PUBLIC_HOST", "shell-side.local")  # lado ui's own environment
    shown = lado_cli("ui", "--no-open")
    assert f"From another machine: http://server-side.local:{info['port']}/?token={auth.token()}" in shown.stdout

def test_a_new_token_ends_an_open_event_stream_and_the_old_cookie():
    # Start a server, open /api/events with the cookie in a thread, POST new-token with
    # the cookie and the server's Origin, then: the stream's read returns (ended) within
    # a few seconds, and /api/sessions with the old cookie is 401.
```

  (`start_background` takes the test's environment; the second `setenv` changes only the
  `lado ui` subprocess's.)

- [ ] **Step 2: Run, expect FAIL**: the unit tests with `-n0`;
  `uv run pytest -m integration -n0 tests/integration/test_server_process.py -k "another_device or new_token"`.

- [ ] **Step 3: Implement** `server_run.access`:

```python
def access(url: str, token: str, timeout: float = 2) -> dict | None:
    """What the server at `url` answers on /api/access with the token; None when it does
    not answer it (an older server, an error)."""
    ask = urllib.request.Request(f"{url}/api/access", headers={"Authorization": f"Bearer {token}"})
    with contextlib.suppress(OSError, ValueError):
        with urllib.request.urlopen(ask, timeout=timeout) as answer:
            said = json.load(answer)
            return said if isinstance(said, dict) else None
    return None
```

  In `cli._ui`, replace the last `if listening.remote:` block:

```python
    found = server_run.access(info["url"], token)
    link = found.get("link") if found else None
    if link:
        line = f"From another machine: {link}"
        print(line, file=sys.stderr if container and args.no_open else sys.stdout)
```

  The warning and note lines stay from `Listening.of` (now with the environment of
  `lado ui`, which in a container is the container's, so the same).
- [ ] **Step 4: PASS**: the unit tests, then the integration file with `-m integration -n auto`.
- [ ] **Step 5: Commit** `lado ui prints the server's link for another device (LAD-94)`.

### Task 5: Compose publishes on LADO_LISTEN

**Files:**
- Modify: `docker/compose.yaml` (ports, environment, header), `docs/install.md` (the
  `.env` example, `### Open LADO on your phone`), `tests/test_docker.py`,
  `tests/container/test_access.py`

- [ ] **Step 1: Failing tests** in `tests/test_docker.py`:
  - `environment` is `{"LADO_PORT", "LADO_REPOS", "LADO_GIT_NAME", "LADO_GIT_EMAIL",
    "LADO_LISTEN", "LADO_PUBLIC_HOST"}`;
  - `ports == ["${LADO_LISTEN:-127.0.0.1}:${LADO_PORT:-8765}:${LADO_PORT:-8765}"]`;
  - `environment["LADO_LISTEN"] == "${LADO_LISTEN:-127.0.0.1}"`;
  - `environment["LADO_PUBLIC_HOST"] == "${LADO_PUBLIC_HOST:-}"`;
  - the header names `LADO_LISTEN=0.0.0.0` and `LADO_PUBLIC_HOST`;
  - the guide's `.env` names both (the existing "every variable" test then passes);
  - the guide has `### Open LADO on your phone`.
  - Container, `tests/container/test_access.py`: a compose project with
    `LADO_LISTEN=0.0.0.0` and `LADO_PUBLIC_HOST=lado-test.local` (the test's own
    `LADO_PORT`): `docker compose exec lado lado ui --no-open` prints exactly one stdout
    line, and stderr has `From another machine: http://lado-test.local:<port>/?token=`.

- [ ] **Step 2: Run, expect FAIL**: `uv run pytest tests/test_docker.py -n auto`.
- [ ] **Step 3: Implement** compose:

```yaml
    environment:
      LADO_PORT: ${LADO_PORT:-8765}
      LADO_REPOS: ${LADO_PROJECTS:?set LADO_PROJECTS to your projects folder}
      # Where the port is published (below), and the name other devices reach this
      # computer by: the UI's link for a phone (Open on another device).
      LADO_LISTEN: ${LADO_LISTEN:-127.0.0.1}
      LADO_PUBLIC_HOST: ${LADO_PUBLIC_HOST:-}
      ...
    ports:
      # This computer only, unless LADO_LISTEN names another address: the UI's token is
      # the one guard, and it travels unencrypted.
      - "${LADO_LISTEN:-127.0.0.1}:${LADO_PORT:-8765}:${LADO_PORT:-8765}"
```

  The header's settings list gains:

```
#   LADO_LISTEN=0.0.0.0                 # optional: other devices of your network may open
#                                       # LADO (the token travels unencrypted); default
#                                       # 127.0.0.1, this computer only
#   LADO_PUBLIC_HOST=my-mac.local       # optional: this computer's name for the UI's link
#                                       # for a phone (Open on another device)
```

  The guide's section says the design doc's "What the human gets" in the guide's voice,
  with the warning, and that a laptop with `LADO_LISTEN=0.0.0.0` is open on every network
  it joins.
- [ ] **Step 4: PASS**: `uv run pytest tests/test_docker.py -n auto`. The container test is
  run by CI (`make test-container` needs `make docker`); run it locally when Docker is
  there: `make docker && uv run pytest -m container -n0 tests/container/test_access.py`.
- [ ] **Step 5: Commit** `Compose publishes LADO on LADO_LISTEN and names the host for the link (LAD-94)`.

### Task 6: The dialog in the UI

**Files:**
- Create: `web/src/Share.tsx`, `web/src/Share.test.tsx`
- Modify: `web/src/SystemPanel.tsx` (the header's icons), `web/src/icons.tsx` (`QrIcon`,
  `GitHubIcon`),
  `web/src/api.ts` (`getAccess`, `newAccessToken`, type `AccessInfo`),
  `web/src/styles.css`, `web/package.json` and `web/package-lock.json`
  (`qrcode-generator`, exact version: `npm install --save-exact qrcode-generator`)

**Interfaces:**
- Consumes: `AccessInfo` (Task 3).
- Produces:
  - `export function cutToken(link: string): string`;
  - `export function ShareButton(): JSX.Element` (the icon and its dialog);
  - `export function QrCode({ text }: { text: string }): JSX.Element`.

- [ ] **Step 1: Failing vitest** `Share.test.tsx`:
  - `cutToken("http://h:1/?token=abcdefghijkl")` → `http://h:1/?token=abcd…ijkl`;
    `cutToken("http://h:1/?token=abc")` stays as it is; a link without `token=` stays.
  - With `getAccess` faked to a link: the dialog shows the warning text, an element with
    `role="img"` named `QR code of the link`, the cut link, and Copy link writes the full
    link (`navigator.clipboard.writeText` spied).
  - `reason: "loopback", container: false`: the command `lado server stop && lado ui
    --host 0.0.0.0`, no QR.
  - `reason: "loopback", container: true`: `LADO_LISTEN=0.0.0.0`.
  - `reason: "no-address"`: names `LADO_PUBLIC_HOST`, no QR.
  - `reason: "unknown"`: shows `note`.
  - New link…: `Make a new link?` first; Cancel calls nothing; `Make a new link` calls
    `newAccessToken` and shows the new link; a refusal shows its message.
  - `SystemPanel.test.tsx`: the header's buttons in the order `Open on another device`,
    `Copy system info`, `LADO on GitHub` (a link to the repository, new tab), and no text
    `GitHub ↗`.
  - `QrCode` for a text: a square SVG whose dark modules match
    `qrcode(0, "M")`'s `isDark` for that text.

- [ ] **Step 2: Run, expect FAIL**: `cd web && npx vitest run src/Share.test.tsx`.

- [ ] **Step 3: Implement**
  - `api.ts`:

```ts
export type AccessInfo = components["schemas"]["AccessInfo"];
export const getAccess = () => get<AccessInfo>("/api/access");
export const newAccessToken = () => post<AccessInfo>("/api/access/new-token");
```

    (use the module's existing POST helper; it sends `credentials: "same-origin"`, so the
    browser sends Origin and stores the answer's cookie).
  - `QrCode`:

```tsx
import qrcode from "qrcode-generator";

// The link as a QR code: black modules on white with a 4-module quiet zone, in both
// themes, as a phone's camera needs.
export function QrCode({ text }: { text: string }) {
  const code = qrcode(0, "M");
  code.addData(text);
  code.make();
  const count = code.getModuleCount();
  const size = count + 8;
  const cells = [];
  for (let row = 0; row < count; row++)
    for (let col = 0; col < count; col++)
      if (code.isDark(row, col)) cells.push(<rect key={`${row}-${col}`} x={col + 4} y={row + 4} width={1} height={1} />);
  return (
    <svg className="share-qr" viewBox={`0 0 ${size} ${size}`} role="img" aria-label="QR code of the link" shapeRendering="crispEdges">
      <rect width={size} height={size} fill="#fff" />
      <g fill="#000">{cells}</g>
    </svg>
  );
}
```

  - `ShareButton`: an `icon-button` with `QrIcon`, `Tooltip` `Open on another device`,
    `aria-label` the same; opens `ShareDialog`, a `<dialog className="question-dialog
    share-dialog">` shown with `showModal()`, loading `getAccess()` on open; states and
    texts exactly as the design doc's UI section; `CopyButton` / `useCopy` from
    `Copy.tsx` for Copy link (`Link copied`), Copy command and Copy lines.
  - `SystemPanel.tsx`, the header's `system-links`: `<ShareButton />`, the clipboard
    button as today, then in place of the text `GitHub ↗`:

```tsx
<Tooltip tip="LADO on GitHub">
  <a className="icon-button" href={GITHUB} target="_blank" rel="noreferrer" aria-label="LADO on GitHub">
    <GitHubIcon />
  </a>
</Tooltip>
```

    `GitHubIcon`: the GitHub mark (GitHub's published logo, allowed for linking to
    GitHub), `viewBox="0 0 16 16"`, `fill="currentColor"`, `aria-hidden`, the `icon`
    class. Existing tests that find `GitHub ↗` by text (vitest `SystemPanel.test.tsx`,
    `tests/ui/test_system_panel.py`) find the link by its label `LADO on GitHub`. `useDismiss` of the panel must not
    close it while the dialog is open: pass an `onOpenChange` like `onAsk` and hold
    `asking`-style state in `LiveButton` (the Update dialog's pattern).
  - `styles.css`: `.share-body` (flex, gap 18px, wrap), `.share-qr` (180px square, 1px
    `--line` border, radius 6px), `.share-link` (`overflow-wrap: anywhere`, 12px, the
    `.command` look), `.share-warning` (`.problem` with `border-left-color:
    var(--human)`).
- [ ] **Step 4: PASS**: `cd web && npx vitest run`, then `make web`.
- [ ] **Step 5: Commit** `The system panel opens a dialog with the link and QR code for another device (LAD-94)`.

### Task 7: UI end to end

**Files:**
- Create: `tests/ui/test_share_access.py`
- Modify: `tests/ui/conftest.py` only if the server fixture cannot take a host and
  environment (add parameters; keep the defaults).

- [ ] **Step 1: Write the tests** (marker `ui`):
  - the panel's header: the three icons in order, screenshot `share-panel`;
  - a server on `0.0.0.0` with `LADO_PUBLIC_HOST=lado-ui.test`: open `live`, the icon
    `Open on another device`, the dialog shows the QR image and
    `http://lado-ui.test:<port>/?token=` with `…`; Copy link puts the full link on the
    clipboard (grant `clipboard-read`); screenshot `share-link`;
  - New link…: confirm; the dialog's link changes; the page's `live` comes back; a second
    browser context logged in before shows the server's 401 message after its next
    request; screenshot `share-new-link`;
  - a server on 127.0.0.1: the dialog shows the `--host 0.0.0.0` command; screenshot
    `share-loopback`;
  - with `LADO_CONTAINER=1`, `LADO_LISTEN=0.0.0.0` and no name: names
    `LADO_PUBLIC_HOST`; screenshot `share-no-address`.
- [ ] **Step 2: Run**: `uv run pytest -m ui -n0 tests/ui/test_share_access.py`; screenshots
  in `<temp dir>/lado-ui-shots/`. Attach each as a run artifact.
- [ ] **Step 3: Commit** `UI tests open LADO on another device (LAD-94)`.

### Task 8: Docs and CHANGELOG

**Files:**
- Modify: `docs/design/ui.md`, `docs/cli.md`, `docs/design/modules.md`, `CHANGELOG.md`,
  `src/lado/server/auth.py` docstring (a new token in a running server)

- [ ] **Step 1:** `docs/design/ui.md`:
  - the new section `### Open on another device (decided 2026-10-18, LAD-94)` after
    System panel: the icon, the dialog's states, New link, the mockup's name;
  - the Server section's Host bullet: `LADO_LISTEN` and `LADO_PUBLIC_HOST`, the rule's
    summary, `lado ui`'s line now from `/api/access`, in a container too;
  - the Token bullet: `POST /api/access/new-token` and `GET /api/access`.
- [ ] **Step 2:** `docs/cli.md`'s `lado ui`: the `From another machine` line, its rule and
  its stream in a container. `docs/design/modules.md`: `run.py` (`Listening`'s rule,
  `network_address`, `access`), `auth.py` (`renew`).
- [ ] **Step 3:** CHANGELOG under `## 0.41.0 (unreleased)` (add the heading if missing):
  `- The UI opens LADO on a phone or another computer: a QR code and the link in the
  system panel, New link to log everyone else out without a restart; in Docker set
  LADO_LISTEN and LADO_PUBLIC_HOST in .env (LAD-94).`
- [ ] **Step 4:** `uv run pytest tests/test_agents_md.py -n0` (AGENTS.md is not changed;
  the map needs no line).
- [ ] **Step 5: Commit** `Docs for opening LADO on another device (LAD-94)`.

### Regression run (before the build report)

- `make lint`
- `make test` (report the counts)
- `uv run pytest -m integration -n auto tests/integration/test_server_process.py`
- `uv run pytest -m ui tests/ui/test_share_access.py tests/ui/test_system_panel.py`
- `make web`
- `openspec validate share-access-link --strict` and `openspec validate --specs --strict`
- The container test runs in CI (`make test-container` is not in a normal round).

## Requirement → tests

| Requirement (share-access, container) | Tests |
|---|---|
| The link to another device follows one rule | Task 1 unit; Task 4 integration; Task 7 e2e |
| LADO_PUBLIC_HOST is a host or it is refused loudly | Task 1 unit |
| GET /api/access gives the link to the token's holder only | Task 3 unit |
| A new link logs everyone else out without a restart | Task 2, Task 3 unit; Task 4 integration; Task 7 e2e |
| The system panel opens the dialog for another device | Task 6 vitest; Task 7 e2e |
| lado ui prints the link for another device by the same rule | Task 4 unit and integration; Task 5 container |
| container: The UI server in a container names the port's publication… | Task 1 unit |
| container: lado ui in a container prints the link for the host's browser | Task 4 unit; Task 5 container |
| container: The compose file publishes one port number | Task 5 unit (`test_docker.py`) |
