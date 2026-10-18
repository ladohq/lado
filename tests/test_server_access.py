"""The link that opens LADO on another device and a new one (share-access): GET /api/access
and POST /api/access/new-token, in process with FastAPI's test client. The rule behind the
link: the `Listening` tests of tests/test_server.py; the open streams a new token ends:
tests/test_feed.py and tests/test_terminal_socket.py."""

import pytest
from fastapi.testclient import TestClient

from lado.server import app as server_app
from lado.server import auth
from lado.server import run as server_run

PORT = 8765
OWN = {"origin": "http://testserver"}  # the test client's Host


@pytest.fixture(autouse=True)
def an_address(monkeypatch):
    monkeypatch.setattr(server_run, "network_address", lambda: "192.168.1.23")


def client_for(host: str = "0.0.0.0", container: bool = False, **env: str) -> TestClient:
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
    assert answer.status_code == 200
    assert answer.json() == {
        "link": f"http://kaos.local:{PORT}/?token={auth.token()}",
        "reason": None,
        "port": PORT,
        "container": False,
        "listen": None,
        "note": None,
    }
    assert answer.headers["cache-control"] == "no-store"
    assert "access-control-allow-origin" not in answer.headers


def test_a_bearer_token_reads_it_too():
    client = client_for()
    client.cookies.clear()
    answer = client.get("/api/access", headers={"authorization": f"Bearer {auth.token()}"})
    assert answer.json()["link"] == f"http://192.168.1.23:{PORT}/?token={auth.token()}"


def test_the_address_is_found_anew_for_each_answer(monkeypatch):
    client = client_for()
    monkeypatch.setattr(server_run, "network_address", lambda: "10.0.0.5")
    assert client.get("/api/access").json()["link"].startswith(f"http://10.0.0.5:{PORT}/")


def test_on_loopback_no_link_and_no_token():
    answer = client_for(host="127.0.0.1", LADO_PUBLIC_HOST="kaos.local").get("/api/access")
    assert (answer.json()["reason"], answer.json()["link"]) == ("loopback", None)
    assert auth.token() not in answer.text


def test_in_a_container_without_a_name():
    found = client_for(container=True, LADO_LISTEN="0.0.0.0").get("/api/access").json()
    assert (found["reason"], found["link"], found["listen"], found["container"]) == (
        "no-address",
        None,
        "0.0.0.0",
        True,
    )
    assert found["note"] is None


def test_unknown_carries_the_container_note():
    found = client_for(container=True).get("/api/access").json()
    assert (found["reason"], found["listen"]) == ("unknown", None)
    assert found["note"] == server_run.CONTAINER_NOTE.format(host="0.0.0.0", port=PORT)


def test_a_new_token_logs_others_out_and_keeps_this_browser():
    client = client_for(LADO_PUBLIC_HOST="kaos.local")
    old = auth.token()
    answer = client.post("/api/access/new-token", headers=OWN)
    new = auth.token()
    assert answer.status_code == 200 and new != old
    assert answer.json()["link"] == f"http://kaos.local:{PORT}/?token={new}"
    assert answer.headers["cache-control"] == "no-store"
    assert answer.cookies[auth.cookie_name(PORT)] == new
    assert "httponly" in answer.headers["set-cookie"].lower()
    assert client.get("/api/sessions").status_code == 200  # with the cookie of the answer
    other = TestClient(client.app)
    other.cookies.set(auth.cookie_name(PORT), old)
    assert other.get("/api/sessions").status_code == 401
    bearer = {"authorization": f"Bearer {old}"}
    assert TestClient(client.app).get("/api/sessions", headers=bearer).status_code == 401


def test_a_new_token_without_a_link_holds_no_token():
    client = client_for(host="127.0.0.1")
    answer = client.post("/api/access/new-token", headers=OWN)
    assert answer.status_code == 200 and answer.json()["reason"] == "loopback"
    assert auth.token() not in answer.text  # the cookie is in a header, not the body
    assert client.get("/api/sessions").status_code == 200


def test_two_new_tokens_in_a_row_from_one_tab():
    client = client_for()
    assert client.post("/api/access/new-token", headers=OWN).status_code == 200
    assert client.post("/api/access/new-token", headers=OWN).status_code == 200
    assert client.get("/api/sessions").status_code == 200


def test_a_new_token_from_another_origin_is_refused():
    client = client_for()
    old = auth.token()
    answer = client.post("/api/access/new-token", headers={"origin": "http://evil.example"})
    assert answer.status_code == 403 and auth.token() == old


def test_a_new_token_ends_the_streams_and_the_terminals(monkeypatch):
    client = client_for()
    ended = []

    async def close_all():
        ended.append("terminals")

    monkeypatch.setattr(client.app.state.hub, "end_streams", lambda: ended.append("feed"))
    monkeypatch.setattr(server_app.terminals, "close_all", close_all)
    client.post("/api/access/new-token", headers=OWN)
    assert ended == ["feed", "terminals"]
