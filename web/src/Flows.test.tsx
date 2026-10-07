// The session's Flows tab: its runs in two groups, a run's page with its head, what goes on
// now (its gate, answered there) and the history of its events, live from the feed.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, useLocation, useNavigate } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { GateInfo, NoteInfo, RunEventInfo, RunInfo, SessionInfo } from "./api";
import { App } from "./App";
import { clock, dayName, since } from "./ChatText";
import { FakeEventSource, FakeSocket, narrowColumn, stream, wideColumn } from "./fakes";
import styles from "./styles.css?raw";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const NO_WAITS = { gates: 0, questions: 0, agents: 0 };
const SETTINGS = { kits: ["team"], provider: "claude", permission_mode: null, without: [], ran_seconds: 0, running_since: null, stopped_at: null };
const SESSIONS: SessionInfo[] = [
  { name: "lado", repo: "/src/lado", status: "running", agents: 2, waiting: NO_WAITS, ...SETTINGS },
  { name: "old", repo: "/src/old", status: "stopped", agents: 0, waiting: NO_WAITS, ...SETTINGS },
];

type State = RunInfo["states"][number];

const work = (name: string, agent: string, outcomes: Record<string, string>, max_visits: number | null = null): State => ({
  name,
  kind: "work",
  agent,
  gate: null,
  ask: null,
  outcomes,
  max_visits,
  needs: [],
});

const STATES: State[] = [
  work("implement", "developer", { done: "review" }),
  work("review", "reviewer", { approved: "merge_ok", changes: "implement", again: "review" }, 3),
  { ...work("merge_ok", "", { approved: "done", rejected: "implement" }), kind: "gate", agent: null, gate: "approval", ask: "Merge it?" },
  { ...work("done", "", {}), kind: "end", agent: null },
];

function run(name: string, more: Partial<RunInfo> = {}): RunInfo {
  return {
    name,
    flow: "fix",
    kit: { name: "lado-dev", version: "0.7.0", source: "project" },
    task: "The human's gate answer as their bubble\nmore lines of the task",
    state: "review",
    status: "active",
    reason: "",
    acting: "reviewer",
    visits: { implement: 2, review: 2 },
    gate: null,
    worktree: "/w",
    branch: `lado/lado/${name.replace("/", "-")}`,
    language: "",
    created_at: "2026-10-04T10:02:00.000Z",
    since: "2026-10-04T11:20:00.000Z",
    ended_at: null,
    states: STATES,
    problem: null,
    ...more,
  };
}

function note(id: number, more: Partial<NoteInfo> = {}): NoteInfo {
  return {
    id,
    run: "fix/gate-bubble",
    state: "implement",
    kind: "report",
    actor: "developer",
    outcome: "done",
    target: "review",
    summary: `note ${id}`,
    body: "",
    created_at: `2026-10-04T10:${String(10 + id).padStart(2, "0")}:00.000Z`,
    ...more,
  };
}

function event(id: number, kind: string, detail: string, created_at: string, more: Partial<RunEventInfo> = {}): RunEventInfo {
  return { id, run: "fix/gate-bubble", kind, actor: "lado", detail, transition: null, created_at, ...more };
}

function gate(id: number, more: Partial<GateInfo> = {}): GateInfo {
  return {
    id,
    run: "feature/flows-tab",
    state: "merge_ok",
    kind: "approval",
    question: "Merge it?",
    options: ["approve", "reject"],
    note: "ready to merge",
    note_body: "",
    needs: [],
    answer: null,
    comment: "",
    answered_by: null,
    created_at: "2026-10-04T11:00:00.000Z",
    answered_at: null,
    problem: null,
    ...more,
  };
}

type Data = { runs?: RunInfo[]; notes?: NoteInfo[]; events?: RunEventInfo[]; gates?: GateInfo[]; agents?: string[] };
type Posted = { path: string; body: unknown };

const AGENT = {
  role: "developer",
  provider: "claude",
  status: "busy",
  run: null,
  task: null,
  status_reason: null,
  branch: "b",
  worktree: "/w",
  spawned_at: "2026-10-04T10:00:00.000Z",
  since: "2026-10-04T10:00:00.000Z",
};

function serve({ runs = [], notes = [], events = [], gates = [], agents = [] }: Data) {
  const posted: Posted[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        posted.push({ path, body: init.body ? JSON.parse(String(init.body)) : undefined });
        return new Response(JSON.stringify({ result: "approved" }));
      }
      if (path === "/api/sessions") return new Response(JSON.stringify(SESSIONS));
      const of = (list: unknown) => new Response(JSON.stringify(list));
      if (path.endsWith("/runs")) return of(runs);
      if (path.endsWith("/notes")) return of(notes);
      if (path.endsWith("/events")) return of(events);
      if (path.endsWith("/gates")) return of(gates);
      if (path.endsWith("/agents")) return of(agents.map((name) => ({ ...AGENT, name })));
      if (path.includes("/messages?")) return of({ items: [], earlier: false });
      return new Response("{}", { status: 404 });
    }),
  );
  return posted;
}

