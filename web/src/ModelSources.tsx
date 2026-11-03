// Settings → Models, Sources (docs/design/ui.md, Models): every agent CLI LADO knows, then
// every saved model server. Opening one reads its models now (a CLI's aliases and own list
// through the launch window's route with `fresh`, a server's by a probe with its kept key),
// ↻ Refresh reads them again; nothing is read before and no list outlives the page. Each
// model has a tick per CLI that can run it: on exactly when a configured model has that CLI,
// model and server (ticking saves one with its default name, unticking removes it). The
// latest read of a source wins; a closed source takes no late answer.
import { type MutableRefObject, useEffect, useId, useRef, useState } from "react";

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
} from "./api";
import { MODEL_DEBOUNCE, useDebounced } from "./Launch";
import { SecretField } from "./ProjectVariables";
import { messageOf } from "./SessionControl";
import { SuggestField } from "./SuggestField";

export const SEARCH_ABOVE = 10; // a list longer than this has a search field

// A source's models as last read: reading, a CLI's list, a server's probe, or why not.
export type Read =
  | { reading: true }
  | { cli: ProviderModels }
  | { probe: ProbeInfo }
  | { refused: EntryRefused };

// After a server was saved or changed here: the lines its source shows.
export type Saved = { notes: string[]; warnings: string[]; saved: string | null };

export const cliKey = (name: string) => `cli:${name}`;
export const serverKey = (name: string) => `server:${name.toLowerCase()}`;

// The configured models of `model` of `cli` on `server` (null: the CLI's own way); a
// server's name is found ignoring case.
const ticked = (models: ConfiguredModelInfo[], cli: string, model: string, server: string | null) =>
  models.filter(
    (m) => m.cli === cli && m.model === model && (m.server ?? "").toLowerCase() === (server ?? "").toLowerCase(),
  );

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

// The models a read list holds (null: it gave no list, so none is missing from it).
export function listed(read: Read | undefined): Set<string> | null {
  if (!read) return null;
  if ("cli" in read) return read.cli.models === null ? null : new Set([...read.cli.aliases, ...read.cli.models]);
  if ("probe" in read) return read.probe.models === null ? null : new Set(read.probe.models);
  return null;
}

// What the CLIs a probe found can use the server, grouped by API as `lado model-server
// probe` prints them.
export function clisLine(probe: ProbeInfo): string {
  const groups: string[] = [];
  for (const api of [...new Set(probe.clis.map((c) => c.api))]) {
    const titles = probe.clis.filter((c) => c.api === api).map((c) => c.title);
    groups.push(`${titles.join(", ")} (${api})`);
  }
  return groups.join("; ") || "no CLI";
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
  onChanged: (settings?: ModelSettings) => void;
  // The latest read of each source, by key: whatever fills a source (a read here, an add or
  // a change) counts one up, so an older read's late answer is dropped.
  latest: MutableRefObject<Record<string, number>>;
};

// A new read, add or change of the source `key`: its number in `latest`.
export const nextRead = (latest: MutableRefObject<Record<string, number>>, key: string) =>
  (latest.current[key] = (latest.current[key] ?? 0) + 1);

export function ModelSources(props: Props) {
  const { settings, logins, latest } = props;
  const read = (key: string, ask: () => Promise<Read>) => {
    const asked = nextRead(latest, key);
    props.onRead(key, { reading: true });
    ask().then(
      (found) => latest.current[key] === asked && props.onRead(key, found),
      (error: unknown) =>
        latest.current[key] === asked &&
        props.onRead(key, { refused: refusalOf(error) }),
    );
  };
  const readCli = (name: string) =>
    read(cliKey(name), async () => ({ cli: await getProviderModels(name, "", null, true) }));
  const readServer = (name: string) =>
    read(serverKey(name), async () => ({ probe: await probeModelServer(name) }));
  const toggle = (key: string, reader: () => void) => {
    const opening = !props.open.has(key);
    props.onOpen(key, opening);
    props.onSaved(key, null); // the lines of a save are said once, in the open source
    if (opening) reader();
    else {
      nextRead(latest, key); // no late answer fills it
      props.onRead(key, null);
    }
  };
  useEffect(() => {
    const asked = latest.current;
    return () => {
      for (const key of Object.keys(asked)) asked[key]++;
    };
  }, []);
  const installed = (cli: string) => {
    const row = logins.find((r) => r.cli.name === cli);
    return !row?.ready || row.cli.installed;
  };

  return (
    <ul className="src-list">
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
          />
        );
      })}
      {settings.servers.map((server) => {
        const key = serverKey(server.name);
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
            onRefresh={() => readServer(server.name)}
            onProbe={(probe, saved) => {
              nextRead(latest, key);
              props.onOpen(key, true); // a changed server shows open, as an added one
              props.onRead(key, { probe });
              props.onSaved(key, saved);
            }}
            onStale={() => props.onSaved(key, null)}
            onChanged={props.onChanged}
          />
        );
      })}
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

