// A session's facts (docs/design/ui.md, Session head and Phone layout): the git remote and
// branch, the kits' and the CLI's tooltips that the head shows on a computer, and on a phone
// the sheet the session's name opens, with the same pieces, so the two never say different
// things. The sheet: the status and run time, the whole folder, git, the kits with their
// versions, the CLI with its version and permission mode, then Rename (the title edited in
// place, as the pencil does), Copy path, Copy link and All sessions. A modal dialog at the
// page's bottom; Close, Esc or a tap beside it closes it.
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";

import type { ProviderInfo, RepoInfo, SessionAbout, SessionInfo, SessionKitInfo } from "./api";
import { CopyButton } from "./Copy";
import { FolderIcon, GitIcon, LinkIcon, PencilIcon } from "./icons";
import { projectPath, sessionLink } from "./paths";
import { shortRemote } from "./remote";
import { label } from "./sessionLabel";
import { TitleEdit } from "./TitleEdit";
import { Tooltip } from "./Tooltip";

const NEXT_AGENT = "installed now: the next agent starts with it";

// The repository's remote, short, and its branch; the remote's whole URL is copied from
// the git icon and shown in the tooltip with the branch and the path.
export function GitFact({ name, repo }: { name: string; repo: RepoInfo }) {
  const { remote, branch, path } = repo;
  if (!remote && !branch) return null;
  const text = [remote && shortRemote(remote), branch].filter(Boolean).join(" · ");
  const where = [branch && `branch ${branch}`, path].filter(Boolean).join(" · ");
  return (
    <span className="session-fact session-git">
      {remote ? (
        <CopyButton
          label="Copy URL"
          copied="URL copied"
          text={remote}
          field={{ title: `Remote of ${name}`, label: "URL" }}
          icon={<GitIcon />}
        />
      ) : (
        <GitIcon />
      )}
      <Tooltip
        tip={
          <>
            {remote && <div className="tooltip-line">{remote}</div>}
            <div className="tooltip-line">{where}</div>
          </>
        }
      >
        <span className="session-hint" tabIndex={0}>
          {text}
        </span>
      </Tooltip>
    </span>
  );
}

export function KitTip({ kit }: { kit: SessionKitInfo }) {
  if (!kit.valid) {
    return (
      <div className="tooltip-line">
        <b>{kit.name}</b>: {kit.problem}
      </div>
    );
  }
  return (
    <>
      <div className="tooltip-line">
        <b>{kit.name}</b> v{kit.version}
      </div>
      <div className="tooltip-line">{kit.source}</div>
      <div className="tooltip-line">{NEXT_AGENT}</div>
    </>
  );
}

// The CLI's version (or that it is not installed), then the session's permission mode.
export function CliTip({ cli, mode }: { cli: ProviderInfo; mode: string | null }) {
  return (
    <>
      {cli.installed ? (
        <>
          <div className="tooltip-line">
            <b>{cli.title}</b> {cli.version || cli.detail}
          </div>
          {cli.warning && <div className="tooltip-line session-warn">tested with {cli.tested_version}</div>}
          <div className="tooltip-line">{NEXT_AGENT}</div>
        </>
      ) : (
        <div className="tooltip-line">
          <b>{cli.title}</b> not installed: {cli.detail}
        </div>
      )}
      {mode && <div className="tooltip-line">mode {mode}</div>}
    </>
  );
}

// The sheet. `state` is the status and run time in the head's words; `about` null while it
// loads or when it failed (the facts are the session's settings alone, as in the head).
export function SessionDetails({
  session,
  about,
  state,
  onSaved,
  onClose,
}: {
  session: SessionInfo;
  about: SessionAbout | null;
  state: string;
  onSaved: (saved: SessionInfo) => void;
  onClose: () => void;
}) {
  const { name, repo, kits, provider, permission_mode: mode } = session;
  const dialog = useRef<HTMLDialogElement>(null);
  const renamer = useRef<HTMLButtonElement>(null);
  const [editing, setEditing] = useState(false);
  const back = useRef(false); // the focus goes back to Rename once the field is gone
  const repository = about?.repos[0];
  const cli = about?.provider;

  useEffect(() => {
    const shown = dialog.current;
    shown?.showModal();
    return () => shown?.close();
  }, []);
  useEffect(() => {
    if (editing || !back.current) return;
    back.current = false;
    renamer.current?.focus();
  });

  return (
    <dialog
      ref={dialog}
      className="session-details"
      aria-label={label(session)}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => event.target === event.currentTarget && onClose()}
    >
      <div className="session-details-box">
        <header className="session-details-head">
          {editing ? (
            <TitleEdit
              session={session}
              hint="Enter to save · Esc to cancel · empty shows the name"
              suggestionHint="Tab takes the name · Enter to save · Esc to cancel"
              onClose={(saved) => {
                if (saved) onSaved(saved);
                back.current = true;
                setEditing(false);
              }}
            />
          ) : (
            <h2>{label(session)}</h2>
          )}
          <button type="button" className="ghost" aria-label="Close" onClick={onClose}>
            ×
          </button>
        </header>
        <p className="session-details-state">
          {session.title !== null && `${name} · `}
          {state}
        </p>
        <dl>
          {about?.project && (
            <>
              <dt>Project</dt>
              <dd title={`Project ${about.project.id}`}>
                <Link to={projectPath(about.project.id)}>{about.project.title ?? about.project.id}</Link>
              </dd>
            </>
          )}
          <dt>Folder</dt>
          <dd>
            <code>{repo}</code>
          </dd>
          {repository && (repository.remote || repository.branch) && (
            <>
              <dt>Git</dt>
              <dd>
                <GitFact name={name} repo={repository} />
              </dd>
            </>
          )}
          <dt>Kits</dt>
          <dd className="session-kits">
            {kits.map((kit, at) => {
              const found = about?.kits.find((one) => one.name === kit);
              return (
                <span key={kit}>
                  {at > 0 && ", "}
                  {found ? (
                    <Tooltip tip={<KitTip kit={found} />}>
                      <span className="session-kit session-hint" tabIndex={0}>
                        {kit}
                      </span>
                    </Tooltip>
                  ) : (
                    kit
                  )}
                  {found?.valid && ` ${found.version}`}
                </span>
              );
            })}
          </dd>
          <dt>Agent CLI</dt>
          <dd>
            {cli ? (
              <Tooltip tip={<CliTip cli={cli} mode={mode} />}>
                <span className="session-hint" tabIndex={0}>
                  {provider}
                </span>
              </Tooltip>
            ) : (
              provider
            )}
            {cli?.installed && cli.version && ` ${cli.version}`}
            {cli?.warning && (
              <span role="img" aria-label="untested version" className="session-warn">
                {" "}!
              </span>
            )}
            {mode && ` · mode ${mode}`}
          </dd>
        </dl>
        <div className="session-details-actions">
          <button ref={renamer} type="button" className="quiet" disabled={editing} onClick={() => setEditing(true)}>
            <PencilIcon />
            Rename
          </button>
          <CopyButton
            label="Copy path"
            copied="Path copied"
            text={repo}
            field={{ title: `Path of ${name}`, label: "Path" }}
            icon={<FolderIcon />}
            named
          />
          <CopyButton
            label="Copy link"
            copied="Link copied"
            text={sessionLink(name)}
            field={{ title: `Link to ${name}`, label: "Link" }}
            icon={<LinkIcon />}
            named
          />
          <Link className="quiet" to="/sessions">
            All sessions
          </Link>
        </div>
      </div>
    </dialog>
  );
}
