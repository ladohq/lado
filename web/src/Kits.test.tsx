import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { InstalledKitInfo, MarketplaceInfo, OfferInfo, OutdatedInfo, PlanInfo } from "./api";
import { App } from "./App";
import { FakeEventSource, stream, stubDialogs } from "./fakes";

const GIT = { kind: "git", folder: null, valid: true, problem: null, updated_at: null, missing: false } as const;
const AT = "2026-10-05T08:00:00Z";

const INSTALLED: InstalledKitInfo[] = [
  {
    ...GIT,
    name: "jira",
    version: "1.1.0",
    description: "Tasks in Jira.",
    address: "https://github.com/acme/kit-jira.git",
    tag: "v1.1.0",
    commit: "9f3c2ab",
    marketplace: "old",
    installed_at: AT,
    agents: 0,
    skills: 2,
    flows: 0,
    mcp: ["jira"],
  },
  {
    ...GIT,
    name: "lado-dev",
    version: "0.9.1",
    description: "Develop LADO itself.",
    address: "https://github.com/ladohq/kit-lado-dev.git",
    tag: "v0.9.1",
    commit: "4be21c0",
    marketplace: "official",
    installed_at: AT,
    agents: 4,
    skills: 12,
    flows: 2,
    mcp: [],
  },
  {
    name: "my-reviewers",
    version: "",
    description: "",
    valid: false,
    problem: 'kit "my-reviewers": its folder /work/my-reviewers is missing',
    kind: "folder",
    address: null,
    tag: null,
    commit: null,
    folder: "/work/my-reviewers",
    marketplace: null,
    installed_at: AT,
    updated_at: null,
    agents: 0,
    skills: 0,
    flows: 0,
    mcp: [],
    missing: true,
  },
  {
    name: "default",
    version: "0.1.0",
    description: "A supervisor that delegates.",
    valid: true,
    problem: null,
    kind: "built-in",
    address: null,
    tag: null,
    commit: null,
    folder: null,
    marketplace: null,
    installed_at: null,
    updated_at: null,
    agents: 2,
    skills: 0,
    flows: 0,
    mcp: [],
    missing: false,
  },
];

const MARKET = { updated_at: AT, index: true, problem: null, enabled: true, official: false } as const;
const MARKETS: MarketplaceInfo[] = [
  { ...MARKET, name: "official", url: "https://github.com/ladohq/marketplace.git", official: true, kits: 2 },
  {
    ...MARKET,
    name: "team",
    url: "https://github.com/acme/marketplace.git",
    kits: 1,
    problem: "index.json is invalid: index must be a whole number",
  },
];

const OFFERS: OfferInfo[] = [
  {
    name: "lado-dev",
    marketplace: "official",
    address: "https://github.com/ladohq/kit-lado-dev.git",
    installed: true,
    index: null,
  },
  {
    name: "reviewers",
    marketplace: "official",
    address: "https://github.com/ladohq/kit-reviewers.git",
    installed: false,
    index: {
      address: "https://github.com/ladohq/kit-reviewers.git",
      latest: "v2.0.0",
      commit: null,
      lado: null,
      description: "Strict reviewers.",
      agents: { reviewer: "reviews" },
      skills: ["review"],
      flows: null,
      mcp: null,
    },
  },
  {
    name: "wiki",
    marketplace: "team",
    address: "https://github.com/acme/kit-wiki.git",
    installed: false,
    index: null,
  },
];

const PLAN: PlanInfo = {
  name: "wiki",
  version: "1.0.0",
  description: "A wiki.",
  spec: "wiki@v1.0.0",
  address: "https://github.com/acme/kit-wiki.git",
  tag: "v1.0.0",
  commit: "abc1234",
  source: "marketplace team",
  marketplace: "team",
  installed: null,
  needs_confirmation: true,
  current: false,
  versions: ["v1.0.0"],
  agents: ["writer"],
  skills: ["wiki"],
  flows: [],
  mcp: [{ name: "wiki", command: "npx -y wiki-mcp" }],
  new_mcp: [],
  warnings: [],
  notes: [],
  users: null,
};

type Answer = { status?: number; body?: unknown };
type Route = (body: unknown) => Answer | unknown;

let routes: Record<string, Route>;
let calls: { method: string; path: string; body: unknown }[];

