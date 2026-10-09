// The system panel and updating LADO from the UI (docs/design/ui.md, System panel): the top
// bar's `live` is a button that opens a popover about this LADO, the server, its home, tmux,
// the providers and the update check, with the system info to copy for an issue. A newer
// LADO marks `live` with `↑ X.Y.Z` and gives the panel an Update block; Update… shows the
// plan (U1), and after the human confirms, the page waits for the server, which the update
// stops and starts again (U2), then shows the update's result once (U3).
//
// The page learns how the update ended only from the server that comes back: it waits for
// a server started after the one it asked (/api/health's started_at) and a result of its
// own update (by the id the server answered) that no longer runs. A rollback ends on a
// server of the same version, so the version alone cannot tell.
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
  type RefObject,
} from "react";

import {
  ApiError,
  checkUpdateNow,
  getHealth,
  getSystem,
  getUpdate,
  getUpdatePlan,
  startUpdate,
  type Health,
  type ProviderInfo,
  type SystemInfo,
  type UpdateInfo,
  type UpdatePlan,
  type UpdateResultInfo,
} from "./api";
import { clock, day, duration } from "./ChatText";
import { CopyButton, useCopy } from "./Copy";
import { ClipboardIcon, FolderIcon } from "./icons";
import { useLive } from "./live";
import { useBelow, useDismiss } from "./Menu";
import { storeUpdateSeen, updateSeen } from "./prefs";
import { Tooltip } from "./Tooltip";
import { BUNDLE_VERSION } from "./version";

export const GITHUB = "https://github.com/ladohq/lado";
export const POLL_MS = 2000; // between two looks at the server while it restarts
export const GIVE_UP_MS = 5 * 60_000; // then the page says where the log is, and goes on looking
const RESULT_DAYS = 1; // an update's result older than this is not shown

type Link = "open" | "connecting";

// The update the page started and waits for.
export type Waiting = { id: string; to: string; before: string; log: string; since: number };

type UpdateState = {
  info: UpdateInfo | null;
  setInfo: (info: UpdateInfo) => void;
  waiting: Waiting | null;
  wait: (waiting: Waiting) => void;
};

const UpdateContext = createContext<UpdateState>({
  info: null,
  setInfo: () => {},
  waiting: null,
  wait: () => {},
});

const messageOf = (error: unknown) => (error instanceof ApiError ? error.message : String(error));

// Whether the update `waiting` is over: its result, no longer running, and a server started
// after the one before; or the same server, when the update ended before it started (a
// failed result with no log: nothing was stopped).
export function finished(waiting: Waiting, health: Health, update: UpdateInfo): boolean {
  const last = update.last;
  if (last?.id !== waiting.id || last.outcome === "running") return false;
  const notStarted = last.outcome === "failed" && last.log === null;
  return notStarted || Date.parse(health.started_at) > Date.parse(waiting.before);
}

// What the update check says and whether a newer LADO is out, asked each time the change
// feed opens (also after the server restarted), and the update the page waits for.
export function UpdateProvider({ children }: { children: ReactNode }) {
  const { link } = useLive();
  const [info, setInfo] = useState<UpdateInfo | null>(null);
  const [waiting, setWaiting] = useState<Waiting | null>(null);
  useEffect(() => {
    if (link !== "open") return;
    let current = true;
    getUpdate().then(
      (update) => current && setInfo(update),
      () => {}, // nothing to show: `lado doctor` says why
    );
    return () => {
      current = false;
    };
  }, [link]);
  useEffect(() => {
    if (!waiting) return;
    let current = true;
    const look = async () => {
      try {
        const [health, update] = await Promise.all([getHealth(), getUpdate()]);
        if (current && finished(waiting, health, update)) {
          setInfo(update);
          setWaiting(null);
        }
      } catch {
        // The server is away: look again.
      }
    };
    const timer = setInterval(() => void look(), POLL_MS);
    return () => {
      current = false;
      clearInterval(timer);
    };
  }, [waiting]);
  const wait = useCallback((started: Waiting) => setWaiting(started), []);
  return <UpdateContext.Provider value={{ info, setInfo, waiting, wait }}>{children}</UpdateContext.Provider>;
}

