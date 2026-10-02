"""An agent's terminal through the UI server (lado.server.terminals): who may open the
WebSocket (token and Origin), its frames, backpressure and how it ends; the history and the
agents endpoints. In process with FastAPI's test client and a made-up terminal; with real tmux
and the fake agent: tests/integration/test_terminal_socket.py."""

import asyncio
import json
import queue
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from lado import runtime, state, terminal
from lado.server import app as server_app
from lado.server import auth, terminals

PORT = 8123
OWN = f"http://127.0.0.1:{PORT}"
URL = "/api/sessions/s/agents/supervisor/terminal"


class FakeTerminal:
    """A terminal whose output the test gives (None ends it) and whose window it sizes."""

    def __init__(self, session: str, agent: str, mode: str):
        self.session, self.agent, self.mode = session, agent, mode
        self.output: queue.Queue[bytes | None] = queue.Queue()
        self.written: list[bytes] = []
        self.size = self.window = (80, 24)
        self.closed = False

    def read(self, timeout: float = 0.25) -> bytes | None:
        try:
            return self.output.get(timeout=timeout)
        except queue.Empty:
            return b""

    def write(self, data: bytes) -> None:
        if self.mode != terminal.CONTROL:
            raise terminal.ReadOnly("view")
        self.written.append(data)

    def resize(self, size: tuple[int, int]) -> None:
        self.size = size

    def follow_window(self) -> tuple[int, int] | None:
        if self.window == self.size:
            return None
        self.size = self.window
        return self.size

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def terms(monkeypatch):
    """The terminals the server opens, made up; `ended` says why one ended."""
    opened: list[FakeTerminal] = []

    def open_(session, agent, mode):
        terminal._check(session, agent)
        opened.append(FakeTerminal(session, agent, mode))
        return opened[-1]

    monkeypatch.setattr(terminal, "open", open_)
    monkeypatch.setattr(terminals, "SIZE_EVERY", 0.05)
    return opened


@pytest.fixture
def session(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)


@pytest.fixture
def client():
    return TestClient(server_app.create_app(auth.token(), PORT))


def headers(origin: str | None = OWN, bearer: bool = False) -> dict[str, str]:
    found = {"origin": origin} if origin else {}
    if bearer:
        found["authorization"] = f"Bearer {auth.token()}"
    return found


def logged_in(client: TestClient) -> TestClient:
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    return client


def closed(ws) -> tuple[int, str]:
    """The close frame that comes next: its code and reason."""
    message = ws.receive()
    assert message["type"] == "websocket.close", message
    return message["code"], message.get("reason", "")


@pytest.mark.parametrize("origin", [OWN, f"http://localhost:{PORT}"])
def test_the_servers_own_origin_with_the_cookie_opens_it(client, session, terms, origin):
    with logged_in(client).websocket_connect(URL, headers=headers(origin)) as ws:
        assert ws.receive_json() == {"type": "size", "cols": 80, "rows": 24}
    assert [t.mode for t in terms] == ["view"]


@pytest.mark.parametrize(
    "origin", ["http://evil.example", f"http://127.0.0.1:{PORT + 1}", f"https://127.0.0.1:{PORT}"]
)
def test_another_origin_is_refused_before_the_upgrade(client, session, terms, origin):
    with pytest.raises(WebSocketDisconnect) as refused:
        with logged_in(client).websocket_connect(URL, headers=headers(origin, bearer=True)):
            pass
    assert refused.value.code == 1008
    assert terms == []


def test_without_an_origin_only_a_bearer_token_opens_it(client, session, terms):
    with pytest.raises(WebSocketDisconnect):
        with logged_in(client).websocket_connect(URL, headers=headers(None)):
            pass
    with TestClient(client.app).websocket_connect(URL, headers=headers(None, bearer=True)) as ws:
        assert ws.receive_json()["type"] == "size"
    assert len(terms) == 1


