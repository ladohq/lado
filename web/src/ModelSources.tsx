// Settings → Models, where models come from (docs/design/ui.md, Models): the block Model
// servers, every saved server by name then Add server. A source opens from its whole row;
// opening it reads its models now by a probe with its kept key, ↻ reads them again; nothing is
// read before and no list outlives the page. A list's order is set when it is read (the
// source's configured models first) and no tick changes it; it is bounded and scrolls within
// itself. A server's model opens under its row the installed CLIs that can run it, a tick each,
// with the name a tick would save (the core's). A tick is on exactly when a configured model
// has that CLI, model and server: ticking saves one, unticking removes it with no Undo (a tick
// again brings it back under its name while the page stays open), after a question when it is
// its CLI's default. A server shows its list, its Change form or its Remove question, one at a
// time. A server added takes the form's place, one removed leaves a line in its own.
import { type MutableRefObject, type ReactNode, type RefObject, useEffect, useId, useRef, useState } from "react";

import {
  addModel,
  addModelServer,
  checkModel,
  checkModelServer,
  type CliDefault,
  type ConfiguredModelInfo,
  type EntryRefused,
  getModelSettings,
  type ModelCheck,
  type ModelServerInfo,
  type ModelSettings,
  type ProbeInfo,
  probeModelServer,
  type ProviderLogins,
  refusalOf,
  removeModel,
  removeModelServer,
  type ServerCheck,
} from "./api";
import { ChevronIcon, ForgetIcon, PencilIcon } from "./icons";
import { MODEL_DEBOUNCE, useDebounced } from "./Launch";
import { SecretField } from "./ProjectVariables";
import { messageOf } from "./SessionControl";

const SEARCH_ABOVE = 10; // a list longer than this has a search field
const SHORT = 20; // a server's list this long shows whole on a phone

export const SERVERS_LEAD =
  "LM Studio, Ollama, vLLM, LiteLLM or another OpenAI-compatible server. Type its address: LADO finds its type, its models and the agent CLIs that can use it.";

// A source's models as last read: reading, a server's probe with the order set at that read,
// or why not.
export type Read = { reading: true } | { probe: ProbeInfo; order: string[] } | { refused: EntryRefused };

// After a server was saved or changed here: the lines its source shows (`added`: it was added
// now, so its list says how to go on).
export type Saved = {
  notes: string[];
  warnings: string[];
  saved: string;
  added: boolean;
};

// What both blocks share with the section, which keeps it while the page is open.
export type Sources = {
  settings: ModelSettings;
  logins: ProviderLogins[];
  reads: Record<string, Read>;
  onRead: (key: string, read: Read | null) => void;
  open: Set<string>;
  onOpen: (key: string, open: boolean) => void;
  saved: Record<string, Saved>;
  onSaved: (key: string, saved: Saved | null) => void;
  onChanged: (settings?: ModelSettings) => Promise<void> | void;
  // The latest read of each source, by key: whatever fills a source (a read here, an add or
  // a change) counts one up, so an older read's late answer is dropped.
  latest: MutableRefObject<Record<string, number>>;
  onTouch: () => void; // the human changes something here
  names: Record<string, string>; // the names of models unticked here, by tickKey
  onName: (key: string, name: string | null) => void;
  onDefaultGone: (cli: string, name: string) => void; // a tick removed a default not asked about
};

export const serverKey = (name: string) => `server:${name.toLowerCase()}`;
const fold = (text: string) => text.toLowerCase();
const plural = (n: number, one: string) => `${n} ${one}${n === 1 ? "" : "s"}`;
const tickKey = (cli: string, model: string, server: string) => `${cli}\n${model}\n${fold(server)}`;

// The configured models of `model` of `cli` on `server`, its name found ignoring case.
const ticked = (models: ConfiguredModelInfo[], cli: string, model: string, server: string) =>
  models.filter((m) => m.cli === cli && m.model === model && fold(m.server) === fold(server));

// The tick of `model` of `cli` on `server`: on when a configured model has them; with
// several, the names of them all (the tick is then disabled).
export function tickState(
  models: ConfiguredModelInfo[],
  cli: string,
  model: string,
  server: string,
): { on: boolean; several: string[] } {
  const same = ticked(models, cli, model, server);
  return {
    on: same.length > 0,
    several: same.length > 1 ? same.map((m) => m.name) : [],
  };
}

// The configured models on a server.
const fromSource = (models: ConfiguredModelInfo[], server: string) =>
  models.filter((m) => fold(m.server) === fold(server));

// The models a read list holds, embeddings left out (null: it gave no list, so none is
// missing from it).
export function listed(read: Read | undefined): Set<string> | null {
  if (!read) return null;
  if ("probe" in read) return read.probe.models === null ? null : new Set(read.probe.models);
  return null;
}

const listOf = (probe: ProbeInfo): string[] => {
  const embeddings = new Set(probe.embeddings);
  return (probe.models ?? []).filter((m) => !embeddings.has(m));
};

// A list's order at its read: the models of the source's configured models it no longer
// lists, then those it lists, then the rest as it gave them.
export function orderOf(list: string[], own: ConfiguredModelInfo[]): string[] {
  const mine = new Set(own.map((m) => m.model));
  const has = new Set(list);
  return [
    ...[...mine].filter((m) => !has.has(m)),
    ...list.filter((m) => mine.has(m)),
    ...list.filter((m) => !mine.has(m)),
  ];
}

// A new read, add or change of the source `key`: its number in `latest`.
const nextRead = (latest: MutableRefObject<Record<string, number>>, key: string) =>
  (latest.current[key] = (latest.current[key] ?? 0) + 1);

