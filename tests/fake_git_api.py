"""The user API of a git server, as the probe of lado.git_servers asks it: GitLab's
`/api/v4/user`, GitHub's `/api/v3/user`, or a server that answers as neither. The probe's
tests run it in process; tests/fake_git_server.py answers the same profiles beside git.
Standard library only.

Each profile says how the two paths answer; every other request gets 404 with a plain text
body, as a web server would. `make_certificate` makes a self-signed certificate for
127.0.0.1 with `openssl`, for a server over TLS that only a test trusts; `make_ca_certificate`
and `ConnectProxy` reach a fake as a named host (gitlab.com) with no network.
"""

from __future__ import annotations

import contextlib
import json
import shutil
import socket
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
# GitLab answers this on any path of its API, also GitHub's, without a token it takes.
GITLAB_401 = Answer(401, {"message": "401 Unauthorized"})
GITHUB_401 = Answer(
    401,
    {
        "message": "Bad credentials",
        "documentation_url": "https://docs.github.com/enterprise-server@3.14/rest",
        "status": "401",
    },
)
# GitLab's 401 for a token it knows but no longer takes: OAuth's words, no message.
GITLAB_REVOKED = Answer(
    401,
    {
        "error": "invalid_token",
        "error_description": "Token was revoked. You have to re-authorize from the user.",
    },
)
GITLAB_EXPIRED = Answer(
    401,
    {
        "error": "invalid_token",
        "error_description": "Token is expired. You can either do re-authorization or token "
        "refresh.",
    },
)
GITLAB_SCOPE = Answer(
    403,
    {"error": "insufficient_scope", "error_description": "The request requires higher privileges"},
)
HANG = Answer(0)  # no answer: the request waits for the server's end
GITLAB_TOKEN = "/api/v4/personal_access_tokens/self"  # GitLab 15.5 on: the token's own facts
GITLAB_SCOPES = ("read_repository", "write_repository", "read_api")


def gitlab_token(*scopes: str) -> Answer:
    return Answer(200, {"id": 9, "name": "lado", "scopes": list(scopes), "active": True})


def github_user(scopes: str) -> Answer:
    """GitHub's user answer for a classic token: its scopes in `X-OAuth-Scopes`."""
    return GITHUB_USER._replace(headers=(("X-OAuth-Scopes", scopes),))


PROFILES: dict[str, dict[str, Answer]] = {
    # A GitLab older than 15.5: no token's own facts, its rights not told.
    "gitlab": {GITLAB: GITLAB_USER},
    "gitlab-full": {GITLAB: GITLAB_USER, GITLAB_TOKEN: gitlab_token(*GITLAB_SCOPES)},
    "gitlab-read": {GITLAB: GITLAB_USER, GITLAB_TOKEN: gitlab_token("read_repository", "read_api")},
    "gitlab-api-only": {GITLAB: GITLAB_USER, GITLAB_TOKEN: gitlab_token("api")},
    "gitlab-no-repo": {GITLAB: GITLAB_USER, GITLAB_TOKEN: gitlab_token("read_api")},
    # GitHub's user with a fine-grained token: no X-OAuth-Scopes.
    "github-repo": {GITHUB: github_user("repo, read:org")},
    "github-no-repo": {GITHUB: github_user("read:org")},
    "github-no-scopes": {GITHUB: github_user("")},
    # As gitlab.com: GitHub's path refused as any other path of GitLab's API.
    "gitlab-com": {GITLAB: GITLAB_USER, GITHUB: GITLAB_401},
    "github": {GITHUB: GITHUB_USER},
    "gitlab-refuses": {GITLAB: GITLAB_401},
    # gitlab.com with a revoked or expired token: GitHub's path refused as any other.
    "gitlab-revoked": {GITLAB: GITLAB_REVOKED, GITHUB: GITLAB_401},
    "gitlab-expired": {GITLAB: GITLAB_EXPIRED, GITHUB: GITLAB_401},
    "github-refuses": {GITHUB: GITHUB_401},
    "gitlab-scope": {GITLAB: GITLAB_SCOPE},
    "both": {GITLAB: GITLAB_USER, GITHUB: GITHUB_USER},
    "neither": {},
    # GitLab's user, and GitHub's path never answering.
    "gitlab-github-hangs": {GITLAB: GITLAB_USER, GITHUB: HANG},
    "hang": {GITLAB: HANG, GITHUB: HANG},
    "gateway": {},  # GATEWAY_401 on every path (DEFAULTS)
}
# A sign-in gateway in front of a server: its own 401 on any path, whatever the token.
GATEWAY_401 = Answer(401, {"message": "Unauthorized"})
DEFAULTS: dict[str, Answer] = {"gateway": GATEWAY_401}  # a profile's answer off its paths
REDIRECT = "redirect"  # 302 to the location given, on every path


