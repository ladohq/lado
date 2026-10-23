// Projects (docs/design/ui.md, Projects): the list on the left, the selected project on the
// right at /projects/<id>, as Sessions lays out sessions; on a phone the list or the project
// in turns. Projects have no change feed: the list and the page are read anew when they open,
// after a change, when the sessions of the feed start or stop, and when the window gets the
// focus. New project makes one as `lado project create` does.
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Link, NavLink, Outlet, useNavigate, useOutletContext, useParams } from "react-router";

import {
  ApiError,
  createProject,
  getProject,
  listProjects,
  renameProject,
  suggestProjectId,
  type ProjectId,
  type ProjectInfo,
  type ProjectSummary,
} from "./api";
import { PencilIcon } from "./icons";
import { useDebounced, useLaunch } from "./Launch";
import { useLive } from "./live";
import { projectPath, sessionPath } from "./paths";
import { usePhone } from "./phone";
import { ProjectRepos, ProjectSessions } from "./ProjectRepos";
import { ProjectVariables } from "./ProjectVariables";
import { messageOf, plural as count } from "./SessionControl";
import { labelOf } from "./sessionLabel";
import { useTitle } from "./Shell";
import { TitleEdit } from "./TitleEdit";
import { Tooltip } from "./Tooltip";

// Calls `read` when the page opens, when a session of the feed appears, starts, stops or
// goes, and when the window gets the focus: what a project's list and page show changes
// with its sessions, and in another browser.
function useReadAnew(read: () => void) {
  const loaded = useLive().sessions;
  const sessions =
    loaded && "sessions" in loaded
      ? loaded.sessions.map((one) => `${one.name}\0${one.status}\0${one.project ?? ""}`).join("\n")
      : "";
  useEffect(() => read(), [read, sessions]);
  useEffect(() => {
    window.addEventListener("focus", read);
    return () => window.removeEventListener("focus", read);
  }, [read]);
}

// The latest of overlapping reads wins: an older answer that comes later is dropped, and
// so is every answer of a read begun before `drop` (a change's own answer is newer).
function useLatest<T>(ask: () => Promise<T>, take: (result: { value: T } | { error: unknown }) => void) {
  const asked = useRef(0);
  const read = useCallback(() => {
    const mine = ++asked.current;
    ask().then(
      (value) => mine === asked.current && take({ value }),
      (error: unknown) => mine === asked.current && take({ error }),
    );
  }, [ask, take]);
  const drop = useCallback(() => {
    asked.current += 1;
  }, []);
  return { read, drop };
}

type Listed = { projects: ProjectSummary[] } | { error: string } | null;

type Context = { reload: () => void };

export function Projects() {
  useTitle("Projects");
  const current = useParams().id;
  const phone = usePhone();
  const navigate = useNavigate();
  const [listed, setListed] = useState<Listed>(null);
  const [query, setQuery] = useState("");
  const [making, setMaking] = useState(false);
  const { read: reload } = useLatest(
    listProjects,
    useCallback((result) => setListed("value" in result ? { projects: result.value } : { error: messageOf(result.error) }), []),
  );
  useReadAnew(reload);

  const made = (id: string) => {
    setMaking(false);
    reload();
    navigate(projectPath(id));
  };
  const dialog = making && <NewProjectDialog onClose={() => setMaking(false)} onMade={made} />;
  if (current === undefined && listed && "projects" in listed && listed.projects.length === 0) {
    return (
      <div className="projects-empty">
        <h2>No projects yet</h2>
        <p>
          A project is a folder in your workspace (<code>projects/&lt;id&gt;</code>) with its repositories and its own
          environment variables and secrets, so sessions for different clients get different keys.
        </p>
        <p>
          <button type="button" className="primary" onClick={() => setMaking(true)}>
            New project…
          </button>
        </p>
        {dialog}
      </div>
    );
  }

  const wanted = query.trim().toLowerCase();
  const found =
    listed && "projects" in listed
      ? listed.projects.filter((one) => [one.id, one.title ?? ""].some((text) => text.toLowerCase().includes(wanted)))
      : [];
  const showsList = phone === null || current === undefined;
  return (
    <div className="projects">
      {showsList && (
        <div className="session-list project-list">
          <div className="session-list-head">
            <h2>Projects</h2>
            <button type="button" className="plus" aria-label="New project" title="New project" onClick={() => setMaking(true)}>
              <span aria-hidden="true">+</span>
            </button>
          </div>
          <input
            type="search"
            className="search"
            placeholder="Find a project"
            aria-label="Find a project"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <nav aria-label="Projects">
            {listed === null && <p className="muted">Loading…</p>}
            {listed && "error" in listed && (
              <p className="problem" role="alert">
                {listed.error}
              </p>
            )}
            <ul>
              {found.map((one) => (
                <ProjectRow key={one.id} project={one} />
              ))}
            </ul>
          </nav>
        </div>
      )}
      {(phone === null || current !== undefined) && (
        <div className="project-detail">
          <Outlet context={{ reload } satisfies Context} />
        </div>
      )}
      {dialog}
    </div>
  );
}