const runPath = (session: string, name: string) => `/sessions/${session}/flows/${encodeURIComponent(name)}`;

// The address, and the browser's Back.
function Where() {
  const { pathname, search } = useLocation();
  const navigate = useNavigate();
  return (
    <>
      <output aria-label="Address">{pathname + search}</output>
      <button type="button" onClick={() => navigate(-1)}>
        Browser back
      </button>
    </>
  );
}

function open(path: string | string[]) {
  return render(
    <MemoryRouter initialEntries={typeof path === "string" ? [path] : path}>
      <App />
      <Where />
    </MemoryRouter>,
  );
}

const address = () => screen.getByRole("status", { name: "Address" }).textContent;
const back = () => fireEvent.click(screen.getByRole("button", { name: "Browser back" }));
const runs = () => screen.findByRole("navigation", { name: "Flow runs" });
const page = (name: string) => screen.findByRole("region", { name: `Run ${name}` });

const WAITING = run("feature/flows-tab", {
  flow: "feature",
  state: "merge_ok",
  status: "waiting",
  reason: "Merge it?",
  acting: "human",
  gate: 41,
  visits: { implement: 1, review: 1, merge_ok: 1 },
  created_at: "2026-10-04T10:46:00.000Z",
});
const ACTIVE = run("fix/gate-bubble");
const ENDED = run("fix/old", {
  state: "done",
  status: "ended",
  acting: "",
  ended_at: "2026-10-03T09:00:00.000Z",
  created_at: "2026-10-03T08:00:00.000Z",
});
const CANCELLED = run("fix/older", {
  status: "cancelled",
  reason: "not needed",
  acting: "",
  ended_at: "2026-10-03T10:00:00.000Z",
  created_at: "2026-10-02T08:00:00.000Z",
});

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
  wideColumn();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const rowNames = (region: HTMLElement) =>
  within(region)
    .queryAllByRole("link")
    .map((one) => one.querySelector(".run-name")?.textContent);

// The overview

const FLOWS = "/sessions/lado/flows";
const group = (list: HTMLElement, name: string) => within(list).getByRole("region", { name });
const fold = (name: RegExp) => screen.getByRole("button", { name }) as HTMLButtonElement;
const HISTORY_OPEN = () => localStorage.setItem("lado.flowsGroups", JSON.stringify({ history: "open" }));

test("the tab opens on the overview, also in a wide column: Active in green, the waiting runs first, as cards", async () => {
  serve({ runs: [ACTIVE, ENDED, WAITING, CANCELLED] });
  open(FLOWS);
  const list = await runs();
  expect((await screen.findByRole("link", { name: "Flows · 2" })).getAttribute("aria-current")).toBe("page");
  expect(address()).toBe(FLOWS);
  expect(screen.queryByRole("region", { name: /^Run / })).toBeNull();
  const active = group(list, "Active");
  expect(active.className).toContain("tone-done");
  expect(rowNames(active)).toEqual(["feature/flows-tab", "fix/gate-bubble"]);
  const [waiting, acting] = within(active).getAllByRole("link");
  expect(waiting.getAttribute("href")).toBe(runPath("lado", WAITING.name));
  expect(waiting.className).toBe("list-card waits");
  expect(acting.className).toBe("list-card");
  expect(waiting.querySelector(".pill")?.textContent).toBe("Waits for you");
  expect(acting.querySelector(".pill")).toBeNull();
  expect(waiting.querySelector(".run-about")?.textContent).toBe(`merge_ok · gate #41 · ${since(WAITING.since)}`);
  expect(acting.querySelector(".run-about")?.textContent).toBe(`review · → reviewer · ${since(ACTIVE.since)}`);
  expect(acting.querySelector(".run-card-meta")?.textContent).toBe(`fix · lado-dev 0.7.0 · started ${clock(ACTIVE.created_at)}`);
  expect(acting.textContent).not.toContain(ACTIVE.task.split("\n")[0]);
});

test("a card's states are the run head's: the same chips, the current one marked, orange while it waits", async () => {
  serve({ runs: [ACTIVE, WAITING] });
  open(FLOWS);
  const [waiting, acting] = within(group(await runs(), "Active")).getAllByRole("link");
  const chips = within(acting).getAllByRole("listitem", { name: /^State / });
  expect(chips.map((one) => one.textContent)).toEqual(["implement×2", "review2/3", "◇ merge_ok", "done"]);
  expect(chips[1].getAttribute("aria-current")).toBe("step");
  expect(chips[1].className).toBe("flow-state visited current");
  const gate = within(waiting).getByRole("listitem", { name: "State merge_ok" });
  expect(gate.className).toBe("flow-state visited current waiting");
});

