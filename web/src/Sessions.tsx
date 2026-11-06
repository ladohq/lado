// Sessions: the list on the left (from /api/sessions, searched by name here), the selected
// session on the right with its tabs. The list's width is dragged on its edge and remembered;
// the list collapses to a strip of the sessions' icons (remembered too). On a phone the list
// is the Sessions page and a session's page shows the session alone (docs/design/ui.md,
// Phone layout).
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
  type RefObject,
} from "react";
import { createPortal } from "react-dom";
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
  useOutletContext,
  useParams,
  useSearchParams,
} from "react-router";

import { Agents } from "./Agents";
import { ArtifactPanel } from "./ArtifactPanel";
import { Artifacts } from "./ArtifactsTable";
import { getSessionAbout, setSessionTitle, type SessionAbout, type SessionInfo, type SessionStatus } from "./api";
import { Chat, FOCUS_CHAT, focusChat } from "./Chat";
import { duration } from "./ChatText";
import { fitColumns, LIST_STRIP, listMax } from "./columns";
import { Flows, isOpen } from "./Flows";
import { ForgetManyDialog } from "./ForgetMany";
import { GroupHead, type Tone } from "./GroupHead";
import {
  ActivityIcon,
  AgentsIcon,
  ArtifactsIcon,
  BetweenIcon,
  ChevronIcon,
  CollapsePanelIcon,
  FindIcon,
  FlowsIcon,
  ForgetIcon,
  GitIcon,
  ProblemIcon,
} from "./icons";
import { useLaunch, type StartedState } from "./Launch";
import { isLive, useLive, useLiveStore, type Loaded } from "./live";
import { escapeIsTaken, useBelow, useDismiss } from "./Menu";
import { SessionActions } from "./SessionControl";
import { label } from "./sessionLabel";
import { SessionRowMenu } from "./SessionRowMenu";
import { TerminalPanel, usePutBackTerminals, type PanelColumn } from "./Terminals";
import { NotFound } from "./pages";
import { FIND_PARAM, isTab, projectPath, sessionPath, TABS, VIEW_PARAM, type Tab } from "./paths";
import {
  SESSIONS_WIDTH,
  storeAgentMessages,
  storedAgentMessages,
  storedLastColumn,
  storedPanel,
  storedSessionGroups,
  storedSessionsList,
  storeLastColumn,
  storePanel,
  storeSessionGroups,
  storeSessionsList,
  type Column,
  type ColumnPrefs,
  type SessionGroup,
} from "./prefs";
import { useMedia, usePhone } from "./phone";
import { DetailsPopover, GitTip, SessionDetails } from "./SessionDetails";
import { useSkipSlot, useTitle, useTopBar } from "./Shell";
import { Splitter, useStripFocus, useWidth } from "./Splitter";
import { Team } from "./Team";
import { TitleEdit } from "./TitleEdit";
import { Tooltip } from "./Tooltip";

// What each status means to the human, in the words of `lado ls`.
const STATUS: Record<SessionStatus, string> = {
  running: "running",
  stopped: "stopped",
  tmux_gone: "tmux session is gone",
  loop_down: "session loop not running",
};

// The pages inside (NoSession, Session) name themselves: a session's unknown tab is Not found.
// The list and the session's header follow the change feed (live.ts).
export function Sessions() {
  const loaded = useLive().sessions;
  const launch = useLaunch();
  const [query, setQuery] = useState("");
  const [folds, setFolds] = useState(storedSessionGroups);
  const current = useParams().name;

  const wanted = query.trim().toLowerCase();
  const found =
    loaded && "sessions" in loaded
      ? loaded.sessions.filter((one) => [one.name, one.title ?? ""].some((text) => text.toLowerCase().includes(wanted)))
      : [];
  const groups = grouped(found);
  const toggle = (group: SessionGroup) => {
    const next = { ...folds, [group]: folds[group] === "open" ? "folded" : "open" } as const;
    setFolds(next);
    storeSessionGroups(next);
  };
  // The stopped sessions Forget stopped sessions… was pressed for, as the group showed them
  // then (the search's): the window keeps them while it is open.
  const [forgetting, setForgetting] = useState<SessionInfo[] | null>(null);
  const forgetStopped = (
    <Tooltip tip="Forget stopped sessions…">
      <button
        type="button"
        className="group-action"
        aria-label="Forget stopped sessions…"
        aria-haspopup="dialog"
        onClick={() => setForgetting(groups.stopped)}
      >
        <ForgetIcon />
      </button>
    </Tooltip>
  );
  const group = (id: SessionGroup) => (
    <Group
      id={id}
      sessions={groups[id]}
      open={wanted !== "" || folds[id] === "open"}
      searching={wanted !== ""}
      current={current}
      onToggle={() => toggle(id)}
      action={id === "stopped" ? forgetStopped : undefined}
    />
  );
  const [page, room] = useWidth<HTMLDivElement>();
  const columns = useSessionColumns(room);
  const { list } = columns;
  // On a phone (phone.ts) Sessions is the list and a session's page the session alone: no
  // strip, no edge, nothing of the computer's list read or written.
  const phone = usePhone();
  // At 601 to 900 px the strip is always there and the open list lies over the session.
  const over = phone === null && list.over;
  const strip = phone === null && (list.folded || over);
  const showsList = phone === null ? !list.folded : current === undefined;
  const focus = useStripFocus(list.folded);
  const openList = (open: boolean) => {
    focus.toggled();
    if (open) list.open();
    else list.fold();
  };
  const box = useRef<HTMLDivElement>(null);
  // A press beside the list closes it, the focus back on Sessions, after the press's own default.
  // The strip's Sessions closes it by its own click, and what takes the focus by the press keeps
  // it.
  const { open: stripOpen } = focus;
  const pressedAway = useCallback(
    (event: MouseEvent) => {
      const target = event.target as Element;
      if (target.closest(".sessions-open")) return;
      list.fold();
      if (!target.closest(TAKES_FOCUS)) setTimeout(() => stripOpen.current?.focus());
    },
    [stripOpen, list],
  );
  useDismiss(over, box, pressedAway);
  useEffect(() => {
    if (!over) return;
    const close = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || escapeIsTaken(event.target)) return;
      focus.toggled();
      list.fold();
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [over, focus, list]);
  const newSession = (
    <button type="button" className="plus" aria-label="New session" title="New session" onClick={() => launch()}>
      <span aria-hidden="true">+</span>
    </button>
  );
  // The session keeps its place in the page whether the list is open or not: its terminals
  // stay connected.
  return (
    <div
      ref={page}
      className={strip ? "sessions collapsed" : "sessions"}
      style={phone ? undefined : ({ "--list-width": `${strip ? LIST_STRIP : list.width}px` } as CSSProperties)}
    >
      {phone === null && !strip && (
        <Splitter
          label="Resize the session list"
          edge="right"
          width={list.width}
          bounds={{ ...SESSIONS_WIDTH, max: list.max }}
          onChange={list.setWidth}
        />
      )}
      {strip && (
        <SessionStrip
          loaded={loaded}
          current={current}
          open={!list.folded}
          openRef={focus.open}
          onToggle={() => openList(list.folded)}
        >
          {newSession}
        </SessionStrip>
      )}
      {showsList && (
        <div
          ref={box}
          className={over ? "session-list over" : "session-list"}
          onClick={(event) => {
            if (over && (event.target as Element).closest("a.session-link")) list.fold();
          }}
        >
          <div className="session-list-head">
            <h2>Sessions</h2>
            {newSession}
            {phone === null && (
              <button
                ref={focus.collapse}
                type="button"
                className="ghost"
                aria-label="Collapse sessions"
                title="Collapse sessions"
                onClick={() => openList(false)}
              >
                <CollapsePanelIcon side="left" />
              </button>
            )}
          </div>
          <input
            type="search"
            className="search"
            placeholder="Find a session"
            aria-label="Find a session"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <nav aria-label="Sessions">
            {loaded === null && <p className="muted">Loading…</p>}
            {loaded && "error" in loaded && (
              <p className="problem" role="alert">
                {loaded.error}
              </p>
            )}
            {loaded && "sessions" in loaded && (
              <>
                {group("needs-you")}
                {group("running")}
                {group("stopped")}
              </>
            )}
          </nav>
        </div>
      )}
      <div className="session-detail">
        <Outlet context={{ loaded, panel: columns.panel } satisfies SessionsOutlet} />
      </div>
      {forgetting && <ForgetManyDialog sessions={forgetting} onClose={() => setForgetting(null)} />}
    </div>
  );
}

