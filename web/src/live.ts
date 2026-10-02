// The change feed (docs/design/ui.md, Server): one EventSource per browser tab, opened by
// the shell, and the store the sections read; a section opens no stream of its own and
// never polls. On `reset` the store loads the data again (the first load and after a gap
// are one path); a `change` carries its item as it is now, or null when it is gone.
import { createContext, useContext, useSyncExternalStore } from "react";

import { ApiError, getSessions, type SessionInfo } from "./api";

export type Change = { kind: string; session: string; key: string; op: string; item: unknown };

export type Loaded = { sessions: SessionInfo[] } | { error: string } | null;

// connecting: before the first open; down: no stream now, one comes again; refused: the
// token is wrong, the shell says how to get in and nothing is tried again.
export type Link = "connecting" | "open" | "down" | "refused";

export type LiveState = { sessions: Loaded; link: Link; problem: string | null };

export const RETRY_MS = 3000; // the pause before a new stream when the server closed one

export class Live {
  private state: LiveState = { sessions: null, link: "connecting", problem: null };
  private listeners = new Set<() => void>();
  private source: EventSource | null = null;
  private retry: ReturnType<typeof setTimeout> | undefined;
  private lastId = ""; // the latest journal id the stream sent; derived changes have none
  private loading: Change[] | null = null; // changes that came while a load runs

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
    const problem = await getSessions().then(
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

  private load() {
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
  const live = useContext(LiveContext);
  if (live === null) throw new Error("useLive outside the shell");
  return useSyncExternalStore(live.subscribe, live.get);
}
