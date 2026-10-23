// New session's Project way (docs/design/ui.md, Launch and session control): a project, then
// one of its repositories, as GET /api/project-launch gives them. The window only chooses:
// a project's repositories are added on the project's page.
import { useId, useRef, type KeyboardEvent, type ReactNode } from "react";

import type { ProjectLaunch, ProjectRepo, ProjectSummary } from "./api";
import { projectPath } from "./paths";
import { plural as count } from "./SessionControl";

const projectLabel = (project: ProjectSummary) =>
  `${project.title ? `${project.title} · ${project.id}` : project.id}${project.found ? "" : " · folder not found"}`;

export function ProjectField({
  launch,
  asked,
  asking = false,
  problem,
  head,
  disabled,
  onProject,
  onRepo,
  onLeave,
}: {
  launch: ProjectLaunch | null; // null: asking the first time
  // what `launch` answered (null: the server's choice); one it says is gone is named
  asked: { project: string | null; repo: string | null };
  // a new choice is asked: `launch` is the last answer with the choice in it, shown as it
  // is (the select and the list keep their focus) and marked busy
  asking?: boolean;
  problem: string | null; // why the server did not answer
  head: ReactNode; // the switch of the window's ways, beside the label
  disabled: boolean;
  onProject: (id: string) => void;
  onRepo: (name: string) => void;
  onLeave: (path: string) => void; // close the window and open `path`
}) {
  const ids = useId();
  const chosen = launch?.projects.find((one) => one.id === launch.project) ?? null;
  // E1: what was asked and is not there any more, said over the server's choice; not
  // while a new choice is asked, whose answer will say.
  const gone = asking ? null : (launch?.gone ?? null);
  return (
    <>
      <div className="field launch-where">
        <div className="where-head">
          <span className="field-label">Where</span>
          {head}
        </div>
        {problem ? (
          <span className="field-note bad">{problem}</span>
        ) : launch === null ? (
          <span className="field-note">checking…</span>
        ) : chosen === null ? (
          <span className="field-note">
            No projects yet. A project keeps its repositories and the variables its sessions get.{" "}
            <button type="button" className="link-button" onClick={() => onLeave("/projects")}>
              Make one in Projects
            </button>
          </span>
        ) : (
          <>
            <label className="field-label field-sub" htmlFor={`${ids}-project`}>
              Project
            </label>
            <select
              id={`${ids}-project`}
              value={chosen.id}
              disabled={disabled}
              onChange={(event) => onProject(event.target.value)}
            >
              {launch.projects.map((one) => (
                <option key={one.id} value={one.id} disabled={!one.found && one.id !== chosen.id}>
                  {projectLabel(one)}
                </option>
              ))}
            </select>
            {gone === "project" && asked.project && (
              <span className="field-note warn">{`⚠ No project ${asked.project} any more: choose one.`}</span>
            )}
            <span className="field-note">
              {count(chosen.repos, "repository", "repositories")} ·{" "}
              {chosen.running.length > 0 ? `${count(chosen.running.length, "session")} running` : "no sessions running"} ·
              folder <code>{chosen.folder}</code>
            </span>
          </>
        )}
      </div>
      {launch !== null && chosen !== null && (
        <RepoPick
          launch={launch}
          project={chosen}
          gone={gone === "repo" ? asked.repo : null}
          asking={asking}
          disabled={disabled}
          onRepo={onRepo}
          onLeave={onLeave}
        />
      )}
    </>
  );
}

// The project's repositories, always listed, one chosen; none: the way to the project's page.
function RepoPick({
  launch,
  project,
  gone,
  asking,
  disabled,
  onRepo,
  onLeave,
}: {
  launch: ProjectLaunch;
  project: ProjectSummary;
  gone: string | null; // the repository asked that the project has no more
  asking: boolean;
  disabled: boolean;
  onRepo: (name: string) => void;
  onLeave: (path: string) => void;
}) {
  const list = useRef<HTMLUListElement>(null);
  const repos = launch.repos;
  const chosen = repos.find((one) => one.name === launch.repo) ?? null;
  const at = chosen ? repos.indexOf(chosen) : -1;
  const pick = (repo: ProjectRepo) => {
    if (!disabled && repo.name !== launch.repo) onRepo(repo.name);
  };
  // A radio group's keys: the arrows move the choice and the focus, Space chooses.
  const onKey = (event: KeyboardEvent, repo: ProjectRepo, i: number) => {
    const step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[event.key];
    if (step !== undefined) {
      event.preventDefault();
      const next = (i + step + repos.length) % repos.length;
      pick(repos[next]);
      (list.current?.children[next] as HTMLElement | undefined)?.focus();
    } else if (event.key === " " || event.key === "Enter") {
      event.preventDefault();
      pick(repo);
    }
  };
  const label = project.title ?? project.id;
  return (
    <div className="field launch-where">
      <span className="field-label">Repository</span>
      <ul
        ref={list}
        className="repo-pick"
        role="radiogroup"
        aria-label="Repository"
        aria-disabled={disabled || undefined}
        aria-busy={asking || undefined}
      >
        {repos.length === 0 ? (
          <li className="repo-none">
            <span className="muted">
              No repositories yet. Add one on the project's page:{" "}
              <button type="button" className="link-button" onClick={() => onLeave(projectPath(project.id))}>
                Open {label}
              </button>
            </span>
          </li>
        ) : (
          repos.map((repo, i) => (
            <li
              key={repo.name}
              role="radio"
              aria-checked={repo === chosen}
              tabIndex={i === Math.max(at, 0) ? 0 : -1}
              className={repo === chosen ? "on" : undefined}
              onClick={() => pick(repo)}
              onKeyDown={(event) => onKey(event, repo, i)}
            >
              <span className="dot" aria-hidden="true" />
              <b>{repo.name}</b>
              <span className="muted">{[repo.branch ?? "detached HEAD", repo.remote].filter(Boolean).join(" · ")}</span>
            </li>
          ))
        )}
      </ul>
      {gone && <span className="field-note warn">{`⚠ No repository ${gone} in ${label} any more: choose one.`}</span>}
      {chosen && (
        <span className="field-note ok">✓ git repository{chosen.branch ? ` · branch ${chosen.branch}` : ""}</span>
      )}
    </div>
  );
}
