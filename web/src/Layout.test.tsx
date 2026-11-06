// The session page's layout (docs/design/ui.md, Structure): the team chips, the session
// list's groups and "+", the rail with Launch and the top bar.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { StrictMode, useState } from "react";
import { createPortal } from "react-dom";
import { Link, MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { AgentInfo, SessionInfo } from "./api";
import { App } from "./App";
import { AGENT_REST, columnWidth, FakeEventSource, FakeResizeObserver, FakeScreen, FakeSocket, stream, stubDialogs } from "./fakes";
import { LOST_AFTER_MS } from "./live";
import { ranText, sessionMark, tabScroll } from "./Sessions";
import { Shell, useTitle, useTopBar } from "./Shell";
import { TOOLTIP_DELAY_MS } from "./Tooltip";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const NONE = { gates: 0, questions: 0, agents: 0 };

function session(name: string, more: Partial<SessionInfo> = {}): SessionInfo {
  const settings = { kits: ["default"], provider: "claude", permission_mode: null, without: [], ran_seconds: 0, running_since: null, stopped_at: null, title: null, project: null };
  return { name, repo: `/src/${name}`, status: "running", agents: 1, waiting: NONE, busy: 0, ...settings, ...more };
}

function agent(name: string, role: string, status: AgentInfo["status"], more: Partial<AgentInfo> = {}): AgentInfo {
  return { name, role, provider: "claude", status, run: null, task: null, status_reason: null, ...AGENT_REST, ...more };
}

let sessions: SessionInfo[] = [];
let agents: AgentInfo[] = [];
let runs: { name: string; status: string; created_at: string }[] | "pending" = []; // the session's runs, newest first

beforeEach(() => {
  localStorage.clear();
  sessions = [session("lado")];
  agents = [];
  runs = [];
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
      if (path.endsWith("/runs")) return runs === "pending" ? new Promise<Response>(() => {}) : new Response(JSON.stringify(runs));
      if (path.endsWith("/about")) return new Response("{}", { status: 404 }); // the head without its about
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
  vi.restoreAllMocks();
});

function open(path = "/sessions/lado") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

// The team

test("the team shows every agent as a chip, the supervisor first, with its status and name, the role for the ear", async () => {
  agents = [
    agent("w1", "developer", "busy", { task: "Build the layout" }),
    agent("supervisor", "supervisor", "idle"),
    agent("w2", "reviewer", "waiting"),
    agent("w3", "developer", "starting"),
    agent("w4", "developer", "stopped"),
  ];
  open();
  const team = await screen.findByRole("toolbar", { name: "Team" });
  const chips = await within(team).findAllByRole("button");
  expect(chips.map((chip) => chip.getAttribute("aria-label"))).toEqual([
    "supervisor, idle",
    "w1, developer, working",
    "w2, reviewer, waits for you",
    "w3, developer, starting",
    "w4, developer, stopped",
  ]);
  // Each status has a dot of its own (colour and shape: styles.css).
  const dots = chips.map((chip) => chip.querySelector(".dot")!.className);
  expect(new Set(dots).size).toBe(5);
  expect(chips.map((chip) => chip.textContent)).toEqual(["supervisor", "w1", "w2", "w3", "w4"]); // no role shown
  expect(chips.some((chip) => chip.hasAttribute("title"))).toBe(false); // the tooltip, below
  // The panel shows the supervisor's terminal from the start.
  expect(chips.map((chip) => chip.getAttribute("aria-pressed"))).toEqual(["true", "false", "false", "false", "false"]);
});

test("a chip's popup: its name, status and how long, role · provider, its flow run and what a click does", async () => {
  const since = new Date(Date.now() - 4 * 60_000).toISOString();
  agents = [
    agent("supervisor", "supervisor", "idle", { since }),
    agent("w1", "developer", "busy", { provider: "kilo", run: "feature/ui-polish", task: "Build it", since }),
  ];
  open();
  const team = await screen.findByRole("toolbar", { name: "Team" });
  const tip = async (name: string) => {
    const chip = await within(team).findByRole("button", { name: new RegExp(`^${name},`) });
    fireEvent.focus(chip);
    const shown = screen.getByRole("tooltip");
    expect(chip.getAttribute("aria-describedby")).toBe(shown.id);
    const lines = [...shown.querySelectorAll(".tooltip-line")].map((line) => line.textContent);
    fireEvent.blur(chip);
    return lines;
  };
  expect(await tip("w1")).toEqual([
    "w1",
    "working · 4 min",
    "developer · kilo",
    "flow feature/ui-polish",
    "Click to open the terminal",
  ]); // no task
  expect(await tip("supervisor")).toEqual(["supervisor", "idle · 4 min", "claude", "Click to open the terminal"]); // the role is its name
});

test("a run's agents are chips in a frame coloured by the run, with a link to its page in Flows", async () => {
  agents = [
    agent("dev", "developer", "busy", { run: "feature/x" }),
    agent("supervisor", "supervisor", "idle"),
    agent("w1", "researcher", "idle"),
    agent("rev", "reviewer", "waiting", { run: "feature/x" }),
    agent("dev-2", "developer", "starting", { run: "fix/y" }),
  ];
  // Newest first, as the server serves them: fix/y started third, feature/x first.
  runs = [
    { name: "fix/y", status: "active", created_at: "2026-10-04T10:03:00.000Z" },
    { name: "old/z", status: "ended", created_at: "2026-10-04T10:02:00.000Z" },
    { name: "feature/x", status: "active", created_at: "2026-10-04T10:01:00.000Z" },
  ];
  open();
  const team = await screen.findByRole("toolbar", { name: "Team" });
  await within(team).findAllByRole("button");
  const frames = within(team).getAllByRole("group");
  expect(frames.map((frame) => frame.getAttribute("aria-label"))).toEqual(["run feature/x", "run fix/y"]);
  const [x, y] = frames;
  await waitFor(() => expect(x.getAttribute("data-colour")).toBe("1"));
  expect(y.getAttribute("data-colour")).toBe("3");
  const link = within(x).getByRole("link", { name: "run feature/x in Flows" });
  expect(link.getAttribute("href")).toBe(`/sessions/lado/flows/${encodeURIComponent("feature/x")}`);
  expect(x.textContent).toBe("devrev"); // no name, no state of the run, no roles
  const inX = within(x).getAllByRole("button");
  expect(inX.map((chip) => chip.getAttribute("aria-label"))).toEqual(["dev, developer, working", "rev, reviewer, waits for you"]);
  expect(within(y).getAllByRole("button").map((chip) => chip.getAttribute("aria-label"))).toEqual([
    "dev-2, developer, starting",
  ]);
  // The supervisor and its own workers: first, outside every frame, the same chips.
  const chips = within(team).getAllByRole("button");
  expect(chips.slice(0, 2).map((chip) => chip.getAttribute("aria-label"))).toEqual([
    "supervisor, idle",
    "w1, researcher, idle",
  ]);
  expect(chips.slice(0, 2).some((chip) => chip.closest(".team-run") !== null)).toBe(false);
  expect(chips.every((chip) => chip.className === "team-chip")).toBe(true);
  // A chip in a frame opens its agent's terminal, as any chip.
  fireEvent.click(inX[1]);
  expect(inX[1].getAttribute("aria-pressed")).toBe("true");
  expect(chips[0].getAttribute("aria-pressed")).toBe("false");
});

test("until the session's runs are loaded, a run's frame has no colour", async () => {
  agents = [agent("supervisor", "supervisor", "idle"), agent("dev", "developer", "busy", { run: "feature/x" })];
  runs = "pending";
  open();
  const team = await screen.findByRole("toolbar", { name: "Team" });
  const frame = await within(team).findByRole("group", { name: "run feature/x" });
  expect(frame.hasAttribute("data-colour")).toBe(false);
  expect(within(frame).getByRole("link", { name: "run feature/x in Flows" })).toBeTruthy();
});

test("a chip follows its agent's changes", async () => {
  agents = [agent("supervisor", "supervisor", "idle")];
  open();
  const team = await screen.findByRole("toolbar", { name: "Team" });
  await within(team).findByRole("button", { name: "supervisor, idle" });
  const busy = agent("supervisor", "supervisor", "busy");
  stream().send("change", { kind: "agents", session: "lado", key: "supervisor", op: "update", item: busy }, "11");
  expect(within(team).getByRole("button", { name: "supervisor, working" })).toBeTruthy();
});

// The team in the head: jsdom measures nothing, so what fits is said here, by the level the
// team shows and its avatars.
function teamFits(fits: (level: number, visible: number) => boolean) {
  vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
    const team = this.closest<HTMLElement>(".head-team");
    const fit = Number(team?.dataset.fit ?? 0);
    const visible = team?.querySelectorAll(".strip-agent").length ?? 0;
    const right = team && this !== team && !fits(fit, visible) ? 100 : 0;
    return new DOMRect(0, 0, right, 0);
  });
}