function CliSource({
  row,
  open,
  read,
  models,
  onToggle,
  onRefresh,
  onChanged,
}: {
  row: ProviderLogins;
  open: boolean;
  read: Read | undefined;
  models: ConfiguredModelInfo[];
  onToggle: () => void;
  onRefresh: () => void;
  onChanged: (settings?: ModelSettings) => void;
}) {
  const cli = row.cli;
  const off = row.ready && !cli.installed;
  const word = loginWord(row);
  const list = read && "cli" in read ? read.cli : null;
  const rows: ModelRow[] = list
    ? [
        ...list.aliases.map((value) => ({ value, tag: "alias" })),
        ...(list.models ?? []).filter((m) => !list.aliases.includes(m)).map((value) => ({ value, tag: "" })),
      ]
    : [];
  return (
    <li className={`src${open ? " src-open" : ""}${off ? " src-off" : ""}`}>
      <div className="src-head">
        <button
          type="button"
          className="src-toggle"
          aria-expanded={open}
          disabled={off}
          onClick={onToggle}
          title={off ? `${cli.title} is not installed` : undefined}
        >
          <span className="src-chev" aria-hidden="true">
            {open ? "▾" : "▸"}
          </span>
          <strong>{cli.title}</strong>
        </button>
        <span className="badge">CLI</span>
        {word && <span className="src-sub">{word}</span>}
        {open && (
          <button type="button" className="quiet src-refresh" onClick={onRefresh} disabled={read && "reading" in read}>
            ↻ Refresh
          </button>
        )}
      </div>
      {open && (
        <SourceBody
          read={read}
          rows={rows}
          columns={[{ name: cli.name, title: cli.title }]}
          server={null}
          whose={`${cli.title}'s list`}
          models={models}
          missing={models.filter((m) => m.cli === cli.name && m.server === null)}
          onChanged={onChanged}
        />
      )}
    </li>
  );
}

type ModelRow = { value: string; tag: string };
type Column = { name: string; title: string };

