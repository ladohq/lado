// What the UI remembers per browser: the theme and whether the rail is collapsed. Browser
// storage may be missing or refuse (private windows, blocked site data); then the defaults
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

// The terminal panel on the right of a session page: its width in pixels.
const PANEL = "lado.terminals";
export const PANEL_WIDTH = { initial: 480, min: 280, max: 1200 };

export type PanelPrefs = { width: number };

export function storedPanel(): PanelPrefs {
  try {
    const width = Number(JSON.parse(read(PANEL) ?? "{}").width);
    return { width: width >= PANEL_WIDTH.min && width <= PANEL_WIDTH.max ? width : PANEL_WIDTH.initial };
  } catch {
    return { width: PANEL_WIDTH.initial };
  }
}

export function storePanel(panel: PanelPrefs): void {
  write(PANEL, JSON.stringify(panel));
}

// Whether the Activity feed shows the agents' messages to each other (off by default).
const AGENT_MESSAGES = "lado.agentMessages";

export const storedAgentMessages = (): boolean => read(AGENT_MESSAGES) === "shown";

export function storeAgentMessages(shown: boolean): void {
  write(AGENT_MESSAGES, shown ? "shown" : "hidden");
}

// Whether the session list shows its stopped sessions (folded by default).
const STOPPED = "lado.stoppedSessions";

export const storedStoppedOpen = (): boolean => read(STOPPED) === "open";

export function storeStoppedOpen(open: boolean): void {
  write(STOPPED, open ? "open" : "folded");
}