test("a card of a run whose flow cannot be read has the problem in place of its states", async () => {
  serve({ runs: [run("fix/gate-bubble", { states: [], problem: "not JSON" })] });
  open(FLOWS);
  const card = within(group(await runs(), "Active")).getByRole("link");
  expect(within(card).queryByRole("list", { name: "States" })).toBeNull();
  expect(card.querySelector(".problem")?.textContent).toBe("Flow cannot be read: not JSON");
});

test("in a column narrower than 900 px the overview is the same, and no run opens by itself", async () => {
  narrowColumn();
  serve({ runs: [ACTIVE, WAITING, ENDED] });
  open(FLOWS);
  const list = await runs();
  expect(address()).toBe(FLOWS);
  expect(rowNames(group(list, "Active"))).toEqual(["feature/flows-tab", "fix/gate-bubble"]);
  expect(screen.queryByRole("region", { name: /^Run / })).toBeNull();
});

test("History is folded by default; each group folds by its heading and is remembered", async () => {
  serve({ runs: [ACTIVE, ENDED, CANCELLED] });
  open(FLOWS);
  const list = await runs();
  expect(fold(/^History/).getAttribute("aria-expanded")).toBe("false");
  expect(within(group(list, "History")).queryAllByRole("link")).toHaveLength(0);
  fireEvent.click(fold(/^History/));
  const history = group(list, "History");
  expect(history.className).toContain("tone-neutral");
  expect(rowNames(history)).toEqual(["fix/older", "fix/old"]);
  fireEvent.click(fold(/^Active/));
  expect(within(group(list, "Active")).queryAllByRole("link")).toHaveLength(0);
  expect(JSON.parse(localStorage.getItem("lado.flowsGroups")!)).toEqual({ active: "folded", history: "open" });
  cleanup();
  open(FLOWS);
  await runs();
  expect(fold(/^Active/).getAttribute("aria-expanded")).toBe("false");
  expect(fold(/^History/).getAttribute("aria-expanded")).toBe("true");
});

test("with no runs both groups say they are empty", async () => {
  HISTORY_OPEN();
  serve({ runs: [] });
  open(FLOWS);
  const list = await runs();
  expect(within(group(list, "Active")).getByText("No active runs")).toBeTruthy();
  expect(within(group(list, "History")).getByText("No ended runs yet")).toBeTruthy();
});

test("without open runs the tab is just Flows", async () => {
  serve({ runs: [ENDED] });
  open("/sessions/lado/activity");
  expect(await screen.findByRole("link", { name: "Flows" })).toBeTruthy();
});

test("History shows its first 10 by days, then Show N more", async () => {
  HISTORY_OPEN();
  const ended = Array.from({ length: 12 }, (_, at) =>
    // One local day, 20:00 back to 09:00.
    run(`fix/e${at + 1}`, { status: "ended", acting: "", ended_at: new Date(2026, 9, 3, 20 - at).toISOString() }),
  );
  serve({ runs: [ACTIVE, ...ended] });
  open(FLOWS);
  const history = group(await runs(), "History");
  expect(rowNames(history)).toEqual(ended.slice(0, 10).map((one) => one.name));
  expect(within(history).getAllByRole("heading", { level: 4 }).map((one) => one.textContent)).toEqual([
    dayName(ended[0].ended_at!),
  ]);
  fireEvent.click(within(history).getByRole("button", { name: "Show 2 more" }));
  expect(rowNames(history)).toHaveLength(12);
});

test("an ended run's row has its name, status and time, no states, no task; its day heads its rows", async () => {
  HISTORY_OPEN();
  serve({ runs: [ACTIVE, ENDED] });
  open(FLOWS);
  const history = group(await runs(), "History");
  const row = within(history).getByRole("link");
  expect(row.className).toBe("list-row dim");
  expect(row.textContent).toBe(`fix/old${`ended · ${clock(ENDED.ended_at!)}`}`);
  expect(within(history).getByRole("heading", { level: 4 }).textContent).toBe(dayName(ENDED.ended_at!));
});

// A run's page in place of the overview

test("a run's page replaces the overview in a wide column, with the way back to it", async () => {
  serve({ runs: [ACTIVE, WAITING, ENDED, CANCELLED] });
  open(FLOWS);
  fireEvent.click(within(group(await runs(), "Active")).getByRole("link", { name: /fix\/gate-bubble/ }));
  const region = await page("fix/gate-bubble");
  expect(screen.queryByRole("navigation", { name: "Flow runs" })).toBeNull();
  // The page is in a size container: its @container rules hold.
  expect(region.closest(".list-main")).toBeTruthy();
  expect(styles).toMatch(/\.list-main\s*\{[^}]*container-type:\s*inline-size/);
  fireEvent.click(screen.getByRole("link", { name: "‹ All runs (2 open, 2 ended)" }));
  expect(await runs()).toBeTruthy();
  expect(address()).toBe(FLOWS);
});

