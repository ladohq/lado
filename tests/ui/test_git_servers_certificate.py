"""Settings → Git servers' trust of a server's certificate in a browser (openspec capability
git-servers-page): a real `lado server` and fake GitLab APIs over TLS under a test authority
that neither the server nor the browser trusts (no SSL_CERT_FILE). Check asks whether to
trust it; Don't trust saves nothing; Trust saves it and the check works; the Certificate row
removes it with Undo; Add asks under Address and saves it with the server. Screenshots of
each state at 1440 and 390, and the page scrolls no sideways."""

import certificates as made
import fake_git_api as fake
import pytest
from playwright.sync_api import Browser, Page, expect
from test_git_servers_section import form_add, head, open_page, row, section

from lado import git_kinds, git_servers, state

pytestmark = pytest.mark.ui

TOKEN = "glpat-CANARY-ui-ce77"


@pytest.fixture
def corp(tmp_path, monkeypatch):
    """Two GitLabs under Corp Root CA, which no process trusts: `saved` at https://localhost
    (saved without a certificate) and `new` at https://127.0.0.1, to add; and the root."""
    for name in ("SSL_CERT_FILE", "SSL_CERT_DIR"):
        monkeypatch.delenv(name, raising=False)
    root = made.authority("Corp Root CA")
    servers = {}
    for name, host in (("saved", "localhost"), ("new", "127.0.0.1")):
        chain = made.write_chain(tmp_path / name, made.server(host, root), root)
        server = fake.Server("gitlab-full", token=TOKEN, certificate=chain)
        server.url = server.url.replace("127.0.0.1", host)
        servers[name] = server
    at = git_servers.address(servers["saved"].url)
    git_servers.save(at, git_servers.Checked(git_kinds.by_name("gitlab"), fake.LOGIN), TOKEN)
    yield servers["saved"], servers["new"], root
    for server in servers.values():
        server.close()


def certificate_value(page: Page, address: str):
    """The value of a server's Certificate row (the row of its ⓘ About Certificate)."""
    about = page.get_by_role("button", name="About Certificate")
    return row(page, address).locator(".gx-row", has=about).locator(".gx-val")


def _shots(page: Page, shot, name: str) -> None:
    """The page as it is at 1440, then at 390, back to 1440; no sideways scroll at either."""
    for width in (1440, 390):
        page.set_viewport_size({"width": width, "height": 900})
        # The layout follows the new width a moment later: fails when it never fits.
        page.wait_for_function(
            "document.documentElement.scrollWidth <= window.innerWidth", timeout=5_000
        )
        shot(page, f"{name}-{width}")
    page.set_viewport_size({"width": 1440, "height": 900})


