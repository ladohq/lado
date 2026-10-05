// A tab's list and the page of the item it picks (Flows, Agents): side by side in a wide
// column; in a narrow one either the list or the page.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes, useLocation, useParams } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { columnWidth, FakeResizeObserver, narrowColumn, wideColumn } from "./fakes";
import { ListPage, type Entry, type Group } from "./ListPage";

const FOLD = "test.fold";

const HOUR = 3600 * 1000;

function entry(key: string, more: Partial<Entry> = {}): Entry {
  return { key, to: `/things/${key}`, row: <span className="row-name">{key}</span>, search: [key], ...more };
}

// 3 open things, and `old` ended ones, an hour apart from now back.
function groups({ old = 3, ...more }: { old?: number; problem?: string; loading?: boolean } = {}): Group[] {
  const ended = Array.from({ length: old }, (_, at) =>
    entry(`old-${at + 1}`, { at: new Date(Date.now() - (at + 1) * HOUR).toISOString(), tone: "dim" }),
  );
  return [
    { name: "Waiting", tone: "waits", entries: [entry("a", { tone: "waits", search: ["a", "Alpha task"] })] },
    { name: "Active", entries: [entry("b", { search: ["b", "Beta"] }), entry("c")] },
    {
      name: "Ended",
      entries: ended,
      days: true,
      fold: { stored: () => localStorage.getItem(FOLD) === "open", store: (open) => localStorage.setItem(FOLD, open ? "open" : "folded") },
      ...more,
    },
  ];
}

type Props = { list?: Group[]; fallback?: string; notice?: string };

function Things({ list = groups(), fallback = "/things/a", notice }: Props) {
  const { key } = useParams();
  return (
    <ListPage
      label="Things"
      noun="thing"
      groups={list}
      selected={key}
      page={
        <>
          <p>page of {key}</p>
          <Link to="/things/old-1">go to old-1</Link>
          <Link to="/things/old-2">go to old-2</Link>
        </>
      }
      listPath="/things"
      back="All things (3 open)"
      fallback={fallback}
      empty={<p>No things yet</p>}
      notice={notice === undefined ? undefined : <p>{notice}</p>}
    />
  );
}

function Where() {
  const { pathname } = useLocation();
  return <output aria-label="Address">{pathname}</output>;
}

function open(path: string, props: Props = {}) {
  const view = (more: Props) => (
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/things/:key?" element={<Things {...props} {...more} />} />
      </Routes>
      <Where />
    </MemoryRouter>
  );
  const result = render(view({}));
  return { ...result, again: (more: Props) => result.rerender(view(more)) };
}

const address = () => screen.getByRole("status", { name: "Address" }).textContent;
const nav = () => screen.queryByRole("navigation", { name: "Things" });
const pageOf = (key: string) => screen.queryByText(`page of ${key}`);
const names = (within_: HTMLElement) => Array.from(within_.querySelectorAll(".row-name")).map((one) => one.textContent);

beforeEach(() => localStorage.clear());

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// Wide and narrow

test("until its column is measured nothing is drawn and nothing redirects, but the root is there", () => {
  columnWidth(null);
  const { container } = open("/things");
  expect(container.querySelector(".list-page")).toBeTruthy();
  expect(nav()).toBeNull();
  expect(screen.queryByText(/page of/)).toBeNull();
  expect(address()).toBe("/things");
  FakeResizeObserver.resize(() => 1000);
  expect(address()).toBe("/things/a");
  expect(nav()).toBeTruthy();
});

test("a root drawn after a notice (loading) is measured all the same", () => {
  wideColumn();
  const view = open("/things/b", { notice: "Loading…" });
  expect(screen.getByText("Loading…")).toBeTruthy();
  expect(nav()).toBeNull();
  view.again({ notice: undefined });
  expect(nav()).toBeTruthy();
  expect(pageOf("b")).toBeTruthy();
});

test("in a wide column the list and the page are side by side, and no item goes to the default (replaced)", () => {
  wideColumn();
  open("/things");
  expect(address()).toBe("/things/a");
  expect(nav()).toBeTruthy();
  expect(pageOf("a")).toBeTruthy();
  expect(screen.queryByRole("combobox")).toBeNull();
  expect(screen.queryByRole("link", { name: /All things/ })).toBeNull();
  fireEvent.click(within(nav()!).getByRole("link", { name: "b" }));
  expect(address()).toBe("/things/b");
  expect(pageOf("b")).toBeTruthy();
  expect(nav()).toBeTruthy();
});

test("in a wide column with no default, the empty page shows beside the list", () => {
  wideColumn();
  open("/things", { fallback: "" });
  expect(address()).toBe("/things");
  expect(screen.getByText("No things yet")).toBeTruthy();
  expect(nav()).toBeTruthy();
});

