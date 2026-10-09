import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { Health, SystemInfo, UpdateInfo, UpdatePlan, UpdateResultInfo } from "./api";
import { App } from "./App";
import { FakeEventSource, stubDialogs } from "./fakes";
import { browserLine, checkLine, GIVE_UP_MS, POLL_MS, shortHome, when } from "./SystemPanel";
import { BUNDLE_VERSION } from "./version";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const STARTED = "2026-10-09T10:00:00.000+00:00";
const NOW = new Date();

const PROVIDER = {
  permission_modes: [],
  install_hint: "",
  detail: "",
};

const SYSTEM: SystemInfo = {
  version: BUNDLE_VERSION,
  python: "3.13.1",
  os: "macOS 15.6",
  machine: "arm64",
  installer: "uv tool",
  started_at: new Date(Date.now() - (2 * 60 + 14) * 60_000).toISOString(),
  open_to_network: false,
  home: "/Users/someone/.lado",
  home_set: false,
  schema: 23,
  tmux: { version: "3.5a", socket: "lado" },
  providers: [
    { ...PROVIDER, name: "claude", title: "Claude Code", installed: true, version: "2.1.295", tested_version: "2.1.295", warning: "" },
    { ...PROVIDER, name: "kilo", title: "Kilo", installed: true, version: "7.9.0", tested_version: "7.8.3", warning: "untested" },
    { ...PROVIDER, name: "opencode", title: "OpenCode", installed: false, version: "", tested_version: "1.18", warning: "" },
  ],
  kits: [{ name: "default", version: "1.0.0", origin: "built-in" }],
  sessions: { running: 1, stopped: 0, gone: 0 },
  last: null,
  report: "### LADO system info\n- LADO x\n",
};

const PLAN: UpdatePlan = {
  from: BUNDLE_VERSION,
  to: "99.0.0",
  released: "2026-10-12",
  installer: "uv tool",
  command: "uv tool install lado==99.0.0",
  lost: [],
  downgrade: false,
  sessions: [
    {
      name: "lado",
      repo: "/src/lado",
      agents: [
        { name: "supervisor", status: "busy" },
        { name: "developer", status: "idle" },
      ],
      open_runs: 1,
    },
  ],
  gone: [],
  server: "http://127.0.0.1:8000",
  socket: "lado",
  by_hand: [],
};

function info(more: Partial<UpdateInfo> = {}): UpdateInfo {
  return {
    current: BUNDLE_VERSION,
    latest: BUNDLE_VERSION,
    available: null,
    released: null,
    checked_at: NOW.toISOString(),
    error: null,
    running: false,
    can_update: true,
    why_not: null,
    by_hand: [],
    last: null,
    ...more,
  };
}

function result(more: Partial<UpdateResultInfo> = {}): UpdateResultInfo {
  return {
    id: "u-1",
    outcome: "ok",
    from: BUNDLE_VERSION,
    to: "99.0.0",
    started_at: new Date().toISOString(),
    ended_at: new Date().toISOString(),
    sessions_failed: [],
    reason: null,
    database: "kept",
    log: "/home/x/.lado/update.log",
    tail: ["LADO 99.0.0 is ready."],
    problem: null,
    ...more,
  };
}

// What the server answers; a test changes these as the server would change.
let update: UpdateInfo;
let checked: UpdateInfo | { status: number; detail: string };
let health: Health;
let down: boolean; // the server is away (restarting)

