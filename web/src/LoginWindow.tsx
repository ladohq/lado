// The login window of Settings → Providers and environment (docs/design/ui.md), for a CLI that
// logs in by its own command (OpenCode, Kilo, Codex's sign-in code; LoginSheet.tsx opens it):
// a sheet over the page (the whole screen on a phone) with the terminal of the CLI's own login
// command, always in control, over the agents' terminal protocol (terminalLink.ts). A link in
// it, also one wrapped over lines, opens in a new tab (xterm's web links addon). Under it the
// action's help line, "Text to send", which sends its text and Enter as one input (a code, a
// key), and the keys ↑ ↓ Enter Esc for menus, so it works from a phone. When the command ends
// the socket closes for good and the sheet goes (`onEnded`); Close ends the command first.
//
// For an action that shows a code (`showsCode`: Codex's sign-in code) the terminal stays
// hidden: the window waits for the socket's `prompt` frame (the link and the code the
// provider read from the command's output) and shows two steps, "Open sign-in page" and the
// code with "Copy code" (Copy.tsx: also over plain http), the CLI's own lines, and on a
// computer a QR code of the link. When the command ends with another status than 0 (the
// `ended` frame) the window stays with the CLI's last words, "Get a new code" (`onRetry`) and
// "Back" (`onBack`). Without a prompt within FALLBACK_MS the terminal shows after all.
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

import { closeLogin } from "./api";
import { CopyButton } from "./Copy";
import { CopyIcon, OpenTabIcon } from "./icons";
import { QrCode } from "./QrCode";
import { loginTerminalUrl, TermLink, type LinkState } from "./terminalLink";

// What each key sends to the terminal, as a keyboard's would.
export const KEYS: { label: string; name: string; data: string }[] = [
  { label: "↑", name: "Up", data: "\x1b[A" },
  { label: "↓", name: "Down", data: "\x1b[B" },
  { label: "Enter", name: "Enter", data: "\r" },
  { label: "Esc", name: "Escape", data: "\x1b" },
];

export const FALLBACK_MS = 10_000; // without a prompt by then, the terminal shows

const HELP = "Open the link, sign in, then send what it gives you (a code) from here.";

// The socket's frames of a login window (lado.server.terminals.serve_login).
type Prompt = { link: string; code: string; expires: string; lines: string[] };
type Ended = { status: number | null; said: string };

