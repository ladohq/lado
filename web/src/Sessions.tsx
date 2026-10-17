// Sessions: the list on the left (from /api/sessions, searched by name here), the selected
// session on the right with its tabs. The list's width is dragged on its edge and remembered;
// the list collapses to a strip of the sessions' icons (remembered too).
import { useEffect, useRef, useState, type CSSProperties, type ReactNode, type RefObject } from "react";
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
import { getSessionAbout, type SessionAbout, type SessionInfo, type SessionStatus } from "./api";
import { Chat } from "./Chat";
import { duration } from "./ChatText";
import { CopyButton } from "./Copy";
import { Flows, isOpen } from "./Flows";
import { GroupHead, type Tone } from "./GroupHead";
import {
  ActivityIcon,
  AgentCliIcon,
  AgentsIcon,
  ArtifactsIcon,
  BetweenIcon,
  CollapsePanelIcon,
  FindIcon,
  FlowsIcon,
  FolderIcon,
  KitsIcon,
  LinkIcon,
  PencilIcon,
  ProblemIcon,
} from "./icons";
import { useLaunch, type StartedState } from "./Launch";
import { isLive, useLive, useLiveStore, type Loaded } from "./live";
import { SessionActions } from "./SessionControl";
import { label } from "./sessionLabel";
import { SessionRowMenu } from "./SessionRowMenu";
import { MAIN_MIN, TerminalPanel } from "./Terminals";
import { NotFound } from "./pages";
import { FIND_PARAM, isTab, sessionLink, sessionPath, TABS, VIEW_PARAM, type Tab } from "./paths";
import {
  PANEL_WIDTH,
  SESSIONS_WIDTH,
  storeAgentMessages,
  storedAgentMessages,
  storedSessionGroups,
  storedSessionsList,
  storeSessionGroups,
  storeSessionsList,
  type ColumnPrefs,
  type SessionGroup,
} from "./prefs";
import { usePhone } from "./phone";
import { CliTip, GitFact, KitTip, SessionDetails } from "./SessionDetails";
import { useTitle, useTopBar } from "./Shell";
import { fitWidth, Splitter, useStripFocus, useWidth } from "./Splitter";
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
  const group = (id: SessionGroup) => (
    <Group
      id={id}
      sessions={groups[id]}
      open={wanted !== "" || folds[id] === "open"}
      searching={wanted !== ""}
      current={current}
      onToggle={() => toggle(id)}
    />
  );
  const [list, setList] = useState(storedSessionsList);
  const focus = useStripFocus(list.collapsed);
  const [page, room] = useWidth<HTMLDivElement>();
  // The list leaves the session and the terminals their least widths; collapsed, the strip
  // gives the session the rest.
  const width = fitWidth(list.width, SESSIONS_WIDTH, room === null ? null : room - MAIN_MIN - PANEL_WIDTH.min);
  const keep = (change: Partial<ColumnPrefs>) => {
    const next = { ...list, ...change };
    setList(next);
    storeSessionsList(next);
  };
  const collapse = (collapsed: boolean) => {
    focus.toggled();
    keep({ collapsed });
  };
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
      className={list.collapsed ? "sessions collapsed" : "sessions"}
      style={{ "--list-width": `${list.collapsed ? STRIP_WIDTH : width}px` } as CSSProperties}
    >
      {!list.collapsed && (
        <Splitter
          label="Resize the session list"
          edge="right"
          width={width}
          bounds={SESSIONS_WIDTH}
          onChange={(next) => keep({ width: next })}
        />
      )}
      {list.collapsed ? (
        <SessionStrip loaded={loaded} openRef={focus.open} onOpen={() => collapse(false)}>
          {newSession}
        </SessionStrip>
      ) : (
        <div className="session-list">
          <div className="session-list-head">
            <h2>Sessions</h2>
            {newSession}
            <button
              ref={focus.collapse}
              type="button"
              className="ghost"
              aria-label="Collapse sessions"
              title="Collapse sessions"
              onClick={() => collapse(true)}
            >
              <CollapsePanelIcon side="left" />
            </button>
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
        <Outlet context={loaded} />
      </div>
    </div>
  );
}

// The width of the list collapsed to a strip, in pixels.
const STRIP_WIDTH = 44;

// The list collapsed to a strip: Sessions opens it again, then New session (`children`), then
// an icon per session not stopped, in the open list's order (those that need the human first,
// a line after them). While the list loads the icons' column is empty and busy; when it
// cannot load, an alert says why, as the open list does.
function SessionStrip({
  loaded,
  openRef,
  onOpen,
  children,
}: {
  loaded: Loaded;
  openRef: RefObject<HTMLButtonElement | null>;
  onOpen: () => void;
  children: ReactNode;
}) {
  const groups = loaded && "sessions" in loaded ? grouped(loaded.sessions) : null;
  return (
    <nav className="sessions-strip" aria-label="Sessions">
      <button ref={openRef} type="button" className="strip-open sessions-open" title="Show the sessions" onClick={onOpen}>
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
        <ul className="strip-icons" aria-busy={groups === null || undefined}>
          {groups?.["needs-you"].map((session) => <StripIcon key={session.name} session={session} />)}
          {groups && groups["needs-you"].length > 0 && groups.running.length > 0 && (
            <li className="strip-gap" aria-hidden="true" />
          )}
          {groups?.running.map((session) => <StripIcon key={session.name} session={session} />)}
        </ul>
      )}
    </nav>
  );
}

