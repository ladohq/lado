// Sessions: the list on the left (from /api/sessions, searched by name here), the selected
// session on the right with its tabs. The list's width is dragged on its edge and remembered;
// the list collapses to a strip of the sessions' icons (remembered too).
import { useEffect, useState, type CSSProperties, type ReactNode, type RefObject } from "react";
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
  useOutletContext,
  useParams,
} from "react-router";

import { Agents } from "./Agents";
import type { SessionInfo, SessionStatus } from "./api";
import { Chat } from "./Chat";
import { duration, since as ago } from "./ChatText";
import { CopyButton } from "./Copy";
import { FoldToggle } from "./Fold";
import { Flows, isOpen } from "./Flows";
import { AgentCliIcon, CollapsePanelIcon, FolderIcon, KitsIcon, LinkIcon, ProblemIcon } from "./icons";
import { useLaunch, type StartedState } from "./Launch";
import { isLive, useLive, useLiveStore, type Loaded } from "./live";
import { SessionActions } from "./SessionControl";
import { sessionLink, SessionRowMenu } from "./SessionRowMenu";
import { MAIN_MIN, TerminalPanel } from "./Terminals";
import { NotFound } from "./pages";
import { isTab, PLANS, sessionPath, TABS, type Tab } from "./paths";
import { Placeholder } from "./Placeholder";
import {
  PANEL_WIDTH,
  SESSIONS_WIDTH,
  storeAgentMessages,
  storedAgentMessages,
  storedSessionsList,
  storedStoppedOpen,
  storeSessionsList,
  storeStoppedOpen,
  type ColumnPrefs,
} from "./prefs";
import { useTitle } from "./Shell";
import { fitWidth, Splitter, useStripFocus, useWidth } from "./Splitter";
import { Team } from "./Team";
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
  const [stoppedOpen, setStoppedOpen] = useState(storedStoppedOpen);

  const wanted = query.trim().toLowerCase();
  const found = loaded && "sessions" in loaded ? loaded.sessions.filter((one) => one.name.toLowerCase().includes(wanted)) : [];
  const groups = grouped(found);
  const toggleStopped = () => {
    setStoppedOpen(!stoppedOpen);
    storeStoppedOpen(!stoppedOpen);
  };
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
  const toggle = (collapsed: boolean) => {
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
        <SessionStrip loaded={loaded} openRef={focus.open} onOpen={() => toggle(false)}>
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
              onClick={() => toggle(true)}
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
                <Group name="Needs you" sessions={groups.needsYou} />
                <Group name="Running" sessions={groups.running} />
                {groups.stopped.length > 0 && (
                  <FoldToggle
                    name="Stopped"
                    count={groups.stopped.length}
                    open={stoppedOpen}
                    controls="stopped-sessions"
                    onToggle={toggleStopped}
                  />
                )}
                {stoppedOpen && <Group name="Stopped" id="stopped-sessions" sessions={groups.stopped} hideName />}
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
          {groups?.needsYou.map((session) => <StripIcon key={session.name} session={session} />)}
          {groups && groups.needsYou.length > 0 && groups.running.length > 0 && (
            <li className="strip-gap" aria-hidden="true" />
          )}
          {groups?.running.map((session) => <StripIcon key={session.name} session={session} />)}
        </ul>
      )}
    </nav>
  );
}

// A session's two letters: the first of its first two words, else its first two letters.
// Two sessions may share them: the tooltip and the label tell them apart.
const initials = (name: string) => {
  const words = name.split(/[-_./\s]+/).filter(Boolean);
  return (words.length > 1 ? words[0][0] + words[1][0] : name.slice(0, 2)).toUpperCase();
};

function StripIcon({ session }: { session: SessionInfo }) {
  const needsYou = waits(session);
  return (
    <li>
      <Tooltip tip={<SessionTip session={session} />}>
        <NavLink
          to={sessionPath(session.name)}
          className={`strip-session${needsYou ? " waits" : ""}`}
          aria-label={needsYou ? `${session.name}, needs you` : session.name}
        >
          {initials(session.name)}
        </NavLink>
      </Tooltip>
    </li>
  );
}

