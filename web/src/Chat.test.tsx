// The chat in a session's Activity tab: the messages with the human and the agents'
// questions, live from the feed; the composer and the answers go to the API.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { GateInfo, MessageInfo, RunEventInfo, SessionInfo } from "./api";
import { App } from "./App";
import { FakeEventSource, FakeSocket, stream } from "./fakes";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const SESSIONS: SessionInfo[] = [
  { name: "lado", repo: "/src/lado", status: "running", agents: 2, waiting: { gates: 0, questions: 0, agents: 0 } },
  { name: "old", repo: "/src/old", status: "stopped", agents: 0, waiting: { gates: 0, questions: 0, agents: 0 } },
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
    created_at: "2026-10-03T12:00:00.000Z",
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

function event(id: number, kind: string, detail: string, created_at = "2026-10-03T12:00:00.500Z"): RunEventInfo {
  return { id, run: "feature/x", kind, actor: "w1", detail, created_at };
}

type Posted = { path: string; body: unknown };

// The API: the sessions, a session's messages (`chat`) and run events (`events`), and the
// POSTs, which answer `answer`.
function serve(
  chat: MessageInfo[],
  answer: { status: number; body: unknown } = { status: 200, body: { result: "sent" } },
  events: RunEventInfo[] = [],
  gates: GateInfo[] = [],
) {
  const posted: Posted[] = [];
  const fetch = vi.fn(async (path: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      posted.push({ path, body: init.body ? JSON.parse(String(init.body)) : undefined });
      return new Response(JSON.stringify(answer.body), { status: answer.status });
    }
    if (path === "/api/sessions") return new Response(JSON.stringify(SESSIONS));
    if (path.startsWith("/api/sessions/") && path.endsWith("/messages")) {
      return new Response(JSON.stringify(chat));
    }
    if (path.startsWith("/api/sessions/") && path.endsWith("/events")) {
      return new Response(JSON.stringify(events));
    }
    if (path.startsWith("/api/sessions/") && path.endsWith("/gates")) {
      return new Response(JSON.stringify(gates));
    }
    if (path.endsWith("/agents")) return new Response("[]");
    return new Response("{}", { status: 404 });
  });
  vi.stubGlobal("fetch", fetch);
  return { fetch, posted };
}

function open(path = "/sessions/lado/activity") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

const chat = () => screen.findByRole("log", { name: "Chat with the session" });

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
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("the chat shows who wrote each message, its summary and its body as Markdown without HTML", async () => {
  serve([
    message(1, "human", "supervisor", "merge w1, please"),
    message(2, "supervisor", "human", "merged w1", { body: "**All** checks pass.\n\n<img src=x onerror=alert(1)>" }),
  ]);
  open();
  const log = await chat();
  const [mine, reply] = await within(log).findAllByRole("article");
  expect(within(mine).getByText("you")).toBeTruthy();
  expect(within(mine).getByText("to supervisor")).toBeTruthy();
  expect(within(mine).getByText("merge w1, please")).toBeTruthy();
  expect(within(reply).getByText("supervisor")).toBeTruthy();
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
  expect(articles.map((one) => within(one).getAllByRole("heading")[0].textContent)).toEqual(["merge w1", "merged"]);
  expect(within(articles[0]).getByText(/replied only in its terminal/)).toBeTruthy();
});

test("a question is answered with a choice; the card waits for the feed to say so", async () => {
  const { posted } = serve([question(5)]);
  open();
  const card = await within(await chat()).findByRole("article", { name: "Question from w1" });
  expect(within(card).getByText("Tests pass.")).toBeTruthy();
  fireEvent.click(within(card).getByRole("button", { name: "yes" }));
  await waitFor(() => expect(posted).toEqual([{ path: "/api/sessions/lado/questions/5/answer", body: { choice: "yes" } }]));
  expect(within(card).getByRole("button", { name: "yes" })).toBeTruthy(); // not shown as answered yet
  stream().send("change", changed(question(5, { question_state: "answered", answered_by: 6 })), "11");
  stream().send("change", changed(message(6, "human", "w1", "Answer to #5: yes", { reply_to: 5, choice: "yes" })), "12");
  const answered = within(await chat()).getByRole("article", { name: "Question from w1" });
  expect(within(answered).queryByRole("button")).toBeNull();
  expect(within(answered).getByText("Answered: yes")).toBeTruthy();
});