// What the page gives what it shows: the sessions, and the terminal panel's part of the columns.
type SessionsOutlet = { loaded: Loaded; panel: PanelColumn };

// The window where a session's page stands still and its columns lie over it (styles.css).
const NARROW = "(max-width: 900px)";

// The session list's part of the columns: `max`, the widest its edge goes now; `over`, it lies
// open over the session (601 to 900 px).
type ListColumn = {
  folded: boolean;
  width: number;
  max: number;
  over: boolean;
  open: () => void;
  fold: () => void;
  setWidth: (width: number) => void;
};

// A column's stored prefs and their one writer: what comes through it is the human's choice.
function useColumnPrefs(stored: () => ColumnPrefs, store: (prefs: ColumnPrefs) => void) {
  const [prefs, setPrefs] = useState(stored);
  const keep = useCallback(
    (change: Partial<ColumnPrefs>) => {
      setPrefs((now) => {
        const next = { ...now, ...change, chosen: true };
        store(next);
        return next;
      });
    },
    [store],
  );
  return [prefs, keep] as const;
}

// The columns beside the chat, what `fitColumns` makes of the human's choices. Each stored key
// has its one writer here, and only what the human does reaches it: at 601 to 900 px both
// columns start folded whatever is stored, and what opens there lies over the session and
// is not remembered.
function useSessionColumns(room: number | null): { list: ListColumn; panel: PanelColumn } {
  const [list, keepList] = useColumnPrefs(storedSessionsList, storeSessionsList);
  const [panel, keepPanel] = useColumnPrefs(storedPanel, storePanel);
  const [last, setLast] = useState<Column | null>(storedLastColumn);
  const openedLast = useCallback((column: Column) => {
    setLast(column);
    storeLastColumn(column);
  }, []);
  const [control, setControl] = useState(false);
  const [over, setOver] = useState<"list" | "terminals" | null>(null);
  const narrow = useMedia(NARROW);
  useEffect(() => {
    if (!narrow) setOver(null);
  }, [narrow]);
  const width = list.width ?? SESSIONS_WIDTH.initial;
  // Before the first measure nothing folds: the stored choice shows, and no terminal is made.
  const input = { room: room ?? Infinity, list: { ...list, width }, panel, last, control };
  const fit = fitColumns(input);
  const max = Math.max(SESSIONS_WIDTH.min, Math.min(SESSIONS_WIDTH.max, listMax(input)));
  const listColumn = useMemo(
    () => ({
      folded: narrow ? over !== "list" : fit.listFolded,
      width,
      max,
      over: narrow && over === "list",
      open: () => {
        if (narrow) return setOver("list");
        openedLast("list");
        keepList({ collapsed: false });
      },
      fold: () => {
        if (narrow) setOver(null);
        else keepList({ collapsed: true });
      },
      setWidth: (next: number) => keepList({ width: next }),
    }),
    [narrow, over, fit.listFolded, width, max, keepList, openedLast],
  );
  const panelColumn = useMemo(
    () => ({
      folded: narrow ? over !== "terminals" : fit.panelFolded,
      width: fit.panelWidth,
      over: narrow,
      ready: room !== null || typeof ResizeObserver === "undefined",
      open: () => {
        if (narrow) return setOver("terminals");
        openedLast("panel");
        keepPanel({ collapsed: false });
      },
      fold: () => {
        if (narrow) setOver(null);
        else keepPanel({ collapsed: true });
      },
      setWidth: (next: number | null) => keepPanel({ width: next }),
      setControl,
    }),
    [narrow, over, fit.panelFolded, fit.panelWidth, room, keepPanel, openedLast],
  );
  return { list: listColumn, panel: panelColumn };
}

