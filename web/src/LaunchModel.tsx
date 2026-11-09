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
import { OtherName } from "./CliDefault";
import { useAsked } from "./Launch";
import { type Health, ModelPicker, type Pick, sameModel, useModelChoices } from "./ModelPicker";

export type Choice =
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

const INSTALL_FILE = "docs/install.md";
const INSTALL_DOCS = `https://github.com/ladohq/lado/blob/main/${INSTALL_FILE}`;
const SECTION = /see "([^"]+)" in $/; // what stands before the file's name

// A warning's text, one string for `lado start` and this window: here its file is a link to the
// section it names, as a wheel holds no such file.
function warningText(warning: string): ReactNode {
  const at = warning.indexOf(INSTALL_FILE);
  if (at < 0) return `⚠ ${warning}`;
  const section = SECTION.exec(warning.slice(0, at))?.[1];
  const anchor = section ? `#${section.toLowerCase().replaceAll(" ", "-")}` : "";
  return (
    <>
      {`⚠ ${warning.slice(0, at)}`}
      <a href={INSTALL_DOCS + anchor} target="_blank" rel="noreferrer">
        {`${INSTALL_FILE} ↗`}
      </a>
      {warning.slice(at + INSTALL_FILE.length)}
    </>
  );
}

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
  onLogin,
  draft = null,
}: {
  // the choice the window's draft kept, for its agent CLI: taken only with that CLI
  draft?: { cli: string; choice: Choice } | null;
  // `starts_on_server` with `login_missing`: its agents start on a saved model of a server only
  cli: { name: string; title: string; login_missing?: boolean; starts_on_server?: boolean } | null;
  project: string | null; // null: not known yet, so nothing is checked
  resuming: SessionInfo | null;
  busy: boolean;
  refusal: ModelRefusal | null; // the last start's, for the value in the field
  onClearRefusal: () => void;
  onShow: () => void; // open Advanced
  onLogin: () => void; // to the CLI's login, leaving the window
}) {
  const id = useId();
  const field = useRef<HTMLButtonElement>(null);
  const [entries, setEntries] = useState<ModelSettings | null>(null);
  const [choice, setChoice] = useState<Choice>(() => draft?.choice ?? cameWith(resuming));
  const [lostNote, setLostNote] = useState<string | null>(null);
  const [other, setOther] = useState<string | null>(null); // Other name's field, with its text
  const [tries, setTries] = useState(0); // Check again asks anew
  const [again, setAgain] = useState<ModelRefusal | SessionModelCheck | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const name = cli?.name ?? "";
  const list = useModelChoices(name);
  const listNow = useRef(list);
  listNow.current = list;

  // Read at the window's focus too: Settings opens in a new tab, and this window stays as it is;
  // a list already read, whose rows may be open, goes with it (the CLI's part kept a minute).
  useEffect(() => {
    let current = true;
    const read = () => {
      getModelSettings().then(
        (found) => current && setEntries(found),
        () => undefined, // no defaults known: the core still decides at the start
      );
    };
    const again = () => {
      read();
      if (listNow.current.choices !== null) listNow.current.read(false, "");
    };
    read();
    window.addEventListener("focus", again);
    return () => {
      current = false;
      window.removeEventListener("focus", again);
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

  // Without its login the CLI starts on a saved model of a server only (runtime.check_login): a
  // new session opening on a value that needs the login takes its one saved model, once, and
  // never after the human moved the field; with several the human picks.
  const serverOnly = cli?.login_missing === true && cli.starts_on_server === true;
  const [moved, setMoved] = useState(false);
  const [tookOne, setTookOne] = useState(false); // the field took the one model by itself
  const picksOne =
    serverOnly &&
    entries !== null &&
    resuming === null &&
    draft?.cli !== name &&
    !moved &&
    choice.kind === "default" &&
    (defaultValue === null || defaultValue.external === null) &&
    own.length === 1;
  useEffect(() => {
    if (!picksOne) return;
    setChoice({ kind: "pick", value: asValue(own[0].name) });
    setTookOne(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- when it comes to that
  }, [picksOne]);
  // The CLI's settings need the login: refused here, as the start would refuse them.
  const loginRefusal: SessionModelCheck | null =
    serverOnly && entries !== null && value === null && !picksOne
      ? {
          kind: "refused",
          text: `${cli.title} is not logged in, so it runs on your server's models only: pick one.`,
          field: "",
          name: "",
          retry: false,
          short: `${cli.title} is not logged in`,
          peek: "needs login",
          warnings: [],
          server: null,
          login: true,
        }
      : null;
  // A refusal for the missing login is left by a server's model: the default when it is on a
  // server, else the first saved one.
  const serverValue =
    defaultValue !== null && defaultValue.external !== null ? defaultValue : own[0] ? asValue(own[0].name) : null;

  // A model is its CLI's: another agent CLI takes the field to that CLI's default, or back to
  // what a resumed session has. No CLI says nothing of that: the agent CLIs are being read again
  // (another project), and the same one comes back.
  const shownCli = useRef(cli);
  useEffect(() => {
    if (cli === null) return;
    const before = shownCli.current;
    shownCli.current = cli;
    // The first CLI known: a draft's choice holds only for the CLI it was made for.
    if (before === null && draft && draft.cli !== cli.name) setChoice(cameWith(resuming));
    if (before === null || before.name === cli.name) return;
    const lost = value !== null && choice.kind !== "default";
    setLostNote(
      lost ? `${nameOf(value)} belongs to ${before.title}, so the model is back to ${cli.title}'s default.` : null,
    );
    setChoice(cli.name === resuming?.provider ? cameWith(resuming) : { kind: "default" });
    setMoved(false);
    setTookOne(false);
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

  // The refusal Check again asks about stands, with Start off, until the new answer comes.
  const asking = again !== null && asked !== null && answer === null;
  const refusedCheck = checked?.kind === "refused" ? checked : null;
  const refused = refusal ?? loginRefusal ?? refusedCheck ?? (asking ? again : null);
  const byLogin = refused !== null && "login" in refused && refused.login;
  const wrong = refused !== null || missing;

  useEffect(() => {
    if (again === null || answer === null) return;
    setAgain(null);
    if (checked?.kind !== "refused") field.current?.focus({ preventScroll: true }); // its button went
  }, [again, answer, checked?.kind]);

  // Why Start is off comes into sight, on a phone's short window too.
  useEffect(() => {
    if (!wrong) return;
    onShow();
    box.current?.scrollIntoView?.({ block: "center" });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- when a refusal comes
  }, [wrong]);
  useEffect(() => {
    if (refusal === null || busy) return;
    field.current?.focus({ preventScroll: true });
    box.current?.scrollIntoView?.({ block: "center" });
  }, [refusal, busy]);

  const changed = (next: Choice) => {
    setChoice(next);
    setMoved(true);
    setTookOne(false);
    setLostNote(null);
    setOther(null);
    setAgain(null);
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
  const useServer = (next: CliDefault) => {
    changed(sameModel(next, defaultValue) && !resuming ? { kind: "default" } : { kind: "pick", value: next });
    field.current?.focus({ preventScroll: true });
  };
  const checkAgain = () => {
    if (asking) return;
    setAgain(refused);
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
        <span>{`The session ran on the model ${resuming?.model}, which is no longer in Settings → Model servers. Pick a model or use ${title}'s settings.`}</span>
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
        <span>
          {kept
            ? `${refused.text.replace(/\.$/, "")}. The session ran on it before. Pick another model, or resume on ${title}'s settings.`
            : refused.text}
        </span>
        <span className="way-out">
          {refused.retry && (
            <button
              type="button"
              className="chip-button"
              aria-disabled={asking ? true : undefined}
              onClick={checkAgain}
            >
              {asking ? "Checking…" : "Check again"}
            </button>
          )}
          {byLogin ? (
            <>
              {serverValue !== null && (
                <button type="button" className="chip-button" onClick={() => useServer(serverValue)}>
                  {`Use ${nameOf(serverValue)}`}
                </button>
              )}
              <button type="button" className="chip-button" onClick={onLogin}>
                Log in first
              </button>
            </>
          ) : (
            <button type="button" className="chip-button" onClick={useSettings}>
              {`Use ${title}'s settings`}
            </button>
          )}
        </span>
      </span>,
    );
  } else {
    if (lostNote === null && choice.kind === "pick" && tookOne) {
      notes.push(
        <span key="note" className="field-note">
          {`For this session only: ${title} is not logged in, so it runs on your server's model.`}
        </span>,
      );
    } else if (lostNote === null && choice.kind === "default" && defaultValue !== null) {
      notes.push(
        <span key="note" className="field-note">
          {`${title}'s default model, from Settings → Agent CLIs.`}
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
          {warningText(warning)}
        </span>,
      );
    }
  }

  const server = value?.server ?? null;
  const down = refused?.peek === "not answering" && server !== null;
  const health: Record<string, Health> = down ? { [server.toLowerCase()]: { down: refused.text } } : {};
  const notesId = `${id}-notes`;

  const fieldNode = (
    <div className="field launch-wide" ref={box}>
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
        needsLogin={serverOnly}
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

  // The mark is why Start may be off: only the name and the server give way on a narrow window.
  const pastDefault = choice.kind === "settings" && defaultValue !== null;
  // Team's summary names the model only off the CLI's default, or when its check warns.
  const told = choice.kind !== "default" || wrong || Boolean(checked?.peek);
  const named =
    !told ? null : value !== null ? nameOf(value) : pastDefault || wrong ? `${title}'s settings` : null;
  const peek =
    named === null ? null : (
      <span className="launch-first-line">
        <span className="launch-first-name">
          <span className="k">Model</span> <span className="launch-first-peek">{named}</span>
          {server !== null && ` on ${server}`}
        </span>
        {!wrong && checked?.peek && <span className="launch-first-mark">{` ⚠ ${checked.peek}`}</span>}
        {wrong && (
          <b className="launch-first-mark launch-first-bad">{` ! ${missing ? "not in Settings" : refused?.peek}`}</b>
        )}
      </span>
    );

  return {
    field: fieldNode,
    peek,
    blocked: wrong,
    send,
    focus: () => field.current?.focus(),
    kept: cli ? { cli: cli.name, choice } : null, // for the window's draft
  };
}
