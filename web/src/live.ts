// The change feed (docs/design/ui.md, Server): one EventSource per browser tab, opened by
// the shell, and the store the sections read; a section opens no stream of its own and
// never polls. On `reset` the store loads the data again (the first load and after a gap
// are one path); a `change` carries its item as it is now, or null when it is gone.
import { createContext, useContext, useSyncExternalStore } from "react";

import {
  ApiError,
  getAgents,
  getAvailableKits,
  getGates,
  getInstalledKits,
  getMarketplaces,
  getMessages,
  getNotes,
  getRunEvents,
  getRuns,
  getSessions,
  getWaiting,
  probeStream,
  type AgentInfo,
  type GateInfo,
  type InstalledKitInfo,
  type MarketplaceInfo,
  type MessageInfo,
  type OfferInfo,
  type MessagePage,
  type MessageQuery,
  type NoteInfo,
  type RunEventInfo,
  type RunInfo,
  type SessionInfo,
  type WaitingItem,
} from "./api";

export type Change = { kind: string; session: string; key: string; op: string; item: unknown };

export type Loaded = { sessions: SessionInfo[] } | { error: string } | null;

// A list of one session a page watches: its items, why it could not load, or loading.
export type ListLoaded<T> = { items: T[] } | { error: string } | null;

// connecting: before the first open; down: no stream now, one comes again; refused: the
// token is wrong, the shell says how to get in and nothing is tried again.
export type Link = "connecting" | "open" | "down" | "refused";

// A window of a session's messages a page watches (watchMessages): the latest `limit` of one
// kind (the server's filter without the cursors) when it opens, then the earlier pages it
// asks for (loadEarlier, loadUpTo) and the feed's newer ones. A session grows without end:
// no page loads all of its messages.
export type MessageSpec = Omit<MessageQuery, "before" | "after" | "limit"> & { limit: number };
export type MessageFilter = Omit<MessageQuery, "limit">;

// Its items oldest first, whether messages of its kind come before them, the time from which
// it holds every one of its kind (null: it holds all; a page shows what else it has, such as
// gates, from then on), whether earlier ones load now and why they could not.
export type MessageWindow = {
  items: MessageInfo[];
  earlier: boolean;
  from: string | null;
  loadingEarlier: boolean;
  problem: string | null;
};
export type WindowLoaded = MessageWindow | { error: string } | null;

const filterOf = ({ limit: _, ...filter }: MessageSpec): MessageFilter => filter;

export const windowKey = (spec: MessageSpec) =>
  JSON.stringify([spec.with ?? null, spec.agent ?? null, spec.since ?? null, spec.until ?? null, spec.limit]);

const second = (time: string) => Math.floor(Date.parse(time) / 1000) * 1000;

// Whether a message is one the filter takes: the server's rule (state.MessageFilter, the
// case table messageFilter.cases.json checks both), for the feed's changes.
export function matches(message: Pick<MessageInfo, "id" | "from" | "to" | "created_at">, filter: MessageFilter): boolean {
  const party = (name?: string) => name === undefined || message.from === name || message.to === name;
  const at = Date.parse(message.created_at);
  return (
    party(filter.with) &&
    party(filter.agent) &&
    (filter.before === undefined || message.id < filter.before) &&
    (filter.after === undefined || message.id > filter.after) &&
    (filter.since === undefined || at >= second(filter.since)) &&
    (filter.until === undefined || at < second(filter.until) + 1000)
  );
}

// A watched window: its pages, the loads under way and the changes that came meanwhile.
type Watched = {
  session: string;
  spec: MessageSpec;
  key: string;
  watchers: number;
  loads: number;
  loadingEarlier: boolean;
  pending: Change[];
};

// agents, events, gates, runs, notes: the lists of each session a page watches (watch), by
// session name; messages: its windows, by session and windowKey. waiting: what waits for the
// human in all sessions, while watched.
export type LiveState = {
  sessions: Loaded;
  agents: Record<string, ListLoaded<AgentInfo>>;
  messages: Record<string, Record<string, WindowLoaded>>;
  events: Record<string, ListLoaded<RunEventInfo>>; // the flow runs' events
  gates: Record<string, ListLoaded<GateInfo>>; // open and closed: a closed gate's item stays
  runs: Record<string, ListLoaded<RunInfo>>; // open and closed, newest first
  notes: Record<string, ListLoaded<NoteInfo>>; // the steps of all its runs, oldest first
  waiting: ListLoaded<WaitingItem>;
  kits: KitsLoaded | null; // while the Kits page watches them
  kitChanges: number; // how many changes of the installed kits came: the session head asks its about again
  link: Link;
  problem: string | null;
};

