// What the UI remembers per browser: the theme, the rail, the columns of a session page and
// a few choices. Browser storage may be missing or refuse (private windows, blocked site data); then the defaults
// hold and nothing breaks.

export type Theme = "system" | "light" | "dark";

const THEME = "lado.theme";
const RAIL = "lado.rail";

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Not remembered: the choice holds until the page is closed.
  }
}

// The server version this tab reloaded for (the version banner's Reload), kept for the
// tab only: after the reload, a banner for the same version says to restart the server.
const RELOADED_FOR = "lado.reloadedFor";

export function reloadedFor(): string | null {
  try {
    return sessionStorage.getItem(RELOADED_FOR);
  } catch {
    return null;
  }
}

export function storeReloadedFor(version: string | null): void {
  try {
    if (version === null) sessionStorage.removeItem(RELOADED_FOR);
    else sessionStorage.setItem(RELOADED_FOR, version);
  } catch {
    // Not remembered: after the reload the banner offers a reload again.
  }
}

export function storedTheme(): Theme {
  const theme = read(THEME);
  return theme === "light" || theme === "dark" ? theme : "system";
}

// "system" leaves the root without data-theme: tokens.css follows prefers-color-scheme.
export function applyTheme(theme: Theme): void {
  if (theme === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
}

export function chooseTheme(theme: Theme): void {
  applyTheme(theme);
  write(THEME, theme);
}

// Collapsed by default on a narrow window (< 900 px).
export function storedRailCollapsed(): boolean {
  const rail = read(RAIL);
  if (rail !== null) return rail === "collapsed";
  return window.matchMedia?.("(max-width: 899px)").matches ?? false;
}

export function storeRailCollapsed(collapsed: boolean): void {
  write(RAIL, collapsed ? "collapsed" : "expanded");
}

// A column's width in pixels: where it starts, and how narrow and wide it may be dragged.
export type Bounds = { initial: number; min: number; max: number };

// What is stored under `key` as JSON, or null when nothing is (or it is not JSON).
function readJson(key: string): Record<string, unknown> | null {
  try {
    const value = JSON.parse(read(key) ?? "null");
    return value !== null && typeof value === "object" ? value : null;
  } catch {
    return null;
  }
}

const widthIn = (value: unknown, bounds: Bounds) => {
  const width = Number(value);
  return width >= bounds.min && width <= bounds.max ? width : bounds.initial;
};

// A column of a session page that collapses to a strip: its width, and whether it is
// collapsed. Collapsed by default on a narrow window (≤ 900 px, where the columns stack); a
// value stored before it could collapse is open.
export type ColumnPrefs = { width: number; collapsed: boolean };

export function storedColumn(key: string, bounds: Bounds): ColumnPrefs {
  const stored = readJson(key);
  const collapsed =
    stored === null ? (window.matchMedia?.("(max-width: 900px)").matches ?? false) : stored.collapsed === true;
  return { width: widthIn(stored?.width, bounds), collapsed };
}

export function storeColumn(key: string, column: ColumnPrefs): void {
  write(key, JSON.stringify(column));
}

// The terminal panel on the right of a session page.
const PANEL = "lado.terminals";
export const PANEL_WIDTH: Bounds = { initial: 480, min: 280, max: 1200 };

export const storedPanel = (): ColumnPrefs => storedColumn(PANEL, PANEL_WIDTH);

export const storePanel = (panel: ColumnPrefs): void => storeColumn(PANEL, panel);

// The session list on the left of the Sessions page.
const SESSIONS_LIST = "lado.sessionsList";
export const SESSIONS_WIDTH: Bounds = { initial: 260, min: 200, max: 480 };

export const storedSessionsList = (): ColumnPrefs => storedColumn(SESSIONS_LIST, SESSIONS_WIDTH);

export const storeSessionsList = (list: ColumnPrefs): void => storeColumn(SESSIONS_LIST, list);

// Whether Take control asks first (until the human says not to ask again).
const ASK_CONTROL = "lado.askControl";

export const storedAskControl = (): boolean => read(ASK_CONTROL) !== "never";

export function storeAskControl(ask: boolean): void {
  write(ASK_CONTROL, ask ? "ask" : "never");
}

// Whether the Activity feed shows the agents' messages to each other (off by default).
const AGENT_MESSAGES = "lado.agentMessages";

export const storedAgentMessages = (): boolean => read(AGENT_MESSAGES) === "shown";

export function storeAgentMessages(shown: boolean): void {
  write(AGENT_MESSAGES, shown ? "shown" : "hidden");
}

// Whether the browser notifies when something new waits for the human (off by default;
// it also needs the browser's permission).
const NOTIFICATIONS = "lado.notifications";

export const storedNotifications = (): boolean => read(NOTIFICATIONS) === "on";

export function storeNotifications(on: boolean): void {
  write(NOTIFICATIONS, on ? "on" : "off");
}

// The order of a run's history on its page in the Flows tab (the newest first by default).
export type FlowsOrder = "newest" | "oldest";

const FLOWS_ORDER = "lado.flowsOrder";

export const storedFlowsOrder = (): FlowsOrder => (read(FLOWS_ORDER) === "oldest" ? "oldest" : "newest");

export function storeFlowsOrder(order: FlowsOrder): void {
  write(FLOWS_ORDER, order);
}

// The Kits page's source chip: "all", "git", "folder", "built-in" or "marketplace:<name>".
const KITS_SOURCE = "lado.kitsSource";

export const storedKitsSource = (): string => read(KITS_SOURCE) ?? "all";

export function storeKitsSource(source: string): void {
  write(KITS_SOURCE, source);
}

// Each group of the session list open or folded, by the group's id: Needs you and Running
// open, Stopped folded by default. An older LADO kept only Stopped's, under STOPPED: it is
// where Stopped starts until the groups are stored, and never read after that.
export type SessionGroup = "needs-you" | "running" | "stopped";
export type SessionGroups = Record<SessionGroup, "open" | "folded">;

const SESSION_GROUPS = "lado.sessionGroups";
const STOPPED = "lado.stoppedSessions";

export function storedSessionGroups(): SessionGroups {
  const stored = readJson(SESSION_GROUPS);
  const first = stored === null && read(STOPPED) === "open" ? "open" : "folded";
  const fold = (group: SessionGroup, fallback: "open" | "folded") => {
    const value = stored?.[group];
    return value === "open" || value === "folded" ? value : fallback;
  };
  return { "needs-you": fold("needs-you", "open"), running: fold("running", "open"), stopped: fold("stopped", first) };
}

export function storeSessionGroups(groups: SessionGroups): void {
  write(SESSION_GROUPS, JSON.stringify(groups));
}
