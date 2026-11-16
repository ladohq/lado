// Settings → Git servers (docs/design/ui.md, Git servers): the human's GitLab and GitHub
// Enterprise servers, as `lado git-server` keeps them, on Model servers' rows and form. The
// list is read when the page opens and after each change of its own (GET /api/git-servers asks
// no server). A row has nothing to open: its address, its kind, the login it signs in as, and
// 🗑, which asks first. + Add server opens a form under the list, with gitlab.com filled in while
// it is not saved; once the address's typing settles the server is asked with no token, and the
// kind it looks like is only a hint for Token's link; the kind is chosen by hand only for a
// server that cannot be told. Add server saves as `lado git-server add` does, with the token in
// its request's body only; a refusal shows under its field. Nothing under the pointer moves
// (useScrollAnchor).
import { useCallback, useEffect, useId, useRef, useState } from "react";

import {
  addGitServer,
  checkGitServer,
  type EntryRefused,
  type GitKindInfo,
  type GitServerAdded,
  type GitServerCheck,
  type GitServerInfo,
  type GitServers,
  getGitServers,
  refusalOf,
  removeGitServer,
} from "./api";
import { ForgetIcon } from "./icons";
import { MODEL_DEBOUNCE, useDebounced } from "./Launch";
import { CheckNote, emptyKey } from "./ModelSources";
import { SecretField } from "./ProjectVariables";
import { SettingsPage } from "./SettingsPage";
import { useScrollAnchor } from "./useScrollAnchor";

export const GIT_LEAD =
  "Your GitLab or GitHub Enterprise: agents clone and push there with its token. github.com uses gh's login. Running agents get a change after a restart.";
export const GITLAB_COM = "https://gitlab.com";
const RESTART = "Agents started from now on reach it; restart running agents to give it to them.";
const TOKEN_NOTE = "Only LADO reads it; never shown again.";

// What the row says under the address: the login, or why it cannot be trusted as it is.
function secondLine(server: GitServerInfo): { text: string; warn: boolean } {
  if (!server.has_token) return { text: "⚠ its token file is missing: add it again", warn: true };
  if (server.login === null) return { text: "⚠ not checked: saved without a check", warn: true };
  return { text: `signed in as ${server.login}`, warn: false };
}

