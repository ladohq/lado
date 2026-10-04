// The session's Flows tab: its runs in groups, a run's page with the picture of its flow,
// its open gate and the timeline of its steps, live from the feed.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { GateInfo, NoteInfo, RunEventInfo, RunInfo, SessionInfo } from "./api";
import { App } from "./App";
import { FakeEventSource, FakeResizeObserver, FakeSocket, stream } from "./fakes";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const NO_WAITS = { gates: 0, questions: 0, agents: 0 };
const SETTINGS = { kits: ["team"], provider: "claude", permission_mode: null, without: [] };
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
  return { id, run: "fix/gate-bubble", kind, actor: "lado", detail, created_at, ...more };
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
    ...more,
  };
}

type Data = { runs?: RunInfo[]; notes?: NoteInfo[]; events?: RunEventInfo[]; gates?: GateInfo[] };
type Posted = { path: string; body: unknown };

function serve({ runs = [], notes = [], events = [], gates = [] }: Data) {
  const posted: Posted[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        posted.push({ path, body: init.body ? JSON.parse(String(init.body)) : undefined });
        return new Response(JSON.stringify({ result: "approved" }));
      }
      if (path === "/api/sessions") return new Response(JSON.stringify(SESSIONS));
      const of = (list: unknown[]) => new Response(JSON.stringify(list));
      if (path.endsWith("/runs")) return of(runs);
      if (path.endsWith("/notes")) return of(notes);
      if (path.endsWith("/events")) return of(events);
      if (path.endsWith("/gates")) return of(gates);
      if (path.endsWith("/agents") || path.endsWith("/messages")) return of([]);
      return new Response("{}", { status: 404 });
    }),
  );
  return posted;
}

const runPath = (session: string, name: string) => `/sessions/${session}/flows/${encodeURIComponent(name)}`;

