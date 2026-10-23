// Delete project (docs/design/ui.md, Projects): the block at the bottom of the project's
// page and its dialog. The dialog shows the core's preview (`GET …/deletion`, what `lado
// project delete` prints), then DELETEs once the project's id is typed: always, since its
// variables and secrets are on no remote. A refusal, of the preview or of the delete, leaves
// the core's text and Close. After the delete the list of projects opens.
import { useEffect, useId, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { deleteProject, getProjectDeletion, type ProjectDeletion, type ProjectInfo } from "./api";
import { ForgottenSessions } from "./ProjectRepos";
import { messageOf } from "./SessionControl";

export function ProjectDelete({ project, onDeleted }: { project: ProjectInfo; onDeleted: () => void }) {
  const heading = useId();
  const [open, setOpen] = useState(false);
  return (
    <section className="project-section project-delete" aria-labelledby={heading}>
      <div className="project-section-head">
        <h3 id={heading}>Delete project</h3>
        <button type="button" className="quiet danger-text project-add" onClick={() => setOpen(true)}>
          Delete project…
        </button>
      </div>
      <p className="muted">
        Deletes its folder with every repository in it, its sessions, variables and secrets. Refused while a session of
        the project runs.
      </p>
      {open && <DeleteProjectDialog project={project} onClose={() => setOpen(false)} onDeleted={onDeleted} />}
    </section>
  );
}

type Preview = { deletion: ProjectDeletion } | { refused: string } | null;

function DeleteProjectDialog({
  project,
  onClose,
  onDeleted,
}: {
  project: ProjectInfo;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const typedId = useId();
  const navigate = useNavigate();
  const [preview, setPreview] = useState<Preview>(null);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const title = project.title ?? project.id;

  useEffect(() => {
    dialog.current?.showModal();
    let current = true;
    getProjectDeletion(project.id).then(
      (deletion) => current && setPreview({ deletion }),
      (error: unknown) => current && setPreview({ refused: messageOf(error) }),
    );
    return () => {
      current = false;
    };
  }, [project.id]);

  const remove = async () => {
    setBusy(true);
    try {
      await deleteProject(project.id);
    } catch (error) {
      setPreview({ refused: messageOf(error) });
      setBusy(false);
      return;
    }
    onDeleted();
    navigate("/projects");
  };

  const deletion = preview && "deletion" in preview ? preview.deletion : null;
  const ready = deletion !== null && !busy && typed === project.id;
  return (
    <dialog
      ref={dialog}
      className="question-dialog repo-delete project-delete-dialog"
      aria-label={`Delete project ${title}?`}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      <h3>Delete project {title}?</h3>
      {preview === null && <p className="muted">Loading…</p>}
      {preview && "refused" in preview && (
        <span className="field-note bad" role="alert">
          {preview.refused}
        </span>
      )}
      {deletion && (
        <>
          <FolderSentence deletion={deletion} />
          <div className="removal-list">
            {deletion.kind === "folder" &&
              (deletion.unpushed.length > 0 ? (
                <>
                  <h4>Work that is not on the remote</h4>
                  <ul>
                    {deletion.unpushed.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </>
              ) : (
                <p className="muted">All its work is on the remote.</p>
              ))}
            {deletion.sessions.length > 0 ? (
              <ForgottenSessions sessions={deletion.sessions} />
            ) : (
              <p className="muted">No session is forgotten.</p>
            )}
            {deletion.variables.length + deletion.secrets.length > 0 ? (
              <>
                <h4>Variables and secrets that are deleted</h4>
                <ul>
                  {deletion.variables.map((name) => (
                    <li key={`v-${name}`}>{name}</li>
                  ))}
                  {deletion.secrets.map((name) => (
                    <li key={`s-${name}`}>
                      {name}
                      <span className="muted"> — secret</span>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="muted">No variables or secrets.</p>
            )}
          </div>
          <div className="field">
            <label htmlFor={typedId}>
              Type <b>{project.id}</b> to delete it
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
              Delete project
            </button>
          </>
        )}
      </div>
    </dialog>
  );
}

// What happens to the project's folder: removed whole, only the link, or nothing there.
function FolderSentence({ deletion }: { deletion: ProjectDeletion }) {
  const folder = <span className="path">{deletion.folder}</span>;
  const rest = "Its sessions, variables and secrets are deleted. This cannot be undone.";
  if (deletion.kind === "link") {
    const target = <span className="path">{deletion.target}</span>;
    return (
      <p>
        Its folder {folder} is a link to {target}: only the link is deleted, {target} and everything in it stay. {rest}
      </p>
    );
  }
  if (deletion.kind === "missing") {
    return (
      <p>
        Its folder {folder} is not found. {rest}
      </p>
    );
  }
  return (
    <p>
      Its folder {folder} is deleted with everything in it, and so are its sessions, variables and secrets. This cannot
      be undone.
    </p>
  );
}