// The API: each route is "METHOD path"; an answer with `status` is that answer, anything
// else is the body of a 200.
function serve(extra: Record<string, Route> = {}) {
  routes = {
    "GET /api/sessions": () => [],
    "GET /api/health": () => ({ ok: true, version: "x" }),
    "GET /api/kits/installed": () => INSTALLED,
    "GET /api/kits/available": () => OFFERS,
    "GET /api/marketplaces": () => MARKETS,
    ...extra,
  };
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ method, path, body });
      if (path.startsWith("/api/events")) return new Response("");
      const route = routes[`${method} ${path}`];
      if (!route) return new Response(JSON.stringify({ detail: `no route ${method} ${path}` }), { status: 404 });
      const got = (await route(body)) as Answer;
      if (got !== null && typeof got === "object" && "status" in got) {
        if (got.status === 204) return new Response(null, { status: 204 });
        return new Response(JSON.stringify(got.body), { status: got.status });
      }
      return new Response(JSON.stringify(got));
    }),
  );
}

const asked = (method: string, path: string) => calls.filter((one) => one.method === method && one.path === path);

function open(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  localStorage.clear();
  stubDialogs();
  serve();
  FakeEventSource.all = [];
  FakeEventSource.autoStart = true;
  vi.stubGlobal("EventSource", FakeEventSource);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const page = () => screen.getByRole("main");
const kitList = () => screen.getByRole("list", { name: "Kits" });
const kitRow = (name: string) => within(kitList()).getByRole("listitem", { name });
const kitNames = () => within(kitList()).getAllByRole("listitem").map((row) => row.getAttribute("aria-label"));
const marketplacesBlock = () => screen.getByRole("complementary", { name: "Marketplaces" });

// Addresses and tabs

test("/kits opens Installed; each tab has its address", async () => {
  open("/kits");
  const tabs = await screen.findByRole("navigation", { name: "Kits" });
  const current = within(tabs).getByRole("link", { current: "page" });
  expect(current.textContent).toMatch(/^Installed/);
  expect(within(tabs).getByRole("link", { name: /Available/ }).getAttribute("href")).toBe("/kits/available");
  expect(within(tabs).getByRole("link", { name: /Updates/ }).getAttribute("href")).toBe("/kits/updates");
});

test.each([
  ["/kits/available", /^Available/],
  ["/kits/updates", /^Updates/],
])("%s opens its tab", async (path, name) => {
  open(path);
  const tabs = await screen.findByRole("navigation", { name: "Kits" });
  expect(within(tabs).getByRole("link", { current: "page" }).textContent).toMatch(name);
});

test("/marketplace goes to /kits; the rail has no Marketplace", async () => {
  open("/marketplace");
  expect(await screen.findByRole("navigation", { name: "Kits" })).toBeTruthy();
  const rail = screen.getByRole("navigation", { name: "Sections" });
  expect(within(rail).queryByRole("link", { name: "Marketplace" })).toBeNull();
  expect(within(rail).getByRole("link", { name: "Kits" }).getAttribute("aria-current")).toBe("page");
});

test("/kits/elsewhere is Not found", async () => {
  open("/kits/elsewhere");
  expect(await screen.findByText("There is no page at this address.")).toBeTruthy();
});

// Installed

test("Installed shows each kit with its source; built-in ones have no buttons", async () => {
  open("/kits");
  const dev = await screen.findByRole("listitem", { name: "lado-dev" });
  expect(within(dev).getByText("v0.9.1")).toBeTruthy();
  expect(within(dev).getByText("official")).toBeTruthy();
  expect(within(dev).getByText("4 roles · 12 skills · 2 flows")).toBeTruthy();
  expect(within(dev).getByRole("button", { name: "Update lado-dev…" })).toBeTruthy();
  expect(within(dev).getByRole("button", { name: "Remove lado-dev…" })).toBeTruthy();
  // A kit of a marketplace removed since says so; the UI counts it from the two lists.
  expect(within(kitRow("jira")).getByText("old (removed)")).toBeTruthy();
  const mine = kitRow("my-reviewers");
  expect(within(mine).getByText("folder")).toBeTruthy();
  expect(within(mine).getByRole("alert").textContent).toContain("is missing");
  expect(within(mine).queryByRole("button", { name: /Update/ })).toBeNull();
  const builtin = kitRow("default");
  expect(within(builtin).getByText("built-in")).toBeTruthy();
  expect(within(builtin).queryAllByRole("button")).toEqual([]);
});

test("a kit installed elsewhere (the CLI) comes in through the feed, without a reload", async () => {
  open("/kits");
  await screen.findByRole("listitem", { name: "lado-dev" });
  const loads = asked("GET", "/api/kits/installed").length;
  const added: InstalledKitInfo = { ...INSTALLED[1], name: "added", description: "From the CLI." };
  stream().send("change", { kind: "kits", session: "", key: "added", op: "insert", item: added }, "11");
  expect(await screen.findByRole("listitem", { name: "added" })).toBeTruthy();
  stream().send("change", { kind: "kits", session: "", key: "jira", op: "delete", item: null }, "12");
  await waitFor(() => expect(screen.queryByRole("listitem", { name: "jira" })).toBeNull());
  expect(asked("GET", "/api/kits/installed")).toHaveLength(loads);
  // Available is asked again: what is installed changed.
  await waitFor(() => expect(asked("GET", "/api/kits/available").length).toBeGreaterThan(1));
});

test("the search and the source chips filter the kits; the chip is remembered", async () => {
  open("/kits");
  await screen.findByRole("listitem", { name: "lado-dev" });
  fireEvent.change(screen.getByRole("searchbox", { name: "Find a kit" }), { target: { value: "JIRA" } });
  expect(kitNames()).toEqual(["jira"]);
  fireEvent.change(screen.getByRole("searchbox", { name: "Find a kit" }), { target: { value: "" } });
  const chips = screen.getByRole("group", { name: "Source" });
  expect(within(chips).getAllByRole("button").map((chip) => chip.textContent)).toEqual([
    "All",
    "official",
    "team",
    "git",
    "folder",
    "built-in",
  ]);
  fireEvent.click(within(chips).getByRole("button", { name: "folder" }));
  expect(kitNames()).toEqual(["my-reviewers"]);
  expect(localStorage.getItem("lado.kitsSource")).toBe("folder");
  cleanup();
  open("/kits");
  await screen.findByRole("listitem", { name: "my-reviewers" });
  expect(screen.queryByRole("listitem", { name: "lado-dev" })).toBeNull();
});

// Available

test("Available lists the marketplaces' kits; an installed one has no Install", async () => {
  open("/kits/available");
  const reviewers = await screen.findByRole("listitem", { name: "reviewers" });
  expect(within(reviewers).getByText("Strict reviewers.")).toBeTruthy();
  expect(within(reviewers).getByText("v2.0.0")).toBeTruthy();
  expect(within(reviewers).getByRole("button", { name: "Install reviewers…" })).toBeTruthy();
  // Without an index.json entry: its name and address.
  expect(within(kitRow("wiki")).getByText("https://github.com/acme/kit-wiki.git")).toBeTruthy();
  const dev = kitRow("lado-dev");
  expect(within(dev).getByText("installed")).toBeTruthy();
  expect(within(dev).queryByRole("button")).toBeNull();
});

test("on a fresh LADO_HOME Available says no marketplace is fetched, with Update", async () => {
  const fresh: MarketplaceInfo = { ...MARKETS[0], updated_at: null, kits: null, index: false, problem: "not fetched yet: update it" };
  serve({
    "GET /api/kits/installed": () => [INSTALLED[3]],
    "GET /api/kits/available": () => [],
    "GET /api/marketplaces": () => [fresh],
    "POST /api/marketplaces/update": () => [{ name: "official", marketplace: MARKETS[0], error: null }],
  });
  open("/kits/available");
  expect(await screen.findByText("No marketplace fetched yet.")).toBeTruthy();
  expect(asked("POST", "/api/marketplaces/update")).toHaveLength(0); // nothing is cloned by itself
  fireEvent.click(within(page()).getByRole("button", { name: "Update official" }));
  await waitFor(() => expect(asked("POST", "/api/marketplaces/update")).toHaveLength(1));
  expect(asked("POST", "/api/marketplaces/update")[0].body).toEqual({ name: "official" });
});

// Updates

test("updates are checked only with the button", async () => {
  const outdated: OutdatedInfo[] = [
    { name: "lado-dev", installed: "v0.9.1", latest: "v0.10.0", pre: null, note: "", warnings: [], newer: "v0.10.0" },
    { name: "jira", installed: "v1.1.0", latest: "v1.1.0", pre: null, note: "", warnings: [], newer: null },
    {
      name: "my-reviewers",
      installed: "",
      latest: null,
      pre: null,
      note: "local, not checked",
      warnings: [],
      newer: null,
    },
  ];
  serve({ "POST /api/kits/check-updates": () => outdated });
  open("/kits/updates");
  expect(await screen.findByText("Check for updates to see them.")).toBeTruthy();
  expect(asked("POST", "/api/kits/check-updates")).toHaveLength(0);
  fireEvent.click(within(page()).getAllByRole("button", { name: "Check for updates" })[0]);
  const dev = await screen.findByRole("listitem", { name: "lado-dev" });
  expect(within(dev).getByText("v0.10.0 available")).toBeTruthy();
  expect(screen.queryByRole("listitem", { name: "jira" })).toBeNull();
  expect(screen.getByText("my-reviewers: local, not checked")).toBeTruthy();
  expect(screen.getByText(/^Updates checked/)).toBeTruthy();
  const tabs = screen.getByRole("navigation", { name: "Kits" });
  expect(within(tabs).getByRole("link", { name: /Updates/ }).textContent).toBe("Updates 1");
  // The badge is on Installed too.
  fireEvent.click(within(tabs).getByRole("link", { name: /Installed/ }));
  expect(within(await screen.findByRole("listitem", { name: "lado-dev" })).getByText("v0.10.0 available")).toBeTruthy();
});

test("a kit updated since the check is no longer an update", async () => {
  const outdated: OutdatedInfo[] = [
    { name: "lado-dev", installed: "v0.9.1", latest: "v0.10.0", pre: null, note: "", warnings: [], newer: "v0.10.0" },
  ];
  serve({ "POST /api/kits/check-updates": () => outdated });
  open("/kits/updates");
  fireEvent.click((await within(page()).findAllByRole("button", { name: "Check for updates" }))[0]);
  await screen.findByRole("listitem", { name: "lado-dev" });
  const updated: InstalledKitInfo = { ...INSTALLED[1], tag: "v0.10.0", version: "0.10.0" };
  stream().send("change", { kind: "kits", session: "", key: "lado-dev", op: "update", item: updated }, "11");
  const tabs = screen.getByRole("navigation", { name: "Kits" });
  await waitFor(() => expect(within(tabs).getByRole("link", { name: /Updates/ }).textContent).toBe("Updates 0"));
  expect(screen.queryByRole("listitem", { name: "lado-dev" })).toBeNull();
  fireEvent.click(within(tabs).getByRole("link", { name: /Installed/ }));
  const dev = await screen.findByRole("listitem", { name: "lado-dev" });
  expect(within(dev).getByText("v0.10.0")).toBeTruthy();
  expect(within(dev).queryByText("v0.10.0 available")).toBeNull();
});

// Install

function addKit() {
  fireEvent.click(within(page()).getByRole("button", { name: "Add kit…" }));
  return screen.getByRole("dialog", { name: "Add kit" });
}

test("Add kit shows the core's plan and installs its tag and commit only after the check", async () => {
  serve({
    "POST /api/kits/plan": () => PLAN,
    "POST /api/kits/install": () => INSTALLED[1],
  });
  open("/kits");
  await screen.findByRole("listitem", { name: "lado-dev" });
  const dialog = addKit();
  fireEvent.change(within(dialog).getByRole("combobox", { name: "Marketplace" }), { target: { value: "team" } });
  fireEvent.change(within(dialog).getByRole("combobox", { name: "Kit" }), { target: { value: "wiki" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Next" }));
  const plan = await screen.findByRole("dialog", { name: "Install wiki v1.0.0?" });
  expect(asked("POST", "/api/kits/plan")[0].body).toEqual({ spec: "wiki", marketplace: "team", pre: false });
  expect(within(plan).getByText("npx -y wiki-mcp", { exact: false })).toBeTruthy();
  expect(within(plan).getByText(/Not from the official marketplace/)).toBeTruthy();
  const install = within(plan).getByRole("button", { name: "Install" });
  expect((install as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(within(plan).getByRole("checkbox", { name: "I checked the address and the MCP servers" }));
  expect((install as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(install);
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(asked("POST", "/api/kits/install")[0].body).toEqual({
    spec: "wiki@v1.0.0",
    marketplace: "team",
    commit: "abc1234",
  });
});

test("an official kit needs no check; a folder sends the MCP servers the plan showed", async () => {
  const folder: PlanInfo = {
    ...PLAN,
    name: "mine",
    spec: "/work/mine",
    address: "/work/mine",
    tag: null,
    commit: null,
    source: "folder",
    marketplace: null,
    needs_confirmation: false,
    versions: [],
  };
  serve({ "POST /api/kits/plan": () => folder, "POST /api/kits/install": () => INSTALLED[2] });
  open("/kits");
  await screen.findByRole("listitem", { name: "lado-dev" });
  const dialog = addKit();
  fireEvent.click(within(dialog).getByRole("radio", { name: "Folder" }));
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Folder" }), { target: { value: "/work/mine" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Next" }));
  const plan = await screen.findByRole("dialog", { name: "Install mine from a folder?" });
  expect(within(plan).queryByRole("checkbox")).toBeNull();
  fireEvent.click(within(plan).getByRole("button", { name: "Install" }));
  await waitFor(() => expect(asked("POST", "/api/kits/install")).toHaveLength(1));
  expect(asked("POST", "/api/kits/install")[0].body).toEqual({ spec: "/work/mine", mcp: ["wiki"] });
});

test("a refused plan shows the core's words with Back; a 409 asks to look at the plan again", async () => {
  let refuse = true;
  serve({
    "POST /api/kits/plan": () =>
      refuse ? { status: 400, body: { detail: { message: "jira v1.2.0 needs LADO 0.22", switch_off: [] } } } : PLAN,
    "POST /api/kits/install": () => ({ status: 409, body: { detail: "the kit changed since the plan: v1.0.0 moved" } }),
  });
  open("/kits");
  await screen.findByRole("listitem", { name: "lado-dev" });
  let dialog = addKit();
  fireEvent.click(within(dialog).getByRole("radio", { name: "Git address" }));
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Git address" }), {
    target: { value: "https://github.com/acme/kit-jira.git" },
  });
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Version" }), { target: { value: "v1.2.0" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Next" }));
  dialog = await screen.findByRole("dialog", { name: "Refused" });
  expect(within(dialog).getByRole("alert").textContent).toBe("jira v1.2.0 needs LADO 0.22");
  expect(asked("POST", "/api/kits/plan")[0].body).toEqual({
    spec: "https://github.com/acme/kit-jira.git@v1.2.0",
    pre: false,
  });
  fireEvent.click(within(dialog).getByRole("button", { name: "Back" }));
  dialog = screen.getByRole("dialog", { name: "Add kit" });
  expect((within(dialog).getByRole("textbox", { name: "Version" }) as HTMLInputElement).value).toBe("v1.2.0");
  refuse = false;
  fireEvent.click(within(dialog).getByRole("button", { name: "Next" }));
  const plan = await screen.findByRole("dialog", { name: "Install wiki v1.0.0?" });
  fireEvent.click(within(plan).getByRole("checkbox"));
  fireEvent.click(within(plan).getByRole("button", { name: "Install" }));
  expect((await within(plan).findByRole("alert")).textContent).toBe("the kit changed since the plan: v1.0.0 moved");
  fireEvent.click(within(plan).getByRole("button", { name: "Look at the plan again" }));
  await waitFor(() => expect(asked("POST", "/api/kits/plan")).toHaveLength(3));
});

