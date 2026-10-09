// The session page's layout (docs/design/ui.md, Structure): the team chips, the session
// list's groups and "+", the rail with Launch and the top bar.
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { StrictMode, useState } from "react";
import { createPortal } from "react-dom";
import { Link, MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { AgentInfo, SessionInfo } from "./api";
import { App } from "./App";
import { AGENT_REST, columnWidth, FakeEventSource, FakeResizeObserver, FakeSocket, stream, stubDialogs } from "./fakes";
import { Shell, useTitle, useTopBar } from "./Shell";
import { TOOLTIP_DELAY_MS } from "./Tooltip";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const NONE = { gates: 0, questions: 0, agents: 0 };

function session(name: string, more: Partial<SessionInfo> = {}): SessionInfo {
  const settings = { kits: ["default"], provider: "claude", permission_mode: null, without: [], ran_seconds: 0, running_since: null, stopped_at: null };
  return { name, repo: `/src/${name}`, status: "running", agents: 1, waiting: NONE, busy: 0, activity_since: null, ...settings, ...more };
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

// The card's first line starts with the session's name in bold, no dot or other mark before it.
const nameFirst = (shown: HTMLElement) => {
  const line = shown.querySelector(".tooltip-line")!;
  const first = line.firstChild!;
  return first.nodeName === "B" ? first.textContent : `starts with ${first.nodeName}`;
};

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
    const lead = nameFirst(shown);
    fireEvent.blur(row);
    expect(screen.queryByRole("tooltip")).toBeNull();
    return { lines, lead };
  };
  expect(await card(/^gated/)).toEqual({
    lines: ["gated · running · 3 agents", "Needs you: 1 gate · 2 questions", "/src/gated", "default, review · claude · mode auto"],
    lead: "gated",
  });
  expect(await card(/^calm/)).toEqual({
    lines: ["calm · running · idle · 1 agent", "/src/calm", "default · kilo"],
    lead: "calm",
  });
  const stopped = await card(/^old/);
  expect(stopped).toEqual({
    lines: ["old · stopped · 0 agents", "/src/old", "default · claude", "Stopped: open it and press Resume"],
    lead: "old",
  });
  // The pointer resting on a row shows it too.
  vi.useFakeTimers();
  try {
    const row = within(list()).getByRole("link", { name: /^calm/ });
    fireEvent.mouseEnter(row);
    expect(screen.queryByRole("tooltip")).toBeNull();
    act(() => vi.advanceTimersByTime(TOOLTIP_DELAY_MS));
    expect(screen.getByRole("tooltip").textContent).toContain("calm · running · idle · 1 agent");
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

// Whether a Running session's agents work (SessionInfo.busy, activity_since): a dot before
// its name and its line.
const MINUTE = 60_000;
const ago = (ms: number) => new Date(Date.now() - ms).toISOString();
const row = (name: string) => within(list()).getByRole("link", { name: new RegExp(`^${name}`) });
const dot = (link: HTMLElement) => within(link).queryByRole("img");
const about = (link: HTMLElement) => link.querySelector(".session-about")!.textContent;

test("a Running row says whether its agents work: a full dot and how many, or a ring, with the time since", async () => {
  sessions = [
    session("one", { busy: 1, activity_since: ago(3 * MINUTE) }),
    session("two", { agents: 3, busy: 2, activity_since: ago(40_000) }),
    session("calm", { activity_since: ago(12 * MINUTE) }),
    session("pair", { agents: 2, activity_since: ago(2 * 60 * MINUTE) }),
    session("fresh", { busy: 1 }), // no event tells since when
    session("quiet", { agents: 2 }),
  ];
  open("/sessions");
  await within(list()).findByRole("link", { name: /^one/ });
  expect(names(group("Running"))).toEqual(["one", "two", "calm", "pair", "fresh", "quiet"]);
  const working = dot(row("one"))!;
  expect(working.getAttribute("aria-label")).toBe("working");
  expect(working.className).toContain("activity-working");
  expect(about(row("one"))).toBe("1 of 1 agent · 3 min");
  expect(about(row("two"))).toBe("2 of 3 agents · <1 min");
  const idle = dot(row("calm"))!;
  expect(idle.getAttribute("aria-label")).toBe("idle");
  expect(idle.className).toContain("activity-idle");
  expect(about(row("calm"))).toBe("1 agent · 12 min");
  expect(about(row("pair"))).toBe("2 agents · 2 h");
  expect(about(row("fresh"))).toBe("1 of 1 agent");
  expect(dot(row("quiet"))!.getAttribute("aria-label")).toBe("idle");
  expect(about(row("quiet"))).toBe("2 agents");
});

test("a row's time goes on by itself, on the minute's clock of the head's run time", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  try {
    sessions = [session("calm", { activity_since: ago(30_000) })];
    open("/sessions");
    await within(list()).findByRole("link", { name: /^calm/ });
    expect(about(row("calm"))).toBe("1 agent · <1 min");
    act(() => vi.advanceTimersByTime(MINUTE));
    expect(about(row("calm"))).toBe("1 agent · 1 min");
    act(() => vi.advanceTimersByTime(2 * MINUTE));
    expect(about(row("calm"))).toBe("1 agent · 3 min");
  } finally {
    vi.useRealTimers();
  }
});

test("only a Running row has the dot: Needs you, Stopped, tmux gone and loop down rows are as before", async () => {
  sessions = [
    session("gated", { busy: 1, activity_since: ago(MINUTE), waiting: { gates: 1, questions: 0, agents: 0 } }),
    session("gone", { status: "tmux_gone" }),
    session("down", { status: "loop_down", agents: 2 }),
    session("old", { status: "stopped", agents: 0 }),
  ];
  localStorage.setItem("lado.sessionGroups", JSON.stringify({ stopped: "open" }));
  open("/sessions");
  await within(list()).findByRole("link", { name: /^gated/ });
  for (const name of ["gated", "gone", "down", "old"]) expect(dot(row(name))).toBeNull();
  expect(about(row("gated"))).toBe("1 gate");
  expect(about(row("gone"))).toBe("1 agent");
  expect(about(row("down"))).toBe("2 agents");
  expect(about(row("old"))).toBe("stopped");
});

test("a Running row's card and its icon in the strip say whether it works", async () => {
  sessions = [
    session("busy", { agents: 3, busy: 2, activity_since: ago(MINUTE) }),
    session("calm", { activity_since: ago(12 * MINUTE) }),
    session("gated", { waiting: { gates: 1, questions: 0, agents: 0 } }),
  ];
  open("/sessions");
  const first = async (name: RegExp) => {
    const link = await within(list()).findByRole("link", { name });
    fireEvent.focus(link);
    const line = screen.getByRole("tooltip").querySelector(".tooltip-line")!.textContent;
    fireEvent.blur(link);
    return line;
  };
  expect(await first(/^busy/)).toBe("busy · running · 2 of 3 agents working");
  expect(await first(/^calm/)).toBe("calm · running · idle 12 min · 1 agent");
  expect(await first(/^gated/)).toBe("gated · running · 1 agent");
  cleanup();
  collapsed();
  open("/sessions");
  const icon = (name: string) => within(strip()!).getByRole("link", { name: new RegExp(`^${name}`) });
  await within(strip()!).findByRole("link", { name: /^busy/ });
  expect(icon("busy").getAttribute("aria-label")).toBe("busy, working");
  expect(icon("busy").querySelector(".dot")!.className).toContain("activity-working");
  expect(icon("calm").getAttribute("aria-label")).toBe("calm, idle");
  expect(icon("calm").querySelector(".dot")!.className).toContain("activity-idle");
  expect(icon("gated").getAttribute("aria-label")).toBe("gated, needs you");
  expect(icon("gated").querySelector(".dot")).toBeNull();
  fireEvent.focus(icon("busy"));
  expect(nameFirst(screen.getByRole("tooltip"))).toBe("busy");
  expect(screen.getByRole("tooltip").querySelector(".tooltip-line")!.textContent).toBe("busy · running · 2 of 3 agents working");
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
  await within(strip()!).findByRole("link", { name: "lado, idle" });
  // In the open list's order: Needs you, then Running; no stopped session.
  expect(icons().map((icon) => icon.getAttribute("aria-label"))).toEqual([
    "gated.site, needs you",
    "stuck, needs you",
    "crm-api, idle",
    "lado, idle",
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
  await within(strip()!).findByRole("link", { name: "lado, idle" });
  expect(strip()!.querySelector(".strip-gap")).toBeNull();
});

test("an icon opens its session at the row's address and is current there", async () => {
  collapsed();
  sessions = [session("lado"), session("crm-api")];
  open("/sessions/lado/flows");
  const lado = await within(strip()!).findByRole("link", { name: "lado, idle" });
  const crm = within(strip()!).getByRole("link", { name: "crm-api, idle" });
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

test("the top bar has the title and the link; the server's address is in the link's tooltip", async () => {
  open("/sessions");
  const bar = screen.getByRole("banner");
  expect(bar.querySelector("h1")!.textContent).toBe("Sessions");
  expect(within(bar).queryByText(window.location.host)).toBeNull();
  const link = await within(bar).findByRole("status");
  expect(link.textContent).toBe("live");
  expect(link.getAttribute("title")).toBeNull(); // the UI's tooltip, not the browser's
  fireEvent.focus(link);
  expect(screen.getByRole("tooltip").textContent).toBe(`The LADO server this page talks to: ${window.location.host}`);
  fireEvent.blur(link);
  expect(within(bar).queryByRole("button")).toBeNull();
  stream().fail(false);
  expect(within(bar).getByRole("status").textContent).toMatch(/reconnecting/);
});

// The session's head in the top bar (docs/design/ui.md, Session head; feature/session-head-topbar)

const bar = () => screen.getByRole("banner");
const barHeadings = () => [...bar().querySelectorAll("h1")].map((one) => one.textContent);

test("a session's head is the top bar: its name, the running dot with no word, the facts and the actions", async () => {
  open();
  const region = await screen.findByRole("region", { name: "Session lado" });
  expect(barHeadings()).toEqual(["lado"]);
  const dot = within(bar()).getByRole("img", { name: "running" });
  expect(bar().textContent).not.toMatch(/running/);
  fireEvent.focus(dot);
  expect(screen.getByRole("tooltip").textContent).toBe("running");
  fireEvent.blur(dot);
  expect(bar().querySelector(".session-meta .session-path")!.textContent).toBe("/src/lado");
  expect(within(bar()).getByRole("button", { name: "Copy link" })).toBeTruthy();
  expect(within(bar()).getByRole("button", { name: "Stop session…" })).toBeTruthy();
  expect(bar().querySelector(".link")!.textContent).toBe("live");
  expect(region.querySelector(".session-head, .session-meta, h1, h2")).toBeNull();
  expect(document.title).toBe("lado · LADO");
});

test.each([
  ["stopped", "stopped", null, /^stopped .* ago · ran /],
  ["tmux_gone", "tmux session is gone", "tmux session is gone", /^ran /],
  ["loop_down", "session loop not running", "session loop not running", /^ran |^\d|^<1/],
] as const)("a %s session's dot is named %j; the words, when any, in the danger tone before the run time", async (status, name, words, ran) => {
  const since = status === "loop_down" ? new Date().toISOString() : null;
  const stopped = status === "stopped" ? new Date(Date.now() - 60 * 60_000).toISOString() : null;
  sessions = [session("lado", { status, running_since: since, stopped_at: stopped })];
  open();
  await screen.findByRole("region", { name: "Session lado" });
  const dot = within(bar()).getByRole("img", { name });
  expect(dot.classList).toContain(`session-dot-${status}`);
  const said = bar().querySelector(".session-state");
  expect(said?.textContent ?? null).toBe(words);
  if (said) expect(said.classList).toContain("danger-text");
  expect(bar().querySelector(".session-ran")!.textContent).toMatch(ran);
  expect(bar().textContent!.match(/stopped/g)?.length ?? 0).toBe(status === "stopped" ? 1 : 0);
});

test("the top bar is the page's: a session claims it, not found and loading keep the title, under StrictMode too", async () => {
  sessions = [session("lado"), session("app")];
  const view = render(
    <StrictMode>
      <MemoryRouter initialEntries={["/sessions/lado"]}>
        <App />
      </MemoryRouter>
    </StrictMode>,
  );
  // While the sessions load, the page has no session: the Shell's title.
  expect(barHeadings()).toEqual(["Sessions"]);
  await screen.findByRole("region", { name: "Session lado" });
  expect(barHeadings()).toEqual(["lado"]);
  fireEvent.click(within(screen.getByRole("navigation", { name: "Sessions" })).getByRole("link", { name: /^app/ }));
  await screen.findByRole("region", { name: "Session app" });
  expect(barHeadings()).toEqual(["app"]);
  expect(bar().querySelectorAll(".session-head")).toHaveLength(1);
  view.unmount();
  render(
    <StrictMode>
      <MemoryRouter initialEntries={["/sessions/nowhere"]}>
        <App />
      </MemoryRouter>
    </StrictMode>,
  );
  expect(await screen.findByText("Session nowhere not found")).toBeTruthy();
  expect(barHeadings()).toEqual(["Sessions"]);
  expect(bar().querySelector(".session-head")).toBeNull();
  expect(document.title).toBe("Sessions · LADO");
});

// Two heads that claim the bar at once (useTopBar's contract): the claims are counted, so
// the one that goes does not give the bar back while the other still holds it.
function Claim({ name }: { name: string }) {
  const slot = useTopBar();
  return slot && createPortal(<span className="claim">{name}</span>, slot);
}

function TwoClaims() {
  useTitle("Page");
  const [both, setBoth] = useState(true);
  return (
    <>
      <Claim name="first" />
      {both && <Claim name="second" />}
      <button type="button" onClick={() => setBoth(false)}>
        Drop the second
      </button>
      <Link to="/plain">Elsewhere</Link>
    </>
  );
}

test("the bar stays claimed while any page part claims it; the title comes back with the last", () => {
  const routes = (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<TwoClaims />} />
        <Route path="plain" element={<Plain />} />
      </Route>
    </Routes>
  );
  render(<MemoryRouter initialEntries={["/"]}>{routes}</MemoryRouter>);
  const claims = () => [...bar().querySelectorAll(".claim")].map((one) => one.textContent);
  expect(claims()).toEqual(["first", "second"]);
  expect(barHeadings()).toEqual([]);
  fireEvent.click(screen.getByRole("button", { name: "Drop the second" }));
  expect(claims()).toEqual(["first"]);
  expect(barHeadings()).toEqual([]); // the first still holds it
  fireEvent.click(screen.getByRole("link", { name: "Elsewhere" }));
  expect(claims()).toEqual([]);
  expect(barHeadings()).toEqual(["Plain"]);
});

function Plain() {
  useTitle("Plain");
  return null;
}
