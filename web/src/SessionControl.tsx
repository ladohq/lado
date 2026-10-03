// A session's actions (docs/design/ui.md, Launch and session control), in its head and in
// its row of the session list, by its status: Stop a session that runs (or whose tmux
// session is gone, to mark it stopped), Resume one that does not run, Forget one that is
// stopped. Stop asks in a popover, Forget in a modal window; both say first what they do,
// from the server's preview.
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";

import {
  ApiError,
  forgetSession,
  getForgetPreview,
  getStopPreview,
  stopSession,
  type ForgetPreview,
  type SessionInfo,
  type StopPreview,
} from "./api";
import { useLaunch } from "./Launch";

type Action = "stop" | "resume" | "forget";

const LABELS: Record<Action, string> = { stop: "Stop session…", resume: "Resume…", forget: "Forget…" };

// What can be done to a session of each status; the first is its main action.
function actionsOf(session: SessionInfo): Action[] {
  switch (session.status) {
    case "running":
    case "loop_down":
      return ["stop"];
    case "stopped":
      return ["resume", "forget"];
    case "tmux_gone":
      return ["resume", "stop"];
  }
}

const messageOf = (error: unknown) => (error instanceof ApiError ? error.message : String(error));

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

// Closes on Escape and on a press outside `box`.
function useDismiss(open: boolean, box: React.RefObject<HTMLElement | null>, close: () => void) {
  useEffect(() => {
    if (!open) return;
    const away = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) close();
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open, box, close]);
}

export function SessionActions({ session, place }: { session: SessionInfo; place: "head" | "row" }) {
  const launch = useLaunch();
  const actions = actionsOf(session);
  const [shown, setShown] = useState<"menu" | "stop" | "forget" | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const more = useRef<HTMLButtonElement>(null);
  const close = () => setShown(null);
  useDismiss(shown === "menu" || shown === "stop", box, close);

  const act = (action: Action) => {
    if (action === "resume") {
      setShown(null);
      launch({ kind: "resume", session });
    } else {
      setShown(action);
    }
  };

  const main = actions[0];
  return (
    <div ref={box} className={`session-actions actions-${place}${shown ? " shown" : ""}`}>
      {place === "row" ? (
        <button
          type="button"
          className="icon-button"
          aria-label={`${main === "stop" ? "Stop" : "Resume"} ${session.name}`}
          title={main === "stop" ? "Stop" : "Resume"}
          onClick={() => act(main)}
        >
          <span aria-hidden="true">{main === "stop" ? "■" : "▶"}</span>
        </button>
      ) : (
        main === "resume" && (
          <button type="button" className="primary" onClick={() => act("resume")}>
            Resume…
          </button>
        )
      )}
      <button
        ref={more}
        type="button"
        className="icon-button"
        aria-label={place === "row" ? `More actions for ${session.name}` : "Session actions"}
        aria-haspopup="menu"
        aria-expanded={shown === "menu"}
        onClick={() => setShown(shown === "menu" ? null : "menu")}
      >
        <span aria-hidden="true">⋯</span>
      </button>
      {shown === "menu" && (
        <ActionMenu
          label={place === "row" ? `Actions for ${session.name}` : "Session actions"}
          actions={actions}
          onAction={act}
          onClose={() => {
            close();
            more.current?.focus();
          }}
        />
      )}
      {shown === "stop" && <StopPopover session={session.name} onClose={close} />}
      {shown === "forget" && <ForgetDialog session={session.name} onClose={close} />}
    </div>
  );
}

function ActionMenu({
  label,
  actions,
  onAction,
  onClose,
}: {
  label: string;
  actions: Action[];
  onAction: (action: Action) => void;
  onClose: () => void;
}) {
  const menu = useRef<HTMLDivElement>(null);
  useEffect(() => {
    menu.current?.querySelector<HTMLButtonElement>("button")?.focus();
  }, []);
  return (
    <div
      ref={menu}
      role="menu"
      aria-label={label}
      className="action-menu"
      onKeyDown={(event) => {
        const items = [...(menu.current?.querySelectorAll<HTMLButtonElement>("button") ?? [])];
        const at = items.indexOf(document.activeElement as HTMLButtonElement);
        if (event.key === "Escape") {
          event.preventDefault();
          onClose();
        } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
          event.preventDefault();
          const step = event.key === "ArrowDown" ? 1 : -1;
          items[(at + step + items.length) % items.length]?.focus();
        }
      }}
    >
      {actions.map((action) => (
        <button
          key={action}
          type="button"
          role="menuitem"
          className={action === "resume" ? "" : "danger-item"}
          onClick={() => onAction(action)}
        >
          {LABELS[action]}
        </button>
      ))}
    </div>
  );
}

type Loaded<T> = { value: T } | { error: string } | null;

