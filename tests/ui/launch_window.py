"""The New session window's controls for the browser tests (openspec change
new-session-window): the rail's New session, Where's list, Other folder…'s path field, the
session's Name, Team and the footer's start button."""

from playwright.sync_api import Locator, Page, expect


def new_session(page: Page) -> Locator:
    """The New session window, opened from the rail (on a phone, from Menu), once it chose
    its place."""
    item = page.get_by_role("navigation", name="Sections").get_by_role("button", name="New session")
    if not item.is_visible():
        page.get_by_role("button", name="Menu").click()
    item.click()
    dialog = page.get_by_role("dialog", name="New session")
    expect(dialog.get_by_role("combobox", name="Where")).not_to_have_value("…")
    return dialog


def pick_place(dialog: Locator, name: str) -> None:
    """One of Where's options: a recent place by its name, or a way (`Other folder…`)."""
    where = dialog.get_by_role("combobox", name="Where")
    if where.get_attribute("aria-expanded") != "true":
        where.focus()
        where.press("ArrowDown")
    dialog.get_by_role("listbox", name="Places").get_by_role("option", name=name).click()


def other_folder(page: Page) -> tuple[Locator, Locator]:
    """The window on Other folder…, and its path field."""
    dialog = new_session(page)
    pick_place(dialog, "Other folder…")
    return dialog, dialog.get_by_role("combobox", name="Folder")


def start_button(dialog: Locator) -> Locator:
    """The footer's main button, whatever it names."""
    return dialog.locator(".launch-buttons .primary")


def open_team(dialog: Locator) -> None:
    change = dialog.get_by_role("button", name="Change")
    if change.count():
        change.click()


def agent(dialog: Locator) -> Locator:
    """Team's Agent, Team opened."""
    open_team(dialog)
    return dialog.get_by_role("combobox", name="Agent")


def name_field(dialog: Locator) -> Locator:
    """The session's Name, on Task's label row."""
    return dialog.get_by_role("textbox", name="Name", exact=True)


def add_kit(dialog: Locator) -> Locator:
    open_team(dialog)
    return dialog.get_by_role("combobox", name="Add kit")
