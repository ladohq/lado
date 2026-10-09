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

    row.get_by_role("button", name="Install wiki v1.0.0…").click()
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

    row.get_by_role("button", name="Actions for wiki").click()
    page.get_by_role("menu", name="wiki").get_by_role("menuitem", name="Remove…").click()
    remove = page.get_by_role("dialog", name="Remove wiki?")
    expect(remove).to_contain_text("No session uses it.")
    shot(page, "remove")
    remove.get_by_role("button", name="Remove").click()
    expect(remove).to_have_count(0)
    expect(kits.get_by_role("listitem", name="wiki")).to_have_count(0)
    assert state.get_kit("wiki") is None
    assert not (state.home() / "marketplaces" / "official").exists()


def open_menu_item(page: Page, kit: str, item: str):
    """Choose `item` in the ⋯ of kit `kit`'s card."""
    card = page.get_by_role("list", name="Kits").get_by_role("listitem", name=kit)
    card.get_by_role("button", name=f"Actions for {kit}").click()
    page.get_by_role("menu", name=kit).get_by_role("menuitem", name=item).click()


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
    open_menu_item(page, "big", "Update…")
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
    open_menu_item(page, "big", "Update…")
    expect(update).to_contain_text("big is up to date")
    expect(update).not_to_contain_text("skill-01")
    shot(page, "up-to-date")

    update.get_by_role("combobox", name="Install another version").select_option("v1.0.0")
    expect(update.locator("footer").get_by_role("button", name="Update to v1.0.0")).to_be_visible()
    page.set_viewport_size({"width": 420, "height": 700})
    box = footer.get_by_role("button", name="Update to v1.0.0").bounding_box()
    assert box is not None and box["x"] + box["width"] <= 420 and box["y"] + box["height"] <= 700
    shot(page, "update-narrow")


def small_kit(tmp_path, name, version, newer=None) -> str:
    """Kit `name` installed from a local git repo at `version`; with `newer` that version
    tagged after the install."""
    work = init_repo(tmp_path / f"{name}-kit")

    def files(at):
        kit_yaml = f"name: {name}\nversion: {at}\ndescription: The {name} kit, at {at}.\n"
        return {
            "kit.yaml": kit_yaml,
            "agents/writer.md": AGENT.replace("mcp: {wiki: {command: [wiki-mcp]}}\n", ""),
        }

    url = publish(work, files(version), tag=f"v{version}")
    kit_core.install(kit_core.plan_add(f"{url}@v{version}"))
    if newer:
        publish(work, files(newer), tag=f"v{newer}")
    return url


def boxes(locator):
    return [one.bounding_box() for one in locator.all()]


def no_sideways_scroll(page: Page) -> bool:
    return page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_kits_are_cards_in_a_grid_and_the_up_arrow_plans_the_version_found(
    page: Page, server, tmp_path, shot
):
    local_marketplace(tmp_path)
    for name in ("alpha", "beta-kit", "gamma"):
        small_kit(tmp_path, name, "1.0.0")
    small_kit(tmp_path, "long-version-kit", "10.100.1000", newer="10.100.1001")

    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(f"{server['url']}/kits?token={server['token']}")
    kits = page.get_by_role("list", name="Kits")
    cards = kits.get_by_role("listitem")
    expect(cards).to_have_count(5)  # and the built-in default
    first, second = boxes(cards)[:2]
    assert first["y"] == second["y"] and first["x"] < second["x"], (first, second)
    assert no_sideways_scroll(page)
    shot(page, "installed")
    page.emulate_media(color_scheme="dark")
    shot(page, "installed-dark")
    page.emulate_media(color_scheme="light")

    page.get_by_role("button", name="Check for updates").click()
    long = kits.get_by_role("listitem", name="long-version-kit")
    up = long.get_by_role("button", name="Update long-version-kit to v10.100.1001…")
    expect(up).to_be_visible()
    expect(long).to_contain_text("v10.100.1001")
    expect(kits.get_by_role("button", name="Update alpha to", exact=False)).to_have_count(0)

    tabs = page.get_by_role("navigation", name="Kits")
    tabs.get_by_role("link", name="Updates 1").click()
    expect(cards).to_have_count(1)
    shot(page, "updates")
    page.emulate_media(color_scheme="dark")
    shot(page, "updates-dark")
    page.emulate_media(color_scheme="light")

    # The narrowest column a card gets, 220px: the version line wraps inside the card.
    for width in range(1440, 900, -4):
        page.set_viewport_size({"width": width, "height": 900})
        card = long.bounding_box()
        if card and card["width"] < 228:
            break
    assert card is not None and 220 <= card["width"] < 228, card
    line = long.locator(".kit-version-line")
    tag, newer = line.locator(".kit-version").all()
    assert newer.bounding_box()["y"] > tag.bounding_box()["y"]
    for part in line.locator(":scope > *").all():
        box = part.bounding_box()
        assert box["x"] + box["width"] <= card["x"] + card["width"], (
            part.text_content(),
            box,
            card,
        )
    shot(page, "narrow-card")

    page.set_viewport_size({"width": 1440, "height": 900})
    tabs.get_by_role("link", name="Installed 5").click()
    up.click()
    update = page.get_by_role("dialog", name="Update long-version-kit")
    expect(
        update.locator("footer").get_by_role("button", name="Update to v10.100.1001")
    ).to_be_visible()
    shot(page, "update-from-arrow")
    update.locator("footer").get_by_role("button", name="Cancel").click()

    tabs.get_by_role("link", name="Available 1").click()
    wiki = kits.get_by_role("listitem", name="wiki")
    expect(wiki.get_by_role("button", name="Install wiki v1.0.0…")).to_be_visible()
    shot(page, "available")
    page.emulate_media(color_scheme="dark")
    shot(page, "available-dark")
    page.emulate_media(color_scheme="light")

    tabs.get_by_role("link", name="Installed 5").click()
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("button", name="Collapse menu").click()  # the rail stays open by itself
    expect(cards).to_have_count(5)
    assert len({box["x"] for box in boxes(cards)}) == 1
    shot(page, "installed-phone")
    assert no_sideways_scroll(page)
