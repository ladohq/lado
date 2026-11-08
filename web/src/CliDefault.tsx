// A CLI's default model in its row on Settings → Agent CLIs (docs/design/ui.md, Agent CLIs):
// `Default model` and the CLI's picker, which saves at once as `lado model default` does, with
// its warnings and their ways out under it. Opening the row reads the CLI's list only for a
// built-in default, in the background; opening the picker reads its list now and asks each
// server of the CLI's models once. A CLI not installed has no picker: with a default, one line
// that it cannot run and `Use <CLI>'s settings`. A save that succeeds says `✓ Saved` beside the
// field until the human's next change on the page; which row says it is the page's (Providers.tsx).
import { useEffect, useId, useRef, useState } from "react";

import {
  checkModelDefault,
  clearModelDefault,
  type ModelCheck,
  probeModelServer,
  type ProviderLogins,
  refusalOf,
  setModelDefault,
  unreachable,
} from "./api";
import { MODEL_DEBOUNCE, useDebounced } from "./Launch";
import { type Health, ModelPicker, type Pick, serverWords, useModelChoices } from "./ModelPicker";
import type { ModelSettingsState } from "./useModelSettings";

const fold = (text: string) => text.toLowerCase();

// The page's `✓ Saved`: the CLI whose row says it, cleared when a save starts, taken by the row
// whose save succeeded.
export type SavedProps = { saved: string | null; onSaving: () => void; onSaved: () => void };

export function CliDefault({
  row,
  settings,
  ...mark
}: { row: ProviderLogins; settings: ModelSettingsState } & SavedProps) {
  const { entries } = settings;
  const cli = row.cli.name;
  const value = entries?.defaults.find((d) => d.cli === cli) ?? null;
  if (entries === null) return null;
  if (!row.cli.installed)
    return value === null ? null : <NotInstalled row={row} name={value.name} settings={settings} mark={mark} />;
  return <Picker row={row} settings={settings} mark={mark} />;
}

function useSave(cli: string, settings: ModelSettingsState, mark: SavedProps) {
  const [problem, setProblem] = useState<string | null>(null);
  const save = async (pick: Pick | { typed: string }): Promise<boolean> => {
    setProblem(null);
    mark.onSaving();
    try {
      if (pick === null) await settings.reload(await clearModelDefault(cli));
      else await settings.reload((await setModelDefault(cli, pick)).settings);
      mark.onSaved();
      return true;
    } catch (error) {
      setProblem(
        unreachable(error) ? "LADO's server does not answer: the value was not saved." : refusalOf(error).message,
      );
      return false;
    }
  };
  return { problem, save };
}

// No `✓ Saved` here: the line goes with the default, and that is the answer.
function NotInstalled({
  row,
  name,
  settings,
  mark,
}: {
  row: ProviderLogins;
  name: string;
  settings: ModelSettingsState;
  mark: SavedProps;
}) {
  const { problem, save } = useSave(row.cli.name, settings, { ...mark, onSaved: () => undefined });
  const self = useRef<HTMLDivElement>(null);
  // The line goes with the default: the focus goes to the row's name (Providers.tsx).
  const clear = async () => {
    const rowName = self.current?.closest("li")?.querySelector<HTMLElement>(".pv-name");
    if (await save(null)) rowName?.focus({ preventScroll: true });
  };
  return (
    <div className="cli-model cli-off" ref={self}>
      <p className="srow-desc">{`Default model: ${name} — cannot run: not installed`}</p>
      <span className="way-out">
        <button type="button" className="chip-button" onClick={() => void clear()}>
          {`Use ${row.cli.title}'s settings`}
        </button>
      </span>
      {problem && (
        <span className="field-note bad" role="alert">
          {problem}
        </span>
      )}
    </div>
  );
}

