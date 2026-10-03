// The terminal panel of a session page (docs/design/ui.md, Terminal): docked under the page
// on every tab, collapsible, its height dragged and remembered. Its tabs: the supervisor's
// terminal, always first and in control (the human's chat with it), and the agents opened
// from the Agents tab, to view; a tab closes with ×. A hidden tab keeps its socket; a closed
// one closes it. In view the wheel opens the window's history, read only; Take control
// asks first, then types into the agent; Release goes back to view.
import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";

import { getHistory, type History } from "./api";
import { PANEL_HEIGHT, storedPanel, storePanel } from "./prefs";
import { TermLink, terminalUrl, type LinkState, type Mode } from "./terminalLink";

export const SUPERVISOR = "supervisor";
const HEIGHT_STEP = 40; // pixels per arrow key on the panel's handle

const TerminalsContext = createContext<((agent: string) => void) | null>(null);

// Open an agent's terminal in the panel (from the Agents tab).
export function useOpenTerminal(): (agent: string) => void {
  const open = useContext(TerminalsContext);
  if (open === null) throw new Error("useOpenTerminal outside a session's page");
  return open;
}

const tabName = (agent: string) => (agent === SUPERVISOR ? "Supervisor" : agent);

export function TerminalPanel({ session, children }: { session: string; children: ReactNode }) {
  const [tabs, setTabs] = useState<string[]>([SUPERVISOR]);
  const [active, setActive] = useState(SUPERVISOR);
  const [panel, setPanel] = useState(storedPanel);

  const change = (next: typeof panel) => {
    setPanel(next);
    storePanel(next);
  };

  const open = useCallback((agent: string) => {
    setTabs((now) => (now.includes(agent) ? now : [...now, agent]));
    setActive(agent);
    setPanel((now) => (now.collapsed ? { ...now, collapsed: false } : now));
  }, []);

  const close = (agent: string) => {
    const left = tabs.filter((one) => one !== agent);
    setTabs(left);
    if (active === agent) setActive(left[left.length - 1]);
  };

  return (
    <TerminalsContext.Provider value={open}>
      {children}
      <section
        className={`terminals${panel.collapsed ? " collapsed" : ""}`}
        aria-label="Terminals"
        style={panel.collapsed ? undefined : { height: `${panel.height}px` }}
      >
        {!panel.collapsed && <Handle height={panel.height} onChange={(height) => change({ ...panel, height })} />}
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
                  onClick={() => {
                    setActive(agent);
                    if (panel.collapsed) change({ ...panel, collapsed: false });
                  }}
                >
                  {tabName(agent)}
                </button>
                {agent !== SUPERVISOR && (
                  <button
                    type="button"
                    className="term-close"
                    aria-label={`Close ${agent}'s terminal`}
                    title="Close"
                    onClick={() => close(agent)}
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
          </div>
          <button
            type="button"
            className="ghost term-collapse"
            aria-expanded={!panel.collapsed}
            aria-label={panel.collapsed ? "Expand the terminals" : "Collapse the terminals"}
            title={panel.collapsed ? "Expand" : "Collapse"}
            onClick={() => change({ ...panel, collapsed: !panel.collapsed })}
          >
            {panel.collapsed ? "▴" : "▾"}
          </button>
        </div>
        {tabs.map((agent) => (
          <div
            key={agent}
            id={`term-${agent}`}
            role="tabpanel"
            aria-labelledby={`term-tab-${agent}`}
            className="term-body"
            hidden={agent !== active || panel.collapsed}
          >
            <AgentTerminal session={session} agent={agent} visible={agent === active && !panel.collapsed} />
          </div>
        ))}
      </section>
    </TerminalsContext.Provider>
  );
}

// The panel's top edge: drag it, or use the arrow keys, to change the panel's height.
function Handle({ height, onChange }: { height: number; onChange: (height: number) => void }) {
  const clamp = (value: number) => Math.round(Math.min(PANEL_HEIGHT.max, Math.max(PANEL_HEIGHT.min, value)));
  const drag = (event: React.PointerEvent) => {
    const startY = event.clientY;
    const startHeight = height;
    const move = (moved: PointerEvent) => onChange(clamp(startHeight + startY - moved.clientY));
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
      aria-orientation="horizontal"
      aria-valuenow={height}
      aria-valuemin={PANEL_HEIGHT.min}
      aria-valuemax={PANEL_HEIGHT.max}
      tabIndex={0}
      className="term-handle"
      onPointerDown={drag}
      onKeyDown={(event) => {
        if (event.key === "ArrowUp") onChange(clamp(height + HEIGHT_STEP));
        if (event.key === "ArrowDown") onChange(clamp(height - HEIGHT_STEP));
      }}
    />
  );
}

type Layer = { loading: true } | History | { error: string };

const PHASE: Record<LinkState["phase"], string> = {
  connecting: "connecting…",
  open: "live",
  retrying: "reconnecting",
  closed: "closed",
};

function AgentTerminal({ session, agent, visible }: { session: string; agent: string; visible: boolean }) {
  const [mode, setModeNow] = useState<Mode>(agent === SUPERVISOR ? "control" : "view");
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
      fontSize: 13,
      scrollback: 0, // the history is tmux's: the wheel goes to tmux, or the history layer
      disableStdin: mode === "view",
      theme: { background: colours.backgroundColor, foreground: colours.color, cursor: colours.color },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(element);
    const socket = new TermLink(terminalUrl(window.location, session, agent, mode), {
      output: (data) => term.write(data),
      size: (cols, rows) => {
        if (mode === "view") term.resize(cols, rows); // the agent's window, whole
      },
      error: setNotice,
      state: (state) => {
        setLink(state);
        if (state.phase === "open") fitNow.current();
      },
    });
    // In control the terminal fills the panel and tells the server its size; in view it
    // has the window's size and nothing typed goes out.
    fitNow.current = () => {
      if (mode !== "control" || !visibleNow.current) return;
      fit.fit();
      socket.resize(term.cols, term.rows);
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
