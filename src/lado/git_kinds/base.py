"""What a kind of git server is (lado.git_kinds): how its API is asked with a token, how its
answer is told, and what git and the human need of it."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lado import text as visible

if TYPE_CHECKING:  # the HTTP client is loaded by a probe only, never by a hook
    from lado.model_servers import Answer


REFUSES = "refuses the token"  # a kind's own 401: the token expired, was revoked or is wrong


@dataclass(frozen=True)
class Kind:
    name: str  # as `--kind` and lado.db name it
    title: str  # as the human reads it
    path: str  # the API's path of the token's user, under the server's root
    login_field: str  # the user's name in that path's answer
    git_user: str  # the user name git sends with the token
    tool: str  # the server's own command-line tool
    token_path: str  # the page where the human makes a token, under the root
    scopes: str  # what a token needs, in words
    # The rights agents need of a token, the one to clone first; `rights` reads them.
    needs: tuple[str, ...] = ()

    def headers(self, token: str) -> dict[str, str]:
        raise NotImplementedError

    def rights(
        self, root: str, token: str, answer: Answer, ask: Callable[[str, dict[str, str]], Answer]
    ) -> frozenset[str] | None:
        """The rights (scopes) the server says `token` has, by `answer`, its answer to
        `request` that gave a login, and as many more requests as the kind needs (`ask`: a
        URL and headers, with no redirect followed); None when it tells none."""
        return None

    def granted(self, told: frozenset[str]) -> frozenset[str]:
        """The rights `told` grants: a broader right holds narrower ones."""
        return told

    def missing(self, told: frozenset[str]) -> tuple[str, ...]:
        """The rights of `needs` a token with the rights `told` lacks, in `needs`' order."""
        granted = self.granted(told)
        return tuple(need for need in self.needs if need not in granted)

    def request(self, root: str, token: str | None) -> tuple[str, dict[str, str]]:
        """The URL and the headers of the request that tells this kind, carrying `token`;
        None sends no header at all, so no credential (the address's check before Add)."""
        return root + self.path, {} if token is None else self.headers(token)

    def login(self, answer: Answer) -> str | None:
        """The user the token signs in as, by the answer to `request`; None when the answer
        is not this kind's. The server's words: one line of visible text."""
        if answer.status != 200 or not isinstance(answer.body, dict):
            return None
        login = answer.body.get(self.login_field)
        return visible.one_line(login) if isinstance(login, str) and login.strip() else None

    def refusal(self, answer: Answer) -> str | None:
        """How the answer to `request` refuses the token, as the end of "<title> at <root>
        …"; None when it is no refusal of this kind's."""
        if answer.status == 401 and isinstance(answer.body, dict) and "message" in answer.body:
            return REFUSES
        return None

    def token_page(self, root: str) -> str:
        return root + self.token_path
