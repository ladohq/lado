// Fakes for the UI's unit tests (not part of the bundle: only tests import this file). jsdom
// has no canvas for xterm.js and no server for WebSockets.

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
  dispose() {}
}

export const xtermFor = (url: string) =>
  FakeXterm.all[FakeSocket.all.findIndex((socket) => socket.url === url)];