// The reads of the sources and their opening and closing.
function useReads(props: Sources) {
  const { latest } = props;
  const models = useRef(props.settings.models); // the entries a read's order is set from
  models.current = props.settings.models;
  const readServer = (name: string) => {
    const key = serverKey(name);
    const asked = nextRead(latest, key);
    props.onRead(key, { reading: true });
    probeModelServer(name).then(
      (probe) => {
        if (latest.current[key] !== asked) return;
        props.onRead(key, { probe, order: orderOf(listOf(probe), fromSource(models.current, name)) });
      },
      (error: unknown) => latest.current[key] === asked && props.onRead(key, { refused: refusalOf(error) }),
    );
  };
  const close = (key: string) => {
    props.onOpen(key, false);
    nextRead(latest, key); // no late answer fills it
    props.onRead(key, null);
  };
  const toggle = (key: string, reader: () => void) => {
    props.onSaved(key, null); // the lines of a save are said once, in the open source
    if (props.open.has(key)) return close(key);
    props.onOpen(key, true);
    reader();
  };
  // A server added or changed shows open with the probe of its save, as a read.
  const filled = (name: string, probe: ProbeInfo, saved: Saved) => {
    const key = serverKey(name);
    nextRead(latest, key);
    props.onOpen(key, true);
    props.onRead(key, {
      probe,
      order: orderOf(listOf(probe), fromSource(models.current, name)),
    });
    props.onSaved(key, saved);
  };
  return { readServer, close, toggle, filled };
}

export function ModelServers(props: Sources) {
  const { settings } = props;
  const reads = useReads(props);
  // The servers by name at the first render, then each one added here at the end, where its
  // form was; a server removed here leaves its line in its place.
  const order = useRef<string[] | null>(null);
  if (order.current === null)
    order.current = settings.servers.map((s) => s.name).sort((a, b) => fold(a).localeCompare(fold(b)));
  for (const server of settings.servers)
    if (!order.current.some((name) => fold(name) === fold(server.name))) order.current.push(server.name);
  const [gone, setGone] = useState<Record<string, string>>({});
  const [adding, setAdding] = useState(false);
  const [fresh, setFresh] = useState<string | null>(null); // the server just added: the focus
  const addButton = useRef<HTMLButtonElement>(null);
  const [removedOne, setRemovedOne] = useState(false); // a server went: the focus goes to Add
  useEffect(() => {
    if (!removedOne) return;
    setRemovedOne(false);
    addButton.current?.focus();
  }, [removedOne]);
  const installed = (cli: string) => {
    const row = props.logins.find((r) => r.cli.name === cli);
    return !row?.ready || row.cli.installed;
  };
  return (
    <div className="mx-block">
      <h3>
        Model servers {settings.servers.length > 0 && <span className="mx-count">{settings.servers.length}</span>}
      </h3>
      <p className="mx-lead">{SERVERS_LEAD}</p>
      <ul className="mx-srcs">
        {order.current.map((name) => {
          const key = serverKey(name);
          const server = settings.servers.find((s) => fold(s.name) === fold(name));
          const line = gone[fold(name)];
          if (!server && !line) return null;
          return (
            <li key={key} className={`mx-src${props.open.has(key) ? " mx-open" : ""}`} data-anchor="">
              {server ? (
                <ServerSource
                  server={server}
                  sources={props}
                  read={props.reads[key]}
                  saved={props.saved[key]}
                  focus={fresh !== null && fold(fresh) === fold(server.name)}
                  installed={installed}
                  onToggle={() => reads.toggle(key, () => reads.readServer(server.name))}
                  onClose={() => props.open.has(key) && reads.close(key)}
                  onRefresh={() => reads.readServer(server.name)}
                  onProbe={(probe, saved) => reads.filled(server.name, probe, saved)}
                  onGone={(done) => {
                    reads.close(key);
                    for (const one of Object.keys(props.saved)) props.onSaved(one, null); // old now
                    setGone((now) => ({ ...now, [fold(server.name)]: done }));
                    setRemovedOne(true);
                  }}
                />
              ) : (
                <div className="mx-done" role="status">
                  {line}
                </div>
              )}
            </li>
          );
        })}
        <li className="mx-add-slot">
          {adding ? (
            <AddServer
              onCancel={() => setAdding(false)}
              onTouch={props.onTouch}
              onAdded={(server, probe, saved) => {
                setAdding(false);
                setFresh(server.name);
                reads.filled(server.name, probe, saved);
                void props.onChanged();
              }}
            />
          ) : (
            <button ref={addButton} type="button" className="quiet mx-add" onClick={() => setAdding(true)}>
              <span aria-hidden="true">+</span> Add server
            </button>
          )}
        </li>
      </ul>
    </div>
  );
}

export function loginWord(row: ProviderLogins): string {
  if (!row.ready) return "";
  if (!row.cli.installed) return "not installed";
  if (row.login.state === "no") return "not logged in";
  if (row.login.state === "yes") return "logged in";
  return "";
}

// A source's row: the whole row opens and closes it (its framed arrow turns), its name and
// badges, then its second line; its icons at the right. `tip`: the whole address, on hover
// and on keyboard focus.
function SourceHead({
  title,
  badges,
  open,
  tip,
  focus,
  onToggle,
  children,
  acts,
}: {
  title: string;
  badges?: ReactNode;
  open: boolean;
  tip?: string;
  focus?: boolean;
  onToggle: () => void;
  children: ReactNode;
  acts?: ReactNode;
}) {
  const id = useId();
  const hit = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (focus) hit.current?.focus();
  }, [focus]);
  return (
    <div className="mx-head">
      <button
        ref={hit}
        type="button"
        className="mx-hit"
        aria-expanded={open}
        aria-label={title}
        aria-describedby={id}
        onClick={onToggle}
      >
        <span className="mx-disc" aria-hidden="true">
          <ChevronIcon />
        </span>
        <span className="mx-src-title">
          <span className="mx-l1">
            <span className="mx-src-name">{title}</span>
            {badges}
          </span>
          <span className="mx-l2" id={id}>
            {children}
          </span>
        </span>
        {tip && (
          <span className="mx-tip" role="tooltip">
            {tip}
          </span>
        )}
      </button>
      {acts && <span className="mx-acts">{acts}</span>}
    </div>
  );
}

type Column = { name: string; title: string };

