// Launch and session control (docs/design/ui.md, Launch and session control): the New
// session window, its Resume mode, the session's actions in its head, its list row's menu, Stop
// and Forget.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { StrictMode } from "react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type {
  CloneJob,
  CloneTarget,
  FolderInfo,
  KitInfo,
  ProviderInfo,
  RecentFolder,
  SessionAbout,
  SessionInfo,
} from "./api";
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
    stopped_at: null,
    title: null,
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
    problem_kind: null,
    hint: null,
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
let repos: string | null; // the repositories folder, LADO_REPOS
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
  repos = null;
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
      if (url.pathname === "/api/repos-folder") return json({ path: repos });
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
async function ready(path: string, more: Partial<FolderInfo> = {}, chosen = false) {
  folders[path] = folder(path, { provider: { name: "claude", reason: "only_installed" }, ...more });
  type(path);
  await screen.findByText(/✓ git repository · branch main/);
  await waitFor(() => expect(providerSelect().disabled).toBe(false));
  // The suggested provider is set in an effect after the folder's render: Start needs it.
  // `chosen`: the human picked one, which the suggestion leaves alone.
  const suggested = folders[path].provider?.name;
  if (suggested && !chosen) await waitFor(() => expect(providerSelect().value).toBe(suggested));
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
  await waitFor(() => expect(startButton().disabled).toBe(false));
});

const FIRST_COMMIT = "git add -A && git commit -m 'First commit'";

test("a folder the human can fix shows the reason, the hint's sentence and its command to copy", async () => {
  const writeText = vi.fn(async () => {});
  clipboard(writeText);
  await openLaunch();
  folders["/tmp/new"] = folder("/tmp/new", {
    ok: false,
    problem: "/tmp/new has no commits yet",
    problem_kind: "no_commits",
    hint: { text: "Make a first commit, in that folder:", command: FIRST_COMMIT },
  });
  type("/tmp/new");
  expect(await screen.findByText("/tmp/new has no commits yet")).toBeTruthy();
  expect(screen.getByText("Make a first commit, in that folder:")).toBeTruthy();
  expect(screen.getByText(FIRST_COMMIT).tagName).toBe("CODE");
  fireEvent.click(screen.getByRole("button", { name: "Copy command" }));
  await waitFor(() => expect(screen.getByText("Command copied").getAttribute("role")).toBe("status"));
  expect(writeText).toHaveBeenCalledWith(FIRST_COMMIT);
  expect(startButton().disabled).toBe(true);
});

test("when no copy works the hint's command is selected to copy by hand", async () => {
  clipboard(async () => Promise.reject(new Error("not allowed")));
  stubLegacyCopy(false);
  await openLaunch();
  folders["/tmp/new"] = folder("/tmp/new", {
    ok: false,
    problem: "/tmp/new has no commits yet",
    problem_kind: "no_commits",
    hint: { text: "Make a first commit, in that folder:", command: FIRST_COMMIT },
  });
  type("/tmp/new");
  fireEvent.click(await screen.findByRole("button", { name: "Copy command" }));
  await waitFor(() => expect(window.getSelection()?.toString()).toBe(FIRST_COMMIT));
  expect(screen.getByText("Press ⌘C / Ctrl+C to copy")).toBeTruthy();
});