async function headTeam(names: string[], fits: (level: number, visible: number) => boolean) {
  teamFits(fits);
  agents = [agent("supervisor", "supervisor", "idle"), ...names.map((name) => agent(name, "developer", "idle"))];
  open();
  return screen.findByRole("toolbar", { name: "Team" });
}

test("with no agents the head holds no room for a team", async () => {
  agents = [];
  open();
  await screen.findByRole("region", { name: "Session lado" });
  await act(async () => {
    await new Promise((done) => setTimeout(done)); // the agents arrive
  });
  expect(document.querySelector(".head-team")).toBeNull();
});

test("the team stands in the head on every tab, and no row of it on Activity", async () => {
  agents = [agent("supervisor", "supervisor", "idle")];
  open("/sessions/lado/artifacts");
  const team = await screen.findByRole("toolbar", { name: "Team" });
  expect(team.closest(".topbar")).toBeTruthy();
  expect(team.nextElementSibling?.className).toBe("session-head-actions");
  expect(screen.queryByRole("group", { name: "Team" })).toBeNull();
});

test("no level mixes names and avatars: names at 1, avatars at 2 with the chevron", async () => {
  const team = await headTeam(["developer-2", "reviewer"], (level) => level >= 2);
  await waitFor(() => expect(team.dataset.fit).toBe("2"));
  expect(team.querySelectorAll(".team-chip")).toHaveLength(0);
  expect([...team.querySelectorAll(".strip-agent")].map((one) => one.firstChild?.textContent)).toEqual(["S", "D2", "R"]);
  expect(within(team).getByRole("button", { name: "All 3 agents" }).className).toBe("team-more chevron");
});

test("at level 1 every name is cut to one length, whole in its name and popup", async () => {
  const team = await headTeam(["developer-2", "reviewer"], (level) => level >= 1);
  await waitFor(() => expect(team.dataset.fit).toBe("1"));
  expect(team.querySelector(".team-label")).toBeNull();
  expect([...team.querySelectorAll(".team-chip-name")].map((one) => one.textContent)).toEqual([
    "supervisor",
    "developer-2",
    "reviewer",
  ]);
  expect(within(team).getByRole("button", { name: "developer-2, developer, idle" })).toBeTruthy();
});

test("at level 3 the first avatars that fit show, and the button stands for the rest", async () => {
  const team = await headTeam(["w1", "w2", "w3"], (level, visible) => level === 3 && visible <= 2);
  await waitFor(() => expect(team.querySelectorAll(".strip-agent")).toHaveLength(2));
  const more = within(team).getByRole("button", { name: "2 more agents" });
  expect(more.textContent).toBe("+2");
  expect(more.querySelector(".dot")).toBeNull(); // the diamond's room counted, not shown
});

test("a status change leaves the level, and a hidden agent's wait shows on the button", async () => {
  const team = await headTeam(["w1", "w2"], (level, visible) => level === 3 && visible <= 1);
  await waitFor(() => expect(team.querySelectorAll(".strip-agent")).toHaveLength(1));
  const waits = agent("w2", "developer", "waiting");
  stream().send("change", { kind: "agents", session: "lado", key: "w2", op: "update", item: waits }, "11");
  const more = await within(team).findByRole("button", { name: "2 more agents, 1 waits for you" });
  expect(more.querySelector(".dot-waiting")).toBeTruthy();
  expect(team.querySelectorAll(".strip-agent")).toHaveLength(1);
});

test("with no avatar left the button shows the Agents icon and the number, no plus", async () => {
  const team = await headTeam(["w1"], () => false);
  const more = await within(team).findByRole("button", { name: "2 agents" });
  expect(more.textContent).toBe("2");
  expect(more.querySelector("svg")).toBeTruthy();
});

test("a level with names stands only while the title keeps its limit; avatars take no limit", async () => {
  vi.spyOn(Range.prototype, "getBoundingClientRect").mockReturnValue(new DOMRect(0, 0, 300, 0));
  const team = await headTeam(["w1"], () => true);
  await waitFor(() => expect(team.dataset.fit).toBe("2"));
});

test("the team's list shows every agent; a row opens its terminal and closes the list", async () => {
  const team = await headTeam(["w1", "w2"], (level, visible) => level === 3 && visible <= 1);
  await waitFor(() => expect(team.querySelectorAll(".strip-agent")).toHaveLength(1));
  const more = within(team).getByRole("button", { name: "2 more agents" });
  fireEvent.click(more);
  const dialog = screen.getByRole("dialog", { name: "Team" });
  expect(within(dialog).getByRole("heading").textContent).toBe("Team · 3 agents");
  const rows = within(dialog).getAllByRole("button");
  expect(rows.map((row) => row.querySelector(".team-popover-name")!.textContent)).toEqual(["supervisor", "w1", "w2"]);
  expect(rows[0]!.getAttribute("aria-current")).toBe("true");
  expect(document.activeElement).toBe(rows[0]);
  fireEvent.click(rows[2]!);
  expect(screen.queryByRole("dialog", { name: "Team" })).toBeNull();
  expect(more.hasAttribute("data-shown")).toBe(true); // the terminal shown is among the hidden
  fireEvent.click(more);
  expect(within(screen.getByRole("dialog", { name: "Team" })).getAllByRole("button")[2]!.getAttribute("aria-current")).toBe("true");
});

test("the list's button says its name as a tooltip, on the chevron and on +N", async () => {
  const team = await headTeam(["w1", "w2", "w3"], (level, visible) => level === 3 && visible <= 2);
  await waitFor(() => expect(team.querySelectorAll(".strip-agent")).toHaveLength(2));
  for (const name of ["w2", "w3"]) {
    const waits = agent(name, "developer", "waiting");
    stream().send("change", { kind: "agents", session: "lado", key: name, op: "update", item: waits }, "11");
  }
  const more = await within(team).findByRole("button", { name: "2 more agents, 2 wait for you" });
  fireEvent.mouseEnter(more);
  expect((await screen.findByRole("tooltip")).textContent).toBe("2 more agents, 2 wait for you");
});

test("with the list open its button shows no tooltip, and the one that was up goes", async () => {
  const team = await headTeam(["w1"], (level) => level === 2);
  await waitFor(() => expect(team.dataset.fit).toBe("2"));
  const button = within(team).getByRole("button", { name: "All 2 agents" });
  fireEvent.mouseEnter(button);
  expect((await screen.findByRole("tooltip")).textContent).toBe("All 2 agents");
  fireEvent.click(button);
  expect(screen.getByRole("dialog", { name: "Team" })).toBeTruthy();
  expect(screen.queryByRole("tooltip")).toBeNull();
  fireEvent.mouseLeave(button);
  fireEvent.mouseEnter(button);
  await act(() => new Promise((done) => setTimeout(done, TOOLTIP_DELAY_MS + 20)));
  expect(screen.queryByRole("tooltip")).toBeNull();
});

test("Esc and a second click close the list with the focus on its button; a press away leaves the focus", async () => {
  const team = await headTeam(["w1"], (level) => level === 2);
  await waitFor(() => expect(team.dataset.fit).toBe("2"));
  const button = within(team).getByRole("button", { name: "All 2 agents" });
  fireEvent.click(button);
  fireEvent.keyDown(document.activeElement!, { key: "Escape" });
  expect(screen.queryByRole("dialog", { name: "Team" })).toBeNull();
  expect(document.activeElement).toBe(button);
  fireEvent.click(button);
  fireEvent.click(button);
  expect(screen.queryByRole("dialog", { name: "Team" })).toBeNull();
  expect(document.activeElement).toBe(button);
  fireEvent.click(button);
  fireEvent.mouseDown(document.body);
  expect(screen.queryByRole("dialog", { name: "Team" })).toBeNull();
});

