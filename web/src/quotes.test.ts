// How a quote reaches a composer (docs/design/ui.md, Selected text and copy buttons): the
// session's mounted composer takes it, else it waits for the chat the page goes to.
import { afterEach, expect, test, vi } from "vitest";

import { chatPath } from "./paths";
import { onQuote, registerComposer, sendQuote, takePending } from "./quotes";

const undo: (() => void)[] = [];
afterEach(() => {
  undo.splice(0).forEach((one) => one());
  takePending("s");
  takePending("t");
});

test("a mounted composer of the session takes the quote, the page stays", () => {
  const insert = vi.fn();
  const other = vi.fn();
  undo.push(registerComposer("s", insert), registerComposer("t", other));
  const navigate = vi.fn();
  sendQuote("s", "> A", navigate);
  expect(insert).toHaveBeenCalledWith("> A");
  expect(other).not.toHaveBeenCalled();
  expect(navigate).not.toHaveBeenCalled();
  expect(takePending("s")).toBeNull();
});

test("of two mounted composers the latest takes it", () => {
  const first = vi.fn();
  const second = vi.fn();
  undo.push(registerComposer("s", first), registerComposer("s", second));
  sendQuote("s", "> A", vi.fn());
  expect(second).toHaveBeenCalledWith("> A");
  expect(first).not.toHaveBeenCalled();
});

test("without a composer the quote waits and the session's chat opens", () => {
  const gone = registerComposer("s", vi.fn());
  gone();
  const navigate = vi.fn();
  sendQuote("s", "> A", navigate);
  expect(navigate).toHaveBeenCalledWith(chatPath("s"));
  expect(takePending("s")).toBe("> A\n");
  expect(takePending("s")).toBeNull();
});

test("two quotes before the chat mounts are both kept", () => {
  sendQuote("s", "> A", vi.fn());
  sendQuote("s", "> B", vi.fn());
  expect(takePending("s")).toBe("> A\n\n> B\n");
});

test("the session's listeners hear each quote", () => {
  const heard = vi.fn();
  const other = vi.fn();
  undo.push(onQuote("s", heard), onQuote("t", other));
  sendQuote("s", "> A", vi.fn());
  undo.push(registerComposer("s", vi.fn()));
  sendQuote("s", "> B", vi.fn());
  expect(heard).toHaveBeenCalledTimes(2);
  expect(other).not.toHaveBeenCalled();
});
