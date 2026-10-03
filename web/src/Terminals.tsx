// The terminal panel of a session page (docs/design/ui.md, Terminal and Structure): on the
// right of the page, on every tab, closed until a terminal is opened (a team chip, or Open
// terminal in the Agents tab); its width dragged and remembered. Each open terminal is a
// tab, closed with ×; closing the last one closes the panel. A hidden tab keeps its socket;
// a closed one closes it. Every terminal opens to view: the wheel opens the window's
// history, read only; Take control asks first, then types into the agent; Release goes back.
import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";

import { getHistory, type History } from "./api";
import { PANEL_WIDTH, storedPanel, storePanel } from "./prefs";
import { TermLink, terminalUrl, type LinkState, type Mode } from "./terminalLink";

const WIDTH_STEP = 40; // pixels per arrow key on the panel's edge

type Terminals = { open: (agent: string) => void; active: string | null };

const TerminalsContext = createContext<Terminals | null>(null);

function useTerminals(): Terminals {
  const terminals = useContext(TerminalsContext);
  if (terminals === null) throw new Error("a terminal outside a session's page");
  return terminals;
}

// Open an agent's terminal in the panel, or select its tab.
export function useOpenTerminal(): (agent: string) => void {
  return useTerminals().open;
}

// The agent whose terminal the panel shows, or null when it is closed.
export function useShownTerminal(): string | null {
  return useTerminals().active;
}

