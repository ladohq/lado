// The session page's layout (docs/design/ui.md, Structure): the team chips, the session
// list's groups and "+", the rail with Launch and the top bar.
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { AgentInfo, SessionInfo } from "./api";
import { App } from "./App";
import { AGENT_REST, columnWidth, FakeEventSource, FakeResizeObserver, FakeSocket, stream, stubDialogs } from "./fakes";
import { TOOLTIP_DELAY_MS } from "./Tooltip";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const NONE = { gates: 0, questions: 0, agents: 0 };

function session(name: string, more: Partial<SessionInfo> = {}): SessionInfo {
  const settings = { kits: ["default"], provider: "claude", permission_mode: null, without: [], ran_seconds: 0, running_since: null, stopped_at: null };
  return { name, repo: `/src/${name}`, status: "running", agents: 1, waiting: NONE, ...settings, ...more };
}

function agent(name: string, role: string, status: AgentInfo["status"], more: Partial<AgentInfo> = {}): AgentInfo {
  return { name, role, provider: "claude", status, run: null, task: null, status_reason: null, ...AGENT_REST, ...more };
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
      if (path.endsWith("/about")) return new Response("{}", { status: 404 }); // the head without its about
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
    agent("w1", "developer", "busy", { task: "Build the layout" }),
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

test("a run's agents are compact chips in a frame named by the run, a link to its page in Flows", async () => {
  agents = [
    agent("dev", "developer", "busy", { run: "feature/x" }),
    agent("supervisor", "supervisor", "idle"),
    agent("w1", "researcher", "idle"),
    agent("rev", "reviewer", "waiting", { run: "feature/x" }),
    agent("dev-2", "developer", "starting", { run: "fix/y" }),
  ];
  open();
  const team = await screen.findByRole("group", { name: "Team" });
  await within(team).findAllByRole("button");
  const frames = within(team).getAllByRole("group");
  expect(frames.map((frame) => frame.getAttribute("aria-label"))).toEqual(["run feature/x", "run fix/y"]);
  const [x, y] = frames;
  const link = within(x).getByRole("link", { name: "feature/x" });
  expect(link.getAttribute("href")).toBe(`/sessions/lado/flows/${encodeURIComponent("feature/x")}`);
  expect(x.textContent).toBe("feature/xdevrev"); // no state of the run, no roles
  const inX = within(x).getAllByRole("button");
  expect(inX.map((chip) => chip.getAttribute("aria-label"))).toEqual(["dev, developer, busy", "rev, reviewer, waiting"]);
  expect(inX.every((chip) => chip.classList.contains("chip-compact"))).toBe(true);
  expect(within(y).getAllByRole("button").map((chip) => chip.getAttribute("aria-label"))).toEqual([
    "dev-2, developer, starting",
  ]);
  // The supervisor and its own workers: full chips first, outside every frame.
  const chips = within(team).getAllByRole("button");
  expect(chips.slice(0, 2).map((chip) => chip.getAttribute("aria-label"))).toEqual([
    "supervisor, supervisor, idle",
    "w1, researcher, idle",
  ]);
  expect(chips.slice(0, 2).some((chip) => chip.closest(".team-run") !== null)).toBe(false);
  expect(within(chips[1]).getByText("researcher")).toBeTruthy();
  // A chip in a frame opens its agent's terminal, as any chip.
  fireEvent.click(inX[1]);
  expect(inX[1].getAttribute("aria-pressed")).toBe("true");
  expect(chips[0].getAttribute("aria-pressed")).toBe("false");
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

const names = (region: HTMLElement) =>
  within(region)
    .queryAllByRole("link")
    .map((link) => link.querySelector(".session-name")!.textContent);
const head = (name: RegExp) => within(list()).getByRole("button", { name });
const storedGroups = () => JSON.parse(localStorage.getItem("lado.sessionGroups") ?? "null");

// Six sessions: three need the human, one runs, two are stopped.
const MIXED = () => [
  session("calm"),
  session("gated", { waiting: { gates: 1, questions: 0, agents: 0 } }),
  session("asking", { waiting: { gates: 0, questions: 2, agents: 0 } }),
  session("stuck", { status: "tmux_gone", waiting: { gates: 0, questions: 0, agents: 1 } }),
  session("gone", { status: "stopped", agents: 0 }), // its gates are open, but nothing waits in it
  session("old", { status: "stopped", agents: 0 }),
];

test("the list groups the sessions: Needs you, Running, then Stopped folded, each under a heading in its tone", async () => {
  sessions = MIXED();
  open("/sessions");
  await within(list()).findByRole("link", { name: /calm/ });
  expect(names(group("Needs you"))).toEqual(["gated", "asking", "stuck"]);
  expect(names(group("Running"))).toEqual(["calm"]);
  expect(group("Needs you").className).toContain("tone-human");
  expect(group("Running").className).toContain("tone-done");
  expect(group("Stopped").className).toContain("tone-neutral");
  // Each heading is a button in an h3, with its count; Stopped is folded by default.
  expect(head(/^Needs you/).textContent).toBe("Needs you 3");
  expect(head(/^Needs you/).closest("h3")!.className).toContain("group-head");
  expect(head(/^Running/).getAttribute("aria-expanded")).toBe("true");
  const stopped = head(/^Stopped/);
  expect(stopped.textContent).toBe("Stopped 2");
  expect(stopped.getAttribute("aria-expanded")).toBe("false");
  // A stopped session is stopped first: nothing can be answered in it.
  expect(names(group("Stopped"))).toEqual([]);
  expect(within(group("Needs you")).getByRole("link", { name: /gated/ }).textContent).toContain("1 gate");
  expect(within(group("Needs you")).getByRole("link", { name: /asking/ }).textContent).toContain("2 questions");
  expect(within(group("Needs you")).getByRole("link", { name: /stuck/ }).textContent).toContain("1 agent waiting");
  fireEvent.click(stopped);
  expect(names(group("Stopped"))).toEqual(["gone", "old"]);
});

test("a group without sessions is not drawn, heading and all", async () => {
  sessions = [session("calm")];
  open("/sessions");
  await within(list()).findByRole("link", { name: /calm/ });
  expect(within(list()).queryByRole("region", { name: "Needs you" })).toBeNull();
  expect(within(list()).queryByRole("region", { name: "Stopped" })).toBeNull();
  expect(within(list()).queryByRole("button", { name: /^(Needs you|Stopped)/ })).toBeNull();
});

test("each heading folds and opens its group; its list stays in the page for aria-controls; remembered by the group's id", async () => {
  sessions = MIXED();
  open("/sessions");
  await within(list()).findByRole("link", { name: /calm/ });
  for (const [name, rows] of [
    ["Needs you", ["gated", "asking", "stuck"]],
    ["Running", ["calm"]],
  ] as const) {
    const button = head(new RegExp(`^${name}`));
    const controlled = () => document.getElementById(button.getAttribute("aria-controls")!);
    expect(controlled()).toBeTruthy();
    fireEvent.click(button);
    expect(button.getAttribute("aria-expanded")).toBe("false");
    expect(names(group(name))).toEqual([]);
    expect(button.textContent).toBe(`${name} ${rows.length}`); // the count stays
    expect(controlled()).toBeTruthy();
    fireEvent.click(button);
    expect(button.getAttribute("aria-expanded")).toBe("true");
    expect(names(group(name))).toEqual(rows);
  }
  fireEvent.click(head(/^Running/));
  fireEvent.click(head(/^Stopped/));
  expect(storedGroups()).toEqual({ "needs-you": "open", running: "folded", stopped: "open" });
  cleanup();
  open("/sessions");
  await within(list()).findByRole("link", { name: /^gone/ }); // remembered open
  expect(head(/^Running/).getAttribute("aria-expanded")).toBe("false");
  expect(names(group("Running"))).toEqual([]);
});

test("an older LADO's open Stopped is where Stopped starts, until the groups are stored", async () => {
  sessions = MIXED();
  localStorage.setItem("lado.stoppedSessions", "open");
  open("/sessions");
  await within(list()).findByRole("link", { name: /^gone/ });
  expect(head(/^Stopped/).getAttribute("aria-expanded")).toBe("true");
});

test("while the search has text the groups with matches are open, and what is remembered stays", async () => {
  sessions = MIXED();
  open("/sessions");
  await within(list()).findByRole("link", { name: /calm/ });
  fireEvent.click(head(/^Running/));
  const before = storedGroups();
  const search = screen.getByRole("searchbox", { name: "Find a session" });
  fireEvent.change(search, { target: { value: "o" } }); // only gone and old
  expect(names(group("Stopped"))).toEqual(["gone", "old"]);
  expect(head(/^Stopped/).getAttribute("aria-expanded")).toBe("true");
  fireEvent.change(search, { target: { value: "cal" } });
  expect(names(group("Running"))).toEqual(["calm"]);
  // A heading folds nothing while the search has text: it is off, and a click changes nothing.
  expect((head(/^Running/) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(head(/^Running/));
  expect(names(group("Running"))).toEqual(["calm"]);
  expect(storedGroups()).toEqual(before);
  fireEvent.change(search, { target: { value: "" } });
  expect(names(group("Running"))).toEqual([]);
  expect(head(/^Stopped/).getAttribute("aria-expanded")).toBe("false");
});

test("the open session stays in sight in its folded group, also when it moves to one; going there changes nothing remembered", async () => {
  sessions = [session("lado"), session("calm"), session("old", { status: "stopped", agents: 0 })];
  open("/sessions/lado");
  await within(list()).findByRole("link", { name: /calm/ });
  fireEvent.click(head(/^Running/));
  expect(names(group("Running"))).toEqual(["lado"]);
  expect(head(/^Running/).getAttribute("aria-expanded")).toBe("false");
  const remembered = storedGroups();
  // Stopped is folded: the open session goes there when it stops, and is seen there alone.
  const stopped = session("lado", { status: "stopped", agents: 0 });
  stream().send("change", { kind: "sessions", session: "lado", key: "", op: "update", item: stopped }, "11");
  expect(names(group("Stopped"))).toEqual(["lado"]);
  expect(head(/^Stopped/).getAttribute("aria-expanded")).toBe("false");
  expect(names(group("Running"))).toEqual([]);
  // Another session from the list: the folded group shows nothing again.
  fireEvent.click(head(/^Running/));
  fireEvent.click(within(group("Running")).getByRole("link", { name: /calm/ }));
  expect(await screen.findByRole("region", { name: "Session calm" })).toBeTruthy();
  expect(names(group("Stopped"))).toEqual([]);
  expect(storedGroups()).toEqual({ ...remembered, running: "open" });
});

test("the rows look alike in every group: no dim, no mark of waiting; the status line of a session in trouble stays", async () => {
  sessions = MIXED();
  localStorage.setItem("lado.sessionGroups", JSON.stringify({ stopped: "open" }));
  open("/sessions");
  await within(list()).findByRole("link", { name: /^gone/ });
  const rows = [...list().querySelectorAll<HTMLElement>(".session-link")];
  expect(rows).toHaveLength(6);
  for (const row of rows) expect(row.className).toBe("session-link");
  expect(within(group("Needs you")).getByRole("link", { name: /stuck/ }).querySelector(".status-tmux_gone")!.textContent).toBe(
    "tmux session is gone",
  );
});

test("a row's card on focus and hover: name · status · agents, what needs the human, the folder, kits · provider · mode", async () => {
  sessions = [
    session("gated", {
      agents: 3,
      waiting: { gates: 1, questions: 2, agents: 0 },
      kits: ["default", "review"],
      permission_mode: "auto",
    }),
    session("calm", { provider: "kilo" }),
    session("old", { status: "stopped", agents: 0 }),
  ];
  localStorage.setItem("lado.sessionGroups", JSON.stringify({ stopped: "open" }));
  open("/sessions");
  const card = async (name: RegExp) => {
    const row = await within(list()).findByRole("link", { name });
    fireEvent.focus(row);
    const shown = screen.getByRole("tooltip");
    expect(row.getAttribute("aria-describedby")).toBe(shown.id);
    const lines = [...shown.querySelectorAll(".tooltip-line")].map((line) => line.textContent);
    const tone = shown.querySelector(".session-tip")!.className;
    fireEvent.blur(row);
    expect(screen.queryByRole("tooltip")).toBeNull();
    return { lines, tone };
  };
  expect(await card(/^gated/)).toEqual({
    lines: ["gated · running · 3 agents", "Needs you: 1 gate · 2 questions", "/src/gated", "default, review · claude · mode auto"],
    tone: "session-tip tone-human",
  });
  expect(await card(/^calm/)).toEqual({
    lines: ["calm · running · 1 agent", "/src/calm", "default · kilo"],
    tone: "session-tip tone-done",
  });
  const stopped = await card(/^old/);
  expect(stopped).toEqual({
    lines: ["old · stopped · 0 agents", "/src/old", "default · claude", "Stopped: open it and press Resume"],
    tone: "session-tip tone-neutral",
  });
  // The pointer resting on a row shows it too.
  vi.useFakeTimers();
  try {
    const row = within(list()).getByRole("link", { name: /^calm/ });
    fireEvent.mouseEnter(row);
    expect(screen.queryByRole("tooltip")).toBeNull();
    act(() => vi.advanceTimersByTime(TOOLTIP_DELAY_MS));
    expect(screen.getByRole("tooltip").textContent).toContain("calm · running · 1 agent");
    fireEvent.mouseLeave(row);
    expect(screen.queryByRole("tooltip")).toBeNull();
  } finally {
    vi.useRealTimers();
  }
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
