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

// The terminal panel on the right of a session page: its width, and whether it is collapsed
// to a strip. Collapsed by default on a narrow window (≤ 900 px, where the columns stack);
// a value stored before it could collapse is open.
const PANEL = "lado.terminals";
export const PANEL_WIDTH: Bounds = { initial: 480, min: 280, max: 1200 };

export type PanelPrefs = { width: number; collapsed: boolean };

export function storedPanel(): PanelPrefs {
  const stored = readJson(PANEL);
  const collapsed =
    stored === null ? (window.matchMedia?.("(max-width: 900px)").matches ?? false) : stored.collapsed === true;
  return { width: widthIn(stored?.width, PANEL_WIDTH), collapsed };
}

export function storePanel(panel: PanelPrefs): void {
  write(PANEL, JSON.stringify(panel));
}

// The session list on the left of the Sessions page: its width.
const SESSIONS_LIST = "lado.sessionsList";
export const SESSIONS_WIDTH: Bounds = { initial: 260, min: 200, max: 480 };

export const storedSessionsList = (): { width: number } => ({
  width: widthIn(readJson(SESSIONS_LIST)?.width, SESSIONS_WIDTH),
});

export function storeSessionsList(list: { width: number }): void {
  write(SESSIONS_LIST, JSON.stringify(list));
}

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

// Whether the Flows tab's list shows its ended runs (folded by default).
const FLOWS_ENDED = "lado.flowsEnded";

export const storedFlowsEndedOpen = (): boolean => read(FLOWS_ENDED) === "open";

export function storeFlowsEndedOpen(open: boolean): void {
  write(FLOWS_ENDED, open ? "open" : "folded");
}

// The Kits page's source chip: "all", "git", "folder", "built-in" or "marketplace:<name>".
const KITS_SOURCE = "lado.kitsSource";

export const storedKitsSource = (): string => read(KITS_SOURCE) ?? "all";

export function storeKitsSource(source: string): void {
  write(KITS_SOURCE, source);
}

// Whether the session list shows its stopped sessions (folded by default).
const STOPPED = "lado.stoppedSessions";

export const storedStoppedOpen = (): boolean => read(STOPPED) === "open";

export function storeStoppedOpen(open: boolean): void {
  write(STOPPED, open ? "open" : "folded");
}
