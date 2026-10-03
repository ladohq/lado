"""The UI server (lado.server): token, authorization, the API, and finding the one server of
a LADO_HOME. In process, with FastAPI's test client; the server as a process is in
tests/integration/test_server_process.py."""

import json
import os
import socket
import sqlite3
import stat
from pathlib import Path

import pytest
from agent_helpers import previous_schema
from fastapi.testclient import TestClient

from lado import __version__, cli, loop, runtime, state
from lado.server import app as server_app
from lado.server import auth
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


def test_health_needs_no_token(client):
    answer = client.get("/api/health")
    assert answer.status_code == 200
    assert answer.json() == {"ok": True, "version": __version__}


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
    runtime.start_session(str(repo), "s", None)
    runtime.start_session(str(repo), "t", None)
    runtime.stop_session("t")
    held = loop.take_lock("s")
    answer = authorized(client).get("/api/sessions")
    held.close()
    none = {"gates": 0, "questions": 0, "agents": 0}
    assert answer.json() == [
        {"name": "s", "repo": str(repo), "status": "running", "agents": 1, "waiting": none},
        {"name": "t", "repo": str(repo), "status": "stopped", "agents": 0, "waiting": none},
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


@pytest.mark.parametrize("path", ["/assets/none.js", "/assets/x", "/none.css", "/old.js"])
def test_a_missing_file_of_the_bundle_is_404_not_the_page(bundle, path):
    """After an upgrade an open tab asking for an old file gets 404, not HTML instead of JS."""
    answer = bundle.get(path)
    assert answer.status_code == 404
    assert "bundle" not in answer.text


@pytest.mark.parametrize("path", ["/sessions/a.b", "/sessions/my%20app.v2/flows", "/gates/x.js"])
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
    """A link from a notification (/gates/12?token=...) leads straight to the gate."""
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


def test_only_localhost_is_served():
    for host in ("127.0.0.1", "localhost"):
        server_run.check_host(host)
    with pytest.raises(runtime.LadoError, match="only on 127.0.0.1"):
        server_run.check_host("0.0.0.0")


def test_a_busy_port_is_skipped_for_the_next_free_one():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        first = busy.getsockname()[1]
        sock = server_run.bind("127.0.0.1", None, first=first, last=first + 10)
        with sock:
            assert first < sock.getsockname()[1] <= first + 10


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


def write_info(port: int, version: str = __version__, pid: int | None = None) -> None:
    info = {"url": f"http://127.0.0.1:{port}", "port": port, "pid": pid or os.getpid()}
    server_run.info_path().write_text(json.dumps({**info, "version": version}))


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
    assert f"http://127.0.0.1:8001/?token={auth.token()}" in capsys.readouterr().out
    lock.close()


def test_ui_warns_about_a_server_of_another_version(capsys):
    lock = server_run.take_lock()
    write_info(8001, version="0.0.1")
    assert cli.main(["ui", "--no-open"]) == 0
    err = capsys.readouterr().err
    assert "0.0.1" in err and "lado server stop" in err
    lock.close()


def test_ui_names_server_log_when_the_server_does_not_come_up(capsys, monkeypatch):
    monkeypatch.setattr(server_run, "start_background", lambda port: None)
    monkeypatch.setattr(server_run, "READY_TIMEOUT", 0.2)
    assert cli.main(["ui", "--no-open"]) == 1
    assert str(state.home() / "server.log") in capsys.readouterr().err


def test_server_refuses_another_host(capsys):
    assert cli.main(["server", "--host", "0.0.0.0"]) == 1
    assert "only on 127.0.0.1" in capsys.readouterr().err
