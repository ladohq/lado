// The artifact panel's width (docs/design/ui.md, Artifacts, The panel): its left edge, the
// shared splitter with a grip, Expand and Restore width, remembered in lado.artifactPanel,
// within the room the window leaves; a narrow window shows it full screen with neither. Its
// buttons in one row, its top bar: the actions with their labels, icons under 560 px.
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { ArtifactPanel } from "./ArtifactPanel";
import type { ArtifactInfo } from "./api";
import { artifact, FakeEventSource } from "./fakes";
import { Live, LiveContext } from "./live";

const DESIGN = artifact();
let served: ArtifactInfo = DESIGN; // the record's artifact the server gives
let answer: Promise<Response> | null = null; // a record still on its way

beforeEach(() => {
  localStorage.clear();
  served = DESIGN;
  answer = null;
  FakeEventSource.all = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      const of = (body: unknown) => new Response(JSON.stringify(body));
      if (path.endsWith("/artifacts")) return of([served]);
      if (path.endsWith("/content")) return new Response("# Design");
      if (path.includes("/records/")) return answer ?? of({ artifact: served, record: served.latest });
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

function Where() {
  const { pathname, search } = useLocation();
  return <output aria-label="Address">{pathname + search}</output>;
}

function Open({ at = "/sessions/lado/activity?view=r1" }: { at?: string }) {
  const [live] = useState(() => new Live());
  return (
    <LiveContext.Provider value={live}>
      <MemoryRouter initialEntries={[at]}>
        <ArtifactPanel session="lado" record={DESIGN.latest.id} />
        <Where />
      </MemoryRouter>
    </LiveContext.Provider>
  );
}

const panel = () => screen.getByRole("dialog", { name: /^Artifact/ });
const edge = () => screen.getByRole("separator", { name: "Artifact panel width" });
const shown = () => panel().style.width;
const stored = () => JSON.parse(localStorage.getItem("lado.artifactPanel") ?? "null");

test("its close takes the record and its session (Needs you's ?session=) out of the address", async () => {
  render(<Open at="/needs-you?view=r1&session=lado&x=1" />);
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  expect(screen.getByRole("status", { name: "Address" }).textContent).toBe("/needs-you?x=1");
});

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
  fireEvent.focus(expand);
  expect(screen.getByRole("tooltip").textContent).toBe("Widen the panel");
  fireEvent.blur(expand);
  fireEvent.click(expand);
  expect(shown()).toBe("1200px");
  expect(stored()).toEqual({ width: 660, expanded: true });
  const restore = screen.getByRole("button", { name: "Restore width" });
  fireEvent.focus(restore);
  expect(screen.getByRole("tooltip").textContent).toBe("Restore width"); // Esc closes the panel here: no "(Esc)"
  fireEvent.blur(restore);
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

const bar = () => panel().querySelector<HTMLElement>(".panel-top")!;
// The bar's buttons and links in order, by their accessible names.
const names = () => [...bar().querySelectorAll("a, button")].map((one) => one.getAttribute("aria-label") ?? one.textContent);
const ACTIONS = ["Open in Artifacts tab", "Open in new tab", "Download", "Copy link"];

test("a panel of 560 px or wider holds every button in its top bar, the actions with their labels", async () => {
  render(<Open />);
  await within(bar()).findByRole("link", { name: "Download" });
  expect(names()).toEqual([...ACTIONS, "Expand", "Close"]);
  for (const name of ["Open in Artifacts tab", "Open in new tab", "Download"]) {
    const link = within(bar()).getByRole("link", { name });
    expect(link.textContent).toBe(name);
    expect(link.classList.contains("icon-button")).toBe(false);
    fireEvent.focus(link);
    expect(screen.queryByRole("tooltip")).toBeNull(); // its label says it already
  }
  expect(within(bar()).getByRole("link", { name: "Open in Artifacts tab" }).getAttribute("href")).toBe(
    "/sessions/lado/artifacts/a1?record=r1",
  );
  expect(within(screen.getByRole("banner")).queryAllByRole("link")).toHaveLength(0);
  expect(within(screen.getByRole("banner")).queryAllByRole("button")).toHaveLength(0);
});

test("over the Artifacts tab, or an artifact's page, the link to the page says Full page; Expand stays", async () => {
  render(<Open at="/sessions/lado/artifacts?view=r1" />);
  const link = await within(bar()).findByRole("link", { name: "Full page" });
  expect(link.getAttribute("href")).toBe("/sessions/lado/artifacts/a1?record=r1");
  expect(names()).toEqual(["Full page", ...ACTIONS.slice(1), "Expand", "Close"]);
  fireEvent.focus(link);
  expect(screen.getByRole("tooltip").textContent).toBe("Open as a page in this tab");
  cleanup();
  render(<Open at="/sessions/lado/artifacts/a1?view=r1" />);
  expect(await within(bar()).findByRole("link", { name: "Full page" })).toBeTruthy();
});

// The phone layout's query holds (phone.ts).
const phone = () =>
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: query.includes("max-width: 600px"),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));

