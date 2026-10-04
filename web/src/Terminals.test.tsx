import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { AgentInfo, SessionInfo } from "./api";
import { App } from "./App";
import { AGENT_REST, FakeEventSource, FakeResizeObserver, FakeSocket, FakeXterm, stream, stubDialogs } from "./fakes";
import { RETRY_MS } from "./terminalLink";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const NONE = { gates: 0, questions: 0, agents: 0 };
const SESSION: SessionInfo = {
  name: "lado",
  repo: "/src/lado",
  status: "running",
  agents: 2,
  waiting: NONE,
  kits: ["default"],
  provider: "claude",
  permission_mode: null,
  without: [],
};
const AGENTS: AgentInfo[] = [
  { name: "supervisor", role: "supervisor", provider: "claude", status: "idle", run: null, task: null, waiting_reason: null, ...AGENT_REST },
  { name: "w1", role: "developer", provider: "kilo", status: "busy", run: null, task: "Build it", waiting_reason: null, ...AGENT_REST },
];
const BASE = "ws://localhost:3000/api/sessions/lado/agents";

let history: { text: string; alternate: boolean } = { text: "line 1\nline 2", alternate: false };
let narrow = false;

beforeEach(() => {
  localStorage.clear();
  FakeSocket.all = [];
  FakeXterm.all = [];
  FakeEventSource.all = [];
  FakeEventSource.autoStart = true;
  history = { text: "line 1\nline 2", alternate: false };
  narrow = false;
  stubDialogs();
  vi.stubGlobal("WebSocket", FakeSocket);
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: narrow && query.includes("max-width"),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      const body = path.endsWith("/agents")
        ? AGENTS
        : path.includes("/history")
          ? history
          : path === "/api/sessions"
            ? [SESSION]
            : [];
      return new Response(JSON.stringify(body), { status: 200 });
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const panel = () => screen.getByRole("complementary", { name: "Terminals" });

async function open(path = "/sessions/lado") {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
  await screen.findByRole("region", { name: "Session lado" });
}

const team = () => screen.findByRole("group", { name: "Team" });

// The chip of an agent in the team above the chat: it opens or selects its terminal.
async function chip(agent: string) {
  return within(await team()).findByRole("button", { name: new RegExp(`^${agent},`) });
}

async function openTerminal(agent: string) {
  fireEvent.click(await chip(agent));
  return within(panel()).getByRole("tabpanel", { name: agent });
}

const socketOf = (agent: string, mode: string) =>
  FakeSocket.all.filter((socket) => socket.url === `${BASE}/${agent}/terminal?mode=${mode}`);

const tabNames = () => within(panel()).getAllByRole("tab").map((tab) => tab.textContent);

// A tab is named after its agent and its status, as the agent's chip.
const tab = (agent: string) => within(panel()).getByRole("tab", { name: new RegExp(`^${agent},`) });

function agentChange(item: AgentInfo | null, key = item?.name ?? "") {
  stream().send("change", { kind: "agents", session: "lado", key, op: item ? "update" : "delete", item });
}

// The panel: always there, the supervisor's terminal pinned in it

test("the panel shows the supervisor's terminal from the start, before any click, and it cannot be closed", async () => {
  await open();
  expect(tab("supervisor").getAttribute("aria-selected")).toBe("true");
  expect(within(panel()).getByRole("tabpanel", { name: "supervisor" })).toBeTruthy();
  expect(socketOf("supervisor", "view")).toHaveLength(1);
  expect(within(panel()).queryByRole("button", { name: "Close supervisor's terminal" })).toBeNull();
  expect((await chip("supervisor")).getAttribute("aria-pressed")).toBe("true");
});

test("a chip opens its agent's terminal on the right, to view", async () => {
  await open();
  const view = await openTerminal("w1");
  expect(tab("w1").getAttribute("aria-selected")).toBe("true");
  expect(socketOf("w1", "view")).toHaveLength(1);
  expect(socketOf("w1", "control")).toHaveLength(0);
  act(() => socketOf("w1", "view")[0].open());
  expect(within(view).getByRole("status").textContent).toContain("live");
  act(() => FakeXterm.all[1].type("x"));
  expect(socketOf("w1", "view")[0].sent).toEqual([]); // in view nothing typed goes out
  expect(within(view).getByRole("button", { name: "Take control" })).toBeTruthy();
});

test("the chip of the shown terminal is marked; another chip adds a tab and keeps the first socket", async () => {
  await open();
  await openTerminal("w1");
  expect((await chip("w1")).getAttribute("aria-pressed")).toBe("true");
  expect((await chip("supervisor")).getAttribute("aria-pressed")).toBe("false");
  expect(tabNames()).toEqual(["supervisor", "w1"]);
  await openTerminal("supervisor");
  expect((await chip("w1")).getAttribute("aria-pressed")).toBe("false");
  const [w1] = socketOf("w1", "view");
  expect(w1.closed).toBe(false); // hidden, not closed
  fireEvent.click(await chip("w1")); // selects the tab it has: no new socket
  expect(socketOf("w1", "view")).toHaveLength(1);
  expect(tab("w1").getAttribute("aria-selected")).toBe("true");
});

test("the panel keeps its terminals while the session's tabs change", async () => {
  await open();
  await openTerminal("w1");
  fireEvent.click(screen.getByRole("link", { name: "Flows" }));
  expect(tabNames()).toEqual(["supervisor", "w1"]);
  fireEvent.click(screen.getByRole("link", { name: "Activity" }));
  expect(FakeSocket.all).toHaveLength(2); // the same terminals, no new ones
});

test("× closes a tab and its socket; with the last other tab closed the supervisor's is shown", async () => {
  await open();
  await openTerminal("w1");
  fireEvent.click(within(panel()).getByRole("button", { name: "Close w1's terminal" }));
  expect(socketOf("w1", "view")[0].closed).toBe(true);
  expect(tabNames()).toEqual(["supervisor"]);
  expect(tab("supervisor").getAttribute("aria-selected")).toBe("true");
  expect(socketOf("supervisor", "view")[0].closed).toBe(false);
});

test("the Agents tab opens an agent's terminal in the same panel", async () => {
  await open("/sessions/lado/agents/w1");
  const agent = await screen.findByRole("region", { name: "Agent w1" });
  fireEvent.click(within(agent).getByRole("button", { name: "Open terminal" }));
  expect(tab("w1").getAttribute("aria-selected")).toBe("true");
  expect(socketOf("w1", "view")).toHaveLength(1);
});

// Where the page is now: the address without the host.
function Where() {
  const { pathname, search } = useLocation();
  return <output aria-label="Address">{pathname + search}</output>;
}

async function openAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
      <Where />
    </MemoryRouter>,
  );
  await screen.findByRole("region", { name: "Session lado" });
}

