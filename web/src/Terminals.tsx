// The terminal panel of a session page (docs/design/ui.md, Terminal and Structure): on the
// right of the page, on every tab, always there, so the page never jumps. Its first tab is
// the supervisor's, pinned (no ×, kept at the left); a team chip or Open terminal in the
// Agents tab adds an agent's tab or selects it (scrolled into view), and the others close
// with ×. A tab shows its agent's status (a small dot, live; stopped when the agent is not
// listed) and its name, cut to fit; the tabs stay on one line and scroll sideways, the
// wheel too; its tooltip says who the agent is (Tooltip.tsx). A tab's terminal opens its socket
// the first time it is shown in the open panel: a panel collapsed when the page opens opens
// none. Then a hidden tab keeps its socket, a closed one closes it. The panel collapses to a
// strip with a dot per open terminal (remembered; at first on a narrow window), its width is dragged on its edge
// (remembered; narrowed while the window leaves the session too little room), and Expand
// shows it over the whole page with the same terminals. Every terminal opens to view: the
// wheel opens the window's history, read only; Take control asks first in a dialog (until
// the human says not to ask again), then types into the agent; Release goes back. A terminal
// closed for good has Reconnect, and opens again by itself when its agent comes back.
import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { useSearchParams } from "react-router";

import { getHistory, type AgentInfo, type History } from "./api";
import { CollapsePanelIcon, ExpandIcon } from "./icons";
import { useLive, useLiveStore } from "./live";
import { TERMINAL_PARAM } from "./paths";
import { PANEL_WIDTH, storeAskControl, storedAskControl, storedPanel, storePanel, type ColumnPrefs } from "./prefs";
import { fitWidth, Splitter, useStripFocus, useWidth } from "./Splitter";
import { AgentTip, StatusDot, SUPERVISOR } from "./Team";
import { Tooltip } from "./Tooltip";
import { TermLink, terminalUrl, type LinkState, type Mode } from "./terminalLink";

// The least width of the session beside the panel: the panel is narrowed to leave it.
export const MAIN_MIN = 360;

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

// The agent whose terminal the panel shows, or null while the panel is collapsed.
export function useShownTerminal(): string | null {
  return useTerminals().active;
}

// Esc on an expanded panel puts it back, except where Esc is someone else's: a dialog, the
// history layer, and the terminal of an agent the human controls (Esc goes to the agent).
function escapeIsOurs(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return true;
  if (target.closest("dialog, .term-history")) return false;
  return !(target.closest(".term-xterm") && target.closest('[data-mode="control"]'));
}

