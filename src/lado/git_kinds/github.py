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
        # GitHub's refusals link its documentation; GitLab answers a bare 401 on any path of
        # its API, this one included (gitlab.com does), which is no GitHub's.
        if isinstance(answer.body, dict) and "documentation_url" in answer.body:
            return super().refusal(answer)
        return None


KIND = GitHub(
    name="github",
    title="GitHub",
    path="/api/v3/user",
    login_field="login",
    git_user="x-access-token",
    tool="gh",
    token_path="/settings/tokens",
    scopes="scope repo",
)
