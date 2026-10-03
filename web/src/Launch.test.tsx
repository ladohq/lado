// Launch and session control (docs/design/ui.md, Launch and session control): the New
// session window, its Resume mode, the session's actions in its head and in the list, Stop
// and Forget.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { FolderInfo, KitInfo, ProviderInfo, RecentFolder, SessionInfo } from "./api";
import { App } from "./App";
import { FakeEventSource, FakeSocket, stubDialogs } from "./fakes";
import { BUNDLE_VERSION } from "./version";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const NONE = { gates: 0, questions: 0, agents: 0 };

function session(name: string, more: Partial<SessionInfo> = {}): SessionInfo {
  return {
    name,
    repo: `/src/${name}`,
    status: "running",
    agents: 1,
    waiting: NONE,
    kits: ["default"],
    provider: "claude",
    permission_mode: null,
    without: [],
    ...more,
  };
}

function folder(path: string, more: Partial<FolderInfo> = {}): FolderInfo {
  return {
    path,
    ok: true,
    problem: null,
    root: path,
    branch: "main",
    has_commits: true,
    subfolders: [],
    default_name: path.split("/").pop() ?? "",
    name_state: "free",
    ...more,
  };
}

function provider(name: string, more: Partial<ProviderInfo> = {}): ProviderInfo {
  return {
    name,
    title: name === "claude" ? "Claude Code" : "Kilo CLI",
    default: name === "claude",
    permission_modes: name === "claude" ? ["default", "acceptEdits", "plan", "dontAsk"] : ["default", "plan"],
    install_hint: `install ${name}`,
    installed: true,
    version: name === "claude" ? "2.1.287" : "7.2.1",
    detail: "",
    tested_version: "",
    warning: "",
    ...more,
  };
}

const kit = (name: string, more: Partial<KitInfo> = {}): KitInfo => ({
  name,
  version: "1.0.0",
  description: "",
  valid: true,
  problem: null,
  ...more,
});

type Call = { method: string; path: string; body: unknown };

let sessions: SessionInfo[];
let folders: Record<string, FolderInfo>;
let recent: RecentFolder[];
let kits: KitInfo[];
let providers: () => Promise<ProviderInfo[]>;
let answers: Record<string, () => Response | Promise<Response>>; // "METHOD path" -> the server's answer
let calls: Call[];

const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });

beforeEach(() => {
  localStorage.clear();
  stubDialogs();
  sessions = [session("lado")];
  folders = {};
  recent = [];
  kits = [kit("default"), kit("team")];
  providers = async () => [provider("claude"), provider("kilo")];
  answers = {};
  calls = [];
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ method, path, body });
      const url = new URL(path, "http://lado.test");
      const answer = answers[`${method} ${url.pathname}`];
      if (answer) return answer();
      if (url.pathname === "/api/health") return json({ ok: true, version: BUNDLE_VERSION });
      if (url.pathname === "/api/sessions") return json(sessions);
      if (url.pathname === "/api/folders") {
        const asked = url.searchParams.get("path") ?? "";
        return json(folders[asked] ?? folder(asked, { ok: false, problem: `${asked} does not exist`, root: null }));
      }
      if (url.pathname === "/api/folders/recent") return json(recent);
      if (url.pathname === "/api/kits") return json(kits);
      if (url.pathname === "/api/providers") return json(await providers());
      return json([]);
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

function open(path = "/sessions") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

async function openLaunch() {
  open();
  fireEvent.click(screen.getByRole("button", { name: "Launch" }));
  return screen.findByRole("dialog", { name: "New session" });
}

const where = () => screen.getByRole("combobox", { name: /Where/ }) as HTMLInputElement;

function type(path: string) {
  fireEvent.change(where(), { target: { value: path } });
}

const startButton = () => screen.getByRole("button", { name: "Start session" }) as HTMLButtonElement;

async function ready(path: string, more: Partial<FolderInfo> = {}) {
  folders[path] = folder(path, more);
  type(path);
  await screen.findByText(/✓ git repository · branch main/);
}

// Launch on the rail and "+"

