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
  ModelChoices,
  ModeWordsInfo,
  ProjectLaunch,
  ProviderInfo,
  RecentFolder,
  ScratchTarget,
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
    project: null,
    model: null,
    model_missing: false,
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
    scratch: false,
    ...more,
  };
}

// Each mode in its provider's words (lado.providers' permission_mode_words).
const WORDS: Record<string, ModeWordsInfo> = {
  default: {
    value: "default",
    title: "Ask before changes (recommended)",
    summary: "Asks before changes",
    description: "Asks before it edits files or runs commands.",
    risky: false,
  },
  acceptEdits: {
    value: "acceptEdits",
    title: "Edit files without asking",
    summary: "Edits without asking",
    description: "Still asks before commands.",
    risky: false,
  },
  plan: {
    value: "plan",
    title: "Plan only, no changes",
    summary: "Plan only",
    description: "Reads and proposes a plan; changes nothing.",
    risky: false,
  },
  dontAsk: { value: "dontAsk", title: "dontAsk", summary: "dontAsk", description: "", risky: false },
  bypassPermissions: {
    value: "bypassPermissions",
    title: "Full access, never ask ⚠",
    summary: "Full access ⚠",
    description: "Does anything, deleting files too. Only for a folder you can afford to lose.",
    risky: true,
  },
};

function provider(name: string, more: Partial<ProviderInfo> = {}): ProviderInfo {
  const modes = more.permission_modes ?? (name === "claude" ? ["default", "acceptEdits", "plan", "dontAsk"] : ["default", "plan"]);
  return {
    name,
    title: name === "claude" ? "Claude Code" : "Kilo CLI",
    permission_modes: modes,
    mode_words: modes.map((one) => WORDS[one] ?? { value: one, title: one, summary: one, description: "", risky: false }),
    install_hint: `install ${name}`,
    installed: true,
    version: name === "claude" ? "2.1.287" : "7.2.1",
    detail: "",
    tested_version: "",
    warning: "",
    login_missing: false,
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
let workspace: { path: string; made: boolean }; // LADO_REPOS, else ~/workspace
let kits: KitInfo[];
let abouts: Record<string, SessionAbout>; // by session; none: 404
let providers: (project: string | null) => Promise<ProviderInfo[]>; // GET /api/providers?project=
// GET /api/model-settings and POST /api/session-model/check.
let modelEntries: { models: { cli: string }[]; servers: unknown[]; defaults: unknown[] };
let sessionCheck: (asked: unknown) => unknown;

// As lado.model_check words them: Claude Code has aliases and no list; Kilo a list.
function modelsOf(name: string, model: string): Pick<ModelChoices, "aliases" | "models" | "why" | "check"> {
  const title = name === "claude" ? "Claude Code" : "Kilo CLI";
  const aliases = name === "claude" ? ["sonnet", "opus"] : [];
  const models = name === "claude" ? null : ["kilo/small", "kilo/large"];
  const why = name === "claude" ? "Claude Code gives no list of models beyond its aliases" : "";
  const verdict: Omit<ModelChoices["check"], "field" | "name"> = !model
    ? { kind: "default", text: `empty: ${title}'s default model; type or pick one of its models` }
    : aliases.includes(model)
      ? { kind: "ok", text: `an alias of ${title}` }
      : models === null
        ? { kind: "warn", text: `${why}: LADO cannot check ${model}; a wrong name stops its agents at their first turn` }
        : models.includes(model)
          ? { kind: "ok", text: `in ${title}'s list of models` }
          : { kind: "refused", text: `${model} is not in ${title}'s list of models; kilo models prints the list` };
  return { aliases, models, why, check: { ...verdict, field: "", name: "" } };
}
let answers: Record<string, () => Response | Promise<Response>>; // "METHOD path" -> the server's answer
let calls: Call[];
// GET /api/project-launch: Shop with backend and frontend, its last session in backend
let projectLaunch: (project: string | null, repo: string | null) => ProjectLaunch;

const shopRepo = (name: string) => ({ name, path: `/ws/projects/shop/${name}`, branch: "main", remote: null });

function shopLaunch(project: string | null, repo: string | null): ProjectLaunch {
  const projects = [
    { id: "acme", title: "ACME CRM", folder: "/ws/projects/acme", found: true, repos: 0, running: [] },
    { id: "shop", title: "Shop", folder: "/ws/projects/shop", found: true, repos: 2, running: [] },
  ];
  if (project === "acme") {
    const none = { default_name: null, name_state: null, provider: null, last: null };
    return { projects, project: "acme", repos: [], repo: null, root: null, ...none };
  }
  const chosen = repo ?? "backend";
  const last =
    chosen === "backend"
      ? session("shop-backend", {
          repo: "/real/projects/shop/backend",
          status: "stopped",
          kits: ["team"],
          provider: "kilo",
          permission_mode: "plan",
          project: "shop",
        })
      : null;
  return {
    projects,
    project: "shop",
    repos: [shopRepo("backend"), shopRepo("frontend")],
    repo: chosen,
    // git's root, links resolved: the workspace /ws is a link to /real
    root: `/real/projects/shop/${chosen}`,
    default_name: `shop-${chosen}`,
    name_state: last ? "stopped_here" : "free",
    provider: last ? { name: "kilo", reason: "last_session" } : null,
    last,
  };
}

const HOME_WORKSPACE = "/Users/ann/workspace"; // the default, not made unless a test says so
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });

beforeEach(() => {
  localStorage.clear();
  stubDialogs();
  sessions = [session("lado")];
  folders = {};
  recent = [];
  workspace = { path: HOME_WORKSPACE, made: false };
  kits = [kit("default"), kit("team")];
  abouts = {};
  providers = async () => [provider("claude"), provider("kilo")];
  modelEntries = { models: [], servers: [], defaults: [] };
  sessionCheck = () => ({
    kind: "ok",
    text: "in its list of models",
    field: "",
    name: "",
    retry: false,
    short: "",
    peek: "",
    warnings: [],
    server: null,
  });
  answers = {};
  calls = [];
  projectLaunch = shopLaunch;
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
      if (url.pathname === "/api/scratch-target") {
        return json(scratchTarget(url.searchParams.get("text") ?? "", url.searchParams.get("path")));
      }
      if (url.pathname === "/api/repos-folder") return json(workspace);
      if (url.pathname === "/api/project-launch") {
        return json(projectLaunch(url.searchParams.get("project"), url.searchParams.get("repo")));
      }
      if (url.pathname === "/api/kits") return json(kits);
      if (url.pathname === "/api/providers") return json(await providers(url.searchParams.get("project")));
      const choices = /^\/api\/providers\/([^/]+)\/model-choices$/.exec(url.pathname);
      if (choices) {
        const cli = decodeURIComponent(choices[1]);
        const listed = modelsOf(cli, url.searchParams.get("model") ?? "");
        const external = modelEntries.models.filter((one) => one.cli === cli);
        return json({
          ...listed,
          external,
          other_name: listed.models === null,
          whole_process: false,
          read_again: false,
        });
      }
      if (url.pathname === "/api/model-settings") return json(modelEntries);
      if (url.pathname === "/api/session-model/check") return json(sessionCheck(body));
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

const placeBox = () => screen.getByRole("combobox", { name: "Where" }) as HTMLInputElement;

// Where's list, opened from the keyboard; `name` picks one of its options.
async function pickPlace(name: string | RegExp) {
  const box = placeBox();
  if (box.getAttribute("aria-expanded") !== "true") fireEvent.keyDown(box, { key: "ArrowDown" });
  const list = await screen.findByRole("listbox", { name: "Places" });
  fireEvent.mouseDown(within(list).getByRole("option", { name }));
}

// The New session window, on Other folder… unless `otherFolder` is false: with no recent
// places it opens on New empty folder.
async function openLaunch(otherFolder = true) {
  open();
  fireEvent.click(within(rail()).getByRole("button", { name: "New session" }));
  const dialog = await screen.findByRole("dialog", { name: "New session" });
  if (otherFolder) {
    await waitFor(() => expect(placeBox().value).not.toBe("…"));
    await pickPlace("Other folder…");
  }
  return dialog;
}

const rail = () => screen.getByRole("navigation", { name: "Sections" });

// Other folder…'s path field.
const where = () => screen.getByRole("combobox", { name: "Folder" }) as HTMLInputElement;

function type(path: string) {
  fireEvent.change(where(), { target: { value: path } });
}

// The footer's main button, whatever it names.
const startButton = () => document.querySelector(".launch-buttons .primary") as HTMLButtonElement;
const footerText = () => document.querySelector(".launch-buttons")?.textContent ?? "";

// Team opened, for its fields.
function openTeam() {
  const change = screen.queryByRole("button", { name: "Change" });
  if (change) fireEvent.click(change);
}

const teamSummary = () => document.querySelector(".team-sum")?.textContent ?? "";

// Team's fields, also while it is folded (hidden).
const providerSelect = () => screen.getByRole("combobox", { name: "Agent", hidden: true }) as HTMLSelectElement;
const nameField = () => screen.getByRole("textbox", { name: "Session name", hidden: true }) as HTMLInputElement;
const kitsGroup = () => screen.getByRole("group", { name: /^Team setup/, hidden: true });

const modeChosen = () => (document.querySelector(".mode-list input:checked") as HTMLInputElement | null)?.value;

function chooseMode(value: string) {
  fireEvent.click(document.querySelector(`.mode-list input[value="${value}"]`)!);
}

// A folder that will do, with claude suggested unless `more` says otherwise; the providers
// answered.
async function ready(path: string, more: Partial<FolderInfo> = {}, chosen = false) {
  folders[path] = folder(path, { provider: { name: "claude", reason: "only_installed" }, ...more });
  type(path);
  await screen.findByText(/✓ Ready · branch main/);
  await waitFor(() => expect(providerSelect().disabled).toBe(false));
  // The suggested provider is set in an effect after the folder's render: Start needs it.
  // `chosen`: the human picked one, which the suggestion leaves alone.
  const suggested = folders[path].provider?.name;
  if (suggested && !chosen) await waitFor(() => expect(providerSelect().value).toBe(suggested));
}

// New session on the rail and "+"

test("New session is on the rail right after Home, not in the top bar, and + opens the same window", async () => {
  open();
  const items = within(rail())
    .getAllByRole("listitem")
    .map((item) => item.textContent);
  expect(items.slice(0, 3)).toEqual(["Home", "New session", "Needs you"]);
  const top = document.querySelector(".topbar")!;
  expect(within(top as HTMLElement).queryByRole("button", { name: "New session" })).toBeNull();
  const plus = screen.getAllByRole("button", { name: "New session" }).find((one) => one.classList.contains("plus"))!;
  fireEvent.click(plus);
  const dialog = await screen.findByRole("dialog", { name: "New session" });
  expect(dialog.hasAttribute("open")).toBe(true);
  fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("dialog", { name: "New session" })).toBeNull();
});

// The order and the opening (capability new-session-window)

const WEBAPP = "/Users/ann/workspace/webapp";

function recentFolder(path: string, more: Partial<SessionInfo> = {}, project: RecentFolder["project"] = null): RecentFolder {
  const name = path.split("/").pop()!;
  return { path, session: session(name, { repo: path, status: "stopped", stopped_at: ago(2 * 86400_000), ...more }), project };
}

test("the window asks Where, then Task, then shows Team, with no source switch and no Advanced", async () => {
  recent = [recentFolder(WEBAPP)];
  folders[WEBAPP] = folder(WEBAPP, { provider: { name: "claude", reason: "last_session" } });
  open();
  fireEvent.click(within(rail()).getByRole("button", { name: "New session" }));
  const dialog = await screen.findByRole("dialog", { name: "New session" });
  const labels = [...dialog.querySelectorAll(".launch-body > .field > .field-label, .launch-team .team-head .field-label")]
    .map((one) => one.textContent?.trim());
  expect(labels).toEqual(["Where", "Task", "Team"]);
  expect(within(dialog).queryByRole("group", { name: "Source" })).toBeNull();
  expect(within(dialog).queryByText(/Advanced/)).toBeNull();
  expect(within(dialog).queryByText(/First message/)).toBeNull();
});

test("the window opens on the last place with the focus in Task, and the button names the place", async () => {
  recent = [recentFolder(WEBAPP, { status: "running", stopped_at: null }), recentFolder("/src/old")];
  folders[WEBAPP] = folder(WEBAPP, { provider: { name: "claude", reason: "last_session" } });
  open();
  fireEvent.click(within(rail()).getByRole("button", { name: "New session" }));
  await waitFor(() => expect(placeBox().value).toBe("webapp"));
  expect(screen.getByText(WEBAPP, { selector: ".place-path" })).toBeTruthy();
  await screen.findByText("✓ Ready · branch main");
  await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("textbox", { name: "Task" })));
  await waitFor(() => expect(startButton().textContent).toBe("Start in webapp"));
  expect(calls.some((c) => c.path === `/api/folders?path=${encodeURIComponent(WEBAPP)}`)).toBe(true);
});

test("the first session ever opens on New empty folder, with no message above Where", async () => {
  const dialog = await openLaunch(false);
  await waitFor(() => expect(placeBox().value).toBe("New empty folder"));
  expect(dialog.querySelector(".launch-body")!.firstElementChild!.textContent).toMatch(/^Where/);
  await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("textbox", { name: "Folder name" })));
});

test("Where's list has Recent with a project's badge, then Somewhere else", async () => {
  recent = [
    recentFolder(WEBAPP),
    recentFolder("/ws/projects/shop/backend", { project: "shop" }, { id: "shop", title: "Shop", repo: "backend" }),
  ];
  folders[WEBAPP] = folder(WEBAPP);
  await openLaunch(false);
  await waitFor(() => expect(placeBox().value).toBe("webapp"));
  fireEvent.keyDown(placeBox(), { key: "ArrowDown" });
  const list = await screen.findByRole("listbox", { name: "Places" });
  expect([...list.querySelectorAll(".place-group")].map((one) => one.textContent)).toEqual(["Recent", "Somewhere else"]);
  const options = within(list).getAllByRole("option").map((one) => one.querySelector(".place-text")!.textContent);
  expect(options).toEqual([`webapp${WEBAPP}`, "backendProject Shop", "Other folder…", "Clone from URL…", "New empty folder…", "Project…"]);
  expect(placeBox().getAttribute("aria-expanded")).toBe("true");
  expect(within(list).getAllByRole("option")[0].getAttribute("aria-selected")).toBe("true");
});

test("the list is used from the keyboard: arrows, Enter picks, the first Esc closes only the list", async () => {
  recent = [recentFolder(WEBAPP), recentFolder("/src/notes")];
  folders[WEBAPP] = folder(WEBAPP);
  folders["/src/notes"] = folder("/src/notes");
  const dialog = await openLaunch(false);
  await waitFor(() => expect(placeBox().value).toBe("webapp"));
  fireEvent.keyDown(placeBox(), { key: "ArrowDown" });
  await screen.findByRole("listbox", { name: "Places" });
  fireEvent.keyDown(placeBox(), { key: "ArrowDown" });
  fireEvent.keyDown(placeBox(), { key: "Enter" });
  expect(placeBox().value).toBe("notes");
  expect(screen.queryByRole("listbox", { name: "Places" })).toBeNull();
  fireEvent.keyDown(placeBox(), { key: "n" });
  expect(placeBox().value).toBe("n");
  const list = await screen.findByRole("listbox", { name: "Places" });
  expect(within(list).getAllByRole("option")[0].textContent).toContain("notes");
  fireEvent.keyDown(placeBox(), { key: "Escape" });
  expect(screen.queryByRole("listbox", { name: "Places" })).toBeNull();
  expect(dialog.hasAttribute("open")).toBe(true);
  expect(screen.getByRole("dialog", { name: "New session" })).toBeTruthy();
});

test("a typed path lists Use folder first, then its parent's subfolders; Enter on one puts it in Where", async () => {
  folders["~/workspace/"] = folder("~/workspace/", { ok: false, problem: "no", subfolders: ["webapp", "notes"] });
  folders["~/workspace/webapp"] = folder("~/workspace/webapp");
  await openLaunch(false);
  await waitFor(() => expect(placeBox().value).toBe("New empty folder"));
  fireEvent.change(placeBox(), { target: { value: "~/workspace/we" } });
  const list = await screen.findByRole("listbox", { name: "Places" });
  await waitFor(() =>
    expect(within(list).getAllByRole("option").map((o) => o.textContent)).toEqual(["Use folder ~/workspace/we", "webapp/"]),
  );
  fireEvent.keyDown(placeBox(), { key: "ArrowDown" });
  fireEvent.keyDown(placeBox(), { key: "Enter" });
  expect(placeBox().value).toBe("webapp");
  expect(await screen.findByText("✓ Ready · branch main")).toBeTruthy();
});

test("a recent project repository opens on its project: the badge, the button names the project", async () => {
  recent = [recentFolder("/ws/projects/shop/backend", { project: "shop" }, { id: "shop", title: "Shop", repo: "backend" })];
  await openLaunch(false);
  await waitFor(() => expect(placeBox().value).toBe("backend"));
  expect(screen.getByText("Project Shop", { selector: ".place-text .place-badge" })).toBeTruthy();
  expect(calls.some((c) => c.path === "/api/project-launch?project=shop&repo=backend")).toBe(true);
  await waitFor(() => expect(startButton().textContent).toMatch(/Shop$/));
  fireEvent.click(screen.getByRole("button", { name: "About Where" }));
  expect(screen.getByText("backend is a repository of the project Shop: the team works with Shop's keys and settings.")).toBeTruthy();
});

// A stopped session of the place: Resume beside a new start (D3, D5)

