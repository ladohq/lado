import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { AgentInfo, SessionInfo } from "./api";
import { App } from "./App";
import { FakeSocket, FakeXterm, lastSocket } from "./fakes";
import { RETRY_MS } from "./terminalLink";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const SESSION: SessionInfo = { name: "lado", repo: "/src/lado", status: "running", agents: 2 };
const AGENTS: AgentInfo[] = [
  { name: "supervisor", role: "supervisor", provider: "claude", status: "idle" },
  { name: "w1", role: "developer", provider: "kilo", status: "busy" },
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
          : [SESSION];
      return new Response(JSON.stringify(body), { status: 200 });
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function open(path = "/sessions/lado") {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
  return screen.findByRole("region", { name: "Terminals" });
}

const socketOf = (agent: string, mode: string) =>
  FakeSocket.all.filter((socket) => socket.url === `${BASE}/${agent}/terminal?mode=${mode}`);

test("a session's page has the terminal panel with the supervisor's terminal, in control", async () => {
  const panel = await open();
  const tab = within(panel).getByRole("tab", { name: "Supervisor" });
  expect(tab.getAttribute("aria-selected")).toBe("true");
  const [socket] = socketOf("supervisor", "control");
  act(() => socket.open());
  expect(within(panel).getByRole("status").textContent).toContain("live");
  act(() => socket.frame(new TextEncoder().encode("hello from the agent").buffer));
  expect(FakeXterm.all[0].written).toBe("hello from the agent");
  // In control what is typed goes out, and the terminal's size follows the panel.
  act(() => FakeXterm.all[0].type("ls\r"));
  expect(socket.frames).toEqual([
    { type: "resize", cols: 120, rows: 30 },
    { type: "input", data: "ls\r" },
  ]);
});

test("the panel shows on every tab of the session", async () => {
  await open("/sessions/lado/flows");
  expect(screen.getByRole("region", { name: "Terminals" })).toBeTruthy();
  fireEvent.click(screen.getByRole("link", { name: "Agents" }));
  expect(screen.getByRole("region", { name: "Terminals" })).toBeTruthy();
  expect(FakeSocket.all).toHaveLength(1); // the same terminal, not a new one
});

test("the panel collapses and changes height, and remembers both; collapsed keeps the socket", async () => {
  const panel = await open();
  const collapse = within(panel).getByRole("button", { name: "Collapse the terminals" });
  fireEvent.click(collapse);
  expect(within(panel).getByRole("tabpanel", { hidden: true }).hidden).toBe(true);
  expect(lastSocket().closed).toBe(false);
  expect(JSON.parse(localStorage.getItem("lado.terminals")!).collapsed).toBe(true);
  fireEvent.click(within(panel).getByRole("button", { name: "Expand the terminals" }));

  const handle = within(panel).getByRole("separator", { name: "Resize the terminals" });
  const before = Number(handle.getAttribute("aria-valuenow"));
  fireEvent.keyDown(handle, { key: "ArrowUp" });
  const after = Number(handle.getAttribute("aria-valuenow"));
  expect(after).toBeGreaterThan(before);
  expect(panel.style.height).toBe(`${after}px`);
  expect(JSON.parse(localStorage.getItem("lado.terminals")!)).toEqual({ collapsed: false, height: after });
});

test("the Agents tab lists the agents live and opens an agent's terminal, to view", async () => {
  const panel = await open("/sessions/lado/agents");
  const list = await screen.findByRole("table", { name: "Agents of lado" });
  await within(list).findByText("w1");
  expect(within(list).getByText("in the panel")).toBeTruthy(); // the supervisor's
  fireEvent.click(within(list).getByRole("button", { name: "Open w1's terminal" }));
  const tab = within(panel).getByRole("tab", { name: "w1" });
  expect(tab.getAttribute("aria-selected")).toBe("true");
  expect(socketOf("w1", "view")).toHaveLength(1);
  // In view nothing typed goes out.
  act(() => socketOf("w1", "view")[0].open());
  act(() => FakeXterm.all[1].type("x"));
  expect(socketOf("w1", "view")[0].sent).toEqual([]);
});

test("a hidden tab keeps its socket; closing a tab closes it", async () => {
  const panel = await open("/sessions/lado/agents");
  fireEvent.click(await screen.findByRole("button", { name: "Open w1's terminal" }));
  fireEvent.click(within(panel).getByRole("tab", { name: "Supervisor" }));
  const [w1] = socketOf("w1", "view");
  expect(w1.closed).toBe(false);
  fireEvent.click(within(panel).getByRole("button", { name: "Close w1's terminal" }));
  expect(w1.closed).toBe(true);
  expect(within(panel).queryByRole("tab", { name: "w1" })).toBeNull();
  expect(socketOf("supervisor", "control")[0].closed).toBe(false);
});

async function w1Terminal() {
  const panel = await open("/sessions/lado/agents");
  fireEvent.click(await screen.findByRole("button", { name: "Open w1's terminal" }));
  const view = within(panel).getByRole("tabpanel", { name: "w1" });
  act(() => socketOf("w1", "view")[0].open());
  return { panel, view };
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
  expect(socketOf("w1", "control")).toHaveLength(1);
  fireEvent.click(within(view).getByRole("button", { name: "Release" }));
  expect(socketOf("w1", "control")[0].closed).toBe(true);
  expect(socketOf("w1", "view")).toHaveLength(2);
});

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

test("a close for good shows the reason and does not reconnect; any other reconnects", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const panel = await open();
  const [socket] = socketOf("supervisor", "control");
  act(() => socket.end(4404, 'session "lado" is stopped'));
  expect(within(panel).getByRole("status").textContent).toContain('session "lado" is stopped');
  act(() => vi.advanceTimersByTime(RETRY_MS * 3));
  expect(FakeSocket.all).toHaveLength(1);
});

test("a temporary close says reconnecting, then a new socket opens", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const panel = await open();
  act(() => socketOf("supervisor", "control")[0].end(1006));
  expect(within(panel).getByRole("status").textContent).toContain("reconnecting");
  act(() => vi.advanceTimersByTime(RETRY_MS));
  await waitFor(() => expect(socketOf("supervisor", "control")).toHaveLength(2));
});

test("an error frame shows in the terminal's bar", async () => {
  const panel = await open();
  const [socket] = socketOf("supervisor", "control");
  act(() => socket.open());
  act(() => socket.frame({ type: "error", reason: "the size of a terminal open to view follows" }));
  expect(within(panel).getByRole("alert").textContent).toContain("follows");
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
