"""The fake git server API of the probe's tests answers as its profiles say."""

import json
import urllib.error
import urllib.request

import fake_git_api as fake
import pytest


def _get(url: str, headers: dict[str, str] | None = None) -> tuple[int, object]:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=5) as answer:
            return answer.status, json.loads(answer.read())
    except urllib.error.HTTPError as e:
        with e:
            raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw.decode()


@pytest.fixture
def serve():
    started = []

    def start(profile, **kwargs):
        server = fake.Server(profile, **kwargs)
        started.append(server)
        return server

    yield start
    for server in started:
        server.close()


def test_a_profile_answers_its_paths_and_404_elsewhere(serve):
    server = serve("gitlab")
    assert _get(server.url + fake.GITLAB) == (200, fake.GITLAB_USER.body)
    status, body = _get(server.url + fake.GITHUB)
    assert status == 404 and "Not Found" in body
    assert server.paths() == [fake.GITHUB, fake.GITLAB]


def test_with_a_token_each_kind_wants_it_its_own_way(serve):
    server = serve("both", token="t0k")
    assert _get(server.url + fake.GITLAB)[0] == 401
    assert _get(server.url + fake.GITLAB, {"PRIVATE-TOKEN": "t0k"})[0] == 200
    assert _get(server.url + fake.GITHUB, {"PRIVATE-TOKEN": "t0k"})[0] == 401
    assert _get(server.url + fake.GITHUB, {"Authorization": "token t0k"})[0] == 200
