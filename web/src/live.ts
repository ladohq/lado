// The change feed (docs/design/ui.md, Server): one EventSource per browser tab, opened by
// the shell, and the store the sections read; a section opens no stream of its own and
// never polls. On `reset` the store loads the data again (the first load and after a gap
// are one path); a `change` carries its item as it is now, or null when it is gone.
import { createContext, useContext, useSyncExternalStore } from "react";

import {
  ApiError,
  getAgents,
  getMessages,
  getRunEvents,
  getSessions,
  probeStream,
  type AgentInfo,
  type MessageInfo,
  type RunEventInfo,
  type SessionInfo,
} from "./api";

export type Change = { kind: string; session: string; key: string; op: string; item: unknown };

export type Loaded = { sessions: SessionInfo[] } | { error: string } | null;

// A list of one session a page watches: its items, why it could not load, or loading.
export type ListLoaded<T> = { items: T[] } | { error: string } | null;

// connecting: before the first open; down: no stream now, one comes again; refused: the
// token is wrong, the shell says how to get in and nothing is tried again.
export type Link = "connecting" | "open" | "down" | "refused";

// agents, messages, events: the lists of each session a page watches (watch), by session name.
export type LiveState = {
  sessions: Loaded;
  agents: Record<string, ListLoaded<AgentInfo>>;
  messages: Record<string, ListLoaded<MessageInfo>>; // all of them: a page picks what it shows
  events: Record<string, ListLoaded<RunEventInfo>>; // the flow runs' events
  link: Link;
  problem: string | null;
};

type ListName = "agents" | "messages" | "events";

// How a list of a session is loaded and follows the feed: the change kind that is its, an
// item's key (the change's), which items it keeps and in what order.
type ListKind<T> = {
  load: (session: string) => Promise<T[]>;
  key: (item: T) => string;
  keeps: (item: T) => boolean;
  order?: (a: T, b: T) => number;
};

const LISTS: { agents: ListKind<AgentInfo>; messages: ListKind<MessageInfo>; events: ListKind<RunEventInfo> } = {
  agents: { load: getAgents, key: (agent) => agent.name, keeps: () => true },
  messages: {
    load: getMessages,
    key: (message) => String(message.id),
    keeps: () => true,
    order: (a, b) => a.id - b.id,
  },
  events: { load: getRunEvents, key: (event) => String(event.id), keeps: () => true, order: (a, b) => a.id - b.id },
};

export const RETRY_MS = 3000; // the pause before a new stream when the server closed one

export class Live {
  private state: LiveState = {
    sessions: null,
    agents: {},
    messages: {},
    events: {},
    link: "connecting",
    problem: null,
  };
  private listeners = new Set<() => void>();
  private source: EventSource | null = null;
  private retry: ReturnType<typeof setTimeout> | undefined;
  private lastId = ""; // the latest journal id the stream sent; derived changes have none
  private loading: Change[] | null = null; // changes that came while a load runs
  // Per list, session -> pages that watch it, and the changes that came while it loads.
  private watched: Record<ListName, Map<string, number>> = { agents: new Map(), messages: new Map(), events: new Map() };
  private listLoads: Record<ListName, Map<string, Change[]>> = {
    agents: new Map(),
    messages: new Map(),
    events: new Map(),
  };

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

  // A page that shows the session's agents, messages or run events: they load now and follow the feed until
  // the last page that watches them lets go (the returned function).
  watch(list: ListName, session: string): () => void {
    const watched = this.watched[list];
    watched.set(session, (watched.get(session) ?? 0) + 1);
    if (!(session in this.state[list])) this.loadList(list, session);
    return () => {
      const left = (watched.get(session) ?? 1) - 1;
      if (left > 0) {
        watched.set(session, left);
        return;
      }
      watched.delete(session);
      this.listLoads[list].delete(session);
      const { [session]: _, ...others } = this.state[list];
      this.set({ [list]: others });
    };
  }

  private loadList(list: ListName, session: string) {
    const kind = LISTS[list] as ListKind<unknown>;
    const changes: Change[] = [];
    this.listLoads[list].set(session, changes);
    const current = this.state[list];
    this.set({ [list]: { ...current, [session]: current[session] ?? null } });
    kind
      .load(session)
      .then(
        (items) => ({ items: items.filter(kind.keeps) }),
        (error: unknown) => ({ error: message(error) }),
      )
      .then((loaded) => {
        if (this.listLoads[list].get(session) !== changes) return; // a later load, or let go
        this.listLoads[list].delete(session);
        this.set({ [list]: { ...this.state[list], [session]: loaded } });
        changes.forEach((change) => this.applyList(list, change));
      });
  }

  private applyList(list: ListName, change: Change) {
    const pending = this.listLoads[list].get(change.session);
    if (pending) {
      pending.push(change);
      return;
    }
    const kind = LISTS[list] as ListKind<unknown>;
    const loaded = this.state[list][change.session] as ListLoaded<unknown> | undefined;
    if (!loaded || "error" in loaded) return;
    const item = change.item === null || !kind.keeps(change.item) ? null : change.item;
    const others = loaded.items.filter((one) => kind.key(one) !== change.key);
    const at = loaded.items.findIndex((one) => kind.key(one) === change.key);
    let items =
      item === null ? others : at < 0 ? [...others, item] : loaded.items.map((one, i) => (i === at ? item : one));
    if (kind.order) items = [...items].sort(kind.order);
    this.set({ [list]: { ...this.state[list], [change.session]: { items } } });
  }

  private load() {
    for (const list of Object.keys(this.watched) as ListName[]) {
      this.watched[list].forEach((_, session) => this.loadList(list, session));
    }
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
    const list = change.kind as ListName;
    if (list in this.watched && this.watched[list].has(change.session)) this.applyList(list, change);
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

// The store itself, for a page that asks it to watch something (watch).
export function useLiveStore(): Live {
  const live = useContext(LiveContext);
  if (live === null) throw new Error("useLive outside the shell");
  return live;
}