// The list collapsed to a strip: Sessions opens it again (and at 601 to 900 px, where the strip
// stays under the open list, closes it), then New session (`children`), then an icon per
// session not stopped, in the open list's order (those that need the human first, a line after
// them), the open session's scrolled into view. While the list loads the icons' column is empty
// and busy; when it cannot load, an alert says why, as the open list does.
function SessionStrip({
  loaded,
  current,
  open,
  openRef,
  onToggle,
  children,
}: {
  loaded: Loaded;
  current?: string;
  open: boolean;
  openRef: RefObject<HTMLButtonElement | null>;
  onToggle: () => void;
  children: ReactNode;
}) {
  const groups = loaded && "sessions" in loaded ? grouped(loaded.sessions) : null;
  const marks = badges([...(groups?.["needs-you"] ?? []), ...(groups?.running ?? [])]);
  // By the list's own scroll: Chromium's Tab would start from an icon scrolled to with
  // scrollIntoView (Terminals.tsx).
  const icons = useRef<HTMLUListElement>(null);
  const known = groups !== null;
  useLayoutEffect(() => {
    const list = icons.current;
    const on = list?.querySelector('[aria-current="page"]');
    if (!list || !on) return;
    const box = list.getBoundingClientRect();
    const icon = on.getBoundingClientRect();
    list.scrollLeft += Math.min(0, icon.left - box.left) + Math.max(0, icon.right - box.right);
    list.scrollTop += Math.min(0, icon.top - box.top) + Math.max(0, icon.bottom - box.bottom);
  }, [current, known]);
  const icon = (session: SessionInfo) => (
    <StripIcon key={session.name} session={session} mark={marks.get(session.name) ?? ""} />
  );
  return (
    <nav className="sessions-strip" aria-label="Sessions">
      <button
        ref={openRef}
        type="button"
        className="strip-open sessions-open"
        title={open ? "Hide the sessions" : "Show the sessions"}
        aria-expanded={open}
        onClick={onToggle}
      >
        Sessions
      </button>
      {children}
      {loaded && "error" in loaded ? (
        <Tooltip tip={<div className="tooltip-line">{loaded.error}</div>}>
          <span className="strip-problem" role="alert" aria-label={loaded.error} tabIndex={0}>
            <ProblemIcon />
          </span>
        </Tooltip>
      ) : (
        <ul ref={icons} className="strip-icons" aria-busy={groups === null || undefined}>
          {groups?.["needs-you"].map(icon)}
          {groups && groups["needs-you"].length > 0 && groups.running.length > 0 && (
            <li className="strip-gap" aria-hidden="true" />
          )}
          {groups?.running.map(icon)}
        </ul>
      )}
    </nav>
  );
}

// A session's two letters: the first of its first two words, else its first two letters.
// Letters are whole characters (code points), as a title may start with an emoji.
const initials = (name: string) => {
  const words = name.split(/[-_./\s]+/).filter(Boolean);
  const first = (text: string) => [...text][0];
  return (words.length > 1 ? first(words[0]) + first(words[1]) : [...name].slice(0, 2).join("")).toUpperCase();
};

// A session's badge: the last 3 digits of a title (or name) that starts with `<word>-<number>`,
// as a task's session does, else its two letters.
const badge = (session: SessionInfo) => {
  const called = label(session);
  return called.match(/^\p{L}+-(\d+)/u)?.[1].slice(-3) ?? initials(called);
};

// The sessions' badges in the strip's order, by name: a later one alike gets a mark (`154·2`).
function badges(sessions: SessionInfo[]): Map<string, string> {
  const seen = new Map<string, number>();
  return new Map(
    sessions.map((session) => {
      const text = badge(session);
      const times = (seen.get(text) ?? 0) + 1;
      seen.set(text, times);
      return [session.name, times === 1 ? text : `${text}·${times}`];
    }),
  );
}

function StripIcon({ session, mark }: { session: SessionInfo; mark: string }) {
  const needsYou = waits(session);
  const working = workWord(session);
  const called = label(session);
  return (
    <li>
      <Tooltip tip={<SessionTip session={session} />}>
        <NavLink
          to={sessionPath(session.name)}
          className={`strip-session${needsYou ? " waits" : ""}${[...mark].length > 3 ? " long" : ""}`}
          aria-label={needsYou ? `${called}, needs you` : working ? `${called}, ${working}` : called}
        >
          {mark}
          {needsYou && <span className="dot dot-small dot-waiting" aria-hidden="true" />}
          {working && <span className={`dot dot-small activity-${working}`} aria-hidden="true" />}
        </NavLink>
      </Tooltip>
    </li>
  );
}

// Who a session is, the card of its row and of its icon: its title and name (or its name),
// status and agents, how long it ran (the icons have no row line), what waits for the
// human, its folder, its kits, provider and permission mode; a stopped one, how to bring it back (Resume is in the
// session's head). Its status word explains the colours of the row and the icon: in its
// group's tone, a session in trouble (tmux gone, loop down) in the danger colour.
function SessionTip({ session }: { session: SessionInfo }) {
  const trouble = session.status === "tmux_gone" || session.status === "loop_down";
  const mode = session.permission_mode ? ` · mode ${session.permission_mode}` : "";
  const ran = useRan(session);
  return (
    <div className={`session-tip tone-${TONES[groupOf(session)]}`}>
      <div className="tooltip-line">
        <b>{label(session)}</b> · {session.title !== null && `${session.name} · `}
        <span className={trouble ? "danger-text" : "tip-status"}>{STATUS[session.status]}</span> ·{" "}
        {tracked(session) ? work(session) : count(session.agents, "agent")}
      </div>
      <div className="tooltip-line">{session.running_since ? `ran ${ran}` : ran}</div>
      {waits(session) && <div className="tooltip-line waits">Needs you: {about(session)}</div>}
      <div className="tooltip-line">{session.repo}</div>
      <div className="tooltip-line">
        {session.kits.join(", ")} · {session.provider}
        {mode}
      </div>
      {!isLive(session) && <div className="tooltip-line">Stopped: open it and press Resume</div>}
    </div>
  );
}

