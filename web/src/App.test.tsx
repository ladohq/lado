import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { AgentInfo, SessionInfo } from "./api";
import { App } from "./App";
import { AGENT_REST, FakeEventSource, FakeSocket, stream, stubDialogs, wideColumn } from "./fakes";
import { BUNDLE_VERSION } from "./version";

// A session's page has the terminal panel (Terminals.test.tsx): no canvas, no server here.
vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const NONE = { gates: 0, questions: 0, agents: 0 };
const SETTINGS = { kits: ["default"], provider: "claude", permission_mode: null, without: [], ran_seconds: 0, running_since: null, stopped_at: null };

const SESSIONS: SessionInfo[] = [
  { name: "lado", repo: "/src/lado", status: "running", agents: 3, waiting: NONE, ...SETTINGS },
  { name: "my app.v2", repo: "/src/app", status: "stopped", agents: 0, waiting: NONE, ...SETTINGS },
  { name: "old", repo: "/src/old", status: "loop_down", agents: 0, waiting: NONE, ...SETTINGS },
];

const AGENTS: AgentInfo[] = [
  {
    name: "supervisor",
    role: "supervisor",
    provider: "claude",
    status: "idle",
    run: null,
    task: null,
    waiting_reason: null,
    ...AGENT_REST,
  },
];

// The LADO version /api/health answers (it needs no token): the bundle's own unless a test
// sets another.
let serverVersion = BUNDLE_VERSION;
// The newer LADO /api/update names, if any.
let available: string | null = null;

// The API: /api/sessions answers `status` and `body`; a request for the event stream (the
// shell asking why one was refused) answers `events`, or the same as /api/sessions.
function serve(status = 200, body: unknown = SESSIONS, events?: { status: number; body: unknown }) {
  const fetch = vi.fn(async (path: string) => {
    if (path === "/api/health") return new Response(JSON.stringify({ ok: true, version: serverVersion }));
    if (path === "/api/update") {
      const update = { current: BUNDLE_VERSION, latest: available, available, checked_at: null };
      return new Response(JSON.stringify(update));
    }
    if (path.startsWith("/api/events")) {
      const answer = events ?? { status, body: status === 200 ? "" : body };
      return new Response(JSON.stringify(answer.body), { status: answer.status });
    }
    if (path === "/api/sessions/lado/agents") {
      return new Response(JSON.stringify(AGENTS), { status: 200 });
    }
    // The feed's messages and run events (Chat.test.tsx), the runs and their steps (Flows.test.tsx).
    if (path.includes("/messages?")) return new Response(JSON.stringify({ items: [], earlier: false }));
    if (["/events", "/runs", "/notes", "/gates"].some((end) => path.endsWith(end))) {
      return new Response("[]");
    }
    // The Kits page's lists (Kits.test.tsx).
    if (path.startsWith("/api/kits/") || path === "/api/marketplaces") return new Response("[]");
    expect(path).toBe("/api/sessions");
    return new Response(JSON.stringify(body), { status });
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

function open(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

function wide(matches: boolean) {
  // jsdom has no matchMedia: (max-width: 899px) matches when the window is narrow.
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: query.includes("max-width") ? !matches : false,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    })),
  );
}


