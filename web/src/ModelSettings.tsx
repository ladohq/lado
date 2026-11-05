// Settings → Models (docs/design/ui.md, Models): one section, no tabs, an intro and two blocks:
// Your agent CLIs, a card per agent CLI with its default model and the configured models it
// runs; Model servers, where those models come from (ModelSources.tsx). What the commands
// `lado model-server` and `lado model` do, with their rules and lines: every refusal is the
// core's line under the field it names. The entries are read when the section opens and after
// each change of its own (GET /api/model-settings asks no server); opening it reads no source
// and only the lists of CLIs whose default is built-in, in the background. Opening a picker
// reads its CLI's list now and asks each server of that CLI's models once. Nothing under the
// pointer moves (useScrollAnchor) and no row leaves on a timer: the page scrolls to the section
// once, when it opens at #models, and keeps it at the top while the sections above grow, until
// the human acts; a model removed by × leaves its row as Undo, then as a line, until the
// human's next change here. The page says nothing of sessions using a default: none does yet.
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useLocation } from "react-router";

import {
  addModel,
  clearModelDefault,
  type ConfiguredModelInfo,
  type EntryRefused,
  getModelSettings,
  getProviderLogins,
  getProviderModels,
  type ModelCheck,
  type ModelSettings as Entries,
  probeModelServer,
  type ProviderLogins,
  refusalOf,
  removeModel,
  renameModel,
  setModelDefault,
} from "./api";
import { CloseIcon } from "./icons";
import { MODEL_DEBOUNCE, useDebounced } from "./Launch";
import { type Health, ModelPicker, type Pick, serverWords, useModelChoices } from "./ModelPicker";
import { listed, loginWord, ModelServers, type Read, type Saved, serverKey, type Sources } from "./ModelSources";
import { MODELS_ANCHOR } from "./paths";
import { POLL_MS } from "./Providers";
import { messageOf } from "./SessionControl";
import { keepAtTop, useScrollAnchor } from "./useScrollAnchor";

export const INTRO = "Choose a default model for each agent CLI, and add the models of your own servers.";
export const LEAD =
  "A default model for each agent CLI. Left on its settings, the agent CLI chooses. Your models come from the model servers below.";
export const LEAD_NO_MODELS =
  "A default model for each agent CLI. To add models of your own, add a model server below and tick the agent CLIs that run them.";
// Reads of the CLIs' rows at most while they are not read yet.
const LOGIN_POLLS = 30;
// How long a model removed by × offers Undo; its row then stays as a line.
export const UNDO_MS = 10000;
const FOLD_ABOVE = 5; // a card with more models shows this many until unfolded

