"""Settings → Git servers in a browser (openspec capability git-servers-page): a real `lado
server` and the fake git APIs of tests/fake_git_api.py in the test's process, with no network:
gitlab.com is a fake reached through a local proxy (HTTPS_PROXY) with a certificate of a test
CA the server trusts (SSL_CERT_FILE). Add's states, Check's outcomes, Replace token, the
commit author with Undo and Remove server, the focus after each action and one result line at
a time; the token is in no answer of the API, not in the page, in no log of the server and in
no file but its own; at 1440, 768 and 390 the page scrolls no sideways."""

import re
import socket

import fake_git_api as fake
import pytest
from playwright.sync_api import Browser, Page, Route, expect
from test_main_screen import log_in

from lado import git_kinds, git_servers, state
from lado.cli import main

pytestmark = pytest.mark.ui

TOKEN = "glpat-CANARY-ui-5b1d"
WRONG = "glpat-WRONG-ui-77aa"
SLOW = 12_000  # ms: a server that does not answer takes the server's 5 s


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
def lab(monkeypatch):
    """A GitLab of the human's own over plain http on 127.0.0.1 whose answers the test
    changes as it goes (the profile `ui-lab`, read at each request): at first all rights."""
    monkeypatch.setitem(fake.PROFILES, "ui-lab", fake.PROFILES["gitlab-full"])
    server = fake.Server("ui-lab", token=TOKEN)
    yield server
    server.close()


def answers_as(monkeypatch, profile: str | dict) -> None:
    found = fake.PROFILES[profile] if isinstance(profile, str) else profile
    monkeypatch.setitem(fake.PROFILES, "ui-lab", found)


def section(page: Page):
    return page.get_by_role("region", name="Git servers")


def open_page(page: Page, server) -> None:
    log_in(page, server)
    page.goto(f"{server['url']}/settings/git-servers")
    expect(section(page).get_by_role("button", name="About Servers")).to_be_visible()


def form_add(page: Page):
    return (
        section(page)
        .locator(".mx-form")
        .get_by_role("button", name=re.compile("^(Add server|Add without a check)$"))
    )


def plus_add(page: Page):
    return section(page).locator(".mx-add")


def row(page: Page, address: str):
    return section(page).locator(
        "li.mx-src", has=page.get_by_role("button", name=address, exact=True)
    )


def head(page: Page, address: str):
    """A server's head: the button named by its address alone."""
    return section(page).get_by_role("button", name=address, exact=True)


def results(page: Page):
    return section(page).locator(".gx-result, .mx-done")


def listed(capsys) -> list[list[str]]:
    capsys.readouterr()
    assert main(["git-server", "list"]) == 0
    return [line.split() for line in capsys.readouterr().out.splitlines()[1:]]


def no_sideways_scroll(page: Page) -> None:
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def keeping(page: Page) -> list[tuple[str, str]]:
    """Each answer of the git servers' API the page gets, kept."""
    answers: list[tuple[str, str]] = []

    def keep(route: Route) -> None:
        answer = route.fetch()
        answers.append((route.request.url, answer.text()))
        route.fulfill(response=answer)

    page.route(re.compile(r"/api/git-servers"), keep)
    return answers


def token_nowhere(page: Page, answers, tmp_path, lado_home) -> None:
    for url, text in answers:
        assert TOKEN not in text and WRONG not in text, url
    assert TOKEN not in page.content() and WRONG not in page.content()
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


