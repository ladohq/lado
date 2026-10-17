// Forget stopped sessions (docs/design/ui.md, Launch and session control): the window the
// Stopped band opens, the single Forget's window for many. It lists the sessions it is given,
// fixed while it is open, each ticked; loads each one's forget preview; and forgets the
// counted ones one after another through the single Forget's API, so the core decides each,
// reporting each. A session with open runs goes only with the switch on, as in the single
// Forget; one whose preview is refused cannot be ticked.
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";

import { forgetSession, getForgetPreview, type ForgetPreview, type SessionInfo } from "./api";
import { since } from "./ChatText";
import { messageOf, plural } from "./SessionControl";
import { label } from "./sessionLabel";

type Preview = { value: ForgetPreview } | { error: string };

// A forgotten session, the core's reason it was not, or the one being forgotten now.
type Outcome = "forgotten" | "working" | { error: string };

// "a", "a and b", "a, b and c".
const joined = (names: string[]) =>
  names.length < 2 ? names.join("") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;

export function ForgetManyDialog({ sessions, onClose }: { sessions: SessionInfo[]; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const navigate = useNavigate();
  const current = useParams().name;
  const [previews, setPreviews] = useState<Record<string, Preview>>({});
  const [ticked, setTicked] = useState(() => new Set(sessions.map((one) => one.name)));
  const [force, setForce] = useState(false);
  // The sessions pressed for, in order, and how each ended; null before the press.
  const [run, setRun] = useState<string[] | null>(null);
  const [outcomes, setOutcomes] = useState<Record<string, Outcome>>({});
  const [finished, setFinished] = useState(false);

  useEffect(() => {
    dialog.current?.showModal();
    let shown = true;
    for (const { name } of sessions)
      getForgetPreview(name).then(
        (value) => shown && setPreviews((all) => ({ ...all, [name]: { value } })),
        (error: unknown) => shown && setPreviews((all) => ({ ...all, [name]: { error: messageOf(error) } })),
      );
    return () => {
      shown = false;
    };
    // Loaded once, for the sessions the window opened with.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const found = (name: string) => {
    const preview = previews[name];
    return preview && "value" in preview ? preview.value : null;
  };
  const refusal = (name: string) => {
    const preview = previews[name];
    return preview && "error" in preview ? preview.error : null;
  };
  const runsOf = (name: string) => found(name)?.open_runs.length ?? 0;
  const tickable = sessions.filter((one) => refusal(one.name) === null);
  const chosen = tickable.filter((one) => ticked.has(one.name));
  const withRuns = chosen.filter((one) => runsOf(one.name) > 0).map((one) => one.name);
  const counted = chosen.filter((one) => found(one.name) !== null && (runsOf(one.name) === 0 || force));
  const loading = sessions.some((one) => previews[one.name] === undefined);
  const leftBy = chosen.filter((one) => (found(one.name)?.worktrees.length ?? 0) > 0);
  const trees = leftBy.flatMap((one) => found(one.name)!.worktrees);
  const busy = run !== null && !finished;
  const all = tickable.length > 0 && chosen.length === tickable.length;

  const tick = (name: string, on: boolean) =>
    setTicked((before) => {
      const next = new Set(before);
      if (on) next.add(name);
      else next.delete(name);
      return next;
    });

  const forget = async () => {
    const names = counted.map((one) => one.name);
    setRun(names);
    const gone: string[] = [];
    for (const name of names) {
      setOutcomes((before) => ({ ...before, [name]: "working" }));
      try {
        await forgetSession(name, force && runsOf(name) > 0);
        gone.push(name);
        setOutcomes((before) => ({ ...before, [name]: "forgotten" }));
      } catch (error) {
        setOutcomes((before) => ({ ...before, [name]: { error: messageOf(error) } }));
      }
    }
    if (current !== undefined && gone.includes(current)) navigate("/sessions");
    if (gone.length === names.length) onClose();
    else setFinished(true);
  };

  const shown = run === null ? sessions : sessions.filter((one) => run.includes(one.name));
  const step = run === null ? 0 : run.findIndex((name) => outcomes[name] === "working") + 1;
  const title = "Forget stopped sessions?";
  return (
    <dialog
      ref={dialog}
      className="question-dialog forget-many"
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
      <p>Their history (messages, runs, notes, gates) is deleted. This cannot be undone.</p>
      <div className="forget-many-list">
        {run === null && (
          <label className="forget-many-all">
            <input
              type="checkbox"
              checked={all}
              disabled={tickable.length === 0}
              onChange={() => setTicked(new Set(all ? [] : tickable.map((one) => one.name)))}
            />
            <b>{`All ${sessions.length}`}</b>
          </label>
        )}
        <ul>
          {shown.map((session) => {
            const { name } = session;
            const runs = runsOf(name);
            const outcome = outcomes[name];
            const reason = refusal(name) ?? (typeof outcome === "object" ? outcome.error : null);
            const about = session.stopped_at ? `stopped ${since(session.stopped_at)} ago` : "stopped";
            const text = (
              <>
                <span className="forget-many-name">{label(session)}</span>{" "}
                <span className="muted">{session.title === null ? about : `${name} · ${about}`}</span>
                {runs > 0 && <span className="forget-many-runs">{plural(runs, "open run")}</span>}
              </>
            );
            return (
              <li key={name} className={outcome === "forgotten" ? "done" : reason ? "failed" : undefined}>
                {run === null ? (
                  <label>
                    <input
                      type="checkbox"
                      checked={ticked.has(name) && refusal(name) === null}
                      disabled={refusal(name) !== null}
                      onChange={(event) => tick(name, event.target.checked)}
                    />
                    {text}
                  </label>
                ) : (
                  <span className="forget-many-row">
                    <span className="forget-many-mark" aria-hidden="true">
                      {outcome === "forgotten" ? "✓" : outcome === "working" ? "…" : reason ? "✕" : ""}
                    </span>
                    <span className="forget-many-name">{label(session)}</span>{" "}
                    {outcome === "forgotten" && <span className="muted">forgotten</span>}
                    {outcome === "working" && <span className="muted">forgetting…</span>}
                  </span>
                )}
                {reason && <span className="forget-many-reason">{reason}</span>}
              </li>
            );
          })}
        </ul>
      </div>
      {run === null && trees.length > 0 && (
        <details className="left-on-disk">
          <summary className="muted">
            {`Left on disk: ${plural(trees.length, "worktree")} of ${plural(leftBy.length, "session")} (remove them yourself if you need to)`}
          </summary>
          <ul>
            {trees.map((tree) => (
              <li key={tree.path}>
                <code>{`${tree.path} · branch ${tree.branch}`}</code>
              </li>
            ))}
          </ul>
        </details>
      )}
      {run === null && withRuns.length > 0 && (
        <>
          <label className="switch">
            <input type="checkbox" checked={force} onChange={(event) => setForce(event.target.checked)} />
            {`Also forget their ${plural(
              withRuns.reduce((sum, name) => sum + runsOf(name), 0),
              "open run",
            )} (${withRuns.join(", ")})`}
          </label>
          {!force && <p className="muted forget-many-stay">{`While this is off, ${joined(withRuns)} stay.`}</p>}
        </>
      )}
      <div className="question-buttons">
        {finished ? (
          <button type="button" className="quiet" onClick={onClose} autoFocus>
            Close
          </button>
        ) : (
          <>
            <button type="button" className="quiet" onClick={onClose} disabled={busy} autoFocus>
              Cancel
            </button>
            <button
              type="button"
              className="danger"
              disabled={busy || loading || counted.length === 0}
              onClick={() => void forget()}
            >
              {busy ? `Forgetting ${step} of ${run!.length}…` : `Forget ${plural(counted.length, "session")}`}
            </button>
          </>
        )}
      </div>
    </dialog>
  );
}
