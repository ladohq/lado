// The New session window (docs/design/ui.md, Launch and session control): opened from the
// rail's Launch, the session list's "+", and in its Resume mode from a stopped session's
// Resume. What a folder is, which kits and providers there are and whether a name is taken
// all come from the server; the window decides nothing the core decides.
import { createContext, useContext, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router";

import {
  ApiError,
  getFolder,
  getKits,
  getProviders,
  getRecentFolders,
  resumeSession,
  startSession,
  type FolderInfo,
  type KitInfo,
  type ProviderInfo,
  type RecentFolder,
  type SessionInfo,
  type Started,
  type Taken,
} from "./api";
import { useLive } from "./live";
import { sessionPath } from "./paths";

// How long the window waits after a keystroke before it asks the server about the folder.
export const DEBOUNCE = 200;

const DEFAULT_KIT = "default";
const DEFAULT_MODE = "default"; // also "no mode given": the provider's own default

export type LaunchMode = { kind: "new" } | { kind: "resume"; session: SessionInfo };

const LaunchContext = createContext<(mode?: LaunchMode) => void>(() => {});

// Opens the New session window, or its Resume mode for a session.
export const useLaunch = () => useContext(LaunchContext);

// What a start or resume said, for the session's page to show (its problems until closed).
export type StartedState = { started: Started };

export function LaunchProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<LaunchMode | null>(null);
  return (
    <LaunchContext.Provider value={(next = { kind: "new" }) => setMode(next)}>
      {children}
      {mode && (
        <LaunchDialog
          key={mode.kind === "resume" ? `resume:${mode.session.name}` : "new"}
          mode={mode}
          onMode={setMode}
          onClose={() => setMode(null)}
        />
      )}
    </LaunchContext.Provider>
  );
}

function useDebounced<T>(value: T, ms = DEBOUNCE): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}

type Asked<T> = { value: T } | { error: string } | null; // null: asking

