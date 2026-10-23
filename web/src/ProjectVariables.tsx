// A project's variables and secrets (docs/design/ui.md, Projects): two blocks, each with its
// rows and its "+ Add". A plain variable is edited in place; a secret is replaced, never
// shown. Remove asks in the row. The core's refusals show verbatim under the row or the form,
// its fields kept.
//
// A secret's value lives only in its field (SecretField): an uncontrolled password field
// outside any form, read when the human sends it, sent in the body of one PUT, and emptied
// after a save, on Cancel and when the field goes. It is never put in React's state, an
// address, the browser's storage, the console or an error the page keeps.
import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode, type RefObject } from "react";

import {
  deleteSecret,
  deleteVariable,
  putSecret,
  putVariable,
  type ProjectInfo,
  type VariableChange,
} from "./api";
import { messageOf } from "./SessionControl";

type Props = { project: ProjectInfo; onChanged: (project: ProjectInfo) => void };

// What a row is doing: shown, edited (a variable) or replaced (a secret), or asking to remove.
type Active = { name: string; mode: "edit" | "remove" } | null;

// The core's refusal of a plain variable whose name looks like a secret's (projects.check_variable).
const LIKE_SECRET = "looks like a secret";

export function ProjectVariables({ project, onChanged }: Props) {
  // The secret's form, open, with the name a refused variable moved there.
  const [secretForm, setSecretForm] = useState<{ name: string } | null>(null);
  const [variableForm, setVariableForm] = useState(false);
  return (
    <>
      <Variables
        project={project}
        onChanged={onChanged}
        adding={variableForm}
        onAdding={setVariableForm}
        onSecretInstead={(name) => {
          setVariableForm(false);
          setSecretForm({ name });
        }}
      />
      <Secrets project={project} onChanged={onChanged} adding={secretForm} onAdding={setSecretForm} />
    </>
  );
}

// Sends a change and hands the project on; a refusal's text for the row or the form.
function useChange(onChanged: (project: ProjectInfo) => void) {
  const [busy, setBusy] = useState(false);
  const send = async (request: () => Promise<VariableChange>): Promise<string | null> => {
    setBusy(true);
    try {
      onChanged((await request()).project);
      return null;
    } catch (error) {
      return messageOf(error);
    } finally {
      setBusy(false);
    }
  };
  return { busy, send };
}

function Block({ title, about, children }: { title: string; about: string; children: ReactNode }) {
  const id = useId();
  return (
    <section className="project-section" aria-labelledby={id}>
      <h3 id={id}>{title}</h3>
      <p className="muted">{about}</p>
      {children}
    </section>
  );
}

// A name's cell: the name, and the mark of a name the outside folder gives too.
function NameCell({ name, overrides }: { name: string; overrides: boolean }) {
  return (
    <td className="project-name">
      <span>{name}</span>
      {overrides && (
        <span
          className="badge project-mark"
          title={`The outside folder (LADO_ENV_DIR) also gives ${name}. This project's sessions get the project's value; its outside value is not shown.`}
        >
          overrides outside value
        </span>
      )}
    </td>
  );
}

const Refusal = ({ text }: { text: string | null }) => (text === null ? null : <span className="field-note bad">{text}</span>);

// The row asking to remove `name`: only its second Remove sends the DELETE.
function RemoveRow({
  name,
  overrides,
  busy,
  refused,
  onRemove,
  onCancel,
}: {
  name: string;
  overrides: boolean;
  busy: boolean;
  refused: string | null;
  onRemove: () => void;
  onCancel: () => void;
}) {
  return (
    <tr>
      <NameCell name={name} overrides={overrides} />
      <td colSpan={2}>
        <div className="project-edit">
          <span className="project-ask">{`Remove ${name}?`}</span>
          <button type="button" className="danger" disabled={busy} onClick={onRemove}>
            Remove
          </button>
          <button type="button" className="quiet" disabled={busy} onClick={onCancel}>
            Cancel
          </button>
          <Refusal text={refused} />
        </div>
      </td>
    </tr>
  );
}

