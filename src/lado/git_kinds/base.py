"""What a kind of git server is (lado.git_kinds): how its API is asked with a token, how its
answer is told, and what git and the human need of it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lado import text as visible

if TYPE_CHECKING:  # the HTTP client is loaded by a probe only, never by a hook
    from lado.model_servers import Answer


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

    def headers(self, token: str) -> dict[str, str]:
        raise NotImplementedError

    def request(self, root: str, token: str) -> tuple[str, dict[str, str]]:
        """The URL and the headers of the request that tells this kind, carrying `token`."""
        return root + self.path, self.headers(token)

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
            return "refuses the token"
        return None

    def token_page(self, root: str) -> str:
        return root + self.token_path