// A model removed by ×: its row offers Undo (`expired`: no more), saying why Undo was refused;
// `wasDefault`: it was its CLI's default, which Undo sets again.
type Removed = {
  model: ConfiguredModelInfo;
  wasDefault: boolean;
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
  // By CLI: a default that went with its server, until the human's next change here.
  const [lostDefaults, setLostDefaults] = useState<Record<string, string>>({});
  // By a model's folded name: why Undo could not set its default again.
  const [rowNotes, setRowNotes] = useState<Record<string, string>>({});
  const [unfolded, setUnfolded] = useState<Set<string>>(new Set()); // the CLIs, while the page stays
  const section = useRef<HTMLElement>(null);
  const latest = useRef(0);
  const shown = useRef<Entries | null>(null); // the entries last taken
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
      if (!Array.isArray(found?.models) || !Array.isArray(found?.servers) || !Array.isArray(found?.defaults))
        throw new Error("the server gave no models: reload the page");
      const servers = new Set(found.servers.map((s) => fold(s.name)));
      const gone = (shown.current?.defaults ?? []).filter(
        (d) =>
          d.server !== null &&
          !servers.has(fold(d.server)) &&
          !found.defaults.some((now) => now.cli === d.cli && now.external === d.external),
      );
      if (gone.length)
        setLostDefaults((now) => ({
          ...now,
          ...Object.fromEntries(gone.map((d) => [d.cli, `Its default model ${d.name} was removed with ${d.server}.`])),
        }));
      shown.current = found;
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
  // out go, the lines of the last server added or changed, and of defaults lost with a server.
  const onTouch = useCallback(() => {
    setRemoved((now) => Object.fromEntries(Object.entries(now).filter(([, gone]) => !gone.expired)));
    setSaved((now) => (Object.keys(now).length ? {} : now));
    setLostDefaults((now) => (Object.keys(now).length ? {} : now));
    setRowNotes((now) => (Object.keys(now).length ? {} : now));
  }, []);
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
  const onRemoved = (model: ConfiguredModelInfo, wasDefault: boolean) => {
    onTouch();
    set(model.name, { model, wasDefault, problem: null, busy: false, expired: false });
  };
  const undo = async (gone: Removed) => {
    const { model } = gone;
    onTouch();
    set(model.name, { ...gone, busy: true, problem: null });
    let id: string;
    try {
      id = (
        await addModel({
          name: model.name,
          cli: model.cli,
          model: model.model,
          server: model.server,
        })
      ).model.id;
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
    if (gone.wasDefault) {
      try {
        await reload((await setModelDefault(model.cli, { external: id })).settings);
      } catch (error) {
        // The model is back; only its default is not: its row says why.
        await reload();
        setRowNotes((now) => ({ ...now, [fold(model.name)]: refusalOf(error).message }));
      }
    } else await reload();
    setFocusName(model.name);
    set(model.name, null);
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
  };
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
            <h3>Your agent CLIs</h3>
            <p className="mx-lead">
              {entries.models.length + Object.keys(removed).length > 0 ? LEAD : LEAD_NO_MODELS}
            </p>
            <AgentClis
              entries={entries}
              logins={logins}
              reads={reads}
              removed={removed}
              lostDefaults={lostDefaults}
              rowNotes={rowNotes}
              unfolded={unfolded}
              focusName={focusName}
              onFocused={() => setFocusName(null)}
              onChanged={reload}
              onTouch={onTouch}
              onRemoved={onRemoved}
              onUndo={(gone) => void undo(gone)}
              onExpired={(gone) => set(gone.model.name, { ...gone, expired: true })}
              onFold={(cli) =>
                setUnfolded((now) => {
                  const next = new Set(now);
                  if (!next.delete(cli)) next.add(cli);
                  return next;
                })
              }
            />
          </div>
          <ModelServers {...sources} />
        </>
      )}
    </section>
  );
}

// The warning of a configured model whose server's list, as last read here, lacks it.
function goneOf(model: ConfiguredModelInfo, reads: Record<string, Read>): string | null {
  const has = listed(reads[serverKey(model.server)]);
  if (has === null || has.has(model.model)) return null;
  return `${model.server} no longer lists ${model.model}: agents on it stop at their first turn.`;
}

type Card = {
  cli: string;
  title: string;
  off: boolean; // its field shows its value and does not open
  word: string; // its login, as Agent CLIs and environment read it
  known: boolean; // LADO knows the CLI: a model of one it does not know still has a card
};

type CardsProps = {
  entries: Entries;
  reads: Record<string, Read>;
  removed: Record<string, Removed>;
  lostDefaults: Record<string, string>;
  rowNotes: Record<string, string>;
  unfolded: Set<string>;
  focusName: string | null;
  onFocused: () => void;
  onChanged: (given?: Entries) => Promise<void>;
  onTouch: () => void;
  onRemoved: (model: ConfiguredModelInfo, wasDefault: boolean) => void;
  onUndo: (gone: Removed) => void;
  onExpired: (gone: Removed) => void;
  onFold: (cli: string) => void;
};

// Your agent CLIs: a card per agent CLI LADO knows, the installed ones in LADO's order, then the
// ones not installed, then one for a model of a CLI it does not know.
function AgentClis({ logins, ...props }: CardsProps & { logins: ProviderLogins[] }) {
  const { entries, removed } = props;
  const notInstalled = (row: ProviderLogins) => row.ready && !row.cli.installed;
  const rows = [...logins.filter((r) => !notInstalled(r)), ...logins.filter(notInstalled)];
  const cards: Card[] = rows.map((row) => ({
    cli: row.cli.name,
    title: row.cli.title,
    off: notInstalled(row),
    word: loginWord(row),
    known: true,
  }));
  for (const m of [...entries.models, ...Object.values(removed).map((g) => g.model)])
    if (!cards.some((c) => c.cli === m.cli))
      cards.push({ cli: m.cli, title: m.cli_title, off: true, word: "", known: false });
  return (
    <div className="mx-cards">
      {cards.map((card) => (
        <CliCard key={card.cli} card={card} {...props} />
      ))}
    </div>
  );
}

