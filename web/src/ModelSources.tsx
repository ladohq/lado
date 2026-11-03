// Settings → Models, Add models (docs/design/ui.md, Models): every agent CLI LADO knows, then
// every saved model server, then + Add server. A source opens from its whole row; opening it
// reads its models now (a CLI's aliases and own list through the launch window's route with
// `fresh`, a server's by a probe with its kept key), ↻ reads them again; nothing is read
// before and no list outlives the page. A list's order is set when it is read (the source's
// configured models first) and no tick changes it; it is bounded and scrolls within itself.
// A CLI's model has one tick; a server's model opens under its row the installed CLIs that
// can run it, a tick each. A tick is on exactly when a configured model has that CLI, model
// and server: ticking saves one with its default name, unticking removes it. A server shows
// its list, its Change form or its Remove confirmation, one at a time. Nothing above the
// control acted on moves: a server added takes the form's place, one removed leaves a line.
import { type MutableRefObject, type ReactNode, useEffect, useId, useRef, useState } from "react";

import {
  addModel,
  addModelServer,
  checkModel,
  checkModelServer,
  type ConfiguredModelInfo,
  type EntryRefused,
  getModelSettings,
  getProviderModels,
  type ModelCheck,
  type ModelServerInfo,
  type ModelSettings,
  type ProbeInfo,
  probeModelServer,
  type ProviderLogins,
  type ProviderModels,
  refusalOf,
  removeModel,
  removeModelServer,
  type ServerCheck,
} from "./api";
import { ForgetIcon, PencilIcon } from "./icons";
import { MODEL_DEBOUNCE, useDebounced } from "./Launch";
import { SecretField } from "./ProjectVariables";
import { messageOf } from "./SessionControl";

const SEARCH_ABOVE = 10; // a list longer than this has a search field

// A source's models as last read: reading, a CLI's list or a server's probe with the order
// set at that read, or why not.
export type Read =
  | { reading: true }
  | { cli: ProviderModels; order: string[] }
  | { probe: ProbeInfo; order: string[] }
  | { refused: EntryRefused };

// After a server was saved or changed here: the lines its source shows.
export type Saved = { notes: string[]; warnings: string[]; saved: string };

export const cliKey = (name: string) => `cli:${name}`;
export const serverKey = (name: string) => `server:${name.toLowerCase()}`;
const fold = (text: string) => text.toLowerCase();
const plural = (n: number, one: string) => `${n} ${one}${n === 1 ? "" : "s"}`;

// The configured models of `model` of `cli` on `server` (null: the CLI's own way); a
// server's name is found ignoring case.
const ticked = (models: ConfiguredModelInfo[], cli: string, model: string, server: string | null) =>
  models.filter((m) => m.cli === cli && m.model === model && fold(m.server ?? "") === fold(server ?? ""));

// The tick of `model` of `cli` on `server`: on when a configured model has them; with
// several, the names of them all (the tick is then disabled).
export function tickState(
  models: ConfiguredModelInfo[],
  cli: string,
  model: string,
  server: string | null,
): { on: boolean; several: string[] } {
  const same = ticked(models, cli, model, server);
  return { on: same.length > 0, several: same.length > 1 ? same.map((m) => m.name) : [] };
}

// The configured models a source gave: a CLI's own (no server), or a server's.
const fromSource = (models: ConfiguredModelInfo[], cli: string | null, server: string | null) =>
  models.filter((m) => (server === null ? m.server === null && m.cli === cli : fold(m.server ?? "") === fold(server)));

// The models a read list holds, embeddings left out (null: it gave no list, so none is
// missing from it).
export function listed(read: Read | undefined): Set<string> | null {
  if (!read) return null;
  if ("cli" in read) return read.cli.models === null ? null : new Set([...read.cli.aliases, ...read.cli.models]);
  if ("probe" in read) return read.probe.models === null ? null : new Set(read.probe.models);
  return null;
}

const listOf = (found: { cli: ProviderModels } | { probe: ProbeInfo }): string[] => {
  if ("cli" in found) return [...new Set([...found.cli.aliases, ...(found.cli.models ?? [])])];
  const embeddings = new Set(found.probe.embeddings);
  return (found.probe.models ?? []).filter((m) => !embeddings.has(m));
};

