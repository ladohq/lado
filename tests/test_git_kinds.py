"""The kinds of git server (lado.git_kinds): one module each, named in KINDS alone."""

from lado import git_kinds
from lado.model_servers import Answer


def test_kinds_are_github_and_gitlab_with_their_facts():
    assert [kind.name for kind in git_kinds.KINDS] == ["github", "gitlab"]
    github, gitlab = git_kinds.KINDS
    assert (github.title, github.git_user, github.tool) == ("GitHub", "x-access-token", "gh")
    assert (gitlab.title, gitlab.git_user, gitlab.tool) == ("GitLab", "oauth2", "glab")
    assert github.token_page("https://gh.corp") == "https://gh.corp/settings/tokens"
    assert gitlab.token_page("https://corp.ru/gitlab") == (
        "https://corp.ru/gitlab/-/user_settings/personal_access_tokens"
    )
    assert git_kinds.by_name("gitlab") is gitlab
    assert git_kinds.by_name("bitbucket") is None


def test_each_kind_puts_the_token_in_its_own_header():
    github, gitlab = git_kinds.KINDS
    assert gitlab.request("https://g.lan", "t") == (
        "https://g.lan/api/v4/user",
        {"PRIVATE-TOKEN": "t"},
    )
    url, headers = github.request("https://g.lan", "t")
    assert url == "https://g.lan/api/v3/user"
    assert headers == {"Authorization": "token t", "Accept": "application/vnd.github+json"}


def test_a_kind_tells_its_user_from_its_answer():
    github, gitlab = git_kinds.KINDS
    assert gitlab.login(Answer(200, {"username": "ivan"})) == "ivan"
    assert gitlab.login(Answer(200, {"login": "ivan"})) is None
    assert gitlab.login(Answer(200, {"username": 7})) is None
    assert gitlab.login(Answer(404, {"username": "ivan"})) is None
    assert github.login(Answer(200, {"login": "ivan"})) == "ivan"
    assert github.login(Answer(200, ["login"])) is None


def test_a_kind_tells_a_refused_token_from_its_answer():
    github, gitlab = git_kinds.KINDS
    assert gitlab.refusal(Answer(401, {"message": "401 Unauthorized"})) == "refuses the token"
    assert gitlab.refusal(Answer(403, {"error": "insufficient_scope"})) == (
        "takes the token, but it lacks the scope read_api"
    )
    assert gitlab.refusal(Answer(401, "<html>")) is None
    assert gitlab.refusal(Answer(403, {"error": "forbidden"})) is None
    assert github.refusal(Answer(401, {"message": "Bad credentials"})) == "refuses the token"
    assert github.refusal(Answer(404, {"message": "Not Found"})) is None


def test_a_users_login_is_one_line_of_visible_text():
    github, _ = git_kinds.KINDS
    assert github.login(Answer(200, {"login": "a\nGitLab, signed in as b\x1b[31m"})) == (
        "a GitLab, signed in as b [31m"
    )
