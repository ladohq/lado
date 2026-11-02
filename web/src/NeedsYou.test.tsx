// Needs you (docs/design/ui.md, Structure): what waits for the human in every session not
// stopped, by session, answered in place; the count on the rail and in the tab's title.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { AgentInfo, GateInfo, MessageInfo, SessionInfo, WaitingItem } from "./api";
import { App } from "./App";
import { clock } from "./ChatText";
import { AGENT_REST, artifact, attachment, FakeEventSource, FakeNotification, FakeSocket, setVisible, stream } from "./fakes";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const SINCE = "2026-10-03T12:00:00.000Z";

function session(name: string, waiting = { gates: 0, questions: 0, agents: 0 }, more: Partial<SessionInfo> = {}) {
  const settings = { kits: ["default"], provider: "claude", permission_mode: null, without: [] };
  const time = { ran_seconds: 0, running_since: null, stopped_at: null, busy: 0, title: null };
  return { name, repo: `/src/${name}`, status: "running", agents: 2, waiting, ...settings, ...time, ...more } as SessionInfo;
}

function gate(id: number, more: Partial<GateInfo> = {}): GateInfo {
  return {
    id,
    run: "feature/x",
    state: "design_ok",
    kind: "approval",
    question: "Approve the design?",
    options: ["approve", "reject"],
    note: "design ready",
    note_body: "",
    attachments: [],
    reads: [],
    answer: null,
    comment: "",
    answered_by: null,
    created_at: SINCE,
    answered_at: null,
    closed_by_event: null,
    answer_attachments: [],
    problem: null,
    recommendation: null,
    ...more,
  };
}

function question(id: number, more: Partial<MessageInfo> = {}): MessageInfo {
  return {
    id,
    from: "w1",
    to: "human",
    kind: "question",
    summary: "Merge w1 now?",
    body: "",
    state: "delivered",
    choices: ["yes", "later"],
    free_answer: true,
    question_state: "open",
    answered_by: null,
    reply_to: null,
    choice: null,
    reply_state: null,
    attachments: [],
    created_at: SINCE,
    recommendation: null,
    ...more,
  };
}

function agent(name: string, reason: string | null = null): AgentInfo {
  return {
    name,
    role: "developer",
    provider: "claude",
    status: "waiting",
    run: null,
    task: null,
    status_reason: reason,
    ...AGENT_REST,
  };
}

const waits = {
  gate: (sess: string, one: GateInfo): WaitingItem => ({
    session: sess,
    kind: "gate",
    key: `gate:${one.id}`,
    since: one.created_at,
    gate: one,
    question: null,
    agent: null,
  }),
  question: (sess: string, one: MessageInfo): WaitingItem => ({
    session: sess,
    kind: "question",
    key: `question:${one.id}`,
    since: one.created_at,
    gate: null,
    question: one,
    agent: null,
  }),
  agent: (sess: string, one: AgentInfo, since = SINCE): WaitingItem => ({
    session: sess,
    kind: "agent",
    key: `agent:${sess}/${one.name}@${since}`,
    since,
    gate: null,
    question: null,
    agent: one,
  }),
};

let sessions: SessionInfo[] = [];
let waiting: WaitingItem[] = [];
let agents: AgentInfo[] = [];
let posted: { path: string; body: unknown }[] = [];

beforeEach(() => {
  localStorage.clear();
  sessions = [session("lado"), session("api")];
  waiting = [];
  agents = [];
  posted = [];
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        posted.push({ path, body: init.body ? JSON.parse(String(init.body)) : undefined });
        return new Response(JSON.stringify({ result: "answered" }));
      }
      if (path === "/api/sessions") return new Response(JSON.stringify(sessions));
      if (path === "/api/waiting") return new Response(JSON.stringify(waiting));
      if (path.endsWith("/agents")) return new Response(JSON.stringify(agents));
      if (path.endsWith("/about")) return new Response("{}", { status: 404 }); // the head without its about
      if (path.includes("/messages?")) return new Response(JSON.stringify({ items: [], earlier: false }));
      if (path.endsWith("/content")) return new Response("# Design");
      if (path.includes("/records/")) return new Response(JSON.stringify({ artifact: artifact(), record: artifact().latest }));
      return new Response("[]");
    }),
  );
  FakeEventSource.all = [];
  FakeEventSource.autoStart = true;
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("WebSocket", FakeSocket);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function Where() {
  const { pathname, search, hash } = useLocation();
  return <output aria-label="Address">{pathname + search + hash}</output>;
}

function open(path = "/needs-you") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
      <Where />
    </MemoryRouter>,
  );
}

