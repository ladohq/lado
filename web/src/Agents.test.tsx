// The session's Agents tab: its live agents on the left, the supervisor first; an agent's page on the right with what it does, the state of its work, its
// messages and the actions on it, live from the feed.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type {
  AgentDetails,
  AgentInfo,
  FinishPreviewInfo,
  MessageInfo,
  RunInfo,
  SessionInfo,
} from "./api";
import { App } from "./App";
import { FakeEventSource, FakeSocket, narrowColumn, stream, stubDialogs, wideColumn } from "./fakes";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const NO_WAITS = { gates: 0, questions: 0, agents: 0 };
const SETTINGS = { kits: ["team"], provider: "claude", permission_mode: null, without: [] };
const SESSIONS: SessionInfo[] = [
  { name: "lado", repo: "/src/lado", status: "running", agents: 3, waiting: NO_WAITS, ...SETTINGS },
  { name: "old", repo: "/src/old", status: "stopped", agents: 0, waiting: NO_WAITS, ...SETTINGS },
];

function agent(name: string, more: Partial<AgentInfo> = {}): AgentInfo {
  return {
    name,
    role: name === "supervisor" ? "supervisor" : "developer",
    provider: "claude",
    status: "idle",
    run: null,
    task: name === "supervisor" ? null : `Task of ${name}`,
    waiting_reason: null,
    branch: name === "supervisor" ? null : `lado/lado/${name}`,
    worktree: name === "supervisor" ? null : `/src/lado/.lado/worktrees/lado/${name}`,
    spawned_at: "2026-10-04T10:40:00.000Z",
    since: "2026-10-04T10:50:00.000Z",
    ...more,
  };
}

const SUPERVISOR = agent("supervisor", { spawned_at: "2026-10-04T09:00:00.000Z" });
const DEVELOPER = agent("developer", {
  status: "busy",
  run: "feature/agents-tab",
  task: "Run feature/agents-tab (flow feature), step implement.",
  spawned_at: "2026-10-04T10:40:00.000Z",
});
const WAITING = agent("developer-2", {
  status: "waiting",
  waiting_reason: "did not take 2 messages\nWrite to it again or open its terminal",
  spawned_at: "2026-10-04T10:30:00.000Z",
});

const RUN = {
  name: "feature/agents-tab",
  flow: "feature",
  kit: { name: "lado-dev", version: "0.7.0", source: "project" },
  task: "Agents tab",
  state: "implement",
  status: "active",
  reason: "",
  acting: "developer",
  visits: { design: 1, implement: 2 },
  gate: null,
  worktree: "/w",
  branch: "lado/lado/feature-agents-tab",
  language: "ru",
  created_at: "2026-10-04T10:00:00.000Z",
  since: "2026-10-04T10:40:00.000Z",
  ended_at: null,
  states: [],
  problem: null,
} as RunInfo;

const WORK: AgentDetails = {
  task: "Run feature/agents-tab (flow feature), step implement.\nline 2\nline 3\nline 4\nline 5",
  work: {
    branch: "lado/lado/feature-agents-tab",
    base: "main",
    ahead: 3,
    behind: 0,
    uncommitted: 2,
    last_commit: { sha: "abc1234def", subject: "AgentInfo: run step and since", at: "2026-10-04T10:52:00.000Z" },
  },
  work_problem: null,
};

function message(id: number, from: string, to: string, at: string, more: Partial<MessageInfo> = {}): MessageInfo {
  return {
    id,
    from,
    to,
    kind: "message",
    summary: `message ${id}`,
    body: "",
    state: "read",
    choices: null,
    free_answer: true,
    question_state: null,
    answered_by: null,
    reply_to: null,
    choice: null,
    reply_state: null,
    created_at: at,
    ...more,
  } as MessageInfo;
}

type Data = {
  agents?: AgentInfo[];
  details?: Record<string, AgentDetails>;
  preview?: FinishPreviewInfo | { status: number; detail: string };
  messages?: MessageInfo[];
  runs?: RunInfo[];
  finish?: { status: number; body: unknown };
};
type Asked = { path: string; method: string; body: unknown };

let asked: Asked[] = [];

