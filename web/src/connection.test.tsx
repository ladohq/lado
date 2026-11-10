// The buttons that write across a lost connection (docs/design/ui.md, A lost connection): they
// wait while it is lost, and an action without an answer shows the same error wherever its
// item shows until LADO has read the outcome. A real store, a fake server.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useEffect, useState, type ReactNode } from "react";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { GateInfo, MessageInfo, SessionInfo } from "./api";
import { Composer } from "./Composer";
import { FakeEventSource, stream, stubDialogs } from "./fakes";
import { GateCard } from "./GateCard";
import { LaunchProvider, useLaunch } from "./Launch";
import { Live, LiveContext, LOST_AFTER_MS } from "./live";
import { SessionActions, StoppedBar } from "./SessionControl";
import { TOOLTIP_DELAY_MS } from "./Tooltip";
import { WaitingCard } from "./WaitingCard";

function gate(more: Partial<GateInfo> = {}): GateInfo {
  return {
    id: 1,
    run: "ship/login",
    state: "check",
    kind: "approval",
    question: "Build it as planned?",
    options: ["approve", "reject"],
    note: "",
    note_body: "",
    attachments: [],
    reads: [],
    answer: null,
    comment: "",
    answered_by: null,
    created_at: "2026-11-06T12:00:00.000Z",
    answered_at: null,
    closed_by_event: null,
    answer_attachments: [],
    problem: null,
    note_by: null,
    recommendation: null,
    ...more,
  };
}

const question = (id: number): MessageInfo =>
  ({
    id,
    from: "w1",
    to: "human",
    kind: "question",
    summary: `Question ${id}?`,
    body: "",
    state: "queued",
    choices: ["Yes", "No"],
    free_answer: true,
    question_state: "open",
    attachments: [],
    created_at: "2026-11-06T12:00:00.000Z",
    recommendation: { state: "given", choice: "Yes", text: "", disagrees: false },
  }) as unknown as MessageInfo;

const session = (status: SessionInfo["status"]) =>
  ({ name: "s", repo: "/src/s", status, kits: ["default"], provider: "claude", permission_mode: null, without: [] }) as unknown as SessionInfo;

// The server as the test sets it: `down` answers nothing, `writesLost` answers reads only,
// after `onWrite`, `refuse` refuses a write; each list answers what stands here.
let server: {
  down: boolean;
  writesLost: boolean;
  onWrite: () => void;
  refuse: string | null;
  gates: GateInfo[];
  waiting: { session: string; question: MessageInfo }[];
  messages: Partial<MessageInfo>[];
  sessions: SessionInfo[];
};
let posted: { path: string; body: unknown }[];
let live: Live;

beforeEach(() => {
  server = { down: false, writesLost: false, onWrite: () => {}, refuse: null, gates: [], waiting: [], messages: [], sessions: [session("running")] };
  posted = [];
  stubDialogs();
  vi.spyOn(console, "error").mockImplementation(() => {});
  FakeEventSource.all = [];
  FakeEventSource.autoStart = false;
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      if (server.down) throw new TypeError("Failed to fetch");
      if (init?.method === "POST") {
        if (server.writesLost) {
          server.onWrite();
          throw new TypeError("Failed to fetch");
        }
        if (server.refuse !== null) return new Response(JSON.stringify({ detail: server.refuse }), { status: 400 });
        posted.push({ path, body: init.body ? JSON.parse(String(init.body)) : undefined });
        if (path.endsWith("/resume")) return new Response(JSON.stringify({ session: session("running") }));
        return new Response(JSON.stringify({ result: "sent", dropped: 0 }));
      }
      if (path === "/api/limits") return new Response("null", { status: 500 });
      if (path === "/api/providers") {
        return new Response(JSON.stringify([{ name: "claude", title: "Claude Code", permission_modes: ["default"], installed: true }]));
      }
      if (path.startsWith("/api/kits")) return new Response(JSON.stringify([{ name: "default", title: "Default" }]));
      if (path === "/api/sessions") return new Response(JSON.stringify(server.sessions));
      if (path === "/api/waiting") return new Response(JSON.stringify(server.waiting));
      if (path.endsWith("/gates")) return new Response(JSON.stringify(server.gates));
      if (path.includes("/messages")) {
        const query = new URL(path, "http://lado").searchParams;
        const after = Number(query.get("after") ?? 0);
        const limit = Number(query.get("limit") ?? server.messages.length);
        const items = server.messages.filter((one) => one.id! > after).slice(-limit);
        return new Response(JSON.stringify({ items, earlier: false }));
      }
      if (path.endsWith("/stop-preview")) {
        return new Response(JSON.stringify({ agents: ["w1"], dropped: 0, questions: 0, open_runs: [], worktrees: [] }));
      }
      return new Response("[]");
    }),
  );
  live = new Live();
  live.start();
  stream().start();
});