def test_check_trusts_a_servers_certificate(browser: Browser, corp, server, lado_home, shot):
    saved, _, root = corp
    url = saved.url
    until = root.certificate.not_valid_after_utc.date().isoformat()
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        open_page(page, server)
        head(page, url).click()
        panel = row(page, url)
        check = panel.get_by_role("button", name=f"Check {url}", exact=True)
        card = panel.locator(".gx-trust")
        line = panel.locator(".gx-result")

        # Not trusted: the question; Don't trust saves nothing, Check again asks again.
        check.click()
        expect(card.locator(".gx-trust-h")).to_have_text(
            "⚠ The server's certificate is not trusted."
        )
        expect(card.locator("dd").first).to_have_text("Corp Root CA · Corp Example Ltd")
        fingerprint = ":".join(
            f"{b:02X}" for b in root.certificate.fingerprint(made.hashes.SHA256())
        )
        expect(card.locator("code")).to_have_text(fingerprint)
        _shots(page, shot, "asked")
        card.get_by_role("button", name="Don't trust").click()
        expect(line.locator(".t")).to_have_text(
            "Not trusted: LADO and agents cannot clone or push here over https."
        )
        again = line.get_by_role("button", name=f"Check {url} again")
        expect(again).to_be_focused()
        assert git_servers.certificate(state.git_servers()[0]) is None
        head(page, url).click()
        expect(panel.locator(".mx-l2").first).to_have_text(
            "✕ check failed: certificate not trusted"
        )
        _shots(page, shot, "not-trusted")
        head(page, url).click()
        check.click()
        expect(card).to_be_visible()

        # Trust: saved for this server, checked again, the Certificate row.
        card.get_by_role("button", name="Trust this server").click()
        expect(line).to_have_text(
            f"Certificate trusted. Works: signed in as {fake.LOGIN}, may clone and push."
        )
        expect(check).to_be_focused()
        value = certificate_value(page, url)
        expect(value).to_have_text(f"Corp Root CA · valid until {until}")
        assert git_servers.certificate(state.git_servers()[0]) == root.pem
        _shots(page, shot, "trusted")

        # Remove at once, Undo puts the same one back.
        panel.get_by_role("button", name=f"Remove the certificate of {url}").click()
        expect(panel.get_by_text("Certificate removed.")).to_be_visible()
        expect(value).to_have_text("None")
        undo = panel.get_by_role("button", name=f"Undo the removal of the certificate of {url}")
        expect(undo).to_be_focused()
        assert git_servers.certificate(state.git_servers()[0]) is None
        _shots(page, shot, "removed")
        undo.click()
        expect(panel.get_by_text("Certificate saved.")).to_be_visible()
        expect(value).to_have_text(f"Corp Root CA · valid until {until}")
        assert git_servers.certificate(state.git_servers()[0]) == root.pem

        # Remove server names the certificate.
        panel.get_by_role("button", name=f"Remove {url}", exact=True).click()
        expect(section(page).get_by_role("alertdialog")).to_contain_text(
            "Its token, commit author and certificate go too. This cannot be undone."
        )
    finally:
        context.close()


def test_add_asks_to_trust_under_address(browser: Browser, corp, server, lado_home, shot):
    _, new, root = corp
    until = root.certificate.not_valid_after_utc.date().isoformat()
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        open_page(page, server)
        git = section(page)
        git.locator(".mx-add").click()
        git.get_by_role("textbox", name="Address").fill(new.url)
        card = git.locator(".mx-form .gx-trust")
        expect(card.locator(".gx-trust-h")).to_have_text(
            "⚠ The server's certificate is not trusted."
        )
        expect(form_add(page)).to_be_disabled()
        _shots(page, shot, "add-asked")
        card.get_by_role("button", name="Trust this server").click()
        expect(git.locator(".mx-found")).to_have_text("GitLab answers.")
        expect(git.get_by_text("trusted for this server.")).to_have_text(
            f"Certificate: Corp Root CA · valid until {until}, trusted for this server."
        )
        git.get_by_role("textbox", name="Token").fill(TOKEN)
        _shots(page, shot, "add-trusted")
        form_add(page).click()
        added = git_servers.address(new.url)
        expect(row(page, added.root).locator(".gx-result")).to_have_text(
            f"Saved: GitLab, signed in as {fake.LOGIN}."
        )
        saved = state.git_server_by_host(added.key)
        assert git_servers.certificate(saved) == root.pem
        expect(certificate_value(page, added.root)).to_have_text(
            f"Corp Root CA · valid until {until}"
        )
    finally:
        context.close()


def test_add_without_trust_offers_the_kind(browser: Browser, corp, server, lado_home):
    _, new, _ = corp
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        open_page(page, server)
        git = section(page)
        git.locator(".mx-add").click()
        git.get_by_role("textbox", name="Address").fill(new.url)
        git.locator(".mx-form .gx-trust").get_by_role("button", name="Don't trust").click()
        expect(
            git.get_by_text(
                "⚠ Not trusted, so LADO cannot ask the server. Choose its kind to save it "
                "without a check."
            )
        ).to_be_visible()
        git.get_by_role("radio", name="GitLab").check()
        git.get_by_role("textbox", name="Token").fill(TOKEN)
        expect(form_add(page)).to_have_text("Add without a check")
        form_add(page).click()
        added = git_servers.address(new.url)
        expect(head(page, added.root)).to_be_visible()
        saved = state.git_server_by_host(added.key)
        assert saved.login is None and git_servers.certificate(saved) is None
    finally:
        context.close()
