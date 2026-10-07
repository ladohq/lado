// The live store's message windows: the latest page of the messages of one kind, earlier
// pages on request, and the feed's changes that belong to the window.
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { MessageInfo, MessagePage } from "./api";
import { FakeEventSource, stream } from "./fakes";
import { Live, matches, type MessageFilter, type MessageSpec } from "./live";
import cases from "./messageFilter.cases.json";

function message(id: number, from = "supervisor", to = "human", more: Partial<MessageInfo> = {}): MessageInfo {
  return {
    id,
    from,
    to,
    kind: "message",
    summary: `m${id}`,
    body: "",
    state: "delivered",
    choices: null,
    free_answer: false,
    question_state: null,
    answered_by: null,
    reply_to: null,
    choice: null,
    reply_state: null,
    attachments: [],
    created_at: `2026-10-04T12:00:${String(id % 60).padStart(2, "0")}.000Z`,
    ...more,
  };
}

// Each GET of messages waits until the test answers it (`answer`), oldest first; `asked`
// keeps its query.
let asked: { query: URLSearchParams; resolve: (page: MessagePage | { status: number; detail: string }) => void }[];
let fetch: ReturnType<typeof vi.fn>;

beforeEach(() => {
  asked = [];
  fetch = vi.fn(async (path: string) => {
    if (path === "/api/sessions") return new Response("[]");
    const url = new URL(path, "http://lado");
    if (url.pathname.endsWith("/messages")) {
      return new Promise<Response>((resolve) =>
        asked.push({
          query: url.searchParams,
          resolve: (page) =>
            resolve(
              "status" in page
                ? new Response(JSON.stringify({ detail: page.detail }), { status: page.status })
                : new Response(JSON.stringify(page)),
            ),
        }),
      );
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

const settle = async () => {
  await vi.waitFor(() => {});
  await new Promise((done) => setTimeout(done));
};

const answer = async (items: MessageInfo[], earlier = false) => {
  const next = asked.shift();
  if (!next) throw new Error("no request for messages");
  next.resolve({ items, earlier });
  await settle();
};

const query = (n = 0) => Object.fromEntries(asked[n].query);

async function started(): Promise<Live> {
  const live = new Live();
  live.start();
  stream().start();
  await settle();
  return live;
}

const HUMAN: MessageSpec = { with: "human", limit: 3 };

const ids = (live: Live, spec = HUMAN) => {
  const window = live.messagesOf("lado", spec);
  return window && "items" in window ? window.items.map((one) => one.id) : window;
};

const change = (item: MessageInfo | null, key = String(item?.id)) =>
  stream().send("change", { kind: "messages", session: "lado", key, op: "update", item });

test.each(cases.cases)("the feed's rule takes the messages of the case table: $filter", ({ filter, ids: taken }) => {
  const shown = cases.messages.filter((one) => matches(one, filter as MessageFilter)).map((one) => one.id);
  expect(shown).toEqual(taken);
});

test("a window loads the latest page of its kind, with its limit", async () => {
  const live = await started();
  live.watchMessages("lado", HUMAN);
  expect(ids(live)).toBeNull();
  expect(query()).toEqual({ with: "human", limit: "3" });
  await answer([message(4), message(5), message(7)], true);
  expect(ids(live)).toEqual([4, 5, 7]);
  expect(live.messagesOf("lado", HUMAN)).toMatchObject({ earlier: true, loadingEarlier: false, problem: null });
});

test("the feed adds a newer message, replaces one inside the window, ignores one before it and one of another kind", async () => {
  const live = await started();
  live.watchMessages("lado", HUMAN);
  await answer([message(4), message(7)], true);
  change(message(9));
  change(message(8, "w1", "supervisor")); // between agents
  change(message(2)); // before the window
  change(message(7, "supervisor", "human", { summary: "changed" }));
  change(null, "4");
  const window = live.messagesOf("lado", HUMAN);
  expect(ids(live)).toEqual([7, 9]);
  expect(window && "items" in window && window.items[0].summary).toBe("changed");
});

test("earlier messages are loaded before the window's first one and put in front", async () => {
  const live = await started();
  live.watchMessages("lado", HUMAN);
  await answer([message(4), message(7)], true);
  live.loadEarlier("lado", HUMAN);
  live.loadEarlier("lado", HUMAN); // one at a time
  expect(asked).toHaveLength(1);
  expect(query()).toEqual({ with: "human", limit: "3", before: "4" });
  expect(live.messagesOf("lado", HUMAN)).toMatchObject({ loadingEarlier: true });
  await answer([message(1), message(3)]);
  expect(ids(live)).toEqual([1, 3, 4, 7]);
  expect(live.messagesOf("lado", HUMAN)).toMatchObject({ earlier: false, loadingEarlier: false });
  live.loadEarlier("lado", HUMAN); // nothing earlier
  expect(asked).toHaveLength(0);
});

test("a change that comes while earlier messages load is applied after them, also for a message they bring", async () => {
  const live = await started();
  live.watchMessages("lado", HUMAN);
  await answer([message(4), message(7)], true);
  live.loadEarlier("lado", HUMAN);
  change(message(3, "w1", "human", { kind: "question", question_state: "answered" }));
  change(message(8));
  expect(ids(live)).toEqual([4, 7]);
  await answer([message(1), message(3, "w1", "human", { kind: "question", question_state: "open" })]);
  expect(ids(live)).toEqual([1, 3, 4, 7, 8]);
  const window = live.messagesOf("lado", HUMAN);
  expect(window && "items" in window && window.items[1].question_state).toBe("answered");
});

test("earlier messages that cannot load say why and can be asked for again", async () => {
  const live = await started();
  live.watchMessages("lado", HUMAN);
  await answer([message(4)], true);
  live.loadEarlier("lado", HUMAN);
  asked.shift()!.resolve({ status: 503, detail: "lado.db is newer" });
  await settle();
  expect(live.messagesOf("lado", HUMAN)).toMatchObject({ problem: "lado.db is newer", loadingEarlier: false, earlier: true });
  live.loadEarlier("lado", HUMAN);
  expect(query()).toMatchObject({ before: "4" });
  await answer([message(2)]);
  expect(live.messagesOf("lado", HUMAN)).toMatchObject({ problem: null });
  expect(ids(live)).toEqual([2, 4]);
});

test("a reset of the feed loads the window again from its first message, not only the latest page", async () => {
  const live = await started();
  live.watchMessages("lado", HUMAN);
  await answer([message(4), message(7)], true);
  stream().send("reset", {}, "20");
  expect(query()).toEqual({ with: "human", after: "3" });
  change(message(9));
  await answer([message(4), message(7), message(8)], true);
  expect(ids(live)).toEqual([4, 7, 8, 9]);
});

test("loading up to a message or a time before the window is one request for the range", async () => {
  const live = await started();
  live.watchMessages("lado", HUMAN);
  await answer([message(20), message(30)], true);
  const byId = live.loadUpTo("lado", HUMAN, { id: 12 });
  expect(asked).toHaveLength(1);
  expect(query()).toEqual({ with: "human", after: "11", before: "20" });
  await answer([message(12), message(15)], true);
  await byId;
  expect(ids(live)).toEqual([12, 15, 20, 30]);
  const byTime = live.loadUpTo("lado", HUMAN, { at: "2026-10-04T11:00:00.000Z" });
  expect(query()).toEqual({ with: "human", since: "2026-10-04T11:00:00.000Z", before: "12" });
  await answer([message(5)], true);
  await byTime;
  expect(ids(live)).toEqual([5, 12, 15, 20, 30]);
  await live.loadUpTo("lado", HUMAN, { id: 15 }); // in the window: nothing to load
  expect(asked).toHaveLength(0);
});

test("windows of other kinds and sessions are apart; a window goes when the last page lets go", async () => {
  const live = await started();
  const all: MessageSpec = { limit: 3 };
  const stop = live.watchMessages("lado", HUMAN);
  const stopAll = live.watchMessages("lado", all);
  expect(query(1)).toEqual({ limit: "3" });
  await answer([message(4)]);
  await answer([message(4), message(5, "w1", "supervisor")]);
  change(message(6, "w1", "supervisor"));
  expect(ids(live)).toEqual([4]);
  expect(ids(live, all)).toEqual([4, 5, 6]);
  stop();
  expect(ids(live)).toBeUndefined();
  stopAll();
});

test("an agent's window asks for its messages in its lifetime", async () => {
  const live = await started();
  const spec: MessageSpec = { agent: "w1", since: "2026-10-04T12:00:00.500Z", until: "2026-10-04T12:00:09.000Z", limit: 10 };
  live.watchMessages("lado", spec);
  expect(query()).toEqual({ agent: "w1", since: spec.since, until: spec.until, limit: "10" });
  await answer([message(1, "supervisor", "w1")]);
  change(message(5, "w1", "supervisor"));
  change(message(12, "w1", "supervisor")); // after it finished
  expect(ids(live, spec)).toEqual([1, 5]);
});