function ServerSource({
  server,
  sources,
  read,
  saved,
  focus,
  installed,
  onToggle,
  onClose,
  onRefresh,
  onProbe,
  onGone,
}: {
  server: ModelServerInfo;
  sources: Sources;
  read: Read | undefined;
  saved: Saved | undefined;
  focus: boolean;
  installed: (cli: string) => boolean;
  onToggle: () => void;
  onClose: () => void;
  onRefresh: () => void;
  onProbe: (probe: ProbeInfo, saved: Saved) => void;
  onGone: (line: string) => void;
}) {
  const [mode, setMode] = useState<"change" | "remove" | null>(null);
  const bin = useRef<HTMLButtonElement>(null);
  const open = sources.open.has(serverKey(server.name));
  const own = fromSource(sources.settings.models, server.name);
  const probe = read && "probe" in read ? read.probe : null;
  const columns: Column[] = (probe?.clis ?? []).filter((c) => installed(c.name));
  // One of the list, Change and Remove at a time.
  const show = (next: "change" | "remove") => {
    const to = mode === next ? null : next;
    setMode(to);
    if (to) {
      onClose();
      sources.onSaved(serverKey(server.name), null);
    }
  };
  return (
    <>
      <SourceHead
        title={server.name}
        badges={
          <>
            <span className="badge">{server.kind}</span>
            {server.has_key && <span className="badge">key</span>}
          </>
        }
        open={open}
        tip={server.address}
        focus={focus}
        onToggle={() => {
          setMode(null);
          onToggle();
        }}
        acts={
          <>
            <button
              type="button"
              className="mx-icon"
              aria-pressed={mode === "change"}
              aria-label={`Change ${server.name}`}
              title="Change"
              onClick={() => show("change")}
            >
              <PencilIcon />
            </button>
            <button
              ref={bin}
              type="button"
              className="mx-icon mx-icon-danger"
              aria-pressed={mode === "remove"}
              aria-label={`Remove ${server.name}`}
              title="Remove"
              onClick={() => show("remove")}
            >
              <ForgetIcon />
            </button>
          </>
        }
      >
        {own.length ? `${plural(own.length, "model")} added` : "no models added"}
        {" · "}
        <span className="mono">{server.address}</span>
      </SourceHead>
      {mode === "change" && (
        <ChangeServer
          server={server}
          own={own}
          onTouch={sources.onTouch}
          onDone={(found, done) => {
            setMode(null);
            onProbe(found, done);
            void sources.onChanged();
          }}
          onCancel={() => setMode(null)}
        />
      )}
      {mode === "remove" && (
        <RemoveServer
          server={server}
          own={own}
          defaults={sources.settings.defaults}
          onTouch={sources.onTouch}
          onCancel={() => {
            setMode(null);
            bin.current?.focus();
          }}
          onChanged={sources.onChanged}
          onGone={(line) => {
            setMode(null);
            onGone(line);
          }}
        />
      )}
      {open && (
        <div className="mx-body">
          {saved && (
            <div className="mx-saved">
              <p className="mx-saved-line" role="status">
                {saved.saved}
              </p>
              {saved.warnings.map((line) => (
                <span key={line} className="field-note warn">{`⚠ ${line}`}</span>
              ))}
              {saved.notes.map((line) => (
                <span key={line} className="field-note">
                  {line}
                </span>
              ))}
            </div>
          )}
          <SourceBody
            read={read}
            sources={sources}
            server={server.name}
            columns={columns}
            own={own}
            hint={saved?.added === true}
            onRefresh={onRefresh}
          />
        </div>
      )}
    </>
  );
}