// Who a session is: its name, status and agents, what waits for the human, its folder, its
// kits and provider.
function SessionTip({ session }: { session: SessionInfo }) {
  return (
    <>
      <div className="tooltip-line">
        <b>{session.name}</b> · {STATUS[session.status]} · {count(session.agents, "agent")}
      </div>
      {waits(session) && <div className="tooltip-line waits">Needs you: {about(session)}</div>}
      <div className="tooltip-line">{session.repo}</div>
      <div className="tooltip-line">
        {session.kits.join(", ")} · {session.provider}
      </div>
    </>
  );
}

// Whether something in a session waits for the human, from what the server counts
// (SessionInfo.waiting): never in a stopped session, since nothing in it can be answered.
const waits = (session: SessionInfo) => {
  const { gates, questions, agents } = session.waiting;
  return isLive(session) && gates + questions + agents > 0;
};

// The list's groups: a stopped session is Stopped whatever waits in it.
function grouped(sessions: SessionInfo[]) {
  const stopped = sessions.filter((one) => !isLive(one));
  const live = sessions.filter(isLive);
  return { needsYou: live.filter(waits), running: live.filter((one) => !waits(one)), stopped };
}

const count = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

// One line under a session's name: what waits for the human, or its agents and status.
function about(session: SessionInfo): string {
  const { gates, questions, agents } = session.waiting;
  const parts = [
    gates > 0 && count(gates, "gate"),
    questions > 0 && count(questions, "question"),
    agents > 0 && `${count(agents, "agent")} waiting`,
  ].filter(Boolean);
  if (!isLive(session)) return STATUS.stopped;
  return parts.length ? parts.join(" · ") : count(session.agents, "agent");
}