const address = () => screen.getByRole("status", { name: "Address" }).textContent;
const group = (name: string) => screen.findByRole("region", { name: `Session ${name}` });

const card = (session: string) => screen.findByRole("region", { name: `What waits for you in ${session}` });

test("what waits shows by session: its name, In the chat, its waiting card, then its waiting agents", async () => {
  waiting = [
    waits.gate("lado", gate(1)),
    waits.question("api", question(5)),
    waits.question("lado", question(6, { from: "supervisor", created_at: "2026-10-03T12:00:01.000Z" })),
    waits.agent("lado", agent("w2", "did not take 1 message: answer the dialog in its window")),
    waits.agent("lado", agent("w3")),
  ];
  open();
  const lado = await group("lado");
  const api = await group("api");
  expect(within(lado).getByRole("link", { name: "lado" }).getAttribute("href")).toBe("/sessions/lado/activity");
  expect(within(lado).getByRole("link", { name: "lado's chat" }).textContent).toBe("In the chat");
  expect(within(api).getByRole("link", { name: "api's chat" }).getAttribute("href")).toBe("/sessions/api/activity");
  // One card per session, each with its own tabs: lado's gate first (asked first), then
  // its supervisor's question; api's question.
  const ladoCard = await card("lado");
  expect(lado.contains(ladoCard)).toBe(true);
  const tabs = within(ladoCard).getAllByRole("tab");
  expect(tabs).toEqual([
    within(ladoCard).getByRole("tab", { name: "feature/x 1" }),
    within(ladoCard).getByRole("tab", { name: "supervisor 1" }),
  ]);
  expect(within(within(ladoCard).getByRole("tabpanel")).getByText("Approve the design?")).toBeTruthy();
  const apiCard = await card("api");
  expect(within(apiCard).getAllByRole("tab").map((one) => one.getAttribute("aria-selected"))).toEqual(["true"]);
  expect(within(apiCard).getByText("Merge w1 now?")).toBeTruthy();
  // Agents waiting in their terminal stay rows, after the card.
  const head = (row: HTMLElement) =>
    ["feed-who", "feed-aside"].map((one) => row.querySelector(`.feed-head .${one}`)?.textContent);
  const w2 = within(lado).getByRole("article", { name: "w2 waits" });
  expect(ladoCard.compareDocumentPosition(w2) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(head(w2)).toEqual(["w2", "developer · waiting since"]);
  expect(w2.querySelector(".feed-head time")?.textContent).toBe(clock(SINCE));
  expect(within(w2).getByText("did not take 1 message: answer the dialog in its window")).toBeTruthy();
  const w3 = within(lado).getByRole("article", { name: "w3 waits" });
  expect(within(w3).getByText("waits for you in its terminal")).toBeTruthy();
  expect(within(w2).queryByRole("link")).toBeNull();
});

test("Needs you shows a card minimized in its chat whole, with no minimize icon and no edge", async () => {
  localStorage.setItem("lado.waitingMinimized.lado", JSON.stringify(["gate:1"]));
  waiting = [waits.gate("lado", gate(1))];
  open();
  const lado = await card("lado");
  expect(lado.classList.contains("minimized")).toBe(false);
  expect(within(lado).getByRole("tabpanel")).toBeTruthy();
  expect(within(lado).queryByRole("button", { name: /^(Minimize|Restore) the card$/ })).toBeNull();
  expect(within(lado).queryByRole("separator")).toBeNull();
});

test("a titled session's line shows its title, then its name in grey; the links keep the name", async () => {
  sessions = [session("lado", undefined, { title: "Ревью kit-sdlc" }), session("api")];
  waiting = [waits.gate("lado", gate(1)), waits.question("api", question(5))];
  open();
  const lado = await group("lado");
  const title = within(lado).getByRole("link", { name: "Ревью kit-sdlc" });
  expect(title.getAttribute("href")).toBe("/sessions/lado/activity");
  expect(lado.querySelector("h2 .session-name-id")!.textContent).toBe("lado");
  expect(within(lado).getByRole("link", { name: "lado's chat" })).toBeTruthy();
  const api = await group("api");
  expect(within(api).getByRole("link", { name: "api" })).toBeTruthy();
  expect(api.querySelector(".session-name-id")).toBeNull();
});

test("a gate and a question are answered in place, each to its session; an answered one goes when the feed says so", async () => {
  waiting = [waits.gate("lado", gate(1)), waits.question("lado", question(5)), waits.question("api", question(7))];
  open();
  const lado = await card("lado");
  fireEvent.change(within(lado).getByRole("textbox", { name: "Comment for the next step (optional)" }), {
    target: { value: "fine" },
  });
  fireEvent.click(within(lado).getByRole("button", { name: "Approve" }));
  fireEvent.click(within(lado).getByRole("tab", { name: "w1 1" }));
  fireEvent.click(within(lado).getByRole("button", { name: "yes" }));
  fireEvent.click(within(lado).getByRole("button", { name: "Send answer to w1" }));
  const api = await card("api");
  fireEvent.click(within(api).getByRole("button", { name: "later" }));
  fireEvent.click(within(api).getByRole("button", { name: "Send answer to w1" }));
  await waitFor(() =>
    expect(posted).toEqual([
      { path: "/api/sessions/lado/gates/1/answer", body: { option: "approve", comment: "fine" } },
      { path: "/api/sessions/lado/answers", body: { answers: [{ question: 5, choice: "yes", skip: false }] } },
      { path: "/api/sessions/api/answers", body: { answers: [{ question: 7, choice: "later", skip: false }] } },
    ]),
  );
  waiting = [waits.question("lado", question(5))];
  stream().send("change", { kind: "gates", session: "lado", key: "1", op: "update", item: gate(1, { answer: "approved" }) }, "11");
  await waitFor(() => expect(screen.queryByRole("tab", { name: "feature/x 1" })).toBeNull());
  waiting = [];
  stream().send("change", { kind: "messages", session: "lado", key: "5", op: "update", item: null }, "12");
  expect(await screen.findByText("Nothing waits for you")).toBeTruthy();
});

test("a chip opens the artifact panel over Needs you, which stays with its pick; × closes it", async () => {
  waiting = [waits.question("lado", question(5, { attachments: [attachment()] })), waits.question("api", question(7))];
  open();
  const lado = await card("lado");
  fireEvent.click(within(lado).getByRole("button", { name: "later" }));
  fireEvent.click(within(lado).getByRole("button", { name: "Open artifact feature/x/design" }));
  await waitFor(() => expect(address()).toBe("/needs-you?view=r1&session=lado"));
  const panel = await screen.findByRole("dialog", { name: "Artifact feature/x/design" });
  expect(await within(panel).findByRole("link", { name: "Open in Artifacts tab" })).toBeTruthy();
  // Needs you is still there under it, the pick as it was.
  expect(within(await card("lado")).getByRole("button", { name: "later" }).getAttribute("aria-pressed")).toBe("true");
  expect(await card("api")).toBeTruthy();
  fireEvent.click(within(panel).getByRole("button", { name: "Close" }));
  await waitFor(() => expect(address()).toBe("/needs-you"));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(within(await card("lado")).getByRole("button", { name: "later" }).getAttribute("aria-pressed")).toBe("true");
});

test("Open terminal goes to the agent's terminal in its session, and the address keeps no ?terminal=", async () => {
  agents = [agent("w2")];
  waiting = [waits.agent("lado", agent("w2"))];
  open();
  fireEvent.click(within(await group("lado")).getByRole("button", { name: "Open w2's terminal" }));
  const tab = await screen.findByRole("tab", { name: /^w2,/ });
  await waitFor(() => expect(tab.getAttribute("aria-selected")).toBe("true"));
  await waitFor(() => expect(address()).toBe("/sessions/lado/activity"));
});

test("an agent that waits for its CLI's login offers Log in…, which leads to Settings' section", async () => {
  const reason =
    "Claude Code is not logged in: log in in Settings → Providers and environment, or set CLAUDE_CODE_OAUTH_TOKEN; the agent starts by itself once you do";
  const waits_ = { ...agent("supervisor", reason), login_wait: "claude" };
  waiting = [waits.agent("lado", waits_)];
  open();
  const lado = await group("lado");
  expect(within(lado).getByText(reason)).toBeTruthy();
  const logIn = within(lado).getByRole("button", { name: "Log in for supervisor" });
  expect(logIn.className).toBe("primary");
  expect(within(lado).getByRole("button", { name: "Open supervisor's terminal" }).className).toBe("quiet");
  fireEvent.click(logIn);
  await waitFor(() => expect(address()).toBe("/settings#providers-and-environment"));
});

test("an agent that waits for anything else offers no Log in…", async () => {
  waiting = [waits.agent("lado", agent("w2", "did not take 2 messages"))];
  open();
  const lado = await group("lado");
  expect(within(lado).queryByRole("button", { name: /^Log in/ })).toBeNull();
});

test("with nothing waiting the page says so", async () => {
  open();
  expect(await screen.findByText("Nothing waits for you")).toBeTruthy();
});

test("a list that cannot load says why", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) =>
      path === "/api/waiting"
        ? new Response(JSON.stringify({ detail: "lado.db is newer" }), { status: 503 })
        : path.endsWith("/about")
          ? new Response("{}", { status: 404 })
        : new Response(JSON.stringify(path === "/api/sessions" ? sessions : [])),
    ),
  );
  open();
  expect((await screen.findByText("lado.db is newer")).getAttribute("role")).toBe("alert");
});

