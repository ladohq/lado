// Fakes for the UI's unit tests (not part of the bundle: only tests import this file). jsdom
// has no canvas for xterm.js, no server for WebSockets and no EventSource.
import { act } from "@testing-library/react";
import { vi } from "vitest";

// A WebSocket the test drives: it opens, sends frames and closes as the server would.
export class FakeSocket {
  static all: FakeSocket[] = [];
  binaryType = "blob";
  sent: string[] = [];
  closed = false;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  onclose: ((event: { code: number; reason: string }) => void) | null = null;

  constructor(readonly url: string) {
    FakeSocket.all.push(this);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    this.closed = true;
  }
  open() {
    this.onopen?.();
  }
  // A JSON frame for an object, else the data as it is (output: an ArrayBuffer).
  frame(data: unknown) {
    const json = data !== null && Object.getPrototypeOf(data) === Object.prototype;
    this.onmessage?.({ data: json ? JSON.stringify(data) : data });
  }
  end(code: number, reason = "") {
    this.onclose?.({ code, reason });
  }
  get frames(): unknown[] {
    return this.sent.map((one) => JSON.parse(one));
  }
}

export const lastSocket = () => FakeSocket.all[FakeSocket.all.length - 1];

// xterm.js's Terminal as far as the UI uses it.
export class FakeXterm {
  static all: FakeXterm[] = [];
  cols = 80;
  rows = 24;
  written = "";
  disposed = false;
  element: HTMLElement | null = null;
  private data: ((data: string) => void) | null = null;
  private wheelHandler: ((event: WheelEvent) => boolean) | null = null;

  constructor(readonly options: Record<string, unknown> = {}) {
    FakeXterm.all.push(this);
  }
  loadAddon(addon: { activate?: (term: FakeXterm) => void }) {
    addon.activate?.(this);
  }
  open(element: HTMLElement) {
    this.element = element;
    // xterm.js takes the keys it handles: they go no further up the page.
    element.addEventListener("keydown", (event) => event.stopPropagation());
  }
  write(data: Uint8Array | string) {
    this.written += typeof data === "string" ? data : new TextDecoder().decode(data);
  }
  resize(cols: number, rows: number) {
    this.cols = cols;
    this.rows = rows;
  }
  onData(listener: (data: string) => void) {
    this.data = listener;
    return { dispose: () => (this.data = null) };
  }
  attachCustomWheelEventHandler(handler: (event: WheelEvent) => boolean) {
    this.wheelHandler = handler;
  }
  focus() {}
  dispose() {
    this.disposed = true;
  }
  // What the human does in it.
  type(data: string) {
    this.data?.(data);
  }
  wheel(deltaY: number): boolean {
    return this.wheelHandler?.({ deltaY } as WheelEvent) ?? true;
  }
}

export class FakeFit {
  private term: FakeXterm | null = null;
  activate(term: FakeXterm) {
    this.term = term;
  }
  fit() {
    this.term?.resize(120, 30);
  }
  // A panel of 960 x 300 pixels; a cell is 0.6 x 1.2 font sizes.
  proposeDimensions() {
    const size = Number(this.term?.options.fontSize ?? 13);
    return { cols: Math.floor(960 / (0.6 * size)), rows: Math.floor(300 / (1.2 * size)) };
  }
  dispose() {}
}

// The browser's ResizeObserver: `resize` lays every observed element out at a width; with
// `width` set, an element is laid out at it as soon as it is observed.
export class FakeResizeObserver {
  static all: FakeResizeObserver[] = [];
  static width: number | null = null;
  private targets: Element[] = [];

  constructor(private readonly callback: (entries: { target: Element; contentRect: { width: number } }[]) => void) {
    FakeResizeObserver.all.push(this);
  }
  observe(target: Element) {
    this.targets.push(target);
    const width = FakeResizeObserver.width;
    if (width !== null) this.callback([{ target, contentRect: { width } }]);
  }
  disconnect() {
    this.targets = [];
  }
  static resize(width: (target: Element) => number) {
    act(() =>
      FakeResizeObserver.all.forEach((observer) =>
        observer.targets.forEach((target) => observer.callback([{ target, contentRect: { width: width(target) } }])),
      ),
    );
  }
}

// The page's columns as the browser lays them out: every element measured with useWidth is
// `width` wide as soon as it is drawn (null: not laid out until FakeResizeObserver.resize).
// A tab's list and page (ListPage) are side by side from NARROW (900) on.
export function columnWidth(width: number | null) {
  FakeResizeObserver.all = [];
  FakeResizeObserver.width = width;
  vi.stubGlobal("ResizeObserver", FakeResizeObserver);
}