// An open source's list: reading, the refusal, or its models in the order of its read,
// bounded, with a search above a long one and its count under it; then Model id where the
// list is not whole.
function SourceBody({
  read,
  sources,
  server,
  columns,
  own,
  hint,
  onRefresh,
}: {
  read: Read | undefined;
  sources: Sources;
  server: string;
  columns: Column[];
  own: ConfiguredModelInfo[];
  hint: boolean; // say how to go on: the server was just added
  onRefresh: () => void;
}) {
  const models = sources.settings.models;
  const [search, setSearch] = useState("");
  const [refused, setRefused] = useState<{
    model: string;
    text: string;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [pop, setPop] = useState<string | null>(null);
  // A tick off on its CLI's default: asked first, the tick staying on until the answer.
  const [asking, setAsking] = useState<ConfiguredModelInfo | null>(null);
  const boxes = useRef<Record<string, HTMLInputElement | null>>({}); // by tickKey
  const answered = () => {
    if (asking) boxes.current[tickKey(asking.cli, asking.model, server)]?.focus();
    setAsking(null);
  };
  // The name a tick would save under each CLI of the open server model, by the core.
  const [would, setWould] = useState<{
    model: string;
    by: Record<string, string>;
  } | null>(null);
  const columnNames = columns.map((c) => c.name).join(" ");
  useEffect(() => {
    // Another model's names go; this one's stay until the core answers again (nothing moves).
    setWould((now) => (pop === null ? null : now?.model === pop ? now : { model: pop, by: {} }));
    if (pop === null) return;
    let current = true;
    for (const name of columnNames.split(" ").filter(Boolean))
      checkModel({ name: null, cli: name, model: pop, server }).then(
        (check) =>
          current &&
          check.name !== "" &&
          setWould((now) => (now?.model === pop ? { model: pop, by: { ...now.by, [name]: check.name } } : now)),
        () => undefined, // a tick says what is wrong
      );
    return () => {
      current = false; // the list closed, or another model opened
    };
  }, [pop, server, columnNames, models.length]);
  const reading = !read || "reading" in read;
  const refresh = (
    <button
      type="button"
      className="mx-icon mx-refresh"
      aria-label="Read the models again"
      title="Read the models again"
      disabled={reading}
      onClick={onRefresh}
    >
      ↻
    </button>
  );
  if (reading)
    return (
      <p className="mx-note mx-reading" role="status">
        <span className="mx-spin" aria-hidden="true" /> reading the models…
      </p>
    );
  if ("refused" in read) {
    const stay = own.map((m) => m.name);
    return (
      <>
        <div className="mx-tools">{refresh}</div>
        <span className="field-note warn" role="alert">
          {`⚠ ${read.refused.message}`}
          {read.refused.hint && <span className="mx-hint">{read.refused.hint}</span>}
        </span>
        {stay.length > 0 && (
          <p className="mx-note">
            {stay.length === 1 ? "Its model stays saved: " : "Its models stay saved: "}
            <b>{stay.join(", ")}</b>. Agents on it stop at their first turn until the server answers.
          </p>
        )}
      </>
    );
  }
  const has = listed(read);
  const configured = new Set(own.map((m) => m.model));
  // The order of the read; a model it no longer lists shows while it is configured, and one
  // configured since (by Model id) comes last.
  const rows = [
    ...read.order.filter((m) => configured.has(m) || has === null || has.has(m)),
    ...[...configured].filter((m) => !read.order.includes(m)),
  ];
  const typed = search.trim().toLowerCase();
  const shown = rows.filter((m) => !typed || m.toLowerCase().includes(typed));
  const missing = (m: string) => has !== null && !has.has(m);
  const probe = "probe" in read ? read.probe : null;
  const embeddings = probe?.embeddings.length ?? 0;
  const whole = probe?.models !== null;
  const tick = async (on: string, model: string, add: boolean) => {
    const [one] = ticked(models, on, model, server);
    if (!add && one && sources.settings.defaults.some((d) => d.external === one.id)) {
      setAsking(one);
      return;
    }
    await change(on, model, add);
  };
  const change = async (on: string, model: string, add: boolean) => {
    sources.onTouch();
    setBusy(true);
    setRefused(null);
    const key = tickKey(on, model, server);
    try {
      if (add) {
        const kept = sources.names[key] ?? null; // its name, if unticked here
        try {
          await addModel({ name: kept, cli: on, model, server });
        } catch (error) {
          if (kept === null || refusalOf(error).field !== "name") throw error;
          await addModel({ name: null, cli: on, model, server }); // taken meanwhile: the default
        }
        sources.onName(key, null);
      } else {
        const [one] = ticked(models, on, model, server);
        if (one) {
          const { cleared } = await removeModel(one.name);
          const asked = sources.settings.defaults.some((d) => d.external === one.id);
          if (cleared.includes(on) && !asked) sources.onDefaultGone(on, one.name);
          sources.onName(key, one.name);
        }
      }
    } catch (error) {
      setRefused({ model, text: refusalOf(error).message });
    } finally {
      setBusy(false);
      void sources.onChanged();
    }
  };
  const box = (on: Column, model: string) => {
    const state = tickState(models, on.name, model, server);
    const gone = missing(model) && !state.on; // a model gone from the list is unticked only
    const [one] = ticked(models, on.name, model, server);
    return (
      <input
        type="checkbox"
        aria-label={`${model} on ${on.title}`}
        checked={state.on}
        ref={(el) => {
          boxes.current[tickKey(on.name, model, server)] = el;
        }}
        // Off while a save runs, by aria only: a box truly disabled would drop the focus.
        aria-disabled={busy ? true : undefined}
        disabled={state.several.length > 0 || gone}
        title={
          state.several.length
            ? `${state.several.join(", ")}: remove them on the card of ${on.title}`
            : gone
              ? `${model} is no longer listed: ↻ reads the list again`
              : one
                ? `Unticking removes ${one.name}.`
                : undefined
        }
        onChange={(event) => !busy && void tick(on.name, model, event.target.checked)}
      />
    );
  };
  const note = (model: string) =>
    refused?.model === model && (
      <div className="mx-row-note">
        <span className="field-note bad">{refused.text}</span>
      </div>
    );
  // `as <name>` by a tick that is on, `would be <name>` by one that is off: the name kept from
  // an untick here, else the core's (`core`), else nothing yet.
  const named = (on: Column, model: string, core: string | undefined) => {
    const same = ticked(models, on.name, model, server);
    if (same.length) return <span className="mx-as">{same.map((m) => `as ${m.name}`).join(", ")}</span>;
    const next = sources.names[tickKey(on.name, model, server)] ?? core;
    return next && <span className="mx-as">{`would be ${next}`}</span>;
  };
  const serverRow = (model: string) => {
    const entries = models.filter((m) => m.model === model && fold(m.server) === fold(server));
    // In LADO's order of the agent CLIs, as the probe names them; one it does not, after them.
    const place = (cli: string) => {
      const at = columns.findIndex((c) => c.name === cli);
      return at < 0 ? columns.length : at;
    };
    const titles = [...new Set([...entries].sort((a, b) => place(a.cli) - place(b.cli)).map((m) => m.cli_title))];
    const opened = pop === model;
    if (columns.length === 0)
      return (
        <div key={model} className="mx-pick">
          <div className="mx-row mx-row-plain">
            <span className="mx-id mono">{model}</span>
            {missing(model) && <span className="mx-gone">no longer listed</span>}
          </div>
        </div>
      );
    return (
      <div key={model} className={`mx-pick${titles.length ? " mx-on" : ""}`}>
        <div
          className="mx-row mx-srvrow"
          role="button"
          tabIndex={0}
          aria-expanded={opened}
          aria-label={model}
          onClick={() => setPop(opened ? null : model)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              setPop(opened ? null : model);
            }
            if (event.key === "Escape") setPop(null);
          }}
        >
          <span className="mx-id mono">{model}</span>
          {missing(model) && <span className="mx-gone">no longer listed</span>}
          <span className="mx-right">
            {titles.length > 0 && <span className="mx-in">{`in ${titles.join(", ")}`}</span>}
            <span className="mx-disc mx-disc-s" aria-hidden="true">
              <ChevronIcon />
            </span>
          </span>
        </div>
        {opened && (
          <div
            className="mx-sub"
            role="group"
            aria-label={`Agent CLIs for ${model}`}
            onKeyDown={(event) => event.key === "Escape" && setPop(null)}
          >
            <p>
              Agent CLIs that can run <b className="mono">{model}</b> on {server}:
            </p>
            {columns.map((on) => (
              <label key={on.name} className="mx-sub-item">
                {box(on, model)}
                <span>{on.title}</span>
                {named(on, model, would?.model === model ? would.by[on.name] : undefined)}
              </label>
            ))}
            {asking?.model === model && (
              <div
                className="mx-confirm"
                role="alertdialog"
                aria-label={`Remove ${asking.name}?`}
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    event.stopPropagation();
                    answered();
                  }
                }}
              >
                <p>
                  <b>{`Remove ${asking.name}?`}</b>
                  {` It is ${asking.cli_title}'s default model: ${asking.cli_title} goes back to its settings.`}
                </p>
                <div className="mx-form-acts">
                  <button
                    type="button"
                    className="danger"
                    onClick={() => {
                      answered();
                      void change(asking.cli, model, false);
                    }}
                  >
                    Remove model
                  </button>
                  <button type="button" className="quiet" autoFocus onClick={answered}>
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
        {note(model)}
      </div>
    );
  };
  return (
    <>
      {hint && columns.length > 0 && <p className="mx-note">Open a model to tick the agent CLIs that run it.</p>}
      <div className="mx-tools">
        {rows.length > SEARCH_ABOVE && (
          <input
            className="mx-search"
            type="search"
            aria-label={`Search ${rows.length} models`}
            placeholder={`Search ${rows.length} models`}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        )}
        {refresh}
      </div>
      {probe && probe.models === null && (
        <span className="field-note warn">{`⚠ no list of models: ${probe.models_why}`}</span>
      )}
      {probe?.apis_why && <span className="field-note warn">{`⚠ APIs: cannot be told: ${probe.apis_why}`}</span>}
      {columns.length === 0 && <p className="mx-note">No installed CLI can use this server.</p>}
      {rows.length > 0 && (
        <div className={`mx-list${rows.length <= SHORT ? " mx-short" : ""}`}>
          {shown.map((model) => serverRow(model))}
          {shown.length === 0 && <div className="mx-row mx-row-plain muted">{`No model matches “${search}”.`}</div>}
        </div>
      )}
      {(rows.length > 0 || embeddings > 0) && (
        <p className="mx-foot">
          {rows.length > 0 && (
            <span>{typed ? `${shown.length} of ${plural(rows.length, "model")}` : plural(rows.length, "model")}</span>
          )}
          {embeddings > 0 && (
            <span>{`${plural(embeddings, "embeddings model")} hidden: agents cannot run on ${embeddings === 1 ? "it" : "them"}.`}</span>
          )}
        </p>
      )}
      {!whole && columns.length > 0 && (
        <ModelId
          columns={columns}
          server={server}
          onTouch={sources.onTouch}
          onChanged={sources.onChanged}
        />
      )}
    </>
  );
}

