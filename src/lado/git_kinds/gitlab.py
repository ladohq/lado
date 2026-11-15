"""GitLab, gitlab.com or the human's own: its REST API under `/api/v4`."""

from lado.git_kinds.base import Kind
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
        return super().refusal(answer)


KIND = GitLab(
    name="gitlab",
    title="GitLab",
    path="/api/v4/user",
    login_field="username",
    git_user="oauth2",
    tool="glab",
    token_path="/-/user_settings/personal_access_tokens",
    scopes="scopes read_repository, write_repository, read_api",
)
