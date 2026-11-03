import { act, cleanup, render } from "@testing-library/react";
import { type ReactNode, useRef } from "react";
import { afterEach, expect, test, vi } from "vitest";

import { useScrollAnchor } from "./useScrollAnchor";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// Each element's top on the screen, set by the test before a render (jsdom lays nothing out).
let tops: Record<string, number> = {};
const topOf = (el: Element) => tops[(el as HTMLElement).dataset.t ?? ""] ?? 0;
Element.prototype.getBoundingClientRect = function (this: Element) {
  const top = topOf(this);
  return { top, bottom: top + 30, left: 0, right: 100, width: 100, height: 30, x: 0, y: top, toJSON: () => ({}) };
};

function wide(on: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("max-width") ? !on : on }));
}

let hold: (acted?: Element | null) => void = () => undefined;

function Page({ children }: { children: ReactNode }) {
  const section = useRef<HTMLElement>(null);
  hold = useScrollAnchor(section).hold;
  return (
    <div className="content" data-t="content">
      <section ref={section} data-t="section">
        {children}
      </section>
    </div>
  );
}

function scrolls(target: { scrollBy: unknown }) {
  const by = vi.fn();
  target.scrollBy = by;
  return by;
}

const page = (rows: string[], focus?: string) => (
  <Page>
    {rows.map((r) => (
      <button key={r} type="button" data-t={r} autoFocus={r === focus}>
        {r}
      </button>
    ))}
  </Page>
);

test("the focused element keeps its place: 120 px grown above it scroll .content by 120 on a wide window", () => {
  wide(true);
  tops = { a: 10, b: 300 };
  const view = render(page(["a", "b"], "b"));
  const content = view.container.querySelector(".content") as HTMLElement;
  const by = scrolls(content);
  const window_ = scrolls(window);
  tops = { new: 10, a: 130, b: 420 };
  view.rerender(page(["new", "a", "b"], "b"));
  expect(by).toHaveBeenCalledWith(0, 120);
  expect(window_).not.toHaveBeenCalled();
});

test("at or under 900 px the window scrolls", () => {
  wide(false);
  tops = { a: 10, b: 300 };
  const view = render(page(["a", "b"], "b"));
  const by = scrolls(window);
  tops = { new: 10, a: 130, b: 420 };
  view.rerender(page(["new", "a", "b"], "b"));
  expect(by).toHaveBeenCalledWith(0, 120);
});

test("with no focus in the section the element acted on is the anchor, else the first in view", () => {
  wide(true);
  tops = { a: -50, b: 40, c: 300 };
  const view = render(page(["a", "b", "c"]));
  const content = view.container.querySelector(".content") as HTMLElement;
  const by = scrolls(content);
  act(() => hold(view.getByText("c")));
  tops = { a: -50, b: 40, c: 360 };
  view.rerender(page(["a", "b", "c", "d"]));
  expect(by).toHaveBeenLastCalledWith(0, 60);
  by.mockClear();
  act(() => hold(null));
  tops = { x: -80, a: -50, b: 70, c: 390 }; // b, the first in view, moved by 30
  view.rerender(page(["x", "a", "b", "c", "d"]));
  expect(by).toHaveBeenLastCalledWith(0, 30);
});

test("the anchor is the nearest [data-anchor] around the focus", () => {
  wide(true);
  const card = (rows: string[]) => (
    <Page>
      <div data-anchor="" data-t="card">
        {rows.map((r) => (
          <button key={r} type="button" data-t={r} autoFocus={r === "b"}>
            {r}
          </button>
        ))}
      </div>
    </Page>
  );
  tops = { card: 100, a: 100, b: 130 };
  const view = render(card(["a", "b"]));
  const by = scrolls(view.container.querySelector(".content") as HTMLElement);
  tops = { card: 100, b: 100, a: 130 }; // b went first in its card: the card stays
  view.rerender(card(["b", "a"]));
  expect(by).not.toHaveBeenCalled();
});

test("an anchor gone from the page scrolls nothing", () => {
  wide(true);
  tops = { a: 10, b: 300 };
  const view = render(page(["a", "b"], "b"));
  const by = scrolls(view.container.querySelector(".content") as HTMLElement);
  tops = { a: 130 };
  view.rerender(page(["a"]));
  expect(by).not.toHaveBeenCalled();
});

test("the human's own scroll is no change to undo", () => {
  wide(true);
  tops = { a: 10, b: 300 };
  const view = render(page(["a", "b"], "b"));
  const content = view.container.querySelector(".content") as HTMLElement;
  const by = scrolls(content);
  tops = { a: -90, b: 200 };
  act(() => {
    content.dispatchEvent(new Event("scroll"));
  });
  view.rerender(page(["a", "b"], "b"));
  expect(by).not.toHaveBeenCalled();
});