function open(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

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
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// The list

test("the runs come in groups, the ended ones folded and remembered, the tab counts the open ones", async () => {
  serve({ runs: [ACTIVE, ENDED, WAITING, CANCELLED] });
  open(runPath("lado", ACTIVE.name));
  const list = await runs();
  expect((await screen.findByRole("link", { name: "Flows · 2" })).getAttribute("aria-current")).toBe("page");
  const waiting = within(list).getByRole("region", { name: "Waiting for you" });
  expect(within(waiting).getByRole("link").textContent).toContain("feature/flows-tab");
  expect(within(waiting).getByRole("link").textContent).toContain("merge_ok · gate #41");
  const active = within(list).getByRole("region", { name: "Active" });
  expect(within(active).getByRole("link").textContent).toContain("review · → reviewer");
  expect(within(active).getByRole("link").getAttribute("aria-current")).toBe("page");
  const toggle = within(list).getByRole("button", { name: /Ended \(2\)/ });
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  expect(within(list).queryByRole("region", { name: "Ended" })).toBeNull();
  fireEvent.click(toggle);
  const ended = within(list).getByRole("region", { name: "Ended" });
  // Newest end first.
  expect(within(ended).getAllByRole("link").map((one) => one.textContent)).toEqual([
    expect.stringContaining("fix/older"),
    expect.stringContaining("fix/old"),
  ]);
  expect(within(ended).getAllByRole("link")[0].textContent).toContain("cancelled");
  expect(localStorage.getItem("lado.flowsEnded")).toBe("open");
  cleanup();
  open(runPath("lado", ACTIVE.name));
  expect(within(await runs()).getByRole("region", { name: "Ended" })).toBeTruthy();
});

test("without open runs the tab is just Flows", async () => {
  serve({ runs: [ENDED] });
  open("/sessions/lado/activity");
  expect(await screen.findByRole("link", { name: "Flows" })).toBeTruthy();
});

test("the flows tab without a run opens the first waiting run, else the first active one", async () => {
  serve({ runs: [ACTIVE, WAITING] });
  open("/sessions/lado/flows");
  expect(await page("feature/flows-tab")).toBeTruthy();
  cleanup();
  serve({ runs: [ENDED, ACTIVE] });
  open("/sessions/lado/flows");
  expect(await page("fix/gate-bubble")).toBeTruthy();
});

test("with no runs the tab says so; with only ended ones it asks to select one", async () => {
  serve({ runs: [] });
  open("/sessions/lado/flows");
  expect(await screen.findByText("No flow runs yet")).toBeTruthy();
  cleanup();
  serve({ runs: [ENDED] });
  open("/sessions/lado/flows");
  expect(await screen.findByText("Select a run")).toBeTruthy();
});

test("an unknown run is not found, and the address stays", async () => {
  serve({ runs: [ACTIVE] });
  open(runPath("lado", "fix/nope"));
  expect(await screen.findByText("Run fix/nope not found")).toBeTruthy();
  expect(within(await runs()).getByRole("link").textContent).toContain("fix/gate-bubble");
});

test("in a column narrower than 900 px the list is a select with the same groups", async () => {
  vi.stubGlobal("ResizeObserver", FakeResizeObserver);
  FakeResizeObserver.all = [];
  serve({ runs: [ACTIVE, WAITING, ENDED] });
  open(runPath("lado", ACTIVE.name));
  await page("fix/gate-bubble");
  FakeResizeObserver.resize(() => 1000);
  expect(screen.queryByRole("combobox", { name: "Flow run" })).toBeNull();
  FakeResizeObserver.resize(() => 700);
  const select = screen.getByRole("combobox", { name: "Flow run" }) as HTMLSelectElement;
  expect(screen.queryByRole("navigation", { name: "Flow runs" })).toBeNull();
  expect(select.value).toBe("fix/gate-bubble");
  const groups = Array.from(select.querySelectorAll("optgroup")).map((one) => one.label);
  expect(groups).toEqual(["Waiting for you", "Active", "Ended (1)"]);
  fireEvent.change(select, { target: { value: "feature/flows-tab" } });
  expect(await page("feature/flows-tab")).toBeTruthy();
});

// A run's page

test("a run's page has its head and every state of its flow, the current one marked, and the ways back", async () => {
  serve({ runs: [ACTIVE] });
  open(runPath("lado", ACTIVE.name));
  const region = await page("fix/gate-bubble");
  const head = within(region).getByRole("banner");
  expect(within(head).getByRole("heading", { name: "fix/gate-bubble" })).toBeTruthy();
  expect(head.textContent).toContain("flow fix · lado-dev 0.7.0");
  expect(head.textContent).toContain("The human's gate answer as their bubble");
  expect(head.textContent).toContain("review · active · reviewer");
  expect(head.textContent).toContain("lado/lado/fix-gate-bubble");
  const states = within(region).getAllByRole("listitem", { name: /^State / });
  expect(states.map((one) => one.textContent)).toEqual([
    "implementdeveloper · ×2",
    "reviewreviewer · 2/3",
    "◇ merge_okyou",
    "done",
  ]);
  expect(states[1].getAttribute("aria-current")).toBe("step");
  expect(states[1].className).toContain("current");
  expect(states[0].className).toContain("visited");
  expect(states[2].className).not.toContain("visited");
  const back = within(region).getByRole("list", { name: "Ways back" });
  expect(within(back).getAllByRole("listitem").map((one) => one.textContent)).toEqual([
    "↶ review –changes→ implement",
    "↶ review –again→ review",
    "↶ merge_ok –rejected→ implement",
  ]);
});

test("a run that waits for the human marks its state as waiting, and its open gate is answered on its page", async () => {
  const posted = serve({ runs: [WAITING], gates: [gate(41)] });
  open(runPath("lado", WAITING.name));
  const region = await page("feature/flows-tab");
  const current = within(region).getByRole("listitem", { name: "State merge_ok" });
  expect(current.className).toContain("waiting");
  const card = await within(region).findByRole("article", { name: "Gate #41" });
  expect(within(card).getByText("Merge it?")).toBeTruthy();
  fireEvent.change(within(card).getByRole("textbox"), { target: { value: "ship it" } });
  fireEvent.click(within(card).getByRole("button", { name: "Approve" }));
  await vi.waitFor(() =>
    expect(posted).toEqual([{ path: "/api/sessions/lado/gates/41/answer", body: { option: "approve", comment: "ship it" } }]),
  );
  // The run moves on when the feed brings it, whoever answered.
  stream().send("change", { kind: "gates", session: "lado", key: "41", op: "update", item: gate(41, { answer: "approve", answered_by: "human" }) }, "11");
  stream().send(
    "change",
    { kind: "runs", session: "lado", key: WAITING.name, op: "update", item: { ...WAITING, state: "done", status: "ended", acting: "", gate: null, ended_at: "2026-10-04T11:05:00.000Z" } },
    "12",
  );
  expect(within(region).queryByRole("article", { name: "Gate #41" })).toBeNull();
  expect(within(region).getByRole("listitem", { name: "State done" }).getAttribute("aria-current")).toBe("step");
});

test("in a stopped session the gate on the run's page cannot be answered", async () => {
  serve({ runs: [WAITING], gates: [gate(41)] });
  open(runPath("old", WAITING.name));
  const card = await screen.findByRole("article", { name: "Gate #41" });
  expect((within(card).getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(true);
});

test("the timeline has the run's start, every step in time and the step now, with acting as the core says it", async () => {
  serve({
    runs: [ACTIVE, WAITING],
    notes: [
      note(1, { summary: "built the bubble", body: "line 1\nline 2" }),
      note(2, { run: "feature/flows-tab", summary: "another run's note" }),
      note(3, { state: "review", actor: "reviewer", outcome: "changes", target: "implement", summary: "2 findings" }),
      note(4, { summary: "both fixed" }),
    ],
    events: [
      event(1, "flow_start", "at implement, kit lado-dev 0.7.0", "2026-10-04T10:02:00.000Z", { actor: "supervisor" }),
      event(2, "flow", "implement -done-> review", "2026-10-04T10:11:00.000Z"),
    ],
  });
  open(runPath("lado", ACTIVE.name));
  const steps = await within(await page("fix/gate-bubble")).findByRole("list", { name: "Steps" });
  const items = within(steps).getAllByRole("listitem");
  expect(items.map((one) => one.querySelector(".step-line")?.textContent)).toEqual([
    expect.stringMatching(/started by supervisor · at implement, kit lado-dev 0.7.0$/),
    expect.stringMatching(/implement · developer → done → review$/),
    expect.stringMatching(/review · reviewer → changes → implement$/),
    expect.stringMatching(/implement · developer → done → review$/),
    "now · review · reviewer · visit 2 of 3",
  ]);
  expect(within(items[1]).getByText("built the bubble").tagName).toBe("STRONG");
  expect(items[1].textContent).toContain("line 2");
  // The flow transition event is the step itself: not shown twice.
  expect(steps.textContent).not.toContain("-done->");
  // A new step comes from the feed.
  stream().send("change", { kind: "notes", session: "lado", key: "5", op: "insert", item: note(5, { state: "review", actor: "reviewer", outcome: "approved", target: "merge_ok", summary: "looks good" }) }, "11");
  expect(within(steps).getByText("looks good")).toBeTruthy();
});

test("a long note is cut with Show all", async () => {
  const body = Array.from({ length: 30 }, (_, i) => `line ${i + 1}`).join("\n\n");
  serve({ runs: [ACTIVE], notes: [note(1, { body })] });
  open(runPath("lado", ACTIVE.name));
  const steps = await within(await page("fix/gate-bubble")).findByRole("list", { name: "Steps" });
  expect(steps.textContent).not.toContain("line 30");
  fireEvent.click(within(steps).getByRole("button", { name: "Show all" }));
  expect(steps.textContent).toContain("line 30");
});

test("a note from before LADO kept steps has no outcome; the human's flow-set has none either", async () => {
  serve({
    runs: [ACTIVE],
    notes: [
      note(1, { actor: "", outcome: "", target: "", summary: "an old note" }),
      note(2, { state: "review", kind: "override", actor: "human", outcome: "", target: "implement", summary: "set by the human: redo" }),
    ],
  });
  open(runPath("lado", ACTIVE.name));
  const steps = await within(await page("fix/gate-bubble")).findByRole("list", { name: "Steps" });
  const lines = within(steps).getAllByRole("listitem").map((one) => one.querySelector(".step-line")?.textContent);
  expect(lines[0]).toMatch(/ · implement$/);
  expect(lines[1]).toMatch(/ · review · human → implement$/);
});

test("a step into a loop limit is followed by the loop gate's answer, and a waiting run's now names its gate", async () => {
  const atLimit = run("fix/gate-bubble", { status: "waiting", acting: "human", gate: 42, reason: "loop limit reached at review" });
  serve({
    runs: [atLimit],
    notes: [
      note(1, { state: "review", actor: "reviewer", outcome: "again", target: "review", summary: "second look" }),
      note(2, { state: "review", kind: "override", actor: "human", outcome: "continue", target: "review", summary: "continue: one more" }),
    ],
    gates: [gate(42, { run: "fix/gate-bubble", state: "review", kind: "loop", question: "loop limit reached at review: what next?", options: ["continue", "cancel"] })],
  });
  open(runPath("lado", atLimit.name));
  const region = await page("fix/gate-bubble");
  const steps = await within(region).findByRole("list", { name: "Steps" });
  const lines = within(steps).getAllByRole("listitem").map((one) => one.querySelector(".step-line")?.textContent);
  expect(lines).toEqual([
    expect.stringMatching(/review · reviewer → again → review$/),
    expect.stringMatching(/review · loop limit · human → continue → review$/),
    "now · review · waits for you (gate #42)",
  ]);
  expect(await within(region).findByRole("article", { name: "Gate #42" })).toBeTruthy();
});

test("an ended and a cancelled run end their timeline with the event as the core wrote it", async () => {
  serve({
    runs: [ENDED, CANCELLED],
    events: [
      event(7, "flow_end", "at done", "2026-10-03T09:00:00.000Z", { run: "fix/old" }),
      event(8, "flow_cancel", "not needed", "2026-10-03T10:00:00.000Z", { run: "fix/older", actor: "supervisor" }),
    ],
  });
  open(runPath("lado", "fix/old"));
  let steps = await within(await page("fix/old")).findByRole("list", { name: "Steps" });
  expect(within(steps).getAllByRole("listitem").map((one) => one.querySelector(".step-line")?.textContent)).toEqual([
    expect.stringMatching(/ended · at done$/),
  ]);
  cleanup();
  open(runPath("lado", "fix/older"));
  steps = await within(await page("fix/older")).findByRole("list", { name: "Steps" });
  expect(within(steps).getAllByRole("listitem").map((one) => one.querySelector(".step-line")?.textContent)).toEqual([
    expect.stringMatching(/cancelled by supervisor · not needed$/),
  ]);
});
