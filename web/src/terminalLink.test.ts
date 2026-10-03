import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { FakeSocket } from "./fakes";
import { RETRY_MS, TermLink, terminalUrl, type LinkState } from "./terminalLink";

const last = () => FakeSocket.all[FakeSocket.all.length - 1];

function link() {
  const seen = { output: [] as string[], sizes: [] as [number, number][], errors: [] as string[], states: [] as LinkState[] };
  const made = new TermLink("ws://h/t", {
    output: (data) => seen.output.push(new TextDecoder().decode(data)),
    size: (cols, rows) => seen.sizes.push([cols, rows]),
    error: (reason) => seen.errors.push(reason),
    state: (state) => seen.states.push(state),
  }, (url) => new FakeSocket(url) as unknown as WebSocket);
  return { made, seen };
}

beforeEach(() => {
  FakeSocket.all = [];
  vi.useFakeTimers();
});

afterEach(() => vi.useRealTimers());

test("the address names the session, the agent and the mode, each encoded whole", () => {
  expect(terminalUrl({ protocol: "http:", host: "127.0.0.1:8000" }, "my app/2", "w 1", "view")).toBe(
    "ws://127.0.0.1:8000/api/sessions/my%20app%2F2/agents/w%201/terminal?mode=view",
  );
  expect(terminalUrl({ protocol: "https:", host: "h" }, "s", "a", "control")).toMatch(/^wss:\/\/h\//);
});

test("output, sizes and errors reach their handlers; input and resize go out as JSON", () => {
  const { made, seen } = link();
  made.start();
  last().open();
  expect(seen.states.at(-1)).toEqual({ phase: "open", reason: null });
  last().frame(new TextEncoder().encode("hello").buffer);
  last().frame({ type: "size", cols: 100, rows: 30 });
  last().frame({ type: "error", reason: "take control to type" });
  expect(seen).toMatchObject({ output: ["hello"], sizes: [[100, 30]], errors: ["take control to type"] });
  made.input("ls\r");
  made.resize(90, 20);
  expect(last().sent.map((s) => JSON.parse(s))).toEqual([
    { type: "input", data: "ls\r" },
    { type: "resize", cols: 90, rows: 20 },
  ]);
});

test("a close for good (44xx) shows its reason and opens nothing again", () => {
  const { made, seen } = link();
  made.start();
  last().open();
  last().end(4404, 'session "s" is stopped');
  expect(seen.states.at(-1)).toEqual({ phase: "closed", reason: 'session "s" is stopped' });
  vi.advanceTimersByTime(RETRY_MS * 5);
  expect(FakeSocket.all).toHaveLength(1);
});

test("any other close opens a new socket after a pause, saying why meanwhile", () => {
  const { made, seen } = link();
  made.start();
  last().end(1006);
  expect(seen.states.at(-1)).toEqual({ phase: "retrying", reason: "the connection to the server was lost" });
  vi.advanceTimersByTime(RETRY_MS - 1);
  expect(FakeSocket.all).toHaveLength(1);
  vi.advanceTimersByTime(1);
  expect(FakeSocket.all).toHaveLength(2);
  last().end(4500, "the terminal closed; it opens again");
  expect(seen.states.at(-1)?.reason).toBe("the terminal closed; it opens again");
});

test("stop closes the socket and opens no new one", () => {
  const { made } = link();
  made.start();
  const socket = last();
  made.stop();
  socket.end(1000);
  vi.advanceTimersByTime(RETRY_MS * 5);
  expect(socket.closed).toBe(true);
  expect(FakeSocket.all).toHaveLength(1);
});
