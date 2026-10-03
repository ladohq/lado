// An agent's terminal socket (docs/design/ui.md, Terminal): output as binary frames, JSON
// frames for the window's size and errors, input and resize as JSON. A close with a code
// 4400-4499 is for good (no token, the agent or its session is gone or stopped): the reason
// shows and nothing opens again. Any other close opens a new socket after RETRY_MS.

export type Mode = "view" | "control";

// connecting: before the first open; retrying: closed for now, a new one opens soon;
// closed: for good, the reason says why.
export type LinkState = { phase: "connecting" | "open" | "retrying" | "closed"; reason: string | null };

export type LinkHandlers = {
  output: (data: Uint8Array) => void;
  size: (cols: number, rows: number) => void;
  error: (reason: string) => void;
  state: (state: LinkState) => void;
};

export const RETRY_MS = 2000;

export function terminalUrl(
  where: { protocol: string; host: string },
  session: string,
  agent: string,
  mode: Mode,
): string {
  const scheme = where.protocol === "https:" ? "wss:" : "ws:";
  const path = `/api/sessions/${encodeURIComponent(session)}/agents/${encodeURIComponent(agent)}`;
  return `${scheme}//${where.host}${path}/terminal?mode=${mode}`;
}

export const forGood = (code: number) => code >= 4400 && code < 4500;

export class TermLink {
  private socket: WebSocket | null = null;
  private retry: ReturnType<typeof setTimeout> | undefined;
  private stopped = false;
  private open = false; // the socket is open: what is sent before is dropped, not queued

  constructor(
    private readonly url: string,
    private readonly on: LinkHandlers,
    private readonly makeSocket: (url: string) => WebSocket = (url) => new WebSocket(url),
  ) {}

  start() {
    this.stopped = false;
    this.connect();
  }

  stop() {
    this.stopped = true;
    clearTimeout(this.retry);
    this.socket?.close();
    this.socket = null;
  }

  input(data: string) {
    this.send({ type: "input", data });
  }

  resize(cols: number, rows: number) {
    this.send({ type: "resize", cols, rows });
  }

  private send(frame: object) {
    if (this.socket && this.open) this.socket.send(JSON.stringify(frame));
  }

  private connect() {
    this.on.state({ phase: "connecting", reason: null });
    const socket = this.makeSocket(this.url);
    socket.binaryType = "arraybuffer";
    this.socket = socket;
    this.open = false;
    socket.onopen = () => {
      this.open = true;
      this.on.state({ phase: "open", reason: null });
    };
    socket.onmessage = (event) => {
      if (typeof event.data !== "string") {
        this.on.output(new Uint8Array(event.data as ArrayBuffer)); // binaryType arraybuffer
        return;
      }
      const frame = JSON.parse(event.data);
      if (frame.type === "size") this.on.size(frame.cols, frame.rows);
      else if (frame.type === "error") this.on.error(frame.reason);
    };
    socket.onclose = (event) => {
      if (this.socket !== socket || this.stopped) return;
      this.socket = null;
      if (forGood(event.code)) {
        this.on.state({ phase: "closed", reason: event.reason || `closed (${event.code})` });
        return;
      }
      this.on.state({ phase: "retrying", reason: event.reason || "the connection to the server was lost" });
      this.retry = setTimeout(() => this.connect(), RETRY_MS);
    };
  }
}
