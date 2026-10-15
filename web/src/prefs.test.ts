import { afterEach, beforeEach, expect, test, vi } from "vitest";

import {
  ARTIFACT_PANEL_WIDTH,
  PANEL_WIDTH,
  SESSIONS_WIDTH,
  storeArtifactPanel,
  storeAskControl,
  storedArtifactPanel,
  storedAskControl,
  storedPanel,
  storeColumn,
  storedColumn,
  storedFlowsGroups,
  storedSessionGroups,
  storeFlowsGroups,
  storedMinimized,
  storedSessionsList,
  storedWaitingHeight,
  storeMinimized,
  storePanel,
  storeSessionGroups,
  storeSessionsList,
  storeWaitingHeight,
  WAITING_MIN,
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

test("the Flows tab's groups are remembered in lado.flowsGroups: Active open, History folded by default", () => {
  expect(storedFlowsGroups()).toEqual({ active: "open", history: "folded" });
  storeFlowsGroups({ active: "folded", history: "open" });
  expect(JSON.parse(localStorage.getItem("lado.flowsGroups")!)).toEqual({ active: "folded", history: "open" });
  expect(storedFlowsGroups()).toEqual({ active: "folded", history: "open" });
  localStorage.setItem("lado.flowsGroups", JSON.stringify({ active: "sideways" }));
  expect(storedFlowsGroups()).toEqual({ active: "open", history: "folded" });
  localStorage.setItem("lado.flowsGroups", "not json");
  expect(storedFlowsGroups()).toEqual({ active: "open", history: "folded" });
});

test("the older key of the stopped sessions is only where Stopped starts, until the groups are stored", () => {
  localStorage.setItem("lado.stoppedSessions", "open");
  expect(storedSessionGroups().stopped).toBe("open");
  storeSessionGroups({ "needs-you": "open", running: "folded", stopped: "folded" });
  expect(storedSessionGroups().stopped).toBe("folded");
});

test("the artifact panel is 620 px wide and not expanded at first; its width and expanded are remembered in lado.artifactPanel", () => {
  expect(ARTIFACT_PANEL_WIDTH).toEqual({ initial: 620, min: 400, max: 2400 });
  expect(storedArtifactPanel()).toEqual({ width: 620, expanded: false });
  storeArtifactPanel({ width: 900, expanded: true });
  expect(JSON.parse(localStorage.getItem("lado.artifactPanel") ?? "")).toEqual({ width: 900, expanded: true });
  expect(storedArtifactPanel()).toEqual({ width: 900, expanded: true });
});

test("a bad stored artifact panel is 620 px wide and not expanded", () => {
  for (const bad of ["not json", "[1]", JSON.stringify({ width: 300, expanded: "yes" }), JSON.stringify({ width: 3000, expanded: 1 })]) {
    localStorage.setItem("lado.artifactPanel", bad);
    expect(storedArtifactPanel()).toEqual({ width: 620, expanded: false });
  }
});

test("Take control asks until the human says not to ask again", () => {
  expect(storedAskControl()).toBe(true);
  storeAskControl(false);
  expect(localStorage.getItem("lado.askControl")).toBe("never");
  expect(storedAskControl()).toBe(false);
});

test("the waiting card's height is one value, none at first; a broken one is none", () => {
  expect(storedWaitingHeight()).toBeNull();
  storeWaitingHeight(230);
  expect(localStorage.getItem("lado.waitingHeight")).toBe("230");
  expect(storedWaitingHeight()).toBe(230);
  storeWaitingHeight(null); // back to the default
  expect(localStorage.getItem("lado.waitingHeight")).toBeNull();
  for (const bad of ["tall", "", String(WAITING_MIN - 1), "-5", "Infinity"]) {
    localStorage.setItem("lado.waitingHeight", bad);
    expect(storedWaitingHeight()).toBeNull();
  }
});

test("the minimized waiting card's tabs are kept per session, and dropped", () => {
  expect(storedMinimized("lad-46")).toBeNull();
  storeMinimized("lad-46", ["gate:812", "agent:supervisor"]);
  expect(localStorage.getItem("lado.waitingMinimized.lad-46")).toBe('["gate:812","agent:supervisor"]');
  expect(storedMinimized("lad-46")).toEqual(["gate:812", "agent:supervisor"]);
  expect(storedMinimized("docs-site")).toBeNull();
  storeMinimized("lad-46", null);
  expect(localStorage.getItem("lado.waitingMinimized.lad-46")).toBeNull();
  for (const bad of ["{", '{"a":1}', '["gate:1",2]', "null", "3"]) {
    localStorage.setItem("lado.waitingMinimized.lad-46", bad);
    expect(storedMinimized("lad-46")).toBeNull();
  }
});

test("without browser storage every default holds and nothing breaks", () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("denied");
  });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("denied");
  });
  vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
    throw new Error("denied");
  });
  storeWaitingHeight(230);
  storeWaitingHeight(null);
  storeMinimized("lad-46", ["gate:812"]);
  storeMinimized("lad-46", null);
  expect(storedWaitingHeight()).toBeNull();
  expect(storedMinimized("lad-46")).toBeNull();
  storePanel({ width: 600, collapsed: true });
  storeSessionsList({ width: 300, collapsed: true });
  storeAskControl(false);
  storeArtifactPanel({ width: 900, expanded: true });
  storeSessionGroups({ "needs-you": "folded", running: "folded", stopped: "open" });
  expect(storedPanel()).toEqual({ width: PANEL_WIDTH.initial, collapsed: false });
  expect(storedSessionsList()).toEqual({ width: SESSIONS_WIDTH.initial, collapsed: false });
  expect(storedAskControl()).toBe(true);
  expect(storedArtifactPanel()).toEqual({ width: 620, expanded: false });
  expect(storedSessionGroups()).toEqual({ "needs-you": "open", running: "open", stopped: "folded" });
});