def test_add_servers_in_each_state(
    browser: Browser, gitlab_com, monkeypatch, server, tmp_path, lado_home, capsys, shot
):
    # A GitLab of the human's own whose token lacks the push right, over plain http.
    monkeypatch.setitem(fake.PROFILES, "ui-read", fake.PROFILES["gitlab-read"])
    own = fake.Server("ui-read", token=TOKEN)
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        answers = keeping(page)
        open_page(page, server)
        git = section(page)
        expect(git.get_by_text("No git servers yet.")).to_be_visible()
        shot(page, "empty")

        # The form fills in no server: Address empty, its placeholder naming both kinds.
        plus_add(page).click()
        address = git.get_by_role("textbox", name="Address")
        token = git.get_by_role("textbox", name="Token")
        expect(address).to_have_value("")
        expect(address).to_be_focused()
        expect(address).to_have_attribute("placeholder", "github.com or gitlab.example.com")
        expect(git.locator(".mx-found")).to_have_count(0)
        shot(page, "add-empty")

        # gitlab.com typed: GitLab answers, its token page, asked with no token.
        address.fill("gitlab.com")
        expect(git.locator(".mx-found")).to_have_text("GitLab answers.")
        link = git.get_by_role("link", name="its token page")
        expect(link).to_have_attribute(
            "href", "https://gitlab.com/-/user_settings/personal_access_tokens"
        )
        expect(link.locator("..")).to_contain_text("with the scope api.")
        expect(git.get_by_role("radio")).to_have_count(0)
        assert gitlab_com.requests and all(
            "PRIVATE-TOKEN" not in r.headers and "Authorization" not in r.headers
            for r in gitlab_com.requests
        )
        shot(page, "answered")

        # A wrong token: under Token, kept, Add off until edited.
        token.fill(WRONG)
        form_add(page).click()
        refused = git.get_by_text("GitLab refused this token: copy it whole or make a new one.")
        expect(refused).to_be_visible()
        expect(form_add(page)).to_be_disabled()
        assert state.git_servers() == []
        shot(page, "refused")
        token.fill(TOKEN)
        form_add(page).click()

        # Done: the new row stands open, the focus on its head, its line at the panel's top.
        com = row(page, "https://gitlab.com")
        expect(com.locator(".gx-top")).to_have_text(f"Saved: GitLab, signed in as {fake.LOGIN}.")
        expect(head(page, "https://gitlab.com")).to_be_focused()
        expect(head(page, "https://gitlab.com")).to_have_attribute("aria-expanded", "true")
        expect(address).to_have_count(0)
        assert TOKEN not in page.content()
        shot(page, "saved")

        # Already saved: Replace its token, the focus in New token; Cancel.
        plus_add(page).click()
        expect(results(page)).to_have_count(0)  # the next action took the last line
        expect(address).to_have_value("")  # with gitlab.com saved too
        expect(address).to_be_focused()
        address.fill("gitlab.com")
        expect(git.get_by_text("Already saved.")).to_be_visible()
        expect(form_add(page)).to_be_disabled()
        shot(page, "already-saved")
        git.get_by_role("button", name="Replace its token").click()
        expect(address).to_have_count(0)
        expect(git.get_by_role("textbox", name="New token")).to_be_focused()
        git.get_by_role("textbox", name="New token").press("Escape")
        expect(
            git.get_by_role("button", name="Replace the token of https://gitlab.com")
        ).to_be_focused()

        # No answer: the kind chosen by hand, saved without a check.
        plus_add(page).click()
        silent = f"http://localhost:{closed_port()}"
        address.fill(silent)
        expect(
            git.get_by_text(
                "⚠ No answer: the connection is refused. Choose its kind to save it without a "
                "check."
            )
        ).to_be_visible()
        expect(form_add(page)).to_have_text("Add without a check")
        token.fill(TOKEN)
        expect(form_add(page)).to_be_disabled()
        git.locator(".segments label", has_text="GitLab").click()
        shot(page, "kind")
        form_add(page).click()
        expect(row(page, silent).locator(".gx-top")).to_have_text(
            "Saved without a check as GitLab."
        )
        expect(row(page, silent).locator(".gx-val").first).to_have_text("⚠ Not checked")

        # Plain http, a token without the push right: saved, with the warning.
        plus_add(page).click()
        address.fill(own.url)
        expect(git.get_by_text("the token travels unencrypted.", exact=False)).to_be_visible()
        expect(git.get_by_role("button", name="About plain http")).to_be_visible()
        token.fill(TOKEN)
        form_add(page).click()
        top = row(page, own.url).locator(".gx-top")
        expect(top).to_contain_text(
            "⚠ The token lacks write_repository: agents can clone but not push."
        )
        # One Replace token, Sign-in's, as the main button: the warning has none of its own.
        replace = row(page, own.url).get_by_role("button", name=f"Replace the token of {own.url}")
        expect(replace).to_have_count(1)
        expect(replace).to_have_class("primary")
        expect(top.get_by_role("button")).to_have_count(0)
        expect(row(page, own.url).get_by_text("plain http", exact=True)).to_be_visible()
        expect(results(page)).to_have_count(1)
        shot(page, "missing-scope")

        # The list is the command's.
        assert sorted(r[0] for r in listed(capsys)) == sorted(
            ["https://gitlab.com", silent, own.url]
        )
        token_nowhere(page, answers, tmp_path, lado_home)
    finally:
        context.close()
        own.close()