export const useUpdate = () => useContext(UpdateContext);

// `live` (or connecting…) as the button that opens the panel, `↑ X.Y.Z` beside it while a
// newer LADO is out.
export function LiveButton({ link }: { link: Link }) {
  const { info } = useUpdate();
  const [open, setOpen] = useState(false);
  const [asking, setAsking] = useState(false); // the plan's dialog
  const box = useRef<HTMLSpanElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open && !asking, box, close);
  const below = useBelow(box, panel, open, true);
  const available = info?.available ?? null;
  const label = available ? `System: LADO ${available} is available` : "System";
  return (
    <span ref={box} className="system">
      <Tooltip
        tip={
          available
            ? `LADO ${available} is available`
            : `The LADO server this page talks to: ${window.location.host}`
        }
      >
        <button
          ref={button}
          type="button"
          className={`link link-${link} system-button`}
          aria-label={label}
          aria-haspopup="dialog"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          {/* The feed's state is still announced as it changes. */}
          <span className="link-word" role="status">
            {link === "open" ? "live" : "connecting…"}
          </span>
          {available && <span className="update-mark">↑ {available}</span>}
        </button>
      </Tooltip>
      {open && (
        <SystemPanel
          ref={panel}
          style={below}
          onClose={() => {
            setOpen(false);
            button.current?.focus();
          }}
          onAsk={() => setAsking(true)}
        />
      )}
      {asking && (
        <UpdateDialog
          onClose={(started) => {
            setAsking(false);
            if (started) setOpen(false);
          }}
        />
      )}
    </span>
  );
}

// The day and time of the check: "09:12" today, "yesterday", else "12 Oct".
export function when(iso: string, now = new Date()): string {
  const at = new Date(iso);
  const midnight = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const days = Math.round((midnight(now) - midnight(at)) / 86_400_000);
  if (days === 0) return clock(iso);
  if (days === 1) return "yesterday";
  return day(iso);
}

// The panel's last line: the update check.
export function checkLine(info: UpdateInfo, now = new Date()): { text: string; tip?: string } {
  if (info.checked_at === null) return { text: "No update check (LADO_NO_UPDATE_CHECK=1)" };
  const at = when(info.checked_at, now);
  if (info.error) return { text: `Check failed · ${at}`, tip: info.error };
  const checked = `checked ${at}`;
  return { text: info.available ? checked : `Up to date · ${checked}` };
}

// The browser and its OS from the user agent, the line the page adds to the report.
export function browserLine(agent: string): string {
  const found = [
    ["Edge", /Edg\/(\d+)/],
    ["Firefox", /Firefox\/(\d+)/],
    ["Chrome", /Chrome\/(\d+)/],
    ["Safari", /Version\/(\d+)[\d.]*.*Safari/],
  ] as const;
  const browser = found
    .map(([name, pattern]) => {
      const match = pattern.exec(agent);
      return match ? `${name} ${match[1]}` : null;
    })
    .find((one) => one !== null);
  const os = /iPhone|iPad/.test(agent)
    ? "iOS"
    : /Android/.test(agent)
      ? "Android"
      : /Mac OS X/.test(agent)
        ? "macOS"
        : /Windows/.test(agent)
          ? "Windows"
          : /Linux/.test(agent)
            ? "Linux"
            : "an unknown OS";
  return `- Browser: ${browser ?? "unknown"} on ${os}`;
}

// A home folder shown with `~`.
export const shortHome = (path: string) => path.replace(/^\/(Users|home)\/[^/]+(?=\/|$)/, "~");