afterEach(() => {
  live.stop();
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function Place() {
  return <span data-testid="at">{useLocation().pathname}</span>;
}

const inShell = (children: ReactNode) => (
  <LiveContext.Provider value={live}>
    <MemoryRouter initialEntries={["/somewhere"]}>
      <LaunchProvider>
        {children}
        <Place />
      </LaunchProvider>
    </MemoryRouter>
  </LiveContext.Provider>
);

const show = (children: ReactNode) => render(inShell(children));

function lose() {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  server.down = true;
  stream().fail(false);
  act(() => vi.advanceTimersByTime(LOST_AFTER_MS));
  vi.useRealTimers();
}

async function back() {
  server.down = false;
  await act(async () => {
    stream().open();
    await new Promise((done) => setTimeout(done));
  });
}

const button = (name: string | RegExp) => screen.getByRole("button", { name }) as HTMLButtonElement;
const press = async (name: string | RegExp) => {
  await act(async () => {
    fireEvent.click(button(name));
    await new Promise((done) => setTimeout(done));
  });
};

const card = (more: Partial<GateInfo> = {}) => <GateCard session="s" gate={gate(more)} stopped={false} />;

// A gate.

test("while lost a gate's buttons wait with the reason beside them, and its comment takes text", () => {
  show(card());
  lose();
  expect(button("Approve").disabled).toBe(true);
  expect(button("Reject").disabled).toBe(true);
  expect(screen.getByText("Waiting for connection")).toBeTruthy();
  const comment = screen.getByRole("textbox") as HTMLTextAreaElement;
  expect(comment.disabled).toBe(false);
  fireEvent.change(comment, { target: { value: "Ship the login page first." } });
  expect(comment.value).toBe("Ship the login page first.");
});

test("the feed back: the buttons wake and the reason goes", async () => {
  show(card());
  lose();
  await back();
  expect(button("Approve").disabled).toBe(false);
  expect(screen.queryByText("Waiting for connection")).toBeNull();
});

test.each<[GateInfo["kind"], string[], string, string]>([
  ["approval", ["approve", "reject"], "Approve", "Approval"],
  ["approval", ["approve", "reject"], "Reject", "Rejection"],
  ["loop", ["continue", "cancel"], "Continue", "Answer"],
  ["loop", ["continue", "cancel"], "Cancel run", "Answer"],
  ["choice", ["left", "right"], "left", "Answer"],
])("a %s gate's %s… %s without an answer says %s not confirmed, Retry off", async (kind, options, name, what) => {
  show(card({ kind, options }));
  server.down = true;
  await press(name);
  const alert = screen.getByRole("alert");
  expect(alert.textContent).toBe(`${what} not confirmedRetry`);
  expect(within(alert).getByRole<HTMLButtonElement>("button", { name: "Retry" }).disabled).toBe(true);
  expect(document.body.textContent).not.toMatch(/TypeError|Failed to fetch/);
  expect(console.error).toHaveBeenCalled();
});

test("back with the gate open: not delivered, Retry and the buttons active", async () => {
  server.gates = [gate()];
  show(card());
  server.down = true;
  await press("Approve");
  await back();
  await screen.findByText("Approval not delivered");
  expect(button("Retry").disabled).toBe(false);
  expect(button("Approve").disabled).toBe(false);
  expect(button("Reject").disabled).toBe(false);
});

test("back with the gate closed: the error goes", async () => {
  server.gates = [gate({ answer: "approve" })];
  show(card());
  server.down = true;
  await press("Approve");
  await back();
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
});

test("until the state is read the buttons stay off, also with the feed open", async () => {
  server.gates = [gate()];
  let answer = (_: Response) => {};
  const gates = new Promise<Response>((resolve) => (answer = resolve));
  show(card());
  const open = vi.mocked(fetch).getMockImplementation()!;
  server.down = true;
  await press("Approve");
  vi.mocked(fetch).mockImplementation(async (path, init) => (String(path).endsWith("/gates") ? gates : open(path as string, init)));
  await back();
  expect(screen.getByText("Approval not confirmed")).toBeTruthy();
  expect(button("Approve").disabled).toBe(true);
  expect(button("Retry").disabled).toBe(true);
  await act(async () => answer(new Response(JSON.stringify([gate()]))));
  await screen.findByText("Approval not delivered");
});

test("another decision takes the error's place", async () => {
  server.gates = [gate()];
  show(card());
  server.down = true;
  await press("Approve");
  await back();
  await screen.findByText("Approval not delivered");
  await press("Reject");
  expect(screen.queryByRole("alert")).toBeNull();
  expect(posted).toEqual([{ path: "/api/sessions/s/gates/1/answer", body: { option: "reject", comment: "" } }]);
});

test("Retry sends what was pressed, whatever the field says now", async () => {
  server.gates = [gate()];
  show(card());
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "first words" } });
  server.down = true;
  await press("Approve");
  await back();
  await screen.findByText("Approval not delivered");
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "later words" } });
  await press("Retry");
  expect(posted).toEqual([{ path: "/api/sessions/s/gates/1/answer", body: { option: "approve", comment: "first words" } }]);
  expect(screen.queryByRole("alert")).toBeNull();
});