test("a question takes an own answer, or is dismissed", async () => {
  const { posted } = serve([question(5), question(7, { choices: null })]);
  open();
  const [first, second] = within(await chat()).getAllByRole("article", { name: "Question from w1" });
  fireEvent.change(within(first).getByRole("textbox", { name: "Your answer" }), { target: { value: "after the release" } });
  fireEvent.click(within(first).getByRole("button", { name: "Submit" }));
  fireEvent.click(within(second).getByRole("button", { name: "Dismiss" }));
  await waitFor(() => expect(posted).toHaveLength(2));
  expect(posted).toEqual([
    { path: "/api/sessions/lado/questions/5/answer", body: { text: "after the release" } },
    { path: "/api/sessions/lado/questions/7/dismiss", body: undefined },
  ]);
});

test("a choice takes what the human wrote in the field along as a comment", async () => {
  const { posted } = serve([question(5)]);
  open();
  const card = await within(await chat()).findByRole("article", { name: "Question from w1" });
  fireEvent.change(within(card).getByRole("textbox", { name: "Your answer" }), { target: { value: "after the tag" } });
  fireEvent.click(within(card).getByRole("button", { name: "later" }));
  await waitFor(() =>
    expect(posted).toEqual([
      { path: "/api/sessions/lado/questions/5/answer", body: { choice: "later", text: "after the tag" } },
    ]),
  );
});

test("a question with only choices has no field for an own answer", async () => {
  serve([question(5, { free_answer: false })]);
  open();
  const card = await within(await chat()).findByRole("article", { name: "Question from w1" });
  expect(within(card).queryByRole("textbox")).toBeNull();
  expect(within(card).queryByRole("button", { name: "Submit" })).toBeNull();
});

test.each([
  [{ question_state: "dismissed" as const }, "Dismissed"],
  [{ question_state: "closed" as const }, "Question closed: the agent left"],
  [{ question_state: "answered" as const, answered_by: 9 }, "Answered"],
])("a question no longer open says what became of it", async (state, outcome) => {
  serve([question(5, state)]);
  open();
  const card = await within(await chat()).findByRole("article", { name: "Question from w1" });
  expect(within(card).getByText(outcome)).toBeTruthy();
  expect(within(card).queryByRole("button")).toBeNull();
});