test.each([
  ["missing", "/tmp/x does not exist"],
  ["git_refused", "git cannot read /tmp/x: fatal: detected dubious ownership in repository at '/tmp/x'"],
] as const)("a %s folder shows its reason and no hint", async (kind, problem) => {
  await openLaunch();
  folders["/tmp/x"] = folder("/tmp/x", { ok: false, problem, problem_kind: kind, root: null });
  type("/tmp/x");
  expect(await screen.findByText(problem)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Copy command" })).toBeNull();
  expect(document.querySelector(".folder-hint")).toBeNull();
  expect(startButton().disabled).toBe(true);
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

// The repositories folder (LADO_REPOS)

const REPOS = "/Users/me/repos";

test("an empty Where suggests the repositories folder's subfolders on focus, and a pick is its full path", async () => {
  repos = REPOS;
  folders[`${REPOS}/`] = folder(`${REPOS}/`, { ok: false, problem: "no", subfolders: ["api", "app", "site"] });
  await openLaunch();
  await waitFor(() => expect(where().placeholder).toBe(`${REPOS}/…`));
  expect(where().value).toBe("");
  await act(() => new Promise((resolve) => setTimeout(resolve, 50)));
  expect(calls.some((c) => c.path.startsWith("/api/folders?"))).toBe(false); // nothing before focus
  fireEvent.focus(where());
  const list = await screen.findByRole("listbox", { name: "Folders" });
  expect(within(list).getAllByRole("option").map((o) => o.textContent)).toEqual(["api/", "app/", "site/"]);
  fireEvent.mouseDown(within(list).getByRole("option", { name: "app/" }));
  expect(where().value).toBe(`${REPOS}/app`);
});

test("the Repositories folder row puts the folder in Where and lists it", async () => {
  repos = REPOS;
  folders[`${REPOS}/`] = folder(`${REPOS}/`, { ok: false, problem: "no", subfolders: ["api", "app", "site"] });
  const dialog = await openLaunch();
  const row = await within(dialog).findByText(/Repositories folder:/);
  fireEvent.click(within(row).getByRole("button", { name: REPOS }));
  expect(where().value).toBe(`${REPOS}/`);
  const list = await screen.findByRole("listbox", { name: "Folders" });
  expect(within(list).getAllByRole("option").map((o) => o.textContent)).toEqual(["api/", "app/", "site/"]);
  // The field has the focus: the keys pick, and leaving it closes the list.
  expect(document.activeElement).toBe(where());
  fireEvent.keyDown(where(), { key: "ArrowDown" });
  expect(within(list).getAllByRole("option")[0].getAttribute("aria-selected")).toBe("true");
  fireEvent.blur(where());
  expect(screen.queryByRole("listbox", { name: "Folders" })).toBeNull();
});

test("the repositories folder itself in Where is not checked as a folder for a session", async () => {
  repos = REPOS;
  const problem = `${REPOS} is not inside a git repository`;
  folders[`${REPOS}/`] = folder(`${REPOS}/`, { ok: false, problem, root: null, subfolders: ["api"] });
  folders[REPOS] = folders[`${REPOS}/`];
  const dialog = await openLaunch();
  fireEvent.click(within(await within(dialog).findByText(/Repositories folder:/)).getByRole("button", { name: REPOS }));
  await screen.findByRole("listbox", { name: "Folders" });
  for (const value of [`${REPOS}/`, REPOS]) {
    type(value);
    await act(() => new Promise((resolve) => setTimeout(resolve, 400))); // past the check's debounce
    expect(screen.queryByText(problem)).toBeNull();
    expect(screen.queryByText("checking…")).toBeNull();
  }
  type(`${REPOS}/api`);
  folders[`${REPOS}/api`] = folder(`${REPOS}/api`, { ok: false, problem: "api is not inside a git repository" });
  expect(await screen.findByText("api is not inside a git repository")).toBeTruthy();
});

test("a repositories folder of / is listed as /, never //", async () => {
  repos = "/";
  folders["/"] = folder("/", { ok: false, problem: "no", subfolders: ["srv"] });
  await openLaunch();
  await waitFor(() => expect(where().placeholder).toBe("/…"));
  fireEvent.focus(where());
  await screen.findByRole("listbox", { name: "Folders" });
  expect(calls.some((c) => c.path === "/api/folders?path=%2F")).toBe(true);
  expect(calls.some((c) => c.path.includes("%2F%2F"))).toBe(false);
});

test("Resume shows no Repositories folder row", async () => {
  repos = REPOS;
  sessions = [session("lado", { status: "stopped", repo: "/src/lado" })];
  open("/sessions/lado");
  fireEvent.click(await screen.findByRole("button", { name: "Resume…" }));
  const dialog = await screen.findByRole("dialog", { name: "Resume session" });
  await act(() => new Promise((resolve) => setTimeout(resolve, 50)));
  expect(within(dialog).queryByText(/Repositories folder:/)).toBeNull();
});

test("Clone into's placeholder is in the repositories folder", async () => {
  repos = REPOS;
  const dialog = await openLaunch();
  await waitFor(() => expect(where().placeholder).toBe(`${REPOS}/…`));
  fireEvent.click(within(dialog).getByRole("button", { name: "Clone from URL" }));
  fireEvent.change(screen.getByRole("textbox", { name: /Where/ }), {
    target: { value: "git@github.com:acme/app.git" },
  });
  const into = (await screen.findByRole("textbox", { name: "Clone into" })) as HTMLInputElement;
  expect(into.placeholder).toBe(`${REPOS}/<repo>`);
});

test("without a repositories folder an empty Where suggests nothing and has no row", async () => {
  const dialog = await openLaunch();
  expect(where().placeholder).toBe("~/projects/app");
  fireEvent.focus(where());
  await act(() => new Promise((resolve) => setTimeout(resolve, 50)));
  expect(screen.queryByRole("listbox", { name: "Folders" })).toBeNull();
  expect(calls.some((c) => c.path.startsWith("/api/folders?"))).toBe(false);
  expect(within(dialog).queryByText(/Repositories folder:/)).toBeNull();
  fireEvent.click(within(dialog).getByRole("button", { name: "Clone from URL" }));
  fireEvent.change(screen.getByRole("textbox", { name: /Where/ }), {
    target: { value: "git@github.com:acme/app.git" },
  });
  const into = (await screen.findByRole("textbox", { name: "Clone into" })) as HTMLInputElement;
  expect(into.placeholder).toBe("~/lado/<repo>");
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
  await waitFor(() => expect(startButton().disabled).toBe(false));
});

test("without a suggestion no provider is chosen and Start is off until the human picks one", async () => {
  await openLaunch();
  await ready("/src/app", { provider: null });
  expect(providerSelect().value).toBe("");
  expect(screen.getByText("choose the agent CLI for this session")).toBeTruthy();
  expect(startButton().disabled).toBe(true);
  fireEvent.change(providerSelect(), { target: { value: "kilo" } });
  expect(providerSelect().value).toBe("kilo");
  await waitFor(() => expect(startButton().disabled).toBe(false));
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
  await ready("/src/other", { provider: { name: "kilo", reason: "only_installed" } }, true);
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
  await waitFor(() => expect(startButton().disabled).toBe(false));
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
  expect((field.closest("details") as HTMLDetailsElement).open).toBe(true);
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

// First message (openspec change first-message)

const STARTED = { resumed: false, changes: [], problems: [], lead: "", warnings: [] };
const LIMITS = {
  extensions: {},
  text_types: [],
  agent_images: [],
  max_size: 1000,
  max_files: 3,
  image_limit: 500,
  image_max_side: 8000,
  max_message: 20,
};
const FIRST_ROW = "First message to the supervisor (optional)";
const firstField = () => screen.getByRole("textbox", { name: "First message" }) as HTMLTextAreaElement;
const firstRow = () => screen.getByText(/^First message to the supervisor/).closest("details") as HTMLDetailsElement;

function writeFirst(text: string) {
  const row = firstRow();
  if (!row.open) fireEvent.click(row.querySelector("summary")!);
  fireEvent.change(firstField(), { target: { value: text } });
}

test("the first message row is folded when the window opens", async () => {
  await openLaunch();
  expect(screen.getByText(FIRST_ROW)).toBeTruthy();
  expect(firstRow().open).toBe(false);
  // It comes before Advanced.
  const rows = [...document.querySelectorAll(".launch-dialog details summary")].map((s) => s.textContent);
  expect(rows).toEqual([FIRST_ROW, "Advanced: switch off agents, skills, MCP servers or flows"]);
});

test("a first message is sent with the start", async () => {
  answers["POST /api/sessions"] = () => json({ session: session("app", { repo: "/src/app" }), ...STARTED });
  await openLaunch();
  await ready("/src/app");
  writeFirst("  Take LAD-19\n");
  expect(screen.getByText(/sent to the supervisor as your message once it starts/)).toBeTruthy();
  fireEvent.click(startButton());
  await screen.findByRole("region", { name: "Session app" });
  const sent = calls.find((c) => c.method === "POST" && c.path === "/api/sessions")!;
  expect(sent.body).toMatchObject({ prompt: "Take LAD-19" });
});

test("an empty first message is not sent", async () => {
  answers["POST /api/sessions"] = () => json({ session: session("app", { repo: "/src/app" }), ...STARTED });
  await openLaunch();
  await ready("/src/app");
  writeFirst("  \n ");
  fireEvent.click(startButton());
  await screen.findByRole("region", { name: "Session app" });
  const sent = calls.find((c) => c.method === "POST" && c.path === "/api/sessions")!;
  expect(sent.body).not.toHaveProperty("prompt");
});

test("folded with text the row shows its first line", async () => {
  await openLaunch();
  writeFirst("\n  Line one  \nLine two");
  fireEvent.click(firstRow().querySelector("summary")!);
  expect(firstRow().querySelector("summary")!.textContent).toBe("First message to the supervisor: Line one");
});

test("a first message over the limit keeps Start off, also folded", async () => {
  answers["GET /api/limits"] = () => json(LIMITS);
  await openLaunch();
  await ready("/src/app");
  writeFirst("x".repeat(21));
  expect(await screen.findByText("21 characters, the limit is 20")).toBeTruthy();
  expect(startButton().disabled).toBe(true);
  fireEvent.click(firstRow().querySelector("summary")!);
  expect(startButton().disabled).toBe(true);
  fireEvent.click(firstRow().querySelector("summary")!);
  fireEvent.change(firstField(), { target: { value: "x".repeat(20) } });
  await waitFor(() => expect(startButton().disabled).toBe(false));
});

test("the Resume window sends its first message", async () => {
  sessions = [session("lado", { status: "stopped", repo: "/src/lado" })];
  answers["POST /api/sessions/lado/resume"] = () => json({ session: session("lado"), ...STARTED, resumed: true });
  open("/sessions/lado");
  fireEvent.click(await screen.findByRole("button", { name: "Resume…" }));
  const dialog = await screen.findByRole("dialog", { name: "Resume session" });
  expect(firstRow().open).toBe(false);
  writeFirst("Continue the review");
  const resume = within(dialog).getByRole("button", { name: "Resume session" }) as HTMLButtonElement;
  await waitFor(() => expect(resume.disabled).toBe(false));
  fireEvent.click(resume);
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Resume session" })).toBeNull());
  expect(calls.find((c) => c.method === "POST")!.body).toEqual({ prompt: "Continue the review" });
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
] as const)("a %s session's head has Rename session, Copy path, Copy link and the icons %j, each with its tooltip, and no menu", async (status, labels) => {
  sessions = [session("lado", { status })];
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  const buttons = within(head()).getAllByRole("button");
  expect(buttons.map((button) => button.getAttribute("aria-label"))).toEqual(["Rename session", "Copy path", "Copy link", ...labels]);
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
  "a %s session's row has only its menu, of Rename…, Copy link and Open in new tab",
  async (status) => {
    sessions = [session("lado", { status })];
    localStorage.setItem("lado.stoppedSessions", "open");
    open("/sessions");
    const buttons = within(await row("lado")).getAllByRole("button");
    expect(buttons.map((button) => button.getAttribute("aria-label"))).toEqual(["Actions for lado"]);
    const menu = await openRowMenu("lado");
    expect(within(menu).getAllByRole("menuitem").map((item) => item.textContent)).toEqual(["Rename…", "Copy link", "Open in new tab"]);
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
  const [rename, copy, tab] = within(menu).getAllByRole("menuitem");
  expect(document.activeElement).toBe(rename);
  fireEvent.keyDown(menu, { key: "ArrowDown" });
  expect(document.activeElement).toBe(copy);
  fireEvent.keyDown(menu, { key: "ArrowDown" });
  expect(document.activeElement).toBe(tab);
  fireEvent.keyDown(menu, { key: "ArrowDown" });
  expect(document.activeElement).toBe(rename);
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

// Clone from URL (openspec change clone-from-url)

const URL_ = "git@github.com:ladohq/marketplace.git";
const INTO = "/home/me/lado/marketplace";

function target(more: Partial<CloneTarget> = {}): CloneTarget {
  return {
    path: INTO,
    state: "new",
    text: "a new folder",
    origin: null,
    branch: null,
    suggestion: null,
    default_name: "marketplace",
    name_state: "free",
    provider: { name: "claude", reason: "only_installed" },
    ...more,
  };
}

function job(more: Partial<CloneJob> = {}): CloneJob {
  return {
    id: "j1",
    url: URL_,
    path: INTO,
    branch: "main",
    state: "running",
    progress: null,
    error: null,
    seconds: 0,
    ...more,
  };
}

const remote = (branches = ["main", "develop", "release/1.2"], fallback: string | null = "main") => () =>
  json({ url: URL_, branches, default: fallback });

const urlInput = () => screen.getByRole("textbox", { name: /Where/ }) as HTMLInputElement;
const cloneButton = () => screen.getByRole("button", { name: "Clone and start" }) as HTMLButtonElement;
const branchSelect = () => screen.getByRole("combobox", { name: "Branch" }) as HTMLSelectElement;

async function cloneSource(url = URL_) {
  const dialog = await openLaunch();
  fireEvent.click(within(dialog).getByRole("button", { name: "Clone from URL" }));
  fireEvent.change(urlInput(), { target: { value: url } });
  return dialog;
}

// The form ready to clone: branches listed, the folder new, claude chosen.
async function cloneReady() {
  answers["GET /api/clone-target"] = () => json(target());
  answers["POST /api/remote-branches"] = remote();
  const dialog = await cloneSource();
  await screen.findByText("✓ repository found · 3 branches");
  await waitFor(() => expect(cloneButton().disabled).toBe(false));
  return dialog;
}

test("branches come by themselves, the default one chosen and marked; Clone and start waits for them", async () => {
  let listed: () => void = () => {};
  const pending = new Promise<void>((resolve) => (listed = resolve));
  answers["GET /api/clone-target"] = () => json(target());
  answers["POST /api/remote-branches"] = async () => {
    await pending;
    return remote()();
  };
  const dialog = await cloneSource();
  expect(within(dialog).getByRole("button", { name: "Clone from URL" }).getAttribute("aria-pressed")).toBe("true");
  expect(await screen.findByText("fetching branches…")).toBeTruthy();
  expect(await screen.findByText("✓ a new folder")).toBeTruthy();
  expect((screen.getByRole("textbox", { name: "Clone into" }) as HTMLInputElement).value).toBe(INTO);
  expect(cloneButton().disabled).toBe(true);
  await act(async () => listed());
  await screen.findByText("✓ repository found · 3 branches");
  expect(branchSelect().value).toBe("main");
  expect([...branchSelect().options].map((one) => one.textContent)).toEqual([
    "main (default)",
    "develop",
    "release/1.2",
  ]);
  expect(screen.getByText("the repository's default branch")).toBeTruthy();
  expect((screen.getByRole("textbox", { name: "Name" }) as HTMLInputElement).value).toBe("marketplace");
  await waitFor(() => expect(cloneButton().disabled).toBe(false));
  const asked = calls.filter((c) => c.path === "/api/remote-branches");
  expect(asked).toEqual([{ method: "POST", path: "/api/remote-branches", body: { url: URL_ } }]);
  const checked = calls.find((c) => c.path.startsWith("/api/clone-target"))!;
  expect(new URL(checked.path, "http://lado.test").searchParams.get("url")).toBe(URL_);
});

test("a listing failure shows under the URL with its hint and Copy, and Clone and start stays off", async () => {
  answers["GET /api/clone-target"] = () => json(target());
  answers["POST /api/remote-branches"] = () =>
    json(
      {
        detail: {
          message: `cannot read ${URL_}: github.com refused this machine's ssh key (fatal: x)`,
          kind: "ssh_denied",
          hint: { text: "Check that this machine's ssh key is added to your account on github.com:", command: "ssh -T git@github.com" },
        },
      },
      400,
    );
  await cloneSource();
  expect(await screen.findByText(/github.com refused this machine's ssh key/)).toBeTruthy();
  expect(screen.getByText("ssh -T git@github.com").tagName).toBe("CODE");
  expect(screen.getByRole("button", { name: "Copy command" })).toBeTruthy();
  expect(cloneButton().disabled).toBe(true);
});

test("a clone of this repository there offers Use this clone, which switches to Folder and clones nothing", async () => {
  answers["GET /api/clone-target"] = () =>
    json(
      target({
        state: "same_repo",
        text: `${INTO} is already a clone of this repository (origin ${URL_}), on branch develop`,
        origin: URL_,
        branch: "develop",
      }),
    );
  answers["POST /api/remote-branches"] = remote();
  folders[INTO] = folder(INTO);
  const dialog = await cloneSource();
  expect(await screen.findByText(/is already a clone of this repository/)).toBeTruthy();
  expect(screen.getByText(/LADO will use it as it is: no clone, no pull, no branch switch/)).toBeTruthy();
  fireEvent.click(await screen.findByRole("button", { name: "Use this clone" }));
  expect(within(dialog).getByRole("button", { name: "Folder" }).getAttribute("aria-pressed")).toBe("true");
  expect(where().value).toBe(INTO);
  expect(await screen.findByText(/✓ git repository · branch main/)).toBeTruthy();
  expect(calls.some((c) => c.path === "/api/clones")).toBe(false);
});

test("a clone of another repository there says so with a free folder, and Clone and start is off", async () => {
  const text = `${INTO} is a clone of another repository (origin git@github.com:acme/marketplace.git): choose another folder, e.g. /home/me/lado/ladohq-marketplace`;
  answers["GET /api/clone-target"] = () => json(target({ state: "other_repo", text }));
  answers["POST /api/remote-branches"] = remote();
  await cloneSource();
  expect(await screen.findByText(text)).toBeTruthy();
  await screen.findByText("✓ repository found · 3 branches");
  expect(cloneButton().disabled).toBe(true);
});

test("a long branch list is a field that filters as the human types", async () => {
  const many = ["main", ...Array.from({ length: 40 }, (_, i) => `feature/f${String(i).padStart(2, "0")}`)];
  answers["GET /api/clone-target"] = () => json(target());
  answers["POST /api/remote-branches"] = remote(many);
  await cloneSource();
  await screen.findByText("✓ repository found · 41 branches");
  const field = screen.getByRole("combobox", { name: "Branch" }) as HTMLInputElement;
  expect(field.tagName).toBe("INPUT");
  expect(field.value).toBe("main");
  fireEvent.change(field, { target: { value: "f1" } });
  const listed = await screen.findByRole("listbox", { name: "Branches" });
  expect(within(listed).getAllByRole("option").map((one) => one.textContent)).toEqual(
    Array.from({ length: 10 }, (_, i) => `feature/f1${i}`),
  );
  fireEvent.mouseDown(within(listed).getByText("feature/f12"));
  expect(field.value).toBe("feature/f12");
});

test("the clone shows its progress, the window cannot be closed, and Cancel clone stops it", async () => {
  let current = job({ branch: "develop" });
  answers["POST /api/clones"] = () => json(current);
  answers["GET /api/clones/j1"] = () => json(current);
  answers["DELETE /api/clones/j1"] = () => {
    current = job({ branch: "develop", state: "cancelled", seconds: 7 });
    return json(current);
  };
  const dialog = await cloneReady();
  fireEvent.change(branchSelect(), { target: { value: "develop" } });
  fireEvent.click(cloneButton());
  expect(await screen.findByRole("button", { name: "Cloning…" })).toBeTruthy();
  const sent = calls.find((c) => c.method === "POST" && c.path === "/api/clones")!;
  expect(sent.body).toEqual({ url: URL_, path: INTO, branch: "develop" });
  current = job({
    branch: "develop",
    progress: { phase: "Receiving objects", percent: 45, detail: "12.30 MiB | 2.10 MiB/s" },
    seconds: 6,
  });
  expect(await screen.findByText("Receiving objects")).toBeTruthy();
  expect(screen.getByText(/· 45%/)).toBeTruthy();
  expect(screen.getByText("12.30 MiB | 2.10 MiB/s")).toBeTruthy();
  expect(screen.getByText(`cloning branch develop into ${INTO} · 0:06`)).toBeTruthy();
  expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("45");
  expect((within(dialog).getByRole("button", { name: "Close" }) as HTMLButtonElement).disabled).toBe(true);
  expect(urlInput().disabled).toBe(true);
  fireEvent.keyDown(dialog, { key: "Escape" });
  expect(screen.getByRole("dialog", { name: "New session" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Cancel clone" }));
  await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.path === "/api/clones/j1")).toBe(true));
  await waitFor(() => expect(cloneButton().disabled).toBe(false));
  expect(screen.getByText("the clone was cancelled")).toBeTruthy();
  expect(calls.some((c) => c.path === "/api/sessions" && c.method === "POST")).toBe(false);
});

test("a finished clone starts the session in the cloned folder and opens it", async () => {
  answers["POST /api/clones"] = () => json(job());
  answers["GET /api/clones/j1"] = () => json(job({ state: "done", seconds: 3 }));
  answers["POST /api/sessions"] = () =>
    json({ session: session("marketplace", { repo: INTO }), resumed: false, changes: [], problems: [], lead: "", warnings: [] });
  await cloneReady();
  fireEvent.click(cloneButton());
  expect(await screen.findByRole("region", { name: "Session marketplace" })).toBeTruthy();
  const sent = calls.find((c) => c.method === "POST" && c.path === "/api/sessions")!;
  expect(sent.body).toEqual({
    where: { kind: "folder", path: INTO },
    name: "marketplace",
    kits: ["default"],
    provider: "claude",
  });
});

test("Clone and start carries the first message to the start after the clone", async () => {
  answers["POST /api/clones"] = () => json(job());
  answers["GET /api/clones/j1"] = () => json(job({ state: "done", seconds: 3 }));
  answers["POST /api/sessions"] = () => json({ session: session("marketplace", { repo: INTO }), ...STARTED });
  await cloneReady();
  writeFirst("Read the README first");
  fireEvent.click(cloneButton());
  expect(await screen.findByRole("region", { name: "Session marketplace" })).toBeTruthy();
  const sent = calls.find((c) => c.method === "POST" && c.path === "/api/sessions")!;
  expect(sent.body).toMatchObject({ prompt: "Read the README first" });
});

test("a failed clone shows why with its hint and keeps the form", async () => {
  answers["POST /api/clones"] = () => json(job());
  answers["GET /api/clones/j1"] = () =>
    json(
      job({
        state: "failed",
        error: { message: `cannot clone ${URL_}: no branch dev (fatal: x)`, kind: "no_branch", hint: null },
      }),
    );
  const dialog = await cloneReady();
  fireEvent.click(cloneButton());
  expect((await within(dialog).findByRole("alert")).textContent).toBe(`cannot clone ${URL_}: no branch dev (fatal: x)`);
  await waitFor(() => expect(cloneButton().disabled).toBe(false));
});

test("a name taken after the clone switches the window to Folder with the clone and the refusal", async () => {
  answers["POST /api/clones"] = () => json(job());
  answers["GET /api/clones/j1"] = () => json(job({ state: "done" }));
  answers["POST /api/sessions"] = () =>
    json(
      {
        detail: {
          message: 'session "marketplace" exists already (running, in /src/other)',
          status: "running",
          repo: "/src/other",
        },
      },
      409,
    );
  folders[INTO] = folder(INTO);
  const dialog = await cloneReady();
  fireEvent.click(cloneButton());
  expect((await within(dialog).findByRole("alert")).textContent).toContain('session "marketplace" exists already');
  expect(within(dialog).getByRole("button", { name: "Folder" }).getAttribute("aria-pressed")).toBe("true");
  expect(where().value).toBe(INTO);
});

test("a poll that fails is asked again: the clone goes on, Cancel clone stays (F3)", async () => {
  let polls = 0;
  answers["POST /api/clones"] = () => json(job());
  answers["GET /api/clones/j1"] = () => {
    polls += 1;
    if (polls === 1) return json({ detail: "server busy" }, 503);
    if (polls === 2) return json(job({ seconds: 1 }));
    return json(job({ state: "done", seconds: 2 }));
  };
  answers["POST /api/sessions"] = () =>
    json({ session: session("marketplace", { repo: INTO }), resumed: false, changes: [], problems: [], lead: "", warnings: [] });
  const dialog = await cloneReady();
  fireEvent.click(cloneButton());
  await waitFor(() => expect(polls).toBeGreaterThanOrEqual(2), { timeout: 3000 });
  expect(within(dialog).queryByRole("alert")).toBeNull();
  expect(screen.getByRole("button", { name: "Cancel clone" })).toBeTruthy();
  expect(await screen.findByRole("region", { name: "Session marketplace" }, { timeout: 3000 })).toBeTruthy();
});

test("a clone job the server no longer knows ends the clone with why", async () => {
  answers["POST /api/clones"] = () => json(job());
  answers["GET /api/clones/j1"] = () => json({ detail: "no clone job j1" }, 404);
  const dialog = await cloneReady();
  fireEvent.click(cloneButton());
  expect((await within(dialog).findByRole("alert", {}, { timeout: 3000 })).textContent).toBe("no clone job j1");
  await waitFor(() => expect(cloneButton().disabled).toBe(false));
});

test("Enter in the long branch field with no branch picked neither clones nor changes the branch (F5)", async () => {
  const many = ["main", ...Array.from({ length: 40 }, (_, i) => `feature/f${String(i).padStart(2, "0")}`)];
  answers["GET /api/clone-target"] = () => json(target());
  answers["POST /api/remote-branches"] = remote(many);
  await cloneSource();
  await screen.findByText("✓ repository found · 41 branches");
  await waitFor(() => expect(cloneButton().disabled).toBe(false));
  const field = screen.getByRole("combobox", { name: "Branch" }) as HTMLInputElement;
  fireEvent.change(field, { target: { value: "feat" } });
  // Not prevented, the browser's implicit submission would clone the default branch.
  expect(fireEvent.keyDown(field, { key: "Enter" })).toBe(false);
  expect(field.value).toBe("feat");
  expect(calls.some((c) => c.path === "/api/clones")).toBe(false);
  fireEvent.change(field, { target: { value: "feature/f07" } });
  fireEvent.keyDown(field, { key: "Enter" });
  fireEvent.blur(field);
  expect(field.value).toBe("feature/f07");
});

test("the clone's form does not take kits and mode from a folder typed before (F7)", async () => {
  recent = [
    {
      path: "/src/app",
      session: session("app", { repo: "/src/app", kits: ["team"], provider: "kilo", permission_mode: "plan" }),
    },
  ];
  folders["/src/app"] = folder("/src/app", { provider: { name: "kilo", reason: "last_session" } });
  answers["GET /api/clone-target"] = () => json(target());
  answers["POST /api/remote-branches"] = remote();
  const dialog = await openLaunch();
  fireEvent.click(await screen.findByRole("button", { name: "/src/app" }));
  const kitsField = screen.getByRole("group", { name: "Kits" });
  await waitFor(() => expect(within(kitsField).getByText("team")).toBeTruthy());
  fireEvent.click(within(dialog).getByRole("button", { name: "Clone from URL" }));
  fireEvent.change(urlInput(), { target: { value: URL_ } });
  await screen.findByText("✓ repository found · 3 branches");
  await waitFor(() => expect(within(kitsField).getByText("default")).toBeTruthy());
  expect(within(kitsField).queryByText("team")).toBeNull();
  expect(screen.queryByText("from the last session of this folder")).toBeNull();
  expect((screen.getByRole("combobox", { name: "Permission mode" }) as HTMLSelectElement).value).toBe("default");
});

test("Resume it is off while a clone runs (F10)", async () => {
  answers["GET /api/clone-target"] = () => json(target({ name_state: "stopped_here" }));
  answers["POST /api/remote-branches"] = remote();
  answers["POST /api/clones"] = () => json(job());
  answers["GET /api/clones/j1"] = () => json(job());
  await cloneSource();
  await screen.findByText("✓ repository found · 3 branches");
  await waitFor(() => expect(cloneButton().disabled).toBe(false));
  fireEvent.click(cloneButton());
  await screen.findByRole("button", { name: "Cloning…" });
  expect((screen.getByRole("button", { name: "Resume it" }) as HTMLButtonElement).disabled).toBe(true);
});

test("Cancel clone pressed as the clone ends starts no session; the clone is offered as a folder (F11)", async () => {
  let release: () => void = () => {};
  const pending = new Promise<void>((resolve) => (release = resolve));
  answers["POST /api/clones"] = () => json(job());
  answers["GET /api/clones/j1"] = async () => {
    await pending;
    return json(job({ state: "done" }));
  };
  answers["DELETE /api/clones/j1"] = () => json(job({ state: "done" }));
  folders[INTO] = folder(INTO);
  const dialog = await cloneReady();
  fireEvent.click(cloneButton());
  fireEvent.click(await screen.findByRole("button", { name: "Cancel clone" }));
  await act(async () => release());
  expect(await screen.findByText(`the clone ended before Cancel clone; it is in ${INTO}`, {}, { timeout: 3000 })).toBeTruthy();
  expect(within(dialog).getByRole("button", { name: "Folder" }).getAttribute("aria-pressed")).toBe("true");
  expect(where().value).toBe(INTO);
  expect(calls.some((c) => c.method === "POST" && c.path === "/api/sessions")).toBe(false);
});

test("after a listing failed, a new URL shows fetching branches… while it waits (F12)", async () => {
  answers["GET /api/clone-target"] = () => json(target());
  answers["POST /api/remote-branches"] = () => json({ detail: { message: "cannot read x: y", kind: "git_failed", hint: null } }, 400);
  await cloneSource();
  await screen.findByText("cannot read x: y");
  expect(branchSelect().options[0].textContent).toBe("—");
  fireEvent.change(urlInput(), { target: { value: "git@github.com:ladohq/other.git" } });
  expect(branchSelect().options[0].textContent).toBe("fetching branches…");
});

test("under StrictMode the clone is still asked for until it ends (F6)", async () => {
  answers["GET /api/clone-target"] = () => json(target());
  answers["POST /api/remote-branches"] = remote();
  answers["POST /api/clones"] = () => json(job());
  answers["GET /api/clones/j1"] = () => json(job({ state: "done" }));
  answers["POST /api/sessions"] = () =>
    json({ session: session("marketplace", { repo: INTO }), resumed: false, changes: [], problems: [], lead: "", warnings: [] });
  render(
    <StrictMode>
      <MemoryRouter initialEntries={["/sessions"]}>
        <App />
      </MemoryRouter>
    </StrictMode>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Launch" }));
  const dialog = await screen.findByRole("dialog", { name: "New session" });
  fireEvent.click(within(dialog).getByRole("button", { name: "Clone from URL" }));
  fireEvent.change(urlInput(), { target: { value: URL_ } });
  await screen.findByText("✓ repository found · 3 branches");
  await waitFor(() => expect(cloneButton().disabled).toBe(false));
  fireEvent.click(cloneButton());
  expect(await screen.findByRole("region", { name: "Session marketplace" }, { timeout: 3000 })).toBeTruthy();
});

test("a window whose page goes away during a clone cancels it at once with a beacon", async () => {
  const beacon = vi.fn(() => true);
  Object.defineProperty(navigator, "sendBeacon", { value: beacon, configurable: true });
  let state: CloneJob["state"] = "running";
  answers["POST /api/clones"] = () => json(job());
  answers["GET /api/clones/j1"] = () => json(job({ state }));
  answers["POST /api/sessions"] = () =>
    json({ session: session("marketplace", { repo: INTO }), resumed: false, changes: [], problems: [], lead: "", warnings: [] });
  await cloneReady();
  window.dispatchEvent(new Event("pagehide"));
  expect(beacon).not.toHaveBeenCalled(); // no clone yet
  // The page may go away at the very DOM change that shows the clone running, or its end,
  // before any later task of React's scheduler: the beacons are counted right there.
  let atRunning: number | null = null;
  let atEnd: number | null = null;
  const leaveAt = new MutationObserver(() => {
    if (atRunning === null && screen.queryByRole("button", { name: "Cancel clone" })) {
      window.dispatchEvent(new Event("pagehide"));
      atRunning = beacon.mock.calls.length;
    }
    if (atEnd === null && screen.queryByRole("region", { name: "Session marketplace" })) {
      window.dispatchEvent(new Event("pagehide"));
      atEnd = beacon.mock.calls.length;
    }
  });
  leaveAt.observe(document.body, { childList: true, subtree: true, attributes: true, characterData: true });
  try {
    fireEvent.click(cloneButton());
    await screen.findByRole("button", { name: "Cancel clone" });
    expect(atRunning).toBe(1);
    expect(beacon).toHaveBeenCalledWith("/api/clones/j1/cancel");
    window.dispatchEvent(new Event("pagehide"));
    expect(beacon).toHaveBeenCalledTimes(2);
    state = "done";
    await screen.findByRole("region", { name: "Session marketplace" }, { timeout: 3000 });
    expect(atEnd).toBe(2);
    window.dispatchEvent(new Event("pagehide"));
    expect(beacon.mock.calls).toEqual([["/api/clones/j1/cancel"], ["/api/clones/j1/cancel"]]);
  } finally {
    leaveAt.disconnect();
  }
});

test("a clone that ended while the window was away is offered as a folder, not refused (F18)", async () => {
  let cloned = false;
  answers["POST /api/clones"] = () => json(job());
  answers["GET /api/clones/j1"] = () => {
    cloned = true; // done and dropped by the server while the window did not ask
    return json({ detail: "no clone job j1" }, 404);
  };
  folders[INTO] = folder(INTO);
  const dialog = await cloneReady();
  answers["GET /api/clone-target"] = () =>
    json(
      cloned
        ? target({ state: "same_repo", text: `${INTO} is already a clone of this repository`, branch: "main" })
        : target(),
    );
  fireEvent.click(cloneButton());
  expect(
    await screen.findByText(`the clone ended while this window was away; it is in ${INTO}`, {}, { timeout: 3000 }),
  ).toBeTruthy();
  expect(within(dialog).getByRole("button", { name: "Folder" }).getAttribute("aria-pressed")).toBe("true");
  expect(where().value).toBe(INTO);
  expect(within(dialog).queryByRole("alert")).toBeNull();
});