test("a Retry that finds the gate closed shows no error", async () => {
  server.gates = [gate()];
  show(card());
  server.down = true;
  await press("Approve");
  await back();
  await screen.findByText("Approval not delivered");
  server.refuse = "gate #1 is closed already: approve by human";
  await press("Retry");
  expect(screen.queryByRole("alert")).toBeNull();
});

test("a Retry refused otherwise shows the server's words", async () => {
  server.gates = [gate()];
  show(card());
  server.down = true;
  await press("Approve");
  await back();
  await screen.findByText("Approval not delivered");
  server.refuse = "the flow changed";
  await press("Retry");
  expect(screen.getByRole("alert").textContent).toBe("the flow changed");
  expect(button("Approve").disabled).toBe(false);
});

test("a refusal of the first press shows as ever, with no Retry", async () => {
  show(card());
  server.refuse = "the flow changed";
  await press("Approve");
  expect(screen.getByRole("alert").textContent).toBe("the flow changed");
  expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
});

test("the same error shows wherever the gate shows, and survives a change of page", async () => {
  const open = gate();
  const inChat = <WaitingCard session="s" questions={[]} gates={[open]} runs={[]} stopped={false} focus={null} />;
  const view = show(inChat);
  server.down = true;
  await press("Approve");
  expect(screen.getByText("Approval not confirmed")).toBeTruthy();
  view.rerender(
    <LiveContext.Provider value={live}>
      <MemoryRouter>
        <GateCard session="s" gate={open} stopped={false} />
      </MemoryRouter>
    </LiveContext.Provider>,
  );
  expect(screen.getByText("Approval not confirmed")).toBeTruthy();
  expect(button("Retry").disabled).toBe(true);
});

test("in a stopped session Retry follows the buttons", async () => {
  server.gates = [gate()];
  const view = show(card());
  server.down = true;
  await press("Approve");
  await back();
  await screen.findByText("Approval not delivered");
  view.rerender(
    <LiveContext.Provider value={live}>
      <MemoryRouter>
        <GateCard session="s" gate={gate()} stopped />
      </MemoryRouter>
    </LiveContext.Provider>,
  );
  expect(button("Retry").disabled).toBe(true);
  expect(screen.getByText("The session is stopped: resume it to answer.")).toBeTruthy();
});

// Send answer.

const waitingFor = (questions: MessageInfo[]) => (
  <WaitingCard session="s" questions={questions} gates={[]} runs={[]} stopped={false} focus={null} />
);

test("while lost Send answer waits with a tooltip, and the choices stay", async () => {
  show(waitingFor([question(5)]));
  lose();
  const send = button("Send answer to w1");
  expect(send.disabled).toBe(true);
  expect(button("Yes").disabled).toBe(false);
  fireEvent.click(button("Other…"));
  expect((screen.getByRole("textbox") as HTMLTextAreaElement).disabled).toBe(false);
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  fireEvent.mouseEnter(send.parentElement!);
  act(() => vi.advanceTimersByTime(TOOLTIP_DELAY_MS));
  vi.useRealTimers();
  expect(screen.getByRole("tooltip").textContent).toBe("Waiting for connection");
});

