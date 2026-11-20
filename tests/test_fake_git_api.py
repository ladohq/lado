"""The fake git server API of the probe's tests answers as its profiles say."""

import json
import ssl
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


def test_the_proxy_reaches_a_fake_as_gitlab_com_over_tls(serve, tmp_path):
    ca, certificate = fake.make_ca_certificate(tmp_path, "gitlab.com")
    server = serve("gitlab", certificate=certificate)
    proxy = fake.ConnectProxy({"gitlab.com:443": ("127.0.0.1", server.port)})
    try:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"https": proxy.url}),
            urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=str(ca))),
        )
        with opener.open("https://gitlab.com" + fake.GITLAB, timeout=5) as answer:
            assert json.loads(answer.read()) == fake.GITLAB_USER.body
        with pytest.raises(urllib.error.URLError):
            opener.open("https://gitlab.example" + fake.GITLAB, timeout=5)
        assert proxy.asked == ["gitlab.com:443", "gitlab.example:443"]
    finally:
        proxy.close()


def test_with_a_token_each_kind_wants_it_its_own_way(serve):
    server = serve("both", token="t0k")
    assert _get(server.url + fake.GITLAB)[0] == 401
    assert _get(server.url + fake.GITLAB, {"PRIVATE-TOKEN": "t0k"})[0] == 200
    assert _get(server.url + fake.GITHUB, {"PRIVATE-TOKEN": "t0k"})[0] == 401
    assert _get(server.url + fake.GITHUB, {"Authorization": "token t0k"})[0] == 200
