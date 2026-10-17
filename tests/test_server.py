"""The UI server (lado.server): token, authorization, the API, and finding the one server of
a LADO_HOME. In process, with FastAPI's test client; the server as a process is in
tests/integration/test_server_process.py."""

import errno
import json
import os
import re
import shutil
import socket
import sqlite3
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest
from agent_helpers import previous_schema
from fastapi.testclient import TestClient

from lado import __version__, cli, loop, runtime, state
from lado.server import app as server_app
from lado.server import auth, feed
from lado.server import run as server_run

PORT = 8123
OPENAPI = Path(__file__).parent.parent / "web" / "openapi.json"


@pytest.fixture
def client():
    return TestClient(server_app.create_app(auth.token(), PORT), follow_redirects=False)


def test_the_token_is_kept_in_lado_home_for_the_owner_only():
    token = auth.token()
    path = state.home() / "server-token"
    assert path.read_text().strip() == token
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert auth.token() == token  # the same on the next start
    new = auth.token(new=True)
    assert new != token and auth.token() == new


def test_a_new_token_replaces_the_file_whole_and_for_the_owner_only(monkeypatch):
    """A `lado ui` reading as the server renews sees the old token or the new one, never no
    file (it would make a token of its own)."""
    old = auth.token()
    before = set(os.listdir(state.home()))
    seen = []
    replace = os.replace

    def watched(src, dst):
        seen.append(auth.token_path().read_text().strip())
        replace(src, dst)

    monkeypatch.setattr(auth.os, "replace", watched)
    new = auth.token(new=True)
    assert seen == [old] and new != old and auth.token() == new
    assert stat.S_IMODE(auth.token_path().stat().st_mode) == 0o600
    assert set(os.listdir(state.home())) == before  # no temporary file left


def test_renew_swaps_the_guards_token():
    guard = auth.Guard(auth.token(), PORT)
    old = guard.token
    new = guard.renew()
    assert guard.token == new == auth.token() and new != old


@pytest.mark.parametrize("content", ["", "  \n"])
def test_an_empty_token_file_gets_a_new_token(content):
    """A file left empty (a write that failed on a full disk) is no token: the server would
    take an empty one from anyone."""
    path = state.home() / "server-token"
    path.write_text(content)
    token = auth.token()
    assert len(token) >= 32
    assert path.read_text().strip() == token
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert auth.token() == token


def test_a_failed_token_write_leaves_the_file_and_no_temporary_file(monkeypatch):
    path = state.home() / "server-token"
    old = auth.token()
    before = set(os.listdir(state.home()))

    def full(*args):
        raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))

    monkeypatch.setattr(os, "write", full)
    with pytest.raises(runtime.LadoError) as error:
        auth.token(new=True)
    said = str(error.value)
    assert "cannot write the UI server's token to" in said and str(path) in said
    assert os.strerror(errno.ENOSPC) in said
    assert path.read_text().strip() == old
    assert set(os.listdir(state.home())) == before

    path.unlink()
    with pytest.raises(runtime.LadoError):
        auth.token()
    assert not path.exists()
    assert set(os.listdir(state.home())) == before - {"server-token"}


def test_the_server_refuses_an_empty_token(client):
    assert client.get("/api/sessions", headers={"Authorization": "Bearer "}).status_code == 401
    answer = client.get("/?token=")
    assert answer.status_code == 401
    assert "set-cookie" not in answer.headers
    client.cookies.set(f"lado_token_{PORT}", "")
    assert client.get("/api/sessions").status_code == 401
    with pytest.raises(ValueError):
        auth.Guard("", PORT)


def test_health_needs_no_token(client):
    answer = client.get("/api/health")
    assert answer.status_code == 200
    said = answer.json()
    assert (said["ok"], said["version"]) == (True, __version__)


def test_the_api_refuses_a_request_without_the_token(client):
    assert client.get("/api/sessions").status_code == 401
    wrong = {"Authorization": "Bearer nope"}
    assert client.get("/api/sessions", headers=wrong).status_code == 401


def test_the_api_takes_a_bearer_token(client):
    answer = client.get("/api/sessions", headers={"Authorization": f"Bearer {auth.token()}"})
    assert answer.status_code == 200


def test_the_link_with_the_token_sets_a_cookie_of_the_port_and_redirects(client):
    answer = client.get(f"/?token={auth.token()}")
    assert answer.status_code == 303
    assert answer.headers["location"] == "/"
    cookie = answer.headers["set-cookie"]
    assert cookie.startswith(f"lado_token_{PORT}={auth.token()};")
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
    assert client.get("/api/sessions").status_code == 200  # the client keeps the cookie


def test_the_link_with_a_wrong_token_sets_no_cookie(client):
    answer = client.get("/?token=nope")
    assert answer.status_code == 401
    assert "set-cookie" not in answer.headers


