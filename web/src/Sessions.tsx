// Sessions: the list on the left (from /api/sessions, searched by name here), the selected
// session on the right with its tabs. The list's width is dragged on its edge and remembered.
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Link, NavLink, Outlet, useOutletContext, useParams } from "react-router";

import type { SessionInfo, SessionStatus } from "./api";
import { Chat } from "./Chat";
import { useLive, useLiveStore, type Loaded } from "./live";
import { MAIN_MIN, TerminalPanel, useOpenTerminal } from "./Terminals";
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
} from "./prefs";
import { Launch, useTitle } from "./Shell";
import { fitWidth, Splitter, useWidth } from "./Splitter";
import { Team } from "./Team";

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
  const page = useRef<HTMLDivElement>(null);
  const room = useWidth(page);
  // The list leaves the session and the terminals their least widths.
  const width = fitWidth(list.width, SESSIONS_WIDTH, room === null ? null : room - MAIN_MIN - PANEL_WIDTH.min);
  const resize = (next: number) => {
    setList({ width: next });
    storeSessionsList({ width: next });
  };
  return (
    <div ref={page} className="sessions" style={{ "--list-width": `${width}px` } as CSSProperties}>
      <Splitter label="Resize the session list" edge="right" width={width} bounds={SESSIONS_WIDTH} onChange={resize} />
      <div className="session-list">
        <div className="session-list-head">
          <h2>Sessions</h2>
          <Launch variant="plus" />
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
                <button
                  type="button"
                  className="group-toggle"
                  aria-expanded={stoppedOpen}
                  aria-controls="stopped-sessions"
                  onClick={toggleStopped}
                >
                  <span aria-hidden="true">{stoppedOpen ? "▾" : "›"} </span>
                  Stopped ({groups.stopped.length})
                </button>
              )}
              {stoppedOpen && <Group name="Stopped" id="stopped-sessions" sessions={groups.stopped} hideName />}
            </>
          )}
        </nav>
      </div>
      <div className="session-detail">
        <Outlet context={loaded} />
      </div>
    </div>
  );
}

const waits = (session: SessionInfo) => {
  const { gates, questions, agents } = session.waiting;
  return gates + questions + agents > 0;
};

// The list's groups, from what the server counts (SessionInfo.waiting): a stopped session is
// Stopped whatever waits in it, since nothing in it can be answered.
function grouped(sessions: SessionInfo[]) {
  const stopped = sessions.filter((one) => one.status === "stopped");
  const live = sessions.filter((one) => one.status !== "stopped");
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
  if (session.status !== "stopped" && parts.length) return parts.join(" · ");
  return session.status === "stopped" ? STATUS.stopped : count(session.agents, "agent");
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
          <li key={session.name}>
            <NavLink
              to={sessionPath(session.name)}
              className={`session-link${session.status === "running" ? "" : " dim"}${waits(session) && session.status !== "stopped" ? " waits" : ""}`}
            >
              <span className="session-name">{session.name}</span>
              <span className="session-about">{about(session)}</span>
              {session.status !== "running" && session.status !== "stopped" && <Status status={session.status} />}
            </NavLink>
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
    return (
      <p className="empty">
        No sessions yet. Start one with <code>lado start &lt;repo&gt;</code>
      </p>
    );
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
  const { name = "", tab = "activity" } = useParams();
  const loaded = useOutletContext<Loaded>();
  if (!isTab(tab)) return <NotFound />;
  return <SessionTab name={name} tab={tab} loaded={loaded} />;
}

function SessionTab({ name, tab, loaded }: { name: string; tab: Tab; loaded: Loaded }) {
  useTitle("Sessions");
  if (loaded === null || "error" in loaded) return null; // the list says what is wrong
  const session = loaded.sessions.find((one) => one.name === name);
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
      <SessionView name={name} tab={tab} session={session} />
    </TerminalPanel>
  );
}

function SessionView({ name, tab, session }: { name: string; tab: Tab; session: SessionInfo }) {
  return (
    <section className="session" aria-label={`Session ${name}`}>
      <header className="session-head">
        <h2>{name}</h2>
        <Status status={session.status} />
      </header>
      <nav className="tabs" aria-label="Session sections">
        {TABS.map((one) => (
          <Link
            key={one}
            to={sessionPath(name, one)}
            className="tab"
            aria-current={one === tab ? "page" : undefined}
          >
            {TAB_NAMES[one]}
          </Link>
        ))}
      </nav>
      {tab === "agents" ? (
        <Agents session={name} />
      ) : tab === "activity" ? (
        <Activity session={name} stopped={session.status === "stopped"} />
      ) : (
        <Placeholder title={TAB_NAMES[tab]} plan={PLANS[tab]} level={3}>
          {TAB_TEXT[tab]}
        </Placeholder>
      )}
    </section>
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

// The session's agents, live: their roles, providers and status, and their terminals.
// The full section (branches, worktrees, what each works on) is the Agents task's.
function Agents({ session }: { session: string }) {
  const live = useLiveStore();
  const loaded = useLive().agents[session] ?? null;
  const openTerminal = useOpenTerminal();
  useEffect(() => live.watch("agents", session), [live, session]);

  if (loaded === null) return <p className="muted">Loading…</p>;
  if ("error" in loaded) {
    return (
      <p className="problem" role="alert">
        {loaded.error}
      </p>
    );
  }
  return (
    <table className="agents" aria-label={`Agents of ${session}`}>
      <thead>
        <tr>
          <th scope="col">Agent</th>
          <th scope="col">Role</th>
          <th scope="col">Provider</th>
          <th scope="col">Status</th>
          <th scope="col">Terminal</th>
        </tr>
      </thead>
      <tbody>
        {loaded.items.map((agent) => (
          <tr key={agent.name}>
            <td className="agent-name">{agent.name}</td>
            <td>{agent.role}</td>
            <td>{agent.provider}</td>
            <td>
              <span className={`status agent-${agent.status}`}>{agent.status}</span>
            </td>
            <td>
              <button
                type="button"
                className="quiet"
                aria-label={`Open ${agent.name}'s terminal`}
                onClick={() => openTerminal(agent.name)}
              >
                Open terminal
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
