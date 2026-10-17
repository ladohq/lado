// The Shell on a phone (docs/design/ui.md, Phone layout): <html data-phone>, the Menu button
// and the rail as a drawer.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { SessionInfo } from "./api";
import { App } from "./App";
import { FakeEventSource, FakeScreen, FakeSocket, stubDialogs } from "./fakes";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const NONE = { gates: 0, questions: 0, agents: 0 };

function session(name: string, more: Partial<SessionInfo> = {}): SessionInfo {
  const settings = { kits: ["default"], provider: "claude", permission_mode: null, without: [], ran_seconds: 0, running_since: null, stopped_at: null, title: null };
  return { name, repo: `/src/${name}`, status: "running", agents: 1, waiting: NONE, busy: 0, ...settings, ...more };
}

let sessions: SessionInfo[] = [];

beforeEach(() => {
  localStorage.clear();
  sessions = [session("lado")];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      if (path === "/api/sessions") return new Response(JSON.stringify(sessions));
      if (path.endsWith("/about")) return new Response("{}", { status: 404 });
      if (path.includes("/messages?")) return new Response(JSON.stringify({ items: [], earlier: false }));
      return new Response("[]");
    }),
  );
  FakeEventSource.all = [];
  FakeEventSource.autoStart = true;
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("WebSocket", FakeSocket);
  stubDialogs();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  delete document.documentElement.dataset.phone;
});

function open(path = "/kits") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

test("the page says on <html> whether it is a phone, upright or sideways, and follows it", () => {
  const phone = FakeScreen.phone();
  open();
  expect(document.documentElement.dataset.phone).toBe("tall");
  phone.set({ width: 844, height: 390 });
  expect(document.documentElement.dataset.phone).toBe("short");
  phone.set({ pointer: "fine" });
  expect(document.documentElement.dataset.phone).toBeUndefined();
});

test("a computer's page never says it is a phone", () => {
  new FakeScreen("fine", 390, 844);
  open();
  expect(document.documentElement.dataset.phone).toBeUndefined();
});
