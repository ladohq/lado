// New session's Where (docs/design/ui.md, Launch and session control): one combobox that
// shows the place on one line, its name then a muted secondary (a folder's path, a project's
// repository `in project <title>`), and lists the recent places the same way, then the other
// ways; a typed path lists that folder and its parent's
// subfolders. Under it stand the fields of the way chosen and the folder check's notes.
// Every fact comes from the server; this file only shows and picks.
import { useLayoutEffect, useId, useRef, useState, type CSSProperties, type ReactNode, type RefObject } from "react";

import {
  getFolder,
  type CloneTarget,
  type FolderInfo,
  type ProjectPlace,
  type RecentFolder,
  type RemoteInfo,
  type ScratchTarget,
  type Workspace,
} from "./api";
import { since } from "./ChatText";
import { useCopy } from "./Copy";
import { InfoTip } from "./InfoTip";
import { BRANCH_LIST, cloneRefused, useAsked, useDebounced, valueOf } from "./Launch";

// The ways of the list's group Somewhere else; "folder" is Other folder….
export type Way = "folder" | "url" | "scratch" | "project";

export type Icon = "folder" | "project" | "link" | "plus" | "open" | "search";

// What the closed field shows of the place: its name, then a secondary, muted, on the same
// line (a folder's path, `in project <title>`), which is cut first.
export type Shown = { icon: Icon; name: string; sub?: string | null };

const WAYS: { way: Way; label: string; icon: Icon }[] = [
  { way: "folder", label: "Other folder…", icon: "open" },
  { way: "url", label: "Clone from URL…", icon: "link" },
  { way: "scratch", label: "New empty folder…", icon: "plus" },
  { way: "project", label: "Project…", icon: "project" },
];

const PATHS: Record<Icon, ReactNode> = {
  folder: <path d="M1.5 3.5h4.2l1.5 1.5h7.3v8H1.5z" />,
  plus: (
    <>
      <path d="M1.5 3.5h4.2l1.5 1.5h7.3v8H1.5z" />
      <path d="M8 7v4M6 9h4" />
    </>
  ),
  open: <path d="M1.5 12.5v-9h4.2l1.5 1.5h6v2M1.5 12.5l2-5.5h11l-2 5.5z" />,
  project: (
    <>
      <rect x="1.5" y="4.5" width="13" height="9" rx="1.5" />
      <path d="M5.5 4.5v-2h5v2" />
    </>
  ),
  link: <path d="M6.5 9.5l3-3M7 4.5l1.2-1.2a2.6 2.6 0 0 1 3.7 3.7L10.7 8.2M9 11.5l-1.2 1.2a2.6 2.6 0 0 1-3.7-3.7L5.3 7.8" />,
  search: (
    <>
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.5 10.5l3.5 3.5" />
    </>
  ),
};

export function PlaceIcon({ icon }: { icon: Icon }) {
  return (
    <svg className="place-icon" width="18" height="18" viewBox="0 0 16 16" aria-hidden="true">
      <g fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" strokeLinecap="round">
        {PATHS[icon]}
      </g>
    </svg>
  );
}

// A project's repository's secondary.
export const projectSub = (title: string) => `in project ${title}`;

// Where suggestions come from: the folder up to the last "/" and the name typed after it.
export function parentOf(path: string): { parent: string; prefix: string } | null {
  const slash = path.lastIndexOf("/");
  if (slash < 0) return null;
  return { parent: path.slice(0, slash + 1), prefix: path.slice(slash + 1) };
}

// A folder as a parent: "/" stays "/", "/a/b" becomes "/a/b/".
export const withSlash = (folder: string) => (folder.endsWith("/") ? folder : `${folder}/`);

export const lastPart = (path: string) => path.replace(/\/+$/, "").split("/").pop() || path;

// A recent place as the list names it: a project's repository by its name, a folder by its
// last segment.
const recentName = (one: RecentFolder) => one.project?.repo ?? lastPart(one.path);

