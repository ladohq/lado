"""A model API that answers every request at once with 401: the smoke tests' endpoint
(tests/smoke/) and the container tests' (tests/container/, which run it in the image as a
script). Standard library only: it runs with the image's Python under -I.

    python fake_endpoint.py <port> <log file>   # 127.0.0.1:<port>, one JSON line per request
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
    """Answers every request at once with 401, and keeps the method and path of each and, in
    `tools`, the names of the tools it offers (with `log`, appends them to that file as a JSON
    line)."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0, log: Path | None = None):
        self.requests: list[tuple[str, str]] = []
        self.tools: list[list[str]] = []
        kept_together = threading.Lock()  # the n-th of `tools` is the n-th request's
        endpoint = self

        class Handler(BaseHTTPRequestHandler):
            def answer(self):
                length = int(self.headers.get("Content-Length") or 0)
                names = tool_names(self.rfile.read(length))
                with kept_together:
                    endpoint.requests.append((self.command, self.path))
                    endpoint.tools.append(names)
                if log is not None:
                    line = {"method": self.command, "path": self.path, "tools": names}
                    with log.open("a") as kept:
                        kept.write(json.dumps(line) + "\n")
                body = ANTHROPIC_401 if "/messages" in self.path else OPENAI_401
                data = json.dumps(body).encode()
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


if __name__ == "__main__":
    Endpoint(port=int(sys.argv[1]), log=Path(sys.argv[2]))._thread.join()