test("in a narrow column the list takes it without an item, the page with one, and back keeps the search and the scroll", () => {
  narrowColumn();
  // jsdom keeps no scroll position: the elements keep what is set.
  const scrolled = new WeakMap<Element, number>();
  vi.spyOn(HTMLElement.prototype, "scrollTop", "get").mockImplementation(function (this: HTMLElement) {
    return scrolled.get(this) ?? 0;
  });
  vi.spyOn(HTMLElement.prototype, "scrollTop", "set").mockImplementation(function (this: HTMLElement, value: number) {
    scrolled.set(this, value);
  });
  open("/things");
  expect(address()).toBe("/things");
  expect(nav()).toBeTruthy();
  expect(screen.queryByText(/page of/)).toBeNull();
  expect(screen.queryByRole("combobox")).toBeNull();
  fireEvent.change(screen.getByRole("searchbox", { name: "Find a thing" }), { target: { value: "c" } });
  const list = nav()!;
  list.scrollTop = 120;
  fireEvent.scroll(list);
  fireEvent.click(within(nav()!).getByRole("link", { name: "c" }));
  expect(address()).toBe("/things/c");
  expect(pageOf("c")).toBeTruthy();
  expect(nav()).toBeNull();
  fireEvent.click(screen.getByRole("link", { name: "‹ All things (3 open)" }));
  expect(address()).toBe("/things");
  expect((screen.getByRole("searchbox", { name: "Find a thing" }) as HTMLInputElement).value).toBe("c");
  expect(nav()!.scrollTop).toBe(120);
});

// The selected item

test("the selected item is always seen: its folded group opens and its row shows past the first 10, the fold not stored", () => {
  wideColumn();
  open("/things/old-12", { list: groups({ old: 14 }) });
  const list = nav()!;
  const row = within(list).getByRole("link", { name: "old-12" });
  expect(row.getAttribute("aria-current")).toBe("page");
  expect(within(list).getByRole("button", { name: /Ended \(14\)/ }).getAttribute("aria-expanded")).toBe("true");
  expect(names(within(list).getByRole("region", { name: "Ended" }))).toHaveLength(12);
  expect(within(list).getByRole("button", { name: "Show 2 more" })).toBeTruthy();
  expect(localStorage.getItem(FOLD)).toBeNull();
  expect(within(list).getAllByRole("link").filter((one) => one.getAttribute("aria-current"))).toHaveLength(1);
});

test("a group opened for its selected item folds on its toggle, and opens again whenever an item of it is picked", () => {
  wideColumn();
  open("/things/old-1", { list: groups({ old: 3 }) });
  const toggle = () => within(nav()!).getByRole("button", { name: /Ended \(3\)/ });
  fireEvent.click(toggle());
  expect(toggle().getAttribute("aria-expanded")).toBe("false");
  expect(within(nav()!).queryByRole("region", { name: "Ended" })).toBeNull();
  expect(localStorage.getItem(FOLD)).toBe("folded");
  expect(pageOf("old-1")).toBeTruthy(); // the page stays
  fireEvent.click(toggle());
  expect(localStorage.getItem(FOLD)).toBe("open");
  fireEvent.click(toggle());
  fireEvent.click(within(nav()!).getByRole("link", { name: "a" }));
  expect(within(nav()!).queryByRole("region", { name: "Ended" })).toBeNull();
  // Picked from elsewhere (a link, the address): its group opens for it, not remembered.
  fireEvent.click(screen.getByRole("link", { name: "go to old-1" }));
  expect(within(nav()!).getByRole("link", { name: "old-1" }).getAttribute("aria-current")).toBe("page");
  // Folded again, another item picked, then the same one again: it opens again.
  fireEvent.click(toggle());
  fireEvent.click(within(nav()!).getByRole("link", { name: "a" }));
  fireEvent.click(screen.getByRole("link", { name: "go to old-1" }));
  expect(within(nav()!).getByRole("link", { name: "old-1" }).getAttribute("aria-current")).toBe("page");
  fireEvent.click(screen.getByRole("link", { name: "go to old-2" }));
  expect(within(nav()!).getByRole("link", { name: "old-2" }).getAttribute("aria-current")).toBe("page");
  expect(localStorage.getItem(FOLD)).toBe("folded");
});

test("while the search has text a folded group is open and its toggle does nothing", () => {
  wideColumn();
  open("/things/a", { list: groups({ old: 3 }) });
  fireEvent.change(screen.getByRole("searchbox", { name: "Find a thing" }), { target: { value: "old" } });
  const toggle = within(nav()!).getByRole("button", { name: /Ended \(3\)/ }) as HTMLButtonElement;
  expect(toggle.getAttribute("aria-expanded")).toBe("true");
  expect(toggle.disabled).toBe(true);
  fireEvent.click(toggle);
  expect(localStorage.getItem(FOLD)).toBeNull();
  fireEvent.change(screen.getByRole("searchbox", { name: "Find a thing" }), { target: { value: "" } });
  expect(within(nav()!).queryByRole("region", { name: "Ended" })).toBeNull();
});

