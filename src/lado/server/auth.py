"""Who may call the UI server: the only place that checks it.

Now a token of LADO_HOME, kept in LADO_HOME/server-token (owner only) until
`lado server --new-token`. `lado ui` opens `/?token=<token>` (any page of the UI takes it);
the server then sets a cookie and sends the browser on to the same page without the token,
so the token leaves the address bar. The cookie's name holds
the port: a browser sends 127.0.0.1's cookies to every port, and two LADO servers (say, one
for development) would otherwise overwrite each other's. Other clients send
`Authorization: Bearer <token>`. A real login for a remote host replaces this module.
"""

import os
import secrets
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.requests import HTTPConnection
from fastapi.responses import RedirectResponse

from lado import state


def token_path():
    return state.home() / "server-token"


def token(new: bool = False) -> str:
    """The server's token; made on first use, and again with `new`."""
    path = token_path()
    if not new and path.exists():
        return path.read_text().strip()
    value = secrets.token_urlsafe(32)
    path.unlink(missing_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as file:
        file.write(value + "\n")
    return value


def cookie_name(port: int) -> str:
    return f"lado_token_{port}"


class Refused(Exception):
    """A connection the server does not take: its HTTP status and why."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


class Guard:
    """Checks the token of the server listening on `port`, and for a connection that changes
    something its Origin: only the server's own pages may, so another page in the browser
    cannot use the human's cookie (a terminal's input is the first such connection)."""

    def __init__(self, token: str, port: int):
        self.token = token
        self.cookie = cookie_name(port)
        self.origins = {f"http://{host}:{port}" for host in ("127.0.0.1", "localhost")}

    def _valid(self, given: str | None) -> bool:
        return given is not None and secrets.compare_digest(given.encode(), self.token.encode())

    def check(self, conn: HTTPConnection, changes: bool = False) -> None:
        """Refused (401) without the token. With `changes` first Refused (403) for another
        Origin than the server's own, and for none unless the token is a Bearer one (a
        client that is not a browser: a browser always sends its Origin)."""
        scheme, _, given = conn.headers.get("authorization", "").partition(" ")
        bearer = scheme.lower() == "bearer" and self._valid(given)
        if changes:
            origin = conn.headers.get("origin")
            if origin is None and not bearer:
                raise Refused(403, "no Origin: only a client with a Bearer token may")
            if origin is not None and origin not in self.origins:
                raise Refused(403, f"the Origin {origin} is not this server's")
        if bearer or self._valid(conn.cookies.get(self.cookie)):
            return
        raise Refused(401, "no valid token: open the link `lado ui` prints")

    def __call__(self, request: Request) -> None:
        """A FastAPI dependency: refuse a request without the token (401)."""
        try:
            self.check(request)
        except Refused as refused:
            raise HTTPException(refused.status, refused.detail) from refused

    def changes(self, request: Request) -> None:
        """A FastAPI dependency of a request that changes something: refuse it without the
        token (401) or from another Origin (403)."""
        try:
            self.check(request, changes=True)
        except Refused as refused:
            raise HTTPException(refused.status, refused.detail) from refused

    def login(self, request: Request) -> RedirectResponse:
        """The answer to `<page>?token=<given>`: the cookie and a redirect to the same page
        without the token, or 401. The redirect is the path as it was sent, still encoded
        (a run's name holds "/" as %2F in one segment), and a path on this server: leading
        slashes are made one, so `//host/x` cannot send the browser to another host."""
        if not self._valid(request.query_params.get("token")):
            raise HTTPException(401, "wrong token: open the link `lado ui` prints")
        target = "/" + request.scope["raw_path"].decode("ascii").lstrip("/")
        rest = urlencode([(k, v) for k, v in request.query_params.multi_items() if k != "token"])
        answer = RedirectResponse(f"{target}?{rest}" if rest else target, status_code=303)
        answer.set_cookie(self.cookie, self.token, httponly=True, samesite="strict", path="/")
        return answer
