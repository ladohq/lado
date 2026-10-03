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

// The terminal panel of a session page: collapsed or not, and its height in pixels.
const PANEL = "lado.terminals";
export const PANEL_HEIGHT = { initial: 320, min: 160, max: 900 };

export type PanelPrefs = { collapsed: boolean; height: number };

export function storedPanel(): PanelPrefs {
  try {
    const found = JSON.parse(read(PANEL) ?? "{}");
    const height = Number(found.height);
    return {
      collapsed: found.collapsed === true,
      height: height >= PANEL_HEIGHT.min && height <= PANEL_HEIGHT.max ? height : PANEL_HEIGHT.initial,
    };
  } catch {
    return { collapsed: false, height: PANEL_HEIGHT.initial };
  }
}

export function storePanel(panel: PanelPrefs): void {
  write(PANEL, JSON.stringify(panel));
}