test("Send answer without an answer: not confirmed, then not delivered while one is open", async () => {
  server.waiting = [{ session: "s", question: question(5) }];
  show(waitingFor([question(5)]));
  server.down = true;
  await press("Send answer to w1");
  expect(screen.getByText("Answer not confirmed")).toBeTruthy();
  await back();
  await screen.findByText("Answer not delivered");
  expect(button("Send answer to w1").disabled).toBe(false);
  server.waiting = [];
  await press("Retry");
  expect(posted).toEqual([{ path: "/api/sessions/s/answers", body: { answers: [{ question: 5, choice: "Yes", skip: false }] } }]);
  expect(screen.queryByRole("alert")).toBeNull();
});

test("Send answer: none of the questions open any more, the error goes", async () => {
  show(waitingFor([question(5)]));
  server.down = true;
  await press("Send answer to w1");
  await back();
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
});

test("a Retry refused as a stopped question shows no error", async () => {
  server.waiting = [{ session: "s", question: question(5) }];
  show(waitingFor([question(5)]));
  server.down = true;
  await press("Send answer to w1");
  await back();
  await screen.findByText("Answer not delivered");
  server.refuse = "question #5 is stopped";
  await press("Retry");
  expect(screen.queryByRole("alert")).toBeNull();
});

// Send.

const composer = () => <Composer session="s" />;
const field = () => screen.getByRole("textbox") as HTMLTextAreaElement;
const type = (text: string) => fireEvent.change(field(), { target: { value: text } });
const human = (id: number, text: string, more: Partial<MessageInfo> = {}) => ({
  id,
  from: "human",
  to: "supervisor",
  summary: text,
  body: "",
  attachments: [],
  ...more,
});

test("while lost Send waits, Enter sends nothing and the field keeps its text", async () => {
  show(composer());
  type("Check the login form too");
  lose();
  expect(button("Send").disabled).toBe(true);
  await act(async () => {
    fireEvent.keyDown(field(), { key: "Enter" });
    await new Promise((done) => setTimeout(done));
  });
  expect(posted).toEqual([]);
  expect(field().value).toBe("Check the login form too");
  type("Check the login form too, please");
  expect(field().value).toBe("Check the login form too, please");
});

test("Send's tooltip says why it waits", () => {
  show(composer());
  type("hi");
  lose();
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  fireEvent.mouseEnter(button("Send").parentElement!);
  act(() => vi.advanceTimersByTime(TOOLTIP_DELAY_MS));
  vi.useRealTimers();
  expect(screen.getByRole("tooltip").textContent).toBe("Waiting for connection");
});

function Window() {
  const [stop] = useState(() => live.watchMessages("s", { with: "human", limit: 10 }));
  useEffect(() => stop, [stop]);
  return null;
}

// A composer under a window that holds `id`, the session's latest message of the human.
async function composerAfter(id: number, text = "earlier") {
  server.messages = [human(id, text)];
  show(
    <>
      <Window />
      {composer()}
    </>,
  );
  await waitFor(() => expect(live.lastMessage("s")).toBe(id));
}

test("the answer lost: found in the feed, no second message, the field empty", async () => {
  await composerAfter(1);
  type("hi");
  server.down = true;
  await press("Send");
  expect(screen.getByText("Message not confirmed")).toBeTruthy();
  expect(field().value).toBe("hi");
  server.messages.push(human(8, "hi"));
  await back();
  await waitFor(() => expect(field().value).toBe(""));
  expect(screen.queryByRole("alert")).toBeNull();
  expect(posted).toEqual([]);
});

test("found, the words changed meanwhile: the field keeps them", async () => {
  await composerAfter(1);
  type("hi");
  server.down = true;
  await press("Send");
  type("hi again");
  server.messages.push(human(8, "hi"));
  await back();
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  expect(field().value).toBe("hi again");
});

test("an empty window with the same words in the history: the server's latest id is the cursor", async () => {
  server.messages = [human(4, "hi")];
  show(composer());
  type("hi");
  server.writesLost = true;
  await press("Send");
  await screen.findByText("Message not delivered");
  expect(button("Retry").disabled).toBe(false);
  expect(field().value).toBe("hi");
});