export function TerminalPanel({ session, children }: { session: string; children: ReactNode }) {
  const live = useLiveStore();
  const loaded = useLive().agents[session] ?? null;
  // The panel follows the agents itself, on every tab: a terminal opens again when its agent
  // comes back.
  useEffect(() => live.watch("agents", session), [live, session]);
  const agents = loaded && "items" in loaded ? loaded.items : [];
  const infoOf = (agent: string) => agents.find((one) => one.name === agent) ?? null;
  // An agent not in the session's list (gone, or not loaded yet) shows as stopped.
  const statusOf = (agent: string) => infoOf(agent)?.status ?? "stopped";

  const [tabs, setTabs] = useState<string[]>([SUPERVISOR]);
  const [active, setActive] = useState(SUPERVISOR);
  const [panel, setPanel] = useState(storedPanel);
  const [expanded, setExpanded] = useState(false);
  const [shown, setShown] = useState<string[]>([]); // the tabs whose terminal is made
  const [page, room] = useWidth<HTMLDivElement>();
  const tabList = useRef<HTMLDivElement>(null);

  // The selected tab, chosen here or by a chip, scrolls into the tabs' view.
  useEffect(() => {
    tabList.current
      ?.querySelector('[aria-selected="true"]')
      ?.scrollIntoView?.({ inline: "nearest", block: "nearest" });
  }, [active, panel.collapsed]);

  const keep = useCallback((change: Partial<ColumnPrefs>) => {
    setPanel((now) => {
      const next = { ...now, ...change };
      storePanel(next);
      return next;
    });
  }, []);

  const open = useCallback(
    (agent: string) => {
      setTabs((now) => (now.includes(agent) ? now : [...now, agent]));
      setActive(agent);
      keep({ collapsed: false });
    },
    [keep],
  );

  // ?terminal=<agent> (Needs you, a notification) opens that agent's terminal once the
  // agents are loaded, and leaves the address (replaced, so Back and a reload do not open
  // it again); an agent the session does not have is named.
  const [params, setParams] = useSearchParams();
  const wanted = params.get(TERMINAL_PARAM);
  const [missing, setMissing] = useState<string | null>(null);
  useEffect(() => {
    if (wanted === null || loaded === null || "error" in loaded) return;
    if (loaded.items.some((one) => one.name === wanted)) {
      open(wanted);
      setMissing(null);
    } else {
      setMissing(wanted);
    }
    setParams(
      (now) => {
        const next = new URLSearchParams(now);
        next.delete(TERMINAL_PARAM);
        return next;
      },
      { replace: true, preventScrollReset: true },
    );
  }, [wanted, loaded, open, setParams]);

  const close = (agent: string) => {
    const left = tabs.filter((one) => one !== agent);
    setTabs(left);
    setShown((now) => now.filter((one) => one !== agent));
    if (active === agent) setActive(left[left.length - 1]);
  };

  const focus = useStripFocus(panel.collapsed);
  const collapse = () => {
    setExpanded(false);
    focus.toggled();
    keep({ collapsed: true });
  };

  // A tab's terminal is made the first time it shows in the open panel.
  const made = panel.collapsed || shown.includes(active) ? shown : [...shown, active];
  useEffect(() => {
    if (made !== shown) setShown(made);
  });

  useEffect(() => {
    if (!expanded) return;
    const restore = (event: KeyboardEvent) => {
      if (event.key === "Escape" && escapeIsOurs(event.target)) setExpanded(false);
    };
    // Captured: xterm.js takes the keys it handles, so they never bubble up to the window.
    window.addEventListener("keydown", restore, true);
    return () => window.removeEventListener("keydown", restore, true);
  }, [expanded]);

  const width = fitWidth(panel.width, PANEL_WIDTH, room === null ? null : room - MAIN_MIN);
  const classes = ["terminals", panel.collapsed && "collapsed", expanded && "expanded"].filter(Boolean).join(" ");

  return (
    <TerminalsContext.Provider value={{ open, active: panel.collapsed ? null : active }}>
      <div ref={page} className="session-page">
        <div className="session-main" style={{ minWidth: `${MAIN_MIN}px` }}>
          {missing !== null && (
            <p className="problem" role="alert">
              {missing} is not in this session
            </p>
          )}
          {children}
        </div>
        <aside
          className={classes}
          aria-label="Terminals"
          style={panel.collapsed ? undefined : { width: `${width}px` }}
        >
          {panel.collapsed ? (
            <>
              <button
                ref={focus.open}
                type="button"
                className="strip-open"
                title="Show the terminals"
                onClick={() => {
                  focus.toggled();
                  keep({ collapsed: false });
                }}
              >
                Terminals
              </button>
              <ul className="terminals-dots" aria-label="Open terminals">
                {tabs.map((agent) => (
                  <li key={agent} title={`${agent}: ${statusOf(agent)}`} aria-label={`${agent}, ${statusOf(agent)}`}>
                    <StatusDot status={statusOf(agent)} small />
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <>
              {!expanded && (
                <Splitter
                  label="Resize the terminals"
                  edge="left"
                  width={width}
                  bounds={PANEL_WIDTH}
                  onChange={(next) => keep({ width: next })}
                />
              )}
              <div className="terminals-bar">
                <div
                  ref={tabList}
                  role="tablist"
                  aria-label="Open terminals"
                  className="term-tabs"
                  onWheel={(event) => {
                    // The wheel scrolls the tabs sideways.
                    if (event.deltaX === 0) event.currentTarget.scrollLeft += event.deltaY;
                  }}
                >
                  {tabs.map((agent) => (
                    <div
                      key={agent}
                      className={`term-tab${agent === SUPERVISOR ? " pinned" : ""}`}
                      data-active={agent === active || undefined}
                      style={{ "--chars": agent.length } as CSSProperties}
                    >
                      <Tooltip tip={<AgentTip name={agent} info={infoOf(agent)} />}>
                        <button
                          type="button"
                          role="tab"
                          id={`term-tab-${agent}`}
                          aria-label={`${agent}, ${statusOf(agent)}`}
                          aria-selected={agent === active}
                          aria-controls={`term-${agent}`}
                          onClick={() => setActive(agent)}
                        >
                          <StatusDot status={statusOf(agent)} small />
                          <span className="term-tab-name">{agent}</span>
                        </button>
                      </Tooltip>
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
                <div className="term-actions">
                  <button
                    type="button"
                    className="ghost"
                    aria-label={expanded ? "Restore terminal" : "Expand terminal"}
                    title={expanded ? "Restore terminal (Esc)" : "Expand terminal over the page"}
                    onClick={() => setExpanded(!expanded)}
                  >
                    <ExpandIcon expanded={expanded} />
                  </button>
                  {!expanded && (
                    <button
                      ref={focus.collapse}
                      type="button"
                      className="ghost"
                      aria-label="Collapse terminals"
                      title="Collapse terminals"
                      onClick={collapse}
                    >
                      <CollapsePanelIcon />
                    </button>
                  )}
                </div>
              </div>
            </>
          )}
          {tabs.map((agent) => (
            <div
              key={agent}
              id={`term-${agent}`}
              role="tabpanel"
              aria-label={agent}
              className="term-body"
              hidden={panel.collapsed || agent !== active}
            >
              {made.includes(agent) && (
                <AgentTerminal
                  session={session}
                  agent={agent}
                  visible={!panel.collapsed && agent === active}
                  info={infoOf(agent)}
                />
              )}
            </div>
          ))}
        </aside>
      </div>
    </TerminalsContext.Provider>
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

const controlText = (agent: string) =>
  `What you type goes straight to ${agent}, as if you typed in its tmux window. Messages LADO ` +
  "delivers to it meanwhile land among your keys.";

// `info`: the agent as the session's agents list has it, or null while it is not there.
function AgentTerminal({
  session,
  agent,
  visible,
  info,
}: {
  session: string;
  agent: string;
  visible: boolean;
  info: AgentInfo | null;
}) {
  const [mode, setModeNow] = useState<Mode>("view");
  const [link, setLink] = useState<LinkState>({ phase: "connecting", reason: null });
  const [attempt, setAttempt] = useState(0); // a new socket each time it changes: Reconnect
  // Another mode is another socket: the old one's state is not shown for it.
  const setMode = (next: Mode) => {
    setLink({ phase: "connecting", reason: null });
    setModeNow(next);
  };
  const reconnect = () => {
    setLink({ phase: "connecting", reason: null });
    setAttempt((now) => now + 1);
  };
  // A socket closed for good opens again when the agent comes back or changes (a resumed
  // session's supervisor, starting, then idle); the agent as it was at the close is kept, so
  // an agent that still has no terminal is not asked again until it changes.
  const infoNow = useRef(info);
  infoNow.current = info;
  const closedWith = useRef<AgentInfo | null>(null);
  useEffect(() => {
    if (link.phase === "closed" && info !== null && info !== closedWith.current) reconnect();
  }, [link.phase, info]);
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
        if (state.phase === "closed") closedWith.current = infoNow.current;
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
  }, [session, agent, mode, showHistory, attempt]);

  useEffect(() => {
    if (visible) fitNow.current();
  }, [visible]);

  const status =
    link.phase === "retrying" || link.phase === "closed"
      ? `${PHASE[link.phase]}: ${link.reason}`
      : PHASE[link.phase];

  const takeControl = () => {
    setAsking(false);
    setLayer(null);
    setMode("control");
  };

  return (
    <div className="term" data-mode={mode}>
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
        {link.phase === "closed" && (
          <button type="button" className="quiet" onClick={reconnect}>
            Reconnect
          </button>
        )}
        {mode === "control" ? (
          <button type="button" className="quiet" onClick={() => setMode("view")}>
            Release
          </button>
        ) : (
          <button
            type="button"
            className="quiet"
            title={controlText(agent)}
            onClick={() => (storedAskControl() ? setAsking(true) : takeControl())}
          >
            Take control
          </button>
        )}
      </div>
      {asking && <ControlDialog agent={agent} onTake={takeControl} onCancel={() => setAsking(false)} />}
      <div className="term-screen">
        <div ref={box} className="term-xterm" />
        {layer && <HistoryLayer layer={layer} onClose={() => setLayer(null)} />}
      </div>
    </div>
  );
}

// Take control's question, modal: Esc is Cancel. "Don't ask again" is remembered in the
// browser for every agent; without browser storage it asks the next time anyway.
function ControlDialog({ agent, onTake, onCancel }: { agent: string; onTake: () => void; onCancel: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [never, setNever] = useState(false);
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  return (
    <dialog
      ref={dialog}
      className="term-ask"
      aria-label={`Take control of ${agent}`}
      onCancel={(event) => {
        event.preventDefault();
        onCancel();
      }}
      onKeyDown={(event) => {
        if (event.key !== "Escape") return;
        event.preventDefault();
        onCancel();
      }}
    >
      <h3>Take control of {agent}?</h3>
      <p>{controlText(agent)}</p>
      <label className="switch">
        <input type="checkbox" checked={never} onChange={(event) => setNever(event.target.checked)} />
        Don't ask again
      </label>
      <div className="term-ask-buttons">
        <button type="button" className="quiet" onClick={onCancel}>
          Cancel
        </button>
        <button
          type="button"
          className="primary"
          autoFocus
          onClick={() => {
            if (never) storeAskControl(false);
            onTake();
          }}
        >
          Take control
        </button>
      </div>
    </dialog>
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
