"""GitLab, gitlab.com or the human's own: its REST API under `/api/v4`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lado.git_kinds.base import REFUSES, Kind

if TYPE_CHECKING:
    from lado.model_servers import Answer


class GitLab(Kind):
    def headers(self, token: str) -> dict[str, str]:
        return {"PRIVATE-TOKEN": token}

    def refusal(self, answer: Answer) -> str | None:
        # A token without read_api may still push: GitLab answers its user API so.
        body = answer.body
        if answer.status == 403 and isinstance(body, dict):
            if body.get("error") == "insufficient_scope":
                return "takes the token, but it lacks the scope read_api"
        # A token it knows but no longer takes (revoked, expired) gets OAuth's words instead
        # of its message.
        if answer.status == 401 and isinstance(body, dict):
            if body.get("error") == "invalid_token":
                return REFUSES
        if isinstance(body, dict) and "documentation_url" in body:  # GitHub's (github.py)
            return None
        return super().refusal(answer)

    def rights(self, root, token, answer, ask):
        # The token's own facts, from GitLab 15.5 on; an older one answers 404.
        told = ask(root + TOKEN_SELF, self.headers(token))
        scopes = told.body.get("scopes") if isinstance(told.body, dict) else None
        if told.status != 200 or not isinstance(scopes, list):
            return None
        return frozenset(scope for scope in scopes if isinstance(scope, str))

    def granted(self, told):
        # GitLab's docs: `api` grants clone and push over HTTPS; write_repository reads too.
        granted = set(told)
        if "api" in told:
            granted |= {"read_repository", "write_repository"}
        if "write_repository" in granted:
            granted.add("read_repository")
        return frozenset(granted)


TOKEN_SELF = "/api/v4/personal_access_tokens/self"


KIND = GitLab(
    name="gitlab",
    title="GitLab",
    path="/api/v4/user",
    login_field="username",
    git_user="oauth2",
    tool="glab",
    token_path="/-/user_settings/personal_access_tokens",
    scopes="scopes read_repository, write_repository, read_api",
    needs=("read_repository", "write_repository"),  # read_api: its user API refuses without
)
