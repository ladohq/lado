// The phone layout's one query (docs/design/ui.md, Phone layout): a window no wider than 600 px,
// or a touch screen no higher than 500 px.
import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { FakeScreen } from "./fakes";
import { PHONE_QUERY, type Phone, usePhone, usePhoneViewport } from "./phone";

afterEach(() => vi.unstubAllGlobals());

test("a touch screen upright is a tall phone, sideways a short one", () => {
  FakeScreen.phone();
  expect(renderHook(usePhone).result.current).toBe("tall");
  FakeScreen.sideways();
  expect(renderHook(usePhone).result.current).toBe("short");
});

test("a window of 600 px or less is a phone with a mouse too; a wider one, however low, is not", () => {
  expect(PHONE_QUERY).toBe("(max-width: 600px), (pointer: coarse) and (max-height: 500px)");
  new FakeScreen("fine", 390, 844);
  expect(renderHook(usePhone).result.current).toBe("tall");
  new FakeScreen("fine", 601, 844);
  expect(renderHook(usePhone).result.current).toBeNull();
  new FakeScreen("fine", 844, 390);
  expect(renderHook(usePhone).result.current).toBeNull();
  new FakeScreen("fine", 1280, 400);
  expect(renderHook(usePhone).result.current).toBeNull();
});

test("a touch laptop is no phone", () => {
  new FakeScreen("coarse", 1440, 900);
  expect(renderHook(usePhone).result.current).toBeNull();
});

test("a tablet is no phone either way round", () => {
  new FakeScreen("coarse", 820, 1180);
  expect(renderHook(usePhone).result.current).toBeNull();
  new FakeScreen("coarse", 1180, 820);
  expect(renderHook(usePhone).result.current).toBeNull();
});

test("the layout follows the phone as it turns, without a reload", () => {
  const screen = FakeScreen.phone();
  const { result } = renderHook(usePhone);
  expect(result.current).toBe("tall");
  screen.set({ width: 844, height: 390 });
  expect(result.current).toBe("short");
  screen.set({ width: 390, height: 844 });
  expect(result.current).toBe("tall");
  screen.set({ pointer: "fine", width: 700 }); // a computer's window, widened
  expect(result.current).toBeNull();
});

test("without matchMedia (an old browser, jsdom) there is no phone", () => {
  vi.stubGlobal("matchMedia", undefined);
  expect(renderHook(usePhone).result.current).toBeNull();
});

// The visible part of the window (LAD-109): the hook puts it on <html> for the app's frame.
class FakeViewport extends EventTarget {
  height = 544;
  offsetTop = 0;
  move(change: { height?: number; offsetTop?: number }, type: "resize" | "scroll") {
    Object.assign(this, change);
    act(() => {
      this.dispatchEvent(new Event(type));
    });
  }
}

const variable = (name: string) => document.documentElement.style.getPropertyValue(name);

function viewport(): FakeViewport {
  const fake = new FakeViewport();
  vi.stubGlobal("visualViewport", fake);
  return fake;
}

test("on a phone the visible part of the window is on <html> and follows it", () => {
  const fake = viewport();
  const { unmount } = renderHook(() => usePhoneViewport("tall"));
  expect(variable("--phone-height")).toBe("544px");
  expect(variable("--phone-top")).toBe("0px");
  fake.move({ height: 300 }, "resize"); // the keyboard opens
  expect(variable("--phone-height")).toBe("300px");
  fake.move({ offsetTop: 120 }, "scroll"); // Safari pans the page
  expect(variable("--phone-top")).toBe("120px");
  unmount();
  expect(variable("--phone-height")).toBe("");
  expect(variable("--phone-top")).toBe("");
  fake.move({ height: 200 }, "resize"); // no listener left
  expect(variable("--phone-height")).toBe("");
});

test("leaving the phone layout takes the variables away", () => {
  const fake = viewport();
  const { rerender } = renderHook(({ phone }: { phone: Phone }) => usePhoneViewport(phone), {
    initialProps: { phone: "tall" },
  });
  expect(variable("--phone-height")).toBe("544px");
  rerender({ phone: null });
  expect(variable("--phone-height")).toBe("");
  expect(variable("--phone-top")).toBe("");
  fake.move({ height: 300 }, "resize");
  expect(variable("--phone-height")).toBe("");
});

test("a tablet's page follows the visible part of the window too; a computer of its width does not", () => {
  viewport();
  for (const [width, height] of [
    [768, 1024],
    [1180, 734],
    [1032, 1366],
  ]) {
    new FakeScreen("coarse", width, height);
    const { unmount } = renderHook(() => usePhoneViewport(null));
    expect(variable("--phone-height")).toBe("544px");
    unmount();
  }
  new FakeScreen("fine", 1180, 734);
  const { unmount } = renderHook(() => usePhoneViewport(null));
  expect(variable("--phone-height")).toBe("");
  unmount();
  new FakeScreen("fine", 768, 1024);
  renderHook(() => usePhoneViewport(null));
  expect(variable("--phone-height")).toBe("");
});

test("no variable without a phone or without visualViewport", () => {
  viewport();
  renderHook(() => usePhoneViewport(null));
  expect(variable("--phone-height")).toBe("");
  vi.stubGlobal("visualViewport", undefined);
  renderHook(() => usePhoneViewport("tall"));
  expect(variable("--phone-height")).toBe("");
  expect(variable("--phone-top")).toBe("");
});