test("Install… on an Available row goes straight to the plan", async () => {
  serve({ "POST /api/kits/plan": () => PLAN });
  open("/kits/available");
  fireEvent.click(await screen.findByRole("button", { name: "Install wiki…" }));
  expect(await screen.findByRole("dialog", { name: "Install wiki v1.0.0?" })).toBeTruthy();
  expect(asked("POST", "/api/kits/plan")[0].body).toEqual({ spec: "wiki", marketplace: "team", pre: false });
});

test("Esc does not close a dialog while its request runs", async () => {
  let answer: (value: unknown) => void = () => {};
  serve({ "POST /api/kits/plan": () => new Promise((resolve) => (answer = resolve)) });
  open("/kits/available");
  fireEvent.click(await screen.findByRole("button", { name: "Install wiki…" }));
  const dialog = await screen.findByRole("dialog");
  fireEvent.keyDown(dialog, { key: "Escape" });
  expect(screen.getByRole("dialog")).toBeTruthy();
  await act(async () => answer(PLAN));
  fireEvent.keyDown(await screen.findByRole("dialog", { name: "Install wiki v1.0.0?" }), { key: "Escape" });
  expect(screen.queryByRole("dialog")).toBeNull();
});

// Update

const UPDATE: PlanInfo = {
  ...PLAN,
  name: "lado-dev",
  version: "0.10.0",
  spec: "https://github.com/ladohq/kit-lado-dev.git@v0.10.0",
  tag: "v0.10.0",
  commit: "c81d0e4",
  source: "official",
  marketplace: "official",
  installed: "v0.9.1",
  needs_confirmation: false,
  versions: ["v0.10.0", "v0.9.2", "v0.9.1"],
  mcp: [{ name: "playwright", command: "npx @playwright/mcp" }],
  new_mcp: ["playwright"],
  warnings: ["lado-dev v0.10.0 starts an MCP server v0.9.1 did not: playwright (npx @playwright/mcp)"],
  notes: ["running session lado gets v0.10.0 for new agents only"],
  users: { running: ["lado"], stopped: [], running_line: "x", stopped_line: null },
};