// The server's answer to `ask(key)`, asked again when `key` changes; nothing for a null key.
function useAsked<T>(key: string | null, ask: (key: string) => Promise<T>): Asked<T> {
  const [asked, setAsked] = useState<{ key: string; answer: Asked<T> } | null>(null);
  useEffect(() => {
    if (key === null) return;
    let current = true;
    ask(key).then(
      (value) => current && setAsked({ key, answer: { value } }),
      (error: unknown) => current && setAsked({ key, answer: { error: messageOf(error) } }),
    );
    return () => {
      current = false;
    };
    // `ask` is one of the API's functions: the same for the window's life.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return asked !== null && asked.key === key ? asked.answer : null;
}

function useOnce<T>(ask: () => Promise<T>, skip = false): Asked<T> {
  return useAsked(skip ? null : "", () => ask());
}

const messageOf = (error: unknown) => (error instanceof ApiError ? error.message : String(error));

const valueOf = <T,>(asked: Asked<T>): T | null => (asked !== null && "value" in asked ? asked.value : null);

// Where suggestions come from (N1): the folder up to the last "/" and the name typed after it.
function parentOf(path: string): { parent: string; prefix: string } | null {
  const slash = path.lastIndexOf("/");
  if (slash < 0) return null;
  return { parent: path.slice(0, slash + 1), prefix: path.slice(slash + 1) };
}

const splitWithout = (text: string) => text.split(/[\s,]+/).filter(Boolean);

const sameList = (a: string[], b: string[]) => a.length === b.length && a.every((one, i) => one === b[i]);

function LaunchDialog({
  mode,
  onMode,
  onClose,
}: {
  mode: LaunchMode;
  onMode: (mode: LaunchMode) => void;
  onClose: () => void;
}) {
  const resuming = mode.kind === "resume" ? mode.session : null;
  const dialog = useRef<HTMLDialogElement>(null);
  const navigate = useNavigate();
  const live = useLive();
  const ids = useId();

  const [path, setPath] = useState(resuming?.repo ?? "");
  const [name, setName] = useState<string | null>(resuming?.name ?? null); // null: the default
  const [kits, setKits] = useState<string[]>(resuming?.kits ?? [DEFAULT_KIT]);
  const [provider, setProvider] = useState<string | null>(resuming?.provider ?? null); // null: LADO's default
  const [permissionMode, setPermissionMode] = useState(resuming?.permission_mode ?? DEFAULT_MODE);
  const [without, setWithout] = useState(resuming?.without.join(", ") ?? "");
  const [touched, setTouched] = useState<Set<string>>(new Set());
  const [fromLast, setFromLast] = useState(false);
  const [modeNote, setModeNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<ApiError | null>(null);

  useEffect(() => {
    dialog.current?.showModal();
  }, []);

  const settled = useDebounced(path.trim());
  const checked = useAsked(resuming || !settled ? null : settled, getFolder);
  const folder = valueOf(checked);
  const current = folder !== null && folder.path === settled && settled === path.trim() ? folder : null;
  const recent = valueOf(useOnce(getRecentFolders, resuming !== null)) ?? [];
  const root = resuming?.repo ?? folder?.root ?? null;
  const kitList = useAsked(root ?? "", (where) => getKits(where || null));
  const providerList = useOnce(getProviders);
  const providers = valueOf(providerList);

  const chosenProvider = provider ?? providers?.find((one) => one.default)?.name ?? null;
  const providerInfo = providers?.find((one) => one.name === chosenProvider) ?? null;
  const modes = providerInfo?.permission_modes ?? [];

  // M5: kits, provider and mode of a new session come from the folder's last session.
  const last = resuming ? null : (recent.find((one) => one.path === folder?.root)?.session ?? null);
  useEffect(() => {
    if (resuming || folder === null) return;
    if (!touched.has("kits")) setKits(last?.kits ?? [DEFAULT_KIT]);
    if (!touched.has("provider")) setProvider(last?.provider ?? null);
    if (!touched.has("mode")) setPermissionMode(last?.permission_mode ?? DEFAULT_MODE);
    setFromLast(last !== null);
    // Again only when the folder's last session is another one.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [last?.name, folder?.root]);

  const touch = (field: string) => setTouched((before) => new Set(before).add(field));

  const shownName = name ?? current?.default_name ?? "";
  const resumable = (sessionName: string) => {
    const loaded = live.sessions;
    return loaded && "sessions" in loaded ? loaded.sessions.find((one) => one.name === sessionName) : undefined;
  };
  const resumeIt = (sessionName: string) => {
    const found = resumable(sessionName);
    if (found) onMode({ kind: "resume", session: found });
  };

  const chooseProvider = (next: string) => {
    touch("provider");
    setProvider(next);
    const info = providers?.find((one) => one.name === next);
    const supported = info?.permission_modes ?? [];
    if (permissionMode !== DEFAULT_MODE && !supported.includes(permissionMode)) {
      setModeNote(`${next} has no mode ${permissionMode}: set to default`);
      setPermissionMode(DEFAULT_MODE);
    } else {
      setModeNote(null);
    }
  };

  const ready = resuming !== null || (current?.ok ?? false);

  const submit = async () => {
    setBusy(true);
    setRefused(null);
    const off = splitWithout(without);
    try {
      let started: Started;
      if (resuming) {
        const changed: Record<string, unknown> = {};
        if (!sameList(kits, resuming.kits)) changed.kits = kits;
        if (chosenProvider !== null && chosenProvider !== resuming.provider) changed.provider = chosenProvider;
        if (permissionMode !== (resuming.permission_mode ?? DEFAULT_MODE)) changed.permission_mode = permissionMode;
        if (!sameList(off, resuming.without)) changed.without = off;
        started = await resumeSession(resuming.name, changed);
      } else {
        started = await startSession({
          where: { kind: "folder", path: path.trim() },
          ...(shownName ? { name: shownName } : {}),
          kits,
          ...(chosenProvider !== null ? { provider: chosenProvider } : {}),
          ...(permissionMode !== DEFAULT_MODE ? { permission_mode: permissionMode } : {}),
          ...(off.length ? { without: off } : {}),
        });
      }
      onClose();
      const state: StartedState = { started };
      navigate(sessionPath(started.session.name, "activity"), { state });
    } catch (error) {
      setRefused(error instanceof ApiError ? error : new ApiError(0, String(error)));
      setBusy(false);
    }
  };

  const title = resuming ? "Resume session" : "New session";
  const taken = refused?.status === 409 ? (refused.detail as Taken) : null;

  return (
    <dialog
      ref={dialog}
      className="launch-dialog"
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
      onKeyDown={(event) => {
        if (event.key !== "Escape" || event.defaultPrevented) return;
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (ready && !busy) void submit();
        }}
      >
        <div className="launch-head">
          <h2>{title}</h2>
          <button type="button" className="ghost" aria-label="Close" onClick={onClose} disabled={busy}>
            ×
          </button>
        </div>

        <WhereField
          path={path}
          onPath={(next) => {
            setPath(next);
            setRefused(null);
          }}
          folder={current}
          checking={!resuming && path.trim() !== "" && current === null}
          problem={checked !== null && "error" in checked ? checked.error : null}
          recent={recent}
          disabled={busy || resuming !== null}
        />

        <div className="launch-grid">
          <div className="field">
            <label htmlFor={`${ids}-name`}>Name</label>
            <input
              id={`${ids}-name`}
              value={shownName}
              disabled={busy || resuming !== null}
              onChange={(event) => setName(event.target.value)}
            />
            {!resuming && name === null && current && (
              <NameHint folder={current} onResume={() => resumeIt(current.default_name ?? "")} />
            )}
          </div>

          <KitsField
            root={root}
            listed={kitList}
            kits={kits}
            disabled={busy}
            fromLast={fromLast}
            onKits={(next) => {
              touch("kits");
              setKits(next);
            }}
          />

          <div className="field">
            <label htmlFor={`${ids}-provider`}>Provider</label>
            <select
              id={`${ids}-provider`}
              value={providers ? (chosenProvider ?? "") : ""}
              disabled={busy || providers === null}
              onChange={(event) => chooseProvider(event.target.value)}
            >
              {providers === null ? (
                <option value="">checking…</option>
              ) : (
                providers.map((one) => (
                  <option key={one.name} value={one.name} disabled={!one.installed}>
                    {one.installed ? `${one.name} · ${one.title} ${one.version}`.trim() : `${one.name} · not installed`}
                  </option>
                ))
              )}
            </select>
            <ProviderNote asked={providerList} info={providerInfo} chosen={chosenProvider} />
          </div>

          <div className="field">
            <label htmlFor={`${ids}-mode`}>Permission mode</label>
            <select
              id={`${ids}-mode`}
              value={modes.length ? permissionMode : DEFAULT_MODE}
              disabled={busy || modes.length === 0}
              onChange={(event) => {
                touch("mode");
                setModeNote(null);
                setPermissionMode(event.target.value);
              }}
            >
              {(modes.length ? modes : [DEFAULT_MODE]).map((one) => (
                <option key={one} value={one}>
                  {one}
                </option>
              ))}
            </select>
            <span className="field-note">
              {modeNote ??
                (providerInfo === null
                  ? ""
                  : modes.length
                    ? `the modes ${providerInfo.name} supports`
                    : `${providerInfo.name} takes no permission mode`)}
            </span>
          </div>
        </div>

        <details className="launch-advanced">
          <summary>Advanced: switch off agents, skills, MCP servers or flows</summary>
          <label className="field">
            Switch off
            <input
              value={without}
              disabled={busy}
              placeholder="agent:reviewer, skill:style"
              onChange={(event) => setWithout(event.target.value)}
            />
          </label>
          <span className="field-note">kind:name, separated by commas; kinds: agent, skill, mcp, flow</span>
        </details>

        {refused && (
          <div className="launch-refused">
            <p className="problem" role="alert">
              {refused.message}
            </p>
            {taken && taken.repo === root && resumable(shownName) && (
              <button type="button" className="quiet" onClick={() => resumeIt(shownName)}>
                Resume it
              </button>
            )}
          </div>
        )}

        <div className="launch-buttons">
          <button type="button" className="quiet" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={busy || !ready}>
            {busy ? (resuming ? "Resuming…" : "Starting…") : title === "New session" ? "Start session" : title}
          </button>
        </div>
      </form>
    </dialog>
  );
}

function WhereField({
  path,
  onPath,
  folder,
  checking,
  problem,
  recent,
  disabled,
}: {
  path: string;
  onPath: (path: string) => void;
  folder: FolderInfo | null;
  checking: boolean;
  problem: string | null;
  recent: RecentFolder[];
  disabled: boolean;
}) {
  const ids = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const split = parentOf(path);
  const parent = useDebounced(split?.parent ?? null);
  const listed = valueOf(useAsked(open && parent ? parent : null, getFolder));
  const prefix = (split?.prefix ?? "").toLowerCase();
  const options =
    open && listed && split && listed.path === split.parent
      ? listed.subfolders.filter((one) => one.toLowerCase().startsWith(prefix))
      : [];

  const pick = (folderName: string) => {
    if (!split) return;
    onPath(split.parent + folderName);
    setOpen(false);
    setActive(-1);
  };

  return (
    <div className="field launch-where">
      <label htmlFor={`${ids}-where`}>
        Where <span className="muted">· a folder (projects come later)</span>
      </label>
      <div className="where-box">
        <input
          id={`${ids}-where`}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={options.length > 0}
          aria-controls={`${ids}-folders`}
          aria-activedescendant={active >= 0 && options[active] ? `${ids}-folder-${active}` : undefined}
          value={path}
          placeholder="~/projects/app"
          autoComplete="off"
          spellCheck={false}
          disabled={disabled}
          onChange={(event) => {
            onPath(event.target.value);
            setOpen(true);
            setActive(-1);
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
      {recent.length > 0 && !disabled && (
        <div className="recent">
          Recent:
          {recent.map((one) => (
            <button key={one.path} type="button" className="chip-button" onClick={() => onPath(one.path)}>
              {one.path}
            </button>
          ))}
        </div>
      )}
      {folder?.ok && (
        <span className="field-note ok">
          ✓ git repository{folder.branch ? ` · branch ${folder.branch}` : ""}
        </span>
      )}
      {folder && !folder.ok && <span className="field-note bad">{folder.problem}</span>}
      {problem && <span className="field-note bad">{problem}</span>}
      {checking && !problem && <span className="field-note">checking…</span>}
    </div>
  );
}

function NameHint({ folder, onResume }: { folder: FolderInfo; onResume: () => void }) {
  const name = folder.default_name;
  if (folder.name_state === "running") return <span className="field-note">"{name}" is taken by a running session</span>;
  if (folder.name_state === "taken_elsewhere") {
    return <span className="field-note">"{name}" is taken by a session of another folder</span>;
  }
  if (folder.name_state === "stopped_here") {
    return (
      <span className="field-note">
        a stopped session {name} exists for this folder{" "}
        <button type="button" className="link-button" onClick={onResume}>
          Resume it
        </button>
      </span>
    );
  }
  return null;
}

function KitsField({
  root,
  listed,
  kits,
  disabled,
  fromLast,
  onKits,
}: {
  root: string | null;
  listed: Asked<KitInfo[]>;
  kits: string[];
  disabled: boolean;
  fromLast: boolean;
  onKits: (kits: string[]) => void;
}) {
  const id = useId();
  const known = valueOf(listed) ?? [];
  const others = known.filter((one) => !kits.includes(one.name));
  return (
    <div className="field">
      <span id={id} className="field-label">
        Kits
      </span>
      <div role="group" aria-labelledby={id} className="kits-box">
        {kits.map((name) => {
          const info = known.find((one) => one.name === name);
          return (
            <span key={name} className={`chip${info && !info.valid ? " invalid" : ""}`} title={info?.problem ?? undefined}>
              <span>{name}</span>
              {info?.version && <span className="muted"> {info.version}</span>}
              <button
                type="button"
                aria-label={`Remove ${name}`}
                disabled={disabled}
                onClick={() => onKits(kits.filter((one) => one !== name))}
              >
                ×
              </button>
            </span>
          );
        })}
        {others.length > 0 && (
          <select
            aria-label="Add kit"
            className="add-kit"
            value=""
            disabled={disabled}
            onChange={(event) => event.target.value && onKits([...kits, event.target.value])}
          >
            <option value="">+ Add kit</option>
            {others.map((one) => (
              <option key={one.name} value={one.name} disabled={!one.valid}>
                {one.valid
                  ? `${one.name}${one.version ? ` ${one.version}` : ""}`
                  : `${one.name} · invalid: run lado kits check ${one.name}`}
              </option>
            ))}
          </select>
        )}
      </div>
      {listed !== null && "error" in listed && <span className="field-note bad">{listed.error}</span>}
      {fromLast && <span className="field-note">from the last session of this folder</span>}
      {root === null && listed === null && <span className="field-note">checking…</span>}
    </div>
  );
}

function ProviderNote({
  asked,
  info,
  chosen,
}: {
  asked: Asked<ProviderInfo[]>;
  info: ProviderInfo | null;
  chosen: string | null;
}) {
  if (asked !== null && "error" in asked) return <span className="field-note bad">{asked.error}</span>;
  if (asked === null) return <span className="field-note">checking the agent CLIs…</span>;
  if (info === null) return chosen ? <span className="field-note bad">unknown provider {chosen}</span> : null;
  if (!info.installed) return <span className="field-note bad">{`${info.detail}; ${info.install_hint}`}</span>;
  if (info.warning) return <span className="field-note warn">⚠ {info.warning}</span>;
  return null;
}