// The Kits page's lists: the installed kits (then the built-in ones), the marketplaces and
// the kits they offer. The feed carries the items of the first two (session ''); what is
// available is asked again whole when either changes.
export type KitsLoaded = {
  installed: ListLoaded<InstalledKitInfo>;
  marketplaces: ListLoaded<MarketplaceInfo>;
  available: ListLoaded<OfferInfo>;
};
type KitList = keyof KitsLoaded;

const KIT_LOADS: { [list in KitList]: () => Promise<KitsLoaded[list] extends ListLoaded<infer T> ? T[] : never> } = {
  installed: getInstalledKits,
  marketplaces: getMarketplaces,
  available: getAvailableKits,
};

// An installed kit's place: the user's first, then the built-in ones, each by name.
const kitOrder = (a: InstalledKitInfo, b: InstalledKitInfo) =>
  Number(a.kind === "built-in") - Number(b.kind === "built-in") || a.name.localeCompare(b.name);

// The change kinds that can change what waits for the human; a session's change does when
// it stops or comes back (isLive).
const WAITING_KINDS = new Set(["gates", "agents", "messages"]);

// A session whose waits count: the server's rule (state.waiting_items), the same here.
export const isLive = (session: SessionInfo) => session.status !== "stopped";

type ListName = "agents" | "events" | "gates" | "runs" | "notes";

// How a list of a session is loaded and follows the feed: the change kind that is its, an
// item's key (the change's), which items it keeps and in what order.
type ListKind<T> = {
  load: (session: string) => Promise<T[]>;
  key: (item: T) => string;
  keeps: (item: T) => boolean;
  order?: (a: T, b: T) => number;
};

const LISTS: {
  agents: ListKind<AgentInfo>;
  events: ListKind<RunEventInfo>;
  gates: ListKind<GateInfo>;
  runs: ListKind<RunInfo>;
  notes: ListKind<NoteInfo>;
} = {
  agents: { load: getAgents, key: (agent) => agent.name, keeps: () => true },
  events: { load: getRunEvents, key: (event) => String(event.id), keeps: () => true, order: (a, b) => a.id - b.id },
  gates: { load: getGates, key: (gate) => String(gate.id), keeps: () => true, order: (a, b) => a.id - b.id },
  runs: {
    load: getRuns,
    key: (run) => run.name,
    keeps: () => true,
    order: (a, b) => b.created_at.localeCompare(a.created_at),
  },
  notes: { load: getNotes, key: (note) => String(note.id), keeps: () => true, order: (a, b) => a.id - b.id },
};

export const RETRY_MS = 3000; // the pause before a new stream when the server closed one

export class Live {
  private state: LiveState = {
    sessions: null,
    agents: {},
    messages: {},
    events: {},
    gates: {},
    runs: {},
    notes: {},
    waiting: null,
    kits: null,
    kitChanges: 0,
    link: "connecting",
    problem: null,
  };
  // The Kits page's lists: how many pages watch them, and per list whether a load runs and
  // whether another one follows it for the changes that came meanwhile.
  private kitsWatchers = 0;
  private kitLoads: Record<KitList, { loading: boolean; again: boolean }> = {
    installed: { loading: false, again: false },
    marketplaces: { loading: false, again: false },
    available: { loading: false, again: false },
  };
  // What waits for the human: how many pages watch it, whether a load runs, and whether
  // another one follows it for the changes that came meanwhile.
  private waitingWatchers = 0;
  private waitingLoading = false;
  private waitingAgain = false;
  private listeners = new Set<() => void>();
  private source: EventSource | null = null;
  private retry: ReturnType<typeof setTimeout> | undefined;
  private lastId = ""; // the latest journal id the stream sent; derived changes have none
  private loading: Change[] | null = null; // changes that came while a load runs
  // Per list, session -> pages that watch it, and the changes that came while it loads.
  private watched: Record<ListName, Map<string, number>> = {
    agents: new Map(),
    events: new Map(),
    gates: new Map(),
    runs: new Map(),
    notes: new Map(),
  };
  private listLoads: Record<ListName, Map<string, Change[]>> = {
    agents: new Map(),
    events: new Map(),
    gates: new Map(),
    runs: new Map(),
    notes: new Map(),
  };
  private windows = new Map<string, Watched>(); // by session and windowKey

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
      // After a gap the kits may have changed unseen; the first reset is no change.
      if (this.lastId) this.set({ kitChanges: this.state.kitChanges + 1 });
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

