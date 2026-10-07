// The session's Flows tab (docs/design/ui.md, Flows): the overview of its runs across the
// whole column, Active (the waiting ones first, as cards with their flow's states) and
// History, both foldable and found by the tab bar's search (?find=); or, in its place at any
// width, a run's page with the way back: its head (status, task, its flow's states), what
// goes on now (who acts, its gate answered in place, or how it ended) and its history, one
// feed of events that open to their details. A step is a note (NoteInfo: who reported it,
// the outcome and where it leads); the run's start, end and cancel are its events. All of
// it live from the feed (live.ts); the groups are ListPage's ListGroup.
import { useCallback, useEffect, useRef, useState, type MouseEvent, type ReactNode, type RefObject } from "react";
import { Link, useSearchParams } from "react-router";

import type { GateInfo, NoteInfo, RunEventInfo, RunInfo } from "./api";
import { AgentName } from "./Agents";
import { Body, clock, since } from "./ChatText";
import { GateCard, gateTitle } from "./GateCard";
import { useLive, useLiveStore, type ListLoaded } from "./live";
import { filterGroups, ListGroup, type Entry as ListEntry } from "./ListPage";
import { FIND_PARAM, runPath, sessionPath } from "./paths";
import {
  storedFlowsGroups,
  storedFlowsOrder,
  storeFlowsGroups,
  storeFlowsOrder,
  type FlowsGroup,
  type FlowsOrder,
} from "./prefs";

const HISTORY_FIRST = 10; // the ended runs shown before Show N more

// The run's events the history shows; a transition (`flow`) is its step's note.
const EDGES = ["flow_start", "flow_end", "flow_cancel"];

export const isOpen = (run: RunInfo) => run.status === "active" || run.status === "waiting";

type Lists = { runs: RunInfo[]; notes: NoteInfo[]; events: RunEventInfo[]; gates: GateInfo[] };

export function Flows({ session, run, stopped }: { session: string; run?: string; stopped: boolean }) {
  const live = useLiveStore();
  const state = useLive();
  useEffect(() => live.watch("runs", session), [live, session]);
  useEffect(() => live.watch("notes", session), [live, session]);
  useEffect(() => live.watch("events", session), [live, session]);
  useEffect(() => live.watch("gates", session), [live, session]);
  useEffect(() => live.watch("agents", session), [live, session]); // who links to its page

  const loaded = [state.runs[session], state.notes[session], state.events[session], state.gates[session]] as (
    | ListLoaded<unknown>
    | undefined
  )[];
  const failed = loaded.find((one) => one && "error" in one) as { error: string } | undefined;
  const ready = loaded.every((one) => one && "items" in one);
  const items = (one: unknown) => (one && "items" in (one as object) ? (one as { items: never[] }).items : []);
  const lists: Lists = {
    runs: items(loaded[0]),
    notes: items(loaded[1]),
    events: items(loaded[2]),
    gates: items(loaded[3]),
  };
  let notice;
  if (failed) {
    notice = (
      <p className="problem" role="alert">
        {failed.error}
      </p>
    );
  } else if (!ready) {
    notice = <p className="muted">Loading…</p>;
  }
  // What the overview had when a run's page replaced it, for the way back: its search and
  // its scroll. Flows stays mounted from the overview to a run's page and back.
  const [params] = useSearchParams();
  const find = params.get(FIND_PARAM) ?? "";
  const lastFind = useRef(find);
  const scroll = useRef(0);
  useEffect(() => {
    if (run === undefined) lastFind.current = find;
  }, [run, find]);

  if (notice) return <div className="flows-tab">{notice}</div>;
  const groups = grouped(lists.runs);
  if (run === undefined) return <RunsOverview session={session} groups={groups} query={find} scroll={scroll} />;
  const selected = lists.runs.find((one) => one.name === run);
  const query = lastFind.current ? `?${new URLSearchParams({ [FIND_PARAM]: lastFind.current })}` : "";
  return (
    <div className="flows-tab">
      <div className="list-main">
        <Link className="list-back" to={sessionPath(session, "flows") + query}>
          ‹ All runs ({groups.active.length} open, {groups.ended.length} ended)
        </Link>
        {selected === undefined ? (
          <p className="empty">Run {run} not found</p>
        ) : (
          <RunPage key={selected.name} session={session} run={selected} stopped={stopped} lists={lists} />
        )}
      </div>
    </div>
  );
}

