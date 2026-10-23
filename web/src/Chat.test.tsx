// The chat in a session's Activity tab: the messages with the human and the agents'
// questions, live from the feed; the composer and the answers go to the API.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { AttachmentInfo, GateInfo, MessageInfo, MessagePage, RunEventInfo, RunInfo, SessionInfo, WaitingItem } from "./api";
import { App } from "./App";
import { messageText } from "./Chat";
import { clock, day, dayName } from "./ChatText";
import { FakeEventSource, FakeIntersectionObserver, FakeSocket, stream } from "./fakes";
import { storeAgentMessages } from "./prefs";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const NO_WAITS = { gates: 0, questions: 0, agents: 0 };
const SETTINGS = { kits: ["default"], provider: "claude", permission_mode: null, without: [], ran_seconds: 0, running_since: null, stopped_at: null, busy: 0, title: null, project: null };
const SESSIONS: SessionInfo[] = [
  { name: "lado", repo: "/src/lado", status: "running", agents: 2, waiting: NO_WAITS, ...SETTINGS },
  { name: "old", repo: "/src/old", status: "stopped", agents: 0, waiting: NO_WAITS, ...SETTINGS },
];

function message(id: number, from: string, to: string, summary: string, more: Partial<MessageInfo> = {}): MessageInfo {
  return {
    id,
    from,
    to,
    kind: "message",
    summary,
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
    created_at: "2026-10-03T12:00:00.000Z",
    recommendation: null,
    ...more,
  };
}

function question(id: number, more: Partial<MessageInfo> = {}): MessageInfo {
  return message(id, "w1", "human", "Merge w1 now?", {
    kind: "question",
    body: "Tests pass.",
    choices: ["yes", "later"],
    free_answer: true,
    question_state: "open",
    ...more,
  });
}

// A run event as the server gives it: a flow event's transition as state.transition reads it.
function event(
  id: number,
  kind: string,
  detail: string,
  created_at = "2026-10-03T12:00:00.500Z",
  more: Partial<RunEventInfo> = {},
): RunEventInfo {
  const [, from_state, outcome, to_state] = /^(\w+) -(\w+)-> (\w+)$/.exec(detail) ?? [];
  const transition = kind === "flow" && from_state ? { from_state, outcome, to_state } : null;
  return { id, run: "feature/x", kind, actor: "w1", detail, transition, created_at, ...more };
}

type Posted = { path: string; body: unknown };

// The server's page of `all` for a query: with, before, after, since (by the second it
// names no less), the latest `limit`, and whether earlier ones of the kind come before.
function page(all: MessageInfo[], query: URLSearchParams): MessagePage {
  const number = (name: string) => Number(query.get(name) ?? NaN);
  const party = query.get("with");
  const since = query.get("since");
  const kind = all.filter(
    (one) =>
      (party === null || one.from === party || one.to === party) &&
      (since === null || Date.parse(one.created_at) >= Math.floor(Date.parse(since) / 1000) * 1000),
  );
  const taken = kind.filter(
    (one) => !(one.id >= number("before")) && !(one.id <= number("after")),
  );
  const items = query.has("limit") ? taken.slice(-number("limit")) : taken;
  const bound = items[0]?.id ?? number("before");
  return { items, earlier: kind.some((one) => one.id < bound) };
}

// What waits for the human, as the server lists it from `chat` and `gates` as they are now
// (state.waiting_items): open gates, then open questions, of the running session "lado".
function waitingOf(chat: MessageInfo[], gates: GateInfo[]): WaitingItem[] {
  return [
    ...gates
      .filter((one) => one.answer === null)
      .map((gate) => ({ session: "lado", kind: "gate" as const, key: `gate-${gate.id}`, since: gate.created_at, gate })),
    ...chat
      .filter((one) => one.kind === "question" && one.question_state === "open")
      .map((question) => ({ session: "lado", kind: "question" as const, key: `question-${question.id}`, since: question.created_at, question })),
  ];
}

// The API: the sessions, a session's messages (`chat`, by pages; each query in `queries`),
// run events (`events`), gates, what waits (from `chat` and `gates` as they are when asked)
// and runs, and the POSTs, which answer `answer`.
function serve(
  chat: MessageInfo[],
  answer: { status: number; body: unknown } = { status: 200, body: { result: "sent" } },
  events: RunEventInfo[] = [],
  gates: GateInfo[] = [],
  runs: RunInfo[] = [],
) {
  const posted: Posted[] = [];
  const queries: Record<string, string>[] = [];
  const fetch = vi.fn(async (path: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      posted.push({ path, body: init.body ? JSON.parse(String(init.body)) : undefined });
      return new Response(JSON.stringify(answer.body), { status: answer.status });
    }
    if (path === "/api/sessions") return new Response(JSON.stringify(SESSIONS));
    const url = new URL(path, "http://lado");
    if (url.pathname.startsWith("/api/sessions/") && url.pathname.endsWith("/messages")) {
      queries.push(Object.fromEntries(url.searchParams));
      return new Response(JSON.stringify(page(chat, url.searchParams)));
    }
    if (path.startsWith("/api/sessions/") && path.endsWith("/events")) {
      return new Response(JSON.stringify(events));
    }
    if (path.startsWith("/api/sessions/") && path.endsWith("/gates")) {
      return new Response(JSON.stringify(gates));
    }
    if (path === "/api/waiting") return new Response(JSON.stringify(waitingOf(chat, gates)));
    if (path.endsWith("/runs")) return new Response(JSON.stringify(runs));
    if (path.endsWith("/agents")) return new Response("[]");
    return new Response("{}", { status: 404 });
  });
  vi.stubGlobal("fetch", fetch);
  return { fetch, posted, queries };
}

function open(path = "/sessions/lado/activity") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

const chat = () => screen.findByRole("log", { name: "Chat with the session" });

// A row's head: who, and the muted part (undefined when there is none).
const head = (row: HTMLElement) =>
  ["feed-who", "feed-aside"].map((one) => row.querySelector(`.feed-head .${one}`)?.textContent);

function changed(item: MessageInfo | null, key = String(item?.id), session = "lado") {
  return { kind: "messages", session, key, op: "update", item };
}

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
  FakeEventSource.all = [];
  FakeEventSource.autoStart = true;
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("WebSocket", FakeSocket);
  FakeIntersectionObserver.all = [];
  vi.stubGlobal("IntersectionObserver", FakeIntersectionObserver);
});