test("an unknown run is not found, with the way back, and the address stays", async () => {
  serve({ runs: [ACTIVE] });
  open(runPath("lado", "fix/nope"));
  expect(await screen.findByText("Run fix/nope not found")).toBeTruthy();
  expect(screen.getByRole("link", { name: "‹ All runs (1 open, 0 ended)" })).toBeTruthy();
  expect(address()).toBe(runPath("lado", "fix/nope"));
});

// The search, in the session's tab bar

const LOGIN = run("fix/login", { status: "ended", task: "Add a LOGIN page", ended_at: "2026-10-03T11:00:00.000Z" });
const finder = () => screen.queryByRole("button", { name: "Find a run" });
const field = () => screen.queryByRole("searchbox", { name: "Find a run" }) as HTMLInputElement | null;

test("the search finds a run by its name, task, flow or state in both groups at once, from ?find=", async () => {
  serve({ runs: [ACTIVE, WAITING, LOGIN] });
  open(`${FLOWS}?find=login`);
  const list = await runs();
  expect(rowNames(list)).toEqual(["fix/login"]);
  expect(within(group(list, "Active")).getByText("No match")).toBeTruthy();
  // Searching, every group shows open and its heading is off; what is remembered stays.
  expect(fold(/^History/).disabled).toBe(true);
  expect(fold(/^History/).getAttribute("aria-expanded")).toBe("true");
  expect(localStorage.getItem("lado.flowsGroups")).toBeNull();
  // With text, the field is open in the tab bar.
  expect(field()!.value).toBe("login");
  fireEvent.change(field()!, { target: { value: "merge_ok" } });
  expect(rowNames(list)).toEqual(["feature/flows-tab"]);
  expect(within(group(list, "History")).getByText("No match")).toBeTruthy();
  fireEvent.change(field()!, { target: { value: "FIX" } });
  expect(rowNames(list)).toEqual(["fix/gate-bubble", "fix/login"]);
  fireEvent.change(field()!, { target: { value: "nothing like it" } });
  expect(within(list).getByText("No run matches “nothing like it”")).toBeTruthy();
});

test("the field writes ?find= in place, keeps the other parameters, and an empty one drops it", async () => {
  serve({ runs: [ACTIVE, LOGIN] });
  open(["/sessions/lado/activity", `${FLOWS}?x=1`]);
  await runs();
  fireEvent.click(finder()!);
  fireEvent.change(field()!, { target: { value: "lo" } });
  fireEvent.change(field()!, { target: { value: "log in" } });
  expect(address()).toBe(`${FLOWS}?x=1&find=log+in`);
  fireEvent.change(field()!, { target: { value: "" } });
  expect(address()).toBe(`${FLOWS}?x=1`);
  // Typing added no step to the history: Back leaves the tab.
  back();
  expect(address()).toBe("/sessions/lado/activity");
});

test("the find button is only on the Flows overview: a click or / opens the field, Esc clears and closes it", async () => {
  serve({ runs: [ACTIVE, LOGIN] });
  open(FLOWS);
  const list = await runs();
  expect(field()).toBeNull();
  fireEvent.click(finder()!);
  expect(document.activeElement).toBe(field());
  // Left empty, it closes.
  fireEvent.blur(field()!);
  expect(field()).toBeNull();
  fireEvent.keyDown(document.body, { key: "/" });
  expect(document.activeElement).toBe(field());
  fireEvent.change(field()!, { target: { value: "login" } });
  // Left with text, it stays.
  fireEvent.blur(field()!);
  expect(field()).toBeTruthy();
  fireEvent.keyDown(field()!, { key: "Escape" });
  expect(field()).toBeNull();
  expect(address()).toBe(FLOWS);
  expect(rowNames(list)).toEqual(["fix/gate-bubble"]);
  // A "/" typed in a field is the field's.
  const other = document.createElement("textarea");
  document.body.append(other);
  fireEvent.keyDown(other, { key: "/" });
  expect(field()).toBeNull();
  other.remove();
  // Not on a run's page, not on another tab.
  fireEvent.click(within(list).getByRole("link", { name: /fix\/gate-bubble/ }));
  await page("fix/gate-bubble");
  expect(finder()).toBeNull();
  fireEvent.keyDown(document.body, { key: "/" });
  expect(field()).toBeNull();
  fireEvent.click(screen.getByRole("link", { name: "Agents" }));
  expect(finder()).toBeNull();
});