test("an empty window, the answer lost: still found by the server's latest id", async () => {
  server.messages = [human(4, "hi")];
  show(composer());
  type("hi");
  server.writesLost = true;
  server.onWrite = () => server.messages.push(human(9, "hi"));
  await press("Send");
  await waitFor(() => expect(field().value).toBe(""));
  expect(screen.queryByRole("alert")).toBeNull();
});

test("no cursor to be had: the old words never count, and Retry waits for the server", async () => {
  server.messages = [human(4, "hi")];
  show(composer());
  type("hi");
  server.down = true;
  await press("Send");
  expect(screen.getByText("Message not confirmed")).toBeTruthy();
  await back();
  await screen.findByText("Message not delivered");
  expect(button("Retry").disabled).toBe(false);
  expect(field().value).toBe("hi");
});

test("not found: Retry sends the words of the click, the field keeps the new ones", async () => {
  await composerAfter(1);
  type("hi");
  server.down = true;
  await press("Send");
  await back();
  await screen.findByText("Message not delivered");
  type("something else");
  await press("Retry");
  expect(posted).toEqual([{ path: "/api/sessions/s/messages", body: { text: "hi" } }]);
  expect(field().value).toBe("something else");
  expect(screen.queryByRole("alert")).toBeNull();
});

test("the same words sent before the click do not count", async () => {
  await composerAfter(4, "hi");
  type("hi");
  server.down = true;
  await press("Send");
  await back();
  await screen.findByText("Message not delivered");
  const asked = vi.mocked(fetch).mock.calls.map(([path]) => String(path));
  expect(asked.some((path) => path.includes("/messages?") && path.includes("after=4"))).toBe(true);
});

test("a file that could not be uploaded: nothing sent, its name and no connection", async () => {
  show(composer());
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File(["x"], "plan.txt", { type: "text/plain" })] } });
  server.down = true;
  await press("Send");
  const line = screen.getByRole("alert").textContent!;
  expect(line).toContain("plan.txt was not uploaded: no connection.");
  expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
});

// Stop.

const actions = (status: SessionInfo["status"] = "running") => <SessionActions session={session(status)} onActivity={false} />;
const openStop = async () => {
  await press("Stop session…");
  await screen.findByRole("button", { name: "Stop s" });
};

test("while lost Stop waits in the head and in its popover", async () => {
  show(actions());
  await openStop();
  lose();
  expect(button("Stop s").disabled).toBe(true);
  expect(button("Stop and forget").disabled).toBe(true);
  expect(button("Stop session…").disabled).toBe(true);
  expect(button("Cancel").disabled).toBe(false);
});

test("Stop without an answer: not confirmed, and the popover closes once it is stopped", async () => {
  show(actions());
  await openStop();
  server.down = true;
  await press("Stop s");
  expect(screen.getByText("Stop not confirmed")).toBeTruthy();
  server.sessions = [session("stopped")];
  await back();
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
});

test("Stop reached with its popover closed leaves the Forget window the human opened", async () => {
  const view = show(actions());
  await openStop();
  server.down = true;
  await press("Stop s");
  await press("Cancel");
  expect(screen.queryByRole("dialog")).toBeNull();
  view.rerender(inShell(actions("stopped")));
  await press("Forget…");
  expect(screen.getByRole("dialog", { name: 'Forget session "s"?' })).toBeTruthy();
  server.sessions = [session("stopped")];
  await back();
  await waitFor(() => expect(live.get().attempts).toEqual({}));
  expect(screen.getByRole("dialog", { name: 'Forget session "s"?' })).toBeTruthy();
});

test("Stop not delivered: Retry stops it, and a refusal as stopped closes too", async () => {
  show(actions());
  await openStop();
  server.down = true;
  await press("Stop s");
  await back();
  await screen.findByText("Stop not delivered");
  server.refuse = 'session "s" is stopped already; resume it with `lado start`, or drop it with `lado forget s`';
  await press("Retry");
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("Stop and forget with its answer lost never forgets by itself", async () => {
  show(actions());
  await openStop();
  server.down = true;
  await press("Stop and forget");
  expect(screen.getByText("Stop not confirmed")).toBeTruthy();
  server.sessions = [session("stopped")];
  await back();
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  const deletes = vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === "DELETE");
  expect(deletes).toEqual([]);
});

test("Stop and forget's Retry repeats the stop alone", async () => {
  show(actions());
  await openStop();
  server.down = true;
  await press("Stop and forget");
  await back();
  await screen.findByText("Stop not delivered");
  await press("Retry");
  expect(posted).toEqual([{ path: "/api/sessions/s/stop", body: undefined }]);
  const deletes = vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === "DELETE");
  expect(deletes).toEqual([]);
});

