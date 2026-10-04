// The session's Flows tab (docs/design/ui.md, Flows): its runs on the left, in groups, and
// the selected run's page on the right: its head, every state of its flow, its open gate,
// answered in place, and the timeline of its steps. A step is a note (NoteInfo: who
// reported it, the outcome and where it leads); the run's start, end and cancel are its
// events. All of it live from the feed (live.ts); in a narrow column the list is a select.
import { useEffect, useRef, useState } from "react";
import { Navigate, NavLink, useNavigate } from "react-router";

import type { GateInfo, NoteInfo, RunEventInfo, RunInfo } from "./api";
import { AgentName } from "./Agents";
import { clock, day, Preview, since } from "./ChatText";
import { FoldToggle } from "./Fold";
import { Gate } from "./GateCard";
import { useLive, useLiveStore, type ListLoaded } from "./live";
import { runPath } from "./paths";
import { storedFlowsEndedOpen, storeFlowsEndedOpen } from "./prefs";
import { useNarrow } from "./Splitter";

const NOTE_LINES = 6; // the lines of a step's note shown before Show all

// The run's events the timeline shows; a transition (`flow`) is its step's note.
const EVENT_WORDS: Record<string, string> = { flow_start: "started", flow_end: "ended", flow_cancel: "cancelled" };

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
  const root = useRef<HTMLDivElement>(null);
  const narrow = useNarrow(root);

  const loaded = [state.runs[session], state.notes[session], state.events[session], state.gates[session]] as (
    | ListLoaded<unknown>
    | undefined
  )[];
  const failed = loaded.find((one) => one && "error" in one) as { error: string } | undefined;
  const ready = loaded.every((one) => one && "items" in one);
  let body;
  if (failed) {
    body = (
      <p className="problem" role="alert">
        {failed.error}
      </p>
    );
  } else if (!ready) {
    body = <p className="muted">Loading…</p>;
  } else {
    const items = (one: unknown) => (one as { items: never[] }).items;
    const lists: Lists = {
      runs: items(loaded[0]),
      notes: items(loaded[1]),
      events: items(loaded[2]),
      gates: items(loaded[3]),
    };
    body = <FlowsBody session={session} run={run} stopped={stopped} lists={lists} narrow={narrow} />;
  }
  return (
    <div ref={root} className={`flows${narrow ? " narrow" : ""}`}>
      {body}
    </div>
  );
}

// The list's groups: waiting for the human, active, and ended (ended or cancelled), the
// latest end first.
function grouped(runs: RunInfo[]) {
  const ended = runs.filter((one) => !isOpen(one));
  ended.sort((a, b) => (b.ended_at ?? "").localeCompare(a.ended_at ?? ""));
  return {
    waiting: runs.filter((one) => one.status === "waiting"),
    active: runs.filter((one) => one.status === "active"),
    ended,
  };
}

function FlowsBody({
  session,
  run,
  stopped,
  lists,
  narrow,
}: {
  session: string;
  run?: string;
  stopped: boolean;
  lists: Lists;
  narrow: boolean;
}) {
  const groups = grouped(lists.runs);
  if (run === undefined) {
    const first = groups.waiting[0] ?? groups.active[0];
    if (first) return <Navigate replace to={runPath(session, first.name)} />;
  }
  const selected = lists.runs.find((one) => one.name === run);
  let page;
  if (run === undefined) {
    page = <p className="empty">{lists.runs.length === 0 ? "No flow runs yet" : "Select a run"}</p>;
  } else if (selected === undefined) {
    page = <p className="empty">Run {run} not found</p>;
  } else {
    page = <RunPage session={session} run={selected} stopped={stopped} lists={lists} />;
  }
  if (lists.runs.length === 0) return page;
  return (
    <>
      {narrow ? (
        <RunSelect session={session} run={run} groups={groups} />
      ) : (
        <RunList session={session} groups={groups} />
      )}
      <div className="flow-run">{page}</div>
    </>
  );
}

type Groups = ReturnType<typeof grouped>;

function RunList({ session, groups }: { session: string; groups: Groups }) {
  const [endedOpen, setEndedOpen] = useState(storedFlowsEndedOpen);
  const toggle = () => {
    setEndedOpen(!endedOpen);
    storeFlowsEndedOpen(!endedOpen);
  };
  return (
    <nav className="run-list" aria-label="Flow runs">
      <RunGroup session={session} name="Waiting for you" runs={groups.waiting} />
      <RunGroup session={session} name="Active" runs={groups.active} />
      {groups.ended.length > 0 && (
        <FoldToggle name="Ended" count={groups.ended.length} open={endedOpen} controls="ended-runs" onToggle={toggle} />
      )}
      {endedOpen && <RunGroup session={session} name="Ended" id="ended-runs" runs={groups.ended} hideName />}
    </nav>
  );
}

