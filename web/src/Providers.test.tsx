import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { ProviderLogins, ProvidersPage } from "./api";
import { claudeRow, cli, FakeSocket, FakeXterm, LOGIN, opencodeRow } from "./fakes";
import { POLL_MS, Providers, stateText } from "./Providers";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));
vi.mock("@xterm/addon-web-links", () => ({ WebLinksAddon: class {} }));

const claude = claudeRow;
const opencode = opencodeRow;

function codex(): ProviderLogins {
  return {
    ...opencode(),
    cli: cli("codex", "Codex CLI"),
    login: { ...LOGIN, state: "yes", method: "ChatGPT" },
    actions: [],
    note: "Codex agents do not get this login yet (GitHub #113)",
  };
}

let page: ProvidersPage;
let calls: { method: string; path: string; body: unknown }[];

beforeEach(() => {
  FakeSocket.all = [];
  FakeXterm.all = [];
  calls = [];
  page = { providers: [claude(), opencode(), codex()], checking: false, environment: "" };
  vi.stubGlobal("WebSocket", FakeSocket);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ method, path, body });
      if (path === "/api/providers/logins" || path === "/api/providers/check")
        return new Response(JSON.stringify(page), { status: 200 });
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

function mount() {
  return render(
    <MemoryRouter>
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

test("the subtitle, a ↻ by the heading, and nothing of lado doctor", async () => {
  await show();
  expect(screen.getByText("Sign-ins your agents use. Changes apply to agents started afterwards.")).toBeTruthy();
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
  expect(screen.queryByText(/No agent CLI is installed/)).toBeNull();
});

test("no CLI installed: one line over the list", async () => {
  const off = (row: ProviderLogins) => ({ ...row, cli: { ...row.cli, installed: false } });
  page.providers = page.providers.map(off);
  await show();
  expect(screen.getByText("No agent CLI is installed: install one of them to start a session.")).toBeTruthy();
});

test("an untested version says what LADO is tested with", async () => {
  page.providers[1] = {
    ...opencode(),
    cli: { ...cli("opencode", "OpenCode"), version: "7.9.1", tested_version: "7.8.x", warning: "untested" },
  };
  const row = await show("OpenCode");
  expect(within(row).getByText("LADO is tested with 7.8.x")).toBeTruthy();
  expect(within(await show()).queryByText(/LADO is tested with/)).toBeNull();
});

test("a sign-in that cannot be checked says so, and why", async () => {
  page.providers[0] = claude({ login: { ...LOGIN, state: "unknown", problem: "timed out after 10 s" } });
  const row = await show();
  expect(within(row).getByText("Couldn't check the sign-in")).toBeTruthy();
  expect(within(row).getByText("timed out after 10 s")).toBeTruthy();
});

test("the agents' environment only when it could not be read", async () => {
  await show();
  expect(screen.queryByText(/Agents' environment/)).toBeNull();
  cleanup();
  page = { ...page, environment: "the login shell did not answer in 10 s" };
  await show();
  expect(
    screen.getByText(/⚠ Agents' environment could not be read from your login shell: the login shell did not answer/),
  ).toBeTruthy();
});

test("without a login: Not logged in, the waiting agents and the one primary Log in…", async () => {
  const row = await show();
  expect(within(row).getByText("Not logged in").tagName).toBe("STRONG");
  expect(within(row).getByRole("link", { name: "supervisor of my-app" }).getAttribute("href")).toContain("my-app");
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

test("OpenCode has one button too; Codex its note and none", async () => {
  await show();
  const open = screen.getByRole("listitem", { name: "OpenCode" });
  expect(within(open).getByText("Logged in · 2 credentials, 1 variable")).toBeTruthy();
  expect(buttons(open)).toEqual(["Change login…"]);
  const codexRow = screen.getByRole("listitem", { name: "Codex CLI" });
  expect(within(codexRow).getByText("Logged in · ChatGPT")).toBeTruthy();
  expect(within(codexRow).getByText(/GitHub #113/)).toBeTruthy();
  expect(buttons(codexRow)).toEqual([]);
});

test("the state in words, unknown as couldn't check, never as not logged in", () => {
  expect(stateText(claude({ login: { ...LOGIN, state: "unknown", problem: "timed out" } }))).toBe(
    "Couldn't check the sign-in",
  );
  expect(stateText({ ...codex(), login: { ...LOGIN, state: "no" } })).toBe("No login");
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