test("Launch is on the rail right after Home, not in the top bar, and + opens the same window", async () => {
  open();
  const rail = screen.getByRole("navigation", { name: "Sections" });
  const items = within(rail)
    .getAllByRole("listitem")
    .map((item) => item.textContent);
  expect(items.slice(0, 3)).toEqual(["Home", "Launch", "Needs you"]);
  const top = document.querySelector(".topbar")!;
  expect(within(top as HTMLElement).queryByRole("button", { name: "Launch" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "New session" }));
  const dialog = await screen.findByRole("dialog", { name: "New session" });
  expect(dialog.hasAttribute("open")).toBe(true);
  fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("dialog", { name: "New session" })).toBeNull();
});

// Where

test("the folder is checked by the server and its reason shown; Start stays off until it will do", async () => {
  await openLaunch();
  expect(startButton().disabled).toBe(true);
  folders["/tmp/x"] = folder("/tmp/x", { ok: false, problem: "/tmp/x is not inside a git repository", root: null });
  type("/tmp/x");
  expect(await screen.findByText("/tmp/x is not inside a git repository")).toBeTruthy();
  expect(startButton().disabled).toBe(true);
  await ready("/src/lado");
  expect(startButton().disabled).toBe(false);
});

test("subfolders are suggested from the parent of what is typed and picked with the keyboard", async () => {
  folders["/src/"] = folder("/src/", { ok: false, problem: "no", subfolders: ["lado", "lado-kits", "other"] });
  await openLaunch();
  type("/src/la");
  const list = await screen.findByRole("listbox", { name: "Folders" });
  expect(within(list).getAllByRole("option").map((o) => o.textContent)).toEqual(["lado/", "lado-kits/"]);
  expect(calls.some((c) => c.path === "/api/folders?path=%2Fsrc%2F")).toBe(true);
  fireEvent.keyDown(where(), { key: "ArrowDown" });
  fireEvent.keyDown(where(), { key: "ArrowDown" });
  expect(within(list).getAllByRole("option")[1].getAttribute("aria-selected")).toBe("true");
  fireEvent.keyDown(where(), { key: "Enter" });
  expect(where().value).toBe("/src/lado-kits");
  expect(screen.queryByRole("listbox", { name: "Folders" })).toBeNull();
});

test("a recent folder is one click, and its last session gives kits, provider and mode", async () => {
  recent = [
    {
      path: "/src/app",
      session: session("app", { repo: "/src/app", kits: ["team"], provider: "kilo", permission_mode: "plan" }),
    },
  ];
  folders["/src/app"] = folder("/src/app");
  await openLaunch();
  fireEvent.click(await screen.findByRole("button", { name: "/src/app" }));
  expect(where().value).toBe("/src/app");
  await screen.findByText(/✓ git repository/);
  const kitsField = screen.getByRole("group", { name: "Kits" });
  await waitFor(() => expect(within(kitsField).getByText("team")).toBeTruthy());
  expect(within(kitsField).queryByText("default")).toBeNull();
  expect(screen.getAllByText("from the last session of this folder").length).toBeGreaterThan(0);
  await waitFor(() => expect((screen.getByRole("combobox", { name: "Provider" }) as HTMLSelectElement).value).toBe("kilo"));
  expect((screen.getByRole("combobox", { name: "Permission mode" }) as HTMLSelectElement).value).toBe("plan");
});

// Name

test("the name is the folder's default, with what the server says of it", async () => {
  await openLaunch();
  await ready("/src/lado", { default_name: "lado", name_state: "running" });
  expect((screen.getByRole("textbox", { name: "Name" }) as HTMLInputElement).value).toBe("lado");
  expect(screen.getByText('"lado" is taken by a running session')).toBeTruthy();
  folders["/src/old"] = folder("/src/old", { default_name: "old", name_state: "taken_elsewhere" });
  type("/src/old");
  expect(await screen.findByText('"old" is taken by a session of another folder')).toBeTruthy();
});