def test_check_a_saved_server_in_each_outcome(
    browser: Browser, lab, monkeypatch, server, tmp_path, lado_home, shot
):
    at = git_servers.address(lab.url)
    git_servers.save(at, git_servers.Checked(git_kinds.by_name("gitlab"), fake.LOGIN), TOKEN)
    certified = fake.Server("gitlab", token=TOKEN, certificate=fake.make_certificate(tmp_path))
    cert_at = git_servers.address(certified.url.replace("127.0.0.1", "localhost"))
    git_servers.save(cert_at, git_servers.Checked(git_kinds.by_name("gitlab"), "b.sample"), TOKEN)
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        answers = keeping(page)
        open_page(page, server)
        git = section(page)
        head(page, lab.url).click()
        panel = row(page, lab.url)
        check = panel.get_by_role("button", name=f"Check {lab.url}", exact=True)
        line = panel.locator(".gx-result")

        def outcome(profile, text: str, closed: str | None, timeout: float = 5_000) -> None:
            answers_as(monkeypatch, profile)
            check.click()
            expect(line).to_have_text(text, timeout=timeout)
            expect(check).to_be_focused()
            if closed:  # the closed row's second line follows the check
                head(page, lab.url).click()
                expect(panel.locator(".mx-l2").first).to_have_text(closed)
                head(page, lab.url).click()

        outcome("gitlab-full", f"Works: signed in as {fake.LOGIN}, may clone and push.", None)
        expect(line).to_have_attribute("role", "status")
        shot(page, "works")
        outcome(
            "gitlab-refuses",
            "GitLab refused the token: it expired or was revoked.",
            "✕ check failed: token refused",
        )
        replace = panel.get_by_role("button", name=f"Replace the token of {lab.url}")
        expect(replace).to_have_count(1)
        expect(replace).to_have_class("primary")
        expect(line).to_have_attribute("role", "alert")
        shot(page, "refused")
        outcome(
            "gitlab-read",
            "The token lacks write_repository.",
            "✕ check failed: a scope missing",
        )
        line.get_by_role("button", name="About the missing scope").click()
        expect(
            git.get_by_text(re.compile("^Agents can clone but not push with it"))
        ).to_be_visible()
        shot(page, "missing-scope")
        outcome(
            "gitlab",
            f"Works: signed in as {fake.LOGIN}; the token's rights are not checked.",
            f"signed in as {fake.LOGIN}",
        )
        outcome(
            {fake.GITLAB: fake.Answer(302, "moved", (("Location", "https://sso.example/login"),))},
            "It redirects to https://sso.example/login: add that address instead.",
            "✕ check failed: redirect",
        )
        outcome(
            "github",
            "It answers as GitHub, not GitLab: remove it and add it again.",
            "✕ check failed: another kind",
        )
        outcome("neither", "It answers as neither GitHub nor GitLab.", None)
        outcome("hang", "⚠ No answer in 5 seconds. Check again", "⚠ check: no answer", timeout=SLOW)
        line.get_by_role("button", name="About no answer").click()
        expect(git.get_by_text(re.compile("^Check that LADO's computer reaches"))).to_be_visible()
        shot(page, "no-answer")
        answers_as(monkeypatch, "gitlab-full")
        line.get_by_role("button", name=f"Check {lab.url} again").click()
        expect(line).to_have_text(f"Works: signed in as {fake.LOGIN}, may clone and push.")

        # The certificate this machine does not trust: the question to trust it, its tip
        # (tests/ui/test_git_servers_certificate.py follows it through).
        cert_head = head(page, cert_at.root)
        cert_head.click()
        row(page, cert_at.root).get_by_role("button", name=f"Check {cert_at.root}").click()
        card = row(page, cert_at.root).locator(".gx-trust")
        expect(card.locator(".gx-trust-h")).to_have_text(
            "⚠ The server's certificate is not trusted."
        )
        expect(results(page)).to_have_count(0)  # the question is the page's one result
        card.get_by_role("button", name="About the certificate").click()
        expect(
            git.get_by_text(re.compile("^The server's certificate is signed by"))
        ).to_be_visible()
        shot(page, "certificate")
        token_nowhere(page, answers, tmp_path, lado_home)
    finally:
        context.close()
        certified.close()


