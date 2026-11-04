// Settings → Models (docs/design/ui.md, Models): one section, no tabs, an intro and three
// blocks: Your models, the configured models in a card per agent CLI that has some; Model
// servers and Models of your agent CLIs, where models come from (ModelSources.tsx). What the
// commands `lado model-server` and `lado model` do, with their rules and lines: every refusal
// is the core's line under the field it names. The entries are read when the section opens
// and after each change of its own (GET /api/model-settings asks no server); opening it reads
// no source. Nothing under the pointer moves (useScrollAnchor) and no row leaves on a timer:
// the page scrolls to the section once, when it opens at #models, and keeps it at the top while
// the sections above grow, until the human acts; a model removed by × leaves its row as Undo,
// then as a line, until the human's next change here.
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useLocation } from "react-router";

import {
  addModel,
  type ConfiguredModelInfo,
  type EntryRefused,
  getModelSettings,
  getProviderLogins,
  type ModelSettings as Entries,
  type ProviderLogins,
  refusalOf,
  removeModel,
  renameModel,
} from "./api";
import { CloseIcon } from "./icons";
import {
  CliModels,
  cliKey,
  listed,
  ModelServers,
  type Read,
  type Saved,
  serverKey,
  type Sources,
} from "./ModelSources";
import { MODELS_ANCHOR } from "./paths";
import { POLL_MS } from "./Providers";
import { messageOf } from "./SessionControl";
import { keepAtTop, useScrollAnchor } from "./useScrollAnchor";

export const INTRO =
  "Name the models your agents run on: an agent CLI, its model and, if the model lives elsewhere, a model server. Without any, each agent runs on its agent CLI's default model.";
export const EMPTY = "No models yet. Without them each agent runs on its agent CLI's default model.";
export const EMPTY_HOW = "Add a model server below, or tick the models your agent CLIs already offer.";
// Reads of the CLIs' rows at most while they are not read yet.
const LOGIN_POLLS = 30;
// How long a model removed by × offers Undo; its row then stays as a line.
export const UNDO_MS = 10000;

// A model removed by ×: its row offers Undo (`expired`: no more), saying why Undo was refused.
type Removed = {
  model: ConfiguredModelInfo;
  problem: string | null;
  busy: boolean;
  expired: boolean;
};

const fold = (text: string) => text.toLowerCase();
const byName = (a: ConfiguredModelInfo, b: ConfiguredModelInfo) => fold(a.name).localeCompare(fold(b.name));

