import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { ProviderLogins, ProvidersPage } from "./api";
import { FakeSocket, FakeXterm, lastSocket } from "./fakes";
import { KEYS, LoginWindow } from "./LoginWindow";
import { Providers, stateText } from "./Providers";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));
const links: { opened: string[]; loaded: number } = { opened: [], loaded: 0 };
vi.mock("@xterm/addon-web-links", () => ({
  WebLinksAddon: class {
    constructor(readonly open: (event: unknown, uri: string) => void) {
      links.loaded += 1;
    }
    activate() {}
  },
}));

function cli(name: string, title: string) {
  return {
    name,
    title,
    permission_modes: [],
    install_hint: `install ${name}`,
    installed: true,
    version: "1.0.0",
    detail: `${name} 1.0.0`,
    tested_version: "",
    warning: "",
    login_missing: false,
  };
}

const LOGIN = { method: "", file: "", variable: "", layer: "", source: "", items: [], problem: "" };

function claude(more: Partial<ProviderLogins> = {}): ProviderLogins {
  return {
    cli: cli("claude", "Claude Code"),
    login: { ...LOGIN, state: "no" },
    needs_login: true,
    actions: [
      { id: "login", label: "Log in with your Claude account…" },
      { id: "login-console", label: "Log in with Anthropic Console…" },
    ],
    can_logout: true,
    variables: [
      { name: "CLAUDE_CODE_OAUTH_TOKEN", secret: false, layer: "" },
      { name: "ANTHROPIC_API_KEY", secret: false, layer: "" },
    ],
    note: "",
    waiting: [{ session: "my-app", agent: "supervisor" }],
    running: [
      { session: "my-app", agent: "supervisor" },
      { session: "my-app", agent: "developer" },
    ],
    projects: [],
    window: false,
    ...more,
  };
}

function codex(): ProviderLogins {
  return {
    ...claude(),
    cli: cli("codex", "Codex CLI"),
    login: { ...LOGIN, state: "yes", method: "ChatGPT", file: "/h/.codex/auth.json", source: "/h/.codex/auth.json" },
    needs_login: false,
    actions: [],
    can_logout: false,
    variables: [],
    note: "Codex agents do not get this login yet (GitHub #113)",
    waiting: [],
    running: [],
  };
}

let page: ProvidersPage;
let calls: { method: string; path: string; body: unknown }[];

beforeEach(() => {
  FakeSocket.all = [];
  FakeXterm.all = [];
  links.opened = [];
  links.loaded = 0;
  calls = [];
  page = {
    providers: [claude(), codex()],
    checks: [
      { name: "Claude Code", level: "ok", detail: "2.1.295", hint: "" },
      { name: "Claude Code login", level: "warn", detail: "not logged in: its agents wait", hint: "" },
    ],
  };
  vi.stubGlobal("WebSocket", FakeSocket);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ method, path, body });
      if (path === "/api/providers/logins") return new Response(JSON.stringify(page), { status: 200 });
      if (path === "/api/providers/claude/variables/GH_TOKEN")
        return new Response(JSON.stringify({ detail: "refused" }), { status: 400 });
      const row = path.startsWith("/api/providers/claude") ? claude() : codex();
      return new Response(JSON.stringify(row), { status: 200 });
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function show() {
  render(
    <MemoryRouter>
      <Providers />
    </MemoryRouter>,
  );
  return screen.findByRole("listitem", { name: "Claude Code" });
}