function CliCard({
  card,
  entries,
  reads,
  removed,
  lostDefaults,
  rowNotes,
  unfolded,
  focusName,
  onFocused,
  onChanged,
  onTouch,
  onRemoved,
  onUndo,
  onExpired,
  onFold,
}: CardsProps & { card: Card }) {
  const id = useId();
  const { cli, title, off } = card;
  const value = entries.defaults.find((d) => d.cli === cli) ?? null;
  const live = entries.models.filter((m) => m.cli === cli).sort(byName);
  const list = useModelChoices(cli);
  const { read } = list;
  const field = useRef<HTMLButtonElement>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [other, setOther] = useState<string | null>(null); // Other name's field, with its text
  const [health, setHealth] = useState<Record<string, Health>>({});
  const [checking, setChecking] = useState(false);
  const probes = useRef<Record<string, number>>({}); // each server's latest question

  // A built-in default is read in the background, so a list that lost it shows on the card.
  const builtin = value?.builtin ?? null;
  useEffect(() => {
    if (builtin !== null && !off) read(false, builtin);
  }, [builtin, off, read]);

  const probe = async (server: string) => {
    const key = fold(server);
    const asked = (probes.current[key] = (probes.current[key] ?? 0) + 1);
    let found: Health;
    try {
      found = { models: (await probeModelServer(server)).models };
    } catch (error) {
      found = { down: refusalOf(error).message };
    }
    if (probes.current[key] === asked) setHealth((now) => ({ ...now, [key]: found }));
  };

  const save = async (pick: Pick): Promise<boolean> => {
    onTouch();
    setProblem(null);
    try {
      if (pick === null) await onChanged(await clearModelDefault(cli));
      else await onChanged((await setModelDefault(cli, pick)).settings);
      return true;
    } catch (error) {
      setProblem(refusalOf(error).message);
      return false;
    }
  };
  const useSettings = async () => {
    await save(null);
    field.current?.focus();
  };
  const useSettingsChip = (
    <button type="button" className="chip-button" onClick={() => void useSettings()}>
      {`Use ${title}'s settings`}
    </button>
  );

  const check = builtin !== null && list.checked === builtin ? list.choices?.check : undefined;
  const lost = check?.kind === "refused";
  const server = value?.server ?? null;
  const state = server !== null ? health[fold(server)] : undefined;
  const words = value !== null ? serverWords(state, value.model) : null;
  const address = entries.servers.find((s) => fold(s.name) === fold(server ?? ""))?.address ?? "";
  const checkAgain = (onCheck: () => void, busy: boolean) => (
    <button
      type="button"
      className="chip-button"
      aria-disabled={busy ? true : undefined}
      onClick={() => !busy && onCheck()}
    >
      Check again
    </button>
  );
  const askServer = () => {
    if (server === null) return;
    setChecking(true);
    void probe(server).finally(() => setChecking(false));
  };

  const notes = [
    problem !== null && (
      <span key="problem" className="field-note bad" role="alert">
        {problem}
      </span>
    ),
    value?.external != null && value.whole_process && (
      <span key="whole" className="field-note">
        {`On ${title} this model takes the whole process: an agent on it runs only on ${server}.`}
      </span>
    ),
    lost && (
      <span key="lost" className="field-note warn" role="status">
        <span>{`⚠ ${title} no longer lists ${builtin}: agents on it stop at their first turn.`}</span>
        <span className="way-out">{useSettingsChip}</span>
      </span>
    ),
    check?.kind === "warn" && (
      <span key="warn" className="field-note warn" role="status">
        <span>{`⚠ ${check.text}`}</span>
        {list.choices?.read_again && (
          <span className="way-out">{checkAgain(() => read(true, builtin ?? ""), list.reading)}</span>
        )}
      </span>
    ),
    words !== null && value !== null && server !== null && state !== undefined && (
      <span key="server" className="field-note warn" role="status">
        <span>
          {"down" in state
            ? `⚠ ${state.down.replace(address, server)}; ${value.name} is on it. Start the server or pick another model.`
            : `⚠ ${server} no longer lists ${value.model}: agents on it stop at their first turn.`}
        </span>
        <span className="way-out">
          {checkAgain(askServer, checking)}
          {useSettingsChip}
        </span>
      </span>
    ),
    checking && server !== null && (
      <span key="checking" className="field-note" role="status">
        <span className="mx-spin" aria-hidden="true" /> {`checking ${server} …`}
      </span>
    ),
    off && card.known && value !== null && (
      <span key="off" className="way-out">
        {useSettingsChip}
      </span>
    ),
    lostDefaults[cli] && (
      <span key="gone" className="field-note">
        {lostDefaults[cli]}
      </span>
    ),
  ].filter(Boolean);

  const gone = Object.values(removed).filter(
    (g) => g.model.cli === cli && !live.some((m) => fold(m.name) === fold(g.model.name)),
  );
  const rows = [
    ...live.map((model) => ({ model, gone: null as Removed | null })),
    ...gone.map((g) => ({ model: g.model, gone: g as Removed | null })),
  ].sort((a, b) => {
    const first = (m: ConfiguredModelInfo) => (m.id === value?.external ? 0 : 1);
    return first(a.model) - first(b.model) || byName(a.model, b.model);
  });
  const open = unfolded.has(cli);
  const shown = open || rows.length <= FOLD_ABOVE ? rows : rows.slice(0, FOLD_ABOVE);
  const servers = new Map(entries.servers.map((s) => [fold(s.name), s.address]));
  const warning =
    card.off && card.known
      ? value !== null
        ? "⚠ not installed: its default model cannot run"
        : live.length > 0
          ? "⚠ not installed: its models cannot run"
          : "⚠ not installed"
      : null;

  return (
    <div className={`mc-cli${off ? " mc-off" : ""}`} role="group" aria-label={title} data-anchor="">
      <div className="mc-head">
        <span className="mc-name">{title}</span>
        {warning ? <span className="mx-card-warn">{warning}</span> : <span className="mc-state">{card.word}</span>}
      </div>
      <div className="mc-row">
        <span className="mc-label">Default model</span>
        <div className="mc-field">
          <ModelPicker
            cli={{ name: cli, title }}
            value={value}
            where="settings"
            own={live}
            list={list}
            off={off}
            lost={lost}
            health={health}
            describedBy={notes.length > 0 ? `${id}-notes` : undefined}
            fieldRef={field}
            onOpen={() => {
              for (const name of new Set(live.map((m) => m.server))) void probe(name);
            }}
            onPick={(pick) => void save(pick)}
            onOther={setOther}
          />
          {other !== null && (
            <OtherName
              cli={cli}
              start={other}
              onUse={async (name) => {
                if (await save({ builtin: name })) {
                  setOther(null);
                  field.current?.focus();
                }
              }}
              onCancel={() => {
                setOther(null);
                field.current?.focus();
              }}
            />
          )}
          {notes.length > 0 && (
            <div className="mc-notes" id={`${id}-notes`}>
              {notes}
            </div>
          )}
        </div>
      </div>
      {rows.length > 0 && (
        <div className="mc-models">
          <div className="mx-table" role="table" aria-label={`Your models on ${title}`}>
            <div className="mx-mrow mx-mhead" role="row">
              <span role="columnheader" aria-label="Name">
                <span aria-hidden="true">Your models</span>{" "}
                <span className="mx-count" aria-hidden="true">
                  {live.length}
                </span>
              </span>
              <span role="columnheader">Model</span>
              <span role="columnheader">From</span>
              <span role="columnheader" aria-label="Remove" />
            </div>
            {shown.map(({ model, gone }) =>
              gone ? (
                <UndoRow key={`removed:${model.name}`} gone={gone} onUndo={onUndo} onExpired={onExpired} />
              ) : (
                <ModelRow
                  key={model.name}
                  model={model}
                  isDefault={model.id === value?.external}
                  address={servers.get(fold(model.server))}
                  gone={goneOf(model, reads)}
                  note={rowNotes[fold(model.name)] ?? null}
                  focus={focusName !== null && fold(focusName) === fold(model.name)}
                  onFocused={onFocused}
                  onChanged={onChanged}
                  onTouch={onTouch}
                  onRemoved={onRemoved}
                />
              ),
            )}
          </div>
          {rows.length > FOLD_ABOVE && (
            <div className="mc-more">
              <button type="button" className="link-button" aria-expanded={open} onClick={() => onFold(cli)}>
                {open ? "Show fewer" : `Show all ${rows.length} models`}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// `Other name…`'s field: the check `lado model default` would make once the typing settles,
// and Use, off while refused; the warning of a name set so then stands on the card.
function OtherName({
  cli,
  start,
  onUse,
  onCancel,
}: {
  cli: string;
  start: string;
  onUse: (name: string) => Promise<void>;
  onCancel: () => void;
}) {
  const id = useId();
  const [text, setText] = useState(start);
  const [check, setCheck] = useState<{ of: string; note: ModelCheck } | null>(null);
  const name = text.trim();
  const settled = useDebounced(name, MODEL_DEBOUNCE);
  useEffect(() => {
    if (!settled) return;
    let current = true;
    getProviderModels(cli, settled).then(
      (found) => current && setCheck({ of: settled, note: found.check }),
      () => undefined, // Use says what is wrong
    );
    return () => {
      current = false;
    };
  }, [cli, settled]);
  const note = check?.of === name ? check.note : null;
  return (
    <div className="mc-other">
      <label className="mc-other-l" htmlFor={id}>
        Other name
      </label>
      <div className="mc-other-row">
        <input
          id={id}
          className="mono"
          value={text}
          autoFocus
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              onCancel();
            }
          }}
        />
        <button
          type="button"
          className="quiet"
          disabled={!name || note?.kind === "refused"}
          onClick={() => void onUse(name)}
        >
          Use
        </button>
        <button type="button" className="quiet" onClick={onCancel}>
          Cancel
        </button>
      </div>
      {note && note.kind !== "default" && (
        <span className={`field-note${note.kind === "refused" ? " bad" : note.kind === "warn" ? " warn" : ""}`}>
          {note.text}
        </span>
      )}
    </div>
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
  const { model, wasDefault, problem, busy, expired } = gone;
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
          Removed <b>{model.name}</b>.{wasDefault && ` ${model.cli_title} is back on its settings.`}
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
  isDefault,
  address,
  gone,
  note,
  focus,
  onFocused,
  onChanged,
  onTouch,
  onRemoved,
}: {
  model: ConfiguredModelInfo;
  isDefault: boolean;
  address: string | undefined;
  gone: string | null;
  note: string | null;
  focus: boolean;
  onFocused: () => void;
  onChanged: (given?: Entries) => Promise<void>;
  onTouch: () => void;
  onRemoved: (model: ConfiguredModelInfo, wasDefault: boolean) => void;
}) {
  const [renaming, setRenaming] = useState(false);
  const [asking, setAsking] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const name = useRef<HTMLButtonElement>(null);
  const cross = useRef<HTMLButtonElement>(null);
  const refocus = useRef(false);
  const backToCross = useRef(false);
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
  useEffect(() => {
    if (asking || !backToCross.current) return;
    backToCross.current = false;
    cross.current?.focus();
  }, [asking]);
  const remove = async () => {
    setProblem(null);
    try {
      const left = await removeModel(model.name);
      onRemoved(model, isDefault);
      await onChanged(left);
    } catch (error) {
      setAsking(false);
      setProblem(refusalOf(error).message);
    }
  };
  const cancel = () => {
    backToCross.current = true;
    setAsking(false);
  };
  if (asking)
    return (
      <div
        className="mx-mrow mc-ask mx-confirm"
        role="alertdialog"
        aria-label={`Remove ${model.name}?`}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            cancel();
          }
        }}
      >
        <p>
          <b>{`Remove ${model.name}?`}</b>
          {` It is ${model.cli_title}'s default model: ${model.cli_title} goes back to its settings.`}
        </p>
        <div className="mx-form-acts">
          <button type="button" className="danger" onClick={() => void remove()}>
            Remove model
          </button>
          <button type="button" className="quiet" autoFocus onClick={cancel}>
            Cancel
          </button>
        </div>
      </div>
    );
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
        {(problem ?? note) && <span className="field-note bad">{problem ?? note}</span>}
      </span>
      <span className="mx-meta">
        <span className="mx-model mono" role="cell" title={model.model}>
          {model.model}
        </span>
        <span className="mx-from" role="cell" title={address}>
          {model.server}
        </span>
      </span>
      <span className="mx-x-cell" role="cell">
        <button
          ref={cross}
          type="button"
          className="mx-icon"
          title="Remove"
          aria-label={`Remove ${model.name}`}
          onClick={() => (isDefault ? setAsking(true) : void remove())}
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