export const wideColumn = () => columnWidth(1000);
export const narrowColumn = () => columnWidth(700);

// The browser's IntersectionObserver: `show` says each observed element is in view (or not),
// as the browser does when one is observed and when it comes into view.
export class FakeIntersectionObserver {
  static all: FakeIntersectionObserver[] = [];
  targets: Element[] = [];

  constructor(private readonly callback: (entries: { target: Element; isIntersecting: boolean }[]) => void) {
    FakeIntersectionObserver.all.push(this);
  }
  observe(target: Element) {
    this.targets.push(target);
  }
  unobserve(target: Element) {
    this.targets = this.targets.filter((one) => one !== target);
  }
  disconnect() {
    this.targets = [];
  }
  static show(visible = true) {
    act(() =>
      FakeIntersectionObserver.all.forEach((observer) =>
        observer.callback(observer.targets.map((target) => ({ target, isIntersecting: visible }))),
      ),
    );
  }
}

// jsdom has <dialog> but not showModal and close: the UI's modal dialogs need them.
export function stubDialogs() {
  HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close ??= function (this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
}

export const xtermFor = (url: string) =>
  FakeXterm.all[FakeSocket.all.findIndex((socket) => socket.url === url)];

// The browser's EventSource as the server drives it: `start` opens it and sends reset, as
// a new stream does; the tests send changes and errors themselves.
export class FakeEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  static all: FakeEventSource[] = [];
  static autoStart = true;

  readyState = FakeEventSource.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  private listeners = new Map<string, ((event: MessageEvent) => void)[]>();
  private lastId = "";

  constructor(readonly url: string) {
    FakeEventSource.all.push(this);
    if (FakeEventSource.autoStart) queueMicrotask(() => this.start());
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  close() {
    this.readyState = FakeEventSource.CLOSED;
  }

  start(id = "10") {
    this.open();
    this.send("reset", {}, id);
  }

  open() {
    this.readyState = FakeEventSource.OPEN;
    act(() => this.onopen?.(new Event("open")));
  }

  // An event with an `id:` line when `id` is given; without one the browser keeps the last.
  send(type: string, data: unknown, id?: string) {
    if (id !== undefined) this.lastId = id;
    const event = new MessageEvent(type, { data: JSON.stringify(data), lastEventId: this.lastId });
    act(() => this.listeners.get(type)?.forEach((listener) => listener(event)));
  }

  // A network error (the browser tries again itself) or a refused answer (it gives up).
  fail(closed: boolean) {
    this.readyState = closed ? FakeEventSource.CLOSED : FakeEventSource.CONNECTING;
    act(() => this.onerror?.(new Event("error")));
  }
}

export const stream = () => FakeEventSource.all[FakeEventSource.all.length - 1];

// The browser's Notification: the permission it has, the human's answer when asked
// (`answer`), and the notifications shown; `click` is the human clicking one.
export class FakeNotification {
  static permission: NotificationPermission = "default";
  static answer: NotificationPermission = "granted";
  static asked = 0;
  static all: FakeNotification[] = [];

  static reset() {
    FakeNotification.permission = "default";
    FakeNotification.answer = "granted";
    FakeNotification.asked = 0;
    FakeNotification.all = [];
  }

  static async requestPermission(): Promise<NotificationPermission> {
    FakeNotification.asked += 1;
    FakeNotification.permission = FakeNotification.answer;
    return FakeNotification.answer;
  }

  onclick: ((event: Event) => void) | null = null;
  closed = false;

  constructor(
    readonly title: string,
    readonly options: NotificationOptions = {},
  ) {
    FakeNotification.all.push(this);
  }
  close() {
    this.closed = true;
  }
  click() {
    act(() => this.onclick?.(new Event("click")));
  }
}

// The fields of an AgentInfo a test that is not about them leaves as they are: an agent
// without a branch of its own, spawned and in its status since 10:00.
export const AGENT_REST = {
  branch: null,
  worktree: null,
  spawned_at: "2026-10-04T10:00:00.000Z",
  since: "2026-10-04T10:00:00.000Z",
};

// Whether the tab is on the screen (document.visibilityState).
export function setVisible(visible: boolean) {
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    get: () => (visible ? "visible" : "hidden"),
  });
}