test("each CLI's login as its status says, with the agents that wait and the note", async () => {
  const row = await show();
  expect(within(row).getByText("Not logged in")).toBeTruthy();
  expect(within(row).getByRole("link", { name: "supervisor of my-app" }).getAttribute("href")).toContain("my-app");
  expect(within(row).getByRole("button", { name: "Log in with your Claude account…" }).className).toBe("primary");
  expect(within(row).getByLabelText("CLAUDE_CODE_OAUTH_TOKEN")).toBeTruthy();
  const codexRow = screen.getByRole("listitem", { name: "Codex CLI" });
  expect(within(codexRow).getByText("Logged in · ChatGPT")).toBeTruthy();
  expect(within(codexRow).getByText(/GitHub #113/)).toBeTruthy();
  expect(within(codexRow).queryAllByRole("button")).toEqual([]); // no login for Codex
  const doctor = screen.getByRole("list", { name: "lado doctor about the providers" });
  expect(within(doctor).getByText(/Claude Code login: not logged in/)).toBeTruthy();
});

test("a logout in the window is offered only with a login to log out of", async () => {
  const kilo = (state: "yes" | "no"): ProviderLogins => ({
    ...codex(),
    cli: cli("kilo", "Kilo CLI"),
    login: { ...LOGIN, state, method: state === "yes" ? "1 credential" : "" },
    note: "",
    actions: [
      { id: "login", label: "Add a login…" },
      { id: "logout", label: "Log out of one…" },
    ],
  });
  page.providers = [kilo("no")];
  render(
    <MemoryRouter>
      <Providers />
    </MemoryRouter>,
  );
  const row = await screen.findByRole("listitem", { name: "Kilo CLI" });
  expect(within(row).getAllByRole("button").map((b) => b.textContent)).toEqual(["Add a login…"]);
  cleanup();
  page.providers = [kilo("yes")];
  render(
    <MemoryRouter>
      <Providers />
    </MemoryRouter>,
  );
  const logged = await screen.findByRole("listitem", { name: "Kilo CLI" });
  expect(within(logged).getAllByRole("button").map((b) => b.textContent)).toEqual(["Add a login…", "Log out of one…"]);
});

test("the state in words, unknown with why, never as not logged in", () => {
  expect(stateText(claude({ login: { ...LOGIN, state: "unknown", problem: "timed out" } }))).toBe("Unknown: timed out");
  expect(stateText({ ...codex(), login: { ...LOGIN, state: "no" } })).toBe("No login");
  expect(stateText(claude({ login: { ...LOGIN, state: "yes", method: "token" } }))).toBe("Logged in · token");
});

test("Check again reads the CLIs anew", async () => {
  await show();
  fireEvent.click(screen.getByRole("button", { name: "Check again" }));
  await waitFor(() => expect(calls.filter((c) => c.path === "/api/providers/logins")).toHaveLength(2));
});

test("a token is sent in the body once, the field emptied, never shown", async () => {
  const row = await show();
  const field = within(row).getByLabelText("CLAUDE_CODE_OAUTH_TOKEN") as HTMLInputElement;
  fireEvent.change(field, { target: { value: "canary-tok" } });
  const [save] = within(row).getAllByRole("button", { name: "Save" });
  fireEvent.click(save);
  await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
  const put = calls.find((c) => c.method === "PUT")!;
  expect(put.path).toBe("/api/providers/claude/variables/CLAUDE_CODE_OAUTH_TOKEN");
  expect(put.body).toEqual({ value: "canary-tok" });
  await waitFor(() => expect(field.value).toBe(""));
  expect(document.body.textContent).not.toContain("canary-tok");
});

const SUBSCRIPTION = { ...LOGIN, state: "yes" as const, method: "Claude subscription (Max)", file: "/h/.credentials.json" };

test("Log out asks first, naming the running agents that share the login file", async () => {
  page.providers[0] = claude({ login: SUBSCRIPTION, waiting: [] });
  const row = await show();
  fireEvent.click(within(row).getByRole("button", { name: "Log out…" }));
  const ask = within(row).getByRole("group", { name: "Log out of Claude Code?" });
  expect(ask.textContent).toContain(
    "supervisor of my-app, developer of my-app share this login and may stop being able to answer",
  );
  expect(calls.some((c) => c.path.endsWith("/logout"))).toBe(false);
  fireEvent.click(within(ask).getByRole("button", { name: "Log out" }));
  await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/api/providers/claude/logout")).toBe(true));
});

test("no Log out for a login a variable gives: the CLI's logout would not remove it", async () => {
  page.providers[0] = claude({
    login: { ...LOGIN, state: "yes", method: "token", variable: "CLAUDE_CODE_OAUTH_TOKEN", layer: "LADO's secret" },
    waiting: [],
  });
  const row = await show();
  expect(within(row).queryByRole("button", { name: "Log out…" })).toBeNull();
});

test("Remove of a saved token asks first", async () => {
  page.providers[0] = claude({
    variables: [{ name: "CLAUDE_CODE_OAUTH_TOKEN", secret: true, layer: "LADO's secret" }],
  });
  const row = await show();
  expect(within(row).getByText("set · LADO's secret")).toBeTruthy();
  fireEvent.click(within(row).getByRole("button", { name: "Remove…" }));
  const ask = within(row).getByRole("group", { name: "Remove CLAUDE_CODE_OAUTH_TOKEN from LADO's secrets?" });
  // Running agents keep the environment they started with.
  expect(ask.textContent).toContain(
    "supervisor of my-app, developer of my-app keep it until they start again; new agents go without it",
  );
  expect(ask.textContent).not.toContain("stop being able to answer");
  fireEvent.click(within(ask).getByRole("button", { name: "Remove" }));
  await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.path.endsWith("/CLAUDE_CODE_OAUTH_TOKEN"))).toBe(true));
});

test("a login action opens the window; its end reads the CLIs again", async () => {
  const row = await show();
  fireEvent.click(within(row).getByRole("button", { name: "Log in with your Claude account…" }));
  const sheet = await screen.findByRole("dialog", { name: "Log in: Claude Code" });
  expect(calls.find((c) => c.method === "POST" && c.path === "/api/providers/claude/login")?.body).toEqual({ action: "login" });
  const socket = lastSocket();
  expect(socket.url).toBe("ws://localhost:3000/api/providers/claude/login/terminal");
  act(() => socket.open());
  act(() => socket.end(4404, "the login window of claude ended"));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(sheet.isConnected).toBe(false);
  await waitFor(() => expect(calls.filter((c) => c.path === "/api/providers/logins")).toHaveLength(2));
});

function window_() {
  const ended = vi.fn();
  render(<LoginWindow provider="claude" title="Claude Code" onEnded={ended} />);
  const socket = lastSocket();
  act(() => socket.open());
  return { socket, ended };
}

test("Send sends the text and Enter as one input; the keys send theirs", () => {
  const { socket } = window_();
  const field = screen.getByLabelText("Text to send") as HTMLInputElement;
  fireEvent.change(field, { target: { value: "code-42" } });
  fireEvent.click(screen.getByRole("button", { name: "Send ⏎" }));
  const inputs = () => socket.frames.filter((f) => (f as { type: string }).type === "input");
  expect(inputs()).toEqual([{ type: "input", data: "code-42\r" }]);
  expect(field.value).toBe("");
  for (const key of KEYS) fireEvent.click(screen.getByRole("button", { name: key.name }));
  expect(inputs().slice(1)).toEqual([
    { type: "input", data: "\x1b[A" },
    { type: "input", data: "\x1b[B" },
    { type: "input", data: "\r" },
    { type: "input", data: "\x1b" },
  ]);
});

test("links in the window are clickable: the web links addon is loaded", () => {
  window_();
  expect(links.loaded).toBe(1);
});

test("Close ends the command first", async () => {
  const { ended } = window_();
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  await waitFor(() => expect(ended).toHaveBeenCalled());
  expect(calls).toContainEqual({ method: "DELETE", path: "/api/providers/claude/login", body: undefined });
});
