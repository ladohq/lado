// The login window of Settings → Providers and environment (docs/design/ui.md): a sheet over
// the page (the whole screen on a phone) with the terminal of the CLI's own login command,
// always in control, over the agents' terminal protocol (terminalLink.ts). A link in it,
// also one wrapped over lines, opens in a new tab (xterm's web links addon). Under it "Text
// to send" sends its text and Enter as one input (a code, a key), and the keys ↑ ↓ Enter
// Esc go to menus, so it works from a phone. When the command ends the socket closes for
// good and the sheet goes (`onEnded`); Close ends the command first.
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { useEffect, useId, useRef, useState } from "react";

import { closeLogin } from "./api";
import { loginTerminalUrl, TermLink, type LinkState } from "./terminalLink";

// What each key sends to the terminal, as a keyboard's would.
export const KEYS: { label: string; name: string; data: string }[] = [
  { label: "↑", name: "Up", data: "\x1b[A" },
  { label: "↓", name: "Down", data: "\x1b[B" },
  { label: "Enter", name: "Enter", data: "\r" },
  { label: "Esc", name: "Escape", data: "\x1b" },
];

export function LoginWindow({
  provider,
  title,
  onEnded,
}: {
  provider: string;
  title: string;
  onEnded: () => void;
}) {
  const id = useId();
  const box = useRef<HTMLDivElement>(null);
  const link = useRef<TermLink | null>(null);
  const [state, setState] = useState<LinkState>({ phase: "connecting", reason: null });
  const [text, setText] = useState("");
  const [closing, setClosing] = useState(false);
  const ended = useRef(onEnded);
  ended.current = onEnded;

  useEffect(() => {
    const element = box.current!;
    const colours = getComputedStyle(element);
    const term = new Terminal({
      fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
      fontSize: 13,
      theme: { background: colours.backgroundColor, foreground: colours.color, cursor: colours.color },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.loadAddon(new WebLinksAddon((_event, uri) => window.open(uri, "_blank", "noopener,noreferrer")));
    term.open(element);
    const socket = new TermLink(loginTerminalUrl(window.location, provider), {
      output: (data) => term.write(data),
      size: () => {},
      error: () => {},
      state: (now) => {
        setState(now);
        if (now.phase === "open") resize();
        if (now.phase === "closed") ended.current(); // the command ended, or Close
      },
    });
    const resize = () => {
      fit.fit();
      socket.resize(term.cols, term.rows);
    };
    const typed = term.onData((data) => socket.input(data));
    const observed = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(resize);
    observed?.observe(element);
    link.current = socket;
    socket.start();
    return () => {
      observed?.disconnect();
      typed.dispose();
      socket.stop();
      link.current = null;
      term.dispose();
    };
  }, [provider]);

  const send = () => {
    link.current?.input(`${text}\r`); // one input: the CLI reads the line and its Enter
    setText("");
  };
  const close = async () => {
    setClosing(true);
    try {
      await closeLogin(provider);
    } finally {
      ended.current();
    }
  };
  const open = state.phase === "open";

  return (
    <div className="login-sheet" role="dialog" aria-modal="true" aria-labelledby={id}>
      <div className="login-window">
        <div className="login-top">
          <h3 id={id}>{`Log in: ${title}`}</h3>
          {state.phase !== "open" && <span className="muted login-link">{state.reason ?? "connecting…"}</span>}
          <button type="button" className="quiet" disabled={closing} onClick={close}>
            Close
          </button>
        </div>
        <div className="login-term" ref={box} data-link={state.phase} />
        <div className="login-help">
          <p className="muted">Open the link, sign in, then send what it gives you (a code) from here.</p>
          <div className="login-send">
            <input
              type="text"
              aria-label="Text to send"
              placeholder="Text to send"
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
              value={text}
              onChange={(event) => setText(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && open) send();
              }}
            />
            <button type="button" className="primary" disabled={!open} onClick={send}>
              Send ⏎
            </button>
          </div>
          <div className="login-keys">
            {KEYS.map((key) => (
              <button
                key={key.name}
                type="button"
                className="quiet"
                aria-label={key.name}
                disabled={!open}
                onClick={() => link.current?.input(key.data)}
              >
                {key.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
