// A session's head on a phone (docs/design/ui.md, Phone layout): one line of the top bar, and
// the session's details in a sheet its name opens.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { SessionAbout, SessionInfo } from "./api";
import { App } from "./App";
import { FakeEventSource, FakeScreen, FakeSocket, stubDialogs } from "./fakes";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const NONE = { gates: 0, questions: 0, agents: 0 };
const FOLDER = "/Users/kao/Projects/lado/.lado/worktrees/lad-95/task-lad-95";

function session(more: Partial<SessionInfo> = {}): SessionInfo {
  const settings = { kits: ["default", "uiflow"], provider: "claude", permission_mode: "auto", without: [], ran_seconds: 0, running_since: null, stopped_at: null, title: null, project: null };
  return { name: "lad-95", repo: FOLDER, status: "running", agents: 1, waiting: NONE, busy: 0, ...settings, ...more };
}

const ABOUT: SessionAbout = {
  repos: [{ path: FOLDER, remote: "git@github.com:ladohq/lado.git", branch: "lado/lad-95/task-lad-95" }],
  kits: [
    { name: "default", version: "0.1.0", source: "built-in", valid: true, problem: null },
    { name: "uiflow", version: "1.0.0", source: "/kits/uiflow", valid: true, problem: null },
  ],
  provider: {
    name: "claude",
    title: "Claude Code",
    permission_modes: [],
    install_hint: "",
    installed: true,
    version: "2.1.0",
    detail: "",
    tested_version: "2.1.0",
    warning: "",
    login_missing: false,
  },
};

let sessions: SessionInfo[] = [];
let calls: { method: string; path: string; body: unknown }[] = [];
let about: SessionAbout = ABOUT;

beforeEach(() => {
  localStorage.clear();
  sessions = [session()];
  about = ABOUT;
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      calls.push({ method: init?.method ?? "GET", path, body: init?.body ? JSON.parse(String(init.body)) : null });
      if (path === "/api/sessions") return new Response(JSON.stringify(sessions));
      if (path.endsWith("/about")) return new Response(JSON.stringify(about));
      if (path.endsWith("/title")) {
        const saved = { ...sessions[0], title: (init?.body && JSON.parse(String(init.body)).title) ?? null };
        return new Response(JSON.stringify(saved));
      }
      if (path === "/api/limits") return new Response(JSON.stringify({ max_title: 80 }));
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
});

function open() {
  return render(
    <MemoryRouter initialEntries={["/sessions/lad-95"]}>
      <App />
    </MemoryRouter>,
  );
}

const sheet = () => screen.getByRole("dialog", { name: "lad-95" });

test("on a phone the head is the status dot, the name as a button and Stop: no facts", async () => {
  FakeScreen.phone();
  open();
  const bar = screen.getByRole("banner");
  const name = await within(bar).findByRole("button", { name: "lad-95" });
  expect(name.getAttribute("aria-haspopup")).toBe("dialog");
  expect(within(bar).getByRole("img", { name: "running · idle · 1 agent" })).toBeTruthy();
  expect(within(bar).getByRole("button", { name: "Stop session…" })).toBeTruthy();
  await waitFor(() => expect(calls.some((call) => call.path.endsWith("/about"))).toBe(true));
  for (const fact of ["Copy path", "Copy link", "Rename session", "Copy URL"]) {
    expect(within(bar).queryByRole("button", { name: fact })).toBeNull();
  }
  expect(bar.textContent).not.toContain(FOLDER);
  expect(bar.textContent).not.toContain("uiflow");
});

test("a computer keeps the head with its facts", async () => {
  FakeScreen.computer();
  open();
  const bar = screen.getByRole("banner");
  await within(bar).findByRole("button", { name: "Copy path" });
  expect(within(bar).getByRole("button", { name: "Rename session" })).toBeTruthy();
  expect(within(bar).queryByRole("button", { name: "lad-95" })).toBeNull();
});

