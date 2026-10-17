// The Shell on a phone (docs/design/ui.md, Phone layout): <html data-phone>, the Menu button
// and the rail as a drawer.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { SessionInfo } from "./api";
import { App } from "./App";
import { FakeEventSource, FakeScreen, FakeSocket, stubDialogs } from "./fakes";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const NONE = { gates: 0, questions: 0, agents: 0 };

function session(name: string, more: Partial<SessionInfo> = {}): SessionInfo {
  const settings = { kits: ["default"], provider: "claude", permission_mode: null, without: [], ran_seconds: 0, running_since: null, stopped_at: null, title: null };
  return { name, repo: `/src/${name}`, status: "running", agents: 1, waiting: NONE, busy: 0, ...settings, ...more };
}

let sessions: SessionInfo[] = [];

beforeEach(() => {
  localStorage.clear();
  sessions = [session("lado")];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      if (path === "/api/sessions") return new Response(JSON.stringify(sessions));
      if (path.endsWith("/about")) return new Response("{}", { status: 404 });
      if (path.includes("/messages?")) return new Response(JSON.stringify({ items: [], earlier: false }));
      return new Response("[]");
    }),
  );
  FakeEventSource.all = [];
  FakeEventSource.autoStart = true;
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("WebSocket", FakeSocket);
  stubDialogs();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  delete document.documentElement.dataset.phone;
});

function open(path = "/kits") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

test("the page says on <html> whether it is a phone, upright or sideways, and follows it", () => {
  const phone = FakeScreen.phone();
  open();
  expect(document.documentElement.dataset.phone).toBe("tall");
  phone.set({ width: 844, height: 390 });
  expect(document.documentElement.dataset.phone).toBe("short");
  phone.set({ pointer: "fine" });
  expect(document.documentElement.dataset.phone).toBeUndefined();
});

test("a computer's page never says it is a phone", () => {
  new FakeScreen("fine", 390, 844);
  open();
  expect(document.documentElement.dataset.phone).toBeUndefined();
});

// The menu

const rail = () => screen.getByRole("navigation", { name: "Sections" });
const menu = () => screen.getByRole("button", { name: /^Menu/ });

test("a computer has no Menu: the rail is there", () => {
  new FakeScreen("fine", 390, 844);
  open();
  expect(screen.queryByRole("button", { name: /^Menu/ })).toBeNull();
  expect(rail().hasAttribute("data-open")).toBe(false);
  expect(screen.getByRole("button", { name: "Expand menu" })).toBeTruthy(); // narrow: collapsed
});

test("on a phone Menu starts the top bar and counts what waits", async () => {
  FakeScreen.phone();
  sessions = [session("lado", { waiting: { gates: 1, questions: 1, agents: 0 } })];
  open();
  await screen.findByRole("button", { name: "Menu, 2 waiting" });
  const bar = screen.getByRole("banner");
  expect(bar.firstElementChild).toBe(menu());
  expect(menu().textContent).toBe("2");
  expect(menu().getAttribute("aria-expanded")).toBe("false");
  expect(screen.queryByRole("button", { name: /(Collapse|Expand) menu/ })).toBeNull(); // the drawer has its names
});

test("Menu opens the rail with its names, and Esc closes it, the focus back on Menu", () => {
  FakeScreen.phone();
  localStorage.setItem("lado.rail", "collapsed");
  open();
  expect(menu().textContent).toBe("");
  fireEvent.click(menu());
  expect(rail().hasAttribute("data-open")).toBe(true);
  expect(menu().getAttribute("aria-expanded")).toBe("true");
  expect(document.querySelector(".app")!.classList.contains("collapsed")).toBe(false); // names shown
  expect(document.activeElement).toBe(screen.getByRole("link", { name: "Home" }));
  fireEvent.keyDown(document, { key: "Escape" });
  expect(rail().hasAttribute("data-open")).toBe(false);
  expect(document.activeElement).toBe(menu());
  expect(localStorage.getItem("lado.rail")).toBe("collapsed"); // untouched
});

test("a tap on the dimmed page closes the menu", () => {
  FakeScreen.phone();
  open();
  fireEvent.click(menu());
  fireEvent.click(screen.getByRole("button", { name: "Close menu" }));
  expect(rail().hasAttribute("data-open")).toBe(false);
  expect(screen.queryByRole("button", { name: "Close menu" })).toBeNull();
  expect(document.activeElement).toBe(menu());
});

test("choosing a section goes there and closes the menu", async () => {
  FakeScreen.phone();
  open("/kits");
  fireEvent.click(menu());
  fireEvent.click(screen.getByRole("link", { name: "Settings" }));
  await screen.findByRole("heading", { name: "Settings" });
  expect(rail().hasAttribute("data-open")).toBe(false);
});

test("Launch in the menu opens the New session window and closes the menu", () => {
  FakeScreen.phone();
  open();
  fireEvent.click(menu());
  act(() => fireEvent.click(screen.getByRole("button", { name: "Launch" })));
  expect(rail().hasAttribute("data-open")).toBe(false);
});

test("turned into a computer (a mouse plugged in), an open menu goes", () => {
  const phone = FakeScreen.phone();
  open();
  fireEvent.click(menu());
  phone.set({ pointer: "fine" });
  expect(rail().hasAttribute("data-open")).toBe(false);
  expect(screen.queryByRole("button", { name: /^Menu/ })).toBeNull();
});
