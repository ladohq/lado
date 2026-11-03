// Settings → Models (docs/design/ui.md, Models): two tabs, Your models, the configured models
// in a card per agent CLI, and Add models, where models come from (ModelSources.tsx). What the
// commands `lado model-server` and `lado model` do, with their rules and lines: every refusal
// is the core's line under the field it names. The entries are read when the section opens
// and after each change of its own (GET /api/model-settings asks no server); opening it reads
// no source. Nothing above the control acted on moves: the page scrolls to the section once,
// when it opens at #models; a model removed leaves its row as Undo, of the same height.
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
import { cliKey, listed, ModelSources, type Read, type Saved, serverKey } from "./ModelSources";
import { MODELS_ANCHOR } from "./paths";
import { POLL_MS } from "./Providers";
import { messageOf } from "./SessionControl";

export const EMPTY = "No models yet. Without them each agent runs on its CLI's default model.";
// Reads of the CLIs' rows at most while they are not read yet.
const LOGIN_POLLS = 30;
// How long a removed model's Undo stays.
export const UNDO_MS = 10000;

type Tab = "mine" | "add";
// A model removed here, by its tick or ×: its row offers Undo, saying why Undo was refused.
type Removed = { model: ConfiguredModelInfo; problem: string | null; busy: boolean };

const fold = (text: string) => text.toLowerCase();
const byName = (a: ConfiguredModelInfo, b: ConfiguredModelInfo) => fold(a.name).localeCompare(fold(b.name));

