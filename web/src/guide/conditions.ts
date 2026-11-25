// The first-run guide's named conditions (docs/design/ui.md, First-run guide): what a hint's
// `when` names in hints.ts, over the guide's record, the facts the Settings pages published
// (facts.ts, newer than the server's), the route and the `data-guide` markers on screen. The
// markers are the whole interface to the components: a form or window is open while a visible
// element carries its marker. Part of the lazy engine.
import type { GuideInfo } from "../api";
import type { Facts } from "./facts";
import { GUIDED_CLIS, type Cond, type Hint, type Part } from "./hints";

export type Context = {
  info: GuideInfo;
  facts: Facts;
  route: string;
  phone: boolean;
  passed: ReadonlySet<string>; // the rows passed in this page load (I have neither, a closed window)
  noneOfThese: boolean; // the "none of these" card was asked for
  next?: Hint; // the step a phone's `precede` hint stands before
};

// The first visible element that carries `marker`; a hidden one (an ancestor with `hidden`,
// display: none) does not count.
export function findMarker(marker: string, root: ParentNode = document): HTMLElement | null {
  for (const element of root.querySelectorAll<HTMLElement>(`[data-guide="${marker}"]`)) {
    if (visible(element)) return element;
  }
  return null;
}

export function visible(element: HTMLElement): boolean {
  if (element.closest("[hidden]")) return false;
  return typeof element.checkVisibility === "function" ? element.checkVisibility() : true;
}

// A guided CLI's row is left to log in: installed (or not read yet), not logged in, not passed.
function toLogIn(context: Context, cli: string): boolean {
  if (context.passed.has(cli)) return false;
  const row = context.facts.logins?.rows.find((one) => one.name === cli);
  if (!row || !row.ready) return true;
  return row.installed && !row.loggedIn;
}

// An agent CLI has a model to work on: it is logged in, or a model of a saved server is ticked
// for it (a server saved with no model ticked is none).
export function modelConnected(context: Context): boolean {
  const { logins, models } = context.facts;
  if (logins?.rows.some((row) => row.loggedIn)) return true;
  if (models !== undefined && models > 0) return true;
  return context.info.facts?.model === true;
}

export function authorInEffect(context: Context): boolean {
  return context.facts.author ?? context.info.facts?.author ?? false;
}

export function partDone(context: Context, part: Part): boolean {
  if (part === "model") return modelConnected(context);
  if (part === "author") return authorInEffect(context);
  return false; // Start working: completes the guide
}

const atRoute = (route: string, path: string) => route === path || route.startsWith(`${path}/`);

const sheetOf = (cli: string) =>
  [...document.querySelectorAll<HTMLElement>('[data-guide="login-sheet"]')].find(
    (sheet) => visible(sheet) && sheet.dataset.guideCli === cli,
  ) ?? null;

export const CONDITIONS: Record<string, (context: Context, ...args: string[]) => boolean> = {
  telemetryAnswered: (context) => !(context.facts.statisticsAsked ?? context.info.telemetry_asked),
  modelConnected,
  authorInEffect,
  phone: (context) => context.phone,
  route: (context, path) => atRoute(context.route, path),
  // A section page of Settings, not its phone list.
  settingsSection: (context) => /^\/settings\/[^/]+/.test(context.route),
  marker: (_, name) => findMarker(name) !== null,
  // A window of the app is open: a modal <dialog>, or a dialog of the app's own.
  windowOpen: () =>
    document.querySelector("dialog[open]") !== null ||
    [...document.querySelectorAll<HTMLElement>('[role="dialog"][aria-modal="true"]')].some(
      (one) => !one.closest(".gd-layer") && visible(one),
    ),
  drawerOpen: () => document.querySelector(".rail[data-open]") !== null,
  // The step a `precede` hint stands before has its target on screen.
  nextVisible: (context) => (context.next?.target ? findMarker(context.next.target) !== null : false),
  // `*`: any CLI the guide has texts for.
  cliToLogIn: (context, cli) => (cli === "*" ? GUIDED_CLIS : [cli]).some((one) => toLogIn(context, one)),
  loginWindow: (_, cli) => sheetOf(cli) !== null,
  loginChoice: (_, cli, id) => sheetOf(cli)?.querySelector(`[data-guide-choice="${id}"]`) != null,
  loginPicked: (_, cli) => sheetOf(cli)?.dataset.guidePicked !== undefined,
  loginRefused: () => findMarker("login-refusal") !== null,
  noneOfThese: (context) => context.noneOfThese,
};

// Whether all of `when` holds; a name with "!" first is its negation.
export function holds(when: Cond[], context: Context): boolean {
  return when.every(([name, ...args]) => {
    const negated = name.startsWith("!");
    const test = CONDITIONS[negated ? name.slice(1) : name];
    if (!test) throw new Error(`the guide knows no condition ${name}`);
    return test(context, ...args) !== negated;
  });
}
