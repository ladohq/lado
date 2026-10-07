// The session's Artifacts tab (a table of its artifacts, newest first, with filters and a
// search; an artifact's page), the chips of attachments in the chat, on gates and in the
// Flows tab's notes, and the panel a chip opens over the page. Live from the feed.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { ArtifactInfo, AttachmentInfo, GateInfo, MessageInfo, NoteInfo, RunInfo, SessionInfo } from "./api";
import { App } from "./App";
import { artifact, attachment, FakeEventSource, FakeSocket, stream, wideColumn } from "./fakes";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

const NO_WAITS = { gates: 0, questions: 0, agents: 0 };
const SETTINGS = { kits: ["team"], provider: "claude", permission_mode: null, without: [], ran_seconds: 0, running_since: null, stopped_at: null };
const SESSIONS: SessionInfo[] = [{ name: "lado", repo: "/src/lado", status: "running", agents: 1, waiting: NO_WAITS, ...SETTINGS }];

const DESIGN = artifact({}, { created_at: "2026-10-07T12:00:00.000Z", summary: "first cut" });
const PLAN = artifact(
  { id: "a2", scope: "", name: "plan", full_name: "plan", title: "Plan of the week" },
  { id: "p1", hash: "hp", author: "supervisor", run: null, state: null, created_at: "2026-10-07T11:00:00.000Z" },
);
const SHOT = artifact(
  { id: "a3", scope: "fix/y", name: "shot.png", full_name: "fix/y/shot.png", title: null },
  { id: "s1", hash: "hs", media_type: "image/png", author: "developer", run: "fix/y", state: "build", created_at: "2026-10-07T13:00:00.000Z" },
);

function message(id: number, attachments: AttachmentInfo[], more: Partial<MessageInfo> = {}): MessageInfo {
  return {
    id,
    from: "architect",
    to: "human",
    kind: "message",
    summary: "The design is ready",
    body: "",
    state: "delivered",
    choices: null,
    free_answer: false,
    question_state: null,
    answered_by: null,
    reply_to: null,
    choice: null,
    reply_state: null,
    attachments,
    created_at: "2026-10-07T12:01:00.000Z",
    ...more,
  };
}

function note(id: number, more: Partial<NoteInfo> = {}): NoteInfo {
  return {
    id,
    run: "feature/x",
    state: "design",
    kind: "report",
    actor: "architect",
    outcome: "done",
    target: "design_ok",
    summary: "Design ready",
    body: "",
    attachments: [attachment()],
    created_at: "2026-10-07T12:01:00.000Z",
    ...more,
  };
}

function gate(more: Partial<GateInfo> = {}): GateInfo {
  return {
    id: 41,
    run: "feature/x",
    state: "design_ok",
    kind: "approval",
    question: "Approve the design?",
    options: ["approve", "reject"],
    note: "Design ready",
    note_body: "",
    attachments: [attachment()],
    reads: [],
    answer: null,
    comment: "",
    answered_by: null,
    created_at: "2026-10-07T12:02:00.000Z",
    answered_at: null,
    problem: null,
    ...more,
  };
}

const RUN = {
  name: "feature/x",
  flow: "feature",
  kit: { name: "team", version: "1.0.0", source: "project" },
  task: "Add x",
  state: "design_ok",
  status: "waiting",
  reason: "Approve the design?",
  acting: "human",
  visits: { design: 1, design_ok: 1 },
  gate: 41,
  worktree: "/w",
  branch: "lado/lado/feature-x",
  language: "",
  created_at: "2026-10-07T11:50:00.000Z",
  since: "2026-10-07T12:02:00.000Z",
  ended_at: null,
  states: [],
  problem: null,
} as RunInfo;

type Data = { artifacts?: ArtifactInfo[]; messages?: MessageInfo[]; gates?: GateInfo[]; notes?: NoteInfo[]; runs?: RunInfo[] };

function serve({ artifacts = [DESIGN, PLAN, SHOT], messages = [], gates = [], notes = [], runs = [] }: Data = {}) {
  const fetch = vi.fn(async (path: string) => {
    const of = (body: unknown) => new Response(JSON.stringify(body));
    if (path === "/api/sessions") return of(SESSIONS);
    if (path.endsWith("/artifacts")) return of(artifacts);
    if (path.includes("/records/") && path.endsWith("/content")) return new Response(`# Content of ${path.split("/")[5]}`);
    const record = /\/records\/([^/?]+)$/.exec(path)?.[1];
    if (record) {
      const found = artifacts.find((one) => one.latest.id === record) ?? DESIGN;
      return of({ artifact: found, record: { ...found.latest, id: record, hash: record === found.latest.id ? found.latest.hash : "old" } });
    }
    if (path.includes("/messages?")) return of({ items: messages, earlier: false });
    if (path.endsWith("/gates")) return of(gates);
    if (path.endsWith("/notes")) return of(notes);
    if (path.endsWith("/runs")) return of(runs);
    if (path.endsWith("/events") || path.endsWith("/agents")) return of([]);
    return new Response("{}", { status: 404 });
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

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

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: false, media: query, addEventListener: () => {}, removeEventListener: () => {} }));
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

