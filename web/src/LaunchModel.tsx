// The launch window's Model field (docs/design/ui.md, Launch and session control): the one
// picker for the chosen agent CLI, holding its default until the human picks. A session that
// keeps following its default sends no model, so the window sends only a choice the human made;
// what it shows comes from the core, by the check a start would make of the value in the field.
import { type ReactNode, useEffect, useId, useRef, useState } from "react";

import {
  checkSessionModel,
  type CliDefault,
  getModelSettings,
  type ModelRefusal,
  type ModelSettings,
  type SessionInfo,
  type SessionModelCheck,
} from "./api";
import { useAsked } from "./Launch";
import { type Health, ModelPicker, type Pick, useModelChoices } from "./ModelPicker";
import { OtherName } from "./ModelSettings";

type Choice =
  | { kind: "default" } // follows the CLI's default, as it is at each launch
  | { kind: "kept" } // the model a resumed session has
  | { kind: "settings"; chosen: boolean } // `chosen`: by a way out, whatever the session had
  | { kind: "pick"; value: CliDefault };

const builtin = (cli: string, model: string): CliDefault => ({
  cli,
  external: null,
  builtin: model,
  name: model,
  model,
  server: null,
  whole_process: false,
});

const nameOf = (value: CliDefault) => (value.external !== null ? value.name : value.model);

const sameModel = (a: CliDefault, b: CliDefault | null) =>
  b !== null && a.external === b.external && a.builtin === b.builtin;

// How a window opens: on the model a resumed session has, else its CLI's default.
function cameWith(resuming: SessionInfo | null): Choice {
  if (resuming?.model === "") return { kind: "settings", chosen: false };
  return resuming?.model ? { kind: "kept" } : { kind: "default" };
}