def test_without_the_token_it_ends_at_once_saying_why(client, session, terms):
    with client.websocket_connect(URL, headers=headers()) as ws:
        assert ws.receive_json()["type"] == "error"
        assert closed(ws) == (4401, "no valid token: open the link `lado ui` prints")
    assert terms == []


def test_the_guard_checks_origin_on_any_connection_that_changes_something(monkeypatch):
    guard = auth.Guard("t", PORT)

    class Conn:
        def __init__(self, headers, cookies=None):
            self.headers, self.cookies = headers, cookies or {}

    cookie = {auth.cookie_name(PORT): "t"}
    guard.check(Conn({"origin": OWN}, cookie), changes=True)
    guard.check(Conn({}, cookie))  # reading needs no Origin
    guard.check(Conn({"authorization": "Bearer t"}), changes=True)
    for conn, status in [
        (Conn({}, cookie), 403),
        (Conn({"origin": "http://evil.example"}, cookie), 403),
        (Conn({"origin": OWN}), 401),
        (Conn({"origin": OWN, "authorization": "Bearer x"}), 401),
    ]:
        with pytest.raises(auth.Refused) as refused:
            guard.check(conn, changes=True)
        assert refused.value.status == status


def test_output_comes_as_binary_frames(client, session, terms):
    with logged_in(client).websocket_connect(URL + "?mode=control", headers=headers()) as ws:
        ws.receive_json()  # size
        terms[0].output.put(b"hello \x1b[1mworld")
        assert ws.receive_bytes() == b"hello \x1b[1mworld"


def test_control_takes_input_and_resize(client, session, terms):
    with logged_in(client).websocket_connect(URL + "?mode=control", headers=headers()) as ws:
        ws.receive_json()
        ws.send_text(json.dumps({"type": "input", "data": "ls\r"}))
        ws.send_text(json.dumps({"type": "resize", "cols": 120, "rows": 40}))
        ws.send_text(json.dumps({"type": "input", "data": "é"}))
        terms[0].output.put(b"done")  # in order: once this comes, the input was taken
        assert ws.receive_bytes() == b"done"
    assert terms[0].written == [b"ls\r", "é".encode()]
    assert terms[0].size == (120, 40)


@pytest.mark.parametrize(
    ("frame", "error"),
    [
        ({"type": "input", "data": "rm -rf /\r"}, "open to view: take control to type"),
        ({"type": "resize", "cols": 10, "rows": 5}, "follows the agent's window"),
    ],
)
def test_view_answers_input_and_resize_with_an_error_frame(client, session, terms, frame, error):
    with logged_in(client).websocket_connect(URL + "?mode=view", headers=headers()) as ws:
        ws.receive_json()
        ws.send_text(json.dumps(frame))
        answer = ws.receive_json()
        assert answer["type"] == "error" and error in answer["reason"]
        terms[0].output.put(b"still open")
        assert ws.receive_bytes() == b"still open"
    assert terms[0].written == [] and terms[0].size == (80, 24)


@pytest.mark.parametrize(
    "text", ["not json", "[]", '{"type": "paste"}', '{"type": "input"}', '{"type": "resize"}']
)
def test_a_frame_it_does_not_know_gets_an_error_frame(client, session, terms, text):
    with logged_in(client).websocket_connect(URL + "?mode=control", headers=headers()) as ws:
        ws.receive_json()
        ws.send_text(text)
        assert ws.receive_json()["type"] == "error"
    assert terms[0].written == []


def test_view_follows_the_windows_size(client, session, terms):
    with logged_in(client).websocket_connect(URL, headers=headers()) as ws:
        assert ws.receive_json() == {"type": "size", "cols": 80, "rows": 24}
        terms[0].window = (132, 43)
        assert ws.receive_json() == {"type": "size", "cols": 132, "rows": 43}


def test_no_terminal_ends_it_for_good_with_the_reason(client, session, terms):
    with logged_in(client).websocket_connect(
        "/api/sessions/s/agents/w9/terminal", headers=headers()
    ) as ws:
        assert ws.receive_json() == {"type": "error", "reason": 'no agent "w9" in session "s"'}
        assert closed(ws) == (4404, 'no agent "w9" in session "s"')