// The tab's overview across its whole column: Active, the open runs as cards with their
// flow's states, and History, the ended ones as rows by days; each group folds (remembered),
// and the search of the tab bar (?find=) finds runs in both.
function RunsOverview({
  session,
  groups,
  query,
  scroll,
}: {
  session: string;
  groups: { active: RunInfo[]; ended: RunInfo[] };
  query: string;
  scroll: RefObject<number>;
}) {
  const [folds, setFolds] = useState(storedFlowsGroups);
  const restore = useCallback((list: HTMLElement | null) => {
    if (list) list.scrollTop = scroll.current;
  }, [scroll]);
  const searching = query.trim() !== "";
  const toggle = (group: FlowsGroup) => {
    const next = { ...folds, [group]: folds[group] === "open" ? "folded" : "open" } as const;
    setFolds(next);
    storeFlowsGroups(next);
  };
  const shown = filterGroups(
    [
      {
        name: "Active",
        tone: "done",
        look: "card",
        entries: groups.active.map((one) => card(session, one)),
        empty: "No active runs",
      },
      {
        name: "History",
        entries: groups.ended.map((one) => entry(session, one)),
        days: true,
        first: HISTORY_FIRST,
        empty: "No ended runs yet",
      },
    ],
    query,
  );
  const ids: FlowsGroup[] = ["active", "history"];
  return (
    <div className="flows-tab">
      <nav
        ref={restore}
        className="runs-overview"
        aria-label="Flow runs"
        onScroll={(event) => (scroll.current = event.currentTarget.scrollTop)}
      >
        {shown.map(({ group, entries }, at) => (
          <ListGroup
            key={group.name}
            group={group}
            entries={entries}
            searching={searching}
            fold={{ open: folds[ids[at]] === "open", onToggle: () => toggle(ids[at]), disabled: searching }}
          />
        ))}
        {searching && shown.every(({ entries }) => entries.length === 0) && (
          <p className="muted list-none">No run matches “{query.trim()}”</p>
        )}
      </nav>
    </div>
  );
}

// The list's groups: the open runs, those waiting for the human first; and the ended or
// cancelled ones, the latest end first.
function grouped(runs: RunInfo[]) {
  const ended = runs.filter((one) => !isOpen(one));
  ended.sort((a, b) => (b.ended_at ?? "").localeCompare(a.ended_at ?? ""));
  return {
    active: [...runs.filter((one) => one.status === "waiting"), ...runs.filter((one) => one.status === "active")],
    ended,
  };
}

// An open run's card: its name, "Waits for you" when it does, its flow and kit and when it
// started; the line of what goes on now; its flow's states, as on its page. Found as a row.
function card(session: string, run: RunInfo): ListEntry {
  const kit = [run.kit.name, run.kit.version].filter(Boolean).join(" ");
  return {
    ...entry(session, run),
    row: (
      <>
        <span className="run-card-top">
          <span className="run-name">{run.name}</span>
          {run.status === "waiting" && <span className="pill waits">Waits for you</span>}
          <span className="run-card-meta">
            {[run.flow, kit, `started ${clock(run.created_at)}`].filter(Boolean).join(" · ")}
          </span>
        </span>
        <span className="run-about">{about(run)}</span>
        <States run={run} />
      </>
    ),
  };
}

