// Actions without an answer: the store keeps each one, looks at its outcome when it can and
// repeats it on Retry; each kind's look reads the server's state.
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { ApiError, Unreached, type GateInfo, type MessageInfo, type SessionInfo, type WaitingItem } from "./api";
import { Attempts, closedBy, LOOK_EVERY_MS, looks, type Action, type Attempt, type Outcome } from "./attempts";
import cases from "./closedRefusals.cases.json";

type All = Record<string, Attempt>;

let all: All;
let open: boolean;
let attempts: Attempts;

const unreached = () => Promise.reject(new Unreached());
const settle = () => vi.advanceTimersByTimeAsync(0);

function action(more: Partial<Action> = {}): Action {
  return {
    what: "Approval",
    repeat: vi.fn(unreached),
    look: vi.fn(async (): Promise<Outcome> => "missed"),
    closed: () => false,
    reached: vi.fn(),
    ...more,
  };
}

beforeEach(() => {
  vi.useFakeTimers();
  all = {};
  open = true;
  attempts = new Attempts(
    (now) => (all = now),
    () => open,
  );
});

afterEach(() => {
  attempts.stop();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("an answered action leaves nothing and says so", async () => {
  const given = action({ repeat: vi.fn(async () => "sent") });
  await expect(attempts.send("k", given)).resolves.toBe(true);
  expect(all).toEqual({});
  expect(given.reached).not.toHaveBeenCalled(); // the caller goes on by itself
});

test("a refusal goes to the caller as before, and no attempt is kept", async () => {
  const refusal = new ApiError(400, "no");
  await expect(attempts.send("k", action({ repeat: () => Promise.reject(refusal) }))).rejects.toBe(refusal);
  expect(all).toEqual({});
});

test("no answer keeps the action unknown and looks at once", async () => {
  const look = vi.fn(unreached);
  const sent = attempts.send("k", action({ look }));
  await expect(sent).resolves.toBe(false);
  expect(all.k.state).toBe("unknown");
  await settle();
  expect(look).toHaveBeenCalledTimes(1);
  expect(all.k.state).toBe("unknown");
});

test("a look that finds it missed says so", async () => {
  await attempts.send("k", action());
  await settle();
  expect(all.k.state).toBe("missed");
});

test("a look that finds it reached ends it", async () => {
  const given = action({ look: async () => "reached" });
  await attempts.send("k", given);
  await settle();
  expect(all).toEqual({});
  expect(given.reached).toHaveBeenCalledTimes(1);
});

test("a look that finds its item gone drops it with no end of its own", async () => {
  const given = action({ look: async () => "gone" });
  await attempts.send("k", given);
  await settle();
  expect(all).toEqual({});
  expect(given.reached).not.toHaveBeenCalled();
});

test("a 404 on a look means the session is gone", async () => {
  const given = action({ look: () => Promise.reject(new ApiError(404, "unknown session")) });
  await attempts.send("k", given);
  await settle();
  expect(all).toEqual({});
});

test("the feed never dropped: it looks every 3 s until it can", async () => {
  const look = vi.fn<() => Promise<Outcome>>(unreached);
  await attempts.send("k", action({ look }));
  await settle();
  await vi.advanceTimersByTimeAsync(LOOK_EVERY_MS);
  expect(look).toHaveBeenCalledTimes(2);
  look.mockResolvedValue("missed");
  await vi.advanceTimersByTimeAsync(LOOK_EVERY_MS);
  expect(all.k.state).toBe("missed");
  await vi.advanceTimersByTimeAsync(LOOK_EVERY_MS * 3);
  expect(look).toHaveBeenCalledTimes(3); // known: no more looks
});

test("with the feed down it waits, and the feed's return looks", async () => {
  open = false;
  const look = vi.fn<() => Promise<Outcome>>(unreached);
  await attempts.send("k", action({ look }));
  await settle();
  await vi.advanceTimersByTimeAsync(LOOK_EVERY_MS * 3);
  expect(look).toHaveBeenCalledTimes(1);
  open = true;
  look.mockResolvedValue("missed");
  attempts.look();
  await settle();
  expect(all.k.state).toBe("missed");
});

test("the connection coming back alone leaves the error", async () => {
  const look = vi.fn<() => Promise<Outcome>>(() => new Promise(() => {}));
  await attempts.send("k", action({ look }));
  attempts.look();
  await settle();
  expect(all.k.state).toBe("unknown");
});

test("Retry that succeeds ends it", async () => {
  const repeat = vi.fn<() => Promise<unknown>>(unreached);
  const given = action({ repeat });
  await attempts.send("k", given);
  await settle();
  repeat.mockResolvedValue("sent");
  await attempts.retry("k");
  expect(all).toEqual({});
  expect(given.reached).toHaveBeenCalledTimes(1);
});

test("Retry with no answer is unknown again and looks", async () => {
  const look = vi.fn<() => Promise<Outcome>>(async () => "missed");
  await attempts.send("k", action({ look }));
  await settle();
  look.mockImplementation(unreached);
  await attempts.retry("k");
  expect(all.k.state).toBe("unknown");
  await settle();
  expect(look).toHaveBeenCalledTimes(2);
});

test("Retry refused as closed counts as reached, no error", async () => {
  const repeat = vi.fn<() => Promise<unknown>>(unreached);
  const given = action({ repeat, closed: closedBy.gate });
  await attempts.send("k", given);
  await settle();
  repeat.mockRejectedValue(new ApiError(400, "gate #3 is closed already: approve by human"));
  await attempts.retry("k");
  expect(all).toEqual({});
  expect(given.reached).toHaveBeenCalledTimes(1);
});

test("Retry refused otherwise shows the refusal", async () => {
  const repeat = vi.fn<() => Promise<unknown>>(unreached);
  await attempts.send("k", action({ repeat }));
  await settle();
  repeat.mockRejectedValue(new ApiError(400, "no such option"));
  await attempts.retry("k");
  expect(all.k.state).toEqual({ refused: "no such option" });
});

test("no look runs while Retry does", async () => {
  let done = (_: string) => {};
  const repeat = vi.fn<() => Promise<unknown>>(unreached);
  const look = vi.fn<() => Promise<Outcome>>(async () => "missed");
  await attempts.send("k", action({ repeat, look }));
  await settle();
  repeat.mockImplementation(() => new Promise((resolve) => (done = resolve)));
  const retried = attempts.retry("k");
  expect(all.k.state).toBe("unknown");
  attempts.look();
  await settle();
  expect(look).toHaveBeenCalledTimes(1);
  done("sent");
  await retried;
  expect(all).toEqual({});
});

test("another decision replaces it, and a late look leaves the new one alone", async () => {
  let answer = (_: Outcome) => {};
  const first = action({ look: () => new Promise((resolve) => (answer = resolve)) });
  await attempts.send("k", first);
  attempts.clear("k");
  expect(all).toEqual({});
  const second = action({ what: "Rejection", look: async () => "missed" });
  await attempts.send("k", second);
  await settle();
  answer("reached");
  await settle();
  expect(all.k.what).toBe("Rejection");
  expect(first.reached).not.toHaveBeenCalled();
});

test.each(cases.refusals)("$kind: $text → closed $closed", ({ kind, text, closed }) => {
  const made = text.replaceAll("#N", "#12").replaceAll("S", "ship-it");
  expect(closedBy[kind as keyof typeof closedBy](made)).toBe(closed);
});

// Each kind's look, on the answers of the API.

const answers = (byPath: Record<string, unknown>) =>
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      const found = Object.entries(byPath).find(([start]) => path.startsWith(start));
      return found ? new Response(JSON.stringify(found[1])) : new Response("[]");
    }),
  );

