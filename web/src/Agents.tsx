// The session's Agents tab (docs/design/ui.md, Agents): its live agents on the left, the
// supervisor first; the selected agent's page on the right: what it does (status, run and
// step, task), its branch, worktree and the state of its work in git, its latest messages,
// and the actions on it (its terminal, a message to it, Finish). The agents follow the feed
// (live.ts); the state of the work is asked of the server: git has no item in the feed. The
// list and the page are a ListPage.
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";

import {
  ApiError,
  finishAgent,
  getAgentDetails,
  getFinishPreview,
  type AgentDetails,
  type AgentInfo,
  type FinishPreviewInfo,
  type RunInfo,
} from "./api";
import { Composer } from "./Chat";
import { clock, Preview, since } from "./ChatText";
import { isOpen } from "./Flows";
import { messageWindow, useLive, useLiveStore, windowKey, type MessageSpec } from "./live";
import { ListPage, type Entry } from "./ListPage";
import { agentPath, runPath, sessionPath } from "./paths";
import { storeAgentMessages } from "./prefs";
import { StatusDot, SUPERVISOR } from "./Team";
import { useOpenTerminal } from "./Terminals";

const MESSAGES = 10; // the latest messages of an agent its page shows
const TASK_LINES = 3; // the lines of a task shown before Show more

const messageOf = (error: unknown) => (error instanceof ApiError ? error.message : String(error));

const firstLine = (text: string | null) => (text ?? "").split("\n")[0];

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

// The supervisor first, then the others by when they were spawned.
export function agentOrder(agents: AgentInfo[]): AgentInfo[] {
  const others = agents.filter((one) => one.name !== SUPERVISOR);
  others.sort((a, b) => a.spawned_at.localeCompare(b.spawned_at));
  return [...agents.filter((one) => one.name === SUPERVISOR), ...others];
}

// An agent's name as another page shows it (Flows): a link to its page while it lives, else
// the name only. The page that shows it watches the session's agents.
export function AgentName({ session, name }: { session: string; name: string }) {
  const loaded = useLive().agents[session];
  const alive = loaded && "items" in loaded && loaded.items.some((one) => one.name === name);
  return alive ? <Link to={agentPath(session, name)}>{name}</Link> : <>{name}</>;
}

export function Agents({ session, agent, stopped }: { session: string; agent?: string; stopped: boolean }) {
  const live = useLiveStore();
  const state = useLive();
  useEffect(() => live.watch("agents", session), [live, session]);
  useEffect(() => live.watch("runs", session), [live, session]);

  const loaded = state.agents[session] ?? null;
  const agents = loaded && "items" in loaded ? agentOrder(loaded.items) : null;
  const runs = state.runs[session];
  const lists = { runs: runs && "items" in runs ? runs.items : [] };

  let notice;
  if (loaded === null) {
    notice = <p className="muted">Loading…</p>;
  } else if ("error" in loaded) {
    notice = (
      <p className="problem" role="alert">
        {loaded.error}
      </p>
    );
  } else if (stopped) {
    // `lado stop` forgets a session's agents: there is nothing to list.
    notice = <p className="empty">Session stopped: no agents</p>;
  }
  const alive = agents?.find((one) => one.name === agent);
  const page = alive ? (
    <AgentPage key={alive.name} session={session} agent={alive} lists={lists} />
  ) : (
    <p className="empty">Agent {agent} not found</p>
  );
  return (
    <ListPage
      label="Agents"
      noun="agent"
      groups={[
        {
          name: "Agents",
          heading: false,
          entries: (agents ?? []).map((one) => liveEntry(session, one, lists.runs)),
        },
      ]}
      selected={agent === undefined ? undefined : `agent:${agent}`}
      page={page}
      listPath={sessionPath(session, "agents")}
      back="All agents"
      fallback={agentPath(session, SUPERVISOR)}
      notice={notice}
    />
  );
}

// What an agent works for now: its run and the run's state, else the first line of its task.
function workingOn(agent: AgentInfo, runs: RunInfo[]): string {
  if (agent.run) {
    const run = runs.find((one) => one.name === agent.run);
    return run ? `${agent.run} · ${run.state}` : agent.run;
  }
  return firstLine(agent.task);
}

// A live agent's row: its status, and why it waits or stopped, or what it works for.
function liveEntry(session: string, agent: AgentInfo, runs: RunInfo[]): Entry {
  const waits = agent.status === "waiting";
  const detail = agent.status_reason ? firstLine(agent.status_reason) : workingOn(agent, runs);
  return {
    key: `agent:${agent.name}`,
    to: agentPath(session, agent.name),
    row: (
      <>
        <span className="agent-row-head">
          <StatusDot status={agent.status} />
          <span className="agent-row-name">{agent.name}</span>
        </span>
        <span className="agent-row-about">
          {agent.status} · {since(agent.since)}
        </span>
        {detail && <span className="agent-row-about">{detail}</span>}
      </>
    ),
    search: [agent.name, agent.role, agent.task ?? "", agent.run ?? ""],
    tone: waits ? "waits" : undefined,
  };
}

