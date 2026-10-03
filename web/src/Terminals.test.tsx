import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { AgentInfo, SessionInfo } from "./api";
import { App } from "./App";
import { FakeSocket, FakeXterm } from "./fakes";
import { RETRY_MS } from "./terminalLink";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const NONE = { gates: 0, questions: 0, agents: 0 };
const SESSION: SessionInfo = { name: "lado", repo: "/src/lado", status: "running", agents: 2, waiting: NONE };
const AGENTS: AgentInfo[] = [
  { name: "supervisor", role: "supervisor", provider: "claude", status: "idle", run: null, task: null },
  { name: "w1", role: "developer", provider: "kilo", status: "busy", run: null, task: "Build it" },
];
const BASE = "ws://localhost:3000/api/sessions/lado/agents";

let history: { text: string; alternate: boolean } = { text: "line 1\nline 2", alternate: false };

// The change feed: it opens with a reset, so the sessions load; no changes after.
class StreamStub {
  static CLOSED = 2;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  readyState = 1;
  constructor(readonly url: string) {}
  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    if (type === "reset") queueMicrotask(() => listener(new MessageEvent("reset", { lastEventId: "1" })));
  }
  close() {}
}

beforeEach(() => {
  localStorage.clear();
  FakeSocket.all = [];
  FakeXterm.all = [];
  history = { text: "line 1\nline 2", alternate: false };
  vi.stubGlobal("WebSocket", FakeSocket);
  vi.stubGlobal("EventSource", StreamStub);
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
});

const panel = () => screen.queryByRole("complementary", { name: "Terminals" });

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
  return within(panel()!).getByRole("tabpanel", { name: agent });
}

const socketOf = (agent: string, mode: string) =>
  FakeSocket.all.filter((socket) => socket.url === `${BASE}/${agent}/terminal?mode=${mode}`);

test("the terminal panel is closed at first and no socket opens with the page", async () => {
  await open();
  await team();
  expect(panel()).toBeNull();
  expect(FakeSocket.all).toHaveLength(0);
});

test("a chip opens its agent's terminal on the right, to view, the supervisor's too", async () => {
  await open();
  const view = await openTerminal("supervisor");
  const tab = within(panel()!).getByRole("tab", { name: "supervisor" });
  expect(tab.getAttribute("aria-selected")).toBe("true");
  expect(socketOf("supervisor", "view")).toHaveLength(1);
  expect(socketOf("supervisor", "control")).toHaveLength(0);
  act(() => socketOf("supervisor", "view")[0].open());
  expect(within(view).getByRole("status").textContent).toContain("live");
  act(() => FakeXterm.all[0].type("x"));
  expect(socketOf("supervisor", "view")[0].sent).toEqual([]); // in view nothing typed goes out
  expect(within(view).getByRole("button", { name: "Take control" })).toBeTruthy();
});

test("the chip of the open terminal is marked; another chip adds a tab and keeps the first socket", async () => {
  await open();
  await openTerminal("w1");
  expect((await chip("w1")).getAttribute("aria-pressed")).toBe("true");
  expect((await chip("supervisor")).getAttribute("aria-pressed")).toBe("false");
  await openTerminal("supervisor");
  expect((await chip("w1")).getAttribute("aria-pressed")).toBe("false");
  expect(within(panel()!).getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["w1", "supervisor"]);
  const [w1] = socketOf("w1", "view");
  expect(w1.closed).toBe(false); // hidden, not closed
  fireEvent.click(await chip("w1")); // selects the tab it has: no new socket
  expect(socketOf("w1", "view")).toHaveLength(1);
  expect(within(panel()!).getByRole("tab", { name: "w1" }).getAttribute("aria-selected")).toBe("true");
});