def test_a_gitlab_token_for_git_alone_says_what_glab_cannot(
    browser: Browser, lab, monkeypatch, server, shot
):
    answers_as(monkeypatch, "gitlab-git")
    glab = "glab cannot open merge requests: the token lacks api."
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        open_page(page, server)
        git = section(page)
        plus_add(page).click()
        git.get_by_role("textbox", name="Address").fill(lab.url)
        expect(git.get_by_text("the token travels unencrypted.", exact=False)).to_be_visible()
        git.get_by_role("textbox", name="Token").fill(TOKEN)
        form_add(page).click()
        panel = row(page, lab.url)
        top = panel.locator(".gx-top")
        expect(top).to_have_text(f"Saved: GitLab, signed in as {fake.LOGIN}; {glab}")
        expect(top.locator(".gx-result")).to_have_class(re.compile(r"\bok\b"))
        shot(page, "added")

        panel.get_by_role("button", name=f"Check {lab.url}", exact=True).click()
        line = panel.locator(".gx-result")
        expect(line).to_have_text(f"Works: signed in as {fake.LOGIN}, may clone and push; {glab}")
        expect(line).to_have_attribute("role", "status")
        expect(results(page)).to_have_count(1)
        shot(page, "checked")
    finally:
        context.close()


def test_replace_a_token(browser: Browser, lab, monkeypatch, server, tmp_path, lado_home, shot):
    at = git_servers.address(lab.url)
    git_servers.save(at, git_servers.Checked(git_kinds.by_name("gitlab"), "old.login"), TOKEN)
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        answers = keeping(page)
        open_page(page, server)
        head(page, lab.url).click()
        panel = row(page, lab.url)
        opener = panel.get_by_role("button", name=f"Replace the token of {lab.url}")
        new = panel.get_by_role("textbox", name="New token")

        def replace(value: str) -> None:
            opener.click()
            expect(new).to_be_focused()
            new.fill(value)
            panel.get_by_role("button", name="Save token").click()

        # Refused: under the field, kept.
        replace(WRONG)
        expect(
            panel.get_by_text("GitLab refused this token: copy it whole or make a new one.")
        ).to_be_visible()
        expect(new).to_have_value(WRONG)
        expect(panel.get_by_role("button", name="Save token")).to_be_disabled()
        shot(page, "refused")
        panel.get_by_role("button", name="Cancel").click()
        expect(opener).to_be_focused()

        # Another user than before.
        replace(TOKEN)
        line = panel.locator(".gx-result")
        expect(line).to_have_text(f"Token replaced: signed in as {fake.LOGIN}.")
        expect(panel.get_by_text("⚠ Before, it was old.login.", exact=False)).to_be_visible()
        expect(opener).to_be_focused()
        expect(new).to_have_count(0)
        shot(page, "other-user")

        # No answer: save it without a check, as GitLab.
        answers_as(monkeypatch, "hang")
        replace(TOKEN)
        expect(
            panel.get_by_text("⚠ No answer in 5 seconds: save it without a check, as GitLab.")
        ).to_be_visible(timeout=SLOW)
        assert state.git_servers()[0].login == fake.LOGIN  # nothing saved yet
        shot(page, "no-answer")
        panel.get_by_role("button", name="Save without a check").click()
        expect(line).to_have_text("Saved without a check as GitLab.", timeout=SLOW)
        assert state.git_servers()[0].login is None
        head(page, lab.url).click()
        expect(panel.locator(".mx-l2").first).to_have_text("⚠ not checked")
        token_nowhere(page, answers, tmp_path, lado_home)
    finally:
        context.close()


