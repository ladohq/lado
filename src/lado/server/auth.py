"""Who may call the UI server: the only place that checks it.

Now a token of LADO_HOME, kept in LADO_HOME/server-token (owner only) until
`lado server --new-token` at a start, or a new link in the running server
(`POST /api/access/new-token`, `Guard.renew`), which logs out every browser but the one
that asked. The file is written atomically (a temporary file, then a rename), and an empty
one counts as missing: an empty token is never made, kept or accepted.
`lado ui` opens `/?token=<token>` (any page of the UI takes it); the server then sets a
cookie and sends the browser on to the same page without the token, so the token leaves the
address bar. The cookie's name holds
the port: a browser sends 127.0.0.1's cookies to every port, and two LADO servers (say, one
for development) would otherwise overwrite each other's. Other clients send
`Authorization: Bearer <token>`. A connection that changes something is also checked for
its Origin (`Guard`). The server may listen on any address (`lado server --host`); the
token then travels over plain HTTP, a risk taken knowingly until a real login and TLS
replace this module.
"""

import os
import secrets
import tempfile
from pathlib import Path
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.requests import HTTPConnection
from fastapi.responses import RedirectResponse, Response

from lado import state
from lado.runtime import LadoError


def token_path():
    return state.home() / "server-token"


def token(new: bool = False) -> str:
    """The server's token; made on first use, again with `new` (a reader sees the old token
    or the new one, never none: `_write`), and when the file is empty (an empty token would
    let anyone in)."""
    path = token_path()
    if not new and path.exists():
        value = path.read_text().strip()
        if value:
            return value
    value = secrets.token_urlsafe(32)
    _write(path, value)
    return value


def _write(path, value: str) -> None:
    """Write the token to a temporary file (owner only) and move it over `path`, so a failed
    write leaves `path` as it was; LadoError names the path and the reason."""
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".server-token.")
        try:
            os.write(fd, (value + "\n").encode())
        finally:
            os.close(fd)
        os.replace(temporary, path)
    except OSError as error:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
        reason = error.strerror or error
        raise LadoError(f"cannot write the UI server's token to {path}: {reason}") from error


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
    cannot use the human's cookie (a terminal's input is the first such connection).

    The server does not know the names it is reached by (0.0.0.0, a tunnel to another port,
    a proxy), so its own page is the one whose Origin names the request's own Host: its
    authority (host and port), scheme aside, so a TLS proxy that keeps the Host passes. A
    page of another name that resolves to this server (DNS rebinding) passes this check but
    has no cookie: the cookie is the host's only."""

    def __init__(self, token: str, port: int):
        if not token:
            raise ValueError("the UI server's token is empty")
        self.token = token
        self.cookie = cookie_name(port)

    def renew(self) -> str:
        """A new token, in LADO_HOME and for this server at once: the old one is refused
        from the next check on. A short request checked before finishes with it; a long
        connection (an event stream, a terminal) is checked again once the new token's
        caller can end it (`admits`), so none of the old token outlives the renewal."""
        self.token = token(new=True)
        return self.token

    def set_cookie(self, response: Response) -> None:
        """The cookie of the current token on `response`."""
        response.set_cookie(self.cookie, self.token, httponly=True, samesite="strict", path="/")

    def admits(self, conn: HTTPConnection) -> bool:
        """Whether `conn` holds the token now (`check` without its reason)."""
        try:
            self.check(conn)
        except Refused:
            return False
        return True

    def _valid(self, given: str | None) -> bool:
        return bool(given) and secrets.compare_digest(given.encode(), self.token.encode())

    def check(self, conn: HTTPConnection, changes: bool = False) -> None:
        """Refused (401) without the token. With `changes` first Refused (403) for an Origin
        that is not the request's own Host, or with no Host, and for no Origin unless the
        token is a Bearer one (a client that is not a browser: a browser always sends its
        Origin)."""
        scheme, _, given = conn.headers.get("authorization", "").partition(" ")
        bearer = scheme.lower() == "bearer" and self._valid(given)
        if changes:
            origin = conn.headers.get("origin")
            if origin is None and not bearer:
                raise Refused(403, "no Origin: only a client with a Bearer token may")
            if origin is not None:
                host = conn.headers.get("host")
                if host is None:
                    raise Refused(403, f"the Origin {origin} came with no Host")
                _, sep, authority = origin.partition("://")
                if not sep or authority.lower() != host.lower():
                    raise Refused(403, f"the Origin {origin} is not this server's ({host})")
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
        self.set_cookie(answer)
        return answer