test("the team is one Tab stop, and the arrows, Home and End move among its items", async () => {
  agents = [agent("supervisor", "supervisor", "idle"), agent("w1", "developer", "idle"), agent("w2", "developer", "idle", { run: "x" })];
  open();
  const team = await screen.findByRole("toolbar", { name: "Team" });
  const items = await waitFor(() => {
    const all = [...team.querySelectorAll<HTMLElement>("button, a")];
    expect(all).toHaveLength(4); // the run's link too
    return all;
  });
  expect(items.map((one) => one.tabIndex)).toEqual([0, -1, -1, -1]);
  items[0]!.focus();
  fireEvent.keyDown(items[0]!, { key: "ArrowRight" });
  expect(document.activeElement).toBe(items[1]);
  expect(items.map((one) => one.tabIndex)).toEqual([-1, 0, -1, -1]);
  fireEvent.keyDown(items[1]!, { key: "End" });
  expect(document.activeElement).toBe(items[3]);
  fireEvent.keyDown(items[3]!, { key: "Home" });
  expect(document.activeElement).toBe(items[0]);
  fireEvent.keyDown(items[0]!, { key: "ArrowLeft" });
  expect(document.activeElement).toBe(items[3]);
});

test("a new agent leaves the open list and the focus in it where they were", async () => {
  const team = await headTeam(["w1", "w2"], (level) => level === 2);
  await waitFor(() => expect(team.dataset.fit).toBe("2"));
  fireEvent.click(within(team).getByRole("button", { name: "All 3 agents" }));
  const dialog = screen.getByRole("dialog", { name: "Team" });
  const row = within(dialog).getAllByRole("button")[2]!;
  row.focus();
  const w3 = agent("w3", "developer", "idle");
  stream().send("change", { kind: "agents", session: "lado", key: "w3", op: "update", item: w3 }, "11");
  await within(team).findByRole("button", { name: "All 4 agents" });
  await waitFor(() => expect(within(screen.getByRole("dialog", { name: "Team" })).getAllByRole("button")).toHaveLength(4));
  expect(document.activeElement?.textContent).toContain("w2");
});

test("the run time growing chooses the level again, while the team shows whole names", async () => {
  const fits = vi.fn(() => true);
  const team = await headTeam(["w1"], fits);
  await waitFor(() => expect(fits).toHaveBeenCalled());
  await act(async () => {
    await new Promise((done) => setTimeout(done));
  });
  const before = fits.mock.calls.length;
  const grown = session("lado", { ran_seconds: 7200 });
  stream().send("change", { kind: "sessions", session: "lado", key: "", op: "update", item: grown }, "11");
  await waitFor(() => expect(fits.mock.calls.length).toBeGreaterThan(before));
  expect(team.dataset.fit).toBe("0");
});

test("a list left open at level 0 keeps its button until it closes, the focus then on the team", async () => {
  let least = 2;
  const team = await headTeam(["w1"], (level) => level >= least);
  await waitFor(() => expect(team.dataset.fit).toBe("2"));
  fireEvent.click(within(team).getByRole("button", { name: "All 2 agents" }));
  least = 0;
  const w2 = agent("w2", "developer", "idle");
  stream().send("change", { kind: "agents", session: "lado", key: "w2", op: "update", item: w2 }, "11");
  await waitFor(() => expect(team.dataset.fit).toBe("0"));
  expect(screen.getByRole("dialog", { name: "Team" })).toBeTruthy();
  fireEvent.keyDown(document.activeElement!, { key: "Escape" });
  expect(screen.queryByRole("dialog", { name: "Team" })).toBeNull();
  expect(team.querySelector(".team-more")).toBeNull();
  expect(document.activeElement).toBe(team.querySelector(".team-chip"));
});