  // A page that shows the session's agents, messages, run events, gates, runs or notes, what
  // waits for the human, or the kits: they load now and follow the feed until the last page
  // that watches them lets go (the returned function).
  watch(list: "waiting" | "kits"): () => void;
  watch(list: ListName, session: string): () => void;
  watch(list: ListName | "waiting" | "kits", session = ""): () => void {
    if (list === "waiting") return this.watchWaiting();
    if (list === "kits") return this.watchKits();
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

  // A page that shows a window of the session's messages: its latest page loads now and it
  // follows the feed until the last page that watches it lets go (the returned function).
  watchMessages(session: string, spec: MessageSpec): () => void {
    const key = windowKey(spec);
    const id = `${session}\n${key}`;
    let watched = this.windows.get(id);
    if (!watched) {
      watched = { session, spec, key, watchers: 0, loads: 0, loadingEarlier: false, pending: [] };
      this.windows.set(id, watched);
      this.setWindow(watched, null);
      this.loadLatest(watched);
    }
    watched.watchers += 1;
    const mine = watched;
    return () => {
      mine.watchers -= 1;
      if (mine.watchers > 0 || this.windows.get(id) !== mine) return;
      this.windows.delete(id);
      const { [key]: _, ...others } = this.state.messages[session] ?? {};
      const { [session]: __, ...sessions } = this.state.messages;
      this.set({ messages: Object.keys(others).length ? { ...sessions, [session]: others } : sessions });
    };
  }

  // The window as the store has it now: undefined when no page watches it.
  messagesOf(session: string, spec: MessageSpec): WindowLoaded | undefined {
    return messageWindow(this.state, session, spec);
  }

  // The page of the window's messages before its first one; one load at a time.
  loadEarlier(session: string, spec: MessageSpec) {
    const watched = this.windows.get(`${session}\n${windowKey(spec)}`);
    const now = watched && this.windowOf(watched);
    if (!watched || !now || !("items" in now) || !now.earlier || watched.loadingEarlier) return;
    watched.loadingEarlier = true;
    this.setWindow(watched, { ...now, loadingEarlier: true, problem: null });
    const before = now.items[0]?.id;
    this.loadInto(watched, { ...filterOf(spec), limit: spec.limit, before }, (loaded, got) => {
      watched.loadingEarlier = false;
      if (!loaded || !("items" in loaded)) return loaded;
      if ("error" in got) return { ...loaded, loadingEarlier: false, problem: got.error };
      return { ...prepend(loaded, got, null), loadingEarlier: false, problem: null };
    });
  }

  // The window's messages from a message (`id`) or a time (`at`, a gate's or a run event's)
  // on, in one load, when it lies before the window: a link leads there.
  loadUpTo(session: string, spec: MessageSpec, target: { id: number } | { at: string }): Promise<void> {
    const watched = this.windows.get(`${session}\n${windowKey(spec)}`);
    const now = watched && this.windowOf(watched);
    if (!watched || !now || !("items" in now) || !now.earlier) return Promise.resolve();
    const first = now.items[0];
    if (first && ("id" in target ? target.id >= first.id : Date.parse(target.at) >= Date.parse(first.created_at))) {
      return Promise.resolve();
    }
    const range = "id" in target ? { after: target.id - 1 } : { since: target.at };
    const since = "at" in target ? target.at : null;
    return this.loadInto(watched, { ...filterOf(spec), ...range, before: first?.id }, (loaded, got) => {
      if (!loaded || !("items" in loaded)) return loaded;
      if ("error" in got) return { ...loaded, problem: got.error };
      return { ...loaded, ...prepend(loaded, got, since), problem: null };
    });
  }

  private windowOf(watched: Watched): WindowLoaded {
    return this.state.messages[watched.session]?.[watched.key] ?? null;
  }

  private setWindow(watched: Watched, loaded: WindowLoaded) {
    const session = this.state.messages[watched.session] ?? {};
    this.set({ messages: { ...this.state.messages, [watched.session]: { ...session, [watched.key]: loaded } } });
  }

  // The latest page, when the window opens or after a reset that finds it empty.
  private loadLatest(watched: Watched) {
    void this.loadInto(watched, { ...filterOf(watched.spec), limit: watched.spec.limit }, (_, got) =>
      "error" in got ? got : { ...got, from: fromOf(got, null), loadingEarlier: false, problem: null },
    );
  }

  // One load into the window: the changes that come while any load runs wait and are
  // applied after the last one, as a whole list's are (loadList).
  private loadInto(
    watched: Watched,
    query: MessageQuery,
    merge: (loaded: WindowLoaded, got: MessagePage | { error: string }) => WindowLoaded,
  ): Promise<void> {
    watched.loads += 1;
    return getMessages(watched.session, query)
      .then(
        (page) => page,
        (error: unknown) => ({ error: message(error) }),
      )
      .then((got) => {
        if (this.windows.get(`${watched.session}\n${watched.key}`) !== watched) return; // let go
        watched.loads -= 1;
        this.setWindow(watched, merge(this.windowOf(watched), got));
        if (watched.loads > 0) return;
        const changes = watched.pending;
        watched.pending = [];
        changes.forEach((change) => this.applyWindow(watched, change));
      });
  }

  // The feed's change of a message: one the window's filter takes is added after its last,
  // put in its place inside it, and left out before it while earlier ones are not loaded;
  // one it does not take, or a message gone, leaves it.
  private applyWindow(watched: Watched, change: Change) {
    if (watched.loads > 0) {
      watched.pending.push(change);
      return;
    }
    const now = this.windowOf(watched);
    if (!now || !("items" in now)) return;
    const item = change.item as MessageInfo | null;
    const others = now.items.filter((one) => String(one.id) !== change.key);
    if (item === null || !matches(item, filterOf(watched.spec))) {
      if (others.length !== now.items.length) this.setWindow(watched, { ...now, items: others });
      return;
    }
    const first = now.items[0];
    if (now.earlier && first && item.id < first.id) return;
    this.setWindow(watched, { ...now, items: [...others, item].sort((a, b) => a.id - b.id) });
  }

  private watchWaiting(): () => void {
    this.waitingWatchers += 1;
    if (this.waitingWatchers === 1) this.loadWaiting();
    return () => {
      this.waitingWatchers -= 1;
      if (this.waitingWatchers === 0) this.set({ waiting: null });
    };
  }

  // What waits has no item of its own in the feed: it is loaded again whole, on reset and
  // on each change that can change it, since a count would miss one item in place of
  // another. One load at a time; the changes that come meanwhile make one more.
  private loadWaiting() {
    if (this.waitingWatchers === 0) return;
    if (this.waitingLoading) {
      this.waitingAgain = true;
      return;
    }
    this.waitingLoading = true;
    getWaiting()
      .then(
        (items) => ({ items }),
        (error: unknown) => ({ error: message(error) }),
      )
      .then((loaded) => {
        this.waitingLoading = false;
        if (this.waitingWatchers > 0) this.set({ waiting: loaded });
        if (this.waitingAgain) {
          this.waitingAgain = false;
          this.loadWaiting();
        }
      });
  }

  private watchKits(): () => void {
    this.kitsWatchers += 1;
    if (this.kitsWatchers === 1) {
      this.set({ kits: { installed: null, marketplaces: null, available: null } });
      (Object.keys(KIT_LOADS) as KitList[]).forEach((list) => this.loadKits(list));
    }
    return () => {
      this.kitsWatchers -= 1;
      if (this.kitsWatchers === 0) this.set({ kits: null });
    };
  }

  // One of the Kits page's lists, whole: one load at a time, as what waits (loadWaiting).
  private loadKits(list: KitList) {
    if (this.kitsWatchers === 0) return;
    const load = this.kitLoads[list];
    if (load.loading) {
      load.again = true;
      return;
    }
    load.loading = true;
    KIT_LOADS[list]()
      .then(
        (items: unknown[]) => ({ items }),
        (error: unknown) => ({ error: message(error) }),
      )
      .then((loaded) => {
        load.loading = false;
        if (this.state.kits !== null) this.set({ kits: { ...this.state.kits, [list]: loaded } });
        if (load.again) {
          load.again = false;
          this.loadKits(list);
        }
      });
  }

  // A change of an installed kit or a marketplace: its item takes its place (a kit by its
  // name, never a built-in one: they are not in the journal); during a load the list loads
  // again after it. What is available follows both.
  private applyKits(change: Change) {
    const kits = this.state.kits;
    if (kits === null) return;
    const list: KitList = change.kind === "kits" ? "installed" : "marketplaces";
    const loaded = kits[list];
    if (this.kitLoads[list].loading) this.kitLoads[list].again = true;
    else if (loaded !== null && "items" in loaded) {
      if (list === "installed") {
        const others = (loaded.items as InstalledKitInfo[]).filter(
          (one) => one.kind === "built-in" || one.name !== change.key,
        );
        const item = change.item as InstalledKitInfo | null;
        const items = (item === null ? others : [...others, item]).sort(kitOrder);
        this.set({ kits: { ...kits, installed: { items } } });
      } else {
        const others = (loaded.items as MarketplaceInfo[]).filter((one) => one.name !== change.key);
        const item = change.item as MarketplaceInfo | null;
        const items = (item === null ? others : [...others, item]).sort((a, b) => a.name.localeCompare(b.name));
        this.set({ kits: { ...kits, marketplaces: { items } } });
      }
    }
    this.loadKits("available");
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
    this.windows.forEach((watched) => this.reloadWindow(watched));
    this.loadWaiting();
    (Object.keys(KIT_LOADS) as KitList[]).forEach((list) => this.loadKits(list));
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

  // After a gap in the feed: the window again from its first message to the latest, so it
  // keeps what the human scrolled back to; an empty one as when it opened.
  private reloadWindow(watched: Watched) {
    const now = this.windowOf(watched);
    const first = now && "items" in now ? now.items[0] : undefined;
    if (!first) {
      this.loadLatest(watched);
      return;
    }
    const since = now && "items" in now ? now.from : null;
    void this.loadInto(watched, { ...filterOf(watched.spec), after: first.id - 1 }, (_, got) =>
      "error" in got ? got : { ...got, from: fromOf(got, since), loadingEarlier: watched.loadingEarlier, problem: null },
    );
  }

  private apply(change: Change) {
    const list = change.kind as ListName;
    if (list in this.watched && this.watched[list].has(change.session)) this.applyList(list, change);
    if (change.kind === "messages") {
      this.windows.forEach((watched) => {
        if (watched.session === change.session) this.applyWindow(watched, change);
      });
    }
    if (WAITING_KINDS.has(change.kind)) this.loadWaiting();
    if (change.kind === "kits" || change.kind === "marketplaces") this.applyKits(change);
    if (change.kind === "kits") this.set({ kitChanges: this.state.kitChanges + 1 });
    const loaded = this.state.sessions;
    if (change.kind !== "sessions" || loaded === null || "error" in loaded) return;
    const item = change.item as SessionInfo | null;
    const before = loaded.sessions.find((one) => one.name === change.session);
    if ((before !== undefined && isLive(before)) !== (item !== null && isLive(item))) this.loadWaiting();
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

// An earlier page in front of the window: its items take the place of the same ones there.
// `since`: the time the page was asked from, when it was.
function prepend(
  window: MessageWindow,
  page: MessagePage,
  since: string | null,
): Pick<MessageWindow, "items" | "earlier" | "from"> {
  const fresh = new Set(page.items.map((one) => one.id));
  const items = [...page.items, ...window.items.filter((one) => !fresh.has(one.id))].sort((a, b) => a.id - b.id);
  return { items, earlier: page.earlier, from: fromOf({ items, earlier: page.earlier }, since ?? window.from) };
}

// The time from which a window holds every message of its kind: its first message's, or
// an earlier time it was loaded from; null when nothing comes before it.
function fromOf(page: MessagePage, since: string | null): string | null {
  if (!page.earlier) return null;
  const first = page.items[0]?.created_at ?? null;
  if (since === null || first === null) return first ?? since;
  return Date.parse(since) < Date.parse(first) ? since : first;
}

// A window of the session's messages as the store has it: undefined when no page watches it.
export function messageWindow(state: LiveState, session: string, spec: MessageSpec): WindowLoaded | undefined {
  return state.messages[session]?.[windowKey(spec)];
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
