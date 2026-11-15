"""GitHub Enterprise Server: its REST API under `/api/v3`."""

from lado.git_kinds.base import Kind


class GitHub(Kind):
    def headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}


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
