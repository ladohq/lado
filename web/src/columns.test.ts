// The rule of a session page's columns (docs/design/ui.md, Structure): `room` is the page
// beside the rail, as it is laid out at each window's width with a folded rail (60 px).
import { expect, test } from "vitest";

import { CHAT_MIN, fitColumns, LIST_STRIP, listMax, STRIP, type ColumnsInput } from "./columns";

const beside = (window: number, rail = 60) => window - rail;

const NOTHING_STORED: Omit<ColumnsInput, "room"> = {
  list: { width: 260, collapsed: false },
  panel: { width: null, collapsed: false, chosen: false },
  last: null,
  control: false,
};
const OPENED = { width: null, collapsed: false, chosen: true };

const fit = (room: number, change: Partial<ColumnsInput> = {}) => fitColumns({ room, ...NOTHING_STORED, ...change });

const chat = (room: number, { listFolded, panelFolded, panelWidth }: ReturnType<typeof fitColumns>, list = 260) =>
  room - (listFolded ? LIST_STRIP : list) - (panelFolded ? STRIP : panelWidth);

test.each([
  [1440, 448, 672],
  [1280, 384, 576],
  [1101, 360, 421],
])("nothing stored at %i px: the terminals take 40 %% of the session's area", (window, panel, left) => {
  const shown = fit(beside(window));
  expect(shown).toEqual({ listFolded: false, panelFolded: false, panelWidth: panel });
  expect(chat(beside(window), shown)).toBe(left);
});

test("a large window holds the terminals at 640 px", () => {
  expect(fit(2400).panelWidth).toBe(640);
});

test("terminals nobody opened fold first", () => {
  const shown = fit(beside(1024));
  expect(shown).toMatchObject({ listFolded: false, panelFolded: true });
  expect(chat(beside(1024), shown)).toBe(672);
});

test("terminals the human opened stay and the list folds", () => {
  const shown = fit(beside(1024), { panel: OPENED });
  expect(shown).toEqual({ listFolded: true, panelFolded: false, panelWidth: 366 });
  expect(chat(beside(1024), shown)).toBe(550);
});

test("a terminal in control counts as opened by the human", () => {
  expect(fit(beside(1024), { control: true })).toMatchObject({ listFolded: true, panelFolded: false });
});

test("taking control opens the panel last; the list opened after it folds the panel", () => {
  expect(fit(beside(1024), { control: true, last: "panel" })).toMatchObject({ listFolded: true, panelFolded: false });
  expect(fit(beside(1024), { control: true, last: "list" })).toMatchObject({ listFolded: false, panelFolded: true });
});

test.each([901, 1024, 1101, 1280, 1440])("at %i px the chat keeps its least width, whatever is open", (window) => {
  for (const rail of [60, 216]) {
    for (const panel of [NOTHING_STORED.panel, OPENED]) {
      for (const last of [null, "list", "panel"] as const) {
        const room = beside(window, rail);
        expect(chat(room, fit(room, { panel, last }))).toBeGreaterThanOrEqual(CHAT_MIN);
      }
    }
  }
});

test("the list opened last stays and the terminals fold", () => {
  expect(fit(beside(1024), { panel: OPENED, last: "list" })).toMatchObject({ listFolded: false, panelFolded: true });
});

test("the terminals opened last stay and the list folds", () => {
  expect(fit(beside(1024), { panel: OPENED, last: "panel" })).toMatchObject({ listFolded: true, panelFolded: false });
});

test("a list the human folded leaves the terminals theirs, even after it was opened last", () => {
  const list = { width: 260, collapsed: true };
  expect(fit(beside(1024), { list, panel: OPENED, last: "list" })).toMatchObject({ panelFolded: false });
});

test("a wide panel narrows to leave the chat its room, and comes back", () => {
  const panel = { ...OPENED, width: 640 };
  expect(fit(beside(1024), { panel })).toEqual({ listFolded: true, panelFolded: false, panelWidth: 496 });
  expect(fit(beside(1440), { panel })).toEqual({ listFolded: false, panelFolded: false, panelWidth: 640 });
});

test("with the rail open at 901 px the panel folds too, as it would be under its least width", () => {
  expect(fit(beside(901, 216), { panel: OPENED })).toMatchObject({ listFolded: true, panelFolded: true });
});

test("a list that fits beside the folded panel stays open", () => {
  expect(fit(beside(960, 216), { panel: OPENED })).toMatchObject({ listFolded: false, panelFolded: true });
});

test("the panel narrows no further than its least width", () => {
  const shown = fit(LIST_STRIP + CHAT_MIN + 280, { panel: OPENED });
  expect(shown).toEqual({ listFolded: true, panelFolded: false, panelWidth: 280 });
  expect(fit(LIST_STRIP + CHAT_MIN + 279, { panel: OPENED }).panelFolded).toBe(true);
});

test("terminals nobody opened do not narrow: they fold", () => {
  const list = { width: 260, collapsed: true };
  expect(fit(LIST_STRIP + CHAT_MIN + 300, { list })).toMatchObject({ panelFolded: true });
});

test("both come back in order: the list first, then the terminals", () => {
  const rooms = [700, 720, 1040, 1041].map((room) => fit(room));
  expect(rooms.map(({ listFolded, panelFolded }) => [listFolded, panelFolded])).toEqual([
    [true, true], // 700 - 260 - 32 is less than 420
    [false, true],
    [false, false],
    [false, false],
  ]);
});

test("terminals nobody opened do not stay beside a list that folded: both fold", () => {
  expect(fit(850, { list: { width: 480, collapsed: false } })).toMatchObject({ listFolded: true, panelFolded: true });
});

test("terminals the human opened stay beside a wide list that folds, though the list came last", () => {
  const list = { width: 480, collapsed: false };
  expect(fit(850, { list, panel: OPENED, last: "list" })).toMatchObject({ listFolded: true, panelFolded: false });
});

test("the list is dragged no wider than leaves the chat its room beside the terminals that stay", () => {
  expect(listMax({ room: 1380, ...NOTHING_STORED, panel: { ...OPENED, width: 640 } })).toBe(1380 - 640 - CHAT_MIN);
  expect(listMax({ room: 1380, ...NOTHING_STORED, panel: OPENED })).toBe(1380 - 360 - CHAT_MIN);
});

test("terminals that would fold for the list leave it the room of their strip", () => {
  expect(listMax({ room: 800, ...NOTHING_STORED })).toBe(800 - STRIP - CHAT_MIN);
  const folded = { width: null, collapsed: true, chosen: true };
  expect(listMax({ room: 800, ...NOTHING_STORED, panel: folded })).toBe(800 - STRIP - CHAT_MIN);
  expect(listMax({ room: 800, ...NOTHING_STORED, panel: OPENED, last: "list" })).toBe(800 - STRIP - CHAT_MIN);
});

test("a list at its widest stays open", () => {
  const panel = { ...OPENED, width: 640 };
  const width = listMax({ room: 1380, ...NOTHING_STORED, panel });
  expect(fit(1380, { list: { width, collapsed: false }, panel })).toMatchObject({ listFolded: false, panelFolded: false });
});

test("what the human folded stays folded, whatever the room", () => {
  const folded = { width: null, collapsed: true, chosen: true };
  expect(fit(2400, { panel: folded }).panelFolded).toBe(true);
  expect(fit(2400, { list: { width: 260, collapsed: true } }).listFolded).toBe(true);
});
