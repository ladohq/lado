// Settings → Models (docs/design/ui.md, Models): Your models, the configured models, above
// Sources, where models come from (ModelSources.tsx), and + Add server. What the commands
// `lado model-server` and `lado model` do, with their rules and lines: every refusal is the
// core's line under the field it names. The entries are read when the section opens and
// after each change of its own (GET /api/model-settings asks no server); opening it reads
// no source. A server's key lives only in its field (SecretField), emptied after a send, on
// Cancel and when the form closes. The page scrolls to it at #models.
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useLocation } from "react-router";

import {
  addModelServer,
  type ConfiguredModelInfo,
  type EntryRefused,
  getModelSettings,
  getProviderLogins,
  type ModelSettings as Entries,
  type ProbeInfo,
  type ProviderLogins,
  refusalOf,
  removeModel,
  renameModel,
} from "./api";
import {
  CheckNote,
  clisLine,
  cliKey,
  FieldNotes,
  listed,
  ModelSources,
  type Read,
  type Saved,
  serverKey,
} from "./ModelSources";
import { MODELS_ANCHOR } from "./paths";
import { SecretField } from "./ProjectVariables";
import { POLL_MS } from "./Providers";
import { messageOf } from "./SessionControl";

export const EMPTY =
  "No models yet. Without them each agent runs on its CLI's default model. Tick models in Sources below.";
const LOGIN_POLLS = 30; // reads of the CLIs' rows at most while they are not read yet