// jsdom lays nothing out: every clientHeight is 0, which the scroll rule takes for a hidden
// feed (an expanded waiting card). The feed gets 1 px, so it is shown; the tests give its
// scrollHeight themselves.
beforeEach(() => {
  Object.defineProperty(HTMLElement.prototype, "clientHeight", {
    configurable: true,
    get(this: HTMLElement) {
      return this.classList.contains("chat-feed") ? 1 : 0;
    },
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  delete (HTMLElement.prototype as { clientHeight?: number }).clientHeight;
});

test("the chat shows who wrote each message, its summary and its body as Markdown without HTML", async () => {
  serve([
    message(1, "human", "supervisor", "merge w1, please"),
    message(2, "supervisor", "human", "merged w1", { body: "**All** checks pass.\n\n<img src=x onerror=alert(1)>" }),
  ]);
  open();
  const log = await chat();
  const [mine, reply] = await within(log).findAllByRole("article");
  expect(head(mine)).toEqual(["You", "→ supervisor"]);
  expect(mine.className).toContain("mine");
  expect(mine.querySelector(".avatar")?.textContent).toBe("Y");
  expect(within(mine).getByText("merge w1, please")).toBeTruthy();
  expect(head(reply)).toEqual(["supervisor", undefined]);
  expect(reply.querySelector(".avatar")?.textContent).toBe("S");
  expect(reply.querySelector(".feed-head time")?.textContent).toBe(clock(reply.querySelector("time")!.dateTime));
  expect(within(reply).getByText("All").tagName).toBe("STRONG"); // a body to the human shows at once
  expect(reply.querySelector("img")).toBeNull();
});

test("a failed message and a reply only in the terminal are marked", async () => {
  serve([
    message(1, "human", "supervisor", "are you there?", { state: "failed", reply_state: null }),
    message(2, "human", "supervisor", "merge w1", { reply_state: "missing" }),
    message(3, "human", "supervisor", "thanks", { reply_state: "replied" }),
  ]);
  open();
  const [failed, missing, replied] = within(await chat()).getAllByRole("article");
  expect(within(failed).getByText("not delivered")).toBeTruthy();
  expect(within(missing).getByText("supervisor replied only in its terminal")).toBeTruthy();
  expect(within(replied).queryByText(/replied only/)).toBeNull();
});

test("a message that continues its sender's group has no head; its time stays in a <time>", async () => {
  serve([
    message(1, "supervisor", "human", "first", { created_at: "2026-10-03T12:00:00.000Z" }),
    message(2, "supervisor", "human", "second", { created_at: "2026-10-03T12:02:00.000Z" }),
    question(3, { from: "supervisor", created_at: "2026-10-03T12:03:00.000Z", question_state: "closed" }),
  ]);
  open();
  const [first, second, asked] = await within(await chat()).findAllByRole("article");
  expect(first.className).not.toContain("continued");
  expect(head(first)).toEqual(["supervisor", undefined]);
  expect(second.className).toContain("continued");
  expect(second.querySelector(".feed-head")).toBeNull();
  expect(second.getAttribute("aria-label")).toBe("Message from supervisor");
  expect(second.querySelector("time")?.getAttribute("dateTime")).toBe("2026-10-03T12:02:00.000Z");
  expect(asked.className).toContain("continued");
  expect(asked.getAttribute("aria-label")).toBe("Question from supervisor");
});

test("a divider with the day's name stands between entries of different local days", async () => {
  const days = [new Date(2026, 9, 2, 23, 50), new Date(2026, 9, 3, 0, 10)].map((one) => one.toISOString());
  serve([
    message(1, "supervisor", "human", "late", { created_at: days[0] }),
    message(2, "supervisor", "human", "early", { created_at: days[1] }),
  ]);
  open();
  const log = await chat();
  await within(log).findByText("early");
  const dividers = within(log).getAllByRole("separator");
  expect(dividers.map((one) => one.textContent)).toEqual([dayName(days[1])]);
  expect(within(log).getAllByRole("article")[1].className).not.toContain("continued");
});

test("no card in the chat draws a head of its own", async () => {
  serve(
    [message(1, "human", "supervisor", "go"), question(5), question(6, { question_state: "answered", answered_by: 9 })],
    undefined,
    [],
    [gate(1), closed(2, "approve")],
  );
  open();
  const log = await chat();
  await within(log).findAllByRole("article", { name: "Question from w1" });
  expect(log.querySelector(".chat-meta, .chat-from")).toBeNull();
});

test("the chat follows the feed: new and changed messages, not those between agents", async () => {
  serve([message(1, "human", "supervisor", "merge w1")]);
  open();
  const log = await chat();
  await within(log).findByText("merge w1");
  stream().send("change", changed(message(3, "supervisor", "human", "merged")), "11");
  stream().send("change", changed(message(2, "w1", "supervisor", "between agents")), "12");
  stream().send("change", changed(message(1, "human", "supervisor", "merge w1", { reply_state: "missing" })), "13");
  stream().send("change", changed(message(4, "supervisor", "human", "elsewhere"), "4", "old"), "14");
  const articles = within(log).getAllByRole("article");
  expect(articles.map(said)).toEqual(["merge w1", "merged"]);
  expect(within(articles[0]).getByText(/replied only in its terminal/)).toBeTruthy();
});

// The waiting card above the composer (WaitingCard.tsx; its own behaviour in
// WaitingCard.test.tsx).
const waitingCard = (session = "lado") => screen.findByRole("region", { name: `What waits for you in ${session}` });

test("an open question is one line in the feed whose arrow leads to its tab; it is answered in the card", async () => {
  const chatList = [question(5)];
  const { posted } = serve(chatList);
  const scrolled = vi.fn();
  Element.prototype.scrollIntoView = scrolled;
  open();
  const line = await within(await chat()).findByRole("article", { name: "Question from w1" });
  expect(line.className).toContain("chat-quiet");
  expect(line.id).toBe("message-5");
  expect(line.querySelector(".late-text")?.textContent).toBe("w1 asked: Merge w1 now?");
  // The arrow stands beside the text, which a long line cuts, never in it.
  expect(line.querySelector(".late-text button")).toBeNull();
  expect(within(line).queryByText("Tests pass.")).toBeNull(); // the details are in the card
  expect(within(await chat()).queryByRole("button", { name: "yes" })).toBeNull();
  const card = await waitingCard();
  expect(within(card).getByText("Tests pass.")).toBeTruthy();
  // The card stands between the feed and the composer.
  const section = screen.getByRole("region", { name: "Chat" });
  expect([...section.children].map((one) => one.className.split(" ")[0])).toEqual(["chat-feed", "waiting-card", "composer"]);
  // In the chat it minimizes, and the edge above it resizes it.
  expect(within(card).getByRole("button", { name: "Minimize the card" })).toBeTruthy();
  expect(within(card).getByRole("separator", { name: "Resize the card" })).toBeTruthy();
  scrolled.mockClear();
  fireEvent.click(within(line).getByRole("button", { name: "Answer question #5" }));
  await waitFor(() => expect(card.querySelector('[data-item="5"]')?.className).toContain("marked"));
  expect(scrolled.mock.contexts).toEqual([card.querySelector('[data-item="5"]')]);
  fireEvent.click(within(card).getByRole("button", { name: "yes" }));
  fireEvent.click(within(card).getByRole("button", { name: "Send answer to w1" }));
  await waitFor(() =>
    expect(posted).toEqual([{ path: "/api/sessions/lado/answers", body: { answers: [{ question: 5, choice: "yes", skip: false }] } }]),
  );
  expect(within(card).getByRole("button", { name: "yes" })).toBeTruthy(); // not shown as answered yet
  chatList[0] = question(5, { question_state: "answered", answered_by: 6 });
  chatList.push(message(6, "human", "w1", "Answer to #5: yes", { reply_to: 5, choice: "yes" }));
  stream().send("change", changed(chatList[0]), "11");
  stream().send("change", changed(chatList[1]), "12");
  await waitFor(() => expect(screen.queryByRole("region", { name: "What waits for you in lado" })).toBeNull());
  const answered = within(await chat()).getByRole("article", { name: "Question from w1" });
  expect(within(answered).queryByRole("button")).toBeNull();
  // The answer is in the card: the choice marked in the list, who answered and when under
  // it, the choice not repeated there; no row of its own.
  expect(answered.querySelector(".choices .chosen")?.textContent).toBe("✓ yes");
  const given = answered.querySelector(".question-answer") as HTMLElement;
  expect(given.id).toBe("message-6");
  expect(given.querySelector(".answer-head")?.textContent).toContain("You · answered");
  expect(given.querySelector(".answer-choice")).toBeNull();
  expect(given.textContent).toBe(given.querySelector(".answer-top")?.textContent);
  expect(answered.querySelector(".chat-outcome")).toBeNull();
  expect(within(await chat()).queryByRole("article", { name: "Message from you" })).toBeNull();
  expect((await chat()).textContent).not.toMatch(/Answered|Answer to #5/);
});

test("an answer given after other rows is in its question's card and one quiet line where it was given", async () => {
  const scrolled = vi.fn();
  Element.prototype.scrollIntoView = scrolled;
  serve(
    [
      question(5, { question_state: "answered", answered_by: 7 }),
      message(6, "supervisor", "human", "in between"),
      message(7, "human", "w1", "Answer to #5: after the release", { reply_to: 5 }),
      question(8, { question_state: "answered", answered_by: 10 }),
      message(9, "supervisor", "human", "in between too"),
      message(10, "human", "w1", "Answer to #8: later", { reply_to: 8, choice: "later", body: "after the tag" }),
    ].map((one, i) => ({ ...one, created_at: `2026-10-03T12:0${i}:00.000Z` })),
  );
  open();
  const log = await chat();
  const [own, chose] = within(log).getAllByRole("article", { name: "Question from w1" });
  expect(own.querySelector(".question-answer .chat-body")?.textContent).toBe("after the release");
  expect(chose.querySelector(".choices .chosen")?.textContent).toBe("✓ later");
  expect(chose.querySelector(".question-answer .chat-body")?.textContent).toBe("after the tag"); // the comment
  expect(chose.textContent?.match(/later/g)).toHaveLength(1); // the choice once, in the list
  expect(own.querySelector(".choices .chosen")).toBeNull();
  const lines = within(log).getAllByRole("article", { name: /^You answered question/ });
  expect(lines.map((one) => [one.id, one.textContent])).toEqual([
    ["message-7", expect.stringContaining("after the release")],
    ["message-10", expect.stringMatching(/later.*after the tag/)],
  ]);
  // The card's answer has no anchor of its own: a link to the answer goes to its line.
  expect(own.querySelector(".question-answer")?.id).toBe("");
  scrolled.mockClear();
  fireEvent.click(within(lines[0]).getByRole("link", { name: "question #5 ↑" }));
  expect(scrolled.mock.contexts).toEqual([own]);
  expect(within(log).queryByRole("article", { name: "Message from you" })).toBeNull();
});

test("an answer to a question not in the window is a row that says which question; it never continues a group", async () => {
  serve(
    [
      message(12, "human", "w1", "one more thing"),
      message(13, "human", "w1", "Answer to #10: A", { reply_to: 10, choice: "A" }),
      message(14, "human", "w1", "Answer to #11: B", { reply_to: 11, choice: "B" }),
      message(15, "human", "w1", "thanks"),
    ].map((one, i) => ({ ...one, created_at: `2026-10-03T12:00:0${i}.000Z` })),
  );
  open();
  const rows = await within(await chat()).findAllByRole("article", { name: "Message from you" });
  expect(rows.map((one) => head(one)[1])).toEqual(["→ w1", "→ w1 · answer to #10", "→ w1 · answer to #11", "→ w1"]);
  expect(rows[1].id).toBe("message-13");
});

test("an own answer of more lines shows its whole text once in the card, as typed", async () => {
  serve([
    question(5, { question_state: "answered", answered_by: 6 }),
    message(6, "human", "w1", "Answer to #5: after the release", { reply_to: 5, body: "after the release\nand the tag" }),
  ]);
  open();
  const card = await within(await chat()).findByRole("article", { name: "Question from w1" });
  const given = card.querySelector(".question-answer") as HTMLElement;
  expect(given.textContent?.match(/after the release/g)).toHaveLength(1);
  expect(given.querySelectorAll("br")).toHaveLength(1);
});

test("a dismissal is in its question's card; a late one also a quiet line, one whose question is not in the window a line of its own", async () => {
  serve([
    question(5, { question_state: "dismissed", answered_by: 6 }),
    message(6, "human", "w1", "Dismissed #5", { reply_to: 5 }),
    question(9, { question_state: "dismissed", answered_by: 11 }),
    message(10, "supervisor", "human", "in between"),
    message(11, "human", "w1", "Dismissed #9", { reply_to: 9 }),
    message(7, "human", "w1", "Dismissed #4", { reply_to: 4 }),
    message(8, "human", "w1", "Answer to #3: no", { reply_to: 3 }),
  ].map((one, i) => ({ ...one, created_at: `2026-10-03T12:0${i}:00.000Z` })));
  open();
  const log = await chat();
  const [first, second] = await within(log).findAllByRole("article", { name: "Question from w1" });
  for (const card of [first, second]) {
    expect(card.querySelector(".question-answer.dismissed .answer-head")?.textContent).toContain("You · skipped");
  }
  expect(first.querySelector(".question-answer")?.id).toBe("message-6");
  const late = within(log).getByRole("article", { name: "You skipped question #9" });
  expect([late.id, late.textContent]).toEqual(["message-11", expect.stringContaining("skipped question #9 ↑")]);
  const lines = within(log).getAllByRole("article", { name: /^You skipped question/ });
  expect(lines.map((one) => one.id)).toEqual(["message-11", "message-7"]);
  // A one-line own answer whose question is not in the window is an answer.
  const answer = within(log).getByRole("article", { name: "Message from you" });
  expect(within(answer).getByRole("heading").textContent).toBe("no");
});

test("a dismissal's comment shows in the card, in its late line and in its line without the question", async () => {
  serve([
    question(5, { question_state: "dismissed", answered_by: 6 }),
    message(6, "human", "w1", "Dismissed #5", { reply_to: 5, body: "not now:\nafter the release" }),
    question(9, { question_state: "dismissed", answered_by: 11 }),
    message(10, "supervisor", "human", "in between"),
    message(11, "human", "w1", "Dismissed #9", { reply_to: 9, body: "wrong\nquestion" }),
    message(7, "human", "w1", "Dismissed #4", { reply_to: 4, body: "asked twice" }),
  ].map((one, i) => ({ ...one, created_at: `2026-10-03T12:0${i}:00.000Z` })));
  open();
  const log = await chat();
  const [first] = await within(log).findAllByRole("article", { name: "Question from w1" });
  const given = first.querySelector(".question-answer.dismissed") as HTMLElement;
  expect(given.textContent).toContain("not now:");
  expect(given.querySelectorAll("br")).toHaveLength(1);
  const late = within(log).getByRole("article", { name: "You skipped question #9" });
  expect(late.querySelector(".late-text")?.textContent).toMatch(/skipped question #9 ↑ · wrong question$/);
  const alone = within(log).getByRole("article", { name: "You skipped question #4" });
  expect(alone.textContent).toContain("asked twice");
});


test.each([
  [{ question_state: "dismissed" as const, answered_by: 9 }, "You · skipped"],
  [{ question_state: "closed" as const }, "Closed: the agent left"],
  [{ question_state: "answered" as const, answered_by: 9 }, "You · answered"],
])("a question no longer open says what became of it, also without the reply in the window", async (state, outcome) => {
  serve([question(5, state)]);
  open();
  const card = await within(await chat()).findByRole("article", { name: "Question from w1" });
  expect(card.querySelector(".chat-outcome, .answer-head")?.textContent).toBe(outcome);
  expect(within(card).getByText("Question #5")).toBeTruthy();
  expect(within(card).queryByRole("button")).toBeNull();
});

test("the composer sends with Enter, keeps Shift+Enter for a new line and shows nothing ahead of the feed", async () => {
  const { posted } = serve([]);
  open();
  await chat();
  const field = screen.getByRole("textbox", { name: "Write to the supervisor…" });
  fireEvent.change(field, { target: { value: "first line" } });
  fireEvent.keyDown(field, { key: "Enter", shiftKey: true });
  expect(posted).toEqual([]);
  fireEvent.change(field, { target: { value: "merge w1\nthen tag it" } });
  fireEvent.keyDown(field, { key: "Enter" });
  await waitFor(() => expect(posted).toEqual([{ path: "/api/sessions/lado/messages", body: { text: "merge w1\nthen tag it" } }]));
  await waitFor(() => expect((field as HTMLTextAreaElement).value).toBe(""));
  expect(within(await chat()).queryByRole("article")).toBeNull();
});

test("the composer is one frame with Send inside, says to whom and how to send", async () => {
  serve([]);
  open();
  await chat();
  const field = screen.getByRole("textbox", { name: "Write to the supervisor…" }) as HTMLTextAreaElement;
  const frame = field.closest(".composer-box")!;
  expect(within(frame as HTMLElement).getByRole("button", { name: "Send" })).toBeTruthy();
  expect(field.rows).toBe(1);
  const form = field.closest("form")!;
  expect(form.querySelector(".composer-to")?.textContent).toBe("to supervisor");
  expect(form.querySelector(".composer-keys")?.textContent).toBe(
    "Enter to send · Shift+Enter for a new line · paste or drop files to attach",
  );
});

test("in a stopped session the composer is off and says why", async () => {
  serve([]);
  open("/sessions/old/activity");
  await chat();
  const field = screen.getByRole("textbox", { name: "Write to the supervisor…" }) as HTMLTextAreaElement;
  expect(field.disabled).toBe(true);
  expect(field.placeholder).toBe("The session is stopped: resume it to write");
  expect((screen.getByRole("button", { name: "Send" }) as HTMLButtonElement).disabled).toBe(true);
});

test("the composer's field grows with its text up to 8 lines, then scrolls", async () => {
  serve([]);
  open();
  await chat();
  const field = screen.getByRole("textbox", { name: "Write to the supervisor…" }) as HTMLTextAreaElement;
  let height = 44;
  Object.defineProperty(field, "scrollHeight", { configurable: true, get: () => height });
  field.style.lineHeight = "20px";
  fireEvent.change(field, { target: { value: "one\ntwo" } });
  expect(field.style.height).toBe("44px");
  expect(field.style.overflowY).toBe("hidden");
  height = 400;
  fireEvent.change(field, { target: { value: "many\nlines\n".repeat(10) } });
  expect(field.style.height).toBe("160px"); // 8 lines of 20 pixels
  expect(field.style.overflowY).toBe("auto");
});

test("a message the server refuses keeps its text and says why at the field", async () => {
  const { posted } = serve([], { status: 400, body: { detail: 'session "lado" is stopped' } });
  open();
  await chat();
  const field = screen.getByRole("textbox", { name: "Write to the supervisor…" });
  fireEvent.change(field, { target: { value: "hi" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  expect((await screen.findByRole("alert")).textContent).toBe('session "lado" is stopped');
  expect((field as HTMLTextAreaElement).value).toBe("hi");
  expect(posted).toHaveLength(1);
});

test.each(["messages", "events", "gates"])(
  "a feed whose %s the server cannot load (an older server: 404) says so instead of an empty chat",
  async (list) => {
    const { fetch } = serve([]);
    const served = fetch.getMockImplementation()!;
    fetch.mockImplementation(async (path: string, init?: RequestInit) =>
      new URL(path, "http://lado").pathname === `/api/sessions/lado/${list}`
        ? new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 })
        : served(path, init),
    );
    open();
    const feed = await chat();
    expect((await within(feed).findByRole("alert")).textContent).toBe("Not Found");
    expect(within(feed).queryByText(/No messages yet/)).toBeNull();
  },
);

test("an empty chat says how to start", async () => {
  serve([]);
  open();
  expect(within(await chat()).getByText("No messages yet. Write to the supervisor below.")).toBeTruthy();
});

// The feed around the chat (the Layout task): run events, the agents' messages to each
// other behind a switch, bodies to the human shown at once.

// What each row says first: its summary's heading, or the human's text, which has none.
const said = (row: HTMLElement) => (row.querySelector(".chat-summary") ?? row.querySelector(".chat-body"))?.textContent;

const headings = (log: HTMLElement) => within(log).getAllByRole("article").map(said);

// The text of a message (docs/design/ui.md, Message text): the human's once, as typed; an
// agent's to the human its summary and whole body; a very long one cut behind Show more.

const paragraphs = (n: number) => Array.from({ length: n }, (_, i) => `line ${i + 1}`).join("\n\n");

test("the human's message of more lines shows its text once: no heading, nothing folded", async () => {
  // The core's summary is the first line with its tab as a space; the body the whole text.
  const text = "first\tline of mine\nand the second";
  serve([message(1, "human", "supervisor", "first line of mine", { body: text })]);
  open();
  const row = await within(await chat()).findByRole("article", { name: "Message from you" });
  expect(row.textContent?.match(/first.line of mine/g)).toHaveLength(1);
  expect(row.textContent).toContain("first\tline of mine");
  expect(row.querySelector("details")).toBeNull();
  expect(within(row).queryByRole("heading")).toBeNull();
  expect(within(row).getByText(/and the second/)).toBeTruthy();
});

test("the human's message without a body shows its summary as its text", async () => {
  serve([message(1, "human", "supervisor", "merge w1, please")]);
  open();
  const row = await within(await chat()).findByRole("article", { name: "Message from you" });
  expect(row.querySelector(".chat-body")?.textContent).toBe("merge w1, please");
  expect(within(row).queryByRole("heading")).toBeNull();
});

test("the human's single line breaks are breaks; an agent's body is one paragraph", async () => {
  serve([
    message(1, "human", "supervisor", "a", { body: "a\nb" }),
    message(2, "supervisor", "human", "two lines", { body: "a\nb" }),
  ]);
  open();
  const [mine, theirs] = await within(await chat()).findAllByRole("article");
  const own = mine.querySelector(".chat-body")!;
  expect(own.querySelectorAll("p")).toHaveLength(1);
  expect(own.querySelectorAll("br")).toHaveLength(1);
  const body = theirs.querySelector(".chat-body")!;
  expect(body.querySelectorAll("p")).toHaveLength(1);
  expect(body.querySelector("br")).toBeNull();
});

test("an agent's message to the human shows its summary in bold and its whole body up to 30 lines", async () => {
  serve([message(2, "supervisor", "human", "report", { body: paragraphs(30) })]);
  open();
  const card = await within(await chat()).findByRole("article");
  const summary = within(card).getByRole("heading");
  expect([summary.textContent, summary.className]).toEqual(["report", expect.stringContaining("lead")]);
  expect(within(card).getByText("line 30")).toBeTruthy();
  expect(within(card).queryByRole("button", { name: /Show/ })).toBeNull();
  expect(card.querySelector("details")).toBeNull();
});

test("a longer text shows its first 12 lines and Show more, which shows it all in place", async () => {
  serve([
    message(1, "human", "supervisor", "line 1", { body: paragraphs(31) }),
    message(2, "supervisor", "human", "report", { body: paragraphs(31) }),
  ]);
  open();
  for (const card of await within(await chat()).findAllByRole("article")) {
    expect(within(card).getByText("line 12")).toBeTruthy();
    expect(within(card).queryByText("line 13")).toBeNull();
    const more = within(card).getByRole("button", { name: "Show more" });
    expect(more.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(more);
    expect(within(card).getByText("line 31")).toBeTruthy();
    expect(within(card).getByRole("button", { name: "Show less" }).getAttribute("aria-expanded")).toBe("true");
  }
});

test.each([
  ["the human's, its whole text", message(1, "human", "supervisor", "Раунд 1", { body: "Раунд 1\nи ещё" }), "Раунд 1\nи ещё"],
  ["the human's of one line", message(1, "human", "supervisor", "go"), "go"],
  ["an agent's, summary and body", message(1, "analyst", "human", "Раунд 1", { body: "1. Какие действия?" }), "Раунд 1\n\n1. Какие действия?"],
  ["an agent's whose body repeats its summary", message(1, "analyst", "human", "Раунд 1", { body: "Раунд 1\n\nдалее" }), "Раунд 1\n\nдалее"],
  ["an agent's without a body", message(1, "analyst", "human", "Раунд 1"), "Раунд 1"],
])("a message's copied text: %s", (_, one, text) => {
  expect(messageText(one)).toBe(text);
});

test("each message's head has Copy message, also a row that continues its group", async () => {
  serve([
    message(1, "supervisor", "human", "merged w1", { body: "All checks pass." }),
    message(2, "supervisor", "human", "next"),
  ]);
  open();
  const log = await chat();
  const [first, second] = await within(log).findAllByRole("article");
  const copier = within(first).getByRole("button", { name: "Copy message" }).closest(".copy-icon-button")!;
  expect(copier.parentElement?.classList.contains("feed-when")).toBe(true);
  // Right before the time, nothing after it: the time ends on the feed's edge (LAD-136).
  expect([copier.nextElementSibling?.tagName, copier.nextElementSibling?.nextElementSibling]).toEqual(["TIME", null]);
  expect(copier.parentElement?.nextElementSibling).toBeNull(); // the block that wraps whole ends the head
  expect(second.classList.contains("continued")).toBe(true);
  expect(within(second).getByRole("button", { name: "Copy message" })).toBeTruthy();
});

test("an agent's summary that its body's first line repeats is not drawn", async () => {
  serve([
    message(1, "supervisor", "human", "merged w1", { body: "merged w1\n\nAll checks pass." }),
    message(2, "supervisor", "human", "the plan for…", { body: "the plan for the chat\n\nmore" }),
    message(3, "supervisor", "human", "merged w1", { body: "All checks pass." }),
  ]);
  open();
  const [same, cut, other] = await within(await chat()).findAllByRole("article");
  expect(within(same).queryByRole("heading")).toBeNull();
  expect(same.textContent?.match(/merged w1/g)).toHaveLength(1);
  expect(within(cut).queryByRole("heading")).toBeNull();
  expect(within(other).getByRole("heading").textContent).toBe("merged w1");
});

test("an agents' message to each other is one muted line of its summary; its body opens on a click", async () => {
  serve([
    message(1, "supervisor", "w1", "please merge", { body: "the **details**" }),
    message(2, "w1", "supervisor", "done"),
  ]);
  storeAgentMessages(true);
  open();
  const log = await chat();
  const [long, short] = await within(log).findAllByRole("article", { name: /^Message from .* to / });
  const folded = long.querySelector("details")!;
  expect(folded.open).toBe(false);
  expect(folded.querySelector("summary")?.textContent).toContain("please merge");
  expect(folded.querySelector("summary .chevron")).toBeTruthy();
  expect(folded.querySelector(":scope > .chat-body strong")?.textContent).toBe("details");
  expect(short.querySelector("details")).toBeNull();
  expect(short.querySelector(".chevron")).toBeNull();
  expect(within(short).getByRole("heading").textContent).toBe("done");
});

test("the agents' messages to each other show behind a toggle that loads the window of all messages and is remembered", async () => {
  const { queries } = serve([
    message(1, "human", "supervisor", "merge w1"),
    message(2, "supervisor", "w1", "please merge", { body: "details" }),
    message(3, "supervisor", "human", "merged"),
  ]);
  open();
  const log = await chat();
  await within(log).findByText("merged");
  expect(headings(log)).toEqual(["merge w1", "merged"]);
  expect(queries).toEqual([{ with: "human", limit: "50" }]);
  const toggle = screen.getByRole("button", { name: "Messages between agents" });
  expect(toggle.getAttribute("aria-pressed")).toBe("false");
  fireEvent.click(toggle);
  expect(toggle.getAttribute("aria-pressed")).toBe("true");
  await within(log).findByText("please merge");
  expect(headings(log)).toEqual(["merge w1", "please merge", "merged"]);
  expect(queries.at(-1)).toEqual({ limit: "50" });
  const between = within(log).getByRole("article", { name: "Message from supervisor to w1" });
  expect(head(between)).toEqual(["supervisor", "→ w1"]);
  expect(between.className).toContain("between");
  stream().send("change", changed(message(4, "w1", "supervisor", "done")), "11");
  expect(headings(log)).toContain("done");
  fireEvent.click(toggle);
  await waitFor(() => expect(headings(log)).toEqual(["merge w1", "merged"]));
  fireEvent.click(toggle);
  await within(log).findByText("please merge");
  cleanup();
  open();
  const again = await chat();
  await within(again).findByText("please merge");
  expect(screen.getByRole("button", { name: "Messages between agents" }).getAttribute("aria-pressed")).toBe("true");
});

test("the toggle for messages between agents is an icon at the team row's end whose tooltip says its state", async () => {
  serve([message(1, "human", "supervisor", "merge w1")]);
  open();
  await chat();
  const row = document.querySelector(".team-row")!;
  const toggle = within(row as HTMLElement).getByRole("button", { name: "Messages between agents" });
  expect(row.lastElementChild).toBe(toggle);
  expect(toggle.querySelector("svg")).toBeTruthy();
  expect(toggle.textContent).toBe("");
  expect(screen.queryByText(/Show agent messages/)).toBeNull();
  const lines = async () =>
    [...(await screen.findByRole("tooltip")).querySelectorAll(".tooltip-line")].map((line) => line.textContent);
  fireEvent.mouseEnter(toggle);
  expect(await lines()).toEqual(["Messages between agents: hidden", "Click to also show what agents write to each other."]);
  expect(toggle.getAttribute("aria-describedby")).toBe(screen.getByRole("tooltip").id);
  fireEvent.mouseLeave(toggle);
  expect(screen.queryByRole("tooltip")).toBeNull();
  fireEvent.click(toggle);
  fireEvent.focus(toggle); // the keyboard's focus: at once
  expect([...screen.getByRole("tooltip").querySelectorAll(".tooltip-line")].map((line) => line.textContent)).toEqual([
    "Messages between agents: shown",
    "Click to show only your conversation with the agents.",
  ]);
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("tooltip")).toBeNull();
  fireEvent.focus(toggle);
  fireEvent.blur(toggle);
  expect(screen.queryByRole("tooltip")).toBeNull();
});

// Flow events (docs/design/ui.md, Flow events): a run's events in a group under its name.

const runGroups = (log: HTMLElement) => within(log).getAllByRole("list", { name: /^Flow run / });
const kept = (line: HTMLElement, name: string) => line.querySelector(`.${name}`)?.textContent;

// A run of a flow that declares these states, each with its outcomes.
function flowRun(name: string, states: [string, Record<string, string>][], more: Partial<RunInfo> = {}): RunInfo {
  return {
    name,
    flow: "feature",
    kit: { name: "lado-dev", version: "0.11.1", source: "project" },
    task: "show messages once",
    state: states[0][0],
    status: "active",
    reason: "",
    acting: "w1",
    visits: {},
    gate: null,
    worktree: "/w",
    branch: `lado/lado/${name.replace("/", "-")}`,
    language: "",
    created_at: "2026-10-03T11:59:00Z",
    since: "2026-10-03T11:59:00Z",
    ended_at: null,
    states: states.map(([state, outcomes]) => ({
      name: state,
      kind: Object.keys(outcomes).length ? "work" : "end",
      agent: null,
      gate: null,
      ask: null,
      outcomes,
      max_visits: null,
      reads: [],
      produces: [],
    })),
    problem: null,
    ...more,
  };
}

const FEATURE: [string, Record<string, string>][] = [
  ["design", { ready: "architecture" }],
  ["architecture", { changes: "design", approved: "build" }],
  ["build", { ready: "review" }],
  ["review", { approved: "done", changes: "build", again: "review" }],
  ["done", {}],
];

test("a run's events in a row are one group under the run's name, which links to the run; each line says who and what", async () => {
  serve(
    [message(1, "human", "supervisor", "start it", { created_at: "2026-10-03T12:00:00Z" })],
    undefined,
    [
      event(5, "flow_start", "flow feature from kit lado-dev 0.11.1: show messages once", "2026-10-03T11:59:00Z", { actor: "supervisor" }),
      event(6, "flow", "design -ready-> architecture", "2026-10-03T11:59:30Z", { actor: "supervisor" }),
      event(7, "flow", "architecture -changes-> design", "2026-10-03T11:59:40Z", { actor: "architect" }),
      event(8, "something_else", "not a line", "2026-10-03T11:59:45Z"),
      event(9, "gate_answer", "#1 approve", "2026-10-03T11:59:50Z", { actor: "human" }),
      event(10, "flow", "moved somehow", "2026-10-03T12:00:01Z"),
      event(11, "gate_open", "#2 approval at check: Ship it?", "2026-10-03T12:00:02Z", { actor: "lado" }),
      event(12, "flow_set", "at review: by hand", "2026-10-03T12:00:03Z", { actor: "human" }),
      event(13, "flow_cancel", "no longer needed", "2026-10-03T12:00:04Z", { actor: "supervisor" }),
    ],
    [],
    [flowRun("feature/x", FEATURE)],
  );
  open();
  const log = await chat();
  await within(log).findAllByRole("listitem");
  const groups = runGroups(log);
  expect(groups.map((one) => within(one).getAllByRole("listitem").length)).toEqual([3, 3]);
  const group = groups[0].closest(".run-group") as HTMLElement;
  const link = within(group).getByRole("link", { name: "feature/x" });
  expect(link.getAttribute("href")).toBe("/sessions/lado/flows/feature%2Fx");
  expect(within(log).queryByRole("link", { name: "Flows" })).toBeNull();
  const [started, ready, changes, odd, set, cancelled] = within(log).getAllByRole("listitem");
  expect([kept(started, "run-actor"), kept(started, "run-chip"), kept(started, "run-detail")]).toEqual([
    "supervisor",
    "started",
    "flow feature from kit lado-dev 0.11.1: show messages once",
  ]);
  expect(started.querySelector(".avatar")?.textContent).toBe("S");
  expect(Array.from(ready.querySelectorAll(".run-state")).map((one) => one.textContent)).toEqual(["design", "architecture"]);
  expect([kept(ready, "run-outcome"), ready.querySelector(".run-outcome")?.className]).toEqual([
    "ready",
    expect.stringContaining("forward"),
  ]);
  expect(changes.querySelector(".run-outcome")?.className).toContain("back"); // the flow declares design first
  expect(kept(changes, "run-actor")).toBe("architect");
  expect([odd.querySelector(".run-state"), kept(odd, "run-detail")]).toEqual([null, "moved somehow"]);
  expect([kept(set, "run-chip"), kept(set, "run-actor")]).toEqual(["set by you", "You"]);
  expect([kept(cancelled, "run-chip"), kept(cancelled, "run-detail")]).toEqual(["cancelled", "no longer needed"]);
  expect(within(ready).getByText(clock("2026-10-03T11:59:30Z")).tagName).toBe("TIME");
  expect(within(log).queryByText(/not a line|#1 approve|#2 approval/)).toBeNull(); // a gate's opening is no line
  const order = Array.from(log.querySelectorAll("li, article")).map((one) => one.tagName);
  expect(order).toEqual(["LI", "LI", "LI", "ARTICLE", "LI", "LI", "LI"]);
  stream().send(
    "change",
    { kind: "events", session: "lado", key: "14", op: "insert", item: event(14, "flow_end", "at done", "2026-10-03T12:01:00Z", { actor: "lado" }) },
    "11",
  );
  const end = within(log).getAllByRole("listitem").at(-1)!;
  expect([kept(end, "run-chip"), kept(end, "run-detail")]).toEqual(["ended", "at done"]);
  expect(runGroups(log)).toHaveLength(2); // it joins the group above
});

// A step's direction by its run's flow (flowSteps.tsx): the same as the Flows tab's.

const outcome = (line: HTMLElement) => line.querySelector<HTMLElement>(".run-outcome")!;

test("ready, changes and ready again: both ready forward and green, changes back with the icon, by the flow's order", async () => {
  serve(
    [],
    undefined,
    [
      event(6, "flow", "build -ready-> review", "2026-10-03T11:59:30Z"),
      event(7, "flow", "review -changes-> build", "2026-10-03T11:59:40Z", { actor: "reviewer" }),
      event(8, "flow", "build -ready-> review", "2026-10-03T11:59:50Z"),
      event(9, "flow", "review -again-> review", "2026-10-03T11:59:55Z", { actor: "reviewer" }),
    ],
    [],
    [flowRun("feature/x", FEATURE)],
  );
  open();
  const log = await chat();
  await waitFor(() => expect(log.querySelectorAll(".run-outcome.forward")).toHaveLength(2));
  const lines = within(log).getAllByRole("listitem");
  const [ready, changes, again, stays] = lines.map(outcome);
  expect([ready, changes, again, stays].map((one) => one.className)).toEqual([
    "run-outcome forward",
    "run-outcome back",
    "run-outcome forward",
    "run-outcome back",
  ]);
  // The direction is read out with the line's text (a name on a plain span is dropped), and
  // shown by the colour and the icon only.
  expect(lines.map((line) => line.textContent)).toEqual(
    ["ready, a step forward", "changes, a step back", "ready, a step forward", "again, a step back"].map((said) =>
      expect.stringContaining(said),
    ),
  );
  expect(lines.map((line) => line.querySelector(".visually-hidden")?.textContent)).toEqual(
    Array(4).fill(expect.stringMatching(/^, a step /)),
  );
  expect([ready, changes, again, stays].map((one) => one.querySelector("svg") !== null)).toEqual([false, true, false, true]);
  expect(changes.textContent).toBe("changes");
});

test("hovering a step's outcome says where it goes, and for a step back what runs again", async () => {
  serve(
    [],
    undefined,
    [event(6, "flow", "build -ready-> review", "2026-10-03T11:59:30Z"), event(7, "flow", "review -changes-> build", "2026-10-03T11:59:40Z")],
    [],
    [flowRun("feature/x", FEATURE)],
  );
  open();
  const log = await chat();
  await waitFor(() => expect(log.querySelectorAll(".run-outcome.back")).toHaveLength(1));
  const [ready, changes] = within(log).getAllByRole("listitem").map(outcome);
  const lines = async () =>
    [...(await screen.findByRole("tooltip")).querySelectorAll(".tooltip-line")].map((line) => line.textContent);
  fireEvent.mouseEnter(ready);
  expect(await lines()).toEqual(["Forward in the flow, to review"]);
  fireEvent.mouseLeave(ready);
  fireEvent.mouseEnter(changes);
  expect(await lines()).toEqual(["Back: the work returns to build", "Runs again: build › review"]);
  fireEvent.mouseLeave(changes);
});

test("a step of a run whose flow cannot be read, or that is not loaded, is neutral: no colour, icon, name or tooltip", async () => {
  serve(
    [],
    undefined,
    [
      event(6, "flow", "review -changes-> build", "2026-10-03T11:59:30Z"),
      event(7, "flow", "review -changes-> build", "2026-10-03T11:59:40Z", { run: "fix/y" }),
    ],
    [],
    [flowRun("feature/x", FEATURE, { states: [], problem: "not JSON" })],
  );
  open();
  const log = await chat();
  await waitFor(() => expect(log.querySelectorAll(".run-outcome")).toHaveLength(2));
  for (const line of within(log).getAllByRole("listitem")) {
    const one = outcome(line);
    expect([one.className, one.querySelector("svg"), line.textContent]).toEqual([
      "run-outcome",
      null,
      expect.not.stringContaining("a step"),
    ]);
    fireEvent.mouseEnter(one);
  }
  await new Promise((done) => setTimeout(done, 400)); // past the tooltip's delay
  expect(screen.queryByRole("tooltip")).toBeNull();
});

test("events of two runs in a row are two groups, each under its run's name", async () => {
  serve([], undefined, [
    event(5, "flow_start", "a", "2026-10-03T12:00:00Z"),
    event(6, "flow_start", "b", "2026-10-03T12:00:01Z", { run: "fix/y" }),
  ]);
  open();
  const log = await chat();
  await within(log).findAllByRole("listitem");
  expect(runGroups(log).map((one) => one.getAttribute("aria-label"))).toEqual(["Flow run feature/x", "Flow run fix/y"]);
});

// Flow gates (the Gates task): an open gate is a card answered with its options, a closed
// one a line.

function gate(id: number, more: Partial<GateInfo> = {}): GateInfo {
  return {
    id,
    run: "feature/x",
    state: "check",
    kind: "approval",
    question: "Ship it?",
    options: ["approve", "reject"],
    note: "built it",
    note_body: "All **tests** pass.",
    attachments: [],
    reads: ["feature/x/plan"],
    answer: null,
    comment: "",
    answered_by: null,
    created_at: "2026-10-03T12:00:00.250Z",
    answered_at: null,
    closed_by_event: null,
    answer_attachments: [],
    problem: null,
    recommendation: null,
    ...more,
  };
}

const closed = (id: number, answer: string, more: Partial<GateInfo> = {}) =>
  gate(id, { answer, answered_by: "human", answered_at: "2026-10-03T12:05:00Z", reads: null, ...more });

// A closed gate's line in the feed.
const gateCard = async (id = 1) => within(await chat()).findByRole("article", { name: `Gate #${id}` });
// An open gate: its line in the feed, its panel in the waiting card (the shown tab).
const gateLine = async (id = 1) => within(await chat()).findByRole("article", { name: `Gate #${id} waits` });
const gateTab = async () => within(await waitingCard()).findByRole("tabpanel");

function gateChanged(item: GateInfo) {
  return { kind: "gates", session: "lado", key: String(item.id), op: "update", item };
}

test("a card minimized before a reload stays so while the session's gates still load after its questions", async () => {
  localStorage.setItem("lado.waitingMinimized.lado", JSON.stringify(["gate:1", "agent:w1"]));
  const { fetch } = serve([question(5)], undefined, [], [gate(1)]);
  let release = () => {};
  const gatesLater = new Promise<void>((resolve) => (release = resolve));
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      if (path.startsWith("/api/sessions/") && path.endsWith("/gates")) await gatesLater;
      return fetch(path, init);
    }),
  );
  open();
  const card = await waitingCard();
  await within(card).findByRole("tab", { name: "w1 1" });
  expect(card.classList.contains("minimized")).toBe(true);
  release();
  await within(card).findByRole("tab", { name: "feature/x 1" });
  expect(card.classList.contains("minimized")).toBe(true);
  expect(JSON.parse(localStorage.getItem("lado.waitingMinimized.lado") ?? "null")).toEqual(["gate:1", "agent:w1"]);
});

test("an open gate is a line in the feed and a tab of the card: its question, the note that led to it and the artifacts it reads", async () => {
  serve([], undefined, [], [gate(1)]);
  open();
  const line = await gateLine();
  expect(line.id).toBe("gate-1");
  expect(line.querySelector(".avatar-gate")).toBeTruthy();
  expect(line.querySelector(".late-text")?.textContent).toBe("Gate #1 feature/x · check waits: Ship it?");
  expect(within(line).queryByRole("button", { name: "Approve" })).toBeNull();
  const tab = within(await waitingCard()).getByRole("tab", { name: "feature/x 1" });
  expect(tab.getAttribute("aria-selected")).toBe("true");
  const card = await gateTab();
  expect(within(card).getByText("Ship it?")).toBeTruthy();
  expect(within(card).getByText("built it").tagName).toBe("STRONG");
  expect(within(card).getByText("tests").tagName).toBe("STRONG"); // the body, open, as Markdown
  // The session's artifacts are not loaded here: the name alone (ArtifactsTable.test.tsx).
  const reads = within(card).getByRole("list", { name: "Artifacts it reads" });
  expect(within(reads).getAllByRole("listitem").map((one) => one.textContent)).toEqual(["plan"]);
  expect(within(card).getByRole("textbox", { name: "Comment for the next step (optional)" })).toBeTruthy();
});

test("a gate whose run's flow cannot be read shows the problem instead of the artifacts it reads", async () => {
  const problem = 'run "feature/x": its flow snapshot is not JSON: line 1';
  serve([], undefined, [], [gate(1, { reads: null, problem })]);
  open();
  const card = await gateTab();
  expect(within(card).getByText(`Artifacts it reads cannot be shown: ${problem}`)).toBeTruthy();
  expect(within(card).queryByRole("list", { name: "Artifacts it reads" })).toBeNull();
  expect(within(card).getByText("Ship it?")).toBeTruthy();
  // Whether it can be answered is the core's to say.
  const approve = within(card).getByRole("button", { name: "Approve" }) as HTMLButtonElement;
  expect(approve.disabled).toBe(false);
});

test("a long note before the gate is behind Show more", async () => {
  const body = Array.from({ length: 30 }, (_, i) => `line ${i + 1}`).join("\n\n");
  serve([], undefined, [], [gate(1, { note_body: body })]);
  open();
  const card = await gateTab();
  expect(within(card).getByText("line 20")).toBeTruthy();
  expect(within(card).queryByText("line 21")).toBeNull();
  fireEvent.click(within(card).getByRole("button", { name: "Show more" }));
  expect(within(card).getByText("line 30")).toBeTruthy();
});

test.each([
  [gate(1), ["Approve", "Reject"]],
  [gate(1, { kind: "choice", options: ["left", "right"] }), ["left", "right"]],
  [gate(1, { kind: "loop", options: ["continue", "cancel"], reads: [] }), ["Continue", "Cancel run"]],
])("a gate's buttons are its options", async (one, labels) => {
  serve([], undefined, [], [one]);
  open();
  const card = await gateTab();
  const buttons = within(card.querySelector(".waiting-send") as HTMLElement).getAllByRole("button");
  expect(buttons.map((button) => button.textContent)).toEqual(labels);
  expect(buttons[0].className).toContain("primary");
});

test("a gate is answered with an option and the comment; the card waits for the feed", async () => {
  const gates = [gate(1)];
  const { posted } = serve([], undefined, [], gates);
  let release = () => {};
  const held = new Promise<void>((resolve) => (release = resolve));
  const plain = globalThis.fetch;
  vi.stubGlobal("fetch", async (path: string, init?: RequestInit) => {
    if (init?.method === "POST") await held;
    return plain(path, init);
  });
  open();
  const card = await gateTab();
  fireEvent.change(within(card).getByRole("textbox", { name: "Comment for the next step (optional)" }), {
    target: { value: "add a test\nfor the form" },
  });
  fireEvent.click(within(card).getByRole("button", { name: "Reject" }));
  await waitFor(() => expect((within(card).getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(true));
  release();
  await waitFor(() =>
    expect(posted).toEqual([
      { path: "/api/sessions/lado/gates/1/answer", body: { option: "reject", comment: "add a test\nfor the form" } },
    ]),
  );
  await waitFor(() => expect((within(card).getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(false));
  gates[0] = closed(1, "reject", { comment: "add a test\nfor the form" });
  stream().send("change", gateChanged(gates[0]), "11");
  const line = await gateCard();
  expect(within(line).queryByRole("button", { name: "Approve" })).toBeNull();
  expect(within(line).getByRole("button", { name: "Gate #1 · feature/x · check: reject by human" })).toBeTruthy();
  expect(screen.queryByRole("region", { name: "What waits for you in lado" })).toBeNull();
});

test("an answer the server refuses says why on the gate's tab", async () => {
  serve([], { status: 400, body: { detail: "gate #1 is closed already: approve by human" } }, [], [gate(1)]);
  open();
  const card = await gateTab();
  fireEvent.click(within(card).getByRole("button", { name: "Approve" }));
  expect((await within(card).findByRole("alert")).textContent).toBe("gate #1 is closed already: approve by human");
  expect(within(card).getByRole("button", { name: "Approve" })).toBeTruthy();
});

// A flow whose gate "check" goes forward to ship and back to build.
const GATED: [string, Record<string, string>][] = [
  ["build", { ready: "check" }],
  ["check", { approved: "ship", rejected: "build" }],
  ["ship", {}],
];

// The folded card's head: the one button of a closed gate's card, named by its title.
const gateHead = (card: HTMLElement) => within(card).getByRole("button", { name: /^Gate #\d+ · / });

// A run that reached gate #1 and the human's rejection of it with a comment of two lines.
function rejected(more: Partial<GateInfo> = {}) {
  const at = "2026-10-03T12:05:00.123Z";
  serve(
    [],
    undefined,
    [
      event(4, "flow", "build -ready-> check", "2026-10-03T12:00:00.100Z"),
      event(5, "gate_open", "#1 approval at check: Ship it?", "2026-10-03T12:00:00.250Z", { actor: "lado" }),
      event(6, "gate_answer", "#1 reject: split the form", at, { actor: "human" }),
      event(7, "flow", "check -rejected-> build", at, { actor: "human" }),
    ],
    [closed(1, "reject", { comment: "split the form first\nthen ship", answered_at: at, closed_by_event: 7, ...more })],
    [flowRun("feature/x", GATED)],
  );
  open();
}

test("the human rejects with a comment: the chat shows it once, under the move; the gate's card has none", async () => {
  rejected();
  const log = await chat();
  const card = await gateCard();
  await waitFor(() => expect(log.querySelector(".run-comment")).toBeTruthy());
  expect(log.textContent?.split("split the form first")).toHaveLength(2); // one copy
  expect(card.textContent).not.toContain("split the form first");
  expect(gateHead(card).getAttribute("aria-label")).toBe("Gate #1 · feature/x · check: reject by human");
  const move = (await moves()).find((one) => kept(one, "run-actor") === "You")!;
  expect(move.querySelector(".run-comment")?.textContent).toContain("split the form first");
});

test("the human's move and its comment stand on the human's ground, the agents' lines do not", async () => {
  rejected();
  await gateCard();
  await waitFor(async () => expect((await moves()).map((one) => one.classList.contains("mine"))).toEqual([false, true]));
});

test("a rejected gate, folded: a card with the flag, its title, the answer's chip by the move's direction, by you, the time and a chevron", async () => {
  rejected();
  const card = await gateCard();
  const head = gateHead(card);
  await waitFor(() => expect(head.querySelector(".run-outcome.back")).toBeTruthy());
  expect(head.getAttribute("aria-expanded")).toBe("false");
  expect(head.querySelector(".avatar-gate svg")).toBeTruthy();
  expect([kept(head, "gate-head-title"), kept(head, "gate-head-where"), kept(head, "gate-head-by")]).toEqual([
    "Gate #1",
    "feature/x · check",
    "by you",
  ]);
  const chip = head.querySelector(".run-outcome.back")!;
  expect([chip.textContent, chip.querySelector("svg") !== null]).toEqual(["reject", true]);
  expect(head.querySelector("time")?.getAttribute("dateTime")).toBe("2026-10-03T12:05:00.123Z");
  expect(head.querySelector(".gate-chevron svg")).toBeTruthy();
  // The chevron first, the time last: the time ends on the feed's edge (LAD-136).
  expect([head.firstElementChild?.className, head.lastElementChild?.tagName]).toEqual(["gate-chevron", "TIME"]);
  fireEvent.click(head);
  expect(head.getAttribute("aria-expanded")).toBe("true");
  expect(card.classList.contains("expanded")).toBe(true);
  fireEvent.click(head);
  expect(within(card).queryByText("Ship it?")).toBeNull();
});

test("an opened closed gate shows the question and the answer on the human's ground, read only, without reads", async () => {
  rejected();
  const card = await gateCard();
  await waitFor(() => expect(card.querySelector(".run-outcome.back")).toBeTruthy());
  fireEvent.click(gateHead(card));
  const body = card.querySelector(".gate-closed-card") as HTMLElement;
  expect(within(body).getByText("Ship it?")).toBeTruthy();
  const plaque = body.querySelector(".question-answer") as HTMLElement;
  expect(plaque.className).not.toContain("dismissed");
  expect([kept(plaque, "answer-who"), kept(plaque, "run-outcome"), kept(plaque, "answer-target")]).toEqual(["You", "reject", "→ build"]);
  expect(plaque.querySelector(".chat-body br")).toBeTruthy(); // the human's line breaks, as typed
  expect(plaque.textContent).toContain("split the form first");
  expect(within(card).queryByRole("list", { name: "Artifacts it reads" })).toBeNull();
  expect(within(card).queryByRole("textbox")).toBeNull();
  expect(within(card).queryByRole("button", { name: "Approve" })).toBeNull();
  expect(within(card).queryByRole("button", { name: "Reject" })).toBeNull();
});

test("the same gate answered twice: each move shows its own gate's comment, each card its own move's target", async () => {
  const at = "2026-10-03T12:05:00Z";
  serve(
    [],
    undefined,
    [
      event(6, "flow", "check -rejected-> build", at, { actor: "human" }),
      event(7, "flow", "build -ready-> check", "2026-10-03T12:05:00.300Z"),
      event(9, "flow", "check -approved-> ship", "2026-10-03T12:05:00.600Z", { actor: "human" }),
    ],
    [
      // Both answered at the same moment, as far as the times tell.
      closed(1, "reject", { comment: "first try", created_at: "2026-10-03T12:00:00Z", answered_at: at, closed_by_event: 6 }),
      closed(2, "approve", { comment: "second try", created_at: "2026-10-03T12:05:00.300Z", answered_at: at, closed_by_event: 9 }),
    ],
    [flowRun("feature/x", GATED)],
  );
  open();
  const log = await chat();
  await waitFor(() => expect(log.querySelectorAll(".run-comment")).toHaveLength(2));
  const said = (await moves()).filter((one) => one.querySelector(".run-comment")).map((one) => kept(one, "run-comment"));
  expect(said).toEqual(["first try", "second try"]);
  const targets = [];
  for (const id of [1, 2]) {
    const card = await gateCard(id);
    fireEvent.click(gateHead(card));
    targets.push(kept(card, "answer-target"));
  }
  expect(targets).toEqual(["→ build", "→ ship"]);
});

test("a gate closed by a cancel: its card says cancelled by supervisor without the reason; the reason is on the cancel's line", async () => {
  serve(
    [],
    undefined,
    [event(6, "flow_cancel", "dropped for now", "2026-10-03T12:05:00Z", { actor: "supervisor" })],
    [closed(1, "cancelled", { answered_by: "supervisor", comment: "dropped for now", closed_by_event: 6 })],
    [flowRun("feature/x", GATED)],
  );
  open();
  const card = await gateCard();
  const head = gateHead(card);
  expect(head.getAttribute("aria-label")).toBe("Gate #1 · feature/x · check: cancelled by supervisor");
  expect(card.textContent).not.toContain("dropped for now");
  expect([kept(head, "gate-head-by"), head.querySelector(".run-outcome")?.className]).toEqual(["by supervisor", "run-outcome"]);
  const [cancel] = await moves();
  expect(cancel.textContent).toContain("dropped for now");
  expect(cancel.classList.contains("mine")).toBe(false);
  // Closed by an agent: the plaque names it, quieter, with the reason.
  fireEvent.click(head);
  const plaque = card.querySelector(".question-answer") as HTMLElement;
  expect(plaque.className).toContain("dismissed");
  expect([kept(plaque, "answer-who"), kept(plaque, "run-outcome"), kept(plaque, "answer-target")]).toEqual([
    "supervisor",
    "cancelled",
    undefined,
  ]);
  expect(plaque.textContent).toContain("dropped for now");
});

test("a gate closed by flow-set: overridden by you, neutral, the reason on the human's line on their ground", async () => {
  serve(
    [],
    undefined,
    [event(6, "flow_set", "check -> build: built by hand", "2026-10-03T12:05:00Z", { actor: "human" })],
    [closed(1, "overridden", { comment: "built by hand", closed_by_event: 6 })],
    [flowRun("feature/x", GATED)],
  );
  open();
  const card = await gateCard();
  expect(gateHead(card).getAttribute("aria-label")).toBe("Gate #1 · feature/x · check: overridden by human");
  expect(card.textContent).not.toContain("built by hand");
  const [forced] = await moves();
  expect(forced.textContent).toContain("built by hand");
  expect(forced.classList.contains("mine")).toBe(true);
});

const files = (...names: string[]): AttachmentInfo[] =>
  names.map((name) => ({
    artifact: `a-${name}`,
    record: `r-${name}`,
    full_name: `feature/x/${name}`,
    name,
    scope: "feature/x",
    title: null,
    media_type: "text/markdown",
    size: 1200,
    hash: "h",
  }));

test("a long note is one folded line with its summary and artifacts; opened, 6 lines, Show more and the artifacts", async () => {
  const body = Array.from({ length: 30 }, (_, i) => `line ${i + 1}`).join("\n\n");
  serve([], undefined, [], [closed(1, "reject", { note: "review converged", note_body: body, attachments: files("ledger", "report") })]);
  open();
  const card = await gateCard();
  fireEvent.click(gateHead(card));
  expect(within(card).getByText("Ship it?")).toBeTruthy();
  const [note] = Array.from(card.querySelectorAll<HTMLDetailsElement>("details.gate-row"));
  expect(note.open).toBe(false);
  expect(note.querySelector("summary")?.textContent).toBe("Notereview converged · 2 artifacts");
  fireEvent.click(note.querySelector("summary")!);
  expect(note.open).toBe(true);
  expect(within(note).getByText("line 6")).toBeTruthy();
  expect(within(note).queryByText("line 7")).toBeNull();
  expect(within(note).getByRole("button", { name: "Show more" })).toBeTruthy();
  expect(within(note).getAllByRole("button", { name: /^Open artifact / })).toHaveLength(2);
});

test.each([
  ["reject", "recommended Approve · you answered otherwise"],
  ["approve", "recommended Approve · you agreed"],
])("the recommendation is one folded line that says whether the answer agreed (%s)", async (answer, said) => {
  serve([], undefined, [], [closed(1, answer, { note: "", note_body: "", recommendation: given("approve") })]);
  open();
  const card = await gateCard();
  fireEvent.click(gateHead(card));
  const [rec] = Array.from(card.querySelectorAll<HTMLDetailsElement>("details.gate-row"));
  expect(rec.open).toBe(false);
  expect(rec.querySelector("summary")?.textContent).toBe(`Supervisor${said}`);
  expect(card.querySelector(".rec")).toBeNull();
  fireEvent.click(rec.querySelector("summary")!);
  expect(within(rec).getByText("not").tagName).toBe("STRONG");
});

test("the lead's disagreement with the agent stays orange on the recommendation's line", async () => {
  serve([], undefined, [], [closed(1, "reject", { note: "", note_body: "", recommendation: given("reject", true, "w1") })]);
  open();
  const card = await gateCard();
  fireEvent.click(gateHead(card));
  const summary = card.querySelector("details.gate-row summary")!;
  expect(summary.textContent).toBe("Supervisorrecommended Reject · you agreed · disagreed with w1");
  expect(summary.querySelector(".rec-closed-differs")?.textContent).toBe(" · disagreed with w1");
});

test("a gate with no note and no recommendation opens to its question and answer only", async () => {
  serve([], undefined, [], [closed(1, "approve", { note: "", note_body: "", comment: "" })]);
  open();
  const card = await gateCard();
  fireEvent.click(gateHead(card));
  expect(within(card).getByText("Ship it?")).toBeTruthy();
  expect(card.querySelector(".question-answer")).toBeTruthy();
  expect(card.querySelectorAll("details")).toHaveLength(0);
  // Without its move in the feed: the answer's word, neutral, and no target.
  expect([card.querySelector(".gate-head .run-outcome")?.className, kept(card, "answer-target")]).toEqual(["run-outcome", undefined]);
});

test("gates are in time order among messages and run events; the gate's line stands under the move that led to it", async () => {
  serve(
    [message(1, "human", "supervisor", "start it", { created_at: "2026-10-03T12:00:00Z" })],
    undefined,
    [
      event(5, "flow", "build -done-> check", "2026-10-03T12:00:00.100Z"),
      // The gate's event and the gate are written in one transaction: the same moment.
      event(6, "gate_open", "#1 approval at check: Ship it?", "2026-10-03T12:00:02Z", { actor: "lado" }),
      event(7, "gate_answer", "#1 approve", "2026-10-03T12:00:03Z"),
      event(8, "flow_end", "at end", "2026-10-03T12:00:04Z"),
    ],
    [gate(1, { created_at: "2026-10-03T12:00:02Z" })],
  );
  open();
  const log = await chat();
  await gateLine();
  const order = Array.from(log.querySelectorAll(":scope > article, :scope > .run-group li")).map(
    (one) => one.getAttribute("aria-label") ?? one.querySelector(".run-chip, .run-outcome")?.textContent,
  );
  expect(order).toEqual(["Message from you", "done", "Gate #1 waits", "ended"]);
});

test("a gate shows once, in its own row: its opening is no line, open or answered", async () => {
  const at = "2026-10-03T12:05:00.123Z";
  serve(
    [],
    undefined,
    [
      event(4, "flow", "build -ready-> check", "2026-10-03T12:00:00.250Z"),
      event(5, "gate_open", "#1 approval at check: Ship it?", "2026-10-03T12:00:00.250Z", { actor: "lado" }),
      event(6, "gate_answer", "#1 approve", at, { actor: "human" }),
      event(7, "flow", "check -approved-> ship", at, { actor: "human" }),
      event(8, "flow", "ship -ready-> check", "2026-10-03T12:06:00Z", { actor: "w1" }),
      event(9, "gate_open", "#2 approval at check: Ship it again?", "2026-10-03T12:06:00Z", { actor: "lado" }),
    ],
    [closed(1, "approve", { answered_at: at, closed_by_event: 7 }), gate(2, { question: "Ship it again?", created_at: "2026-10-03T12:06:00Z" })],
    [flowRun("feature/x", GATED)],
  );
  open();
  const log = await chat();
  await gateCard();
  await gateLine(2);
  expect(log.querySelector("li.run-gate_open")).toBeNull();
  expect(within(log).queryByText(/waits for you|approval at check/)).toBeNull();
  // Each gate's row right after the group whose last line is the move that led to it.
  const rows = Array.from(log.querySelectorAll(":scope > article, :scope > .run-group")).map((one) =>
    one.tagName === "ARTICLE"
      ? one.getAttribute("aria-label")
      : Array.from(one.querySelectorAll("li")).map((line) => kept(line as HTMLElement, "run-outcome")),
  );
  expect(rows).toEqual([["ready"], "Gate #1", ["approved", "ready"], "Gate #2 waits"]);
  // The question only in the open gate's row.
  expect(log.textContent?.split("Ship it again?")).toHaveLength(2);
});

// The human's answer to a gate is the run's move from "You", the comment under it.

const moves = async () => within(await chat()).findAllByRole("listitem");

test("the human's answer to a gate is one line, the run's move from You with the comment under it; the gate's line stays", async () => {
  const at = "2026-10-03T12:05:00.123Z";
  serve(
    [
      message(1, "supervisor", "human", "working on it", { created_at: "2026-10-03T12:03:00Z" }),
      message(2, "supervisor", "human", "done", { created_at: "2026-10-03T12:07:00Z" }),
    ],
    undefined,
    [event(5, "flow", "check -approved-> ship", at, { actor: "human" }), event(6, "gate_answer", "#1 approve: ship it", at, { actor: "human" })],
    [closed(1, "approve", { comment: "ship **it**\nnow", created_at: "2026-10-03T12:01:00Z", answered_at: at, closed_by_event: 5 })],
  );
  open();
  const log = await chat();
  const [move] = await moves();
  expect([kept(move, "run-actor"), kept(move, "run-outcome")]).toEqual(["You", "approved"]);
  expect(move.querySelector(".avatar")?.textContent).toBe("Y");
  const comment = move.querySelector(".run-comment")!;
  expect(within(comment as HTMLElement).getByText("it").tagName).toBe("STRONG");
  expect(comment.querySelectorAll("br")).toHaveLength(1); // the human's line breaks, as typed
  const order = Array.from(log.querySelectorAll(":scope > article, :scope > .run-group li")).map(
    (one) => one.getAttribute("aria-label") ?? kept(one as HTMLElement, "run-actor"),
  );
  expect(order).toEqual(["Gate #1", "Message from supervisor", "You", "Message from supervisor"]);
  expect(within(log).getAllByRole("listitem")).toHaveLength(1); // no second row of the answer
  expect(within(log).queryByRole("article", { name: /Your answer to gate/ })).toBeNull();
});

test("a move of the human without its gate in the feed is the move alone; another's move has no comment", async () => {
  serve([], undefined, [
    event(5, "flow", "check -approved-> ship", "2026-10-03T12:05:00Z", { actor: "human" }),
    event(6, "flow", "ship -done-> end", "2026-10-03T12:05:01Z", { actor: "w1" }),
  ], [closed(1, "approve", { comment: "elsewhere", run: "fix/y", answered_at: "2026-10-03T12:05:00Z" })]);
  open();
  const [mine, theirs] = await moves();
  expect(kept(mine, "run-actor")).toBe("You");
  expect(mine.querySelector(".run-comment")).toBeNull();
  expect(theirs.querySelector(".run-comment")).toBeNull();
});

// The files of the human's answers (docs/design/ui.md, Answer in the question card; Flow
// gates): uploads of the session's scope, an image previewed, every file a chip.
const uploads = (...names: string[]): AttachmentInfo[] =>
  names.map((name) => ({
    artifact: `a-${name}`,
    record: `r-${name}`,
    full_name: name,
    name,
    scope: "",
    title: null,
    media_type: name.endsWith(".png") ? "image/png" : "text/plain",
    size: 1200,
    hash: "h",
  }));
const shown = (where: Element) => ({
  images: where.querySelectorAll(".chat-image").length,
  chips: Array.from(where.querySelectorAll(".chip .chip-name")).map((one) => one.textContent),
});

test("an answer's files show in its question's card, previews and chips; its late line counts them", async () => {
  serve(
    [
      question(5, { question_state: "answered", answered_by: 7 }),
      message(6, "supervisor", "human", "in between"),
      message(7, "human", "w1", "Answer to #5: see these", { reply_to: 5, attachments: uploads("shot-1a2b3c4d.png", "server-1a2b3c4d.log") }),
    ].map((one, i) => ({ ...one, created_at: `2026-10-03T12:0${i}:00.000Z` })),
  );
  open();
  const log = await chat();
  const card = await within(log).findByRole("article", { name: "Question from w1" });
  const given = card.querySelector(".question-answer")!;
  expect(given.querySelector(".chat-body")?.textContent).toBe("see these");
  expect(shown(given)).toEqual({ images: 1, chips: ["shot-1a2b3c4d.png", "server-1a2b3c4d.log"] });
  const late = within(log).getByRole("article", { name: "You answered question #5" });
  expect(late.querySelector(".late-text")?.textContent).toMatch(/· see these · 2 files$/);
});

test("an own answer of files only shows them alone in the card; a skip's files show under its comment", async () => {
  serve([
    question(5, { question_state: "answered", answered_by: 6 }),
    message(6, "human", "w1", "Answer to #5: 1 file: shot-1a2b3c4d.png", { reply_to: 5, attachments: uploads("shot-1a2b3c4d.png") }),
    question(7, { question_state: "dismissed", answered_by: 8 }),
    message(8, "human", "w1", "Dismissed #7", { reply_to: 7, body: "later", attachments: uploads("notes-1a2b3c4d.log") }),
  ]);
  open();
  const [own, skipped] = await within(await chat()).findAllByRole("article", { name: "Question from w1" });
  expect(own.querySelector(".question-answer .chat-body")).toBeNull();
  expect(shown(own.querySelector(".question-answer")!)).toEqual({ images: 1, chips: ["shot-1a2b3c4d.png"] });
  expect(skipped.querySelector(".question-answer .chat-body")?.textContent).toBe("later");
  expect(shown(skipped.querySelector(".question-answer")!)).toEqual({ images: 0, chips: ["notes-1a2b3c4d.log"] });
});

test("an answer and a skip to questions not in the window show their files", async () => {
  serve(
    [
      message(13, "human", "w1", "Answer to #10: 1 file: shot-1a2b3c4d.png", { reply_to: 10, attachments: uploads("shot-1a2b3c4d.png") }),
      message(14, "human", "w1", "Dismissed #11", { reply_to: 11, attachments: uploads("notes-1a2b3c4d.log") }),
    ].map((one, i) => ({ ...one, created_at: `2026-10-03T12:00:0${i}.000Z` })),
  );
  open();
  const log = await chat();
  const row = await within(log).findByRole("article", { name: "Message from you" });
  expect(row.querySelector(".chat-answer")).toBeNull();
  expect(shown(row)).toEqual({ images: 1, chips: ["shot-1a2b3c4d.png"] });
  expect(shown(within(log).getByRole("article", { name: "You skipped question #11" }))).toEqual({ images: 0, chips: ["notes-1a2b3c4d.log"] });
});

test("a gate's answer with files: previews and chips under the move after the comment; the opened card chips only, the folded one none", async () => {
  rejected({ answer_attachments: uploads("shot-1a2b3c4d.png", "server-1a2b3c4d.log") });
  const card = await gateCard();
  await waitFor(async () => expect((await moves()).some((one) => one.querySelector(".run-comment"))).toBe(true));
  const move = (await moves()).find((one) => kept(one, "run-actor") === "You")!;
  const comment = move.querySelector(".run-comment")!;
  expect(comment.textContent).toContain("split the form first");
  expect(shown(comment)).toEqual({ images: 1, chips: ["shot-1a2b3c4d.png", "server-1a2b3c4d.log"] });
  expect(shown(card)).toEqual({ images: 0, chips: [] });
  fireEvent.click(gateHead(card));
  expect(shown(card.querySelector(".gate-closed-card .question-answer")!)).toEqual({
    images: 0,
    chips: ["shot-1a2b3c4d.png", "server-1a2b3c4d.log"],
  });
});

test("a gate answered with files only shows them under the move", async () => {
  rejected({ comment: "", answer_attachments: uploads("server-1a2b3c4d.log") });
  await gateCard();
  await waitFor(async () => expect((await moves()).some((one) => one.querySelector(".run-comment"))).toBe(true));
  const move = (await moves()).find((one) => kept(one, "run-actor") === "You")!;
  expect(shown(move.querySelector(".run-comment")!)).toEqual({ images: 0, chips: ["server-1a2b3c4d.log"] });
  expect(move.querySelector(".run-comment .chat-body")).toBeNull();
});

test("answering a gate on the open page puts the move at the bottom and scrolls to it", async () => {
  serve([message(1, "supervisor", "human", "later", { created_at: "2026-10-03T12:02:00Z" })], undefined, [], [gate(1)]);
  open();
  const feed = await chat();
  await gateLine();
  let height = 700;
  Object.defineProperty(feed, "scrollHeight", { configurable: true, get: () => height });
  feed.scrollTop = 700; // the human reads at the bottom
  fireEvent.scroll(feed);
  const at = "2026-10-03T12:09:00Z";
  stream().send("change", gateChanged(closed(1, "reject", { answered_at: at })), "11");
  height = 900;
  const moved = event(5, "flow", "check -rejected-> build", at, { actor: "human" });
  stream().send("change", { kind: "events", session: "lado", key: "5", op: "insert", item: moved }, "12");
  const [move] = await moves();
  expect(kept(move, "run-actor")).toBe("You");
  expect(feed.lastElementChild?.contains(move)).toBe(true);
  expect(feed.scrollTop).toBe(900);
});

test("while a gate is open, no hint stands over the composer; the line's arrow shows its tab; the composer does not answer it", async () => {
  const { posted } = serve([question(5, { created_at: "2026-10-03T12:00:00.000Z" })], undefined, [], [closed(1, "approve"), gate(2)]);
  const scrolled = vi.fn();
  Element.prototype.scrollIntoView = scrolled;
  open();
  const line = await gateLine(2);
  const card = await waitingCard();
  expect(screen.queryByText(/answer on its card/)).toBeNull();
  expect(document.querySelector(".gate-hint")).toBeNull();
  expect(within(card).getByRole("tab", { name: "w1 1" }).getAttribute("aria-selected")).toBe("true");
  scrolled.mockClear(); // the terminal panel scrolls its tabs too
  fireEvent.click(within(line).getByRole("button", { name: "Answer gate #2" }));
  await waitFor(() => expect(within(card).getByRole("tab", { name: "feature/x 1" }).getAttribute("aria-selected")).toBe("true"));
  const panel = card.querySelector('[data-item="2"]') as HTMLElement;
  expect(panel.className).toContain("marked");
  // The gate's item into the list's view; its tab scrolls only the tabs' row, sideways.
  expect(scrolled.mock.contexts).toEqual([panel]);
  const field = screen.getByRole("textbox", { name: "Write to the supervisor…" });
  fireEvent.change(field, { target: { value: "approve" } });
  fireEvent.keyDown(field, { key: "Enter" });
  await waitFor(() => expect(posted).toEqual([{ path: "/api/sessions/lado/messages", body: { text: "approve" } }]));
  expect(within(card).getByRole("tab", { name: "feature/x 1" })).toBeTruthy(); // still open
});

test("in a stopped session the card keeps its gate, its buttons off, and says why", async () => {
  serve([], undefined, [], [gate(1)]);
  open("/sessions/old/activity");
  const card = within(await waitingCard("old")).getByRole("tabpanel");
  expect((within(card).getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(true);
  expect(within(card).getByText("The session is stopped: resume it to answer.")).toBeTruthy();
});

// The lead's recommendation (LAD-27): one entry with the gate or the question.

const given = (choice: string | null, disagrees = false, by = "w1") => ({
  state: "given" as const,
  text: "I would **not** ship it.",
  choice,
  disagrees,
  by,
  at: "2026-10-03T12:01:00.000Z",
});
const asked = { state: "asked" as const, text: "", choice: null, disagrees: false, by: "w1", at: null };

// A gate's buttons in its tab's Send row, with their classes.
const buttons = (card: HTMLElement) =>
  within(card)
    .getAllByRole("button")
    .filter((one) => one.closest(".waiting-send"))
    .map((one) => `${one.textContent}:${one.className}`);
// A question's choices in its tab, with whether each is picked.
const picked = (item: HTMLElement) =>
  within(item)
    .getAllByRole("button")
    .filter((one) => !one.classList.contains("other"))
    .map((one) => `${one.textContent}:${one.getAttribute("aria-pressed")}`);

test("a gate's recommendation is a block in its tab; the primary button moves to the recommended option", async () => {
  serve([], undefined, [], [gate(1, { recommendation: asked })]);
  open();
  const card = await gateTab();
  expect(within(card).getByText("Supervisor is preparing a recommendation…")).toBeTruthy();
  expect(buttons(card)).toEqual(["Approve:primary", "Reject:quiet"]);
  expect((within(card).getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(false);
  stream().send("change", gateChanged(gate(1, { recommendation: given("reject", true) })), "11");
  const block = await within(card).findByRole("region", { name: "Supervisor's recommendation" });
  expect(block.querySelector(".rec-differs")?.textContent).toBe("disagrees with w1");
  expect(within(block).getByText("not").tagName).toBe("STRONG");
  expect(buttons(card)).toEqual(["Approve:quiet", "Reject:primary"]);
  // Between the note and the answer.
  const order = Array.from(card.querySelectorAll(".gate-note, .rec, form.answer")).map((one) => one.className);
  expect(order).toEqual(["gate-note", "rec differs", "answer"]);
});

test("a stopped session's gate keeps its buttons off and shows the recommendation", async () => {
  serve([], undefined, [], [gate(1, { recommendation: given("reject") })]);
  open("/sessions/old/activity");
  const card = within(await waitingCard("old")).getByRole("tabpanel");
  expect(within(card).getByRole("region", { name: "Supervisor's recommendation" })).toBeTruthy();
  const reject = within(card).getByRole("button", { name: "Reject" }) as HTMLButtonElement;
  expect([reject.disabled, reject.className]).toEqual([true, "primary"]);
});

test("a question's recommended choice is picked ahead in its tab; closed, its quiet line names it and the choice stays marked once", async () => {
  serve([question(5, { recommendation: given("later") })]);
  open();
  const item = within(await waitingCard()).getByRole("listitem", { name: "Question #5" });
  expect(within(item).getByRole("region", { name: "Supervisor's recommendation" })).toBeTruthy();
  expect(picked(item)).toEqual(["yes:false", "later:true"]);
  const done = { question_state: "answered" as const, answered_by: 6, recommendation: given("later") };
  stream().send("change", changed(question(5, done)), "11");
  stream().send("change", changed(message(6, "human", "w1", "Answer to #5: later", { reply_to: 5, choice: "later" })), "12");
  const feed = await chat();
  await waitFor(() => expect(feed.querySelector("details.rec-closed")).toBeTruthy());
  const card = within(feed).getByRole("article", { name: "Question from w1" });
  expect(card.querySelector("details.rec-closed summary")?.textContent).toBe("SSupervisor recommended: later");
  expect(Array.from(card.querySelectorAll(".choices.closed li")).map((one) => one.textContent)).toEqual(["yes", "✓ later"]);
  expect(card.querySelector(".question-answer")?.textContent).not.toContain("later");
});

test("a question with no recommendation asked shows no block and picks nothing", async () => {
  serve([question(5)]);
  open();
  const item = within(await waitingCard()).getByRole("listitem", { name: "Question #5" });
  expect(item.querySelector(".rec")).toBeNull();
  expect(picked(item)).toEqual(["yes:false", "later:false"]);
});

// Links from Needs you and from a notification

test("a link to an old open question waits for what waits to load and loads no page for its line", async () => {
  const { queries } = serve([question(5, { created_at: "2026-10-02T09:00:00.000Z" }), ...history(70, 10)]);
  let release = () => {};
  const held = new Promise<void>((resolve) => (release = resolve));
  const plain = globalThis.fetch;
  vi.stubGlobal("fetch", async (path: string, init?: RequestInit) => {
    if (path === "/api/waiting") await held;
    return plain(path, init);
  });
  open("/sessions/lado/activity#message-5");
  await within(await chat()).findByText("note 79");
  release();
  const card = await waitingCard();
  await waitFor(() => expect(card.querySelector('[data-item="5"]')?.className).toContain("marked"));
  expect(queries).toEqual([{ with: "human", limit: "50" }]);
});

test.each([
  ["#message-5", "w1 1", "5"],
  ["#gate-1", "feature/x 1", "1"],
])("an address with an open item's anchor %s shows its tab and marks it, and scrolls the feed nowhere", async (anchor, tab, item) => {
  const scrolled: Element[] = [];
  Element.prototype.scrollIntoView = function (this: Element) {
    scrolled.push(this);
  };
  serve([question(5, { created_at: "2026-10-03T12:00:00.000Z" })], undefined, [], [gate(1, { created_at: "2026-10-03T12:00:01.000Z" })]);
  open(`/sessions/lado/activity${anchor}`);
  const card = await waitingCard();
  await waitFor(() => expect(within(card).getByRole("tab", { name: tab }).getAttribute("aria-selected")).toBe("true"));
  const marked = card.querySelector(`[data-item="${item}"]`) as HTMLElement;
  await waitFor(() => expect(marked.className).toContain("marked"));
  expect(scrolled.filter((one) => one.closest(".chat-feed"))).toEqual([]);
});

test("an address with a closed card's anchor scrolls to it once the feed is loaded, after the scroll to the latest", async () => {
  const order: string[] = [];
  Element.prototype.scrollIntoView = function (this: Element) {
    order.push(this.id || this.className);
  };
  serve(
    [
      question(5, { question_state: "closed" }),
      ...Array.from({ length: 30 }, (_, i) => message(10 + i, "supervisor", "human", `note ${i}`)),
    ],
    undefined,
    [],
    [closed(1, "approve")],
  );
  open("/sessions/lado/activity#message-5");
  const card = await within(await chat()).findByRole("article", { name: "Question from w1" });
  await waitFor(() => expect(order).toContain("message-5"));
  expect(card.id).toBe("message-5");
  cleanup();
  order.length = 0;
  open("/sessions/lado/activity#gate-1");
  await gateCard(1);
  await waitFor(() => expect(order).toContain("gate-1"));
  // A later message scrolls to the latest as before.
  const feed = await chat();
  Object.defineProperty(feed, "scrollHeight", { value: 900 });
  stream().send("change", changed(message(99, "supervisor", "human", "newer", { created_at: "2026-10-03T12:01:00Z" })), "11");
  await within(feed).findByText("newer");
  expect(feed.scrollTop).toBe(900);
});

test("a question to the human shows while the agents' messages are hidden", async () => {
  serve([question(5), message(6, "w1", "supervisor", "between agents")]);
  open();
  const log = await chat();
  expect(await within(log).findByRole("article", { name: "Question from w1" })).toBeTruthy();
  expect(within(log).queryByText("between agents")).toBeNull();
});

// Pages: the chat opens with the latest messages and loads earlier ones when the human
// scrolls to the top.

// Messages 1..n to and from the human, one a minute from 2 Oct 10:00 UTC on.
const history = (n: number, first = 1) =>
  Array.from({ length: n }, (_, i) =>
    message(first + i, i % 2 ? "supervisor" : "human", i % 2 ? "human" : "supervisor", `note ${first + i}`, {
      created_at: new Date(Date.UTC(2026, 9, 2, 10, i)).toISOString(),
    }),
  );

// The start of the session over history(): its first message's day as the chat writes it,
// in the zone and locale the tests run in ("2 Oct", "Oct 2", "2 окт.").
const historyStart = () => `Start of session lado · ${day(history(1)[0].created_at)}`;

// The feed's height grows with what it shows: 100 pixels for each message.
function measured(feed: HTMLElement) {
  Object.defineProperty(feed, "scrollHeight", {
    configurable: true,
    get: () => 100 * feed.querySelectorAll("article").length,
  });
}

test("the chat opens with one page of the human's messages, the latest ones, at the bottom", async () => {
  const { queries } = serve([...history(70), message(71, "w1", "supervisor", "between agents")]);
  open();
  const log = await chat();
  await within(log).findByText("note 70");
  expect(queries).toEqual([{ with: "human", limit: "50" }]);
  expect(within(log).getAllByRole("article")).toHaveLength(50);
  expect(within(log).queryByText("note 20")).toBeNull();
  expect(within(log).queryByText(/Start of session/)).toBeNull();
});

test("at the top the chat loads the earlier page and keeps what the human sees in place", async () => {
  const { queries, fetch } = serve(history(70));
  open();
  const log = await chat();
  await within(log).findByText("note 70");
  measured(log);
  log.scrollTop = 0;
  fireEvent.scroll(log);
  let release = () => {};
  const held = new Promise<void>((resolve) => (release = resolve));
  const plain = fetch.getMockImplementation()!;
  fetch.mockImplementation(async (path: string, init?: RequestInit) => {
    await held;
    return plain(path, init);
  });
  FakeIntersectionObserver.show();
  // The feed's own status, not a Copy message's.
  const loading = () => within(log).queryAllByRole("status").filter((one) => !one.closest(".copy-button"));
  expect(loading().map((one) => one.textContent)).toEqual(["Loading earlier messages…"]);
  FakeIntersectionObserver.show(); // one load at a time
  release();
  await within(log).findByText("note 1");
  expect(queries.slice(1)).toEqual([{ with: "human", limit: "50", before: "21" }]);
  expect(log.scrollTop).toBe(2000); // 20 messages above the one that was at the top
  expect(loading()).toEqual([]);
  expect(within(log).getByText(historyStart())).toBeTruthy();
});

test("a new message scrolls to it only when the human was at the bottom", async () => {
  serve(history(10));
  open();
  const log = await chat();
  await within(log).findByText("note 10");
  measured(log);
  expect(within(log).getByText(historyStart())).toBeTruthy();
  stream().send("change", changed(message(11, "supervisor", "human", "newer")), "11");
  await within(log).findByText("newer");
  expect(log.scrollTop).toBe(1100);
  log.scrollTop = 300; // the human scrolled up to read
  fireEvent.scroll(log);
  stream().send("change", changed(message(12, "supervisor", "human", "newest")), "12");
  await within(log).findByText("newest");
  expect(log.scrollTop).toBe(300);
});

test("earlier messages that cannot load say why and load again on Retry", async () => {
  const { fetch, queries } = serve(history(70));
  open();
  const log = await chat();
  await within(log).findByText("note 70");
  const plain = fetch.getMockImplementation()!;
  fetch.mockImplementation(async (path: string, init?: RequestInit) =>
    path.includes("before=")
      ? new Response(JSON.stringify({ detail: "lado.db is newer" }), { status: 503 })
      : plain(path, init),
  );
  FakeIntersectionObserver.show();
  const problem = await within(log).findByRole("alert");
  expect(problem.textContent).toContain("lado.db is newer");
  fetch.mockImplementation(plain);
  fireEvent.click(within(problem).getByRole("button", { name: "Retry" }));
  await within(log).findByText("note 1");
  expect(queries.filter((one) => one.before)).toHaveLength(1);
});

test("gates and run events before the first loaded message wait until the messages before them are loaded", async () => {
  const old = new Date(Date.UTC(2026, 9, 2, 10, 5, 30)).toISOString();
  serve(
    history(70),
    undefined,
    [event(5, "flow_start", "at design", old)],
    [closed(1, "approve", { created_at: old, answered_at: old })],
  );
  open();
  const log = await chat();
  await within(log).findByText("note 70");
  expect(within(log).queryByRole("article", { name: "Gate #1" })).toBeNull();
  expect(within(log).queryByText(/at design/)).toBeNull();
  FakeIntersectionObserver.show();
  await within(log).findByText("note 1");
  expect(within(log).getByRole("article", { name: "Gate #1" })).toBeTruthy();
  expect(within(log).getByText(/at design/)).toBeTruthy();
});

test("a link to a message or a gate before the window loads up to it in one request and scrolls there", async () => {
  const scrolled: string[] = [];
  Element.prototype.scrollIntoView = function (this: Element) {
    scrolled.push(this.id);
  };
  const old = new Date(Date.UTC(2026, 9, 2, 10, 3, 30)).toISOString();
  const { queries } = serve([...history(70), question(80, { created_at: "2026-10-02T12:00:00.000Z" })], undefined, [], [
    closed(1, "approve", { created_at: old }),
  ]);
  open("/sessions/lado/activity#message-12");
  const log = await chat();
  await within(log).findByText("note 12");
  await waitFor(() => expect(scrolled).toContain("message-12"));
  expect(queries).toEqual([
    { with: "human", limit: "50" },
    { with: "human", after: "11", before: "22" },
  ]);
  expect(within(log).queryByText("note 11")).toBeNull();
  cleanup();
  scrolled.length = 0;
  const again = serve([...history(70), question(80, { created_at: "2026-10-02T12:00:00.000Z" })], undefined, [], [
    closed(1, "approve", { created_at: old }),
  ]);
  open("/sessions/lado/activity#gate-1");
  await gateCard(1);
  await waitFor(() => expect(scrolled).toContain("gate-1"));
  expect(again.queries).toEqual([
    { with: "human", limit: "50" },
    { with: "human", since: old, before: "22" },
  ]);
});

test("a link to a message that is not in the chat loads once and scrolls nowhere", async () => {
  const scrolled = vi.fn();
  Element.prototype.scrollIntoView = scrolled;
  const { queries } = serve([message(3, "w1", "supervisor", "between agents"), ...history(60, 10)]);
  open("/sessions/lado/activity#message-3");
  const log = await chat();
  await within(log).findByText("note 69");
  await waitFor(() => expect(queries).toHaveLength(2));
  // Only the terminal panel scrolls its tab into view.
  expect(scrolled.mock.contexts.filter((one) => log.contains(one as Node))).toEqual([]);
});

// The selection bar's areas (docs/design/ui.md, Selected text and copy buttons).
const area = (element: Element | null | undefined) => {
  const found = element?.closest<HTMLElement>("[data-quote]");
  return found && [found.dataset.quote, found.dataset.quoteSession];
};

test("each message, run event, closed gate and open gate's text is a text area of its session", async () => {
  serve(
    [message(1, "supervisor", "human", "merged w1", { body: "All checks pass." })],
    undefined,
    [event(5, "flow_start", "a", "2026-10-03T12:00:00Z")],
    [closed(1, "approve", { comment: "ship it" }), gate(2)],
  );
  open();
  const log = await chat();
  const said = await within(log).findByText("All checks pass.");
  expect(area(said)).toEqual(["text", "lado"]);
  expect(said.closest("[data-quote]")?.classList.contains("feed-main")).toBe(true);
  expect(area(await within(log).findByText("a"))).toEqual(["text", "lado"]);
  const card = await gateCard();
  fireEvent.click(within(card).getByRole("button", { name: /^Gate #1 · / }));
  expect(area(within(card).getByText("ship it"))).toEqual(["text", "lado"]);
  expect(area(within(await gateTab()).getByText("Ship it?"))).toEqual(["text", "lado"]);
  expect(area(within(await gateTab()).getByRole("textbox"))).toBeNull(); // the comment is no area
  expect(area(screen.getByRole("textbox", { name: "Write to the supervisor…" }))).toBeFalsy();
});
