import { afterEach, beforeEach, expect, test, vi } from "vitest";

import {
  PANEL_WIDTH,
  SESSIONS_WIDTH,
  storeAskControl,
  storedAskControl,
  storedPanel,
  storedSessionsList,
  storePanel,
  storeSessionsList,
} from "./prefs";

function narrow(matches: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: matches && query.includes("max-width"), media: query }));
}

beforeEach(() => {
  localStorage.clear();
  narrow(false);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("the terminal panel is open at its initial width at first, collapsed at first on a narrow window", () => {
  expect(storedPanel()).toEqual({ width: PANEL_WIDTH.initial, collapsed: false });
  narrow(true);
  expect(storedPanel()).toEqual({ width: PANEL_WIDTH.initial, collapsed: true });
});

test("the panel's width and whether it is collapsed are remembered", () => {
  storePanel({ width: 600, collapsed: true });
  expect(storedPanel()).toEqual({ width: 600, collapsed: true });
});

test("a panel remembered before it could collapse is open, also on a narrow window", () => {
  localStorage.setItem("lado.terminals", JSON.stringify({ width: 520 }));
  narrow(true);
  expect(storedPanel()).toEqual({ width: 520, collapsed: false });
});

test("the session list's width is remembered within its bounds", () => {
  expect(storedSessionsList()).toEqual({ width: SESSIONS_WIDTH.initial });
  expect(SESSIONS_WIDTH).toEqual({ initial: 260, min: 200, max: 480 });
  storeSessionsList({ width: 320 });
  expect(storedSessionsList()).toEqual({ width: 320 });
  localStorage.setItem("lado.sessionsList", JSON.stringify({ width: 9000 }));
  expect(storedSessionsList()).toEqual({ width: SESSIONS_WIDTH.initial });
  localStorage.setItem("lado.sessionsList", "not json");
  expect(storedSessionsList()).toEqual({ width: SESSIONS_WIDTH.initial });
});

test("Take control asks until the human says not to ask again", () => {
  expect(storedAskControl()).toBe(true);
  storeAskControl(false);
  expect(localStorage.getItem("lado.askControl")).toBe("never");
  expect(storedAskControl()).toBe(false);
});

test("without browser storage every default holds and nothing breaks", () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("denied");
  });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("denied");
  });
  storePanel({ width: 600, collapsed: true });
  storeSessionsList({ width: 300 });
  storeAskControl(false);
  expect(storedPanel()).toEqual({ width: PANEL_WIDTH.initial, collapsed: false });
  expect(storedSessionsList()).toEqual({ width: SESSIONS_WIDTH.initial });
  expect(storedAskControl()).toBe(true);
});