// Model id: a model of a source whose list is not whole, the check `lado model add` would make
// under the field once the typing settles, and Add (off while refused).
function ModelId({
  columns,
  server,
  onTouch,
  onChanged,
}: {
  columns: Column[];
  server: string;
  onTouch: () => void;
  onChanged: (settings?: ModelSettings) => Promise<void> | void;
}) {
  const id = useId();
  const [model, setModel] = useState("");
  const [cli, setCli] = useState(columns[0].name);
  const [check, setCheck] = useState<ModelCheck | null>(null);
  const [refused, setRefused] = useState<EntryRefused | null>(null);
  const [busy, setBusy] = useState(false);
  const typed = useDebounced(model.trim(), MODEL_DEBOUNCE);
  const chosen = columns.some((c) => c.name === cli) ? cli : columns[0].name;
  useEffect(() => {
    setCheck(null);
    if (!typed) return;
    let current = true;
    checkModel({ name: null, cli: chosen, model: typed, server }).then(
      (found) => current && setCheck(found),
      (error: unknown) => current && setCheck({ kind: "warn", text: messageOf(error), field: "", name: "" }),
    );
    return () => {
      current = false;
    };
  }, [typed, chosen, server]);
  const add = async () => {
    onTouch();
    setBusy(true);
    setRefused(null);
    try {
      await addModel({ name: null, cli: chosen, model: model.trim(), server });
      setModel("");
      setCheck(null);
      void onChanged();
    } catch (error) {
      setRefused(refusalOf(error));
    } finally {
      setBusy(false);
    }
  };
  const settled = check && typed === model.trim() ? check : null;
  const note = refused ?? settled;
  return (
    <div className="mx-other mx-other-cli">
      <div className="field">
        <label htmlFor={id}>Model id</label>
        <input
          id={id}
          className="mono"
          value={model}
          placeholder="a model id the list lacks"
          autoComplete="off"
          spellCheck={false}
          onChange={(event) => {
            setModel(event.target.value);
            setRefused(null);
          }}
          onKeyDown={(event) => event.key === "Enter" && settled?.kind !== "refused" && model.trim() && void add()}
        />
        {note && <CheckNote note={note} />}
      </div>
      <div className="field">
        <label htmlFor={`${id}-cli`}>Agent CLI</label>
        <select id={`${id}-cli`} value={chosen} onChange={(event) => setCli(event.target.value)}>
          {columns.map((c) => (
            <option key={c.name} value={c.name}>
              {c.title}
            </option>
          ))}
        </select>
      </div>
      <button
        type="button"
        className="primary"
        disabled={busy || !model.trim() || settled?.kind === "refused"}
        onClick={() => void add()}
      >
        Add
      </button>
    </div>
  );
}

// A check or a refusal under its field, in the launch window's note look.
function CheckNote({ note }: { note: ModelCheck | EntryRefused }) {
  if ("message" in note)
    return (
      <span className="field-note bad" role="alert">
        {note.message}
        {note.hint && <span className="mx-hint">{note.hint}</span>}
      </span>
    );
  if (note.kind === "ok") return <span className="field-note ok">{`✓ ${note.text}`}</span>;
  if (note.kind === "warn") return <span className="field-note warn">{`⚠ ${note.text}`}</span>;
  if (note.kind === "refused") return <span className="field-note bad">{note.text}</span>;
  return <span className="field-note">{note.text}</span>;
}

