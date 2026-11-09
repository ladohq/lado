import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { ModelSettings, ProviderLogins, ProvidersPage } from "./api";
import { claudeRow, cli, codexRow, FakeSocket, FakeXterm, LOGIN, opencodeRow } from "./fakes";
import { POLL_MS, Providers, stateText } from "./Providers";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));
vi.mock("@xterm/addon-web-links", () => ({ WebLinksAddon: class {} }));

const claude = claudeRow;
const opencode = opencodeRow;

const codex = codexRow;

let page: ProvidersPage;
let entries: ModelSettings;
let calls: { method: string; path: string; body: unknown }[];

beforeEach(() => {
  FakeSocket.all = [];
  FakeXterm.all = [];
  calls = [];
  page = { providers: [claude(), opencode(), codex()], checking: false, environment: "" };
  entries = { models: [], servers: [], defaults: [] };
  vi.stubGlobal("WebSocket", FakeSocket);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ method, path, body });
      if (path === "/api/providers/logins" || path === "/api/providers/check")
        return new Response(JSON.stringify(page), { status: 200 });
      if (path === "/api/model-settings" || path.startsWith("/api/model-defaults/"))
        return new Response(JSON.stringify(entries), { status: 200 });
      if (path.includes("/model-choices")) return new Response(JSON.stringify(NO_LIST), { status: 200 });
      const row = path.startsWith("/api/providers/claude") ? claude() : opencode();
      return new Response(JSON.stringify(row), { status: 200 });
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

// A CLI's list of models, as the picker reads it for a built-in default: none here.
const NO_LIST = {
  aliases: [],
  models: [],
  external: [],
  why: "",
  other_name: true,
  whole_process: false,
  read_again: false,
  check: { kind: "default", text: "", field: "", name: "" },
};

function mount(path = "/settings/agent-clis") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Providers />
    </MemoryRouter>,
  );
}

async function show(title = "Claude Code") {
  mount();
  return screen.findByRole("listitem", { name: title });
}

const buttons = (row: HTMLElement) => within(row).queryAllByRole("button").map((b) => b.textContent);
const checks = () => calls.filter((c) => c.method === "POST" && c.path === "/api/providers/check");
const reads = () => calls.filter((c) => c.method === "GET" && c.path === "/api/providers/logins");
const refresh = () => screen.getByRole("button", { name: "Check the CLIs again" });