export function GitServersPage() {
  const id = useId();
  const [entries, setEntries] = useState<GitServers | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const latest = useRef(0);
  const section = useRef<HTMLElement>(null);
  useScrollAnchor(section);
  // Takes `given` (a change's answer), else reads the list; the latest call's answer wins.
  const reload = useCallback(async (given?: GitServers) => {
    const asked = ++latest.current;
    try {
      const found = given ?? (await getGitServers());
      if (asked !== latest.current) return;
      if (!Array.isArray(found?.servers) || !Array.isArray(found?.kinds))
        throw new Error("the server gave no git servers: reload the page");
      setEntries(found);
      setProblem(null);
    } catch (error) {
      if (asked === latest.current) setProblem(refusalOf(error).message);
    }
  }, []);
  useEffect(() => {
    void reload();
    return () => {
      latest.current++; // no answer counts once the page left
    };
  }, [reload]);
  // The servers by host at the first read, then each one added here at the end, where its form
  // was; a server removed here leaves its line in its place.
  const order = useRef<string[] | null>(null);
  if (entries && order.current === null) order.current = entries.servers.map((s) => s.host);
  for (const server of entries?.servers ?? [])
    if (order.current && !order.current.includes(server.host)) order.current.push(server.host);
  const [gone, setGone] = useState<Record<string, string>>({});
  const [adding, setAdding] = useState(false);
  const [saved, setSaved] = useState<{ host: string; done: GitServerAdded } | null>(null);
  const [fresh, setFresh] = useState<string | null>(null); // the server just added: the focus
  const [removing, setRemoving] = useState<string | null>(null);
  const addButton = useRef<HTMLButtonElement>(null);
  const [removedOne, setRemovedOne] = useState(false); // a server went: the focus goes to Add
  useEffect(() => {
    if (!removedOne) return;
    setRemovedOne(false);
    addButton.current?.focus();
  }, [removedOne]);
  // The human's next change on the page: the lines of the last server saved go.
  const touch = () => setSaved(null);
  const servers = entries?.servers ?? [];
  return (
    <SettingsPage slug="git-servers" className="setting mx" ref={section}>
      {problem && (
        <p className="problem" role="alert">
          {problem}
        </p>
      )}
      {entries && (
        <section className="mx-block" aria-labelledby={id}>
          <h3 id={id}>Servers {servers.length > 0 && <span className="mx-count">{servers.length}</span>}</h3>
          <p className="mx-lead">{GIT_LEAD}</p>
          <ul className="mx-srcs">
            {(order.current ?? []).map((host) => {
              const server = servers.find((s) => s.host === host);
              const line = gone[host];
              if (!server && !line) return null;
              return (
                <li key={host} className="mx-src" data-anchor="">
                  {server ? (
                    <>
                      {saved?.host === host && <SavedLines done={saved.done} />}
                      <GitRow
                        server={server}
                        focus={fresh === host}
                        removing={removing === host}
                        onRemove={() => setRemoving((now) => (now === host ? null : host))}
                      />
                      {removing === host && (
                        <RemoveGitServer
                          server={server}
                          onTouch={touch}
                          onCancel={() => setRemoving(null)}
                          onChanged={reload}
                          onGone={(done) => {
                            setRemoving(null);
                            setGone((now) => ({ ...now, [host]: done }));
                            setRemovedOne(true);
                          }}
                        />
                      )}
                    </>
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
                <AddGitServer
                  initial={servers.some((s) => s.host === "gitlab.com") ? "" : GITLAB_COM}
                  kinds={entries.kinds}
                  onTouch={touch}
                  onCancel={() => setAdding(false)}
                  onAdded={(done) => {
                    setAdding(false);
                    setGone((now) => {
                      const next = { ...now };
                      delete next[done.server.host];
                      return next;
                    });
                    setSaved({ host: done.server.host, done });
                    setFresh(done.server.host);
                    void reload();
                  }}
                />
              ) : (
                <button
                  ref={addButton}
                  type="button"
                  className="quiet mx-add"
                  onClick={() => {
                    touch();
                    setAdding(true);
                  }}
                >
                  <span aria-hidden="true">+</span> Add server
                </button>
              )}
            </li>
          </ul>
        </section>
      )}
    </SettingsPage>
  );
}

function SavedLines({ done }: { done: GitServerAdded }) {
  return (
    <div className="mx-saved gx-saved">
      <p className="mx-saved-line" role="status">
        {done.line}
      </p>
      <p className="mx-note">{RESTART}</p>
      {done.warnings.map((line) => (
        <span key={line} className="field-note warn">{`⚠ ${line}`}</span>
      ))}
    </div>
  );
}

// A server's row: its address whole, its kind, its second line; 🗑 at the right.
function GitRow({
  server,
  focus,
  removing,
  onRemove,
}: {
  server: GitServerInfo;
  focus: boolean;
  removing: boolean;
  onRemove: () => void;
}) {
  const id = useId();
  const title = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (focus) title.current?.focus();
  }, [focus]);
  const second = secondLine(server);
  return (
    <div className="mx-head">
      <div ref={title} className="mx-src-title gx-title" tabIndex={-1} aria-describedby={id}>
        <span className="mx-l1">
          <span className="mx-src-name">{server.address}</span>
          <span className="badge">{server.kind_title}</span>
        </span>
        <span className={`mx-l2${second.warn ? " gx-warn" : ""}`} id={id}>
          {second.text}
        </span>
      </div>
      <span className="mx-acts">
        <button
          type="button"
          className="mx-icon mx-icon-danger"
          aria-pressed={removing}
          aria-label={`Remove ${server.address}`}
          title="Remove"
          onClick={onRemove}
        >
          <ForgetIcon />
        </button>
      </span>
    </div>
  );
}

// Add server: Address and Token, and Kind only for a server that cannot be told. An older
// check's answer is dropped.
function AddGitServer({
  initial,
  kinds,
  onTouch,
  onCancel,
  onAdded,
}: {
  initial: string;
  kinds: GitKindInfo[];
  onTouch: () => void;
  onCancel: () => void;
  onAdded: (done: GitServerAdded) => void;
}) {
  const id = useId();
  const [address, setAddress] = useState(initial);
  const [kind, setKind] = useState<string | null>(null);
  const [filled, setFilled] = useState(false);
  const [refused, setRefused] = useState<EntryRefused | null>(null); // Add's
  const [busy, setBusy] = useState(false);
  const field = useRef<HTMLInputElement>(null);
  const token = useRef<HTMLInputElement>(null);
  const settled = useDebounced(address, MODEL_DEBOUNCE);
  const asked = useRef(0);
  const [check, setCheck] = useState<{ for: string; found?: GitServerCheck } | null>(null);
  useEffect(() => {
    if (initial) field.current?.select(); // typing replaces it
  }, [initial]);
  useEffect(() => {
    const mine = ++asked.current;
    if (!settled.trim()) return setCheck(null);
    setCheck({ for: settled });
    checkGitServer(settled).then(
      (found) => mine === asked.current && setCheck({ for: settled, found }),
      (error: unknown) =>
        mine === asked.current &&
        setCheck({
          for: settled,
          found: {
            address: null,
            hint: null,
            token_page: null,
            scopes: null,
            choose_kind: false,
            unchecked: null,
            saved: false,
            refusals: [refusalOf(error)],
            warnings: [],
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
  const now = check && check.for === address ? check : null;
  const result = now?.found;
  const checking = !busy && address.trim() !== "" && (address !== settled || (now !== null && !result));
  const choose = !checking && result?.choose_kind === true;
  // Token's link: the hint's kind, or the one chosen.
  const chosen = choose ? kinds.find((k) => k.name === kind) : undefined;
  const page = !checking && result?.address ? (result.token_page ?? (chosen ? result.address + chosen.token_path : null)) : null;
  const scopes = result?.scopes ?? chosen?.scopes ?? "";
  const hinted = !checking && result?.hint ? kinds.find((k) => k.name === result.hint) : undefined;
  const of = (field: string) => (!checking && result ? result.refusals.filter((r) => r.field === field) : []);
  const ready =
    !busy &&
    !checking &&
    result !== undefined &&
    result.address !== null &&
    result.refusals.length === 0 &&
    filled &&
    refused?.field !== "token" &&
    (!choose || chosen !== undefined);
  // A refusal of Add under a field goes once that field is edited.
  const edited = (field: string) => setRefused((was) => (was?.field === field ? null : was));
  const add = async () => {
    if (!ready) return;
    onTouch();
    const given = token.current?.value ?? "";
    setBusy(true);
    setRefused(null);
    try {
      const done = await addGitServer(address, given, choose && chosen ? chosen.name : null);
      emptyKey(token, setFilled);
      onAdded(done);
    } catch (error) {
      const why = refusalOf(error);
      if (why.field !== "token") emptyKey(token, setFilled);
      setRefused(why);
      setBusy(false);
    }
  };
  const mine = (field: string) => (refused?.field === field ? [refused] : []);
  const addressBad = [...of("address"), ...mine("address")];
  return (
    <div className="mx-form">
      <div className="launch-grid">
        <div className="field launch-wide">
          <label htmlFor={`${id}-address`}>Address</label>
          <input
            ref={field}
            id={`${id}-address`}
            value={address}
            placeholder="gitlab.example.com or https://host/path"
            aria-invalid={addressBad.length ? true : undefined}
            autoFocus
            onChange={(event) => {
              setAddress(event.target.value);
              setKind(null);
              edited("address");
              edited("kind");
            }}
          />
          {checking ? (
            <span className="field-note mx-check" role="status">
              <span className="mx-spin" aria-hidden="true" />
              {` checking ${address.trim()} …`}
            </span>
          ) : (
            <>
              {addressBad.map((r) => (
                <CheckNote key={r.message} note={r} />
              ))}
              {(result?.warnings ?? []).map((line) => (
                <span key={line} className="field-note warn">{`⚠ ${line}`}</span>
              ))}
              {result?.unchecked && (
                <span className="field-note warn">
                  {`⚠ ${result.unchecked.message}`}
                  {result.unchecked.hint && <span className="mx-hint">{result.unchecked.hint}</span>}
                </span>
              )}
              {hinted && <span className="field-note">{`Looks like ${hinted.title}; the token tells for sure.`}</span>}
              {result?.saved && <span className="field-note">Already saved: Add server replaces its token.</span>}
            </>
          )}
        </div>
        {choose && (
          <div className="field launch-wide">
            <span className="field-label" id={`${id}-kind`}>
              Kind
            </span>
            <fieldset className="choice" aria-labelledby={`${id}-kind`}>
              <div className="segments">
                {kinds.map((option) => (
                  <label key={option.name}>
                    <input
                      type="radio"
                      name={`${id}-kind`}
                      value={option.name}
                      checked={kind === option.name}
                      onChange={() => {
                        setKind(option.name);
                        edited("kind");
                      }}
                    />
                    {option.title}
                  </label>
                ))}
              </div>
            </fieldset>
            {mine("kind").map((r) => (
              <CheckNote key={r.message} note={r} />
            ))}
          </div>
        )}
        <div className="field launch-wide">
          <label htmlFor={`${id}-token`}>Token</label>
          <SecretField
            field={token}
            label="Token"
            placeholder="Paste the token"
            onFilled={(now) => {
              setFilled(now);
              edited("token");
            }}
            onEnter={() => void add()}
          />
          {mine("token").map((r) => (
            <CheckNote key={r.message} note={r} />
          ))}
          {page && (
            <span className="field-note">
              {"Make one at "}
              <a href={page} target="_blank" rel="noreferrer">
                {page}
              </a>
              {` with the ${scopes}.`}
            </span>
          )}
          <span className="field-note">{TOKEN_NOTE}</span>
        </div>
      </div>
      <div className="mx-form-acts">
        <button type="button" className="primary" disabled={!ready} onClick={() => void add()}>
          {busy ? "checking the server…" : choose ? "Add without a check" : "Add server"}
        </button>
        <button type="button" className="quiet" onClick={onCancel}>
          Cancel
        </button>
        {[...of(""), ...mine("")].map((r) => (
          <CheckNote key={r.message} note={r} />
        ))}
      </div>
    </div>
  );
}

// Remove: asks under the row, the focus on Cancel; Esc cancels.
function RemoveGitServer({
  server,
  onTouch,
  onCancel,
  onChanged,
  onGone,
}: {
  server: GitServerInfo;
  onTouch: () => void;
  onCancel: () => void;
  onChanged: (given?: GitServers) => Promise<void>;
  onGone: (line: string) => void;
}) {
  const id = useId();
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const remove = async () => {
    onTouch();
    setBusy(true);
    setProblem(null);
    try {
      const left = await removeGitServer(server.host);
      onGone(`Removed ${server.address}.`);
      void onChanged(left);
    } catch (error) {
      setProblem(refusalOf(error).message);
      setBusy(false);
      void onChanged();
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
        <b>{`Remove ${server.address}?`}</b> Its token is deleted too. This cannot be undone. Running agents keep
        reaching it until they restart.
      </p>
      <div className="mx-form-acts">
        <button type="button" className="danger" disabled={busy} onClick={() => void remove()}>
          Remove server
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
