// A tab's list and the page of the item it picks (Agents): side by side in a wide column; in
// a narrow one either the list or the page.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { Link, MemoryRouter, Route, Routes, useLocation, useParams } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { columnWidth, FakeResizeObserver, narrowColumn, wideColumn } from "./fakes";
import { filterGroups, ListGroup, ListPage, type Entry, type Group } from "./ListPage";

const HOUR = 3600 * 1000;

function entry(key: string, more: Partial<Entry> = {}): Entry {
  return { key, to: `/things/${key}`, row: <span className="row-name">{key}</span>, search: [key], ...more };
}

// 3 open things, and `old` ended ones, an hour apart from now back.
function groups({ old = 3 }: { old?: number } = {}): Group[] {
  const ended = Array.from({ length: old }, (_, at) =>
    entry(`old-${at + 1}`, { at: new Date(Date.now() - (at + 1) * HOUR).toISOString(), tone: "dim" }),
  );
  return [
    { name: "Waiting", tone: "human", entries: [entry("a", { tone: "waits", search: ["a", "Alpha task"] })] },
    { name: "Active", entries: [entry("b", { search: ["b", "Beta"] }), entry("c")] },
    { name: "Ended", entries: ended, days: true, first: 10, empty: "Nothing ended yet" },
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

test("the selected item is always seen: its row shows past the first 10", () => {
  wideColumn();
  open("/things/old-12", { list: groups({ old: 14 }) });
  const list = nav()!;
  const row = within(list).getByRole("link", { name: "old-12" });
  expect(row.getAttribute("aria-current")).toBe("page");
  expect(names(within(list).getByRole("region", { name: "Ended" }))).toHaveLength(12);
  expect(within(list).getByRole("button", { name: "Show 2 more" })).toBeTruthy();
  expect(within(list).getAllByRole("link").filter((one) => one.getAttribute("aria-current"))).toHaveLength(1);
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
  expect(within(nav()!).queryByRole("heading", { name: /^Live/ })).toBeNull();
  expect(within(nav()!).getByRole("heading", { name: "Gone 1" })).toBeTruthy();
});

// The groups

test("every group is open under its heading with its count; nothing folds", () => {
  wideColumn();
  open("/things/a", { list: groups({ old: 3 }) });
  const list = nav()!;
  expect(within(list).queryByRole("button", { name: /Ended/ })).toBeNull();
  for (const [name, count] of [
    ["Waiting", "1"],
    ["Active", "2"],
    ["Ended", "3"],
  ]) {
    const group = within(list).getByRole("region", { name });
    const heading = within(group).getByRole("heading", { level: 3, name: `${name} ${count}` });
    expect(heading.querySelector(".group-name")?.textContent).toBe(name);
    expect(heading.querySelector(".group-count")?.textContent).toBe(count);
    expect(heading.querySelector("svg")).toBeNull(); // no chevron: nothing folds
  }
  expect(names(list)).toEqual(["a", "b", "c", "old-1", "old-2", "old-3"]);
});

test("a group with `first` shows its days and its first rows, then Show N more", () => {
  wideColumn();
  open("/things/a", { list: groups({ old: 30 }) });
  const ended = within(nav()!).getByRole("region", { name: "Ended" });
  expect(names(ended)).toEqual(Array.from({ length: 10 }, (_, at) => `old-${at + 1}`));
  expect(ended.querySelector(".group-count")?.textContent).toBe("30");
  fireEvent.click(within(ended).getByRole("button", { name: "Show 20 more" }));
  expect(names(ended)).toHaveLength(30);
  expect(within(ended).queryByRole("button", { name: /more/ })).toBeNull();
  // 30 hours back from now: today, yesterday and maybe the day before.
  const days = within(ended)
    .getAllByRole("heading", { level: 4 })
    .map((one) => one.textContent);
  expect(days[0]).toBe(new Date(Date.now() - HOUR).getDate() === new Date().getDate() ? "Today" : "Yesterday");
  expect(days).toContain("Yesterday");
});

test("an empty group says its `empty` text; one without it is not shown", () => {
  wideColumn();
  const list: Group[] = [...groups({ old: 0 }), { name: "Nothing", entries: [] }];
  open("/things/a", { list });
  const ended = within(nav()!).getByRole("region", { name: "Ended" });
  expect(within(ended).getByText("Nothing ended yet")).toBeTruthy();
  expect(ended.querySelector(".group-count")?.textContent).toBe("0");
  expect(within(nav()!).queryByRole("region", { name: "Nothing" })).toBeNull();
});

test("the group that waits is in the human's tone, its heading too, its rows marked", () => {
  wideColumn();
  open("/things/a");
  const waiting = within(nav()!).getByRole("region", { name: "Waiting" });
  expect(waiting.className).toContain("tone-human");
  expect(within(waiting).getByRole("heading", { level: 3 }).className).toContain("group-head tone-human");
  // The other groups are neutral.
  expect(within(nav()!).getByRole("heading", { level: 3, name: "Active 2" }).className).toContain("tone-neutral");
  expect(within(waiting).getByRole("link").className).toContain("waits");
});

// The search

test("the search finds by any of an item's texts, any case, in every group, and shows every match", () => {
  wideColumn();
  open("/things/a", { list: groups({ old: 14 }) });
  const search = screen.getByRole("searchbox", { name: "Find a thing" });
  fireEvent.change(search, { target: { value: "ALPHA" } });
  expect(names(nav()!)).toEqual(["a"]);
  // A group without `empty` and no match is gone; one with it says so.
  expect(within(nav()!).queryByRole("region", { name: "Active" })).toBeNull();
  expect(within(within(nav()!).getByRole("region", { name: "Ended" })).getByText("No match")).toBeTruthy();
  fireEvent.change(search, { target: { value: "Old-1" } });
  // old-1 and old-10 to old-14, past the first 10.
  expect(names(nav()!)).toEqual(["old-1", "old-10", "old-11", "old-12", "old-13", "old-14"]);
  expect(within(nav()!).queryByRole("button", { name: /more/ })).toBeNull();
  fireEvent.change(search, { target: { value: "nope" } });
  expect(within(nav()!).getByText("No thing matches “nope”")).toBeTruthy();
  fireEvent.change(search, { target: { value: "" } });
  expect(names(nav()!)).toHaveLength(13);
});

// The shared parts: one group and the search's filter, also for a tab's own overview (Flows)

test("filterGroups keeps each group with the entries any of whose texts has the query, any case; none: all", () => {
  const list = groups({ old: 12 });
  expect(filterGroups(list, "  ").map(({ entries }) => entries.length)).toEqual([1, 2, 12]);
  const found = filterGroups(list, " beta ");
  expect(found.map(({ group }) => group.name)).toEqual(["Waiting", "Active", "Ended"]);
  expect(found.map(({ entries }) => entries.map((one) => one.key))).toEqual([[], ["b"], []]);
});

function Folding({ open: initial, look, searching = false }: { open: boolean; look?: Group["look"]; searching?: boolean }) {
  const [open, setOpen] = useState(initial);
  const group: Group = { name: "Active Runs", tone: "done", look, entries: [entry("b", { tone: "waits" }), entry("c")] };
  return (
    <ListGroup
      group={group}
      entries={group.entries}
      searching={searching}
      fold={{ open, onToggle: () => setOpen(!open), disabled: searching }}
    />
  );
}

function folding(props: Parameters<typeof Folding>[0]) {
  return render(
    <MemoryRouter>
      <Folding {...props} />
    </MemoryRouter>,
  );
}

test("a group with `fold` folds and opens by its heading; folded, its body stays in the page, hidden", () => {
  folding({ open: false });
  const button = screen.getByRole("button", { name: "Active Runs 2" });
  expect(button.getAttribute("aria-expanded")).toBe("false");
  const body = document.getElementById(button.getAttribute("aria-controls")!)!;
  expect(body.id).toBe("list-group-active-runs");
  expect(body.hidden).toBe(true);
  expect(screen.queryByRole("link")).toBeNull();
  fireEvent.click(button);
  expect(button.getAttribute("aria-expanded")).toBe("true");
  expect(body.hidden).toBe(false);
  expect(names(body)).toEqual(["b", "c"]);
  expect(screen.getByRole("region", { name: "Active Runs" }).className).toContain("tone-done");
});

test("while searching a folded group shows open and its heading is off", () => {
  folding({ open: false, searching: true });
  const button = screen.getByRole("button", { name: "Active Runs 2" }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  expect(button.getAttribute("aria-expanded")).toBe("true");
  expect(names(document.getElementById("list-group-active-runs")!)).toEqual(["b", "c"]);
});

test("a group's look sets its rows' class: list rows by default, cards with `card`; the tone either way", () => {
  folding({ open: true });
  expect(screen.getAllByRole("link").map((one) => one.className)).toEqual(["list-row waits", "list-row"]);
  cleanup();
  folding({ open: true, look: "card" });
  expect(screen.getAllByRole("link").map((one) => one.className)).toEqual(["list-card waits", "list-card"]);
});