function RunGroup({
  session,
  name,
  runs,
  id,
  hideName = false,
}: {
  session: string;
  name: string;
  runs: RunInfo[];
  id?: string;
  hideName?: boolean;
}) {
  if (runs.length === 0) return null;
  const slug = name.toLowerCase().replace(/\s+/g, "-");
  const headId = `runs-${slug}`;
  return (
    <section
      className={`run-group runs-${slug}`}
      id={id}
      aria-label={hideName ? name : undefined}
      aria-labelledby={hideName ? undefined : headId}
    >
      {!hideName && (
        <h3 id={headId} className="group-name">
          {name}
        </h3>
      )}
      <ul>
        {runs.map((run) => (
          <li key={run.name}>
            <NavLink
              to={runPath(session, run.name)}
              className={`run-link${run.status === "waiting" ? " waits" : ""}${isOpen(run) ? "" : " dim"}`}
            >
              <span className="run-name">{run.name}</span>
              <span className="run-about">{about(run)}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </section>
  );
}

// One line under a run's name: its state and who acts or what it waits for, and how long
// it has been so; an ended run's status and when it ended.
function about(run: RunInfo): string {
  if (!isOpen(run)) return [run.status, run.ended_at && day(run.ended_at)].filter(Boolean).join(" · ");
  return `${run.state} · ${waitsFor(run)} · ${since(run.since)}`;
}

function waitsFor(run: RunInfo): string {
  if (run.status === "waiting") return run.gate !== null ? `gate #${run.gate}` : run.reason;
  return `→ ${run.acting}`;
}


function RunSelect({ session, run, groups }: { session: string; run?: string; groups: Groups }) {
  const navigate = useNavigate();
  const options = (runs: RunInfo[]) =>
    runs.map((one) => (
      <option key={one.name} value={one.name}>
        {one.name} · {about(one)}
      </option>
    ));
  return (
    <select
      className="run-select"
      aria-label="Flow run"
      value={run ?? ""}
      onChange={(event) => navigate(runPath(session, event.target.value))}
    >
      {run === undefined && <option value="">Select a run</option>}
      {groups.waiting.length > 0 && <optgroup label="Waiting for you">{options(groups.waiting)}</optgroup>}
      {groups.active.length > 0 && <optgroup label="Active">{options(groups.active)}</optgroup>}
      {groups.ended.length > 0 && <optgroup label={`Ended (${groups.ended.length})`}>{options(groups.ended)}</optgroup>}
    </select>
  );
}

function RunPage({ session, run, stopped, lists }: { session: string; run: RunInfo; stopped: boolean; lists: Lists }) {
  const gate = run.gate === null ? undefined : lists.gates.find((one) => one.id === run.gate);
  return (
    <section className="run-page" aria-label={`Run ${run.name}`}>
      <RunHead session={session} run={run} />
      <StatePicture run={run} />
      {gate && gate.answer === null && <Gate session={session} gate={gate} stopped={stopped} />}
      <Timeline session={session} run={run} gate={gate} lists={lists} />
    </section>
  );
}

function RunHead({ session, run }: { session: string; run: RunInfo }) {
  const kit = [run.kit.name, run.kit.version].filter(Boolean).join(" ");
  return (
    <header className="run-head">
      <div className="run-title">
        <h3>{run.name}</h3>
        <span className="run-meta">
          flow {run.flow}
          {kit && ` · ${kit}`} · started <time dateTime={run.created_at}>{clock(run.created_at)}</time>
        </span>
      </div>
      <p className="run-task">{run.task}</p>
      <p className="run-now">
        <strong>{run.state}</strong> · {run.status}
        {run.acting && (
          <>
            {" · "}
            <AgentName session={session} name={run.acting} />
          </>
        )}
        {run.reason && ` · ${run.reason}`} · branch <code>{run.branch}</code>
      </p>
    </header>
  );
}

// Every state of the flow, in the order it declares them: name, who acts (you at a gate),
// visits; the current one marked (orange while it waits for the human), the ones entered
// solid, the others dashed. Under them the ways back: outcomes that lead to an earlier
// state or to the same one. A run whose flow the server cannot read has none: the problem
// stands in their place.
function StatePicture({ run }: { run: RunInfo }) {
  if (run.problem) {
    return (
      <p className="problem" role="alert">
        Flow cannot be read: {run.problem}
      </p>
    );
  }
  const order = run.states.map((one) => one.name);
  const back = run.states.flatMap((from, at) =>
    Object.entries(from.outcomes)
      .filter(([, target]) => order.indexOf(target) >= 0 && order.indexOf(target) <= at)
      .map(([outcome, target]) => `↶ ${from.name} –${outcome}→ ${target}`),
  );
  const current = (name: string) => run.state === name && isOpen(run);
  return (
    <div className="flow-picture">
      <ol className="flow-states" aria-label="States">
        {run.states.map((one) => {
          const visits = run.visits[one.name] ?? 0;
          const count = one.max_visits !== null ? `${visits}/${one.max_visits}` : visits > 0 ? `×${visits}` : "";
          const who = one.kind === "gate" ? "you" : (one.agent ?? "");
          const sub = [who, count].filter(Boolean).join(" · ");
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
            >
              <b>{one.kind === "gate" ? `◇ ${one.name}` : one.name}</b>
              {sub && <span>{sub}</span>}
            </li>
          );
        })}
      </ol>
      {back.length > 0 && (
        <ul className="flow-back" aria-label="Ways back">
          {back.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
    </div>
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
    .filter((one) => one.run === run.name && one.kind in EVENT_WORDS)
    .map((event) => ({ at: event.created_at, rank: event.kind === "flow_start" ? 0 : 2, key: `event-${event.id}`, event }));
  return [...notes, ...events].sort((a, b) => a.rank - b.rank || a.at.localeCompare(b.at));
}

function Timeline({ session, run, gate, lists }: { session: string; run: RunInfo; gate?: GateInfo; lists: Lists }) {
  return (
    <ol className="run-steps" aria-label="Steps">
      {entries(run, lists).map((entry) =>
        entry.note ? (
          <Step key={entry.key} session={session} note={entry.note} />
        ) : (
          <RunEvent key={entry.key} event={entry.event!} />
        ),
      )}
      <Now run={run} gate={gate} />
    </ol>
  );
}

// A step: when, from which state, who reported it, the outcome and where it leads; then
// its note. A note kept before LADO 0.18 has none of these but its state; the human's
// flow-set has no outcome; a loop limit's answer is the human's override with one.
function Step({ session, note }: { session: string; note: NoteInfo }) {
  const loop = note.kind === "override" && note.outcome !== "";
  const parts = [note.state, loop && "loop limit"].filter(Boolean).join(" · ");
  const moves = [note.outcome, note.target].filter(Boolean).map((one) => ` → ${one}`);
  return (
    <li className={`run-step${note.kind === "override" ? " override" : ""}`}>
      <span className="step-line">
        <time dateTime={note.created_at}>{clock(note.created_at)}</time> · {parts}
        {note.actor && (
          <>
            {" · "}
            <AgentName session={session} name={note.actor} />
          </>
        )}
        {moves.join("")}
      </span>
      <div className="step-note">
        <strong>{note.summary}</strong>
        {note.body && <Preview text={note.body} lines={NOTE_LINES} />}
      </div>
    </li>
  );
}

function RunEvent({ event }: { event: RunEventInfo }) {
  const by = event.actor === "lado" ? "" : ` by ${event.actor}`;
  return (
    <li className={`run-step run-${event.kind}`}>
      <span className="step-line">
        <time dateTime={event.created_at}>{clock(event.created_at)}</time> · {EVENT_WORDS[event.kind]}
        {by}
        {event.detail && ` · ${event.detail}`}
      </span>
    </li>
  );
}

// What goes on now: who acts, as the core says it, and the visit; or the gate it waits at.
function Now({ run, gate }: { run: RunInfo; gate?: GateInfo }) {
  if (!isOpen(run)) return null;
  let text;
  if (run.status === "waiting") {
    const where = gate?.state ?? run.state;
    text = `now · ${where} · waits for you${run.gate !== null ? ` (gate #${run.gate})` : `: ${run.reason}`}`;
  } else {
    const max = run.states.find((one) => one.name === run.state)?.max_visits ?? null;
    const visits = run.visits[run.state] ?? 0;
    text = `now · ${run.state} · ${run.acting} · visit ${visits}${max !== null ? ` of ${max}` : ""}`;
  }
  return (
    <li className={`run-step now${run.status === "waiting" ? " waits" : ""}`}>
      <span className="step-line">{text}</span>
    </li>
  );
}