function serve() {
  const fetch = vi.fn(async (path: string, init?: RequestInit) => {
    if (down && path !== "/api/events") throw new TypeError("Failed to fetch");
    const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
    if (path === "/api/health") return json(health);
    if (path === "/api/update" && init?.method === "POST") {
      return json({ id: "u-1", requested_at: STARTED, log: "/home/x/.lado/update.log" }, 202);
    }
    if (path === "/api/update") return json(update);
    if (path === "/api/update/check") {
      return "status" in checked ? json({ detail: checked.detail }, checked.status) : json(checked);
    }
    if (path === "/api/update/plan") return json(PLAN);
    if (path === "/api/system") return json(SYSTEM);
    if (path.startsWith("/api/events")) return json("");
    if (path === "/api/sessions") return json([]);
    return json([]);
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

const open = () =>
  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );

const live = () => screen.findByRole("button", { name: /^System/ });

async function panel() {
  fireEvent.click(await live());
  return screen.findByRole("dialog", { name: "System" });
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  update = info();
  checked = info();
  health = { ok: true, version: BUNDLE_VERSION, started_at: STARTED };
  down = false;
  serve();
  FakeEventSource.all = [];
  FakeEventSource.autoStart = true;
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({ matches: false, media: query, addEventListener() {}, removeEventListener() {} })),
  );
  stubDialogs();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("live is a button that opens the system panel", async () => {
  open();
  const button = await live();
  expect(button.textContent).toBe("live");
  expect(button.getAttribute("aria-haspopup")).toBe("dialog");
  expect(button.getAttribute("aria-expanded")).toBe("false");
  const shown = await panel();
  expect(button.getAttribute("aria-expanded")).toBe("true");
  expect(within(shown).getByText(`LADO ${BUNDLE_VERSION}`)).toBeTruthy();
  expect(within(shown).getByRole("link", { name: "GitHub ↗" }).getAttribute("href")).toBe("https://github.com/ladohq/lado");
  const facts = await within(shown).findByText("Running");
  const rows = Array.from(facts.closest("dl")!.querySelectorAll("dt"), (dt) => [
    dt.textContent,
    dt.nextElementSibling!.textContent,
  ]);
  expect(rows).toEqual([
    ["Server", window.location.origin],
    ["Running", "2 h 14 min"],
    ["Home", "~/.lado"],
    ["tmux", "3.5a · socket lado"],
  ]);
  expect(within(shown).getByRole("button", { name: "Copy path" })).toBeTruthy();
  const providers = within(shown).getByRole("region", { name: "Providers" });
  expect(Array.from(providers.querySelectorAll("li"), (li) => [li.querySelector(".provider-dot")!.className, li.textContent])).toEqual([
    ["provider-dot provider-ok", "Claude Code2.1.295"],
    ["provider-dot provider-warn", "Kilo7.9.0 · tested 7.8.3"],
    ["provider-dot provider-off", "OpenCodenot installed"],
  ]);
  expect(shown.querySelector(".system-check")!.textContent).toMatch(/^Up to date · checked \d\d:\d\d↻$/);
  fireEvent.keyDown(shown, { key: "Escape" });
  expect(screen.queryByRole("dialog", { name: "System" })).toBeNull();
});

test("the clipboard icon copies the report and the browser line", async () => {
  const writeText = vi.fn(async () => {});
  vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText }, userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36" });
  open();
  const shown = await panel();
  const copy = within(shown).getByRole("button", { name: "Copy system info" });
  await waitFor(() => expect((copy as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(copy);
  await waitFor(() => expect(writeText).toHaveBeenCalledWith(`${SYSTEM.report}- Browser: Chrome 141 on macOS\n`));
  expect(await within(shown).findByText("System info copied")).toBeTruthy();
});

test("↻ checks now, and a failed check says so with its reason", async () => {
  open();
  const shown = await panel();
  let answer: (value: Response) => void = () => {};
  const fetch = serve();
  fetch.mockImplementationOnce(() => new Promise((resolve) => (answer = resolve)));
  fireEvent.click(within(shown).getByRole("button", { name: "Check for a newer LADO now" }));
  expect(shown.querySelector(".system-check")!.textContent).toBe("Checking…↻");
  expect(fetch).toHaveBeenCalledWith("/api/update/check", expect.objectContaining({ method: "POST" }));
  const failed = info({ error: "cannot look up LADO's latest version: timed out" });
  await act(async () => answer(new Response(JSON.stringify(failed))));
  const line = shown.querySelector(".system-check")!;
  expect(line.textContent).toMatch(/^Check failed · \d\d:\d\d↻$/);
  fireEvent.focus(within(line as HTMLElement).getByText(/Check failed/));
  expect((await screen.findByRole("tooltip")).textContent).toBe("cannot look up LADO's latest version: timed out");
});

test("a newer LADO marks live and gives the panel its Update block; no line under the bar", async () => {
  update = info({ latest: "99.0.0", available: "99.0.0", released: "2026-10-12" });
  serve();
  open();
  const button = await screen.findByRole("button", { name: "System: LADO 99.0.0 is available" });
  expect(button.textContent).toBe("live↑ 99.0.0");
  expect(screen.queryByText(/is available/)).toBeNull();
  const block = within(await panel()).getByRole("region", { name: "Update" });
  expect(block.textContent).toContain("99.0.0 is out");
  expect(within(block).getByRole("link", { name: "What's new" }).getAttribute("href")).toBe(
    "https://github.com/ladohq/lado/releases/tag/v99.0.0",
  );
  expect(within(block).getByRole("button", { name: "Update…" })).toBeTruthy();
});

test("without an installer the panel shows the commands by hand and no Update button", async () => {
  update = info({
    latest: "99.0.0",
    available: "99.0.0",
    can_update: false,
    why_not: "LADO runs from /x/.venv, not a uv tool or pipx install of lado from PyPI; lado update does not upgrade it",
    by_hand: ["lado server stop", "/x/.venv/bin/pip install lado==99.0.0", "lado ui"],
  });
  serve();
  open();
  const block = within(await panel()).getByRole("region", { name: "Update" });
  expect(within(block).queryByRole("button", { name: "Update…" })).toBeNull();
  expect(block.textContent).toContain("not a uv tool or pipx install");
  expect(block.querySelector("pre")!.textContent).toBe(
    "lado server stop\n/x/.venv/bin/pip install lado==99.0.0\nlado ui",
  );
  expect(within(block).getByRole("button", { name: "Copy commands" })).toBeTruthy();
});

test("Update… shows the plan, starts the update and waits for a restarted server, also of the same version", async () => {
  update = info({ latest: "99.0.0", available: "99.0.0" });
  const fetch = serve();
  open();
  fireEvent.click(within(await panel()).getByRole("button", { name: "Update…" }));
  const dialog = await screen.findByRole("dialog", { name: `Update LADO ${BUNDLE_VERSION} → 99.0.0?` });
  expect(await within(dialog).findByText(/session/)).toBeTruthy();
  expect(dialog.textContent).toContain("session lado: supervisor busy, developer idle · 1 open run");
  expect(dialog.textContent).toContain("this UI server");
  expect(dialog.textContent).toContain("Busy agents lose their current turn.");
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "Date"], now: Date.now() });
  await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: "Restart and update" })));
  expect(fetch).toHaveBeenCalledWith("/api/update", expect.objectContaining({ method: "POST", body: JSON.stringify({ to: "99.0.0" }) }));
  const wait = await screen.findByRole("status", { name: "Updating LADO" });
  expect(wait.textContent).toContain("The server is restarting · 0:00");
  expect(screen.queryByRole("dialog", { name: "System" })).toBeNull();

  down = true; // the update stops the server
  await act(() => vi.advanceTimersByTimeAsync(3 * POLL_MS));
  expect(wait.textContent).toContain("0:06");
  // The old server is back after a rollback: its version is the same, its start is newer.
  down = false;
  health = { ok: true, version: BUNDLE_VERSION, started_at: "2026-10-09T10:05:00.000+00:00" };
  update = info({ last: result({ outcome: "running" }) });
  await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
  expect(screen.getByRole("status", { name: "Updating LADO" })).toBeTruthy(); // still running
  update = info({
    last: result({ outcome: "rolled_back", reason: "LADO 99.0.0 did not install right: --version says nothing", database: "restored", tail: ["Rolling back"] }),
  });
  await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
  expect(screen.queryByRole("status", { name: "Updating LADO" })).toBeNull();
  const banner = screen.getByRole("alert", { name: "Update result" });
  expect(banner.textContent).toContain(
    `The update to 99.0.0 failed: LADO 99.0.0 did not install right: --version says nothing. Rolled back to LADO ${BUNDLE_VERSION}. lado.db was restored from its backup.`,
  );
  expect(banner.querySelector("pre")!.textContent).toBe("Rolling back\n… full log: /home/x/.lado/update.log");
});

