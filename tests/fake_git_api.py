"""The user API of a git server, as the probe of lado.git_servers asks it: GitLab's
`/api/v4/user`, GitHub's `/api/v3/user`, or a server that answers as neither. The probe's
tests run it in process; tests/fake_git_server.py answers the same profiles beside git.
Standard library only.

Each profile says how the two paths answer; every other request gets 404 with a plain text
body, as a web server would. `make_certificate` makes a self-signed certificate for
127.0.0.1 with `openssl`, for a server over TLS that only a test trusts.
"""

from __future__ import annotations

import json
import shutil
import ssl
import subprocess
import threading
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import NamedTuple

import pytest

GITLAB = "/api/v4/user"
GITHUB = "/api/v3/user"
LOGIN = "ivan.petrov"


class Answer(NamedTuple):
    status: int
    body: object = None  # JSON; a str is sent as text/html
    headers: tuple[tuple[str, str], ...] = ()


NOT_FOUND = Answer(404, "<html><body>404 Not Found</body></html>")
GITLAB_USER = Answer(200, {"id": 7, "username": LOGIN, "name": "Ivan Petrov"})
GITHUB_USER = Answer(200, {"id": 7, "login": LOGIN, "type": "User"})
GITLAB_401 = Answer(401, {"message": "401 Unauthorized"})
GITHUB_401 = Answer(401, {"message": "Bad credentials", "status": "401"})
GITLAB_SCOPE = Answer(
    403,
    {"error": "insufficient_scope", "error_description": "The request requires higher privileges"},
)
HANG = Answer(0)  # no answer: the request waits for the server's end

PROFILES: dict[str, dict[str, Answer]] = {
    "gitlab": {GITLAB: GITLAB_USER},
    "github": {GITHUB: GITHUB_USER},
    "gitlab-refuses": {GITLAB: GITLAB_401},
    "github-refuses": {GITHUB: GITHUB_401},
    "gitlab-scope": {GITLAB: GITLAB_SCOPE},
    "both": {GITLAB: GITLAB_USER, GITHUB: GITHUB_USER},
    "neither": {},
    # GitLab's user, and GitHub's path never answering.
    "gitlab-github-hangs": {GITLAB: GITLAB_USER, GITHUB: HANG},
    "hang": {GITLAB: HANG, GITHUB: HANG},
}
REDIRECT = "redirect"  # 302 to the location given, on every path


class Request(NamedTuple):
    method: str
    path: str
    headers: Message


def answer_for(profile: str, path: str, token: str | None, headers: Message) -> Answer:
    """The profile's answer to a GET of `path`; with `token`, a request that does not carry
    it the kind's way gets that kind's 401."""
    found = PROFILES[profile].get(path, NOT_FOUND)
    if token is not None and found not in (NOT_FOUND, HANG):
        if path == GITLAB and headers.get("PRIVATE-TOKEN") != token:
            return GITLAB_401
        if path == GITHUB and headers.get("Authorization") != f"token {token}":
            return GITHUB_401
    return found


def send(handler: BaseHTTPRequestHandler, answer: Answer) -> None:
    if isinstance(answer.body, str):
        data, kind = answer.body.encode(), "text/html"
    else:
        data, kind = json.dumps(answer.body).encode(), "application/json"
    handler.send_response(answer.status)
    handler.send_header("Content-Type", kind)
    handler.send_header("Content-Length", str(len(data)))
    for name, value in answer.headers:
        handler.send_header(name, value)
    handler.end_headers()
    handler.wfile.write(data)


def make_certificate(folder: Path) -> tuple[Path, Path]:
    """A self-signed certificate for 127.0.0.1 and localhost, and its key, in `folder`; the
    test is skipped, naming why, without `openssl`."""
    if shutil.which("openssl") is None:
        pytest.skip("openssl is not installed: no certificate for a TLS server")
    cert, key = folder / "server.crt", folder / "server.key"
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
            "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1,DNS:localhost",
            "-keyout", str(key), "-out", str(cert),
        ],
        check=True,
        capture_output=True,
    )  # fmt: skip
    return cert, key


class Server:
    """The fake on 127.0.0.1, a free port, over TLS with `certificate` (cert, key);
    `requests` keeps each request it received."""

    def __init__(
        self,
        profile: str,
        *,
        token: str | None = None,
        location: str = "",
        certificate: tuple[Path, Path] | None = None,
    ):
        if profile not in PROFILES and profile != REDIRECT:
            raise ValueError(f"unknown profile {profile}")
        self.requests: list[Request] = []
        self.closing = threading.Event()
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                fake.requests.append(Request(self.command, self.path, self.headers))
                if profile == REDIRECT:
                    send(self, Answer(302, "moved", (("Location", location),)))
                    return
                answer = answer_for(profile, self.path, token, self.headers)
                if answer is HANG:
                    fake.closing.wait()
                    return
                send(self, answer)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        scheme = "http"
        if certificate is not None:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(*certificate)
            self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
            scheme = "https"
        self.url = f"{scheme}://127.0.0.1:{self.port}"
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def paths(self) -> list[str]:
        return sorted(r.path for r in self.requests)

    def close(self):
        self.closing.set()
        self.server.shutdown()
        self.server.server_close()