test("on a phone the bar holds Download, Copy link, the menu and Close, as icons", async () => {
  phone();
  windowWidth(560);
  render(<Open />);
  await within(bar()).findByRole("link", { name: "Download" });
  expect(names()).toEqual(["Download", "Copy link", "More actions", "Close"]);
  expect(within(bar()).getByRole("link", { name: "Download" }).textContent).toBe("");
});

test("the phone's menu opens the record in a new tab and leads to its page; Esc leaves the panel open", async () => {
  phone();
  windowWidth(390);
  render(<Open />);
  const more = await within(bar()).findByRole("button", { name: "More actions" });
  expect(more.getAttribute("aria-haspopup")).toBe("menu");
  fireEvent.click(more);
  const menu = screen.getByRole("menu");
  const items = within(menu).getAllByRole("menuitem");
  expect(items.map((one) => one.textContent)).toEqual(["Open in new tab", "Open in Artifacts tab"]);
  expect(items[0].getAttribute("href")).toBe("/view/lado/r1");
  expect(document.activeElement).toBe(items[0]);
  fireEvent.keyDown(items[0], { key: "Escape" });
  expect(screen.queryByRole("menu")).toBeNull();
  expect(document.activeElement).toBe(more);
  expect(panel()).toBeTruthy();
  fireEvent.click(more);
  fireEvent.click(within(screen.getByRole("menu")).getByRole("menuitem", { name: "Open in Artifacts tab" }));
  expect(screen.getByRole("status", { name: "Address" }).textContent).toBe("/sessions/lado/artifacts/a1?record=r1");
});

test("the phone's menu has no Open in new tab for a type the browser cannot show, and says Full page on the tab", async () => {
  phone();
  windowWidth(390);
  served = artifact({}, { media_type: "application/octet-stream" });
  render(<Open at="/sessions/lado/artifacts?view=r1" />);
  fireEvent.click(await within(bar()).findByRole("button", { name: "More actions" }));
  expect(within(screen.getByRole("menu")).getAllByRole("menuitem").map((one) => one.textContent)).toEqual(["Full page"]);
});

test("a stored width of 400 px shows the four actions as icon buttons with tooltips, in one bar", async () => {
  localStorage.setItem("lado.artifactPanel", JSON.stringify({ width: 400, expanded: false }));
  render(<Open />);
  await within(bar()).findByRole("link", { name: "Download" });
  expect(names()).toEqual([...ACTIONS, "Expand", "Close"]);
  for (const name of ["Open in Artifacts tab", "Open in new tab", "Download"]) {
    const link = within(bar()).getByRole("link", { name });
    expect(link.textContent).toBe("");
    expect(link.classList.contains("icon-button")).toBe(true);
    fireEvent.focus(link);
    expect(screen.getByRole("tooltip").textContent).toBe(name);
    fireEvent.blur(link);
  }
  expect(within(screen.getByRole("banner")).queryAllByRole("link")).toHaveLength(0);
});

test("a type the browser cannot show has no Open in new tab in the bar", async () => {
  served = artifact({}, { media_type: "application/octet-stream" });
  render(<Open />);
  await within(bar()).findByRole("link", { name: "Download" });
  expect(names()).toEqual(["Open in Artifacts tab", "Download", "Copy link", "Expand", "Close"]);
});

test("while the record loads, and when it fails, the bar holds only Expand and Close", async () => {
  let give: (answer: Response) => void = () => {};
  answer = new Promise((resolve) => (give = resolve));
  render(<Open />);
  expect(names()).toEqual(["Expand", "Close"]);
  await act(async () => give(new Response(JSON.stringify({ detail: "no such record" }), { status: 404 })));
  await screen.findByRole("alert");
  expect(names()).toEqual(["Expand", "Close"]);
});