test("a stopped session of the place gives the free name and two buttons; the blue one follows Task", async () => {
  sessions = [session("webapp", { status: "stopped", repo: WEBAPP, stopped_at: ago(2 * 86400_000) })];
  recent = [recentFolder(WEBAPP)];
  folders[WEBAPP] = folder(WEBAPP, {
    default_name: "webapp",
    free_name: "webapp-2",
    name_state: "stopped_here",
    provider: { name: "claude", reason: "last_session" },
  });
  await openLaunch(false);
  const line = await screen.findByText(/stopped here/);
  expect(line.closest(".place-line")!.textContent).toBe("✓ Ready · branch main · Session webapp stopped here 2 d ago");
  const resume = await screen.findByRole("button", { name: "Resume webapp" });
  const fresh = screen.getByRole("button", { name: "Start new session webapp-2" }) as HTMLButtonElement;
  expect(teamSummary()).toContain("Name webapp-2");
  expect(resume.className).toBe("primary");
  expect(fresh.className).toBe("quiet peer");
  const order = () => [...document.querySelectorAll(".launch-buttons button")].map((one) => one.textContent);
  const before = order();
  fireEvent.change(screen.getByRole("textbox", { name: "Task" }), { target: { value: "Add a contact form" } });
  expect(resume.className).toBe("quiet peer");
  expect(fresh.className).toBe("primary");
  expect(order()).toEqual(before);
  answers["POST /api/sessions"] = () => json({ session: session("webapp-2", { repo: WEBAPP }), ...STARTED });
  await waitFor(() => expect(fresh.disabled).toBe(false));
  fireEvent.click(fresh);
  await screen.findByRole("region", { name: "Session webapp-2" });
  expect(calls.find((c) => c.method === "POST")!.body).toMatchObject({
    where: { kind: "folder", path: WEBAPP },
    name: "webapp-2",
    prompt: "Add a contact form",
  });
});

test("Resume <name> in New session resumes the stopped session with the task", async () => {
  sessions = [session("webapp", { status: "stopped", repo: WEBAPP })];
  recent = [recentFolder(WEBAPP)];
  folders[WEBAPP] = folder(WEBAPP, {
    default_name: "webapp",
    free_name: "webapp-2",
    name_state: "stopped_here",
    provider: { name: "claude", reason: "last_session" },
  });
  answers["POST /api/sessions/webapp/resume"] = () => json({ session: session("webapp"), ...STARTED, resumed: true });
  await openLaunch(false);
  const resume = (await screen.findByRole("button", { name: "Resume webapp" })) as HTMLButtonElement;
  fireEvent.change(screen.getByRole("textbox", { name: "Task" }), { target: { value: "Go on" } });
  await waitFor(() => expect(resume.disabled).toBe(false));
  fireEvent.click(resume);
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "New session" })).toBeNull());
  expect(calls.find((c) => c.method === "POST")).toMatchObject({ path: "/api/sessions/webapp/resume", body: { prompt: "Go on" } });
});

test("Resume beside a new start sends only what the human changed, not the window's other values", async () => {
  // The stopped session has its own kits, agent CLI and Switch off; the folder's last session,
  // which the window's Team comes from, is another one.
  const stopped = session("webapp", {
    status: "stopped",
    repo: WEBAPP,
    kits: ["team"],
    provider: "kilo",
    permission_mode: "plan",
    without: ["agent:reviewer"],
  });
  sessions = [stopped];
  recent = [recentFolder(WEBAPP, { name: "webapp-3", kits: ["default"], provider: "claude", permission_mode: null })];
  folders[WEBAPP] = folder(WEBAPP, {
    default_name: "webapp",
    free_name: "webapp-2",
    name_state: "stopped_here",
    provider: { name: "claude", reason: "last_session" },
  });
  answers["POST /api/sessions/webapp/resume"] = () => json({ session: session("webapp"), ...STARTED, resumed: true });
  await openLaunch(false);
  const resume = (await screen.findByRole("button", { name: "Resume webapp" })) as HTMLButtonElement;
  await waitFor(() => expect(providerSelect().value).toBe("claude"));
  await waitFor(() => expect(resume.disabled).toBe(false));
  fireEvent.click(resume);
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "New session" })).toBeNull());
  expect(calls.find((c) => c.method === "POST")!.body).toEqual({});
});

test("Resume beside a new start sends the fields the human changed", async () => {
  sessions = [session("webapp", { status: "stopped", repo: WEBAPP, without: ["agent:reviewer"] })];
  recent = [recentFolder(WEBAPP)];
  folders[WEBAPP] = folder(WEBAPP, {
    default_name: "webapp",
    free_name: "webapp-2",
    name_state: "stopped_here",
    provider: { name: "claude", reason: "last_session" },
  });
  answers["POST /api/sessions/webapp/resume"] = () => json({ session: session("webapp"), ...STARTED, resumed: true });
  await openLaunch(false);
  const resume = (await screen.findByRole("button", { name: "Resume webapp" })) as HTMLButtonElement;
  openTeam();
  fireEvent.change(screen.getByRole("textbox", { name: "Switch off" }), { target: { value: "skill:x" } });
  chooseMode("plan");
  await waitFor(() => expect(resume.disabled).toBe(false));
  fireEvent.click(resume);
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "New session" })).toBeNull());
  expect(calls.find((c) => c.method === "POST")!.body).toEqual({ without: ["skill:x"], permission_mode: "plan" });
});

test("a name a running session has gives the free name and one button", async () => {
  sessions = [session("webapp", { repo: WEBAPP })];
  recent = [recentFolder(WEBAPP, { status: "running", stopped_at: null })];
  folders[WEBAPP] = folder(WEBAPP, { default_name: "webapp", free_name: "webapp-2", name_state: "running" });
  await openLaunch(false);
  await screen.findByText("✓ Ready · branch main");
  expect(teamSummary()).toContain("Name webapp-2");
  expect(screen.queryByRole("button", { name: "Resume webapp" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "About Team" }));
  expect(document.body.textContent).toContain('"webapp" is taken by another session.');
});