// The server's page of an agent's messages: from and to `agent`, made from the second of
// `since` to the end of the second of `until`, the latest `limit`.
function agentPage(all: MessageInfo[], query: URLSearchParams) {
  const agent = query.get("agent");
  const since = query.get("since");
  const until = query.get("until");
  const second = (time: string) => Math.floor(Date.parse(time) / 1000) * 1000;
  const taken = all.filter((one) => {
    const at = Date.parse(one.created_at);
    return (
      (agent === null || one.from === agent || one.to === agent) &&
      (since === null || at >= second(since)) &&
      (until === null || at < second(until) + 1000)
    );
  });
  const limit = Number(query.get("limit") ?? taken.length);
  return { items: taken.slice(-limit), earlier: taken.length > limit };
}

// The queries of the messages the page asked for.
const messageQueries = () =>
  asked
    .map((one) => new URL(one.path, "http://lado"))
    .filter((url) => url.pathname.endsWith("/messages"))
    .map((url) => Object.fromEntries(url.searchParams));

function serve(data: Data = {}) {
  const {
    agents = [SUPERVISOR, DEVELOPER, WAITING],
    details = {},
    messages = [],
    runs = [RUN],
  } = data;
  asked = [];
  const fetch = vi.fn(async (path: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    asked.push({ path, method, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    const of = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
    if (method === "POST" && path.endsWith("/finish")) {
      const answer = data.finish ?? { status: 200, body: { result: "Finished worker" } };
      return of(answer.body, answer.status);
    }
    if (method === "POST") return of({ result: "sent" });
    if (path === "/api/sessions") return of(SESSIONS);
    if (path.endsWith("/agents")) return of(path.includes("/old/") ? [] : agents);
    const detailsOf = path.match(/\/agents\/([^/]+)\/details$/);
    if (detailsOf) {
      const name = decodeURIComponent(detailsOf[1]);
      return of(details[name] ?? { task: null, work: null, work_problem: null });
    }
    if (path.endsWith("/finish-preview")) {
      const preview = data.preview ?? { removes_worktree: true, refused: null, work: WORK.work };
      return "status" in preview ? of({ detail: preview.detail }, preview.status) : of(preview);
    }
    const url = new URL(path, "http://lado");
    if (url.pathname.endsWith("/messages")) return of(agentPage(messages, url.searchParams));
    if (path.endsWith("/runs")) return of(runs);
    if (["/events", "/notes", "/gates"].some((end) => path.endsWith(end))) return of([]);
    if (path.includes("/history")) return of({ text: "", alternate: false });
    return of({}, 404);
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

// Where the page is now: the address without the host.
function Where() {
  const { pathname, search } = useLocation();
  return <output aria-label="Address">{pathname + search}</output>;
}

function open(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
      <Where />
    </MemoryRouter>,
  );
}

const address = () => screen.getByRole("status", { name: "Address" }).textContent;
const list = () => screen.findByRole("navigation", { name: "Agents" });
const page = (name: string) => screen.findByRole("region", { name: `Agent ${name}` });

beforeEach(() => {
  localStorage.clear();
  stubDialogs();
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
  wideColumn();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// The list

test("the supervisor comes first, then the agents by spawn; a waiting one is orange with why", async () => {
  serve();
  open("/sessions/lado/agents/developer");
  const nav = await list();
  const rows = within(nav).getAllByRole("link");
  expect(rows.map((one) => one.querySelector(".agent-row-name")?.textContent)).toEqual([
    "supervisor",
    "developer-2",
    "developer",
  ]);
  expect(rows[2].textContent).toContain("busy");
  expect(rows[2].textContent).toContain("feature/agents-tab · implement");
  expect(rows[2].getAttribute("aria-current")).toBe("page");
  expect(rows[1].className).toContain("waits");
  expect(rows[1].textContent).toContain("did not take 2 messages");
  expect(rows[1].textContent).not.toContain("Write to it again");
  expect(rows[0].textContent).toContain("idle");
  expect((await screen.findByRole("link", { name: "Agents · 3" })).getAttribute("aria-current")).toBe("page");
});

test("the list has the live agents only: no Finished group, nothing asked about finished agents", async () => {
  serve();
  open("/sessions/lado/agents/developer");
  const nav = await list();
  await within(nav).findAllByRole("link");
  expect(within(nav).getAllByRole("link")).toHaveLength(3);
  expect(within(nav).queryByRole("button")).toBeNull();
  expect(within(nav).queryByRole("region", { name: "Finished" })).toBeNull();
  expect(nav.textContent).not.toContain("Finished");
  expect(asked.filter((one) => one.path.includes("/agents/finished"))).toEqual([]);
});

test("the tab without an agent opens the supervisor, and an unknown one is not found", async () => {
  serve();
  open("/sessions/lado/agents");
  expect(await page("supervisor")).toBeTruthy();
  expect(address()).toBe("/sessions/lado/agents/supervisor");
  cleanup();
  serve();
  open("/sessions/lado/agents/ghost");
  expect(await screen.findByText("Agent ghost not found")).toBeTruthy();
  expect(address()).toBe("/sessions/lado/agents/ghost");
});

test("an agent that is not live is not found, also with the old ?finished= of a finished one", async () => {
  serve();
  open("/sessions/lado/agents/reviewer?finished=90");
  expect(await screen.findByText("Agent reviewer not found")).toBeTruthy();
  cleanup();
  serve();
  open("/sessions/lado/agents/developer?finished=70");
  expect(await page("developer")).toBeTruthy(); // the live one: the parameter means nothing
  const rows = within(await list()).getAllByRole("link");
  expect(rows.filter((one) => one.getAttribute("aria-current") === "page")).toHaveLength(1);
});

test("in a column narrower than 900 px the list takes it without an agent, an agent's page has the way back", async () => {
  narrowColumn();
  serve();
  open("/sessions/lado/agents");
  const nav = await list();
  expect(address()).toBe("/sessions/lado/agents");
  expect(screen.queryByRole("combobox")).toBeNull();
  expect(screen.queryByRole("region", { name: /^Agent / })).toBeNull();
  fireEvent.click(await within(nav).findByRole("link", { name: /developer-2/ }));
  expect(await page("developer-2")).toBeTruthy();
  expect(address()).toBe("/sessions/lado/agents/developer-2");
  expect(screen.queryByRole("navigation", { name: "Agents" })).toBeNull();
  fireEvent.click(screen.getByRole("link", { name: "‹ All agents" }));
  expect(address()).toBe("/sessions/lado/agents");
  expect(await list()).toBeTruthy();
});

test("the search finds a live agent by its name, role, task or run", async () => {
  serve();
  open("/sessions/lado/agents/supervisor");
  const nav = await list();
  await within(nav).findAllByRole("link");
  const search = screen.getByRole("searchbox", { name: "Find an agent" });
  const found = () => within(nav).getAllByRole("link").map((one) => one.querySelector(".agent-row-name")?.textContent);
  fireEvent.change(search, { target: { value: "AGENTS-TAB" } });
  expect(found()).toEqual(["developer"]);
  fireEvent.change(search, { target: { value: "nobody" } });
  expect(within(nav).getByText("No agent matches “nobody”")).toBeTruthy();
});

test("a stopped session's tab says Session stopped: no agents, and nothing else", async () => {
  serve();
  open("/sessions/old/agents");
  const tab = (await screen.findByText("Session stopped: no agents")).closest(".list-page")!;
  expect(address()).toBe("/sessions/old/agents");
  expect(tab.textContent).toBe("Session stopped: no agents");
  expect(screen.queryByRole("navigation", { name: "Agents" })).toBeNull();
  expect(within(tab as HTMLElement).queryByRole("searchbox")).toBeNull();
  cleanup();
  serve();
  open("/sessions/old/agents/reviewer");
  const named = (await screen.findByText("Session stopped: no agents")).closest(".list-page")!;
  expect(named.textContent).toBe("Session stopped: no agents");
});

// An agent's page

test("an agent's page has its head with the run and step, its branch, work, worktree and task", async () => {
  serve({ details: { developer: WORK } });
  open("/sessions/lado/agents/developer");
  const region = await page("developer");
  const head = within(region).getByRole("banner");
  expect(within(head).getByRole("heading", { name: "developer" })).toBeTruthy();
  expect(head.textContent).toContain("developer · claude");
  expect(head.textContent).toMatch(/busy for \d+ (min|h|d)/);
  expect(head.textContent).toContain("step implement (visit 2)");
  expect(within(head).getByRole("link", { name: "feature/agents-tab" }).getAttribute("href")).toBe(
    "/sessions/lado/flows/feature%2Fagents-tab",
  );
  const facts = region.querySelector("dl")!;
  expect(facts.textContent).toContain("lado/lado/developer");
  expect(facts.textContent).toContain("/src/lado/.lado/worktrees/lado/developer");
  expect(await within(region).findByText(/3 commits ahead of main · 0 behind · 2 files not committed/)).toBeTruthy();
  expect(facts.textContent).toContain("“AgentInfo: run step and since”");
  expect(facts.textContent).toMatch(/as of \d/);
  expect(within(region).queryByRole("note")).toBeNull();
});

test("the task shows its first lines with Show all", async () => {
  serve({ details: { developer: WORK } });
  open("/sessions/lado/agents/developer");
  const region = await page("developer");
  const task = await waitFor(() => {
    const found = region.querySelector(".agent-task");
    expect(found?.textContent).toContain("line 2");
    return found!;
  });
  expect(task.textContent).not.toContain("line 5");
  fireEvent.click(within(task as HTMLElement).getByRole("button", { name: "Show all" }));
  expect(task.textContent).toContain("line 5");
});

test("the work is asked again on Refresh and when the agent becomes idle, never by itself", async () => {
  serve({ details: { developer: WORK } });
  open("/sessions/lado/agents/developer");
  const region = await page("developer");
  await within(region).findByText(/3 commits ahead/);
  const asks = () => asked.filter((one) => one.path.endsWith("/developer/details")).length;
  expect(asks()).toBe(1);
  fireEvent.click(within(region).getByRole("button", { name: "Refresh" }));
  await waitFor(() => expect(asks()).toBe(2));
  stream().send("change", { kind: "agents", session: "lado", key: "developer", op: "update", item: { ...DEVELOPER, status: "waiting" } }, "11");
  await act(async () => {});
  expect(asks()).toBe(2);
  stream().send("change", { kind: "agents", session: "lado", key: "developer", op: "update", item: { ...DEVELOPER, status: "idle" } }, "12");
  await waitFor(() => expect(asks()).toBe(3));
});

test("work that git cannot tell is shown as the server says; the supervisor has no work at all", async () => {
  serve({ details: { developer: { task: "t", work: null, work_problem: "fatal: not a git repository" } } });
  open("/sessions/lado/agents/developer");
  const region = await page("developer");
  expect(await within(region).findByText(/fatal: not a git repository/)).toBeTruthy();
  cleanup();
  serve();
  open("/sessions/lado/agents/supervisor");
  const supervisor = await page("supervisor");
  expect(supervisor.textContent).not.toContain("Branch");
  expect(supervisor.textContent).not.toContain("Work");
  expect(within(supervisor).queryByRole("button", { name: /Finish/ })).toBeNull();
});

test("a waiting agent says why on its page", async () => {
  serve();
  open("/sessions/lado/agents/developer-2");
  const region = await page("developer-2");
  expect(within(region).getByRole("note").textContent).toBe(
    "did not take 2 messages\nWrite to it again or open its terminal",
  );
});

test("Write to the agent sends the human's text to it, and the supervisor's copy is told", async () => {
  serve();
  open("/sessions/lado/agents/developer");
  const region = await page("developer");
  const box = within(region).getByRole("textbox", { name: "Write to developer…" });
  fireEvent.click(within(region).getByRole("button", { name: "Write to developer" }));
  expect(document.activeElement).toBe(box);
  expect(within(region).getByText("The supervisor gets a one-line copy.")).toBeTruthy();
  fireEvent.change(box, { target: { value: "use port 8080" } });
  fireEvent.click(within(region).getByRole("button", { name: "Send" }));
  await waitFor(() =>
    expect(asked.find((one) => one.method === "POST")).toEqual({
      path: "/api/sessions/lado/messages",
      method: "POST",
      body: { to: "developer", text: "use port 8080" },
    }),
  );
});

test("Open terminal opens the agent's terminal in the panel", async () => {
  serve();
  open("/sessions/lado/agents/developer");
  const region = await page("developer");
  fireEvent.click(within(region).getByRole("button", { name: "Open terminal" }));
  const panel = screen.getByRole("complementary", { name: "Terminals" });
  expect(within(panel).getByRole("tab", { name: /developer/ }).getAttribute("aria-selected")).toBe("true");
});

// Messages

const MESSAGES = [
  message(1, "supervisor", "developer", "2026-10-04T08:10:00.000Z", { summary: "to the old developer" }),
  message(2, "developer", "supervisor", "2026-10-04T09:00:00.000Z", { summary: "the old developer reports" }),
  ...Array.from({ length: 11 }, (_, i) =>
    message(10 + i, i % 2 ? "developer" : "lado", i % 2 ? "reviewer" : "developer", `2026-10-04T10:${41 + i}:00.000Z`),
  ),
  message(30, "supervisor", "reviewer", "2026-10-04T10:59:00.000Z", { summary: "not about developer" }),
];

test("an agent's page has its latest 10 messages of its own lifetime, and All in Activity shows agent messages", async () => {
  serve({ messages: MESSAGES });
  open("/sessions/lado/agents/developer");
  const region = await page("developer");
  const box = within(region).getByRole("region", { name: "Messages" });
  const lines = await within(box).findAllByRole("listitem");
  expect(messageQueries()).toEqual([{ agent: "developer", since: "2026-10-04T10:40:00.000Z", limit: "10" }]);
  expect(lines).toHaveLength(10);
  expect(lines[0].textContent).toContain("message 11");
  expect(lines[9].textContent).toContain("message 20");
  expect(lines[0].textContent).toContain("developer → reviewer");
  expect(lines[1].textContent).toContain("lado → developer");
  expect(lines[1].textContent).toContain("· read");
  expect(box.textContent).not.toContain("old developer");
  expect(box.textContent).not.toContain("not about developer");
  fireEvent.click(within(box).getByRole("button", { name: "All in Activity" }));
  expect(address()).toBe("/sessions/lado/activity");
  expect(localStorage.getItem("lado.agentMessages")).toBe("shown");
  expect((screen.getByRole("checkbox", { name: "Show agent messages" }) as HTMLInputElement).checked).toBe(true);
});

test("a message from the feed keeps the page at the latest 10, the new one last", async () => {
  serve({ messages: MESSAGES });
  open("/sessions/lado/agents/developer");
  const box = within(await page("developer")).getByRole("region", { name: "Messages" });
  expect(await within(box).findAllByRole("listitem")).toHaveLength(10);
  const newer = message(40, "developer", "supervisor", "2026-10-04T11:00:00.000Z", { summary: "the newest" });
  stream().send("change", { kind: "messages", session: "lado", key: "40", op: "insert", item: newer }, "11");
  await within(box).findByText(/the newest/);
  const lines = within(box).getAllByRole("listitem");
  expect(lines).toHaveLength(10);
  expect(lines[9].textContent).toContain("the newest");
  expect(lines[0].textContent).toContain("message 12");
});

test("the supervisor's page has its messages, also one of the second it was spawned in", async () => {
  const spawned = "2026-10-04T09:00:00.000Z";
  serve({
    agents: [agent("supervisor", { spawned_at: "2026-10-04T15:04:49.286Z" }), DEVELOPER],
    messages: [
      message(1, "supervisor", "developer", spawned, { summary: "before its spawn" }),
      message(2, "lado", "supervisor", "2026-10-04T15:04:49.100Z", { summary: "its first input" }),
      message(3, "supervisor", "human", "2026-10-04T16:04:45.215Z", { summary: "a question" }),
    ],
  });
  open("/sessions/lado/agents/supervisor");
  const box = within(await page("supervisor")).getByRole("region", { name: "Messages" });
  const lines = await within(box).findAllByRole("listitem");
  expect(lines.map((one) => one.textContent)).toEqual([
    expect.stringContaining("its first input"),
    expect.stringContaining("a question"),
  ]);
});

test("an agent's messages say they load, and why they could not", async () => {
  const fetch = serve();
  const served = fetch.getMockImplementation()!;
  let release = () => {};
  const held = new Promise<void>((resolve) => (release = resolve));
  fetch.mockImplementation(async (path: string, init?: RequestInit) => {
    if (!path.includes("/messages?")) return served(path, init);
    await held;
    return new Response(JSON.stringify({ detail: "lado.db is newer" }), { status: 503 });
  });
  open("/sessions/lado/agents/developer");
  const box = within(await page("developer")).getByRole("region", { name: "Messages" });
  expect(within(box).getByText("Loading…")).toBeTruthy();
  expect(within(box).queryByText("No messages yet")).toBeNull();
  release();
  expect((await within(box).findByRole("alert")).textContent).toBe("lado.db is newer");
});

test("two agents of one name: the live one's page has none of an earlier one's messages", async () => {
  serve({ messages: MESSAGES.slice(0, 4) });
  open("/sessions/lado/agents/developer");
  const box = within(await page("developer")).getByRole("region", { name: "Messages" });
  const lines = await within(box).findAllByRole("listitem");
  expect(lines.map((one) => one.textContent)).toEqual([
    expect.stringContaining("message 10"),
    expect.stringContaining("message 11"),
  ]);
});

// Finish

const dialog = () => screen.findByRole("dialog", { name: "Finish developer?" });

test("Finish asks first with what the core says, then finishes the worker", async () => {
  serve({ preview: { removes_worktree: true, refused: null, work: { ...WORK.work!, ahead: 0, uncommitted: 0 } } });
  open("/sessions/lado/agents/developer");
  fireEvent.click(within(await page("developer")).getByRole("button", { name: "Finish…" }));
  const asking = await dialog();
  expect(await within(asking).findByText("Finish developer: its branch and worktree are removed.")).toBeTruthy();
  expect(within(asking).queryByRole("button", { name: "Discard work…" })).toBeNull();
  fireEvent.click(within(asking).getByRole("button", { name: "Finish developer" }));
  await waitFor(() =>
    expect(asked.find((one) => one.method === "POST")).toEqual({
      path: "/api/sessions/lado/agents/developer/finish",
      method: "POST",
      body: { discard: false },
    }),
  );
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
});

test("a refused finish shows why, and Discard work… asks again with what is lost", async () => {
  serve({
    preview: {
      removes_worktree: true,
      refused: "branch lado/lado/developer is not merged into main",
      work: WORK.work,
    },
  });
  open("/sessions/lado/agents/developer");
  fireEvent.click(within(await page("developer")).getByRole("button", { name: "Finish…" }));
  const asking = await dialog();
  expect(await within(asking).findByText("branch lado/lado/developer is not merged into main")).toBeTruthy();
  expect(within(asking).queryByRole("button", { name: "Finish developer" })).toBeNull();
  fireEvent.click(within(asking).getByRole("button", { name: "Discard work…" }));
  expect(asking.textContent).toContain("3 commits not in main are lost");
  expect(asking.textContent).toContain("2 uncommitted files are lost");
  expect(asking.textContent).toContain("lado/lado/feature-agents-tab");
  fireEvent.click(within(asking).getByRole("button", { name: "Discard and finish" }));
  await waitFor(() =>
    expect(asked.find((one) => one.method === "POST")?.body).toEqual({ discard: true }),
  );
});

test("a run's worker only has its window closed, and has no Discard", async () => {
  serve({ preview: { removes_worktree: false, refused: null, work: WORK.work } });
  open("/sessions/lado/agents/developer");
  fireEvent.click(within(await page("developer")).getByRole("button", { name: "Finish…" }));
  const asking = await dialog();
  expect(
    await within(asking).findByText(
      "Finish developer: closes its window; the run keeps its worktree and branch, and its step will need a new worker.",
    ),
  ).toBeTruthy();
  expect(within(asking).queryByRole("button", { name: "Discard work…" })).toBeNull();
});

test("a finish the server refuses says why and stays open", async () => {
  serve({ finish: { status: 400, body: { detail: 'worker "developer" has uncommitted changes' } } });
  open("/sessions/lado/agents/developer");
  fireEvent.click(within(await page("developer")).getByRole("button", { name: "Finish…" }));
  const asking = await dialog();
  fireEvent.click(await within(asking).findByRole("button", { name: "Finish developer" }));
  expect(await within(asking).findByText('worker "developer" has uncommitted changes')).toBeTruthy();
});