function Picker({ row, settings, mark }: { row: ProviderLogins; settings: ModelSettingsState; mark: SavedProps }) {
  const id = useId();
  const entries = settings.entries!;
  const { name: cli, title } = row.cli;
  const value = entries.defaults.find((d) => d.cli === cli) ?? null;
  const live = entries.models.filter((m) => m.cli === cli);
  const list = useModelChoices(cli);
  const { read } = list;
  const field = useRef<HTMLButtonElement>(null);
  const { problem, save } = useSave(cli, settings, mark);
  const [other, setOther] = useState<string | null>(null); // Other name's field, with its text
  const [health, setHealth] = useState<Record<string, Health>>({});
  const [checking, setChecking] = useState(false);
  // What the human pressed goes away (a chip): the focus moves to the field once the row changed.
  const [handOn, setHandOn] = useState(false);
  const checkedList = useRef(false); // Check again of the list is running
  const probes = useRef<Record<string, number>>({}); // each server's latest question

  useEffect(() => {
    if (!handOn) return;
    setHandOn(false);
    field.current?.focus({ preventScroll: true });
  }, [handOn]);

  // A built-in default is read in the background, so a list that lost it shows in the row.
  const builtin = value?.builtin ?? null;
  useEffect(() => {
    if (builtin !== null) read(false, builtin);
  }, [builtin, read]);

  // The server's state as a probe found it; null when the probe never reached LADO, which says
  // nothing of the model server.
  const probe = async (server: string): Promise<Health | null> => {
    const key = fold(server);
    const asked = (probes.current[key] = (probes.current[key] ?? 0) + 1);
    let found: Health;
    try {
      found = { models: (await probeModelServer(server)).models };
    } catch (error) {
      if (unreachable(error)) return null;
      found = { down: refusalOf(error).message };
    }
    if (probes.current[key] === asked) setHealth((now) => ({ ...now, [key]: found }));
    return found;
  };

  const useSettings = async () => {
    if (await save(null)) setHandOn(true);
  };
  const useSettingsChip = (
    <button type="button" className="chip-button" onClick={() => void useSettings()}>
      {`Use ${title}'s settings`}
    </button>
  );

  const check = builtin !== null && list.checked === builtin ? list.choices?.check : undefined;
  const lost = check?.kind === "refused";
  useEffect(() => {
    if (!checkedList.current || list.reading) return;
    checkedList.current = false;
    if (check?.kind !== "warn") setHandOn(true); // its chip went
  }, [list.reading, check?.kind]);
  const server = value?.server ?? null;
  const state = server !== null ? health[fold(server)] : undefined;
  const words = value !== null ? serverWords(state, value.model) : null;
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
  const askServer = async () => {
    if (server === null || value === null) return;
    setChecking(true);
    const found = await probe(server);
    setChecking(false);
    if (found !== null && serverWords(found, value.model) === null) setHandOn(true); // its chip went
  };
  const askList = () => {
    checkedList.current = true;
    read(true, builtin ?? "");
  };
  const address = entries.servers.find((s) => fold(s.name) === fold(server ?? ""))?.address ?? "";

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
    check?.kind === "warn" && other === null && (
      <span key="warn" className="field-note warn" role="status">
        <span>{`⚠ ${check.text}`}</span>
        {list.choices?.read_again && <span className="way-out">{checkAgain(askList, list.reading)}</span>}
      </span>
    ),
    words !== null && value !== null && server !== null && state !== undefined && (
      <span key="server" className="field-note warn" role="status">
        <span>
          {"down" in state
            ? `⚠ ${state.down.replace(address, server)}. Start it or pick another model.`
            : `⚠ ${value.model} is no longer in ${server}'s list of models. Load it there or pick another model.`}
        </span>
        <span className="way-out">
          {checkAgain(() => void askServer(), checking)}
          {useSettingsChip}
        </span>
      </span>
    ),
    checking && server !== null && (
      <span key="checking" className="field-note" role="status">
        <span className="mx-spin" aria-hidden="true" /> {`checking ${server} …`}
      </span>
    ),
  ].filter(Boolean);

  return (
    <div className="cli-model">
      <span className="cli-ml" aria-hidden="true">
        Default model
      </span>
      <div className="cli-pick">
        <ModelPicker
          cli={{ name: cli, title }}
          value={value}
          where="settings"
          own={live}
          list={list}
          off={false}
          lost={lost}
          health={health}
          describedBy={notes.length > 0 ? `${id}-notes` : undefined}
          fieldRef={field}
          onOpen={() => {
            for (const name of new Set(live.map((m) => m.server))) void probe(name);
          }}
          onPick={(pick) => {
            setOther(null);
            void save(pick);
          }}
          onOther={setOther}
        />
        {other !== null && (
          <OtherName
            cli={cli}
            start={other}
            onUse={async (name) => {
              if (await save({ typed: name })) {
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
      {/* Always there, so filling it moves nothing and a screen reader hears `Saved` once. */}
      <span className="cli-saved" role="status">
        {mark.saved === cli && (
          <>
            <span aria-hidden="true">✓</span> Saved
          </>
        )}
      </span>
    </div>
  );
}

// `Other name…`'s field: the check `lado model default` would make once the typing settles,
// and Use, off while refused; the warning of a name set so then stands in the row.
export function OtherName({
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
    checkModelDefault(cli, settled).then(
      (note) => current && setCheck({ of: settled, note }),
      () => undefined, // Use says what is wrong
    );
    return () => {
      current = false;
    };
  }, [cli, settled]);
  const note = check?.of === name ? check.note : null;
  const shown = note !== null && note.kind !== "default";
  const refused = note?.kind === "refused";
  const use = () => {
    if (name && !refused) void onUse(name);
  };
  // No <form>: the launch window's own form holds it there.
  return (
    <div className="mc-other">
      <label className="mc-other-l" htmlFor={id}>
        Other name
      </label>
      <div className="mc-other-row">
        <input
          id={id}
          className="mono"
          aria-describedby={shown ? `${id}-note` : undefined}
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
            } else if (event.key === "Enter") {
              event.preventDefault();
              use();
            }
          }}
        />
        <button type="button" className="quiet" disabled={!name || refused} onClick={use}>
          Use
        </button>
        <button type="button" className="quiet" onClick={onCancel}>
          Cancel
        </button>
      </div>
      {shown && (
        <span
          id={`${id}-note`}
          className={`field-note${refused ? " bad" : note.kind === "warn" ? " warn" : ""}`}
          role={refused ? "alert" : "status"}
        >
          {note.kind === "warn" ? `⚠ ${note.text}` : note.text}
        </span>
      )}
    </div>
  );
}