// A run's row: its name and one line under it; found by its name, task, flow and state.
function entry(session: string, run: RunInfo): ListEntry {
  return {
    key: run.name,
    to: runPath(session, run.name),
    row: (
      <>
        <span className="run-name">{run.name}</span>
        <span className="run-about">{about(run)}</span>
      </>
    ),
    search: [run.name, run.task, run.flow, run.state],
    tone: run.status === "waiting" ? "waits" : isOpen(run) ? undefined : "dim",
    at: run.ended_at ?? undefined,
  };
}

// One line under a run's name: its state and who acts or what it waits for, and how long
// it has been so; an ended run's status and when it ended (its day heads the rows).
function about(run: RunInfo): string {
  if (!isOpen(run)) return [run.status, run.ended_at && clock(run.ended_at)].filter(Boolean).join(" · ");
  return `${run.state} · ${waitsFor(run)} · ${since(run.since)}`;
}

function waitsFor(run: RunInfo): string {
  if (run.status === "waiting") return run.gate !== null ? `gate #${run.gate}` : run.reason;
  return `→ ${run.acting}`;
}

// How long from one time to another, roughly: "<1 min", "12 min", "1 h 5 min", "1 d 2 h".
function took(from: string, to: string): string {
  const minutes = Math.floor((Date.parse(to) - Date.parse(from)) / 60000);
  if (!(minutes >= 1)) return "<1 min";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return minutes % 60 ? `${hours} h ${minutes % 60} min` : `${hours} h`;
  const days = Math.floor(hours / 24);
  return hours % 24 ? `${days} d ${hours % 24} h` : `${days} d`;
}

// The page is keyed by the run: what is open in its history starts afresh with each run.
function RunPage({ session, run, stopped, lists }: { session: string; run: RunInfo; stopped: boolean; lists: Lists }) {
  const gate = run.gate === null ? undefined : lists.gates.find((one) => one.id === run.gate);
  const open = gate && gate.answer === null ? gate : undefined;
  return (
    <section className="run-page" aria-label={`Run ${run.name}`}>
      <RunHead run={run} />
      <Now session={session} run={run} gate={open} stopped={stopped} lists={lists} />
      <History session={session} run={run} gate={open} lists={lists} />
    </section>
  );
}

const PILLS: Record<string, [string, string]> = {
  active: ["Active", ""],
  waiting: ["Waits for you", "waits"],
  ended: ["Ended", "done"],
  cancelled: ["Cancelled", "dim"],
};

function RunHead({ run }: { run: RunInfo }) {
  const kit = [run.kit.name, run.kit.version].filter(Boolean).join(" ");
  const [label, tone] = PILLS[run.status] ?? [run.status, ""];
  return (
    <header className="run-head">
      <div className="run-title">
        <h3>{run.name}</h3>
        <span className={`pill${tone ? ` ${tone}` : ""}`}>{label}</span>
      </div>
      <p className="run-meta">
        <span>
          flow {run.flow}
          {kit && ` · ${kit}`}
        </span>{" "}
        <span>
          started <time dateTime={run.created_at}>{clock(run.created_at)}</time>
        </span>{" "}
        <span>
          branch <code>{run.branch}</code>
        </span>
      </p>
      {run.task && <Task text={run.task} />}
      <States run={run} />
    </header>
  );
}

// The task's first line, cut to one line, and the whole text on "more".
function Task({ text }: { text: string }) {
  const [all, setAll] = useState(false);
  return (
    <div className="run-task">
      <span className="run-task-label">Task</span>
      {!all && <span className="run-task-first">{text.split("\n")[0]}</span>}
      <button type="button" className="link-button" aria-expanded={all} onClick={() => setAll(!all)}>
        {all ? "less" : "more"}
      </button>
      {all && <p className="run-task-full">{text}</p>}
    </div>
  );
}