const address = () => screen.getByRole("status", { name: "Address" }).textContent;

test("?terminal= in the address opens that agent's terminal, also in a collapsed panel, and leaves the address", async () => {
  localStorage.setItem("lado.terminals", JSON.stringify({ width: 480, collapsed: true }));
  await openAt("/sessions/lado/activity?terminal=w1");
  await waitFor(() => expect(tab("w1").getAttribute("aria-selected")).toBe("true"));
  expect(socketOf("w1", "view")).toHaveLength(1);
  await waitFor(() => expect(address()).toBe("/sessions/lado/activity"));
});

test("?terminal= naming no agent of the session says so", async () => {
  await openAt("/sessions/lado/activity?terminal=w9");
  expect(await screen.findByText("w9 is not in this session")).toBeTruthy();
  await waitFor(() => expect(address()).toBe("/sessions/lado/activity"));
  expect(tabNames()).toEqual(["supervisor"]);
});

// Collapsed to a strip

const collapse = () => fireEvent.click(within(panel()).getByRole("button", { name: "Collapse terminals" }));
const expandPanel = () => fireEvent.click(within(panel()).getByRole("button", { name: "Terminals" }));

test("Collapse terminals leaves a strip whose Terminals button opens the panel again; remembered", async () => {
  await open();
  collapse();
  expect(panel().classList.contains("collapsed")).toBe(true);
  expect(within(panel()).queryByRole("tab")).toBeNull();
  expect(JSON.parse(localStorage.getItem("lado.terminals")!)).toEqual({ width: 480, collapsed: true });
  expect((await chip("supervisor")).getAttribute("aria-pressed")).toBe("false"); // nothing is shown
  cleanup();

  await open();
  expect(panel().classList.contains("collapsed")).toBe(true);
  expandPanel();
  expect(panel().classList.contains("collapsed")).toBe(false);
  expect(tab("supervisor").getAttribute("aria-selected")).toBe("true");
  expect(JSON.parse(localStorage.getItem("lado.terminals")!).collapsed).toBe(false);
});