test("back from a run's page, by its link or the browser's, the overview has its search and its scroll", async () => {
  // jsdom keeps no scroll position: the elements keep what is set.
  const scrolled = new WeakMap<Element, number>();
  vi.spyOn(HTMLElement.prototype, "scrollTop", "get").mockImplementation(function (this: HTMLElement) {
    return scrolled.get(this) ?? 0;
  });
  vi.spyOn(HTMLElement.prototype, "scrollTop", "set").mockImplementation(function (this: HTMLElement, value: number) {
    scrolled.set(this, value);
  });
  serve({ runs: [ACTIVE, WAITING, LOGIN] });
  open(`${FLOWS}?find=fix`);
  let list = await runs();
  list.scrollTop = 140;
  fireEvent.scroll(list);
  fireEvent.click(within(list).getByRole("link", { name: /fix\/gate-bubble/ }));
  await page("fix/gate-bubble");
  expect(address()).toBe(runPath("lado", ACTIVE.name));
  fireEvent.click(screen.getByRole("link", { name: "‹ All runs (2 open, 1 ended)" }));
  list = await runs();
  expect(address()).toBe(`${FLOWS}?find=fix`);
  expect(list.scrollTop).toBe(140);
  expect(rowNames(list)).toEqual(["fix/gate-bubble", "fix/login"]);
  fireEvent.click(within(list).getByRole("link", { name: /fix\/login/ }));
  await page("fix/login");
  back();
  list = await runs();
  expect(address()).toBe(`${FLOWS}?find=fix`);
  expect(list.scrollTop).toBe(140);
});

// A run's page: the head

test("a run's head: name, status, meta, the task's first line with more, and every state as a chip", async () => {
  serve({ runs: [ACTIVE] });
  open(runPath("lado", ACTIVE.name));
  const region = await page("fix/gate-bubble");
  const head = within(region).getByRole("banner");
  expect(within(head).getByRole("heading", { name: "fix/gate-bubble" })).toBeTruthy();
  expect(head.querySelector(".pill")?.textContent).toBe("Active");
  expect(head.textContent).toContain("flow fix · lado-dev 0.7.0");
  expect(head.textContent).toContain(`started ${clock(ACTIVE.created_at)}`);
  expect(head.textContent).toContain("branch lado/lado/fix-gate-bubble");
  expect(head.querySelector(".run-task-first")?.textContent).toBe("The human's gate answer as their bubble");
  expect(head.textContent).not.toContain("more lines of the task");
  fireEvent.click(within(head).getByRole("button", { name: "more" }));
  expect(head.querySelector(".run-task-full")?.textContent).toBe(ACTIVE.task);
  fireEvent.click(within(head).getByRole("button", { name: "less" }));
  expect(head.textContent).not.toContain("more lines of the task");
  const states = within(region).getAllByRole("listitem", { name: /^State / });
  expect(states.map((one) => one.textContent)).toEqual(["implement×2", "review2/3", "◇ merge_ok", "done"]);
  expect(states.map((one) => one.getAttribute("title"))).toEqual(["developer", "reviewer", "you", null]);
  expect(states[1].getAttribute("aria-current")).toBe("step");
  expect(states[1].className).toContain("current");
  expect(states[0].className).toContain("visited");
  expect(states[2].className).not.toContain("visited");
  expect(within(region).queryByRole("list", { name: "Ways back" })).toBeNull();
  expect(region.textContent).not.toContain("↶");
});

test("a run whose flow cannot be read says so, on several lines, where its states would be", async () => {
  const problem = 'run "fix/gate-bubble": its flow snapshot is not JSON:\nline 1';
  serve({ runs: [run("fix/gate-bubble", { states: [], acting: "", problem })], notes: [note(1)] });
  open(runPath("lado", "fix/gate-bubble"));
  const region = await page("fix/gate-bubble");
  expect(within(region).queryByRole("list", { name: "States" })).toBeNull();
  const alert = within(region).getByRole("alert");
  expect(alert.textContent).toBe(`Flow cannot be read: ${problem}`);
  expect(alert.className).toContain("problem");
  expect(within(region).getByRole("list", { name: "Events" }).textContent).toContain("note 1");
});

// A gate card's problem is a `.problem` too (GateCard.tsx).
test("a problem of several lines keeps its lines, on the run's page and in a gate's card", () => {
  expect(styles).toMatch(/(^|\n)\.problem\s*\{[^}]*white-space:\s*pre-wrap/);
});

// A run's page: now

const nowCard = (region: HTMLElement) => within(region).getByRole("region", { name: "Now" });