// A row: the title (the id without one) and the mark of a folder not found, then the id,
// the repositories and the sessions running.
function ProjectRow({ project }: { project: ProjectSummary }) {
  const running = project.running.length;
  return (
    <li>
      <NavLink to={projectPath(project.id)} className="project-link">
        <span className="project-title">
          {project.title ?? project.id}
          {!project.found && <span className="badge badge-warn">folder not found</span>}
        </span>
        <span className="project-about">
          {project.id} · {count(project.repos, "repository", "repositories")} ·{" "}
          {running > 0 ? <span className="project-running">{running} running</span> : "no sessions running"}
        </span>
      </NavLink>
    </li>
  );
}

export function NoProject() {
  const phone = usePhone(); // the list is the page: nothing to select beside it
  return phone ? null : <p className="empty">Select a project</p>;
}

type Shown = { project: ProjectInfo } | { error: string; missing: boolean } | null;

export function ProjectPage() {
  const id = useParams().id!;
  const { reload } = useOutletContext<Context>();
  const phone = usePhone();
  const launch = useLaunch();
  const [shown, setShown] = useState<Shown>(null);
  const ask = useCallback(() => getProject(id), [id]);
  const { read, drop } = useLatest(
    ask,
    useCallback(
      (result) =>
        setShown(
          "value" in result
            ? { project: result.value }
            : {
                error: messageOf(result.error),
                missing: result.error instanceof ApiError && result.error.status === 404,
              },
        ),
      [],
    ),
  );
  useEffect(() => setShown(null), [id]);
  useReadAnew(read);
  const changed = (project: ProjectInfo) => {
    drop(); // a read begun before the change would show the project as it was
    setShown({ project });
    reload();
  };

  const back = phone && (
    <Link className="project-back" to="/projects">
      ← All projects
    </Link>
  );
  if (shown === null) return <p className="muted project-page">Loading…</p>;
  if ("error" in shown) {
    return (
      <div className="project-page">
        {back}
        {shown.missing ? (
          <p className="empty">{`No project ${id}`}</p>
        ) : (
          <p className="problem" role="alert">
            {shown.error}
          </p>
        )}
      </div>
    );
  }
  const { project } = shown;
  return (
    <section className="project-page" aria-label={`Project ${project.id}`}>
      {back}
      <div className="project-head">
        <ProjectTitle project={project} onSaved={changed} />
        <span className="project-id">{project.id}</span>
        <span className="project-head-actions">
          <button type="button" className="quiet" onClick={() => launch({ kind: "new", project: project.id })}>
            New session…
          </button>
        </span>
      </div>
      <p className="project-facts">
        {count(project.repos.length, "repository", "repositories")} · {count(project.running.length, "session")} running
        · folder <code>{project.folder}</code>
        {!project.found && (
          <>
            {" "}
            <span className="badge badge-warn">folder not found</span>
          </>
        )}
      </p>
      <ProjectRepos
        project={project}
        onAdded={() => {
          read();
          reload();
        }}
        onChanged={changed}
      />
      <ProjectSessions id={project.id} />
      <div className="project-notes">
        <span className="field-note warn">
          ⚠ Projects of one LADO are not isolated from each other: an agent of one project can read another's variables
          and secrets. For clients that must not mix, run a separate LADO.
        </span>
        <Running names={project.running} />
      </div>
      <ProjectVariables project={project} onChanged={changed} />
      <p className="placeholder project-later muted">
        Deleting the project: not built yet (Projects, step S7b). Meanwhile: <code>lado project delete {project.id}</code>.
      </p>
    </section>
  );
}

// The project's title, renamed in place as a session's is (TitleEdit, the id its
// suggestion): Rename or a click on the title opens the field; the focus goes back to Rename
// when it closes.
function ProjectTitle({ project, onSaved }: { project: ProjectInfo; onSaved: (project: ProjectInfo) => void }) {
  const [editing, setEditing] = useState(false);
  const pencil = useRef<HTMLButtonElement>(null);
  const back = useRef(false);
  useEffect(() => {
    if (editing || !back.current) return;
    back.current = false;
    pencil.current?.focus();
  });
  if (editing) {
    return (
      <TitleEdit
        name={project.id}
        title={project.title}
        label="Project title"
        save={(title) => renameProject(project.id, title)}
        hint="Enter to save · Esc to cancel"
        suggestionHint="Tab takes the id · Enter to save · Esc to cancel"
        onClose={(saved) => {
          if (saved) onSaved(saved);
          back.current = true;
          setEditing(false);
        }}
      />
    );
  }
  return (
    <span className="project-title-edit">
      <h2 onClick={() => setEditing(true)}>{project.title ?? project.id}</h2>
      <Tooltip tip="Rename project">
        <button
          ref={pencil}
          type="button"
          className="icon-button project-rename"
          aria-label="Rename"
          onClick={() => setEditing(true)}
        >
          <PencilIcon />
        </button>
      </Tooltip>
    </span>
  );
}