export function ModelSettings() {
  const id = useId();
  const [entries, setEntries] = useState<Entries | null>(null);
  const [logins, setLogins] = useState<ProviderLogins[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  const [reads, setReads] = useState<Record<string, Read>>({});
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [saved, setSaved] = useState<Record<string, Saved>>({});
  const [removed, setRemoved] = useState<Record<string, Removed>>({});
  // The names of models unticked here, by their tick's key, while the page stays open: a
  // tick again saves the model under its name (a mis-click loses no name).
  const [names, setNames] = useState<Record<string, string>>({});
  const [focusName, setFocusName] = useState<string | null>(null); // after Undo
  const section = useRef<HTMLElement>(null);
  const latest = useRef(0);
  const reading = useRef<Record<string, number>>({}); // each source's latest read (ModelSources)
  const scrolled = useRef(false);
  const { hash } = useLocation();
  useScrollAnchor(section);

  const reload = useCallback(async (given?: Entries) => {
    const asked = ++latest.current;
    try {
      const found = given ?? (await getModelSettings());
      if (asked !== latest.current) return;
      // A server of another version may answer otherwise (the banner says it is one).
      if (!Array.isArray(found?.models) || !Array.isArray(found?.servers))
        throw new Error("the server gave no models: reload the page");
      setEntries(found);
      setProblem(null);
    } catch (error) {
      if (asked === latest.current) setProblem(messageOf(error));
    }
  }, []);
  useEffect(() => {
    void reload();
    return () => {
      latest.current++;
    };
  }, [reload]);
  // The CLIs' install and login as Agent CLIs and environment's last check read them; read
  // again while that check runs (it starts with the page), never a check of its own.
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let left = LOGIN_POLLS;
    let current = true;
    const take = () =>
      getProviderLogins().then(
        (page) => {
          if (!current || !Array.isArray(page?.providers)) return;
          setLogins(page.providers);
          if ((page.checking || page.providers.some((p) => !p.ready)) && --left > 0) timer = setTimeout(take, POLL_MS);
        },
        () => undefined, // Agent CLIs and environment says why
      );
    void take();
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, []);
  // Once, when the page opens at #models, kept at the top until the human acts: never after
  // a change of the entries.
  const keeping = useRef<(() => void) | null>(null);
  useEffect(() => {
    if (!entries || scrolled.current) return;
    scrolled.current = true;
    if (hash === `#${MODELS_ANCHOR}` && section.current) keeping.current = keepAtTop(section.current);
  }, [entries, hash]);
  useEffect(() => () => keeping.current?.(), []);

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
  // The human's next change in the section: the lines of models removed by × whose Undo ran
  // out go.
  const onTouch = useCallback(
    () => setRemoved((now) => Object.fromEntries(Object.entries(now).filter(([, gone]) => !gone.expired))),
    [],
  );
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
  const set = (name: string, gone: Removed | null) =>
    setRemoved((now) => {
      const next = { ...now };
      if (gone) next[fold(name)] = gone;
      else delete next[fold(name)];
      return next;
    });
  const onRemoved = (model: ConfiguredModelInfo) => {
    onTouch();
    set(model.name, { model, problem: null, busy: false, expired: false });
  };
  const undo = async (gone: Removed) => {
    const { model } = gone;
    onTouch();
    set(model.name, { ...gone, busy: true, problem: null });
    try {
      await addModel({
        name: model.name,
        cli: model.cli,
        model: model.model,
        server: model.server,
      });
    } catch (error) {
      set(model.name, {
        ...gone,
        busy: false,
        problem: refusalOf(error).message,
      });
      void reload();
      return;
    }
    // The Undo row goes only once the reload has brought the model back: nothing moves.
    await reload();
    setFocusName(model.name);
    set(model.name, null);
  };

  const sources: Sources = {
    settings: entries ?? { models: [], servers: [] },
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
  };
  const count = entries?.models.length ?? 0;
  return (
    <section className="setting mx" id={MODELS_ANCHOR} ref={section} aria-labelledby={id}>
      <h2 id={id}>Models</h2>
      <p className="mx-intro">{INTRO}</p>
      {problem && (
        <p className="problem" role="alert">
          {problem}
        </p>
      )}
      {entries && (
        <>
          <div className="mx-block">
            <h3>
              Your models <span className="mx-count">{count}</span>
            </h3>
            <YourModels
              entries={entries}
              logins={logins}
              reads={reads}
              removed={removed}
              focusName={focusName}
              onFocused={() => setFocusName(null)}
              onChanged={reload}
              onTouch={onTouch}
              onRemoved={onRemoved}
              onUndo={(gone) => void undo(gone)}
              onExpired={(gone) => set(gone.model.name, { ...gone, expired: true })}
            />
          </div>
          <ModelServers {...sources} />
          <CliModels {...sources} />
        </>
      )}
    </section>
  );
}

// The warning of a configured model whose source's list, as last read here, lacks it.
function goneOf(model: ConfiguredModelInfo, reads: Record<string, Read>): string | null {
  const has = listed(reads[model.server === null ? cliKey(model.cli) : serverKey(model.server)]);
  if (has === null || has.has(model.model)) return null;
  return `${model.server ?? model.cli_title} no longer lists ${model.model}: agents on it stop at their first turn.`;
}

type Card = { cli: string; title: string; off: boolean };