test("an active run's now says who acts, as the core says it, linked while it lives, and the visit", async () => {
  serve({ runs: [ACTIVE], agents: ["reviewer"] });
  open(runPath("lado", ACTIVE.name));
  const now = nowCard(await page("fix/gate-bubble"));
  expect(now.textContent).toMatch(/^Now · /);
  expect((await within(now).findByRole("link", { name: "reviewer" })).getAttribute("href")).toBe(
    "/sessions/lado/agents/reviewer",
  );
  expect(now.textContent).toContain("review · visit 2 of 3");
});

test("a waiting run's now is its gate, compact, answered on the page; the run moves on with the feed", async () => {
  const posted = serve({
    runs: [WAITING],
    notes: [note(1, { run: WAITING.name, summary: "the design" })],
    gates: [gate(41, { needs: [{ state: "implement", note: note(1, { run: WAITING.name, summary: "the design" }) }] })],
  });
  open(runPath("lado", WAITING.name));
  const region = await page("feature/flows-tab");
  expect(region.querySelector(".run-head .pill")?.textContent).toBe("Waits for you");
  expect(within(region).getByRole("listitem", { name: "State merge_ok" }).className).toContain("waiting");
  const now = nowCard(region);
  expect(now.className).toContain("waits");
  const card = within(now).getByRole("article", { name: "Gate #41" });
  expect(within(card).getByRole("heading", { name: "Gate #41 · feature/flows-tab · merge_ok" })).toBeTruthy();
  expect(card.querySelector("time")?.getAttribute("dateTime")).toBe(gate(41).created_at);
  expect(within(card).getByText("Merge it?")).toBeTruthy();
  expect(card.textContent).not.toContain("ready to merge");
  expect(within(card).queryByRole("list", { name: "Notes it needs" })).toBeNull();
  fireEvent.change(within(card).getByRole("textbox"), { target: { value: "ship it" } });
  fireEvent.click(within(card).getByRole("button", { name: "Approve" }));
  await vi.waitFor(() =>
    expect(posted).toEqual([{ path: "/api/sessions/lado/gates/41/answer", body: { option: "approve", comment: "ship it" } }]),
  );
  stream().send("change", { kind: "gates", session: "lado", key: "41", op: "update", item: gate(41, { answer: "approve", answered_by: "human" }) }, "11");
  stream().send(
    "change",
    { kind: "runs", session: "lado", key: WAITING.name, op: "update", item: { ...WAITING, state: "done", status: "ended", acting: "", gate: null, ended_at: "2026-10-04T11:05:00.000Z" } },
    "12",
  );
  expect(within(region).queryByRole("article", { name: "Gate #41" })).toBeNull();
  expect(nowCard(region).textContent).toContain(`Ended · ${clock("2026-10-04T11:05:00.000Z")}`);
  expect(within(region).getByRole("listitem", { name: "State done" }).getAttribute("aria-current")).toBe("step");
});

test("a waiting run without a gate says why it waits", async () => {
  serve({ runs: [{ ...WAITING, gate: null, reason: "needs a developer" }] });
  open(runPath("lado", WAITING.name));
  expect(nowCard(await page("feature/flows-tab")).textContent).toContain("needs a developer");
});

test("an ended and a cancelled run's now: when, the event's detail and how long the run took", async () => {
  serve({
    runs: [ENDED, CANCELLED],
    events: [
      event(7, "flow_end", "at done", "2026-10-03T09:00:00.000Z", { run: "fix/old" }),
      event(8, "flow_cancel", "not needed", "2026-10-03T10:00:00.000Z", { run: "fix/older", actor: "supervisor" }),
    ],
  });
  open(runPath("lado", "fix/old"));
  let region = await page("fix/old");
  expect(within(region).getByRole("banner").querySelector(".pill")?.textContent).toBe("Ended");
  expect(nowCard(region).textContent).toBe(`Ended · ${clock(ENDED.ended_at!)}at done · took 1 h`);
  cleanup();
  open(runPath("lado", "fix/older"));
  region = await page("fix/older");
  expect(within(region).getByRole("banner").querySelector(".pill")?.textContent).toBe("Cancelled");
  expect(nowCard(region).textContent).toBe(`Cancelled · ${clock(CANCELLED.ended_at!)}not needed · took 1 d 2 h`);
});

