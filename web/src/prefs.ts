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
