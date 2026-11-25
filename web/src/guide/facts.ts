// What the first-run guide knows of the Settings pages (docs/design/ui.md, First-run guide):
// Agent CLIs, Model servers and Git servers publish what they loaded, when they load or change
// it, and the guide listens; it makes no request of its own there; so does the statistics
// banner, whose answer the welcome waits for. In the main bundle, small,
// outside the guide's lazy engine. Also Help → Getting started's request to restart the guide.

export type CliFact = { name: string; ready: boolean; installed: boolean; loggedIn: boolean };

export type Facts = {
  logins?: { rows: CliFact[]; checking: boolean }; // Agent CLIs' rows
  models?: number; // the models of saved model servers ticked for an agent CLI (Model servers)
  author?: boolean; // LADO's or git's own author signs commits (Git servers)
  statisticsAsked?: boolean; // the statistics banner still asks (Telemetry.tsx)
};

let current: Facts = {};
const listeners = new Set<() => void>();
const restarts = new Set<() => void>();

// A page's newest data of one part; the guide takes it over the server's facts.
export function publish<K extends keyof Facts>(part: K, value: Facts[K]): void {
  current = { ...current, [part]: value };
  for (const listener of [...listeners]) listener();
}

export function currentFacts(): Facts {
  return current;
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

// Help → Getting started: the guide's mount restarts it (guide/mount.tsx).
export function restartGuide(): void {
  for (const listener of [...restarts]) listener();
}

export function onRestart(listener: () => void): () => void {
  restarts.add(listener);
  return () => restarts.delete(listener);
}

// A new page load's state (tests).
export function resetFacts(): void {
  current = {};
  listeners.clear();
  restarts.clear();
}