// A list's order at its read: the models of the source's configured models it no longer
// lists, then those it lists, then the rest as it gave them.
export function orderOf(list: string[], own: ConfiguredModelInfo[]): string[] {
  const mine = new Set(own.map((m) => m.model));
  const has = new Set(list);
  return [...[...mine].filter((m) => !has.has(m)), ...list.filter((m) => mine.has(m)), ...list.filter((m) => !mine.has(m))];
}

type Props = {
  settings: ModelSettings;
  logins: ProviderLogins[];
  reads: Record<string, Read>;
  onRead: (key: string, read: Read | null) => void;
  open: Set<string>;
  onOpen: (key: string, open: boolean) => void;
  saved: Record<string, Saved>;
  onSaved: (key: string, saved: Saved | null) => void;
  onChanged: (settings?: ModelSettings) => Promise<void> | void;
  onRemoved: (model: ConfiguredModelInfo) => void; // a model unticked: Your models offers Undo
  // The latest read of each source, by key: whatever fills a source (a read here, an add or
  // a change) counts one up, so an older read's late answer is dropped.
  latest: MutableRefObject<Record<string, number>>;
  // A CLI whose source opens when this tab shows (a card's link in Your models), then null.
  opening?: MutableRefObject<string | null>;
};

// A new read, add or change of the source `key`: its number in `latest`.
const nextRead = (latest: MutableRefObject<Record<string, number>>, key: string) =>
  (latest.current[key] = (latest.current[key] ?? 0) + 1);

export function ModelSources(props: Props) {
  const { settings, logins, latest } = props;
  const models = useRef(settings.models); // the entries a read's order is set from
  models.current = settings.models;
  const read = (key: string, own: (models: ConfiguredModelInfo[]) => ConfiguredModelInfo[], ask: () => Promise<Read>) => {
    const asked = nextRead(latest, key);
    props.onRead(key, { reading: true });
    ask().then(
      (found) => {
        if (latest.current[key] !== asked) return;
        if ("cli" in found || "probe" in found) found = { ...found, order: orderOf(listOf(found), own(models.current)) };
        props.onRead(key, found);
      },
      (error: unknown) => latest.current[key] === asked && props.onRead(key, { refused: refusalOf(error) }),
    );
  };
  const readCli = (name: string) =>
    read(
      cliKey(name),
      (all) => fromSource(all, name, null),
      async () => ({ cli: await getProviderModels(name, "", null, true), order: [] }),
    );
  const readServer = (name: string) =>
    read(
      serverKey(name),
      (all) => fromSource(all, null, name),
      async () => ({ probe: await probeModelServer(name), order: [] }),
    );
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
    props.onRead(key, { probe, order: orderOf(listOf({ probe }), fromSource(models.current, null, name)) });
    props.onSaved(key, saved);
  };
  // A read outlives this tab (the section keeps it): its answer fills the source shown again.
  useEffect(() => {
    const cli = props.opening?.current;
    if (props.opening) props.opening.current = null;
    if (cli && !props.open.has(cliKey(cli))) toggle(cliKey(cli), () => readCli(cli));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, when the tab shows
  }, []);
  const installed = (cli: string) => {
    const row = logins.find((r) => r.cli.name === cli);
    return !row?.ready || row.cli.installed;
  };
  // The servers by name at the first render, then each one added here at the end, where its
  // form was; a server removed here leaves its line in its place.
  const order = useRef<string[] | null>(null);
  if (order.current === null) order.current = settings.servers.map((s) => s.name).sort((a, b) => fold(a).localeCompare(fold(b)));
  for (const server of settings.servers)
    if (!order.current.some((name) => fold(name) === fold(server.name))) order.current.push(server.name);
  const [gone, setGone] = useState<Record<string, string>>({});
  const [adding, setAdding] = useState(false);

  return (
    <ul className="mx-srcs">
      {logins.map((row) => {
        const key = cliKey(row.cli.name);
        return (
          <CliSource
            key={key}
            row={row}
            open={props.open.has(key)}
            read={props.reads[key]}
            models={settings.models}
            onToggle={() => toggle(key, () => readCli(row.cli.name))}
            onRefresh={() => readCli(row.cli.name)}
            onChanged={props.onChanged}
            onRemoved={props.onRemoved}
          />
        );
      })}
      {order.current.map((name) => {
        const key = serverKey(name);
        const server = settings.servers.find((s) => fold(s.name) === fold(name));
        if (!server)
          return gone[fold(name)] ? (
            <li key={key} className="mx-src">
              <div className="mx-gone-line" role="status">
                {gone[fold(name)]}
              </div>
            </li>
          ) : null;
        return (
          <ServerSource
            key={key}
            server={server}
            open={props.open.has(key)}
            read={props.reads[key]}
            saved={props.saved[key]}
            models={settings.models}
            installed={installed}
            onToggle={() => toggle(key, () => readServer(server.name))}
            onClose={() => props.open.has(key) && close(key)}
            onRefresh={() => readServer(server.name)}
            onProbe={(probe, saved) => filled(server.name, probe, saved)}
            onStale={() => props.onSaved(key, null)}
            onGone={(line) => {
              close(key);
              for (const one of Object.keys(props.saved)) props.onSaved(one, null); // old now
              setGone((now) => ({ ...now, [fold(server.name)]: line }));
            }}
            onChanged={props.onChanged}
            onRemoved={props.onRemoved}
          />
        );
      })}
      <li className="mx-src">
        {adding ? (
          <AddServer
            onCancel={() => setAdding(false)}
            onAdded={(server, probe, saved) => {
              setAdding(false);
              filled(server.name, probe, saved);
              void props.onChanged();
            }}
          />
        ) : (
          <div className="mx-addrow">
            <button type="button" className="quiet" onClick={() => setAdding(true)}>
              + Add server
            </button>
            <span className="mx-sub">LM Studio, Ollama, LiteLLM or another OpenAI-compatible server</span>
          </div>
        )}
      </li>
    </ul>
  );
}