test("a panel collapsed when the page opens opens no socket until it is opened", async () => {
  localStorage.setItem("lado.terminals", JSON.stringify({ width: 480, collapsed: true }));
  await open();
  await team();
  expect(FakeSocket.all).toHaveLength(0);
  expandPanel();
  expect(socketOf("supervisor", "view")).toHaveLength(1);
});

test("on a narrow window the panel starts collapsed", async () => {
  narrow = true;
  await open();
  await team();
  expect(panel().classList.contains("collapsed")).toBe(true);
  expect(FakeSocket.all).toHaveLength(0);
});

test("a chip opens a collapsed panel on its agent's terminal", async () => {
  await open();
  collapse();
  await openTerminal("w1");
  expect(panel().classList.contains("collapsed")).toBe(false);
  expect(tab("w1").getAttribute("aria-selected")).toBe("true");
  expect((await chip("w1")).getAttribute("aria-pressed")).toBe("true");
});

test("collapsing the panel keeps its sockets, and in control tells the server no new size", async () => {
  vi.stubGlobal("ResizeObserver", FakeResizeObserver);
  FakeResizeObserver.all = [];
  localStorage.setItem("lado.askControl", "never");
  await open();
  const view = within(panel()).getByRole("tabpanel", { name: "supervisor" });
  fireEvent.click(within(view).getByRole("button", { name: "Take control" }));
  const [control] = socketOf("supervisor", "control");
  act(() => control.open());
  expect(control.frames).toEqual([{ type: "resize", cols: 120, rows: 30 }]);
  collapse();
  FakeResizeObserver.resize(() => 0); // the strip: its terminal has no room
  expect(control.frames).toEqual([{ type: "resize", cols: 120, rows: 30 }]);
  expect(control.closed).toBe(false);
  expandPanel();
  expect(control.frames).toHaveLength(2); // open again: its size goes out
});

// A terminal closed for good: Reconnect, or by itself when its agent comes back

test("a terminal closed for good has Reconnect, which opens a new socket", async () => {
  await open();
  const view = within(panel()).getByRole("tabpanel", { name: "supervisor" });
  act(() => socketOf("supervisor", "view")[0].end(4404, 'session "lado" is stopped'));
  expect(within(view).getByRole("status").textContent).toContain("is stopped");
  fireEvent.click(within(view).getByRole("button", { name: "Reconnect" }));
  expect(socketOf("supervisor", "view")).toHaveLength(2);
  act(() => socketOf("supervisor", "view")[1].open());
  expect(within(view).getByRole("status").textContent).toBe("live");
  expect(within(view).queryByRole("button", { name: "Reconnect" })).toBeNull();
});

test("a terminal closed for good opens again when its agent comes back, also with the team not shown", async () => {
  await open("/sessions/lado/flows"); // no team on this tab: the panel follows the agents itself
  await waitFor(() => expect(socketOf("supervisor", "view")).toHaveLength(1));
  act(() => socketOf("supervisor", "view")[0].end(4404, 'session "lado" is stopped'));
  agentChange(null, "supervisor"); // stopped: its agents are gone
  expect(socketOf("supervisor", "view")).toHaveLength(1);
  agentChange({ ...AGENTS[0], status: "starting" }); // resumed
  await waitFor(() => expect(socketOf("supervisor", "view")).toHaveLength(2));
  // Still no terminal: it stays closed until its agent changes again, not in a loop.
  act(() => socketOf("supervisor", "view")[1].end(4404, 'agent "supervisor" has no terminal'));
  expect(socketOf("supervisor", "view")).toHaveLength(2);
  agentChange({ ...AGENTS[0], status: "idle" });
  await waitFor(() => expect(socketOf("supervisor", "view")).toHaveLength(3));
});

// Take control