def test_the_cookies_of_two_servers_on_other_ports_do_not_mix():
    ours, theirs = auth.token(), "the-other-servers-token"
    client = TestClient(server_app.create_app(ours, PORT))
    client.cookies.set(f"lado_token_{PORT + 1}", ours)  # our token, another port's cookie
    assert client.get("/api/sessions").status_code == 401
    client.cookies.set(f"lado_token_{PORT}", ours)
    assert client.get("/api/sessions").status_code == 200  # beside the other port's cookie
    client.cookies.set(f"lado_token_{PORT + 1}", theirs)
    assert client.get("/api/sessions").status_code == 200


def authorized(client: TestClient) -> TestClient:
    client.headers["Authorization"] = f"Bearer {auth.token()}"
    return client


def test_sessions_lists_name_repo_status_and_agents(client, repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.start_session(str(repo), "t", "plan", "kilo", without=["agent:worker"])
    runtime.stop_session("t")
    with state.connect() as db:
        db.execute("UPDATE sessions SET created_at = '2026-10-05 10:00:00'")
        db.execute("UPDATE events SET created_at = '2026-10-05 10:00:01' WHERE session = 's'")
        db.execute("UPDATE sessions SET stopped_at = '2026-10-05 10:30:00.500' WHERE name = 't'")
        db.execute(
            "UPDATE events SET created_at = '2026-10-05 10:30:00.500' WHERE session = 't'"
            " AND kind = ?",
            (state.SESSION_STOP,),
        )
    held = loop.take_lock("s")
    answer = authorized(client).get("/api/sessions")
    held.close()
    none = {"gates": 0, "questions": 0, "agents": 0}
    defaults = {"kits": ["default"], "provider": "claude", "permission_mode": None, "without": []}
    assert answer.json() == [
        {
            "name": "s",
            "repo": str(repo),
            "status": "running",
            "agents": 1,
            "waiting": none,
            "busy": 1,  # its supervisor is starting
            **defaults,
            "ran_seconds": 0,
            "running_since": "2026-10-05T10:00:00.000Z",
            "stopped_at": None,
            "title": None,
        },
        {
            "name": "t",
            "repo": str(repo),
            "status": "stopped",
            "agents": 0,
            "waiting": none,
            "busy": 0,
            "kits": ["default"],
            "provider": "kilo",
            "permission_mode": "plan",
            "without": ["agent:worker"],
            "ran_seconds": 1800,
            "running_since": None,
            "stopped_at": "2026-10-05T10:30:00.500Z",
            "title": None,
        },
    ]


def test_sessions_without_a_database_is_empty_and_creates_none(client):
    assert authorized(client).get("/api/sessions").json() == []
    assert not (state.home() / "lado.db").exists()


def schema(path: Path) -> tuple[int, list]:
    conn = sqlite3.connect(path)
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        tables = conn.execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall()
    finally:
        conn.close()
    return version, tables


@pytest.mark.parametrize("which", ["older", "newer"])
def test_another_schema_answers_503_and_the_database_stays_as_it_is(client, which):
    state.list_sessions()  # creates lado.db
    if which == "older":
        previous_schema()
    else:
        with state.connect() as db:
            db.execute(f"PRAGMA user_version = {state.SCHEMA_VERSION + 1}")
    db_path = state.home() / "lado.db"
    before = schema(db_path)
    answer = authorized(client).get("/api/sessions")
    assert answer.status_code == 503
    assert "lado server" in answer.json()["detail"]
    assert schema(db_path) == before


def test_another_schema_after_the_check_answers_503_too(client, monkeypatch):
    """The schema changes between the dependency's check and the endpoint's read: the read's
    own connection refuses it, and that is a 503 with its reason, not a 500."""
    state.list_sessions()
    monkeypatch.setattr(feed, "schema_problem", lambda: None)
    previous_schema()
    before = schema(state.home() / "lado.db")
    answer = authorized(client).get("/api/sessions")
    assert answer.status_code == 503
    assert "LADO was upgraded under a running session" in answer.json()["detail"]
    assert schema(state.home() / "lado.db") == before


def test_the_committed_openapi_schema_is_the_servers():
    """The UI's TypeScript types are generated from web/openapi.json (make web-types)."""
    current = server_app.contract()
    assert json.loads(OPENAPI.read_text()) == current, "stale web/openapi.json: make web-types"
    assert "version" not in current["info"]  # a release does not make it stale


def test_the_page_says_how_to_build_a_missing_bundle(tmp_path):
    client = TestClient(server_app.create_app("t", PORT, static=tmp_path / "none"))
    answer = client.get("/")
    assert answer.status_code == 503
    assert "make web" in answer.text


@pytest.fixture
def bundle(tmp_path):
    """A client of a server with a small bundle: index.html, assets/app.js, favicon.svg."""
    (tmp_path / "index.html").write_text("<html>bundle</html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    (tmp_path.parent / "secret.txt").write_text("not served")
    return TestClient(
        server_app.create_app(auth.token(), PORT, static=tmp_path), follow_redirects=False
    )


def test_the_page_is_the_bundles_index(bundle):
    assert bundle.get("/").text == "<html>bundle</html>"


@pytest.mark.parametrize(
    "path", ["/sessions", "/sessions/x", "/sessions/a%20b.c/flows", "/settings"]
)
def test_every_page_path_is_the_bundles_index(bundle, path):
    """The UI's own addresses work when opened directly or reloaded."""
    answer = bundle.get(path)
    assert answer.status_code == 200
    assert answer.text == "<html>bundle</html>"


def test_the_bundles_files_are_served(bundle):
    assert bundle.get("/assets/app.js").text == "console.log(1)"
    assert bundle.get("/favicon.svg").text == "<svg/>"


def test_the_icon_the_page_links_is_served(tmp_path):
    """The UI's page links an icon from web/public, which the build puts at the bundle's
    top; the browser gets it, so it asks for no /favicon.ico."""
    web = Path(__file__).parent.parent / "web"
    page = (web / "index.html").read_text()
    links = re.findall(r'<link rel="icon"[^>]*href="/([^"]+)"', page)
    assert links, "web/index.html links no icon"
    shutil.copytree(web / "public", tmp_path, dirs_exist_ok=True)
    (tmp_path / "index.html").write_text(page)
    client = TestClient(server_app.create_app(auth.token(), PORT, static=tmp_path))
    for link in links:
        answer = client.get(f"/{link}")
        assert answer.status_code == 200
        assert answer.headers["content-type"].startswith("image/svg+xml")


@pytest.mark.parametrize("path", ["/assets/none.js", "/assets/x", "/none.css", "/old.js"])
def test_a_missing_file_of_the_bundle_is_404_not_the_page(bundle, path):
    """After an upgrade an open tab asking for an old file gets 404, not HTML instead of JS."""
    answer = bundle.get(path)
    assert answer.status_code == 404
    assert "bundle" not in answer.text


@pytest.mark.parametrize(
    "path", ["/sessions/a.b", "/sessions/my%20app.v2/flows", "/sessions/x/flows/a.js"]
)
def test_a_name_with_a_dot_below_the_top_is_a_page(bundle, path):
    """The bundle's files are at its top or under /assets; deeper down a dot is in a name."""
    answer = bundle.get(path)
    assert answer.status_code == 200
    assert answer.text == "<html>bundle</html>"


def test_no_file_outside_the_bundle_is_served(bundle):
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/%2e%2e%2fsecret.txt"):
        assert "not served" not in bundle.get(path).text


def test_an_unknown_api_path_is_a_json_404(bundle):
    answer = bundle.get("/api/nope")
    assert answer.status_code == 404
    assert answer.json() == {"detail": "Not Found"}


def test_the_link_with_the_token_on_any_page_redirects_to_that_page(bundle):
    """A link to a page (/sessions/x?token=...) leads straight to it."""
    answer = bundle.get(f"/sessions/x?token={auth.token()}")
    assert answer.status_code == 303
    assert answer.headers["location"] == "/sessions/x"
    assert answer.headers["set-cookie"].startswith(f"lado_token_{PORT}={auth.token()};")
    answer = bundle.get(f"/sessions/a%20b/flows?tab=1&token={auth.token()}&x=y")
    assert answer.headers["location"] == "/sessions/a%20b/flows?tab=1&x=y"


@pytest.mark.parametrize(
    "path", ["/sessions/x/flows/feature%2Fui", "/sessions/a%3Fb", "/sessions/a%25b/agents"]
)
def test_the_redirect_after_the_login_keeps_the_encoded_names(bundle, path):
    """A run's name holds "/", encoded in its one segment: decoded, it would be another page."""
    answer = bundle.get(f"{path}?token={auth.token()}")
    assert answer.status_code == 303
    assert answer.headers["location"] == path


def test_the_link_with_a_wrong_token_on_a_page_is_401(bundle):
    answer = bundle.get("/sessions/x?token=nope")
    assert answer.status_code == 401
    assert "set-cookie" not in answer.headers


def test_the_redirect_after_the_login_stays_on_this_server(bundle):
    """`//host/x` as a Location would send the browser to another host."""
    answer = bundle.get(f"http://testserver//evil.example/x?token={auth.token()}")
    assert answer.status_code == 303
    assert answer.headers["location"] == "/evil.example/x"


# Finding the one server of LADO_HOME, its port and host (lado.server.run).


@pytest.mark.parametrize("address", ["127.0.0.1", "127.0.1.1"])
def test_a_loopback_address_is_reached_by_itself_with_no_warning(address):
    listening = server_run.Listening.of(address, 8001)
    assert listening.url == f"http://{address}:8001"
    assert listening.warning is None and listening.remote is None


def test_every_address_is_reached_locally_on_127_0_0_1_and_from_others_by_its_address(
    monkeypatch,
):
    monkeypatch.setattr(server_run, "network_address", lambda: "192.168.1.23")
    listening = server_run.Listening.of("0.0.0.0", 8001)
    assert listening.url == "http://127.0.0.1:8001"
    assert listening.remote == "http://192.168.1.23:8001"
    assert listening.reason is None
    assert "listens on 0.0.0.0:8001, open to other machines" in listening.warning


def of(host: str, container: bool = False, **env: str) -> server_run.Listening:
    return server_run.Listening.of(host, 8765, container, env)


def test_a_loopback_address_has_no_link_even_with_a_public_host():
    assert of("127.0.0.1", LADO_PUBLIC_HOST="kaos.local").reason == "loopback"
    assert of("127.0.0.1", LADO_PUBLIC_HOST="kaos.local").remote is None
    assert of("127.0.0.1").reason == "loopback"


def test_every_address_takes_the_public_host(monkeypatch):
    monkeypatch.setattr(server_run, "network_address", lambda: "192.168.1.23")
    assert of("0.0.0.0", LADO_PUBLIC_HOST="kaos.local").remote == "http://kaos.local:8765"


def test_every_address_without_a_network_falls_back_to_the_hostname(monkeypatch):
    monkeypatch.setattr(server_run, "network_address", lambda: None)
    monkeypatch.setattr(server_run.socket, "gethostname", lambda: "box")
    assert of("0.0.0.0").remote == "http://box:8765"


def test_one_address_is_itself_or_the_public_host():
    assert of("192.0.2.7").remote == "http://192.0.2.7:8765"
    assert of("192.0.2.7", LADO_PUBLIC_HOST="kaos.local").remote == "http://kaos.local:8765"


@pytest.mark.parametrize(
    ("env", "remote", "reason"),
    [
        ({"LADO_LISTEN": "127.0.0.1", "LADO_PUBLIC_HOST": "kaos.local"}, None, "loopback"),
        ({"LADO_LISTEN": "0.0.0.0"}, None, "no-address"),
        (
            {"LADO_LISTEN": "0.0.0.0", "LADO_PUBLIC_HOST": "kaos.local"},
            "http://kaos.local:8765",
            None,
        ),
        ({"LADO_LISTEN": "192.168.1.23"}, "http://192.168.1.23:8765", None),
        ({}, None, "unknown"),
        ({"LADO_LISTEN": "lado.example"}, None, "unknown"),
        ({"LADO_LISTEN": "::"}, None, "unknown"),
        ({"LADO_PUBLIC_HOST": "kaos.local"}, "http://kaos.local:8765", None),
    ],
)
def test_in_a_container_lado_listen_decides_the_link(env, remote, reason, monkeypatch):
    monkeypatch.setattr(server_run, "network_address", lambda: "172.17.0.2")  # the bridge's
    found = of("0.0.0.0", True, **env)
    assert (found.url, found.remote, found.reason) == ("http://127.0.0.1:8765", remote, reason)


def test_in_a_container_listen_is_lado_listen_as_given():
    assert of("0.0.0.0", True, LADO_LISTEN="0.0.0.0").listen == "0.0.0.0"
    assert of("0.0.0.0", True, LADO_LISTEN="lado.example").listen == "lado.example"
    assert of("0.0.0.0", True).listen is None
    assert of("0.0.0.0", LADO_LISTEN="0.0.0.0").listen is None  # read only in a container


@pytest.mark.parametrize(
    "value", ["http://kaos.local", "kaos.local:8765", " kaos.local ", "a/b", "-x", "x.", "a" * 254]
)
def test_an_invalid_public_host_warns_and_counts_as_unset(value, monkeypatch):
    monkeypatch.setattr(server_run, "network_address", lambda: "192.168.1.23")
    found = of("0.0.0.0", LADO_PUBLIC_HOST=value)
    assert found.remote == "http://192.168.1.23:8765"
    assert found.problems == (
        f"LADO_PUBLIC_HOST is not a host name or address: {value}; "
        "the link for other devices does not use it",
    )


@pytest.mark.parametrize("value", ["kaos-mbp.local", "192.168.1.23", "x", "a" * 253])
def test_a_public_host_is_a_host_name_or_address(value):
    assert server_run.public_host({"LADO_PUBLIC_HOST": value}) == (value, None)


def test_an_empty_public_host_is_unset_without_a_warning():
    found = of("0.0.0.0", True, LADO_LISTEN="0.0.0.0", LADO_PUBLIC_HOST="")
    assert (found.reason, found.problems) == ("no-address", ())


def test_the_network_address_is_the_routes_source_and_none_without_one(monkeypatch):
    class Probe:
        def __init__(self, found):
            self.found = found

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def connect(self, where):
            assert where == server_run.PROBE
            if self.found is None:
                raise OSError(errno.ENETUNREACH, "Network is unreachable")

        def getsockname(self):
            return (self.found, 50000)

    for found, expected in [
        ("192.168.1.23", "192.168.1.23"),
        ("127.0.0.1", None),
        ("0.0.0.0", None),
        (None, None),
    ]:
        monkeypatch.setattr(server_run.socket, "socket", lambda *a, f=found: Probe(f))
        assert server_run.network_address() == expected


@pytest.mark.parametrize(
    ("env", "warning", "note"),
    [
        ({}, False, True),
        ({"LADO_LISTEN": "0.0.0.0"}, True, False),
        ({"LADO_LISTEN": "127.0.0.1"}, False, False),
    ],
)
def test_in_a_container_the_start_line_follows_lado_listen(env, warning, note):
    found = of("0.0.0.0", True, **env)
    assert (bool(found.warning), bool(found.note)) == (warning, note)
    if warning:
        assert "listens on 0.0.0.0:8765, open to other machines" in found.warning


def test_another_address_is_reached_by_itself_with_the_warning():
    listening = server_run.Listening.of("192.0.2.7", 8001)
    assert listening.url == listening.remote == "http://192.0.2.7:8001"
    assert listening.warning == (
        "the LADO server listens on 192.0.2.7:8001, open to other machines: whoever reaches "
        "it with the token can run commands as you, and the token travels unencrypted "
        "(plain HTTP). Use it only on a network you trust."
    )


@pytest.mark.parametrize(
    ("address", "url"),
    [("0.0.0.0", "http://127.0.0.1:8765"), ("192.0.2.7", "http://192.0.2.7:8765")],
)
def test_in_a_container_a_server_on_another_address_notes_the_publication(address, url):
    listening = server_run.Listening.of(address, 8765, container=True, env={})
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
    monkeypatch.setattr(server_run, "network_address", lambda: None)
    monkeypatch.setattr(socket, "gethostname", lambda: "box")
    assert server_run.Listening.of("0.0.0.0", 8001).note is None
    assert server_run.Listening.of("192.0.2.7", 8001).note is None


def test_an_ipv6_address_is_refused():
    with pytest.raises(runtime.LadoError, match="IPv6 is not supported yet"):
        server_run.bind("::1", 0)
    with pytest.raises(runtime.LadoError, match="IPv6 is not supported yet"):
        server_run.address("::")


@pytest.mark.parametrize("host", ["203.0.113.1", "no-such-host.invalid"])
def test_an_address_the_server_cannot_listen_on_is_an_error_not_a_busy_port(host):
    with pytest.raises(runtime.LadoError, match=f"^cannot listen on {host}:8000: .+") as error:
        server_run.bind(host, None, first=8000, last=8002)
    assert "free port" not in str(error.value)


def test_a_name_is_resolved_to_the_address_the_server_listens_on():
    assert server_run.address("localhost") == "127.0.0.1"
    assert server_run.address("0.0.0.0") == "0.0.0.0"
    with pytest.raises(runtime.LadoError, match="^cannot listen on no-such-host.invalid: "):
        server_run.address("no-such-host.invalid")


def test_a_busy_port_is_skipped_for_the_next_free_one():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        first = busy.getsockname()[1]
        sock = server_run.bind("127.0.0.1", None, first=first, last=first + 10)
        with sock:
            assert first < sock.getsockname()[1] <= first + 10


def test_every_address_skips_a_port_busy_on_127_0_0_1():
    """macOS lets 0.0.0.0 take it with SO_REUSEADDR: the local link would reach the other."""
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        first = busy.getsockname()[1]
        with server_run.bind("0.0.0.0", None, first=first, last=first + 10) as sock:
            assert first < sock.getsockname()[1] <= first + 10
        with pytest.raises(runtime.LadoError, match=f"port {first} is busy"):
            server_run.bind("0.0.0.0", first)


def test_every_address_names_itself_when_it_cannot_listen(monkeypatch):
    """The look at 127.0.0.1 only skips a busy port; a port the user may not take (EACCES
    below 1024 on Linux) is the error of 0.0.0.0, not of 127.0.0.1."""

    def bind(sock, address):
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(socket.socket, "bind", bind)
    with pytest.raises(runtime.LadoError, match="^cannot listen on 0.0.0.0:80: Permission denied"):
        server_run.bind("0.0.0.0", 80)


def test_an_exact_port_that_is_busy_is_an_error():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        with pytest.raises(runtime.LadoError, match=f"port {port} is busy"):
            server_run.bind("127.0.0.1", port)


def test_no_free_port_in_the_range_is_an_error():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        with pytest.raises(runtime.LadoError, match=f"no free port from {port} to {port}"):
            server_run.bind("127.0.0.1", None, first=port, last=port)


def write_info(
    port: int, version: str = __version__, pid: int | None = None, host: str | None = None
) -> None:
    """A server.json; without `host` as a LADO before `--host` wrote it."""
    url = server_run.Listening.of(host or "127.0.0.1", port).url
    info = {"url": url, "port": port, "pid": pid or os.getpid(), "version": version}
    server_run.info_path().write_text(json.dumps(info | ({"host": host} if host else {})))


def test_a_server_json_without_a_host_is_of_a_server_on_127_0_0_1():
    with server_run.take_lock():
        write_info(8001)
        assert server_run.running()["host"] == "127.0.0.1"
        write_info(8001, host="0.0.0.0")
        assert server_run.running()["host"] == "0.0.0.0"


def test_server_json_counts_only_while_its_lock_is_held():
    write_info(8001)
    assert server_run.running() is None  # no lock held: left by a server that died
    assert not server_run.info_path().exists()
    lock = server_run.take_lock()
    write_info(8001)
    assert server_run.running()["port"] == 8001
    lock.close()


def test_a_stale_server_json_is_removed_under_the_lock(monkeypatch):
    """Removed after letting the lock go, it could be the file of a server just started."""
    held_while_removed = []
    unlink = Path.unlink

    def watched(path, *args, **kwargs):
        if path == server_run.info_path():
            held_while_removed.append(server_run._held())
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", watched)
    write_info(8001)
    assert server_run.running() is None
    assert held_while_removed == [True]


def test_stop_without_a_server_kills_nobody(capsys, monkeypatch):
    killed = []
    monkeypatch.setattr(os, "kill", lambda *a: killed.append(a))
    write_info(8001, pid=12345)
    assert cli.main(["server", "stop"]) == 0
    assert "not running" in capsys.readouterr().out
    assert killed == []
    assert not server_run.info_path().exists()


def test_stop_waits_for_the_process_after_its_lock(monkeypatch):
    """The server frees its lock a moment before its process ends: stop waits for both."""
    lives = iter([True, True, False])  # the pid lives two polls after the lock is free
    monkeypatch.setattr(server_run, "running", lambda: {"pid": 4242})
    monkeypatch.setattr(server_run.os, "kill", lambda pid, sig: None)
    monkeypatch.setattr(server_run, "_held", lambda: False)
    monkeypatch.setattr(server_run, "_gone", lambda pid: not next(lives))
    assert server_run.stop() == {"pid": 4242}
    assert next(lives, "polled to the end") == "polled to the end"


def test_stop_names_a_process_that_outlives_its_lock(monkeypatch):
    monkeypatch.setattr(server_run, "STOP_TIMEOUT", 0.2)
    monkeypatch.setattr(server_run, "running", lambda: {"pid": 4242})
    monkeypatch.setattr(server_run.os, "kill", lambda pid, sig: None)
    monkeypatch.setattr(server_run, "_held", lambda: False)
    monkeypatch.setattr(server_run, "_gone", lambda pid: False)
    with pytest.raises(runtime.LadoError, match=r"pid 4242\) did not end in 0.2s"):
        server_run.stop()


def test_gone_reaps_a_child_and_reads_another_process():
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    deadline = time.monotonic() + 5
    while not server_run._gone(child.pid):
        assert time.monotonic() < deadline
        time.sleep(0.01)
    with pytest.raises(ChildProcessError):  # reaped: no zombie left
        os.waitpid(child.pid, os.WNOHANG)
    assert not server_run._gone(os.getpid())  # alive, not our child


def test_gone_takes_a_process_it_may_not_signal_as_gone(monkeypatch):
    """A pid of another user is no longer our server's (reused after its end)."""

    def refused(pid, sig):
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(server_run.os, "kill", refused)
    assert server_run._gone(1)


def test_a_second_server_names_the_running_one(capsys):
    lock = server_run.take_lock()
    write_info(8001)
    assert cli.main(["server", "--port", "0"]) == 1
    assert "already runs at http://127.0.0.1:8001" in capsys.readouterr().err
    lock.close()


def test_ui_with_another_port_than_the_running_servers_is_an_error(capsys):
    lock = server_run.take_lock()
    write_info(8001)
    assert cli.main(["ui", "--no-open", "--port", "8002"]) == 1
    assert "http://127.0.0.1:8001" in capsys.readouterr().err
    lock.close()


def test_ui_prints_the_link_of_the_running_server(capsys):
    lock = server_run.take_lock()
    write_info(8001)
    assert cli.main(["ui", "--no-open"]) == 0
    out, err = capsys.readouterr()
    assert out == f"http://127.0.0.1:8001/?token={auth.token()}\n"
    assert "open to other machines" not in err
    lock.close()


@pytest.mark.parametrize("host", ["0.0.0.0", "192.0.2.7"])
def test_ui_with_another_host_than_the_running_servers_is_an_error(capsys, host):
    with server_run.take_lock():
        write_info(8001)
        assert cli.main(["ui", "--no-open", "--host", host]) == 1
        err = capsys.readouterr().err
        assert "http://127.0.0.1:8001" in err and f"not on {host}" in err
        assert "`lado server stop`" in err


def test_ui_with_a_name_of_the_running_servers_host_takes_it(capsys):
    with server_run.take_lock():
        write_info(8001)
        assert cli.main(["ui", "--no-open", "--host", "localhost"]) == 0
        assert capsys.readouterr().out == f"http://127.0.0.1:8001/?token={auth.token()}\n"


def answers_access(monkeypatch, link: str | None) -> list[tuple[str, str]]:
    """The running server's /api/access, made up: its link (None: no link); the asks."""
    asked = []

    def access(url, token, timeout=2):
        asked.append((url, token))
        return {"link": link, "reason": None if link else "unknown"}

    monkeypatch.setattr(server_run, "access", access)
    return asked


def test_ui_without_host_takes_a_server_open_to_other_machines_and_warns(capsys, monkeypatch):
    token = auth.token()
    asked = answers_access(monkeypatch, f"http://192.168.1.23:8001/?token={token}")
    with server_run.take_lock():
        write_info(8001, host="0.0.0.0")
        assert cli.main(["ui", "--no-open"]) == 0
        out, err = capsys.readouterr()
    assert asked == [("http://127.0.0.1:8001", token)]
    assert out.splitlines() == [
        f"http://127.0.0.1:8001/?token={token}",
        f"From another machine: http://192.168.1.23:8001/?token={token}",
    ]
    assert "open to other machines" in err and "unencrypted" in err


def test_ui_opens_the_local_link_and_prints_the_one_for_other_machines(capsys, monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", opened.append)
    token = auth.token()
    answers_access(monkeypatch, f"http://192.0.2.7:8001/?token={token}")
    with server_run.take_lock():
        write_info(8001, host="192.0.2.7")
        assert cli.main(["ui"]) == 0
        out, err = capsys.readouterr()
    assert opened == [f"http://192.0.2.7:8001/?token={token}"]
    assert out.splitlines() == [
        f"Opening http://192.0.2.7:8001/?token={token}",
        f"From another machine: http://192.0.2.7:8001/?token={token}",
    ]
    assert "listens on 192.0.2.7:8001" in err


def test_ui_prints_no_line_for_other_machines_when_the_server_does_not_answer(capsys, monkeypatch):
    """An older server (no /api/access) at an upgrade, or an error: the local link still."""
    monkeypatch.setattr(server_run, "access", lambda url, token, timeout=2: None)
    with server_run.take_lock():
        write_info(8001, host="0.0.0.0")
        assert cli.main(["ui", "--no-open"]) == 0
        out, _ = capsys.readouterr()
    assert out == f"http://127.0.0.1:8001/?token={auth.token()}\n"


def test_ui_in_a_container_prints_only_the_link(capsys, monkeypatch):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    answers_access(monkeypatch, None)
    with server_run.take_lock():
        write_info(8765, host="0.0.0.0")
        assert cli.main(["ui", "--no-open"]) == 0
        out, err = capsys.readouterr()
    assert out == f"http://127.0.0.1:8765/?token={auth.token()}\n"
    assert "lado: note: the LADO server runs in a container" in err
    assert "open to other machines" not in err
    assert "From another machine" not in err


def test_ui_in_a_container_with_a_link_keeps_stdout_the_local_link(capsys, monkeypatch):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    monkeypatch.setenv("LADO_LISTEN", "0.0.0.0")
    token = auth.token()
    answers_access(monkeypatch, f"http://kaos.local:8765/?token={token}")
    with server_run.take_lock():
        write_info(8765, host="0.0.0.0")
        assert cli.main(["ui", "--no-open"]) == 0
        out, err = capsys.readouterr()
        assert cli.main(["ui"]) == 0
        shown, _ = capsys.readouterr()
    assert out == f"http://127.0.0.1:8765/?token={token}\n"
    assert f"From another machine: http://kaos.local:8765/?token={token}\n" in err
    assert "listens on 0.0.0.0:8765, open to other machines" in err
    assert shown.splitlines() == [
        f"http://127.0.0.1:8765/?token={token}",
        "Open it in your browser on the host.",
        f"From another machine: http://kaos.local:8765/?token={token}",
    ]


def test_access_is_none_when_the_server_does_not_answer_it():
    with socket.socket() as closed:
        closed.bind(("127.0.0.1", 0))
        port = closed.getsockname()[1]
    assert server_run.access(f"http://127.0.0.1:{port}", "t", timeout=1) is None


def test_ui_in_a_container_opens_no_browser(capsys, monkeypatch):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    answers_access(monkeypatch, None)
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


def test_ui_starts_a_server_on_the_host_and_port_it_is_given(capsys, monkeypatch):
    started = []
    monkeypatch.setattr(
        server_run, "start_background", lambda host, port: started.append((host, port))
    )
    monkeypatch.setattr(server_run, "wait_ready", lambda started: NEW_SERVER)
    assert cli.main(["ui", "--no-open", "--host", "0.0.0.0", "--port", "8001"]) == 0
    assert cli.main(["ui", "--no-open"]) == 0
    assert started == [("0.0.0.0", 8001), (None, None)]


def test_the_server_is_started_with_its_host_and_port(monkeypatch):
    argv = []
    monkeypatch.setattr(
        server_run.subprocess, "Popen", lambda args, **kwargs: argv.append(args[-5:])
    )
    server_run.start_background("0.0.0.0", 8001)
    server_run.start_background(None, None)
    assert argv[0] == ["server", "--host", "0.0.0.0", "--port", "8001"]
    assert argv[1][-1] == "server"


OLD_SERVER = {
    "url": "http://127.0.0.1:8001",
    "host": "127.0.0.1",  # as `running` reads it from a server.json without one
    "port": 8001,
    "pid": 4321,
    "version": "0.0.1",
}
NEW_SERVER = {**OLD_SERVER, "pid": 4322, "version": __version__}


@pytest.fixture
def old_server(monkeypatch):
    """`lado ui` against a running server of another version, with the run helpers
    replaced; returns the calls made to them."""
    calls = []
    monkeypatch.setattr(server_run, "running", lambda: OLD_SERVER)

    def stop():
        calls.append("stop")
        return OLD_SERVER

    def start_background(host, port):
        calls.append(("start", host, port))
        return "started"

    def wait_ready(started):
        calls.append(("wait", started))
        return NEW_SERVER

    monkeypatch.setattr(server_run, "stop", stop)
    monkeypatch.setattr(server_run, "start_background", start_background)
    monkeypatch.setattr(server_run, "wait_ready", wait_ready)
    return calls


def test_ui_restarts_a_server_of_another_version_on_its_port(capsys, old_server):
    assert cli.main(["ui", "--no-open"]) == 0
    assert old_server == ["stop", ("start", "127.0.0.1", 8001), ("wait", "started")]
    out, err = capsys.readouterr()
    assert out == f"http://127.0.0.1:8001/?token={auth.token()}\n"  # stdout: the link only
    assert err.splitlines()[0] == f"lado: restarted the LADO server: 0.0.1 -> {__version__}"
    assert "warning: the running" not in err


def test_ui_restarts_a_server_of_another_version_on_its_host(capsys, monkeypatch, old_server):
    monkeypatch.setattr(server_run, "running", lambda: {**OLD_SERVER, "host": "0.0.0.0"})
    assert cli.main(["ui", "--no-open"]) == 0
    assert old_server == ["stop", ("start", "0.0.0.0", 8001), ("wait", "started")]


def test_ui_with_another_host_refuses_a_server_of_another_version_too(capsys, old_server):
    """Before the restart: an old server's host is 127.0.0.1, and the restart keeps it."""
    assert cli.main(["ui", "--no-open", "--host", "0.0.0.0"]) == 1
    assert old_server == []
    assert "`lado server stop`" in capsys.readouterr().err


def test_ui_with_another_port_refuses_a_server_of_another_version_too(capsys, old_server):
    assert cli.main(["ui", "--no-open", "--port", "8002"]) == 1
    assert old_server == []
    assert "not on port 8002" in capsys.readouterr().err


def test_ui_names_lado_server_stop_when_the_old_server_does_not_stop(
    capsys, monkeypatch, old_server
):
    def stop():
        raise runtime.LadoError("the LADO server (pid 4321) did not end in 10s")

    monkeypatch.setattr(server_run, "stop", stop)
    assert cli.main(["ui", "--no-open"]) == 1
    assert old_server == []
    err = capsys.readouterr().err
    assert "0.0.1" in err and "did not end in 10s" in err and "`lado server stop`" in err


def test_ui_names_lado_server_stop_when_the_old_server_cannot_be_signalled(
    capsys, monkeypatch, old_server
):
    def stop():
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(server_run, "stop", stop)
    assert cli.main(["ui", "--no-open"]) == 1
    assert old_server == []
    assert "`lado server stop`" in capsys.readouterr().err


def test_ui_names_server_log_when_the_server_does_not_come_up(capsys, monkeypatch):
    monkeypatch.setattr(server_run, "start_background", lambda host, port: None)
    monkeypatch.setattr(server_run, "READY_TIMEOUT", 0.2)
    assert cli.main(["ui", "--no-open"]) == 1
    assert str(state.home() / "server.log") in capsys.readouterr().err


def test_server_refuses_an_ipv6_host(capsys):
    assert cli.main(["server", "--host", "::"]) == 1
    assert "IPv6 is not supported yet" in capsys.readouterr().err


def test_update_tells_the_version_and_a_newer_one(client, published):
    published(**{"99.0.0": "2026-10-04"})
    answer = authorized(client).get("/api/update").json()
    assert answer["current"] == __version__
    assert (answer["latest"], answer["available"]) == ("99.0.0", "99.0.0")
    assert answer["checked_at"]
    assert client.get("/api/update").json() == answer  # the cache, no new look
    assert (state.home() / "update-check.json").exists()


def test_update_of_the_latest_version_and_with_the_check_off(client, published, monkeypatch):
    published(**{__version__: "2026-10-04"})
    answer = authorized(client).get("/api/update").json()
    assert (answer["latest"], answer["available"]) == (__version__, None)
    monkeypatch.setenv("LADO_NO_UPDATE_CHECK", "1")
    (state.home() / "update-check.json").unlink()
    off = client.get("/api/update").json()
    assert (off["current"], off["latest"], off["available"], off["checked_at"]) == (
        __version__,
        None,
        None,
        None,
    )


def test_update_needs_the_token(client):
    assert client.get("/api/update").status_code == 401