// The count

const rail = () => screen.getByRole("navigation", { name: "Sections" });

test("the rail counts what waits in the sessions not stopped, also collapsed, and the tab's title says it", async () => {
  sessions = [
    session("lado", { gates: 1, questions: 1, agents: 0 }),
    session("api", { gates: 0, questions: 0, agents: 1 }, { status: "tmux_gone" }),
    session("old", { gates: 4, questions: 0, agents: 0 }, { status: "stopped" }),
  ];
  open("/sessions");
  const link = await within(rail()).findByRole("link", { name: "Needs you, 3 waiting" });
  expect(within(link).getByText("3")).toBeTruthy();
  await waitFor(() => expect(document.title).toBe("(3) Sessions · LADO"));
  fireEvent.click(within(rail()).getByRole("button", { name: "Collapse menu" }));
  expect(within(rail()).getByRole("link", { name: "Needs you, 3 waiting" })).toBeTruthy();
  stream().send(
    "change",
    { kind: "sessions", session: "lado", key: "lado", op: "update", item: session("lado") },
    "11",
  );
  await within(rail()).findByRole("link", { name: "Needs you, 1 waiting" });
  stream().send(
    "change",
    { kind: "sessions", session: "api", key: "api", op: "update", item: session("api") },
    "12",
  );
  const quiet = await within(rail()).findByRole("link", { name: "Needs you" });
  expect(quiet.textContent).toBe("Needs you");
  await waitFor(() => expect(document.title).toBe("Sessions · LADO"));
});