function Variables({
  project,
  onChanged,
  adding,
  onAdding,
  onSecretInstead,
}: Props & { adding: boolean; onAdding: (open: boolean) => void; onSecretInstead: (name: string) => void }) {
  const { busy, send } = useChange(onChanged);
  const [active, setActive] = useState<Active>(null);
  const [value, setValue] = useState("");
  const [refused, setRefused] = useState<string | null>(null);
  const open = (next: Active, start = "") => {
    setActive(next);
    setValue(start);
    setRefused(null);
  };
  const done = (text: string | null) => (text === null ? open(null) : setRefused(text));

  return (
    <Block title="Variables" about="Every agent of this project's sessions gets them, over LADO's own environment.">
      {project.variables.length > 0 && (
        <table className="project-vars">
          <thead>
            <tr>
              <th>Name</th>
              <th>Value</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {project.variables.map(({ name, value: shown }) => {
              const overrides = project.overrides.includes(name);
              if (active?.name === name && active.mode === "remove") {
                return (
                  <RemoveRow
                    key={name}
                    name={name}
                    overrides={overrides}
                    busy={busy}
                    refused={refused}
                    onRemove={async () => done(await send(() => deleteVariable(project.id, name)))}
                    onCancel={() => open(null)}
                  />
                );
              }
              if (active?.name === name) {
                const save = async () => done(await send(() => putVariable(project.id, name, value)));
                return (
                  <tr key={name}>
                    <NameCell name={name} overrides={overrides} />
                    <td colSpan={2}>
                      <div className="project-edit">
                        <input
                          className="project-in-value"
                          aria-label={`Value of ${name}`}
                          value={value}
                          autoFocus
                          onChange={(event) => setValue(event.target.value)}
                          onKeyDown={(event) => event.key === "Enter" && save()}
                        />
                        <button type="button" className="primary" disabled={busy} onClick={save}>
                          Save
                        </button>
                        <button type="button" className="quiet" disabled={busy} onClick={() => open(null)}>
                          Cancel
                        </button>
                        <Refusal text={refused} />
                      </div>
                    </td>
                  </tr>
                );
              }
              return (
                <tr key={name}>
                  <NameCell name={name} overrides={overrides} />
                  <td className="project-value">{shown}</td>
                  <td className="project-acts">
                    <button type="button" className="quiet" onClick={() => open({ name, mode: "edit" }, shown)}>
                      Edit
                    </button>
                    <button type="button" className="quiet" onClick={() => open({ name, mode: "remove" })}>
                      Remove
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {adding ? (
        <NewVariable project={project} busy={busy} send={send} onClose={() => onAdding(false)} onSecretInstead={onSecretInstead} />
      ) : (
        <div className="project-add">
          <button type="button" className="quiet" onClick={() => onAdding(true)}>
            + Add variable
          </button>
        </div>
      )}
    </Block>
  );
}

function NewVariable({
  project,
  busy,
  send,
  onClose,
  onSecretInstead,
}: {
  project: ProjectInfo;
  busy: boolean;
  send: (request: () => Promise<VariableChange>) => Promise<string | null>;
  onClose: () => void;
  onSecretInstead: (name: string) => void;
}) {
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  // The refusal, with the name it was for.
  const [refused, setRefused] = useState<{ text: string; name: string } | null>(null);
  const add = async () => {
    const text = await send(() => putVariable(project.id, name, value));
    if (text === null) onClose();
    else setRefused({ text, name });
  };
  const enter = (event: KeyboardEvent) => event.key === "Enter" && add();
  return (
    <div className="project-add project-edit">
      <input
        className="project-in-name"
        aria-label="Name"
        placeholder="NAME"
        value={name}
        autoFocus
        spellCheck={false}
        autoCapitalize="off"
        onChange={(event) => setName(event.target.value)}
        onKeyDown={enter}
      />
      <input
        className="project-in-value"
        aria-label="Value"
        placeholder="value"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={enter}
      />
      <button type="button" className="primary" disabled={busy} onClick={add}>
        Add
      </button>
      <button type="button" className="quiet" disabled={busy} onClick={onClose}>
        Cancel
      </button>
      <Refusal text={refused?.text ?? null} />
      {refused?.text.includes(LIKE_SECRET) && (
        <span>
          <button type="button" className="link-button" onClick={() => onSecretInstead(refused.name)}>
            {`Add ${refused.name} as a secret instead`}
          </button>
        </span>
      )}
    </div>
  );
}

// The one field a secret's value is typed in. `filled` says whether it holds text (Replace
// needs some), never what.
function SecretField({
  field,
  label,
  placeholder,
  onFilled,
  onEnter,
}: {
  field: RefObject<HTMLInputElement | null>;
  label: string;
  placeholder: string;
  onFilled?: (filled: boolean) => void;
  onEnter: () => void;
}) {
  useEffect(() => {
    const node = field.current;
    return () => {
      if (node) node.value = ""; // the page or the form goes: nothing stays in the field
    };
  }, [field]);
  return (
    <input
      ref={field}
      type="password"
      className="project-in-value"
      aria-label={label}
      placeholder={placeholder}
      autoComplete="off"
      data-1p-ignore=""
      data-lpignore="true"
      spellCheck={false}
      onChange={(event) => onFilled?.(event.target.value !== "")}
      onKeyDown={(event) => event.key === "Enter" && onEnter()}
    />
  );
}

// Sends the value the field holds now and empties the field when the core takes it.
async function sendSecret(
  field: RefObject<HTMLInputElement | null>,
  send: (request: () => Promise<VariableChange>) => Promise<string | null>,
  id: string,
  name: string,
): Promise<string | null> {
  const refused = await send(() => putSecret(id, name, field.current?.value ?? ""));
  if (refused === null && field.current) field.current.value = "";
  return refused;
}

function Secrets({
  project,
  onChanged,
  adding,
  onAdding,
}: Props & { adding: { name: string } | null; onAdding: (form: { name: string } | null) => void }) {
  const { busy, send } = useChange(onChanged);
  const [active, setActive] = useState<Active>(null);
  const [refused, setRefused] = useState<string | null>(null);
  const [filled, setFilled] = useState(false);
  const field = useRef<HTMLInputElement>(null);
  const open = (next: Active) => {
    if (field.current) field.current.value = "";
    setActive(next);
    setFilled(false);
    setRefused(null);
  };
  const done = (text: string | null) => (text === null ? open(null) : setRefused(text));
  const unused = new Map(project.unused.map((one) => [one.name, one.reason]));
  // What the folder holds that is no secret's row: a link, a bad name, or the folder itself.
  const others = project.unused.filter((one) => one.name === null || !project.secrets.includes(one.name));

  return (
    <Block title="Secrets" about="Keys and tokens: a value is set or replaced, never shown again.">
      {project.secrets.length > 0 && (
        <table className="project-vars">
          <thead>
            <tr>
              <th>Name</th>
              <th>Value</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {project.secrets.map((name) => {
              const overrides = project.overrides.includes(name);
              if (active?.name === name && active.mode === "remove") {
                return (
                  <RemoveRow
                    key={name}
                    name={name}
                    overrides={overrides}
                    busy={busy}
                    refused={refused}
                    onRemove={async () => done(await send(() => deleteSecret(project.id, name)))}
                    onCancel={() => open(null)}
                  />
                );
              }
              if (active?.name === name) {
                const replace = async () => {
                  if (field.current?.value) done(await sendSecret(field, send, project.id, name));
                };
                return (
                  <tr key={name}>
                    <NameCell name={name} overrides={overrides} />
                    <td colSpan={2}>
                      <div className="project-edit">
                        <SecretField
                          field={field}
                          label={`New value of ${name}`}
                          placeholder="New value (the old one is not shown)"
                          onFilled={setFilled}
                          onEnter={replace}
                        />
                        <button type="button" className="primary" disabled={busy || !filled} onClick={replace}>
                          Replace
                        </button>
                        <button type="button" className="quiet" disabled={busy} onClick={() => open(null)}>
                          Cancel
                        </button>
                        <Refusal text={refused} />
                      </div>
                    </td>
                  </tr>
                );
              }
              const reason = unused.get(name);
              return (
                <tr key={name}>
                  <NameCell name={name} overrides={overrides} />
                  <td>
                    {reason === undefined ? (
                      <span className="project-hidden">set · hidden</span>
                    ) : (
                      <span className="field-note warn">{`⚠ Agents do not get it: ${reason}`}</span>
                    )}
                  </td>
                  <td className="project-acts">
                    <button type="button" className="quiet" onClick={() => open({ name, mode: "edit" })}>
                      Replace
                    </button>
                    <button type="button" className="quiet" onClick={() => open({ name, mode: "remove" })}>
                      Remove
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {others.length > 0 && (
        <div className="project-notes">
          {others.map(({ name, reason }) => (
            <span key={name ?? ""} className="field-note warn">
              {name === null
                ? `⚠ The secrets folder is not used: ${reason}`
                : `⚠ ${name}: agents do not get it: ${reason}`}
            </span>
          ))}
        </div>
      )}
      {adding ? (
        <NewSecret key={adding.name} project={project} start={adding.name} busy={busy} send={send} onClose={() => onAdding(null)} />
      ) : (
        <div className="project-add">
          <button type="button" className="quiet" onClick={() => onAdding({ name: "" })}>
            + Add secret
          </button>
        </div>
      )}
    </Block>
  );
}

function NewSecret({
  project,
  start,
  busy,
  send,
  onClose,
}: {
  project: ProjectInfo;
  start: string;
  busy: boolean;
  send: (request: () => Promise<VariableChange>) => Promise<string | null>;
  onClose: () => void;
}) {
  const [name, setName] = useState(start);
  const [refused, setRefused] = useState<string | null>(null);
  const field = useRef<HTMLInputElement>(null);
  const add = async () => {
    const text = await sendSecret(field, send, project.id, name);
    if (text === null) onClose();
    else setRefused(text);
  };
  const cancel = () => {
    if (field.current) field.current.value = "";
    onClose();
  };
  return (
    <div className="project-add project-edit">
      <input
        className="project-in-name"
        aria-label="Name"
        placeholder="NAME"
        value={name}
        autoFocus={start === ""}
        spellCheck={false}
        autoCapitalize="off"
        onChange={(event) => setName(event.target.value)}
      />
      <SecretField field={field} label="Value" placeholder="value (not shown after saving)" onEnter={add} />
      <button type="button" className="primary" disabled={busy} onClick={add}>
        Add
      </button>
      <button type="button" className="quiet" disabled={busy} onClick={cancel}>
        Cancel
      </button>
      <Refusal text={refused} />
    </div>
  );
}
