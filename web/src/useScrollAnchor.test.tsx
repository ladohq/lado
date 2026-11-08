import { act, cleanup, fireEvent, render } from "@testing-library/react";
import { type ReactNode, useRef } from "react";
import { afterEach, expect, test, vi } from "vitest";

import { useScrollAnchor } from "./useScrollAnchor";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// Each element's top on the screen, set by the test before a render (jsdom lays nothing out);
// each is 30 px high, `.content` 900 px.
let tops: Record<string, number> = {};
const topOf = (el: Element) => tops[(el as HTMLElement).dataset.t ?? ""] ?? 0;
Element.prototype.getBoundingClientRect = function (this: Element) {
  const top = topOf(this);
  const height = (this as HTMLElement).dataset.t === "content" ? 900 : 30;
  return {
    top,
    bottom: top + height,
    left: 0,
    right: 100,
    width: 100,
    height,
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

function Page({ children }: { children: ReactNode }) {
  const section = useRef<HTMLElement>(null);
  useScrollAnchor(section);
  return (
    <div className="content" data-t="content">
      <section ref={section} data-t="section">
        {children}
      </section>
    </div>
  );
}

// The container's scrollTo, recorded; with `browser`, the page moves as a browser's does:
// every top on the screen by what the scroll changed, the scroll by whole pixels, never above 0.
function scrolls(target: { scrollTo: unknown }, browser = false) {
  let at = 0;
  const by = vi.fn((_x: number, y: number) => {
    if (!browser) return;
    const to = Math.max(0, Math.round(y));
    tops = Object.fromEntries(Object.entries(tops).map(([k, t]) => [k, t - (to - at)]));
    at = to;
    if (target !== window) (target as HTMLElement & { _top?: number })._top = to;
  });
  target.scrollTo = by;
  if (browser && target !== window)
    Object.defineProperty(target, "scrollTop", { get: () => at, configurable: true });
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
  tops = { section: 0, a: 10, b: 300 };
  const view = render(page(["a", "b"], "b"));
  const by = scrolls(view.container.querySelector(".content") as HTMLElement, true);
  tops = { section: 0, x: 10, a: 130.5, b: 420.5 };
  view.rerender(page(["x", "a", "b"], "b"));
  expect(by).toHaveBeenLastCalledWith(0, 120.5); // the page goes to 121: b at 299.5
  expect(tops.b).toBe(299.5);
  tops = Object.fromEntries(Object.entries(tops).map(([k, t]) => [k, k === "b" ? t + 60.5 : t]));
  view.rerender(page(["x", "y", "a", "b"], "b")); // 60.5 more above b
  expect(by).toHaveBeenLastCalledWith(0, 181); // from where it wanted, not from where it went
  expect(tops.b).toBe(300);
});

test("a scroll stopped at the top is no place wanted: the next correction counts from where the page is", () => {
  wide(true);
  tops = { section: 0, a: 10, b: 300 };
  const view = render(page(["a", "b"], "b"));
  const by = scrolls(view.container.querySelector(".content") as HTMLElement, true);
  tops = { section: 0, b: 250 }; // 50 px gone above b, the page at its top already
  view.rerender(page(["b"], "b"));
  expect(by).toHaveBeenLastCalledWith(0, -50);
  tops = { section: 0, x: 10, b: 370 }; // then 120 px grow above it
  view.rerender(page(["x", "b"], "b"));
  expect(by).toHaveBeenLastCalledWith(0, 120);
  expect(tops.b).toBe(250);
});

test("at the page's end the browser's own stop makes up for what went above: no second correction", () => {
  wide(true);
  tops = { section: -2000, a: -1900, b: 400 };
  const view = render(page(["a", "b"], "b"));
  const content = view.container.querySelector(".content") as HTMLElement;
  const by = vi.fn();
  content.scrollTo = by;
  let at = 2000;
  Object.defineProperty(content, "scrollTop", { get: () => at, configurable: true });
  Object.defineProperty(content, "clientHeight", { get: () => 900, configurable: true });
  let height = 2900; // the end of the page: 2000 + 900
  Object.defineProperty(content, "scrollHeight", { get: () => height, configurable: true });
  view.rerender(page(["a", "b"], "b")); // noted at the end of the page
  // 58 px gone above b: the page is shorter, and the browser stopped the scroll 58 px earlier,
  // so b stays where it was on the screen while the section came down.
  height -= 58;
  at -= 58;
  tops = { section: -1942, b: 400 };
  view.rerender(page(["b"], "b"));
  expect(by).not.toHaveBeenCalled();
});

test("near the page's end the browser stops part of the way: only the rest is scrolled", () => {
  wide(true);
  tops = { section: -2000, a: -1900, b: 400 };
  const view = render(page(["a", "b"], "b"));
  const content = view.container.querySelector(".content") as HTMLElement;
  const by = vi.fn();
  content.scrollTo = by;
  let at = 2884;
  Object.defineProperty(content, "scrollTop", { get: () => at, configurable: true });
  Object.defineProperty(content, "clientHeight", { get: () => 848, configurable: true });
  let height = 3762; // 30 px above the end of the page
  Object.defineProperty(content, "scrollHeight", { get: () => height, configurable: true });
  view.rerender(page(["a", "b"], "b"));
  height -= 72; // 72 px gone above b: the new end stops the scroll 42 px earlier
  at = 2842;
  tops = { section: -1958, b: 370 };
  view.rerender(page(["b"], "b"));
  expect(by).toHaveBeenLastCalledWith(0, 2812); // where the 72 px alone would put it
});

test("a correction made, the next render with nothing changed scrolls nothing", () => {
  wide(true);
  tops = { section: 0, a: 10, b: 300 };
  const view = render(page(["a", "b"], "b"));
  const by = scrolls(view.container.querySelector(".content") as HTMLElement, true);
  tops = { section: 0, x: 10, a: 130, b: 420 };
  view.rerender(page(["x", "a", "b"], "b"));
  expect(by).toHaveBeenCalledWith(0, 120);
  view.rerender(page(["x", "a", "b"], "b"));
  view.rerender(page(["x", "a", "b"], "b"));
  expect(by).toHaveBeenCalledTimes(1);
  expect(tops.b).toBe(300);
});

test("the focus out of view holds nothing: what shows stays, and the focus is noted where it is now", () => {
  wide(true);
  tops = { section: 0, a: 300, b: 1000 }; // b, focused, below the view
  const view = render(page(["a", "b"], "b"));
  const by = scrolls(view.container.querySelector(".content") as HTMLElement, true);
  tops = { section: 0, a: 300, x: 330, b: 1300 }; // 300 px grow between a and b
  view.rerender(page(["a", "x", "b"], "b"));
  expect(by).not.toHaveBeenCalled();
  // The human scrolled b into view by 600 px, then 60 px grow above it.
  tops = { section: -600, a: -300, x: -270, y: -240, b: 760 };
  view.rerender(page(["a", "x", "y", "b"], "b"));
  expect(by).toHaveBeenLastCalledWith(0, 60); // from its place after the change it did not hold
});

test("the focus in view, pushed out of it by what grows above, is kept", () => {
  wide(true);
  tops = { section: 0, a: 10, b: 800 };
  const view = render(page(["a", "b"], "b"));
  const by = scrolls(view.container.querySelector(".content") as HTMLElement);
  tops = { section: 0, x: 10, a: 310, b: 1100 };
  view.rerender(page(["x", "a", "b"], "b"));
  expect(by).toHaveBeenCalledWith(0, 300);
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

test("with no focus in the section the element pressed there is the anchor, until a press elsewhere", () => {
  wide(true);
  tops = { a: -50, b: 40, c: 300 };
  const view = render(page(["a", "b", "c"]));
  const content = view.container.querySelector(".content") as HTMLElement;
  const by = scrolls(content);
  fireEvent.pointerDown(view.getByText("c")); // pressed, never focused (Safari's buttons)
  tops = { a: -50, b: 40, c: 360 };
  view.rerender(page(["a", "b", "c", "d"]));
  expect(by).toHaveBeenLastCalledWith(0, 60);
  by.mockClear();
  fireEvent.pointerDown(document.body); // the human goes elsewhere
  tops = { x: -80, a: -50, b: 70, c: 390 };
  view.rerender(page(["x", "a", "b", "c", "d"]));
  expect(by).not.toHaveBeenCalled();
});

test("with nothing focused or pressed in the section, nothing scrolls whatever grows", () => {
  wide(true);
  tops = { a: 40, b: 300 };
  const view = render(page(["a", "b"]));
  const by = scrolls(view.container.querySelector(".content") as HTMLElement);
  tops = { x: 40, a: 160, b: 420 };
  view.rerender(page(["x", "a", "b"]));
  expect(by).not.toHaveBeenCalled();
});

test("a section above growing moves the whole section: nothing scrolls", () => {
  wide(true);
  tops = { section: 0, a: 10, b: 300 };
  const view = render(page(["a", "b"], "b"));
  const by = scrolls(view.container.querySelector(".content") as HTMLElement);
  tops = { section: 300, a: 310, b: 600 }; // 300 px grew above the section, nothing in it
  view.rerender(page(["a", "b"], "b"));
  expect(by).not.toHaveBeenCalled();
  tops = { section: 300, x: 310, a: 370, b: 660 }; // then 60 px in it, above b
  view.rerender(page(["x", "a", "b"], "b"));
  expect(by).toHaveBeenLastCalledWith(0, 60);
});

test("a scroll inside the section notes the anchor where it is now", () => {
  wide(true);
  tops = { a: 10, b: 300 };
  const view = render(page(["a", "b"], "b"));
  const by = scrolls(view.container.querySelector(".content") as HTMLElement);
  tops = { a: -40, b: 250 }; // a list in the section scrolled within itself
  act(() => {
    view.getByText("a").dispatchEvent(new Event("scroll"));
  });
  view.rerender(page(["a", "b"], "b"));
  expect(by).not.toHaveBeenCalled();
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
  const by = scrolls(content, true);
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

test("the human's own scroll moves the whole section: no change to undo", () => {
  wide(true);
  tops = { section: 0, a: 10, b: 300 };
  const view = render(page(["a", "b"], "b"));
  const content = view.container.querySelector(".content") as HTMLElement;
  const by = scrolls(content);
  tops = { section: -100, a: -90, b: 200 };
  act(() => {
    content.dispatchEvent(new Event("scroll"));
  });
  view.rerender(page(["a", "b"], "b"));
  expect(by).not.toHaveBeenCalled();
});