class Request(NamedTuple):
    method: str
    path: str
    headers: Message


def answer_for(profile: str, path: str, token: str | None, headers: Message) -> Answer:
    """The profile's answer to a GET of `path`; with `token`, a request that does not carry
    it the kind's way gets that kind's 401; a refusal stays one."""
    found = PROFILES[profile].get(path, DEFAULTS.get(profile, NOT_FOUND))
    if token is not None and found.status == 200:
        if path in (GITLAB, GITLAB_TOKEN) and headers.get("PRIVATE-TOKEN") != token:
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


def make_ca_certificate(folder: Path, host: str) -> tuple[Path, tuple[Path, Path]]:
    """A test CA's certificate, and a certificate for `host` it signed with its key, in
    `folder`: a process that trusts the CA (SSL_CERT_FILE) reaches a fake server as `host`
    with no network. Skipped, naming why, without `openssl`."""
    if shutil.which("openssl") is None:
        pytest.skip("openssl is not installed: no certificate for a TLS server")
    ca, ca_key = folder / "ca.crt", folder / "ca.key"
    cert, key, request = folder / f"{host}.crt", folder / f"{host}.key", folder / f"{host}.csr"
    extensions = folder / f"{host}.ext"
    extensions.write_text(
        f"subjectAltName=DNS:{host}\nbasicConstraints=CA:FALSE\n"
        "keyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n"
        "subjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid\n"
    )

    def run(*args: str) -> None:
        subprocess.run(["openssl", *args], check=True, capture_output=True)

    run(
        "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-subj", "/CN=LADO test CA",
        "-addext", "basicConstraints=critical,CA:TRUE",
        "-addext", "keyUsage=critical,keyCertSign,cRLSign",
        "-keyout", str(ca_key), "-out", str(ca),
    )  # fmt: skip
    run(
        "req", "-newkey", "rsa:2048", "-nodes", "-subj", f"/CN={host}",
        "-keyout", str(key), "-out", str(request),
    )  # fmt: skip
    run(
        "x509", "-req", "-in", str(request), "-CA", str(ca), "-CAkey", str(ca_key),
        "-CAcreateserial", "-days", "2", "-extfile", str(extensions), "-out", str(cert),
    )  # fmt: skip
    return ca, (cert, key)


class ConnectProxy:
    """An HTTPS proxy on 127.0.0.1, a free port, that tunnels a CONNECT to a `routes` key
    (`host:port`) to its address on this machine and refuses any other; `asked` keeps each
    CONNECT's target. Over a tunnel the client speaks TLS with the server it reaches."""

    def __init__(self, routes: dict[str, tuple[str, int]]):
        self.routes = routes
        self.asked: list[str] = []
        self._listener = socket.create_server(("127.0.0.1", 0))
        self.port = self._listener.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self._closing = threading.Event()
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self) -> None:
        while not self._closing.is_set():
            try:
                client, _ = self._listener.accept()
            except OSError:
                return
            threading.Thread(target=self._tunnel, args=(client,), daemon=True).start()

    def _tunnel(self, client: socket.socket) -> None:
        with client:
            head = b""
            while b"\r\n\r\n" not in head:
                chunk = client.recv(4096)
                if not chunk:
                    return
                head += chunk
            method, target, *_ = head.split(b"\r\n", 1)[0].decode().split()
            self.asked.append(target)
            to = self.routes.get(target) if method == "CONNECT" else None
            if to is None:
                client.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
                return
            with socket.create_connection(to) as upstream:
                client.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
                back = threading.Thread(target=_pipe, args=(upstream, client), daemon=True)
                back.start()
                _pipe(client, upstream)
                back.join(10)

    def close(self) -> None:
        self._closing.set()
        self._listener.close()


def _pipe(source: socket.socket, sink: socket.socket) -> None:
    """Copy `source` to `sink` until `source` ends, then end `sink`'s writing."""
    try:
        while data := source.recv(65536):
            sink.sendall(data)
    except OSError:
        pass
    with contextlib.suppress(OSError):
        sink.shutdown(socket.SHUT_WR)


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