const warnings = (lines: string[]) =>
  lines.map((line) => <span key={line} className="field-note warn">{`⚠ ${line}`}</span>);

// What answered the form's check: its type and address, its models and the CLIs that can use it.
function Found({ probe }: { probe: ProbeInfo }) {
  const embeddings = new Set(probe.embeddings);
  const count = probe.models === null ? null : probe.models.filter((m) => !embeddings.has(m)).length;
  return (
    <div className="mx-found launch-wide" role="status">
      <span className="mx-found-t">
        {`✓ ${probe.kind} answers at `}
        <span className="mono">{probe.address}</span>
      </span>
      <dl>
        <dt>Models</dt>
        <dd>
          {count === null ? `no list of models: ${probe.models_why}` : count}
          {embeddings.size > 0 && (
            <span className="muted">{` · ${plural(embeddings.size, "embeddings model")} hidden: agents cannot run on ${embeddings.size === 1 ? "it" : "them"}.`}</span>
          )}
        </dd>
        <dt>Agent CLIs</dt>
        <dd>{probe.clis.length ? probe.clis.map((c) => c.title).join(", ") : "none can use it"}</dd>
      </dl>
    </div>
  );
}

const KEY_NOTE = "Kept in a file only LADO reads; never shown again.";

// Add server: Name, Address and Key. Once the typing settles the form checks the name and
// probes the address without the key; Check key probes it with the key; Add server probes and
// saves as `lado model-server add` does, on only for a free name and a server that answered,
// or asks for a key with one typed. An older check's answer is dropped.
function AddServer({
  onCancel,
  onTouch,
  onAdded,
}: {
  onCancel: () => void;
  onTouch: () => void;
  onAdded: (server: ModelServerInfo, probe: ProbeInfo, saved: Saved) => void;
}) {
  const id = useId();
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [filled, setFilled] = useState(false);
  const [keyRev, setKeyRev] = useState(0); // counts the key's edits: a check with an older key is old
  const [refused, setRefused] = useState<EntryRefused | null>(null); // Add's
  const [busy, setBusy] = useState(false);
  const key = useRef<HTMLInputElement>(null);
  const typed = `${name}\n${address}\n${filled}`;
  const settled = useDebounced(typed, MODEL_DEBOUNCE);
  const asked = useRef(0);
  const [auto, setAuto] = useState<{ for: string; found?: ServerCheck } | null>(null);
  const [keyed, setKeyed] = useState<{
    for: string;
    rev: number;
    found?: ServerCheck;
  } | null>(null);
  useEffect(() => {
    const [n, a, f] = settled.split("\n");
    const mine = ++asked.current;
    if (!n && !a.trim()) return setAuto(null);
    setAuto({ for: settled });
    checkModelServer(n, a, null, f === "true").then(
      (found) => mine === asked.current && setAuto({ for: settled, found }),
      (error: unknown) =>
        mine === asked.current &&
        setAuto({
          for: settled,
          found: {
            probe: null,
            refusals: [refusalOf(error)],
            warnings: [],
            notes: [],
          },
        }),
    );
  }, [settled]);
  useEffect(
    () => () => {
      asked.current++; // the form goes: no answer fills it
    },
    [],
  );
  const checkKey = () => {
    const given = key.current?.value ?? "";
    if (!given) return;
    const mine = ++asked.current;
    const at = { for: typed, rev: keyRev };
    setKeyed(at);
    checkModelServer(name, address, given, true).then(
      (found) => mine === asked.current && setKeyed({ ...at, found }),
      (error: unknown) =>
        mine === asked.current &&
        setKeyed({
          ...at,
          found: {
            probe: null,
            refusals: [refusalOf(error)],
            warnings: [],
            notes: [],
          },
        }),
    );
  };
  const keyedNow = keyed && keyed.for === typed && keyed.rev === keyRev ? keyed : null;
  const autoNow = auto && auto.for === typed ? auto : null;
  const result = keyedNow?.found ?? (keyedNow ? undefined : autoNow?.found);
  const checking =
    !busy && (typed !== settled || (autoNow !== null && !autoNow.found) || (keyedNow !== null && !keyedNow.found));
  const of = (field: string) => (result?.refusals ?? []).filter((r) => r.field === field && refused?.field !== field);
  const asksKey = !keyedNow && (result?.refusals ?? []).some((r) => r.field === "key");
  // The server asked for a key at this address: Key says so until the address changes.
  const needsKey = asksKey || (keyedNow !== null && (autoNow?.found?.refusals ?? []).some((r) => r.field === "key"));
  const ready =
    !busy &&
    !checking &&
    refused?.field !== "key" &&
    name !== "" &&
    address.trim() !== "" &&
    result !== undefined &&
    !result.refusals.some((r) => ["name", "address", ""].includes(r.field)) &&
    (result.probe !== null || (asksKey && filled));
  // A refusal of Add under a field goes once that field is edited.
  const edited = (field: string) => setRefused((now) => (now?.field === field ? null : now));
  const add = async () => {
    if (!ready) return;
    onTouch();
    const given = key.current?.value ?? "";
    setBusy(true);
    setRefused(null);
    try {
      const done = await addModelServer(name, address, given === "" ? null : given);
      emptyKey(key, setFilled);
      onAdded(done.server, done.probe, {
        notes: done.notes,
        warnings: done.warnings,
        saved: `Saved model server "${done.server.name}".`,
        added: true,
      });
    } catch (error) {
      const why = refusalOf(error);
      if (why.field !== "key") emptyKey(key, setFilled);
      setRefused(why);
      setBusy(false);
    }
  };
  const bad = (lines: EntryRefused[]) => lines.map((r) => <CheckNote key={r.message} note={r} />);
  const nameBad = [...of("name"), ...(refused?.field === "name" ? [refused] : [])];
  const addressBad = [...of("address"), ...(refused?.field === "address" ? [refused] : [])];
  const keyBad = [...(!checking && !asksKey ? of("key") : []), ...(refused?.field === "key" ? [refused] : [])];
  const nameFree = !checking && name !== "" && result !== undefined && nameBad.length === 0;
  return (
    <div className="mx-form">
      <div className="launch-grid">
        <div className="field">
          <label htmlFor={`${id}-name`}>Name</label>
          <input
            id={`${id}-name`}
            className="words"
            value={name}
            placeholder="e.g. LM Studio at home"
            aria-invalid={nameBad.length ? true : undefined}
            autoFocus
            onChange={(event) => {
              setName(event.target.value);
              edited("name");
            }}
          />
          {bad(nameBad)}
          {nameFree && <span className="field-note ok">free</span>}
        </div>
        <div className="field">
          <label htmlFor={`${id}-address`}>Address</label>
          <input
            id={`${id}-address`}
            value={address}
            placeholder="localhost:1234 or https://host/v1"
            aria-invalid={addressBad.length ? true : undefined}
            onChange={(event) => {
              setAddress(event.target.value);
              edited("address");
            }}
          />
          {checking && address.trim() !== "" ? (
            <span className="field-note mx-check" role="status">
              <span className="mx-spin" aria-hidden="true" />
              {` checking ${address.trim()} …`}
            </span>
          ) : (
            <>
              {bad(addressBad)}
              {asksKey &&
                of("key").map((r) => (
                  <span key={r.message} className="field-note warn">
                    {`⚠ ${r.message}`}
                    {r.hint && <span className="mx-hint">{r.hint}</span>}
                  </span>
                ))}
              {(result?.notes ?? []).map((line) => (
                <span key={line} className="field-note">
                  {line}
                </span>
              ))}
            </>
          )}
        </div>
        {!checking && result?.probe && <Found probe={result.probe} />}
        <div className="field launch-wide">
          <label htmlFor={`${id}-key`}>
            Key <span className="mx-opt">{needsKey ? "required by this server" : "optional"}</span>
          </label>
          <SecretField
            field={key}
            label="Key"
            placeholder="Only if the server asks for one"
            onFilled={(now) => {
              setFilled(now);
              setKeyRev((n) => n + 1);
              edited("key");
            }}
            onEnter={() => void add()}
          />
          {filled && warnings(result?.warnings ?? [])}
          {warnings((refused?.warnings ?? []).filter((line) => !(filled && result?.warnings.includes(line))))}
          {bad(keyBad)}
          <span className="field-note">
            {asksKey && filled
              ? `The key is sent to the server only when you press Check key or Add server. ${KEY_NOTE}`
              : KEY_NOTE}
          </span>
        </div>
      </div>
      <div className="mx-form-acts">
        {asksKey && filled && (
          <button type="button" className="quiet" onClick={checkKey}>
            Check key
          </button>
        )}
        <button type="button" className="primary" disabled={!ready} onClick={() => void add()}>
          {busy ? "checking the server…" : "Add server"}
        </button>
        <button type="button" className="quiet" onClick={onCancel}>
          Cancel
        </button>
        {bad(of(""))}
        {refused && !["name", "address", "key"].includes(refused.field) && <CheckNote note={refused} />}
      </div>
    </div>
  );
}