test("a 409 after the press opens Team, puts the focus on Session name and offers the next name", async () => {
  answers["POST /api/sessions"] = () =>
    json({ detail: { message: 'session "app" exists already (stopped, in /src/app)', status: "stopped", repo: "/src/app" } }, 409);
  await openLaunch();
  await ready("/src/app");
  fireEvent.click(startButton());
  await screen.findByText('session "app" exists already (stopped, in /src/app)');
  await waitFor(() => expect(teamIsOpen()).toBe(true));
  await waitFor(() => expect(document.activeElement).toBe(nameField()));
  expect(nameField().getAttribute("aria-invalid")).toBe("true");
  expect(nameField().getAttribute("aria-describedby")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Use app-2" }));
  expect(nameField().value).toBe("app-2");
});

// Where: Other folder…

const OUTSIDE =
  "Outside the workspace (/Users/ann/projects): this folder is only in the container, your computer does not see it or the agents' work in it";

test("a folder outside the workspace in a container: a warning after the check mark, Start stays", async () => {
  await openLaunch();
  await ready("/home/lado/app", { warning: OUTSIDE });
  const ok = screen.getByText(/✓ Ready · branch main/);
  const warned = screen.getByText(`⚠ ${OUTSIDE}`);
  expect(warned.className).toBe("field-note warn");
  expect(ok.compareDocumentPosition(warned) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  await waitFor(() => expect(startButton().disabled).toBe(false));
});

test("the kits list that does not load is a warning in Team, not a refusal: Start stays on", async () => {
  answers["GET /api/kits"] = () => json({ detail: "the kits do not load" }, 500);
  await openLaunch();
  await ready("/Users/ann/projects/app");
  const warned = await screen.findByText("the kits do not load");
  expect(warned.className).toBe("field-note warn");
  expect(warned.closest(".launch-team")).toBeTruthy();
  await waitFor(() => expect(startButton().disabled).toBe(false));
});

test("the folder is checked by the server and its reason shown; Start stays off until it will do", async () => {
  await openLaunch();
  expect(startButton().disabled).toBe(true);
  await waitFor(() => expect(footerText()).toContain("To start: choose a place"));
  folders["/tmp/x"] = folder("/tmp/x", { ok: false, problem: "/tmp/x is not inside a git repository", root: null });
  type("/tmp/x");
  expect(await screen.findByText("/tmp/x is not inside a git repository")).toBeTruthy();
  expect(startButton().disabled).toBe(true);
  await ready("/src/lado");
  await waitFor(() => expect(startButton().disabled).toBe(false));
  expect(startButton().textContent).toBe("Start in lado");
  expect(footerText()).not.toContain("To start");
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
  expect(where().getAttribute("aria-describedby")).toBe(screen.getByText("/tmp/new has no commits yet").closest(".place-notes")!.id);
  fireEvent.click(screen.getByRole("button", { name: "Copy command" }));
  await waitFor(() => expect(screen.getByText("Command copied").getAttribute("role")).toBe("status"));
  expect(writeText).toHaveBeenCalledWith(FIRST_COMMIT);
  expect(startButton().disabled).toBe(true);
});

const IN_SHOP = "/ws/projects/shop/frontend belongs to the project Shop: start a session in the project";
const SHOP_HINT = { text: "Start a session in the project:", command: "lado start --project shop --repo frontend" };

test("a folder inside a project is refused in the refusal box with the project's command, and Start is off", async () => {
  await openLaunch();
  folders["/ws/projects/shop/frontend"] = folder("/ws/projects/shop/frontend", {
    ok: false,
    problem: IN_SHOP,
    root: null,
    branch: null,
    problem_kind: "in_project",
    hint: SHOP_HINT,
    default_name: null,
    name_state: null,
  });
  type("/ws/projects/shop/frontend");
  const box = (await screen.findByText(IN_SHOP)).closest(".field-note.bad") as HTMLElement;
  expect(within(box).getByText("Start a session in the project:")).toBeTruthy();
  expect(within(box).getByText(SHOP_HINT.command).tagName).toBe("CODE");
  expect(within(box).getByRole("button", { name: "Copy command" })).toBeTruthy();
  expect(within(box).queryByRole("button", { name: "Start from scratch here" })).toBeNull();
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

test("a recent folder's last session gives kits, agent and mode", async () => {
  recent = [recentFolder("/src/app", { kits: ["team"], provider: "kilo", permission_mode: "plan" })];
  folders["/src/app"] = folder("/src/app", { provider: { name: "kilo", reason: "last_session" } });
  await openLaunch(false);
  await waitFor(() => expect(placeBox().value).toBe("app"));
  await screen.findByText(/✓ Ready/);
  await waitFor(() => expect(teamSummary()).toContain("Setup team"));
  await waitFor(() => expect(providerSelect().value).toBe("kilo"));
  expect(teamSummary()).toContain("Agent Kilo CLI");
  expect(teamSummary()).toContain("Permissions Plan only");
  expect(modeChosen()).toBe("plan");
  fireEvent.click(screen.getByRole("button", { name: "About Team" }));
  expect(screen.getByText("As in the last session in this folder.")).toBeTruthy();
});

// The workspace (LADO_REPOS, else ~/workspace)

const REPOS = "/Users/me/repos";

test("an empty folder field suggests the workspace's subfolders on focus, and a pick is its full path", async () => {
  workspace = { path: REPOS, made: true };
  folders[`${REPOS}/`] = folder(`${REPOS}/`, { ok: false, problem: "no", subfolders: ["api", "app", "site"] });
  await openLaunch();
  await waitFor(() => expect(where().placeholder).toBe(`${REPOS}/…`));
  expect(where().value).toBe("");
  fireEvent.focus(where());
  const list = await screen.findByRole("listbox", { name: "Folders" });
  expect(within(list).getAllByRole("option").map((o) => o.textContent)).toEqual(["api/", "app/", "site/"]);
  fireEvent.mouseDown(within(list).getByRole("option", { name: "app/" }));
  expect(where().value).toBe(`${REPOS}/app`);
});

test("the workspace itself in the folder field is not checked as a folder for a session", async () => {
  workspace = { path: REPOS, made: true };
  const problem = `${REPOS} is not inside a git repository`;
  folders[`${REPOS}/`] = folder(`${REPOS}/`, { ok: false, problem, root: null, subfolders: ["api"] });
  folders[REPOS] = folders[`${REPOS}/`];
  await openLaunch();
  await waitFor(() => expect(where().placeholder).toBe(`${REPOS}/…`));
  for (const value of [`${REPOS}/`, REPOS]) {
    type(value);
    await act(() => new Promise((resolve) => setTimeout(resolve, 400))); // past the check's debounce
    expect(screen.queryByText(problem)).toBeNull();
    expect(screen.queryByText("checking…")).toBeNull();
  }
  folders[`${REPOS}/api`] = folder(`${REPOS}/api`, { ok: false, problem: "api is not inside a git repository" });
  type(`${REPOS}/api`);
  expect(await screen.findByText("api is not inside a git repository")).toBeTruthy();
});

test("a workspace of / is listed as /, never //", async () => {
  workspace = { path: "/", made: true };
  folders["/"] = folder("/", { ok: false, problem: "no", subfolders: ["srv"] });
  await openLaunch();
  await waitFor(() => expect(where().placeholder).toBe("/…"));
  fireEvent.focus(where());
  await screen.findByRole("listbox", { name: "Folders" });
  expect(calls.some((c) => c.path === "/api/folders?path=%2F")).toBe(true);
  expect(calls.some((c) => c.path.includes("%2F%2F"))).toBe(false);
});

test("a workspace not made yet: its placeholders and no suggestions", async () => {
  await openLaunch();
  await waitFor(() => expect(where().placeholder).toBe(`${HOME_WORKSPACE}/…`));
  fireEvent.focus(where());
  await act(() => new Promise((resolve) => setTimeout(resolve, 50)));
  expect(screen.queryByRole("listbox", { name: "Folders" })).toBeNull();
  expect(calls.some((c) => c.path.startsWith("/api/folders?"))).toBe(false);
  expect(screen.queryByText(/Workspace:/)).toBeNull();
  await pickPlace("Clone from URL…");
  fireEvent.change(screen.getByRole("textbox", { name: "Repository URL" }), {
    target: { value: "git@github.com:acme/app.git" },
  });
  const into = (await screen.findByRole("textbox", { name: "Clone into" })) as HTMLInputElement;
  expect(into.placeholder).toBe(`${HOME_WORKSPACE}/<repo>`);
  await pickPlace("New empty folder…");
  fireEvent.click(screen.getByRole("button", { name: "About Folder name" }));
  expect(screen.getByText(`LADO creates it in ${HOME_WORKSPACE}.`)).toBeTruthy();
});

// Team (capability new-session-window)

test("Team is one line; Change opens Session name, Agent, Team setup, Permissions, Model and Switch off", async () => {
  await openLaunch();
  await ready("/src/lado");
  expect(teamSummary()).toBe("Setup defaultAgent Claude CodePermissions Asks before changesName lado");
  const change = screen.getByRole("button", { name: "Change" });
  expect(change.getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(change);
  const body = document.querySelector(".team-body") as HTMLElement;
  expect(body.hidden).toBe(false);
  expect(screen.getByRole("button", { name: "Hide" }).getAttribute("aria-expanded")).toBe("true");
  expect([...body.querySelectorAll(".field-label, label, legend")].map((one) => one.textContent?.trim()).filter(Boolean)).toEqual(
    expect.arrayContaining(["Session name", "Agent", "Team setup", "Permissions", "Model", "Switch off"]),
  );
  expect(nameField().value).toBe("lado");
});

test("Permissions are the agent's words: the chosen one's description and always the risky one's", async () => {
  providers = async () => [provider("claude", { permission_modes: ["default", "plan", "manual", "bypassPermissions"] })];
  await openLaunch();
  await ready("/src/lado");
  openTeam();
  const rows = [...document.querySelectorAll(".mode-list li")].map((one) => one.textContent);
  expect(rows).toEqual([
    "Ask before changes (recommended)Asks before it edits files or runs commands.",
    "Plan only, no changes",
    "manual",
    "Full access, never ask ⚠Does anything, deleting files too. Only for a folder you can afford to lose.",
  ]);
  expect(modeChosen()).toBe("default");
  chooseMode("plan");
  expect(document.querySelector(".mode-list li.on")!.textContent).toBe("Plan only, no changesReads and proposes a plan; changes nothing.");
  fireEvent.click(screen.getByRole("button", { name: "About Permissions" }));
  expect(screen.getByText("plan", { selector: "code" })).toBeTruthy();
});

test("an agent with no modes shows No permission modes., and Team names no Permissions", async () => {
  providers = async () => [provider("claude", { permission_modes: [] })];
  await openLaunch();
  await ready("/src/lado");
  expect(teamSummary()).not.toContain("Permissions");
  openTeam();
  expect(screen.getByText("No permission modes.")).toBeTruthy();
});

test("kits start as the default kit; an invalid kit cannot be added and says why", async () => {
  kits = [kit("default", { description: "a supervisor that delegates" }), kit("team"), kit("broken", { valid: false, problem: "bad" })];
  await openLaunch();
  await ready("/src/lado");
  openTeam();
  const field = kitsGroup();
  expect(within(field).getByText("default")).toBeTruthy();
  const add = (await within(field).findByRole("combobox", { name: "Add setup" })) as HTMLSelectElement;
  const broken = within(add).getByRole("option", { name: /broken/ }) as HTMLOptionElement;
  expect(broken.disabled).toBe(true);
  expect(broken.textContent).toContain("invalid: run lado kits check broken");
  fireEvent.click(screen.getByRole("button", { name: "About Team setup" }));
  expect(screen.getByText("default: a supervisor that delegates")).toBeTruthy();
  fireEvent.change(add, { target: { value: "team" } });
  expect(within(field).getByText("team")).toBeTruthy();
  fireEvent.click(within(field).getByRole("button", { name: "Remove default" }));
  expect(within(field).queryByText("default")).toBeNull();
});

test("without a kit Start stays off and the footer says why", async () => {
  await openLaunch();
  await ready("/src/lado");
  openTeam();
  fireEvent.click(within(kitsGroup()).getByRole("button", { name: "Remove default" }));
  expect(await screen.findByText("a session needs at least one kit")).toBeTruthy();
  expect(startButton().disabled).toBe(true);
  await waitFor(() => expect(footerText()).toContain("To start: choose a team setup."));
});

test("providers show checking while their CLIs are asked, a missing one is off, a warning is shown", async () => {
  let release: (found: ProviderInfo[]) => void = () => {};
  providers = () => new Promise((resolve) => (release = resolve));
  await openLaunch();
  openTeam();
  const select = providerSelect();
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
  const kilo = within(select).getByRole("option", { name: /Kilo CLI/ }) as HTMLOptionElement;
  expect(kilo.disabled).toBe(true);
  expect(kilo.textContent).toBe("Kilo CLI · not installed");
  expect(within(select).getByRole("option", { name: "Claude Code 2.1.288" })).toBeTruthy();
  expect(screen.getByText(/LADO is tested with Claude Code 2\.1\.287/)).toBeTruthy();
});

test("the folder's suggested agent is chosen; Team's info says where it comes from", async () => {
  await openLaunch();
  await ready("/src/app", { provider: { name: "kilo", reason: "last_any" } });
  await waitFor(() => expect(providerSelect().value).toBe("kilo"));
  expect(teamSummary()).toContain("Agent Kilo CLI");
  fireEvent.click(screen.getByRole("button", { name: "About Team" }));
  expect(screen.getByText("Agent as in your last session; setup and permissions are LADO's defaults.")).toBeTruthy();
  await waitFor(() => expect(startButton().disabled).toBe(false));
});

test("without a suggestion no agent is chosen; the footer's link opens Team on Agent", async () => {
  await openLaunch();
  await ready("/src/app", { provider: null });
  expect(providerSelect().value).toBe("");
  expect(teamSummary()).toContain("Agent choose…");
  expect(startButton().disabled).toBe(true);
  await waitFor(() => expect(footerText()).toContain("To start: choose an agent."));
  fireEvent.click(screen.getByRole("button", { name: "choose an agent" }));
  await waitFor(() => expect(teamIsOpen()).toBe(true));
  await waitFor(() => expect(document.activeElement).toBe(providerSelect()));
  fireEvent.change(providerSelect(), { target: { value: "kilo" } });
  await waitFor(() => expect(startButton().disabled).toBe(false));
});

test("a provider not installed cannot be chosen, even when suggested", async () => {
  providers = async () => [provider("claude"), provider("kilo", { installed: false, version: "" })];
  await openLaunch();
  await ready("/src/app", { provider: { name: "kilo", reason: "last_session" } });
  await waitFor(() => expect(providerSelect().disabled).toBe(false));
  const kilo = within(providerSelect()).getByRole("option", { name: /Kilo CLI/ }) as HTMLOptionElement;
  expect(kilo.disabled).toBe(true);
  expect(startButton().disabled).toBe(true);
  await waitFor(() => expect(teamIsOpen()).toBe(true)); // its refusal in sight
});

test("the human's own choice of agent is kept when the folder changes", async () => {
  await openLaunch();
  await ready("/src/app", { provider: { name: "kilo", reason: "last_session" } });
  await waitFor(() => expect(providerSelect().value).toBe("kilo"));
  fireEvent.change(providerSelect(), { target: { value: "claude" } });
  await ready("/src/other", { provider: { name: "kilo", reason: "only_installed" } }, true);
  expect(providerSelect().value).toBe("claude");
});

test("a mode the new agent does not support goes back to the default, and the window says so", async () => {
  await openLaunch();
  await ready("/src/app");
  openTeam();
  chooseMode("dontAsk");
  fireEvent.change(providerSelect(), { target: { value: "kilo" } });
  expect(modeChosen()).toBe("default");
  expect(screen.getByText("Kilo CLI has no such mode: set to the default")).toBeTruthy();
});

// A CLI without the login its agents need (openspec change refuse-start-without-login)

const NO_LOGIN = "Claude Code is not logged in: its agents cannot start.";

test("a CLI without its login is greyed out, not taken from the suggestion, and Start stays off", async () => {
  providers = async () => [provider("claude", { login_missing: true }), provider("kilo")];
  await openLaunch();
  await ready("/src/app", { provider: { name: "claude", reason: "last_session" } }, true);
  const claude = within(providerSelect()).getByRole("option", { name: "Claude Code · not logged in" }) as HTMLOptionElement;
  expect(claude.disabled).toBe(true);
  expect(providerSelect().value).toBe("");
  const note = (await screen.findByText(NO_LOGIN, { exact: false })).closest(".field-note") as HTMLElement;
  expect(note.classList).toContain("bad");
  expect(within(note).getByRole("button", { name: "Log in first" })).toBeTruthy();
  await waitFor(() => expect(teamIsOpen()).toBe(true));
  expect(startButton().disabled).toBe(true);
  await waitFor(() => expect(footerText()).toContain("To start: log in to Claude Code."));
  fireEvent.change(providerSelect(), { target: { value: "kilo" } });
  await waitFor(() => expect(startButton().disabled).toBe(false));
  expect(screen.queryByText(NO_LOGIN, { exact: false })).toBeNull();
});

test("Log in first closes the window and opens its CLI's row in Agent CLIs", async () => {
  providers = async () => [provider("claude", { login_missing: true }), provider("kilo")];
  await openLaunch();
  await ready("/src/app", { provider: { name: "claude", reason: "only_installed" } }, true);
  fireEvent.click(await screen.findByRole("button", { name: "Log in first" }));
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "New session" })).toBeNull());
  expect(await screen.findByRole("heading", { name: "Agent CLIs" })).toBeTruthy();
});

test("the Project way asks for the chosen project's providers, where its own login counts", async () => {
  providers = async (project) => [provider("claude", { login_missing: project !== "shop" }), provider("kilo")];
  const dialog = await openProject();
  await waitFor(() => expect(calls.some((c) => c.path === "/api/providers?project=shop")).toBe(true));
  fireEvent.click(repoRadio(dialog, "frontend"));
  await waitFor(() => expect(providerSelect().disabled).toBe(false));
  await waitFor(() => {
    const claude = within(providerSelect()).getByRole("option", { name: /^Claude Code/, hidden: true }) as HTMLOptionElement;
    expect(claude.disabled).toBe(false);
  });
  fireEvent.change(providerSelect(), { target: { value: "claude" } });
  await waitFor(() => expect(startIn("Shop").disabled).toBe(false));
  fireEvent.change(within(dialog).getByRole("combobox", { name: "Project" }), { target: { value: "acme" } });
  await waitFor(() => expect(calls.some((c) => c.path === "/api/providers?project=acme")).toBe(true));
  expect(await screen.findByText(NO_LOGIN, { exact: false })).toBeTruthy();
});

// Starting

test("Start sends the window's fields, says Starting… and keeps the focus, then opens the session", async () => {
  let release: () => void = () => {};
  const pending = new Promise<void>((resolve) => (release = resolve));
  const started = session("app", { repo: "/src/app" });
  answers["POST /api/sessions"] = async () => {
    await pending;
    return json({ session: started, resumed: false, changes: [], problems: ["run x needs a rev"], lead: "", warnings: [] });
  };
  await openLaunch();
  await ready("/src/app");
  openTeam();
  fireEvent.change(screen.getByRole("textbox", { name: "Switch off" }), { target: { value: "agent:rev, skill:x" } });
  await waitFor(() => expect(startButton().disabled).toBe(false));
  startButton().focus();
  fireEvent.click(startButton());
  await waitFor(() => expect(startButton().textContent).toBe("Starting…"));
  expect(startButton().disabled).toBe(false);
  expect(startButton().getAttribute("aria-disabled")).toBe("true");
  expect(document.activeElement).toBe(startButton());
  expect(where().disabled).toBe(true);
  fireEvent.click(startButton()); // pressed again while it works: nothing more is sent
  expect(calls.filter((c) => c.method === "POST")).toHaveLength(1);
  expect(calls.find((c) => c.method === "POST")!.body).toEqual({
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
  await waitFor(() => expect(startButton().disabled).toBe(false));
  fireEvent.click(startButton());
  expect(await screen.findByRole("region", { name: "Session app" })).toBeTruthy();
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain(trust);
});

test("a refused start shows the core's whole reason, takes the focus there and keeps the window", async () => {
  answers["POST /api/sessions"] = () => json({ detail: "kit \"nope\" not found; looked in /a, /b" }, 400);
  await openLaunch();
  await ready("/src/app");
  await waitFor(() => expect(startButton().disabled).toBe(false));
  fireEvent.click(startButton());
  const dialog = screen.getByRole("dialog", { name: "New session" });
  const alert = await within(dialog).findByRole("alert");
  expect(alert.textContent).toBe('kit "nope" not found; looked in /a, /b');
  await waitFor(() => expect(document.activeElement).toBe(alert.closest(".launch-refused")));
  expect(document.activeElement).not.toBe(document.body);
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
  openTeam();
  const field = screen.getByRole("textbox", { name: "Switch off" }) as HTMLInputElement;
  expect(field.placeholder).toBe("agent:reviewer@kit-b, skill:style");
  fireEvent.click(screen.getByRole("button", { name: "About Switch off" }));
  expect(screen.getByText("kind:name or kind:name@kit, separated by commas; kinds: agent, skill, mcp, flow.")).toBeTruthy();
  fireEvent.change(field, { target: { value: "skill:x" } });
  toggleTeam();
  fireEvent.click(startButton());
  const dialog = screen.getByRole("dialog", { name: "New session" });
  expect((await within(dialog).findByRole("alert")).textContent).toContain('agent "reviewer" is defined by two kits');
  await waitFor(() => expect(teamIsOpen()).toBe(true));
  expect(within(dialog).getByRole("button", { name: "Switch off reviewer of kit-a" })).toBeTruthy();
  fireEvent.click(within(dialog).getByRole("button", { name: "Switch off reviewer of kit-b" }));
  expect(field.value).toBe("skill:x, agent:reviewer@kit-b");
  expect(calls.filter((c) => c.method === "POST")).toHaveLength(1); // started again only by Start
});

// Task (openspec change first-message, capability new-session-window)

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
const firstField = () => screen.getByRole("textbox", { name: /^(Task|Message)$/ }) as HTMLTextAreaElement;

function writeFirst(text: string) {
  fireEvent.change(firstField(), { target: { value: text } });
}

test("Task is a visible field of three lines with its placeholder and its info", async () => {
  await openLaunch();
  const task = firstField();
  expect(task.rows).toBe(3);
  expect(task.placeholder).toBe("What should the team do?");
  const about = screen.getByRole("button", { name: "About Task" });
  fireEvent.click(about);
  expect(screen.getByText("The team gets this as its first message and answers in the chat. You can leave it empty.")).toBeTruthy();
  expect(document.activeElement).not.toBe(task);
});

test("a task is sent with the start", async () => {
  answers["POST /api/sessions"] = () => json({ session: session("app", { repo: "/src/app" }), ...STARTED });
  await openLaunch();
  await ready("/src/app");
  writeFirst("  Take LAD-19\n");
  await waitFor(() => expect(startButton().disabled).toBe(false));
  fireEvent.click(startButton());
  await screen.findByRole("region", { name: "Session app" });
  const sent = calls.find((c) => c.method === "POST" && c.path === "/api/sessions")!;
  expect(sent.body).toMatchObject({ prompt: "Take LAD-19" });
});

test("an empty task is not sent", async () => {
  answers["POST /api/sessions"] = () => json({ session: session("app", { repo: "/src/app" }), ...STARTED });
  await openLaunch();
  await ready("/src/app");
  writeFirst("  \n ");
  await waitFor(() => expect(startButton().disabled).toBe(false));
  fireEvent.click(startButton());
  await screen.findByRole("region", { name: "Session app" });
  const sent = calls.find((c) => c.method === "POST" && c.path === "/api/sessions")!;
  expect(sent.body).not.toHaveProperty("prompt");
});

test("a task over the limit keeps Start off, says so under it and in the footer", async () => {
  answers["GET /api/limits"] = () => json(LIMITS);
  await openLaunch();
  await ready("/src/app");
  writeFirst("x".repeat(21));
  const note = await screen.findByText("21 characters, the limit is 20");
  expect(firstField().getAttribute("aria-describedby")).toBe(note.id);
  expect(startButton().disabled).toBe(true);
  await waitFor(() => expect(footerText()).toContain("To start: shorten the task."));
  fireEvent.click(screen.getByRole("button", { name: "shorten the task" }));
  expect(document.activeElement).toBe(firstField());
  writeFirst("x".repeat(20));
  await waitFor(() => expect(startButton().disabled).toBe(false));
});

// The draft (D6) and the focus

test("Esc keeps Where, Task and Team for the next opening; a start clears them", async () => {
  answers["POST /api/sessions"] = () => json({ session: session("app", { repo: "/src/app" }), ...STARTED });
  const dialog = await openLaunch();
  await ready("/src/app");
  writeFirst("Look at the tests");
  openTeam();
  chooseMode("plan");
  fireEvent.keyDown(dialog, { key: "Escape" });
  expect(screen.queryByRole("dialog", { name: "New session" })).toBeNull();
  fireEvent.click(within(rail()).getByRole("button", { name: "New session" }));
  await screen.findByRole("dialog", { name: "New session" });
  expect(firstField().value).toBe("Look at the tests");
  expect(where().value).toBe("/src/app");
  expect(modeChosen()).toBe("plan");
  await waitFor(() => expect(startButton().disabled).toBe(false));
  fireEvent.click(startButton());
  await screen.findByRole("region", { name: "Session app" });
  fireEvent.click(within(rail()).getByRole("button", { name: "New session" }));
  await screen.findByRole("dialog", { name: "New session" });
  expect(firstField().value).toBe("");
});

test("the footer says why while the agent CLIs are asked, and when their list fails", async () => {
  let release: (found: ProviderInfo[]) => void = () => {};
  providers = () => new Promise((resolve) => (release = resolve));
  await openLaunch();
  await ready("/src/app").catch(() => undefined); // the Agent field stays checking…
  await screen.findByText(/✓ Ready/);
  expect(startButton().disabled).toBe(true);
  expect(footerText()).toContain("To start: wait for the agent CLIs.");
  await act(async () => release([provider("claude")]));
  await waitFor(() => expect(startButton().disabled).toBe(false));
  expect(footerText()).not.toContain("To start");
});

test("a list of agent CLIs that fails: the footer says choose an agent, Team shows why", async () => {
  answers["GET /api/providers"] = () => json({ detail: "the CLIs cannot be read" }, 500);
  await openLaunch();
  folders["/src/app"] = folder("/src/app");
  type("/src/app");
  await screen.findByText(/✓ Ready/);
  await waitFor(() => expect(footerText()).toContain("To start: choose an agent."));
  fireEvent.click(screen.getByRole("button", { name: "choose an agent" }));
  expect(await screen.findByText("the CLIs cannot be read")).toBeTruthy();
});

test("Enter in a field beside a stopped session with no task resumes it, as its blue button does", async () => {
  sessions = [session("webapp", { status: "stopped", repo: WEBAPP })];
  recent = [recentFolder(WEBAPP)];
  folders[WEBAPP] = folder(WEBAPP, {
    default_name: "webapp",
    free_name: "webapp-2",
    name_state: "stopped_here",
    provider: { name: "claude", reason: "last_session" },
  });
  answers["POST /api/sessions/webapp/resume"] = () => json({ session: session("webapp"), ...STARTED, resumed: true });
  await openLaunch(false);
  const resume = (await screen.findByRole("button", { name: "Resume webapp" })) as HTMLButtonElement;
  await waitFor(() => expect(resume.disabled).toBe(false));
  openTeam();
  fireEvent.submit(nameField().closest("form")!);
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "New session" })).toBeNull());
  expect(calls.filter((c) => c.method === "POST").map((c) => c.path)).toEqual(["/api/sessions/webapp/resume"]);
});

test("the draft keeps the model picked, for its agent CLI", async () => {
  const dialog = await openLaunch();
  await ready("/src/app", { provider: { name: "kilo", reason: "only_installed" } });
  openTeam();
  await waitFor(() => expect(modelField().disabled).toBe(false));
  fireEvent.click(modelField());
  fireEvent.click(await screen.findByRole("option", { name: "kilo/large" }));
  await waitFor(() => expect(modelField().textContent).toContain("kilo/large"));
  fireEvent.keyDown(dialog, { key: "Escape" });
  fireEvent.click(within(rail()).getByRole("button", { name: "New session" }));
  await screen.findByRole("dialog", { name: "New session" });
  await waitFor(() => expect(modelField().textContent).toContain("kilo/large"));
  answers["POST /api/sessions"] = () => json({ session: session("app", { repo: "/src/app" }), ...STARTED });
  await waitFor(() => expect(startButton().disabled).toBe(false));
  fireEvent.click(startButton());
  await screen.findByRole("region", { name: "Session app" });
  expect(calls.find((c) => c.method === "POST")!.body).toMatchObject({ model: "kilo/large" });
});

test("an info button's Esc closes only it; the window stays", async () => {
  const dialog = await openLaunch();
  const about = screen.getByRole("button", { name: "About Task" });
  fireEvent.click(about);
  fireEvent.keyDown(about, { key: "Escape" });
  expect(about.getAttribute("aria-expanded")).toBe("false");
  expect(screen.getByRole("dialog", { name: "New session" })).toBe(dialog);
});

// The session's model (in Team)

const modelField = () => screen.getByRole("combobox", { name: "Model", hidden: true }) as HTMLButtonElement;
const teamIsOpen = () => screen.queryByRole("button", { name: "Hide" }) !== null;
const toggleTeam = () => fireEvent.click(screen.getByRole("button", { name: teamIsOpen() ? "Hide" : "Change" }));
// Team's summary of the model: none on the CLI's default.
const summary = () => document.querySelector(".team-sum .launch-first-line")?.textContent ?? "";
const posted = () => calls.find((c) => c.method === "POST" && !c.path.includes("session-model"))!.body as { model?: string };
const checked = () => calls.filter((c) => c.path === "/api/session-model/check");

const QWEN = "Локальная Qwen";
const HOME = "LM Studio дома";
const SILENT = `${HOME} does not answer (connection refused); qwen3-8b is on it. Start the server or pick another model.`;

function saved(name: string, model: string, cli = "kilo", server = HOME) {
  return { id: `id-${name}`, name, cli, cli_title: cli, model, server, whole_process: false };
}

const defaultOf = (model: ReturnType<typeof saved>) => ({
  cli: model.cli,
  external: model.id,
  builtin: null,
  name: model.name,
  model: model.model,
  server: model.server,
  whole_process: false,
});

const silent = () => ({
  kind: "refused",
  text: SILENT,
  field: "server",
  name: "",
  retry: true,
  short: `${HOME} does not answer`,
  peek: "not answering",
  warnings: [],
  server: HOME,
});