test("an item is picked by its key: two rows of one name are told apart", () => {
  wideColumn();
  const twins: Group[] = [
    { name: "Live", heading: false, entries: [entry("live:dev", { row: <span>dev</span> })] },
    { name: "Gone", entries: [entry("gone:7", { row: <span>dev</span> })] },
  ];
  open("/things/gone:7", { list: twins });
  const rows = within(nav()!).getAllByRole("link", { name: "dev" });
  expect(rows.map((one) => one.getAttribute("aria-current"))).toEqual([null, "page"]);
  expect(within(nav()!).queryByRole("heading", { name: "Live" })).toBeNull();
  expect(within(nav()!).getByRole("heading", { name: "Gone" })).toBeTruthy();
});

// The groups

test("a folded group opens on its toggle, which is remembered; it shows its days and its first 10, then Show N more", () => {
  wideColumn();
  open("/things/a", { list: groups({ old: 30 }) });
  const list = nav()!;
  const toggle = within(list).getByRole("button", { name: /Ended \(30\)/ });
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  expect(within(list).queryByRole("region", { name: "Ended" })).toBeNull();
  fireEvent.click(toggle);
  expect(localStorage.getItem(FOLD)).toBe("open");
  const ended = within(list).getByRole("region", { name: "Ended" });
  expect(names(ended)).toEqual(Array.from({ length: 10 }, (_, at) => `old-${at + 1}`));
  fireEvent.click(within(ended).getByRole("button", { name: "Show 20 more" }));
  expect(names(ended)).toHaveLength(30);
  expect(within(ended).queryByRole("button", { name: /more/ })).toBeNull();
  // 30 hours back from now: today, yesterday and maybe the day before.
  const days = within(ended)
    .getAllByRole("heading")
    .map((one) => one.textContent);
  expect(days[0]).toBe(new Date(Date.now() - HOUR).getDate() === new Date().getDate() ? "Today" : "Yesterday");
  expect(days).toContain("Yesterday");
  cleanup();
  open("/things/a", { list: groups({ old: 30 }) });
  expect(within(nav()!).getByRole("region", { name: "Ended" })).toBeTruthy();
});

test("the group that waits is marked, its rows too; an empty group is not shown", () => {
  wideColumn();
  const list: Group[] = [...groups(), { name: "Nothing", entries: [] }];
  open("/things/a", { list });
  const waiting = within(nav()!).getByRole("region", { name: "Waiting" });
  expect(waiting.className).toContain("waits");
  expect(within(waiting).getByRole("link").className).toContain("waits");
  expect(within(nav()!).queryByRole("region", { name: "Nothing" })).toBeNull();
});

test("a group's problem and loading show in its place, with no items and while searching", () => {
  wideColumn();
  const view = open("/things/a", { list: groups({ old: 0, problem: "cannot read the ended runs" }) });
  const alert = within(nav()!).getByRole("alert");
  expect(alert.textContent).toBe("cannot read the ended runs");
  fireEvent.change(screen.getByRole("searchbox", { name: "Find a thing" }), { target: { value: "zzz" } });
  expect(within(nav()!).getByRole("alert").textContent).toBe("cannot read the ended runs");
  view.again({ list: groups({ old: 0, loading: true }) });
  expect(within(nav()!).getByRole("region", { name: "Ended" }).textContent).toContain("Loading…");
});

// The search

test("the search finds by any of an item's texts, any case; it opens folded groups and shows every match", () => {
  wideColumn();
  open("/things/a", { list: groups({ old: 14 }) });
  const search = screen.getByRole("searchbox", { name: "Find a thing" });
  fireEvent.change(search, { target: { value: "ALPHA" } });
  expect(names(nav()!)).toEqual(["a"]);
  expect(within(nav()!).queryByRole("region", { name: "Active" })).toBeNull();
  fireEvent.change(search, { target: { value: "Old-1" } });
  // old-1 and old-10 to old-14, past the first 10, from a folded group.
  expect(names(nav()!)).toEqual(["old-1", "old-10", "old-11", "old-12", "old-13", "old-14"]);
  expect(localStorage.getItem(FOLD)).toBeNull();
  fireEvent.change(search, { target: { value: "nope" } });
  expect(within(nav()!).getByText("No thing matches “nope”")).toBeTruthy();
  fireEvent.change(search, { target: { value: "" } });
  expect(names(nav()!)).toEqual(["a", "b", "c"]);
});