test("the toolbar leaves a key with a modifier to the browser", async () => {
  agents = [agent("supervisor", "supervisor", "idle"), agent("w1", "developer", "idle")];
  open();
  const team = await screen.findByRole("toolbar", { name: "Team" });
  const [first] = await within(team).findAllByRole("button");
  first!.focus();
  for (const modifier of ["altKey", "ctrlKey", "metaKey", "shiftKey"]) {
    expect(fireEvent.keyDown(first!, { key: "ArrowRight", [modifier]: true })).toBe(true); // not prevented
    expect(document.activeElement).toBe(first);
  }
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
  const first = shown.querySelector(".session-tip")!.firstElementChild!.firstChild!;
  return first.nodeName === "B" ? first.textContent : `starts with ${first.nodeName}`;
};

// A card's lines as text, a labelled fact as `<label> <value>`.
const tipLines = (shown: HTMLElement) =>
  [...shown.querySelector(".session-tip")!.children].flatMap((line) =>
    line.tagName === "DL"
      ? [...line.querySelectorAll("dt")].map((label) => `${label.textContent} ${label.nextElementSibling!.textContent}`)
      : [line.textContent],
  );

test("a row's card on focus and hover: the name, what the session is in, its labelled facts", async () => {
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
    const lines = tipLines(shown);
    const lead = nameFirst(shown);
    fireEvent.blur(row);
    expect(screen.queryByRole("tooltip")).toBeNull();
    return { lines, lead };
  };
  expect(await card(/^gated/)).toEqual({
    lines: ["gated", "Needs you: 1 gate · 2 questions", "Ran <1 min", "Folder /src/gated", "Kits default, review", "CLI claude", "Mode auto"],
    lead: "gated",
  });
  expect(await card(/^calm/)).toEqual({
    lines: ["calm", "idle", "Ran <1 min", "Folder /src/calm", "Kits default", "CLI kilo"],
    lead: "calm",
  });
  const stopped = await card(/^old/);
  expect(stopped).toEqual({
    lines: ["old", "stopped", "Ran <1 min", "Folder /src/old", "Kits default", "CLI claude", "Open it and press Resume"],
    lead: "old",
  });
  // The pointer resting on a row shows it too.
  vi.useFakeTimers();
  try {
    const row = within(list()).getByRole("link", { name: /^calm/ });
    fireEvent.mouseEnter(row);
    expect(screen.queryByRole("tooltip")).toBeNull();
    act(() => vi.advanceTimersByTime(TOOLTIP_DELAY_MS));
    expect(tipLines(screen.getByRole("tooltip")).slice(0, 2)).toEqual(["calm", "idle"]);
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

// A Running session's row: a dot before its name for whether its agents work
// (SessionInfo.busy), and a line with how long it ran, the head's run time.
const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const ago = (ms: number) => new Date(Date.now() - ms).toISOString();
const row = (name: string) => within(list()).getByRole("link", { name: new RegExp(`^${name}`) });
const dot = (link: HTMLElement) => within(link).queryByRole("img");
const about = (link: HTMLElement) => link.querySelector(".session-about")!.textContent;

test("a Running row says whether its agents work, a full dot or a ring, and its run time, not how many agents it has", async () => {
  sessions = [
    session("one", { busy: 1, running_since: ago(3 * MINUTE) }),
    session("two", { agents: 3, busy: 2, running_since: ago(40_000) }),
    session("calm", { ran_seconds: 10 * 60, running_since: ago(2 * HOUR + 4 * MINUTE + 30_000) }),
    session("long", { agents: 2, ran_seconds: 32 * 60 * 60, running_since: ago(MINUTE) }),
  ];
  open("/sessions");
  await within(list()).findByRole("link", { name: /^one/ });
  expect(names(group("Running"))).toEqual(["one", "two", "calm", "long"]);
  const working = dot(row("one"))!;
  expect(working.getAttribute("aria-label")).toBe("working");
  expect(working.className).toContain("activity-working");
  expect(about(row("one"))).toBe("ran 3 min");
  expect(about(row("two"))).toBe("ran <1 min");
  const idle = dot(row("calm"))!;
  expect(idle.getAttribute("aria-label")).toBe("idle");
  expect(idle.className).toContain("activity-idle");
  expect(about(row("calm"))).toBe("ran 2 h 14 min");
  expect(about(row("long"))).toBe("ran 1 d 8 h");
});

test.each([
  ["a running session: its closed spans and the time since its start, no prefix", { ran_seconds: 600, running_since: "2026-10-11T08:00:00Z" }, "2 h 10 min"],
  ["a running session over a day", { ran_seconds: 32 * 3600, running_since: "2026-10-11T09:59:30Z" }, "1 d 8 h"],
  ["a stopped session: when it stopped and how long it ran", { status: "stopped", ran_seconds: 182 * 60, stopped_at: "2026-10-11T04:40:00Z" }, "stopped 5 h ago · ran 3 h 2 min"],
  ["a session with no start nor stop (tmux gone)", { status: "tmux_gone", ran_seconds: 182 * 60 }, "ran 3 h 2 min"],
] as const)("ranText: %s", (_, more, text) => {
  expect(ranText(session("s", more as Partial<SessionInfo>), Date.parse("2026-10-11T10:00:00Z"))).toBe(text);
});

test("a Running row's run time is the head's and goes on by itself, on the same minute's clock", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  try {
    sessions = [session("calm", { ran_seconds: 10 * 60, running_since: ago(2 * HOUR + 4 * MINUTE + 30_000) })];
    open("/sessions/calm");
    await screen.findByRole("region", { name: "Session calm" });
    const head = () => document.querySelector(".session-ran")!.textContent;
    expect(about(row("calm"))).toBe("ran 2 h 14 min");
    expect(head()).toBe("2 h 14 min");
    act(() => vi.advanceTimersByTime(MINUTE));
    expect(about(row("calm"))).toBe("ran 2 h 15 min");
    expect(head()).toBe("2 h 15 min");
  } finally {
    vi.useRealTimers();
  }
});

test("a Stopped row says when it stopped and how long it ran, as its head does", async () => {
  sessions = [session("old", { status: "stopped", agents: 0, ran_seconds: (3 * 60 + 2) * 60, stopped_at: ago(5 * HOUR + 20 * MINUTE) })];
  localStorage.setItem("lado.sessionGroups", JSON.stringify({ stopped: "open" }));
  open("/sessions/old");
  await screen.findByRole("region", { name: "Session old" });
  expect(about(row("old"))).toBe("stopped 5 h ago · ran 3 h 2 min");
  expect(document.querySelector(".session-ran")!.textContent).toBe("stopped 5 h ago · ran 3 h 2 min");
  expect(dot(row("old"))).toBeNull();
});

test("only a Running row has the dot; a row in trouble says its run time unless something waits", async () => {
  sessions = [
    session("gated", { busy: 1, running_since: ago(MINUTE), waiting: { gates: 1, questions: 0, agents: 0 } }),
    session("gone", { status: "tmux_gone", ran_seconds: 600 }),
    session("down", { status: "loop_down", agents: 2, running_since: ago(HOUR) }),
    session("held", { status: "tmux_gone", ran_seconds: 600, waiting: { gates: 1, questions: 0, agents: 0 } }),
  ];
  open("/sessions");
  await within(list()).findByRole("link", { name: /^gated/ });
  for (const name of ["gated", "gone", "down", "held"]) expect(dot(row(name))).toBeNull();
  expect(about(row("gated"))).toBe("1 gate");
  expect(about(row("gone"))).toBe("ran 10 min");
  expect(about(row("down"))).toBe("ran 1 h");
  expect(about(row("held"))).toBe("1 gate");
});

// A card's lines, of a row's link or an icon.
const cardLines = (link: HTMLElement) => {
  fireEvent.focus(link);
  const lines = tipLines(screen.getByRole("tooltip"));
  fireEvent.blur(link);
  return lines;
};

test("a card's state line and Ran, in the row's card and the icon's", async () => {
  sessions = [
    session("busy", { agents: 3, busy: 2, ran_seconds: 32 * 60 * 60, running_since: ago(MINUTE) }),
    session("calm", { running_since: ago(12 * MINUTE) }),
    session("gated", { running_since: ago(MINUTE), waiting: { gates: 1, questions: 0, agents: 0 } }),
    session("old", { status: "stopped", agents: 0, ran_seconds: (3 * 60 + 2) * 60, stopped_at: ago(5 * HOUR) }),
    session("undated", { status: "stopped", agents: 0, ran_seconds: (3 * 60 + 2) * 60 }),
    session("gone", { status: "tmux_gone", ran_seconds: 600 }),
    session("held", { status: "tmux_gone", ran_seconds: 600, waiting: { gates: 1, questions: 0, agents: 0 } }),
    session("down", { status: "loop_down", running_since: ago(HOUR) }),
  ];
  localStorage.setItem("lado.sessionGroups", JSON.stringify({ stopped: "open" }));
  open("/sessions");
  await within(list()).findByRole("link", { name: /^busy/ });
  expect(cardLines(row("busy")).slice(0, 3)).toEqual(["busy", "2 of 3 agents working", "Ran 1 d 8 h"]);
  expect(cardLines(row("calm")).slice(0, 3)).toEqual(["calm", "idle", "Ran 12 min"]);
  expect(cardLines(row("gated")).slice(0, 3)).toEqual(["gated", "Needs you: 1 gate", "Ran 1 min"]);
  expect(cardLines(row("old")).slice(0, 3)).toEqual(["old", "stopped 5 h ago", "Ran 3 h 2 min"]);
  expect(cardLines(row("undated")).slice(0, 3)).toEqual(["undated", "stopped", "Ran 3 h 2 min"]);
  expect(cardLines(row("gone")).slice(0, 3)).toEqual(["gone", "tmux session is gone", "Ran 10 min"]);
  expect(cardLines(row("held")).slice(0, 4)).toEqual(["held", "tmux session is gone", "Needs you: 1 gate", "Ran 10 min"]);
  expect(cardLines(row("down")).slice(0, 3)).toEqual(["down", "session loop not running", "Ran 1 h"]);
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
  expect(icon("gated").querySelector(".dot")!.className).toContain("dot-waiting");
  fireEvent.focus(icon("busy"));
  expect(nameFirst(screen.getByRole("tooltip"))).toBe("busy");
  fireEvent.blur(icon("busy"));
  expect(cardLines(icon("busy")).slice(0, 3)).toEqual(["busy", "2 of 3 agents working", "Ran 1 d 8 h"]);
});

// The card's state line: the mark before its words, hidden from a screen reader, which reads
// the words, and the words' class, which gives their colour.
const statusOf = (link: HTMLElement) => {
  fireEvent.focus(link);
  const shown = screen.getByRole("tooltip");
  const card = shown.firstElementChild!;
  const line = card.children[1];
  const mark = line.querySelector(".dot");
  const word = line.lastElementChild!;
  const seen = { card: card.className, mark: mark?.className ?? null, hidden: mark?.getAttribute("aria-hidden") ?? null, word: `${word.className}: ${word.textContent}` };
  fireEvent.blur(link);
  return seen;
};

test("a card's state line has the row's mark in its colour, in the row's card and the icon's", async () => {
  sessions = [
    session("busy", { busy: 1 }),
    session("calm"),
    session("gated", { waiting: { gates: 1, questions: 0, agents: 0 } }),
    session("stuck", { status: "tmux_gone" }),
    session("old", { status: "stopped", agents: 0 }),
  ];
  localStorage.setItem("lado.sessionGroups", JSON.stringify({ stopped: "open" }));
  open("/sessions");
  await within(list()).findByRole("link", { name: /^old/ });
  const working = { card: "session-tip tone-done", mark: "dot activity-working", hidden: "true", word: "tip-status: 1 of 1 agent working" };
  const running = { card: "session-tip tone-done", mark: "dot activity-idle", hidden: "true", word: "tip-muted: idle" };
  const needsYou = { card: "session-tip tone-human", mark: "dot dot-waiting", hidden: "true", word: "tip-waits: Needs you: 1 gate" };
  const trouble = { card: "session-tip tone-done", mark: "dot session-dot-tmux_gone", hidden: "true", word: "danger-text: tmux session is gone" };
  expect(statusOf(row("busy"))).toEqual(working);
  expect(statusOf(row("calm"))).toEqual(running);
  expect(statusOf(row("gated"))).toEqual(needsYou);
  expect(statusOf(row("stuck"))).toEqual(trouble);
  expect(statusOf(row("old"))).toEqual({ card: "session-tip tone-neutral", mark: null, hidden: null, word: "tip-muted: stopped" });
  cleanup();
  collapsed();
  open("/sessions");
  await within(strip()!).findByRole("link", { name: /^calm/ });
  const icon = (name: string) => within(strip()!).getByRole("link", { name: new RegExp(`^${name}`) });
  expect(statusOf(icon("calm"))).toEqual(running);
  expect(statusOf(icon("gated"))).toEqual(needsYou);
  expect(statusOf(icon("stuck"))).toEqual(trouble);
  // The strip has no icon of a stopped session, so no card of one.
  expect(within(strip()!).queryByRole("link", { name: /^old/ })).toBeNull();
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

test("short of room the list folds to its strip and comes back, and nothing is stored", async () => {
  columnWidth(null);
  localStorage.setItem("lado.sessionsList", JSON.stringify({ width: 400 }));
  open("/sessions");
  FakeResizeObserver.resize(() => 800); // 400 + the terminals' strip leave the chat 368 px
  expect(document.querySelector("nav.sessions-strip")).toBeTruthy();
  expect(document.querySelector<HTMLElement>(".sessions")!.style.getPropertyValue("--list-width")).toBe("48px");
  expect(JSON.parse(localStorage.getItem("lado.sessionsList")!)).toEqual({ width: 400 });
  FakeResizeObserver.resize(() => 1600);
  expect(document.querySelector("nav.sessions-strip")).toBeNull();
  const edge = screen.getByRole("separator", { name: "Resize the session list" });
  expect(Number(edge.getAttribute("aria-valuenow"))).toBe(400);
});

test("the strip's badges tell sessions apart: a task's number, a title's letters, a mark on a clash", async () => {
  sessions = [
    session("lad-154-epic"),
    session("x1", { title: "lad-189 (session UI review)" }),
    session("lad-77-checkout", { title: "Checkout redesign" }),
    session("web-2154"),
    session("kilo-ui"),
  ];
  localStorage.setItem("lado.sessionsList", JSON.stringify({ collapsed: true }));
  open("/sessions");
  await waitFor(() => expect(document.querySelectorAll(".strip-session")).toHaveLength(5));
  const badges = [...document.querySelectorAll(".strip-session")].map((one) => one.textContent);
  expect(badges).toEqual(["154", "189", "CR", "154·2", "KU"]);
  expect(document.querySelectorAll(".strip-session.long")).toHaveLength(1);
});

test("with nothing stored the rail follows the window; the human's choice wins", () => {
  const screen_ = new FakeScreen("fine", 1599, 900);
  open("/sessions");
  const app = document.querySelector(".app")!;
  expect(app.classList.contains("collapsed")).toBe(true);
  screen_.set({ width: 1600 });
  expect(app.classList.contains("collapsed")).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Collapse menu" }));
  expect(localStorage.getItem("lado.rail")).toBe("collapsed");
  screen_.set({ width: 2000 });
  expect(app.classList.contains("collapsed")).toBe(true);
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

// On a phone (docs/design/ui.md, Phone layout): Sessions is the list, a session's page the
// session alone; nothing of the computer's list is read or written.

test("on a phone Sessions is the list, whatever the computer's list keeps: no strip, no edge, no collapse", async () => {
  collapsed();
  FakeScreen.phone();
  open("/sessions");
  const list = screen.getByRole("navigation", { name: "Sessions" });
  expect(list.classList.contains("sessions-strip")).toBe(false);
  expect(await within(list).findByRole("link", { name: /^lado/ })).toBeTruthy();
  expect(screen.getByRole("searchbox", { name: "Find a session" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "New session" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Collapse sessions" })).toBeNull();
  expect(screen.queryByRole("separator", { name: "Resize the session list" })).toBeNull();
  expect(screen.queryByText("Select a session")).toBeNull();
  expect(screen.getByRole("banner").textContent).toContain("Sessions");
});

test("on a phone a session's page is the session alone; the computer's list state is untouched", async () => {
  localStorage.setItem("lado.sessionsList", JSON.stringify({ width: 320, collapsed: false }));
  FakeScreen.phone();
  open("/sessions");
  fireEvent.click(await screen.findByRole("link", { name: /^lado/ }));
  await screen.findByRole("region", { name: "Session lado" });
  expect(screen.queryByRole("navigation", { name: "Sessions" })).toBeNull();
  expect(JSON.parse(localStorage.getItem("lado.sessionsList")!)).toEqual({ width: 320, collapsed: false });
});

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

test("an icon's card: the name, what the session is in, its labelled facts, how to go on; Esc hides it", async () => {
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
    const lines = tipLines(shown);
    const waits = [...shown.querySelectorAll(".tip-waits")].map((line) => line.textContent);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("tooltip")).toBeNull();
    return { lines, waits };
  };
  expect(await tip(/^gated/)).toEqual({
    lines: ["gated", "Needs you: 1 gate · 2 questions", "Ran <1 min", "Folder /src/gated", "Kits default, review", "CLI claude"],
    waits: ["Needs you: 1 gate · 2 questions"],
  });
  expect(await tip(/^stuck/)).toEqual({
    lines: ["stuck", "session loop not running", "Ran <1 min", "Folder /src/stuck", "Kits default", "CLI kilo", "Open it and press Stop session, then Resume"],
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
      if (path === "/api/repos-folder") {
        return Promise.resolve(new Response(JSON.stringify({ path: "/Users/ann/workspace", made: false })));
      }
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
  // Live is the system panel's button (SystemPanel.test.tsx).
  const link = await within(bar).findByRole("button", { name: "System" });
  expect(link.textContent).toBe("live");
  expect(link.getAttribute("title")).toBeNull(); // the UI's tooltip, not the browser's
  fireEvent.focus(link);
  expect(screen.getByRole("tooltip").textContent).toBe(`The LADO server this page talks to: ${window.location.host}`);
  fireEvent.blur(link);
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  stream().fail(false);
  act(() => vi.advanceTimersByTime(LOST_AFTER_MS));
  vi.useRealTimers();
  expect(within(bar).getByRole("status").textContent).toBe("reconnecting…");
});

// The session's head in the top bar (docs/design/ui.md, Session head; feature/session-head-topbar)

const bar = () => screen.getByRole("banner");
const barHeadings = () => [...bar().querySelectorAll("h1")].map((one) => one.textContent);
const headTitle = () => bar().querySelector("h1 button") as HTMLElement;
const details = () => screen.getByRole("dialog", { name: "Session details" });
const rename = () => {
  fireEvent.click(headTitle());
  fireEvent.click(within(details()).getByRole("button", { name: "Rename" }));
};

test("a session's head is the top bar: its dot with no stop, its title, Stop and the link, no facts", async () => {
  open();
  const region = await screen.findByRole("region", { name: "Session lado" });
  expect(barHeadings()).toEqual(["lado"]);
  const dot = within(bar()).getByRole("img", { name: "running · idle" });
  expect(dot.classList).toContain("activity-idle");
  expect(bar().textContent).not.toMatch(/running/);
  fireEvent.focus(dot);
  expect(screen.getByRole("tooltip").textContent).toBe("running · idle");
  fireEvent.blur(dot);
  expect(dot.getAttribute("tabindex")).toBeNull();
  expect(bar().textContent).not.toContain("/src/lado");
  expect(within(bar()).queryByRole("button", { name: "Copy link" })).toBeNull();
  expect(within(bar()).queryByRole("button", { name: "Copy path" })).toBeNull();
  expect(within(bar()).getByRole("button", { name: "Stop session…" }).textContent).toBe("Stop");
  expect(bar().querySelector(".link")!.textContent).toBe("live");
  expect(region.querySelector(".session-head, h1, h2")).toBeNull();
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

// A session's mark, one rule for its row, its icon, its card and its head (LAD-108)

test.each([
  ["needs-you", { waiting: { gates: 0, questions: 1, agents: 0 } }, "needs you · 1 question"],
  ["needs-you", { agents: 3, busy: 2, waiting: { gates: 2, questions: 0, agents: 1 } }, "needs you · 2 gates · 1 agent waiting"],
  ["working", { agents: 3, busy: 2 }, "running · 2 of 3 agents working"],
  ["idle", { agents: 3 }, "running · idle"],
  ["stopped", { status: "stopped", waiting: { gates: 1, questions: 0, agents: 0 } }, "stopped"],
  ["tmux_gone", { status: "tmux_gone", waiting: { gates: 1, questions: 0, agents: 0 } }, "tmux session is gone"],
  ["loop_down", { status: "loop_down", busy: 1 }, "session loop not running"],
] as const)("a session's mark is %s, its words %j", (mark, more, words) => {
  expect(sessionMark(session("lado", more))).toEqual({ mark, words });
});

test.each([
  ["needs-you", { waiting: { gates: 0, questions: 1, agents: 0 } }, "needs you · 1 question", "dot-waiting", "Needs you", null],
  ["working", { agents: 3, busy: 2 }, "running · 2 of 3 agents working", "activity-working", "Running", "activity-working"],
  ["idle", { agents: 3 }, "running · idle", "activity-idle", "Running", "activity-idle"],
  ["stopped", { status: "stopped" }, "stopped", "session-dot-stopped", "Stopped", null],
  ["tmux_gone", { status: "tmux_gone" }, "tmux session is gone", "session-dot-tmux_gone", "Running", null],
  ["loop_down", { status: "loop_down" }, "session loop not running", "session-dot-loop_down", "Running", null],
] as const)("%s: the head's dot and the session's row show the same mark", async (_mark, more, words, look, where, rowDot) => {
  sessions = [session("lado", more)];
  open();
  await screen.findByRole("region", { name: "Session lado" });
  const dot = within(bar()).getByRole("img", { name: words });
  expect(dot.classList).toContain("session-dot");
  expect(dot.classList).toContain(look);
  fireEvent.focus(dot);
  expect(screen.getByRole("tooltip").textContent).toBe(words);
  fireEvent.blur(dot);
  const link = within(group(where)).getByRole("link", { name: /^lado/ });
  const mark = within(link).queryByRole("img");
  expect(mark?.className ?? null).toEqual(rowDot && expect.stringContaining(rowDot));
});

test("a question waits while the agents idle: the head's dot is the orange diamond, no green dot", async () => {
  sessions = [session("lado", { agents: 3, waiting: { gates: 0, questions: 1, agents: 0 } })];
  open();
  await screen.findByRole("region", { name: "Session lado" });
  const dot = within(bar()).getByRole("img", { name: "needs you · 1 question" });
  expect([...dot.classList]).toEqual(["session-dot", "dot", "dot-waiting"]);
  expect(bar().querySelector(".activity-working, .activity-idle, .session-dot-running")).toBeNull();
});

test.each([
  ["tmux_gone", "tmux session is gone"],
  ["loop_down", "session loop not running"],
] as const)("%s while a gate waits: the row is in Needs you and the icon says so, the head's dot is the trouble", async (status, words) => {
  sessions = [session("lado", { status, waiting: { gates: 1, questions: 0, agents: 0 } })];
  open();
  await screen.findByRole("region", { name: "Session lado" });
  const dot = within(bar()).getByRole("img", { name: words });
  expect(dot.classList).toContain(`session-dot-${status}`);
  expect(within(group("Needs you")).getByRole("link", { name: /^lado/ })).toBeTruthy();
  cleanup();
  collapsed();
  open();
  await screen.findByRole("region", { name: "Session lado" });
  expect(within(strip()!).getByRole("link", { name: /^lado/ }).getAttribute("aria-label")).toBe("lado, needs you");
  expect(within(bar()).getByRole("img", { name: words }).classList).toContain(`session-dot-${status}`);
});

test("the head's dot follows the session's work, as its row does, with no reload", async () => {
  sessions = [session("lado", { agents: 2, busy: 1 })];
  open();
  await screen.findByRole("region", { name: "Session lado" });
  expect(within(bar()).getByRole("img", { name: "running · 1 of 2 agents working" }).classList).toContain("activity-working");
  const calm = session("lado", { agents: 2, busy: 0 });
  stream().send("change", { kind: "sessions", session: "lado", key: "", op: "update", item: calm }, "11");
  expect(within(bar()).getByRole("img", { name: "running · idle" }).classList).toContain("activity-idle");
  expect(within(row("lado")).getByRole("img", { name: "idle" }).className).toContain("activity-idle");
  const asked = session("lado", { agents: 2, waiting: { gates: 0, questions: 1, agents: 0 } });
  stream().send("change", { kind: "sessions", session: "lado", key: "", op: "update", item: asked }, "12");
  expect(within(bar()).getByRole("img", { name: "needs you · 1 question" }).classList).toContain("dot-waiting");
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
  expect(screen.queryByRole("link", { name: "Skip to chat" })).toBeNull();
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

// The session title (docs/design/ui.md, Session title): the label over the name.

const TITLE = "Rename sessions (LAD-66)";
type Put = { path: string; body: unknown };

// The server's PUT of a title: the answer is the session with the title as stored.
function titles(): Put[] {
  const puts: Put[] = [];
  const base = fetch;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      if (path === "/api/limits") return new Response(JSON.stringify({ max_title: 80 }));
      if (init?.method === "PUT") {
        const body = JSON.parse(String(init.body));
        puts.push({ path, body });
        const name = decodeURIComponent(path.split("/")[3]);
        const one = sessions.find((s) => s.name === name)!;
        return new Response(JSON.stringify({ ...one, title: body.title }));
      }
      return base(path, init);
    }),
  );
  return puts;
}

test("a titled row shows its title, its grey line starting with its name; an untitled row is as before", async () => {
  sessions = [session("lado-2", { title: TITLE, agents: 3 }), session("lado-3")];
  open("/sessions");
  const titled = await within(list()).findByRole("link", { name: new RegExp(`^${TITLE.replace(/[()]/g, "\\$&")}`) });
  expect(titled.querySelector(".session-name")!.textContent).toBe(TITLE);
  expect(about(titled)).toMatch(/^lado-2 · ran /);
  expect(titled.getAttribute("href")).toBe("/sessions/lado-2");
  const plain = row("lado-3");
  expect(plain.querySelector(".session-name")!.textContent).toBe("lado-3");
  expect(about(plain)).toMatch(/^ran /);
});

test("the grey line of a titled row that needs the human starts with its name too", async () => {
  sessions = [session("lado-2", { title: TITLE, waiting: { gates: 1, questions: 0, agents: 0 } })];
  open("/sessions");
  const titled = await within(await within(list()).findByRole("region", { name: "Needs you" })).findByRole("link", { name: /^Rename/ });
  expect(about(titled)).toBe("lado-2 · 1 gate");
});

test("the search finds a session by its title or its name", async () => {
  sessions = [session("lado-2", { title: TITLE }), session("crm")];
  open("/sessions");
  await within(list()).findByRole("link", { name: /^crm/ });
  const search = screen.getByRole("searchbox", { name: "Find a session" });
  for (const typed of ["rename", "LADO-2", "lad-66"]) {
    fireEvent.change(search, { target: { value: typed } });
    expect(names(group("Running"))).toEqual([TITLE]);
  }
  fireEvent.change(search, { target: { value: "crm" } });
  expect(names(group("Running"))).toEqual(["crm"]);
});

test("a titled row's card leads with its title, then its name", async () => {
  sessions = [session("lado-2", { title: TITLE })];
  open("/sessions");
  const link = await within(list()).findByRole("link", { name: /^Rename/ });
  fireEvent.focus(link);
  const shown = screen.getByRole("tooltip");
  expect(tipLines(shown).slice(0, 2)).toEqual([`${TITLE} lado-2`, "idle"]);
  expect(nameFirst(shown)).toBe(TITLE);
});

test("a card names the project by its title, by its id without one, and has no empty label", async () => {
  sessions = [
    session("titled", { project: "crm-3", project_title: "CRM 3", permission_mode: "auto" }),
    session("plain", { project: "shop-api", project_title: null }),
    session("alone"),
  ];
  open("/sessions");
  await within(list()).findByRole("link", { name: /^alone/ });
  expect(cardLines(row("titled"))).toEqual(["titled", "idle", "Project CRM 3", "Ran <1 min", "Folder /src/titled", "Kits default", "CLI claude", "Mode auto"]);
  expect(cardLines(row("plain"))[2]).toBe("Project shop-api");
  expect(cardLines(row("alone"))).toEqual(["alone", "idle", "Ran <1 min", "Folder /src/alone", "Kits default", "CLI claude"]);
});

test("a project's new title in the feed shows in the open card", async () => {
  sessions = [session("crm", { project: "crm-3", project_title: "CRM 3" })];
  open("/sessions");
  const link = await within(list()).findByRole("link", { name: /^crm/ });
  fireEvent.focus(link);
  expect(tipLines(screen.getByRole("tooltip"))[2]).toBe("Project CRM 3");
  const renamed = session("crm", { project: "crm-3", project_title: "CRM" });
  stream().send("change", { kind: "sessions", session: "crm", key: "", op: "update", item: renamed }, "11");
  expect(tipLines(screen.getByRole("tooltip"))[2]).toBe("Project CRM");
});

test("a card shows six kits and how many more, and CLI stays", async () => {
  const kits = ["a", "b", "c", "d", "e", "f", "g", "h", "i"];
  sessions = [session("many", { kits }), session("six", { kits: kits.slice(0, 6) })];
  open("/sessions");
  await within(list()).findByRole("link", { name: /^many/ });
  expect(cardLines(row("many")).slice(4)).toEqual(["Kits a, b, c, d, e, f +3 more", "CLI claude"]);
  expect(cardLines(row("six")).slice(4)).toEqual(["Kits a, b, c, d, e, f", "CLI claude"]);
});

test("a card says how to go on from a stopped or broken session, a running one's says nothing", async () => {
  sessions = [
    session("calm"),
    session("gone", { status: "tmux_gone" }),
    session("down", { status: "loop_down" }),
    session("old", { status: "stopped", agents: 0 }),
  ];
  localStorage.setItem("lado.sessionGroups", JSON.stringify({ stopped: "open" }));
  open("/sessions");
  await within(list()).findByRole("link", { name: /^old/ });
  const last = (name: string) => cardLines(row(name)).at(-1);
  expect(last("calm")).toBe("CLI claude");
  expect(last("gone")).toBe("Open it and press Resume");
  expect(last("old")).toBe("Open it and press Resume");
  expect(last("down")).toBe("Open it and press Stop session, then Resume");
});

test("a titled session's icon in the strip takes its letters and its name from the title, its card too", async () => {
  collapsed();
  sessions = [session("lado-2", { title: TITLE }), session("lado")];
  open("/sessions");
  await within(strip()!).findByRole("link", { name: "lado, idle" });
  expect(icons().map((icon) => icon.getAttribute("aria-label"))).toEqual([`${TITLE}, idle`, "lado, idle"]);
  expect(icons().map((icon) => icon.textContent)).toEqual(["RS", "LA"]);
  fireEvent.focus(icons()[0]);
  expect(tipLines(screen.getByRole("tooltip"))[0]).toBe(`${TITLE} lado-2`);
});

test("a titled session's head: the title alone, its name in Details; the tab's title is the title", async () => {
  sessions = [session("lado-2", { title: TITLE })];
  open("/sessions/lado-2");
  await screen.findByRole("region", { name: "Session lado-2" });
  expect(barHeadings()).toEqual([TITLE]);
  expect(bar().textContent).not.toContain("lado-2");
  expect(document.title).toBe(`${TITLE} · LADO`);
  fireEvent.click(headTitle());
  expect(details().querySelector(".session-details-state")!.textContent).toContain("id lado-2");
});

test("the head's title is a button in the h1 that opens Details; a double click opens no field", async () => {
  open();
  await screen.findByRole("region", { name: "Session lado" });
  expect(barHeadings()).toEqual(["lado"]);
  const title = headTitle();
  expect(title.closest("h1")).toBeTruthy();
  expect(title.getAttribute("aria-haspopup")).toBe("dialog");
  expect(title.getAttribute("aria-expanded")).toBe("false");
  expect(within(bar()).queryByRole("button", { name: "Rename session" })).toBeNull();
  fireEvent.doubleClick(title);
  expect(within(bar()).queryByRole("textbox", { name: "Session title" })).toBeNull();
  fireEvent.click(title);
  expect(title.getAttribute("aria-expanded")).toBe("true");
  expect(document.activeElement).toBe(within(details()).getByRole("button", { name: "Copy path" }));
});

test("Esc and a second click close Details with the focus on the title", async () => {
  open();
  await screen.findByRole("region", { name: "Session lado" });
  fireEvent.click(headTitle());
  fireEvent.keyDown(document.activeElement!, { key: "Escape" });
  expect(screen.queryByRole("dialog", { name: "Session details" })).toBeNull();
  expect(document.activeElement).toBe(headTitle());
  fireEvent.click(headTitle());
  fireEvent.mouseDown(headTitle());
  fireEvent.click(headTitle());
  expect(screen.queryByRole("dialog", { name: "Session details" })).toBeNull();
  expect(document.activeElement).toBe(headTitle());
});

test("a press on an empty place closes Details and the focus goes to the title; on a field it stays there", async () => {
  open();
  await screen.findByRole("region", { name: "Session lado" });
  fireEvent.click(headTitle());
  fireEvent.mouseDown(document.body);
  expect(screen.queryByRole("dialog", { name: "Session details" })).toBeNull();
  await waitFor(() => expect(document.activeElement).toBe(headTitle()));
  fireEvent.click(headTitle());
  const composer = await screen.findByRole("textbox", { name: "Write to the supervisor…" });
  fireEvent.mouseDown(composer);
  composer.focus(); // the browser's own, after the press
  expect(screen.queryByRole("dialog", { name: "Session details" })).toBeNull();
  await act(async () => {
    await new Promise((done) => setTimeout(done));
  });
  expect(document.activeElement).toBe(composer);
});

test("Rename in Details edits the title in the head: Enter saves, the head and the row show it, the focus is on the title", async () => {
  const puts = titles();
  sessions = [session("lado")];
  open();
  await screen.findByRole("region", { name: "Session lado" });
  rename();
  expect(screen.queryByRole("dialog", { name: "Session details" })).toBeNull();
  const field = within(bar()).getByRole("textbox", { name: "Session title" }) as HTMLInputElement;
  expect(field.value).toBe("");
  expect(field.placeholder).toBe("lado");
  expect(within(bar()).getByText("Tab takes the name · Enter to save · Esc to cancel")).toBeTruthy();
  fireEvent.change(field, { target: { value: "Review" } });
  expect(within(bar()).getByText("Enter to save · Esc to cancel · empty shows the name")).toBeTruthy();
  fireEvent.keyDown(field, { key: "Enter" });
  await waitFor(() => expect(barHeadings()).toEqual(["Review"]));
  expect(puts).toEqual([{ path: "/api/sessions/lado/title", body: { title: "Review" } }]);
  expect(document.activeElement).toBe(headTitle());
  expect(within(list()).getByRole("link", { name: /^Review/ })).toBeTruthy();
  expect(document.title).toBe("Review · LADO");
});

test("Esc in the head's field sends nothing, the focus on the title", async () => {
  const puts = titles();
  sessions = [session("lado", { title: "Old" })];
  open();
  await screen.findByRole("region", { name: "Session lado" });
  rename();
  const field = within(bar()).getByRole("textbox", { name: "Session title" });
  fireEvent.change(field, { target: { value: "x" } });
  fireEvent.keyDown(field, { key: "Escape" });
  expect(barHeadings()).toEqual(["Old"]);
  expect(document.activeElement).toBe(headTitle());
  await act(async () => {});
  expect(puts).toEqual([]);
});

const rowMenu = async (name: string) => {
  const item = (await within(list()).findByRole("button", { name: `Actions for ${name}` })).closest("li") as HTMLElement;
  fireEvent.click(within(item).getByRole("button", { name: `Actions for ${name}` }));
  return { item, menu: await screen.findByRole("menu", { name }) };
};

test("Rename… is the row menu's first item and edits the title in the row; Esc returns the focus to ⋯", async () => {
  const puts = titles();
  sessions = [session("lado-2", { title: TITLE })];
  open("/sessions");
  const { item, menu } = await rowMenu("lado-2");
  expect(within(menu).getAllByRole("menuitem").map((one) => one.textContent)).toEqual(["Rename…", "Copy link", "Open in new tab"]);
  fireEvent.click(within(menu).getByRole("menuitem", { name: "Rename…" }));
  expect(screen.queryByRole("menu")).toBeNull();
  const field = within(item).getByRole("textbox", { name: "Session title" }) as HTMLInputElement;
  expect(field.value).toBe(TITLE);
  expect(within(item).queryByRole("link")).toBeNull(); // no link while it edits
  expect(within(item).getByText("lado-2 · Enter to save · Esc to cancel")).toBeTruthy();
  fireEvent.change(field, { target: { value: "x" } });
  fireEvent.keyDown(field, { key: "Escape" });
  expect(item.querySelector(".session-name")!.textContent).toBe(TITLE);
  expect(document.activeElement).toBe(within(item).getByRole("button", { name: "Actions for lado-2" }));
  await act(async () => {});
  expect(puts).toEqual([]);
});

test("Rename… with an empty field clears the title: the name shows again", async () => {
  const puts = titles();
  sessions = [session("lado-2", { title: TITLE })];
  open("/sessions");
  const { item, menu } = await rowMenu("lado-2");
  fireEvent.click(within(menu).getByRole("menuitem", { name: "Rename…" }));
  const field = within(item).getByRole("textbox", { name: "Session title" });
  fireEvent.change(field, { target: { value: "" } });
  fireEvent.keyDown(field, { key: "Enter" });
  await waitFor(() => expect(item.querySelector(".session-name")?.textContent).toBe("lado-2"));
  expect(puts).toEqual([{ path: "/api/sessions/lado-2/title", body: { title: null } }]);
  expect(document.activeElement).toBe(within(item).getByRole("button", { name: "Actions for lado-2" }));
});

test("a title from the feed while the field is open keeps the typed text; after Esc the row shows the stored title", async () => {
  titles();
  sessions = [session("lado-2")];
  open("/sessions");
  const { item, menu } = await rowMenu("lado-2");
  fireEvent.click(within(menu).getByRole("menuitem", { name: "Rename…" }));
  const field = within(item).getByRole("textbox", { name: "Session title" }) as HTMLInputElement;
  fireEvent.change(field, { target: { value: "Mine" } });
  const elsewhere = session("lado-2", { title: "Theirs" });
  stream().send("change", { kind: "sessions", session: "lado-2", key: "", op: "update", item: elsewhere }, "11");
  expect(field.value).toBe("Mine");
  fireEvent.keyDown(field, { key: "Escape" });
  expect(item.querySelector(".session-name")!.textContent).toBe("Theirs");
});

test("a title set elsewhere shows in the open page from the feed", async () => {
  sessions = [session("lado")];
  open();
  await screen.findByRole("region", { name: "Session lado" });
  stream().send("change", { kind: "sessions", session: "lado", key: "", op: "update", item: session("lado", { title: "Review" }) }, "11");
  expect(barHeadings()).toEqual(["Review"]);
  expect(within(list()).getByRole("link", { name: /^Review/ })).toBeTruthy();
});

test("the head's field closes when the page goes to another session: its text is never saved there", async () => {
  const puts = titles();
  sessions = [session("lado"), session("other")];
  open();
  await screen.findByRole("region", { name: "Session lado" });
  rename();
  const field = within(bar()).getByRole("textbox", { name: "Session title" });
  fireEvent.change(field, { target: { value: "Mine" } });
  fireEvent.click(within(list()).getByRole("link", { name: /^other/ })); // no blur, as "Back" goes
  await screen.findByRole("region", { name: "Session other" });
  expect(within(bar()).queryByRole("textbox", { name: "Session title" })).toBeNull();
  expect(barHeadings()).toEqual(["other"]);
  fireEvent.blur(field);
  fireEvent.keyDown(field, { key: "Enter" });
  await act(async () => {});
  expect(puts).toEqual([]);
});

test("an icon's letters from a title that starts with an emoji are whole characters", async () => {
  collapsed();
  sessions = [session("lado", { title: "🚀 Релиз" }), session("x", { title: "𝒜𝒷" })];
  open("/sessions");
  await within(strip()!).findByRole("link", { name: "🚀 Релиз, idle" });
  expect(icons().map((icon) => icon.textContent)).toEqual(["🚀Р", "𝒜𝒷"]);
});

// A stopped session's terminals

const terminals = () => screen.getByRole("complementary", { name: "Terminals" });
const terminalsFolded = () => within(terminals()).queryByRole("button", { name: "Show the terminals" }) !== null;
const sessionNow = (item: SessionInfo, id: string) => {
  act(() => stream().send("change", { kind: "sessions", session: item.name, key: "", op: "update", item }, id));
};
const STOPPED: Partial<SessionInfo> = { status: "stopped", agents: 0 };

test("a stopped session's terminals are folded whatever is stored, and the stored choice comes back with Resume", async () => {
  localStorage.setItem("lado.terminals", JSON.stringify({ width: 500, collapsed: false }));
  localStorage.setItem("lado.lastColumn", "list");
  sessions = [session("lado", STOPPED)];
  open();
  await screen.findByRole("region", { name: "Session lado" });
  expect(terminalsFolded()).toBe(true);
  sessionNow(session("lado"), "11");
  expect(terminalsFolded()).toBe(false);
  expect(localStorage.getItem("lado.terminals")).toBe(JSON.stringify({ width: 500, collapsed: false }));
  expect(localStorage.getItem("lado.lastColumn")).toBe("list");
});

test("what the human does to a stopped session's terminals stores nothing and ends with Resume", async () => {
  localStorage.setItem("lado.terminals", JSON.stringify({ collapsed: true }));
  localStorage.setItem("lado.lastColumn", "list");
  sessions = [session("lado", STOPPED)];
  open();
  await screen.findByRole("region", { name: "Session lado" });
  fireEvent.click(within(terminals()).getByRole("button", { name: "Show the terminals" }));
  expect(terminalsFolded()).toBe(false);
  fireEvent.click(within(terminals()).getByRole("button", { name: "Collapse terminals" }));
  expect(terminalsFolded()).toBe(true);
  fireEvent.click(within(terminals()).getByRole("button", { name: "Show the terminals" }));
  expect(localStorage.getItem("lado.terminals")).toBe(JSON.stringify({ collapsed: true }));
  expect(localStorage.getItem("lado.lastColumn")).toBe("list");
  sessionNow(session("lado"), "11");
  expect(terminalsFolded()).toBe(true);
  expect(localStorage.getItem("lado.terminals")).toBe(JSON.stringify({ collapsed: true }));
});

test("the terminals of a session that stops fold, and those opened in a stopped session fold again after another session", async () => {
  sessions = [session("lado"), session("old", STOPPED)];
  localStorage.setItem("lado.sessionGroups", JSON.stringify({ stopped: "open" }));
  open();
  await screen.findByRole("region", { name: "Session lado" });
  expect(terminalsFolded()).toBe(false);
  sessionNow(session("lado", STOPPED), "11");
  expect(terminalsFolded()).toBe(true);
  fireEvent.click(within(terminals()).getByRole("button", { name: "Show the terminals" }));
  expect(terminalsFolded()).toBe(false);
  fireEvent.click(within(list()).getByRole("link", { name: /old/ }));
  await screen.findByRole("region", { name: "Session old" });
  expect(terminalsFolded()).toBe(true);
});

// The tabs' bar

test("a tab is kept clear of the room at each end, and a tab in the clear does not move the row", () => {
  const view = { left: 100, width: 300 };
  expect(tabScroll(view, { left: 200, width: 80 }, 56)).toBe(100); // stands in the clear
  expect(tabScroll(view, { left: 350, width: 80 }, 56)).toBe(186); // under the right end
  expect(tabScroll(view, { left: 120, width: 80 }, 56)).toBe(64); // under the left end
  expect(tabScroll({ left: 100, width: 150 }, { left: 300, width: 80 }, 56)).toBe(244); // too wide for the room left: its start
});

test("on Activity the bar holds both forms of the choice, which say the same", async () => {
  open();
  const radios = await screen.findByRole("radiogroup", { name: "Messages between agents" });
  const icon = document.querySelector<HTMLElement>(".session-tabs .between-toggle")!;
  expect(icon.getAttribute("aria-label")).toBe("Messages between agents");
  expect(icon.getAttribute("aria-pressed")).toBe("false");
  fireEvent.click(icon);
  expect(icon.getAttribute("aria-pressed")).toBe("true");
  expect(within(radios).getByRole("radio", { name: "All" }).getAttribute("aria-checked")).toBe("true");
  fireEvent.click(within(radios).getByRole("radio", { name: "Yours" }));
  expect(icon.getAttribute("aria-pressed")).toBe("false");
  fireEvent.mouseEnter(icon);
  expect((await screen.findByRole("tooltip")).textContent).toBe(
    "Messages between agents: hiddenClick to also show what agents write to each other.",
  );
});
