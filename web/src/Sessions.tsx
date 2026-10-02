import { useEffect, useState } from "react";

import { ApiError, getSessions, type SessionInfo, type SessionStatus } from "./api";

// What each status means to the human, in the words of `lado ls`.
const STATUS: Record<SessionStatus, string> = {
  running: "running",
  stopped: "stopped",
  tmux_gone: "tmux session is gone",
  loop_down: "session loop not running",
};

type Loaded = { sessions: SessionInfo[] } | { error: string } | null;

export function Sessions() {
  const [loaded, setLoaded] = useState<Loaded>(null);

  useEffect(() => {
    getSessions()
      .then((sessions) => setLoaded({ sessions }))
      .catch((error: unknown) =>
        setLoaded({ error: error instanceof ApiError ? error.message : String(error) }),
      );
  }, []);

  return (
    <div className="page">
      <header className="bar">
        <span className="mark">LADO</span>
      </header>
      <main className="content">
        <h1>
          Sessions
          {loaded && "sessions" in loaded && (
            <span className="count">{loaded.sessions.length}</span>
          )}
        </h1>
        {loaded === null && <p className="muted">Loading…</p>}
        {loaded && "error" in loaded && (
          <p className="problem" role="alert">
            {loaded.error}
          </p>
        )}
        {loaded && "sessions" in loaded && <Table sessions={loaded.sessions} />}
      </main>
    </div>
  );
}

function Table({ sessions }: { sessions: SessionInfo[] }) {
  if (sessions.length === 0) {
    return (
      <p className="muted">
        No sessions yet. Start one with <code>lado start &lt;repo&gt;</code>
      </p>
    );
  }
  return (
    <div className="panel">
      <table>
        <thead>
          <tr>
            <th>Session</th>
            <th>Repository</th>
            <th>Status</th>
            <th className="number">Agents</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((session) => (
            <tr key={session.name}>
              <td className="name">{session.name}</td>
              <td className="repo">
                <code>{session.repo}</code>
              </td>
              <td>
                <span className={`status status-${session.status}`}>{STATUS[session.status]}</span>
              </td>
              <td className="number">{session.agents}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
