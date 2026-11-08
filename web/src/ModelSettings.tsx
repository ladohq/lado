// Settings → Model servers (docs/design/ui.md, Model servers): two blocks, Servers, where the
// human's models come from (ModelSources.tsx), then Your models, one table of them all with the
// agent CLI each runs in, its default marked. What the commands `lado model-server` and `lado
// model` do, with their rules and lines: every refusal is the core's line under the field it
// names. The entries are read when the page opens and after each change of its own
// (useModelSettings; GET /api/model-settings asks no server); opening it reads no source.
// Nothing under the pointer moves (useScrollAnchor) and no row leaves on a timer: removing a
// model asks nothing, a default's too; one removed by × leaves its row as Undo, then as a line,
// until the human's next change here (removedModels.tsx, shared with the ticks).
// Each CLI's default is picked on Agent CLIs (CliDefault.tsx).
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router";

import {
  checkProviders,
  type ConfiguredModelInfo,
  type EntryRefused,
  getProviderLogins,
  type ModelSettings as Entries,
  type ProviderLogins,
  type ProvidersPage,
  refusalOf,
  removeModel,
  renameModel,
} from "./api";
import { CloseIcon } from "./icons";
import { listed, ModelServers, type Read, type Saved, serverKey, type Sources } from "./ModelSources";
import { agentClisPath } from "./paths";
import { POLL_MS } from "./Providers";
import { type Removed, UndoLine, useRemovedModels } from "./removedModels";
import { SettingsPage } from "./SettingsPage";
import { useModelSettings } from "./useModelSettings";
import { useScrollAnchor } from "./useScrollAnchor";

// Reads of the CLIs' rows at most while they are not read yet.
const LOGIN_POLLS = 30;

const fold = (text: string) => text.toLowerCase();

export function ModelSettings() {
  const { entries, problem, reload } = useModelSettings();
  const [logins, setLogins] = useState<ProviderLogins[]>([]);
  const [reads, setReads] = useState<Record<string, Read>>({});
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [saved, setSaved] = useState<Record<string, Saved>>({});
  const removed = useRemovedModels(reload);
  // The names of models unticked here, by their tick's key, while the page stays open: a
  // tick again saves the model under its name (a mis-click loses no name).
  const [names, setNames] = useState<Record<string, string>>({});
  const [focusName, setFocusName] = useState<string | null>(null); // after Undo
  const section = useRef<HTMLElement>(null);
  const reading = useRef<Record<string, number>>({}); // each source's latest read (ModelSources)
  useScrollAnchor(section);

  // The CLIs' install and login: the page asks for a check when it opens, as Agent CLIs does
  // (a server just started has read none; one that runs goes on), then reads the rows while
  // it runs. The columns of a server's model name only the CLIs found installed.
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let left = LOGIN_POLLS;
    let current = true;
    const take = (ask: () => Promise<ProvidersPage> = getProviderLogins) =>
      ask().then(
        (page) => {
          if (!current || !Array.isArray(page?.providers)) return;
          setLogins(page.providers);
          if ((page.checking || page.providers.some((p) => !p.ready)) && --left > 0)
            timer = setTimeout(() => void take(), POLL_MS);
        },
        () => undefined, // Agent CLIs says why
      );
    void take(checkProviders);
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, []);

  const onRead = useCallback((key: string, read: Read | null) => {
    setReads((now) => {
      const next = { ...now };
      if (read === null) delete next[key];
      else next[key] = read;
      return next;
    });
  }, []);
  const onOpen = useCallback((key: string, opening: boolean) => {
    setOpen((now) => {
      const next = new Set(now);
      if (opening) next.add(key);
      else next.delete(key);
      return next;
    });
  }, []);
  // The lines of a server's add or change belong to the last such action.
  const onSaved = useCallback((key: string, done: Saved | null) => {
    setSaved((now) => {
      if (done !== null) return { [key]: done };
      const next = { ...now };
      delete next[key];
      return next;
    });
  }, []);
  // The human's next change on the page: the lines of removed models whose Undo ran out go,
  // and the lines of the last server added or changed.
  const touchRemoved = removed.touch;
  const onTouch = useCallback(() => {
    touchRemoved();
    setSaved((now) => (Object.keys(now).length ? {} : now));
  }, [touchRemoved]);
  const onName = useCallback(
    (key: string, name: string | null) =>
      setNames((now) => {
        const next = { ...now };
        if (name === null) delete next[key];
        else next[key] = name;
        return next;
      }),
    [],
  );
  const onRemoved = (model: ConfiguredModelInfo, wasDefault: boolean) => {
    onTouch();
    removed.add(model, wasDefault, null);
  };
  const undo = async (gone: Removed) => {
    onTouch();
    if (await removed.undo(gone)) setFocusName(gone.model.name);
  };

  const sources: Sources = {
    settings: entries ?? { models: [], servers: [], defaults: [] },
    logins,
    reads,
    onRead,
    open,
    onOpen,
    saved,
    onSaved,
    onChanged: reload,
    latest: reading,
    onTouch,
    names,
    onName,
    removed,
  };
  return (
    <SettingsPage slug="model-servers" className="setting mx" ref={section}>
      {problem && (
        <p className="problem" role="alert">
          {problem}
        </p>
      )}
      {entries && (
        <>
          <ModelServers {...sources} />
          <YourModels
            entries={entries}
            logins={logins}
            reads={reads}
            removed={removed.list.filter((gone) => gone.at === null)}
            focusName={focusName}
            onFocusName={setFocusName}
            onFocused={() => setFocusName(null)}
            onChanged={reload}
            onTouch={onTouch}
            onRemoved={onRemoved}
            onUndo={(gone) => void undo(gone)}
            onExpired={removed.expire}
          />
        </>
      )}
    </SettingsPage>
  );
}