// Browser notifications

const waitingAsked = () =>
  vi.mocked(fetch).mock.calls.filter(([path]) => path === "/api/waiting").length;

// Something changed in a session: the store loads what waits again.
async function changeWaiting(items: WaitingItem[], id: string) {
  const before = waitingAsked();
  waiting = items;
  stream().send("change", { kind: "gates", session: "lado", key: "1", op: "update", item: null }, id);
  await waitFor(() => expect(waitingAsked()).toBeGreaterThan(before));
}

function notificationsOn() {
  localStorage.setItem("lado.notifications", "on");
  FakeNotification.permission = "granted";
}

const shown = () => FakeNotification.all.map((one) => [one.title, one.options.body, one.options.tag, one.options.silent]);

describe("notifications", () => {
  beforeEach(() => {
    FakeNotification.reset();
    vi.stubGlobal("Notification", FakeNotification);
    vi.stubGlobal("isSecureContext", true);
    vi.stubGlobal("focus", vi.fn());
    setVisible(false);
  });

  afterEach(() => setVisible(true));

  test("are off by default: nothing is asked, loaded or shown", async () => {
    open("/sessions");
    await within(rail()).findByRole("link", { name: "Needs you" });
    stream().send("change", { kind: "gates", session: "lado", key: "1", op: "update", item: null }, "11");
    expect(waitingAsked()).toBe(0);
    expect(FakeNotification.asked).toBe(0);
    expect(FakeNotification.all).toEqual([]);
  });

  test("Enable notifications on Needs you asks the browser and turns them on when allowed", async () => {
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Enable notifications" }));
    expect(await screen.findByText(/Browser notifications are on/)).toBeTruthy();
    expect(FakeNotification.asked).toBe(1);
    expect(localStorage.getItem("lado.notifications")).toBe("on");
  });

  test("a browser that blocks them, has none or is not on a secure page is explained", async () => {
    FakeNotification.answer = "denied";
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Enable notifications" }));
    expect(await screen.findByText(/The browser blocks notifications for this page/)).toBeTruthy();
    expect(localStorage.getItem("lado.notifications")).toBeNull();
    cleanup();
    vi.stubGlobal("isSecureContext", false);
    open();
    expect(await screen.findByText(/only on a secure page/)).toBeTruthy();
    cleanup();
    vi.stubGlobal("Notification", undefined);
    open();
    expect(await screen.findByText("This browser cannot show notifications.")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Enable notifications" }) as HTMLButtonElement).disabled).toBe(true);
  });

  test("turned on, but the browser's permission reset to ask, says to allow them again, not that it blocks them", async () => {
    localStorage.setItem("lado.notifications", "on");
    FakeNotification.permission = "default";
    open();
    expect(await screen.findByText(/The browser asks again before it shows notifications/)).toBeTruthy();
    expect(screen.queryByText(/blocks notifications/)).toBeNull();
    FakeNotification.permission = "denied";
    cleanup();
    open();
    expect(await screen.findByText(/The browser blocks notifications for this page/)).toBeTruthy();
  });

  test("each new item shows one silent notification, tagged by its key; what waited at the start does not", async () => {
    notificationsOn();
    waiting = [waits.gate("lado", gate(1))];
    open("/sessions");
    await waitFor(() => expect(waitingAsked()).toBe(1));
    await changeWaiting([waits.gate("lado", gate(1)), waits.question("api", question(5))], "11");
    await waitFor(() => expect(shown()).toEqual([["LADO · api", "Merge w1 now?", "question:5", true]]));
    // One in place of another: the same count, a new item.
    await changeWaiting([waits.gate("lado", gate(1)), waits.agent("lado", agent("w2"))], "12");
    await waitFor(() => expect(shown()).toHaveLength(2));
    expect(shown()[1]).toEqual(["LADO · lado", "w2 waits for you in its terminal", "agent:lado/w2@" + SINCE, true]);
    await changeWaiting([waits.agent("lado", agent("w3", "did not take 1 message"))], "13");
    await waitFor(() => expect(shown()).toHaveLength(3));
    expect(shown()[2][1]).toBe("w3 waits: did not take 1 message");
  });

  test("a notification names the session by its title, else by its name", async () => {
    notificationsOn();
    sessions = [session("lado", undefined, { title: "Review" }), session("api")];
    open("/sessions");
    await waitFor(() => expect(waitingAsked()).toBe(1));
    await changeWaiting([waits.gate("lado", gate(1)), waits.question("api", question(5))], "11");
    await waitFor(() => expect(shown()).toHaveLength(2));
    expect(shown().map((one) => one[0])).toEqual(["LADO · Review", "LADO · api"]);
  });

  test("nothing shows while the tab is on the screen, and what came then is not shown later", async () => {
    notificationsOn();
    open("/sessions");
    await waitFor(() => expect(waitingAsked()).toBe(1));
    setVisible(true);
    await changeWaiting([waits.gate("lado", gate(1))], "11");
    setVisible(false);
    await changeWaiting([waits.gate("lado", gate(1)), waits.gate("lado", gate(2, { question: "Ship?" }))], "12");
    await waitFor(() => expect(shown()).toEqual([["LADO · lado", "Ship?", "gate:2", true]]));
  });

  test("what came while the feed was down shows after its reset", async () => {
    notificationsOn();
    open("/sessions");
    await waitFor(() => expect(waitingAsked()).toBe(1));
    waiting = [waits.gate("lado", gate(1))];
    stream().send("reset", {}, "30");
    await waitFor(() => expect(shown()).toEqual([["LADO · lado", "Approve the design?", "gate:1", true]]));
  });

  test("a click focuses the tab and goes to the item; an item that goes closes its notification", async () => {
    notificationsOn();
    open("/sessions");
    await waitFor(() => expect(waitingAsked()).toBe(1));
    await changeWaiting([waits.gate("lado", gate(1)), waits.question("lado", question(5))], "11");
    await waitFor(() => expect(FakeNotification.all).toHaveLength(2));
    const [first, second] = FakeNotification.all;
    first.click();
    expect(window.focus).toHaveBeenCalled();
    expect(first.closed).toBe(true);
    await waitFor(() => expect(address()).toBe("/sessions/lado/activity#gate-1"));
    await changeWaiting([], "12");
    await waitFor(() => expect(second.closed).toBe(true));
  });

  test("Settings turns them on, asking the browser first, and off", async () => {
    open("/settings");
    const toggle = (await screen.findByRole("checkbox", { name: "Browser notifications" })) as HTMLInputElement;
    expect(toggle.checked).toBe(false);
    fireEvent.click(toggle);
    await waitFor(() => expect(toggle.checked).toBe(true));
    expect(FakeNotification.asked).toBe(1);
    expect(localStorage.getItem("lado.notifications")).toBe("on");
    await waitFor(() => expect(waitingAsked()).toBe(1)); // the notifier follows what waits
    fireEvent.click(toggle);
    await waitFor(() => expect(toggle.checked).toBe(false));
    expect(localStorage.getItem("lado.notifications")).toBe("off");
    FakeNotification.answer = "denied";
    FakeNotification.permission = "default";
    fireEvent.click(toggle);
    expect(await screen.findByText(/The browser blocks notifications for this page/)).toBeTruthy();
    expect(toggle.checked).toBe(false);
  });
});