function SystemPanel({
  ref: box,
  style,
  onClose,
  onAsk,
}: {
  ref: RefObject<HTMLDivElement | null>;
  style?: CSSProperties;
  onClose: () => void;
  onAsk: () => void;
}) {
  const { info, setInfo } = useUpdate();
  const [system, setSystem] = useState<SystemInfo | { error: string } | null>(null);
  const [checking, setChecking] = useState(false);
  const { note, copy } = useCopy();
  useEffect(() => {
    box.current?.focus();
    let current = true;
    getSystem().then(
      (found) => current && setSystem(found),
      (error: unknown) => current && setSystem({ error: messageOf(error) }),
    );
    return () => {
      current = false;
    };
    // Loaded once, when the panel opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const checkNow = async () => {
    setChecking(true);
    try {
      setInfo(await checkUpdateNow());
    } catch {
      // The line keeps what it said; the check's own failure comes in its answer.
    } finally {
      setChecking(false);
    }
  };
  const facts = system !== null && "version" in system ? system : null;
  const version = facts?.version ?? info?.current ?? BUNDLE_VERSION;
  const line = info ? checkLine(info) : null;
  return (
    <div
      ref={box}
      role="dialog"
      aria-label="System"
      className="popover system-panel"
      style={style}
      tabIndex={-1}
      onKeyDown={(event) => {
        if (event.key !== "Escape") return;
        event.preventDefault();
        onClose();
      }}
    >
      <header className="system-head">
        <strong>LADO {version}</strong>
        <span className="system-links">
          <span role="status" className="row-note">
            {note}
          </span>
          <Tooltip tip="Copy system info for an issue">
            <button
              type="button"
              className="icon-button"
              aria-label="Copy system info"
              disabled={!facts}
              onClick={() =>
                facts && void copy(`${facts.report}${browserLine(navigator.userAgent)}\n`, "System info copied")
              }
            >
              <ClipboardIcon />
            </button>
          </Tooltip>
          <a href={GITHUB} target="_blank" rel="noreferrer">
            GitHub ↗
          </a>
        </span>
      </header>
      {info?.available && <UpdateBlock info={info} onAsk={onAsk} />}
      {system !== null && "error" in system && (
        <p className="problem" role="alert">
          {system.error}
        </p>
      )}
      <dl className="system-facts">
        <dt>Server</dt>
        <dd>{window.location.origin}</dd>
        {facts && <Running since={facts.started_at} />}
        {facts && (
          <>
            <dt>Home</dt>
            <dd className="system-home">
              <CopyButton
                label="Copy path"
                copied="Path copied"
                text={facts.home}
                field={{ title: "Path of LADO's home", label: "Path" }}
                icon={<FolderIcon />}
              />
              <span title={facts.home}>{shortHome(facts.home)}</span>
            </dd>
            <dt>tmux</dt>
            <dd>
              {facts.tmux.version} · socket {facts.tmux.socket}
            </dd>
            {facts.gui_session && (
              <>
                <dt>Graphical session</dt>
                <dd>
                  process {facts.gui_session.process} ·{" "}
                  {facts.gui_session.server ? `server ${facts.gui_session.server}` : "no tmux server"}
                </dd>
              </>
            )}
          </>
        )}
      </dl>
      {facts === null && system === null && <p className="muted">Loading…</p>}
      {facts && (
        <section className="system-providers" aria-label="Providers">
          <h4>Providers</h4>
          <ul>
            {facts.providers.map((provider) => (
              <ProviderRow key={provider.name} provider={provider} />
            ))}
          </ul>
        </section>
      )}
      {line && (
        <p className="system-check">
          {checking ? (
            <span>Checking…</span>
          ) : line.tip ? (
            <Tooltip tip={line.tip}>
              <span tabIndex={0}>{line.text}</span>
            </Tooltip>
          ) : (
            <span>{line.text}</span>
          )}
          {info?.checked_at !== null && (
            <button
              type="button"
              className="link-button"
              aria-label="Check for a newer LADO now"
              disabled={checking}
              onClick={() => void checkNow()}
            >
              ↻
            </button>
          )}
        </p>
      )}
    </div>
  );
}

function Running({ since }: { since: string }) {
  const seconds = (Date.now() - Date.parse(since)) / 1000;
  return (
    <>
      <dt>Running</dt>
      <dd>
        <Tooltip tip={`since ${new Date(since).toLocaleString()}`}>
          <span tabIndex={0}>{duration(seconds, true)}</span>
        </Tooltip>
      </dd>
    </>
  );
}

function ProviderRow({ provider }: { provider: ProviderInfo }) {
  const tone = !provider.installed ? "off" : provider.warning ? "warn" : "ok";
  const detail = !provider.installed
    ? "not installed"
    : provider.warning
      ? `${provider.version} · tested ${provider.tested_version}`
      : provider.version || provider.detail;
  return (
    <li>
      <span className={`provider-dot provider-${tone}`} aria-hidden="true" />
      <span>{provider.title}</span>
      <small title={provider.warning || undefined}>{detail}</small>
    </li>
  );
}

// A newer LADO (P2), or why this one cannot update itself here (P3: by hand).
function UpdateBlock({ info, onAsk }: { info: UpdateInfo; onAsk: () => void }) {
  const version = info.available!;
  const released = info.released ? ` · ${new Date(`${info.released}T12:00:00`).toLocaleDateString([], { day: "numeric", month: "short" })}` : "";
  const notes = `${GITHUB}/releases/tag/v${version}`;
  return (
    <section className="system-update" aria-label="Update">
      <div className="system-update-row">
        <span>
          <strong>{version}</strong> is out<span className="muted">{released}</span>
          <br />
          <a href={notes} target="_blank" rel="noreferrer">
            What's new
          </a>
        </span>
        {info.can_update && (
          <button type="button" className="primary" onClick={onAsk}>
            Update…
          </button>
        )}
      </div>
      {!info.can_update && info.why_not && <p className="system-why">{info.why_not}.</p>}
      {!info.can_update && info.by_hand.length > 0 && (
        <div className="system-by-hand">
          <span>By hand:</span>
          <CopyButton
            label="Copy commands"
            copied="Commands copied"
            text={info.by_hand.join("\n")}
            field={{ title: "Commands that update LADO", label: "Commands" }}
            icon={<ClipboardIcon />}
          />
          <pre className="log">{info.by_hand.join("\n")}</pre>
        </div>
      )}
    </section>
  );
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

// U1: the plan `lado update` would print, then the update.
function UpdateDialog({ onClose }: { onClose: (started: boolean) => void }) {
  const { wait } = useUpdate();
  const dialog = useRef<HTMLDialogElement>(null);
  const [plan, setPlan] = useState<UpdatePlan | { error: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  useEffect(() => {
    dialog.current?.showModal();
    let current = true;
    getUpdatePlan().then(
      (found) => current && setPlan(found),
      (error: unknown) => current && setPlan({ error: messageOf(error) }),
    );
    return () => {
      current = false;
    };
  }, []);
  const found = plan !== null && "to" in plan ? plan : null;
  const update = async () => {
    if (!found) return;
    setBusy(true);
    setRefused(null);
    try {
      const before = (await getHealth()).started_at;
      const started = await startUpdate(found.to);
      wait({ id: started.id, to: found.to, before, log: started.log, since: Date.now() });
      onClose(true);
    } catch (error) {
      setRefused(messageOf(error));
      setBusy(false);
    }
  };
  const title = found ? `Update LADO ${found.from} → ${found.to}?` : "Update LADO?";
  return (
    <dialog
      ref={dialog}
      className="question-dialog update-dialog"
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose(false);
      }}
    >
      <h3>{title}</h3>
      {plan === null && <p className="muted">Loading…</p>}
      {plan !== null && "error" in plan && (
        <p className="problem" role="alert">
          {plan.error}
        </p>
      )}
      {found && (
        <>
          {found.downgrade && (
            <p className="problem">An older LADO may refuse lado.db (it says so when it starts).</p>
          )}
          {(found.sessions.length > 0 || found.server) && (
            <>
              <p className="muted">To restart:</p>
              <ul className="update-restarts">
                {found.sessions.map((sess) => (
                  <li key={sess.name}>
                    session <strong>{sess.name}</strong>:{" "}
                    {sess.agents.length > 0
                      ? sess.agents.map((agent) => `${agent.name} ${agent.status}`).join(", ")
                      : "no agents"}
                    {sess.open_runs > 0 ? ` · ${plural(sess.open_runs, "open run")}` : ""}
                  </li>
                ))}
                {found.server && <li>this UI server</li>}
              </ul>
            </>
          )}
          {found.sessions.length > 0 && (
            <p className="muted">
              Busy agents lose their current turn. Runs, gates, branches and worktrees stay; each supervisor
              starts a new conversation and gets what its open runs wait for.
            </p>
          )}
          {found.gone.map((sess) => (
            <p key={sess.name} className="muted">
              Not running, its tmux session is gone: {sess.name}; resume it with <code>{sess.command}</code>
            </p>
          ))}
          {found.agents_note && <p className="muted">{found.agents_note}</p>}
        </>
      )}
      {refused && (
        <p className="problem" role="alert">
          {refused}
        </p>
      )}
      <div className="question-buttons">
        <button type="button" className="quiet" onClick={() => onClose(false)} disabled={busy}>
          Cancel
        </button>
        <button type="button" className="danger" disabled={busy || !found} onClick={() => void update()}>
          {busy ? "Starting…" : "Restart and update"}
        </button>
      </div>
    </dialog>
  );
}

// U2 while the page waits for the server, then U3: the latest update's result, once.
export function UpdateStatus() {
  const { info, waiting } = useUpdate();
  const [seen, setSeen] = useState(updateSeen);
  if (waiting) return <UpdateWait waiting={waiting} />;
  const last = info?.last;
  if (!last || last.outcome === "running" || last.problem || !last.ended_at) return null;
  if (resultKey(last) === seen) return null;
  if (Date.now() - Date.parse(last.ended_at) > RESULT_DAYS * 86_400_000) return null;
  const dismiss = () => {
    storeUpdateSeen(resultKey(last));
    setSeen(resultKey(last));
  };
  return <UpdateResult last={last} onDismiss={dismiss} />;
}

const resultKey = (last: UpdateResultInfo) => last.id ?? last.started_at;

function UpdateWait({ waiting }: { waiting: Waiting }) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const elapsed = Math.max(0, Math.floor((now - waiting.since) / 1000));
  const clock = `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}`;
  return (
    <section className="update-banner update-wait" role="status" aria-label="Updating LADO">
      <strong>Updating to {waiting.to}</strong>
      <p>
        The server is restarting · <span className="update-clock">{clock}</span>
      </p>
      <p className="muted">
        The update stops the sessions and this server, installs {waiting.to}, then brings them back. The page
        reconnects by itself.
      </p>
      {now - waiting.since >= GIVE_UP_MS && (
        <p className="problem">
          The server did not come back. See <code>{waiting.log}</code>; start it with <code>lado ui</code>.
        </p>
      )}
    </section>
  );
}