type Option =
  | { kind: "recent"; recent: RecentFolder }
  | { kind: "use"; path: string }
  | { kind: "sub"; path: string; name: string }
  | { kind: "way"; way: Way; label: string; icon: Icon };

// Where the list goes: fixed under the field, so the window's scrolling body does not cut
// it; at 760 px or less in the flow, under the field.
function useListPlace(anchor: RefObject<HTMLElement | null>, open: boolean): CSSProperties | undefined {
  const [style, setStyle] = useState<CSSProperties | undefined>(undefined);
  useLayoutEffect(() => {
    const box = anchor.current?.getBoundingClientRect();
    if (!open || !box || window.innerWidth <= 760) {
      setStyle((now) => (now === undefined ? now : undefined));
      return;
    }
    const placed: CSSProperties = {
      position: "fixed",
      top: box.bottom + 4,
      left: box.left,
      width: box.width,
      maxHeight: Math.max(160, window.innerHeight - box.bottom - 12),
    };
    setStyle((now) => (JSON.stringify(now) === JSON.stringify(placed) ? now : placed));
  });
  return style;
}

export function PlaceBox({
  id,
  shown,
  recent,
  onRecent,
  onPath,
  onWay,
  disabled,
  describedBy,
  inputRef,
}: {
  id: string; // the input's, for Where's label
  shown: Shown;
  recent: RecentFolder[];
  onRecent: (place: RecentFolder) => void;
  onPath: (path: string) => void; // a typed folder, or one of its parent's subfolders
  onWay: (way: Way) => void;
  disabled: boolean;
  describedBy?: string;
  inputRef: RefObject<HTMLInputElement | null>;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const listStyle = useListPlace(box, open);
  const typed = query.trim();
  const path = /^[/~]/.test(typed) ? typed : null;
  const split = path ? parentOf(path) : null;
  const parent = useDebounced(split?.parent ?? null);
  const listed = valueOf(useAsked(open && parent ? parent : null, getFolder));
  const subs =
    split && listed && parent === split.parent
      ? listed.subfolders
          .filter((one) => one.toLowerCase().startsWith(split.prefix.toLowerCase()) && one !== split.prefix)
          .map((name): Option => ({ kind: "sub", path: split.parent + name, name }))
      : [];
  const word = typed.toLowerCase();
  const recentOptions = path
    ? []
    : recent
        .filter((one) => !word || recentName(one).toLowerCase().includes(word))
        .map((one): Option => ({ kind: "recent", recent: one }));
  const wayOptions = path ? [] : WAYS.map((one): Option => ({ kind: "way", ...one }));
  const options: Option[] = path ? [{ kind: "use", path }, ...subs] : [...recentOptions, ...wayOptions];
  const at = Math.min(active, options.length - 1);

  const close = () => {
    setOpen(false);
    setQuery("");
  };
  const show = (start = 0) => {
    setOpen(true);
    setActive(start);
  };
  const pick = (option: Option) => {
    close();
    if (option.kind === "recent") onRecent(option.recent);
    else if (option.kind === "way") onWay(option.way);
    else onPath(option.path);
  };
  const optionId = (i: number) => `${id}-option-${i}`;

  const row = (option: Option, i: number) => {
    const key = `${option.kind}:${"path" in option ? option.path : option.kind === "recent" ? option.recent.path : option.way}`;
    const common = {
      id: optionId(i),
      role: "option",
      "aria-selected": i === at,
      className: `place-option${i === at ? " active" : ""}${option.kind === "way" ? " other" : ""}`,
      onMouseDown: (event: React.MouseEvent) => {
        event.preventDefault(); // keep the input's focus
        pick(option);
      },
    };
    if (option.kind === "recent") {
      const one = option.recent;
      return (
        <li key={key} {...common}>
          <PlaceIcon icon={one.project ? "project" : "folder"} />
          <span className="place-text">
            <span className="place-name">{recentName(one)}</span>
            <span className="place-sub">{one.project ? projectSub(one.project.title ?? one.project.id) : one.path}</span>
          </span>
          {(one.session.running_since ?? one.session.stopped_at) && (
            <span className="place-meta">{`${since((one.session.running_since ?? one.session.stopped_at)!)} ago`}</span>
          )}
        </li>
      );
    }
    if (option.kind === "way") {
      return (
        <li key={key} {...common}>
          <PlaceIcon icon={option.icon} />
          <span className="place-text">
            <span className="place-name">{option.label}</span>
          </span>
        </li>
      );
    }
    return (
      <li key={key} {...common}>
        <PlaceIcon icon={option.kind === "use" ? "folder" : "open"} />
        <span className="place-text">
          <span className="place-name">{option.kind === "use" ? `Use folder ${option.path}` : `${option.name}/`}</span>
        </span>
      </li>
    );
  };

  const wayStart = recentOptions.length;
  return (
    <div className="place-wrap">
      <div
        ref={box}
        className={`place-box${open ? " open" : ""}${disabled ? " off" : ""}`}
        title={open ? undefined : shown.sub ? `${shown.name} — ${shown.sub}` : shown.name}
        onMouseDown={(event) => {
          if (disabled || event.target === inputRef.current) return;
          event.preventDefault();
          inputRef.current?.focus();
          if (open) close();
          else show();
        }}
      >
        <PlaceIcon icon={open ? "search" : shown.icon} />
        <span className="place-text">
          {/* As wide as the name's text, in the field's own font: a hidden copy sizes it. */}
          <span className={`place-fit${open ? " open" : ""}`} data-text={open ? "" : shown.name}>
            <input
              ref={inputRef}
              id={id}
              role="combobox"
              aria-autocomplete="list"
              aria-expanded={open}
              aria-controls={`${id}-list`}
              aria-activedescendant={open && options[at] ? optionId(at) : undefined}
              aria-describedby={describedBy}
              className={`place-input${open ? "" : " place-name"}`}
              value={open ? query : shown.name}
              placeholder={open ? "Type a name or a path" : ""}
              readOnly={!open}
              autoComplete="off"
              spellCheck={false}
              disabled={disabled}
              onClick={() => (open ? undefined : show())}
              onChange={(event) => {
                setQuery(event.target.value);
                setActive(0);
                setOpen(true);
              }}
              onPaste={(event) => {
                if (open) return;
                event.preventDefault();
                setQuery(event.clipboardData.getData("text"));
                show();
              }}
              onBlur={close}
              onKeyDown={(event) => {
                if (!open) {
                  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                    event.preventDefault();
                    show();
                  } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey && event.key !== " ") {
                    event.preventDefault();
                    setQuery(event.key);
                    show();
                  }
                  return;
                }
                if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                  event.preventDefault();
                  const step = event.key === "ArrowDown" ? 1 : -1;
                  if (options.length) setActive((at + step + options.length) % options.length);
                } else if (event.key === "Enter") {
                  event.preventDefault();
                  if (options[at]) pick(options[at]);
                } else if (event.key === "Escape") {
                  event.preventDefault(); // the first Esc closes only the list
                  close();
                } else if (event.key === "Tab") {
                  close();
                }
              }}
            />
          </span>
          {!open && shown.sub && <span className="place-sub">{shown.sub}</span>}
        </span>
        <svg className={`place-chev${open ? " up" : ""}`} width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
          <path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      </div>
      {open && (
        <ul id={`${id}-list`} role="listbox" aria-label="Places" className="place-list" style={listStyle}>
          {path ? (
            options.map(row)
          ) : (
            <>
              {recentOptions.length > 0 && (
                <li role="presentation" className="place-group">
                  Recent
                </li>
              )}
              {recentOptions.map(row)}
              {recentOptions.length > 0 && <li role="separator" className="place-sep" />}
              <li role="presentation" className="place-group">
                Somewhere else
              </li>
              {wayOptions.map((option, i) => row(option, wayStart + i))}
            </>
          )}
        </ul>
      )}
    </div>
  );
}

