// The artifact panel's width (docs/design/ui.md, Artifacts, The panel): its left edge, the
// shared splitter with a grip, Expand and Restore width, remembered in lado.artifactPanel,
// within the room the window leaves; a narrow window shows it full screen with neither.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { ArtifactPanel } from "./ArtifactPanel";
import { artifact, FakeEventSource } from "./fakes";
import { Live, LiveContext } from "./live";

const DESIGN = artifact();

beforeEach(() => {
  localStorage.clear();
  FakeEventSource.all = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      const of = (body: unknown) => new Response(JSON.stringify(body));
      if (path.endsWith("/artifacts")) return of([DESIGN]);
      if (path.endsWith("/content")) return new Response("# Design");
      if (path.includes("/records/")) return of({ artifact: DESIGN, record: DESIGN.latest });
      return new Response("{}", { status: 404 });
    }),
  );
  windowWidth(1264); // room for 1200 px
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function windowWidth(width: number) {
  vi.stubGlobal("innerWidth", width);
  act(() => {
    window.dispatchEvent(new Event("resize"));
  });
}

function Open() {
  const [live] = useState(() => new Live());
  return (
    <LiveContext.Provider value={live}>
      <MemoryRouter initialEntries={["/sessions/lado/activity?view=r1"]}>
        <ArtifactPanel session="lado" record={DESIGN.latest.id} />
      </MemoryRouter>
    </LiveContext.Provider>
  );
}

const panel = () => screen.getByRole("dialog", { name: /^Artifact/ });
const edge = () => screen.getByRole("separator", { name: "Artifact panel width" });
const shown = () => panel().style.width;
const stored = () => JSON.parse(localStorage.getItem("lado.artifactPanel") ?? "null");

test("the panel's left edge is the shared splitter with a grip, 620 px wide at first, within 400 px and the room", () => {
  render(<Open />);
  expect(shown()).toBe("620px");
  expect([edge().getAttribute("aria-valuenow"), edge().getAttribute("aria-valuemin"), edge().getAttribute("aria-valuemax")]).toEqual([
    "620",
    "400",
    "1200",
  ]);
  expect(edge().classList.contains("splitter-left")).toBe(true);
  expect(edge().querySelectorAll(".splitter-grip-dot")).toHaveLength(3);
});

test("the arrow keys and a drag change the width and store it; a double click puts 620 back", () => {
  render(<Open />);
  fireEvent.keyDown(edge(), { key: "ArrowLeft" });
  expect(shown()).toBe("660px");
  expect(stored()).toEqual({ width: 660, expanded: false });
  fireEvent.pointerDown(edge(), { clientX: 600 });
  fireEvent.pointerMove(edge(), { clientX: 400 });
  fireEvent.pointerUp(edge());
  expect(shown()).toBe("860px");
  fireEvent.pointerDown(edge(), { clientX: 600 });
  fireEvent.pointerMove(edge(), { clientX: -2000 });
  fireEvent.pointerUp(edge());
  expect(stored()).toEqual({ width: 1200, expanded: false }); // never past the room
  fireEvent.doubleClick(edge());
  expect(shown()).toBe("620px");
  expect(stored()).toEqual({ width: 620, expanded: false });
});

test("Expand fills the room and turns into Restore width, which brings the chosen width back", () => {
  render(<Open />);
  fireEvent.keyDown(edge(), { key: "ArrowLeft" });
  const expand = screen.getByRole("button", { name: "Expand" });
  expect(expand.title).toBe("Expand");
  fireEvent.click(expand);
  expect(shown()).toBe("1200px");
  expect(stored()).toEqual({ width: 660, expanded: true });
  const restore = screen.getByRole("button", { name: "Restore width" });
  expect(restore.title).toBe("Restore width"); // Esc closes the panel here: no "(Esc)"
  fireEvent.click(restore);
  expect(shown()).toBe("660px");
  expect(stored()).toEqual({ width: 660, expanded: false });
});

test("dragging or a key while expanded ends expanded at the width it gives", () => {
  render(<Open />);
  fireEvent.click(screen.getByRole("button", { name: "Expand" }));
  fireEvent.pointerDown(edge(), { clientX: 100 });
  fireEvent.pointerMove(edge(), { clientX: 300 });
  fireEvent.pointerUp(edge());
  expect(shown()).toBe("1000px");
  expect(stored()).toEqual({ width: 1000, expanded: false });
  expect(screen.getByRole("button", { name: "Expand" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Expand" }));
  fireEvent.keyDown(edge(), { key: "ArrowRight" });
  expect(stored()).toEqual({ width: 1160, expanded: false });
});

test("the width and expanded are read back as stored", () => {
  localStorage.setItem("lado.artifactPanel", JSON.stringify({ width: 900, expanded: false }));
  render(<Open />);
  expect(shown()).toBe("900px");
  cleanup();
  localStorage.setItem("lado.artifactPanel", JSON.stringify({ width: 900, expanded: true }));
  render(<Open />);
  expect(shown()).toBe("1200px");
  expect(screen.getByRole("button", { name: "Restore width" })).toBeTruthy();
});

test("a window narrower than 464 px shows the panel full screen with no edge, grip, Expand or width", () => {
  windowWidth(463);
  render(<Open />);
  expect(screen.queryByRole("separator")).toBeNull();
  expect(screen.queryByRole("button", { name: "Expand" })).toBeNull();
  expect(shown()).toBe("");
  expect(screen.getByRole("button", { name: "Close" })).toBeTruthy();
});

test("a 700 px window shows the edge and Expand, the panel within its room", () => {
  windowWidth(700);
  render(<Open />);
  expect(edge().getAttribute("aria-valuemax")).toBe("636");
  expect(shown()).toBe("620px");
  expect(screen.getByRole("button", { name: "Expand" })).toBeTruthy();
});

test("the panel narrows with the window and gets its chosen width back when it widens", () => {
  localStorage.setItem("lado.artifactPanel", JSON.stringify({ width: 900, expanded: false }));
  render(<Open />);
  windowWidth(800);
  expect(shown()).toBe("736px");
  windowWidth(1264);
  expect(shown()).toBe("900px");
  expect(stored()).toEqual({ width: 900, expanded: false });
  windowWidth(463);
  expect(shown()).toBe("");
});