function usePreview<T>(load: () => Promise<T>): Loaded<T> {
  const [loaded, setLoaded] = useState<Loaded<T>>(null);
  useEffect(() => {
    let current = true;
    load().then(
      (value) => current && setLoaded({ value }),
      (error: unknown) => current && setLoaded({ error: messageOf(error) }),
    );
    return () => {
      current = false;
    };
    // Loaded once, when the question opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return loaded;
}

function stopItems(preview: StopPreview): string[] {
  const n = preview.agents.length;
  const runs = preview.open_runs.length;
  return [
    n === 0 ? "it has no agents to close" : n === 1 ? "its agent is closed" : `its ${n} agents are closed`,
    ...(preview.dropped > 0
      ? [
          preview.dropped === 1
            ? "1 message they have not got is dropped"
            : `${preview.dropped} messages they have not got are dropped`,
        ]
      : []),
    runs > 0
      ? `branches, worktrees, ${plural(runs, "open run")} and the history stay`
      : "branches, worktrees and the history stay",
    "you can resume it later",
  ];
}

function StopPopover({ session, onClose }: { session: string; onClose: () => void }) {
  const preview = usePreview(() => getStopPreview(session));
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    panel.current?.focus();
  }, []);
  const stop = async () => {
    setBusy(true);
    setRefused(null);
    try {
      await stopSession(session);
      onClose();
    } catch (error) {
      setRefused(messageOf(error));
      setBusy(false);
    }
  };
  const title = `Stop session "${session}"?`;
  return (
    <div
      ref={panel}
      role="dialog"
      aria-label={title}
      className="popover stop-popover"
      tabIndex={-1}
      onKeyDown={(event) => {
        if (event.key !== "Escape") return;
        event.preventDefault();
        onClose();
      }}
    >
      <h3>{title}</h3>
      {preview === null && <p className="muted">Loading…</p>}
      {preview !== null && "error" in preview && (
        <p className="problem" role="alert">
          {preview.error}
        </p>
      )}
      {preview !== null && "value" in preview && (
        <ul className="consequences">
          {stopItems(preview.value).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
      {refused && (
        <p className="problem" role="alert">
          {refused}
        </p>
      )}
      <div className="question-buttons">
        <button type="button" className="quiet" onClick={onClose} disabled={busy}>
          Cancel
        </button>
        <button
          type="button"
          className="danger"
          disabled={busy || preview === null || "error" in preview}
          onClick={() => void stop()}
        >
          {busy ? "Stopping…" : `Stop ${session}`}
        </button>
      </div>
    </div>
  );
}

function ForgetDialog({ session, onClose }: { session: string; onClose: () => void }) {
  const preview = usePreview<ForgetPreview>(() => getForgetPreview(session));
  const dialog = useRef<HTMLDialogElement>(null);
  const navigate = useNavigate();
  const [force, setForce] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  const found = preview !== null && "value" in preview ? preview.value : null;
  const runs = found?.open_runs ?? [];
  const forget = async () => {
    setBusy(true);
    setRefused(null);
    try {
      await forgetSession(session, runs.length > 0 && force);
      onClose();
      navigate("/sessions");
    } catch (error) {
      setRefused(messageOf(error));
      setBusy(false);
    }
  };
  const title = `Forget session "${session}"?`;
  return (
    <dialog
      ref={dialog}
      className="question-dialog"
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
      onKeyDown={(event) => {
        if (event.key !== "Escape") return;
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      <h3>{title}</h3>
      <p>Its history (messages, runs, notes, gates) is deleted. This cannot be undone.</p>
      {preview === null && <p className="muted">Loading…</p>}
      {preview !== null && "error" in preview && (
        <p className="problem" role="alert">
          {preview.error}
        </p>
      )}
      {found && found.worktrees.length > 0 && (
        <div className="left-on-disk">
          <span className="muted">Left on disk (remove them yourself if you need to):</span>
          <ul>
            {found.worktrees.map((tree) => (
              <li key={tree.path}>
                <code>{`${tree.path} · branch ${tree.branch}`}</code>
              </li>
            ))}
          </ul>
        </div>
      )}
      {runs.length > 0 && (
        <label className="switch">
          <input type="checkbox" checked={force} disabled={busy} onChange={(event) => setForce(event.target.checked)} />
          {`Also forget its ${plural(runs.length, "open run")} (${runs.join(", ")})`}
        </label>
      )}
      {refused && (
        <p className="problem" role="alert">
          {refused}
        </p>
      )}
      <div className="question-buttons">
        <button type="button" className="quiet" onClick={onClose} disabled={busy} autoFocus>
          Cancel
        </button>
        <button
          type="button"
          className="danger"
          disabled={busy || found === null || (runs.length > 0 && !force)}
          onClick={() => void forget()}
        >
          {busy ? "Forgetting…" : `Forget ${session}`}
        </button>
      </div>
    </dialog>
  );
}