def test_the_author_with_undo_and_remove_server(browser: Browser, server, lado_home, capsys, shot):
    corp = "https://gitlab.corp.example"
    other = "https://git.lab.example"
    for address in (corp, other):
        checked = git_servers.Checked(git_kinds.by_name("gitlab"), "ivan.petrov")
        git_servers.save(git_servers.address(address), checked, TOKEN)
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        open_page(page, server)
        git = section(page)
        head(page, corp).click()
        panel = row(page, corp)
        expect(panel.get_by_text("Your own git author")).to_be_visible()
        panel.get_by_role("button", name=f"Set the commit author of {corp}").click()
        name = panel.get_by_role("textbox", name="Name")
        email = panel.get_by_role("textbox", name="Email")
        expect(name).to_be_focused()
        name.fill("Ivan Petrov")
        email.fill("ivan.petrov")
        panel.get_by_role("button", name="Save author").click()
        expect(
            panel.locator(".field", has=page.get_by_role("textbox", name="Email")).get_by_role(
                "alert"
            )
        ).to_contain_text("not an email address: name@host")
        email.fill("ivan.petrov@corp.example")
        panel.get_by_role("button", name="Save author").click()
        expect(panel.locator(".gx-result")).to_have_text("Author saved.")
        edit = panel.get_by_role("button", name=f"Edit the commit author of {corp}")
        expect(edit).to_be_focused()
        expect(panel.locator(".gx-val b").last).to_have_text(
            "Ivan Petrov <ivan.petrov@corp.example>"
        )
        assert listed(capsys)[1][-3:] == ["Ivan", "Petrov", "<ivan.petrov@corp.example>"]
        shot(page, "author-saved")

        panel.get_by_role("button", name=f"Remove the commit author of {corp}").click()
        expect(panel.locator(".gx-result")).to_contain_text("Author removed.")
        undo = panel.get_by_role("button", name=f"Undo the removal of the commit author of {corp}")
        expect(undo).to_be_focused()
        assert listed(capsys)[1][-1] == "-"
        shot(page, "author-removed")
        undo.click()
        expect(panel.locator(".gx-result")).to_have_text("Author saved.")
        expect(edit).to_be_focused()
        assert state.git_server_by_host("gitlab.corp.example").author_name == "Ivan Petrov"

        # Remove server: asked in the foot, the focus on Cancel; done, + Add server.
        removed = state.git_server_by_host("gitlab.corp.example")
        panel.get_by_role("button", name=f"Remove {corp}").click()
        ask = git.get_by_role("alertdialog")
        expect(ask).to_contain_text(f"Remove {corp}?")
        expect(ask).to_contain_text(
            "Its token, commit author and certificate go too. This cannot be undone."
        )
        expect(ask.get_by_role("button", name="Cancel")).to_be_focused()
        shot(page, "remove-asks")
        ask.get_by_role("button", name="Remove server").click()
        expect(git.get_by_text(f"Removed {corp}.")).to_be_visible()
        expect(plus_add(page)).to_be_focused()
        assert not (lado_home / "git-servers" / removed.id).exists()
        assert [r[0] for r in listed(capsys)] == [other]
        shot(page, "removed")
    finally:
        context.close()


@pytest.fixture
def github_com(tmp_path, monkeypatch):
    """The fake GitHub API as https://api.github.com for the server, as gitlab_com is: with
    no token GitHub's 401, with TOKEN its user with the scope repo. Taken before `server`."""
    folder = tmp_path / "github-ca"
    folder.mkdir()
    with fake.reached_as(monkeypatch, folder, "api.github.com", "github-com", token=TOKEN) as api:
        yield api


def test_github_com_is_added_checked_and_removed_as_any_server(
    browser: Browser, github_com, server, tmp_path, lado_home, capsys, shot
):
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        answers = keeping(page)
        open_page(page, server)
        git = section(page)
        plus_add(page).click()
        address = git.get_by_role("textbox", name="Address")
        address.fill("github.com")
        expect(git.locator(".mx-found")).to_have_text("GitHub answers.")
        link = git.get_by_role("link", name="its token page")
        expect(link).to_have_attribute("href", "https://github.com/settings/tokens")
        expect(link.locator("..")).to_contain_text("scope repo")
        assert all("Authorization" not in r.headers for r in github_com.requests)
        shot(page, "add")
        git.get_by_role("textbox", name="Token").fill(TOKEN)
        form_add(page).click()

        dotcom = row(page, "https://github.com")
        expect(dotcom.locator(".gx-top")).to_have_text(f"Saved: GitHub, signed in as {fake.LOGIN}.")
        expect(head(page, "https://github.com")).to_contain_text("GitHub")
        shot(page, "saved")
        assert [r[:3] for r in listed(capsys)] == [["https://github.com", "GitHub", fake.LOGIN]]

        dotcom.get_by_role("button", name="Check https://github.com").click()
        expect(dotcom.locator(".gx-result")).to_have_text(
            f"Works: signed in as {fake.LOGIN}, may clone and push."
        )
        shot(page, "checked")

        dotcom.get_by_role("button", name="Set the commit author of https://github.com").click()
        dotcom.get_by_role("textbox", name="Name").fill("Ivan Petrov")
        dotcom.get_by_role("textbox", name="Email").fill("ivan.petrov@example.com")
        dotcom.get_by_role("button", name="Save author").click()
        expect(dotcom.locator(".gx-result")).to_have_text("Author saved.")
        assert state.git_server_by_host("github.com").author_name == "Ivan Petrov"
        shot(page, "author")

        dotcom.get_by_role("button", name="Remove https://github.com").click()
        git.get_by_role("alertdialog").get_by_role("button", name="Remove server").click()
        expect(git.get_by_text("Removed https://github.com.")).to_be_visible()
        assert state.git_servers() == []
        # GitHub asked at api.github.com alone; never at github.com itself.
        assert "api.github.com:443" in github_com.proxy.asked
        assert "github.com:443" not in github_com.proxy.asked
        token_nowhere(page, answers, tmp_path, lado_home)
    finally:
        context.close()