function Group({
  name,
  sessions,
  id,
  hideName = false,
}: {
  name: string;
  sessions: SessionInfo[];
  id?: string;
  hideName?: boolean;
}) {
  if (sessions.length === 0) return null;
  const slug = name.toLowerCase().replace(/\s+/g, "-");
  const headId = `group-${slug}`;
  return (
    <section
      className={`session-group group-${slug}`}
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
        {sessions.map((session) => (
          <li key={session.name} className="session-row">
            <NavLink
              to={sessionPath(session.name)}
              className={`session-link${session.status === "running" ? "" : " dim"}${waits(session) ? " waits" : ""}`}
            >
              <span className="session-name">{session.name}</span>
              <span className="session-about">{about(session)}</span>
              {session.status !== "running" && session.status !== "stopped" && <Status status={session.status} />}
            </NavLink>
            <SessionRowMenu name={session.name} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function Status({ status }: { status: SessionStatus }) {
  return <span className={`status status-${status}`}>{STATUS[status]}</span>;
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

const TAB_TEXT: Record<Tab, string> = {
  activity: "Messages between the agents and you, flow steps and their notes, as they happen.",
  agents: "The session's agents: their roles, status and branches.",
  flows: "The session's flow runs: their state, who acts and the notes of each step.",
  artifacts: "The documents the agents write: designs, plans, reviews and reports.",
};

export function Session() {
  const { name = "", tab = "activity", item } = useParams();
  const loaded = useOutletContext<Loaded>();
  // Only the Flows and Agents tabs have pages of their own: their runs' and agents'.
  if (!isTab(tab) || (item !== undefined && tab !== "flows" && tab !== "agents")) return <NotFound />;
  return <SessionTab name={name} tab={tab} item={item} loaded={loaded} />;
}

function SessionTab({ name, tab, item, loaded }: { name: string; tab: Tab; item?: string; loaded: Loaded }) {
  useTitle("Sessions");
  const started = (useLocation().state as StartedState | null)?.started;
  if (loaded === null || "error" in loaded) return null; // the list, or its strip, says what is wrong
  // Just started here: the change feed may bring it a moment after the start's answer.
  const session =
    loaded.sessions.find((one) => one.name === name) ?? (started?.session.name === name ? started.session : undefined);
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
  const counts: Partial<Record<Tab, number>> = {
    flows: runs && "items" in runs ? runs.items.filter(isOpen).length : 0,
    agents: agents && "items" in agents ? agents.items.length : 0,
  };
  const tabName = (one: Tab) => (counts[one] ? `${TAB_NAMES[one]} · ${counts[one]}` : TAB_NAMES[one]);
  const stopped = session.status === "stopped";
  return (
    <section className="session" aria-label={`Session ${name}`}>
      <SessionHead session={session} />
      <StartedNotice name={name} />
      <nav className="tabs" aria-label="Session sections">
        {TABS.map((one) => (
          <Link
            key={one}
            to={sessionPath(name, one)}
            className="tab"
            aria-current={one === tab ? "page" : undefined}
          >
            {tabName(one)}
          </Link>
        ))}
      </nav>
      {tab === "agents" ? (
        <Agents session={name} agent={item} stopped={stopped} />
      ) : tab === "activity" ? (
        <Activity session={name} stopped={stopped} />
      ) : tab === "flows" ? (
        <Flows session={name} run={item} stopped={stopped} />
      ) : (
        <Placeholder title={TAB_NAMES[tab]} plan={PLANS[tab]} level={3}>
          {TAB_TEXT[tab]}
        </Placeholder>
      )}
    </section>
  );
}

// The session's head (docs/design/ui.md, Structure): its name, status and how long it ran,
// Copy link and its actions; below, small, its folder (Copy path on the folder's icon), its
// kits and its agents' CLI with the permission mode.
function SessionHead({ session }: { session: SessionInfo }) {
  const { name, repo, kits, provider, permission_mode: mode } = session;
  return (
    <header className="session-head">
      <div className="session-title">
        <h2 title={name}>{name}</h2>
        <Status status={session.status} />
        <Ran session={session} />
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
      </div>
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
        <span className="session-fact">
          <KitsIcon />
          <span className="session-kits">{kits.join(", ")}</span>
        </span>
        <span className="session-fact">
          <AgentCliIcon />
          <span className="session-agent-cli">{mode ? `${provider} · ${mode}` : provider}</span>
        </span>
      </div>
    </header>
  );
}

const TICK_MS = 60_000; // how often a running session's time is counted on

// How long the session ran: while it runs, its closed spans and the time since its last
// start, counted on each minute; stopped, how long ago too.
function Ran({ session }: { session: SessionInfo }) {
  const { running_since: since, stopped_at: stopped } = session;
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    if (!since) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), TICK_MS);
    return () => clearInterval(timer);
  }, [since]);
  const open = since ? Math.max(0, (now - new Date(since).getTime()) / 1000) : 0;
  const ran = duration(session.ran_seconds + open, true);
  const text = since ? ran : stopped ? `stopped ${ago(stopped)} ago · ran ${ran}` : `ran ${ran}`;
  return <span className="session-ran">{text}</span>;
}

// What a start or resume from the New session window said: the settings a resume changed,
// and open runs that cannot go on as they are, until the human closes it.
function StartedNotice({ name }: { name: string }) {
  const location = useLocation();
  const navigate = useNavigate();
  const started = (location.state as StartedState | null)?.started;
  if (!started || started.session.name !== name) return null;
  const { changes, problems, resumed } = started;
  if (changes.length === 0 && problems.length === 0) return null;
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
      <button type="button" className="quiet" onClick={close}>
        Close
      </button>
    </div>
  );
}

// The Activity tab: the team, the switch for the agents' messages to each other (it changes
// only what the feed shows, and is remembered), and the feed with the composer.
function Activity({ session, stopped }: { session: string; stopped: boolean }) {
  const [agentMessages, setAgentMessages] = useState(storedAgentMessages);
  return (
    <div className="activity">
      <div className="team-row">
        <Team session={session} />
        <label className="switch">
          <input
            type="checkbox"
            checked={agentMessages}
            onChange={(event) => {
              setAgentMessages(event.target.checked);
              storeAgentMessages(event.target.checked);
            }}
          />
          Show agent messages
        </label>
      </div>
      <Chat session={session} stopped={stopped} agentMessages={agentMessages} />
    </div>
  );
}
