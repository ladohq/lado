// The session page's layout (docs/design/ui.md, Structure): the team chips, the session
// list's groups and "+", the rail with Launch and the top bar.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { AgentInfo, SessionInfo } from "./api";
import { App } from "./App";
import { AGENT_REST, columnWidth, FakeEventSource, FakeResizeObserver, FakeSocket, stream } from "./fakes";

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
      return new Response("[]");
    }),
  );
  FakeEventSource.all = [];
  FakeEventSource.autoStart = true;
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("WebSocket", FakeSocket);
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
  expect(JSON.parse(localStorage.getItem("lado.sessionsList")!)).toEqual({ width: 300 });
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