const gate = (id: number, answer: string | null) => ({ id, answer }) as GateInfo;

test.each([
  [[gate(1, null)], "missed"],
  [[gate(1, "approve")], "reached"],
  [[], "reached"],
])("a gate: %j is %s", async (gates, outcome) => {
  answers({ "/api/sessions/s/gates": gates });
  await expect(looks.gate("s", 1)()).resolves.toBe(outcome);
});

const waiting = (session: string, id: number) => ({ session, question: { id } }) as WaitingItem;

test.each([
  [[], "reached"],
  [[waiting("s", 3)], "missed"],
  [[waiting("s", 9)], "reached"],
  [[waiting("other", 2)], "reached"],
  [[waiting("s", 2), waiting("s", 9)], "missed"],
])("questions 2 and 3: %j is %s", async (items, outcome) => {
  answers({ "/api/waiting": items });
  await expect(looks.questions("s", [2, 3])()).resolves.toBe(outcome);
});

const message = (more: Partial<MessageInfo>) =>
  ({ id: 8, from: "human", to: "supervisor", summary: "hi", body: "", attachments: [], ...more }) as MessageInfo;

const page = (items: MessageInfo[]) => ({ "/api/sessions/s/messages": { items, earlier: false } });

test("Send: the message after the click is found by its text", async () => {
  answers(page([message({})]));
  await expect(looks.send("s", "supervisor", 7, " hi\n", [])()).resolves.toBe("reached");
  const asked = vi.mocked(fetch).mock.calls[0][0] as string;
  expect(asked).toContain("after=7");
});