test("Take control asks in a modal dialog first; Cancel and Esc keep the terminal to view", async () => {
  await open();
  const view = within(panel()).getByRole("tabpanel", { name: "supervisor" });
  const take = within(view).getByRole("button", { name: "Take control" });
  expect(take.getAttribute("title")).toMatch(/goes straight to supervisor/);
  fireEvent.click(take);
  const ask = screen.getByRole("dialog", { name: "Take control of supervisor" });
  expect(ask.tagName).toBe("DIALOG");
  expect(ask.hasAttribute("open")).toBe(true); // shown with showModal
  expect(ask.textContent).toMatch(/goes straight to supervisor/);
  fireEvent.click(within(ask).getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("dialog")).toBeNull();

  fireEvent.click(take);
  fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(socketOf("supervisor", "control")).toHaveLength(0);
  expect(localStorage.getItem("lado.askControl")).toBeNull();
});

test("Don't ask again: Take control takes it at once, for every agent and after a reload", async () => {
  await open();
  fireEvent.click(within(panel()).getByRole("button", { name: "Take control" }));
  const ask = screen.getByRole("dialog", { name: "Take control of supervisor" });
  fireEvent.click(within(ask).getByRole("checkbox", { name: "Don't ask again" }));
  fireEvent.click(within(ask).getByRole("button", { name: "Take control" }));
  expect(socketOf("supervisor", "control")).toHaveLength(1);
  cleanup();

  await open();
  const view = await openTerminal("w1");
  fireEvent.click(within(view).getByRole("button", { name: "Take control" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(socketOf("w1", "control")).toHaveLength(1);
});

test("without browser storage Take control asks every time", async () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("denied");
  });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("denied");
  });
  await open();
  const view = within(panel()).getByRole("tabpanel", { name: "supervisor" });
  fireEvent.click(within(view).getByRole("button", { name: "Take control" }));
  const ask = screen.getByRole("dialog");
  fireEvent.click(within(ask).getByRole("checkbox", { name: "Don't ask again" }));
  fireEvent.click(within(ask).getByRole("button", { name: "Take control" }));
  fireEvent.click(within(view).getByRole("button", { name: "Release" }));
  fireEvent.click(within(view).getByRole("button", { name: "Take control" }));
  expect(screen.getByRole("dialog")).toBeTruthy();
  vi.restoreAllMocks();
});

async function w1Terminal() {
  await open();
  const view = await openTerminal("w1");
  act(() => socketOf("w1", "view")[0].open());
  return { view };
}

test("Take control opens it in control after the dialog; Release goes back to view", async () => {
  const { view } = await w1Terminal();
  fireEvent.click(within(view).getByRole("button", { name: "Take control" }));
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Take control" }));
  expect(socketOf("w1", "view")[0].closed).toBe(true);
  const [control] = socketOf("w1", "control");
  act(() => control.open());
  // In control what is typed goes out, and the terminal's size follows the panel.
  act(() => FakeXterm.all[2].type("ls\r"));
  expect(control.frames).toEqual([
    { type: "resize", cols: 120, rows: 30 },
    { type: "input", data: "ls\r" },
  ]);
  fireEvent.click(within(view).getByRole("button", { name: "Release" }));
  expect(control.closed).toBe(true);
  expect(socketOf("w1", "view")).toHaveLength(2);
});

// Expanded over the page

test("Expand terminal shows the panel over the page with the same socket; Restore terminal puts it back", async () => {
  await open();
  fireEvent.click(within(panel()).getByRole("button", { name: "Expand terminal" }));
  expect(panel().classList.contains("expanded")).toBe(true);
  fireEvent.click(within(panel()).getByRole("button", { name: "Restore terminal" }));
  expect(panel().classList.contains("expanded")).toBe(false);
  expect(FakeSocket.all).toHaveLength(1);
  expect(FakeSocket.all[0].closed).toBe(false);
});

