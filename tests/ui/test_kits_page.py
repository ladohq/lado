"""The Kits page in a browser: a kit of a local marketplace installed through the plan
dialog, seen in Installed, then removed. Kits and marketplaces are local git repos, never
the network; the official marketplace is never fetched."""

import json

import pytest
from agent_helpers import init_repo, publish
from playwright.sync_api import Page, expect

from lado import kits as kit_core
from lado import marketplaces, state

pytestmark = pytest.mark.ui

AGENT = "---\nname: writer\ndescription: writes\nmcp: {wiki: {command: [wiki-mcp]}}\n---\nW.\n"


def local_marketplace(tmp_path) -> str:
    """Marketplace "local" listing kit "wiki" (v1.0.0), with an index.json entry."""
    files = {
        "kit.yaml": "name: wiki\nversion: 1.0.0\ndescription: Keep a wiki of the project.\n",
        "agents/writer.md": AGENT,
    }
    kit = publish(init_repo(tmp_path / "wiki-kit"), files, tag="v1.0.0")
    entry = {"address": kit, "latest": "v1.0.0", "description": "Keep a wiki of the project."}
    listing = {
        "marketplace.yaml": f"kits:\n  wiki: {kit}\n",
        "index.json": json.dumps({"index": 1, "kits": {"wiki": entry}}),
    }
    marketplaces.add("local", publish(init_repo(tmp_path / "local"), listing))
    return kit


def test_a_kit_is_installed_from_a_marketplace_and_removed(page: Page, server, tmp_path, shot):
    kit = local_marketplace(tmp_path)
    page.goto(f"{server['url']}/kits/available?token={server['token']}")
    kits = page.get_by_role("list", name="Kits")
    row = kits.get_by_role("listitem", name="wiki")
    expect(row).to_contain_text("Keep a wiki of the project.")
    markets = page.get_by_role("complementary", name="Marketplaces")
    expect(markets.get_by_role("listitem", name="local")).to_contain_text("1 kit")
    expect(markets.get_by_role("listitem", name="official")).to_contain_text("not fetched yet")
    shot(page, "available")

    row.get_by_role("button", name="Install wiki…").click()
    plan = page.get_by_role("dialog", name="Install wiki v1.0.0")
    expect(plan).to_contain_text("Not from the official marketplace.")
    expect(plan.get_by_role("list", name="MCP servers")).to_contain_text("wiki-mcp")
    install = plan.locator("footer").get_by_role("button", name="Install")
    expect(install).to_be_disabled()
    plan.get_by_role("checkbox", name="I checked the address and the MCP servers").check()
    shot(page, "plan")
    install.click()
    expect(plan).to_have_count(0)
    installed = state.get_kit("wiki")
    assert (installed.address, installed.tag, installed.marketplace) == (kit, "v1.0.0", "local")
    # Its only kit is installed: Available says so instead of listing it.
    expect(page.get_by_text("All kits of your marketplaces are installed")).to_be_visible()
    tabs = page.get_by_role("navigation", name="Kits")
    expect(tabs.get_by_role("link", name="Available 0")).to_be_visible()
    expect(kits).to_have_count(0)
    shot(page, "available-all-installed")

    tabs.get_by_role("link", name="Installed 2").click()
    row = kits.get_by_role("listitem", name="wiki")
    expect(row).to_contain_text("v1.0.0")
    expect(row).to_contain_text("local")
    expect(row).to_contain_text("1 role")
    expect(kits.get_by_role("listitem", name="default")).to_contain_text("built-in")
    shot(page, "installed")
    page.emulate_media(color_scheme="dark")
    shot(page, "installed-dark")
    page.emulate_media(color_scheme="light")

    row.get_by_role("button", name="Remove wiki…").click()
    remove = page.get_by_role("dialog", name="Remove wiki?")
    expect(remove).to_contain_text("No session uses it.")
    shot(page, "remove")
    remove.get_by_role("button", name="Remove").click()
    expect(remove).to_have_count(0)
    expect(kits.get_by_role("listitem", name="wiki")).to_have_count(0)
    assert state.get_kit("wiki") is None
    assert not (state.home() / "marketplaces" / "official").exists()


SKILL = "---\nname: {0}\ndescription: does {0}\n---\nDo {0}.\n"


def big_kit(work, version, skills, agents):
    files = {
        "kit.yaml": f"name: big\nversion: {version}\ndescription: A kit with many skills.\n",
        **{f"agents/{a}.md": f"---\nname: {a}\ndescription: {a}\n---\n{a}.\n" for a in agents},
        **{f"skills/{s}/SKILL.md": SKILL.format(s) for s in skills},
    }
    return publish(work, files, tag=f"v{version}")


def test_the_update_window_keeps_its_buttons_on_a_short_screen(page: Page, server, tmp_path, shot):
    work = init_repo(tmp_path / "big-kit")
    url = big_kit(work, "1.0.0", [f"skill-{n:02}" for n in range(75)], ["writer", "editor"])
    kit_core.install(kit_core.plan_add(f"{url}@v1.0.0"))
    (work / "agents" / "editor.md").unlink()
    (work / "skills" / "skill-00" / "SKILL.md").unlink()
    big_kit(work, "1.1.0", [f"skill-{n:02}" for n in range(1, 78)], ["writer", "tester"])

    page.set_viewport_size({"width": 1280, "height": 700})
    page.goto(f"{server['url']}/kits?token={server['token']}")
    page.get_by_role("button", name="Update big…").click()
    update = page.get_by_role("dialog", name="Update big")
    expect(update).to_contain_text("+ tester")
    expect(update.get_by_role("group", name="Skills")).to_contain_text("+3")
    footer = update.locator("footer")
    for name in ("Cancel", "Update to v1.1.0"):
        box = footer.get_by_role("button", name=name).bounding_box()
        assert box is not None and box["y"] + box["height"] <= 700, (name, box)
    update.get_by_role("button", name="Show all 77").click()
    box = footer.get_by_role("button", name="Update to v1.1.0").bounding_box()
    assert box is not None and box["y"] + box["height"] <= 700, box
    shot(page, "update")

    footer.get_by_role("button", name="Update to v1.1.0").click()
    expect(update).to_have_count(0)
    assert state.get_kit("big").tag == "v1.1.0"
    page.get_by_role("button", name="Update big…").click()
    expect(update).to_contain_text("big is up to date")
    expect(update).not_to_contain_text("skill-01")
    shot(page, "up-to-date")

    update.get_by_role("combobox", name="Install another version").select_option("v1.0.0")
    expect(update.locator("footer").get_by_role("button", name="Update to v1.0.0")).to_be_visible()
    page.set_viewport_size({"width": 420, "height": 700})
    box = footer.get_by_role("button", name="Update to v1.0.0").bounding_box()
    assert box is not None and box["x"] + box["width"] <= 420 and box["y"] + box["height"] <= 700
    shot(page, "update-narrow")