function loginWord(row: ProviderLogins): string {
  if (!row.ready) return "";
  if (!row.cli.installed) return "not installed";
  if (row.login.state === "no") return "not logged in";
  if (row.login.state === "yes") return "logged in";
  return "";
}

// A source's row: the whole row opens and closes it (its framed arrow turns), its name, its
// badge, how many models it gave and its state or address; its icons at the right.
function SourceHead({
  title,
  badge,
  open,
  off,
  added,
  hint,
  onToggle,
  children,
  acts,
}: {
  title: string;
  badge: string;
  open: boolean;
  off: boolean;
  added: number;
  hint?: string;
  onToggle: () => void;
  children: ReactNode;
  acts?: ReactNode;
}) {
  const id = useId();
  return (
    <div className="mx-head">
      <button
        type="button"
        className="mx-hit"
        aria-expanded={open}
        aria-label={title}
        aria-describedby={id}
        disabled={off}
        title={hint}
        onClick={onToggle}
      >
        <span className="mx-chev" aria-hidden="true">
          ▶
        </span>
        <span className="mx-title">{title}</span>
        <span className="badge">{badge}</span>
        <span className="mx-meta" id={id}>
          {added > 0 && (
            <>
              <b className="mx-added">{`${added} added`}</b>
              {" · "}
            </>
          )}
          {children}
        </span>
      </button>
      <span className="mx-acts">{acts}</span>
    </div>
  );
}

function CliSource({
  row,
  open,
  read,
  models,
  onToggle,
  onRefresh,
  onChanged,
  onRemoved,
}: {
  row: ProviderLogins;
  open: boolean;
  read: Read | undefined;
  models: ConfiguredModelInfo[];
  onToggle: () => void;
  onRefresh: () => void;
  onChanged: (settings?: ModelSettings) => Promise<void> | void;
  onRemoved: (model: ConfiguredModelInfo) => void;
}) {
  const cli = row.cli;
  const off = row.ready && !cli.installed;
  const own = fromSource(models, cli.name, null);
  return (
    <li className={`mx-src${open ? " mx-open" : ""}${off ? " mx-off" : ""}`}>
      <SourceHead
        title={cli.title}
        badge="CLI"
        open={open}
        off={off}
        added={own.length}
        hint={off ? `${cli.title} is not installed` : undefined}
        onToggle={onToggle}
      >
        {loginWord(row)}
      </SourceHead>
      {open && (
        <SourceBody
          read={read}
          cli={{ name: cli.name, title: cli.title }}
          server={null}
          columns={[]}
          models={models}
          own={own}
          onRefresh={onRefresh}
          onChanged={onChanged}
          onRemoved={onRemoved}
        />
      )}
    </li>
  );
}

type Column = { name: string; title: string };

