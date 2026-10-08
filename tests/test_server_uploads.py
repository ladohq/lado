"""The human's files in the UI server's API: the upload, the limits the UI checks against
and a message that attaches them. In process, with FastAPI's test client."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from lado import artifacts, runtime, state
from lado.server import app as server_app
from lado.server import auth

PORT = 8123
OWN = "http://testserver"  # the test client's Host
UPLOAD = "/api/sessions/s/artifacts"
MESSAGES = "/api/sessions/s/messages"
ABC = "ba7816bf"  # the start of sha256(b"abc")


@pytest.fixture
def client():
    client = TestClient(server_app.create_app(auth.token(), PORT))
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    client.headers["origin"] = OWN
    return client


@pytest.fixture
def session(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task", name="w1")
    return "s"


def test_an_upload_gives_the_artifact_with_its_record(client, session):
    answer = client.post(UPLOAD, params={"file_name": "Shot 1.PNG"}, content=b"abc")
    assert answer.status_code == 200
    info = answer.json()
    assert (info["full_name"], info["scope"], info["title"]) == (f"shot-1-{ABC}.png", "", "Shot 1.PNG")
    latest = info["latest"]
    assert (latest["author"], latest["media_type"], latest["size"]) == ("human", "image/png", 3)
    again = client.post(UPLOAD, params={"file_name": "Shot 1.PNG"}, content=b"abc").json()
    assert again["latest"]["id"] == latest["id"]
    assert len(artifacts.of_session("s")) == 1


def test_an_upload_to_a_stopped_session_or_without_a_name_is_refused(client, session):
    answer = client.post(UPLOAD, params={"file_name": " "}, content=b"abc")
    assert (answer.status_code, answer.json()["detail"]) == (400, "the file has no name")
    runtime.stop_session("s")
    answer = client.post(UPLOAD, params={"file_name": "a.txt"}, content=b"abc")
    assert answer.status_code == 400
    assert 'session "s" is stopped' in answer.json()["detail"]
    assert client.post("/api/sessions/x/artifacts", params={"file_name": "a"}).status_code == 404


def test_an_upload_needs_the_token_and_the_servers_own_origin(session):
    anonymous = TestClient(server_app.create_app(auth.token(), PORT))
    anonymous.headers["origin"] = OWN
    assert anonymous.post(UPLOAD, params={"file_name": "a.txt"}, content=b"a").status_code == 401
    foreign = TestClient(server_app.create_app(auth.token(), PORT))
    foreign.cookies.set(auth.cookie_name(PORT), auth.token())
    foreign.headers["origin"] = "http://evil.example"
    assert foreign.post(UPLOAD, params={"file_name": "a.txt"}, content=b"a").status_code == 403
    assert artifacts.of_session("s") == []


def _asgi_upload(app, chunks, length=None):
    """POST the upload straight to the ASGI app, a chunk per receive, counting how many
    the app asked for: the test client would read the whole body first."""
    asked = []
    headers = [
        (b"host", b"testserver"),
        (b"origin", OWN.encode()),
        (b"cookie", f"{auth.cookie_name(PORT)}={auth.token()}".encode()),
    ]
    if length is not None:
        headers.append((b"content-length", str(length).encode()))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": UPLOAD,
        "raw_path": UPLOAD.encode(),
        "query_string": b"file_name=big.log",
        "headers": headers,
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 1),
        "root_path": "",
    }
    sent = []

    async def receive():
        n = len(asked)
        asked.append(n)
        if n < len(chunks):
            return {"type": "http.request", "body": chunks[n], "more_body": n + 1 < len(chunks)}
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    return status, len(asked)


def test_an_upload_over_the_limit_is_413_having_read_no_more_than_the_limit(
    session, monkeypatch
):
    monkeypatch.setattr(artifacts, "MAX_SIZE", 10)
    app = server_app.create_app(auth.token(), PORT)
    status, asked = _asgi_upload(app, [b"x" * 4] * 100)
    assert status == 413
    assert asked == 3  # 12 bytes: over 10 + 1
    status, asked = _asgi_upload(app, [b"x" * 4] * 100, length=400)
    assert (status, asked) == (413, 0)  # its length says so: nothing read
    assert artifacts.of_session("s") == []
    status, _ = _asgi_upload(app, [b"x" * 5, b"x" * 5])
    assert status == 200


def test_the_limits_the_ui_checks_against_are_the_cores(client):
    answer = client.get("/api/limits")
    assert answer.status_code == 200
    limits = answer.json()
    assert limits["extensions"]["png"] == "image/png"
    assert limits["extensions"] == artifacts.EXTENSIONS
    assert (limits["max_size"], limits["max_files"]) == (25 * 1024 * 1024, 10)
    assert (limits["image_limit"], limits["image_max_side"]) == (3_932_160, 8000)
    assert limits["max_message"] == runtime.MAX_MESSAGE
    assert limits["agent_images"] == ["image/png", "image/jpeg", "image/gif", "image/webp"]
    assert limits["text_types"] == ["application/json", "image/svg+xml"]


def test_the_limits_need_the_token():
    anonymous = TestClient(server_app.create_app(auth.token(), PORT))
    assert anonymous.get("/api/limits").status_code == 401


def test_a_message_attaches_the_uploaded_files(client, session):
    name = client.post(UPLOAD, params={"file_name": "a.txt"}, content=b"abc").json()["full_name"]
    answer = client.post(MESSAGES, json={"to": "w1", "text": "", "artifacts": [name]})
    assert answer.status_code == 200
    message, copy = state.list_messages("s")[-2:]
    assert (message.recipient, message.summary, message.attachments) == ("w1", f"1 file: {name}", 1)
    assert copy.summary == f"human wrote to w1: 1 file: {name} (#{message.id}, 1 file)"
    chat = client.get(MESSAGES, params={"with": "human"}).json()["items"]
    assert [a["full_name"] for a in chat[-1]["attachments"]] == [name]


def test_a_message_with_an_unknown_file_is_refused_with_nothing_queued(client, session):
    before = state.list_messages("s")
    answer = client.post(MESSAGES, json={"text": "see", "artifacts": ["nothing"]})
    assert (answer.status_code, answer.json()["detail"]) == (
        400,
        'no artifact "nothing" in session s',
    )
    assert client.post(MESSAGES, json={"text": ""}).status_code == 400
    assert state.list_messages("s") == before