// Whether something in a session waits for the human, from what the server counts
// (SessionInfo.waiting): never in a stopped session, since nothing in it can be answered.
const waits = (session: SessionInfo) => {
  const { gates, questions, agents } = session.waiting;
  return isLive(session) && gates + questions + agents > 0;
};

// What a session is in, the one rule of its row, its icon, its card and its head: stopped or
// in trouble (tmux gone, loop down) by its status; else needs you when something waits for
// the human; else working when an agent works (SessionInfo.busy), idle when none does. The
// words name it in the head's tooltip and the phone's details, in the card's words.
type Mark = "needs-you" | "working" | "idle" | Exclude<SessionStatus, "running">;

export function sessionMark(session: SessionInfo): { mark: Mark; words: string } {
  if (session.status !== "running") return { mark: session.status, words: STATUS[session.status] };
  if (waits(session)) return { mark: "needs-you", words: `needs you · ${about(session)}` };
  return { mark: session.busy > 0 ? "working" : "idle", words: `${STATUS.running} · ${work(session)}` };
}

// The state line of Details: the mark's words and the run time, without `running`, which the
// work says, and a stopped session's `stopped` once, which `ran` says.
const detailsState = (session: SessionInfo, ran: string): string => {
  if (session.status === "stopped" && session.stopped_at) return ran;
  return `${sessionMark(session).words.replace(`${STATUS.running} · `, "")} · ${ran}`;
};

// A running session's agents at work, in its card's and its head's words.
const work = (session: SessionInfo) => {
  const agents = count(session.agents, "agent");
  return session.busy > 0 ? `${session.busy} of ${agents} working` : `idle · ${agents}`;
};

// The list's groups, by their ids (prefs.ts): a stopped session is Stopped whatever waits in
// it, one in trouble is in Needs you when something waits. Each has its name and its
// heading's tone (GroupHead), which its rows and cards take.
const groupOf = (session: SessionInfo): SessionGroup =>
  !isLive(session) ? "stopped" : waits(session) ? "needs-you" : "running";

const NAMES: Record<SessionGroup, string> = { "needs-you": "Needs you", running: "Running", stopped: "Stopped" };
const TONES: Record<SessionGroup, Tone> = { "needs-you": "human", running: "done", stopped: "neutral" };

function grouped(sessions: SessionInfo[]): Record<SessionGroup, SessionInfo[]> {
  const groups: Record<SessionGroup, SessionInfo[]> = { "needs-you": [], running: [], stopped: [] };
  for (const session of sessions) groups[groupOf(session)].push(session);
  return groups;
}

const count = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

// Whether the list says if a session's agents work, and its word for it: a Running row of a
// session that runs (its mark working or idle); the server counts none in one that does not.
const ACTIVITY: Partial<Record<Mark, "working" | "idle">> = { working: "working", idle: "idle" };
const workWord = (session: SessionInfo) => ACTIVITY[sessionMark(session).mark] ?? null;
const tracked = (session: SessionInfo) => workWord(session) !== null;

// The line under a Running row's name, its agents and how long it ran, and a Stopped row's,
// when it stopped and how long it ran: the head's run time, counted on by the minute.
function RanAbout({ session }: { session: SessionInfo }) {
  const ran = useRan(session);
  return <span className="session-about">{named(session, tracked(session) ? `${count(session.agents, "agent")} · ${ran}` : ran)}</span>;
}

// A row's line under a title starts with the session's name: the row shows the title.
const named = (session: SessionInfo, line: string) => (session.title === null ? line : `${session.name} · ${line}`);

