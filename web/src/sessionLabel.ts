// How the UI names a session (docs/design/ui.md, Session title): by its title, the human's
// label, else by its name, which stays its identifier (the address, the CLI, its branches).
// The one place that decides it; where a title shows, the name is shown beside it.
import type { SessionInfo } from "./api";
import type { Loaded } from "./live";

export const label = (session: Pick<SessionInfo, "name" | "title">): string => session.title ?? session.name;

// For a place that holds only a session's name (Needs you, a notification): its label from
// the live list, else the name.
export function labelOf(name: string, loaded: Loaded): string {
  const found = loaded && "sessions" in loaded ? loaded.sessions.find((one) => one.name === name) : undefined;
  return found ? label(found) : name;
}

// A title's length as the server counts it (runtime.MAX_TITLE): characters, not UTF-16
// units, after the trim.
export const titleLength = (text: string): number => [...text.trim()].length;