export function LoginWindow({
  provider,
  title,
  help,
  extra,
  showsCode = false,
  onEnded,
  onRetry,
  onBack,
}: {
  provider: string;
  title: string;
  help?: string; // the action's own line (Codex's sign-in code needs nothing sent back)
  extra?: ReactNode; // in the header, before Close (LoginSheet's "Log out of one…")
  showsCode?: boolean; // the action's window shows a code, not a terminal
  onEnded: () => void;
  onRetry?: () => void; // "Get a new code": the action again
  onBack?: () => void; // "Back": the sheet's choices
}) {
  const id = useId();
  const box = useRef<HTMLDivElement>(null);
  const link = useRef<TermLink | null>(null);
  const [state, setState] = useState<LinkState>({ phase: "connecting", reason: null });
  const [text, setText] = useState("");
  const [closing, setClosing] = useState(false);
  const [prompt, setPrompt] = useState<Prompt | null>(null);
  const [failed, setFailed] = useState<Ended | null>(null);
  const [fallback, setFallback] = useState(false);
  const ended = useRef(onEnded);
  ended.current = onEnded;
  const end = useRef<Ended | null>(null); // the last `ended` frame
  const codes = useRef(showsCode);
  codes.current = showsCode;

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
      frame: (frame) => {
        if (frame.type === "prompt" && typeof frame.link === "string" && frame.link.startsWith("https://")) {
          setPrompt(frame as unknown as Prompt);
        } else if (frame.type === "ended") end.current = frame as unknown as Ended;
      },
      state: (now) => {
        setState(now);
        if (now.phase === "open") resize();
        if (now.phase !== "closed") return;
        // The command ended, or Close: a code window's failure stays to be read.
        const last = end.current;
        if (codes.current && last && last.status !== 0) setFailed(last);
        else ended.current();
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

  useEffect(() => {
    if (!showsCode || prompt) return;
    const timer = setTimeout(() => setFallback(true), FALLBACK_MS);
    return () => clearTimeout(timer);
  }, [showsCode, prompt]);

  const terminal = !showsCode || (fallback && !prompt); // once shown, ResizeObserver fits it

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
          {state.phase !== "open" && !failed && <span className="muted login-link">{state.reason ?? "connecting…"}</span>}
          {extra}
          <button type="button" className="quiet" disabled={closing} onClick={close}>
            Close
          </button>
        </div>
        {failed ? (
          <Failed title={title} said={failed.said} onRetry={onRetry} onBack={onBack} />
        ) : (
          showsCode &&
          (prompt ? (
            <Steps prompt={prompt} />
          ) : fallback ? (
            <p className="login-note">{`LADO could not find the link and the code in ${title}'s output; here is ${title}'s own window.`}</p>
          ) : (
            <p className="login-wait">
              <span className="login-spin" aria-hidden="true" />
              {`Asking ${title} for a sign-in code…`}
            </p>
          ))
        )}
        <div className="login-term" ref={box} data-link={state.phase} hidden={!terminal || failed !== null} />
        {!failed && (
          <div className="login-help">
            <p className="muted">{help || HELP}</p>
            {terminal && (
              <>
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
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// The two steps of a sign-in code, the CLI's own lines under them; the QR code of the link
// beside them on a computer (styles.css hides it at a phone's width).
function Steps({ prompt }: { prompt: Prompt }) {
  return (
    <>
      <div className="login-steps">
        <ol className="login-step-list">
          <li className="login-step">
            <span className="login-n">1</span>
            <div className="login-step-body">
              <span>Open the sign-in page and sign in to ChatGPT</span>
              <div className="login-row">
                <a className="primary login-open" href={prompt.link} target="_blank" rel="noopener noreferrer">
                  <OpenTabIcon />
                  Open sign-in page
                </a>
                <span className="muted login-url">{prompt.link.replace(/^https:\/\//, "")}</span>
              </div>
            </div>
          </li>
          <li className="login-step">
            <span className="login-n">2</span>
            <div className="login-step-body">
              <span>
                Enter this one-time code there{prompt.expires && " "}
                {prompt.expires && <span className="muted">{`(${prompt.expires})`}</span>}
              </span>
              <div className="login-row">
                <code className="login-code">{prompt.code}</code>
                <CopyButton
                  label="Copy code"
                  copied="Code copied"
                  text={prompt.code}
                  field={{ title: "Sign-in code", label: "Code" }}
                  icon={<CopyIcon />}
                  className="login-copy"
                  named
                />
              </div>
            </div>
          </li>
        </ol>
        <div className="login-qr">
          <QrCode text={prompt.link} label="QR code of the sign-in page" className="login-qr-code" />
          <span className="muted">Or scan it with your phone</span>
        </div>
      </div>
      {prompt.lines.length > 0 && (
        <div className="login-details">
          {prompt.lines.map((line, i) => (
            <p key={i}>{line}</p>
          ))}
        </div>
      )}
    </>
  );
}

function Failed({ title, said, onRetry, onBack }: { title: string; said: string; onRetry?: () => void; onBack?: () => void }) {
  return (
    <div className="login-fail" role="alert">
      <b>{`${title} did not sign you in`}</b>
      {said && (
        <>
          <span className="muted">{`What ${title} said:`}</span>
          <blockquote>{said}</blockquote>
        </>
      )}
      <div className="login-row">
        {onRetry && (
          <button type="button" className="primary" onClick={onRetry}>
            Get a new code
          </button>
        )}
        {onBack && (
          <button type="button" className="quiet" onClick={onBack}>
            Back
          </button>
        )}
      </div>
    </div>
  );
}
