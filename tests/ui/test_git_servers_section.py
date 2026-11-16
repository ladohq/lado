"""Settings → Git servers in a browser (openspec change git-servers-page): a real `lado server`
and the fake git APIs of tests/fake_git_api.py in the test's process, with no network:
gitlab.com is a fake reached through a local proxy (HTTPS_PROXY) with a certificate of a test
CA the server trusts (SSL_CERT_FILE). Add gitlab.com with a wrong token then the right one, a
server of the human's own, one that does not answer with its kind chosen, then remove one;
the list is the one `lado git-server list` prints, and the token is in no answer of the API,
not in the page after the save, in no log of the server and in no file but its own."""

import re
import socket

import fake_git_api as fake
import pytest
from playwright.sync_api import Browser, Page, Route, expect
from test_main_screen import log_in

from lado import state
from lado.cli import main

pytestmark = pytest.mark.ui

TOKEN = "glpat-CANARY-ui-5b1d"
WRONG = "glpat-WRONG-ui-77aa"
RESTART = "Agents started from now on reach it; restart running agents to give it to them."


def closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def gitlab_com(tmp_path, monkeypatch):
    """The fake GitLab as https://gitlab.com for the server, which takes this environment:
    asked with no token it answers GitLab's 401, on GitHub's path too, as gitlab.com does;
    with TOKEN its user. Taken before `server`."""
    ca, certificate = fake.make_ca_certificate(tmp_path, "gitlab.com")
    server = fake.Server("gitlab-com", token=TOKEN, certificate=certificate)
    proxy = fake.ConnectProxy({"gitlab.com:443": ("127.0.0.1", server.port)})
    for name in ("http_proxy", "HTTP_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.delenv(name, raising=False)
    for name in ("https_proxy", "HTTPS_PROXY"):
        monkeypatch.setenv(name, proxy.url)
    for name in ("no_proxy", "NO_PROXY"):
        monkeypatch.setenv(name, "127.0.0.1,localhost")
    monkeypatch.setenv("SSL_CERT_FILE", str(ca))
    yield server
    proxy.close()
    server.close()


@pytest.fixture
def own():
    """A GitHub Enterprise of the human's own over plain http on 127.0.0.1."""
    server = fake.Server("github", token=TOKEN)
    yield server
    server.close()


def section(page: Page):
    return page.get_by_role("region", name="Git servers")


def open_page(page: Page, server) -> None:
    log_in(page, server)
    page.goto(f"{server['url']}/settings/git-servers")
    expect(section(page).get_by_role("heading", name=re.compile("^Servers"))).to_be_visible()


def form_add(page: Page):
    return section(page).get_by_role(
        "button", name=re.compile("^(Add server|Add without a check)$")
    )


def plus_add(page: Page):
    return section(page).locator(".mx-add")


def listed(capsys) -> list[list[str]]:
    capsys.readouterr()
    assert main(["git-server", "list"]) == 0
    return [line.split() for line in capsys.readouterr().out.splitlines()[1:]]


def test_add_three_servers_and_remove_one(
    browser: Browser, gitlab_com, own, server, tmp_path, lado_home, capsys, shot
):
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    answers: list[tuple[str, str]] = []  # each answer of the git servers' API the page got

    def keep(route: Route) -> None:
        answer = route.fetch()
        answers.append((route.request.url, answer.text()))
        route.fulfill(response=answer)

    try:
        page = context.new_page()
        page.route(re.compile(r"/api/git-servers"), keep)
        open_page(page, server)
        git = section(page)
        expect(git.get_by_role("heading", name="Servers", exact=True)).to_be_visible()
        shot(page, "empty")

        # gitlab.com, filled in: its hint and token page, asked with no token.
        plus_add(page).click()
        address = git.get_by_role("textbox", name="Address")
        expect(address).to_have_value("https://gitlab.com")
        expect(git.get_by_text("Looks like GitLab; the token tells for sure.")).to_be_visible()
        link = git.get_by_role(
            "link", name="https://gitlab.com/-/user_settings/personal_access_tokens"
        )
        expect(link).to_be_visible()
        expect(git.get_by_role("radio")).to_have_count(0)  # no kind to choose
        expect(form_add(page)).to_have_text("Add server")
        assert gitlab_com.requests and all(
            "PRIVATE-TOKEN" not in r.headers and "Authorization" not in r.headers
            for r in gitlab_com.requests
        )
        shot(page, "gitlab-com")
        token = git.get_by_role("textbox", name="Token")
        token.fill(WRONG)
        form_add(page).click()
        refused = git.get_by_text("GitLab at https://gitlab.com refuses the token")
        expect(refused).to_be_visible()
        expect(
            git.get_by_text(re.compile("make a token at https://gitlab.com/-/user_settings/"))
        ).to_be_visible()
        expect(form_add(page)).to_be_disabled()
        assert state.git_servers() == []
        shot(page, "wrong-token")
        token.fill(TOKEN)
        form_add(page).click()
        expect(
            git.get_by_text(
                f"Saved git server https://gitlab.com: GitLab, signed in as {fake.LOGIN}."
            )
        ).to_be_visible()
        expect(git.get_by_text(RESTART)).to_be_visible()
        assert TOKEN not in page.content()
        shot(page, "gitlab-com-saved")

        # A server of the human's own: Address starts empty now.
        plus_add(page).click()
        expect(address).to_have_value("")
        address.fill(own.url)
        expect(git.get_by_text("Looks like GitHub; the token tells for sure.")).to_be_visible()
        expect(git.get_by_text(re.compile("over plain http://, unencrypted"))).to_be_visible()
        token.fill(TOKEN)
        form_add(page).click()
        expect(
            git.get_by_text(f"Saved git server {own.url}: GitHub, signed in as {fake.LOGIN}.")
        ).to_be_visible()

        # One that does not answer: its kind chosen by hand.
        silent = f"http://localhost:{closed_port()}"
        plus_add(page).click()
        address.fill(silent)
        expect(
            git.get_by_text(re.compile("does not answer: the connection is refused"))
        ).to_be_visible()
        expect(form_add(page)).to_have_text("Add without a check")
        token.fill(TOKEN)
        expect(form_add(page)).to_be_disabled()
        git.locator(".segments label", has_text="GitLab").click()
        expect(
            git.get_by_role("link", name=f"{silent}/-/user_settings/personal_access_tokens")
        ).to_be_visible()
        shot(page, "kind-chosen")
        form_add(page).click()
        expect(
            git.get_by_text(
                f"Saved git server {silent} as GitLab without a check (it does not answer: the "
                "connection is refused)."
            )
        ).to_be_visible()

        # Each added where its form was; read anew, the list is the command's, by host.
        rows = git.locator(".mx-head")
        expect(rows).to_have_text(
            [
                f"https://gitlab.comGitLabsigned in as {fake.LOGIN}",
                f"{own.url}GitHubsigned in as {fake.LOGIN}",
                f"{silent}GitLab⚠ not checked: saved without a check",
            ]
        )
        assert listed(capsys) == [
            [own.url, "GitHub", fake.LOGIN, "yes"],
            ["https://gitlab.com", "GitLab", fake.LOGIN, "yes"],
            [silent, "GitLab", "not", "checked", "yes"],
        ]
        page.reload()
        expect(rows).to_have_text(
            [
                f"{own.url}GitHubsigned in as {fake.LOGIN}",
                f"https://gitlab.comGitLabsigned in as {fake.LOGIN}",
                f"{silent}GitLab⚠ not checked: saved without a check",
            ]
        )
        shot(page, "three")

        # Remove asks first.
        removed = state.git_server_by_host(own.url.removeprefix("http://"))
        git.get_by_role("button", name=f"Remove {own.url}").click()
        ask = git.get_by_role("alertdialog")
        expect(ask).to_contain_text(f"Remove {own.url}?")
        expect(ask.get_by_role("button", name="Cancel")).to_be_focused()
        shot(page, "remove-asks")
        ask.get_by_role("button", name="Remove server").click()
        expect(git.get_by_text(f"Removed {own.url}.")).to_be_visible()
        expect(plus_add(page)).to_be_focused()
        assert not (lado_home / "git-servers" / removed.id).exists()
        assert [row[0] for row in listed(capsys)] == ["https://gitlab.com", silent]
        shot(page, "removed")

        # The token: in no answer, the page, a log, or a file but the servers' own.
        posted = [url for url, _ in answers if url.endswith("/api/git-servers")]
        assert len(posted) >= 5  # the list read, the four Adds
        for url, text in answers:
            assert TOKEN not in text and WRONG not in text, url
        assert TOKEN not in page.content()
        for log in (tmp_path / "server.out", lado_home / "server.log"):
            if log.exists():
                text = log.read_text(errors="replace")
                assert TOKEN not in text and WRONG not in text, log
        held = sorted(
            str(p.relative_to(lado_home))
            for p in lado_home.rglob("*")
            if p.is_file() and TOKEN.encode() in p.read_bytes()
        )
        assert held == sorted(f"git-servers/{s.id}/token" for s in state.git_servers())

        page.set_viewport_size({"width": 390, "height": 844})
        # The page stands alone on a phone: measured once it does.
        expect(
            page.get_by_role("link", name="Settings", exact=True).filter(has_text="‹")
        ).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        shot(page, "phone")
    finally:
        context.close()