export function ModelSettings() {
  const id = useId();
  const [entries, setEntries] = useState<Entries | null>(null);
  const [logins, setLogins] = useState<ProviderLogins[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("mine");
  const [reads, setReads] = useState<Record<string, Read>>({});
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [saved, setSaved] = useState<Record<string, Saved>>({});
  const [removed, setRemoved] = useState<Record<string, Removed>>({});
  const section = useRef<HTMLElement>(null);
  const latest = useRef(0);
  const reading = useRef<Record<string, number>>({}); // each source's latest read (ModelSources)
  const scrolled = useRef(false);
  const { hash } = useLocation();

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
  // Once, when the page opens at #models: never after a change of the entries.
  useEffect(() => {
    if (!entries || scrolled.current) return;
    scrolled.current = true;
    if (hash === `#${MODELS_ANCHOR}`) section.current?.scrollIntoView({ block: "start" });
  }, [entries, hash]);

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
  const onRemoved = useCallback(
    (model: ConfiguredModelInfo) =>
      setRemoved((now) => ({ ...now, [fold(model.name)]: { model, problem: null, busy: false } })),
    [],
  );
  const forget = useCallback(
    (name: string) =>
      setRemoved((now) => {
        const next = { ...now };
        delete next[fold(name)];
        return next;
      }),
    [],
  );
  const undo = async (gone: Removed) => {
    const { model } = gone;
    setRemoved((now) => ({ ...now, [fold(model.name)]: { ...gone, busy: true, problem: null } }));
    try {
      await addModel({ name: model.name, cli: model.cli, model: model.model, server: model.server });
      forget(model.name);
    } catch (error) {
      setRemoved((now) => ({ ...now, [fold(model.name)]: { model, busy: false, problem: refusalOf(error).message } }));
    }
    void reload();
  };
  // Opens a CLI's source in Add models, as its card's link asks.
  const opening = useRef<string | null>(null);
  const goTo = (cli: string) => {
    setTab("add");
    if (!open.has(cliKey(cli))) opening.current = cli;
  };

  const count = entries?.models.length ?? 0;
  return (
    <section className="setting" id={MODELS_ANCHOR} ref={section} aria-labelledby={id}>
      <h2 id={id}>Models</h2>
      <p className="muted">
        The models your agents can run on, each with the agent CLI that runs it. Without any, each agent runs on its
        agent CLI's default model.
      </p>
      {problem && (
        <p className="problem" role="alert">
          {problem}
        </p>
      )}
      {entries && (
        <>
          <div className="tab-bar mx-tabs" role="tablist" aria-label="Models">
            <button
              type="button"
              role="tab"
              className="tab-item"
              aria-selected={tab === "mine"}
              data-active={tab === "mine" ? "" : undefined}
              onClick={() => setTab("mine")}
            >
              Your models <span className="tab-count">{count}</span>
            </button>
            <button
              type="button"
              role="tab"
              className="tab-item"
              aria-selected={tab === "add"}
              data-active={tab === "add" ? "" : undefined}
              onClick={() => setTab("add")}
            >
              Add models
            </button>
          </div>
          <div className="mx-panel" role="tabpanel">
            {tab === "mine" ? (
              <YourModels
                entries={entries}
                logins={logins}
                reads={reads}
                removed={removed}
                onChanged={reload}
                onRemoved={onRemoved}
                onUndo={(gone) => void undo(gone)}
                onExpired={forget}
                onAdd={() => setTab("add")}
                onGoTo={goTo}
              />
            ) : (
              <ModelSources
                settings={entries}
                logins={logins}
                reads={reads}
                onRead={onRead}
                open={open}
                onOpen={onOpen}
                saved={saved}
                onSaved={onSaved}
                onChanged={reload}
                latest={reading}
                onRemoved={onRemoved}
                opening={opening}
              />
            )}
          </div>
        </>
      )}
    </section>
  );
}

// The warnings of a configured model: its CLI not installed, its model not in the list its
// source gave when last read here.
function warningsOf(model: ConfiguredModelInfo, logins: ProviderLogins[], reads: Record<string, Read>) {
  const out: { short: string; long: string }[] = [];
  const row = logins.find((r) => r.cli.name === model.cli);
  if (row?.ready && !row.cli.installed)
    out.push({ short: `${model.cli_title} is not installed`, long: `${model.cli_title} is not installed` });
  const source = model.server ?? model.cli_title;
  const has = listed(reads[model.server === null ? cliKey(model.cli) : serverKey(model.server)]);
  if (has !== null && !has.has(model.model))
    out.push({
      short: "not in list",
      long: `not in ${source}'s list of models: agents on it will stop at their first turn`,
    });
  return out;
}

type Card = { cli: string; title: string; row: ProviderLogins | null };

// Your models: a card per agent CLI LADO knows, in the order of Add models, then one for a
// model of a CLI it does not know; a card's models by name ignoring case, a removed one's
// Undo row in its place.
function YourModels({
  entries,
  logins,
  reads,
  removed,
  onChanged,
  onRemoved,
  onUndo,
  onExpired,
  onAdd,
  onGoTo,
}: {
  entries: Entries;
  logins: ProviderLogins[];
  reads: Record<string, Read>;
  removed: Record<string, Removed>;
  onChanged: (given?: Entries) => Promise<void>;
  onRemoved: (model: ConfiguredModelInfo) => void;
  onUndo: (gone: Removed) => void;
  onExpired: (name: string) => void;
  onAdd: () => void;
  onGoTo: (cli: string) => void;
}) {
  const gone = Object.values(removed);
  if (entries.models.length === 0 && gone.length === 0)
    return (
      <p className="mx-empty">
        {EMPTY}{" "}
        <button type="button" className="link-button" onClick={onAdd}>
          Add models
        </button>
      </p>
    );
  const cards: Card[] = logins.map((row) => ({ cli: row.cli.name, title: row.cli.title, row }));
  for (const m of [...entries.models, ...gone.map((g) => g.model)])
    if (!cards.some((c) => c.cli === m.cli)) cards.push({ cli: m.cli, title: m.cli_title, row: null });
  const servers = new Map(entries.servers.map((s) => [fold(s.name), s.address]));
  return (
    <>
      {cards.map((card) => {
        const live = entries.models.filter((m) => m.cli === card.cli);
        const rows = [
          ...live.map((model) => ({ model, gone: null as Removed | null })),
          ...gone.filter((g) => g.model.cli === card.cli && !live.some((m) => fold(m.name) === fold(g.model.name))).map((g) => ({ model: g.model, gone: g })),
        ].sort((a, b) => byName(a.model, b.model));
        const off = card.row?.ready && !card.row.cli.installed;
        const word = off ? "not installed" : card.row?.ready && card.row.login.state === "no" ? "not logged in" : "";
        return (
          <div key={card.cli} className="mx-card" role="group" aria-label={card.title}>
            <div className="mx-card-h">
              <span className="mx-title">{card.title}</span>
              <span className="tab-count">{live.length}</span>
              {word && <span className={off ? "field-note warn mx-card-warn" : "mx-sub"}>{off ? `⚠ ${card.title} is not installed` : word}</span>}
            </div>
            {rows.length === 0 ? (
              <p className="mx-none-p">
                {`No models: its agents run on ${card.title}'s default model. `}
                <button type="button" className="link-button" onClick={() => onGoTo(card.cli)}>
                  {`Add from ${card.title}`}
                </button>
              </p>
            ) : (
              <table className="mx-table">
                <colgroup>
                  <col className="c-name" />
                  <col />
                  <col />
                  <col className="c-act" />
                </colgroup>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Model</th>
                    <th>From</th>
                    <th aria-label="Remove" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map(({ model, gone }) =>
                    gone ? (
                      <UndoRow key={`removed:${model.name}`} gone={gone} onUndo={onUndo} onExpired={onExpired} />
                    ) : (
                      <ModelRow
                        key={model.name}
                        model={model}
                        address={model.server ? servers.get(fold(model.server)) : undefined}
                        warnings={warningsOf(model, logins, reads)}
                        onChanged={onChanged}
                        onRemoved={onRemoved}
                      />
                    ),
                  )}
                </tbody>
              </table>
            )}
          </div>
        );
      })}
      <p className="mx-count">Click a name to rename it. Sessions will refer to the model, not to its name.</p>
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
  onExpired: (name: string) => void;
}) {
  const { model, problem, busy } = gone;
  // Gone after UNDO_MS, kept while its Undo runs or was refused (to say why).
  useEffect(() => {
    if (problem || busy) return;
    const timer = setTimeout(() => onExpired(model.name), UNDO_MS);
    return () => clearTimeout(timer);
  }, [model.name, problem, busy, onExpired]);
  return (
    <tr className="mx-undo">
      <td colSpan={4}>
        <span role="status">
          Removed <b>{model.name}</b>.
        </span>
        <button type="button" className="link-button" disabled={busy} onClick={() => onUndo(gone)}>
          Undo
        </button>
        {problem && <span className="field-note bad">{problem}</span>}
      </td>
    </tr>
  );
}

