"""A git server over https for the integration tests of git servers: `git http-backend`
behind Python's http.server, with a self-signed certificate only the test trusts (its
`GIT_SSL_CAINFO` and `SSL_CERT_FILE`), Basic auth with the token as password on every git
request, and GitLab's user API of tests/fake_git_api.py beside it. Standard library and
git only.

Each request is kept in `requests` with the user and password it carried (None without);
a git request without the token gets 401 and `WWW-Authenticate`, as a server asks git for
its credential. Repositories live under `root`; `repository` makes one with a commit on
main. Pushes are taken (http.receivepack) once authenticated.
"""

from __future__ import annotations

import base64
import os
import shutil
import ssl
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import NamedTuple

import fake_git_api


class Request(NamedTuple):
    method: str
    path: str
    user: str | None
    password: str | None


def _credentials(header: str | None) -> tuple[str | None, str | None]:
    if not header or not header.startswith("Basic "):
        return None, None
    try:
        user, _, password = base64.b64decode(header[6:]).decode().partition(":")
    except ValueError:
        return None, None
    return user, password


class Server:
    """The server on 127.0.0.1, a free port, under `root`, wanting `token`."""

    def __init__(self, root: Path, token: str, certificate: tuple[Path, Path], profile="gitlab"):
        self.root = root
        self.requests: list[Request] = []
        fake = self
        backend = shutil.which("git")
        assert backend, "git is needed"

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def handle_one(self):
                path, _, query = self.path.partition("?")
                user, password = _credentials(self.headers.get("Authorization"))
                fake.requests.append(Request(self.command, path, user, password))
                body = self._body()
                if path.startswith("/api/"):
                    fake_git_api.send(
                        self, fake_git_api.answer_for(profile, path, token, self.headers)
                    )
                    return
                if password != token:
                    data = b"Unauthorized\n"
                    self.send_response(401)
                    self.send_header("WWW-Authenticate", 'Basic realm="fake git"')
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                self._backend(path, query, user or "", body)

            do_GET = do_POST = handle_one

            def _body(self) -> bytes:
                if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
                    data = b""
                    while True:
                        size = int(self.rfile.readline().strip() or b"0", 16)
                        if size == 0:
                            self.rfile.readline()
                            return data
                        data += self.rfile.read(size)
                        self.rfile.readline()
                return self.rfile.read(int(self.headers.get("Content-Length") or 0))

            def _backend(self, path: str, query: str, user: str, body: bytes):
                env = {
                    "PATH": os.environ["PATH"],
                    "GIT_PROJECT_ROOT": str(fake.root),
                    "GIT_HTTP_EXPORT_ALL": "1",
                    "REQUEST_METHOD": self.command,
                    "PATH_INFO": path,
                    "QUERY_STRING": query,
                    "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                    "CONTENT_LENGTH": str(len(body)),
                    "REMOTE_USER": user,
                    "REMOTE_ADDR": "127.0.0.1",
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "HOME": str(fake.root),
                }
                if self.headers.get("Content-Encoding"):
                    env["HTTP_CONTENT_ENCODING"] = self.headers["Content-Encoding"]
                if self.headers.get("Git-Protocol"):
                    env["GIT_PROTOCOL"] = self.headers["Git-Protocol"]
                done = subprocess.run(
                    [backend, "http-backend"], input=body, env=env, capture_output=True
                )
                head, _, data = done.stdout.partition(b"\r\n\r\n")
                status, headers = 200, []
                for line in head.decode().split("\r\n"):
                    name, _, value = line.partition(": ")
                    if name.lower() == "status":
                        status = int(value.split()[0])
                    elif name:
                        headers.append((name, value))
                self.send_response(status)
                for name, value in headers:
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(*certificate)
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.port = self.server.server_address[1]
        self.url = f"https://127.0.0.1:{self.port}"
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def repository(self, name: str, work: Path) -> str:
        """A bare repository `name` (e.g. "team/app.git") with the commits of the repository
        `work`; its https URL."""
        bare = self.root / name
        bare.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--bare", str(work), str(bare)], check=True)
        subprocess.run(["git", "-C", str(bare), "config", "http.receivepack", "true"], check=True)
        return f"{self.url}/{name}"

    def git_requests(self) -> list[Request]:
        return [r for r in self.requests if not r.path.startswith("/api/")]

    def close(self):
        self.server.shutdown()
        self.server.server_close()
