// A tab's list and the page of the item it picks (docs/design/ui.md, Structure: List and
// page), one component for every such tab (Flows, Agents). In a column of NARROW px and
// wider the list is on the left and the page on the right, each scrolling by itself, and an
// address without an item goes to the tab's default one. In a narrower column (the terminals
// open) either the list takes the column (the address without an item) or the page does,
// with a link back to the list, which keeps its search and its scroll. Nothing is drawn
// before the column is measured: which of the two it is is not known yet.
//
// The list: a search over it, then groups of items; a folded group (ended runs) is at the
// bottom, remembered, by days and its first 10 first. The selected item is
// always seen. A group can say why it has no items (its problem, or that it is loading).
import { useCallback, useRef, useState, type ReactNode } from "react";
import { Link, Navigate } from "react-router";

import { dayName } from "./ChatText";
import { FoldToggle } from "./Fold";
import { useWidth } from "./Splitter";

// Narrower than this, a tab's list and page take the column in turn.
export const NARROW = 900;

const FIRST = 10; // the items of a folded group shown before Show N more

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
  tone?: "waits";
  heading?: boolean; // its name above its rows (by default); a folded group has its toggle
  days?: boolean; // its rows under the local day of their `at`
  fold?: { stored: () => boolean; store: (open: boolean) => void };
  problem?: string | null; // why it has no items, shown in their place
  loading?: boolean;
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
  empty,
  notice,
}: {
  label: string; // the list's name: "Flow runs"
  noun: string; // one item: "run"
  groups: Group[];
  selected?: string; // the key the address names; none: the address names no item
  page: ReactNode; // the page of the item the address names
  listPath: string; // the tab's address without an item
  back: string; // the link back to the list in a narrow column: "All runs (2 open)"
  fallback?: string; // where a wide column without an item goes; none: `empty`
  empty?: ReactNode;
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
            <p className="muted">
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
            <div className="list-main">{selected === undefined ? empty : page}</div>
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

// One group of the list. A folded one is open while the search has text (its toggle then does
// nothing) or when the human opened it; it opens, not remembered, each time an item of it is
// selected, and folds again on its toggle.
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
  const [folded, setFolded] = useState(() => (group.fold ? !group.fold.stored() : false));
  const [all, setAll] = useState(false);
  // The selected item the group holds, as last seen: the group opens when it comes to hold one
  // (picked, or loaded after it was picked), also the one it held before another was picked.
  const [held, setHeld] = useState<string | undefined>(undefined);
  const holds = group.entries.some((entry) => entry.key === selected) ? selected : undefined;
  if (holds !== held) {
    setHeld(holds);
    if (holds !== undefined) setFolded(false);
  }
  const id = `list-group-${slug(group.name)}`;
  const className = `list-group${group.tone ? ` ${group.tone}` : ""}`;
  if (group.problem || group.loading) {
    return (
      <section className={className} aria-labelledby={`${id}-name`}>
        <h3 id={`${id}-name`} className="group-name">
          {group.name}
        </h3>
        {group.problem ? (
          <p className="problem" role="alert">
            {group.problem}
          </p>
        ) : (
          <p className="muted">Loading…</p>
        )}
      </section>
    );
  }
  if (entries.length === 0) return null;
  const at = entries.findIndex((entry) => entry.key === selected);
  let rows = entries;
  if (group.fold && !searching && !all) rows = entries.slice(0, Math.max(FIRST, at + 1));
  const rest = entries.length - rows.length;
  const items = (
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
  if (group.fold) {
    const fold = group.fold;
    const open = !folded || searching;
    const toggle = () => {
      setFolded(open);
      fold.store(!open);
    };
    return (
      <>
        <FoldToggle
          name={group.name}
          count={entries.length}
          open={open}
          controls={id}
          onToggle={toggle}
          disabled={searching}
        />
        {open && (
          <section id={id} className={className} aria-label={group.name}>
            {items}
          </section>
        )}
      </>
    );
  }
  if (group.heading === false) {
    return (
      <section className={className} aria-label={group.name}>
        {items}
      </section>
    );
  }
  return (
    <section className={className} aria-labelledby={`${id}-name`}>
      <h3 id={`${id}-name`} className="group-name">
        {group.name}
      </h3>
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
