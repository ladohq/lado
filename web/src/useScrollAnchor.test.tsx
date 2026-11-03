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
  return {
    top,
    bottom: top + 30,
    left: 0,
    right: 100,
    width: 100,
    height: 30,
    x: 0,
    y: top,
    toJSON: () => ({}),
  };
};

function wide(on: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: query.includes("max-width") ? !on : on,
  }));
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

test("half pixels the page cannot scroll do not add up: the anchor keeps its first place", () => {
  wide(true);
  tops = { a: 10, b: 300 };
  const view = render(page(["a", "b"], "b"));
  const content = view.container.querySelector(".content") as HTMLElement;
  const by = scrolls(content);
  tops = { new: 10, a: 130.5, b: 420.5 };
  view.rerender(page(["new", "a", "b"], "b"));
  expect(by).toHaveBeenLastCalledWith(0, 120.5);
  act(() => {
    content.dispatchEvent(new Event("scroll")); // the scroll it made, by whole pixels
  });
  tops = { new: -110, a: 10.5, b: 300.5 };
  view.rerender(page(["new", "a", "b"], "b"));
  expect(by).toHaveBeenCalledTimes(1); // half a pixel off: not scrolled for
  tops = { new: -110, a: 10.5, b: 360.5 };
  view.rerender(page(["new", "a", "b", "c"], "b"));
  expect(by).toHaveBeenLastCalledWith(0, 60.5); // back to 300, not to 300.5
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

const inCard = (rows: string[], focus: string) => (
  <Page>
    <div data-anchor="" data-t="card">
      {rows.map((r) => (
        <button key={r} type="button" data-t={r} autoFocus={r === focus}>
          {r}
        </button>
      ))}
    </div>
  </Page>
);

test("the focus moved within its card by a line above it is kept in place", () => {
  wide(true);
  tops = { card: 100, a: 100, b: 130 };
  const view = render(inCard(["a", "b"], "b"));
  const by = scrolls(view.container.querySelector(".content") as HTMLElement);
  tops = { card: 100, x: 100, a: 130, b: 160 }; // a line above it in the card
  view.rerender(inCard(["x", "a", "b"], "b"));
  expect(by).toHaveBeenCalledWith(0, 30);
});

test("an anchor gone from the page: the nearest [data-anchor] that held it stays in place", () => {
  wide(true);
  tops = { card: 100, a: 100, b: 130 };
  const view = render(inCard(["a", "b"], "b"));
  const by = scrolls(view.container.querySelector(".content") as HTMLElement);
  tops = { card: 160, c: 160, a: 190 }; // b replaced, 60 px grown above the card
  view.rerender(inCard(["c", "a"], ""));
  expect(by).toHaveBeenCalledWith(0, 60);
});

test("what held an anchor gone stays the anchor through the renders that follow", () => {
  wide(true);
  const headed = (rows: string[], focus: string) => (
    <Page>
      <p data-t="head">head</p>
      <div data-anchor="" data-t="card">
        {rows.map((r) => (
          <button key={r} type="button" data-t={r} autoFocus={r === focus}>
            {r}
          </button>
        ))}
      </div>
    </Page>
  );
  tops = { head: 10, card: 100, a: 100, b: 130 };
  const view = render(headed(["a", "b"], "b"));
  const by = scrolls(view.container.querySelector(".content") as HTMLElement);
  tops = { head: 10, card: 100, a: 100 }; // b gone, nothing moved yet
  view.rerender(headed(["a"], ""));
  expect(by).not.toHaveBeenCalled();
  tops = { head: 10, card: 40, a: 40 }; // then 60 px go above the card, not above the head
  view.rerender(headed(["a", "c"], ""));
  expect(by).toHaveBeenCalledWith(0, -60);
});

test("what held an anchor is noted where it is now, not where it was when first held", () => {
  wide(true);
  tops = { card: 100, a: 100, b: 130 };
  const view = render(inCard(["a", "b"], "b"));
  const content = view.container.querySelector(".content") as HTMLElement;
  // A scroll moves everything on the screen at once, as a browser's does.
  const by = vi.fn((_x: number, y: number) => {
    tops = Object.fromEntries(Object.entries(tops).map(([k, t]) => [k, t - y]));
  });
  content.scrollBy = by as unknown as typeof content.scrollBy;
  tops = { card: 100, x: 100, a: 130, b: 160 }; // a line in the card above b: b kept in place
  view.rerender(inCard(["x", "a", "b"], "b"));
  expect(by).toHaveBeenLastCalledWith(0, 30);
  act(() => {
    content.dispatchEvent(new Event("scroll"));
  });
  view.rerender(inCard(["x", "a"], "")); // b goes: the card stays where it is now, at 70
  expect(by).toHaveBeenCalledTimes(1);
});

test("an anchor gone from the page with nothing around it scrolls nothing", () => {
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
