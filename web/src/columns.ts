// What a session's page shows beside the chat (docs/design/ui.md, Structure): one rule, from
// the room there is and what the human chose, with no state of its own. A column folded for
// room comes back because the room did, to the choice that stayed stored (prefs.ts).
import { PANEL_WIDTH, type Column } from "./prefs";

export const CHAT_MIN = 420; // the chat's least width above 900 px; --chat-min in tokens.css
export const STRIP = 32; // the terminals folded to a strip; --strip-w in tokens.css
export const LIST_STRIP = 48; // the list folded to a strip

// The terminals' width with none set on their edge: this much of the session's area, the page
// beside the list.
const SHARE = 0.4;
const PANEL_DEFAULT = { min: 360, max: 640 };

export type ColumnsInput = {
  room: number; // the page beside the rail
  list: { width: number; collapsed: boolean };
  panel: { width: number | null; collapsed: boolean; chosen: boolean };
  last: Column | null; // the column the human opened last
  control: boolean; // a terminal of the panel is in control
};

export type Columns = { listFolded: boolean; panelFolded: boolean; panelWidth: number };

// Whether the human opened the terminals (a terminal in control counts), and whether they stay
// when something must fold: not after the human opened a list that is still wanted. Taking
// control counts as opening the panel last (Sessions.tsx).
const opened = ({ panel, control }: ColumnsInput) => !panel.collapsed && (panel.chosen || control);
const panelStays = (input: ColumnsInput) => opened(input) && (input.last !== "list" || input.list.collapsed);

// The widest the list may be dragged: the chat keeps its room beside terminals that stay, and
// past that the rule would fold the list under the pointer. Other terminals fold for it.
export function listMax(input: ColumnsInput): number {
  const beside = panelStays(input) ? (input.panel.width ?? PANEL_DEFAULT.min) : STRIP;
  return input.room - beside - CHAT_MIN;
}

export function fitColumns(input: ColumnsInput): Columns {
  const { room, list, panel } = input;
  const listAt = (open: boolean) => (open ? list.width : LIST_STRIP);
  const widthAt = (open: boolean) => {
    const area = room - listAt(open);
    return panel.width ?? Math.min(PANEL_DEFAULT.max, Math.max(PANEL_DEFAULT.min, Math.round(area * SHARE)));
  };
  const shown = (listOpen: boolean, panelOpen: boolean, panelWidth = widthAt(listOpen)): Columns & { chat: number } => ({
    listFolded: !listOpen,
    panelFolded: !panelOpen,
    panelWidth,
    chat: room - listAt(listOpen) - (panelOpen ? panelWidth : STRIP),
  });
  const listOpen = !list.collapsed;
  const panelOpen = !panel.collapsed;
  // The ways to show the columns, the best first: the first that leaves the chat its room.
  // Only terminals the human opened narrow, and only beside the folded list; terminals nobody
  // opened never stay beside a list that folded.
  const narrowed = room - LIST_STRIP - CHAT_MIN;
  const tries = panelStays(input)
    ? [
        shown(listOpen, true),
        shown(false, true),
        ...(narrowed >= PANEL_WIDTH.min ? [shown(false, true, Math.min(narrowed, widthAt(false)))] : []),
        shown(listOpen, false),
      ]
    : [shown(listOpen, panelOpen), shown(listOpen, false), ...(opened(input) ? [shown(false, true)] : [])];
  const { chat: _, ...best } = tries.find(({ chat }) => chat >= CHAT_MIN) ?? shown(false, false);
  return best;
}
