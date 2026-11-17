"""GitHub Enterprise Server: its REST API under `/api/v3`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lado.git_kinds.base import Kind

if TYPE_CHECKING:
    from lado.model_servers import Answer


class GitHub(Kind):
    def headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}

    def refusal(self, answer: Answer) -> str | None:
        # GitLab answers its bare 401 on any path of its API, this one included (gitlab.com
        # does): that is no GitHub's refusal, which says why and links its documentation.
        body = answer.body
        if isinstance(body, dict) and "documentation_url" not in body:
            if body.get("message") == GITLAB_401:
                return None
        return super().refusal(answer)

    def rights(self, root, token, answer, ask):
        # A classic token's scopes ride on every answer; a fine-grained token's do not.
        scopes = answer.headers.get("x-oauth-scopes")
        if scopes is None:
            return None
        return frozenset(scope.strip() for scope in scopes.split(",") if scope.strip())


GITLAB_401 = "401 Unauthorized"  # GitLab's message for a missing or refused token


KIND = GitHub(
    name="github",
    title="GitHub",
    path="/api/v3/user",
    login_field="login",
    git_user="x-access-token",
    tool="gh",
    token_path="/settings/tokens",
    scopes="scope repo",
    needs=("repo",),  # clone and push alike
)