type Lists = { runs: RunInfo[] };

// Where the work stands in git: asked when the page opens, again when the agent becomes idle
// (it may have committed) and on Refresh; no polling. The last answer stays while a new one
// is asked.
function useWork(session: string, agent: AgentInfo) {
  const [details, setDetails] = useState<AgentDetails | null>(null);
  const [at, setAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const asked = useRef(0);
  const load = () => {
    const ask = ++asked.current;
    setLoading(true);
    getAgentDetails(session, agent.name).then(
      (answer) => {
        if (ask !== asked.current) return;
        setDetails(answer);
        setAt(new Date().toISOString());
        setProblem(null);
        setLoading(false);
      },
      (error: unknown) => {
        if (ask !== asked.current) return;
        setProblem(messageOf(error));
        setLoading(false);
      },
    );
  };
  const before = useRef(agent.status);
  useEffect(() => {
    if (before.current !== agent.status && agent.status === "idle") load();
    before.current = agent.status;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agent.status]);
  useEffect(() => {
    load();
    // Loaded once per agent: the page is keyed by its name.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return { details, at, loading, problem, refresh: load };
}

// A live agent's page; a stopped session has none (its agents are forgotten).
function AgentPage({ session, agent, lists }: { session: string; agent: AgentInfo; lists: Lists }) {
  const openTerminal = useOpenTerminal();
  const work = useWork(session, agent);
  const composer = useRef<HTMLTextAreaElement>(null);
  const [finishing, setFinishing] = useState(false);
  const worker = agent.name !== SUPERVISOR;
  const run = agent.run ? lists.runs.find((one) => one.name === agent.run) : undefined;
  const task = work.details?.task ?? agent.task;
  return (
    <section className="agent-page" aria-label={`Agent ${agent.name}`}>
      <header className="agent-head">
        <div className="agent-title">
          <h3>{agent.name}</h3>
          <span className="muted">
            {agent.role} · {agent.provider}
          </span>
        </div>
        <p className="agent-now">
          <StatusDot status={agent.status} /> {agent.status} for {since(agent.since)} · spawned{" "}
          <time dateTime={agent.spawned_at}>{clock(agent.spawned_at)}</time>
          {agent.run && (
            <>
              {" "}
              for run <Link to={runPath(session, agent.run)}>{agent.run}</Link>
              {run && isOpen(run) && (
                <>
                  , step <strong>{run.state}</strong> (visit {run.visits[run.state] ?? 0})
                </>
              )}
            </>
          )}
        </p>
        <div className="agent-actions">
          <button type="button" className="quiet" onClick={() => openTerminal(agent.name)}>
            Open terminal
          </button>
          <button type="button" className="quiet" onClick={() => composer.current?.focus()}>
            Write to {agent.name}
          </button>
          {worker && (
            <button type="button" className="quiet finish-button" onClick={() => setFinishing(true)}>
              Finish…
            </button>
          )}
        </div>
      </header>
      {agent.status === "waiting" && (
        <p className="agent-waits" role="note">
          {agent.status_reason ?? "Waits for you in its terminal."}
        </p>
      )}
      {agent.status === "stopped" && agent.status_reason && (
        <p className="agent-waits" role="note">
          Stopped: {agent.status_reason}
        </p>
      )}
      <dl className="agent-facts">
        {agent.branch && (
          <>
            <dt>Branch</dt>
            <dd>
              <code>{agent.branch}</code>
            </dd>
            <dt>Work</dt>
            <dd>
              <Work work={work} />
            </dd>
            <dt>Worktree</dt>
            <dd>
              <code>{agent.worktree}</code>
            </dd>
          </>
        )}
        {task && (
          <>
            <dt>Task</dt>
            <dd className="agent-task">
              <Preview text={task} lines={TASK_LINES} />
            </dd>
          </>
        )}
      </dl>
      <AgentMessages session={session} name={agent.name} from={agent.spawned_at} />
      <div className="agent-composer">
        <Composer session={session} stopped={false} to={agent.name} inputRef={composer} />
        {worker && <p className="muted hint">The supervisor gets a one-line copy.</p>}
      </div>
      {finishing && <FinishDialog session={session} agent={agent.name} onClose={() => setFinishing(false)} />}
    </section>
  );
}

function Work({ work }: { work: ReturnType<typeof useWork> }) {
  const { details, at, loading, problem, refresh } = work;
  const found = details?.work;
  let text;
  if (details === null) {
    text = problem ?? "Loading…";
  } else if (found) {
    const last = found.last_commit;
    text = (
      <>
        {plural(found.ahead, "commit")} ahead of {found.base} · {found.behind} behind ·{" "}
        {plural(found.uncommitted, "file")} not committed · last commit{" "}
        <time dateTime={last.at}>{clock(last.at)}</time> “{last.subject}”
      </>
    );
  } else {
    text = details.work_problem ?? "";
  }
  return (
    <span className={`agent-work${loading && details !== null ? " stale" : ""}`}>
      {text}
      {at && <span className="muted"> · as of {clock(at)}</span>}
      {loading && details !== null && <span className="muted"> · refreshing…</span>}{" "}
      <button type="button" className="link-button" onClick={refresh} disabled={loading}>
        Refresh
      </button>
    </span>
  );
}

// The agent's latest messages, from and to it, in its lifetime only (a name is used again):
// a window of the session's messages the server takes them from, one load.
function AgentMessages({ session, name, from }: { session: string; name: string; from: string }) {
  const navigate = useNavigate();
  const live = useLiveStore();
  const spec: MessageSpec = { agent: name, since: from, limit: MESSAGES };
  const key = windowKey(spec);
  useEffect(() => live.watchMessages(session, spec), [live, session, key]); // key: the spec's
  const window = messageWindow(useLive(), session, spec);
  const latest = window && "items" in window ? window.items.slice(-MESSAGES) : []; // the feed adds to it
  const all = () => {
    storeAgentMessages(true);
    navigate(sessionPath(session, "activity"));
  };
  return (
    <section className="agent-messages" aria-label="Messages">
      <h4>Messages</h4>
      {!window ? (
        <p className="muted">Loading…</p>
      ) : "error" in window ? (
        <p className="problem" role="alert">
          {window.error}
        </p>
      ) : latest.length === 0 ? (
        <p className="muted">No messages yet</p>
      ) : (
        <ol>
          {latest.map((one) => (
            <li key={one.id}>
              <span className="muted">
                <time dateTime={one.created_at}>{clock(one.created_at)}</time> {one.from} → {one.to}
              </span>{" "}
              · {one.summary} · <span className="muted">{one.state}</span>
            </li>
          ))}
        </ol>
      )}
      <button type="button" className="link-button" onClick={all}>
        All in Activity
      </button>
    </section>
  );
}

// Finish asks first and says only what the core's preview says: what goes, or why it is
// refused, and then Discard work… with what would be thrown away.
function FinishDialog({ session, agent, onClose }: { session: string; agent: string; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const navigate = useNavigate();
  const [preview, setPreview] = useState<{ value: FinishPreviewInfo } | { error: string } | null>(null);
  const [discarding, setDiscarding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  useEffect(() => {
    dialog.current?.showModal();
    let current = true;
    getFinishPreview(session, agent).then(
      (value) => current && setPreview({ value }),
      (error: unknown) => current && setPreview({ error: messageOf(error) }),
    );
    return () => {
      current = false;
    };
  }, [session, agent]);
  const finish = async (discard: boolean) => {
    setBusy(true);
    setRefused(null);
    try {
      await finishAgent(session, agent, discard);
      onClose();
      navigate(sessionPath(session, "agents"));
    } catch (error) {
      setRefused(messageOf(error));
      setBusy(false);
    }
  };
  const found = preview !== null && "value" in preview ? preview.value : null;
  const title = `Finish ${agent}?`;
  const work = found?.work;
  return (
    <dialog
      ref={dialog}
      className="question-dialog"
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      <h3>{title}</h3>
      {preview === null && <p className="muted">Loading…</p>}
      {preview !== null && "error" in preview && (
        <p className="problem" role="alert">
          {preview.error}
        </p>
      )}
      {found && !discarding && (
        <p>
          {found.removes_worktree
            ? `Finish ${agent}: its branch and worktree are removed.`
            : `Finish ${agent}: closes its window; the run keeps its worktree and branch, and its step will need a new worker.`}
        </p>
      )}
      {found?.refused && !discarding && (
        <p className="problem" role="alert">
          {found.refused}
        </p>
      )}
      {discarding && (
        <div role="alert">
          <p>Discard the work of {agent}? This cannot be undone.</p>
          {work && (
            <ul className="consequences">
              <li>
                branch <code>{work.branch}</code> is deleted
              </li>
              <li>
                {plural(work.ahead, "commit")} not in {work.base} {work.ahead === 1 ? "is" : "are"} lost
              </li>
              <li>
                {plural(work.uncommitted, "uncommitted file")} {work.uncommitted === 1 ? "is" : "are"} lost
              </li>
            </ul>
          )}
        </div>
      )}
      {refused && (
        <p className="problem" role="alert">
          {refused}
        </p>
      )}
      <div className="question-buttons">
        <button type="button" className="quiet" onClick={onClose} disabled={busy} autoFocus>
          Cancel
        </button>
        {found && !found.refused && (
          <button type="button" className="primary" disabled={busy} onClick={() => void finish(false)}>
            {busy ? "Finishing…" : `Finish ${agent}`}
          </button>
        )}
        {found?.refused && found.removes_worktree && !discarding && (
          <button type="button" className="quiet" disabled={busy} onClick={() => setDiscarding(true)}>
            Discard work…
          </button>
        )}
        {discarding && (
          <button type="button" className="danger" disabled={busy} onClick={() => void finish(true)}>
            {busy ? "Discarding…" : "Discard and finish"}
          </button>
        )}
      </div>
    </dialog>
  );
}
