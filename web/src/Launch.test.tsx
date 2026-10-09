// Launch and session control (docs/design/ui.md, Launch and session control): the New
// session window, its Resume mode, the session's actions in its head, its list row's menu, Stop
// and Forget.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { FolderInfo, KitInfo, ProviderInfo, RecentFolder, SessionAbout, SessionInfo } from "./api";
import { App } from "./App";
import { FakeEventSource, FakeSocket, stubDialogs, stubLegacyCopy, unstubLegacyCopy } from "./fakes";
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
    ran_seconds: 0,
    running_since: null,
    busy: 0,
    activity_since: null,
    stopped_at: null,
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
    provider: null,
    ...more,
  };
}

function provider(name: string, more: Partial<ProviderInfo> = {}): ProviderInfo {
  return {
    name,
    title: name === "claude" ? "Claude Code" : "Kilo CLI",
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
let abouts: Record<string, SessionAbout>; // by session; none: 404
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
  abouts = {};
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
      const about = /^\/api\/sessions\/([^/]+)\/about$/.exec(url.pathname);
      if (about) {
        const found = abouts[decodeURIComponent(about[1])];
        return found ? json(found) : json({ detail: "unknown session" }, 404);
      }
      if (url.pathname.endsWith("/messages")) return json({ items: [], earlier: false });
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
const providerSelect = () => screen.getByRole("combobox", { name: "Provider" }) as HTMLSelectElement;

// A folder that will do, with claude suggested unless `more` says otherwise; the providers
// answered.
async function ready(path: string, more: Partial<FolderInfo> = {}) {
  folders[path] = folder(path, { provider: { name: "claude", reason: "only_installed" }, ...more });
  type(path);
  await screen.findByText(/✓ git repository · branch main/);
  await waitFor(() => expect(providerSelect().disabled).toBe(false));
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

test("a folder typed in full is not suggested again", async () => {
  folders["/src/"] = folder("/src/", { ok: false, problem: "no", subfolders: ["lado", "lado-kits"] });
  await openLaunch();
  type("/src/lado-kits");
  await waitFor(() => expect(calls.some((c) => c.path === "/api/folders?path=%2Fsrc%2F")).toBe(true));
  await act(() => new Promise((resolve) => setTimeout(resolve, 50)));
  expect(screen.queryByRole("listbox", { name: "Folders" })).toBeNull();
  type("/src/lado");
  const list = await screen.findByRole("listbox", { name: "Folders" });
  expect(within(list).getAllByRole("option").map((o) => o.textContent)).toEqual(["lado-kits/"]);
});

test("a recent folder is one click, and its last session gives kits, provider and mode", async () => {
  recent = [
    {
      path: "/src/app",
      session: session("app", { repo: "/src/app", kits: ["team"], provider: "kilo", permission_mode: "plan" }),
    },
  ];
  folders["/src/app"] = folder("/src/app", { provider: { name: "kilo", reason: "last_session" } });
  await openLaunch();
  fireEvent.click(await screen.findByRole("button", { name: "/src/app" }));
  expect(where().value).toBe("/src/app");
  await screen.findByText(/✓ git repository/);
  const kitsField = screen.getByRole("group", { name: "Kits" });
  await waitFor(() => expect(within(kitsField).getByText("team")).toBeTruthy());
  expect(within(kitsField).queryByText("default")).toBeNull();
  expect(screen.getAllByText("from the last session of this folder").length).toBeGreaterThan(0);
  await waitFor(() => expect((screen.getByRole("combobox", { name: "Provider" }) as HTMLSelectElement).value).toBe("kilo"));
  expect(screen.getByText("from the folder's last session")).toBeTruthy();
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

test("without a kit Start stays off and the window says why", async () => {
  await openLaunch();
  await ready("/src/lado");
  const field = screen.getByRole("group", { name: "Kits" });
  fireEvent.click(within(field).getByRole("button", { name: "Remove default" }));
  // Waited for: under the load of a full run it was not there yet when looked for at once.
  expect(await screen.findByText("a session needs at least one kit")).toBeTruthy();
  expect(startButton().disabled).toBe(true);
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
  fireEvent.change(select, { target: { value: "claude" } });
  const kilo = within(select).getByRole("option", { name: /kilo/ }) as HTMLOptionElement;
  expect(kilo.disabled).toBe(true);
  expect(kilo.textContent).toContain("not installed");
  expect(screen.getByText(/LADO is tested with Claude Code 2\.1\.287/)).toBeTruthy();
});

test("the folder's suggested provider is chosen, with the core's reason", async () => {
  await openLaunch();
  await ready("/src/app", { provider: { name: "kilo", reason: "last_session" } });
  await waitFor(() => expect(providerSelect().value).toBe("kilo"));
  expect(screen.getByText("from the folder's last session")).toBeTruthy();
  await ready("/src/one", { provider: { name: "claude", reason: "only_installed" } });
  await waitFor(() => expect(providerSelect().value).toBe("claude"));
  expect(screen.getByText("the only one installed")).toBeTruthy();
  expect(screen.queryByText("from the folder's last session")).toBeNull();
  expect(startButton().disabled).toBe(false);
});

test("without a suggestion no provider is chosen and Start is off until the human picks one", async () => {
  await openLaunch();
  await ready("/src/app", { provider: null });
  expect(providerSelect().value).toBe("");
  expect(screen.getByText("choose the agent CLI for this session")).toBeTruthy();
  expect(startButton().disabled).toBe(true);
  fireEvent.change(providerSelect(), { target: { value: "kilo" } });
  expect(providerSelect().value).toBe("kilo");
  expect(startButton().disabled).toBe(false);
});

test("a provider not installed cannot be chosen, even when suggested", async () => {
  providers = async () => [provider("claude"), provider("kilo", { installed: false, version: "" })];
  await openLaunch();
  await ready("/src/app", { provider: { name: "kilo", reason: "last_session" } });
  await waitFor(() => expect(providerSelect().disabled).toBe(false));
  const kilo = within(providerSelect()).getByRole("option", { name: /kilo/ }) as HTMLOptionElement;
  expect(kilo.disabled).toBe(true);
  expect(startButton().disabled).toBe(true);
});

test("the human's own choice of provider is kept when the folder changes", async () => {
  await openLaunch();
  await ready("/src/app", { provider: { name: "kilo", reason: "last_session" } });
  await waitFor(() => expect(providerSelect().value).toBe("kilo"));
  fireEvent.change(providerSelect(), { target: { value: "claude" } });
  await ready("/src/other", { provider: { name: "kilo", reason: "only_installed" } });
  expect(providerSelect().value).toBe("claude");
  expect(screen.queryByText("the only one installed")).toBeNull();
});

test("a mode the new provider does not support goes back to default, and the window says so", async () => {
  await openLaunch();
  const providerSelect = (await screen.findByRole("combobox", { name: "Provider" })) as HTMLSelectElement;
  await waitFor(() => expect(providerSelect.disabled).toBe(false));
  fireEvent.change(providerSelect, { target: { value: "claude" } });
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
    return json({ session: started, resumed: false, changes: [], problems: ["run x needs a rev"], lead: "", warnings: [] });
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
  expect((await screen.findByRole("alert")).textContent).toContain("run x needs a rev");
});

test("a start's warnings show on the new session's page, such as what its supervisor waits for", async () => {
  const trust =
    'Claude Code asks whether to trust /src/app: in its terminal choose "Yes, I trust this folder" ' +
    '(Enter alone answers "No, exit" and closes the agent)';
  answers["POST /api/sessions"] = () =>
    json({
      session: session("app", { repo: "/src/app" }),
      resumed: false,
      changes: [],
      problems: [],
      lead: "lead: supervisor of kit default",
      warnings: [trust],
    });
  await openLaunch();
  await ready("/src/app");
  await waitFor(() => expect((screen.getByRole("combobox", { name: "Provider" }) as HTMLSelectElement).disabled).toBe(false));
  fireEvent.click(startButton());
  expect(await screen.findByRole("region", { name: "Session app" })).toBeTruthy();
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain(trust);
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

test("a name in two kits offers to switch off either one, into the Switch off field", async () => {
  answers["POST /api/sessions"] = () =>
    json(
      {
        detail: {
          message: 'agent "reviewer" is defined by two kits: kit-a (…) and kit-b (…)',
          switch_off: ["agent:reviewer@kit-a", "agent:reviewer@kit-b"],
        },
      },
      400,
    );
  await openLaunch();
  await ready("/src/app");
  const field = screen.getByRole("textbox", { name: /Switch off/ }) as HTMLInputElement;
  expect(field.placeholder).toBe("agent:reviewer@kit-b, skill:style");
  expect(screen.getByText("kind:name or kind:name@kit, separated by commas; kinds: agent, skill, mcp, flow")).toBeTruthy();
  fireEvent.change(field, { target: { value: "skill:x" } });
  fireEvent.click(startButton());
  const dialog = screen.getByRole("dialog", { name: "New session" });
  expect((await within(dialog).findByRole("alert")).textContent).toContain('agent "reviewer" is defined by two kits');
  expect(within(dialog).getByRole("button", { name: "Switch off reviewer of kit-a" })).toBeTruthy();
  fireEvent.click(within(dialog).getByRole("button", { name: "Switch off reviewer of kit-b" }));
  expect(field.value).toBe("skill:x, agent:reviewer@kit-b");
  expect((dialog.querySelector("details.launch-advanced") as HTMLDetailsElement).open).toBe(true);
  expect(calls.filter((c) => c.method === "POST")).toHaveLength(1); // started again only by Start
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

test("a taken name of a running session of this folder offers to open it, not to resume it", async () => {
  sessions = [session("app", { repo: "/src/app" })];
  answers["POST /api/sessions"] = () =>
    json({ detail: { message: 'session "app" exists already (running, in /src/app)', status: "running", repo: "/src/app" } }, 409);
  await openLaunch();
  await ready("/src/app");
  fireEvent.change(screen.getByRole("textbox", { name: "Name" }), { target: { value: "app" } });
  fireEvent.click(startButton());
  const dialog = screen.getByRole("dialog", { name: "New session" });
  await within(dialog).findByRole("alert");
  expect(within(dialog).queryByRole("button", { name: "Resume it" })).toBeNull();
  fireEvent.click(within(dialog).getByRole("button", { name: "Open it" }));
  expect(await screen.findByRole("region", { name: "Session app" })).toBeTruthy();
  expect(screen.queryByRole("dialog", { name: "New session" })).toBeNull();
});

// Resume

test("Resume fills the window from the session, sends only what changed and shows the changes", async () => {
  sessions = [session("lado", { status: "stopped", repo: "/src/lado", kits: ["team"], provider: "kilo", permission_mode: "plan" })];
  answers["POST /api/sessions/lado/resume"] = () =>
    json({
      session: session("lado"),
      resumed: true,
      changes: ["permission mode: plan -> default"],
      problems: ["run y needs a rev"],
      lead: "",
      warnings: [],
    });
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
  // The session's page shows them after the navigation, a render after the window closed.
  expect(await screen.findByText("permission mode: plan -> default")).toBeTruthy();
  expect((await screen.findByRole("alert")).textContent).toContain("run y needs a rev");
});

// The session's actions, by status: icons in its head, in the top bar; its list row has only
// the entry's menu

const head = () => document.querySelector(".topbar .session-head") as HTMLElement;

test.each([
  ["running", ["Stop session…"]],
  ["loop_down", ["Stop session…"]],
  ["stopped", ["Resume…", "Forget…"]],
  ["tmux_gone", ["Resume…", "Stop session…"]],
] as const)("a %s session's head has Copy path, Copy link and the icons %j, each with its tooltip, and no menu", async (status, labels) => {
  sessions = [session("lado", { status })];
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  const buttons = within(head()).getAllByRole("button");
  expect(buttons.map((button) => button.getAttribute("aria-label"))).toEqual(["Copy path", "Copy link", ...labels]);
  for (const button of buttons) {
    expect(button.querySelector("svg")).toBeTruthy();
    expect(button.getAttribute("title")).toBeNull(); // the UI's tooltip, not the browser's
    fireEvent.focus(button);
    expect(screen.getByRole("tooltip").textContent).toBe(button.getAttribute("aria-label"));
    fireEvent.blur(button);
  }
  expect(within(head()).queryByRole("button", { name: "Session actions" })).toBeNull();
  expect(head().querySelector("[aria-haspopup='menu']")).toBeNull();
});

test("Forget is drawn in the colour of a dangerous action", async () => {
  sessions = [session("lado", { status: "stopped" })];
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  expect(within(head()).getByRole("button", { name: "Forget…" }).classList).toContain("danger-icon");
  expect(within(head()).getByRole("button", { name: "Resume…" }).classList).not.toContain("danger-icon");
});

const MINUTE = 60_000;
const ago = (ms: number) => new Date(Date.now() - ms).toISOString();
const ranText = () => head().querySelector(".session-ran")?.textContent;

test("a running session's head says how long it ran, and counts on each minute", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  try {
    sessions = [session("lado", { ran_seconds: 10 * 60, running_since: ago((2 * 60 + 4) * MINUTE + 30_000) })];
    open("/sessions/lado");
    await screen.findByRole("region", { name: "Session lado" });
    expect(ranText()).toBe("2 h 14 min");
    act(() => vi.advanceTimersByTime(MINUTE));
    expect(ranText()).toBe("2 h 15 min");
  } finally {
    vi.useRealTimers();
  }
});

test.each([
  ["stopped", { stopped_at: ago(5 * 60 * MINUTE + 20 * MINUTE) }, "stopped 5 h ago · ran 3 h 2 min"],
  ["tmux_gone", {}, "ran 3 h 2 min"],
] as const)("a %s session's head says how long it ran", async (status, more, text) => {
  sessions = [session("lado", { status, ran_seconds: (3 * 60 + 2) * 60, ...more })];
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  expect(ranText()).toBe(text);
});

test("a stopped session's head counts on how long ago it stopped", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  try {
    sessions = [session("lado", { status: "stopped", ran_seconds: 120, stopped_at: ago(59 * MINUTE + 30_000) })];
    open("/sessions/lado");
    await screen.findByRole("region", { name: "Session lado" });
    expect(ranText()).toBe("stopped 59 min ago · ran 2 min");
    act(() => vi.advanceTimersByTime(MINUTE));
    expect(ranText()).toBe("stopped 1 h ago · ran 2 min");
  } finally {
    vi.useRealTimers();
  }
});

test("the head's second line has the folder, whole in its title, the kits and the provider, no mode", async () => {
  sessions = [
    session("lado", { repo: "/Users/me/src/lado", kits: ["team", "default"], provider: "kilo", permission_mode: "plan" }),
    session("app"),
  ];
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  const meta = head().querySelector(".session-meta") as HTMLElement;
  const path = meta.querySelector(".session-path") as HTMLElement;
  expect(path.textContent).toBe("/Users/me/src/lado");
  expect(path.getAttribute("title")).toBe("/Users/me/src/lado");
  expect(meta.querySelector(".session-kits")?.textContent).toBe("team, default");
  expect(meta.querySelector(".session-agent-cli")?.textContent).toBe("kilo");
  expect(within(meta).getAllByRole("button").map((button) => button.getAttribute("aria-label"))).toEqual(["Copy path"]);
  cleanup();
  open("/sessions/app");
  await screen.findByRole("region", { name: "Session app" });
  expect(head().querySelector(".session-agent-cli")?.textContent).toBe("claude");
});

test.each([
  ["Copy link", "Link copied", (): string => `${window.location.origin}/sessions/my%20app`],
  ["Copy path", "Path copied", (): string => "/src/my app"],
] as const)("%s in the head copies and says %s for a while", async (label, said, text) => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  try {
    const writeText = vi.fn(async () => {});
    clipboard(writeText);
    const legacy = stubLegacyCopy();
    sessions = [session("my app")];
    open("/sessions/my%20app?token=secret");
    await screen.findByRole("region", { name: "Session my app" });
    fireEvent.click(within(head()).getByRole("button", { name: label }));
    await waitFor(() => expect(within(head()).getByText(said).getAttribute("role")).toBe("status"));
    expect(writeText).toHaveBeenCalledWith(text());
    expect(legacy).toEqual([]);
    await act(() => vi.advanceTimersByTimeAsync(1900));
    expect(within(head()).getByText(said)).toBeTruthy();
    await act(() => vi.advanceTimersByTimeAsync(200));
    expect(within(head()).queryByText(said)).toBeNull();
  } finally {
    vi.useRealTimers();
  }
});

test.each([
  ["Copy link", "Link copied", (): string => `${window.location.origin}/sessions/my%20app`],
  ["Copy path", "Path copied", (): string => "/src/my app"],
] as const)("%s in the head copies without the Clipboard API, as over http from another machine", async (label, said, text) => {
  const legacy = stubLegacyCopy();
  sessions = [session("my app")];
  open("/sessions/my%20app");
  await screen.findByRole("region", { name: "Session my app" });
  const button = within(head()).getByRole("button", { name: label });
  button.focus();
  fireEvent.click(button);
  await waitFor(() => expect(within(head()).getByText(said).getAttribute("role")).toBe("status"));
  expect(legacy).toEqual([text()]);
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.querySelector("body > textarea")).toBeNull();
  expect(document.activeElement).toBe(button);
});

test("a refused Clipboard API copy falls back to the legacy copy", async () => {
  clipboard(async () => Promise.reject(new Error("not allowed")));
  const legacy = stubLegacyCopy();
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  fireEvent.click(within(head()).getByRole("button", { name: "Copy path" }));
  await waitFor(() => expect(within(head()).getByText("Path copied")).toBeTruthy());
  expect(legacy).toEqual(["/src/lado"]);
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.querySelector("body > textarea")).toBeNull();
});

test.each([
  ["Copy link", "Link to lado", "Link", (): string => `${window.location.origin}/sessions/lado`],
  ["Copy path", "Path of lado", "Path", (): string => "/src/lado"],
] as const)("when no copy works %s in the head shows the text selected", async (label, dialog, name, text) => {
  clipboard(async () => Promise.reject(new Error("not allowed")));
  stubLegacyCopy(false);
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  fireEvent.click(within(head()).getByRole("button", { name: label }));
  const asked = await screen.findByRole("dialog", { name: dialog });
  const field = within(asked).getByRole("textbox", { name }) as HTMLInputElement;
  expect(field.value).toBe(text());
  await waitFor(() => expect(document.activeElement).toBe(field)); // focused once it is drawn
  expect([field.selectionStart, field.selectionEnd]).toEqual([0, field.value.length]);
  fireEvent.keyDown(asked, { key: "Escape" });
  expect(screen.queryByRole("dialog", { name: dialog })).toBeNull();
  expect(document.activeElement).toBe(within(head()).getByRole("button", { name: label }));
});

const row = async (name: string) => (await screen.findByRole("link", { name: new RegExp(name) })).closest("li") as HTMLElement;

async function openRowMenu(name: string) {
  fireEvent.click(within(await row(name)).getByRole("button", { name: `Actions for ${name}` }));
  return screen.findByRole("menu", { name });
}

test.each(["running", "loop_down", "stopped", "tmux_gone"] as const)(
  "a %s session's row has only its menu, of Copy link and Open in new tab",
  async (status) => {
    sessions = [session("lado", { status })];
    localStorage.setItem("lado.stoppedSessions", "open");
    open("/sessions");
    const buttons = within(await row("lado")).getAllByRole("button");
    expect(buttons.map((button) => button.getAttribute("aria-label"))).toEqual(["Actions for lado"]);
    const menu = await openRowMenu("lado");
    expect(within(menu).getAllByRole("menuitem").map((item) => item.textContent)).toEqual(["Copy link", "Open in new tab"]);
  },
);

test("Open in new tab is a link to the session's page in a new tab", async () => {
  sessions = [session("my app")];
  open("/sessions");
  const menu = await openRowMenu("my app");
  const item = within(menu).getByRole("menuitem", { name: "Open in new tab" });
  expect(item.tagName).toBe("A");
  expect(item.getAttribute("href")).toBe("/sessions/my%20app");
  expect(item.getAttribute("target")).toBe("_blank");
  expect(item.getAttribute("rel")).toBe("noopener");
});

test("the row's menu is used from the keyboard: the first item has the focus, arrows move, Esc closes", async () => {
  open("/sessions");
  const menu = await openRowMenu("lado");
  const [copy, tab] = within(menu).getAllByRole("menuitem");
  expect(document.activeElement).toBe(copy);
  fireEvent.keyDown(menu, { key: "ArrowDown" });
  expect(document.activeElement).toBe(tab);
  fireEvent.keyDown(menu, { key: "ArrowDown" });
  expect(document.activeElement).toBe(copy);
  fireEvent.keyDown(menu, { key: "ArrowUp" });
  expect(document.activeElement).toBe(tab);
  fireEvent.keyDown(menu, { key: "Escape" });
  expect(screen.queryByRole("menu")).toBeNull();
  expect(document.activeElement).toBe(within(await row("lado")).getByRole("button", { name: "Actions for lado" }));
});

test("a press outside the row's menu closes it", async () => {
  open("/sessions");
  await openRowMenu("lado");
  fireEvent.mouseDown(document.body);
  expect(screen.queryByRole("menu")).toBeNull();
});

function clipboard(writeText: ((text: string) => Promise<void>) | undefined) {
  Object.defineProperty(navigator, "clipboard", {
    value: writeText ? { writeText } : undefined,
    configurable: true,
  });
}

afterEach(() => {
  clipboard(undefined);
  unstubLegacyCopy();
});

test("Copy link copies the session page's address, without the token, and says so outside the menu", async () => {
  const writeText = vi.fn(async () => {});
  clipboard(writeText);
  sessions = [session("my app")];
  open("/sessions?token=secret");
  const menu = await openRowMenu("my app");
  fireEvent.click(within(menu).getByRole("menuitem", { name: "Copy link" }));
  const status = within(await row("my app")).getByRole("status");
  await waitFor(() => expect(status.textContent).toBe("Link copied"));
  expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/sessions/my%20app`);
  expect(screen.queryByRole("menu")).toBeNull();
});

test("Copy link in the row's menu copies without the Clipboard API, and the focus goes back to ⋯", async () => {
  const legacy = stubLegacyCopy();
  open("/sessions");
  const menu = await openRowMenu("lado");
  fireEvent.click(within(menu).getByRole("menuitem", { name: "Copy link" }));
  const status = within(await row("lado")).getByRole("status");
  await waitFor(() => expect(status.textContent).toBe("Link copied"));
  expect(legacy).toEqual([`${window.location.origin}/sessions/lado`]);
  expect(screen.queryByRole("menu")).toBeNull();
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.querySelector("body > textarea")).toBeNull();
  expect(document.activeElement).toBe(within(await row("lado")).getByRole("button", { name: "Actions for lado" }));
});

test.each([
  ["no Clipboard API and a refused legacy copy", undefined, false],
  ["a refused copy and a failing legacy copy", async () => Promise.reject(new Error("not allowed")), "throws"],
] as const)("with %s Copy link shows the address selected, to copy by hand", async (_, writeText, legacy) => {
  clipboard(writeText);
  stubLegacyCopy(legacy);
  open("/sessions");
  const menu = await openRowMenu("lado");
  fireEvent.click(within(menu).getByRole("menuitem", { name: "Copy link" }));
  const asked = await screen.findByRole("dialog", { name: "Link to lado" });
  expect(screen.queryByRole("menu")).toBeNull();
  const field = within(asked).getByRole("textbox", { name: "Link" }) as HTMLInputElement;
  expect(field.value).toBe(`${window.location.origin}/sessions/lado`);
  await waitFor(() => expect(document.activeElement).toBe(field)); // focused once it is drawn
  expect([field.selectionStart, field.selectionEnd]).toEqual([0, field.value.length]);
  expect(within(asked).getByText("Press ⌘C / Ctrl+C to copy")).toBeTruthy();
  expect(document.querySelector("body > textarea")).toBeNull();
  expect(within(await row("lado")).getByRole("status").textContent).toBe("");
  fireEvent.keyDown(asked, { key: "Escape" });
  expect(screen.queryByRole("dialog", { name: "Link to lado" })).toBeNull();
});

test("Stop from the head says what it does, stops the session and the page stays", async () => {
  answers["GET /api/sessions/lado/stop-preview"] = () =>
    json({ agents: ["supervisor", "w1"], dropped: 2, open_runs: ["feature/x"], worktrees: [] });
  answers["POST /api/sessions/lado/stop"] = () => json({ dropped: 2 });
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  fireEvent.click(within(head()).getByRole("button", { name: "Stop session…" }));
  const asked = await screen.findByRole("dialog", { name: 'Stop session "lado"?' });
  await within(asked).findByText("its 2 agents are closed");
  expect(within(asked).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
    "its 2 agents are closed",
    "2 messages they have not got are dropped",
    "branches, worktrees, 1 open run and the history stay",
    "you can resume it later",
  ]);
  fireEvent.click(within(asked).getByRole("button", { name: "Stop lado" }));
  await waitFor(() => expect(screen.queryByRole("dialog", { name: 'Stop session "lado"?' })).toBeNull());
  expect(calls.filter((c) => c.method === "POST").map((c) => c.path)).toEqual(["/api/sessions/lado/stop"]);
  expect(screen.getByRole("region", { name: "Session lado" })).toBeTruthy(); // the page stays
});

test("Stop of a session whose tmux session is gone is in its head beside Resume", async () => {
  sessions = [session("lado", { status: "tmux_gone" })];
  answers["GET /api/sessions/lado/stop-preview"] = () => json({ agents: [], dropped: 0, open_runs: [], worktrees: [] });
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  fireEvent.click(within(head()).getByRole("button", { name: "Stop session…" }));
  const asked = await screen.findByRole("dialog", { name: 'Stop session "lado"?' });
  expect(await within(asked).findByText("it has no agents to close")).toBeTruthy();
  fireEvent.keyDown(asked, { key: "Escape" });
  expect(screen.queryByRole("dialog", { name: 'Stop session "lado"?' })).toBeNull();
});

test("a refused stop says why in its popover", async () => {
  answers["GET /api/sessions/lado/stop-preview"] = () => json({ agents: [], dropped: 0, open_runs: [], worktrees: [] });
  answers["POST /api/sessions/lado/stop"] = () => json({ detail: 'session "lado" is stopped already' }, 400);
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  fireEvent.click(within(head()).getByRole("button", { name: "Stop session…" }));
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
  fireEvent.click(within(head()).getByRole("button", { name: "Forget…" }));
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

// The head's facts from GET /api/sessions/{name}/about: the repository, the kits' and the
// provider's versions (docs/design/ui.md, Session head)

function about(more: Partial<SessionAbout> = {}): SessionAbout {
  return {
    repos: [{ path: "/src/lado", remote: "git@github.com:ladohq/lado.git", branch: "main" }],
    kits: [
      { name: "team", version: "1.2.0", source: "user git@github.com:me/team@v1.2.0: /k/team", valid: true, problem: null },
      { name: "default", version: "0.25.0", source: "built-in: /lado/default", valid: true, problem: null },
    ],
    provider: provider("claude", { version: "2.1.300", tested_version: "2.1.300" }),
    ...more,
  };
}

const meta = () => head().querySelector(".session-meta") as HTMLElement;
const tip = () => screen.getByRole("tooltip").textContent;
const aboutCalls = () => calls.filter((call) => call.path.endsWith("/about")).length;

async function openHead(given: SessionAbout, mode: string | null = "plan") {
  sessions = [session("lado", { kits: ["team", "default"], permission_mode: mode })];
  abouts = { lado: given };
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  await waitFor(() => expect(meta().querySelector(".session-kit")).toBeTruthy());
}

test("with its about, the head's second line has the folder, the remote and branch, the kits and the CLI", async () => {
  await openHead(about());
  const facts = [...meta().children].map((fact) => fact.textContent);
  expect(facts).toEqual(["/src/lado", "github.com/ladohq/lado · main", "team, default", "claude"]);
  expect(within(meta()).getAllByRole("button").map((button) => button.getAttribute("aria-label"))).toEqual([
    "Copy path",
    "Copy URL",
  ]);
  expect(within(meta()).queryByRole("img", { name: "untested version" })).toBeNull();
});

test("Copy URL on the git icon copies the remote's whole URL", async () => {
  const writeText = vi.fn(async () => {});
  clipboard(writeText);
  await openHead(about());
  fireEvent.click(within(meta()).getByRole("button", { name: "Copy URL" }));
  await waitFor(() => expect(within(meta()).getByText("URL copied")).toBeTruthy());
  expect(writeText).toHaveBeenCalledWith("git@github.com:ladohq/lado.git");
});

test("Copy URL copies without the Clipboard API", async () => {
  const legacy = stubLegacyCopy();
  await openHead(about());
  fireEvent.click(within(meta()).getByRole("button", { name: "Copy URL" }));
  await waitFor(() => expect(within(meta()).getByText("URL copied")).toBeTruthy());
  expect(legacy).toEqual(["git@github.com:ladohq/lado.git"]);
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("the git fact is the branch alone without a remote, and none without either", async () => {
  await openHead(about({ repos: [{ path: "/src/lado", remote: null, branch: "trunk" }] }));
  expect(meta().querySelector(".session-git")?.textContent).toBe("trunk");
  expect(within(meta()).queryByRole("button", { name: "Copy URL" })).toBeNull();
  cleanup();
  await openHead(about({ repos: [{ path: "/src/lado", remote: null, branch: null }] }));
  expect(meta().querySelector(".session-git")).toBeNull();
});

test("the git fact's tooltip has the whole URL, the branch and the path", async () => {
  await openHead(about());
  fireEvent.focus(meta().querySelector(".session-git .session-hint") as HTMLElement);
  expect(tip()).toBe("git@github.com:ladohq/lado.gitbranch main · /src/lado");
});

test("each kit's tooltip has its version, where it is and that the next agent starts with it", async () => {
  const broken = { name: "default", version: "", source: "", valid: false, problem: 'kit "default" not found' };
  await openHead(about({ kits: [about().kits[0], broken] }));
  const [team, gone] = meta().querySelectorAll<HTMLElement>(".session-kit");
  fireEvent.focus(team);
  expect(tip()).toBe("team v1.2.0user git@github.com:me/team@v1.2.0: /k/teaminstalled now: the next agent starts with it");
  fireEvent.blur(team);
  fireEvent.focus(gone);
  expect(tip()).toBe('default: kit "default" not found');
});

test("the CLI's tooltip has its version; ! in the line only for an untested version", async () => {
  const untested = provider("claude", { version: "2.1.300", tested_version: "2.1.291", warning: "untested version" });
  await openHead(about({ provider: untested }), null);
  expect(within(meta()).getByRole("img", { name: "untested version" }).textContent).toBe("!");
  fireEvent.focus(meta().querySelector(".session-agent-cli .session-hint") as HTMLElement);
  expect(tip()).toBe("Claude Code 2.1.300tested with 2.1.291installed now: the next agent starts with it");
  cleanup();
  await openHead(about({ provider: provider("claude", { installed: false, version: "", detail: "`claude` not found on PATH" }) }), null);
  fireEvent.focus(meta().querySelector(".session-agent-cli .session-hint") as HTMLElement);
  expect(tip()).toBe("Claude Code not installed: `claude` not found on PATH");
});

test("the CLI's tooltip has the session's permission mode as its last line, when it has one", async () => {
  await openHead(about(), "bypassPermissions");
  expect(meta().querySelector(".session-agent-cli")?.textContent).toBe("claude");
  fireEvent.focus(meta().querySelector(".session-agent-cli .session-hint") as HTMLElement);
  const lines = () => [...screen.getByRole("tooltip").querySelectorAll(".tooltip-line")].map((line) => line.textContent);
  expect(lines()).toEqual(["Claude Code 2.1.300", "installed now: the next agent starts with it", "mode bypassPermissions"]);
  cleanup();
  await openHead(about({ provider: provider("claude", { installed: false, version: "", detail: "`claude` not found on PATH" }) }));
  fireEvent.focus(meta().querySelector(".session-agent-cli .session-hint") as HTMLElement);
  expect(lines()).toEqual(["Claude Code not installed: `claude` not found on PATH", "mode plan"]);
});

test("about is asked again when a kit changes, or the session's kits, and not for another change", async () => {
  await openHead(about());
  expect(aboutCalls()).toBe(1);
  const stream = FakeEventSource.all[0];
  const changed = (kits: string[]) => session("lado", { kits, permission_mode: "plan" });
  stream.send("change", { kind: "sessions", session: "lado", key: "", op: "update", item: changed(["team", "default"]) }, "11");
  stream.send("change", { kind: "kits", session: "", key: "team", op: "update", item: null }, "12");
  await waitFor(() => expect(aboutCalls()).toBe(2));
  stream.send("change", { kind: "sessions", session: "lado", key: "", op: "update", item: changed(["default"]) }, "13");
  await waitFor(() => expect(aboutCalls()).toBe(3));
});
