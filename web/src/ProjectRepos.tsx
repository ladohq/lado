// The project's page's repositories and sessions (docs/design/ui.md, Projects): the
// repositories as the server reads them from the disk, each with Start session and Delete;
// Add repository, a clone (the same clone job as New session's) or one from scratch; Delete
// repository after its preview; the project's sessions from the change feed. Every rule is
// the core's: the dialogs show its refusals as they come.
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router";

import {
  addProjectRepo,
  getProject,
  getRemoteBranches,
  getRepoRemoval,
  removeProjectRepo,
  type CloneRefused,
  type ProjectInfo,
  type RemoteInfo,
  type RepoRemoval,
  type SessionInfo,
} from "./api";
import { since } from "./ChatText";
import { useCloneJob, type CloneEnd } from "./cloneJob";
import { BRANCHES_DEBOUNCE, CloneProgress, cloneRefused, defaultBranch, FolderHint, useDebounced, useLaunch } from "./Launch";
import { useLive } from "./live";
import { sessionPath } from "./paths";
import { messageOf } from "./SessionControl";
import { StatusDot } from "./Sessions";

// The block Repositories, with the two dialogs it opens. `onAdded` reads the project anew;
// `onChanged` shows the project a removal answered.
export function ProjectRepos({
  project,
  onAdded,
  onChanged,
}: {
  project: ProjectInfo;
  onAdded: () => void;
  onChanged: (project: ProjectInfo) => void;
}) {
  const launch = useLaunch();
  const heading = useId();
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);
  const empty = project.repos.length === 0;
  const add = (primary: boolean) => (
    <button type="button" className={`${primary ? "primary" : "quiet"} project-add`} onClick={() => setAdding(true)}>
      + Add repository
    </button>
  );
  return (
    <section className="project-section" aria-labelledby={heading}>
      <div className="project-section-head">
        <h3 id={heading}>Repositories</h3>
        {!empty && add(false)}
      </div>
      {empty ? (
        <>
          <p className="project-empty-repos">
            No repositories yet. A session works in one of the project's repositories: clone one or start one from
            scratch.
          </p>
          {add(true)}
        </>
      ) : (
        <>
          <p className="muted">Git folders in the project's folder, read from the disk. Each session works in one of them.</p>
          <table className="project-repos">
            <tbody>
              {project.repos.map((repo) => (
                <tr key={repo.name}>
                  <td>
                    <span className="repo-name">{repo.name}</span>
                    <span className="repo-about">
                      {repo.branch === null ? (
                        "detached HEAD"
                      ) : (
                        <>
                          branch <b>{repo.branch}</b>
                        </>
                      )}{" "}
                      · {repo.remote === null ? "no remote" : <code>{repo.remote}</code>}
                    </span>
                  </td>
                  <td className="project-acts">
                    <button
                      type="button"
                      className="quiet"
                      onClick={() => launch({ kind: "new", project: project.id, repo: repo.name })}
                    >
                      Start session
                    </button>
                    <button type="button" className="quiet" onClick={() => setRemoving(repo.name)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {adding && (
        <AddRepoDialog
          project={project}
          onClose={() => setAdding(false)}
          onAdded={() => {
            setAdding(false);
            onAdded();
          }}
        />
      )}
      {removing !== null && (
        <DeleteRepoDialog
          project={project}
          name={removing}
          onClose={() => setRemoving(null)}
          onRemoved={(after) => {
            setRemoving(null);
            onChanged(after);
          }}
        />
      )}
    </section>
  );
}

// The block Sessions: the feed's sessions of the project, running ones first (the latest
// started first), then the rest (the latest stopped first); each its mark, its title as a
// link, its name beside a title, its repository (its folder's last part) and its time.
export function ProjectSessions({ id }: { id: string }) {
  const heading = useId();
  const loaded = useLive().sessions;
  const all = loaded && "sessions" in loaded ? loaded.sessions : [];
  const mine = all.filter((one) => one.project === id);
  const running = mine.filter((one) => one.status !== "stopped").sort(latest((one) => one.running_since));
  const stopped = mine.filter((one) => one.status === "stopped").sort(latest((one) => one.stopped_at));
  return (
    <section className="project-section" aria-labelledby={heading}>
      <div className="project-section-head">
        <h3 id={heading}>Sessions</h3>
      </div>
      {mine.length === 0 ? (
        <p className="muted">No sessions in this project yet.</p>
      ) : (
        <>
          <p className="muted">Sessions started in this project, running first.</p>
          <ul className="project-sessions">
            {[...running, ...stopped].map((one) => (
              <SessionItem key={one.name} session={one} />
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

const latest = (at: (session: SessionInfo) => string | null) => (a: SessionInfo, b: SessionInfo) =>
  (at(b) ?? "").localeCompare(at(a) ?? "");

function SessionItem({ session }: { session: SessionInfo }) {
  const repo = session.repo.split("/").filter(Boolean).pop() ?? session.repo;
  const when =
    session.status === "stopped"
      ? session.stopped_at && `stopped ${since(session.stopped_at)} ago`
      : session.running_since && `running ${since(session.running_since)}`;
  return (
    <li>
      <StatusDot session={session} />
      <Link to={sessionPath(session.name)}>{session.title ?? session.name}</Link>
      <span className="muted">{session.title === null ? repo : `${session.name} · ${repo}`}</span>
      {when && <span className="when">{when}</span>}
    </li>
  );
}

type Source = "url" | "scratch";

// A refusal of the dialog's request: its text, and the core's hint when it gives one.
type Refusal = { message: string; hint: CloneRefused["hint"] };

const refusalOf = (error: unknown): Refusal => {
  const why = error && typeof error === "object" && "detail" in error ? cloneRefused(error.detail) : null;
  return { message: why?.message ?? messageOf(error), hint: why?.hint ?? null };
};

// Add a repository: Clone from URL (Git URL, Name from the URL until edited, Branch from the
// remote) or From scratch (Name). The clone runs as New session's does, and while it runs
// the dialog does not close (Esc, Cancel) but by Cancel clone. On success it closes; the
// page shows the repository. It starts no session (#1282).
function AddRepoDialog({
  project,
  onClose,
  onAdded,
}: {
  project: ProjectInfo;
  onClose: () => void;
  onAdded: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const ids = useId();
  const clone = useCloneJob();
  const [source, setSource] = useState<Source>("url");
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [nameEdited, setNameEdited] = useState(false);
  const [picked, setPicked] = useState<{ url: string; branch: string } | null>(null);
  const [listed, setListed] = useState<{ url: string; remote: RemoteInfo } | { url: string; failed: Refusal } | null>(
    null,
  );
  const [refused, setRefused] = useState<Refusal | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const running = clone.job !== null;
  const title = project.title ?? project.id;

  useEffect(() => {
    dialog.current?.showModal();
  }, []);

  // The remote's branches, asked once the URL stops changing; an answer counts only for the
  // URL as it is.
  const typedUrl = url.trim();
  const asked = useDebounced(typedUrl, BRANCHES_DEBOUNCE);
  useEffect(() => {
    if (source !== "url" || asked === "") return;
    let current = true;
    getRemoteBranches(asked).then(
      (remote) => current && setListed({ url: asked, remote }),
      (error: unknown) => current && setListed({ url: asked, failed: refusalOf(error) }),
    );
    return () => {
      current = false;
    };
  }, [asked, source]);
  const shown = listed?.url === typedUrl ? listed : null;
  const remote = shown && "remote" in shown ? shown.remote : null;
  useEffect(() => {
    if (!nameEdited && remote) setName(remote.repo_name ?? "");
  }, [remote, nameEdited]);
  const branch = remote
    ? picked?.url === typedUrl && remote.branches.includes(picked.branch)
      ? picked.branch
      : defaultBranch(remote)
    : null;

  const typedName = name.trim();
  const off = busy || running;
  const ready = !off && typedName !== "" && (source === "scratch" || (remote !== null && branch !== null));

  const ended = (end: CloneEnd) => {
    if ("done" in end || end.ended === "away") return onAdded(); // the clone is there
    if (end.ended === "left") return;
    setBusy(false);
    if (end.ended === "gone") setRefused(refusalOf(end.error));
    else if (end.job.error) setRefused({ message: end.job.error.message, hint: end.job.error.hint });
    else setNote("the clone was cancelled");
  };

  const submit = async () => {
    if (!ready) return;
    setBusy(true);
    setRefused(null);
    setNote(null);
    if (source === "scratch") {
      try {
        await addProjectRepo(project.id, typedName);
      } catch (error) {
        setRefused(refusalOf(error));
        setBusy(false);
        return;
      }
      onAdded();
      return;
    }
    // A job the server forgot ended while no one asked: the clone is there when the project
    // lists it (a folder in projects/ is no target of New session's check).
    const isThere = async () => (await getProject(project.id)).repos.some((one) => one.name === typedName);
    let end: CloneEnd;
    try {
      end = await clone.run({ url: typedUrl, project: project.id, name: typedName, branch }, isThere);
    } catch (error) {
      setRefused(refusalOf(error));
      setBusy(false);
      return;
    }
    ended(end);
  };

  const edited = () => {
    setRefused(null);
    setNote(null);
  };
  const refusal = refused && (
    <div className="field-note bad">
      <div role="alert">{refused.message}</div>
      {refused.hint && <FolderHint text={refused.hint.text} command={refused.hint.command} />}
    </div>
  );
  const nameField = (
    <div className="field">
      <label htmlFor={`${ids}-name`}>Name</label>
      <input
        id={`${ids}-name`}
        className="mono"
        value={name}
        spellCheck={false}
        autoCapitalize="off"
        autoComplete="off"
        disabled={off}
        onChange={(event) => {
          setName(event.target.value);
          setNameEdited(true);
          edited();
        }}
      />
      {refusal ?? (typedName && <span className="field-note">Its folder: {`${project.folder}/${typedName}`}</span>)}
    </div>
  );

  return (
    <dialog
      ref={dialog}
      className="question-dialog add-repo"
      aria-label={`Add a repository to ${title}`}
      onCancel={(event) => {
        event.preventDefault();
        if (!off) onClose();
      }}
    >
      <form
        method="dialog"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <h3>Add a repository to {title}</h3>
        <div className="field">
          <div className="where-head">
            <span className="field-label">Source</span>
            <span className="segments" role="group" aria-label="Source">
              <SourceButton on={source === "url"} disabled={off} onClick={() => setSource("url")}>
                Clone from URL
              </SourceButton>
              <SourceButton on={source === "scratch"} disabled={off} onClick={() => setSource("scratch")}>
                From scratch
              </SourceButton>
            </span>
          </div>
        </div>
        {source === "url" ? (
          <>
            <div className="field">
              <label htmlFor={`${ids}-url`}>Git URL</label>
              <input
                id={`${ids}-url`}
                className="mono"
                value={url}
                placeholder="git@github.com:owner/repo.git or https://…"
                spellCheck={false}
                autoComplete="off"
                autoFocus
                disabled={off}
                onChange={(event) => {
                  setUrl(event.target.value);
                  edited();
                }}
              />
              {typedUrl !== "" && shown === null && <span className="field-note">checking the repository…</span>}
              {remote && (
                <span className="field-note ok">
                  ✓ repository found · {remote.branches.length} branch{remote.branches.length === 1 ? "" : "es"}
                </span>
              )}
              {shown && "failed" in shown && (
                <div className="field-note bad">
                  <div>{shown.failed.message}</div>
                  {shown.failed.hint && <FolderHint text={shown.failed.hint.text} command={shown.failed.hint.command} />}
                </div>
              )}
            </div>
            <div className="two">
              {nameField}
              <div className="field">
                <label htmlFor={`${ids}-branch`}>Branch</label>
                <select
                  id={`${ids}-branch`}
                  value={branch ?? ""}
                  disabled={off || remote === null}
                  onChange={(event) => setPicked({ url: typedUrl, branch: event.target.value })}
                >
                  {(remote?.branches ?? []).map((one) => (
                    <option key={one} value={one}>
                      {one === remote?.default ? `${one} (default)` : one}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </>
        ) : (
          <>
            {nameField}
            <span className="field-note">A new git repository with one empty commit.</span>
          </>
        )}
        {clone.job && <CloneProgress job={clone.job} />}
        {note && (
          <p className="field-note" role="status">
            {note}
          </p>
        )}
        <div className="question-buttons">
          {running ? (
            <button type="button" className="danger" onClick={clone.cancel}>
              Cancel clone
            </button>
          ) : (
            <>
              <button type="button" className="quiet" disabled={busy} onClick={onClose}>
                Cancel
              </button>
              <button type="submit" className="primary" disabled={!ready}>
                {source === "url" ? "Clone" : "Create"}
              </button>
            </>
          )}
        </div>
      </form>
    </dialog>
  );
}

function SourceButton({
  on,
  disabled,
  onClick,
  children,
}: {
  on: boolean;
  disabled: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button type="button" aria-pressed={on} disabled={disabled} onClick={onClick}>
      {children}
    </button>
  );
}

type Preview = { removal: RepoRemoval } | { refused: string } | null;

// Delete a repository: the removal's preview (its folder, the work not on the remote, the
// sessions forgotten), then DELETE. With work not on the remote the button is on only once
// the repository's name is typed. A refusal, of the preview or of the delete, leaves the
// text and Close.
function DeleteRepoDialog({
  project,
  name,
  onClose,
  onRemoved,
}: {
  project: ProjectInfo;
  name: string;
  onClose: () => void;
  onRemoved: (project: ProjectInfo) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const typedId = useId();
  const [preview, setPreview] = useState<Preview>(null);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    dialog.current?.showModal();
    let current = true;
    getRepoRemoval(project.id, name).then(
      (removal) => current && setPreview({ removal }),
      (error: unknown) => current && setPreview({ refused: messageOf(error) }),
    );
    return () => {
      current = false;
    };
  }, [project.id, name]);

  const remove = async () => {
    setBusy(true);
    let after: ProjectInfo;
    try {
      after = await removeProjectRepo(project.id, name);
    } catch (error) {
      setPreview({ refused: messageOf(error) });
      setBusy(false);
      return;
    }
    onRemoved(after);
  };

  const removal = preview && "removal" in preview ? preview.removal : null;
  const asksName = removal !== null && removal.unpushed.length > 0;
  const ready = removal !== null && !busy && (!asksName || typed === name);
  return (
    <dialog
      ref={dialog}
      className="question-dialog repo-delete"
      aria-label={`Delete repository ${name}?`}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      <h3>Delete repository {name}?</h3>
      {preview === null && <p className="muted">Loading…</p>}
      {preview && "refused" in preview && (
        <span className="field-note bad" role="alert">
          {preview.refused}
        </span>
      )}
      {removal && (
        <>
          <p>
            Its folder <span className="path">{removal.path}</span> is deleted with everything in it. This cannot be
            undone.
          </p>
          {removal.unpushed.length === 0 && removal.sessions.length === 0 ? (
            <p className="muted">All its work is on the remote. No session is forgotten.</p>
          ) : (
            <div className="removal-list">
              {removal.unpushed.length > 0 ? (
                <>
                  <h4>Work that is not on the remote</h4>
                  <ul>
                    {removal.unpushed.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </>
              ) : (
                <p className="muted">All its work is on the remote.</p>
              )}
              {removal.sessions.length > 0 ? (
                <>
                  <h4>Sessions that are forgotten</h4>
                  <ul>
                    {removal.sessions.map((one) => (
                      <li key={one.name}>
                        {one.name}
                        {one.open_runs > 0 && (
                          <span className="muted">
                            {" "}
                            ({one.open_runs} open run{one.open_runs === 1 ? "" : "s"})
                          </span>
                        )}
                        {one.project === null && (
                          <span className="muted"> — no project, started in this folder before projects</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <p className="muted">No session is forgotten.</p>
              )}
            </div>
          )}
          {asksName && (
            <div className="field">
              <label htmlFor={typedId}>
                Type <b>{name}</b> to delete it
              </label>
              <input
                id={typedId}
                className="mono"
                value={typed}
                spellCheck={false}
                autoCapitalize="off"
                autoComplete="off"
                autoFocus
                disabled={busy}
                onChange={(event) => setTyped(event.target.value)}
              />
            </div>
          )}
        </>
      )}
      <div className="question-buttons">
        {preview && "refused" in preview ? (
          <button type="button" className="quiet" onClick={onClose}>
            Close
          </button>
        ) : (
          <>
            <button type="button" className="quiet" disabled={busy} onClick={onClose}>
              Cancel
            </button>
            <button type="button" className="danger" disabled={!ready} onClick={() => void remove()}>
              Delete repository
            </button>
          </>
        )}
      </div>
    </dialog>
  );
}
