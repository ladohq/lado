// The change feed (docs/design/ui.md, Server): one EventSource per browser tab, opened by
// the shell, and the store the sections read; a section opens no stream of its own and
// never polls. On `reset` the store loads the data again (the first load and after a gap
// are one path); a `change` carries its item as it is now, or null when it is gone.
import { createContext, useContext, useSyncExternalStore } from "react";

import { ApiError, getAgents, getSessions, probeStream, type AgentInfo, type SessionInfo } from "./api";

export type Change = { kind: string; session: string; key: string; op: string; item: unknown };

export type Loaded = { sessions: SessionInfo[] } | { error: string } | null;

export type AgentsLoaded = { agents: AgentInfo[] } | { error: string } | null;

// connecting: before the first open; down: no stream now, one comes again; refused: the
// token is wrong, the shell says how to get in and nothing is tried again.
export type Link = "connecting" | "open" | "down" | "refused";

// agents: the agents of each session a page watches (watchAgents), by session name.
export type LiveState = {
  sessions: Loaded;
  agents: Record<string, AgentsLoaded>;
  link: Link;
  problem: string | null;
};

export const RETRY_MS = 3000; // the pause before a new stream when the server closed one

export class Live {
  private state: LiveState = { sessions: null, agents: {}, link: "connecting", problem: null };
  private listeners = new Set<() => void>();
  private source: EventSource | null = null;
  private retry: ReturnType<typeof setTimeout> | undefined;
  private lastId = ""; // the latest journal id the stream sent; derived changes have none
  private loading: Change[] | null = null; // changes that came while a load runs
  private watched = new Map<string, number>(); // session -> pages that watch its agents
  private agentLoads = new Map<string, Change[]>(); // a session's agents being loaded

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  get = () => this.state;

  private set(patch: Partial<LiveState>) {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach((listener) => listener());
  }

  start() {
    this.connect();
  }

  stop() {
    clearTimeout(this.retry);
    this.source?.close();
    this.source = null;
  }

  private connect() {
    const url = this.lastId ? `/api/events?after=${encodeURIComponent(this.lastId)}` : "/api/events";
    const source = new EventSource(url);
    this.source = source;
    source.onopen = () => this.set({ link: "open", problem: null });
    source.addEventListener("reset", (event) => {
      this.lastId = event.lastEventId;
      this.load();
    });
    source.addEventListener("change", (event) => {
      if (event.lastEventId) this.lastId = event.lastEventId;
      const change = JSON.parse(event.data) as Change;
      if (this.loading) this.loading.push(change);
      else this.apply(change);
    });
    source.onerror = () => {
      if (this.source !== source) return;
      this.set({ link: "down" });
      // The browser tries again by itself after a network error, not after an answer
      // other than the stream (401, 503): then ask the API why, and try again later.
      if (source.readyState === EventSource.CLOSED) void this.diagnose(source);
    };
  }

  private async diagnose(source: EventSource) {
    // The stream's own answer: the rest of the API may work while the feed does not.
    const problem = await probeStream(source.url).then(
      () => null,
      (error: unknown) => error,
    );
    if (this.source !== source) return; // stopped meanwhile
    if (problem instanceof ApiError && problem.status === 401) {
      this.set({ link: "refused", problem: problem.message }); // api.ts told the shell
      return;
    }
    this.set({ problem: problem === null ? null : message(problem) });
    this.retry = setTimeout(() => this.connect(), RETRY_MS);
  }

  // A page that shows the session's agents: they load now and follow the feed until the
  // last page that watches them lets go (the returned function).
  watchAgents(session: string): () => void {
    this.watched.set(session, (this.watched.get(session) ?? 0) + 1);
    if (!(session in this.state.agents)) this.loadAgents(session);
    return () => {
      const left = (this.watched.get(session) ?? 1) - 1;
      if (left > 0) {
        this.watched.set(session, left);
        return;
      }
      this.watched.delete(session);
      this.agentLoads.delete(session);
      const { [session]: _, ...others } = this.state.agents;
      this.set({ agents: others });
    };
  }

  private loadAgents(session: string) {
    const changes: Change[] = [];
    this.agentLoads.set(session, changes);
    this.set({ agents: { ...this.state.agents, [session]: this.state.agents[session] ?? null } });
    getAgents(session)
      .then(
        (agents) => ({ agents }),
        (error: unknown) => ({ error: message(error) }),
      )
      .then((agents) => {
        if (this.agentLoads.get(session) !== changes) return; // a later load, or let go
        this.agentLoads.delete(session);
        this.set({ agents: { ...this.state.agents, [session]: agents } });
        changes.forEach((change) => this.applyAgent(change));
      });
  }

  private applyAgent(change: Change) {
    const pending = this.agentLoads.get(change.session);
    if (pending) {
      pending.push(change);
      return;
    }
    const loaded = this.state.agents[change.session];
    if (!loaded || "error" in loaded) return;
    const item = change.item as AgentInfo | null;
    const others = loaded.agents.filter((one) => one.name !== change.key);
    const at = loaded.agents.findIndex((one) => one.name === change.key);
    const agents =
      item === null ? others : at < 0 ? [...others, item] : loaded.agents.map((one, i) => (i === at ? item : one));
    this.set({ agents: { ...this.state.agents, [change.session]: { agents } } });
  }

  private load() {
    this.watched.forEach((_, session) => this.loadAgents(session));
    const changes: Change[] = [];
    this.loading = changes;
    getSessions()
      .then(
        (sessions) => ({ sessions }),
        (error: unknown) => ({ error: message(error) }),
      )
      .then((sessions) => {
        if (this.loading !== changes) return; // a later reset loads again
        this.loading = null;
        this.set({ sessions });
        changes.forEach((change) => this.apply(change)); // newer than the load, or the same
      });
  }

  private apply(change: Change) {
    if (change.kind === "agents" && this.watched.has(change.session)) this.applyAgent(change);
    const loaded = this.state.sessions;
    if (change.kind !== "sessions" || loaded === null || "error" in loaded) return;
    const item = change.item as SessionInfo | null;
    const others = loaded.sessions.filter((one) => one.name !== change.session);
    if (item === null) {
      this.set({ sessions: { sessions: others } });
      return;
    }
    const at = loaded.sessions.findIndex((one) => one.name === change.session);
    const sessions = at < 0 ? [...others, item] : loaded.sessions.map((one, i) => (i === at ? item : one));
    this.set({ sessions: { sessions } });
  }
}

function message(error: unknown): string {
  return error instanceof ApiError ? error.message : String(error);
}

export const LiveContext = createContext<Live | null>(null);

export function useLive(): LiveState {
  const live = useLiveStore();
  return useSyncExternalStore(live.subscribe, live.get);
}

// The store itself, for a page that asks it to watch something (watchAgents).
export function useLiveStore(): Live {
  const live = useContext(LiveContext);
  if (live === null) throw new Error("useLive outside the shell");
  return live;
}
