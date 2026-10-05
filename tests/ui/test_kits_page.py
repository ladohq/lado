"""The Kits page in a browser: a kit of a local marketplace installed through the plan
dialog, seen in Installed, then removed. Kits and marketplaces are local git repos, never
the network; the official marketplace is never fetched."""

import json

import pytest
from agent_helpers import init_repo, publish
from playwright.sync_api import Page, expect

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
    plan = page.get_by_role("dialog", name="Install wiki v1.0.0?")
    expect(plan).to_contain_text("Not from the official marketplace.")
    expect(plan).to_contain_text("wiki: wiki-mcp")
    install = plan.get_by_role("button", name="Install")
    expect(install).to_be_disabled()
    plan.get_by_role("checkbox", name="I checked the address and the MCP servers").check()
    shot(page, "plan")
    install.click()
    expect(plan).to_have_count(0)
    installed = state.get_kit("wiki")
    assert (installed.address, installed.tag, installed.marketplace) == (kit, "v1.0.0", "local")

    page.get_by_role("navigation", name="Kits").get_by_role("link", name="Installed 2").click()
    row = kits.get_by_role("listitem", name="wiki")
    expect(row).to_contain_text("v1.0.0")
    expect(row).to_contain_text("local")
    expect(row).to_contain_text("1 role")
    expect(kits.get_by_role("listitem", name="default")).to_contain_text("built-in")
    shot(page, "installed")

    row.get_by_role("button", name="Remove wiki…").click()
    remove = page.get_by_role("dialog", name="Remove wiki?")
    expect(remove).to_contain_text("No session uses it.")
    shot(page, "remove")
    remove.get_by_role("button", name="Remove").click()
    expect(remove).to_have_count(0)
    expect(kits.get_by_role("listitem", name="wiki")).to_have_count(0)
    assert state.get_kit("wiki") is None
    assert not (state.home() / "marketplaces" / "official").exists()