test("in a stopped session the gate on the run's page cannot be answered", async () => {
  serve({ runs: [WAITING], gates: [gate(41)] });
  open(runPath("old", WAITING.name));
  const card = await screen.findByRole("article", { name: "Gate #41" });
  expect((within(card).getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(true);
});

// A run's page: the history

const feed = async (name: string) => within(await page(name)).findByRole("list", { name: "Events" });
// The feed's rows; a note's Markdown may have list items of its own.
const steps = (list: HTMLElement) => Array.from(list.querySelectorAll<HTMLElement>(":scope > li"));
const lines = (list: HTMLElement) => steps(list).map((one) => one.querySelector(".feed-top")?.textContent);
const opened = (list: HTMLElement) =>
  within(list)
    .queryAllByRole("button", { expanded: true })
    .map((one) => one.textContent);

const STEPS = {
  runs: [ACTIVE, WAITING],
  agents: ["supervisor", "reviewer"],
  notes: [
    note(1, { summary: "built the bubble", body: "**bold** line\n\n- item" }),
    note(2, { run: "feature/flows-tab", summary: "another run's note", body: "x" }),
    note(3, { state: "review", actor: "reviewer", outcome: "changes", target: "implement", summary: "2 findings", body: "fix them" }),
    note(4, { summary: "both fixed" }),
  ],
  events: [
    event(1, "flow_start", "at implement, kit lado-dev 0.7.0", "2026-10-04T10:02:00.000Z", { actor: "supervisor" }),
    event(2, "flow", "implement -done-> review", "2026-10-04T10:11:00.000Z"),
  ],
};

test("the history is newest first; its switch turns it and is remembered", async () => {
  serve(STEPS);
  open(runPath("lado", ACTIVE.name));
  let list = await feed("fix/gate-bubble");
  const region = await page("fix/gate-bubble");
  expect(within(region).getByRole("heading", { name: "History · 4 events" })).toBeTruthy();
  const newest = [
    "developer implement done → review",
    "reviewer review changes → implement",
    "developer implement done → review",
    "supervisor started the run",
  ];
  expect(lines(list)).toEqual(newest);
  expect(steps(list).map((one) => one.querySelector(".feed-summary")?.textContent)).toEqual([
    "both fixed",
    "2 findings",
    "built the bubble",
    "at implement, kit lado-dev 0.7.0",
  ]);
  // The flow transition event is the step itself: not shown twice.
  expect(list.textContent).not.toContain("-done->");
  fireEvent.click(within(region).getByRole("button", { name: "Newest first ↓" }));
  expect(lines(list)).toEqual([...newest].reverse());
  expect(localStorage.getItem("lado.flowsOrder")).toBe("oldest");
  cleanup();
  open(runPath("lado", ACTIVE.name));
  list = await feed("fix/gate-bubble");
  expect(lines(list)).toEqual([...newest].reverse());
  fireEvent.click(within(await page("fix/gate-bubble")).getByRole("button", { name: "Oldest first ↑" }));
  expect(localStorage.getItem("lado.flowsOrder")).toBe("newest");
});


test("a row has the time, who, from, outcome, to and the summary; a way back is marked, not when the flow cannot be read", async () => {
  serve(STEPS);
  open(runPath("lado", ACTIVE.name));
  const list = await feed("fix/gate-bubble");
  const [fixed, findings] = steps(list);
  expect(fixed.querySelector("time")?.textContent).toBe(clock(note(4).created_at));
  expect(fixed.querySelector(".feed-chip")?.className).not.toContain("back");
  expect(findings.querySelector(".feed-chip")?.className).toContain("back");
  expect(findings.querySelector(".feed-dot")?.className).toContain("back");
  await vi.waitFor(() => expect(findings.querySelector(".feed-who a")?.getAttribute("href")).toBe("/sessions/lado/agents/reviewer"));
  expect(within(fixed).queryByRole("link", { name: "developer" })).toBeNull(); // finished: no page
  cleanup();
  serve({ ...STEPS, runs: [{ ...ACTIVE, states: [], problem: "unreadable" }] });
  open(runPath("lado", ACTIVE.name));
  const unread = await feed("fix/gate-bubble");
  expect(unread.querySelectorAll(".back")).toHaveLength(0);
});

test("the latest event with a body is open at first: its facts and its body as Markdown; Open all opens all", async () => {
  serve(STEPS);
  open(runPath("lado", ACTIVE.name));
  const list = await feed("fix/gate-bubble");
  expect(opened(list)).toEqual(["2 findings"]);
  const findings = steps(list)[1];
  const facts = Object.fromEntries(
    Array.from(findings.querySelectorAll(".feed-facts dt")).map((one) => [one.textContent, one.nextElementSibling?.textContent]),
  );
  expect(facts).toEqual({ Who: "reviewer", From: "review", Outcome: "changes", To: "implement", "Step took": "2 min" });
  expect(findings.querySelector(".chat-body")?.textContent).toBe("fix them");
  // Another opens on a click, as Markdown.
  const bubble = steps(list)[2];
  fireEvent.click(within(bubble).getByRole("button", { name: "built the bubble" }));
  expect(bubble.querySelector(".chat-body strong")?.textContent).toBe("bold");
  expect(bubble.querySelector(".chat-body li")?.textContent).toBe("item");
  fireEvent.click(within(bubble).getByRole("button", { name: "built the bubble" }));
  expect(bubble.querySelector(".chat-body")).toBeNull();
  const region = await page("fix/gate-bubble");
  fireEvent.click(within(region).getByRole("button", { name: "Open all" }));
  expect(opened(list)).toEqual(["both fixed", "2 findings", "built the bubble"]);
  fireEvent.click(within(region).getByRole("button", { name: "Close all" }));
  expect(opened(list)).toEqual([]);
});

test("a new event with a body from the feed opens; another run's page starts afresh", async () => {
  serve(STEPS);
  open(runPath("lado", ACTIVE.name));
  const list = await feed("fix/gate-bubble");
  stream().send(
    "change",
    { kind: "notes", session: "lado", key: "5", op: "insert", item: note(5, { state: "review", actor: "reviewer", outcome: "approved", target: "merge_ok", summary: "looks good", body: "ok" }) },
    "11",
  );
  expect(opened(list)).toEqual(["looks good", "2 findings"]);
  stream().send("change", { kind: "notes", session: "lado", key: "6", op: "insert", item: note(6, { summary: "no body" }) }, "12");
  expect(opened(list)).toEqual(["looks good", "2 findings"]);
  fireEvent.click(screen.getByRole("link", { name: /^‹ All runs/ }));
  fireEvent.click(within(await runs()).getByRole("link", { name: /feature\/flows-tab/ }));
  expect(opened(await feed("feature/flows-tab"))).toEqual(["another run's note"]);
});

test("while a gate is open, the notes it needs are open too", async () => {
  const design = note(1, { run: WAITING.name, state: "implement", summary: "the design", body: "design text" });
  serve({
    runs: [WAITING],
    notes: [
      design,
      note(2, { run: WAITING.name, state: "implement", kind: "override", actor: "human", outcome: "", target: "review", summary: "flow-set", body: "why" }),
      note(3, { run: WAITING.name, state: "review", actor: "reviewer", outcome: "approved", target: "merge_ok", summary: "approved", body: "fine" }),
    ],
    gates: [gate(41, { needs: [{ state: "implement", note: design }, { state: "review", note: null }] })],
  });
  open(runPath("lado", WAITING.name));
  expect(opened(await feed("feature/flows-tab"))).toEqual(["approved", "the design"]);
});

test("the start, end and cancel are one line, never opened, without the end's detail", async () => {
  serve({
    runs: [ENDED, CANCELLED],
    notes: [note(1, { run: "fix/old", state: "merge", actor: "supervisor", outcome: "merged", target: "done", summary: "merged", created_at: "2026-10-03T09:00:00.001Z" })],
    events: [
      event(7, "flow_start", "at merge", "2026-10-03T09:00:00.002Z", { run: "fix/old" }),
      event(8, "flow_end", "at done", "2026-10-03T09:00:00.000Z", { run: "fix/old" }),
      event(9, "flow_cancel", "not needed", "2026-10-03T10:00:00.000Z", { run: "fix/older", actor: "supervisor" }),
    ],
  });
  open(runPath("lado", "fix/old"));
  // The start first and the end last, whatever millisecond each row of the step got.
  let list = await feed("fix/old");
  expect(lines(list)).toEqual(["ended the run", "supervisor merge merged → done", "started the run"]);
  const [end, , start] = steps(list);
  for (const one of [end, start]) expect(within(one).queryByRole("button")).toBeNull();
  expect(list.textContent).not.toContain("at done");
  cleanup();
  open(runPath("lado", "fix/older"));
  list = await feed("fix/older");
  expect(lines(list)).toEqual(["cancelled by supervisor"]);
  expect(list.textContent).not.toContain("not needed");
});

test("a flow-set, a loop limit's answer and a note from before steps were kept show what they have", async () => {
  serve({
    runs: [ACTIVE],
    notes: [
      note(1, { actor: "", outcome: "", target: "", summary: "an old note" }),
      note(2, { state: "review", kind: "override", actor: "human", outcome: "", target: "implement", summary: "set by the human: redo" }),
      note(3, { state: "review", kind: "override", actor: "human", outcome: "continue", target: "review", summary: "continue" }),
    ],
  });
  open(runPath("lado", ACTIVE.name));
  const list = await feed("fix/gate-bubble");
  expect(lines(list)).toEqual([
    "you review continue → review loop limit",
    "you review → implement flow-set",
    "implement",
  ]);
  fireEvent.click(within(await page("fix/gate-bubble")).getByRole("button", { name: "Open all" }));
  const [loop, set, old] = steps(list);
  expect(loop.querySelector(".feed-detail")?.textContent).toContain("No comment.");
  expect(Array.from(set.querySelectorAll(".feed-facts dt")).map((one) => one.textContent)).toEqual(["Who", "From", "To", "Step took"]);
  expect(Array.from(old.querySelectorAll(".feed-facts dt")).map((one) => one.textContent)).toEqual(["From"]);
});