def test_a_terminal_that_ends_for_good_closes_with_the_reason_else_to_open_again(
    client, session, terms, monkeypatch
):
    reason = terminal.NoTerminal('session "s" is stopped')
    monkeypatch.setattr(terminal, "ended", lambda session, agent: reason)
    with logged_in(client).websocket_connect(URL, headers=headers()) as ws:
        ws.receive_json()
        terms[0].output.put(None)
        assert closed(ws) == (4404, 'session "s" is stopped')
    monkeypatch.setattr(terminal, "ended", lambda session, agent: None)
    with logged_in(client).websocket_connect(URL, headers=headers()) as ws:
        ws.receive_json()
        terms[1].output.put(None)
        assert closed(ws)[0] == 4500
    assert all(t.closed for t in terms)


def test_a_mode_it_does_not_know_is_refused(client, session, terms):
    with logged_in(client).websocket_connect(URL + "?mode=admin", headers=headers()) as ws:
        assert ws.receive_json()["type"] == "error"
        assert closed(ws)[0] == 4400
    assert terms == []


def test_the_terminal_closes_when_the_browser_goes(client, session, terms):
    with logged_in(client).websocket_connect(URL, headers=headers()) as ws:
        ws.receive_json()
    deadline = time.monotonic() + 5
    while not terms[0].closed:
        assert time.monotonic() < deadline, "the terminal is still open"
        time.sleep(0.02)


def test_the_next_read_waits_until_the_last_output_was_sent():
    """Backpressure: a slow browser slows the reading of the terminal, nothing piles up."""

    class SlowSocket:
        def __init__(self):
            self.sent: list[bytes] = []
            self.go = asyncio.Event()

        async def send_bytes(self, data: bytes) -> None:
            await self.go.wait()
            self.sent.append(data)

        async def send_json(self, data) -> None:
            pass

    class CountingTerminal(FakeTerminal):
        reads = 0

        def read(self, timeout: float = 0.25):
            self.reads += 1
            return b"x" if self.reads < 3 else None

    async def scenario():
        ws, term = SlowSocket(), CountingTerminal("s", "a", "control")
        pump = asyncio.create_task(terminals.output(ws, term))
        await asyncio.sleep(0.2)
        assert term.reads == 1  # the first chunk waits to be sent
        ws.go.set()
        await asyncio.wait_for(pump, 5)
        assert ws.sent == [b"x", b"x"] and term.reads == 3

    asyncio.run(scenario())


def test_history_gives_the_lines_and_whether_the_agent_is_full_screen(client, session, monkeypatch):
    asked = []

    def history(session, agent, lines):
        terminal._check(session, agent)
        asked.append((session, agent, lines))
        return terminal.History("line 1\nline 2\n", False)

    monkeypatch.setattr(terminal, "history", history)
    client = logged_in(client)
    answer = client.get("/api/sessions/s/agents/supervisor/history?lines=500")
    assert answer.json() == {"text": "line 1\nline 2\n", "alternate": False}
    assert asked == [("s", "supervisor", 500)]
    assert client.get("/api/sessions/s/agents/supervisor/history?lines=0").status_code == 422
    missing = client.get("/api/sessions/s/agents/w9/history")
    assert (missing.status_code, missing.json()["detail"]) == (404, 'no agent "w9" in session "s"')
    assert (
        TestClient(client.app).get("/api/sessions/s/agents/supervisor/history").status_code == 401
    )


def test_the_agents_of_a_session(client, session):
    answer = logged_in(client).get("/api/sessions/s/agents")
    assert answer.json() == [
        {"name": "supervisor", "role": "supervisor", "provider": "claude", "status": "starting"}
    ]
    assert logged_in(client).get("/api/sessions/x/agents").status_code == 404
    state.set_status("s", "supervisor", state.IDLE)
    assert logged_in(client).get("/api/sessions/s/agents").json()[0]["status"] == "idle"
