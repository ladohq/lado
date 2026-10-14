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
import { FakeEventSource } from "./fakes";
import { Live, LiveContext } from "./live";
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
};

let posted: { path: string; body: unknown }[] = [];
let answer: { status: number; body: unknown } = { status: 200, body: { result: "sent" } };

beforeEach(() => {
  posted = [];
  answer = { status: 200, body: { result: "sent" } };
  FakeEventSource.all = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
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