// The line under the name of another row (Needs you, tmux gone, loop down): what waits for
// the human, or its agents.
function about(session: SessionInfo): string {
  const { gates, questions, agents } = session.waiting;
  const parts = [
    gates > 0 && count(gates, "gate"),
    questions > 0 && count(questions, "question"),
    agents > 0 && `${count(agents, "agent")} waiting`,
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : count(session.agents, "agent");
}

// One group of the list under its heading, which folds it; a group without sessions is not
// drawn. Folded, its list stays in the page (the heading's aria-controls) and shows only the
// open session, when it is in the group: the open session is always seen. While the search
// has text the group is open and its heading off: a click would change only what is
// remembered, not what is seen.
function Group({
  id,
  sessions,
  open,
  searching,
  current,
  onToggle,
  action,
}: {
  id: SessionGroup;
  sessions: SessionInfo[];
  open: boolean;
  searching: boolean;
  current?: string;
  onToggle: () => void;
  action?: ReactNode;
}) {
  if (sessions.length === 0) return null;
  const rows = open ? sessions : sessions.filter((one) => one.name === current);
  return (
    <section className={`session-group tone-${TONES[id]}`} aria-labelledby={`group-${id}-name`}>
      <GroupHead
        nameId={`group-${id}-name`}
        name={NAMES[id]}
        count={sessions.length}
        tone={TONES[id]}
        fold={{ open, controls: `group-${id}`, onToggle, disabled: searching }}
        action={action}
      />
      <ul id={`group-${id}`} hidden={rows.length === 0}>
        {rows.map((session) => (
          <SessionRow key={session.name} session={session} />
        ))}
      </ul>
    </section>
  );
}

// A row: the session's title (or name) and its line, a link to it, and its ⋯. Rename… in ⋯
// turns the title into a field in the row (TitleEdit), the row no link while it edits; the
// focus goes back to ⋯ when it closes.
function SessionRow({ session }: { session: SessionInfo }) {
  const item = useRef<HTMLLIElement>(null);
  const { editing, edit, closed } = useTitleEdit(() =>
    item.current?.querySelector<HTMLButtonElement>(".row-menu button")?.focus(),
  );
  if (editing) {
    return (
      <li ref={item} className="session-row">
        <div className="session-link session-row-edit">
          <TitleEdit
            name={session.name}
            title={session.title}
            label="Session title"
            save={(title) => setSessionTitle(session.name, title)}
            hint={`${session.name} · Enter to save · Esc to cancel`}
            suggestionHint={`${session.name} · Tab takes the name · Enter to save · Esc to cancel`}
            onClose={closed}
          />
        </div>
      </li>
    );
  }
  const working = workWord(session);
  return (
    <li ref={item} className="session-row">
      <Tooltip tip={<SessionTip session={session} />}>
        <NavLink to={sessionPath(session.name)} className="session-link">
          <span className="session-name">
            <span>{label(session)}</span>
            {working && <span className={`dot activity-${working}`} role="img" aria-label={working} />}
          </span>
          {working || !isLive(session) ? (
            <RanAbout session={session} />
          ) : (
            <span className="session-about">{named(session, about(session))}</span>
          )}
          {session.status !== "running" && session.status !== "stopped" && <Status status={session.status} />}
        </NavLink>
      </Tooltip>
      <SessionRowMenu name={session.name} onRename={edit} />
    </li>
  );
}

// Whether a session's title is edited in place (TitleEdit), in its head or its row: `closed`
// shows a saved session at once (Live.sessionChanged) and, once the field is gone, gives the
// focus back to its opener (`refocus`).
function useTitleEdit(refocus: () => void) {
  const live = useLiveStore();
  const [editing, setEditing] = useState(false);
  const back = useRef(false);
  useEffect(() => {
    if (editing || !back.current) return;
    back.current = false;
    refocus();
  });
  return {
    editing,
    edit: () => setEditing(true),
    closed: (saved?: SessionInfo) => {
      if (saved) live.sessionChanged(saved);
      back.current = true;
      setEditing(false);
    },
  };
}

function Status({ status }: { status: SessionStatus }) {
  return <span className={`status status-${status}`}>{STATUS[status]}</span>;
}

// The session's mark in its head, a dot before its name, the list's (sessionMark), named by
// its words: needs you the orange diamond of a waiting agent, working and idle the row's full
// dot and ring; stopped in the muted tone (its run time says "stopped"), and a session that
// needs an action (tmux gone, loop down) in the danger tone, its status in words after the name.
const HEAD_MARKS: Record<Mark, string> = {
  "needs-you": "dot dot-waiting",
  working: "dot activity-working",
  idle: "dot activity-idle",
  stopped: "session-dot-stopped",
  tmux_gone: "session-dot-tmux_gone",
  loop_down: "session-dot-loop_down",
};

// `stop`: a Tab stop, for a tap's or the keyboard's tooltip; a computer's head has none.
export function StatusDot({ session, stop = true }: { session: SessionInfo; stop?: boolean }) {
  const { mark, words } = sessionMark(session);
  return (
    <Tooltip tip={words}>
      <span className={`session-dot ${HEAD_MARKS[mark]}`} role="img" aria-label={words} tabIndex={stop ? 0 : undefined} />
    </Tooltip>
  );
}

export function NoSession() {
  useTitle("Sessions");
  const { loaded } = useOutletContext<SessionsOutlet>();
  const phone = usePhone(); // the list is the page: nothing to select beside it
  if (loaded && "sessions" in loaded && loaded.sessions.length === 0) {
    return <p className="empty">No sessions yet. Start one with Launch.</p>;
  }
  return phone ? null : <p className="empty">Select a session</p>;
}

const TAB_NAMES: Record<Tab, string> = {
  activity: "Activity",
  agents: "Agents",
  flows: "Flows",
  artifacts: "Artifacts",
};

// The tabs whose page without an item has a search in the tab bar, by its name; the search
// is the address's ?find=, which the tab reads.
const FINDS: Partial<Record<Tab, string>> = { flows: "Find a run" };

const TAB_ICONS: Record<Tab, typeof ActivityIcon> = {
  activity: ActivityIcon,
  agents: AgentsIcon,
  flows: FlowsIcon,
  artifacts: ArtifactsIcon,
};

export function Session() {
  const { name = "", tab = "activity", item } = useParams();
  const { loaded, panel } = useOutletContext<SessionsOutlet>();
  // Only the Flows, Agents and Artifacts tabs have pages of their own: their runs', agents'
  // and artifacts'.
  if (!isTab(tab) || (item !== undefined && tab === "activity")) return <NotFound />;
  return <SessionTab name={name} tab={tab} item={item} loaded={loaded} panel={panel} />;
}

function SessionTab({
  name,
  tab,
  item,
  loaded,
  panel,
}: {
  name: string;
  tab: Tab;
  item?: string;
  loaded: Loaded;
  panel: PanelColumn;
}) {
  const started = (useLocation().state as StartedState | null)?.started;
  // Just started here: the change feed may bring it a moment after the start's answer.
  const session =
    loaded === null || "error" in loaded
      ? undefined
      : (loaded.sessions.find((one) => one.name === name) ?? (started?.session.name === name ? started.session : undefined));
  // The session names the page, by its title if it has one; while it loads or when there is
  // none, the page is Sessions.
  useTitle(session ? label(session) : "Sessions");
  if (loaded === null || "error" in loaded) return null; // the list, or its strip, says what is wrong
  if (session === undefined) {
    return (
      <div className="empty">
        <p>Session {name} not found</p>
        <Link to="/sessions">All sessions</Link>
      </div>
    );
  }
  return (
    // The panel keeps its terminals while the tabs change: keyed by the session only.
    <TerminalPanel key={name} session={name} column={panel}>
      <SessionView name={name} tab={tab} item={item} session={session} />
    </TerminalPanel>
  );
}

function SessionView({ name, tab, item, session }: { name: string; tab: Tab; item?: string; session: SessionInfo }) {
  const live = useLiveStore();
  const runs = useLive().runs[name] ?? null;
  const agents = useLive().agents[name] ?? null;
  useEffect(() => live.watch("runs", name), [live, name]);
  useEffect(() => live.watch("agents", name), [live, name]);
  const artifacts = useLive().artifacts[name] ?? null;
  useEffect(() => live.watch("artifacts", name), [live, name]);
  const counts: Partial<Record<Tab, number>> = {
    flows: runs && "items" in runs ? runs.items.filter(isOpen).length : 0,
    agents: agents && "items" in agents ? agents.items.length : 0,
    artifacts: artifacts && "items" in artifacts ? artifacts.items.length : 0,
  };
  const stopped = session.status === "stopped";
  const view = useSearchParams()[0].get(VIEW_PARAM); // a chip's record, in the panel over the tab
  return (
    <section className="session" aria-label={`Session ${name}`}>
      <SessionHead session={session} tab={tab} />
      <StartedNotice name={name} />
      <SessionTabs name={name} tab={tab} counts={counts}>
        {FINDS[tab] !== undefined && item === undefined && <Find key={tab} label={FINDS[tab]} />}
      </SessionTabs>
      {tab === "agents" ? (
        <Agents session={name} agent={item} stopped={stopped} />
      ) : tab === "activity" ? (
        <Activity session={name} stopped={stopped} />
      ) : tab === "flows" ? (
        <Flows session={name} run={item} stopped={stopped} />
      ) : (
        <Artifacts session={name} artifact={item} />
      )}
      {view && <ArtifactPanel session={name} record={view} />}
    </section>
  );
}

// How the tabs give way when they do not fit their bar (styles.css, `data-fit`): 0 as they are,
// 1 no icons, 2 no counts either, 3 they scroll sideways behind a fade, with ‹ and ›.
const LAST_FIT = 3;

// The tab bar: the tabs, which give way by the levels above, and at its right end what stays
// outside them (`children`, a tab's search). The level is chosen by trying each before the
// paint, again when the tabs' row or a tab changes its width (the bar, the search coming, a
// count, the font).
function SessionTabs({
  name,
  tab,
  counts,
  children,
}: {
  name: string;
  tab: Tab;
  counts: Partial<Record<Tab, number>>;
  children: ReactNode;
}) {
  const bar = useRef<HTMLElement>(null);
  const row = useRef<HTMLDivElement>(null);
  const [fit, setFit] = useState(0);
  const [ends, setEnds] = useState({ start: true, end: true });
  const lookAtEnds = useCallback(() => {
    const tabs = row.current;
    if (!tabs) return;
    const start = tabs.scrollLeft <= 0;
    const end = tabs.scrollLeft + tabs.clientWidth >= tabs.scrollWidth - 1;
    setEnds((now) => (now.start === start && now.end === end ? now : { start, end }));
  }, []);
  useLayoutEffect(() => {
    const box = bar.current;
    const tabs = row.current;
    if (!box || !tabs) return;
    const choose = () => {
      let level = 0;
      for (; level < LAST_FIT; level++) {
        box.dataset.fit = String(level);
        if (tabs.scrollWidth <= tabs.clientWidth) break;
      }
      box.dataset.fit = String(level);
      setFit(level);
      lookAtEnds();
    };
    choose();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(choose);
    observer.observe(tabs);
    for (const one of tabs.children) observer.observe(one);
    return () => observer.disconnect();
  }, [lookAtEnds]);
  // The tab shown stays in view. By the row's own scroll: Chromium's Tab would start from a
  // tab scrolled to with scrollIntoView (Terminals.tsx).
  useLayoutEffect(() => {
    const tabs = row.current;
    const on = tabs?.querySelector<HTMLElement>('[aria-current="page"]');
    if (!tabs || !on) return;
    if (on.offsetLeft < tabs.scrollLeft) tabs.scrollLeft = on.offsetLeft;
    else if (on.offsetLeft + on.offsetWidth > tabs.scrollLeft + tabs.clientWidth)
      tabs.scrollLeft = on.offsetLeft + on.offsetWidth - tabs.clientWidth;
    lookAtEnds();
  }, [tab, fit, lookAtEnds]);
  const scroll = (side: 1 | -1) => row.current?.scrollBy({ left: side * row.current.clientWidth });
  return (
    <nav ref={bar} className="tab-bar session-tabs" aria-label="Session sections" data-fit={fit}>
      <div className="session-tabs-box">
        <div ref={row} className="session-tabs-scroll" onScroll={lookAtEnds}>
          {TABS.map((one) => {
            const SectionIcon = TAB_ICONS[one];
            return (
              <Link
                key={one}
                to={sessionPath(name, one)}
                className="tab-item"
                aria-current={one === tab ? "page" : undefined}
              >
                <SectionIcon />
                {TAB_NAMES[one]}
                {counts[one] ? (
                  <>
                    {" "}
                    {/* Named "Agents · 3"; the dot is for the ear only. */}
                    <span className="tab-count">
                      <span className="visually-hidden">·</span> {counts[one]}
                    </span>
                  </>
                ) : null}
              </Link>
            );
          })}
        </div>
        {fit === LAST_FIT && !ends.start && (
          <div className="session-tabs-more start">
            <button type="button" className="icon-button" aria-label="Earlier tabs" onClick={() => scroll(-1)}>
              ‹
            </button>
          </div>
        )}
        {fit === LAST_FIT && !ends.end && (
          <div className="session-tabs-more end">
            <button type="button" className="icon-button" aria-label="More tabs" onClick={() => scroll(1)}>
              ›
            </button>
          </div>
        )}
      </div>
      {children}
    </nav>
  );
}

// A tab's search at the right end of the tab bar: a magnifier that opens a field on a click
// or "/" (not while typing in another field: an input, a textarea, a select, an editable
// element, xterm's own textarea too). The field writes the address's ?find= in place, so
// typing adds no step to the browser's history; the other parameters stay, and an empty
// search drops it. Esc clears and closes it; left empty, it closes; with text, it stays.
function Find({ label }: { label: string }) {
  const [params, setParams] = useSearchParams();
  const query = params.get(FIND_PARAM) ?? "";
  const [opened, setOpened] = useState(false);
  const [focus, setFocus] = useState(0); // bumped to focus the field once it is drawn
  const field = useRef<HTMLInputElement>(null);
  const shown = opened || query !== "";

  useEffect(() => {
    if (focus > 0) field.current?.focus();
  }, [focus]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest?.("input, textarea, select") || target?.isContentEditable) return;
      event.preventDefault();
      setOpened(true);
      setFocus((one) => one + 1);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const write = (value: string) =>
    setParams(
      (now) => {
        const next = new URLSearchParams(now);
        if (value === "") next.delete(FIND_PARAM);
        else next.set(FIND_PARAM, value);
        return next;
      },
      { replace: true, preventScrollReset: true },
    );
  return (
    <div className={shown ? "tab-find open" : "tab-find"}>
      {shown && (
        <input
          ref={field}
          type="search"
          className="search"
          placeholder={label}
          aria-label={label}
          value={query}
          onChange={(event) => write(event.target.value)}
          onBlur={(event) => event.currentTarget.value === "" && setOpened(false)}
          onKeyDown={(event) => {
            if (event.key !== "Escape") return;
            write("");
            setOpened(false);
          }}
        />
      )}
      <button
        type="button"
        className="icon-button"
        aria-label={label}
        title={`${label} (/)`}
        onClick={() => {
          setOpened(true);
          setFocus((one) => one + 1);
        }}
      >
        <FindIcon />
      </button>
    </div>
  );
}

// The session's head in the top bar's slot (useTopBar), and `Skip to chat` before everything
// else of the page.
function SessionHead({ session, tab }: { session: SessionInfo; tab: Tab }) {
  const slot = useTopBar();
  const phone = usePhone();
  if (slot === null) return null;
  return (
    <>
      <SkipToChat name={session.name} tab={tab} />
      {createPortal(phone ? <PhoneHead session={session} /> : <HeadLine session={session} />, slot)}
    </>
  );
}

// Hidden until it has the focus. It puts the focus on the Activity tab's feed, by way of the
// address from another tab, as the feed is not there yet (Chat, FOCUS_CHAT).
function SkipToChat({ name, tab }: { name: string; tab: Tab }) {
  const slot = useSkipSlot();
  const putBackTerminals = usePutBackTerminals();
  if (slot === null) return null;
  return createPortal(
    <Link
      className="skip-link"
      to={sessionPath(name)}
      state={FOCUS_CHAT}
      onClick={(event) => {
        putBackTerminals(); // expanded, they lie over the chat
        if (tab !== "activity") return;
        event.preventDefault();
        focusChat();
      }}
    >
      Skip to chat
    </Link>,
    slot,
  );
}

// What a press outside Details leaves the focus on (docs/design/ui.md, Session head).
const TAKES_FOCUS = "a, button, input, textarea, select, [contenteditable]";

// The head on a computer, one line of the top bar (docs/design/ui.md, Structure and Session
// head): the status as a dot, the project as a breadcrumb, the title as a button that opens
// Details, a broken session's status in words, the run time, the branch on a wide window
// (styles.css), the actions. The rest of the facts are in Details (DetailsPopover).
function HeadLine({ session }: { session: SessionInfo }) {
  const { status } = session;
  const about = useAbout(session);
  const repository = about?.repos[0];
  const trouble = status === "tmux_gone" || status === "loop_down";
  const ran = useRan(session);
  const [details, setDetails] = useState(false);
  const title = useRef<HTMLButtonElement>(null);
  const box = useRef<HTMLDivElement>(null); // the title and Details: a second click is no press outside
  const popover = useRef<HTMLDivElement>(null);
  const below = useBelow(title, popover, details);
  const close = useCallback(() => {
    setDetails(false);
    title.current?.focus();
  }, []);
  // After the press: its own default would take the focus from the title again. What took
  // the focus by the press keeps it (the terminal's input, a summary); the body and what only
  // a script focuses (the feed) have a tabIndex below 0, and count as an empty place.
  const pressedAway = useCallback((event: MouseEvent) => {
    setDetails(false);
    if ((event.target as Element).closest(TAKES_FOCUS)) return;
    setTimeout(() => {
      if (((document.activeElement as HTMLElement | null)?.tabIndex ?? -1) < 0) title.current?.focus();
    });
  }, []);
  useDismiss(details, box, pressedAway);
  // Tab went on past the title: open, Details would lie over the focus, which stays where it
  // went. Looked at after the event, as the legacy copy takes the focus for a moment.
  const focusLeft = useCallback(() => {
    setTimeout(() => {
      const now = document.activeElement;
      if (now && now !== document.body && !box.current?.contains(now)) setDetails(false);
    });
  }, []);
  // The title edited in place (Session title), from Details; the focus goes back to the
  // title when the field closes.
  const { editing, edit, closed } = useTitleEdit(() => title.current?.focus());
  return (
    <div className="session-head">
      <StatusDot session={session} stop={false} />
      {about?.project && <ProjectCrumb project={about.project} />}
      <div ref={box} className="session-title-box" onBlur={focusLeft}>
        {editing ? (
          <TitleEdit
            name={session.name}
            title={session.title}
            label="Session title"
            save={(saved) => setSessionTitle(session.name, saved)}
            hint="Enter to save · Esc to cancel · empty shows the name"
            suggestionHint="Tab takes the name · Enter to save · Esc to cancel"
            onClose={closed}
          />
        ) : (
          <h1 className="session-title">
            <button
              ref={title}
              type="button"
              title={label(session)}
              aria-haspopup="dialog"
              aria-expanded={details}
              onClick={() => (details ? close() : setDetails(true))}
            >
              <span className="session-title-text">{label(session)}</span>
              <span className="session-chevron">
                <ChevronIcon />
              </span>
            </button>
          </h1>
        )}
        {details && (
          <DetailsPopover
            ref={popover}
            style={below}
            session={session}
            about={about}
            state={detailsState(session, ran)}
            onRename={() => {
              setDetails(false);
              edit();
            }}
            onClose={close}
          />
        )}
      </div>
      {trouble && <span className="session-state danger-text">{STATUS[status]}</span>}
      <span className="session-ran">{ran}</span>
      {repository?.branch && (
        <Tooltip tip={<GitTip repo={repository} />}>
          <span className="session-branch">
            <GitIcon />
            <span>{repository.branch}</span>
          </span>
        </Tooltip>
      )}
      <div className="session-head-actions">
        <SessionActions session={session} />
      </div>
      <span className="topbar-sep" aria-hidden="true" />
    </div>
  );
}

// The project's title, read with the about: a rename shows on the next look; a link to its
// page, then a `/` that only the eye needs.
function ProjectCrumb({ project }: { project: NonNullable<SessionAbout["project"]> }) {
  const shown = project.title ?? project.id;
  return (
    <>
      <Tooltip
        tip={
          <>
            <div className="tooltip-line">{shown}</div>
            <div className="tooltip-line">Project {project.id}</div>
          </>
        }
      >
        <Link className="session-crumb" to={projectPath(project.id)}>
          {shown}
        </Link>
      </Tooltip>
      <span className="session-crumb-sep" aria-hidden="true">
        /
      </span>
    </>
  );
}

// The head on a phone (docs/design/ui.md, Phone layout): the status dot, the title (or name)
// as a button that opens the session's details, and the session's actions; the change
// feed's mark is the Shell's, between them by styles.css. The facts are in the details.
function PhoneHead({ session }: { session: SessionInfo }) {
  const about = useAbout(session);
  const live = useLiveStore();
  const [details, setDetails] = useState(false);
  const ran = useRan(session);
  return (
    <div className="session-head">
      <StatusDot session={session} />
      <h1 className="session-title">
        <button
          type="button"
          aria-haspopup="dialog"
          aria-expanded={details}
          onClick={() => setDetails(true)}
        >
          <span className="session-title-text">{label(session)}</span>
          <span className="session-chevron">
            <ChevronIcon />
          </span>
        </button>
      </h1>
      <div className="session-head-actions">
        <SessionActions session={session} />
      </div>
      {details && (
        <SessionDetails
          session={session}
          about={about}
          state={detailsState(session, ran)}
          onSaved={(saved) => live.sessionChanged(saved)}
          onClose={() => setDetails(false)}
        />
      )}
    </div>
  );
}

// The session's about, asked when its head opens and again when what it is read from may
// have changed: the session's folder, kits or provider, or an installed kit (the feed's
// `kits`). No change in the feed says the CLI's version changed: it is read at the head's
// opening only.
function useAbout(session: SessionInfo): SessionAbout | null {
  const kitChanges = useLive().kitChanges;
  const [about, setAbout] = useState<SessionAbout | null>(null);
  const { name, repo, provider } = session;
  const kits = session.kits.join("\n");
  useEffect(() => {
    let current = true;
    getSessionAbout(name).then(
      (got) => current && setAbout(got),
      () => current && setAbout(null),
    );
    return () => {
      current = false;
    };
  }, [name, repo, kits, provider, kitChanges]);
  return about;
}

const TICK_MS = 60_000; // how often the times of the session list and head are counted on

// The clock of a time counted from `from` (none: no clock): now, again on each TICK_MS.
function useNow(from: string | null): number {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    if (!from) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), TICK_MS);
    return () => clearInterval(timer);
  }, [from]);
  return now;
}