function ServerSource({
  server,
  open,
  read,
  saved,
  models,
  installed,
  onToggle,
  onRefresh,
  onProbe,
  onStale,
  onChanged,
}: {
  server: ModelServerInfo;
  open: boolean;
  read: Read | undefined;
  saved: Saved | undefined;
  models: ConfiguredModelInfo[];
  installed: (cli: string) => boolean;
  onToggle: () => void;
  onRefresh: () => void;
  onProbe: (probe: ProbeInfo, saved: Saved) => void;
  onStale: () => void;
  onChanged: (settings?: ModelSettings) => void;
}) {
  const [mode, setMode] = useState<"change" | "remove" | null>(null);
  const own = models.filter((m) => (m.server ?? "").toLowerCase() === server.name.toLowerCase());
  const probe = read && "probe" in read ? read.probe : null;
  const embeddings = new Set(probe?.embeddings ?? []);
  const rows: ModelRow[] = (probe?.models ?? []).map((value) => ({
    value,
    tag: embeddings.has(value) ? "(embeddings)" : "",
  }));
  const columns: Column[] = (probe?.clis ?? []).filter((c) => installed(c.name));
  return (
    <li className={`src${open ? " src-open" : ""}`}>
      <div className="src-head">
        <button type="button" className="src-toggle" aria-expanded={open} onClick={onToggle}>
          <span className="src-chev" aria-hidden="true">
            {open ? "▾" : "▸"}
          </span>
          <strong>{server.name}</strong>
        </button>
        <span className="badge">{server.kind}</span>
        <span className="mm-addr">{server.address}</span>
        {server.has_key && <span className="src-sub">key: yes</span>}
        <span className="mm-row-acts">
          {open && (
            <button type="button" className="quiet src-refresh" onClick={onRefresh} disabled={read && "reading" in read}>
              ↻ Refresh
            </button>
          )}
          <button type="button" className="quiet" onClick={() => setMode(mode === "change" ? null : "change")}>
            Change
          </button>
          <button type="button" className="quiet" onClick={() => setMode(mode === "remove" ? null : "remove")}>
            Remove
          </button>
        </span>
      </div>
      {mode === "change" && (
        <ChangeServer
          server={server}
          onSaving={onStale}
          onDone={(probe, done) => {
            setMode(null);
            if (probe && done) onProbe(probe, done);
            onChanged();
          }}
          onCancel={() => setMode(null)}
        />
      )}
      {mode === "remove" && (
        <RemoveServer server={server} own={own} onCancel={() => setMode(null)} onChanged={onChanged} />
      )}
      {open && saved && (
        <>
          {saved.saved && <span className="field-note ok">{saved.saved}</span>}
          {saved.warnings.map((line) => (
            <span key={line} className="field-note warn">{`⚠ ${line}`}</span>
          ))}
          {saved.notes.map((line) => (
            <span key={line} className="field-note">
              {line}
            </span>
          ))}
        </>
      )}
      {open && (
        <SourceBody
          read={read}
          rows={rows}
          columns={columns}
          server={server.name}
          whose="the server's list"
          models={models}
          missing={own}
          onChanged={onChanged}
        />
      )}
    </li>
  );
}