function ServerSource({
  server,
  open,
  read,
  saved,
  models,
  installed,
  onToggle,
  onClose,
  onRefresh,
  onProbe,
  onStale,
  onGone,
  onChanged,
  onRemoved,
}: {
  server: ModelServerInfo;
  open: boolean;
  read: Read | undefined;
  saved: Saved | undefined;
  models: ConfiguredModelInfo[];
  installed: (cli: string) => boolean;
  onToggle: () => void;
  onClose: () => void;
  onRefresh: () => void;
  onProbe: (probe: ProbeInfo, saved: Saved) => void;
  onStale: () => void;
  onGone: (line: string) => void;
  onChanged: (settings?: ModelSettings) => Promise<void> | void;
  onRemoved: (model: ConfiguredModelInfo) => void;
}) {
  const [mode, setMode] = useState<"change" | "remove" | null>(null);
  const own = fromSource(models, null, server.name);
  const probe = read && "probe" in read ? read.probe : null;
  const columns: Column[] = (probe?.clis ?? []).filter((c) => installed(c.name));
  // One of the list, Change and Remove at a time.
  const show = (next: "change" | "remove") => {
    const to = mode === next ? null : next;
    setMode(to);
    if (to) {
      onClose();
      onStale();
    }
  };
  return (
    <li className={`mx-src${open ? " mx-open" : ""}`}>
      <SourceHead
        title={server.name}
        badge={server.kind}
        open={open}
        off={false}
        added={own.length}
        hint={server.address}
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
              title="Change the address or key"
              onClick={() => show("change")}
            >
              <PencilIcon />
            </button>
            <button
              type="button"
              className="mx-icon mx-icon-danger"
              aria-pressed={mode === "remove"}
              aria-label={`Remove ${server.name}`}
              title="Remove the server"
              onClick={() => show("remove")}
            >
              <ForgetIcon />
            </button>
          </>
        }
      >
        <span className="mono">{server.address}</span>
        {server.has_key ? " · key" : ""}
      </SourceHead>
      {mode === "change" && (
        <ChangeServer
          server={server}
          onDone={(probe, done) => {
            setMode(null);
            onProbe(probe, done);
            void onChanged();
          }}
          onCancel={() => setMode(null)}
        />
      )}
      {mode === "remove" && (
        <RemoveServer
          server={server}
          own={own}
          onCancel={() => setMode(null)}
          onChanged={onChanged}
          onGone={(line) => {
            setMode(null);
            onGone(line);
          }}
        />
      )}
      {open && saved && (
        <div className="mx-saved">
          <span className="field-note ok">{`✓ ${saved.saved}`}</span>
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
      {open && (
        <SourceBody
          read={read}
          cli={null}
          server={server.name}
          columns={columns}
          models={models}
          own={own}
          onRefresh={onRefresh}
          onChanged={onChanged}
          onRemoved={onRemoved}
        />
      )}
    </li>
  );
}

// An open source's list: reading, the refusal, or its models in the order of its read,
// bounded, with a search above a long one and its count under it; then Model id where the
// list is not whole.
function SourceBody({
  read,
  cli,
  server,
  columns,
  models,
  own,
  onRefresh,
  onChanged,
  onRemoved,
}: {
  read: Read | undefined;
  cli: Column | null; // a CLI's source, else a server's (`server`, `columns`)
  server: string | null;
  columns: Column[];
  models: ConfiguredModelInfo[];
  own: ConfiguredModelInfo[];
  onRefresh: () => void;
  onChanged: (settings?: ModelSettings) => Promise<void> | void;
  onRemoved: (model: ConfiguredModelInfo) => void;
}) {
  const [search, setSearch] = useState("");
  const [refused, setRefused] = useState<{ model: string; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [pop, setPop] = useState<string | null>(null);
  const reading = !read || "reading" in read;
  const tools = (extra?: ReactNode) => (
    <div className="mx-tools">
      {extra}
      <span className="mx-tools-end">
        <button
          type="button"
          className="mx-icon"
          aria-label="Refresh the list"
          title="Read the list again"
          disabled={reading}
          onClick={onRefresh}
        >
          ↻
        </button>
      </span>
    </div>
  );
  if (reading)
    return (
      <div className="mx-body">
        <p className="mx-count">reading the models…</p>
      </div>
    );
  if ("refused" in read) {
    const stay = own.map((m) => m.name);
    return (
      <div className="mx-body">
        {tools()}
        <span className="field-note warn" role="alert">
          {`⚠ ${read.refused.message}${stay.length ? `. Its models stay: ${stay.join(", ")}.` : ""}`}
        </span>
        {read.refused.hint && <span className="field-note warn">{`⚠ ${read.refused.hint}`}</span>}
      </div>
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
  const whole = cli ? "cli" in read && read.cli.models !== null : probe?.models !== null;
  const tick = async (on: string, model: string, add: boolean) => {
    setBusy(true);
    setRefused(null);
    try {
      if (add) await addModel({ name: null, cli: on, model, server });
      else {
        const [one] = ticked(models, on, model, server);
        if (one) {
          await removeModel(one.name);
          onRemoved(one);
        }
      }
    } catch (error) {
      setRefused({ model, text: refusalOf(error).message });
    } finally {
      setBusy(false);
      void onChanged();
    }
  };
  const box = (on: Column, model: string) => {
    const state = tickState(models, on.name, model, server);
    const gone = missing(model) && !state.on; // a model gone from the list is unticked only
    return (
      <input
        type="checkbox"
        aria-label={`${model} on ${on.title}`}
        checked={state.on}
        disabled={busy || state.several.length > 0 || gone}
        title={
          state.several.length
            ? `${state.several.join(", ")}: remove them in Your models`
            : gone
              ? `${model} is no longer listed: ↻ reads the list again`
              : undefined
        }
        onChange={(event) => void tick(on.name, model, event.target.checked)}
      />
    );
  };
  const note = (model: string) =>
    refused?.model === model && (
      <div className="mx-row-note">
        <span className="field-note bad">{refused.text}</span>
      </div>
    );
  const cliRow = (on: Column, model: string) => {
    const same = ticked(models, on.name, model, null).filter((m) => m.name !== model);
    return (
      <div key={model}>
        <label className={`mx-row${missing(model) ? " mx-row-gone" : ""}`}>
          {box(on, model)}
          <span className="mono" title={model}>
            {model}
            {missing(model) && " ⚠ no longer listed"}
          </span>
          {same.length > 0 && (
            <span className="mx-as" title={same.map((m) => m.name).join(", ")}>
              {same.map((m) => `as ${m.name}`).join(", ")}
            </span>
          )}
        </label>
        {note(model)}
      </div>
    );
  };
  const serverRow = (model: string) => {
    const entries = models.filter((m) => m.model === model && fold(m.server ?? "") === fold(server ?? ""));
    const titles = [...new Set(entries.map((m) => m.cli_title))];
    const opened = pop === model;
    if (columns.length === 0)
      return (
        <div key={model} className={`mx-row mx-row-plain${missing(model) ? " mx-row-gone" : ""}`}>
          <span className="mono" title={model}>
            {model}
          </span>
        </div>
      );
    return (
      <div key={model}>
        <div
          className={`mx-row mx-row-pop${missing(model) ? " mx-row-gone" : ""}${opened ? " mx-row-on" : ""}`}
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
          <span className="mono" title={model}>
            {model}
            {missing(model) && " ⚠ no longer listed"}
          </span>
          <span className="mx-as mx-in" title={titles.join(", ")}>
            {titles.length > 0 && `in ${titles.join(", ")}`}
          </span>
          <span className="mx-cli-btn" aria-hidden="true">
            {titles.length ? "CLIs ▾" : "+ Add ▾"}
          </span>
        </div>
        {opened && (
          <div
            className="mx-pop"
            role="group"
            aria-label={`Agent CLIs for ${model}`}
            onKeyDown={(event) => event.key === "Escape" && setPop(null)}
          >
            <div className="mx-pop-h">
              These agent CLIs can run <b className="mono">{model}</b>:
            </div>
            {columns.map((on) => {
              const names = ticked(models, on.name, model, server).map((m) => m.name);
              return (
                <label key={on.name} className="mx-pop-item">
                  {box(on, model)}
                  <span>{on.title}</span>
                  <span className="mx-sub">{names.join(", ")}</span>
                </label>
              );
            })}
            <div className="mx-pop-f">
              <button type="button" className="quiet" onClick={() => setPop(null)}>
                Done
              </button>
            </div>
          </div>
        )}
        {note(model)}
      </div>
    );
  };
  return (
    <div className="mx-body">
      {tools(
        rows.length > SEARCH_ABOVE && (
          <input
            className="mx-search"
            type="search"
            aria-label="Search the models"
            placeholder={`Search ${rows.length} models`}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        ),
      )}
      {probe && probe.models === null && <span className="field-note warn">{`⚠ no list of models: ${probe.models_why}`}</span>}
      {probe?.apis_why && <span className="field-note warn">{`⚠ APIs: cannot be told: ${probe.apis_why}`}</span>}
      {server !== null && columns.length === 0 && (
        <span className="field-note">No installed CLI can use this server.</span>
      )}
      {rows.length > 0 && (
        <div className="mx-list">
          {shown.map((model) => (cli ? cliRow(cli, model) : serverRow(model)))}
          {shown.length === 0 && <div className="mx-row mx-row-plain muted">{`No model matches “${search}”.`}</div>}
        </div>
      )}
      {rows.length > 0 && (
        <p className="mx-count">
          {typed ? `${shown.length} of ${plural(rows.length, "model")}` : plural(rows.length, "model")}
        </p>
      )}
      {embeddings > 0 && (
        <p className="mx-count">
          {`${plural(embeddings, "embeddings model")} hidden: agents cannot run on ${embeddings === 1 ? "it" : "them"}.`}
        </p>
      )}
      {!whole && (cli !== null || columns.length > 0) && (
        <ModelId columns={cli ? [cli] : columns} server={server} onChanged={onChanged} />
      )}
    </div>
  );
}

// Model id: a model of a source whose list is not whole, the check `lado model add` would make
// under the field once the typing settles, and Add (off while refused).
function ModelId({
  columns,
  server,
  onChanged,
}: {
  columns: Column[];
  server: string | null;
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
    <div className={`mx-other${server !== null ? " mx-other-cli" : ""}`}>
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
      {server !== null && (
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
      )}
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
      <>
        <span className="field-note bad" role="alert">
          {note.message}
        </span>
        {note.hint && <span className="field-note warn">{`⚠ ${note.hint}`}</span>}
      </>
    );
  if (note.kind === "ok") return <span className="field-note ok">{`✓ ${note.text}`}</span>;
  if (note.kind === "warn") return <span className="field-note warn">{`⚠ ${note.text}`}</span>;
  if (note.kind === "refused") return <span className="field-note bad">{note.text}</span>;
  return <span className="field-note">{note.text}</span>;
}

// A refusal's notes under the field it names (`field`), else none.
function FieldNotes({ refused, field }: { refused: EntryRefused | null; field: string }) {
  if (!refused || refused.field !== field) return null;
  return <CheckNote note={refused} />;
}

const warnings = (lines: string[]) =>
  lines.map((line) => <span key={line} className="field-note warn">{`⚠ ${line}`}</span>);

// What a probe found, said under Address before Add.
function probeLine(probe: ProbeInfo): string {
  const embeddings = new Set(probe.embeddings);
  const count = probe.models === null ? "no list of models" : plural(probe.models.filter((m) => !embeddings.has(m)).length, "model");
  const clis = probe.clis.length ? `${probe.clis.map((c) => c.title).join(", ")} can run them` : "no agent CLI can use it";
  return `${probe.kind} · ${count} · ${clis}`;
}

// + Add server: Name, Address and Key (optional). Once the typing settles the form checks
// the name and probes the address without the key; Check key probes it with the key; Add
// probes and saves as `lado model-server add` does, on only for a free name and a server
// that answered, or asks for a key with one typed. An older check's answer is dropped.
function AddServer({
  onCancel,
  onAdded,
}: {
  onCancel: () => void;
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
  const [keyed, setKeyed] = useState<{ for: string; rev: number; found?: ServerCheck } | null>(null);
  useEffect(() => {
    const [n, a, f] = settled.split("\n");
    const mine = ++asked.current;
    if (!n && !a.trim()) return setAuto(null);
    setAuto({ for: settled });
    checkModelServer(n, a, null, f === "true").then(
      (found) => mine === asked.current && setAuto({ for: settled, found }),
      (error: unknown) =>
        mine === asked.current &&
        setAuto({ for: settled, found: { probe: null, refusals: [refusalOf(error)], warnings: [], notes: [] } }),
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
        setKeyed({ ...at, found: { probe: null, refusals: [refusalOf(error)], warnings: [], notes: [] } }),
    );
  };
  const keyedNow = keyed && keyed.for === typed && keyed.rev === keyRev ? keyed : null;
  const autoNow = auto && auto.for === typed ? auto : null;
  const result = keyedNow?.found ?? (keyedNow ? undefined : autoNow?.found);
  const checking = !busy && (typed !== settled || (autoNow !== null && !autoNow.found) || (keyedNow !== null && !keyedNow.found));
  const of = (field: string) => (result?.refusals ?? []).filter((r) => r.field === field && refused?.field !== field);
  const asksKey = !keyedNow && (result?.refusals ?? []).some((r) => r.field === "key");
  const ready =
    !busy &&
    !checking &&
    name !== "" &&
    address.trim() !== "" &&
    result !== undefined &&
    !result.refusals.some((r) => ["name", "address", ""].includes(r.field)) &&
    (result.probe !== null || (asksKey && filled));
  // A refusal of Add under a field goes once that field is edited.
  const edited = (field: string) => setRefused((now) => (now?.field === field ? null : now));
  const add = async () => {
    if (!ready) return;
    const given = key.current?.value ?? "";
    if (key.current) key.current.value = "";
    setFilled(false);
    setBusy(true);
    setRefused(null);
    try {
      const done = await addModelServer(name, address, given === "" ? null : given);
      onAdded(done.server, done.probe, {
        notes: done.notes,
        warnings: done.warnings,
        saved: `Saved model server "${done.server.name}".`,
      });
    } catch (error) {
      setRefused(refusalOf(error));
      setBusy(false);
    }
  };
  const notes = (lines: EntryRefused[], look: "bad" | "warn") =>
    lines.map((r) =>
      look === "bad" ? (
        <CheckNote key={r.message} note={r} />
      ) : (
        <span key={r.message}>
          <span className="field-note warn">{`⚠ ${r.message}`}</span>
          {r.hint && <span className="field-note warn">{`⚠ ${r.hint}`}</span>}
        </span>
      ),
    );
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
            onChange={(event) => {
              setName(event.target.value);
              edited("name");
            }}
          />
          {notes(of("name"), "bad")}
          <FieldNotes refused={refused} field="name" />
        </div>
        <div className="field">
          <label htmlFor={`${id}-address`}>Address</label>
          <input
            id={`${id}-address`}
            value={address}
            placeholder="localhost:1234 or https://host/v1"
            onChange={(event) => {
              setAddress(event.target.value);
              edited("address");
            }}
          />
          {checking && address.trim() !== "" ? (
            <span className="field-note mx-check">
              <span className="mx-spin" aria-hidden="true" />
              {` checking ${address.trim()}…`}
            </span>
          ) : (
            <>
              {result?.probe && <span className="field-note ok">{`✓ ${probeLine(result.probe)}`}</span>}
              {notes(of("address"), "bad")}
              {asksKey && notes(of("key"), "warn")}
              {(result?.notes ?? []).map((line) => (
                <span key={line} className="field-note">
                  {line}
                </span>
              ))}
            </>
          )}
          <FieldNotes refused={refused} field="address" />
        </div>
        <div className="field launch-wide">
          <label htmlFor={`${id}-key`}>
            Key <span className="muted mx-opt">optional</span>
          </label>
          <SecretField
            field={key}
            label="Key"
            placeholder="only if the server asks for one (not shown after saving)"
            onFilled={(now) => {
              setFilled(now);
              setKeyRev((n) => n + 1);
              edited("key");
            }}
            onEnter={() => void add()}
          />
          {filled && warnings(result?.warnings ?? [])}
          {warnings((refused?.warnings ?? []).filter((line) => !(filled && result?.warnings.includes(line))))}
          {!checking && !asksKey && notes(of("key"), "bad")}
          {asksKey && filled && (
            <span className="field-note">The key is sent to the server only when you press Check key or Add.</span>
          )}
          <FieldNotes refused={refused} field="key" />
        </div>
      </div>
      <div className="mx-form-acts">
        <button type="button" className="primary" disabled={!ready} onClick={() => void add()}>
          {busy ? "checking the server…" : "Add"}
        </button>
        {asksKey && filled && (
          <button type="button" className="quiet" onClick={checkKey}>
            Check key
          </button>
        )}
        <button type="button" className="quiet" onClick={onCancel}>
          Cancel
        </button>
        {notes(of(""), "bad")}
        {refused && !["name", "address", "key"].includes(refused.field) && <CheckNote note={refused} />}
      </div>
    </div>
  );
}

// The plain-http warning `lado model-server add --replace` gives before it sends anything,
// for the address once the typing settles, while a key goes with it (`keyGoes`); null for
// none. The form's check gives it (its probe of the address is not shown here).
function usePlainHttp(address: string, keyGoes: boolean): string | null {
  const typed = useDebounced(address.trim(), MODEL_DEBOUNCE);
  const [found, setFound] = useState<string | null>(null);
  useEffect(() => {
    setFound(null);
    if (!typed || !keyGoes) return;
    let current = true;
    checkModelServer("", typed, null, true).then(
      (check) => current && setFound(check.warnings[0] ?? null),
      () => undefined, // Save says what is wrong
    );
    return () => {
      current = false;
    };
  }, [typed, keyGoes]);
  return keyGoes && typed === address.trim() ? found : null;
}

// Change: the server's Address, filled, and New key, empty (the kept key stays); Save
// replaces it as `lado model-server add --replace` does, then its list opens.
function ChangeServer({
  server,
  onDone,
  onCancel,
}: {
  server: ModelServerInfo;
  onDone: (probe: ProbeInfo, saved: Saved) => void;
  onCancel: () => void;
}) {
  const id = useId();
  const [address, setAddress] = useState(server.address);
  const [refused, setRefused] = useState<EntryRefused | null>(null);
  const [busy, setBusy] = useState(false);
  const [filled, setFilled] = useState(false);
  const key = useRef<HTMLInputElement>(null);
  const live = usePlainHttp(address, filled || server.has_key); // empty: the kept key goes
  const save = async () => {
    const given = key.current?.value ?? "";
    if (key.current) key.current.value = "";
    setFilled(false);
    setBusy(true);
    setRefused(null);
    try {
      const done = await addModelServer(server.name, address, given === "" ? null : given, true);
      onDone(done.probe, {
        notes: done.notes,
        warnings: done.warnings,
        saved: `Saved model server "${done.server.name}".`,
      });
    } catch (error) {
      setRefused(refusalOf(error));
      setBusy(false);
    }
  };
  return (
    <div className="mx-form">
      <div className="launch-grid">
        <div className="field">
          <label htmlFor={`${id}-address`}>Address</label>
          <input
            id={`${id}-address`}
            value={address}
            onChange={(event) => {
              setAddress(event.target.value);
              setRefused((now) => (now?.field === "address" ? null : now));
            }}
          />
          <FieldNotes refused={refused} field="address" />
        </div>
        <div className="field">
          <label htmlFor={`${id}-key`}>
            New key <span className="muted mx-opt">empty keeps the key</span>
          </label>
          <SecretField
            field={key}
            label="New key"
            placeholder="empty: the saved key stays"
            onFilled={(now) => {
              setFilled(now);
              setRefused((was) => (was?.field === "key" ? null : was));
            }}
            onEnter={() => void save()}
          />
          {live && <span className="field-note warn">{`⚠ ${live}`}</span>}
          {warnings((refused?.warnings ?? []).filter((line) => line !== live))}
          <FieldNotes refused={refused} field="key" />
        </div>
      </div>
      <div className="mx-form-acts">
        <button type="button" className="primary" disabled={busy || !address.trim()} onClick={() => void save()}>
          {busy ? "checking the server…" : "Save"}
        </button>
        <button type="button" className="quiet" onClick={onCancel}>
          Cancel
        </button>
        <span className="field-note">{`Models on ${server.name} keep referring to it.`}</span>
        {refused && !["address", "key"].includes(refused.field) && <CheckNote note={refused} />}
      </div>
    </div>
  );
}

// Remove: asks in the server's row, naming the models saved now (the CLI may have added one
// since the page read them) and saying the key goes too; the removal takes only those,
// refused when the server has others by then, and then it asks anew.
function RemoveServer({
  server,
  own,
  onCancel,
  onChanged,
  onGone,
}: {
  server: ModelServerInfo;
  own: ConfiguredModelInfo[];
  onCancel: () => void;
  onChanged: (settings?: ModelSettings) => Promise<void> | void;
  onGone: (line: string) => void;
}) {
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
  const remove = async () => {
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
    <div className="mx-confirm">
      <span>{`${ask} Its key is deleted too; this cannot be undone.`}</span>
      <div className="mx-form-acts">
        <button type="button" className="danger" disabled={busy} onClick={() => void remove()}>
          {own.length ? "Remove server and models" : "Remove"}
        </button>
        <button type="button" className="quiet" onClick={onCancel}>
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
