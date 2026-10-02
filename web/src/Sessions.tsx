// Sessions: the list on the left (from /api/sessions, searched by name here), the selected
// session on the right with the place for its gates and its tabs.
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useOutletContext, useParams } from "react-router";

import { ApiError, getSessions, type SessionInfo, type SessionStatus } from "./api";
import { NotFound } from "./pages";
import { isTab, PLANS, sessionPath, TABS, type Tab } from "./paths";
import { Placeholder } from "./Placeholder";
import { useTitle } from "./Shell";

// What each status means to the human, in the words of `lado ls`.
const STATUS: Record<SessionStatus, string> = {
  running: "running",
  stopped: "stopped",
  tmux_gone: "tmux session is gone",
  loop_down: "session loop not running",
};

type Loaded = { sessions: SessionInfo[] } | { error: string } | null;

// The pages inside (NoSession, Session) name themselves: a session's unknown tab is Not found.
export function Sessions() {
  const [loaded, setLoaded] = useState<Loaded>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    getSessions()
      .then((sessions) => setLoaded({ sessions }))
      .catch((error: unknown) =>
        setLoaded({ error: error instanceof ApiError ? error.message : String(error) }),
      );
  }, []);

  const wanted = query.trim().toLowerCase();
  return (
    <div className="sessions">
      <div className="session-list">
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
            <ul>
              {loaded.sessions
                .filter((session) => session.name.toLowerCase().includes(wanted))
                .map((session) => (
                  <li key={session.name}>
                    <NavLink
                      to={sessionPath(session.name)}
                      className={`session-link${session.status === "running" ? "" : " dim"}`}
                    >
                      <span className="session-name">{session.name}</span>
                      <Status status={session.status} />
                    </NavLink>
                  </li>
                ))}
            </ul>
          )}
        </nav>
      </div>
      <div className="session-detail">
        <Outlet context={loaded} />
      </div>
    </div>
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
    <section className="session" aria-label={`Session ${name}`}>
      <header className="session-head">
        <h2>{name}</h2>
        <Status status={session.status} />
      </header>
      <p className="gate-slot" role="note">
        Gates of this session that wait for you will show here.{" "}
        <a href={PLANS.gates.href} target="_blank" rel="noreferrer">
          Plan: {PLANS.gates.label}
        </a>
      </p>
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
      <Placeholder title={TAB_NAMES[tab]} plan={PLANS[tab]} level={3}>
        {TAB_TEXT[tab]}
      </Placeholder>
    </section>
  );
}