// Who gets a change: the agents started after it; each running session by its title (its
// name without one), a link to it.
function Running({ names }: { names: string[] }) {
  const loaded = useLive().sessions;
  if (names.length === 0) {
    return (
      <span className="field-note">
        New values reach the agents started after a change. No session of this project is running.
      </span>
    );
  }
  return (
    <span className="field-note">
      New values reach the agents started after a change; running agents keep the environment they started with.
      Running now:{" "}
      {names.map((name, index) => (
        <span key={name}>
          {index > 0 && ", "}
          <Link to={sessionPath(name)}>{labelOf(name, loaded)}</Link>
        </span>
      ))}{" "}
      — restart a session to give it the change.
    </span>
  );
}

// New project: Title (optional) and Id; Id follows the title (the server's suggestion) until
// the human types in it, then the typed id is checked. The note under Id is its folder or the
// core's refusal, which disables Create; nothing is made before Create, whose request the
// core checks again.
function NewProjectDialog({ onClose, onMade }: { onClose: () => void; onMade: (id: string) => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const idId = useId();
  const [title, setTitle] = useState("");
  const [id, setId] = useState("");
  const [edited, setEdited] = useState(false);
  const editing = useRef(false); // edited, for an answer that comes after the edit
  // The server's answer, with what it was asked: it counts only for the fields as they are.
  const [checked, setChecked] = useState<{ asked: string; answer: ProjectId } | null>(null);
  const [refused, setRefused] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    dialog.current?.showModal();
  }, []);

  const wanted = edited ? `id\0${id}` : `title\0${title}`;
  const asked = useDebounced(wanted);
  useEffect(() => {
    const [kind, text] = asked.split("\0");
    if (text.trim() === "") {
      setChecked(null);
      if (kind === "title" && !editing.current) setId("");
      return;
    }
    let current = true;
    const take = (answer: ProjectId) => {
      if (!current || (kind === "title" && editing.current)) return; // the human took Id over
      if (kind === "title") setId(answer.id ?? "");
      setChecked({ asked, answer });
    };
    suggestProjectId(kind === "id" ? { id: text } : { title: text }).then(take, (error: unknown) =>
      take({ id: kind === "id" ? text : null, folder: null, problem: messageOf(error) }),
    );
    return () => {
      current = false;
    };
  }, [asked]);

  const answer = checked?.asked === wanted ? checked.answer : null;
  const fresh = answer !== null && answer.id === id && id !== "";
  const note = refused ?? (answer && (fresh || answer.id === null) ? answer.problem : null);
  const ready = fresh && answer.problem === null && refused === null && !busy;
  const create = async () => {
    setBusy(true);
    try {
      await createProject(id, title.trim() === "" ? null : title.trim());
      onMade(id);
    } catch (error) {
      setRefused(messageOf(error));
      setBusy(false);
    }
  };

  return (
    <dialog
      ref={dialog}
      className="question-dialog project-new"
      aria-label="New project"
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      <h3>New project</h3>
      <div className="field">
        <label htmlFor={titleId}>
          Title <span className="muted">(optional)</span>
        </label>
        <input
          id={titleId}
          value={title}
          autoFocus
          onChange={(event) => {
            setTitle(event.target.value);
            setRefused(null);
          }}
        />
        <span className="field-note">The name the UI shows; you can change it later.</span>
      </div>
      <div className="field">
        <label htmlFor={idId}>Id</label>
        <input
          id={idId}
          className="mono"
          value={id}
          spellCheck={false}
          autoCapitalize="off"
          onChange={(event) => {
            editing.current = true;
            setEdited(true);
            setId(event.target.value);
            setRefused(null);
          }}
        />
        {note !== null ? (
          <span className="field-note bad">{note}</span>
        ) : (
          fresh &&
          answer.folder && <span className="field-note">{`Its folder: ${answer.folder}. The id never changes.`}</span>
        )}
      </div>
      <span className="field-note warn">
        ⚠ Projects of one LADO are not isolated from each other. For clients that must not mix, run a separate LADO.
      </span>
      <div className="question-buttons">
        <button type="button" className="quiet" disabled={busy} onClick={onClose}>
          Cancel
        </button>
        <button type="button" className="primary" disabled={!ready} onClick={create}>
          Create project
        </button>
      </div>
    </dialog>
  );
}
