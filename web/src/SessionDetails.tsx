// A session's facts (docs/design/ui.md, Session head and Phone layout), one content in two
// frames, so a computer and a phone never say different things. SessionFacts: the status,
// the run time, the id and the project; the whole folder with Copy path, git with Copy URL,
// the kits and the CLI with their versions and the permission mode, then Rename, Copy link
// and All sessions. On a computer DetailsPopover shows it under the head's title, and Rename
// hands over to the head; on a phone SessionDetails is a modal sheet at the page's bottom
// that edits the title itself, and Close, Esc or a tap beside it closes it.
import { useEffect, useRef, useState, type CSSProperties, type Ref, type RefObject } from "react";
import { Link } from "react-router";

import {
  setSessionTitle,
  type ProviderInfo,
  type RepoInfo,
  type SessionAbout,
  type SessionInfo,
  type SessionKitInfo,
} from "./api";
import { CopyButton } from "./Copy";
import { CopyIcon, LinkIcon, PencilIcon } from "./icons";
import { useModal } from "./modal";
import { projectPath, sessionLink } from "./paths";
import { shortRemote } from "./remote";
import { label } from "./sessionLabel";
import { TitleEdit } from "./TitleEdit";
import { Tooltip } from "./Tooltip";

const NEXT_AGENT = "installed now: the next agent starts with it";

// The remote's whole URL, then the branch and the path.
export function GitTip({ repo }: { repo: RepoInfo }) {
  const { remote, branch, path } = repo;
  return (
    <>
      {remote && <div className="tooltip-line">{remote}</div>}
      <div className="tooltip-line">{[branch && `branch ${branch}`, path].filter(Boolean).join(" · ")}</div>
    </>
  );
}

// The repository's remote, short, and its branch.
function GitFact({ repo }: { repo: RepoInfo }) {
  const { remote, branch } = repo;
  return (
    <span className="session-git">
      <Tooltip tip={<GitTip repo={repo} />}>
        <span className="session-hint" tabIndex={0}>
          {[remote && shortRemote(remote), branch].filter(Boolean).join(" · ")}
        </span>
      </Tooltip>
    </span>
  );
}

function KitTip({ kit }: { kit: SessionKitInfo }) {
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
function CliTip({ cli, mode }: { cli: ProviderInfo; mode: string | null }) {
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

type Facts = {
  session: SessionInfo;
  about: SessionAbout | null; // null while it loads or when it failed: the session's settings alone
  state: string; // the status and run time in the head's words
};

// The content of both frames. `renamer` is the Rename button, `renaming` turns it off.
function SessionFacts({
  session,
  about,
  state,
  renamer,
  renaming = false,
  onRename,
}: Facts & { renamer?: Ref<HTMLButtonElement>; renaming?: boolean; onRename: () => void }) {
  const { name, repo, kits, provider, permission_mode: mode } = session;
  const repository = about?.repos[0];
  const cli = about?.provider;
  return (
    <>
      <p className="session-details-state">
        {state} · id <code>{name}</code>
        {about?.project && (
          <>
            {" · project "}
            <Link to={projectPath(about.project.id)} title={`Project ${about.project.id}`}>
              {about.project.title ?? about.project.id}
            </Link>
          </>
        )}
      </p>
      <dl>
        <dt>Folder</dt>
        <dd className="session-details-copied">
          <code>{repo}</code>
        </dd>
        <dd className="session-details-copy">
          <CopyButton
            label="Copy path"
            copied="Path copied"
            text={repo}
            field={{ title: `Path of ${name}`, label: "Path" }}
            icon={<CopyIcon />}
          />
        </dd>
        {repository && (repository.remote || repository.branch) && (
          <>
            <dt>Git</dt>
            <dd className={repository.remote ? "session-details-copied" : undefined}>
              <GitFact repo={repository} />
            </dd>
            {repository.remote && (
              <dd className="session-details-copy">
                <CopyButton
                  label="Copy URL"
                  copied="URL copied"
                  text={repository.remote}
                  field={{ title: `Remote of ${name}`, label: "URL" }}
                  icon={<CopyIcon />}
                />
              </dd>
            )}
          </>
        )}
        <dt>Kits</dt>
        <dd className="session-kits">
          {kits.map((kit) => {
            const found = about?.kits.find((one) => one.name === kit);
            return (
              <div key={kit}>
                {found ? (
                  <Tooltip tip={<KitTip kit={found} />}>
                    <span className="session-kit session-hint" tabIndex={0}>
                      {kit}
                    </span>
                  </Tooltip>
                ) : (
                  kit
                )}
                {found?.valid && <span className="session-version"> {found.version}</span>}
              </div>
            );
          })}
        </dd>
        <dt>CLI</dt>
        <dd className="session-agent-cli">
          <div>
            {cli ? (
              <Tooltip tip={<CliTip cli={cli} mode={mode} />}>
                <span className="session-hint" tabIndex={0}>
                  {provider}
                </span>
              </Tooltip>
            ) : (
              provider
            )}
            {cli?.installed && cli.version && <span className="session-version"> {cli.version}</span>}
            {cli?.warning && (
              <>
                {" "}
                <span role="img" aria-label="untested version" className="session-warn">
                  !
                </span>
              </>
            )}
          </div>
          {mode && <div>permissions: {mode}</div>}
        </dd>
      </dl>
      <div className="session-details-actions">
        <button ref={renamer} type="button" className="quiet" disabled={renaming} onClick={onRename}>
          <PencilIcon />
          Rename
        </button>
        <CopyButton
          label="Copy link"
          copied="Link copied"
          text={sessionLink(name)}
          field={{ title: `Link to ${name}`, label: "Link" }}
          icon={<LinkIcon />}
          named
        />
        <Link className="quiet session-details-all" to="/sessions">
          All sessions
        </Link>
      </div>
    </>
  );
}

// Details on a computer: a popover with no trap, under the head's title. The focus starts on
// Copy path; Esc closes it, unless what is open in it took the key, also with the focus on
// the title or on nothing; a focus gone past them closes it too (HeadLine).
export function DetailsPopover({
  ref: popover,
  style,
  onRename,
  onClose,
  ...facts
}: Facts & {
  ref: RefObject<HTMLDivElement | null>; // the popover, for useBelow
  style?: CSSProperties;
  onRename: () => void;
  onClose: () => void;
}) {
  useEffect(() => {
    popover.current?.querySelector<HTMLElement>(".session-details-copy button")?.focus();
  }, [popover]);
  useEffect(() => {
    const escape = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      event.preventDefault();
      onClose();
    };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [onClose]);
  return (
    <div ref={popover} role="dialog" aria-label="Session details" className="session-popover" style={style}>
      <h2>{label(facts.session)}</h2>
      <SessionFacts {...facts} onRename={onRename} />
    </div>
  );
}

// Details on a phone: the sheet.
export function SessionDetails({
  session,
  about,
  state,
  onSaved,
  onClose,
}: Facts & {
  onSaved: (saved: SessionInfo) => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const renamer = useRef<HTMLButtonElement>(null);
  const [editing, setEditing] = useState(false);
  const back = useRef(false); // the focus goes back to Rename once the field is gone

  useModal(dialog);
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
              name={session.name}
              title={session.title}
              label="Session title"
              save={(title) => setSessionTitle(session.name, title)}
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
        <SessionFacts
          session={session}
          about={about}
          state={state}
          renamer={renamer}
          renaming={editing}
          onRename={() => setEditing(true)}
        />
      </div>
    </dialog>
  );
}