// The window with Kilo CLI chosen, Team open.
async function kiloWindow() {
  await openLaunch();
  await ready("/src/app", { provider: { name: "kilo", reason: "only_installed" } });
  openTeam();
  await waitFor(() => expect(modelField().disabled).toBe(false));
}

async function pickRow(name: string | RegExp) {
  fireEvent.click(modelField());
  fireEvent.click(await screen.findByRole("option", { name }));
}

async function startedWith() {
  answers["POST /api/sessions"] = () => json({ session: session("app", { repo: "/src/app" }), ...STARTED });
  await waitFor(() => expect(startButton().disabled).toBe(false));
  fireEvent.click(startButton());
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "New session" })).toBeNull());
  return posted();
}

test("the Model field comes before Switch off and takes the whole row", async () => {
  await kiloWindow();
  const team = document.querySelector(".team-body")!;
  const labels = [...team.querySelectorAll(":scope > .field > label, :scope > .field > .field-label > label")].map(
    (one) => one.textContent?.trim(),
  );
  expect(labels.slice(-2)).toEqual(["Model", "Switch off"]);
  expect(modelField().closest(".field")!.classList.contains("launch-wide")).toBe(true);
  expect(modelField().textContent).toContain("Kilo CLI's settings");
});

test("with no default the field is on the CLI's settings, says nothing and sends nothing", async () => {
  await kiloWindow();
  expect(modelField().closest(".field")!.querySelector(".field-note")).toBeNull();
  expect(summary()).toBe("");
  expect("model" in (await startedWith())).toBe(false);
  expect(checked()).toEqual([]);
});

test("the default is chosen in advance, marked, checked, and sends nothing", async () => {
  const qwen = saved(QWEN, "qwen3-8b");
  modelEntries = { models: [qwen], servers: [], defaults: [defaultOf(qwen)] };
  await kiloWindow();
  await waitFor(() => expect(modelField().textContent).toContain(QWEN));
  expect(modelField().textContent).toContain("default");
  await screen.findByText("Kilo CLI's default model, from Settings → Agent CLIs.");
  await waitFor(() => expect(checked().length).toBe(1));
  expect(checked()[0].body).toEqual({ cli: "kilo", model: QWEN, project: null });
  expect("model" in (await startedWith())).toBe(false);
});

test("another pick is for this session only and sends its name", async () => {
  const qwen = saved(QWEN, "qwen3-8b");
  const work = saved("Рабочая Qwen", "qwen3-coder-30b");
  modelEntries = { models: [qwen, work], servers: [], defaults: [defaultOf(qwen)] };
  await kiloWindow();
  await waitFor(() => expect(modelField().textContent).toContain(QWEN));
  await pickRow(/^Рабочая Qwen/);
  await screen.findByText(`For this session only. Kilo CLI's default model is ${QWEN}.`);
  expect((await startedWith()).model).toBe("Рабочая Qwen");
});

test("a built-in pick with no default has no such note, and sends the model", async () => {
  await kiloWindow();
  await pickRow("kilo/large");
  await waitFor(() => expect(modelField().textContent).toContain("kilo/large"));
  expect(screen.queryByText(/For this session only/)).toBeNull();
  expect((await startedWith()).model).toBe("kilo/large");
});

test("a pick stays while the providers are read again, as the same agent CLI comes back", async () => {
  await kiloWindow();
  await pickRow("kilo/large");
  await waitFor(() => expect(modelField().textContent).toContain("kilo/large"));
  await pickPlace("Project…"); // no project yet: no providers; then the project's, Kilo too
  await waitFor(() => expect(modelField().disabled).toBe(true));
  await waitFor(() => expect(modelField().disabled).toBe(false));
  expect(modelField().textContent).toContain("kilo/large");
  expect(screen.queryByText(/belongs to/)).toBeNull();
});