const table = () => screen.findByRole("table", { name: "Artifacts" });
const names = (region: HTMLElement) =>
  within(region)
    .queryAllByRole("row")
    .slice(1)
    .map((row) => row.querySelector(".full-name")?.textContent);

// The tab

test("the tab lists the session's artifacts newest first with their columns", async () => {
  serve();
  open("/sessions/lado/artifacts");
  const shown = await table();
  expect(within(shown).getAllByRole("columnheader").map((one) => one.textContent)).toEqual([
    "Name",
    "Type",
    "Size",
    "Author",
    "Updated",
    "Latest change",
  ]);
  expect(names(shown)).toEqual(["fix/y/shot.png", "feature/x/design", "plan"]);
  const design = within(shown).getAllByRole("row")[2];
  expect(design.querySelector(".scope-part")?.textContent).toBe("feature/x/");
  expect(design.textContent).toContain("The design");
  expect(design.textContent).toContain("architect");
  expect(design.textContent).toContain("120 B");
  expect(design.textContent).toContain("first cut");
});

test("the tab filters by scope and type and finds by name, title, change and author", async () => {
  serve();
  open("/sessions/lado/artifacts");
  const shown = await table();
  fireEvent.change(screen.getByRole("combobox", { name: "Scope" }), { target: { value: "" } });
  expect(names(shown)).toEqual(["plan"]);
  fireEvent.change(screen.getByRole("combobox", { name: "Scope" }), { target: { value: "feature/x" } });
  expect(names(shown)).toEqual(["feature/x/design"]);
  fireEvent.change(screen.getByRole("combobox", { name: "Scope" }), { target: { value: "*" } });
  fireEvent.click(screen.getByRole("button", { name: "Images" }));
  expect(names(shown)).toEqual(["fix/y/shot.png"]);
  fireEvent.click(screen.getByRole("button", { name: "All types" }));
  const find = screen.getByRole("searchbox", { name: "Find an artifact" });
  fireEvent.change(find, { target: { value: "week" } });
  expect(names(shown)).toEqual(["plan"]);
  fireEvent.change(find, { target: { value: "first cut" } });
  expect(names(shown)).toEqual(["feature/x/design"]);
  fireEvent.change(find, { target: { value: "developer" } });
  expect(names(shown)).toEqual(["fix/y/shot.png"]);
  fireEvent.change(find, { target: { value: "nothing like it" } });
  expect(screen.getByText("No match")).toBeTruthy();
});

test("a session without artifacts says so", async () => {
  serve({ artifacts: [] });
  open("/sessions/lado/artifacts");
  expect(await screen.findByText("No artifacts yet")).toBeTruthy();
});

test("a row opens the artifact's page, which leads back to the tab", async () => {
  serve();
  open("/sessions/lado/artifacts");
  const shown = await table();
  fireEvent.click(within(shown).getByRole("link", { name: /feature\/x\/design/ }));
  expect(address()).toBe("/sessions/lado/artifacts/a1");
  await screen.findByRole("heading", { name: "Content of r1" });
  fireEvent.click(screen.getByRole("link", { name: "← Artifacts" }));
  expect(address()).toBe("/sessions/lado/artifacts");
});

test("a page of an older record says the artifact changed since and opens the latest", async () => {
  serve();
  open("/sessions/lado/artifacts/a1?record=r0");
  await screen.findByRole("heading", { name: "Content of r0" });
  fireEvent.click(screen.getByRole("button", { name: "Open latest" }));
  expect(address()).toBe("/sessions/lado/artifacts/a1");
  await screen.findByRole("heading", { name: "Content of r1" });
});

test("a page of an unknown artifact says so", async () => {
  serve();
  open("/sessions/lado/artifacts/nope");
  expect(await screen.findByText("No artifact nope in this session")).toBeTruthy();
});

// Chips and the panel

