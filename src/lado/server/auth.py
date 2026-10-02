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


class Guard:
    """Checks the token of the server listening on `port`."""

    def __init__(self, token: str, port: int):
        self.token = token
        self.cookie = cookie_name(port)

    def _valid(self, given: str | None) -> bool:
        return given is not None and secrets.compare_digest(given.encode(), self.token.encode())

    def __call__(self, request: Request) -> None:
        """A FastAPI dependency: refuse a request without the token (401)."""
        scheme, _, given = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() == "bearer" and self._valid(given):
            return
        if self._valid(request.cookies.get(self.cookie)):
            return
        raise HTTPException(401, "no valid token: open the link `lado ui` prints")

    def login(self, request: Request) -> RedirectResponse:
        """The answer to `<page>?token=<given>`: the cookie and a redirect to the same page
        without the token, or 401. The redirect is a path on this server: leading slashes
        are made one, so `//host/x` cannot send the browser to another host."""
        if not self._valid(request.query_params.get("token")):
            raise HTTPException(401, "wrong token: open the link `lado ui` prints")
        target = "/" + request.url.path.lstrip("/")
        rest = urlencode([(k, v) for k, v in request.query_params.multi_items() if k != "token"])
        answer = RedirectResponse(f"{target}?{rest}" if rest else target, status_code=303)
        answer.set_cookie(self.cookie, self.token, httponly=True, samesite="strict", path="/")
        return answer