test("the panel keeps its terminals while the session's tabs change", async () => {
  await open();
  await openTerminal("w1");
  fireEvent.click(screen.getByRole("link", { name: "Flows" }));
  expect(panel()).toBeTruthy();
  fireEvent.click(screen.getByRole("link", { name: "Activity" }));
  expect(FakeSocket.all).toHaveLength(1); // the same terminal, not a new one
});

test("× closes a tab and its socket; closing the last tab closes the panel", async () => {
  await open();
  await openTerminal("w1");
  await openTerminal("supervisor");
  fireEvent.click(within(panel()!).getByRole("button", { name: "Close supervisor's terminal" }));
  expect(socketOf("supervisor", "view")[0].closed).toBe(true);
  expect(within(panel()!).getByRole("tab", { name: "w1" }).getAttribute("aria-selected")).toBe("true");
  fireEvent.click(within(panel()!).getByRole("button", { name: "Close w1's terminal" }));
  expect(socketOf("w1", "view")[0].closed).toBe(true);
  expect(panel()).toBeNull();
});

test("the panel's width changes with its edge and is remembered", async () => {
  await open();
  await openTerminal("w1");
  const edge = within(panel()!).getByRole("separator", { name: "Resize the terminals" });
  expect(edge.getAttribute("aria-orientation")).toBe("vertical");
  const before = Number(edge.getAttribute("aria-valuenow"));
  fireEvent.keyDown(edge, { key: "ArrowLeft" });
  const after = Number(edge.getAttribute("aria-valuenow"));
  expect(after).toBeGreaterThan(before);
  expect(panel()!.style.width).toBe(`${after}px`);
  expect(JSON.parse(localStorage.getItem("lado.terminals")!)).toEqual({ width: after });
  cleanup();
  await open();
  await openTerminal("w1");
  expect(panel()!.style.width).toBe(`${after}px`);
});

test("the Agents tab opens an agent's terminal in the same panel", async () => {
  await open("/sessions/lado/agents");
  const list = await screen.findByRole("table", { name: "Agents of lado" });
  fireEvent.click(await within(list).findByRole("button", { name: "Open supervisor's terminal" }));
  expect(within(panel()!).getByRole("tab", { name: "supervisor" }).getAttribute("aria-selected")).toBe("true");
  expect(socketOf("supervisor", "view")).toHaveLength(1);
});

async function w1Terminal() {
  await open();
  const view = await openTerminal("w1");
  act(() => socketOf("w1", "view")[0].open());
  return { view };
}

test("Take control asks first, then opens it in control; Release goes back to view", async () => {
  const { view } = await w1Terminal();
  fireEvent.click(within(view).getByRole("button", { name: "Take control" }));
  const ask = within(view).getByRole("alertdialog", { name: "Take control of w1" });
  fireEvent.click(within(ask).getByRole("button", { name: "Cancel" }));
  expect(socketOf("w1", "control")).toHaveLength(0);

  fireEvent.click(within(view).getByRole("button", { name: "Take control" }));
  const sure = within(view).getByRole("alertdialog", { name: "Take control of w1" });
  fireEvent.click(within(sure).getByRole("button", { name: "Take control" }));
  expect(socketOf("w1", "view")[0].closed).toBe(true);
  const [control] = socketOf("w1", "control");
  act(() => control.open());
  // In control what is typed goes out, and the terminal's size follows the panel.
  act(() => FakeXterm.all[1].type("ls\r"));
  expect(control.frames).toEqual([
    { type: "resize", cols: 120, rows: 30 },
    { type: "input", data: "ls\r" },
  ]);
  fireEvent.click(within(view).getByRole("button", { name: "Release" }));
  expect(control.closed).toBe(true);
  expect(socketOf("w1", "view")).toHaveLength(2);
});

test("in view the wheel up opens the read-only history; Back to live closes it", async () => {
  const { view } = await w1Terminal();
  const xterm = FakeXterm.all[0];
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
  FakeXterm.all[0].wheel(-1);
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
  const xterm = FakeXterm.all[0];
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
