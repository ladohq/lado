// The waiting card (docs/design/ui.md, The waiting card): a tab per agent with open
// questions and per open gate, the picks of an agent's tab sent together, the gate's panel,
// the card expanded within its page. Its place in the chat and on Needs you: Chat.test.tsx,
// NeedsYou.test.tsx.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { GateInfo, MessageInfo, RecommendationInfo, RunInfo } from "./api";
import { avatar } from "./FeedRow";
import { columnWidth, FakeEventSource, FakeResizeObserver, FakeScreen } from "./fakes";
import { Live, LiveContext } from "./live";
import { WAITING_MIN } from "./prefs";
import { sendQuote, takePending } from "./quotes";
import { runColours } from "./Team";
import { WaitingCard, waitingTabs, type Focus } from "./WaitingCard";

function question(id: number, from: string, more: Partial<MessageInfo> = {}): MessageInfo {
  return {
    id,
    from,
    to: "human",
    kind: "question",
    summary: `Question ${id}?`,
    body: "",
    state: "delivered",
    choices: ["short", "long"],
    free_answer: true,
    question_state: "open",
    answered_by: null,
    reply_to: null,
    choice: null,
    reply_state: null,
    attachments: [],
    created_at: `2026-10-03T12:00:${String(id).padStart(2, "0")}.000Z`,
    recommendation: null,
    ...more,
  };
}

function gate(id: number, run: string, created_at: string, more: Partial<GateInfo> = {}): GateInfo {
  return {
    id,
    run,
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
    created_at,
    answered_at: null,
    closed_by_event: null,
    answer_attachments: [],
    problem: null,
    recommendation: null,
    ...more,
  };
}

function run(name: string): RunInfo {
  return { name } as RunInfo;
}

type Props = {
  questions: MessageInfo[];
  gates?: GateInfo[];
  runs?: RunInfo[] | null;
  stopped?: boolean;
  focus?: Focus;
  at?: string; // the address, the session's Activity tab by default
  chat?: { feed: number | null; loaded: boolean }; // in a session's chat (none on Needs you)
};

let posted: { path: string; body: unknown }[] = [];
let answer: { status: number; body: unknown } = { status: 200, body: { result: "sent" } };
// The human's files: the server's limits, each upload by its file name, those refused.
const LIMITS = {
  extensions: { png: "image/png", log: "text/plain" },
  text_types: [],
  agent_images: ["image/png"],
  max_size: 1000,
  max_files: 2,
  image_limit: 500,
  image_max_side: 8000,
  max_message: 20,
  max_title: 80,
};
let uploads: string[] = [];
let refusedUploads: Record<string, string> = {};
const made: string[] = [];
const revoked: string[] = [];

