// A tab's list and the page of the item it picks (docs/design/ui.md, Structure: List and
// page), one component for every such tab (Flows, Agents). In a column of NARROW px and
// wider the list is on the left and the page on the right, each scrolling by itself, and an
// address without an item goes to the tab's default one. In a narrower column (the terminals
// open) either the list takes the column (the address without an item) or the page does,
// with a link back to the list, which keeps its search and its scroll. Nothing is drawn
// before the column is measured: which of the two it is is not known yet.
//
// The list: a search over all of it, then groups of items, each always open under its
// heading with its count; a group may say why it is empty, show its rows by days and its
// first N before Show N more. The selected item is always seen.
import { useCallback, useRef, useState, type ReactNode } from "react";
import { Link, Navigate } from "react-router";

import { dayName } from "./ChatText";
import { GroupHead, type Tone } from "./GroupHead";
import { useWidth } from "./Splitter";

// Narrower than this, a tab's list and page take the column in turn.
export const NARROW = 900;

export type Entry = {
  key: string; // what the tab's address picks it by: unique in the list
  to: string; // its page's address
  row: ReactNode; // what its row shows
  search: string[]; // the texts the search finds it by
  tone?: "waits" | "dim";
  at?: string; // when, for a group by days
};

export type Group = {
  name: string;
  entries: Entry[];
  tone?: Tone; // its heading's (GroupHead): neutral by default
  heading?: boolean; // its name and count above its rows (by default)
  days?: boolean; // its rows under the local day of their `at`
  empty?: string; // what it says without rows ("No match" while searching); none: not drawn
  first?: number; // the rows shown before Show N more; none: all
};

export function ListPage({
  label,
  noun,
  groups,
  selected,
  page,
  listPath,
  back,
  fallback,
  notice,
}: {
  label: string; // the list's name: "Flow runs"
  noun: string; // one item: "run"
  groups: Group[];
  selected?: string; // the key the address names; none: the address names no item
  page: ReactNode; // the page of the item the address names
  listPath: string; // the tab's address without an item
  back: string; // the link back to the list in a narrow column: "All runs (2 open)"
  fallback?: string; // where a wide column without an item goes; none: an empty page
  notice?: ReactNode; // in place of the list and the page: the tab is loading or failed
}) {
  const [root, width] = useWidth<HTMLDivElement>();
  const [query, setQuery] = useState("");
  const scroll = useRef(0);
  const restore = useCallback((list: HTMLElement | null) => {
    if (list) list.scrollTop = scroll.current;
  }, []);
  const narrow = width !== null && width < NARROW;

  let body: ReactNode = null;
  if (notice !== undefined) {
    body = notice;
  } else if (width !== null) {
    const find = `Find ${/^[aeiou]/i.test(noun) ? "an" : "a"} ${noun}`;
    const wanted = query.trim().toLowerCase();
    const shown = groups.map((group) => ({
      group,
      entries: wanted
        ? group.entries.filter((entry) => entry.search.some((text) => text.toLowerCase().includes(wanted)))
        : group.entries,
    }));
    const list = (
      <div className="list-side">
        <input
          type="search"
          className="search"
          placeholder={find}
          aria-label={find}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <nav
          ref={restore}
          className="list-items"
          aria-label={label}
          onScroll={(event) => (scroll.current = event.currentTarget.scrollTop)}
        >
          {shown.map(({ group, entries }) => (
            <ListGroup key={group.name} group={group} entries={entries} selected={selected} searching={wanted !== ""} />
          ))}
          {wanted && shown.every(({ entries }) => entries.length === 0) && (
            <p className="muted list-none">
              No {noun} matches “{query.trim()}”
            </p>
          )}
        </nav>
      </div>
    );
    if (!narrow) {
      if (selected === undefined && fallback) {
        body = <Navigate replace to={fallback} />;
      } else {
        body = (
          <>
            {list}
            <div className="list-main">{selected === undefined ? null : page}</div>
          </>
        );
      }
    } else if (selected === undefined) {
      body = list;
    } else {
      body = (
        <div className="list-main">
          <Link className="list-back" to={listPath}>
            ‹ {back}
          </Link>
          {page}
        </div>
      );
    }
  }
  return (
    <div ref={root} className={`list-page${narrow ? " narrow" : ""}`}>
      {body}
    </div>
  );
}

const slug = (name: string) => name.toLowerCase().replace(/\s+/g, "-");

// One group of the list: its heading (name and how many rows it has now), then its rows,
// or its `empty` text; while the search has text, every match.
function ListGroup({
  group,
  entries,
  selected,
  searching,
}: {
  group: Group;
  entries: Entry[];
  selected?: string;
  searching: boolean;
}) {
  const [all, setAll] = useState(false);
  if (entries.length === 0 && group.empty === undefined) return null;
  const id = `list-group-${slug(group.name)}`;
  const tone = group.tone ?? "neutral";
  const className = `list-group tone-${tone}`;
  const at = entries.findIndex((entry) => entry.key === selected);
  let rows = entries;
  if (group.first !== undefined && !searching && !all) rows = entries.slice(0, Math.max(group.first, at + 1));
  const rest = entries.length - rows.length;
  const items =
    entries.length === 0 ? (
      <p className="muted list-empty">{searching ? "No match" : group.empty}</p>
    ) : (
      <>
        {byDay(rows, group.days === true).map(({ day, entries: some }) => (
          <div key={day ?? ""} className="list-day">
            {day && <h4 className="day-name">{day}</h4>}
            <ul>
              {some.map((entry) => (
                <li key={entry.key}>
                  <Link
                    to={entry.to}
                    className={`list-row${entry.tone ? ` ${entry.tone}` : ""}`}
                    aria-current={entry.key === selected ? "page" : undefined}
                  >
                    {entry.row}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
        {rest > 0 && (
          <button type="button" className="link-button show-more" onClick={() => setAll(true)}>
            Show {rest} more
          </button>
        )}
      </>
    );
  if (group.heading === false) {
    return (
      <section className={className} aria-label={group.name}>
        {items}
      </section>
    );
  }
  return (
    <section className={className} aria-labelledby={`${id}-name`}>
      <GroupHead nameId={`${id}-name`} name={group.name} count={entries.length} tone={tone} />
      {items}
    </section>
  );
}

// The rows in runs of one local day each, in their order; without days, one run.
function byDay(entries: Entry[], days: boolean): { day: string | null; entries: Entry[] }[] {
  if (!days) return [{ day: null, entries }];
  const runs: { day: string | null; entries: Entry[] }[] = [];
  for (const entry of entries) {
    const day = entry.at ? dayName(entry.at) : "";
    const last = runs[runs.length - 1];
    if (last && last.day === day) last.entries.push(entry);
    else runs.push({ day, entries: [entry] });
  }
  return runs;
}