test("the name opens the details: the state, the whole folder, git, the kits with versions, the CLI", async () => {
  FakeScreen.phone();
  open();
  fireEvent.click(await screen.findByRole("button", { name: "lad-95" }));
  await waitFor(() => expect(sheet().textContent).toContain("uiflow 1.0.0"));
  const text = sheet().textContent!;
  expect(sheet().querySelector(".session-details-state")!.textContent).toMatch(/^running · idle · 1 agent · ran (<1|\d+) min$/);
  expect(text).toContain(FOLDER);
  expect(text).toContain("github.com/ladohq/lado · lado/lad-95/task-lad-95");
  expect(text).toContain("default 0.1.0, uiflow 1.0.0");
  expect(text).toContain("claude 2.1.0 · mode auto");
  for (const button of ["Rename", "Copy path", "Copy link", "Close", "Copy URL"]) {
    expect(within(sheet()).getByRole("button", { name: button })).toBeTruthy();
  }
  expect(within(sheet()).getByRole("link", { name: "All sessions" }).getAttribute("href")).toBe("/sessions");
  expect(screen.getByRole("button", { name: "lad-95" }).getAttribute("aria-expanded")).toBe("true");
});

test("a session in a project has the project's title above the folder in the details", async () => {
  about = { ...ABOUT, project: { id: "shop", title: "Shop" } };
  FakeScreen.phone();
  open();
  fireEvent.click(await screen.findByRole("button", { name: "lad-95" }));
  await waitFor(() => expect(sheet().textContent).toContain("ProjectShop"));
  const terms = [...sheet().querySelectorAll("dt")].map((term) => term.textContent);
  expect(terms.slice(0, 2)).toEqual(["Project", "Folder"]);
  const link = within(sheet()).getByRole("link", { name: "Shop" });
  expect(link.getAttribute("href")).toBe("/projects/shop");
  expect(link.closest("dd")!.getAttribute("title")).toBe("Project shop");
});

test("a session without a project has no Project line in the details", async () => {
  FakeScreen.phone();
  open();
  fireEvent.click(await screen.findByRole("button", { name: "lad-95" }));
  await waitFor(() => expect(sheet().textContent).toContain("uiflow 1.0.0"));
  expect([...sheet().querySelectorAll("dt")].map((term) => term.textContent)).not.toContain("Project");
});

test("a question waits: the bar's dot and the sheet's state line say so in the mark's words", async () => {
  FakeScreen.phone();
  sessions = [session({ agents: 3, waiting: { gates: 0, questions: 1, agents: 0 } })];
  open();
  const bar = screen.getByRole("banner");
  const name = await within(bar).findByRole("button", { name: "lad-95" });
  expect(within(bar).getByRole("img", { name: "needs you · 1 question" }).classList).toContain("dot-waiting");
  fireEvent.click(name);
  expect(sheet().querySelector(".session-details-state")!.textContent).toMatch(/^needs you · 1 question · /);
});

test("Rename edits the title in the sheet, as the pencil does", async () => {
  FakeScreen.phone();
  open();
  fireEvent.click(await screen.findByRole("button", { name: "lad-95" }));
  fireEvent.click(within(sheet()).getByRole("button", { name: "Rename" }));
  const field = within(sheet()).getByRole("textbox", { name: "Session title" });
  fireEvent.change(field, { target: { value: "Phone layout" } });
  fireEvent.keyDown(field, { key: "Enter" });
  await waitFor(() => expect(calls.some((call) => call.method === "PUT")).toBe(true));
  expect(calls.find((call) => call.method === "PUT")).toEqual({
    method: "PUT",
    path: "/api/sessions/lad-95/title",
    body: { title: "Phone layout" },
  });
  await screen.findByRole("button", { name: "Phone layout" });
  const renamed = screen.getByRole("dialog", { name: "Phone layout" }); // the sheet is named by the title
  expect(within(renamed).getByRole("heading").textContent).toBe("Phone layout");
  expect(document.activeElement).toBe(within(renamed).getByRole("button", { name: "Rename" }));
});

test("Close, Esc and a tap beside the sheet close it", async () => {
  FakeScreen.phone();
  open();
  const name = await screen.findByRole("button", { name: "lad-95" });
  fireEvent.click(name);
  fireEvent.click(within(sheet()).getByRole("button", { name: "Close" }));
  expect(screen.queryByRole("dialog", { name: "lad-95" })).toBeNull();
  expect(name.getAttribute("aria-expanded")).toBe("false");

  fireEvent.click(name);
  fireEvent(sheet(), new Event("cancel", { cancelable: true })); // the browser's Esc on a modal
  expect(screen.queryByRole("dialog", { name: "lad-95" })).toBeNull();

  fireEvent.click(name);
  fireEvent.click(sheet()); // the backdrop: the dialog itself, outside its box
  expect(screen.queryByRole("dialog", { name: "lad-95" })).toBeNull();
});