function ModelRow({
  model,
  address,
  warnings,
  onChanged,
  onRemoved,
}: {
  model: ConfiguredModelInfo;
  address: string | undefined;
  warnings: { short: string; long: string }[];
  onChanged: (given?: Entries) => Promise<void>;
  onRemoved: (model: ConfiguredModelInfo) => void;
}) {
  const [renaming, setRenaming] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const remove = async () => {
    setProblem(null);
    try {
      await onChanged(await removeModel(model.name));
      onRemoved(model);
    } catch (error) {
      setProblem(refusalOf(error).message);
    }
  };
  return (
    <tr>
      <td className={renaming ? "mx-renaming" : undefined}>
        {renaming ? (
          <Rename
            name={model.name}
            onDone={(given) => {
              setRenaming(false);
              void onChanged(given);
            }}
            onCancel={() => setRenaming(false)}
          />
        ) : (
          <span
            className="mx-name"
            role="button"
            tabIndex={0}
            title="Click to rename · Enter saves, Esc cancels"
            aria-label={`Rename ${model.name}`}
            onClick={() => setRenaming(true)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                setRenaming(true);
              }
            }}
          >
            {model.name}
          </span>
        )}
        {problem && <span className="field-note bad mx-rename-note">{problem}</span>}
      </td>
      <td className="mono" title={model.model}>
        {model.model}
        {warnings.map((w) => (
          <span key={w.short} className="mx-gone" title={w.long}>{`⚠ ${w.short}`}</span>
        ))}
      </td>
      <td title={address}>{model.server ?? <span className="mx-sub">the CLI itself</span>}</td>
      <td>
        <button
          type="button"
          className="mx-x"
          title={`Remove ${model.name}`}
          aria-label={`Remove ${model.name}`}
          onClick={() => void remove()}
        >
          ×
        </button>
      </td>
    </tr>
  );
}

// The name as a field of its cell: Enter or leaving it renames, Esc restores; a refusal
// keeps the field with the refusal under it, and leaving it then restores the name.
function Rename({ name, onDone, onCancel }: { name: string; onDone: (given: Entries) => void; onCancel: () => void }) {
  const [text, setText] = useState(name);
  const [refused, setRefused] = useState<EntryRefused | null>(null);
  const busy = useRef(false);
  const done = useRef(false);
  const save = async (leaving: boolean) => {
    if (busy.current || done.current) return;
    if (leaving && refused) return onCancel();
    if (text === name) {
      done.current = true;
      return onCancel();
    }
    busy.current = true;
    try {
      const given = await renameModel(name, text);
      done.current = true;
      onDone(given);
    } catch (error) {
      if (leaving) onCancel();
      else setRefused(refusalOf(error));
    } finally {
      busy.current = false;
    }
  };
  return (
    <>
      <input
        className="mx-rename"
        aria-label={`Name of ${name}`}
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
            onCancel();
          }
        }}
        onBlur={() => void save(true)}
      />
      {refused && (
        <span className="field-note bad mx-rename-note" role="alert">
          {refused.message}
        </span>
      )}
    </>
  );
}