test("Esc restores an expanded terminal to view; in control it goes to the agent", async () => {
  localStorage.setItem("lado.askControl", "never");
  await open();
  const view = within(panel()).getByRole("tabpanel", { name: "supervisor" });
  fireEvent.click(within(panel()).getByRole("button", { name: "Expand terminal" }));
  const xterm = () => FakeXterm.all[FakeXterm.all.length - 1].element!;
  fireEvent.keyDown(xterm(), { key: "Escape" });
  expect(panel().classList.contains("expanded")).toBe(false);

  fireEvent.click(within(panel()).getByRole("button", { name: "Expand terminal" }));
  fireEvent.click(within(view).getByRole("button", { name: "Take control" }));
  const [control] = socketOf("supervisor", "control");
  act(() => control.open());
  fireEvent.keyDown(xterm(), { key: "Escape" });
  act(() => FakeXterm.all[FakeXterm.all.length - 1].type("\x1b")); // xterm.js sends it on
  expect(panel().classList.contains("expanded")).toBe(true);
  expect(control.frames).toContainEqual({ type: "input", data: "\x1b" });
  expect(within(view).getByText("In control")).toBeTruthy();
  // Outside the terminal Esc restores it, in control too, which stays.
  fireEvent.keyDown(within(panel()).getByRole("button", { name: "Restore terminal" }), { key: "Escape" });
  expect(panel().classList.contains("expanded")).toBe(false);
  expect(control.closed).toBe(false);
});

// The tabs: their agents' status, many of them, their tooltip

const dotOf = (element: Element) => element.querySelector(".dot")!.className;

test("each tab shows its agent's status as a small dot that follows the agent; an agent gone is stopped", async () => {
  await open();
  await openTerminal("w1");
  expect(tab("supervisor").getAttribute("aria-label")).toBe("supervisor, idle");
  expect(dotOf(tab("supervisor"))).toBe("dot dot-small dot-idle");
  expect(dotOf(tab("w1"))).toBe("dot dot-small dot-busy");
  agentChange({ ...AGENTS[1], status: "waiting" });
  expect(dotOf(tab("w1"))).toBe("dot dot-small dot-waiting");
  expect(tab("w1").getAttribute("aria-label")).toBe("w1, waiting");
  agentChange(null, "w1");
  expect(dotOf(tab("w1"))).toBe("dot dot-small dot-stopped");
  expect(tab("w1").getAttribute("aria-label")).toBe("w1, stopped");
});

test("the collapsed strip shows a small dot per open terminal, named by its agent and status", async () => {
  await open();
  await openTerminal("w1");
  collapse();
  const dots = within(panel()).getByRole("list", { name: "Open terminals" });
  const items = within(dots).getAllByRole("listitem");
  expect(items.map((item) => item.getAttribute("title"))).toEqual(["supervisor: idle", "w1: busy"]);
  expect(items.map(dotOf)).toEqual(["dot dot-small dot-idle", "dot dot-small dot-busy"]);
});

test("a tab's name is cut to fit (its whole name in its tooltip), and the selected tab is scrolled into view", async () => {
  const scrolled = vi.fn();
  Element.prototype.scrollIntoView = scrolled;
  await open();
  await openTerminal("w1");
  expect(tab("w1").querySelector(".term-tab-name")!.textContent).toBe("w1");
  expect(tab("w1").hasAttribute("title")).toBe(false);
  expect(scrolled.mock.instances.at(-1)).toBe(tab("w1"));
  expect(scrolled).toHaveBeenLastCalledWith({ inline: "nearest", block: "nearest" });
  fireEvent.click(tab("supervisor"));
  expect(scrolled.mock.instances.at(-1)).toBe(tab("supervisor"));
  fireEvent.focus(tab("w1"));
  expect(screen.getByRole("tooltip").textContent).toBe("w1 · developer · kilo");
});

// Its width

test("the panel's width changes with its edge and is remembered", async () => {
  await open();
  const edge = within(panel()).getByRole("separator", { name: "Resize the terminals" });
  const before = Number(edge.getAttribute("aria-valuenow"));
  fireEvent.keyDown(edge, { key: "ArrowLeft" });
  const after = Number(edge.getAttribute("aria-valuenow"));
  expect(after).toBeGreaterThan(before);
  expect(panel().style.width).toBe(`${after}px`);
  expect(JSON.parse(localStorage.getItem("lado.terminals")!)).toEqual({ width: after, collapsed: false });
  cleanup();
  await open();
  expect(panel().style.width).toBe(`${after}px`);
});

test("a collapsed panel has no edge", async () => {
  await open();
  collapse();
  expect(within(panel()).queryByRole("separator")).toBeNull();
});

