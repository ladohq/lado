// The chat in a session's Activity tab: the messages with the human and the agents'
// questions, live from the feed; the composer and the answers go to the API.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { MessageInfo, RunEventInfo, SessionInfo } from "./api";
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