test("Update shows the core's plan, its warnings and who gets it; another version plans again", async () => {
  serve({
    "POST /api/kits/lado-dev/plan-update": (body) =>
      (body as { tag?: string }).tag === "v0.9.1"
        ? { ...UPDATE, tag: "v0.9.1", current: true, notes: ['Kit "lado-dev" is at v0.9.1 already.'], warnings: [] }
        : UPDATE,
    "POST /api/kits/lado-dev/update": () => ({ ...INSTALLED[1], tag: "v0.10.0" }),
  });
  open("/kits");
  fireEvent.click(await screen.findByRole("button", { name: "Update lado-dev…" }));
  const dialog = await screen.findByRole("dialog", { name: "Update lado-dev v0.9.1 → v0.10.0?" });
  expect(within(dialog).getByText(UPDATE.warnings[0])).toBeTruthy();
  expect(within(dialog).getByText(UPDATE.notes[0])).toBeTruthy();
  const version = within(dialog).getByRole("combobox", { name: "Version" });
  fireEvent.change(version, { target: { value: "v0.9.1" } });
  expect(await within(dialog).findByText('Kit "lado-dev" is at v0.9.1 already.')).toBeTruthy();
  expect((within(dialog).getByRole("button", { name: "Update" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(version, { target: { value: "v0.10.0" } });
  await within(dialog).findByText(UPDATE.notes[0]);
  fireEvent.click(within(dialog).getByRole("button", { name: "Update" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(asked("POST", "/api/kits/lado-dev/update")[0].body).toEqual({ tag: "v0.10.0", commit: "c81d0e4" });
});

// Remove

test("Remove names the sessions that use the kit, from the core", async () => {
  serve({
    "GET /api/kits/jira/remove-preview": () => ({
      running: ["clens"],
      stopped: ["crm"],
      running_line: "running session clens uses kit jira",
      stopped_line: "stopped session crm uses kit jira too: a resume needs it",
    }),
    "DELETE /api/kits/jira": () => ({ status: 204 }),
  });
  open("/kits");
  fireEvent.click(await screen.findByRole("button", { name: "Remove jira…" }));
  const dialog = await screen.findByRole("dialog", { name: "Remove jira?" });
  expect(await within(dialog).findByText("running session clens uses kit jira")).toBeTruthy();
  expect(within(dialog).getByText("stopped session crm uses kit jira too: a resume needs it")).toBeTruthy();
  fireEvent.click(within(dialog).getByRole("button", { name: "Remove" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(asked("DELETE", "/api/kits/jira")).toHaveLength(1);
});

test("Remove of a kit no session uses, and of one whose folder is gone", async () => {
  serve({
    "GET /api/kits/my-reviewers/remove-preview": () => ({ running: [], stopped: [], running_line: null, stopped_line: null }),
  });
  open("/kits");
  fireEvent.click(await screen.findByRole("button", { name: "Remove my-reviewers…" }));
  const dialog = await screen.findByRole("dialog", { name: "Remove my-reviewers?" });
  expect(await within(dialog).findByText("No session uses it.")).toBeTruthy();
  expect(within(dialog).getByText(/Its folder \/work\/my-reviewers is gone/)).toBeTruthy();
});

// Marketplaces

test("the Marketplaces block shows each one; enabled is a checkbox", async () => {
  serve({ "PATCH /api/marketplaces/team": () => ({ ...MARKETS[1], enabled: false }) });
  open("/kits");
  const block = await waitFor(() => marketplacesBlock());
  const team = await within(block).findByRole("listitem", { name: "team" });
  expect(within(team).getByText("index.json is invalid: index must be a whole number")).toBeTruthy();
  expect(within(team).getByText("1 kit")).toBeTruthy();
  const official = within(block).getByRole("listitem", { name: "official" });
  expect(within(official).queryByRole("button", { name: /Remove/ })).toBeNull();
  fireEvent.click(within(team).getByRole("checkbox", { name: "team enabled" }));
  await waitFor(() => expect(asked("PATCH", "/api/marketplaces/team")).toHaveLength(1));
  expect(asked("PATCH", "/api/marketplaces/team")[0].body).toEqual({ enabled: false });
});

test("Update all shows an error at its marketplace", async () => {
  serve({
    "POST /api/marketplaces/update": () => [
      { name: "official", marketplace: MARKETS[0], error: null },
      { name: "team", marketplace: null, error: "cannot clone https://github.com/acme/marketplace.git" },
    ],
  });
  open("/kits");
  const block = await waitFor(() => marketplacesBlock());
  fireEvent.click(within(block).getByRole("button", { name: "Update all" }));
  const team = within(block).getByRole("listitem", { name: "team" });
  expect((await within(team).findByRole("alert")).textContent).toBe("cannot clone https://github.com/acme/marketplace.git");
  expect(asked("POST", "/api/marketplaces/update")[0].body).toEqual({});
});

test("Add marketplace goes through the core; its refusal is shown", async () => {
  let refuse = true;
  serve({
    "POST /api/marketplaces": () =>
      refuse
        ? { status: 400, body: { detail: { message: 'marketplace "team" exists already', switch_off: [] } } }
        : MARKETS[1],
  });
  open("/kits");
  fireEvent.click(await screen.findByRole("button", { name: "Add marketplace…" }));
  const dialog = screen.getByRole("dialog", { name: "Add marketplace" });
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Name" }), { target: { value: "team" } });
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Git address" }), {
    target: { value: "https://github.com/acme/marketplace.git" },
  });
  fireEvent.click(within(dialog).getByRole("button", { name: "Add" }));
  expect((await within(dialog).findByRole("alert")).textContent).toBe('marketplace "team" exists already');
  refuse = false;
  fireEvent.click(within(dialog).getByRole("button", { name: "Add" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(asked("POST", "/api/marketplaces")[1].body).toEqual({
    name: "team",
    url: "https://github.com/acme/marketplace.git",
  });
});

test("Remove marketplace names the installed kits that stay, counted from the lists", async () => {
  const fromTeam = { ...INSTALLED[0], name: "jira-team", marketplace: "team" };
  serve({
    "GET /api/kits/installed": () => [...INSTALLED, fromTeam],
    "DELETE /api/marketplaces/team": () => ({ status: 204 }),
  });
  open("/kits");
  const block = await waitFor(() => marketplacesBlock());
  const team = await within(block).findByRole("listitem", { name: "team" });
  fireEvent.click(within(team).getByRole("button", { name: "Remove team…" }));
  const dialog = screen.getByRole("dialog", { name: "Remove marketplace team?" });
  expect(within(dialog).getByText(/Its 1 installed kit stays and keeps working: jira-team/)).toBeTruthy();
  fireEvent.click(within(dialog).getByRole("button", { name: "Remove" }));
  await waitFor(() => expect(asked("DELETE", "/api/marketplaces/team")).toHaveLength(1));
  // The feed says it is gone: its kit's source becomes "team (removed)".
  stream().send("change", { kind: "marketplaces", session: "", key: "team", op: "delete", item: null }, "13");
  expect(await within(kitRow("jira-team")).findByText("team (removed)")).toBeTruthy();
});
