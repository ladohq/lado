// The Shell on a phone (docs/design/ui.md, Phone layout): <html data-phone>, the Menu button
// and the rail as a drawer.
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { SessionInfo } from "./api";
import { App } from "./App";
import { FakeEventSource, FakeScreen, FakeSocket, stubDialogs } from "./fakes";
import { Shell } from "./Shell";
import styles from "./styles.css?raw";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const NONE = { gates: 0, questions: 0, agents: 0 };

function session(name: string, more: Partial<SessionInfo> = {}): SessionInfo {
  const settings = { kits: ["default"], provider: "claude", permission_mode: null, without: [], ran_seconds: 0, running_since: null, stopped_at: null, title: null, project: null, model_missing: false };
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
      if (path === "/api/repos-folder") return new Response(JSON.stringify({ path: "/Users/ann/workspace", made: false }));
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

test("a computer's page does not say it is a phone, a narrow one does", () => {
  new FakeScreen("fine", 390, 844);
  open();
  expect(document.documentElement.dataset.phone).toBe("tall");
  cleanup();
  new FakeScreen("fine", 601, 844);
  open();
  expect(document.documentElement.dataset.phone).toBeUndefined();
});

// The menu

test("a session's page starts with Skip to chat; another page has none", async () => {
  FakeScreen.computer();
  open("/sessions/lado");
  const skip = await screen.findByRole("link", { name: "Skip to chat" });
  const first = document.querySelector("a[href], button, input, [tabindex='0']");
  expect(first).toBe(skip);
  cleanup();
  open("/kits");
  expect(screen.queryByRole("link", { name: "Skip to chat" })).toBeNull();
});

const rail = () => screen.getByRole("navigation", { name: "Sections" });
const menu = () => screen.getByRole("button", { name: /^Menu/ });

test("a computer has no Menu: the rail is there", () => {
  new FakeScreen("fine", 700, 844);
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

// A tablet's browser bars take some of 100vh: the rail as high as what shows (100dvh, after
// 100vh for a browser without it), so Help and Settings at its bottom stay in sight. Chromium
// on a computer has no such bars, so the rule is read here.
test("the rail is as high as the visible window, not 100vh under a tablet's bars", () => {
  const rail = styles.replace(/\/\*[\s\S]*?\*\//g, "").match(/\n\.rail \{([^}]*)\}/)![1];
  expect(rail.match(/height:[^;]+;/g)).toEqual(["height: 100vh;", "height: 100dvh;"]);
});

test("on a phone a Settings page names its section in the top bar; the list and a computer say Settings", () => {
  const title = () => screen.getByRole("banner").querySelector("h1")!.textContent;
  FakeScreen.phone();
  open("/settings/statistics");
  expect(title()).toBe("Statistics");
  cleanup();
  open("/settings");
  expect(title()).toBe("Settings");
  cleanup();
  FakeScreen.computer();
  open("/settings/statistics");
  expect(title()).toBe("Settings");
});

test("Help in the drawer opens its menu there; Esc closes only the menu, an item both", async () => {
  FakeScreen.phone();
  open("/kits");
  fireEvent.click(menu());
  const help = screen.getByRole("button", { name: "Help" });
  fireEvent.click(help);
  const helpMenu = screen.getByRole("menu", { name: "Help" });
  expect(rail().contains(helpMenu)).toBe(true); // in the drawer, over Help
  expect(helpMenu.style.position).toBe(""); // placed by the drawer's CSS, not beside the rail
  fireEvent.keyDown(helpMenu, { key: "Escape" });
  expect(screen.queryByRole("menu")).toBeNull();
  expect(rail().hasAttribute("data-open")).toBe(true);
  expect(document.activeElement).toBe(help);
  fireEvent.keyDown(document, { key: "Escape" });
  expect(rail().hasAttribute("data-open")).toBe(false);
  fireEvent.click(menu());
  fireEvent.click(screen.getByRole("button", { name: "Help" }));
  fireEvent.click(screen.getByRole("menuitem", { name: "Report a bug" }));
  await screen.findByRole("heading", { name: "Report a bug" });
  expect(screen.queryByRole("menu")).toBeNull();
  expect(rail().hasAttribute("data-open")).toBe(false);
});

test("Documentation in the drawer's Help closes the menu and the drawer", () => {
  FakeScreen.phone();
  open("/kits");
  fireEvent.click(menu());
  fireEvent.click(screen.getByRole("button", { name: "Help" }));
  fireEvent.click(screen.getByRole("menuitem", { name: "Documentation" }));
  expect(screen.queryByRole("menu")).toBeNull();
  expect(rail().hasAttribute("data-open")).toBe(false);
});

test("New session in the menu opens the New session window and closes the menu", () => {
  FakeScreen.phone();
  open();
  fireEvent.click(menu());
  act(() => fireEvent.click(within(rail()).getByRole("button", { name: "New session" })));
  expect(rail().hasAttribute("data-open")).toBe(false);
});

// A page that moves on by itself, as the browser's Back does: not through the rail.
function Elsewhere() {
  const navigate = useNavigate();
  return (
    <button type="button" onClick={() => navigate("/b")}>
      Go on
    </button>
  );
}

test("a route change from outside the rail (Back) closes the menu", async () => {
  FakeScreen.phone();
  render(
    <MemoryRouter initialEntries={["/a"]}>
      <Routes>
        <Route element={<Shell />}>
          <Route path="a" element={<Elsewhere />} />
          <Route path="b" element={<p>Page b</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
  fireEvent.click(menu());
  expect(rail().hasAttribute("data-open")).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Go on" }));
  await screen.findByText("Page b");
  expect(rail().hasAttribute("data-open")).toBe(false);
});

test("widened into a computer's window, an open menu goes", () => {
  const phone = FakeScreen.phone();
  open();
  fireEvent.click(menu());
  phone.set({ pointer: "fine", width: 700 });
  expect(rail().hasAttribute("data-open")).toBe(false);
  expect(screen.queryByRole("button", { name: /^Menu/ })).toBeNull();
});