test("a server that does not come back in 5 minutes is named with the log, and the page goes on", async () => {
  update = info({ latest: "99.0.0", available: "99.0.0" });
  serve();
  open();
  fireEvent.click(within(await panel()).getByRole("button", { name: "Update…" }));
  const dialog = await screen.findByRole("dialog", { name: /Update LADO/ });
  await within(dialog).findByText(/session/);
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "Date"], now: Date.now() });
  await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: "Restart and update" })));
  down = true;
  await act(() => vi.advanceTimersByTimeAsync(GIVE_UP_MS));
  const wait = screen.getByRole("status", { name: "Updating LADO" });
  expect(wait.textContent).toContain("The server did not come back. See /home/x/.lado/update.log; start it with lado ui.");
  down = false;
  health = { ok: true, version: "99.0.0", started_at: "2026-10-09T10:09:00.000+00:00" };
  update = info({ current: "99.0.0", last: result() });
  await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
  expect(screen.getByRole("status", { name: "Update result" }).textContent).toContain("✓ LADO 99.0.0 is ready.");
});

test("an update's result shows once: dismissed, it stays away", async () => {
  update = info({
    last: result({
      outcome: "partial",
      sessions_failed: [{ name: "demo", command: "lado start /src/demo --name demo" }],
    }),
  });
  serve();
  const first = open();
  const banner = await screen.findByRole("alert", { name: "Update result" });
  expect(banner.textContent).toContain("LADO 99.0.0 runs, but 1 session did not resume.");
  expect(banner.textContent).toContain("demo: resume it with lado start /src/demo --name demo");
  fireEvent.click(within(banner).getByRole("button", { name: "Dismiss" }));
  expect(screen.queryByRole("alert", { name: "Update result" })).toBeNull();
  first.unmount();
  const fetch = serve();
  open();
  await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/update", expect.anything()));
  await live();
  expect(screen.queryByRole("alert", { name: "Update result" })).toBeNull();
});