// The seconds from `iso` to `now`, none below 0.
const secondsSince = (iso: string, now: number) => Math.max(0, (now - new Date(iso).getTime()) / 1000);

// How long the session ran at `now`, the one text of it for the head, the list's rows and
// the card: while it runs, its closed spans and the time since its last start, with no
// prefix; stopped, how long ago too.
export function ranText(session: SessionInfo, now: number): string {
  const { running_since: since, stopped_at: stopped } = session;
  const seconds = (iso: string) => secondsSince(iso, now);
  const ran = duration(session.ran_seconds + (since ? seconds(since) : 0), true);
  return since ? ran : stopped ? `stopped ${duration(seconds(stopped))} ago · ran ${ran}` : `ran ${ran}`;
}

// ranText, counted on each minute.
function useRan(session: SessionInfo): string {
  const now = useNow(session.running_since ?? session.stopped_at); // the time counted from
  return ranText(session, now);
}


// What a start or resume from the New session window said: the settings a resume changed,
// open runs that cannot go on as they are, and its warnings (e.g. what the supervisor's CLI
// asks the human before it starts), until the human closes it.
function StartedNotice({ name }: { name: string }) {
  const location = useLocation();
  const navigate = useNavigate();
  const started = (location.state as StartedState | null)?.started;
  if (!started || started.session.name !== name) return null;
  const { changes, problems, resumed, warnings } = started;
  if (changes.length === 0 && problems.length === 0 && warnings.length === 0) return null;
  const close = () => navigate(`${location.pathname}${location.search}`, { replace: true, state: null });
  return (
    <div className="started-notice">
      {changes.length > 0 && (
        <div role="status">
          <span>{resumed ? "Resumed with new settings:" : "Started:"}</span>
          <ul>
            {changes.map((change) => (
              <li key={change}>{change}</li>
            ))}
          </ul>
        </div>
      )}
      {problems.length > 0 && (
        <div role="alert" className="started-problems">
          <span>Open runs that cannot go on as they are:</span>
          <ul>
            {problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        </div>
      )}
      {warnings.length > 0 && (
        <div role="alert" className="started-problems">
          <span>Warnings:</span>
          <ul>
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
      <button type="button" className="quiet" onClick={close}>
        Close
      </button>
    </div>
  );
}

// The Activity tab: the team, ended by the icon toggle Messages between agents (pressed, the
// feed also shows what agents write to each other; it changes only what the feed shows, and
// is remembered; decided 2026-10-15, LAD-77, mockup-placement.html variant Б), and the feed
// with the composer.
function Activity({ session, stopped }: { session: string; stopped: boolean }) {
  const [agentMessages, setAgentMessages] = useState(storedAgentMessages);
  const tip = (
    <>
      <div className="tooltip-line">Messages between agents: {agentMessages ? "shown" : "hidden"}</div>
      <div className="tooltip-line">
        {agentMessages ? "Click to show only your conversation with the agents." : "Click to also show what agents write to each other."}
      </div>
    </>
  );
  return (
    <div className="activity">
      <div className="team-row">
        <Team session={session} />
        <Tooltip tip={tip}>
          <button
            type="button"
            className="icon-button between-toggle"
            aria-label="Messages between agents"
            aria-pressed={agentMessages}
            onClick={() => {
              setAgentMessages(!agentMessages);
              storeAgentMessages(!agentMessages);
            }}
          >
            <BetweenIcon />
          </button>
        </Tooltip>
      </div>
      <Chat session={session} stopped={stopped} agentMessages={agentMessages} />
    </div>
  );
}