test("a stopped session of the folder is offered to resume, and Resume it turns the window to Resume", async () => {
  sessions = [session("lado", { status: "stopped", provider: "kilo", repo: "/src/lado" })];
  await openLaunch();
  await ready("/src/lado", { default_name: "lado", name_state: "stopped_here" });
  expect(screen.getByText("a stopped session lado exists for this folder")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Resume it" }));
  const dialog = await screen.findByRole("dialog", { name: "Resume session" });
  expect(where().disabled).toBe(true);
  expect((within(dialog).getByRole("textbox", { name: "Name" }) as HTMLInputElement).disabled).toBe(true);
  expect(within(dialog).getByRole("button", { name: "Resume session" })).toBeTruthy();
});

// Kits

test("kits start as the default kit; an invalid kit cannot be added and says why", async () => {
  kits = [kit("default"), kit("team"), kit("broken", { valid: false, problem: "bad" })];
  await openLaunch();
  await ready("/src/lado");
  const field = screen.getByRole("group", { name: "Kits" });
  expect(within(field).getByText("default")).toBeTruthy();
  const add = (await within(field).findByRole("combobox", { name: "Add kit" })) as HTMLSelectElement;
  const broken = within(add).getByRole("option", { name: /broken/ }) as HTMLOptionElement;
  expect(broken.disabled).toBe(true);
  expect(broken.textContent).toContain("invalid: run lado kits check broken");
  fireEvent.change(add, { target: { value: "team" } });
  expect(within(field).getByText("team")).toBeTruthy();
  fireEvent.click(within(field).getByRole("button", { name: "Remove default" }));
  expect(within(field).queryByText("default")).toBeNull();
});

// Provider and permission mode

test("providers show checking while their CLIs are asked, a missing one is off, a warning is shown", async () => {
  let release: (found: ProviderInfo[]) => void = () => {};
  providers = () => new Promise((resolve) => (release = resolve));
  await openLaunch();
  const select = screen.getByRole("combobox", { name: "Provider" }) as HTMLSelectElement;
  expect(select.disabled).toBe(true);
  expect(select.textContent).toContain("checking…");
  await act(async () =>
    release([
      provider("claude", { version: "2.1.288", warning: "LADO is tested with Claude Code 2.1.287" }),
      provider("kilo", { installed: false, version: "", detail: "`kilo` not found on PATH" }),
    ]),
  );
  await waitFor(() => expect(select.disabled).toBe(false));
  const kilo = within(select).getByRole("option", { name: /kilo/ }) as HTMLOptionElement;
  expect(kilo.disabled).toBe(true);
  expect(kilo.textContent).toContain("not installed");
  expect(screen.getByText(/LADO is tested with Claude Code 2\.1\.287/)).toBeTruthy();
});

test("a mode the new provider does not support goes back to default, and the window says so", async () => {
  await openLaunch();
  const providerSelect = (await screen.findByRole("combobox", { name: "Provider" })) as HTMLSelectElement;
  await waitFor(() => expect(providerSelect.disabled).toBe(false));
  const mode = screen.getByRole("combobox", { name: "Permission mode" }) as HTMLSelectElement;
  fireEvent.change(mode, { target: { value: "dontAsk" } });
  fireEvent.change(providerSelect, { target: { value: "kilo" } });
  expect(mode.value).toBe("default");
  expect(screen.getByText("kilo has no mode dontAsk: set to default")).toBeTruthy();
});

// Starting

test("Start sends the window's fields, says Starting… and opens the new session with its problems", async () => {
  let release: () => void = () => {};
  const pending = new Promise<void>((resolve) => (release = resolve));
  const started = session("app", { repo: "/src/app" });
  answers["POST /api/sessions"] = async () => {
    await pending;
    return json({ session: started, resumed: false, changes: [], problems: ["run x needs a rev"] });
  };
  await openLaunch();
  await ready("/src/app");
  const providerSelect = screen.getByRole("combobox", { name: "Provider" }) as HTMLSelectElement;
  await waitFor(() => expect(providerSelect.disabled).toBe(false));
  fireEvent.click(screen.getByText(/Advanced/));
  fireEvent.change(screen.getByRole("textbox", { name: /Switch off/ }), { target: { value: "agent:rev, skill:x" } });
  fireEvent.click(startButton());
  expect(await screen.findByRole("button", { name: "Starting…" })).toBeTruthy();
  expect(where().disabled).toBe(true);
  const sent = calls.find((c) => c.method === "POST")!;
  expect(sent.body).toEqual({
    where: { kind: "folder", path: "/src/app" },
    name: "app",
    kits: ["default"],
    provider: "claude",
    without: ["agent:rev", "skill:x"],
  });
  await act(async () => release());
  expect(await screen.findByRole("region", { name: "Session app" })).toBeTruthy();
  expect(screen.queryByRole("dialog", { name: "New session" })).toBeNull();
  expect(screen.getByRole("alert").textContent).toContain("run x needs a rev");
});

test("a refused start shows the core's whole reason and keeps the window", async () => {
  answers["POST /api/sessions"] = () => json({ detail: "kit \"nope\" not found; looked in /a, /b" }, 400);
  await openLaunch();
  await ready("/src/app");
  fireEvent.click(startButton());
  const dialog = screen.getByRole("dialog", { name: "New session" });
  expect((await within(dialog).findByRole("alert")).textContent).toBe('kit "nope" not found; looked in /a, /b');
  expect(startButton().disabled).toBe(false);
});

test("a taken name is offered to resume when the session is of this folder", async () => {
  sessions = [session("app", { status: "stopped", repo: "/src/app" })];
  answers["POST /api/sessions"] = () =>
    json({ detail: { message: 'session "app" exists already (stopped, in /src/app)', status: "stopped", repo: "/src/app" } }, 409);
  await openLaunch();
  await ready("/src/app");
  fireEvent.change(screen.getByRole("textbox", { name: "Name" }), { target: { value: "app" } });
  fireEvent.click(startButton());
  const dialog = screen.getByRole("dialog", { name: "New session" });
  expect((await within(dialog).findByRole("alert")).textContent).toContain('session "app" exists already');
  fireEvent.click(within(dialog).getByRole("button", { name: "Resume it" }));
  expect(await screen.findByRole("dialog", { name: "Resume session" })).toBeTruthy();
});

// Resume

test("Resume fills the window from the session, sends only what changed and shows the changes", async () => {
  sessions = [session("lado", { status: "stopped", repo: "/src/lado", kits: ["team"], provider: "kilo", permission_mode: "plan" })];
  answers["POST /api/sessions/lado/resume"] = () =>
    json({ session: session("lado"), resumed: true, changes: ["permission mode: plan -> default"], problems: ["run y needs a rev"] });
  open("/sessions/lado");
  fireEvent.click(await screen.findByRole("button", { name: "Resume…" }));
  const dialog = await screen.findByRole("dialog", { name: "Resume session" });
  expect(where().value).toBe("/src/lado");
  expect(within(within(dialog).getByRole("group", { name: "Kits" })).getByText("team")).toBeTruthy();
  const providerSelect = within(dialog).getByRole("combobox", { name: "Provider" }) as HTMLSelectElement;
  await waitFor(() => expect(providerSelect.value).toBe("kilo"));
  const mode = within(dialog).getByRole("combobox", { name: "Permission mode" }) as HTMLSelectElement;
  expect(mode.value).toBe("plan");
  fireEvent.change(mode, { target: { value: "default" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Resume session" }));
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Resume session" })).toBeNull());
  expect(calls.find((c) => c.method === "POST")!.body).toEqual({ permission_mode: "default" });
  expect(screen.getByText("permission mode: plan -> default")).toBeTruthy();
  expect(screen.getByRole("alert").textContent).toContain("run y needs a rev");
});

// The session's actions, by status (in its head and in the list)

const head = () => document.querySelector(".session-head") as HTMLElement;

async function menuItems(container: HTMLElement, label: RegExp | string) {
  fireEvent.click(within(container).getByRole("button", { name: label }));
  const menu = await screen.findByRole("menu");
  const items = within(menu)
    .getAllByRole("menuitem")
    .map((item) => item.textContent);
  fireEvent.keyDown(menu, { key: "Escape" });
  return items;
}

test.each([
  ["running", [], ["Stop session…"]],
  ["loop_down", [], ["Stop session…"]],
  ["stopped", ["Resume…"], ["Resume…", "Forget…"]],
  ["tmux_gone", ["Resume…"], ["Resume…", "Stop session…"]],
] as const)("a %s session's head has %j and its menu %j", async (status, buttons, items) => {
  sessions = [session("lado", { status })];
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  const shown = within(head())
    .getAllByRole("button")
    .map((button) => button.getAttribute("aria-label") ?? button.textContent);
  expect(shown).toEqual([...buttons, "Session actions"]);
  expect(await menuItems(head(), "Session actions")).toEqual(items);
});

test.each([
  ["running", "Stop lado", ["Stop session…"]],
  ["loop_down", "Stop lado", ["Stop session…"]],
  ["stopped", "Resume lado", ["Resume…", "Forget…"]],
  ["tmux_gone", "Resume lado", ["Resume…", "Stop session…"]],
] as const)("a %s session's row has %s and the rest in its menu", async (status, main, items) => {
  sessions = [session("lado", { status })];
  localStorage.setItem("lado.stoppedSessions", "open");
  open("/sessions");
  const row = (await screen.findByRole("link", { name: /lado/ })).closest("li") as HTMLElement;
  const buttons = within(row).getAllByRole("button");
  expect(buttons.map((button) => button.getAttribute("aria-label"))).toEqual([main, "More actions for lado"]);
  expect(await menuItems(row, "More actions for lado")).toEqual(items);
});

test("Stop from the list names the session, says what it does and stops that one", async () => {
  sessions = [session("lado"), session("other")];
  answers["GET /api/sessions/other/stop-preview"] = () =>
    json({ agents: ["supervisor", "w1"], dropped: 2, open_runs: ["feature/x"], worktrees: [] });
  answers["POST /api/sessions/other/stop"] = () => json({ dropped: 2 });
  open("/sessions/lado");
  const row = (await screen.findByRole("link", { name: /other/ })).closest("li") as HTMLElement;
  fireEvent.click(within(row).getByRole("button", { name: "Stop other" }));
  const asked = await screen.findByRole("dialog", { name: 'Stop session "other"?' });
  await within(asked).findByText("its 2 agents are closed");
  expect(within(asked).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
    "its 2 agents are closed",
    "2 messages they have not got are dropped",
    "branches, worktrees, 1 open run and the history stay",
    "you can resume it later",
  ]);
  fireEvent.click(within(asked).getByRole("button", { name: "Stop other" }));
  await waitFor(() => expect(screen.queryByRole("dialog", { name: 'Stop session "other"?' })).toBeNull());
  expect(calls.filter((c) => c.method === "POST").map((c) => c.path)).toEqual(["/api/sessions/other/stop"]);
  expect(screen.getByRole("region", { name: "Session lado" })).toBeTruthy(); // the page stays
});

test("a refused stop says why in its popover", async () => {
  answers["GET /api/sessions/lado/stop-preview"] = () => json({ agents: [], dropped: 0, open_runs: [], worktrees: [] });
  answers["POST /api/sessions/lado/stop"] = () => json({ detail: 'session "lado" is stopped already' }, 400);
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  fireEvent.click(within(head()).getByRole("button", { name: "Session actions" }));
  fireEvent.click(await screen.findByRole("menuitem", { name: "Stop session…" }));
  const asked = await screen.findByRole("dialog", { name: 'Stop session "lado"?' });
  fireEvent.click(await within(asked).findByRole("button", { name: "Stop lado" }));
  expect((await within(asked).findByRole("alert")).textContent).toBe('session "lado" is stopped already');
});

test("Forget lists what stays on disk and needs the open runs ticked, then leaves for the list", async () => {
  sessions = [session("lado", { status: "stopped" })];
  answers["GET /api/sessions/lado/forget-preview"] = () =>
    json({ open_runs: ["feature/x"], worktrees: [{ path: "/src/lado/.lado/worktrees/lado/feature-x", branch: "lado/lado/feature-x" }] });
  answers["DELETE /api/sessions/lado"] = () => json({ open_runs: ["feature/x"], worktrees: [] });
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  fireEvent.click(within(head()).getByRole("button", { name: "Session actions" }));
  fireEvent.click(await screen.findByRole("menuitem", { name: "Forget…" }));
  const asked = await screen.findByRole("dialog", { name: 'Forget session "lado"?' });
  expect(asked.hasAttribute("open")).toBe(true); // modal
  expect(within(asked).getByText("Its history (messages, runs, notes, gates) is deleted. This cannot be undone.")).toBeTruthy();
  expect(
    await within(asked).findByText("/src/lado/.lado/worktrees/lado/feature-x · branch lado/lado/feature-x"),
  ).toBeTruthy();
  const forget = within(asked).getByRole("button", { name: "Forget lado" }) as HTMLButtonElement;
  expect(forget.disabled).toBe(true);
  fireEvent.click(within(asked).getByRole("checkbox", { name: "Also forget its 1 open run (feature/x)" }));
  expect(forget.disabled).toBe(false);
  fireEvent.click(forget);
  await waitFor(() => expect(screen.queryByRole("region", { name: "Session lado" })).toBeNull());
  expect(calls.find((c) => c.method === "DELETE")!.path).toBe("/api/sessions/lado?force=true");
});