// Other folder…'s path field: today's path field, its subfolders suggested from the parent
// of what is typed; empty, the workspace's once it is made.
export function FolderPathField({
  path,
  onPath,
  workspace,
  disabled,
  inputRef,
  describedBy,
}: {
  path: string;
  onPath: (path: string) => void;
  workspace: Workspace | null; // LADO_REPOS, else ~/workspace; null until it is known
  disabled: boolean;
  inputRef: RefObject<HTMLInputElement | null>;
  describedBy?: string;
}) {
  const ids = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const empty = path.trim() === "";
  const made = workspace?.made ? workspace.path : null;
  const split = empty && made ? { parent: withSlash(made), prefix: "" } : parentOf(path);
  const parent = useDebounced(split?.parent ?? null);
  const listed = valueOf(useAsked(open && parent ? parent : null, getFolder));
  const prefix = (split?.prefix ?? "").toLowerCase();
  // The answer of the parent asked now (the server gives its path with `~` expanded).
  const options =
    open && listed && split && parent === split.parent
      ? listed.subfolders.filter((one) => one.toLowerCase().startsWith(prefix) && one !== split.prefix)
      : []; // a folder typed in full is not suggested again: its check shows under the field

  const pick = (folderName: string) => {
    if (!split) return;
    onPath(split.parent + folderName);
    setOpen(false);
    setActive(-1);
  };

  return (
    <div className="field launch-where">
      <label htmlFor={`${ids}-folder`}>Folder</label>
      <div className="where-box">
        <input
          ref={inputRef}
          id={`${ids}-folder`}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={options.length > 0}
          aria-controls={`${ids}-folders`}
          aria-activedescendant={active >= 0 && options[active] ? `${ids}-folder-${active}` : undefined}
          aria-describedby={describedBy}
          value={path}
          placeholder={workspace ? `${withSlash(workspace.path)}…` : ""}
          autoComplete="off"
          spellCheck={false}
          disabled={disabled}
          onChange={(event) => {
            onPath(event.target.value);
            setOpen(true);
            setActive(-1);
          }}
          onFocus={() => {
            // Also before the workspace is known: a focus that comes first lists its
            // subfolders once it is, and until then nothing is asked (no parent).
            if (empty) setOpen(true);
          }}
          onBlur={() => setOpen(false)}
          onKeyDown={(event) => {
            if (options.length === 0) return;
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
              event.preventDefault();
              const step = event.key === "ArrowDown" ? 1 : -1;
              setActive((at) => (at + step + options.length) % options.length);
            } else if (event.key === "Enter" && active >= 0) {
              event.preventDefault();
              pick(options[active]);
            } else if (event.key === "Escape") {
              event.preventDefault();
              setOpen(false);
            }
          }}
        />
        {options.length > 0 && (
          <ul id={`${ids}-folders`} role="listbox" aria-label="Folders" className="where-list">
            {options.map((one, i) => (
              <li
                key={one}
                id={`${ids}-folder-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseDown={(event) => {
                  event.preventDefault(); // keep the input's focus
                  pick(one);
                }}
              >
                {one}/
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// Under Where for a folder: the check's one line (with a stopped session of the place), its
// warning, a refusal with its way out, a fresh start's offer, or the set-up panel (`setup`).
export function FolderNotes({
  id,
  folder,
  checking,
  problem,
  stopped,
  setup,
  disabled,
  onScratch,
  onProject,
}: {
  id: string; // the notes' box, the field's aria-describedby
  folder: FolderInfo | null;
  checking: boolean;
  problem: string | null;
  stopped: { name: string; at: string | null } | null; // a stopped session of the default name here
  setup: ReactNode; // the set-up panel of a plain folder of files
  disabled: boolean;
  onScratch: (path: string) => void; // Start from scratch here
  onProject: (place: ProjectPlace) => void; // the refused folder's project
}) {
  return (
    <div id={id} className="place-notes">
      {folder?.ok && (
        <p className="place-line">
          <span className="ok">{`✓ Ready${folder.branch ? ` · branch ${folder.branch}` : ""}`}</span>
          {stopped && (
            <>
              {" · Session "}
              <b>{stopped.name}</b>
              {` stopped here${stopped.at ? ` ${since(stopped.at)} ago` : ""}`}
            </>
          )}
        </p>
      )}
      {folder?.ok && folder.warning && <span className="field-note warn">⚠ {folder.warning}</span>}
      {folder && !folder.ok && folder.setup !== null && folder.setup !== undefined && setup}
      {folder && !folder.ok && folder.scratch && (
        // In place of LAD-5's command: a new or empty folder takes no file into a commit.
        <div className="place-aside">
          <p>
            {folder.problem_kind === "missing"
              ? "There is no such folder — LADO will create it."
              : "The folder is empty: LADO can start it from scratch."}
          </p>
          <button type="button" className="quiet" disabled={disabled} onClick={() => onScratch(folder.path)}>
            Start from scratch here
          </button>
        </div>
      )}
      {folder && !folder.ok && !folder.scratch && !folder.setup && (
        <div className="field-note bad" role="alert">
          <div>{folder.problem}</div>
          {folder.project && (
            <div className="folder-hint">
              <div className="folder-hint-command">
                <button type="button" className="chip-button" disabled={disabled} onClick={() => onProject(folder.project!)}>
                  {`${folder.project.repo ? "Start in" : "Open"} the project ${folder.project.title ?? folder.project.id}`}
                </button>
              </div>
            </div>
          )}
          {folder.hint && <FolderHint text={folder.hint.text} command={folder.hint.command} />}
        </div>
      )}
      {problem && <span className="field-note bad">{problem}</span>}
      {checking && !problem && <span className="field-note">checking…</span>}
    </div>
  );
}

// New empty folder…'s field: the name in the human's words, the folder it makes when its
// slug differs from them, and why git cannot sign its commit yet.
export function ScratchNameField({
  text,
  onText,
  target,
  problem,
  workspace,
  disabled,
  inputRef,
  onProject,
}: {
  text: string;
  onText: (text: string) => void;
  target: ScratchTarget | null;
  problem: string | null; // the server's refusal of the request itself
  workspace: Workspace | null;
  disabled: boolean;
  inputRef: RefObject<HTMLInputElement | null>;
  onProject: (place: ProjectPlace) => void;
}) {
  const ids = useId();
  const name = target?.name;
  const into = target?.path ? target.path.replace(/\/[^/]*\/?$/, "") || "/" : (workspace?.path ?? null);
  const notes = `${ids}-notes`;
  return (
    <div className="field launch-where">
      <span className="field-label">
        <label htmlFor={`${ids}-scratch-name`}>Folder name</label>
        {into && <InfoTip about="Folder name">{`LADO creates it in ${into}.`}</InfoTip>}
      </span>
      <input
        ref={inputRef}
        id={`${ids}-scratch-name`}
        className="launch-words"
        value={text}
        placeholder="Coffee shop site"
        autoComplete="off"
        disabled={disabled}
        aria-describedby={notes}
        aria-invalid={(text.trim() !== "" && !!target?.problem) || undefined}
        onChange={(event) => onText(event.target.value)}
      />
      <div id={notes} className="place-notes">
        <span className="field-note">Also the session’s name.</span>
        {text.trim() !== "" && target?.problem && <span className="field-note bad">{target.problem}</span>}
        {name && name !== text.trim() && <span className="field-note">{`folder ${name}`}</span>}
        {target?.text &&
          (target.state === null || !["new", "empty"].includes(target.state)) && (
            <RefusedNote text={target.text} hint={target.hint ?? null} project={target.project ?? null} onProject={onProject} />
          )}
        {target?.warning && <span className="field-note warn">⚠ {target.warning}</span>}
        {target?.author && (
          <div className="field-note bad">
            <div>{target.author.text}</div>
            {target.author.hint && <FolderHint text={target.author.hint.text} command={target.author.hint.command} />}
          </div>
        )}
        {problem && <span className="field-note bad">{problem}</span>}
      </div>
    </div>
  );
}

export function UrlField({
  url,
  onUrl,
  listing,
  remote,
  failed,
  disabled,
  inputRef,
}: {
  url: string;
  onUrl: (url: string) => void;
  listing: boolean;
  remote: RemoteInfo | null;
  failed: { error: string; detail?: unknown } | null;
  disabled: boolean;
  inputRef: RefObject<HTMLInputElement | null>;
}) {
  const ids = useId();
  const why = failed ? cloneRefused(failed.detail) : null;
  return (
    <div className="field launch-where">
      <label htmlFor={`${ids}-url`}>Repository URL</label>
      <input
        ref={inputRef}
        id={`${ids}-url`}
        value={url}
        placeholder="git@github.com:owner/repo.git or https://…"
        autoComplete="off"
        spellCheck={false}
        disabled={disabled}
        aria-describedby={`${ids}-notes`}
        aria-invalid={failed !== null || undefined}
        onChange={(event) => onUrl(event.target.value)}
      />
      <div id={`${ids}-notes`} className="place-notes">
        {listing && <span className="field-note">checking the repository…</span>}
        {remote && <span className="field-note ok">✓ Found</span>}
        {failed && (
          <div className="field-note bad">
            <div>{why?.message ?? failed.error}</div>
            {why?.hint && <FolderHint text={why.hint.text} command={why.hint.command} />}
          </div>
        )}
      </div>
    </div>
  );
}

const CAN_CLONE = new Set<CloneTarget["state"]>(["new", "empty"]);
const TARGET_OK: Partial<Record<CloneTarget["state"], string>> = { new: "✓ New folder", empty: "✓ Empty folder" };

// The clone's folder as the core finds it; another repository's clone or a clone of this
// one are told under the fields, in full.
export function TargetNote({
  target,
  problem,
  onProject,
}: {
  target: CloneTarget | null;
  problem: string | null;
  onProject: (place: ProjectPlace) => void;
}) {
  if (problem) return <span className="field-note bad">{problem}</span>;
  if (target === null || target.state === "same_repo" || target.state === "other_repo") return null;
  if (CAN_CLONE.has(target.state)) return <span className="field-note ok">{TARGET_OK[target.state]}</span>;
  return <RefusedNote text={target.text} hint={target.hint ?? null} project={target.project ?? null} onProject={onProject} />;
}

// A folder that takes no clone or fresh start, with what to do instead when the core says
// it: a folder inside a project leads to the project's page, above the core's command.
export function RefusedNote({
  text,
  hint,
  project,
  onProject,
}: {
  text: string;
  hint: FolderInfo["hint"];
  project: ProjectPlace | null;
  onProject: (place: ProjectPlace) => void;
}) {
  if (!hint && !project) return <span className="field-note bad">{text}</span>;
  return (
    <div className="field-note bad">
      <div>{text}</div>
      {project && (
        <div className="folder-hint">
          <div className="folder-hint-command">
            <button type="button" className="chip-button" onClick={() => onProject({ ...project, repo: null })}>
              {`Open the project ${project.title ?? project.id}`}
            </button>
          </div>
        </div>
      )}
      {hint && <FolderHint text={hint.text} command={hint.command} />}
    </div>
  );
}

export function BranchField({
  remote,
  failed,
  branch,
  onBranch,
  disabled,
}: {
  remote: RemoteInfo | null;
  failed: boolean;
  branch: string | null;
  onBranch: (branch: string) => void;
  disabled: boolean;
}) {
  const ids = useId();
  const label = (one: string) => (one === remote?.default ? `${one} (default)` : one);
  return (
    <div className="field">
      <label htmlFor={`${ids}-branch`}>Branch</label>
      {remote && remote.branches.length > BRANCH_LIST ? (
        <BranchCombo id={`${ids}-branch`} remote={remote} branch={branch} onBranch={onBranch} disabled={disabled} />
      ) : (
        <select
          id={`${ids}-branch`}
          value={remote ? (branch ?? "") : ""}
          disabled={disabled || remote === null}
          onChange={(event) => onBranch(event.target.value)}
        >
          {remote === null ? (
            <option value="">{failed ? "—" : "fetching branches…"}</option>
          ) : (
            remote.branches.map((one) => (
              <option key={one} value={one}>
                {label(one)}
              </option>
            ))
          )}
        </select>
      )}
    </div>
  );
}

// A long branch list: a field that lists the branches holding what is typed.
function BranchCombo({
  id,
  remote,
  branch,
  onBranch,
  disabled,
}: {
  id: string;
  remote: RemoteInfo;
  branch: string | null;
  onBranch: (branch: string) => void;
  disabled: boolean;
}) {
  const [typed, setTyped] = useState<string | null>(null); // null: the branch chosen
  const [active, setActive] = useState(-1);
  const shown = typed ?? branch ?? "";
  const options = typed === null ? [] : remote.branches.filter((one) => one.includes(typed) && one !== typed);
  const pick = (one: string) => {
    onBranch(one);
    setTyped(null);
    setActive(-1);
  };
  return (
    <div className="where-box">
      <input
        id={id}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={options.length > 0}
        aria-controls={`${id}-list`}
        aria-activedescendant={active >= 0 && options[active] ? `${id}-option-${active}` : undefined}
        value={shown}
        autoComplete="off"
        spellCheck={false}
        disabled={disabled}
        onChange={(event) => {
          setTyped(event.target.value);
          setActive(-1);
          if (remote.branches.includes(event.target.value)) onBranch(event.target.value);
        }}
        onBlur={() => setTyped(null)}
        onKeyDown={(event) => {
          // Enter while typing picks the branch typed, or the one highlighted; text that is
          // no branch never submits the form with another branch than it shows.
          if (event.key === "Enter" && typed !== null) {
            event.preventDefault();
            if (active >= 0 && options[active]) pick(options[active]);
            else if (remote.branches.includes(typed)) pick(typed);
            return;
          }
          if (options.length === 0) return;
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            const step = event.key === "ArrowDown" ? 1 : -1;
            setActive((at) => (at + step + options.length) % options.length);
          } else if (event.key === "Escape") {
            event.preventDefault();
            setTyped(null);
          }
        }}
      />
      {options.length > 0 && (
        <ul id={`${id}-list`} role="listbox" aria-label="Branches" className="where-list">
          {options.map((one, i) => (
            <li
              key={one}
              id={`${id}-option-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(event) => {
                event.preventDefault(); // keep the input's focus
                pick(one);
              }}
            >
              {one === remote.default ? `${one} (default)` : one}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// What the human can do about the folder (the core's hint): its sentence, then its command
// to copy. When no copy works, the command is selected to copy by hand.
export function FolderHint({ text, command }: { text: string; command: string }) {
  const { note, copy } = useCopy();
  const [byHand, setByHand] = useState(false);
  const code = useRef<HTMLElement>(null);
  const onCopy = async () => {
    const done = await copy(command, "Command copied");
    setByHand(!done);
    if (!done && code.current) window.getSelection()?.selectAllChildren(code.current);
  };
  return (
    <div className="folder-hint">
      <div className="muted">{text}</div>
      <div className="folder-hint-command">
        <code ref={code}>{command}</code>
        <button type="button" className="chip-button" aria-label="Copy command" onClick={onCopy}>
          Copy
        </button>
      </div>
      <span role="status" className="muted">
        {note || (byHand ? "Press ⌘C / Ctrl+C to copy" : "")}
      </span>
    </div>
  );
}
