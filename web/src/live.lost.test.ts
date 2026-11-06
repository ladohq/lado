// The store across a lost connection: `lost` comes 2 s after the feed goes and leaves with
// it, a load that fails keeps what was loaded, and what failed loads again on its own.
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { GateInfo, SessionInfo } from "./api";
import { FakeEventSource, stream } from "./fakes";
import { Live, LOST_AFTER_MS } from "./live";

const gate = { id: 1, run: "r", answer: null } as GateInfo;
const SPEC = { with: "human", limit: 10 } as const;
const NOW = "2026-11-06T12:00:00.000Z";
const message = (id: number) => ({ id, from: "human", to: "supervisor", body: "", summary: "hi", created_at: NOW });

let away = false; // no answer to any request
let fetch: ReturnType<typeof vi.fn>;
let live: Live;

const asked = (path: string) => fetch.mock.calls.filter(([one]) => String(one).startsWith(path)).length;
const settle = () => vi.advanceTimersByTimeAsync(0);

beforeEach(() => {
  vi.useFakeTimers();
  vi.spyOn(console, "error").mockImplementation(() => {});
  away = false;
  fetch = vi.fn(async (path: string) => {
    if (away) throw new TypeError("Failed to fetch");
    if (path === "/api/sessions") return new Response(JSON.stringify([{ name: "lado" } as SessionInfo]));
    if (path === "/api/waiting") return new Response("[]");
    if (path.includes("/gates")) return new Response(JSON.stringify([gate]));
    if (path.includes("/messages")) return new Response(JSON.stringify({ items: [message(5)], earlier: false }));
    return new Response("[]");
  });
  vi.stubGlobal("fetch", fetch);
  FakeEventSource.all = [];
  FakeEventSource.autoStart = false;
  vi.stubGlobal("EventSource", FakeEventSource);
  live = new Live();
  live.start();
});

afterEach(() => {
  live.stop();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("lost comes 2 s after the feed goes, not before", async () => {
  stream().start();
  await settle();
  stream().fail(false);
  expect(live.get().link).toBe("down");
  await vi.advanceTimersByTimeAsync(LOST_AFTER_MS - 1);
  expect(live.get().lost).toBe(false);
  await vi.advanceTimersByTimeAsync(1);
  expect(live.get().lost).toBe(true);
});

test("a drop shorter than that never says lost", async () => {
  stream().start();
  await settle();
  stream().fail(false);
  await vi.advanceTimersByTimeAsync(1000);
  stream().open();
  await vi.advanceTimersByTimeAsync(LOST_AFTER_MS * 2);
  expect(live.get().lost).toBe(false);
});

test("more errors of one loss do not push it back", async () => {
  stream().start();
  await settle();
  stream().fail(false);
  await vi.advanceTimersByTimeAsync(1500);
  stream().fail(false);
  await vi.advanceTimersByTimeAsync(500);
  expect(live.get().lost).toBe(true);
});

test("the feed back: lost goes at once", async () => {
  stream().start();
  await settle();
  stream().fail(false);
  await vi.advanceTimersByTimeAsync(LOST_AFTER_MS);
  stream().open();
  expect(live.get().lost).toBe(false);
});

test("a refused token is no loss", async () => {
  stream().start();
  await settle();
  fetch.mockImplementation(async () => new Response(JSON.stringify({ detail: "token" }), { status: 401 }));
  stream().fail(true);
  await settle();
  expect(live.get().link).toBe("refused");
  await vi.advanceTimersByTimeAsync(LOST_AFTER_MS);
  expect(live.get().lost).toBe(false);
});

test("a stream with no answer has no reason; one the server answered has", async () => {
  stream().start();
  await settle();
  away = true;
  stream().fail(true);
  await settle();
  expect(live.get().problem).toBeNull();
  await vi.advanceTimersByTimeAsync(3000);
  fetch.mockImplementation(async () => new Response(JSON.stringify({ detail: "starting" }), { status: 503 }));
  stream().fail(true);
  await settle();
  expect(live.get().problem).toBe("starting");
});

test("a reload that fails keeps the list and shows no error", async () => {
  live.watch("gates", "lado");
  stream().start();
  await settle();
  expect(live.get().gates.lado).toEqual({ items: [gate] });
  away = true;
  stream().send("reset", {}, "20");
  await settle();
  expect(live.get().gates.lado).toEqual({ items: [gate] });
});

test("a reload that fails keeps the sessions, what waits and the messages", async () => {
  live.watch("waiting");
  live.watchMessages("lado", SPEC);
  stream().start();
  await settle();
  const before = live.get();
  away = true;
  stream().send("reset", {}, "20");
  await settle();
  expect(live.get().sessions).toEqual(before.sessions);
  expect(live.get().waiting).toEqual(before.waiting);
  expect(live.get().messages).toEqual(before.messages);
});

test("a first load that fails says why", async () => {
  stream().start();
  await settle();
  away = true;
  live.watch("gates", "lado");
  await settle();
  expect(live.get().gates.lado).toEqual({ error: "No connection" });
});

test("what failed while away loads again when a resumed stream opens, with no reset", async () => {
  stream().start();
  await settle();
  stream().fail(false);
  away = true;
  live.watch("gates", "lado");
  live.watch("waiting");
  live.watchMessages("lado", SPEC);
  await settle();
  expect(live.get().gates.lado).toEqual({ error: "No connection" });
  away = false;
  stream().open();
  await settle();
  expect(live.get().gates.lado).toEqual({ items: [gate] });
  expect(live.get().waiting).toEqual({ items: [] });
  const windows = live.get().messages.lado;
  expect(Object.values(windows)[0]).toMatchObject({ items: [message(5)] });
});

test("a reload that failed loads again too: what it keeps misses the gap", async () => {
  live.watch("gates", "lado");
  stream().start();
  await settle();
  stream().fail(false);
  away = true;
  stream().send("reset", {}, "20");
  await settle();
  const before = asked("/api/sessions/lado/gates");
  away = false;
  stream().open();
  await settle();
  expect(asked("/api/sessions/lado/gates")).toBe(before + 1);
});

test("the sessions that failed load again", async () => {
  away = true;
  stream().start();
  await settle();
  expect(live.get().sessions).toEqual({ error: "No connection" });
  stream().fail(false);
  away = false;
  stream().open();
  await settle();
  expect(live.get().sessions).toMatchObject({ sessions: [{ name: "lado" }] });
});

test("nothing failed: the feed coming back loads nothing", async () => {
  live.watch("gates", "lado");
  stream().start();
  await settle();
  const before = fetch.mock.calls.length;
  stream().fail(false);
  stream().open();
  await settle();
  expect(fetch.mock.calls.length).toBe(before);
});

test("a list let go is not loaded again", async () => {
  stream().start();
  await settle();
  stream().fail(false);
  away = true;
  const stop = live.watch("gates", "lado");
  await settle();
  stop();
  away = false;
  const before = asked("/api/sessions/lado/gates");
  stream().open();
  await settle();
  expect(asked("/api/sessions/lado/gates")).toBe(before);
  expect(live.get().gates.lado).toBeUndefined();
});

test("the last message known is the highest id of the session's windows", async () => {
  expect(live.lastMessage("lado")).toBe(0);
  live.watchMessages("lado", SPEC);
  stream().start();
  await settle();
  expect(live.lastMessage("lado")).toBe(5);
  expect(live.lastMessage("other")).toBe(0);
});