// An open source's list: reading, the refusal, or its models with their ticks, a search
// above a long list, then Other model….
function SourceBody({
  read,
  rows,
  columns,
  server,
  whose,
  models,
  missing,
  onChanged,
}: {
  read: Read | undefined;
  rows: ModelRow[];
  columns: Column[];
  server: string | null;
  whose: string;
  models: ConfiguredModelInfo[];
  missing: ConfiguredModelInfo[];
  onChanged: (settings?: ModelSettings) => void;
}) {
  const [search, setSearch] = useState("");
  const [refused, setRefused] = useState<{ model: string; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  if (!read || "reading" in read) return <p className="mm-line muted">reading the models…</p>;
  if ("refused" in read) {
    const stay = missing.map((m) => m.name);
    return (
      <>
        <span className="field-note warn" role="alert">
          {`⚠ ${read.refused.message}${stay.length ? `. Its models stay: ${stay.join(", ")}.` : ""}`}
        </span>
        {read.refused.hint && <span className="field-note warn">{`⚠ ${read.refused.hint}`}</span>}
      </>
    );
  }
  const has = listed(read);
  const values = new Set(rows.map((r) => r.value));
  const gone = [...new Set(missing.map((m) => m.model).filter((m) => !values.has(m)))];
  const typed = search.trim().toLowerCase();
  const shown = rows.filter((r) => !typed || r.value.toLowerCase().includes(typed));
  const tick = async (cli: string, model: string, on: boolean) => {
    setBusy(true);
    setRefused(null);
    try {
      if (on) await addModel({ name: null, cli, model, server });
      else {
        const [one] = ticked(models, cli, model, server);
        if (one) await removeModel(one.name);
      }
    } catch (error) {
      setRefused({ model, text: refusalOf(error).message });
    } finally {
      setBusy(false);
      onChanged();
    }
  };
  const line = (row: ModelRow, missingTag: string) => {
    const embeddings = row.tag === "(embeddings)";
    return (
      <tr key={row.value} className={missingTag ? "src-missing" : embeddings ? "src-emb" : undefined}>
        <td className="mono">
          {row.value}
          {row.tag && <span className="tag">{row.tag}</span>}
          {missingTag && <span className="tag">{`⚠ ${missingTag}`}</span>}
          {refused?.model === row.value && <span className="field-note bad">{refused.text}</span>}
        </td>
        {columns.map((column) => {
          const state = tickState(models, column.name, row.value, server);
          return (
            <td key={column.name} className="ck">
              <input
                type="checkbox"
                aria-label={`${row.value} on ${column.title}`}
                checked={state.on}
                disabled={busy || embeddings || state.several.length > 0}
                title={state.several.length ? `Models: ${state.several.join(", ")}; remove them in Your models` : undefined}
                onChange={(event) => void tick(column.name, row.value, event.target.checked)}
              />
            </td>
          );
        })}
      </tr>
    );
  };
  return (
    <>
      {rows.length > SEARCH_ABOVE && (
        <input
          className="src-search"
          type="search"
          aria-label="Search the models"
          placeholder={`Search ${rows.length} models`}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      )}
      {"probe" in read && read.probe.models === null && (
        <span className="field-note warn">{`⚠ no list of models: ${read.probe.models_why}`}</span>
      )}
      {"probe" in read && read.probe.apis_why && (
        <span className="field-note warn">{`⚠ APIs: cannot be told: ${read.probe.apis_why}`}</span>
      )}
      {columns.length === 0 && server !== null && (
        <span className="field-note">No installed CLI can use this server.</span>
      )}
      {(rows.length > 0 || gone.length > 0) && columns.length > 0 && (
        <div className="src-scroll">
          <table className="src-models">
            {server !== null && (
              <thead>
                <tr>
                  <th>Model</th>
                  {columns.map((c) => (
                    <th key={c.name} className="ck">
                      {c.title}
                    </th>
                  ))}
                </tr>
              </thead>
            )}
            <tbody>
              {gone.map((model) => line({ value: model, tag: "" }, has === null ? "" : `not in ${whose}`))}
              {shown.map((row) => line(row, ""))}
            </tbody>
          </table>
        </div>
      )}
      {columns.length > 0 && <OtherModel rows={rows} columns={columns} server={server} onChanged={onChanged} />}
    </>
  );
}

// Other model…: a model the list lacks, the check `lado model add` would make under the
// field once the typing settles, and Add.
function OtherModel({
  rows,
  columns,
  server,
  onChanged,
}: {
  rows: ModelRow[];
  columns: Column[];
  server: string | null;
  onChanged: (settings?: ModelSettings) => void;
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
      (error: unknown) => current && setCheck({ kind: "warn", text: messageOf(error), field: "" }),
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
      onChanged();
    } catch (error) {
      setRefused(refusalOf(error));
    } finally {
      setBusy(false);
    }
  };
  const settled = check && typed === model.trim() ? check : null;
  const note = refused ?? settled;
  return (
    <div className="mm-other">
      <div className="field">
        <label htmlFor={id}>Other model…</label>
        <SuggestField
          id={id}
          value={model}
          onValue={(value) => {
            setModel(value);
            setRefused(null);
          }}
          suggestions={rows.filter((r) => r.tag !== "(embeddings)").map((r) => ({ value: r.value, tag: r.tag || undefined }))}
          arrowLabel="Show the models"
          listLabel="Models"
          placeholder="a model the list lacks"
        />
        {note && <CheckNote note={note} />}
      </div>
      {server !== null && (
        <div className="field">
          <label htmlFor={`${id}-cli`}>CLI</label>
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
export function CheckNote({ note }: { note: ModelCheck | EntryRefused }) {
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

// The plain-http warning `lado model-server add` gives before it sends anything, for the
// address once the typing settles, while a key goes with it (`keyGoes`); null for none.
export function usePlainHttp(address: string, keyGoes: boolean): ModelCheck | null {
  const typed = useDebounced(address.trim(), MODEL_DEBOUNCE);
  const [found, setFound] = useState<ModelCheck | null>(null);
  useEffect(() => {
    setFound(null);
    if (!typed || !keyGoes) return;
    let current = true;
    checkModelServer(typed, true).then(
      (check) => current && setFound(check.kind === "warn" ? check : null),
      () => undefined, // Add says what is wrong
    );
    return () => {
      current = false;
    };
  }, [typed, keyGoes]);
  return keyGoes && typed === address.trim() ? found : null;
}

// The notes under Key: the plain-http warning while a key is typed, else the one of the
// last send, then a refusal of the key.
export function KeyNotes({ live, refused }: { live: ModelCheck | null; refused: EntryRefused | null }) {
  const sent = (refused?.warnings ?? []).filter((line) => line !== live?.text);
  return (
    <>
      {live && <CheckNote note={live} />}
      {sent.map((line) => (
        <span key={line} className="field-note warn">{`⚠ ${line}`}</span>
      ))}
      <FieldNotes refused={refused} field="key" />
    </>
  );
}

// A refusal's notes under the field it names (`field`), else none.
export function FieldNotes({ refused, field }: { refused: EntryRefused | null; field: string }) {
  if (!refused || refused.field !== field) return null;
  return <CheckNote note={refused} />;
}

// Change: the server's Address, filled, and New key, empty (the kept key stays).
function ChangeServer({
  server,
  onSaving,
  onDone,
  onCancel,
}: {
  server: ModelServerInfo;
  onSaving: () => void;
  onDone: (probe: ProbeInfo | null, saved: Saved | null) => void;
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
    onSaving(); // the result of an earlier change is old now
    try {
      const done = await addModelServer(server.name, address, given === "" ? null : given, true);
      onDone(done.probe, {
        notes: done.notes,
        warnings: done.warnings,
        saved: `✓ Replaced model server "${done.server.name}". For: ${clisLine(done.probe)}`,
      });
    } catch (error) {
      setRefused(refusalOf(error));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="mm-form">
      <div className="launch-grid">
        <div className="field">
          <label htmlFor={`${id}-address`}>Address</label>
          <input
            id={`${id}-address`}
            className="mono"
            value={address}
            onChange={(event) => {
              setAddress(event.target.value);
              setRefused((now) => (now?.field === "address" ? null : now));
            }}
          />
          <FieldNotes refused={refused} field="address" />
        </div>
        <div className="field project-edit-key">
          <label htmlFor={`${id}-key`}>New key</label>
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
          <KeyNotes live={live} refused={refused} />
        </div>
      </div>
      <div className="mm-acts">
        <button type="button" className="primary" disabled={busy || !address.trim()} onClick={() => void save()}>
          {busy ? "checking the server…" : "Save"}
        </button>
        <button type="button" className="quiet" onClick={onCancel}>
          Cancel
        </button>
        <span className="field-note">{`Models on ${server.name} keep referring to it.`}</span>
      </div>
      {refused && !["address", "key"].includes(refused.field) && <CheckNote note={refused} />}
    </div>
  );
}

function RemoveServer({
  server,
  own,
  onCancel,
  onChanged,
}: {
  server: ModelServerInfo;
  own: ConfiguredModelInfo[];
  onCancel: () => void;
  onChanged: (settings?: ModelSettings) => void;
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
  // The models it names are the ones saved now (the CLI may have added one since the page
  // read them); the removal takes only those, refused when the server has others by then,
  // and then the entries are read again and it asks anew.
  const reread = () =>
    getModelSettings().then(
      (found) => {
        if (!current.current) return;
        onChanged(found);
        setBusy(false);
      },
      (error: unknown) => current.current && setProblem(refusalOf(error).message),
    );
  useEffect(() => {
    void reread();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, when it asks
  }, []);
  const ask = own.length
    ? `Remove ${server.name} and its ${own.length} models: ${own.map((m) => m.name).join(", ")}?`
    : `Remove ${server.name}?`;
  const remove = async () => {
    setBusy(true);
    setProblem(null);
    try {
      onChanged(
        await removeModelServer(
          server.name,
          own.map((m) => m.name),
        ),
      );
    } catch (error) {
      setProblem(refusalOf(error).message);
      void reread();
    }
  };
  return (
    <div className="mm-confirm">
      <span className="project-ask">{ask}</span>
      <div className="mm-acts">
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