// Every state of the flow, in the order it declares them, as a chip: its name (◇ at a gate),
// its visits, who acts in its title; the current one marked (orange while it waits for the
// human), the ones entered solid, the others dashed. A run whose flow the server cannot
// read has none: the problem stands in their place.
function States({ run }: { run: RunInfo }) {
  if (run.problem) {
    return (
      <p className="problem" role="alert">
        Flow cannot be read: {run.problem}
      </p>
    );
  }
  const current = (name: string) => run.state === name && isOpen(run);
  return (
    <ol className="flow-states" aria-label="States">
      {run.states.map((one) => {
        const visits = run.visits[one.name] ?? 0;
        const count = one.max_visits !== null ? `${visits}/${one.max_visits}` : visits > 0 ? `×${visits}` : "";
        const who = one.kind === "gate" ? "you" : (one.agent ?? undefined);
        const classes = [
          "flow-state",
          visits > 0 ? "visited" : "",
          current(one.name) || (run.state === one.name && one.kind === "end") ? "current" : "",
          current(one.name) && run.status === "waiting" ? "waiting" : "",
        ];
        const here = run.state === one.name && (isOpen(run) || one.kind === "end");
        return (
          <li
            key={one.name}
            className={classes.filter(Boolean).join(" ")}
            aria-label={`State ${one.name}`}
            aria-current={here ? "step" : undefined}
            title={who || undefined}
          >
            <b>{one.kind === "gate" ? `◇ ${one.name}` : one.name}</b>
            {count && <small>{count}</small>}
          </li>
        );
      })}
    </ol>
  );
}

// What goes on now: who acts, as the core says it, and the visit; the gate the run waits at,
// compact, or why it waits; or when it ended, the end's or cancel's detail and how long the
// run took.
function Now({
  session,
  run,
  gate,
  stopped,
  lists,
}: {
  session: string;
  run: RunInfo;
  gate?: GateInfo;
  stopped: boolean;
  lists: Lists;
}) {
  if (run.status === "waiting") {
    return (
      <section className="run-now waits" aria-label="Now">
        <span className="now-head">Waits for you · {since(run.since)}</span>
        {gate ? (
          <article className="run-gate" aria-label={`Gate #${gate.id}`}>
            <header className="gate-head">
              <h4 className="gate-title">{gateTitle(gate)}</h4>
              <time dateTime={gate.created_at}>{clock(gate.created_at)}</time>
            </header>
            <GateCard session={session} gate={gate} stopped={stopped} compact />
          </article>
        ) : (
          <span className="now-text">{run.reason}</span>
        )}
      </section>
    );
  }
  if (isOpen(run)) {
    const max = run.states.find((one) => one.name === run.state)?.max_visits ?? null;
    const visits = run.visits[run.state] ?? 0;
    return (
      <section className="run-now" aria-label="Now">
        <span className="now-head">Now · {since(run.since)}</span>
        <span className="now-text">
          {run.acting && (
            <>
              <strong>
                <AgentName session={session} name={run.acting} />
              </strong>
              {" · "}
            </>
          )}
          {run.state} · visit {visits}
          {max !== null && ` of ${max}`}
        </span>
      </section>
    );
  }
  const end = lists.events.filter((one) => one.run === run.name && (one.kind === "flow_end" || one.kind === "flow_cancel")).at(-1);
  const when = run.ended_at;
  const text = [end?.detail, when && `took ${took(run.created_at, when)}`].filter(Boolean).join(" · ");
  return (
    <section className={`run-now ${run.status === "ended" ? "done" : "dim"}`} aria-label="Now">
      <span className="now-head">
        {PILLS[run.status]?.[0] ?? run.status}
        {when && ` · ${clock(when)}`}
      </span>
      {text && <span className="now-text">{text}</span>}
    </section>
  );
}

type Entry = { at: string; rank: number; key: string; note?: NoteInfo; event?: RunEventInfo };