// The warning of a configured model whose server's list, as last read here, lacks it.
function goneOf(model: ConfiguredModelInfo, reads: Record<string, Read>): string | null {
  const has = listed(reads[serverKey(model.server)]);
  if (has === null || has.has(model.model)) return null;
  return `${model.server} no longer lists ${model.model}: agents on it stop at their first turn.`;
}

// Why a server, as last read here, does not answer; null when it answered or was not read.
function downOf(server: string, reads: Record<string, Read>): string | null {
  const read = reads[serverKey(server)];
  return read && "refused" in read ? read.refused.message : null;
}

// Your models: every configured model in one table, by agent CLI in LADO's order (a CLI LADO
// does not know last), then by name; a model removed by × keeps its place as Undo (`removed`:
// those of ×; one unticked leaves its line under its tick only).
function YourModels({
  entries,
  logins,
  reads,
  removed,
  focusName,
  onFocusName,
  onFocused,
  onChanged,
  onTouch,
  onRemoved,
  onUndo,
  onExpired,
}: {
  entries: Entries;
  logins: ProviderLogins[];
  reads: Record<string, Read>;
  removed: Removed[];
  focusName: string | null;
  onFocusName: (name: string) => void;
  onFocused: () => void;
  onChanged: (given?: Entries) => Promise<void>;
  onTouch: () => void;
  onRemoved: (model: ConfiguredModelInfo, wasDefault: boolean) => void;
  onUndo: (gone: Removed) => void;
  onExpired: (gone: Removed) => void;
}) {
  const id = useId();
  const table = useRef<HTMLDivElement>(null);
  const live = entries.models;
  const gone = removed.filter((g) => !live.some((m) => fold(m.name) === fold(g.model.name)));
  // Why Undo brought a model back without its default, by its folded name.
  const notes = new Map(removed.filter((g) => g.back).map((g) => [fold(g.model.name), g.problem]));
  if (live.length + gone.length === 0 && entries.servers.length === 0) return null;
  const order = (cli: string) => {
    const at = logins.findIndex((row) => row.cli.name === cli);
    return at < 0 ? logins.length : at;
  };
  const rows = [
    ...live.map((model) => ({ model, gone: null as Removed | null })),
    ...gone.map((g) => ({ model: g.model, gone: g as Removed | null })),
  ].sort(
    (a, b) =>
      order(a.model.cli) - order(b.model.cli) ||
      a.model.cli.localeCompare(b.model.cli) ||
      fold(a.model.name).localeCompare(fold(b.model.name)),
  );
  const defaults = new Set(entries.defaults.map((d) => d.external).filter(Boolean));
  const servers = new Map(entries.servers.map((s) => [fold(s.name), s.address]));
  return (
    <section className="mx-block" aria-labelledby={id}>
      <h3 id={id}>
        Your models {live.length > 0 && <span className="mx-count">{live.length}</span>}
      </h3>
      {rows.length === 0 ? (
        <p className="mx-lead">None yet: open a server and tick the agent CLIs that run a model.</p>
      ) : (
        <>
          <p className="mx-lead">
            Pick one as a default in <Link to={agentClisPath()}>Agent CLIs</Link>.
          </p>
          <div className="mx-table yours-table" role="table" aria-label="Your models" ref={table} tabIndex={-1}>
            <div className="mx-mrow yours mx-mhead" role="row">
              <span role="columnheader">Name</span>
              <span role="columnheader">Model</span>
              <span role="columnheader">From</span>
              <span role="columnheader">Agent CLI</span>
              <span role="columnheader" aria-label="Remove" />
            </div>
            {rows.map(({ model, gone }) =>
              gone ? (
                <UndoLine
                  key={`removed:${model.name}`}
                  className="mx-mrow mx-undo"
                  row
                  gone={gone}
                  onUndo={onUndo}
                  onExpired={onExpired}
                  onLeft={() => table.current?.focus({ preventScroll: true })}
                />
              ) : (
                <ModelRow
                  key={model.id}
                  model={model}
                  isDefault={defaults.has(model.id)}
                  address={servers.get(fold(model.server))}
                  gone={goneOf(model, reads)}
                  down={downOf(model.server, reads)}
                  note={notes.get(fold(model.name)) ?? null}
                  focus={focusName !== null && fold(focusName) === fold(model.name)}
                  onFocused={onFocused}
                  onRenamed={(name, back) => back && onFocusName(name)}
                  onChanged={onChanged}
                  onTouch={onTouch}
                  onRemoved={onRemoved}
                />
              ),
            )}
          </div>
        </>
      )}
    </section>
  );
}