test("a running update or an old result shows no banner", async () => {
  update = info({ last: result({ outcome: "running", ended_at: null }) });
  const fetch = serve();
  const first = open();
  await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/update", expect.anything()));
  await live();
  expect(screen.queryByLabelText("Update result")).toBeNull();
  first.unmount();
  update = info({ last: result({ ended_at: "2026-01-01T00:00:00+00:00" }) });
  serve();
  open();
  await live();
  expect(screen.queryByLabelText("Update result")).toBeNull();
});

test("the check line says when it looked and how it went", () => {
  const now = new Date(2026, 9, 9, 15, 0);
  const at = (date: Date) => date.toISOString();
  expect(checkLine(info({ checked_at: at(new Date(2026, 9, 9, 9, 12)) }), now).text).toBe("Up to date · checked 09:12");
  expect(checkLine(info({ available: "9.9.9", checked_at: at(new Date(2026, 9, 8, 22, 0)) }), now).text).toBe(
    "checked yesterday",
  );
  expect(when(at(new Date(2026, 9, 2, 9, 0)), now)).toMatch(/2 Oct|Oct 2/);
  const failed = checkLine(info({ error: "timed out", checked_at: at(new Date(2026, 9, 9, 9, 12)) }), now);
  expect(failed).toEqual({ text: "Check failed · 09:12", tip: "timed out" });
  expect(checkLine(info({ checked_at: null }), now).text).toBe("No update check (LADO_NO_UPDATE_CHECK=1)");
});

test("the browser line and the home folder", () => {
  expect(browserLine("Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0")).toBe(
    "- Browser: Firefox 131 on Linux",
  );
  expect(
    browserLine("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15"),
  ).toBe("- Browser: Safari 18 on macOS");
  expect(shortHome("/Users/kao/.lado")).toBe("~/.lado");
  expect(shortHome("/home/kao")).toBe("~");
  expect(shortHome("/srv/lado")).toBe("/srv/lado");
});

test("an update that did not start ends the wait on the same server and says why", async () => {
  update = info({ latest: "99.0.0", available: "99.0.0" });
  serve();
  open();
  fireEvent.click(within(await panel()).getByRole("button", { name: "Update…" }));
  const dialog = await screen.findByRole("dialog", { name: /Update LADO/ });
  await within(dialog).findByText(/session/);
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "Date"], now: Date.now() });
  await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: "Restart and update" })));
  // The server never went away: its start is the same.
  update = info({
    last: result({ outcome: "failed", log: null, tail: [], database: null, reason: "the update did not start: cannot look up LADO's versions on PyPI" }),
  });
  await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
  expect(screen.queryByRole("status", { name: "Updating LADO" })).toBeNull();
  expect(screen.getByRole("alert", { name: "Update result" }).textContent).toContain(
    `The update to 99.0.0 failed: the update did not start: cannot look up LADO's versions on PyPI. LADO ${BUNDLE_VERSION} runs.`,
  );
});