@pytest.mark.parametrize(("width", "height"), [(1440, 900), (768, 1024), (390, 844)])
def test_the_page_at_each_width(browser: Browser, server, lado_home, shot, width, height):
    corp = "https://gitlab.corp.example"
    checked = git_servers.Checked(git_kinds.by_name("gitlab"), "a.sample")
    saved = git_servers.save(git_servers.address(corp), checked, TOKEN)[0]
    state.set_git_server_author(saved.id, "Sample Name", "sample.name@corp.example.com")
    git_servers.save(
        git_servers.address("https://ghe.example.com:8443"),
        git_servers.Checked(git_kinds.by_name("github"), None),
        TOKEN,
    )
    context = browser.new_context(viewport={"width": width, "height": height})
    try:
        page = context.new_page()
        open_page(page, server)
        git = section(page)
        head(page, corp).click()
        expect(row(page, corp).get_by_role("button", name=f"Check {corp}")).to_be_visible()
        no_sideways_scroll(page)
        shot(page, "page")
        git.get_by_role("button", name="About Servers").click()
        expect(
            git.get_by_text(re.compile("^Your GitLab, gitlab.com, GitHub or GitHub"))
        ).to_be_visible()
        git.get_by_role("button", name="About Servers").press("Escape")

        # Add: the Token tip opens above, leaving the token page link pressable, and a
        # press on a tip never focuses its field.
        plus_add(page).click()
        address = git.get_by_role("textbox", name="Address")
        address.fill(f"http://localhost:{closed_port()}")
        git.locator(".segments label", has_text="GitLab").click()
        link = git.get_by_role("link", name="its token page")
        expect(link).to_be_visible()
        tip = git.get_by_role("button", name="About Token")
        tip.click()
        expect(git.get_by_text(re.compile("^Only LADO reads it"))).to_be_visible()
        expect(git.get_by_role("textbox", name="Token")).not_to_be_focused()
        link.click(trial=True)  # visible, nothing over it
        tip_box = git.locator(".info-pop").bounding_box()
        link_box = link.bounding_box()
        assert tip_box and link_box and tip_box["y"] + tip_box["height"] <= link_box["y"], (
            tip_box,
            link_box,
        )
        assert 8 <= tip_box["x"] and tip_box["x"] + tip_box["width"] <= width - 8, tip_box
        no_sideways_scroll(page)
        shot(page, "add-token-tip")
    finally:
        context.close()


@pytest.mark.parametrize("which", ["Sign-in", "Token"])
def test_an_open_tip_follows_its_button_across_the_layouts(browser: Browser, server, shot, which):
    corp = "https://gitlab.corp.example"
    checked = git_servers.Checked(git_kinds.by_name("gitlab"), "a.sample")
    git_servers.save(git_servers.address(corp), checked, TOKEN)
    context = browser.new_context(viewport={"width": 390, "height": 844})
    try:
        page = context.new_page()
        open_page(page, server)
        git = section(page)
        if which == "Token":  # its tip opens above it
            plus_add(page).click()
        else:  # below it
            head(page, corp).click()
        tip = git.get_by_role("button", name=f"About {which}")
        tip.click()
        pop = git.locator(".info-pop")
        expect(pop).to_be_visible()

        def beside() -> None:
            # The tip's edge just over or under its button, and across it (kept inside the
            # window, it may not reach the button's middle).
            box, button = pop.bounding_box(), tip.bounding_box()
            assert box and button
            over = button["y"] - (box["y"] + box["height"])
            under = box["y"] - (button["y"] + button["height"])
            assert 0 <= over <= 16 or 0 <= under <= 16, (box, button)
            assert box["x"] < button["x"] + button["width"], (box, button)
            assert button["x"] < box["x"] + box["width"], (box, button)

        beside()
        page.set_viewport_size({"width": 900, "height": 844})  # a phone turned, say
        expect(page.locator("html")).not_to_have_attribute("data-phone", re.compile(".*"))
        page.wait_for_timeout(100)  # two frames: what the human sees after the switch
        beside()
        shot(page, "tip-after-widening")
    finally:
        context.close()
