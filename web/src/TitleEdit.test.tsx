// The field that edits a session's title in place (docs/design/ui.md, Session title).
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { SessionInfo } from "./api";
import { TitleEdit } from "./TitleEdit";

type Call = { method: string; path: string; body: unknown };
let calls: Call[] = [];
let refusal: string | null = null;

const session = (title: string | null) => ({ name: "lado-2", title }) as SessionInfo;

beforeEach(() => {
  calls = [];
  refusal = null;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      if (path === "/api/limits") return new Response(JSON.stringify({ max_title: 80 }));
      const body = JSON.parse(String(init?.body));
      calls.push({ method: init?.method ?? "GET", path, body });
      if (refusal) return new Response(JSON.stringify({ detail: refusal }), { status: 400 });
      return new Response(JSON.stringify({ ...session(body.title), title: body.title?.trim() || null }));
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function edit(title: string | null = "Old") {
  const onClose = vi.fn();
  render(<TitleEdit session={session(title)} hint="Enter to save · Esc to cancel" onClose={onClose} />);
  return { field: screen.getByRole("textbox", { name: "Session title" }) as HTMLInputElement, onClose };
}

const limitsRead = () => waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/limits", expect.anything()));

test("the field holds the title, selected, with the name as its placeholder and the hint under it", async () => {
  const { field } = edit("Old");
  expect(field.value).toBe("Old");
  expect(field.placeholder).toBe("lado-2");
  expect(document.activeElement).toBe(field);
  expect([field.selectionStart, field.selectionEnd]).toEqual([0, 3]);
  expect(screen.getByText("Enter to save · Esc to cancel")).toBeTruthy();
  cleanup();
  expect(edit(null).field.value).toBe("");
});

test("Enter saves the trimmed text through the API and closes", async () => {
  const { field, onClose } = edit();
  fireEvent.change(field, { target: { value: "  Review  " } });
  fireEvent.keyDown(field, { key: "Enter" });
  await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
  expect(calls).toEqual([{ method: "PUT", path: "/api/sessions/lado-2/title", body: { title: "Review" } }]);
  expect(onClose).toHaveBeenCalledWith(expect.objectContaining({ name: "lado-2", title: "Review" })); // as stored
});

test("leaving the field saves too", async () => {
  const { field, onClose } = edit();
  fireEvent.change(field, { target: { value: "Review" } });
  fireEvent.blur(field);
  await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
  expect(calls.map((call) => call.body)).toEqual([{ title: "Review" }]);
});

test("an empty field clears the title", async () => {
  const { field, onClose } = edit();
  fireEvent.change(field, { target: { value: "   " } });
  fireEvent.keyDown(field, { key: "Enter" });
  await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
  expect(calls.map((call) => call.body)).toEqual([{ title: null }]);
});

test("Esc cancels: nothing is sent, also by the blur after it", async () => {
  const { field, onClose } = edit();
  fireEvent.change(field, { target: { value: "x" } });
  fireEvent.keyDown(field, { key: "Escape" });
  fireEvent.blur(field);
  expect(onClose).toHaveBeenCalledOnce();
  await act(async () => {});
  expect(calls).toEqual([]);
});

test.each([
  ["the title as stored", "Old", "  Old "],
  ["the name with no title", null, "lado-2"],
  ["nothing with no title", null, ""],
])("the same text as stored sends nothing: %s", async (_, title, typed) => {
  const { field, onClose } = edit(title);
  fireEvent.change(field, { target: { value: typed } });
  fireEvent.keyDown(field, { key: "Enter" });
  expect(onClose).toHaveBeenCalledOnce();
  await act(async () => {});
  expect(calls).toEqual([]);
});

test.each([
  ["Latin", "x".repeat(81)],
  ["Cyrillic", "я".repeat(81)],
])("over the limit (%s) says so under the field and sends nothing", async (_, text) => {
  const { field, onClose } = edit();
  await limitsRead();
  fireEvent.change(field, { target: { value: text } });
  expect(await screen.findByText("81 characters, the limit is 80")).toBeTruthy();
  fireEvent.keyDown(field, { key: "Enter" });
  fireEvent.blur(field);
  await act(async () => {});
  expect(calls).toEqual([]);
  expect(onClose).not.toHaveBeenCalled();
});

test("80 emoji are 80 characters: within the limit", async () => {
  const { field, onClose } = edit();
  await limitsRead();
  fireEvent.change(field, { target: { value: "🚀".repeat(80) } });
  expect(screen.queryByText(/the limit is/)).toBeNull();
  fireEvent.keyDown(field, { key: "Enter" });
  await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
});

test("a refusal shows under the field, which stays open with the text; Enter tries again", async () => {
  refusal = "a title is one line";
  const { field, onClose } = edit();
  fireEvent.change(field, { target: { value: "Review" } });
  fireEvent.keyDown(field, { key: "Enter" });
  expect((await screen.findByRole("alert")).textContent).toBe("a title is one line");
  expect(field.value).toBe("Review");
  expect(onClose).not.toHaveBeenCalled();
  refusal = null;
  fireEvent.change(field, { target: { value: "Review 2" } });
  fireEvent.keyDown(field, { key: "Enter" });
  await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
  expect(calls.map((call) => call.body)).toEqual([{ title: "Review" }, { title: "Review 2" }]);
});

test("while it saves the field is read-only and a second Enter sends nothing", async () => {
  let answer: (response: Response) => void = () => {};
  vi.stubGlobal(
    "fetch",
    vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/limits") return Promise.resolve(new Response(JSON.stringify({ max_title: 80 })));
      calls.push({ method: init?.method ?? "GET", path, body: JSON.parse(String(init?.body)) });
      return new Promise<Response>((resolve) => (answer = resolve));
    }),
  );
  const { field, onClose } = edit();
  fireEvent.change(field, { target: { value: "Review" } });
  fireEvent.keyDown(field, { key: "Enter" });
  await waitFor(() => expect(field.readOnly).toBe(true));
  fireEvent.keyDown(field, { key: "Enter" });
  fireEvent.blur(field);
  expect(calls).toHaveLength(1);
  await act(async () => answer(new Response(JSON.stringify(session("Review")))));
  await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
});