// A session's two letters: the first of its first two words, else its first two letters.
// Two sessions may share them: the tooltip and the label tell them apart. Letters are whole
// characters (code points), as a title may start with an emoji.
const initials = (name: string) => {
  const words = name.split(/[-_./\s]+/).filter(Boolean);
  const first = (text: string) => [...text][0];
  return (words.length > 1 ? first(words[0]) + first(words[1]) : [...name].slice(0, 2).join("")).toUpperCase();
};

function StripIcon({ session }: { session: SessionInfo }) {
  const needsYou = waits(session);
  const work = tracked(session) && workWord(session);
  const called = label(session);
  return (
    <li>
      <Tooltip tip={<SessionTip session={session} />}>
        <NavLink
          to={sessionPath(session.name)}
          className={`strip-session${needsYou ? " waits" : ""}`}
          aria-label={needsYou ? `${called}, needs you` : work ? `${called}, ${work}` : called}
        >
          {initials(called)}
          {work && <span className={`dot dot-small activity-${work}`} aria-hidden="true" />}
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
  const agents = count(session.agents, "agent");
  const work = !tracked(session)
    ? agents
    : session.busy > 0
      ? `${session.busy} of ${agents} working`
      : `idle · ${agents}`;
  return (
    <div className={`session-tip tone-${TONES[groupOf(session)]}`}>
      <div className="tooltip-line">
        <b>{label(session)}</b> · {session.title !== null && `${session.name} · `}
        <span className={trouble ? "danger-text" : "tip-status"}>{STATUS[session.status]}</span> ·{" "}
        {work}
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

// The list's groups, by their ids (prefs.ts): a stopped session is Stopped whatever waits in
// it. Each has its name and its heading's tone (GroupHead), which its rows and cards take.
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

// Whether the list says if a session's agents work (SessionInfo.busy): a Running row of a
// session that runs; the server counts none in one that does not.
const tracked = (session: SessionInfo) => session.status === "running" && !waits(session);
const workWord = (session: SessionInfo) => (session.busy > 0 ? "working" : "idle");

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
}: {
  id: SessionGroup;
  sessions: SessionInfo[];
  open: boolean;
  searching: boolean;
  current?: string;
  onToggle: () => void;
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
            session={session}
            hint={`${session.name} · Enter to save · Esc to cancel`}
            suggestionHint={`${session.name} · Tab takes the name · Enter to save · Esc to cancel`}
            onClose={closed}
          />
        </div>
      </li>
    );
  }
  return (
    <li ref={item} className="session-row">
      <Tooltip tip={<SessionTip session={session} />}>
        <NavLink to={sessionPath(session.name)} className="session-link">
          <span className="session-name">
            <span>{label(session)}</span>
            {tracked(session) && (
              <span className={`dot activity-${workWord(session)}`} role="img" aria-label={workWord(session)} />
            )}
          </span>
          {tracked(session) || !isLive(session) ? (
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

// The session's status in its head, a dot before its name: running in the done tone with
// no word, stopped in the muted one (its run time says "stopped"), and a session that needs
// an action (tmux gone, loop down) in the danger tone, its status in words after the name.
function StatusDot({ status }: { status: SessionStatus }) {
  return (
    <Tooltip tip={STATUS[status]}>
      <span className={`session-dot session-dot-${status}`} role="img" aria-label={STATUS[status]} tabIndex={0} />
    </Tooltip>
  );
}

export function NoSession() {
  useTitle("Sessions");
  const loaded = useOutletContext<Loaded>();
  if (loaded && "sessions" in loaded && loaded.sessions.length === 0) {
    return <p className="empty">No sessions yet. Start one with Launch.</p>;
  }
  return <p className="empty">Select a session</p>;
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
  const loaded = useOutletContext<Loaded>();
  // Only the Flows, Agents and Artifacts tabs have pages of their own: their runs', agents'
  // and artifacts'.
  if (!isTab(tab) || (item !== undefined && tab === "activity")) return <NotFound />;
  return <SessionTab name={name} tab={tab} item={item} loaded={loaded} />;
}

function SessionTab({ name, tab, item, loaded }: { name: string; tab: Tab; item?: string; loaded: Loaded }) {
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
    <TerminalPanel key={name} session={name}>
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
      <SessionHead session={session} />
      <StartedNotice name={name} />
      <nav className="tab-bar session-tabs" aria-label="Session sections">
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
        {FINDS[tab] !== undefined && item === undefined && <Find key={tab} label={FINDS[tab]} />}
      </nav>
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

// The session's head, one line of the top bar (docs/design/ui.md, Structure and Session
// head): its status as a dot, its name and how long it ran; then, small, its folder (Copy
// path on the folder's icon), its git remote and branch (Copy URL on the git icon), its kits
// and its agents' CLI, the versions, and the permission mode, in their tooltips; then Copy
// link and its actions. Until its about comes, or when it fails, the facts are the
// session's settings alone, the mode not shown. Drawn in the top bar's slot (useTopBar).
function SessionHead({ session }: { session: SessionInfo }) {
  const slot = useTopBar();
  if (slot === null) return null;
  return createPortal(<HeadLine session={session} />, slot);
}

function HeadLine({ session }: { session: SessionInfo }) {
  const { name, repo, kits, provider, permission_mode: mode, status } = session;
  const about = useAbout(session);
  const repository = about?.repos[0];
  const cli = about?.provider;
  const trouble = status === "tmux_gone" || status === "loop_down";
  // The title edited in place (Session title): the pencil or a double click opens the field,
  // which gives the focus back to the pencil when it closes.
  const pencil = useRef<HTMLButtonElement>(null);
  const { editing, edit, closed } = useTitleEdit(() => pencil.current?.focus());
  const phone = usePhone();
  if (phone) return <PhoneHead session={session} about={about} />;
  return (
    <div className="session-head">
      <StatusDot status={status} />
      {editing ? (
        <TitleEdit
          session={session}
          hint="Enter to save · Esc to cancel · empty shows the name"
          suggestionHint="Tab takes the name · Enter to save · Esc to cancel"
          onClose={closed}
        />
      ) : (
        <h1 title={label(session)} onDoubleClick={edit}>
          {label(session)}
        </h1>
      )}
      {session.title !== null && (
        <span className="session-name-id" title={`Session ${name}`}>
          {name}
        </span>
      )}
      {!editing && (
        <Tooltip tip="Rename session">
          <button
            ref={pencil}
            type="button"
            className="icon-button session-rename"
            aria-label="Rename session"
            onClick={edit}
          >
            <PencilIcon />
          </button>
        </Tooltip>
      )}
      {trouble && <span className="session-state danger-text">{STATUS[status]}</span>}
      <Ran session={session} />
      <span className="topbar-sep meta-sep" aria-hidden="true" />
      <div className="session-meta">
        <span className="session-folder">
          <CopyButton
            label="Copy path"
            copied="Path copied"
            text={repo}
            field={{ title: `Path of ${name}`, label: "Path" }}
            icon={<FolderIcon />}
          />
          {/* Cut at its start, so the end of the path stays in view. */}
          <span className="session-path" title={repo}>
            <bdi>{repo}</bdi>
          </span>
        </span>
        {repository && <GitFact name={name} repo={repository} />}
        <span className="session-fact">
          <KitsIcon />
          <span className="session-kits">
            {kits.map((kit, at) => {
              const found = about?.kits.find((one) => one.name === kit);
              return (
                <span key={kit}>
                  {at > 0 && ", "}
                  {found ? (
                    <Tooltip tip={<KitTip kit={found} />}>
                      <span className="session-kit session-hint" tabIndex={0}>
                        {kit}
                      </span>
                    </Tooltip>
                  ) : (
                    kit
                  )}
                </span>
              );
            })}
          </span>
        </span>
        <span className="session-fact">
          <AgentCliIcon />
          <span className="session-agent-cli">
            {cli ? (
              <Tooltip tip={<CliTip cli={cli} mode={mode} />}>
                <span className="session-hint" tabIndex={0}>
                  {provider}
                </span>
              </Tooltip>
            ) : (
              provider
            )}
            {cli?.warning && (
              <span role="img" aria-label="untested version" className="session-warn">
                !
              </span>
            )}
          </span>
        </span>
      </div>
      <div className="session-head-actions">
        <CopyButton
          label="Copy link"
          copied="Link copied"
          text={sessionLink(name)}
          field={{ title: `Link to ${name}`, label: "Link" }}
          icon={<LinkIcon />}
        />
        <SessionActions session={session} />
      </div>
      <span className="topbar-sep" aria-hidden="true" />
    </div>
  );
}

// The head on a phone (docs/design/ui.md, Phone layout): the status dot, the title (or name)
// as a button that opens the session's details, and the session's actions; the change
// feed's mark is the Shell's, between them by styles.css. The facts are in the details.
function PhoneHead({ session, about }: { session: SessionInfo; about: SessionAbout | null }) {
  const live = useLiveStore();
  const [details, setDetails] = useState(false);
  const ran = useRan(session);
  return (
    <div className="session-head">
      <StatusDot status={session.status} />
      <h1 className="session-title">
        <button
          type="button"
          aria-haspopup="dialog"
          aria-expanded={details}
          onClick={() => setDetails(true)}
        >
          {label(session)}
        </button>
      </h1>
      <div className="session-head-actions">
        <SessionActions session={session} />
      </div>
      {details && (
        <SessionDetails
          session={session}
          about={about}
          state={`${STATUS[session.status]} · ${ran}`}
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

function Ran({ session }: { session: SessionInfo }) {
  return <span className="session-ran">{useRan(session)}</span>;
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