test("Send: with no cursor nothing counts, once the server answers", async () => {
  answers(page([message({})]));
  await expect(looks.send("s", "supervisor", null, "hi", [])()).resolves.toBe("missed");
  vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
  vi.spyOn(console, "error").mockImplementation(() => {});
  await expect(looks.send("s", "supervisor", null, "hi", [])()).rejects.toBeInstanceOf(Unreached);
});

test("Send: a long text stands in the body", async () => {
  answers(page([message({ summary: "first line", body: "first line\nsecond" })]));
  await expect(looks.send("s", "supervisor", 7, "first line\nsecond", [])()).resolves.toBe("reached");
});

test.each([
  ["no message", []],
  ["another text", [message({ summary: "other" })]],
  ["another agent", [message({ to: "w1" })]],
  ["an agent's own", [message({ from: "w1" })]],
  ["other files", [message({ attachments: [{ full_name: "b.txt" }] as MessageInfo["attachments"] })]],
])("Send: %s is not it", async (_, items) => {
  answers(page(items));
  await expect(looks.send("s", "supervisor", 7, "hi", [])()).resolves.toBe("missed");
});

test("Send: files alone are found by their names", async () => {
  const files = [{ full_name: "a.txt" }, { full_name: "b.txt" }] as MessageInfo["attachments"];
  answers(page([message({ summary: "2 files", attachments: files })]));
  await expect(looks.send("s", "supervisor", 7, "", ["b.txt", "a.txt"])()).resolves.toBe("reached");
});

const sessions = (status: SessionInfo["status"]) => ({ "/api/sessions": [{ name: "s", status }] });

test.each([
  ["running", "missed"],
  ["loop_down", "missed"],
  ["tmux_gone", "missed"],
  ["stopped", "reached"],
] as const)("Stop: a session %s is %s", async (status, outcome) => {
  answers(sessions(status));
  await expect(looks.stop("s")()).resolves.toBe(outcome);
});

test("Stop: a session gone is reached", async () => {
  answers({ "/api/sessions": [] });
  await expect(looks.stop("s")()).resolves.toBe("reached");
});

test.each([
  ["running", "reached"],
  ["loop_down", "reached"],
  ["tmux_gone", "missed"],
  ["stopped", "missed"],
] as const)("Resume: a session %s is %s", async (status, outcome) => {
  answers(sessions(status));
  await expect(looks.resume("s")()).resolves.toBe(outcome);
});

test("Resume: a session gone drops it", async () => {
  answers({ "/api/sessions": [] });
  await expect(looks.resume("s")()).resolves.toBe("gone");
});