// The run's start, its steps by time, then its end or cancel. The start and the end take
// their place by kind, not by time: a run has no step before its start or after its end,
// and the core writes a step's events before its note in one transaction, each row with
// its own millisecond, so the end can be a little older than the step that led to it.
function entries(run: RunInfo, lists: Lists): Entry[] {
  const notes = lists.notes
    .filter((one) => one.run === run.name)
    .map((note) => ({ at: note.created_at, rank: 1, key: `note-${note.id}`, note }));
  const events = lists.events
    .filter((one) => one.run === run.name && EDGES.includes(one.kind))
    .map((event) => ({ at: event.created_at, rank: event.kind === "flow_start" ? 0 : 2, key: `event-${event.id}`, event }));
  return [...notes, ...events].sort((a, b) => a.rank - b.rank || a.at.localeCompare(b.at));
}

// What the history opens by itself: when the page opens, the latest note with a body; while
// a gate is open, the notes it needs (by their ids, as the core chose them).
const latestWithBody = (all: Entry[]) => all.filter((one) => one.note?.body).at(-1)?.key;
const needed = (gate?: GateInfo) =>
  (gate?.needs ?? []).flatMap((need) => (need.note === null ? [] : [`note-${need.note.id}`]));

// The run's history: every event in one feed, the newest first or the oldest (remembered);
// a step opens to its facts and its note's body. A note that comes later with a body opens
// too.
function History({ session, run, gate, lists }: { session: string; run: RunInfo; gate?: GateInfo; lists: Lists }) {
  const all = entries(run, lists);
  const [order, setOrder] = useState<FlowsOrder>(storedFlowsOrder);
  const [opened, setOpened] = useState(
    () => new Set([latestWithBody(all), ...needed(gate)].filter((key): key is string => key !== undefined)),
  );
  const [seen, setSeen] = useState(() => new Set(all.map((one) => one.key)));
  const [gateSeen, setGateSeen] = useState(gate?.id);
  const fresh = all.filter((one) => !seen.has(one.key));
  if (fresh.length > 0 || gate?.id !== gateSeen) {
    const next = new Set(opened);
    for (const one of fresh) if (one.note?.body) next.add(one.key);
    if (gate?.id !== gateSeen) for (const key of needed(gate)) next.add(key);
    setSeen(new Set(all.map((one) => one.key)));
    setGateSeen(gate?.id);
    setOpened(next);
  }

  const steps = all.filter((one) => one.note).map((one) => one.key);
  const allOpen = steps.length > 0 && steps.every((key) => opened.has(key));
  const toggle = (key: string) => {
    const next = new Set(opened);
    if (!next.delete(key)) next.add(key);
    setOpened(next);
  };
  const turn = () => {
    const next = order === "newest" ? "oldest" : "newest";
    setOrder(next);
    storeFlowsOrder(next);
  };
  const rows = all.map((one, at) => (
    <Row
      key={one.key}
      session={session}
      run={run}
      entry={one}
      took={at > 0 ? took(all[at - 1].at, one.at) : undefined}
      open={opened.has(one.key)}
      onToggle={() => toggle(one.key)}
    />
  ));
  return (
    <section className="run-history" aria-labelledby="run-history-name">
      <div className="history-head">
        <h4 id="run-history-name">History · {all.length} events</h4>
        <span className="history-actions">
          <button type="button" className="link-button" onClick={turn}>
            {order === "newest" ? "Newest first ↓" : "Oldest first ↑"}
          </button>
          {steps.length > 0 && (
            <>
              {" · "}
              <button type="button" className="link-button" onClick={() => setOpened(new Set(allOpen ? [] : steps))}>
                {allOpen ? "Close all" : "Open all"}
              </button>
            </>
          )}
        </span>
      </div>
      <ol className="run-feed" aria-label="Events">
        {order === "newest" ? rows.reverse() : rows}
      </ol>
    </section>
  );
}

