// What a session's page shows beside the chat (docs/design/ui.md, Structure): one rule, from
// the room there is and what the human chose, with no state of its own. A column folded for
// room comes back because the room did, to the choice that stayed stored (prefs.ts).
import { PANEL_WIDTH } from "./prefs";

export const CHAT_MIN = 420; // the chat's least width above 900 px; --chat-min in tokens.css
export const STRIP = 32; // the terminals folded to a strip; --strip-w in tokens.css
export const LIST_STRIP = 48; // the list folded to a strip

// The terminals' width with none set on their edge: this much of the session's area, the page
// beside the list.
const SHARE = 0.4;
const PANEL_DEFAULT = { min: 360, max: 640 };

export type Column = "list" | "panel";

export type ColumnsInput = {
  room: number; // the page beside the rail
  list: { width: number; collapsed: boolean };
  panel: { width: number | null; collapsed: boolean; chosen: boolean };
  last: Column | null; // the column the human opened last, while the page lives
  control: boolean; // a terminal of the panel is in control
};

export type Columns = { listFolded: boolean; panelFolded: boolean; panelWidth: number };

export function fitColumns({ room, list, panel, last, control }: ColumnsInput): Columns {
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
  const opened = panelOpen && (panel.chosen || control);
  const keepPanel = opened && (last !== "list" || list.collapsed);
  // The ways to show the columns, the best first: the first that leaves the chat its room.
  // Only terminals the human opened narrow, and only beside the folded list.
  const narrowed = room - LIST_STRIP - CHAT_MIN;
  const tries = keepPanel
    ? [
        shown(listOpen, true),
        shown(false, true),
        ...(narrowed >= PANEL_WIDTH.min ? [shown(false, true, Math.min(narrowed, widthAt(false)))] : []),
        shown(listOpen, false),
      ]
    : [shown(listOpen, panelOpen), shown(listOpen, false), shown(false, panelOpen)];
  const { chat: _, ...best } = tries.find(({ chat }) => chat >= CHAT_MIN) ?? shown(false, false);
  return best;
}