export function useLaunchModel({
  cli,
  project,
  resuming,
  busy,
  refusal,
  onClearRefusal,
  onShow,
}: {
  cli: { name: string; title: string } | null;
  project: string | null; // null: not known yet, so nothing is checked
  resuming: SessionInfo | null;
  busy: boolean;
  refusal: ModelRefusal | null; // the last start's, for the value in the field
  onClearRefusal: () => void;
  onShow: () => void; // open Advanced
}) {
  const id = useId();
  const field = useRef<HTMLButtonElement>(null);
  const [entries, setEntries] = useState<ModelSettings | null>(null);
  const [choice, setChoice] = useState<Choice>(() => cameWith(resuming));
  const [lostNote, setLostNote] = useState<string | null>(null);
  const [other, setOther] = useState<string | null>(null); // Other name's field, with its text
  const [tries, setTries] = useState(0); // Check again asks anew
  const name = cli?.name ?? "";
  const list = useModelChoices(name);

  // Read at the window's focus too: Settings opens in a new tab, and this window stays as it is.
  useEffect(() => {
    let current = true;
    const read = () => {
      getModelSettings().then(
        (found) => current && setEntries(found),
        () => undefined, // no defaults known: the core still decides at the start
      );
    };
    read();
    window.addEventListener("focus", read);
    return () => {
      current = false;
      window.removeEventListener("focus", read);
    };
  }, []);

  const own = (entries?.models ?? []).filter((one) => one.cli === name);
  const defaultValue = (entries?.defaults ?? []).find((one) => one.cli === name) ?? null;
  const asValue = (model: string): CliDefault => {
    const saved = own.find((one) => one.name === model);
    if (!saved) return builtin(name, model);
    return {
      cli: name,
      external: saved.id,
      builtin: null,
      name: saved.name,
      model: saved.model,
      server: saved.server,
      whole_process: false,
    };
  };
  const value =
    choice.kind === "default"
      ? defaultValue
      : choice.kind === "kept"
        ? asValue(resuming?.model ?? "")
        : choice.kind === "pick"
          ? choice.value
          : null;
  const missing = choice.kind === "kept" && resuming?.model_missing === true;

  // A model is its CLI's: another agent CLI takes the field to that CLI's default, or back to
  // what a resumed session has.
  const shownCli = useRef(cli);
  useEffect(() => {
    const before = shownCli.current;
    shownCli.current = cli;
    if (before?.name === cli?.name) return;
    if (before !== null && cli !== null && value !== null && choice.kind !== "default") {
      setLostNote(`${nameOf(value)} belongs to ${before.title}, so the model is back to ${cli.title}'s default.`);
    }
    setChoice(cli?.name === resuming?.provider ? cameWith(resuming) : { kind: "default" });
    setOther(null);
    onClearRefusal();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- when the agent CLI changes
  }, [cli?.name]);

  const asked = value !== null && !missing && cli !== null && project !== null ? nameOf(value) : null;
  const answer = useAsked<SessionModelCheck>(
    asked !== null ? JSON.stringify([name, asked, project, tries]) : null,
    (key) => {
      const [cliName, model, inProject] = JSON.parse(key) as [string, string, string];
      return checkSessionModel(cliName, model, inProject || null);
    },
  );
  const checked = asked !== null && answer !== null && "value" in answer ? answer.value : null;

  const refusedCheck = checked?.kind === "refused" ? checked : null;
  const refused = refusal ?? refusedCheck;
  const wrong = refused !== null || missing;

  useEffect(() => {
    if (wrong) onShow(); // why Start is off
    // eslint-disable-next-line react-hooks/exhaustive-deps -- when a refusal comes
  }, [wrong]);
  useEffect(() => {
    if (refusal !== null && !busy) field.current?.focus({ preventScroll: true });
  }, [refusal, busy]);

  const changed = (next: Choice) => {
    setChoice(next);
    setLostNote(null);
    setOther(null);
    onClearRefusal();
  };
  const picked = (pick: Pick) => {
    if (pick === null) return changed({ kind: "settings", chosen: false });
    const saved = "external" in pick ? own.find((one) => one.id === pick.external) : undefined;
    const next = saved ? asValue(saved.name) : builtin(name, "builtin" in pick ? pick.builtin : "");
    // The default itself keeps a new session following it; a resumed one is moved to it.
    changed(sameModel(next, defaultValue) && !resuming ? { kind: "default" } : { kind: "pick", value: next });
  };
  const useSettings = () => {
    changed({ kind: "settings", chosen: true });
    field.current?.focus({ preventScroll: true });
  };
  const checkAgain = () => {
    onClearRefusal();
    setTries((now) => now + 1);
  };

  // What the start sends: nothing for a value left as it came, "" for the CLI's own settings
  // when something else would otherwise hold.
  let send: string | undefined;
  if (choice.kind === "pick") send = nameOf(choice.value);
  else if (choice.kind === "settings") {
    const passing = defaultValue !== null || Boolean(resuming?.model);
    send = choice.chosen || (resuming?.model !== "" && passing) ? "" : undefined;
  }

  const title = cli?.title ?? "the agent CLI";
  const kept = choice.kind === "kept" && resuming !== null;
  const notes: ReactNode[] = [];
  if (lostNote !== null) {
    notes.push(
      <span key="lost" className="field-note">
        {lostNote}
      </span>,
    );
  }
  if (missing) {
    notes.push(
      <span key="gone" className="field-note bad" role="alert">
        <span>{`The session ran on the model ${resuming?.model}, which is no longer in Settings → Models. Pick a model or use ${title}'s settings.`}</span>
        <span className="way-out">
          <button type="button" className="chip-button" onClick={useSettings}>
            {`Use ${title}'s settings`}
          </button>
        </span>
      </span>,
    );
  } else if (refused !== null) {
    notes.push(
      <span key="refused" className="field-note bad" role="alert">
        <span>{refused.text}</span>
        {kept && <span>{`The session ran on it before. Pick another model, or resume on ${title}'s settings.`}</span>}
        <span className="way-out">
          {refused.retry && (
            <button type="button" className="chip-button" onClick={checkAgain}>
              Check again
            </button>
          )}
          <button type="button" className="chip-button" onClick={useSettings}>
            {`Use ${title}'s settings`}
          </button>
        </span>
      </span>,
    );
  } else {
    if (lostNote === null && choice.kind === "default" && defaultValue !== null) {
      notes.push(
        <span key="note" className="field-note">
          {`${title}'s default model, from Settings → Models.`}
        </span>,
      );
    } else if (lostNote === null && choice.kind === "pick" && defaultValue !== null) {
      notes.push(
        <span key="note" className="field-note">
          {`For this session only. ${title}'s default model is ${defaultValue.name}.`}
        </span>,
      );
    } else if (lostNote === null && choice.kind === "settings" && defaultValue !== null) {
      notes.push(
        <span key="note" className="field-note">
          {`For this session only: the agent CLI chooses, not ${defaultValue.name}.`}
        </span>,
      );
    }
    if (answer !== null && "error" in answer) {
      notes.push(
        <span key="error" className="field-note warn" role="status">
          {`⚠ ${answer.error}`}
        </span>,
      );
    }
    if (checked?.kind === "warn") {
      notes.push(
        <span key="warn" className="field-note warn" role="status">
          {`⚠ ${checked.text}`}
        </span>,
      );
    }
    if (checked?.kind === "ok" && checked.warnings.length > 0) {
      notes.push(
        <span key="ok" className="field-note ok">
          {`✓ ${checked.text}`}
        </span>,
      );
    }
    for (const warning of checked?.warnings ?? []) {
      notes.push(
        <span key={warning} className="field-note warn" role="status">
          {`⚠ ${warning}`}
        </span>,
      );
    }
  }

  const server = value?.server ?? null;
  const down = refused?.peek === "not answering" && server !== null;
  const health: Record<string, Health> = down ? { [server.toLowerCase()]: { down: refused.text } } : {};
  const notesId = `${id}-notes`;

  const fieldNode = (
    <div className="field launch-wide">
      <label htmlFor={id}>Model</label>
      <ModelPicker
        cli={cli ?? { name: "", title }}
        value={value}
        where="launch"
        own={own}
        list={list}
        off={busy || cli === null}
        lost={false}
        health={health}
        fieldId={id}
        invalid={wrong}
        fieldMark={missing ? "not in Settings" : null}
        defaultModel={defaultValue}
        describedBy={notes.length > 0 ? notesId : undefined}
        fieldRef={field}
        onOpen={() => undefined}
        onPick={picked}
        onOther={setOther}
      />
      {other !== null && (
        <OtherName
          cli={name}
          start={other}
          onUse={async (typed) => changed({ kind: "pick", value: asValue(typed) })}
          onCancel={() => setOther(null)}
        />
      )}
      {notes.length > 0 && (
        <div id={notesId} className="field-notes">
          {notes}
        </div>
      )}
    </div>
  );

  const peek =
    value === null ? null : (
      <>
        Advanced: model <span className="launch-first-peek">{nameOf(value)}</span>
        {server !== null && ` on ${server}`}
        {!wrong && (checked?.warnings.length ?? 0) > 0 && " ⚠ key over http"}
        {wrong && <b className="launch-first-bad">{` ! ${missing ? "not in Settings" : refused?.peek}`}</b>}
      </>
    );

  return { field: fieldNode, peek, blocked: wrong, send };
}
