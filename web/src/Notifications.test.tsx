// Settings → General: the theme and the notifications' switch as rows (the switch's behaviour
// with the browser and the notifier: NeedsYou.test.tsx, "notifications").
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { FakeNotification } from "./fakes";
import { GeneralPage } from "./General";

beforeEach(() => {
  FakeNotification.reset();
  vi.stubGlobal("Notification", FakeNotification);
  vi.stubGlobal("isSecureContext", true);
});

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
});

function mount(path = "/settings/general") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <GeneralPage />
    </MemoryRouter>,
  );
}

test("General is two rows: Theme's three choices, and the switch of browser notifications", () => {
  mount();
  const rows = document.querySelectorAll(".srows > .srow");
  expect([...rows].map((row) => row.querySelector(".srow-name")!.textContent)).toEqual([
    "Theme",
    "Browser notifications",
  ]);
  const theme = screen.getByRole("group", { name: "Theme" });
  expect(within(theme).getAllByRole("radio").map((r) => r.parentElement!.textContent)).toEqual([
    "System",
    "Light",
    "Dark",
  ]);
  expect(within(theme).getAllByRole("radio").filter((r) => r.closest("[title]"))).toEqual([]);
  const toggle = screen.getByRole("switch", { name: "Browser notifications" }) as HTMLInputElement;
  expect(toggle.checked).toBe(false);
  expect(toggle.getAttribute("aria-describedby")).toBeTruthy();
  expect(document.getElementById(toggle.getAttribute("aria-describedby")!)!.textContent).toBe(
    "When something waits for you and this tab is hidden.",
  );
  // The cards and their old words are gone.
  expect(screen.queryByRole("heading", { name: "Appearance" })).toBeNull();
  expect(screen.queryByText(/System follows your computer/)).toBeNull();
});

test.each([
  ["blocked", "denied", "Blocked by the browser: allow them in the site settings (icon left of the address), then switch on again."],
  ["not allowed", "default", "Not allowed: switch on again and allow them."],
])("a refusal of the browser (%s) shows in one line under the row", async (_, answer, text) => {
  FakeNotification.answer = answer as NotificationPermission;
  mount();
  await act(async () => fireEvent.click(screen.getByRole("switch", { name: "Browser notifications" })));
  const row = document.getElementById("notifications")!;
  expect(within(row).getByText(text).closest(".srow-problem")).toBeTruthy();
});

test("a browser without notifications, or a page not secure, says so and the switch is off", () => {
  vi.stubGlobal("isSecureContext", false);
  mount();
  expect(screen.getByText("Needs a secure page: open LADO at 127.0.0.1 or localhost.")).toBeTruthy();
  expect((screen.getByRole("switch") as HTMLInputElement).disabled).toBe(true);
  cleanup();
  vi.stubGlobal("Notification", undefined);
  mount();
  // Nothing to fix (an iPhone's Safari has none): a neutral line under the name, no red notice.
  const line = screen.getByText("Not supported by this browser.");
  expect(line.className).toBe("srow-desc");
  expect(line.closest(".srow-text")).toBeTruthy();
  expect(document.querySelector("#notifications .field-problem")).toBeNull();
  const toggle = screen.getByRole("switch") as HTMLInputElement;
  expect([toggle.checked, toggle.disabled]).toEqual([false, true]);
});

test("#notifications scrolls its row into view", () => {
  const scrolled = vi.fn();
  Element.prototype.scrollIntoView = scrolled;
  mount("/settings/general#notifications");
  expect(scrolled).toHaveBeenCalledTimes(1);
  expect(scrolled.mock.contexts[0]).toBe(document.getElementById("notifications"));
});