test("a chip on a message without a body opens the attached record in a panel; Esc closes it", async () => {
  serve({ messages: [message(7, [attachment()])] });
  open("/sessions/lado/activity");
  const chip = await screen.findByRole("button", { name: "Open artifact feature/x/design" });
  expect(chip.querySelector(".scope-part")?.textContent).toBe("feature/x/");
  chip.focus();
  fireEvent.click(chip);
  expect(address()).toBe("/sessions/lado/activity?view=r1");
  const panel = await screen.findByRole("dialog", { name: "Artifact feature/x/design" });
  await within(panel).findByRole("heading", { name: "Content of r1" });
  fireEvent.keyDown(panel, { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(address()).toBe("/sessions/lado/activity");
  expect(document.activeElement).toBe(screen.getByRole("button", { name: "Open artifact feature/x/design" }));
});

test("the panel leads to the artifact's page in the Artifacts tab", async () => {
  serve({ messages: [message(7, [attachment()])] });
  open("/sessions/lado/activity?view=r1");
  const panel = await screen.findByRole("dialog", { name: "Artifact feature/x/design" });
  fireEvent.click(within(panel).getByRole("link", { name: "Open in Artifacts tab" }));
  expect(address()).toBe("/sessions/lado/artifacts/a1?record=r1");
});

test("a chip of an artifact that changed since says so, live, and opens its latest", async () => {
  serve({ messages: [message(7, [attachment()], { body: "Look at it." })] });
  open("/sessions/lado/activity");
  await screen.findByRole("button", { name: "Open artifact feature/x/design" });
  expect(screen.queryByText(/changed since/)).toBeNull();
  const written = artifact({}, { id: "r2", hash: "h2", created_at: "2026-10-07T14:00:00.000Z" });
  act(() => stream().send("change", { kind: "artifacts", session: "lado", key: "a1", op: "update", item: written }));
  expect(await screen.findByText(/changed since/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Open latest feature/x/design" }));
  expect(address()).toBe("/sessions/lado/activity?view=r2");
});

const REVIEW = artifact(
  { id: "a4", name: "review", full_name: "feature/x/review", title: "The review" },
  { id: "v1", hash: "hv", author: "reviewer", state: "review", summary: "looks fine" },
);

const gateCard = async () => (await screen.findByText("Approve the design?")).closest(".chat-gate") as HTMLElement;

test("a gate shows its note with its chips, then the artifacts it reads by their latest records", async () => {
  serve({
    artifacts: [DESIGN, REVIEW, PLAN],
    gates: [gate({ note_body: "No questions.", reads: ["feature/x/review", "feature/x/mockup"] })],
  });
  open("/sessions/lado/activity");
  const card = await gateCard();
  const chip = within(card).getByRole("button", { name: "Open artifact feature/x/design" });
  expect(chip.querySelector(".scope-part")).toBeNull();
  expect(chip.textContent).toContain("design");
  const reads = await within(card).findByRole("list", { name: "Artifacts it reads" });
  expect(within(reads).getAllByRole("listitem").map((one) => one.textContent)).toEqual([
    expect.stringMatching(/^review.*The review — looks fine$/),
    "mockup: no record yet",
  ]);
  // The note, all of it, comes first; the artifacts it reads under it.
  const order = [card.querySelector(".gate-note"), reads];
  expect(order[0]!.compareDocumentPosition(order[1]!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(within(card).getByText("No questions.")).toBeTruthy();
  fireEvent.click(within(reads).getByRole("button", { name: "Open artifact feature/x/review" }));
  expect(await screen.findByRole("dialog", { name: "Artifact feature/x/review" })).toBeTruthy();
  expect(address()).toBe("/sessions/lado/activity?view=v1");
});

test("a write while the gate is open shows at once: a newer record, and its note's chip changed since", async () => {
  serve({ artifacts: [DESIGN, REVIEW], gates: [gate({ reads: ["feature/x/review"] })] });
  open("/sessions/lado/activity");
  const card = await gateCard();
  const reads = await within(card).findByRole("list", { name: "Artifacts it reads" });
  expect(reads.textContent).toContain("looks fine");
  const review = artifact(REVIEW, { ...REVIEW.latest, id: "v2", hash: "hv2", summary: "two nits" });
  act(() => stream().send("change", { kind: "artifacts", session: "lado", key: "a4", op: "update", item: review }));
  expect(await within(reads).findByText(/two nits/)).toBeTruthy();
  expect(within(card).queryByText(/changed since/)).toBeNull();
  const design = artifact({}, { id: "r2", hash: "h2", created_at: "2026-10-07T14:00:00.000Z" });
  act(() => stream().send("change", { kind: "artifacts", session: "lado", key: "a1", op: "update", item: design }));
  expect(await within(card).findByText(/changed since/)).toBeTruthy();
});

test("a note in a run's history carries its chips", async () => {
  serve({ runs: [RUN], notes: [note(3)], gates: [gate()] });
  open("/sessions/lado/flows/feature%2Fx");
  const chip = await screen.findByRole("button", { name: "Open artifact feature/x/design" });
  fireEvent.click(chip);
  expect(await screen.findByRole("dialog", { name: "Artifact feature/x/design" })).toBeTruthy();
});