function change(session: string, item: SessionInfo | null, op = "update") {
  return { kind: "sessions", session, key: "", op, item };
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  delete document.documentElement.dataset.theme;
  wide(true);
  serverVersion = BUNDLE_VERSION;
  available = null;
  serve();
  FakeEventSource.all = [];
  FakeEventSource.autoStart = true;
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("WebSocket", FakeSocket);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const heading = () => screen.getByRole("banner").querySelector("h1")!.textContent;
const rail = () => screen.getByRole("navigation", { name: "Sections" });

test("the rail lists every section in order, Settings at the bottom", () => {
  open("/");
  const names = within(rail())
    .getAllByRole("link")
    .map((link) => link.getAttribute("aria-label"));
  expect(names).toEqual([
    "Home",
    "Needs you",
    "Sessions",
    "Projects",
    "Kits",
    "Settings",
  ]);
  const settings = within(rail()).getByRole("link", { name: "Settings" });
  expect(settings.closest(".rail-bottom")).toBeTruthy();
});

test.each([
  ["/", "Home", "Home"],
  ["/needs-you", "Needs you", "Needs you"],
  ["/sessions", "Sessions", "Sessions"],
  ["/projects", "Projects", "Projects"],
  ["/kits", "Kits", "Kits"],
  ["/kits/updates", "Kits", "Kits"],
  ["/marketplace", "Kits", "Kits"], // the Marketplace page of earlier versions
  ["/settings", "Settings", "Settings"],
])("%s shows %s, marked in the rail", (path, title, item) => {
  open(path);
  expect(heading()).toBe(title);
  const link = within(rail()).getByRole("link", { name: item });
  expect(link.getAttribute("aria-current")).toBe("page");
  expect(within(rail()).getAllByRole("link").filter((l) => l.hasAttribute("aria-current"))).toHaveLength(1);
});

test("following a rail link opens its section", () => {
  open("/");
  fireEvent.click(within(rail()).getByRole("link", { name: "Kits" }));
  expect(heading()).toBe("Kits");
});

test.each([
  ["/", "Home", /docs\/design\/ui\.md#home/],
  ["/projects", "Projects", /ROADMAP\.md#later-after-stage-7/],
])("%s is a placeholder that links to its plan item", (path, title, plan) => {
  open(path);
  const placeholder = screen.getByRole("region", { name: title });
  const link = within(placeholder).getByRole("link", { name: /plan/i });
  expect(link.getAttribute("href")).toMatch(plan);
  expect(within(placeholder).getByRole("link", { name: "Sessions" }).getAttribute("href")).toBe(
    "/sessions",
  );
});

test.each(["/nowhere/at/all", "/gates/12"])("%s is Not found with a link to Home", (path) => {
  open(path); // a gate has no page: it is a card in its session's chat
  expect(heading()).toBe("Not found");
  const main = screen.getByRole("main");
  expect(within(main).getByRole("link", { name: "Home" }).getAttribute("href")).toBe("/");
});

test("the top bar shows the server's address; Launch is on the rail and Escape closes its window", async () => {
  stubDialogs();
  open("/");
  const bar = screen.getByRole("banner");
  expect(within(bar).getByText(window.location.host)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Launch" }));
  const dialog = await screen.findByRole("dialog", { name: "New session" });
  fireEvent.keyDown(dialog, { key: "Escape" });
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("the rail collapses to icons with names and remembers it", () => {
  open("/");
  const toggle = screen.getByRole("button", { name: "Collapse menu" });
  expect(toggle.getAttribute("aria-expanded")).toBe("true");
  fireEvent.click(toggle);
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  expect(toggle.getAttribute("aria-label")).toBe("Expand menu");
  const kits = within(rail()).getByRole("link", { name: "Kits" });
  expect(kits.getAttribute("title")).toBe("Kits");
  expect(kits.querySelector("svg")).toBeTruthy();
  cleanup();
  open("/");
  expect(screen.getByRole("button", { name: "Expand menu" }).getAttribute("aria-expanded")).toBe(
    "false",
  );
});

test("on a narrow window the rail starts collapsed", () => {
  wide(false);
  open("/");
  expect(screen.getByRole("button", { name: "Expand menu" })).toBeTruthy();
});

test("without the token the shell shows the server's message instead of the content", async () => {
  serve(401, { detail: "no valid token: open the link `lado ui` prints" });
  open("/settings");
  expect((await screen.findByRole("alert")).textContent).toBe(
    "no valid token: open the link `lado ui` prints",
  );
  expect(screen.queryByRole("heading", { name: "Appearance" })).toBeNull();
  expect(rail()).toBeTruthy();
});

// The bundle against the server's version

test("the bundle knows the LADO version it was built for", () => {
  expect(BUNDLE_VERSION).toMatch(/^\d+\.\d+\.\d+/);
});

test("a server of the bundle's own version shows no banner", async () => {
  const fetch = serve();
  open("/sessions");
  await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/health", expect.anything()));
  await screen.findByRole("link", { name: /lado/ });
  expect(screen.queryByRole("alert")).toBeNull();
});

test.each(["/", "/sessions", "/settings"])(
  "on %s, a server of another version shows a banner that first offers a reload",
  async (path) => {
    serverVersion = "0.0.1";
    serve();
    const reload = vi.fn();
    vi.stubGlobal("location", { ...window.location, reload });
    open(path);
    const banner = await screen.findByRole("alert");
    expect(banner.textContent).toBe(
      `This page is LADO ${BUNDLE_VERSION}, the server runs 0.0.1: reload the page.Reload`,
    );
    expect(banner.querySelector("code")).toBeNull();
    fireEvent.click(within(banner).getByRole("button", { name: "Reload" }));
    expect(reload).toHaveBeenCalled();
  },
);

test("after a reload that did not help, the banner says to restart the server", async () => {
  serverVersion = "0.0.1";
  serve();
  const reload = vi.fn();
  vi.stubGlobal("location", { ...window.location, reload });
  const first = open("/");
  fireEvent.click(await screen.findByRole("button", { name: "Reload" }));
  first.unmount(); // the page loads again, of the same version
  open("/");
  const banner = await screen.findByRole("alert");
  expect(banner.textContent).toBe(
    `This page is LADO ${BUNDLE_VERSION}, the server runs 0.0.1, also after a reload: run lado server stop, then lado ui.`,
  );
  const commands = Array.from(banner.querySelectorAll("code"), (code) => code.textContent);
  expect(commands).toEqual(["lado server stop", "lado ui"]);
});

test("a reload for another server version than this one's does not count", async () => {
  sessionStorage.setItem("lado.reloadedFor", "0.0.2");
  serverVersion = "0.0.1";
  serve();
  open("/");
  expect((await screen.findByRole("alert")).textContent).toContain("reload the page");
});

// A newer LADO on PyPI (/api/update)

test("a newer LADO is named with the command that installs it", async () => {
  available = "99.0.0";
  serve();
  open("/");
  const line = await screen.findByText(/is available/);
  expect(line.textContent).toBe("LADO 99.0.0 is available: run lado update");
  expect(line.querySelector("code")?.textContent).toBe("lado update");
});

test("without a newer LADO nothing is said", async () => {
  const fetch = serve();
  open("/");
  await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/update", expect.anything()));
  expect(screen.queryByText(/is available/)).toBeNull();
});

// Sessions

test("/sessions lists the sessions and asks to select one", async () => {
  open("/sessions");
  const list = screen.getByRole("navigation", { name: "Sessions" });
  expect(await within(list).findByRole("link", { name: /lado/ })).toBeTruthy();
  expect(within(list).getAllByRole("link")).toHaveLength(2); // the stopped one is folded
  expect(screen.getByText("Select a session")).toBeTruthy();
  const stuck = within(list).getByRole("link", { name: /old/ });
  expect(stuck.className).toContain("dim");
  expect(stuck.textContent).toContain("session loop not running");
});

test("with no sessions, /sessions says how to start one", async () => {
  serve(200, []);
  open("/sessions");
  expect((await screen.findByText(/No sessions yet/)).textContent).toBe("No sessions yet. Start one with Launch.");
});

test("another error of the API is shown in the list", async () => {
  serve(503, { detail: "lado.db has schema version 99" });
  open("/sessions");
  expect((await screen.findByRole("alert")).textContent).toBe("lado.db has schema version 99");
});

test("the search filters the list by name", async () => {
  open("/sessions");
  const list = screen.getByRole("navigation", { name: "Sessions" });
  await within(list).findByRole("link", { name: /lado/ });
  fireEvent.change(screen.getByRole("searchbox", { name: "Find a session" }), {
    target: { value: "OL" },
  });
  expect(within(list).getAllByRole("link").map((l) => l.getAttribute("href"))).toEqual([
    "/sessions/old",
  ]);
});

test("a session opens on its Activity tab with its status, and no placeholder for its gates", async () => {
  open("/sessions/lado");
  const view = await screen.findByRole("region", { name: "Session lado" });
  expect(within(view).getByText("running")).toBeTruthy();
  expect(within(view).queryByRole("note")).toBeNull();
  expect(view.textContent).not.toMatch(/will show here/);
  const tabs = within(view).getByRole("navigation", { name: "Session sections" });
  expect(within(tabs).getAllByRole("link").map((l) => l.textContent)).toEqual([
    "Activity",
    "Agents · 1",
    "Flows",
    "Artifacts",
  ]);
  expect(within(tabs).getByRole("link", { name: "Activity" }).getAttribute("aria-current")).toBe(
    "page",
  );
  expect(within(view).getByRole("region", { name: "Chat" })).toBeTruthy();
  const current = screen.getByRole("navigation", { name: "Sessions" });
  expect(within(current).getByRole("link", { name: /lado/ }).getAttribute("aria-current")).toBe(
    "page",
  );
});

test("/sessions/<name>/flows opens the Flows tab, and a tab changes the address", async () => {
  wideColumn();
  open("/sessions/lado/flows");
  const view = await screen.findByRole("region", { name: "Session lado" });
  expect(await within(view).findByText("No active runs")).toBeTruthy();
  fireEvent.click(within(view).getByRole("link", { name: "Activity" }));
  expect(within(view).getByRole("region", { name: "Chat" })).toBeTruthy();
  expect(within(view).getByRole("link", { name: "Agents · 1" }).getAttribute("href")).toBe(
    "/sessions/lado/agents",
  );
});

test("a session with a space and a dot in its name opens by its encoded address", async () => {
  open("/sessions/my%20app.v2/artifacts");
  const view = await screen.findByRole("region", { name: "Session my app.v2" });
  expect(within(view).getByRole("region", { name: "Artifacts" })).toBeTruthy();
  const list = screen.getByRole("navigation", { name: "Sessions" });
  fireEvent.click(within(list).getByRole("button", { name: "Stopped (1)" }));
  expect(within(list).getByRole("link", { name: /my app\.v2/ }).getAttribute("href")).toBe(
    "/sessions/my%20app.v2",
  );
});

test("an unknown session says so and links to the list", async () => {
  open("/sessions/ghost/agents");
  const missing = await screen.findByText("Session ghost not found");
  expect(missing).toBeTruthy();
  expect(screen.getByRole("link", { name: "All sessions" }).getAttribute("href")).toBe("/sessions");
});

test("an unknown tab of a session is Not found", async () => {
  open("/sessions/lado/nope");
  expect(heading()).toBe("Not found");
});

// Live updates: the change feed

test("the shell opens one event stream; the sessions load on its reset", async () => {
  FakeEventSource.autoStart = false;
  const fetch = serve();
  open("/");
  expect(FakeEventSource.all.map((one) => one.url)).toEqual(["/api/events"]);
  fireEvent.click(within(rail()).getByRole("link", { name: "Sessions" }));
  expect(fetch).not.toHaveBeenCalled();
  stream().start();
  const list = screen.getByRole("navigation", { name: "Sessions" });
  expect(await within(list).findByRole("link", { name: /lado/ })).toBeTruthy();
  fireEvent.click(within(rail()).getByRole("link", { name: "Kits" }));
  fireEvent.click(within(rail()).getByRole("link", { name: "Sessions" }));
  expect(FakeEventSource.all).toHaveLength(1); // a section opens no stream of its own
});

test("every reset loads the sessions again", async () => {
  const fetch = serve();
  open("/sessions");
  await screen.findByRole("link", { name: /lado/ });
  expect(fetch.mock.calls.filter(([path]) => path === "/api/sessions")).toHaveLength(1);
  serve(200, [SESSIONS[0]]);
  stream().send("reset", {}, "20");
  await waitFor(() =>
    expect(within(screen.getByRole("navigation", { name: "Sessions" })).getAllByRole("link")).toHaveLength(1),
  );
});

test("changes update the list and the session's header as they come", async () => {
  open("/sessions/lado");
  const view = await screen.findByRole("region", { name: "Session lado" });
  const list = screen.getByRole("navigation", { name: "Sessions" });
  stream().send("change", change("lado", { ...SESSIONS[0], status: "tmux_gone" }));
  expect(within(view).getByText("tmux session is gone")).toBeTruthy();
  expect(within(list).getByRole("link", { name: /lado/ }).className).toContain("dim");
  stream().send(
    "change",
    change("new", { name: "new", repo: "/src/new", status: "running", agents: 1, waiting: NONE, ...SETTINGS }, "insert"),
    "11",
  );
  expect(within(list).getByRole("link", { name: /new/ })).toBeTruthy();
  stream().send("change", change("old", null, "delete"), "12");
  expect(within(list).queryByRole("link", { name: /old/ })).toBeNull();
  expect(within(list).getAllByRole("link")).toHaveLength(2) // lado and new; the stopped one is folded;
});

test("a change that comes while the sessions load is not lost to an older load", async () => {
  FakeEventSource.autoStart = false;
  let answer: (response: Response) => void = () => {};
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise<Response>((resolve) => (answer = resolve))),
  );
  open("/sessions/lado");
  stream().start();
  stream().send("change", change("lado", { ...SESSIONS[0], status: "tmux_gone" }), "11");
  await act(async () => answer(new Response(JSON.stringify(SESSIONS))));
  const view = await screen.findByRole("region", { name: "Session lado" });
  expect(within(view).getByText("tmux session is gone")).toBeTruthy();
});

test("a change of another kind leaves the sessions alone", async () => {
  open("/sessions");
  const list = screen.getByRole("navigation", { name: "Sessions" });
  await within(list).findByRole("link", { name: /lado/ });
  stream().send("change", { kind: "messages", session: "lado", key: "4", op: "insert", item: null }, "11");
  expect(within(list).getAllByRole("link")).toHaveLength(2);
});

test("the Agents tab follows the agents' changes; a reset loads them again", async () => {
  wideColumn();
  const fetch = serve();
  open("/sessions/lado/agents");
  const list = await screen.findByRole("navigation", { name: "Agents" });
  await within(list).findByRole("link", { name: /supervisor/ });
  const agent = (name: string, status: string) => ({ ...AGENTS[0], name, role: "developer", provider: "kilo", status });
  const row = () => within(list).getByRole("link", { name: /^w1/ });
  stream().send("change", { kind: "agents", session: "lado", key: "w1", op: "insert", item: agent("w1", "starting") }, "11");
  expect(row().textContent).toContain("starting");
  stream().send("change", { kind: "agents", session: "lado", key: "w1", op: "update", item: agent("w1", "busy") }, "12");
  expect(row().textContent).toContain("busy");
  stream().send("change", { kind: "agents", session: "other", key: "w1", op: "insert", item: agent("w1", "idle") }, "13");
  stream().send("change", { kind: "agents", session: "lado", key: "w1", op: "delete", item: null }, "14");
  expect(within(list).queryByRole("link", { name: /^w1/ })).toBeNull();
  const loads = () => fetch.mock.calls.filter(([path]) => path === "/api/sessions/lado/agents").length;
  const before = loads();
  stream().send("reset", {}, "20");
  await waitFor(() => expect(loads()).toBe(before + 1));
});

test("reconnecting shows in the top bar while the stream is down", async () => {
  open("/");
  await waitFor(() => expect(stream().readyState).toBe(FakeEventSource.OPEN));
  const bar = screen.getByRole("banner");
  expect(within(bar).queryByText(/reconnecting/)).toBeNull();
  stream().fail(false);
  expect(within(bar).getByRole("status").textContent).toMatch(/reconnecting/);
  stream().open();
  expect(within(bar).queryByText(/reconnecting/)).toBeNull();
});

test("a stream the server refused: the reason shows, then it reconnects from the last id", async () => {
  open("/sessions");
  await screen.findByRole("link", { name: /lado/ });
  vi.useFakeTimers();
  stream().send("change", change("lado", SESSIONS[0]), "17");
  stream().send("change", change("lado", SESSIONS[0])); // derived: no id of its own
  // The stream's own reason, also when the rest of the API answers.
  const reason = "reading changes failed: disk I/O error";
  serve(200, SESSIONS, { status: 503, body: { detail: reason } });
  stream().fail(true);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
  expect(within(screen.getByRole("banner")).getByRole("status").textContent).toContain(reason);
  expect(FakeEventSource.all).toHaveLength(1);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(5000);
  });
  expect(stream().url).toBe("/api/events?after=17");
});

test("a stream refused for the token shows how to get in and does not try again", async () => {
  FakeEventSource.autoStart = false;
  serve(401, { detail: "no valid token: open the link `lado ui` prints" });
  open("/settings");
  vi.useFakeTimers();
  stream().fail(true);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10000);
  });
  expect(screen.getByRole("alert").textContent).toBe("no valid token: open the link `lado ui` prints");
  expect(FakeEventSource.all).toHaveLength(1);
});