// Change: the server's Address, filled, and New key, empty (the kept key stays). Once the
// address or a key is typed, the form's check says what answers there and the plain-http
// warning of the key that would go (the server's own name is not taken); Save replaces it as
// `lado model-server add --replace` does, then its list opens.
// Empties a key's field once its form has sent it: Add or Save is done, or refused for another
// field than the key (a refused key stays, for the human to edit or erase).
function emptyKey(key: RefObject<HTMLInputElement | null>, setFilled: (filled: boolean) => void) {
  if (key.current) key.current.value = "";
  setFilled(false);
}

function ChangeServer({
  server,
  own,
  onTouch,
  onDone,
  onCancel,
}: {
  server: ModelServerInfo;
  own: ConfiguredModelInfo[];
  onTouch: () => void;
  onDone: (probe: ProbeInfo, saved: Saved) => void;
  onCancel: () => void;
}) {
  const id = useId();
  const [address, setAddress] = useState(server.address);
  const [refused, setRefused] = useState<EntryRefused | null>(null);
  const [busy, setBusy] = useState(false);
  const [filled, setFilled] = useState(false);
  const key = useRef<HTMLInputElement>(null);
  const keyGoes = filled || server.has_key; // empty: the kept key goes
  // The check sends the kept key itself while New key is empty (key_typed false), as Save does.
  const asking = address.trim() !== server.address || filled ? `${address.trim()}\n${filled}` : "";
  const settled = useDebounced(asking, MODEL_DEBOUNCE);
  const [check, setCheck] = useState<{
    for: string;
    found?: ServerCheck;
  } | null>(null);
  useEffect(() => {
    setCheck(null);
    const [at, goes] = settled.split("\n");
    if (!settled || !at) return;
    let current = true;
    setCheck({ for: settled });
    checkModelServer(server.name, at, null, goes === "true", true).then(
      (found) => current && setCheck({ for: settled, found }),
      (error: unknown) =>
        current &&
        setCheck({
          for: settled,
          found: {
            probe: null,
            refusals: [refusalOf(error)],
            warnings: [],
            notes: [],
          },
        }),
    );
    return () => {
      current = false;
    };
  }, [settled, server.name]);
  const now = check && check.for === asking ? check : null;
  const checking = asking !== "" && (asking !== settled || (now !== null && !now.found));
  const found = now?.found;
  const save = async () => {
    onTouch();
    const given = key.current?.value ?? "";
    setBusy(true);
    setRefused(null);
    try {
      const done = await addModelServer(server.name, address, given === "" ? null : given, true);
      emptyKey(key, setFilled);
      onDone(done.probe, {
        notes: done.notes,
        warnings: done.warnings,
        saved: `Saved model server "${done.server.name}".`,
        added: false,
      });
    } catch (error) {
      const why = refusalOf(error);
      if (why.field !== "key") emptyKey(key, setFilled);
      setRefused(why);
      setBusy(false);
    }
  };
  // A refused Save, but for its key, takes the place of the check it followed, under Address,
  // until the address changes; only one of the address keeps Save off (a failure may pass).
  const saveBad = refused && refused.field !== "key" ? refused : null;
  const checked = saveBad ? undefined : found;
  const silent = (checked?.refusals ?? []).filter((r) => r.field === "address" || r.field === "");
  const addressBad = [...silent, ...(saveBad?.field === "address" ? [saveBad] : [])];
  const asksKey = !server.has_key && !filled && (checked?.refusals ?? []).some((r) => r.field === "key");
  const off = busy || !address.trim() || checking || addressBad.length > 0 || refused?.field === "key"; // Save, and Enter in New key
  const live = keyGoes ? (found?.warnings ?? []) : [];
  const models = (probe: ProbeInfo) =>
    probe.models === null ? "no list of models" : plural(probe.models.length - probe.embeddings.length, "model");
  return (
    <div className="mx-form">
      <div className="launch-grid">
        <div className="field">
          <label htmlFor={`${id}-address`}>Address</label>
          <input
            id={`${id}-address`}
            value={address}
            aria-invalid={addressBad.length ? true : undefined}
            onChange={(event) => {
              setAddress(event.target.value);
              setRefused((was) => (was?.field === "key" ? was : null));
            }}
          />
          {checking ? (
            <span className="field-note mx-check" role="status">
              <span className="mx-spin" aria-hidden="true" />
              {` checking ${address.trim()} …`}
            </span>
          ) : (
            <>
              {checked?.probe && (
                <span className="field-note ok">{`✓ ${checked.probe.kind} answers · ${models(checked.probe)}`}</span>
              )}
              {[...silent, ...(saveBad ? [saveBad] : [])].map((r) => (
                <CheckNote key={r.message} note={r} />
              ))}
              {asksKey && <span className="field-note warn">⚠ The server asks for a key: type it in New key.</span>}
            </>
          )}
        </div>
        <div className="field">
          <label htmlFor={`${id}-key`}>
            New key <span className="mx-opt">empty keeps the key</span>
          </label>
          <SecretField
            field={key}
            label="New key"
            placeholder="Only to replace the key"
            onFilled={(on) => {
              setFilled(on);
              setRefused((was) => (was?.field === "key" ? null : was));
            }}
            onEnter={() => !off && void save()}
          />
          {warnings(live)}
          {warnings((refused?.warnings ?? []).filter((line) => !live.includes(line)))}
          {refused?.field === "key" && <CheckNote note={refused} />}
        </div>
      </div>
      <div className="mx-form-acts">
        <button
          type="button"
          className="primary"
          disabled={off}
          onClick={() => void save()}
        >
          {busy ? "checking the server…" : "Save"}
        </button>
        <button type="button" className="quiet" onClick={onCancel}>
          Cancel
        </button>
      </div>
      {own.length > 0 && (
        <p className="mx-note">
          {own.length === 1
            ? "Its 1 model keeps its name and moves with it."
            : `Its ${own.length} models keep their names and move with it.`}
        </p>
      )}
    </div>
  );
}