test("the CLI's settings past a default send an empty model", async () => {
  const qwen = saved(QWEN, "qwen3-8b");
  modelEntries = { models: [qwen], servers: [], defaults: [defaultOf(qwen)] };
  await kiloWindow();
  await waitFor(() => expect(modelField().textContent).toContain(QWEN));
  await pickRow(/^Kilo CLI's settings/);
  await screen.findByText(`For this session only: the agent CLI chooses, not ${QWEN}.`);
  expect((await startedWith()).model).toBe("");
});

test("a server that does not answer opens Advanced, turns Start off and names the ways out", async () => {
  const qwen = saved(QWEN, "qwen3-8b");
  modelEntries = { models: [qwen], servers: [], defaults: [defaultOf(qwen)] };
  sessionCheck = silent;
  await openLaunch();
  await ready("/src/app", { provider: { name: "kilo", reason: "only_installed" } });
  const note = await screen.findByText(SILENT);
  expect(note.closest("[role=alert]")!.className).toContain("field-note bad");
  await waitFor(() => expect(teamIsOpen()).toBe(true));
  expect(modelField().getAttribute("aria-invalid")).toBe("true");
  expect(modelField().querySelector(".srv.down")).toBeTruthy();
  await waitFor(() => expect(startButton().disabled).toBe(true));
  const before = checked().length;
  fireEvent.click(screen.getByRole("button", { name: "Check again" }));
  await waitFor(() => expect(checked().length).toBe(before + 1));
  fireEvent.click(screen.getByRole("button", { name: "Use Kilo CLI's settings" }));
  await waitFor(() => expect(startButton().disabled).toBe(false));
  expect(screen.queryByText(SILENT)).toBeNull();
  expect((await startedWith()).model).toBe("");
});

test("a refusal no new try can help has no Check again", async () => {
  const opus = saved("Шлюз Opus", "gw-opus");
  modelEntries = { models: [opus], servers: [], defaults: [defaultOf(opus)] };
  const text = "Шлюз Opus is on the model server Шлюз; Шлюз does not suit Kilo CLI: why; OpenCode does";
  sessionCheck = () => ({ ...silent(), text, retry: false, peek: "does not suit" });
  await kiloWindow();
  await screen.findByText(text);
  expect(screen.queryByRole("button", { name: "Check again" })).toBeNull();
  expect(screen.getByRole("button", { name: "Use Kilo CLI's settings" })).toBeTruthy();
});

test("a key over plain http warns and leaves Start on", async () => {
  const qwen = saved(QWEN, "qwen3-8b");
  modelEntries = { models: [qwen], servers: [], defaults: [defaultOf(qwen)] };
  const warning = `The key of ${HOME} goes unencrypted (http) to an address outside your machine and network.`;
  sessionCheck = () => ({
    kind: "ok",
    text: `${HOME} lists qwen3-8b among its models.`,
    field: "",
    name: "",
    retry: false,
    short: "",
    peek: "key over http",
    warnings: [warning],
    server: HOME,
  });
  await kiloWindow();
  await screen.findByText(`✓ ${HOME} lists qwen3-8b among its models.`);
  expect(screen.getByText(`⚠ ${warning}`).className).toContain("field-note warn");
  expect(screen.getByText(`⚠ ${warning}`).querySelector("a")).toBeNull();
  expect(startButton().disabled).toBe(false);
  toggleTeam();
  await waitFor(() => expect(summary()).toBe(`Model ${QWEN} on ${HOME} ⚠ key over http`));
});

test("folded, Advanced says what the warning is about, not always the key", async () => {
  const qwen = saved(QWEN, "qwen3-8b");
  modelEntries = { models: [qwen], servers: [], defaults: [defaultOf(qwen)] };
  sessionCheck = () => ({
    kind: "ok",
    text: `${HOME} lists qwen3-8b among its models.`,
    field: "",
    name: "",
    retry: false,
    short: "",
    peek: "context too small",
    warnings: [`${QWEN} on ${HOME} has a context of 4,000 tokens`],
    server: HOME,
  });
  await kiloWindow();
  await screen.findByText(`✓ ${HOME} lists qwen3-8b among its models.`);
  toggleTeam();
  await waitFor(() => expect(summary()).toBe(`Model ${QWEN} on ${HOME} ⚠ context too small`));
});

test("the warning's docs/install.md links to its section on GitHub, in a new tab", async () => {
  const qwen = saved(QWEN, "qwen3-8b");
  modelEntries = { models: [qwen], servers: [], defaults: [defaultOf(qwen)] };
  sessionCheck = () => ({
    kind: "ok",
    text: `${HOME} lists qwen3-8b among its models.`,
    field: "",
    name: "",
    retry: false,
    short: "",
    peek: "context too small",
    warnings: [`${QWEN} is small; see "What to expect of a small model" in docs/install.md`],
    server: HOME,
  });
  await kiloWindow();
  const link = await screen.findByRole("link", { name: "docs/install.md ↗" });
  expect(link.getAttribute("href")).toBe(
    "https://github.com/ladohq/lado/blob/main/docs/install.md#what-to-expect-of-a-small-model",
  );
  expect(link.getAttribute("target")).toBe("_blank");
  expect(link.getAttribute("rel")).toBe("noreferrer");
  expect(link.closest(".field-note")?.textContent).toBe(
    `⚠ ${QWEN} is small; see "What to expect of a small model" in docs/install.md ↗`,
  );
});

test("a warning's link goes to the section the warning names", async () => {
  const qwen = saved(QWEN, "qwen3-8b");
  modelEntries = { models: [qwen], servers: [], defaults: [defaultOf(qwen)] };
  sessionCheck = () => ({
    kind: "ok",
    text: `${HOME} lists qwen3-8b among its models.`,
    field: "",
    name: "",
    retry: false,
    short: "",
    peek: "context unknown",
    warnings: [`${QWEN} has no context; see "A cloud provider" in docs/install.md`],
    server: HOME,
  });
  await kiloWindow();
  const link = await screen.findByRole("link", { name: "docs/install.md ↗" });
  expect(link.getAttribute("href")).toBe(
    "https://github.com/ladohq/lado/blob/main/docs/install.md#a-cloud-provider",
  );
});

test("folded, Advanced names the model and its server, or a built-in model alone", async () => {
  const qwen = saved(QWEN, "qwen3-8b");
  modelEntries = { models: [qwen], servers: [], defaults: [] };
  await kiloWindow();
  expect(summary()).toBe(""); // the CLI's default: no model named
  await pickRow("kilo/large");
  await waitFor(() => expect(modelField().textContent).toContain("kilo/large"));
  toggleTeam();
  await waitFor(() => expect(summary()).toBe("Model kilo/large"));
  expect(screen.getByText("kilo/large", { selector: ".launch-first-peek" })).toBeTruthy();
  toggleTeam();
  await pickRow(/^Локальная Qwen/);
  toggleTeam();
  await waitFor(() => expect(summary()).toBe(`Model ${QWEN} on ${HOME}`));
});

test("the list of another agent CLI shows none of the last one's models while it is read", async () => {
  await kiloWindow();
  fireEvent.click(modelField());
  await screen.findByRole("option", { name: "kilo/large" });
  fireEvent.keyDown(modelField(), { key: "Escape" });
  let answer: (found: Response) => void = () => {};
  answers["GET /api/providers/claude/model-choices"] = () => new Promise<Response>((done) => (answer = done));
  fireEvent.change(providerSelect(), { target: { value: "claude" } });
  await waitFor(() => expect(modelField().textContent).toContain("Claude Code's settings"));
  fireEvent.click(modelField());
  await screen.findByText("reading the models…");
  expect(screen.queryByRole("option", { name: "kilo/large" })).toBeNull();
  answer(json({ ...modelsOf("claude", ""), external: [], other_name: true, whole_process: false, read_again: false }));
  expect(await screen.findByRole("option", { name: "sonnet" })).toBeTruthy();
});

test("the line of a lost pick goes at the next change of agent CLI", async () => {
  providers = async () => [provider("claude"), provider("kilo"), provider("codex")];
  await kiloWindow();
  await pickRow("kilo/large");
  await waitFor(() => expect(modelField().textContent).toContain("kilo/large"));
  fireEvent.change(providerSelect(), { target: { value: "claude" } });
  await screen.findByText(/^kilo\/large belongs to/);
  fireEvent.change(providerSelect(), { target: { value: "codex" } });
  await waitFor(() => expect(screen.queryByText(/belongs to/)).toBeNull());
});

test("the window reads an open list again when it gets the focus back", async () => {
  await kiloWindow();
  fireEvent.click(modelField());
  await screen.findByRole("option", { name: "kilo/large" });
  const qwen = saved(QWEN, "qwen3-8b");
  modelEntries = { models: [qwen], servers: [], defaults: [] };
  fireEvent.focus(window);
  expect(await screen.findByRole("option", { name: new RegExp(`^${QWEN}`) })).toBeTruthy();
});

test("a refusal is scrolled into the window's view", async () => {
  const seen: Element[] = [];
  const scroll = vi.fn(function (this: Element) {
    seen.push(this);
  });
  Element.prototype.scrollIntoView = scroll;
  const qwen = saved(QWEN, "qwen3-8b");
  modelEntries = { models: [qwen], servers: [], defaults: [defaultOf(qwen)] };
  sessionCheck = silent;
  await kiloWindow();
  await screen.findByText(SILENT);
  await waitFor(() => expect(scroll).toHaveBeenCalledWith({ block: "center" }));
  expect(seen.some((one) => one.contains(modelField()) && one.textContent!.includes(SILENT))).toBe(true);
  delete (Element.prototype as Partial<Element>).scrollIntoView;
});

test("Check again keeps the refusal and its buttons, off with the focus, until the answer", async () => {
  const qwen = saved(QWEN, "qwen3-8b");
  modelEntries = { models: [qwen], servers: [], defaults: [defaultOf(qwen)] };
  sessionCheck = silent;
  await kiloWindow();
  await screen.findByText(SILENT);
  let answer: (found: Response) => void = () => {};
  answers["POST /api/session-model/check"] = () => new Promise<Response>((done) => (answer = done));
  const again = screen.getByRole("button", { name: "Check again" });
  again.focus();
  fireEvent.click(again);
  const checking = await screen.findByRole("button", { name: "Checking…" });
  expect(checking.getAttribute("aria-disabled")).toBe("true");
  expect(document.activeElement).toBe(checking);
  expect(screen.getByText(SILENT)).toBeTruthy();
  expect(screen.getByRole("button", { name: "Use Kilo CLI's settings" })).toBeTruthy();
  expect(startButton().disabled).toBe(true);
  expect(modelField().getAttribute("aria-invalid")).toBe("true");
  const before = checked().length;
  fireEvent.click(checking);
  await new Promise((done) => setTimeout(done, 10));
  expect(checked().length).toBe(before); // off: no second question
  answer(json({ ...silent(), kind: "ok", text: "fine", peek: "", short: "", retry: false }));
  await waitFor(() => expect(startButton().disabled).toBe(false));
  expect(screen.queryByText(SILENT)).toBeNull();
  expect(document.activeElement).toBe(modelField());
});

test("Check again that is refused again shows the button back", async () => {
  const qwen = saved(QWEN, "qwen3-8b");
  modelEntries = { models: [qwen], servers: [], defaults: [defaultOf(qwen)] };
  sessionCheck = silent;
  await kiloWindow();
  await screen.findByText(SILENT);
  fireEvent.click(screen.getByRole("button", { name: "Check again" }));
  expect(await screen.findByRole("button", { name: "Check again" })).toBeTruthy();
  expect(screen.getByText(SILENT)).toBeTruthy();
});

test("folded on the CLI's settings past a default, Advanced says so", async () => {
  const qwen = saved(QWEN, "qwen3-8b");
  modelEntries = { models: [qwen], servers: [], defaults: [defaultOf(qwen)] };
  await kiloWindow();
  await waitFor(() => expect(modelField().textContent).toContain(QWEN));
  await pickRow(/^Kilo CLI's settings/);
  toggleTeam();
  await waitFor(() => expect(summary()).toBe("Model Kilo CLI's settings"));
});

test("folded with a refusal, Advanced says so", async () => {
  const qwen = saved(QWEN, "qwen3-8b");
  modelEntries = { models: [qwen], servers: [], defaults: [defaultOf(qwen)] };
  sessionCheck = silent;
  await kiloWindow();
  await screen.findByText(SILENT);
  toggleTeam();
  await waitFor(() => expect(summary()).toBe(`Model ${QWEN} on ${HOME} ! not answering`));
});

test("another agent CLI takes the field to its default, and says what went", async () => {
  await kiloWindow();
  await pickRow("kilo/large");
  await waitFor(() => expect(modelField().textContent).toContain("kilo/large"));
  fireEvent.change(providerSelect(), { target: { value: "claude" } });
  await screen.findByText("kilo/large belongs to Kilo CLI, so the model is back to Claude Code's default.");
  expect(modelField().textContent).toContain("Claude Code's settings");
  expect("model" in (await startedWith())).toBe(false);
});

test("a stale answer of the check is dropped", async () => {
  const qwen = saved(QWEN, "qwen3-8b");
  const work = saved("Рабочая Qwen", "qwen3-coder-30b");
  modelEntries = { models: [qwen, work], servers: [], defaults: [] };
  let answerFirst: (found: Response) => void = () => {};
  answers["POST /api/session-model/check"] = () => {
    const asked = calls.filter((c) => c.path === "/api/session-model/check").at(-1)!.body as { model: string };
    if (asked.model === QWEN) return new Promise<Response>((done) => (answerFirst = done));
    return Promise.resolve(json({ ...silent(), kind: "ok", text: "fine", peek: "", short: "", retry: false }));
  };
  await kiloWindow();
  await pickRow(/^Локальная Qwen/);
  await waitFor(() => expect(checked().length).toBe(1));
  await pickRow(/^Рабочая Qwen/);
  await waitFor(() => expect(checked().length).toBe(2));
  answerFirst(json(silent()));
  await new Promise((done) => setTimeout(done, 20));
  expect(screen.queryByText(SILENT)).toBeNull();
  expect(startButton().disabled).toBe(false);
});

test("a start refused for its model points at the field", async () => {
  await kiloWindow();
  await pickRow("kilo/large");
  await waitFor(() => expect(startButton().disabled).toBe(false));
  answers["POST /api/sessions"] = () =>
    json(
      {
        detail: {
          message: "http://localhost:1234 does not answer (connection refused); LADO cannot check qwen3-8b",
          field: "model",
          text: SILENT,
          short: `${HOME} does not answer`,
          peek: "not answering",
          retry: true,
        },
      },
      409,
    );
  toggleTeam();
  fireEvent.click(startButton());
  await screen.findByText(`Not started: ${HOME} does not answer. See Model above.`);
  expect(screen.getByText(SILENT)).toBeTruthy();
  await waitFor(() => expect(teamIsOpen()).toBe(true));
  expect(document.activeElement).toBe(modelField());
  expect(startButton().disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Use Kilo CLI's settings" }));
  await waitFor(() => expect(startButton().disabled).toBe(false));
  expect(screen.queryByText(/^Not started/)).toBeNull();
});

test("the list's foot opens Settings in a new tab, and the window reads the models at its focus", async () => {
  await kiloWindow();
  writeFirst("Look at the tests");
  fireEvent.click(modelField());
  const link = (await screen.findByRole("link", { name: "Settings → Agent CLIs" })) as HTMLAnchorElement;
  expect(link.closest(".mp-foot")!.textContent).toContain("The default comes from Settings → Agent CLIs.");
  expect(link.target).toBe("_blank");
  expect(link.getAttribute("href")).toBe("/settings/agent-clis");
  fireEvent.keyDown(modelField(), { key: "Escape" });
  const qwen = saved(QWEN, "qwen3-8b");
  modelEntries = { models: [qwen], servers: [], defaults: [defaultOf(qwen)] };
  fireEvent.focus(window);
  await waitFor(() => expect(modelField().textContent).toContain(QWEN));
  expect(firstField().value).toBe("Look at the tests");
});

test("Other name… takes a name outside the list, inside the window's form", async () => {
  await openLaunch();
  await ready("/src/app");
  toggleTeam();
  await waitFor(() => expect(modelField().disabled).toBe(false));
  await pickRow(/^Other name/);
  const typed = screen.getByRole("textbox", { name: "Other name" });
  expect(typed.closest("form")!.className).not.toContain("mc-other");
  fireEvent.change(typed, { target: { value: "claude-opus-5-5" } });
  fireEvent.click(screen.getByRole("button", { name: "Use" }));
  await waitFor(() => expect(modelField().textContent).toContain("claude-opus-5-5"));
  expect((await startedWith()).model).toBe("claude-opus-5-5");
});

async function resumeWindow() {
  open("/sessions/lado/flows");
  fireEvent.click(await screen.findByRole("button", { name: "Resume…" }));
  const dialog = await screen.findByRole("dialog", { name: "Resume session" });
  const button = within(dialog).getByRole("button", { name: "Resume lado" }) as HTMLButtonElement;
  answers["POST /api/sessions/lado/resume"] = () => json({ session: session("lado"), ...STARTED, resumed: true });
  return button;
}

async function resumed(button: HTMLButtonElement) {
  await waitFor(() => expect(button.disabled).toBe(false));
  fireEvent.click(button);
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Resume session" })).toBeNull());
  return calls.find((c) => c.method === "POST" && c.path.endsWith("/resume"))!.body;
}

test("Resume holds the session's model and sends nothing when it stays", async () => {
  sessions = [session("lado", { status: "stopped", repo: "/src/lado", provider: "kilo", model: "kilo/small" })];
  const button = await resumeWindow();
  await waitFor(() => expect(modelField().textContent).toContain("kilo/small"));
  await waitFor(() => expect(summary()).toBe("Model kilo/small"));
  expect(await resumed(button)).toEqual({});
});

test("Resume sends the CLI's settings when the human leaves the kept model", async () => {
  sessions = [session("lado", { status: "stopped", repo: "/src/lado", provider: "kilo", model: "kilo/small" })];
  const button = await resumeWindow();
  toggleTeam();
  await waitFor(() => expect(modelField().textContent).toContain("kilo/small"));
  await pickRow(/^Kilo CLI's settings/);
  expect(await resumed(button)).toEqual({ model: "" });
});

test("Resume of a session on the CLI's settings keeps them past a default", async () => {
  const qwen = saved(QWEN, "qwen3-8b");
  modelEntries = { models: [qwen], servers: [], defaults: [defaultOf(qwen)] };
  sessions = [session("lado", { status: "stopped", repo: "/src/lado", provider: "kilo", model: "" })];
  const button = await resumeWindow();
  await waitFor(() => expect(modelField().textContent).toContain("Kilo CLI's settings"));
  expect(await resumed(button)).toEqual({});
});

test("Resume of a kept model refused says it ran on it before", async () => {
  sessions = [session("lado", { status: "stopped", repo: "/src/lado", provider: "kilo", model: "kilo/old" })];
  sessionCheck = () => ({ ...silent(), text: "kilo/old is not in Kilo CLI's list of models", peek: "not in its list", server: null });
  const button = await resumeWindow();
  await screen.findByText(
    "kilo/old is not in Kilo CLI's list of models. The session ran on it before. Pick another model, or resume on Kilo CLI's settings.",
  );
  await waitFor(() => expect(teamIsOpen()).toBe(true)); // the reason Resume is off is in sight
  expect(button.disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Use Kilo CLI's settings" }));
  expect(await resumed(button)).toEqual({ model: "" });
});

test("Resume of a model no longer saved says so, in the field too", async () => {
  sessions = [
    session("lado", { status: "stopped", repo: "/src/lado", provider: "kilo", model: "Рабочая Qwen", model_missing: true }),
  ];
  const button = await resumeWindow();
  await screen.findByText(
    "The session ran on the model Рабочая Qwen, which is no longer in Settings → Model servers. Pick a model or use Kilo CLI's settings.",
  );
  expect(modelField().textContent).toContain("not in Settings");
  expect(button.disabled).toBe(true);
  expect(screen.queryByRole("button", { name: "Check again" })).toBeNull();
  expect(checked()).toEqual([]);
  fireEvent.click(screen.getByRole("button", { name: "Use Kilo CLI's settings" }));
  expect(await resumed(button)).toEqual({ model: "" });
});

test("the window says Agent, never provider", async () => {
  await kiloWindow();
  const words = screen.getByRole("dialog", { name: "New session" }).textContent ?? "";
  expect(screen.getByRole("combobox", { name: "Agent" })).toBeTruthy();
  expect(words.toLowerCase()).not.toContain("provider");
});

// Resume

test("Resume fills the window from the session, sends only what changed and shows the changes", async () => {
  sessions = [
    session("lado", {
      status: "stopped",
      repo: "/src/lado",
      kits: ["team"],
      provider: "kilo",
      permission_mode: "plan",
      stopped_at: ago(2 * 86400_000),
    }),
  ];
  answers["POST /api/sessions/lado/resume"] = () =>
    json({
      session: session("lado"),
      resumed: true,
      changes: ["permission mode: plan -> default"],
      problems: ["run y needs a rev"],
      lead: "",
      warnings: [],
    });
  open("/sessions/lado/flows");
  fireEvent.click(await screen.findByRole("button", { name: "Resume…" }));
  const dialog = await screen.findByRole("dialog", { name: "Resume session" });
  expect(dialog.querySelector(".resume-status p")!.textContent).toBe("lado · stopped 2 d ago ");
  fireEvent.click(within(dialog).getByRole("button", { name: "About Resume" }));
  expect(within(dialog).getByText("The team continues where it stopped: its chat, tasks and work stay.")).toBeTruthy();
  expect(within(dialog).getByRole("group", { name: "Where" }).querySelector(".where-fixed")!.textContent).toBe("lado /src/lado");
  expect(within(dialog).queryByRole("combobox", { name: "Where" })).toBeNull();
  expect(firstField().placeholder).toBe("What should the team do next?");
  expect(teamSummary()).toBe("Setup teamAgent Kilo CLIPermissions Plan only");
  await waitFor(() => expect(providerSelect().value).toBe("kilo"));
  expect(modeChosen()).toBe("plan");
  openTeam();
  chooseMode("default");
  fireEvent.click(within(dialog).getByRole("button", { name: "Resume lado" }));
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Resume session" })).toBeNull());
  expect(calls.find((c) => c.method === "POST")!.body).toEqual({ permission_mode: "default" });
  // The session's page shows them after the navigation, a render after the window closed.
  expect(await screen.findByText("permission mode: plan -> default")).toBeTruthy();
  expect((await screen.findByRole("alert")).textContent).toContain("run y needs a rev");
});

test("the Resume window sends its message", async () => {
  sessions = [session("lado", { status: "stopped", repo: "/src/lado" })];
  answers["POST /api/sessions/lado/resume"] = () => json({ session: session("lado"), ...STARTED, resumed: true });
  open("/sessions/lado/flows");
  fireEvent.click(await screen.findByRole("button", { name: "Resume…" }));
  const dialog = await screen.findByRole("dialog", { name: "Resume session" });
  expect(screen.getByRole("textbox", { name: "Message" })).toBeTruthy();
  writeFirst("Continue the review");
  const resume = within(dialog).getByRole("button", { name: "Resume lado" }) as HTMLButtonElement;
  await waitFor(() => expect(resume.disabled).toBe(false));
  fireEvent.click(resume);
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Resume session" })).toBeNull());
  expect(calls.find((c) => c.method === "POST")!.body).toEqual({ prompt: "Continue the review" });
});

test("Start a new session instead turns the Resume window into New session on the same place", async () => {
  sessions = [session("lado", { status: "stopped", repo: "/src/lado" })];
  folders["/src/lado"] = folder("/src/lado", { default_name: "lado", free_name: "lado-2", name_state: "stopped_here" });
  open("/sessions/lado/flows");
  fireEvent.click(await screen.findByRole("button", { name: "Resume…" }));
  const dialog = await screen.findByRole("dialog", { name: "Resume session" });
  fireEvent.click(within(dialog).getByRole("button", { name: "Start a new session instead" }));
  await screen.findByRole("dialog", { name: "New session" });
  await waitFor(() => expect(placeBox().value).toBe("lado"));
  await waitFor(() => expect(teamSummary()).toContain("Name lado-2"));
  expect(await screen.findByRole("button", { name: "Resume lado" })).toBeTruthy();
});

test("Resume is off while the session's provider is not installed, on once an installed one is picked", async () => {
  sessions = [session("lado", { status: "stopped", repo: "/src/lado", provider: "kilo" })];
  providers = async () => [provider("claude"), provider("kilo", { installed: false, version: "", detail: "kilo not found" })];
  answers["POST /api/sessions/lado/resume"] = () => json({ session: session("lado"), ...STARTED, resumed: true });
  open("/sessions/lado/flows");
  fireEvent.click(await screen.findByRole("button", { name: "Resume…" }));
  const dialog = await screen.findByRole("dialog", { name: "Resume session" });
  const refusal = await within(dialog).findByText("kilo not found; install kilo");
  expect(refusal.classList).toContain("bad");
  await waitFor(() => expect(teamIsOpen()).toBe(true));
  const resume = within(dialog).getByRole("button", { name: "Resume lado" }) as HTMLButtonElement;
  expect(resume.disabled).toBe(true);
  fireEvent.change(providerSelect(), { target: { value: "claude" } });
  await waitFor(() => expect(resume.disabled).toBe(false));
  expect(within(dialog).queryByText("kilo not found; install kilo")).toBeNull();
  fireEvent.click(resume);
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Resume session" })).toBeNull());
  expect(calls.find((c) => c.method === "POST")!.body).toEqual({ provider: "claude" });
});

test("Resume is off while the session's provider is not among the providers", async () => {
  sessions = [session("lado", { status: "stopped", repo: "/src/lado", provider: "gone" })];
  open("/sessions/lado/flows");
  fireEvent.click(await screen.findByRole("button", { name: "Resume…" }));
  const dialog = await screen.findByRole("dialog", { name: "Resume session" });
  expect((await within(dialog).findByText("unknown agent CLI gone")).classList).toContain("bad");
  expect((within(dialog).getByRole("button", { name: "Resume lado" }) as HTMLButtonElement).disabled).toBe(true);
  // The select shows the session's provider, not the first listed one: picking that one
  // is a change, which a select only reports for another option.
  const select = providerSelect();
  expect(select.value).toBe("gone");
  const gone = within(select).getByRole("option", { name: "gone · unknown", hidden: true }) as HTMLOptionElement;
  await waitFor(() => expect(teamIsOpen()).toBe(true)); // the refusal in sight
  expect(gone.disabled).toBe(true);
});

test("Resume of a CLI without its login is off, says Log in first, and another CLI resumes", async () => {
  sessions = [session("lado", { status: "stopped", repo: "/src/lado", provider: "claude" })];
  providers = async () => [provider("claude", { login_missing: true }), provider("kilo")];
  open("/sessions/lado/flows");
  fireEvent.click(await screen.findByRole("button", { name: "Resume…" }));
  const dialog = await screen.findByRole("dialog", { name: "Resume session" });
  const note = (await within(dialog).findByText(NO_LOGIN, { exact: false })).closest(".field-note") as HTMLElement;
  expect(note.classList).toContain("bad");
  await waitFor(() => expect(teamIsOpen()).toBe(true));
  expect(within(note).getByRole("button", { name: "Log in first" })).toBeTruthy();
  expect(providerSelect().value).toBe("claude");
  const claude = within(providerSelect()).getByRole("option", { name: "Claude Code · not logged in" }) as HTMLOptionElement;
  expect(claude.disabled).toBe(true);
  const resume = within(dialog).getByRole("button", { name: "Resume lado" }) as HTMLButtonElement;
  expect(resume.disabled).toBe(true);
  fireEvent.change(providerSelect(), { target: { value: "kilo" } });
  await waitFor(() => expect(resume.disabled).toBe(false));
});

// The session's actions, by status: icons in its head, in the top bar; its list row has only
// the entry's menu

const head = () => document.querySelector(".topbar .session-head") as HTMLElement;
const details = () => screen.getByRole("dialog", { name: "Session details" });
const openDetails = () => fireEvent.click(head().querySelector("h1 button") as HTMLElement);
const facts = () => [...details().querySelectorAll("dt, dd")].map((one) => one.textContent);

test.each([
  ["running", "activity", ["Stop session…"]],
  ["running", "flows", ["Stop session…"]],
  ["loop_down", "activity", ["Stop session…"]],
  ["stopped", "activity", ["Forget…"]],
  ["stopped", "agents", ["Resume…", "Forget…"]],
  ["stopped", "flows", ["Resume…", "Forget…"]],
  ["stopped", "artifacts", ["Resume…", "Forget…"]],
  ["tmux_gone", "activity", ["Resume…", "Stop session…"]],
  ["tmux_gone", "flows", ["Resume…", "Stop session…"]],
] as const)("a %s session's head on %s has the actions %j, each with its icon and tooltip, and no menu", async (status, tab, labels) => {
  sessions = [session("lado", { status })];
  open(`/sessions/lado/${tab}`);
  await screen.findByRole("region", { name: "Session lado" });
  const buttons = within(head().querySelector(".session-head-actions") as HTMLElement).getAllByRole("button");
  expect(buttons.map((button) => button.getAttribute("aria-label"))).toEqual(labels);
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
  open("/sessions/lado/flows");
  await screen.findByRole("region", { name: "Session lado" });
  expect(within(head()).getByRole("button", { name: "Forget…" }).classList).toContain("danger-icon");
  expect(within(head()).getByRole("button", { name: "Resume…" }).classList).not.toContain("danger-icon");
});

test.each([
  ["stopped", "Resume"],
  ["tmux_gone", ""],
] as const)("Resume in the head of a %s session reads %j", async (status, word) => {
  sessions = [session("lado", { status })];
  open("/sessions/lado/artifacts");
  await screen.findByRole("region", { name: "Session lado" });
  expect(within(head()).getByRole("button", { name: "Resume…" }).textContent).toBe(word);
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

test("before its about comes, Details has the session's settings: the folder, the kits, the provider and the mode", async () => {
  sessions = [
    session("lado", { repo: "/Users/me/src/lado", kits: ["team", "default"], provider: "kilo", permission_mode: "plan" }),
    session("app"),
  ];
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  openDetails();
  expect(facts()).toEqual(["Folder", "/Users/me/src/lado", "", "Kits", "teamdefault", "CLI", "kilopermissions: plan"]);
  expect(within(details()).getByRole("button", { name: "Copy path" })).toBeTruthy();
  expect(within(details()).queryByRole("button", { name: "Copy URL" })).toBeNull();
  cleanup();
  open("/sessions/app");
  await screen.findByRole("region", { name: "Session app" });
  openDetails();
  expect(facts().at(-1)).toBe("claude");
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
    openDetails();
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
  openDetails();
  const button = within(head()).getByRole("button", { name: label });
  button.focus();
  fireEvent.click(button);
  await waitFor(() => expect(within(head()).getByText(said).getAttribute("role")).toBe("status"));
  expect(legacy).toEqual([text()]);
  expect(document.querySelector(".link-popover")).toBeNull();
  expect(document.querySelector("body > textarea")).toBeNull();
  expect(document.activeElement).toBe(button);
});

test("a refused Clipboard API copy falls back to the legacy copy", async () => {
  clipboard(async () => Promise.reject(new Error("not allowed")));
  const legacy = stubLegacyCopy();
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  openDetails();
  fireEvent.click(within(head()).getByRole("button", { name: "Copy path" }));
  await waitFor(() => expect(within(head()).getByText("Path copied")).toBeTruthy());
  expect(legacy).toEqual(["/src/lado"]);
  expect(document.querySelector(".link-popover")).toBeNull();
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
  openDetails();
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

test.each([
  [0, []],
  [1, ["1 open question to you is closed"]],
  [2, ["2 open questions to you are closed"]],
])("Stop says how many open questions it closes: %i", async (questions, line) => {
  answers["GET /api/sessions/lado/stop-preview"] = () =>
    json({ agents: ["supervisor"], dropped: 1, questions, open_runs: [], worktrees: [] });
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  fireEvent.click(within(head()).getByRole("button", { name: "Stop session…" }));
  const asked = await screen.findByRole("dialog", { name: 'Stop session "lado"?' });
  await within(asked).findByText("its agent is closed");
  expect(within(asked).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
    "its agent is closed",
    "1 message they have not got is dropped",
    ...line,
    "branches, worktrees and the history stay",
    "you can resume it later",
  ]);
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

// Stop and forget in Stop's popover

const NO_RUNS = { agents: ["supervisor"], dropped: 0, open_runs: [], worktrees: [] };

test("Stop and forget stops the session, then forgets it without force, then leaves for the list", async () => {
  answers["GET /api/sessions/lado/stop-preview"] = () => json(NO_RUNS);
  answers["POST /api/sessions/lado/stop"] = () => json({ dropped: 0 });
  answers["DELETE /api/sessions/lado"] = () => json({ open_runs: [], worktrees: [] });
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  fireEvent.click(within(head()).getByRole("button", { name: "Stop session…" }));
  const asked = await screen.findByRole("dialog", { name: 'Stop session "lado"?' });
  await within(asked).findByText("its agent is closed");
  const buttons = within(asked).getAllByRole("button");
  expect(buttons.map((button) => button.textContent)).toEqual(["Cancel", "Stop and forget", "Stop lado"]);
  expect(buttons[1].classList).toContain("danger");
  fireEvent.focus(buttons[1]);
  expect(screen.getByRole("tooltip").textContent).toBe("Stops it, then deletes its history for good");
  fireEvent.click(buttons[1]);
  await waitFor(() => expect(screen.queryByRole("region", { name: "Session lado" })).toBeNull());
  expect(calls.filter((c) => c.method !== "GET").map((c) => `${c.method} ${c.path}`)).toEqual([
    "POST /api/sessions/lado/stop",
    "DELETE /api/sessions/lado?force=false",
  ]);
});

test("while the preview loads Stop and forget is not offered", async () => {
  let give: (answer: Response) => void = () => {};
  answers["GET /api/sessions/lado/stop-preview"] = () => new Promise((resolve) => (give = resolve));
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  fireEvent.click(within(head()).getByRole("button", { name: "Stop session…" }));
  const asked = await screen.findByRole("dialog", { name: 'Stop session "lado"?' });
  expect(within(asked).queryByRole("button", { name: "Stop and forget" })).toBeNull();
  await act(async () => give(json(NO_RUNS)));
  expect(await within(asked).findByRole("button", { name: "Stop and forget" })).toBeTruthy();
});

test("a session with open runs is not offered Stop and forget, says why under the buttons; Stop works as before", async () => {
  answers["GET /api/sessions/lado/stop-preview"] = () => json({ ...NO_RUNS, open_runs: ["feature/x"] });
  answers["POST /api/sessions/lado/stop"] = () => json({ dropped: 0 });
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  fireEvent.click(within(head()).getByRole("button", { name: "Stop session…" }));
  const asked = await screen.findByRole("dialog", { name: 'Stop session "lado"?' });
  const line = await within(asked).findByText("It has open runs, so it can be forgotten only from the Stopped list after stopping.");
  expect(asked.querySelector(".question-buttons + .stop-forget-why")).toBe(line);
  expect(within(asked).getAllByRole("button").map((button) => button.textContent)).toEqual(["Cancel", "Stop lado"]);
  fireEvent.click(within(asked).getByRole("button", { name: "Stop lado" }));
  await waitFor(() => expect(screen.queryByRole("dialog", { name: 'Stop session "lado"?' })).toBeNull());
  expect(calls.filter((c) => c.method !== "GET").map((c) => c.path)).toEqual(["/api/sessions/lado/stop"]);
});

test("a refused forget after Stop and forget leaves the session stopped and says why in the popover", async () => {
  answers["GET /api/sessions/lado/stop-preview"] = () => json(NO_RUNS);
  answers["POST /api/sessions/lado/stop"] = () => json({ dropped: 0 });
  answers["DELETE /api/sessions/lado"] = () => json({ detail: 'session "lado" has 1 open run' }, 400);
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  fireEvent.click(within(head()).getByRole("button", { name: "Stop session…" }));
  const asked = await screen.findByRole("dialog", { name: 'Stop session "lado"?' });
  fireEvent.click(await within(asked).findByRole("button", { name: "Stop and forget" }));
  expect((await within(asked).findByRole("alert")).textContent).toBe('session "lado" has 1 open run');
  expect(screen.getByRole("region", { name: "Session lado" })).toBeTruthy(); // the page stays
  // Stopped by now: neither stop is offered again.
  expect((within(asked).getByRole("button", { name: "Stop and forget" }) as HTMLButtonElement).disabled).toBe(true);
  expect((within(asked).getByRole("button", { name: "Stop lado" }) as HTMLButtonElement).disabled).toBe(true);
});

// Forget stopped sessions… on the list's Stopped band (the window itself: ForgetMany.test.tsx)

const sessionList = () => screen.getByRole("navigation", { name: "Sessions" });
const band = (group: string) => within(sessionList()).getByRole("region", { name: group }).querySelector("h3") as HTMLElement;

test("the Stopped band has Forget stopped sessions…, the other bands none; it opens the window with the group's sessions, the group still folded", async () => {
  sessions = [
    session("lado"),
    session("asks", { waiting: { gates: 1, questions: 0, agents: 0 } }),
    session("old", { status: "stopped" }),
    session("older", { status: "stopped", title: "Older work" }),
  ];
  answers["GET /api/sessions/old/forget-preview"] = () => json({ open_runs: [], worktrees: [] });
  answers["GET /api/sessions/older/forget-preview"] = () => json({ open_runs: [], worktrees: [] });
  open("/sessions");
  await within(sessionList()).findByRole("link", { name: /lado/ });
  expect(within(band("Running")).queryByRole("button", { name: "Forget stopped sessions…" })).toBeNull();
  expect(within(band("Needs you")).queryByRole("button", { name: "Forget stopped sessions…" })).toBeNull();
  const fold = within(band("Stopped")).getByRole("button", { name: "Stopped 2" });
  expect(fold.getAttribute("aria-expanded")).toBe("false");
  const action = within(band("Stopped")).getByRole("button", { name: "Forget stopped sessions…" });
  expect(action.getAttribute("aria-haspopup")).toBe("dialog");
  expect(action.querySelector("svg")).toBeTruthy();
  fireEvent.focus(action);
  expect(screen.getByRole("tooltip").textContent).toBe("Forget stopped sessions…");
  fireEvent.blur(action);
  fireEvent.click(action);
  const asked = await screen.findByRole("dialog", { name: "Forget stopped sessions?" });
  expect(within(asked).getAllByRole("listitem").map((item) => item.querySelector(".forget-many-name")!.textContent)).toEqual([
    "old",
    "Older work",
  ]);
  expect(fold.getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(within(asked).getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("dialog", { name: "Forget stopped sessions?" })).toBeNull();
});

test("with text in the search the window lists only the matching stopped sessions", async () => {
  sessions = [session("lado"), session("lad-85", { status: "stopped" }), session("lad-71", { status: "stopped" })];
  answers["GET /api/sessions/lad-85/forget-preview"] = () => json({ open_runs: [], worktrees: [] });
  open("/sessions");
  await within(sessionList()).findByRole("link", { name: /lado/ });
  fireEvent.change(screen.getByRole("searchbox", { name: "Find a session" }), { target: { value: "lad-8" } });
  fireEvent.click(within(band("Stopped")).getByRole("button", { name: "Forget stopped sessions…" }));
  const asked = await screen.findByRole("dialog", { name: "Forget stopped sessions?" });
  expect(within(asked).getAllByRole("listitem").map((item) => item.querySelector(".forget-many-name")!.textContent)).toEqual([
    "lad-85",
  ]);
  expect(calls.filter((c) => c.path.endsWith("/forget-preview")).map((c) => c.path)).toEqual([
    "/api/sessions/lad-85/forget-preview",
  ]);
});

test("with no stopped session there is no Stopped band and no Forget stopped sessions…", async () => {
  sessions = [session("lado")];
  open("/sessions");
  await within(sessionList()).findByRole("link", { name: /lado/ });
  expect(within(sessionList()).queryByRole("region", { name: "Stopped" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Forget stopped sessions…" })).toBeNull();
});

// The head's facts from GET /api/sessions/{name}/about: the repository, the kits' and the
// provider's versions (docs/design/ui.md, Session head)

function about(more: Partial<SessionAbout> = {}): SessionAbout {
  return {
    repos: [{ path: "/src/lado", remote: "git@github.com:ladohq/lado.git", branch: "main" }],
    kits: [
      { name: "team", version: "1.2.0", source: "user git@github.com:me/team@v1.2.0: /k/team", valid: true, problem: null, flows: [] },
      { name: "default", version: "0.25.0", source: "built-in: /lado/default", valid: true, problem: null, flows: [] },
    ],
    provider: provider("claude", { version: "2.1.300", tested_version: "2.1.300" }),
    ...more,
  };
}

const meta = details;
const tip = () => screen.getByRole("tooltip").textContent;
const aboutCalls = () => calls.filter((call) => call.path.endsWith("/about")).length;

async function openHead(given: SessionAbout, mode: string | null = "plan") {
  sessions = [session("lado", { kits: ["team", "default"], permission_mode: mode })];
  abouts = { lado: given };
  open("/sessions/lado");
  await screen.findByRole("region", { name: "Session lado" });
  openDetails();
  await waitFor(() => expect(meta().querySelector(".session-kit")).toBeTruthy());
  (document.activeElement as HTMLElement).blur(); // Copy path's tooltip goes: a test looks at one
}

test("with its about, Details has the folder, the remote and branch, the kits and the CLI with versions", async () => {
  await openHead(about());
  expect(facts()).toEqual([
    "Folder",
    "/src/lado",
    "",
    "Git",
    "github.com/ladohq/lado · main",
    "",
    "Kits",
    "team 1.2.0default 0.25.0",
    "CLI",
    "claude 2.1.300permissions: plan",
  ]);
  expect(within(meta()).getByRole("button", { name: "Copy path" }).closest("dd")).toBeTruthy();
  expect(within(meta()).getByRole("button", { name: "Copy URL" }).closest("dd")).toBeTruthy();
  expect(within(meta()).queryByRole("img", { name: "untested version" })).toBeNull();
});

const crumb = () => head().querySelector(".session-crumb") as HTMLElement;

test("a session in a project has it as the head's breadcrumb and in Details, a link to its page", async () => {
  await openHead(about({ project: { id: "shop", title: "Shop" } }));
  expect(crumb().textContent).toBe("Shop");
  expect(crumb().getAttribute("href")).toBe("/projects/shop");
  expect(crumb().compareDocumentPosition(head().querySelector("h1")!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(head().querySelector(".session-crumb-sep")!.getAttribute("aria-hidden")).toBe("true");
  fireEvent.focus(crumb());
  expect(tip()).toBe("ShopProject shop");
  fireEvent.blur(crumb());
  const state = meta().querySelector(".session-details-state") as HTMLElement;
  expect(state.textContent).toMatch(/ · id lado · project Shop$/);
  const link = within(state).getByRole("link", { name: "Shop" });
  expect(link.getAttribute("href")).toBe("/projects/shop");
  expect(link.getAttribute("title")).toBe("Project shop");
});

test("a project without a title is shown by its id; a session without one has no breadcrumb", async () => {
  await openHead(about({ project: { id: "acme", title: null } }));
  expect(crumb().textContent).toBe("acme");
  cleanup();
  await openHead(about());
  expect(crumb()).toBeNull();
  expect(head().querySelector(".session-crumb-sep")).toBeNull();
  expect(meta().querySelector(".session-details-state")!.textContent).not.toContain("project");
});

test("a project's new title in the feed reaches the head's breadcrumb and Details with no reload", async () => {
  await openHead(about({ project: { id: "shop", title: "Shop" } }));
  abouts = { lado: about({ project: { id: "shop", title: "Shop EU" } }) };
  const renamed = session("lado", { kits: ["team", "default"], permission_mode: "plan", project: "shop", project_title: "Shop EU" });
  FakeEventSource.all[0].send("change", { kind: "sessions", session: "lado", key: "", op: "update", item: renamed }, "11");
  await waitFor(() => expect(crumb().textContent).toBe("Shop EU"));
  expect(meta().querySelector(".session-details-state")!.textContent).toMatch(/ · project Shop EU$/);
});

test("the head's branch has the remote and the path in its tooltip, and no Tab stop", async () => {
  await openHead(about());
  const branch = head().querySelector(".session-branch") as HTMLElement;
  expect(branch.textContent).toBe("main");
  expect(branch.getAttribute("tabindex")).toBeNull();
  fireEvent.focus(branch);
  expect(tip()).toBe("git@github.com:ladohq/lado.gitbranch main · /src/lado");
});

test("Copy URL copies the remote's whole URL", async () => {
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
  expect(document.querySelector(".link-popover")).toBeNull();
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
  const broken = { name: "default", version: "", source: "", valid: false, problem: 'kit "default" not found', flows: [] };
  await openHead(about({ kits: [about().kits[0], broken] }));
  const [team, gone] = meta().querySelectorAll<HTMLElement>(".session-kit");
  fireEvent.focus(team);
  expect(tip()).toBe("team v1.2.0user git@github.com:me/team@v1.2.0: /k/teaminstalled now: the next agent starts with it");
  fireEvent.blur(team);
  fireEvent.focus(gone);
  expect(tip()).toBe('default: kit "default" not found');
});

test("the CLI's tooltip has its version; ! after it only for an untested version", async () => {
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
  expect(meta().querySelector(".session-agent-cli")?.textContent).toBe("claude 2.1.300permissions: bypassPermissions");
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

const urlInput = () => screen.getByRole("textbox", { name: "Repository URL" }) as HTMLInputElement;
const cloneButton = startButton;
const branchSelect = () => screen.getByRole("combobox", { name: "Branch" }) as HTMLSelectElement;

async function cloneSource(url = URL_) {
  const dialog = await openLaunch(false);
  await waitFor(() => expect(placeBox().value).not.toBe("…"));
  await pickPlace("Clone from URL…");
  fireEvent.change(urlInput(), { target: { value: url } });
  return dialog;
}

// The form ready to clone: branches listed, the folder new, claude chosen.
async function cloneReady() {
  answers["GET /api/clone-target"] = () => json(target());
  answers["POST /api/remote-branches"] = remote();
  const dialog = await cloneSource();
  await screen.findByText("✓ Found");
  await waitFor(() => expect(cloneButton().disabled).toBe(false));
  return dialog;
}

test("a clone target outside the workspace in a container: a warning under Clone into", async () => {
  answers["GET /api/clone-target"] = () => json(target({ path: "/home/lado/marketplace", warning: OUTSIDE }));
  answers["POST /api/remote-branches"] = remote();
  await cloneSource();
  const warned = await screen.findByText(`⚠ ${OUTSIDE}`);
  expect(warned.className).toBe("field-note warn");
  const into = screen.getByRole("textbox", { name: "Clone into" });
  expect(into.closest(".field")!.contains(warned)).toBe(true);
  expect(screen.getByText("✓ New folder").compareDocumentPosition(warned) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  await screen.findByText("✓ Found");
  await waitFor(() => expect(cloneButton().disabled).toBe(false));
});

test("a clone target with no warning shows none", async () => {
  await cloneReady();
  expect(screen.queryByText(/Outside the workspace/)).toBeNull();
});

test("branches come by themselves, the default one chosen and marked; Clone and start waits for them", async () => {
  let listed: () => void = () => {};
  const pending = new Promise<void>((resolve) => (listed = resolve));
  answers["GET /api/clone-target"] = () => json(target());
  answers["POST /api/remote-branches"] = async () => {
    await pending;
    return remote()();
  };
  await cloneSource();
  expect(placeBox().value).toBe("Clone from URL");
  expect(await screen.findByText("fetching branches…")).toBeTruthy();
  expect(await screen.findByText("✓ New folder")).toBeTruthy();
  expect((screen.getByRole("textbox", { name: "Clone into" }) as HTMLInputElement).value).toBe(INTO);
  expect(cloneButton().disabled).toBe(true);
  await act(async () => listed());
  await screen.findByText("✓ Found");
  expect(branchSelect().value).toBe("main");
  expect([...branchSelect().options].map((one) => one.textContent)).toEqual([
    "main (default)",
    "develop",
    "release/1.2",
  ]);
  expect(nameField().value).toBe("marketplace");
  await waitFor(() => expect(cloneButton().disabled).toBe(false));
  expect(cloneButton().textContent).toBe("Clone and start in marketplace");
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
  await cloneSource();
  expect(await screen.findByText(/is already a clone of this repository/)).toBeTruthy();
  expect(screen.getByText(/LADO will use it as it is: no clone, no pull, no branch switch/)).toBeTruthy();
  fireEvent.click(await screen.findByRole("button", { name: "Use this clone" }));
  expect(placeBox().value).toBe("marketplace");
  expect(await screen.findByText(/✓ Ready · branch main/)).toBeTruthy();
  expect(calls.some((c) => c.path === "/api/clones")).toBe(false);
});

test("a clone of another repository there says so with a free folder, and Clone and start is off", async () => {
  const text = `${INTO} is a clone of another repository (origin git@github.com:acme/marketplace.git): choose another folder, e.g. /home/me/lado/ladohq-marketplace`;
  answers["GET /api/clone-target"] = () => json(target({ state: "other_repo", text }));
  answers["POST /api/remote-branches"] = remote();
  await cloneSource();
  expect(await screen.findByText(text)).toBeTruthy();
  await screen.findByText("✓ Found");
  expect(cloneButton().disabled).toBe(true);
});

test("a clone into a project's folder shows the refusal with the project's command, and Clone and start is off", async () => {
  const text = `${INTO} belongs to the project Shop: start a session in the project`;
  const hint = { text: "Start a session in the project:", command: "lado start --project shop --repo marketplace" };
  answers["GET /api/clone-target"] = () => json(target({ state: "in_project", text, hint }));
  answers["POST /api/remote-branches"] = remote();
  await cloneSource();
  const box = (await screen.findByText(text)).closest(".field-note.bad") as HTMLElement;
  expect(within(box).getByText(hint.command).tagName).toBe("CODE");
  await screen.findByText("✓ Found");
  expect(cloneButton().disabled).toBe(true);
});

test("a clone into a project's folder offers Open the project, which opens the project's page", async () => {
  const text = `${INTO} belongs to the project Shop: start a session in the project`;
  const hint = { text: "Add a repository to the project:", command: `lado project repo add shop ${URL_}` };
  const project = { id: "shop", title: "Shop", repo: null };
  answers["GET /api/projects/shop"] = () => json({ detail: 'unknown project "shop"' }, 404); // the page opened
  answers["GET /api/clone-target"] = () => json(target({ state: "in_project", text, hint, project }));
  answers["POST /api/remote-branches"] = remote();
  const dialog = await cloneSource();
  const box = (await screen.findByText(text)).closest(".field-note.bad") as HTMLElement;
  expect(within(box).getByText(hint.command)).toBeTruthy(); // the command stays below
  fireEvent.click(within(box).getByRole("button", { name: "Open the project Shop" }));
  expect(dialog.isConnected).toBe(false);
  await waitFor(() => expect(calls.some((c) => c.path === "/api/projects/shop")).toBe(true));
});

test("a clone target refused outside a project offers no project", async () => {
  const text = `${INTO} is not empty: choose another folder`;
  answers["GET /api/clone-target"] = () => json(target({ state: "not_empty", text }));
  answers["POST /api/remote-branches"] = remote();
  await cloneSource();
  await screen.findByText(text);
  expect(screen.queryByRole("button", { name: /Open the project/ })).toBeNull();
});

test("a long branch list is a field that filters as the human types", async () => {
  const many = ["main", ...Array.from({ length: 40 }, (_, i) => `feature/f${String(i).padStart(2, "0")}`)];
  answers["GET /api/clone-target"] = () => json(target());
  answers["POST /api/remote-branches"] = remote(many);
  await cloneSource();
  await screen.findByText("✓ Found");
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
  expect(await screen.findByText("the clone was cancelled")).toBeTruthy();
  expect(cloneButton().getAttribute("aria-disabled")).toBeNull();
  expect(cloneButton().disabled).toBe(false);
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
  expect(placeBox().value).toBe("marketplace");
  expect(screen.getByText(INTO, { selector: ".place-path" })).toBeTruthy();
  await waitFor(() => expect(teamIsOpen()).toBe(true));
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
  await waitFor(() => expect(polls).toBeGreaterThanOrEqual(2));
  expect(within(dialog).queryByRole("alert")).toBeNull();
  expect(screen.getByRole("button", { name: "Cancel clone" })).toBeTruthy();
  expect(await screen.findByRole("region", { name: "Session marketplace" })).toBeTruthy();
});

test("a clone job the server no longer knows ends the clone with why", async () => {
  answers["POST /api/clones"] = () => json(job());
  answers["GET /api/clones/j1"] = () => json({ detail: "no clone job j1" }, 404);
  const dialog = await cloneReady();
  fireEvent.click(cloneButton());
  expect((await within(dialog).findByRole("alert")).textContent).toBe("no clone job j1");
  await waitFor(() => expect(cloneButton().disabled).toBe(false));
});

test("Enter in the long branch field with no branch picked neither clones nor changes the branch (F5)", async () => {
  const many = ["main", ...Array.from({ length: 40 }, (_, i) => `feature/f${String(i).padStart(2, "0")}`)];
  answers["GET /api/clone-target"] = () => json(target());
  answers["POST /api/remote-branches"] = remote(many);
  await cloneSource();
  await screen.findByText("✓ Found");
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
  await openLaunch(false);
  await waitFor(() => expect(teamSummary()).toContain("Setup team"));
  await pickPlace("Clone from URL…");
  fireEvent.change(urlInput(), { target: { value: URL_ } });
  await screen.findByText("✓ Found");
  await waitFor(() => expect(teamSummary()).toContain("Setup default"));
  expect(modeChosen()).toBe("default");
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
  await cloneReady();
  fireEvent.click(cloneButton());
  fireEvent.click(await screen.findByRole("button", { name: "Cancel clone" }));
  await act(async () => release());
  expect(await screen.findByText(`the clone ended before Cancel clone; it is in ${INTO}`)).toBeTruthy();
  expect(placeBox().value).toBe("marketplace");
  expect(screen.getByText(INTO, { selector: ".place-path" })).toBeTruthy();
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
  fireEvent.click(within(rail()).getByRole("button", { name: "New session" }));
  await screen.findByRole("dialog", { name: "New session" });
  await waitFor(() => expect(placeBox().value).not.toBe("…"));
  await pickPlace("Clone from URL…");
  fireEvent.change(urlInput(), { target: { value: URL_ } });
  await screen.findByText("✓ Found");
  await waitFor(() => expect(cloneButton().disabled).toBe(false));
  fireEvent.click(cloneButton());
  expect(await screen.findByRole("region", { name: "Session marketplace" })).toBeTruthy();
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
    // The clone's end shows first as Cancel clone gone, before the session is started.
    if (atRunning !== null && atEnd === null && !screen.queryByRole("button", { name: "Cancel clone" })) {
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
    await screen.findByRole("region", { name: "Session marketplace" });
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
  expect(await screen.findByText(`the clone ended while this window was away; it is in ${INTO}`)).toBeTruthy();
  expect(placeBox().value).toBe("marketplace");
  expect(screen.getByText(INTO, { selector: ".place-path" })).toBeTruthy();
  expect(within(dialog).queryByRole("alert")).toBeNull();
});

// New empty folder (openspec change start-from-scratch, capability new-session-window)

const KOFEINI = "/home/ann/lado/sait-kofeini";

function scratchTarget(text: string, path: string | null, more: Partial<ScratchTarget> = {}): ScratchTarget {
  const name = text === "Сайт кофейни" ? "sait-kofeini" : text.trim().toLowerCase();
  return {
    path: path ?? (name ? `/home/ann/lado/${name}` : null),
    name: name || null,
    title: name && name !== text.trim() ? text.trim() : null,
    problem: name ? null : "type a name",
    state: "new",
    text: "a new folder",
    author: null,
    name_state: "free",
    provider: { name: "claude", reason: "only_installed" },
    warning: null,
    ...more,
  };
}

const scratchName = () => screen.getByRole("textbox", { name: "Folder name" }) as HTMLInputElement;
const createButton = () => screen.getByRole("button", { name: "Create and start" }) as HTMLButtonElement;

async function scratchReady(text = "Сайт кофейни") {
  const dialog = await openLaunch(false);
  await waitFor(() => expect(placeBox().value).toBe("New empty folder"));
  fireEvent.change(scratchName(), { target: { value: text } });
  await waitFor(() => expect(createButton().disabled).toBe(false));
  return dialog;
}

test("the first window: New empty folder, the folder's name when it differs, and Team's Name", async () => {
  const dialog = await openLaunch(false);
  await waitFor(() => expect(placeBox().value).toBe("New empty folder"));
  await waitFor(() => expect(footerText()).toContain("To start: name the folder"));
  fireEvent.change(scratchName(), { target: { value: "Сайт кофейни" } });
  expect(await within(dialog).findByText("folder sait-kofeini")).toBeTruthy();
  await waitFor(() => expect(teamSummary()).toContain("Name sait-kofeini"));
  expect(nameField().disabled).toBe(true);
  await waitFor(() => expect(createButton().disabled).toBe(false));
  fireEvent.change(scratchName(), { target: { value: "shop" } });
  await waitFor(() => expect(teamSummary()).toContain("Name shop"));
  expect(within(dialog).queryByText(/^folder /)).toBeNull();
});

test("a developer's window opens on the last place, not New empty folder", async () => {
  recent = [recentFolder("/src/lado")];
  folders["/src/lado"] = folder("/src/lado");
  await openLaunch(false);
  await waitFor(() => expect(placeBox().value).toBe("lado"));
});

test("a way the human picks before the recent places answer is kept", async () => {
  let answer: (value: Response) => void = () => {};
  answers["GET /api/folders/recent"] = () => new Promise<Response>((resolve) => (answer = resolve));
  open();
  fireEvent.click(within(rail()).getByRole("button", { name: "New session" }));
  await screen.findByRole("dialog", { name: "New session" });
  await pickPlace("Clone from URL…");
  await act(async () => answer(json([recentFolder("/src/lado")])));
  await waitFor(() => expect(calls.some((c) => c.path === "/api/folders/recent")).toBe(true));
  expect(placeBox().value).toBe("Clone from URL");
});

test("no author: the text and the hint with Copy under Folder name, Create and start off", async () => {
  answers["GET /api/scratch-target"] = () =>
    json(
      scratchTarget("Сайт кофейни", null, {
        author: {
          text: "git doesn't know who signs the agents' commits: it has no user.name or user.email",
          hint: { text: "Tell git who you are, once for this computer:", command: "git config --global user.name x" },
        },
      }),
    );
  const dialog = await openLaunch(false);
  await waitFor(() => expect(placeBox().value).toBe("New empty folder"));
  fireEvent.change(scratchName(), { target: { value: "Сайт кофейни" } });
  expect(await within(dialog).findByText(/git doesn't know who signs the agents' commits/)).toBeTruthy();
  expect(within(dialog).getByText("git config --global user.name x")).toBeTruthy();
  expect(within(dialog).getByRole("button", { name: "Copy command" })).toBeTruthy();
  expect(createButton().disabled).toBe(true);
  await waitFor(() => expect(footerText()).toContain("tell git who you are"));
});

test("a refused name shows under Folder name, marked invalid, and Create and start stays off", async () => {
  answers["GET /api/scratch-target"] = () =>
    json(
      scratchTarget("東京", null, {
        path: null,
        name: null,
        title: null,
        state: null,
        text: null,
        name_state: null,
        problem: "the name needs a Latin letter or digit for its folder: type one",
      }),
    );
  const dialog = await openLaunch(false);
  await waitFor(() => expect(placeBox().value).toBe("New empty folder"));
  fireEvent.change(scratchName(), { target: { value: "東京" } });
  expect(await within(dialog).findByText("the name needs a Latin letter or digit for its folder: type one")).toBeTruthy();
  expect(scratchName().getAttribute("aria-invalid")).toBe("true");
  expect(createButton().disabled).toBe(true);
});

test("a fresh start in a project's folder offers Open the project, which opens the project's page", async () => {
  const site = "/ws/projects/shop/site";
  const text = `${site} belongs to the project Shop: start a session in the project`;
  const hint = { text: "Add a repository to the project:", command: "lado project repo add shop --new site" };
  const project = { id: "shop", title: "Shop", repo: null };
  answers["GET /api/projects/shop"] = () => json({ detail: 'unknown project "shop"' }, 404); // the page opened
  answers["GET /api/scratch-target"] = () =>
    json(scratchTarget("site", site, { state: "in_project" as const, text, hint, project }));
  const dialog = await openLaunch(false);
  await waitFor(() => expect(placeBox().value).toBe("New empty folder"));
  fireEvent.change(scratchName(), { target: { value: "site" } });
  const box = (await within(dialog).findByText(text)).closest(".field-note.bad") as HTMLElement;
  expect(within(box).getByText(hint.command).tagName).toBe("CODE");
  expect(createButton().disabled).toBe(true);
  fireEvent.click(within(box).getByRole("button", { name: "Open the project Shop" }));
  expect(dialog.isConnected).toBe(false);
  await waitFor(() => expect(calls.some((c) => c.path === "/api/projects/shop")).toBe(true));
});

test("a folder the server cannot look at shows why, and Create and start stays off", async () => {
  answers["GET /api/scratch-target"] = () =>
    json(scratchTarget("shop", null, { state: null, text: "cannot look at /home/ann/lado/shop: Permission denied" }));
  const dialog = await openLaunch(false);
  await waitFor(() => expect(placeBox().value).toBe("New empty folder"));
  fireEvent.change(scratchName(), { target: { value: "shop" } });
  expect(await within(dialog).findByText("cannot look at /home/ann/lado/shop: Permission denied")).toBeTruthy();
  expect(createButton().disabled).toBe(true);
});

test("Create and start sends the folder, the name and the title, and opens the session", async () => {
  answers["POST /api/sessions"] = () => json({ session: session("sait-kofeini", { repo: KOFEINI }), ...STARTED });
  await scratchReady();
  fireEvent.click(createButton());
  expect(await screen.findByRole("region", { name: "Session sait-kofeini" })).toBeTruthy();
  const sent = calls.find((c) => c.method === "POST" && c.path === "/api/sessions")!;
  expect(sent.body).toEqual({
    where: { kind: "scratch", path: KOFEINI },
    name: "sait-kofeini",
    title: "Сайт кофейни",
    kits: ["default"],
    provider: "claude",
  });
});

test("a start refused after the repository was made turns Where to it, with the refusal", async () => {
  answers["POST /api/sessions"] = () => json({ detail: "the provider nosuch is not known" }, 400);
  folders[KOFEINI] = folder(KOFEINI);
  const dialog = await scratchReady();
  fireEvent.click(createButton());
  expect((await within(dialog).findByRole("alert")).textContent).toBe("the provider nosuch is not known");
  await waitFor(() => expect(placeBox().value).toBe("sait-kofeini"));
  expect(screen.getByText(KOFEINI, { selector: ".place-path" })).toBeTruthy();
});

test("a start refused before the repository was made keeps New empty folder", async () => {
  answers["POST /api/sessions"] = () => json({ detail: "x is not empty: choose a new or empty folder" }, 400);
  const dialog = await scratchReady();
  fireEvent.click(createButton());
  expect((await within(dialog).findByRole("alert")).textContent).toBe("x is not empty: choose a new or empty folder");
  await waitFor(() => expect(createButton().disabled).toBe(false));
  expect(placeBox().value).toBe("New empty folder");
});

test("Start from scratch here: an empty folder turns Where to New empty folder with it", async () => {
  const empty = "/home/ann/Documents/coffee-site";
  folders[empty] = folder(empty, {
    ok: false,
    root: null,
    branch: null,
    problem: `${empty} is not inside a git repository`,
    problem_kind: "not_repo",
    hint: { text: "Make it a repository with a first commit, in that folder:", command: "git init" },
    scratch: true,
  });
  answers["GET /api/scratch-target"] = () =>
    json(scratchTarget("coffee-site", empty, { state: "empty", text: "an empty folder" }));
  const dialog = await openLaunch();
  type(empty);
  const offer = await within(dialog).findByText("The folder is empty: LADO can start it from scratch.");
  expect(offer.closest(".field-note.bad")).toBeNull(); // an offer, not a refusal
  expect(within(dialog).queryByText("git init")).toBeNull();
  fireEvent.click(within(dialog).getByRole("button", { name: "Start from scratch here" }));
  expect(placeBox().value).toBe("New empty folder");
  expect(screen.getByText(empty, { selector: ".place-path" })).toBeTruthy();
  expect(scratchName().value).toBe("coffee-site");
  await waitFor(() => expect(createButton().disabled).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "About Folder name" }));
  expect(screen.getByText("LADO creates it in /home/ann/Documents.")).toBeTruthy();
});

test("a missing folder offers to make it from scratch, under its text", async () => {
  const missing = "/home/ann/lado/shop";
  folders[missing] = folder(missing, {
    ok: false,
    root: null,
    branch: null,
    problem: `${missing} does not exist`,
    problem_kind: "missing",
    scratch: true,
  });
  const dialog = await openLaunch();
  type(missing);
  expect(await within(dialog).findByText("There is no such folder — LADO will create it.")).toBeTruthy();
  expect(within(dialog).getByRole("button", { name: "Start from scratch here" })).toBeTruthy();
});

// A plain folder of files (capability folder-setup)

const NOTES = "/Users/ann/workspace/notes";

function plain(more: Partial<NonNullable<FolderInfo["setup"]>> = {}): FolderInfo {
  return folder(NOTES, {
    ok: false,
    root: null,
    branch: null,
    default_name: "notes",
    free_name: "notes",
    name_state: "free",
    problem: `${NOTES} is not inside a git repository`,
    problem_kind: "not_repo",
    hint: { text: "Make it a repository with a first commit, in that folder:", command: "git init && git add -A && git commit -m 'First commit'" },
    provider: { name: "claude", reason: "only_installed" },
    setup: {
      files: 128,
      bytes: 4404019,
      left_out: [
        { path: ".env", reason: "secret", size: 120, line: "/.env" },
        { path: "talk.mp4", reason: "large", size: 251658240, line: "/talk.mp4" },
        { path: "old-site/", reason: "repository", size: null, line: "/old-site/" },
      ],
      refusal: null,
      author: null,
      make: "git init && git add -A && git commit -m 'First commit'",
      max_files: 20000,
      ...more,
    },
  });
}

test("a plain folder shows what Set up and start saves, and the button sets it up and starts", async () => {
  folders[NOTES] = plain();
  answers["POST /api/sessions"] = () => json({ session: session("notes", { repo: NOTES }), ...STARTED });
  const dialog = await openLaunch();
  type(NOTES);
  const panel = (await within(dialog).findByText(/Not yet set up for LADO/)).closest(".setup-panel") as HTMLElement;
  expect(panel.querySelector("p")!.textContent).toBe(
    "Not yet set up for LADO. Starting saves 128 files (4.2 MB) as the starting point. ",
  );
  expect(dialog.querySelector(".field-note.bad")).toBeNull(); // no refusal
  expect(within(dialog).queryByText(/git init/)).toBeNull(); // the command only under Do it yourself
  await waitFor(() => expect(startButton().disabled).toBe(false));
  expect(startButton().textContent).toBe("Set up and start in notes");
  fireEvent.click(startButton());
  expect(await screen.findByRole("region", { name: "Session notes" })).toBeTruthy();
  expect(calls.find((c) => c.method === "POST")!.body).toMatchObject({
    where: { kind: "setup", path: NOTES, include: [] },
    name: "notes",
  });
});

test("Review ticks a left-out file in: the count, its warning and the command follow", async () => {
  folders[NOTES] = plain();
  const dialog = await openLaunch();
  type(NOTES);
  const review = await within(dialog).findByRole("button", { name: "3 left out · Review" });
  fireEvent.click(review);
  expect(review.getAttribute("aria-expanded")).toBe("true");
  const list = within(dialog).getByRole("list", { name: "Left out" });
  expect((within(list).getByRole("checkbox", { name: "Include old-site/" }) as HTMLInputElement).disabled).toBe(true);
  expect(within(list).getByText("240 MB, larger than 50 MB")).toBeTruthy();
  fireEvent.click(within(list).getByRole("checkbox", { name: "Include .env" }));
  expect(dialog.querySelector(".setup-panel p")!.textContent).toContain("129 files (4.2 MB)");
  expect(within(list).getByText("Will be saved in the history.")).toBeTruthy();
  expect(within(dialog).getByRole("button", { name: "2 left out · Review" })).toBeTruthy();
  fireEvent.click(within(dialog).getByRole("button", { name: "Do it yourself" }));
  expect(within(dialog).queryByRole("list", { name: "Left out" })).toBeNull(); // one open at a time
  expect(within(dialog).getByText("Run in this folder, then choose it again:")).toBeTruthy();
  expect(
    within(dialog).getByText(
      "printf '%s\\n' /talk.mp4 /old-site/ >> .gitignore && git init && git add -A && git commit -m 'First commit'",
    ),
  ).toBeTruthy();
  answers["POST /api/sessions"] = () => json({ session: session("notes", { repo: NOTES }), ...STARTED });
  fireEvent.click(startButton());
  await screen.findByRole("region", { name: "Session notes" });
  expect(calls.find((c) => c.method === "POST")!.body).toMatchObject({ where: { kind: "setup", path: NOTES, include: [".env"] } });
});

test("a folder too big or the home folder is refused, with the footer's reason", async () => {
  folders[NOTES] = plain({ refusal: { kind: "too_big", files: 20001, bytes: 1, line: "" } });
  const dialog = await openLaunch();
  type(NOTES);
  const refusal = await within(dialog).findByText("Choose a smaller folder: this one holds over 20,000 files.");
  expect(refusal.getAttribute("role")).toBe("alert");
  expect(startButton().disabled).toBe(true);
  await waitFor(() => expect(footerText()).toContain("To start: choose a smaller folder."));
  folders["/Users/ann"] = { ...plain({ refusal: { kind: "home", files: 0, bytes: 0, line: "" } }), path: "/Users/ann" };
  type("/Users/ann");
  expect(await within(dialog).findByText("Choose a smaller folder: this is your home folder.")).toBeTruthy();
});

test("git's missing author keeps the set-up off; Check again checks the folder anew", async () => {
  const author = {
    text: "git doesn't know who signs the agents' commits: it has no user.name or user.email",
    hint: {
      text: "Tell git who you are, once for this computer:",
      command: 'git config --global user.name "Your Name" && git config --global user.email you@example.com',
    },
  };
  folders[NOTES] = plain({ author });
  const dialog = await openLaunch();
  type(NOTES);
  expect(await within(dialog).findByText("Git doesn't know who you are yet. Tell it once for this computer:")).toBeTruthy();
  expect(within(dialog).getByText(author.hint.command)).toBeTruthy();
  expect(startButton().disabled).toBe(true);
  await waitFor(() => expect(footerText()).toContain("To start: tell git who you are."));
  const asked = () => calls.filter((c) => c.path === `/api/folders?path=${encodeURIComponent(NOTES)}`).length;
  const before = asked();
  folders[NOTES] = plain();
  fireEvent.click(within(dialog).getByRole("button", { name: "Check again" }));
  await waitFor(() => expect(asked()).toBe(before + 1));
  await waitFor(() => expect(startButton().disabled).toBe(false));
});

// The folder check held back until the test lets it go.
function holdFolders() {
  let release = () => {};
  const held = new Promise<void>((resolve) => (release = resolve));
  answers["GET /api/folders"] = async () => {
    const asked = new URL(calls[calls.length - 1].path, "http://lado.test").searchParams.get("path") ?? "";
    await held;
    return json(folders[asked]);
  };
  return release;
}

test("Check again keeps the author's text with Checking… and the focus, then the panel follows the answer", async () => {
  const author = { text: "no author", hint: { text: "Tell git who you are, once for this computer:", command: "git config x" } };
  folders[NOTES] = plain({ author });
  const dialog = await openLaunch();
  type(NOTES);
  const again = await within(dialog).findByRole("button", { name: "Check again" });
  const release = holdFolders();
  folders[NOTES] = plain();
  again.focus();
  fireEvent.click(again);
  await waitFor(() => expect(again.textContent).toBe("Checking…"));
  expect(again.getAttribute("aria-disabled")).toBe("true");
  expect(document.activeElement).toBe(again);
  expect(footerText()).toContain("To start: wait for the count.");
  await act(async () => release());
  await within(dialog).findByText("128 files (4.2 MB)");
  await waitFor(() => expect(document.activeElement).toBe(firstField()));
});

test("while a plain folder without its author's problem is checked again, the panel reads Counting files…", async () => {
  folders[NOTES] = plain();
  answers["POST /api/sessions"] = () => json({ detail: "kit nope not found" }, 400);
  const dialog = await openLaunch();
  type(NOTES);
  await waitFor(() => expect(startButton().disabled).toBe(false));
  const release = holdFolders();
  fireEvent.click(startButton()); // refused: the folder is checked again
  expect(await within(dialog).findByText("Counting files…")).toBeTruthy();
  expect(footerText()).toContain("To start: wait for the count.");
  expect(startButton().disabled).toBe(true);
  await act(async () => release());
  await within(dialog).findByText("128 files (4.2 MB)");
});

test("a check again that fails shows its error, not a count that never ends", async () => {
  folders[NOTES] = plain();
  answers["POST /api/sessions"] = () => json({ detail: "kit nope not found" }, 400);
  const dialog = await openLaunch();
  type(NOTES);
  await waitFor(() => expect(startButton().disabled).toBe(false));
  answers["GET /api/folders"] = () => json({ detail: "the server cannot look at it" }, 500);
  fireEvent.click(startButton());
  expect(await within(dialog).findByText("the server cannot look at it")).toBeTruthy();
  expect(within(dialog).queryByText("Counting files…")).toBeNull();
  expect(footerText()).not.toContain("wait for the count");
});

test.each([
  [{ kind: "unreadable", files: 0, bytes: 0, line: "warning: could not open directory 'x/'" }, "Choose another folder: git cannot read all of it"],
  [{ kind: "odd_name", files: 0, bytes: 0, line: ".env\\nok" }, "Choose another folder, or rename .env\\nok"],
] as const)("a %s refusal says choose another folder, here and in the footer", async (refusal, text) => {
  folders[NOTES] = plain({ refusal });
  const dialog = await openLaunch();
  type(NOTES);
  expect(await within(dialog).findByText(new RegExp(`^${text.replaceAll("\\", "\\\\")}`))).toBeTruthy();
  await waitFor(() => expect(footerText()).toContain("To start: choose another folder."));
});

test("a tick of a file the new preview no longer leaves out is not sent", async () => {
  folders[NOTES] = plain();
  answers["POST /api/sessions"] = () => json({ detail: "kit nope not found" }, 400);
  const dialog = await openLaunch();
  type(NOTES);
  fireEvent.click(await within(dialog).findByRole("button", { name: "3 left out · Review" }));
  fireEvent.click(within(dialog).getByRole("checkbox", { name: "Include .env" }));
  fireEvent.click(within(dialog).getByRole("checkbox", { name: "Include talk.mp4" }));
  folders[NOTES] = plain({ left_out: [{ path: "talk.mp4", reason: "large", size: 251658240, line: "/talk.mp4" }] });
  await waitFor(() => expect(startButton().disabled).toBe(false));
  fireEvent.click(startButton()); // refused: checked again, .env is no longer left out
  await within(dialog).findByRole("button", { name: /left out · Review/ });
  await waitFor(() => expect(startButton().disabled).toBe(false));
  answers["POST /api/sessions"] = () => json({ session: session("notes", { repo: NOTES }), ...STARTED });
  fireEvent.click(startButton());
  await screen.findByRole("region", { name: "Session notes" });
  const sent = calls.filter((c) => c.method === "POST").pop()!;
  expect(sent.body).toMatchObject({ where: { kind: "setup", include: ["talk.mp4"] } });
});

test("a path typed with ~ is checked, though the server answers it expanded", async () => {
  folders["~/w/app"] = folder("/home/ann/w/app", { provider: { name: "claude", reason: "only_installed" } });
  folders["~/w/"] = folder("/home/ann/w/", { ok: false, problem: "no", subfolders: ["app", "api"] });
  await openLaunch();
  type("~/w/a");
  const list = await screen.findByRole("listbox", { name: "Folders" });
  expect(within(list).getAllByRole("option").map((o) => o.textContent)).toEqual(["app/", "api/"]);
  type("~/w/app");
  expect(await screen.findByText("✓ Ready · branch main")).toBeTruthy();
  await waitFor(() => expect(startButton().disabled).toBe(false));
  expect(screen.queryByText("checking…")).toBeNull();
});

test("a set-up refused at the start shows the core's line and leaves Where on the folder", async () => {
  folders[NOTES] = plain();
  answers["POST /api/sessions"] = () => json({ detail: `git could not set up ${NOTES}: fatal: no commit today` }, 400);
  const dialog = await openLaunch();
  type(NOTES);
  await waitFor(() => expect(startButton().disabled).toBe(false));
  fireEvent.click(startButton());
  await waitFor(() => expect(startButton().textContent).not.toBe("Setting up…"));
  expect((await within(dialog).findByRole("alert")).textContent).toBe(`git could not set up ${NOTES}: fatal: no commit today`);
  expect(where().value).toBe(NOTES);
});

// Project (openspec change new-session-in-project)

async function openProject() {
  const dialog = await openLaunch();
  await pickPlace("Project…");
  await within(dialog).findByRole("radiogroup", { name: "Repository" });
  return dialog;
}

const repoRadio = (dialog: HTMLElement, name: string) => within(dialog).getByRole("radio", { name: new RegExp(`^${name}`) });
const startIn = (title: string) =>
  screen.getByRole("button", { name: new RegExp(`^Start (new session )?in ${title}$`) }) as HTMLButtonElement;

test("Project chooses the last used repository and takes its last session's settings", async () => {
  sessions = [session("shop-backend", { status: "stopped", repo: "/real/projects/shop/backend", project: "shop" })];
  const dialog = await openProject();
  expect((within(dialog).getByRole("combobox", { name: "Project" }) as HTMLSelectElement).value).toBe("shop");
  expect(repoRadio(dialog, "backend").getAttribute("aria-checked")).toBe("true");
  await waitFor(() => expect(teamSummary()).toContain("Setup team"));
  await waitFor(() => expect(providerSelect().value).toBe("kilo"));
  expect(modeChosen()).toBe("plan");
  expect(await screen.findByRole("button", { name: "Resume shop-backend" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Start new session in Shop" })).toBeTruthy();
  expect(calls.some((c) => c.path === "/api/kits?where=%2Freal%2Fprojects%2Fshop%2Fbackend")).toBe(true);
});

test("Start names the project the session goes to, and follows the choice", async () => {
  const dialog = await openProject();
  await waitFor(() => expect(startIn("Shop")).toBeTruthy());
  fireEvent.change(within(dialog).getByRole("combobox", { name: "Project" }), { target: { value: "acme" } });
  expect(await screen.findByRole("button", { name: "Start in ACME CRM" })).toBeTruthy();
});

test("Start in starts in the project's repository chosen", async () => {
  answers["POST /api/sessions"] = () =>
    json({ session: session("shop-frontend", { repo: "/ws/projects/shop/frontend", project: "shop" }), ...STARTED });
  const dialog = await openProject();
  fireEvent.click(repoRadio(dialog, "frontend"));
  await waitFor(() => expect(nameField().value).toBe("shop-frontend"));
  expect(calls.some((c) => c.path === "/api/project-launch?project=shop&repo=frontend")).toBe(true);
  // A change reaches a field that is off, and its empty value would count as the human's choice.
  await waitFor(() => expect(providerSelect().disabled).toBe(false));
  fireEvent.change(providerSelect(), { target: { value: "claude" } });
  await waitFor(() => expect(startIn("Shop").disabled).toBe(false));
  fireEvent.click(startIn("Shop"));
  await screen.findByRole("region", { name: "Session shop-frontend" });
  const sent = calls.find((c) => c.method === "POST" && c.path === "/api/sessions")!;
  expect(sent.body).toEqual({
    where: { kind: "project", project: "shop", repo: "frontend" },
    name: "shop-frontend",
    kits: ["default"], // frontend has no last session: LADO's defaults, as for a folder
    provider: "claude",
  });
});

test("Resume is offered only for a stopped session of the name that is of this project", async () => {
  sessions = [session("shop-backend", { status: "stopped", repo: "/real/projects/shop/backend", project: null })];
  await openProject();
  await waitFor(() => expect(startIn("Shop").disabled).toBe(false));
  expect(screen.queryByRole("button", { name: "Resume shop-backend" })).toBeNull();
});

test("an empty project leaves Start off and leads to its page", async () => {
  answers["GET /api/projects/acme"] = () => json({ detail: 'unknown project "acme"' }, 404);
  const dialog = await openProject();
  fireEvent.change(within(dialog).getByRole("combobox", { name: "Project" }), { target: { value: "acme" } });
  fireEvent.click(await within(dialog).findByRole("button", { name: "Open ACME CRM" }));
  expect(screen.queryByRole("dialog", { name: "New session" })).toBeNull();
  await waitFor(() => expect(calls.some((c) => c.path === "/api/projects/acme")).toBe(true));
});

test("Start is off in an empty project", async () => {
  projectLaunch = () => shopLaunch("acme", null);
  const dialog = await openLaunch();
  await pickPlace("Project…");
  await within(dialog).findByText(/No repositories yet/);
  expect(startIn("ACME CRM").disabled).toBe(true);
  expect(nameField().value).toBe("");
});

const SHOP_PLACE = { id: "shop", title: "Shop", repo: "frontend" };

test("while the server answers a new choice, the list stays, keeps the focus and Start waits", async () => {
  const dialog = await openProject();
  let release = () => {};
  answers["GET /api/project-launch"] = async () => {
    const asked = calls[calls.length - 1].path;
    await new Promise<void>((resolve) => {
      release = resolve;
    });
    const query = new URL(asked, "http://lado.test").searchParams;
    return json(shopLaunch(query.get("project"), query.get("repo")));
  };
  await waitFor(() => expect(startIn("Shop").disabled).toBe(false));
  repoRadio(dialog, "backend").focus();
  fireEvent.keyDown(repoRadio(dialog, "backend"), { key: "ArrowDown" });
  // Asked, not answered: the list is there, the focus on frontend, chosen at once.
  await waitFor(() => expect(calls.some((c) => c.path === "/api/project-launch?project=shop&repo=frontend")).toBe(true));
  expect(document.activeElement).toBe(repoRadio(dialog, "frontend"));
  expect(repoRadio(dialog, "frontend").getAttribute("aria-checked")).toBe("true");
  expect(within(dialog).getByRole("combobox", { name: "Project" })).toBeTruthy();
  expect(startIn("Shop").disabled).toBe(true); // what a start takes is not known yet
  fireEvent.keyDown(document.activeElement!, { key: "ArrowDown" });
  expect(document.activeElement).toBe(repoRadio(dialog, "backend"));
  await waitFor(() => expect(calls.some((c) => c.path === "/api/project-launch?project=shop&repo=backend")).toBe(true));
  await act(async () => release());
  await waitFor(() => expect(nameField().value).toBe("shop-backend"));
  await waitFor(() => expect(startIn("Shop").disabled).toBe(false));
  expect(repoRadio(dialog, "backend").getAttribute("aria-checked")).toBe("true");
});

test("Folder's refusal of a project's repository turns Where to the project with it", async () => {
  folders["/ws/projects/shop/frontend"] = folder("/ws/projects/shop/frontend", {
    ok: false,
    problem: IN_SHOP,
    root: null,
    branch: null,
    problem_kind: "in_project",
    hint: SHOP_HINT,
    default_name: null,
    name_state: null,
    project: SHOP_PLACE,
  });
  const dialog = await openLaunch();
  type("/ws/projects/shop/frontend");
  const box = (await screen.findByText(IN_SHOP)).closest(".field-note.bad") as HTMLElement;
  expect(within(box).getByText(SHOP_HINT.command)).toBeTruthy(); // the command stays below
  fireEvent.click(within(box).getByRole("button", { name: "Start in the project Shop" }));
  await waitFor(() => expect(placeBox().value).toBe("frontend"));
  expect(within(dialog).getByText("Project Shop", { selector: ".place-text .place-badge" })).toBeTruthy();
  await waitFor(() => expect(nameField().value).toBe("shop-frontend"));
  expect(calls.some((c) => c.path === "/api/project-launch?project=shop&repo=frontend")).toBe(true);
});

test("Folder's refusal of another folder of a project opens the project", async () => {
  const notes = "/ws/projects/shop/notes";
  answers["GET /api/projects/shop"] = () => json({ detail: 'unknown project "shop"' }, 404);
  folders[notes] = folder(notes, {
    ok: false,
    problem: `${notes} belongs to the project Shop: start a session in the project`,
    root: null,
    branch: null,
    problem_kind: "in_project",
    hint: { text: "See the project's repositories:", command: "lado project show shop" },
    default_name: null,
    name_state: null,
    project: { ...SHOP_PLACE, repo: null },
  });
  const dialog = await openLaunch();
  type(notes);
  expect(within(dialog).queryByRole("button", { name: "Start in the project Shop" })).toBeNull();
  fireEvent.click(await within(dialog).findByRole("button", { name: "Open the project Shop" }));
  expect(screen.queryByRole("dialog", { name: "New session" })).toBeNull();
  await waitFor(() => expect(calls.some((c) => c.path === "/api/projects/shop")).toBe(true));
});

test("a refusal outside a project offers no project", async () => {
  await openLaunch();
  folders["/tmp/x"] = folder("/tmp/x", { ok: false, problem: "/tmp/x does not exist", problem_kind: "missing", root: null });
  type("/tmp/x");
  await screen.findByText("/tmp/x does not exist");
  expect(screen.queryByRole("button", { name: /in the project|Open the project/ })).toBeNull();
});
