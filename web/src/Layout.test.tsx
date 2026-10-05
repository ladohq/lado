// The session page's layout (docs/design/ui.md, Structure): the team chips, the session
// list's groups and "+", the rail with Launch and the top bar.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { AgentInfo, SessionInfo } from "./api";
import { App } from "./App";
import { AGENT_REST, columnWidth, FakeEventSource, FakeResizeObserver, FakeSocket, stream, stubDialogs } from "./fakes";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const NONE = { gates: 0, questions: 0, agents: 0 };

function session(name: string, more: Partial<SessionInfo> = {}): SessionInfo {
  const settings = { kits: ["default"], provider: "claude", permission_mode: null, without: [] };
  return { name, repo: `/src/${name}`, status: "running", agents: 1, waiting: NONE, ...settings, ...more };
}

function agent(name: string, role: string, status: AgentInfo["status"], more: Partial<AgentInfo> = {}): AgentInfo {
  return { name, role, provider: "claude", status, run: null, task: null, waiting_reason: null, ...AGENT_REST, ...more };
}

let sessions: SessionInfo[] = [];
let agents: AgentInfo[] = [];

beforeEach(() => {
  localStorage.clear();
  sessions = [session("lado")];
  agents = [];
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      if (path === "/api/sessions") return new Response(JSON.stringify(sessions));
      if (path.endsWith("/agents")) return new Response(JSON.stringify(agents));
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

function open(path = "/sessions/lado") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

// The team

test("the team shows every agent as a chip, the supervisor first, with its status, name and role", async () => {
  agents = [
    agent("w1", "developer", "busy", { run: "feature/ui-layout", task: "Build the layout" }),
    agent("supervisor", "supervisor", "idle"),
    agent("w2", "reviewer", "waiting"),
    agent("w3", "developer", "starting"),
    agent("w4", "developer", "stopped"),
  ];
  open();
  const team = await screen.findByRole("group", { name: "Team" });
  const chips = await within(team).findAllByRole("button");
  expect(chips.map((chip) => chip.getAttribute("aria-label"))).toEqual([
    "supervisor, supervisor, idle",
    "w1, developer, busy",
    "w2, reviewer, waiting",
    "w3, developer, starting",
    "w4, developer, stopped",
  ]);
  // Each status has a dot of its own (colour and shape: styles.css).
  const dots = chips.map((chip) => chip.querySelector(".dot")!.className);
  expect(new Set(dots).size).toBe(5);
  expect(within(chips[1]).getByText("developer")).toBeTruthy();
  expect(chips.some((chip) => chip.hasAttribute("title"))).toBe(false); // the tooltip, below
  // The panel shows the supervisor's terminal from the start.
  expect(chips.map((chip) => chip.getAttribute("aria-pressed"))).toEqual(["true", "false", "false", "false", "false"]);
});

test("a chip's tooltip: name · role · provider, and its flow run on a second line", async () => {
  agents = [
    agent("supervisor", "supervisor", "idle"),
    agent("w1", "developer", "busy", { provider: "kilo", run: "feature/ui-polish", task: "Build it" }),
  ];
  open();
  const team = await screen.findByRole("group", { name: "Team" });
  const tip = async (name: string) => {
    const chip = await within(team).findByRole("button", { name: new RegExp(`^${name},`) });
    fireEvent.focus(chip);
    const shown = screen.getByRole("tooltip");
    expect(chip.getAttribute("aria-describedby")).toBe(shown.id);
    const lines = [...shown.querySelectorAll(".tooltip-line")].map((line) => line.textContent);
    fireEvent.blur(chip);
    return lines;
  };
  expect(await tip("w1")).toEqual(["w1 · developer · kilo", "flow feature/ui-polish"]); // no task, no status
  expect(await tip("supervisor")).toEqual(["supervisor · claude"]); // the role is its name
});

test("a chip follows its agent's changes", async () => {
  agents = [agent("supervisor", "supervisor", "idle")];
  open();
  const team = await screen.findByRole("group", { name: "Team" });
  await within(team).findByRole("button", { name: "supervisor, supervisor, idle" });
  const busy = agent("supervisor", "supervisor", "busy");
  stream().send("change", { kind: "agents", session: "lado", key: "supervisor", op: "update", item: busy }, "11");
  expect(within(team).getByRole("button", { name: "supervisor, supervisor, busy" })).toBeTruthy();
});

// The session list

const list = () => screen.getByRole("navigation", { name: "Sessions" });
const group = (name: string) => within(list()).getByRole("region", { name });

test("the list groups the sessions: Needs you, Running, then Stopped folded", async () => {
  sessions = [
    session("calm"),
    session("gated", { waiting: { gates: 1, questions: 0, agents: 0 } }),
    session("asking", { waiting: { gates: 0, questions: 2, agents: 0 } }),
    session("stuck", { status: "tmux_gone", waiting: { gates: 0, questions: 0, agents: 1 } }),
    session("gone", { status: "stopped", agents: 0 }), // its gates are open, but nothing waits in it
    session("old", { status: "stopped", agents: 0 }),
  ];
  open("/sessions");
  await within(list()).findByRole("link", { name: /calm/ });
  const names = (region: HTMLElement) =>
    within(region)
      .queryAllByRole("link")
      .map((link) => link.querySelector(".session-name")!.textContent);
  expect(names(group("Needs you"))).toEqual(["gated", "asking", "stuck"]);
  expect(names(group("Running"))).toEqual(["calm"]);
  // A stopped session is stopped first: nothing can be answered in it.
  const stopped = within(list()).getByRole("button", { name: "Stopped (2)" });
  expect(stopped.getAttribute("aria-expanded")).toBe("false");
  expect(within(list()).queryByRole("link", { name: /^gone/ })).toBeNull();
  expect(within(group("Needs you")).getByRole("link", { name: /gated/ }).textContent).toContain("1 gate");
  expect(within(group("Needs you")).getByRole("link", { name: /asking/ }).textContent).toContain("2 questions");
  expect(within(group("Needs you")).getByRole("link", { name: /stuck/ }).textContent).toContain("1 agent waiting");
  fireEvent.click(stopped);
  expect(names(group("Stopped"))).toEqual(["gone", "old"]);
  cleanup();
  open("/sessions");
  await within(list()).findByRole("link", { name: /^gone/ }); // remembered open
  expect(within(list()).getByRole("button", { name: "Stopped (2)" }).getAttribute("aria-expanded")).toBe("true");
});

test("a session moves to Needs you when the feed says something waits in it", async () => {
  sessions = [session("lado")];
  open("/sessions");
  await within(await screen.findByRole("region", { name: "Running" })).findByRole("link", { name: /lado/ });
  const gated = session("lado", { waiting: { gates: 1, questions: 0, agents: 0 } });
  stream().send("change", { kind: "sessions", session: "lado", key: "", op: "update", item: gated }, "11");
  expect(within(group("Needs you")).getByRole("link", { name: /lado/ })).toBeTruthy();
});

test("the list's width changes with its edge and is remembered", async () => {
  open("/sessions");
  const edge = screen.getByRole("separator", { name: "Resize the session list" });
  expect(Number(edge.getAttribute("aria-valuenow"))).toBe(260);
  fireEvent.keyDown(edge, { key: "ArrowRight" });
  expect(Number(edge.getAttribute("aria-valuenow"))).toBe(300);
  const columns = () => document.querySelector<HTMLElement>(".sessions")!.style.getPropertyValue("--list-width");
  expect(columns()).toBe("300px");
  expect(JSON.parse(localStorage.getItem("lado.sessionsList")!)).toEqual({ width: 300, collapsed: false });
  cleanup();
  open("/sessions");
  expect(columns()).toBe("300px");
  fireEvent.doubleClick(screen.getByRole("separator", { name: "Resize the session list" }));
  expect(columns()).toBe("260px");
});

test("in a narrow window the list is narrowed to leave the session and its terminals room, and its width stays remembered", async () => {
  columnWidth(null);
  localStorage.setItem("lado.sessionsList", JSON.stringify({ width: 400 }));
  open("/sessions");
  const edge = screen.getByRole("separator", { name: "Resize the session list" });
  // The session's least width (360) and the terminals' (280) come first.
  FakeResizeObserver.resize(() => 1000);
  expect(Number(edge.getAttribute("aria-valuenow"))).toBe(1000 - 360 - 280);
  FakeResizeObserver.resize(() => 700);
  expect(Number(edge.getAttribute("aria-valuenow"))).toBe(200);
  expect(JSON.parse(localStorage.getItem("lado.sessionsList")!)).toEqual({ width: 400 });
  FakeResizeObserver.resize(() => 1600);
  expect(Number(edge.getAttribute("aria-valuenow"))).toBe(400);
});

// The session list collapsed to a strip (docs/design/ui.md, Structure: Sessions)

const strip = () => document.querySelector<HTMLElement>("nav.sessions-strip");

test("Collapse sessions folds the list to a strip and Sessions opens it again, remembered, the focus on the other button", async () => {
  localStorage.setItem("lado.sessionsList", JSON.stringify({ width: 320, collapsed: false }));
  open("/sessions");
  const collapse = screen.getByRole("button", { name: "Collapse sessions" });
  expect(collapse.getAttribute("title")).toBe("Collapse sessions");
  expect(collapse.querySelector("svg")).toBeTruthy();
  fireEvent.click(collapse);
  expect(strip()).toBeTruthy();
  expect(strip()!.getAttribute("aria-label")).toBe("Sessions");
  expect(screen.queryByRole("separator", { name: "Resize the session list" })).toBeNull();
  expect(screen.queryByRole("searchbox", { name: "Find a session" })).toBeNull();
  expect(JSON.parse(localStorage.getItem("lado.sessionsList")!)).toEqual({ width: 320, collapsed: true });
  const show = within(strip()!).getByRole("button", { name: "Sessions" });
  expect(show.getAttribute("title")).toBe("Show the sessions");
  expect(document.activeElement).toBe(show);
  cleanup();
  open("/sessions");
  expect(strip()).toBeTruthy(); // remembered
  // A page that opens collapsed does not take the focus.
  expect(document.activeElement).toBe(document.body);
  fireEvent.click(within(strip()!).getByRole("button", { name: "Sessions" }));
  expect(strip()).toBeNull();
  expect(JSON.parse(localStorage.getItem("lado.sessionsList")!)).toEqual({ width: 320, collapsed: false });
  expect(document.activeElement).toBe(screen.getByRole("button", { name: "Collapse sessions" }));
  const columns = document.querySelector<HTMLElement>(".sessions")!.style.getPropertyValue("--list-width");
  expect(columns).toBe("320px");
});

test("on a narrow window with nothing remembered the list starts as a strip", async () => {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: query === "(max-width: 900px)",
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
  open("/sessions");
  expect(strip()).toBeTruthy();
});

const collapsed = () => localStorage.setItem("lado.sessionsList", JSON.stringify({ width: 260, collapsed: true }));
const icons = () => within(strip()!).queryAllByRole("link");

test("the strip shows each session not stopped as two letters, those that need the human first", async () => {
  collapsed();
  sessions = [
    session("crm-api"),
    session("gated.site", { waiting: { gates: 1, questions: 0, agents: 0 } }),
    session("lado"),
    session("old_one", { status: "stopped", waiting: { gates: 1, questions: 0, agents: 0 } }),
    session("stuck", { status: "tmux_gone", waiting: { gates: 0, questions: 0, agents: 1 } }),
  ];
  open("/sessions");
  await within(strip()!).findByRole("link", { name: "lado" });
  // In the open list's order: Needs you, then Running; no stopped session.
  expect(icons().map((icon) => icon.getAttribute("aria-label"))).toEqual([
    "gated.site, needs you",
    "stuck, needs you",
    "crm-api",
    "lado",
  ]);
  expect(icons().map((icon) => icon.textContent)).toEqual(["GS", "ST", "CA", "LA"]);
  expect(icons().map((icon) => icon.classList.contains("waits"))).toEqual([true, true, false, false]);
  expect(icons()[0].textContent).not.toMatch(/\d/); // no count
  // A line between the two parts, only when both have sessions.
  expect(strip()!.querySelectorAll(".strip-icons > li.strip-gap")).toHaveLength(1);
  const gap = strip()!.querySelector(".strip-gap")!;
  expect(gap.previousElementSibling!.textContent).toBe("ST");
  expect(gap.getAttribute("aria-hidden")).toBe("true");
});

test("without a session that needs the human the strip has no line between parts", async () => {
  collapsed();
  sessions = [session("crm-api"), session("lado")];
  open("/sessions");
  await within(strip()!).findByRole("link", { name: "lado" });
  expect(strip()!.querySelector(".strip-gap")).toBeNull();
});

test("an icon opens its session at the row's address and is current there", async () => {
  collapsed();
  sessions = [session("lado"), session("crm-api")];
  open("/sessions/lado/flows");
  const lado = await within(strip()!).findByRole("link", { name: "lado" });
  const crm = within(strip()!).getByRole("link", { name: "crm-api" });
  expect(crm.getAttribute("href")).toBe("/sessions/crm-api");
  expect(lado.getAttribute("aria-current")).toBe("page");
  expect(crm.getAttribute("aria-current")).toBeNull();
  fireEvent.click(crm);
  expect(await screen.findByRole("region", { name: "Session crm-api" })).toBeTruthy();
  expect(crm.getAttribute("aria-current")).toBe("page");
  expect(strip()).toBeTruthy(); // the strip stays
});

test("an icon's tooltip: name · status · agents, what needs the human, the folder, kits · provider; Esc hides it", async () => {
  collapsed();
  sessions = [
    session("gated", { agents: 3, waiting: { gates: 1, questions: 2, agents: 0 }, kits: ["default", "review"] }),
    session("stuck", { status: "loop_down", agents: 1, provider: "kilo" }),
  ];
  open("/sessions");
  const tip = async (name: RegExp) => {
    const icon = await within(strip()!).findByRole("link", { name });
    fireEvent.focus(icon);
    const shown = screen.getByRole("tooltip");
    expect(icon.getAttribute("aria-describedby")).toBe(shown.id);
    const lines = [...shown.querySelectorAll(".tooltip-line")].map((line) => line.textContent);
    const waits = [...shown.querySelectorAll(".tooltip-line.waits")].map((line) => line.textContent);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("tooltip")).toBeNull();
    return { lines, waits };
  };
  expect(await tip(/^gated/)).toEqual({
    lines: ["gated · running · 3 agents", "Needs you: 1 gate · 2 questions", "/src/gated", "default, review · claude"],
    waits: ["Needs you: 1 gate · 2 questions"],
  });
  expect(await tip(/^stuck/)).toEqual({
    lines: ["stuck · session loop not running · 1 agent", "/src/stuck", "default · kilo"],
    waits: [],
  });
});

test("+ in the strip opens New session", async () => {
  collapsed();
  open("/sessions");
  fireEvent.click(within(strip()!).getByRole("button", { name: "New session" }));
  expect(await screen.findByRole("dialog", { name: "New session" })).toBeTruthy();
});

test("while the sessions load the strip's column is busy; a failed load is an alert with its text, Sessions and + still work", async () => {
  collapsed();
  const pending: ((response: Response) => void)[] = [];
  const answer = (response: () => Response) => pending.forEach((resolve) => resolve(response()));
  vi.stubGlobal(
    "fetch",
    vi.fn((path: string) => {
      if (path === "/api/sessions") return new Promise<Response>((resolve) => pending.push(resolve));
      return Promise.resolve(new Response("[]"));
    }),
  );
  open("/sessions");
  await vi.waitFor(() => expect(pending.length).toBeGreaterThan(0));
  const column = strip()!.querySelector(".strip-icons")!;
  expect(column.getAttribute("aria-busy")).toBe("true");
  expect(column.children).toHaveLength(0);
  answer(() => new Response(JSON.stringify({ detail: "the database is locked" }), { status: 500 }));
  const alert = await within(strip()!).findByRole("alert");
  const text = alert.getAttribute("aria-label")!;
  expect(text).toBe("the database is locked");
  fireEvent.focus(alert);
  expect(screen.getByRole("tooltip").textContent).toBe(text);
  fireEvent.click(within(strip()!).getByRole("button", { name: "New session" }));
  expect(await screen.findByRole("dialog", { name: "New session" })).toBeTruthy();
  fireEvent.click(within(strip()!).getByRole("button", { name: "Sessions" }));
  // The open list says the same.
  expect(document.querySelector(".session-list [role=alert]")!.textContent).toBe(text);
});

// The top bar (Launch moved to the rail: Launch and session control, 2026-10-04)

test("the top bar has the title, the server and the link", async () => {
  open("/sessions");
  const bar = screen.getByRole("banner");
  expect(within(bar).getByText(window.location.host)).toBeTruthy();
  expect((await within(bar).findByRole("status")).textContent).toBe("live");
  expect(within(bar).queryByRole("button")).toBeNull();
  stream().fail(false);
  expect(within(bar).getByRole("status").textContent).toMatch(/reconnecting/);
});