beforeEach(() => {
  localStorage.clear();
  posted = [];
  uploads = [];
  refusedUploads = {};
  made.length = 0;
  revoked.length = 0;
  answer = { status: 200, body: { result: "sent" } };
  FakeEventSource.all = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  let thumbs = 0;
  vi.stubGlobal(
    "URL",
    Object.assign(URL, {
      createObjectURL: () => {
        const url = `blob:thumb-${++thumbs}`;
        made.push(url);
        return url;
      },
      revokeObjectURL: (url: string) => revoked.push(url),
    }),
  );
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      if (path === "/api/limits") return new Response(JSON.stringify(LIMITS));
      const url = new URL(path, "http://lado");
      if (init?.method === "POST" && url.pathname.endsWith("/artifacts")) {
        const name = url.searchParams.get("file_name")!;
        uploads.push(name);
        if (refusedUploads[name]) return new Response(JSON.stringify({ detail: refusedUploads[name] }), { status: 500 });
        return new Response(JSON.stringify({ full_name: name.replace(/\.(\w+)$/, "-1a2b3c4d.$1") }));
      }
      if (init?.method === "POST") {
        posted.push({ path, body: JSON.parse(String(init.body)) });
        return new Response(JSON.stringify(answer.body), { status: answer.status });
      }
      return new Response("[]");
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function Card(props: Props) {
  const [live] = useState(() => new Live());
  return (
    <LiveContext.Provider value={live}>
      <MemoryRouter initialEntries={[props.at ?? "/sessions/s/activity"]}>
        <WaitingCard
          session="s"
          questions={props.questions}
          gates={props.gates ?? []}
          runs={props.runs === undefined ? [] : props.runs}
          stopped={props.stopped ?? false}
          focus={props.focus ?? null}
          chat={props.chat}
        />
      </MemoryRouter>
    </LiveContext.Provider>
  );
}

const show = (props: Props) => render(<Card {...props} />);
const card = () => screen.getByRole("region", { name: "What waits for you in s" });
const isExpanded = () => card().classList.contains("expanded");
const tab = (name: string) => within(card()).getByRole("tab", { name });
const selected = () => within(card()).getAllByRole("tab").filter((one) => one.getAttribute("aria-selected") === "true");
const send = () => within(card()).getByRole("button", { name: /^Send / }) as HTMLButtonElement;

test("three things wait: a tab per agent and per gate, in the order their first item was asked; the first shown", () => {
  const questions = [question(12, "supervisor"), question(13, "supervisor"), question(16, "developer")];
  const gates = [gate(1, "task/lad-27", "2026-10-03T12:00:14.000Z")];
  expect(waitingTabs(questions, gates).map((one) => one.key)).toEqual(["agent:supervisor", "gate:1", "agent:developer"]);
  show({ questions, gates });
  const tabs = within(card()).getAllByRole("tab");
  expect(tabs).toEqual([tab("supervisor 2"), tab("task/lad-27 1"), tab("developer 1")]);
  expect(selected()).toEqual([tab("supervisor 2")]);
  expect(within(card()).getByRole("tabpanel").getAttribute("aria-labelledby")).toBe(tab("supervisor 2").id);
});

test("nothing waits: no card", () => {
  const { container } = show({ questions: [] });
  expect(container.textContent).toBe("");
});

test("the colours of an agent and a run: the avatar's letter and colour, the Flows icon and a dashed top in the run's", () => {
  const runs = [run("task/lad-28"), run("task/lad-27")];
  show({ questions: [question(5, "developer")], gates: [gate(1, "task/lad-27", "2026-10-03T12:00:06.000Z")], runs });
  const developer = tab("developer 1");
  expect(developer.dataset.kind).toBe("agent");
  expect(developer.querySelector(".waiting-tab-avatar")?.textContent).toBe("D");
  expect(developer.style.getPropertyValue("--who")).toBe(`var(--avatar-${avatar("developer").colour})`);
  expect(developer.querySelector(".waiting-tab-count")?.textContent).toBe("1");
  const flow = tab("task/lad-27 1");
  expect(flow.dataset.kind).toBe("gate");
  expect(flow.querySelector(".waiting-tab-flow svg")).toBeTruthy();
  expect(flow.style.getPropertyValue("--who")).toBe(`var(--run-${runColours(runs).get("task/lad-27")})`);
});

test("before the runs load, a gate's tab is grey", () => {
  show({ questions: [], gates: [gate(1, "task/lad-27", "2026-10-03T12:00:06.000Z")], runs: null });
  expect(tab("task/lad-27 1").style.getPropertyValue("--who")).toBe("var(--line)");
});

test("a click shows a tab; a new question meanwhile adds to its tab and switches nothing; an emptied tab gives way to the first", () => {
  const first = [question(5, "supervisor"), question(6, "developer")];
  const view = show({ questions: first });
  fireEvent.click(tab("developer 1"));
  expect(selected()).toEqual([tab("developer 1")]);
  view.rerender(<Card questions={[...first, question(7, "supervisor")]} />);
  expect(selected()).toEqual([tab("developer 1")]);
  expect(tab("supervisor 2")).toBeTruthy();
  view.rerender(<Card questions={[question(5, "supervisor"), question(7, "supervisor")]} />);
  expect(selected()).toEqual([tab("supervisor 2")]);
});

test("until the human picks a tab the first one shows, also when an older item loads after the others", () => {
  const questions = [question(5, "supervisor")];
  const view = show({ questions });
  expect(selected()).toEqual([tab("supervisor 1")]);
  // The session's gates load after what waits: the gate, older, comes first.
  view.rerender(<Card questions={questions} gates={[gate(1, "ship/x", "2026-10-03T12:00:01.000Z")]} />);
  expect(selected()).toEqual([tab("ship/x 1")]);
});

test("two questions, one answered: Send is off and says how many are answered; a choice unpicks on a second click", () => {
  show({ questions: [question(5, "supervisor"), question(6, "supervisor")] });
  const [one, two] = within(card()).getAllByRole("listitem");
  expect(one.querySelector(".waiting-question-n")?.textContent).toBe("1.");
  expect(send().textContent).toBe("Send 2 answers to supervisor");
  expect(send().disabled).toBe(true);
  expect(within(card()).getByText("0 of 2 answered")).toBeTruthy();
  fireEvent.click(within(one).getByRole("button", { name: "short" }));
  expect(within(one).getByRole("button", { name: "short" }).getAttribute("aria-pressed")).toBe("true");
  expect(within(card()).getByText("1 of 2 answered")).toBeTruthy();
  expect(send().disabled).toBe(true);
  fireEvent.click(within(one).getByRole("button", { name: "short" }));
  expect(within(one).getByRole("button", { name: "short" }).getAttribute("aria-pressed")).toBe("false");
  expect(within(card()).getByText("0 of 2 answered")).toBeTruthy();
  fireEvent.click(within(two).getByRole("button", { name: "Skip" }));
  expect(within(card()).getByText("1 of 2 answered")).toBeTruthy();
});

test("all answered: a choice, Other… with own words, a Skip with a comment; one request with the tab's replies", async () => {
  show({ questions: [question(5, "supervisor"), question(6, "supervisor"), question(7, "supervisor")] });
  const [one, two, three] = within(card()).getAllByRole("listitem");
  fireEvent.click(within(one).getByRole("button", { name: "short" }));
  fireEvent.click(within(two).getByRole("button", { name: "Other…" }));
  const own = within(two).getByRole("textbox", { name: "Your own answer" });
  expect(document.activeElement).toBe(own);
  expect(send().disabled).toBe(true); // blank own words do not count
  fireEvent.change(own, { target: { value: "main, then rebase" } });
  fireEvent.click(within(three).getByRole("button", { name: "Skip" }));
  fireEvent.change(within(three).getByRole("textbox", { name: "Why you skip it (optional)" }), { target: { value: "later" } });
  expect(within(card()).queryByText(/of 3 answered/)).toBeNull();
  expect(send().disabled).toBe(false);
  fireEvent.click(send());
  await waitFor(() =>
    expect(posted).toEqual([
      {
        path: "/api/sessions/s/answers",
        body: {
          answers: [
            { question: 5, choice: "short", skip: false },
            { question: 6, text: "main, then rebase", skip: false },
            { question: 7, skip: true, text: "later" },
          ],
        },
      },
    ]),
  );
});

test("a choice, Other… and Skip exclude each other; a skip without a comment sends no text", async () => {
  show({ questions: [question(5, "w1")] });
  const item = within(card()).getByRole("listitem");
  expect(item.querySelector(".waiting-question-n")).toBeNull(); // one question: no number
  fireEvent.click(within(item).getByRole("button", { name: "short" }));
  fireEvent.click(within(item).getByRole("button", { name: "Other…" }));
  expect(within(item).getByRole("button", { name: "short" }).getAttribute("aria-pressed")).toBe("false");
  fireEvent.click(within(item).getByRole("button", { name: "Skip" }));
  expect(within(item).getByRole("button", { name: "Other…" }).getAttribute("aria-pressed")).toBe("false");
  expect(within(item).queryByRole("textbox", { name: "Your own answer" })).toBeNull();
  fireEvent.click(send());
  expect(send().textContent).toBe("Send answer to w1");
  await waitFor(() => expect(posted).toEqual([{ path: "/api/sessions/s/answers", body: { answers: [{ question: 5, skip: true }] } }]));
});

test("typing keeps the focus and every character", () => {
  show({ questions: [question(5, "w1")] });
  fireEvent.click(within(card()).getByRole("button", { name: "Other…" }));
  const field = within(card()).getByRole("textbox", { name: "Your own answer" }) as HTMLTextAreaElement;
  fireEvent.change(field, { target: { value: "m" } });
  fireEvent.change(field, { target: { value: "ma" } });
  expect(document.activeElement).toBe(field);
  expect((within(card()).getByRole("textbox", { name: "Your own answer" }) as HTMLTextAreaElement).value).toBe("ma");
});

// A field's height by its text, jsdom having no layout: its scrollHeight `content`, its
// line 20 pixels (the rule's own when the style has none) and no padding.
function grows(field: HTMLTextAreaElement, content: number, value: string) {
  Object.defineProperty(field, "scrollHeight", { configurable: true, get: () => content });
  fireEvent.change(field, { target: { value } });
  return [field.style.height, field.style.overflowY];
}

test("an own answer, a skip's comment and a gate's comment grow with their text from 3 lines to 8, then scroll", () => {
  show({
    questions: [question(5, "w1"), question(6, "w1")],
    gates: [gate(1, "task/lad-27", "2026-10-03T12:00:06.000Z")],
  });
  const [one, two] = within(card()).getAllByRole("listitem");
  fireEvent.click(within(one).getByRole("button", { name: "Other…" }));
  const own = within(one).getByRole("textbox", { name: "Your own answer" }) as HTMLTextAreaElement;
  expect(grows(own, 20, "short")).toEqual(["60px", "hidden"]);
  expect(grows(own, 100, "five\nlines")).toEqual(["100px", "hidden"]);
  expect(grows(own, 400, "many\nlines\n".repeat(10))).toEqual(["160px", "auto"]);
  fireEvent.click(within(two).getByRole("button", { name: "Skip" }));
  const skip = within(two).getByRole("textbox", { name: "Why you skip it (optional)" }) as HTMLTextAreaElement;
  expect(grows(skip, 400, "many\nlines\n".repeat(10))).toEqual(["160px", "auto"]);
  fireEvent.click(tab("task/lad-27 1"));
  const comment = within(card()).getByRole("textbox", { name: "Comment for the next step (optional)" }) as HTMLTextAreaElement;
  expect(grows(comment, 20, "fine")).toEqual(["60px", "hidden"]);
  expect(grows(comment, 400, "many\nlines\n".repeat(10))).toEqual(["160px", "auto"]);
});

function given(choice: string | null, text = "Long: the short one loses data"): RecommendationInfo {
  return { state: "given", text, choice, disagrees: false, by: "w1", at: "2026-10-03T12:01:00.000Z" };
}

test("the supervisor's recommendation shows on its question, its choice picked ahead; the human can unpick or change it", async () => {
  show({
    questions: [
      question(5, "w1", { recommendation: given("long") }),
      question(6, "w1", { recommendation: given(null, "Port 8123: 8080 is taken") }),
      question(7, "w1", { recommendation: { ...given(null), state: "asked", text: "" } }),
    ],
  });
  const [one, two, three] = within(card()).getAllByRole("listitem");
  expect(within(one).getByRole("region", { name: "Supervisor's recommendation" }).textContent).toContain("the short one loses data");
  expect(within(two).getByRole("region", { name: "Supervisor's recommendation" }).textContent).toContain("8080 is taken");
  expect(within(three).getByRole("region", { name: "Supervisor's recommendation" }).textContent).toContain("preparing");
  expect(within(one).getByRole("button", { name: "long" }).getAttribute("aria-pressed")).toBe("true");
  expect(within(two).getAllByRole("button").filter((b) => b.getAttribute("aria-pressed") === "true")).toEqual([]);
  expect(within(card()).getByText("1 of 3 answered")).toBeTruthy();
  fireEvent.click(within(one).getByRole("button", { name: "long" })); // unpicked: stays unpicked
  expect(within(one).getByRole("button", { name: "long" }).getAttribute("aria-pressed")).toBe("false");
  expect(within(card()).getByText("0 of 3 answered")).toBeTruthy();
  fireEvent.click(within(one).getByRole("button", { name: "short" }));
  fireEvent.click(within(two).getByRole("button", { name: "Skip" }));
  fireEvent.click(within(three).getByRole("button", { name: "Skip" }));
  fireEvent.click(send());
  await waitFor(() =>
    expect(posted[0]?.body).toEqual({
      answers: [
        { question: 5, choice: "short", skip: false },
        { question: 6, skip: true },
        { question: 7, skip: true },
      ],
    }),
  );
});

test("the recommended choice is sent as it is when the human leaves it; a recommendation that comes later picks it then", async () => {
  const { rerender } = show({ questions: [question(5, "w1", { recommendation: { ...given(null), state: "asked", text: "" } })] });
  expect(send().disabled).toBe(true);
  rerender(<Card questions={[question(5, "w1", { recommendation: given("short") })]} />);
  expect(within(card()).getByRole("button", { name: "short" }).getAttribute("aria-pressed")).toBe("true");
  fireEvent.click(send());
  await waitFor(() => expect(posted[0]?.body).toEqual({ answers: [{ question: 5, choice: "short", skip: false }] }));
});

test("a recommended choice the question does not have picks nothing", () => {
  show({ questions: [question(5, "w1", { recommendation: given("maybe") })] });
  expect(within(card()).getAllByRole("button").filter((b) => b.getAttribute("aria-pressed") === "true")).toEqual([]);
  expect(send().disabled).toBe(true);
});

test("a question that takes no own answer has its choices and Skip, no Other…", () => {
  show({ questions: [question(5, "w1", { free_answer: false })] });
  const buttons = within(within(card()).getByRole("group")).getAllByRole("button");
  expect(buttons.map((one) => one.textContent)).toEqual(["short", "long", "Skip"]);
});

test("a question's details are Markdown and its attachments chips", () => {
  const attachment = {
    artifact: "a1",
    record: "r1",
    full_name: "plan",
    name: "plan",
    scope: "",
    title: "",
    media_type: "text/markdown",
    size: 10,
    changed: false,
    hash: "h",
  };
  show({ questions: [question(5, "w1", { body: "Pick **one**.", attachments: [attachment] as MessageInfo["attachments"] })] });
  expect(within(card()).getByText("one").tagName).toBe("STRONG");
  expect(within(card()).getByRole("button", { name: "Open artifact plan" })).toBeTruthy();
});

test("a refusal shows on the tab with the core's reason; the picks stay; a question closed meanwhile drops its pick", async () => {
  answer = { status: 400, body: { detail: "question #6 is answered" } };
  const questions = [question(5, "supervisor"), question(6, "supervisor")];
  const view = show({ questions });
  const [one, two] = within(card()).getAllByRole("listitem");
  fireEvent.click(within(one).getByRole("button", { name: "short" }));
  fireEvent.click(within(two).getByRole("button", { name: "long" }));
  fireEvent.click(send());
  expect((await within(card()).findByRole("alert")).textContent).toBe("question #6 is answered");
  expect(within(one).getByRole("button", { name: "short" }).getAttribute("aria-pressed")).toBe("true");
  view.rerender(<Card questions={[questions[0]]} />);
  expect(within(within(card()).getByRole("listitem")).getByRole("button", { name: "short" }).getAttribute("aria-pressed")).toBe("true");
  expect(send().disabled).toBe(false);
});

test("a gate's tab is its panel: question, note, comment, its buttons in the Send row, answered at once", async () => {
  show({ questions: [], gates: [gate(1, "task/lad-27", "2026-10-03T12:00:06.000Z", { problem: "no flow" })] });
  const panel = within(card()).getByRole("tabpanel");
  expect(within(panel).getByText("Approve the design?")).toBeTruthy();
  expect(within(panel).getByText("design ready")).toBeTruthy();
  expect(within(panel).getByText("Artifacts it reads cannot be shown: no flow")).toBeTruthy();
  const row = panel.querySelector(".waiting-send") as HTMLElement;
  expect(within(row).getAllByRole("button").map((one) => one.textContent)).toEqual(["Approve", "Reject"]);
  fireEvent.change(within(panel).getByRole("textbox", { name: "Comment for the next step (optional)" }), { target: { value: "fine" } });
  fireEvent.click(within(row).getByRole("button", { name: "Approve" }));
  await waitFor(() => expect(posted).toEqual([{ path: "/api/sessions/s/gates/1/answer", body: { option: "approve", comment: "fine" } }]));
});

test("an expanded card folds on a quote of its session, not of another", async () => {
  show({ questions: [question(5, "w1")] });
  fireEvent.click(within(card()).getByRole("button", { name: "Expand the card" }));
  await waitFor(() => expect(isExpanded()).toBe(true));
  act(() => sendQuote("other", "> A", () => {}));
  expect(isExpanded()).toBe(true);
  act(() => sendQuote("s", "> A", () => {}));
  await waitFor(() => expect(isExpanded()).toBe(false));
  takePending("s");
  takePending("other");
});

test("a gate's comment and an own answer stay through a switch of tabs and through expanding and folding the card", async () => {
  show({ questions: [question(5, "w1")], gates: [gate(1, "task/lad-27", "2026-10-03T12:00:06.000Z")] });
  const comment = () => within(card()).getByRole("textbox", { name: "Comment for the next step (optional)" }) as HTMLTextAreaElement;
  const own = () => within(card()).getByRole("textbox", { name: "Your own answer" }) as HTMLTextAreaElement;
  fireEvent.click(within(card()).getByRole("button", { name: "Other…" }));
  fireEvent.change(own(), { target: { value: "after the tag" } });
  fireEvent.click(tab("task/lad-27 1"));
  fireEvent.change(comment(), { target: { value: "check the migration" } });
  fireEvent.click(tab("w1 1"));
  expect(own().value).toBe("after the tag");
  fireEvent.click(tab("task/lad-27 1"));
  expect(comment().value).toBe("check the migration");
  fireEvent.click(within(card()).getByRole("button", { name: "Expand the card" }));
  await waitFor(() => expect(isExpanded()).toBe(true));
  expect(comment().value).toBe("check the migration");
  fireEvent.click(within(card()).getByRole("button", { name: "Collapse the card" }));
  await waitFor(() => expect(isExpanded()).toBe(false));
  expect(comment().value).toBe("check the migration");
  fireEvent.click(tab("w1 1"));
  expect(own().value).toBe("after the tag");
  fireEvent.click(tab("task/lad-27 1"));
  fireEvent.click(within(card()).getByRole("button", { name: "Approve" }));
  await waitFor(() =>
    expect(posted).toEqual([{ path: "/api/sessions/s/gates/1/answer", body: { option: "approve", comment: "check the migration" } }]),
  );
});

test("in a stopped session the gate's buttons are off and say why", () => {
  show({ questions: [], gates: [gate(1, "task/lad-27", "2026-10-03T12:00:06.000Z")], stopped: true });
  const panel = within(card()).getByRole("tabpanel");
  expect((within(panel).getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(true);
  expect(within(panel).getByText("The session is stopped: resume it to answer.")).toBeTruthy();
});

test("focus shows the item's tab and marks the item for a moment", async () => {
  vi.useFakeTimers();
  try {
    const questions = [question(5, "supervisor"), question(6, "developer")];
    const view = show({ questions });
    view.rerender(<Card questions={questions} focus={{ key: "agent:developer", item: 6, at: 1 }} />);
    expect(selected()).toEqual([tab("developer 1")]);
    expect(card().querySelector('[data-item="6"]')?.className).toContain("marked");
    act(() => vi.advanceTimersByTime(1600));
    expect(card().querySelector('[data-item="6"]')?.className).not.toContain("marked");
  } finally {
    vi.useRealTimers();
  }
});

test("expanded in its place and back: the expand icon, then Esc or the fold icon; the focus returns", async () => {
  const { container } = show({ questions: [question(5, "w1")] });
  const expand = within(card()).getByRole("button", { name: "Expand the card" });
  expect(expand.getAttribute("aria-expanded")).toBe("false");
  // Esc while it is not expanded does nothing to it.
  fireEvent.keyDown(document, { key: "Escape" });
  expect(isExpanded()).toBe(false);
  fireEvent.click(expand);
  await waitFor(() => expect(isExpanded()).toBe(true));
  // In its page, where it was: no portal, no overlay, no modal dialog.
  expect(container.contains(card())).toBe(true);
  expect(document.querySelector(".waiting-overlay")).toBeNull();
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(card().getAttribute("aria-modal")).toBeNull();
  const collapse = within(card()).getByRole("button", { name: "Collapse the card" });
  expect(collapse.getAttribute("aria-expanded")).toBe("true");
  expect(document.activeElement).toBe(within(card()).getByRole("tab", { name: "w1 1" }));
  fireEvent.keyDown(document, { key: "Escape" });
  await waitFor(() => expect(isExpanded()).toBe(false));
  expect(document.activeElement).toBe(within(card()).getByRole("button", { name: "Expand the card" }));
  fireEvent.click(within(card()).getByRole("button", { name: "Expand the card" }));
  await waitFor(() => expect(isExpanded()).toBe(true));
  fireEvent.click(within(card()).getByRole("button", { name: "Collapse the card" }));
  await waitFor(() => expect(isExpanded()).toBe(false));
  expect(document.activeElement).toBe(within(card()).getByRole("button", { name: "Expand the card" }));
});

test("while an artifact panel is open (?view= in the address), Esc leaves the expanded card to the panel", async () => {
  show({ questions: [question(5, "w1")], at: "/sessions/s/activity?view=r1" });
  fireEvent.click(within(card()).getByRole("button", { name: "Expand the card" }));
  await waitFor(() => expect(isExpanded()).toBe(true));
  fireEvent.keyDown(document, { key: "Escape" });
  expect(isExpanded()).toBe(true);
});

test("the expanded card folds itself when nothing waits any more", async () => {
  const view = show({ questions: [question(5, "w1")] });
  fireEvent.click(within(card()).getByRole("button", { name: "Expand the card" }));
  await waitFor(() => expect(isExpanded()).toBe(true));
  view.rerender(<Card questions={[]} />);
  expect(screen.queryByRole("region", { name: "What waits for you in s" })).toBeNull();
  view.rerender(<Card questions={[question(6, "w1")]} />);
  expect(isExpanded()).toBe(false);
});

// Minimized and resized: only in a session's chat (`chat`).
const IN_CHAT = { feed: null, loaded: true };
const GATE_812 = gate(812, "task/lad-52", "2026-10-03T12:00:01.000Z", {
  question: "Archive the change and merge the pull request?",
});
const iconButton = (name: string) => within(card()).getByRole("button", { name });
const line = () => card().querySelector<HTMLButtonElement>(".waiting-line");
const isMinimized = () => card().classList.contains("minimized");
const edge = () => within(card()).queryByRole("separator", { name: "Resize the card" });

test("in a session's chat the card minimizes to its tabs and one line; the icon, the line or a tab restores it", async () => {
  const questions = [question(5, "supervisor", { summary: "Merge now?" })];
  show({ questions, gates: [GATE_812], chat: IN_CHAT });
  // The pair of icons: Minimize left of Expand.
  const icons = within(card().querySelector(".waiting-actions") as HTMLElement).getAllByRole("button");
  expect(icons.map((one) => one.getAttribute("aria-label"))).toEqual(["Minimize the card", "Expand the card"]);
  fireEvent.click(tab("task/lad-52 1"));
  fireEvent.click(iconButton("Minimize the card"));
  expect(isMinimized()).toBe(true);
  // Its tabs, none shown, and the shown tab's question on one line; no panel, no buttons.
  expect(within(card()).getAllByRole("tab")).toEqual([tab("task/lad-52 1"), tab("supervisor 1")]);
  expect(selected()).toEqual([]);
  expect(line()?.textContent).toBe("Archive the change and merge the pull request?");
  expect(within(card()).queryByRole("tabpanel")).toBeNull();
  expect(within(card()).queryByRole("button", { name: "Approve" })).toBeNull();
  expect(within(card()).queryByRole("textbox")).toBeNull();
  expect(edge()).toBeNull();
  const restore = iconButton("Restore the card");
  expect(restore.getAttribute("aria-expanded")).toBe("false");
  expect(document.activeElement).toBe(restore);
  // The icon restores, the focus on Minimize.
  fireEvent.click(restore);
  expect(isMinimized()).toBe(false);
  expect(selected()).toEqual([tab("task/lad-52 1")]);
  expect(iconButton("Minimize the card").getAttribute("aria-expanded")).toBe("true");
  expect(document.activeElement).toBe(iconButton("Minimize the card"));
  // The line restores, the focus on Minimize.
  fireEvent.click(iconButton("Minimize the card"));
  fireEvent.click(line()!);
  expect(isMinimized()).toBe(false);
  expect(within(card()).getByRole("button", { name: "Approve" })).toBeTruthy();
  expect(document.activeElement).toBe(iconButton("Minimize the card"));
  // A tab restores and shows itself.
  fireEvent.click(iconButton("Minimize the card"));
  fireEvent.click(tab("supervisor 1"));
  expect(isMinimized()).toBe(false);
  expect(selected()).toEqual([tab("supervisor 1")]);
});

test("a minimized agent's tab shows its first question on the line", () => {
  show({ questions: [question(5, "w1", { summary: "First?" }), question(6, "w1", { summary: "Second?" })], chat: IN_CHAT });
  fireEvent.click(iconButton("Minimize the card"));
  expect(line()?.textContent).toBe("First?");
});

test("a new tab restores a minimized card, the shown tab kept; a question added to a tab does not", () => {
  const view = show({ questions: [question(5, "supervisor")], gates: [GATE_812], chat: IN_CHAT });
  fireEvent.click(tab("task/lad-52 1"));
  fireEvent.click(iconButton("Minimize the card"));
  // One more question in the supervisor's tab: still minimized, the tab's count says so.
  const more = [question(5, "supervisor"), question(6, "supervisor")];
  view.rerender(<Card questions={more} gates={[GATE_812]} chat={IN_CHAT} />);
  expect(isMinimized()).toBe(true);
  expect(tab("supervisor 2")).toBeTruthy();
  // A gate of another run: restored, with the tab the human chose.
  const other = gate(813, "task/lad-53", "2026-10-03T12:00:09.000Z");
  view.rerender(<Card questions={more} gates={[GATE_812, other]} chat={IN_CHAT} />);
  expect(isMinimized()).toBe(false);
  expect(within(card()).getAllByRole("tab")).toHaveLength(3);
  expect(selected()).toEqual([tab("task/lad-52 1")]);
  expect(localStorage.getItem("lado.waitingMinimized.s")).toBeNull(); // forgotten
  // An agent with no tab before asks: restored too.
  fireEvent.click(iconButton("Minimize the card"));
  view.rerender(<Card questions={[...more, question(7, "developer")]} gates={[GATE_812, other]} chat={IN_CHAT} />);
  expect(isMinimized()).toBe(false);
});

test("an agent whose tab went away asks again: a new tab, so a minimized card restores itself", () => {
  const view = show({ questions: [question(5, "supervisor")], gates: [GATE_812], chat: IN_CHAT });
  fireEvent.click(iconButton("Minimize the card"));
  view.rerender(<Card questions={[]} gates={[GATE_812]} chat={IN_CHAT} />); // answered elsewhere
  expect(isMinimized()).toBe(true);
  expect(JSON.parse(localStorage.getItem("lado.waitingMinimized.s") ?? "null")).toEqual(["gate:812"]);
  view.rerender(<Card questions={[question(9, "supervisor")]} gates={[GATE_812]} chat={IN_CHAT} />);
  expect(isMinimized()).toBe(false);
});

test("when nothing waits any more the minimized card is forgotten, so the next question shows whole", () => {
  const view = show({ questions: [question(5, "supervisor")], chat: IN_CHAT });
  fireEvent.click(iconButton("Minimize the card"));
  view.rerender(<Card questions={[]} chat={IN_CHAT} />);
  expect(localStorage.getItem("lado.waitingMinimized.s")).toBeNull();
  view.rerender(<Card questions={[question(9, "supervisor")]} chat={IN_CHAT} />);
  expect(isMinimized()).toBe(false);
});

test("what waits not loaded yet forgets nothing of a minimized card", () => {
  localStorage.setItem("lado.waitingMinimized.s", JSON.stringify(["gate:812", "agent:supervisor"]));
  const loading = { feed: null, loaded: false };
  // The questions came, the gates not yet: then both.
  const view = show({ questions: [question(5, "supervisor")], gates: [], chat: loading });
  expect(isMinimized()).toBe(true);
  view.rerender(<Card questions={[question(5, "supervisor")]} gates={[GATE_812]} chat={IN_CHAT} />);
  expect(isMinimized()).toBe(true);
  expect(JSON.parse(localStorage.getItem("lado.waitingMinimized.s") ?? "null")).toEqual(["gate:812", "agent:supervisor"]);
  // Nothing loaded: nothing forgotten either.
  view.rerender(<Card questions={[]} gates={[]} chat={loading} />);
  expect(localStorage.getItem("lado.waitingMinimized.s")).not.toBeNull();
});

test("a minimized card stays minimized when it is drawn again (a reload), while its tabs are the same or fewer", () => {
  const view = show({ questions: [question(5, "supervisor")], gates: [GATE_812], chat: IN_CHAT });
  fireEvent.click(iconButton("Minimize the card"));
  const stored = JSON.parse(localStorage.getItem("lado.waitingMinimized.s") ?? "null");
  expect(stored).toEqual(["gate:812", "agent:supervisor"]);
  view.unmount();
  show({ questions: [], gates: [GATE_812], chat: IN_CHAT }); // the question was answered elsewhere
  expect(isMinimized()).toBe(true);
  fireEvent.click(iconButton("Restore the card"));
  expect(localStorage.getItem("lado.waitingMinimized.s")).toBeNull();
});

test("a minimized card expands whole; folding it brings it back minimized", async () => {
  show({ questions: [], gates: [GATE_812], chat: IN_CHAT });
  fireEvent.click(iconButton("Minimize the card"));
  fireEvent.click(iconButton("Expand the card"));
  await waitFor(() => expect(isExpanded()).toBe(true));
  expect(isMinimized()).toBe(false);
  expect(within(card()).getByRole("button", { name: "Approve" })).toBeTruthy();
  expect(within(card()).queryByRole("button", { name: /^(Minimize|Restore) the card$/ })).toBeNull();
  fireEvent.keyDown(document, { key: "Escape" });
  await waitFor(() => expect(isExpanded()).toBe(false));
  expect(isMinimized()).toBe(true);
  expect(document.activeElement).toBe(iconButton("Expand the card"));
});

test("on Needs you (no chat) the card has no minimize icon and no edge, whatever its chat keeps", () => {
  localStorage.setItem("lado.waitingMinimized.s", JSON.stringify(["gate:812"]));
  localStorage.setItem("lado.waitingHeight", "230");
  show({ questions: [], gates: [GATE_812] });
  expect(isMinimized()).toBe(false);
  expect(within(card()).queryByRole("button", { name: /^(Minimize|Restore) the card$/ })).toBeNull();
  expect(edge()).toBeNull();
  expect(card().style.getPropertyValue("--waiting-height")).toBe("");
});

test("in the chat an edge above the card sets its height in its bounds, kept for every session; a double click forgets it", () => {
  columnWidth(null);
  show({ questions: [], gates: [GATE_812], chat: { feed: 400, loaded: true } });
  FakeResizeObserver.resize(
    () => 800,
    () => 300, // the card, laid out by the stylesheet
  );
  const separator = edge()!;
  expect(separator.getAttribute("aria-orientation")).toBe("horizontal");
  // As laid out until the human moves it: the card and the feed share 700 px, the feed keeps 160.
  expect([separator.getAttribute("aria-valuenow"), separator.getAttribute("aria-valuemax")]).toEqual(["300", "540"]);
  expect(card().style.getPropertyValue("--waiting-height")).toBe("");
  fireEvent.keyDown(separator, { key: "ArrowDown" });
  expect(card().style.getPropertyValue("--waiting-height")).toBe("260px");
  expect(localStorage.getItem("lado.waitingHeight")).toBe("260");
  fireEvent.pointerDown(separator, { clientY: 500 });
  fireEvent.pointerMove(separator, { clientY: 100 });
  expect(card().style.getPropertyValue("--waiting-height")).toBe("540px"); // no higher
  fireEvent.pointerUp(separator);
  fireEvent.doubleClick(separator);
  expect(card().style.getPropertyValue("--waiting-height")).toBe("");
  expect(localStorage.getItem("lado.waitingHeight")).toBeNull();
});

test("dragged below the least height the card minimizes when the edge is let go, not before; the keys at once", () => {
  columnWidth(null);
  const view = show({ questions: [], gates: [GATE_812], chat: { feed: 400, loaded: true } });
  FakeResizeObserver.resize(
    () => 800,
    () => 300,
  );
  let separator = edge()!;
  fireEvent.pointerDown(separator, { clientY: 100 });
  fireEvent.pointerMove(separator, { clientY: 400 }); // 0: below its least height
  expect(isMinimized()).toBe(false);
  expect(card().style.getPropertyValue("--waiting-height")).toBe(`${WAITING_MIN}px`);
  fireEvent.pointerMove(separator, { clientY: 150 }); // back up before the release
  fireEvent.pointerUp(separator);
  expect(isMinimized()).toBe(false);
  expect(card().style.getPropertyValue("--waiting-height")).toBe("250px");
  fireEvent.pointerDown(separator, { clientY: 100 });
  fireEvent.pointerMove(separator, { clientY: 400 });
  fireEvent.pointerUp(separator);
  expect(isMinimized()).toBe(true);
  expect(document.activeElement).toBe(iconButton("Restore the card"));
  // The keys: below the least height minimizes at once.
  fireEvent.click(iconButton("Restore the card"));
  view.rerender(<Card questions={[]} gates={[GATE_812]} chat={{ feed: 400, loaded: true }} />);
  separator = edge()!;
  for (let i = 0; i < 3 && !isMinimized(); i++) fireEvent.keyDown(edge()!, { key: "ArrowDown" });
  expect(isMinimized()).toBe(true);
});

test("a stored height too tall for the chat shows lower and is kept; dragged below the least height the card minimizes", () => {
  localStorage.setItem("lado.waitingHeight", "600");
  columnWidth(null);
  show({ questions: [], gates: [GATE_812], chat: { feed: 160, loaded: true } });
  FakeResizeObserver.resize(
    () => 800,
    () => 400,
  );
  expect(card().style.getPropertyValue("--waiting-height")).toBe("400px"); // 160 + 400 - 160
  expect(localStorage.getItem("lado.waitingHeight")).toBe("600");
  const separator = edge()!;
  fireEvent.pointerDown(separator, { clientY: 100 });
  fireEvent.pointerMove(separator, { clientY: 100 + 400 - WAITING_MIN });
  expect(isMinimized()).toBe(false);
  expect(card().style.getPropertyValue("--waiting-height")).toBe(`${WAITING_MIN}px`);
  fireEvent.pointerMove(separator, { clientY: 100 + 400 - WAITING_MIN + 1 });
  expect(isMinimized()).toBe(false); // until the edge is let go
  fireEvent.pointerUp(separator);
  expect(isMinimized()).toBe(true);
  expect(localStorage.getItem("lado.waitingHeight")).toBe(String(WAITING_MIN)); // kept for the restore
  expect(document.activeElement).toBe(iconButton("Restore the card"));
});

// The human's files in the card's fields (docs/design/ui.md, The waiting card: Fields).

const file = (name: string, bytes = 10, type = "") => new File(["x".repeat(bytes)], name, { type });
const questionItem = (id: number) => card().querySelector(`[data-item="${id}"]`) as HTMLElement;
const chipsIn = (where: HTMLElement) => Array.from(where.querySelectorAll(".file-chip .file-name")).map((one) => one.textContent);

async function attach(where: HTMLElement, ...files: File[]) {
  const clip = within(where).getByRole("button", { name: "Attach files" });
  await waitFor(() => expect(clip.getAttribute("title")).toContain("up to 2 files")); // the limits are loaded
  fireEvent.change(clip.parentElement!.querySelector("input[type=file]")!, { target: { files } });
}

test("Other… of files only is an answer: Send uploads them, then answers with their names; a choice takes no files", async () => {
  show({ questions: [question(5, "w1"), question(6, "w1")] });
  const [one, two] = [questionItem(5), questionItem(6)];
  fireEvent.click(within(one).getByRole("button", { name: "short" }));
  expect(within(one).queryByRole("button", { name: "Attach files" })).toBeNull();
  fireEvent.click(within(two).getByRole("button", { name: "Other…" }));
  expect(send().disabled).toBe(true);
  await attach(two, file("shot.png", 10, "image/png"));
  expect(chipsIn(two)).toEqual(["shot.png"]);
  expect(send().disabled).toBe(false);
  fireEvent.click(send());
  await waitFor(() =>
    expect(posted).toEqual([
      {
        path: "/api/sessions/s/answers",
        body: {
          answers: [
            { question: 5, choice: "short", skip: false },
            { question: 6, text: "", skip: false, artifacts: ["shot-1a2b3c4d.png"] },
          ],
        },
      },
    ]),
  );
  expect(uploads).toEqual(["shot.png"]);
});

test("the card loads the limits: a file attached as soon as Other… shows has its type and thumbnail", async () => {
  show({ questions: [question(5, "w1")] });
  await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([path]) => path === "/api/limits")).toBe(true));
  await act(async () => {}); // the limits are in
  fireEvent.click(within(questionItem(5)).getByRole("button", { name: "Other…" }));
  const input = questionItem(5).querySelector("input[type=file]")!;
  fireEvent.change(input, { target: { files: [file("shot.png", 10, "image/png")] } });
  expect(questionItem(5).querySelector(".file-chip img")?.getAttribute("src")).toBe("blob:thumb-1");
  expect(questionItem(5).querySelector(".file-unseen")).toBeNull();
});

test("the files stay with their question from Other… to Skip and through a switch of tabs; a question closed elsewhere drops them", async () => {
  const gates = [gate(1, "task/lad-27", "2026-10-03T12:00:30.000Z")];
  const view = show({ questions: [question(5, "w1")], gates });
  fireEvent.click(within(questionItem(5)).getByRole("button", { name: "Other…" }));
  await attach(questionItem(5), file("shot.png", 10, "image/png"));
  fireEvent.click(within(questionItem(5)).getByRole("button", { name: "Skip" }));
  expect(chipsIn(questionItem(5))).toEqual(["shot.png"]);
  fireEvent.click(tab("task/lad-27 1"));
  fireEvent.click(tab("w1 1"));
  expect(chipsIn(questionItem(5))).toEqual(["shot.png"]);
  fireEvent.click(send());
  await waitFor(() =>
    expect(posted.at(-1)?.body).toEqual({ answers: [{ question: 5, skip: true, artifacts: ["shot-1a2b3c4d.png"] }] }),
  );
  expect(revoked).toEqual([]);
  view.rerender(<Card questions={[question(7, "w1")]} gates={gates} />);
  await waitFor(() => expect(revoked).toEqual(["blob:thumb-1"]));
  fireEvent.click(within(questionItem(7)).getByRole("button", { name: "Other…" }));
  expect(chipsIn(questionItem(7))).toEqual([]);
});

test("a file dropped on a field goes to it; dropped elsewhere on the card it goes nowhere, and the browser does not open it", async () => {
  show({ questions: [question(5, "w1")] });
  fireEvent.click(within(questionItem(5)).getByRole("button", { name: "Other…" }));
  await attach(questionItem(5)); // the limits are loaded
  const box = questionItem(5).querySelector(".composer-box") as HTMLElement;
  const dragged = { types: ["Files"], files: [file("server.log")] };
  expect(fireEvent.dragOver(box, { dataTransfer: dragged })).toBe(false);
  expect(box.classList.contains("dropping")).toBe(true);
  expect(within(box).getByText("Drop to attach · up to 2 files, 1000 B each")).toBeTruthy();
  fireEvent.drop(box, { dataTransfer: dragged });
  expect(chipsIn(questionItem(5))).toEqual(["server.log"]);
  const text = within(questionItem(5)).getByText("Question 5?");
  expect(fireEvent.dragOver(text, { dataTransfer: dragged })).toBe(false);
  expect(fireEvent.drop(text, { dataTransfer: { types: ["Files"], files: [file("other.log")] } })).toBe(false);
  expect(chipsIn(questionItem(5))).toEqual(["server.log"]);
});

test("a gate's comment takes files: their count beside its buttons; a button uploads them, then answers with their names", async () => {
  show({ questions: [], gates: [gate(1, "task/lad-27", "2026-10-03T12:00:06.000Z")] });
  const panel = within(card()).getByRole("tabpanel");
  await attach(panel, file("shot.png", 100, "image/png"), file("server.log", 96));
  const row = panel.querySelector(".waiting-send") as HTMLElement;
  expect(within(row).getByText("2 files, 196 B")).toBeTruthy();
  fireEvent.change(within(panel).getByRole("textbox", { name: "Comment for the next step (optional)" }), { target: { value: "see the log" } });
  fireEvent.click(within(row).getByRole("button", { name: "Reject" }));
  await waitFor(() =>
    expect(posted).toEqual([
      {
        path: "/api/sessions/s/gates/1/answer",
        body: { option: "reject", comment: "see the log", artifacts: ["shot-1a2b3c4d.png", "server-1a2b3c4d.log"] },
      },
    ]),
  );
});

test("a failed upload leaves the gate open: its chip red with the reason; the next try uploads only that file", async () => {
  refusedUploads = { "server.log": "disk full" };
  show({ questions: [], gates: [gate(1, "task/lad-27", "2026-10-03T12:00:06.000Z")] });
  const panel = within(card()).getByRole("tabpanel");
  await attach(panel, file("shot.png", 10, "image/png"), file("server.log"));
  fireEvent.click(within(panel).getByRole("button", { name: "Approve" }));
  await waitFor(() =>
    expect(within(panel).getByRole("alert").textContent).toBe(
      "server.log was not uploaded: disk full. Remove it, or answer again to try it again.",
    ),
  );
  expect(posted).toEqual([]);
  expect(panel.querySelector(".file-chip.failed .file-size")?.textContent).toBe("disk full");
  refusedUploads = {};
  fireEvent.click(within(panel).getByRole("button", { name: "Approve" }));
  await waitFor(() => expect(posted).toHaveLength(1));
  expect(uploads).toEqual(["shot.png", "server.log", "server.log"]);
});

// On a phone (docs/design/ui.md, Phone layout)

test("on a phone held sideways the card starts minimized, a tab shows it expanded, Esc minimizes it again", async () => {
  FakeScreen.sideways();
  show({ questions: [question(5, "supervisor")], gates: [GATE_812], chat: IN_CHAT });
  expect(isMinimized()).toBe(true);
  expect(line()?.textContent).toBe("Archive the change and merge the pull request?");
  expect(within(card()).queryByRole("button", { name: /^(Minimize|Restore) the card$/ })).toBeNull();
  fireEvent.click(tab("supervisor 1"));
  await waitFor(() => expect(isExpanded()).toBe(true));
  expect(selected()).toEqual([tab("supervisor 1")]);
  expect(within(card()).getByRole("button", { name: /^Send / })).toBeTruthy();
  fireEvent.keyDown(document, { key: "Escape" });
  await waitFor(() => expect(isExpanded()).toBe(false));
  expect(isMinimized()).toBe(true);
  fireEvent.click(line()!); // the line shows it too
  await waitFor(() => expect(isExpanded()).toBe(true));
  fireEvent.click(iconButton("Collapse the card"));
  await waitFor(() => expect(isMinimized()).toBe(true));
  expect(localStorage.getItem("lado.waitingMinimized.s")).toBeNull(); // the layout's fold, not the human's
});

test("turned upright, a card minimized only by the phone held sideways shows whole", () => {
  const phone = FakeScreen.sideways();
  show({ questions: [], gates: [GATE_812], chat: IN_CHAT });
  expect(isMinimized()).toBe(true);
  phone.set({ width: 390, height: 844 });
  expect(isMinimized()).toBe(false);
  expect(within(card()).getByRole("button", { name: "Approve" })).toBeTruthy();
});

test("turned upright from an expanded card, the card folds back in its place", async () => {
  const phone = FakeScreen.sideways();
  show({ questions: [], gates: [GATE_812], chat: IN_CHAT });
  fireEvent.click(tab("task/lad-52 1"));
  await waitFor(() => expect(isExpanded()).toBe(true));
  phone.set({ width: 390, height: 844 });
  expect(isExpanded()).toBe(false);
  expect(isMinimized()).toBe(false);
});

test("the human's own minimized card stays minimized on a phone, and is still theirs upright", () => {
  localStorage.setItem("lado.waitingMinimized.s", JSON.stringify(["gate:812"]));
  const phone = FakeScreen.sideways();
  show({ questions: [], gates: [GATE_812], chat: IN_CHAT });
  expect(isMinimized()).toBe(true);
  phone.set({ width: 390, height: 844 });
  expect(isMinimized()).toBe(true);
  expect(localStorage.getItem("lado.waitingMinimized.s")).toBe(JSON.stringify(["gate:812"]));
});

test("on a phone the card has no edge and keeps no height of its own", () => {
  localStorage.setItem("lado.waitingHeight", "230");
  FakeScreen.phone();
  show({ questions: [], gates: [GATE_812], chat: { feed: 400, loaded: true } });
  expect(edge()).toBeNull();
  expect(card().classList.contains("sized")).toBe(false);
  expect(within(card()).getByRole("button", { name: "Minimize the card" })).toBeTruthy(); // upright: as on a computer
});

test("upright on a phone the human's own minimize is remembered, as on a computer", () => {
  FakeScreen.phone();
  show({ questions: [], gates: [GATE_812], chat: IN_CHAT });
  fireEvent.click(iconButton("Minimize the card"));
  expect(isMinimized()).toBe(true);
  expect(localStorage.getItem("lado.waitingMinimized.s")).toBe(JSON.stringify(["gate:812"]));
});

// LAD-126: with the keyboard open the chat has no room for the card above the composer.
const commentField = () => within(card()).getByRole("textbox", { name: "Comment for the next step (optional)" });

test("on a phone in the chat a gate's comment taking the focus expands the card; the field keeps it and scrolls into view", async () => {
  FakeScreen.phone();
  columnWidth(null);
  const scrolled: Element[] = [];
  Element.prototype.scrollIntoView = function (this: Element) {
    scrolled.push(this);
  };
  try {
    show({ questions: [], gates: [GATE_812], chat: IN_CHAT });
    act(() => commentField().focus());
    await waitFor(() => expect(isExpanded()).toBe(true));
    expect(document.activeElement).toBe(commentField());
    expect(scrolled).toContain(commentField());
    // The keyboard opens after the expansion: the card laid out lower, the field scrolls again.
    scrolled.length = 0;
    FakeResizeObserver.resize(
      () => 400,
      () => 300,
    );
    expect(scrolled).toContain(commentField());
    // The field losing the focus (the keyboard closing) leaves the card expanded.
    act(() => commentField().blur());
    expect(isExpanded()).toBe(true);
    fireEvent.click(iconButton("Collapse the card"));
    await waitFor(() => expect(isExpanded()).toBe(false));
  } finally {
    delete (Element.prototype as { scrollIntoView?: unknown }).scrollIntoView;
  }
});

test("on a phone in the chat Other… expands the card with the own answer focused", async () => {
  FakeScreen.phone();
  show({ questions: [question(5, "supervisor")], chat: IN_CHAT });
  fireEvent.click(within(card()).getByRole("button", { name: "Other…" }));
  await waitFor(() => expect(isExpanded()).toBe(true));
  expect(document.activeElement).toBe(within(card()).getByRole("textbox", { name: "Your own answer" }));
});

test("a field's focus does not expand the card on a computer, nor on Needs you on a phone", () => {
  new FakeScreen("fine", 390, 844);
  show({ questions: [], gates: [GATE_812], chat: IN_CHAT });
  act(() => commentField().focus());
  expect(isExpanded()).toBe(false);
  cleanup();
  FakeScreen.phone();
  show({ questions: [], gates: [GATE_812] });
  act(() => commentField().focus());
  expect(isExpanded()).toBe(false);
});

test("on a phone the expand button still puts the focus on the shown tab", async () => {
  FakeScreen.phone();
  show({ questions: [], gates: [GATE_812], chat: IN_CHAT });
  fireEvent.click(iconButton("Expand the card"));
  await waitFor(() => expect(isExpanded()).toBe(true));
  expect(document.activeElement).toBe(tab("task/lad-52 1"));
});

test("Esc in a dialog over the page leaves an expanded card as it is", async () => {
  show({ questions: [], gates: [GATE_812], chat: IN_CHAT });
  fireEvent.click(iconButton("Expand the card"));
  await waitFor(() => expect(isExpanded()).toBe(true));
  const dialog = document.createElement("dialog");
  const inside = document.createElement("button");
  dialog.append(inside);
  document.body.append(dialog);
  fireEvent.keyDown(inside, { key: "Escape" });
  expect(isExpanded()).toBe(true);
  dialog.remove();
  fireEvent.keyDown(document, { key: "Escape" });
  await waitFor(() => expect(isExpanded()).toBe(false));
});