// Settings and the theme

test("Settings is one flat page: Appearance, Notifications, then Providers and environment", () => {
  open("/settings");
  const sections = screen
    .getAllByRole("heading", { level: 2 })
    .map((h) => h.textContent);
  expect(sections).toEqual(["Appearance", "Notifications", "Providers and environment"]);
  const providers = screen.getByRole("region", { name: "Providers and environment" });
  expect(within(providers).getByRole("link", { name: /plan/i }).getAttribute("href")).toMatch(
    /docs\/design\/ui\.md#providers-and-environment/,
  );
});

test("the theme applies at once on the root and is remembered", () => {
  open("/settings");
  const system = screen.getByRole("radio", { name: "System" }) as HTMLInputElement;
  expect(system.checked).toBe(true);
  expect(document.documentElement.dataset.theme).toBeUndefined();
  fireEvent.click(screen.getByRole("radio", { name: "Dark" }));
  expect(document.documentElement.dataset.theme).toBe("dark");
  cleanup();
  open("/settings");
  expect((screen.getByRole("radio", { name: "Dark" }) as HTMLInputElement).checked).toBe(true);
  fireEvent.click(screen.getByRole("radio", { name: "System" }));
  // No theme on the root: the stylesheet follows prefers-color-scheme.
  expect(document.documentElement.dataset.theme).toBeUndefined();
});

test("without browser storage the theme is the system's and nothing breaks", () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("denied");
  });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("denied");
  });
  open("/settings");
  expect((screen.getByRole("radio", { name: "System" }) as HTMLInputElement).checked).toBe(true);
  act(() => {
    fireEvent.click(screen.getByRole("radio", { name: "Light" }));
  });
  expect(document.documentElement.dataset.theme).toBe("light");
  vi.restoreAllMocks();
});
