// The live store's list of what waits for the human (Needs you): loaded from /api/waiting,
// and loaded again on reset and on every change that can change it; never polled.
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { SessionInfo, WaitingItem } from "./api";
import { FakeEventSource, stream } from "./fakes";
import { Live } from "./live";

const NONE = { gates: 0, questions: 0, agents: 0 };

const session = (name: string, status: SessionInfo["status"] = "running"): SessionInfo => ({
  name,
  repo: `/src/${name}`,
  status,
  agents: 1,
  waiting: NONE,
  kits: ["default"],
  provider: "claude",
  permission_mode: null,
  without: [],
});

const item = (key: string): WaitingItem => ({
  session: "lado",
  kind: "agent",
  key,
  since: "2026-10-03T12:00:00.000Z",
  gate: null,
  question: null,
  agent: null,
});

// Each GET /api/waiting waits until the test answers it (`answer`), oldest first.
let asked: ((items: WaitingItem[]) => void)[] = [];

const answer = async (items: WaitingItem[]) => {
  const next = asked.shift();
  if (!next) throw new Error("no request for /api/waiting");
  next(items);
  await vi.waitFor(() => {});
  await new Promise((done) => setTimeout(done));
};

const waitingRequests = (fetch: ReturnType<typeof vi.fn>) =>
  fetch.mock.calls.filter(([path]) => path === "/api/waiting").length;

let fetch: ReturnType<typeof vi.fn>;

beforeEach(() => {
  asked = [];
  fetch = vi.fn(async (path: string) => {
    if (path === "/api/sessions") return new Response(JSON.stringify([session("lado"), session("old", "stopped")]));
    if (path === "/api/waiting") {
      return new Promise<Response>((resolve) => asked.push((items) => resolve(new Response(JSON.stringify(items)))));
    }
    return new Response("[]");
  });
  vi.stubGlobal("fetch", fetch);
  FakeEventSource.all = [];
  FakeEventSource.autoStart = false;
  vi.stubGlobal("EventSource", FakeEventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// A store with its stream open and the sessions loaded.
async function started(): Promise<Live> {
  const live = new Live();
  live.start();
  stream().start();
  await vi.waitFor(() => expect(live.get().sessions).not.toBeNull());
  return live;
}

const change = (kind: string, session: string, key: string, item: unknown = {}) =>
  stream().send("change", { kind, session, key, op: "update", item });

const keys = (live: Live) => {
  const waiting = live.get().waiting;
  return waiting && "items" in waiting ? waiting.items.map((one) => one.key) : waiting;
};

test("nothing loads what waits until a page watches it, and it goes when the last one lets go", async () => {
  const live = await started();
  change("gates", "lado", "1");
  expect(waitingRequests(fetch)).toBe(0);
  const stop = live.watch("waiting");
  const again = live.watch("waiting");
  expect(waitingRequests(fetch)).toBe(1);
  await answer([item("gate:1")]);
  expect(keys(live)).toEqual(["gate:1"]);
  stop();
  expect(keys(live)).toEqual(["gate:1"]);
  again();
  expect(live.get().waiting).toBeNull();
  change("gates", "lado", "1");
  expect(waitingRequests(fetch)).toBe(1);
});

test("a change of a session's gates, agents or messages loads it again, also of a session no page watches", async () => {
  const live = await started();
  live.watch("waiting");
  await answer([item("gate:1")]);
  for (const kind of ["gates", "agents", "messages"]) {
    change(kind, "other", "x");
    // One item in place of another: the count is the same, the list is not.
    await answer([item(`${kind}:2`)]);
    expect(keys(live)).toEqual([`${kind}:2`]);
  }
  change("events", "lado", "7");
  expect(waitingRequests(fetch)).toBe(4);
});

test("a reset of the feed loads it again", async () => {
  const live = await started();
  live.watch("waiting");
  await answer([]);
  stream().send("reset", {}, "20");
  expect(waitingRequests(fetch)).toBe(2);
  await answer([item("question:3")]);
  expect(keys(live)).toEqual(["question:3"]);
});

test("a session that stops or comes back loads it again; another change of a session does not", async () => {
  const live = await started();
  live.watch("waiting");
  await answer([]);
  change("sessions", "lado", "lado", { ...session("lado"), agents: 3 });
  expect(waitingRequests(fetch)).toBe(1);
  change("sessions", "lado", "lado", session("lado", "stopped"));
  expect(waitingRequests(fetch)).toBe(2);
  await answer([]);
  change("sessions", "old", "old", session("old", "tmux_gone"));
  expect(waitingRequests(fetch)).toBe(3);
});

test("loads at once wait for each other: one at a time, and one more for all changes meanwhile", async () => {
  const live = await started();
  live.watch("waiting");
  change("gates", "lado", "1");
  change("agents", "lado", "w1");
  change("messages", "lado", "5");
  expect(waitingRequests(fetch)).toBe(1);
  await answer([item("old")]);
  expect(waitingRequests(fetch)).toBe(2);
  await answer([item("new")]);
  expect(keys(live)).toEqual(["new"]);
  expect(waitingRequests(fetch)).toBe(2);
});

test("a list that cannot load says why", async () => {
  fetch.mockImplementation(async (path: string) =>
    path === "/api/waiting"
      ? new Response(JSON.stringify({ detail: "lado.db is newer" }), { status: 503 })
      : new Response("[]"),
  );
  const live = await started();
  live.watch("waiting");
  await vi.waitFor(() => expect(live.get().waiting).toEqual({ error: "lado.db is newer" }));
});