test("in a narrow window the panel is narrowed to leave the session its room, and its width stays remembered", async () => {
  vi.stubGlobal("ResizeObserver", FakeResizeObserver);
  FakeResizeObserver.all = [];
  localStorage.setItem("lado.terminals", JSON.stringify({ width: 600, collapsed: false }));
  await open();
  FakeResizeObserver.resize((target) => (target.classList.contains("session-page") ? 800 : 1000));
  const edge = within(panel()).getByRole("separator", { name: "Resize the terminals" });
  expect(Number(edge.getAttribute("aria-valuenow"))).toBe(800 - 360);
  expect(panel().style.width).toBe("440px");
  expect(screen.getByRole("region", { name: "Session lado" }).closest<HTMLElement>(".session-main")!.style.minWidth).toBe(
    "360px",
  );
  expect(JSON.parse(localStorage.getItem("lado.terminals")!).width).toBe(600);
  FakeResizeObserver.resize(() => 1400);
  expect(panel().style.width).toBe("600px");
});

// Inside a terminal

test("in view the wheel up opens the read-only history; Back to live closes it", async () => {
  const { view } = await w1Terminal();
  const xterm = FakeXterm.all[1];
  expect(xterm.wheel(+100)).toBe(false); // down: nothing, and never to the agent
  expect(within(view).queryByRole("region", { name: "History (read only)" })).toBeNull();
  expect(xterm.wheel(-100)).toBe(false);
  const layer = await within(view).findByRole("region", { name: "History (read only)" });
  expect(await within(layer).findByText(/line 1\s+line 2/)).toBeTruthy();
  fireEvent.click(within(layer).getByRole("button", { name: "Back to live ↓" }));
  expect(within(view).queryByRole("region", { name: "History (read only)" })).toBeNull();
});

test("the history of a full-screen agent says where it is instead of an empty layer", async () => {
  history = { text: "", alternate: true };
  const { view } = await w1Terminal();
  FakeXterm.all[1].wheel(-1);
  const layer = await within(view).findByRole("region", { name: "History (read only)" });
  expect((await within(layer).findByText(/inside its CLI/)).textContent).toContain("Take control");
});

test("an agent with no terminal says why in its tab and does not reconnect; any other close reconnects", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  await open();
  const view = await openTerminal("w1");
  act(() => socketOf("w1", "view")[0].end(4404, 'agent "w1" has no terminal'));
  expect(within(view).getByRole("status").textContent).toContain('agent "w1" has no terminal');
  act(() => vi.advanceTimersByTime(RETRY_MS * 3));
  expect(socketOf("w1", "view")).toHaveLength(1);

  const other = await openTerminal("supervisor");
  act(() => socketOf("supervisor", "view")[0].end(1006));
  expect(within(other).getByRole("status").textContent).toContain("reconnecting");
  act(() => vi.advanceTimersByTime(RETRY_MS));
  await waitFor(() => expect(socketOf("supervisor", "view")).toHaveLength(2));
});

test("an error frame shows in the terminal's bar", async () => {
  const { view } = await w1Terminal();
  act(() => socketOf("w1", "view")[0].frame({ type: "error", reason: "the size of a terminal open to view follows" }));
  expect(within(view).getByRole("alert").textContent).toContain("follows");
});

test("in view the terminal takes the window's size and its font shrinks until it fits", async () => {
  await w1Terminal();
  const xterm = FakeXterm.all[1];
  const font = () => Number(xterm.options.fontSize);
  // The panel holds 19 rows at 13 px (FakeFit): a window of 24 rows needs a smaller font.
  act(() => socketOf("w1", "view")[0].frame({ type: "size", cols: 80, rows: 24 }));
  expect([xterm.cols, xterm.rows]).toEqual([80, 24]);
  expect(font()).toBeLessThan(13);
  expect(Math.floor(300 / (1.2 * font()))).toBeGreaterThanOrEqual(24); // all rows show
  // A small window keeps the usual font; a huge one stops at the smallest.
  act(() => socketOf("w1", "view")[0].frame({ type: "size", cols: 40, rows: 10 }));
  expect(font()).toBe(13);
  act(() => socketOf("w1", "view")[0].frame({ type: "size", cols: 400, rows: 120 }));
  expect(font()).toBe(8);
});