export function ModelSettings() {
  const id = useId();
  const [entries, setEntries] = useState<Entries | null>(null);
  const [logins, setLogins] = useState<ProviderLogins[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  const [reads, setReads] = useState<Record<string, Read>>({});
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [saved, setSaved] = useState<Record<string, Saved>>({});
  const [adding, setAdding] = useState(false);
  const section = useRef<HTMLElement>(null);
  const latest = useRef(0);
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
  // The CLIs' install and login as Providers and environment's last check read them; read
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
        () => undefined, // Providers and environment says why
      );
    void take();
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, []);
  useEffect(() => {
    if (entries && hash === `#${MODELS_ANCHOR}`) section.current?.scrollIntoView({ block: "start" });
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
  const onSaved = useCallback((key: string, done: Saved | null) => {
    setSaved((now) => {
      const next = { ...now };
      if (done === null) delete next[key];
      else next[key] = done;
      return next;
    });
  }, []);

  return (
    <section className="setting" id={MODELS_ANCHOR} ref={section} aria-labelledby={id}>
      <h2 id={id}>Models</h2>
      {problem && (
        <p className="problem" role="alert">
          {problem}
        </p>
      )}
      {entries && (
        <>
          <div className="project-section">
            <h3>Your models</h3>
            {entries.models.length === 0 ? (
              <p className="mm-empty">{EMPTY}</p>
            ) : (
              <YourModels entries={entries} logins={logins} reads={reads} onChanged={reload} />
            )}
          </div>
          <div className="project-section">
            <h3>Sources</h3>
            <p className="muted">
              Where models come from: the agent CLIs and your model servers. Open one to read its models.
            </p>
            <ModelSources
              settings={entries}
              logins={logins}
              reads={reads}
              onRead={onRead}
              open={open}
              onOpen={onOpen}
              saved={saved}
              onSaved={onSaved}
              onChanged={(given) => void reload(given)}
            />
            {adding ? (
              <AddServer
                onCancel={() => setAdding(false)}
                onAdded={(name, probe, done) => {
                  setAdding(false);
                  const key = serverKey(name);
                  onOpen(key, true);
                  onRead(key, { probe });
                  onSaved(key, done);
                  void reload();
                }}
              />
            ) : (
              <div className="project-add">
                <button type="button" className="quiet" onClick={() => setAdding(true)}>
                  + Add server
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}

// The warnings of a configured model: its CLI not installed, its model not in the list its
// source gave when last read here.
function warningsOf(model: ConfiguredModelInfo, logins: ProviderLogins[], reads: Record<string, Read>): string[] {
  const out: string[] = [];
  const row = logins.find((r) => r.cli.name === model.cli);
  if (row?.ready && !row.cli.installed) out.push(`${model.cli_title} is not installed`);
  const source = model.server ?? model.cli_title;
  const has = listed(reads[model.server === null ? cliKey(model.cli) : serverKey(model.server)]);
  if (has !== null && !has.has(model.model)) out.push(`not in ${source}'s list of models`);
  return out;
}

function YourModels({
  entries,
  logins,
  reads,
  onChanged,
}: {
  entries: Entries;
  logins: ProviderLogins[];
  reads: Record<string, Read>;
  onChanged: (given?: Entries) => Promise<void>;
}) {
  const [renaming, setRenaming] = useState<string | null>(null);
  const [problem, setProblem] = useState<{ name: string; text: string } | null>(null);
  const remove = async (name: string) => {
    setProblem(null);
    try {
      await onChanged(await removeModel(name));
    } catch (error) {
      setProblem({ name, text: refusalOf(error).message });
    }
  };
  return (
    <>
      <table className="project-vars mm-models">
        <thead>
          <tr>
            <th>Name</th>
            <th>CLI</th>
            <th>Model</th>
            <th>Source</th>
            <th aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {entries.models.map((model) => (
            <tr key={model.name}>
              <td className="project-name">
                {renaming === model.name ? (
                  <Rename
                    name={model.name}
                    onDone={(given) => {
                      setRenaming(null);
                      void onChanged(given);
                    }}
                    onCancel={() => setRenaming(null)}
                  />
                ) : (
                  <>
                    <span className="mm-name">{model.name}</span>{" "}
                    <button
                      type="button"
                      className="mm-pen"
                      title="Rename"
                      aria-label={`Rename ${model.name}`}
                      onClick={() => setRenaming(model.name)}
                    >
                      ✎
                    </button>
                  </>
                )}
                {problem?.name === model.name && <span className="field-note bad">{problem.text}</span>}
              </td>
              <td>{model.cli_title}</td>
              <td className="project-value">{model.model}</td>
              <td className={model.server === null ? "muted" : undefined}>
                {model.server ?? model.cli_title}
                {warningsOf(model, logins, reads).map((line) => (
                  <div key={line} className="field-note warn">{`⚠ ${line}`}</div>
                ))}
              </td>
              <td className="project-acts">
                <button type="button" className="quiet" onClick={() => void remove(model.name)}>
                  Remove
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mm-hint">Rename in place (✎): the name is yours; sessions will refer to the model, not to its name.</p>
    </>
  );
}

function Rename({
  name,
  onDone,
  onCancel,
}: {
  name: string;
  onDone: (given: Entries) => void;
  onCancel: () => void;
}) {
  const [text, setText] = useState(name);
  const [refused, setRefused] = useState<EntryRefused | null>(null);
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    setRefused(null);
    try {
      onDone(await renameModel(name, text));
    } catch (error) {
      setRefused(refusalOf(error));
      setBusy(false);
    }
  };
  return (
    <div className="project-edit">
      <input
        className="project-in-name"
        aria-label={`New name of ${name}`}
        value={text}
        autoFocus
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") void save();
          if (event.key === "Escape") onCancel();
        }}
      />
      <button type="button" className="primary" disabled={busy} onClick={() => void save()}>
        Save
      </button>
      <button type="button" className="quiet" onClick={onCancel}>
        Cancel
      </button>
      {refused && <CheckNote note={refused} />}
    </div>
  );
}

// + Add server: Name, Address and Key (optional); Add probes and saves as `lado model-server
// add` does.
function AddServer({
  onCancel,
  onAdded,
}: {
  onCancel: () => void;
  onAdded: (name: string, probe: ProbeInfo, saved: Saved) => void;
}) {
  const id = useId();
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [refused, setRefused] = useState<EntryRefused | null>(null);
  const [busy, setBusy] = useState(false);
  const key = useRef<HTMLInputElement>(null);
  const add = async () => {
    const given = key.current?.value ?? "";
    if (key.current) key.current.value = "";
    setBusy(true);
    setRefused(null);
    try {
      const done = await addModelServer(name, address, given === "" ? null : given);
      onAdded(done.server.name, done.probe, {
        notes: done.notes,
        warnings: done.warnings,
        saved: `✓ Saved model server "${done.server.name}". For: ${clisLine(done.probe)}`,
      });
    } catch (error) {
      setRefused(refusalOf(error));
      setBusy(false);
    }
  };
  return (
    <div className="mm-form">
      <div className="launch-grid">
        <div className="field">
          <label htmlFor={`${id}-name`}>Name</label>
          <input
            id={`${id}-name`}
            value={name}
            placeholder="e.g. LM Studio at home"
            onChange={(event) => setName(event.target.value)}
          />
          <FieldNotes refused={refused} field="name" />
        </div>
        <div className="field">
          <label htmlFor={`${id}-address`}>Address</label>
          <input
            id={`${id}-address`}
            className="mono"
            value={address}
            placeholder="localhost:1234 or https://host/v1"
            onChange={(event) => setAddress(event.target.value)}
          />
          <FieldNotes refused={refused} field="address" />
        </div>
        <div className="field launch-wide">
          <label htmlFor={`${id}-key`}>
            Key <span className="muted mm-opt">optional</span>
          </label>
          <SecretField
            field={key}
            label="Key"
            placeholder="only if the server asks for one (not shown after saving)"
            onEnter={() => void add()}
          />
          {refused?.warnings.map((line) => (
            <span key={line} className="field-note warn">{`⚠ ${line}`}</span>
          ))}
          <FieldNotes refused={refused} field="key" />
        </div>
      </div>
      <div className="mm-acts">
        <button type="button" className="primary" disabled={busy || !name || !address.trim()} onClick={() => void add()}>
          {busy ? "checking the server…" : "Add"}
        </button>
        <button type="button" className="quiet" onClick={onCancel}>
          Cancel
        </button>
      </div>
      {refused && !["name", "address", "key"].includes(refused.field) && <CheckNote note={refused} />}
    </div>
  );
}
