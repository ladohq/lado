"""A model server of a kind the probe knows (lado.model_servers), or a server that only
looks like one: the probe's tests run it in process, the integration tests as a script.
Standard library only.

    python fake_model_server.py <profile> <port file> [<key>]   # 127.0.0.1, port written

Each profile says how the server answers the paths the probe asks; every other request gets
404 with a plain text body, as a web server would. With a key, a request without
`Authorization: Bearer <key>` gets 401 first.
"""

from __future__ import annotations

import json
import sys
import threading
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import NamedTuple

MODELS = "/v1/models"
OLLAMA_VERSION = "/api/version"
LMSTUDIO_MODELS = "/api/v0/models"
CHAT = "/v1/chat/completions"
RESPONSES = "/v1/responses"
MESSAGES = "/v1/messages"
CONTROL = "/v1/lado-no-such-api"


class Answer(NamedTuple):
    status: int
    body: object = None  # JSON; a str is sent as text/plain
    headers: tuple[tuple[str, str], ...] = ()


def openai_list(*ids: str) -> Answer:
    return Answer(200, {"object": "list", "data": [{"id": i, "object": "model"} for i in ids]})


def anthropic_list(*ids: str) -> Answer:
    data = [{"type": "model", "id": i, "display_name": i} for i in ids]
    return Answer(200, {"data": data, "has_more": False})


# How a server refuses an empty body on an API it has: it parsed the request, and wants a
# model and input.
OPENAI_400 = Answer(400, {"error": {"message": "missing model", "type": "invalid_request_error"}})
ANTHROPIC_400 = Answer(
    400,
    {
        "type": "error",
        "error": {"type": "invalid_request_error", "message": "model: Field required"},
    },
)
VALIDATION_422 = Answer(422, {"detail": [{"loc": ["body", "model"], "msg": "Field required"}]})
NOT_FOUND = Answer(404, "404 page not found")

OLLAMA_MODELS = ("llama3.1:8b", "qwen2.5-coder:7b")

PROFILES: dict[str, dict[tuple[str, str], Answer]] = {
    # An OpenAI-compatible server with chat completions only (vLLM, an older gateway).
    "openai": {("GET", MODELS): openai_list("gpt-oss-20b"), ("POST", CHAT): OPENAI_400},
    # Ollama: its own version, the OpenAI-compatible list, chat completions and Responses.
    "ollama": {
        ("GET", MODELS): openai_list(*OLLAMA_MODELS),
        ("GET", OLLAMA_VERSION): Answer(200, {"version": "0.12.3"}),
        ("POST", CHAT): OPENAI_400,
        ("POST", RESPONSES): OPENAI_400,
    },
    # Ollama whose model list fails.
    "list-500": {
        ("GET", MODELS): Answer(500, {"error": "internal error"}),
        ("GET", OLLAMA_VERSION): Answer(200, {"version": "0.12.3"}),
        ("POST", CHAT): OPENAI_400,
        ("POST", RESPONSES): OPENAI_400,
    },
    # LM Studio: its own REST API's list beside the OpenAI-compatible one.
    "lmstudio": {
        ("GET", MODELS): openai_list("qwen3-8b"),
        ("GET", LMSTUDIO_MODELS): Answer(200, {"object": "list", "data": [{"id": "qwen3-8b"}]}),
        ("POST", CHAT): OPENAI_400,
        ("POST", RESPONSES): OPENAI_400,
    },
    # An Anthropic-compatible server: Anthropic's list and the Messages API.
    "anthropic": {("GET", MODELS): anthropic_list("claude-x"), ("POST", MESSAGES): ANTHROPIC_400},
    # A server with the Responses API alone, and no list.
    "responses-only": {("POST", RESPONSES): OPENAI_400},
    # A server with no list that proves the Messages API alone.
    "messages-only": {("POST", MESSAGES): ANTHROPIC_400},
    # A server with all three APIs; the Responses API refuses with a validation error.
    "all": {
        ("GET", MODELS): openai_list("m1"),
        ("POST", CHAT): OPENAI_400,
        ("POST", RESPONSES): VALIDATION_422,
        ("POST", MESSAGES): ANTHROPIC_400,
    },
    # A list and no API: 405, a 400 that is not JSON and 404.
    "models-only": {
        ("GET", MODELS): openai_list("m1"),
        ("POST", CHAT): Answer(405, {"error": "method not allowed"}),
        ("POST", RESPONSES): Answer(400, "Bad Request"),
    },
    "empty-list": {("GET", MODELS): openai_list(), ("POST", CHAT): OPENAI_400},
    # A web server: 404 to everything.
    "unknown": {},
    # A gateway that answers 400 with JSON to every path, and the same with a list.
    "gateway-400": {"*": OPENAI_400},
    "gateway-400-list": {"*": OPENAI_400, ("GET", MODELS): openai_list("m1")},
    # A server that forbids everything.
    "forbidden": {"*": Answer(403, {"error": "forbidden"})},
}
# Answers without a table: "redirect" (301 to the location given), "hang" (never answers).
SPECIAL = ("redirect", "hang")


class Request(NamedTuple):
    method: str
    path: str
    headers: Message  # a header's name in any case
    body: bytes


class Server:
    """The fake on 127.0.0.1 (a free port, or `port`), answering as its profile says under
    `prefix` (a gateway's path, e.g. "/llm"); `requests` keeps each request it received."""

    def __init__(
        self,
        profile: str,
        *,
        key: str | None = None,
        location: str = "",
        prefix: str = "",
        port: int = 0,
    ):
        if profile not in PROFILES and profile not in SPECIAL:
            raise ValueError(f"unknown profile {profile}")
        self.requests: list[Request] = []
        self.closing = threading.Event()
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def answer(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length)
                fake.requests.append(Request(self.command, self.path, self.headers, body))
                if profile == "hang":
                    fake.closing.wait()
                    return
                self.send(fake.answer_for(self.command, self.path, self.headers))

            def send(self, answer: Answer):
                if isinstance(answer.body, str):
                    data, kind = answer.body.encode(), "text/plain"
                else:
                    data, kind = json.dumps(answer.body).encode(), "application/json"
                self.send_response(answer.status)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(data)))
                for name, value in answer.headers:
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = do_PUT = do_DELETE = answer

            def log_message(self, *args):
                pass

        self._profile, self._key, self._location, self._prefix = profile, key, location, prefix
        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.port = self.server.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}{prefix}"
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def answer_for(self, method: str, path: str, headers) -> Answer:
        if self._key is not None and headers.get("Authorization") != f"Bearer {self._key}":
            return Answer(401, {"error": {"message": "invalid api key"}})
        if self._profile == "redirect":
            return Answer(301, "moved", (("Location", self._location + path),))
        if not path.startswith(self._prefix):
            return NOT_FOUND
        table = PROFILES[self._profile]
        found = table.get((method, path[len(self._prefix) :]))
        return found or table.get("*") or NOT_FOUND

    def paths(self) -> list[tuple[str, str]]:
        return [(r.method, r.path) for r in self.requests]

    def close(self):
        self.closing.set()
        self.server.shutdown()
        self.server.server_close()


if __name__ == "__main__":
    fake = Server(sys.argv[1], key=sys.argv[3] if len(sys.argv) > 3 else None)
    written = Path(sys.argv[2] + ".tmp")  # renamed whole: a reader never sees half of it
    written.write_text(str(fake.port))
    written.replace(sys.argv[2])
    fake._thread.join()
