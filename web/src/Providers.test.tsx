import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { ProviderLogins, ProvidersPage } from "./api";
import { claudeRow, cli, FakeSocket, FakeXterm, LOGIN, opencodeRow } from "./fakes";
import { Providers, stateText } from "./Providers";

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
  page = {
    providers: [claude(), opencode(), codex()],
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
      const row = path.startsWith("/api/providers/claude") ? claude() : opencode();
      return new Response(JSON.stringify(row), { status: 200 });
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function show(title = "Claude Code") {
  render(
    <MemoryRouter>
      <Providers />
    </MemoryRouter>,
  );
  return screen.findByRole("listitem", { name: title });
}

const buttons = (row: HTMLElement) => within(row).queryAllByRole("button").map((b) => b.textContent);

test("without a login: Not logged in, the waiting agents and the one primary Log in…", async () => {
  const row = await show();
  expect(within(row).getByText("Not logged in").tagName).toBe("STRONG");
  expect(within(row).getByRole("link", { name: "supervisor of my-app" }).getAttribute("href")).toContain("my-app");
  expect(buttons(row)).toEqual(["Log in…"]);
  expect(within(row).getByRole("button", { name: "Log in…" }).className).toBe("primary");
  expect(within(row).queryByRole("textbox")).toBeNull(); // no field on the row
  const doctor = screen.getByRole("list", { name: "lado doctor about the providers" });
  expect(within(doctor).getByText(/Claude Code login: not logged in/)).toBeTruthy();
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

test("the state in words, unknown with why, never as not logged in", () => {
  expect(stateText(claude({ login: { ...LOGIN, state: "unknown", problem: "timed out" } }))).toBe("Unknown: timed out");
  expect(stateText({ ...codex(), login: { ...LOGIN, state: "no" } })).toBe("No login");
  const file = { ...LOGIN, state: "yes" as const, method: "Subscription (Max)", where: "Claude Code's login file" };
  expect(stateText(claude({ login: file }))).toBe("Logged in · Subscription (Max) · Claude Code's login file");
  expect(stateText(claude({ login: { ...LOGIN, state: "yes", method: "Bedrock" } }))).toBe("Logged in · Bedrock");
});

test("Check again reads the CLIs anew", async () => {
  await show();
  fireEvent.click(screen.getByRole("button", { name: "Check again" }));
  await waitFor(() => expect(calls.filter((c) => c.path === "/api/providers/logins")).toHaveLength(2));
});

test("the button opens the sheet; its end reads the CLIs again", async () => {
  const row = await show();
  fireEvent.click(within(row).getByRole("button", { name: "Log in…" }));
  const sheet = await screen.findByRole("dialog", { name: "How do you pay for Claude?" });
  fireEvent.click(within(sheet).getByRole("button", { name: "Close" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  await waitFor(() => expect(calls.filter((c) => c.path === "/api/providers/logins")).toHaveLength(2));
});
