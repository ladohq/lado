import { afterEach, beforeEach, expect, test, vi } from "vitest";

import {
  PANEL_WIDTH,
  SESSIONS_WIDTH,
  storeAskControl,
  storedAskControl,
  storedPanel,
  storeColumn,
  storedColumn,
  storedSessionGroups,
  storedSessionsList,
  storePanel,
  storeSessionGroups,
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

test("a column is open at its initial width at first, collapsed at first on a narrow window (max-width: 900px)", () => {
  const bounds = { initial: 300, min: 100, max: 500 };
  const queries: string[] = [];
  vi.stubGlobal("matchMedia", (query: string) => {
    queries.push(query);
    return { matches: true, media: query };
  });
  expect(storedColumn("lado.some", bounds)).toEqual({ width: 300, collapsed: true });
  expect(queries).toEqual(["(max-width: 900px)"]);
  narrow(false);
  expect(storedColumn("lado.some", bounds)).toEqual({ width: 300, collapsed: false });
});

test("a column's width and whether it is collapsed are remembered under its key", () => {
  const bounds = { initial: 300, min: 100, max: 500 };
  storeColumn("lado.some", { width: 420, collapsed: true });
  expect(JSON.parse(localStorage.getItem("lado.some")!)).toEqual({ width: 420, collapsed: true });
  expect(storedColumn("lado.some", bounds)).toEqual({ width: 420, collapsed: true });
  expect(storedColumn("lado.other", bounds)).toEqual({ width: 300, collapsed: false });
});

test("a column remembered before it could collapse is open; a width out of bounds or no JSON is the initial one", () => {
  const bounds = { initial: 300, min: 100, max: 500 };
  narrow(true);
  localStorage.setItem("lado.some", JSON.stringify({ width: 200 }));
  expect(storedColumn("lado.some", bounds)).toEqual({ width: 200, collapsed: false });
  localStorage.setItem("lado.some", JSON.stringify({ width: 9000, collapsed: true }));
  expect(storedColumn("lado.some", bounds)).toEqual({ width: 300, collapsed: true });
  localStorage.setItem("lado.some", "not json");
  expect(storedColumn("lado.some", bounds)).toEqual({ width: 300, collapsed: true }); // as nothing stored
});

test("the session list keeps its width and whether it is collapsed in lado.sessionsList", () => {
  expect(storedSessionsList()).toEqual({ width: SESSIONS_WIDTH.initial, collapsed: false });
  expect(SESSIONS_WIDTH).toEqual({ initial: 260, min: 200, max: 480 });
  storeSessionsList({ width: 320, collapsed: true });
  expect(JSON.parse(localStorage.getItem("lado.sessionsList")!)).toEqual({ width: 320, collapsed: true });
  expect(storedSessionsList()).toEqual({ width: 320, collapsed: true });
  localStorage.clear();
  narrow(true);
  expect(storedSessionsList()).toEqual({ width: SESSIONS_WIDTH.initial, collapsed: true });
  localStorage.setItem("lado.sessionsList", JSON.stringify({ width: 300 })); // stored before it could collapse
  expect(storedSessionsList()).toEqual({ width: 300, collapsed: false });
});

test("each session group is remembered open or folded by its id; Stopped is folded by default", () => {
  expect(storedSessionGroups()).toEqual({ "needs-you": "open", running: "open", stopped: "folded" });
  storeSessionGroups({ "needs-you": "folded", running: "open", stopped: "open" });
  expect(JSON.parse(localStorage.getItem("lado.sessionGroups")!)).toEqual({
    "needs-you": "folded",
    running: "open",
    stopped: "open",
  });
  expect(storedSessionGroups()).toEqual({ "needs-you": "folded", running: "open", stopped: "open" });
  localStorage.setItem("lado.sessionGroups", JSON.stringify({ running: "folded", stopped: "sideways" }));
  expect(storedSessionGroups()).toEqual({ "needs-you": "open", running: "folded", stopped: "folded" });
});

test("the older key of the stopped sessions is only where Stopped starts, until the groups are stored", () => {
  localStorage.setItem("lado.stoppedSessions", "open");
  expect(storedSessionGroups().stopped).toBe("open");
  storeSessionGroups({ "needs-you": "open", running: "folded", stopped: "folded" });
  expect(storedSessionGroups().stopped).toBe("folded");
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
  storeSessionsList({ width: 300, collapsed: true });
  storeAskControl(false);
  storeSessionGroups({ "needs-you": "folded", running: "folded", stopped: "open" });
  expect(storedPanel()).toEqual({ width: PANEL_WIDTH.initial, collapsed: false });
  expect(storedSessionsList()).toEqual({ width: SESSIONS_WIDTH.initial, collapsed: false });
  expect(storedAskControl()).toBe(true);
  expect(storedSessionGroups()).toEqual({ "needs-you": "open", running: "open", stopped: "folded" });
});
