"""A model API that answers every request at once with 401: the smoke tests' endpoint
(tests/smoke/) and the container tests' (tests/container/, which run it in the image as a
script). Standard library only: it runs with the image's Python under -I.

    python fake_endpoint.py <port> <log file>   # 127.0.0.1:<port>, one JSON line per request

`Anthropic` is the smoke tests' server of that API that does answer: the probe of a model server
as `fake_model_server`'s "anthropic" profile, and a scripted turn in Anthropic's streaming form.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# The error each API gives a request with a wrong key; the CLIs end the turn on it and do not
# retry (a closed port would give them a transient error to retry with their own backoff).
ANTHROPIC_401 = {
    "type": "error",
    "error": {"type": "authentication_error", "message": "invalid x-api-key"},
}
OPENAI_401 = {
    "error": {
        "message": "Incorrect API key provided",
        "type": "invalid_request_error",
        "code": "invalid_api_key",
    }
}


def model_name(body: bytes) -> str:
    """The model a request asks for (its `model`); "" for none or a body that is not JSON."""
    try:
        request = json.loads(body)
    except ValueError:
        return ""
    model = request.get("model") if isinstance(request, dict) else None
    return model if isinstance(model, str) else ""


def tool_names(body: bytes) -> list[str]:
    """The names of the tools a request offers the model: its `tools` and those of its input
    items of type `additional_tools` (where Codex 0.162 puts a newer model's), a namespace's
    as `<namespace>.<name>`. No names for a body that is not JSON (a compressed one)."""
    try:
        request = json.loads(body)
    except ValueError:
        return []
    if not isinstance(request, dict):
        return []
    tools = list(request.get("tools") or [])
    for item in request.get("input") or []:
        if isinstance(item, dict) and item.get("type") == "additional_tools":
            tools += item.get("tools") or []
    names = []
    for tool in tools:
        if tool.get("type") == "namespace":
            names += [f"{tool['name']}.{inner['name']}" for inner in tool.get("tools") or []]
        else:
            names.append(tool.get("name"))
    return names


class Endpoint:
    """Answers every request at once with 401, and keeps the method and path of each, in
    `tools` the names of the tools it offers and in `models` the model it asks for (with
    `log`, appends them to that file as a JSON line)."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0, log: Path | None = None):
        self.requests: list[tuple[str, str]] = []
        self.tools: list[list[str]] = []
        self.models: list[str] = []
        kept_together = threading.Lock()  # the n-th of `tools` is the n-th request's
        endpoint = self

        class Handler(BaseHTTPRequestHandler):
            def answer(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length)
                names = tool_names(body)
                with kept_together:
                    endpoint.requests.append((self.command, self.path))
                    endpoint.tools.append(names)
                    endpoint.models.append(model_name(body))
                if log is not None:
                    line = {"method": self.command, "path": self.path, "tools": names}
                    with log.open("a") as kept:
                        kept.write(json.dumps(line) + "\n")
                error = ANTHROPIC_401 if "/messages" in self.path else OPENAI_401
                data = json.dumps(error).encode()
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = answer

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer((host, port), Handler)
        self.url = f"http://{host}:{self.server.server_address[1]}"
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


# What makes `Anthropic` script a turn: a message that holds this runs the shell tool, then an MCP
# tool of LADO's, then ends the turn; any other request gets a line of text.
RUN_TOOLS = "SMOKE-RUN-TOOLS"
SHELL_TOOL = "Bash"
MCP_TOOL = "mcp__lado__list_agents"
SHELL_CALL, MCP_CALL = "toolu_smoke_shell", "toolu_smoke_mcp"


def _tool_use(call: str, name: str, tool_input: dict) -> dict:
    return {"type": "tool_use", "id": call, "name": name, "input": tool_input}


def _text(text: str) -> dict:
    return {"type": "text", "text": text}


def _latest(request: dict) -> dict:
    """The newest message of the conversation: Claude Code 2.1.295 ends `messages` with a
    message of the role `system`, its environment."""
    said = [m for m in request.get("messages") or [] if m.get("role") != "system"]
    return said[-1] if said else {}


def _results(message: dict) -> list[str]:
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [b.get("tool_use_id", "") for b in content if b.get("type") == "tool_result"]


def _events(model: str, content: list[dict], stop_reason: str) -> list[tuple[str, dict]]:
    """A message's stream: the names and the bodies of its server-sent events."""
    usage = {"input_tokens": 1, "output_tokens": 1}
    message = {
        "id": "msg_smoke",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [],
        "stop_reason": None,
        "stop_sequence": None,
        "usage": usage,
    }
    events = [("message_start", {"message": message})]
    for index, block in enumerate(content):
        if block["type"] == "text":
            start = _text("")
            delta = {"type": "text_delta", "text": block["text"]}
        else:
            start = {**block, "input": {}}
            delta = {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}
        events += [
            ("content_block_start", {"index": index, "content_block": start}),
            ("content_block_delta", {"index": index, "delta": delta}),
            ("content_block_stop", {"index": index}),
        ]
    done = {"stop_reason": stop_reason, "stop_sequence": None}
    return [*events, ("message_delta", {"delta": done, "usage": usage}), ("message_stop", {})]


class Anthropic:
    """A server of Anthropic's Messages API on 127.0.0.1 with the model `model` and, with `key`,
    a 401 for a request that carries it in neither `x-api-key` nor `Authorization`. `requests`
    keeps each request as (path, its headers by lower-case name, its body); `marker` is the file
    the scripted shell tool makes."""

    def __init__(self, model: str, marker: Path, key: str | None = None):
        self.requests: list[tuple[str, dict[str, str], bytes]] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def json(self, status: int, answer: object) -> None:
                data = json.dumps(answer).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def stream(self, events: list[tuple[str, dict]]) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for name, body in events:
                    data = json.dumps({"type": name, **body})
                    self.wfile.write(f"event: {name}\ndata: {data}\n\n".encode())

            def answer(self):
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                path = self.path.partition("?")[0]
                headers = {name.lower(): value for name, value in self.headers.items()}
                fake.requests.append((path, headers, body))
                given = {headers.get("x-api-key"), headers.get("authorization")}
                if key is not None and not given & {key, f"Bearer {key}"}:
                    self.json(401, ANTHROPIC_401)
                elif (self.command, path) == ("GET", "/v1/models"):
                    listed = {"type": "model", "id": model, "display_name": model}
                    self.json(200, {"data": [listed], "has_more": False})
                elif (self.command, path) == ("POST", "/v1/messages/count_tokens"):
                    self.json(200, {"input_tokens": 1})
                elif (self.command, path) == ("POST", "/v1/messages"):
                    self.messages(body)
                else:
                    self.send_error(404)

            def messages(self, body: bytes) -> None:
                request = json.loads(body) if body else {}
                if not request.get("model"):
                    error = {"type": "invalid_request_error", "message": "model: Field required"}
                    self.json(400, {"type": "error", "error": error})
                    return
                content, stop_reason = fake.turn(request)
                self.stream(_events(request["model"], content, stop_reason))

            do_GET = do_POST = do_HEAD = answer

            def log_message(self, *args):
                pass

        self.marker = marker
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def turn(self, request: dict) -> tuple[list[dict], str]:
        """The next step of the script for `request`: its content and stop reason."""
        latest = _latest(request)
        results = _results(latest)
        if SHELL_CALL in results and MCP_CALL not in results:  # a turn's results stay together
            return [_tool_use(MCP_CALL, MCP_TOOL, {})], "tool_use"
        offered = {tool.get("name") for tool in request.get("tools") or []}
        if not results and SHELL_TOOL in offered and RUN_TOOLS in json.dumps(latest):
            command = {"command": f"touch '{self.marker}'", "description": "the smoke's marker"}
            return [_tool_use(SHELL_CALL, SHELL_TOOL, command)], "tool_use"
        return [_text("done")], "end_turn"

    def tool_results(self) -> list[str]:
        """The ids of the tool calls whose results came back."""
        found = []
        for path, _, body in self.requests:
            if path == "/v1/messages" and body:
                found += _results(_latest(json.loads(body)))
        return found

    def close(self):
        self.server.shutdown()
        self.server.server_close()


if __name__ == "__main__":
    Endpoint(port=int(sys.argv[1]), log=Path(sys.argv[2]))._thread.join()