// Resume.

function ResumeButton() {
  const launch = useLaunch();
  return (
    <button type="button" onClick={() => launch({ kind: "resume", session: session("stopped") })}>
      open resume
    </button>
  );
}

test("while lost Resume waits in the head", () => {
  show(actions("stopped"));
  lose();
  expect(button("Resume…").disabled).toBe(true);
  expect(button("Forget…").disabled).toBe(false);
});

test("while lost Resume session waits in the bar, and says why", () => {
  show(<StoppedBar session={session("stopped")} />);
  expect(button("Resume session").disabled).toBe(false);
  lose();
  expect(button("Resume session").disabled).toBe(true);
  fireEvent.focus(button("Resume session").closest(".lost-wait")!);
  expect(screen.getByRole("tooltip").textContent).toBe("Waiting for connection");
});

const resumeWindow = async () => {
  await press("open resume");
  const dialog = await screen.findByRole("dialog", { name: "Resume session" });
  await waitFor(() => expect(within(dialog).getByRole<HTMLButtonElement>("button", { name: "Resume s" }).disabled).toBe(false));
  return dialog;
};

test("Resume without an answer: not confirmed; once it runs the window closes on its page", async () => {
  server.sessions = [session("stopped")];
  show(<ResumeButton />);
  const dialog = await resumeWindow();
  server.down = true;
  await act(async () => {
    fireEvent.click(within(dialog).getByRole("button", { name: "Resume s" }));
    await new Promise((done) => setTimeout(done));
  });
  expect(within(dialog).getByText("Resume not confirmed")).toBeTruthy();
  server.sessions = [session("running")];
  await back();
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(screen.getByTestId("at").textContent).toBe("/sessions/s/activity");
});

test("Resume's error survives closing the window; Retry from the new one closes it", async () => {
  server.sessions = [session("stopped")];
  show(<ResumeButton />);
  const first = await resumeWindow();
  server.down = true;
  await act(async () => {
    fireEvent.click(within(first).getByRole("button", { name: "Resume s" }));
    await new Promise((done) => setTimeout(done));
  });
  await back();
  await within(first).findByText("Resume not delivered");
  fireEvent.click(within(first).getByRole("button", { name: "Cancel" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  await press("open resume");
  const second = await screen.findByRole("dialog", { name: "Resume session" });
  const retry = await within(second).findByRole("button", { name: "Retry" });
  await act(async () => {
    fireEvent.click(retry);
    await new Promise((done) => setTimeout(done));
  });
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(screen.getByTestId("at").textContent).toBe("/sessions/s/activity");
});

test("Resume reached with its window closed leaves the human where they are", async () => {
  server.sessions = [session("stopped")];
  show(<ResumeButton />);
  const dialog = await resumeWindow();
  server.down = true;
  await act(async () => {
    fireEvent.click(within(dialog).getByRole("button", { name: "Resume s" }));
    await new Promise((done) => setTimeout(done));
  });
  fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  server.sessions = [session("running")];
  const before = screen.getByTestId("at").textContent;
  await back();
  await waitFor(() => expect(live.get().attempts).toEqual({}));
  expect(screen.getByTestId("at").textContent).toBe(before);
});

test("Resume not delivered: Retry resumes, and a refusal as running counts as reached", async () => {
  server.sessions = [session("stopped")];
  show(<ResumeButton />);
  const dialog = await resumeWindow();
  server.down = true;
  await act(async () => {
    fireEvent.click(within(dialog).getByRole("button", { name: "Resume s" }));
    await new Promise((done) => setTimeout(done));
  });
  await back();
  await within(dialog).findByText("Resume not delivered");
  server.refuse = 'session "s" is already running; use `lado attach s`';
  await act(async () => {
    fireEvent.click(within(dialog).getByRole("button", { name: "Retry" }));
    await new Promise((done) => setTimeout(done));
  });
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
});
