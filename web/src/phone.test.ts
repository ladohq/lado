// The phone layout's one query (docs/design/ui.md, Phone layout): a touch screen no wider
// than 600 px or no higher than 500 px; never a mouse.
import { renderHook } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { FakeScreen } from "./fakes";
import { usePhone } from "./phone";

afterEach(() => vi.unstubAllGlobals());

test("a touch screen upright is a tall phone, sideways a short one", () => {
  FakeScreen.phone();
  expect(renderHook(usePhone).result.current).toBe("tall");
  FakeScreen.sideways();
  expect(renderHook(usePhone).result.current).toBe("short");
});

test("a mouse is never a phone, whatever its window", () => {
  new FakeScreen("fine", 390, 844);
  expect(renderHook(usePhone).result.current).toBeNull();
  new FakeScreen("fine", 844, 390);
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
  screen.set({ pointer: "fine" }); // a mouse plugged in
  expect(result.current).toBeNull();
});

test("without matchMedia (an old browser, jsdom) there is no phone", () => {
  vi.stubGlobal("matchMedia", undefined);
  expect(renderHook(usePhone).result.current).toBeNull();
});