// Remove: asks under the server's row, the focus on Cancel, naming the models saved now (the
// CLI may have added one since the page read them) and the key when it has one; the removal
// takes only those, refused when the server has others by then, and then it asks anew.
function RemoveServer({
  server,
  own,
  defaults,
  onTouch,
  onCancel,
  onChanged,
  onGone,
}: {
  server: ModelServerInfo;
  own: ConfiguredModelInfo[];
  defaults: CliDefault[];
  onTouch: () => void;
  onCancel: () => void;
  onChanged: (settings?: ModelSettings) => Promise<void> | void;
  onGone: (line: string) => void;
}) {
  const id = useId();
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(true); // until the entries are read again
  const current = useRef(true);
  useEffect(
    () => () => {
      current.current = false;
    },
    [],
  );
  const reread = () =>
    getModelSettings().then(
      (found) => {
        if (!current.current) return;
        void onChanged(found);
        setBusy(false);
      },
      (error: unknown) => current.current && setProblem(refusalOf(error).message),
    );
  useEffect(() => {
    void reread();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, when it asks
  }, []);
  const ask = own.length
    ? `Remove ${server.name} and its ${plural(own.length, "model")}: ${own.map((m) => m.name).join(", ")}?`
    : `Remove ${server.name}?`;
  // The defaults on those models, in one sentence for all of them.
  const on = own.filter((m) => defaults.some((d) => d.external === m.id));
  const lost = on.length
    ? on.length === 1
      ? `${on[0].name} is ${on[0].cli_title}'s default model: ${on[0].cli_title} goes back to its settings. `
      : `${on
          .map((m, at) => `${m.name} is ${m.cli_title}'s${at === 0 ? " default model" : ""}`)
          .join(" and ")}: they go back to their settings. `
    : "";
  const remove = async () => {
    onTouch();
    setBusy(true);
    setProblem(null);
    try {
      const left = await removeModelServer(
        server.name,
        own.map((m) => m.name),
      );
      onGone(own.length ? `Removed ${server.name} and its ${plural(own.length, "model")}.` : `Removed ${server.name}.`);
      void onChanged(left);
    } catch (error) {
      setProblem(refusalOf(error).message);
      void reread();
    }
  };
  return (
    <div
      className="mx-confirm"
      role="alertdialog"
      aria-labelledby={id}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.stopPropagation();
          onCancel();
        }
      }}
    >
      <p id={id}>
        <b>{ask}</b> {lost}
        {server.has_key && "Its key is deleted too. "}This cannot be undone.
      </p>
      <div className="mx-form-acts">
        <button type="button" className="danger" disabled={busy} onClick={() => void remove()}>
          {own.length ? `Remove server and ${plural(own.length, "model")}` : "Remove server"}
        </button>
        <button type="button" className="quiet" autoFocus onClick={onCancel}>
          Cancel
        </button>
      </div>
      {problem && (
        <span className="field-note bad" role="alert">
          {problem}
        </span>
      )}
    </div>
  );
}