test("an answer the server refuses says why on the card", async () => {
  serve([question(5)], { status: 400, body: { detail: "question #5 is closed" } });
  open();
  const card = await within(await chat()).findByRole("article", { name: "Question from w1" });
  fireEvent.click(within(card).getByRole("button", { name: "later" }));
  expect((await within(card).findByRole("alert")).textContent).toBe("question #5 is closed");
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
      path === `/api/sessions/lado/${list}`
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

const headings = (log: HTMLElement) =>
  within(log)
    .getAllByRole("article")
    .map((one) => within(one).getAllByRole("heading")[0].textContent);

test("a body to the human shows its first lines at once; a long one has Show all", async () => {
  const lines = Array.from({ length: 12 }, (_, i) => `line ${i + 1}`).join("\n\n");
  serve([message(2, "supervisor", "human", "report", { body: lines })]);
  open();
  const card = await within(await chat()).findByRole("article");
  expect(within(card).getByText("line 1")).toBeTruthy();
  expect(within(card).getByText("line 8")).toBeTruthy();
  expect(within(card).queryByText("line 9")).toBeNull();
  fireEvent.click(within(card).getByRole("button", { name: "Show all" }));
  expect(within(card).getByText("line 12")).toBeTruthy();
  fireEvent.click(within(card).getByRole("button", { name: "Show less" }));
  expect(within(card).queryByText("line 12")).toBeNull();
});

test("a short body to the human has no Show all", async () => {
  serve([message(2, "supervisor", "human", "report", { body: "one line" })]);
  open();
  const card = await within(await chat()).findByRole("article");
  expect(within(card).getByText("one line")).toBeTruthy();
  expect(within(card).queryByRole("button", { name: "Show all" })).toBeNull();
});

test("the agents' messages to each other show behind a switch that only changes the view and is remembered", async () => {
  const { fetch } = serve([
    message(1, "human", "supervisor", "merge w1"),
    message(2, "supervisor", "w1", "please merge", { body: "details" }),
    message(3, "supervisor", "human", "merged"),
  ]);
  open();
  const log = await chat();
  await within(log).findByText("merged");
  expect(headings(log)).toEqual(["merge w1", "merged"]);
  const loads = () => fetch.mock.calls.filter(([path]) => String(path).includes("/messages")).length;
  const before = loads();
  const toggle = screen.getByRole("checkbox", { name: "Show agent messages" });
  expect((toggle as HTMLInputElement).checked).toBe(false);
  fireEvent.click(toggle);
  expect(headings(log)).toEqual(["merge w1", "please merge", "merged"]);
  const between = within(log).getByRole("article", { name: "Message from supervisor to w1" });
  expect(within(between).getByText("to w1")).toBeTruthy();
  expect(loads()).toBe(before); // one list in the store: the switch loads nothing
  stream().send("change", changed(message(4, "w1", "supervisor", "done")), "11");
  expect(headings(log)).toContain("done");
  cleanup();
  open();
  const again = await chat();
  await within(again).findByText("please merge");
  expect((screen.getByRole("checkbox", { name: "Show agent messages" }) as HTMLInputElement).checked).toBe(true);
});

test("run events show as lines in time order, linking to Flows; a kind not listed as a line does not", async () => {
  serve(
    [message(1, "human", "supervisor", "start it", { created_at: "2026-10-03T12:00:00Z" })],
    undefined,
    [
      event(5, "flow_start", "at design", "2026-10-03T11:59:00.000Z"),
      event(6, "flow", "design -done-> review", "2026-10-03T12:00:01.000Z"),
      event(7, "something_else", "not a line", "2026-10-03T12:00:02.000Z"),
    ],
  );
  open();
  const log = await chat();
  const lines = await within(log).findAllByRole("listitem");
  expect(lines.map((line) => line.textContent)).toEqual([
    expect.stringContaining("feature/x: at design"),
    expect.stringContaining("feature/x: design -done-> review"),
  ]);
  const order = Array.from(log.querySelectorAll("li, article")).map((one) => one.tagName);
  expect(order).toEqual(["LI", "ARTICLE", "LI"]);
  expect(within(lines[1]).getByRole("link", { name: "Flows" }).getAttribute("href")).toBe("/sessions/lado/flows");
  expect(within(log).queryByText(/not a line/)).toBeNull();
  stream().send(
    "change",
    { kind: "events", session: "lado", key: "8", op: "insert", item: event(8, "flow_end", "at done", "2026-10-03T12:01:00.000Z") },
    "11",
  );
  expect(within(log).getAllByRole("listitem").at(-1)!.textContent).toContain("feature/x: at done");
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
    needs: [
      {
        state: "design",
        note: { id: 3, state: "design", summary: "the plan", body: "step one", created_at: "2026-10-03T11:00:00Z" },
      },
      { state: "polish", note: null },
    ],
    answer: null,
    comment: "",
    answered_by: null,
    created_at: "2026-10-03T12:00:00.250Z",
    answered_at: null,
    ...more,
  };
}

const closed = (id: number, answer: string, more: Partial<GateInfo> = {}) =>
  gate(id, { answer, answered_by: "human", answered_at: "2026-10-03T12:05:00Z", needs: null, ...more });

const gateCard = async (id = 1) => within(await chat()).findByRole("article", { name: `Gate #${id}` });

function gateChanged(item: GateInfo) {
  return { kind: "gates", session: "lado", key: String(item.id), op: "update", item };
}

test("an open gate is a card: its question, the note that led to it and the notes it needs", async () => {
  serve([], undefined, [], [gate(1)]);
  open();
  const card = await gateCard();
  expect(within(card).getByRole("heading", { name: "Gate #1 · feature/x · check" })).toBeTruthy();
  expect(within(card).getByText("Ship it?")).toBeTruthy();
  expect(within(card).getByText("built it").tagName).toBe("STRONG");
  expect(within(card).getByText("tests").tagName).toBe("STRONG"); // the body, open, as Markdown
  const design = within(card).getByRole("button", { name: "Note from design: the plan" });
  expect(design.getAttribute("aria-expanded")).toBe("false");
  expect(within(card).queryByText("step one")).toBeNull();
  fireEvent.click(design);
  expect(within(card).getByText("step one")).toBeTruthy();
  expect(within(card).getByText("Note from polish: no note yet")).toBeTruthy();
  expect(within(card).getByRole("textbox", { name: "Comment for the next step (optional)" })).toBeTruthy();
});

test("a long note before the gate is behind Show all", async () => {
  const body = Array.from({ length: 30 }, (_, i) => `line ${i + 1}`).join("\n\n");
  serve([], undefined, [], [gate(1, { note_body: body })]);
  open();
  const card = await gateCard();
  expect(within(card).getByText("line 20")).toBeTruthy();
  expect(within(card).queryByText("line 21")).toBeNull();
  fireEvent.click(within(card).getByRole("button", { name: "Show all" }));
  expect(within(card).getByText("line 30")).toBeTruthy();
});

test.each([
  [gate(1), ["Approve", "Reject"]],
  [gate(1, { kind: "choice", options: ["left", "right"] }), ["left", "right"]],
  [gate(1, { kind: "loop", options: ["continue", "cancel"], needs: [] }), ["Continue", "Cancel run"]],
])("a gate's buttons are its options", async (one, labels) => {
  serve([], undefined, [], [one]);
  open();
  const card = await gateCard();
  const buttons = within(card)
    .getAllByRole("button")
    .filter((button) => !button.hasAttribute("aria-expanded"));
  expect(buttons.map((button) => button.textContent)).toEqual(labels);
  expect(buttons[0].className).toContain("primary");
});

test("a gate is answered with an option and the comment; the card waits for the feed", async () => {
  const { posted } = serve([], undefined, [], [gate(1)]);
  let release = () => {};
  const held = new Promise<void>((resolve) => (release = resolve));
  const plain = globalThis.fetch;
  vi.stubGlobal("fetch", async (path: string, init?: RequestInit) => {
    if (init?.method === "POST") await held;
    return plain(path, init);
  });
  open();
  const card = await gateCard();
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
  stream().send("change", gateChanged(closed(1, "reject", { comment: "add a test\nfor the form" })), "11");
  const line = await gateCard();
  expect(within(line).queryByRole("button", { name: "Approve" })).toBeNull();
  expect(line.textContent).toContain("Gate #1 · feature/x · check: reject by human");
});

test("an answer the server refuses says why on the gate's card", async () => {
  serve([], { status: 400, body: { detail: "gate #1 is closed already: approve by human" } }, [], [gate(1)]);
  open();
  const card = await gateCard();
  fireEvent.click(within(card).getByRole("button", { name: "Approve" }));
  expect((await within(card).findByRole("alert")).textContent).toBe("gate #1 is closed already: approve by human");
  expect(within(card).getByRole("button", { name: "Approve" })).toBeTruthy();
});

test("a closed gate is a line with its answer and comment; it opens read only, without needs", async () => {
  serve([], undefined, [], [closed(1, "approve", { comment: "ship it" })]);
  open();
  const line = await gateCard();
  const toggle = within(line).getByRole("button", { name: /Gate #1 · feature\/x · check: approve by human/ });
  expect(line.textContent).toContain("ship it");
  expect(within(line).queryByText("Ship it?")).toBeNull();
  fireEvent.click(toggle);
  expect(within(line).getByText("Ship it?")).toBeTruthy();
  expect(within(line).getByText("built it")).toBeTruthy();
  expect(within(line).queryByText(/Note from/)).toBeNull();
  expect(within(line).queryByRole("textbox")).toBeNull();
  expect(within(line).getAllByRole("button")).toHaveLength(1);
});

test.each([
  [closed(1, "overridden", { comment: "built by hand" }), "check: overridden by human"],
  [closed(1, "cancelled", { answered_by: "supervisor", comment: "dropped" }), "check: cancelled by supervisor"],
])("a gate closed otherwise says how", async (one, text) => {
  serve([], undefined, [], [one]);
  open();
  expect((await gateCard()).textContent).toContain(text);
});

test("gates are in time order among messages and run events, and a gate's events are no lines", async () => {
  serve(
    [message(1, "human", "supervisor", "start it", { created_at: "2026-10-03T12:00:00Z" })],
    undefined,
    [
      event(5, "flow", "build -done-> check", "2026-10-03T12:00:00.100Z"),
      event(6, "gate_open", "#1 approval at check: Ship it?", "2026-10-03T12:00:00.250Z"),
      event(7, "gate_answer", "#1 approve", "2026-10-03T12:00:03Z"),
      event(8, "flow_end", "at end", "2026-10-03T12:00:04Z"),
    ],
    [gate(1, { created_at: "2026-10-03T12:00:02Z" })],
  );
  open();
  const log = await chat();
  await gateCard();
  const order = Array.from(log.querySelectorAll(":scope > article, :scope > ol > li")).map(
    (one) => one.getAttribute("aria-label") ?? one.textContent,
  );
  expect(order).toEqual([
    "Message from you",
    expect.stringContaining("build -done-> check"),
    "Gate #1",
    expect.stringContaining("at end"),
  ]);
});

test("while a gate is open, a hint over the composer leads to its card; the composer does not answer it", async () => {
  const { posted } = serve([], undefined, [], [closed(1, "approve"), gate(2)]);
  const scrolled = vi.fn();
  Element.prototype.scrollIntoView = scrolled;
  open();
  await gateCard(2);
  const hint = screen.getByText(/Gate #2 waits/);
  scrolled.mockClear(); // the terminal panel scrolls its tabs too
  fireEvent.click(within(hint).getByRole("button", { name: "answer on its card" }));
  expect(scrolled.mock.contexts).toEqual([await gateCard(2)]);
  const field = screen.getByRole("textbox", { name: "Write to the supervisor…" });
  fireEvent.change(field, { target: { value: "approve" } });
  fireEvent.keyDown(field, { key: "Enter" });
  await waitFor(() => expect(posted).toEqual([{ path: "/api/sessions/lado/messages", body: { text: "approve" } }]));
  stream().send("change", gateChanged(closed(2, "approve")), "11");
  await waitFor(() => expect(screen.queryByText(/waits: answer/)).toBeNull());
});

test("in a stopped session a gate's buttons are off and say why", async () => {
  serve([], undefined, [], [gate(1)]);
  open("/sessions/old/activity");
  const card = await gateCard();
  expect((within(card).getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(true);
  expect(within(card).getByText("The session is stopped: resume it to answer.")).toBeTruthy();
});

// Links from Needs you and from a notification

test("an address with a card's anchor scrolls to it once the feed is loaded, after the scroll to the latest", async () => {
  const order: string[] = [];
  Element.prototype.scrollIntoView = function (this: Element) {
    order.push(this.id || this.className);
  };
  serve(
    [question(5), ...Array.from({ length: 30 }, (_, i) => message(10 + i, "supervisor", "human", `note ${i}`))],
    undefined,
    [],
    [gate(1)],
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
  stream().send("change", changed(message(99, "supervisor", "human", "newer")), "11");
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