async function tick(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

test("the page Agent CLIs: its lede, a ↻ by the heading, and nothing of lado doctor", async () => {
  await show();
  expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("Agent CLIs");
  expect(screen.getByText("Changes apply to agents started afterwards.")).toBeTruthy();
  expect(refresh().textContent).toBe("↻");
  const text = document.body.textContent ?? "";
  for (const gone of ["lado doctor", "Check again", "[ok]", "[warn]", "[info]"]) expect(text).not.toContain(gone);
});

test("it asks for a check when it opens, and ↻ asks again", async () => {
  await show();
  expect(checks()).toHaveLength(1);
  fireEvent.click(refresh());
  await waitFor(() => expect(checks()).toHaveLength(2));
});

test("the rows of the last check show at once while ↻ turns, then change in place", async () => {
  vi.useFakeTimers();
  page = { ...page, checking: true };
  mount();
  await tick(0);
  expect(screen.getByRole("listitem", { name: "Claude Code" })).toBeTruthy();
  expect(refresh().className).toContain("spinning");
  expect(refresh().title).toBe("Checking the CLIs…");
  fireEvent.click(refresh()); // a press while it turns starts nothing
  await tick(0);
  expect(checks()).toHaveLength(1);
  // Polled every second while the check runs.
  await tick(POLL_MS);
  expect(reads()).toHaveLength(1);
  page = { ...page, providers: [claude({ login: { ...LOGIN, state: "yes", method: "Bedrock" } })], checking: false };
  await tick(POLL_MS);
  expect(reads()).toHaveLength(2);
  expect(screen.getByText("Logged in · Bedrock")).toBeTruthy();
  expect(refresh().className).not.toContain("spinning");
  await tick(POLL_MS * 3);
  expect(reads()).toHaveLength(2); // the check ended: no more polling
});

test("a failed read ends the turning ↻, which then asks again", async () => {
  vi.useFakeTimers();
  page = { ...page, checking: true };
  mount();
  await tick(0);
  expect(refresh().className).toContain("spinning");
  vi.mocked(fetch).mockImplementationOnce(async () => new Response("down", { status: 502 }));
  await tick(POLL_MS);
  expect(screen.getByRole("alert")).toBeTruthy();
  expect(refresh().className).not.toContain("spinning");
  page = { ...page, checking: false };
  fireEvent.click(refresh());
  await tick(0);
  expect(checks()).toHaveLength(2);
  expect(screen.queryByRole("alert")).toBeNull();
});

test("a first answer that fails leaves ↻ to ask again", async () => {
  vi.mocked(fetch).mockImplementationOnce(async () => new Response("down", { status: 502 }));
  mount();
  await screen.findByRole("alert");
  expect(screen.getByText("Not checked yet. Press ↻ to try again.")).toBeTruthy();
  expect(refresh().className).not.toContain("spinning");
  fireEvent.click(refresh());
  await screen.findByRole("listitem", { name: "Claude Code" });
  expect(checks()).toHaveLength(1); // the first one failed before it was counted
});

test("stops polling when it leaves", async () => {
  vi.useFakeTimers();
  page = { ...page, checking: true };
  const shown = mount();
  await tick(0);
  shown.unmount();
  await tick(POLL_MS * 3);
  expect(reads()).toHaveLength(0);
});

test("a row not read yet shows its name and checking…", async () => {
  page.providers[2] = { ...codex(), ready: false, cli: { ...cli("codex", "Codex CLI"), installed: false, version: "" } };
  const row = await show("Codex CLI");
  expect(within(row).getByText("checking…")).toBeTruthy();
  expect(within(row).queryByText("not installed")).toBeNull();
  expect(buttons(row)).toEqual([]);
});

test("a CLI not installed: greyed, with how to install it", async () => {
  page.providers[2] = { ...codex(), cli: { ...cli("codex", "Codex CLI"), installed: false, version: "" } };
  const row = await show("Codex CLI");
  expect(row.className).toContain("pv-off");
  expect(within(row).getByText("not installed")).toBeTruthy();
  expect(within(row).getByText("install codex")).toBeTruthy();
  expect(within(row).queryByText(/Logged in/)).toBeNull();
  expect(screen.queryByText(/No agent CLI installed/)).toBeNull();
});

test("no CLI installed: one line over the list", async () => {
  const off = (row: ProviderLogins) => ({ ...row, cli: { ...row.cli, installed: false } });
  page.providers = page.providers.map(off);
  await show();
  expect(screen.getByText("No agent CLI installed. Install one to start a session.")).toBeTruthy();
});

test("an untested version says what LADO tested", async () => {
  page.providers[1] = {
    ...opencode(),
    cli: { ...cli("opencode", "OpenCode"), version: "7.9.1", tested_version: "7.8.x", warning: "untested" },
  };
  const row = await show("OpenCode");
  expect(within(row).getByText("LADO tested 7.8.x")).toBeTruthy();
  expect(within(await show()).queryByText(/LADO tested/)).toBeNull();
});

test("a sign-in that cannot be checked says so, and why", async () => {
  page.providers[0] = claude({ login: { ...LOGIN, state: "unknown", problem: "timed out after 10 s" } });
  const row = await show();
  expect(within(row).getByText("Couldn't check the sign-in")).toBeTruthy();
  expect(within(row).getByText("timed out after 10 s")).toBeTruthy();
});

test("the agents' environment only when it could not be read", async () => {
  await show();
  expect(screen.queryByText(/login shell/)).toBeNull();
  cleanup();
  page = { ...page, environment: "zsh exited with 1" };
  await show();
  expect(screen.getByText(/^Couldn't read your login shell/).textContent).toBe(
    "Couldn't read your login shell: zsh exited with 1. Details: lado doctor",
  );
});

test("without a login: Not logged in, the waiting agents and the one primary Log in…", async () => {
  const row = await show();
  expect(within(row).getByText("Not logged in").tagName).toBe("STRONG");
  const agent = within(row).getByRole("link", { name: "supervisor of my-app" });
  expect(agent.getAttribute("href")).toContain("my-app");
  expect(agent.closest("p")?.textContent).toBe("supervisor of my-app waits; it starts once you log in.");
  expect(buttons(row)).toEqual(["Log in…"]);
  expect(within(row).getByRole("button", { name: "Log in…" }).className).toBe("primary");
  expect(within(row).queryByRole("textbox")).toBeNull(); // no field on the row
});

test("with a login: one state line, how and from which layer, and Change login…", async () => {
  page.providers[0] = claude({
    login: { ...LOGIN, state: "yes", method: "Pay per use (API key)", where: "LADO's secret", choice: "usage" },
    waiting: [],
    projects: ["shop"],
  });
  const row = await show();
  expect(within(row).getByText("Logged in · Pay per use (API key) · LADO's secret")).toBeTruthy();
  expect(within(row).getByText("Projects with their own login: shop")).toBeTruthy();
  expect(buttons(row)).toEqual(["Change login…"]);
  expect(within(row).getByRole("button", { name: "Change login…" }).className).toBe("quiet");
});

test("OpenCode and Codex have one button too, and no note that their agents lack the login", async () => {
  await show();
  const open = screen.getByRole("listitem", { name: "OpenCode" });
  expect(within(open).getByText("Logged in · 2 credentials, 1 variable")).toBeTruthy();
  expect(buttons(open)).toEqual(["Change login…"]);
  const row = screen.getByRole("listitem", { name: "Codex CLI" });
  expect(within(row).getByText("Logged in · ChatGPT plan · Codex's login file")).toBeTruthy();
  expect(buttons(row)).toEqual(["Change login…"]);
  expect(row.querySelector(".pv-warn")).toBeNull();
});

test("Codex without a login its model needs: the primary Log in…, and the keyring's note", async () => {
  const note = "Your Codex keeps its login in the system keyring, which Codex agents cannot read.";
  page.providers[2] = codex({ login: { ...LOGIN, state: "no" }, note, logout_file: false });
  const row = await show("Codex CLI");
  expect(within(row).getByText("Not logged in").tagName).toBe("STRONG");
  expect(within(row).getByRole("button", { name: "Log in…" }).className).toBe("primary");
  expect(within(row).getByText(note).className).toBe("pv-warn");
  // A local model needs none: no login, and Log in… is not pressed on the human.
  page.providers[2] = codex({ login: { ...LOGIN, state: "no" }, needs_login: false, logout_file: false });
  cleanup();
  const local = await show("Codex CLI");
  expect(within(local).getByText("No login")).toBeTruthy();
  expect(within(local).getByRole("button", { name: "Log in…" }).className).toBe("quiet");
});

test("the state in words, unknown as couldn't check, never as not logged in", () => {
  expect(stateText(claude({ login: { ...LOGIN, state: "unknown", problem: "timed out" } }))).toBe(
    "Couldn't check the sign-in",
  );
  expect(stateText({ ...codex(), login: { ...LOGIN, state: "no" }, needs_login: false })).toBe("No login");
  const file = { ...LOGIN, state: "yes" as const, method: "Subscription (Max)", where: "Claude Code's login file" };
  expect(stateText(claude({ login: file }))).toBe("Logged in · Subscription (Max) · Claude Code's login file");
  expect(stateText(claude({ login: { ...LOGIN, state: "yes", method: "Bedrock" } }))).toBe("Logged in · Bedrock");
});

test("the button opens the sheet; its end asks for a check", async () => {
  const row = await show();
  fireEvent.click(within(row).getByRole("button", { name: "Log in…" }));
  const sheet = await screen.findByRole("dialog", { name: "How do you pay for Claude?" });
  fireEvent.click(within(sheet).getByRole("button", { name: "Close" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  await waitFor(() => expect(checks()).toHaveLength(2));
});

// A CLI's default model in its row (its picker and warnings: ModelCards.test.tsx).

test("each installed CLI's row holds Default model under its login, whatever its login", async () => {
  page.providers.push({ ...codex(), cli: { ...cli("kilo", "Kilo CLI"), installed: false, version: "" } });
  const row = await show();
  const picker = await within(row).findByRole("combobox", { name: "Default model of Claude Code" });
  expect(picker.textContent).toContain("Claude Code's settings");
  expect(picker.closest(".cli-model")?.querySelector(".cli-ml")?.textContent).toBe("Default model");
  for (const title of ["OpenCode", "Codex CLI"])
    expect(within(screen.getByRole("listitem", { name: title })).getByRole("combobox")).toBeTruthy();
  expect(within(screen.getByRole("listitem", { name: "Kilo CLI" })).queryByRole("combobox")).toBeNull();
});

test("with no model server a line under the rows leads to Model servers; with one, none", async () => {
  await show();
  const line = await screen.findByText(/^Models of your own come from a model server/);
  expect(line.textContent).toBe("Models of your own come from a model server: Model servers");
  expect(within(line).getByRole("link", { name: "Model servers" }).getAttribute("href")).toBe(
    "/settings/model-servers",
  );
  cleanup();
  entries = { ...entries, servers: [{ name: "lmstudio", address: "http://x:1234", kind: "LM Studio", has_key: false }] };
  await show();
  await screen.findByRole("combobox", { name: "Default model of Claude Code" });
  expect(screen.queryByText(/^Models of your own/)).toBeNull();
});

test("a CLI not installed with a default says it cannot run, and its settings clear it", async () => {
  page.providers.push({ ...codex(), cli: { ...cli("kilo", "Kilo CLI"), installed: false, version: "" } });
  entries = {
    ...entries,
    defaults: [
      { cli: "kilo", external: null, builtin: "a/one", name: "a/one", model: "a/one", server: null, whole_process: false },
    ],
  };
  const row = await show("Kilo CLI");
  expect(await within(row).findByText("Default model: a/one — cannot run: not installed")).toBeTruthy();
  entries = { ...entries, defaults: [] };
  fireEvent.click(within(row).getByRole("button", { name: "Use Kilo CLI's settings" }));
  await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.path === "/api/model-defaults/kilo")).toBe(true));
  await waitFor(() => expect(within(row).queryByText(/cannot run/)).toBeNull());
  expect(document.activeElement).toBe(within(row).getByText("Kilo CLI")); // the line went: its name
});

// `✓ Saved` of a default: one for the page, until the human's next change on it.

const savedIn = (title: string) =>
  screen.getByRole("listitem", { name: title }).querySelector(".cli-saved")?.textContent;

async function saveSettings(title: string) {
  fireEvent.click(await screen.findByRole("combobox", { name: `Default model of ${title}` }));
  fireEvent.click(await screen.findByRole("option", { name: new RegExp(`${title}'s settings`) }));
  await waitFor(() => expect(savedIn(title)).toBe("✓ Saved"));
}

test("✓ Saved moves to the row of the next save, and no minute takes it away", async () => {
  await show();
  await saveSettings("OpenCode");
  expect(savedIn("Claude Code")).toBe("");
  await saveSettings("Claude Code");
  expect(savedIn("OpenCode")).toBe("");
  vi.useFakeTimers();
  await tick(60_000);
  expect(savedIn("Claude Code")).toBe("✓ Saved");
});

test("opening a login sheet and ↻ take ✓ Saved away", async () => {
  const row = await show();
  await saveSettings("Claude Code");
  fireEvent.click(within(row).getByRole("button", { name: "Log in…" }));
  await screen.findByRole("dialog");
  expect(savedIn("Claude Code")).toBe("");
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Close" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  await waitFor(() => expect(refresh().className).not.toContain("spinning"));
  await saveSettings("Claude Code");
  fireEvent.click(refresh());
  expect(savedIn("Claude Code")).toBe("");
});

// Arrival at a CLI's row (Needs you's and New session's Log in…).

test("#<cli> scrolls its row to the middle once it is read, and focuses its login button", async () => {
  const scrolled = vi.fn();
  Element.prototype.scrollIntoView = scrolled;
  vi.useFakeTimers({ shouldAdvanceTime: true });
  page = { ...page, checking: true, providers: [{ ...claude(), ready: false }, opencode(), codex()] };
  mount("/settings/agent-clis#claude");
  await tick(0);
  expect(scrolled).not.toHaveBeenCalled(); // the row is not read yet
  page = { ...page, providers: [claude(), opencode(), codex()] };
  await tick(POLL_MS);
  const row = screen.getByRole("listitem", { name: "Claude Code" });
  expect(row.id).toBe("claude");
  expect(scrolled).toHaveBeenCalledTimes(1);
  expect(scrolled.mock.contexts[0]).toBe(row);
  expect(scrolled.mock.calls[0][0]).toMatchObject({ block: "center" });
  expect(document.activeElement).toBe(within(row).getByRole("button", { name: "Log in…" }));
  // The human moves on; the rows read again do not take the focus back.
  refresh().focus();
  page = { ...page, checking: false };
  await tick(POLL_MS);
  expect(scrolled).toHaveBeenCalledTimes(1);
  expect(document.activeElement).toBe(refresh());
});

test("#<cli> of a CLI with no login button focuses its name; an unknown one moves nothing", async () => {
  const scrolled = vi.fn();
  Element.prototype.scrollIntoView = scrolled;
  page.providers[1] = { ...opencode(), choices: [], actions: [] };
  mount("/settings/agent-clis#opencode");
  const row = await screen.findByRole("listitem", { name: "OpenCode" });
  await waitFor(() => expect(scrolled).toHaveBeenCalledTimes(1));
  expect(document.activeElement).toBe(within(row).getByText("OpenCode"));
  cleanup();
  scrolled.mockClear();
  mount("/settings/agent-clis#gemini");
  await screen.findByRole("listitem", { name: "Claude Code" });
  expect(scrolled).not.toHaveBeenCalled();
  expect(document.activeElement).toBe(document.body);
});

test("a hash that is no name (a broken %-code) is an unknown one: the page stays at its top", async () => {
  const scrolled = vi.fn();
  Element.prototype.scrollIntoView = scrolled;
  mount("/settings/agent-clis#%E0%A4%A");
  expect(await screen.findByRole("listitem", { name: "Claude Code" })).toBeTruthy();
  expect(scrolled).not.toHaveBeenCalled();
  expect(document.activeElement).toBe(document.body);
});