// Your models: a card per agent CLI that has models, in LADO's order of agent CLIs, then one
// for a model of a CLI it does not know; a card's models by name ignoring case, a model removed
// by × in its place as its Undo row; under the cards one line names the CLIs without models.
function YourModels({
  entries,
  logins,
  reads,
  removed,
  focusName,
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
  removed: Record<string, Removed>;
  focusName: string | null;
  onFocused: () => void;
  onChanged: (given?: Entries) => Promise<void>;
  onTouch: () => void;
  onRemoved: (model: ConfiguredModelInfo) => void;
  onUndo: (gone: Removed) => void;
  onExpired: (gone: Removed) => void;
}) {
  const gone = Object.values(removed);
  const all = [...entries.models, ...gone.map((g) => g.model)];
  if (all.length === 0)
    return (
      <div className="mx-empty">
        <p>{EMPTY}</p>
        <p className="muted">{EMPTY_HOW}</p>
      </div>
    );
  const cards: Card[] = logins.map((row) => ({
    cli: row.cli.name,
    title: row.cli.title,
    off: row.ready && !row.cli.installed,
  }));
  for (const m of all)
    if (!cards.some((c) => c.cli === m.cli)) cards.push({ cli: m.cli, title: m.cli_title, off: false });
  const shown = cards.filter((c) => all.some((m) => m.cli === c.cli));
  const none = cards.filter((c) => !shown.includes(c)).map((c) => c.title);
  const servers = new Map(entries.servers.map((s) => [fold(s.name), s.address]));
  return (
    <>
      <div className="mx-cards">
        {shown.map((card) => {
          const live = entries.models.filter((m) => m.cli === card.cli);
          const rows = [
            ...live.map((model) => ({ model, gone: null as Removed | null })),
            ...gone
              .filter((g) => g.model.cli === card.cli && !live.some((m) => fold(m.name) === fold(g.model.name)))
              .map((g) => ({ model: g.model, gone: g })),
          ].sort((a, b) => byName(a.model, b.model));
          return (
            <div key={card.cli} className="mx-card" role="group" aria-label={card.title} data-anchor="">
              <div className="mx-card-h">
                <span>{card.title}</span>
                <span className="mx-count">{live.length}</span>
                {card.off && <span className="mx-card-warn">⚠ not installed: its models cannot run</span>}
              </div>
              <div className="mx-table" role="table" aria-label={`${card.title}'s models`}>
                <div className="mx-mrow mx-mhead" role="row">
                  <span role="columnheader">Name</span>
                  <span role="columnheader">Model</span>
                  <span role="columnheader">From</span>
                  <span role="columnheader" aria-label="Remove" />
                </div>
                {rows.map(({ model, gone }) =>
                  gone ? (
                    <UndoRow key={`removed:${model.name}`} gone={gone} onUndo={onUndo} onExpired={onExpired} />
                  ) : (
                    <ModelRow
                      key={model.name}
                      model={model}
                      address={model.server ? servers.get(fold(model.server)) : undefined}
                      gone={goneOf(model, reads)}
                      focus={focusName !== null && fold(focusName) === fold(model.name)}
                      onFocused={onFocused}
                      onChanged={onChanged}
                      onTouch={onTouch}
                      onRemoved={onRemoved}
                    />
                  ),
                )}
              </div>
            </div>
          );
        })}
      </div>
      {none.length > 0 && (
        <p className="mx-rest">
          {none.length === 1
            ? `${none[0]} has no models: its agents run on its default model.`
            : `${none.join(", ")} have no models: their agents run on their default model.`}
        </p>
      )}
    </>
  );
}

function UndoRow({
  gone,
  onUndo,
  onExpired,
}: {
  gone: Removed;
  onUndo: (gone: Removed) => void;
  onExpired: (gone: Removed) => void;
}) {
  const { model, problem, busy, expired } = gone;
  // Undo goes after UNDO_MS, kept while it runs or was refused (to say why); the row stays.
  const latest = useRef(gone);
  latest.current = gone;
  useEffect(() => {
    if (problem || busy || expired) return;
    const timer = setTimeout(() => onExpired(latest.current), UNDO_MS);
    return () => clearTimeout(timer);
  }, [problem, busy, expired, onExpired]);
  return (
    <div className="mx-mrow mx-undo" role="row">
      <span role="cell">
        <span role="status">
          Removed <b>{model.name}</b>.
        </span>
        {problem && <span className="field-note bad">{problem}</span>}
      </span>
      {!expired && (
        // × hands the focus to its Undo.
        <button type="button" className="link-button" autoFocus disabled={busy} onClick={() => onUndo(gone)}>
          Undo
        </button>
      )}
    </div>
  );
}

function ModelRow({
  model,
  address,
  gone,
  focus,
  onFocused,
  onChanged,
  onTouch,
  onRemoved,
}: {
  model: ConfiguredModelInfo;
  address: string | undefined;
  gone: string | null;
  focus: boolean;
  onFocused: () => void;
  onChanged: (given?: Entries) => Promise<void>;
  onTouch: () => void;
  onRemoved: (model: ConfiguredModelInfo) => void;
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
  const remove = async () => {
    setProblem(null);
    try {
      const left = await removeModel(model.name);
      onRemoved(model);
      await onChanged(left);
    } catch (error) {
      setProblem(refusalOf(error).message);
    }
  };
  return (
    <div className="mx-mrow" role="row">
      <span className="mx-nm" role="cell">
        {renaming ? (
          <Rename
            name={model.name}
            onDone={(given) => {
              onTouch();
              setRenaming(false);
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
        {problem && <span className="field-note bad">{problem}</span>}
      </span>
      <span className="mx-meta">
        <span className="mx-model mono" role="cell" title={model.model}>
          {model.model}
        </span>
        {model.server ? (
          <span className="mx-from" role="cell" title={address}>
            {model.server}
          </span>
        ) : (
          <span className="mx-from muted" role="cell">
            the agent CLI
          </span>
        )}
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
  onDone: (given: Entries) => void;
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
      onDone(given);
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
