import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { FakeScreen } from "./fakes";
import { Settings, SettingsIndex, SettingsSection } from "./Settings";
import { SETTINGS_SECTIONS, settingsRedirect } from "./settingsSections";

beforeEach(() => {
  FakeScreen.computer();
  // The pages read the server; none answers here, which they say on the page.
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("{}", { status: 500 })),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function mount(path: string) {
  const router = createMemoryRouter(
    [
      {
        path: "/settings",
        element: <Settings />,
        children: [
          { index: true, element: <SettingsIndex /> },
          { path: ":section", element: <SettingsSection /> },
        ],
      },
    ],
    { initialEntries: [path] },
  );
  render(<RouterProvider router={router} />);
  return router;
}

const list = () => screen.queryByRole("navigation", { name: "Settings sections" });
const heading = () => screen.getByRole("heading", { level: 2 });
const where = (router: ReturnType<typeof mount>) => router.state.location.pathname + router.state.location.hash;

test.each([
  ["/settings", "#providers-and-environment", "/settings/agent-clis"],
  ["/settings", "#models", "/settings/model-servers"],
  ["/settings", "#statistics", "/settings/statistics"],
  ["/settings", "#notifications", "/settings/general#notifications"],
  ["/settings", "#appearance", "/settings/general"],
  ["/settings/agent-clis-and-environment", "", "/settings/agent-clis"],
  ["/settings/models", "", "/settings/model-servers"],
  ["/settings/usage-statistics", "", "/settings/statistics"],
  ["/settings/kits", "", "/settings"],
  ["/settings/general", "", null],
  ["/settings/agent-clis", "#claude", null],
  ["/settings", "", null],
  ["/settings", "#elsewhere", null],
])("%s%s goes to %s", (pathname, hash, to) => {
  expect(settingsRedirect(pathname, hash)).toBe(to);
});

test("an old address lands on its page, replacing the history entry", () => {
  const router = mount("/settings#models");
  expect(where(router)).toBe("/settings/model-servers");
  expect(router.state.historyAction).toBe("REPLACE");
  expect(heading().textContent).toBe("Model servers");
});

test("an old section lands on its new page; an unknown one on Settings", () => {
  const router = mount("/settings/usage-statistics");
  expect(where(router)).toBe("/settings/statistics");
  cleanup();
  const other = mount("/settings/kits");
  expect(where(other)).toBe("/settings/general"); // the list's page on a computer
});

test("a section's page beside the list of the four names, its own marked", () => {
  mount("/settings/statistics");
  const nav = list()!;
  const items = within(nav).getAllByRole("link");
  expect(items.map((a) => a.textContent)).toEqual(["General", "Agent CLIs", "Model servers", "Statistics"]);
  expect(items.map((a) => a.getAttribute("href"))).toEqual(SETTINGS_SECTIONS.map((s) => `/settings/${s.slug}`));
  expect(items.filter((a) => a.getAttribute("aria-current") === "page").map((a) => a.textContent)).toEqual([
    "Statistics",
  ]);
  // Names and icons only: no state line, no mark.
  expect(nav.textContent).toBe("GeneralAgent CLIsModel serversStatistics");
  expect(heading().textContent).toBe("Statistics");
  expect(screen.queryByRole("link", { name: /Settings/ })).toBeNull(); // no back link beside the list
});

test("on a computer /settings opens General, and focuses nothing on the first load", () => {
  const router = mount("/settings");
  expect(where(router)).toBe("/settings/general");
  expect(router.state.historyAction).toBe("REPLACE");
  expect(heading().textContent).toBe("General");
  expect(document.activeElement).toBe(document.body);
});

test("moving to another section focuses its heading", () => {
  mount("/settings/general");
  fireEvent.click(within(list()!).getByRole("link", { name: "Model servers" }));
  expect(heading().textContent).toBe("Model servers");
  expect(document.activeElement).toBe(heading());
});

test("on a phone /settings is the list alone, and a section its own page with ‹ Settings", () => {
  FakeScreen.phone();
  const router = mount("/settings");
  expect(where(router)).toBe("/settings");
  expect(list()).toBeTruthy();
  expect(screen.queryByRole("heading", { level: 2 })).toBeNull();
  fireEvent.click(within(list()!).getByRole("link", { name: "Agent CLIs" }));
  expect(list()).toBeNull();
  expect(heading().textContent).toBe("Agent CLIs");
  expect(document.activeElement).toBe(heading());
  const back = screen.getByRole("link", { name: "Settings" });
  expect(back.textContent).toBe("‹ Settings");
  expect(back.getAttribute("href")).toBe("/settings");
  fireEvent.click(back);
  expect(list()).toBeTruthy();
});

test("a window that grows past a phone's width shows the list beside the page it was on", () => {
  const phone = FakeScreen.phone();
  const router = mount("/settings/statistics");
  expect(list()).toBeNull();
  phone.set({ width: 1024, height: 768, pointer: "fine" });
  expect(list()).toBeTruthy();
  expect(where(router)).toBe("/settings/statistics");
  // And back at the list on a phone: the computer's /settings is General.
  act(() => void router.navigate("/settings"));
  expect(where(router)).toBe("/settings/general");
});
