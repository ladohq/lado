import { act, fireEvent, render } from "@testing-library/react";
import { useRef, useState } from "react";
import { afterEach, expect, test, vi } from "vitest";

import { grow, useGrow } from "./fieldHeight";

// A textarea whose layout jsdom lacks: its scrollHeight is `content` and its line 20 pixels,
// padding 6 and a border of 1 at each side.
function field(content: () => number): HTMLTextAreaElement {
  const box = document.createElement("textarea");
  box.style.lineHeight = "20px";
  box.style.padding = "6px 10px";
  box.style.border = "1px solid black";
  Object.defineProperty(box, "scrollHeight", { configurable: true, get: content });
  document.body.append(box);
  return box;
}

afterEach(() => {
  document.body.innerHTML = "";
});

test("a field with less text than its least lines is that many lines high", () => {
  const box = field(() => 32); // one line and the padding
  grow(box, 3, 8);
  expect(box.style.height).toBe("74px"); // 3 lines, padding and border
  expect(box.style.overflowY).toBe("hidden");
});

test("a field between its least and most lines is as tall as its text", () => {
  const box = field(() => 112); // 5 lines and the padding
  grow(box, 3, 8);
  expect(box.style.height).toBe("114px");
  expect(box.style.overflowY).toBe("hidden");
});

test("a field with more text than its most lines stops there and scrolls", () => {
  const box = field(() => 400);
  grow(box, 3, 8);
  expect(box.style.height).toBe("174px"); // 8 lines, padding and border
  expect(box.style.overflowY).toBe("auto");
});

function Grown({ least, most }: { least: number; most: number }) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  useGrow(ref, text, least, most);
  return <textarea ref={ref} aria-label="field" value={text} onChange={(event) => setText(event.target.value)} />;
}

function rendered(content: () => number) {
  const { getByRole } = render(<Grown least={3} most={8} />);
  const box = getByRole("textbox") as HTMLTextAreaElement;
  box.style.lineHeight = "20px";
  Object.defineProperty(box, "scrollHeight", { configurable: true, get: content });
  const scrolled = vi.fn();
  box.scrollIntoView = scrolled;
  return { box, scrolled };
}

test("a focused field that grows brings its lower edge into view", () => {
  let height = 20;
  const { box, scrolled } = rendered(() => height);
  act(() => box.focus());
  height = 120;
  fireEvent.change(box, { target: { value: "many\nlines" } });
  expect(box.style.height).toBe("120px");
  expect(scrolled).toHaveBeenCalledExactlyOnceWith({ block: "nearest" });
});

test("a field that grows without the focus, or shrinks, scrolls nothing", () => {
  let height = 20;
  const { box, scrolled } = rendered(() => height);
  height = 120;
  fireEvent.change(box, { target: { value: "set by the code" } });
  expect(box.style.height).toBe("120px");
  act(() => box.focus());
  height = 20;
  fireEvent.change(box, { target: { value: "short" } });
  expect(box.style.height).toBe("60px");
  expect(scrolled).not.toHaveBeenCalled();
});