export function TerminalPanel({ session, children }: { session: string; children: ReactNode }) {
  const [tabs, setTabs] = useState<string[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [panel, setPanel] = useState(storedPanel);

  const open = useCallback((agent: string) => {
    setTabs((now) => (now.includes(agent) ? now : [...now, agent]));
    setActive(agent);
  }, []);

  const close = (agent: string) => {
    const left = tabs.filter((one) => one !== agent);
    setTabs(left);
    if (active === agent) setActive(left.length ? left[left.length - 1] : null);
  };

  const resize = (width: number) => {
    setPanel({ width });
    storePanel({ width });
  };

  return (
    <TerminalsContext.Provider value={{ open, active }}>
      <div className="session-page">
        <div className="session-main">{children}</div>
        {tabs.length > 0 && (
          <aside className="terminals" aria-label="Terminals" style={{ width: `${panel.width}px` }}>
            <Edge width={panel.width} onChange={resize} />
            <div className="terminals-bar">
              <div role="tablist" aria-label="Open terminals" className="term-tabs">
                {tabs.map((agent) => (
                  <div key={agent} className="term-tab" data-active={agent === active || undefined}>
                    <button
                      type="button"
                      role="tab"
                      id={`term-tab-${agent}`}
                      aria-selected={agent === active}
                      aria-controls={`term-${agent}`}
                      onClick={() => setActive(agent)}
                    >
                      {agent}
                    </button>
                    <button
                      type="button"
                      className="term-close"
                      aria-label={`Close ${agent}'s terminal`}
                      title="Close"
                      onClick={() => close(agent)}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </div>
            {tabs.map((agent) => (
              <div
                key={agent}
                id={`term-${agent}`}
                role="tabpanel"
                aria-labelledby={`term-tab-${agent}`}
                className="term-body"
                hidden={agent !== active}
              >
                <AgentTerminal session={session} agent={agent} visible={agent === active} />
              </div>
            ))}
          </aside>
        )}
      </div>
    </TerminalsContext.Provider>
  );
}

// The panel's left edge: drag it, or use the arrow keys, to change the panel's width.
function Edge({ width, onChange }: { width: number; onChange: (width: number) => void }) {
  const clamp = (value: number) => Math.round(Math.min(PANEL_WIDTH.max, Math.max(PANEL_WIDTH.min, value)));
  const drag = (event: React.PointerEvent) => {
    const startX = event.clientX;
    const startWidth = width;
    const move = (moved: PointerEvent) => onChange(clamp(startWidth + startX - moved.clientX));
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  return (
    <div
      role="separator"
      aria-label="Resize the terminals"
      aria-orientation="vertical"
      aria-valuenow={width}
      aria-valuemin={PANEL_WIDTH.min}
      aria-valuemax={PANEL_WIDTH.max}
      tabIndex={0}
      className="term-edge"
      onPointerDown={drag}
      onKeyDown={(event) => {
        if (event.key === "ArrowLeft") onChange(clamp(width + WIDTH_STEP));
        if (event.key === "ArrowRight") onChange(clamp(width - WIDTH_STEP));
      }}
    />
  );
}

type Layer = { loading: true } | History | { error: string };

const FONT = { usual: 13, least: 8 }; // pixels

// The largest font, up to the usual one, at which a window of `size` fits the panel. The
// fit addon says how many cells fit at the current font; a cell scales with the font.
function fitFont(term: Terminal, fit: FitAddon, [cols, rows]: [number, number]): void {
  term.options.fontSize = FONT.usual;
  for (let tries = 0; tries < 4; tries++) {
    const room = fit.proposeDimensions();
    if (!room || (room.cols >= cols && room.rows >= rows)) return;
    const now: number = term.options.fontSize ?? FONT.usual;
    const scale = Math.min(room.cols / cols, room.rows / rows);
    const next = Math.max(FONT.least, Math.min(now - 0.5, Math.floor(now * scale * 2) / 2));
    if (next === now) return;
    term.options.fontSize = next;
  }
}

const PHASE: Record<LinkState["phase"], string> = {
  connecting: "connecting…",
  open: "live",
  retrying: "reconnecting",
  closed: "closed",
};

function AgentTerminal({ session, agent, visible }: { session: string; agent: string; visible: boolean }) {
  const [mode, setModeNow] = useState<Mode>("view");
  const [link, setLink] = useState<LinkState>({ phase: "connecting", reason: null });
  // Another mode is another socket: the old one's state is not shown for it.
  const setMode = (next: Mode) => {
    setLink({ phase: "connecting", reason: null });
    setModeNow(next);
  };
  const [notice, setNotice] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  const [layer, setLayer] = useState<Layer | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const fitNow = useRef<() => void>(() => {});
  const visibleNow = useRef(visible);
  visibleNow.current = visible;

  const showHistory = useCallback(() => {
    setLayer((now) => now ?? { loading: true });
    getHistory(session, agent).then(
      (found) => setLayer(found),
      (error: unknown) => setLayer({ error: String(error instanceof Error ? error.message : error) }),
    );
  }, [session, agent]);

  useEffect(() => {
    const element = box.current!;
    const colours = getComputedStyle(element);
    const term = new Terminal({
      fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
      fontSize: FONT.usual,
      scrollback: 0, // the history is tmux's: the wheel goes to tmux, or the history layer
      disableStdin: mode === "view",
      theme: { background: colours.backgroundColor, foreground: colours.color, cursor: colours.color },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(element);
    let window_: [number, number] | null = null; // in view: the agent's window's size
    const socket = new TermLink(terminalUrl(window.location, session, agent, mode), {
      output: (data) => term.write(data),
      size: (cols, rows) => {
        if (mode !== "view") return;
        window_ = [cols, rows];
        fitNow.current();
      },
      error: setNotice,
      state: (state) => {
        setLink(state);
        if (state.phase === "open") fitNow.current();
      },
    });
    // In control the terminal fills the panel and tells the server its size. In view it
    // has the window's size, whole: its font shrinks until the window fits the panel (down
    // to FONT.least; then the panel scrolls, kept at the bottom, where the live lines are).
    fitNow.current = () => {
      if (!visibleNow.current) return;
      if (mode === "control") {
        fit.fit();
        socket.resize(term.cols, term.rows);
        return;
      }
      if (window_ === null) return;
      term.resize(...window_);
      fitFont(term, fit, window_);
      const screen = element.parentElement;
      if (screen) screen.scrollTop = screen.scrollHeight;
    };
    const typed = mode === "control" ? term.onData((data) => socket.input(data)) : null;
    term.attachCustomWheelEventHandler((event) => {
      if (mode === "control") return true; // to tmux: copy-mode, or the CLI's own scrolling
      if (event.deltaY < 0) showHistory();
      return false;
    });
    const resized = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(() => fitNow.current());
    resized?.observe(element);
    setNotice(null);
    socket.start();
    return () => {
      resized?.disconnect();
      typed?.dispose();
      socket.stop();
      term.dispose();
    };
  }, [session, agent, mode, showHistory]);

  useEffect(() => {
    if (visible) fitNow.current();
  }, [visible]);

  const status =
    link.phase === "retrying" || link.phase === "closed"
      ? `${PHASE[link.phase]}: ${link.reason}`
      : PHASE[link.phase];

  return (
    <div className="term">
      <div className="term-tools">
        <span className={`term-mode term-${mode}`}>{mode === "control" ? "In control" : "Viewing"}</span>
        <span role="status" className={`term-link term-link-${link.phase}`}>
          {status}
        </span>
        {notice && (
          <span role="alert" className="term-notice">
            {notice}
          </span>
        )}
        {mode === "control" ? (
          <button type="button" className="quiet" onClick={() => setMode("view")}>
            Release
          </button>
        ) : (
          !asking && (
            <button type="button" className="quiet" onClick={() => setAsking(true)}>
              Take control
            </button>
          )
        )}
      </div>
      {asking && (
        <div role="alertdialog" aria-label={`Take control of ${agent}`} className="term-ask">
          <p>
            What you type goes straight to {agent}, as if you typed in its tmux window. Messages LADO
            delivers to it meanwhile land among your keys.
          </p>
          <button
            type="button"
            className="primary"
            onClick={() => {
              setAsking(false);
              setLayer(null);
              setMode("control");
            }}
          >
            Take control
          </button>
          <button type="button" className="quiet" onClick={() => setAsking(false)}>
            Cancel
          </button>
        </div>
      )}
      <div className="term-screen">
        <div ref={box} className="term-xterm" />
        {layer && <HistoryLayer layer={layer} onClose={() => setLayer(null)} />}
      </div>
    </div>
  );
}

function HistoryLayer({ layer, onClose }: { layer: Layer; onClose: () => void }) {
  const text = useRef<HTMLPreElement>(null);
  useEffect(() => {
    if (text.current) text.current.scrollTop = text.current.scrollHeight; // the latest lines
  }, [layer]);
  return (
    <section
      className="term-history"
      aria-label="History (read only)"
      onKeyDown={(event) => event.key === "Escape" && onClose()}
    >
      <div className="term-history-bar">
        <h4>History (read only)</h4>
        <button type="button" className="quiet" onClick={onClose} autoFocus>
          Back to live ↓
        </button>
      </div>
      {"loading" in layer && <p className="muted">Loading…</p>}
      {"error" in layer && (
        <p className="problem" role="alert">
          {layer.error}
        </p>
      )}
      {"alternate" in layer && layer.alternate && (
        <p className="term-history-note">
          This agent's history is inside its CLI, which runs full screen. To scroll it, press Take control and
          scroll there.
        </p>
      )}
      {"alternate" in layer && !layer.alternate && (
        <pre ref={text} tabIndex={0}>
          {layer.text}
        </pre>
      )}
    </section>
  );
}