function UpdateResult({ last, onDismiss }: { last: UpdateResultInfo; onDismiss: () => void }) {
  const good = last.outcome === "ok";
  const database =
    last.database === "restored"
      ? "lado.db was restored from its backup."
      : last.database === "kept"
        ? "lado.db is as it was."
        : null;
  const said: Record<string, string> = {
    ok: `LADO ${last.to} is ready.`,
    partial: `LADO ${last.to} runs, but ${plural(last.sessions_failed.length, "session")} did not resume.`,
    failed: `The update to ${last.to} failed: ${last.reason}. LADO ${last.from} runs.`,
    rolled_back: `The update to ${last.to} failed: ${last.reason}. Rolled back to LADO ${last.from}.`,
    rollback_failed: `The update to ${last.to} failed, and so did the rollback: ${last.reason}.`,
  };
  return (
    <section
      className={`update-banner update-result ${good ? "update-good" : "update-bad"}`}
      role={good ? "status" : "alert"}
      aria-label="Update result"
    >
      <p>
        <span aria-hidden="true">{good ? "✓ " : "✕ "}</span>
        {said[last.outcome] ?? `The update to ${last.to} ended: ${last.outcome}.`}
        {!good && database && ` ${database}`}
      </p>
      {last.sessions_failed.length > 0 && (
        <ul>
          {last.sessions_failed.map((sess) => (
            <li key={sess.name}>
              {sess.name}: resume it with <code>{sess.command}</code>
            </li>
          ))}
        </ul>
      )}
      {!good && last.tail.length > 0 && (
        <pre className="log">
          {last.tail.join("\n")}
          {last.log ? `\n… full log: ${last.log}` : ""}
        </pre>
      )}
      <button type="button" className="quiet" onClick={onDismiss}>
        Dismiss
      </button>
    </section>
  );
}