function ModelRow({
  model,
  isDefault,
  address,
  gone,
  down,
  note,
  focus,
  onFocused,
  onRenamed,
  onChanged,
  onTouch,
  onRemoved,
}: {
  model: ConfiguredModelInfo;
  isDefault: boolean;
  address: string | undefined;
  gone: string | null;
  down: string | null; // why its server does not answer, as last read here
  note: string | null;
  focus: boolean;
  onFocused: () => void;
  onRenamed: (name: string, focusBack: boolean) => void;
  onChanged: (given?: Entries) => Promise<void>;
  onTouch: () => void;
  onRemoved: (model: ConfiguredModelInfo, wasDefault: boolean) => void;
}) {
  const [renaming, setRenaming] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const name = useRef<HTMLButtonElement>(null);
  const refocus = useRef(false);
  useEffect(() => {
    if (!focus) return;
    name.current?.focus();
    onFocused();
  }, [focus, onFocused]);
  useEffect(() => {
    if (renaming || !refocus.current) return;
    refocus.current = false;
    name.current?.focus();
  }, [renaming]);
  // A default too goes at once: the answer's `cleared` says whether one went (this page may
  // not have known), and Undo sets it again.
  const remove = async () => {
    setProblem(null);
    try {
      const left = await removeModel(model.name);
      onRemoved(model, left.cleared.includes(model.cli));
      await onChanged(left);
    } catch (error) {
      setProblem(refusalOf(error).message);
    }
  };
  return (
    <div className="mx-mrow yours" role="row">
      <span className="mx-nm" role="cell">
        {renaming ? (
          <Rename
            name={model.name}
            onDone={(given, name, back) => {
              onTouch();
              setRenaming(false);
              onRenamed(name, back);
              void onChanged(given);
            }}
            onCancel={(back) => {
              refocus.current = back;
              setRenaming(false);
            }}
          />
        ) : (
          <button
            ref={name}
            type="button"
            className="mx-name"
            title="Click to rename"
            aria-label={`Rename ${model.name}`}
            onClick={() => setRenaming(true)}
          >
            {model.name}
          </button>
        )}
        {gone && (
          <span className="mx-flag" title={gone}>
            ⚠ not in list
          </span>
        )}
        {(problem ?? note) && <span className="field-note bad">{problem ?? note}</span>}
      </span>
      <span className="mx-meta">
        <span className="mx-model mono" role="cell" title={model.model}>
          {model.model}
        </span>
        <span
          className={`mx-from${down ? " mx-from-down" : ""}`}
          role="cell"
          title={[model.server, address, down].filter(Boolean).join(" · ")}
        >
          {down ? `⚠ ${model.server}` : model.server}
        </span>
        <span className="mx-cli" role="cell">
          {isDefault ? `${model.cli_title} · default` : model.cli_title}
        </span>
      </span>
      <span className="mx-x-cell" role="cell">
        <button
          type="button"
          className="mx-icon"
          title="Remove"
          aria-label={`Remove ${model.name}`}
          onClick={() => void remove()}
        >
          <CloseIcon />
        </button>
      </span>
    </div>
  );
}

// The name as a field of its cell: Enter or leaving it renames, Esc restores (the focus back
// on the name); a refusal keeps the field with the refusal under it, and leaving it then
// restores the name.
function Rename({
  name,
  onDone,
  onCancel,
}: {
  name: string;
  onDone: (given: Entries, name: string, focusBack: boolean) => void;
  onCancel: (focusBack: boolean) => void;
}) {
  const id = useId();
  const [text, setText] = useState(name);
  const [refused, setRefused] = useState<EntryRefused | null>(null);
  const busy = useRef(false);
  const done = useRef(false);
  const save = async (leaving: boolean) => {
    if (busy.current || done.current) return;
    if (leaving && refused) return onCancel(false);
    if (text === name) {
      done.current = true;
      return onCancel(!leaving);
    }
    busy.current = true;
    try {
      const given = await renameModel(name, text);
      done.current = true;
      onDone(given, text, !leaving);
    } catch (error) {
      setRefused(refusalOf(error));
    } finally {
      busy.current = false;
    }
  };
  return (
    <span className="mx-name-edit">
      <input
        className="mx-rename"
        aria-label={`Name of ${name}`}
        aria-invalid={refused ? true : undefined}
        aria-describedby={refused ? id : undefined}
        value={text}
        maxLength={64}
        autoFocus
        onFocus={(event) => event.target.select()}
        onChange={(event) => {
          setText(event.target.value);
          setRefused(null);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            void save(false);
          }
          if (event.key === "Escape") {
            event.preventDefault();
            done.current = true;
            onCancel(true);
          }
        }}
        onBlur={() => void save(true)}
      />
      {refused && (
        <span className="field-note bad" id={id} role="alert">
          {refused.message}
        </span>
      )}
    </span>
  );
}