// A step goes back when it leads to a state the flow declares no later than the one it
// left; unknown without the flow (its problem).
function goesBack(run: RunInfo, note: NoteInfo): boolean {
  const order = run.states.map((one) => one.name);
  const from = order.indexOf(note.state);
  const to = order.indexOf(note.target);
  return from >= 0 && to >= 0 && to <= from;
}

// One line of the history. A step: when, a dot (green; orange for a way back or the human's
// answer), who, `from [outcome] → to` and its summary, which opens its facts and its note's
// body. A note kept before LADO 0.18 has only its state; the human's flow-set has no
// outcome; a loop limit's answer is the human's override with one. The start, end and
// cancel are one line each (a blue dot), never opened.
function Row({
  session,
  run,
  entry,
  took,
  open,
  onToggle,
}: {
  session: string;
  run: RunInfo;
  entry: Entry;
  took?: string;
  open: boolean;
  onToggle: () => void;
}) {
  const time = <time dateTime={entry.at}>{clock(entry.at)}</time>;
  if (entry.event) {
    const event = entry.event;
    const by = event.actor === "lado" ? "" : event.actor;
    let top: ReactNode;
    if (event.kind === "flow_cancel") top = <span className="feed-move">cancelled{by && ` by ${by}`}</span>;
    else {
      top = (
        <>
          {by && (
            <>
              <span className="feed-who">
                <AgentName session={session} name={by} />
              </span>{" "}
            </>
          )}
          <span className="feed-move">{event.kind === "flow_start" ? "started the run" : "ended the run"}</span>
        </>
      );
    }
    return (
      <li className="feed-row">
        <div className="feed-line">
          {time}
          <span className="feed-dot edge" aria-hidden="true" />
          <div className="feed-what">
            <div className="feed-top">{top}</div>
            {event.kind === "flow_start" && event.detail && <span className="feed-summary">{event.detail}</span>}
          </div>
        </div>
      </li>
    );
  }
  const note = entry.note!;
  const human = note.actor === "human";
  const back = !run.problem && goesBack(run, note);
  const label = note.kind === "override" ? (note.outcome ? "loop limit" : "flow-set") : "";
  const who = note.actor && (human ? "you" : <AgentName session={session} name={note.actor} />);
  const facts: [string, ReactNode][] = [
    ["Who", who],
    ["From", note.state],
    ["Outcome", note.outcome],
    ["To", note.target],
    ["Step took", took],
  ];
  // A click anywhere on the line opens it, but on a link (who) or the summary's own button.
  const click = (event: MouseEvent) => {
    if (!(event.target as Element).closest("a, button")) onToggle();
  };
  return (
    <li className={`feed-row step${open ? " open" : ""}`}>
      <div className="feed-line" onClick={click}>
        {time}
        <span className={`feed-dot ${back || human ? "back" : "ok"}`} aria-hidden="true" />
        <div className="feed-what">
          <div className="feed-top">
            {who && (
              <>
                <span className="feed-who">{who}</span>{" "}
              </>
            )}
            <span className="feed-move">
              {note.state}
              {note.outcome && (
                <>
                  {" "}
                  <span className={`feed-chip${back ? " back" : ""}`}>{note.outcome}</span>
                </>
              )}
              {note.target && ` → ${note.target}`}
            </span>
            {label && (
              <>
                {" "}
                <span className="feed-label">{label}</span>
              </>
            )}
          </div>
          <button type="button" className="feed-summary" aria-expanded={open} onClick={onToggle}>
            {note.summary}
          </button>
        </div>
        <span className="feed-chevron" aria-hidden="true">
          ▸
        </span>
      </div>
      {open && (
        <div className="feed-detail">
          <dl className="feed-facts">
            {facts
              .filter(([, value]) => value)
              .map(([name, value]) => (
                <div key={name}>
                  <dt>{name}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
          </dl>
          {note.body ? <Body text={note.body} /> : human && <p className="feed-none">No comment.</p>}
        </div>
      )}
    </li>
  );
}
