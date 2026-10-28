// Settings → Providers and environment (docs/design/ui.md): each agent CLI LADO can run, its
// version, whether it is logged in and how, as its own status command says (GET
// /api/providers/logins), where the login comes from, the agents that wait for it and the
// projects with a login of their own; its login window's actions (LoginWindow.tsx), Log out,
// and its login variables as LADO's secrets (the project page's SecretField: written, never
// shown). Log out and Remove ask first, naming the CLI's running agents. Under the rows
// `lado doctor`'s provider checks and Check again. The section is read when it opens, after
// each action, when a login window ends and on Check again: the CLIs' files change outside
// LADO, so not from the change feed. The page scrolls to it at #providers-and-environment.
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Link, useLocation } from "react-router";

import {
  deleteLoginVariable,
  getProviderLogins,
  logOut,
  openLogin,
  putLoginVariable,
  type CheckInfo,
  type ProviderLogins,
  type ProvidersPage,
} from "./api";
import { LoginWindow } from "./LoginWindow";
import { PROVIDERS_ANCHOR, terminalPath } from "./paths";
import { SecretField } from "./ProjectVariables";
import { messageOf } from "./SessionControl";

type Ref = ProviderLogins["running"][number];

const who = (agents: Ref[]) => agents.map((a) => `${a.agent} of ${a.session}`).join(", ");

export function Providers() {
  const id = useId();
  const [page, setPage] = useState<ProvidersPage | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [reading, setReading] = useState(false);
  const [window_, setWindow] = useState<ProviderLogins | null>(null);
  const section = useRef<HTMLElement>(null);
  const { hash } = useLocation();

  const read = useCallback(async () => {
    setReading(true);
    try {
      const found = await getProviderLogins();
      // A server of another version may answer otherwise (the banner says it is one).
      if (!Array.isArray(found?.providers)) throw new Error("the server gave no providers: reload the page");
      setPage(found);
      setProblem(null);
    } catch (error) {
      setProblem(messageOf(error));
    } finally {
      setReading(false);
    }
  }, []);
  useEffect(() => {
    void read();
  }, [read]);
  // A link to the section (Needs you's "Log in…") scrolls to it once it is there.
  useEffect(() => {
    if (page && hash === `#${PROVIDERS_ANCHOR}`) section.current?.scrollIntoView({ block: "start" });
  }, [page, hash]);

  const changed = (row: ProviderLogins) =>
    setPage((now) =>
      now ? { ...now, providers: now.providers.map((p) => (p.cli.name === row.cli.name ? row : p)) } : now,
    );

  return (
    <section className="setting" id={PROVIDERS_ANCHOR} ref={section} aria-labelledby={id}>
      <h2 id={id}>Providers and environment</h2>
      <p className="muted">
        The agent CLIs LADO can run, whether each is logged in and how. A login here is the one every new agent of
        that CLI gets.
      </p>
      {page === null && problem === null && <p className="muted">Reading the CLIs…</p>}
      {problem && (
        <p className="problem" role="alert">
          {problem}
        </p>
      )}
      {page && (
        <>
          <ul className="pv-list">
            {page.providers.map((row) => (
              <ProviderRow key={row.cli.name} row={row} onChanged={changed} onWindow={setWindow} />
            ))}
          </ul>
          <DoctorChecks checks={page.checks} />
        </>
      )}
      <div className="pv-actions pv-again">
        <button type="button" className="quiet" disabled={reading} onClick={() => void read()}>
          {reading ? "Checking…" : "Check again"}
        </button>
      </div>
      {window_ && (
        <LoginWindow
          provider={window_.cli.name}
          title={window_.cli.title}
          onEnded={() => {
            setWindow(null);
            void read();
          }}
        />
      )}
    </section>
  );
}

// The line under the CLI's name: its login's state in words.
export function stateText(row: ProviderLogins): string {
  const login = row.login;
  if (login.state === "yes") return `Logged in · ${login.method}`;
  if (login.state === "no") return row.needs_login ? "Not logged in" : "No login";
  return `Unknown: ${login.problem}`;
}

function ProviderRow({
  row,
  onChanged,
  onWindow,
}: {
  row: ProviderLogins;
  onChanged: (row: ProviderLogins) => void;
  onWindow: (row: ProviderLogins) => void;
}) {
  const { cli, login } = row;
  const [asking, setAsking] = useState<string | null>(null); // "logout" or a variable's name
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const act = async (request: () => Promise<ProviderLogins>) => {
    setBusy(true);
    try {
      onChanged(await request());
      setRefused(null);
      setAsking(null);
      return true;
    } catch (error) {
      setRefused(messageOf(error));
      return false;
    } finally {
      setBusy(false);
    }
  };
  const window_ = async (action: string) => {
    setBusy(true);
    try {
      const opened = await openLogin(cli.name, action);
      onChanged(opened);
      onWindow(opened);
      setRefused(null);
    } catch (error) {
      setRefused(messageOf(error));
    } finally {
      setBusy(false);
    }
  };
  const missing = login.state === "no" && row.needs_login;
  // A logout in the window needs a login to log out of.
  const actions = row.actions.filter((action) => action.id !== "logout" || login.state !== "no");
  // The CLI's logout removes its own login, not a variable's, which would log it in again.
  const canLogOut = row.can_logout && login.state === "yes" && !login.variable;
  const dot = login.state === "yes" ? "ok-dot" : missing ? "dot-waiting" : "off-dot";
  const items = login.items.map((i) => (i.variable ? `${i.name} (${i.variable})` : `${i.name} (${i.kind})`));

  return (
    <li className="pv" aria-label={cli.title}>
      <div className="pv-head">
        <strong>{cli.title}</strong>
        <span className="ver">{cli.installed ? cli.version || cli.detail : "not installed"}</span>
      </div>
      {!cli.installed ? (
        <p className="pv-src">{cli.install_hint}</p>
      ) : (
        <>
          <div className="pv-state">
            <span className={`dot ${dot}`} aria-hidden="true" />
            {missing ? <strong>{stateText(row)}</strong> : stateText(row)}
          </div>
          {login.state === "yes" && (login.source || items.length > 0) && (
            <p className="pv-src">
              {items.length > 0 && <>{items.join(", ")}. </>}
              {login.source && (
                <>
                  From <code>{login.source}</code>
                </>
              )}
            </p>
          )}
          {row.waiting.length > 0 && (
            <p className="pv-warn">
              {row.waiting.map((a, i) => (
                <span key={`${a.session}/${a.agent}`}>
                  {i > 0 && ", "}
                  <Link to={terminalPath(a.session, a.agent)}>{`${a.agent} of ${a.session}`}</Link>
                </span>
              ))}{" "}
              {row.waiting.length === 1 ? "waits" : "wait"} for this login and{" "}
              {row.waiting.length === 1 ? "starts" : "start"} by itself once you log in.
            </p>
          )}
          {row.projects.length > 0 && (
            <p className="pv-src">
              Projects with a login of their own (their sessions use it instead): {row.projects.join(", ")}
            </p>
          )}
          {row.note && <p className="pv-warn">{row.note}</p>}
          {(actions.length > 0 || canLogOut) && (
            <div className="pv-actions">
              {actions.map((action, i) => (
                <button
                  key={action.id}
                  type="button"
                  className={missing && i === 0 ? "primary" : "quiet"}
                  disabled={busy}
                  onClick={() => void window_(action.id)}
                >
                  {action.label}
                </button>
              ))}
              {canLogOut && (
                <button type="button" className="quiet" disabled={busy} onClick={() => setAsking("logout")}>
                  Log out…
                </button>
              )}
            </div>
          )}
          {asking === "logout" && (
            <Confirm
              text={`Log out of ${cli.title}?`}
              running={row.running}
              then="share this login and may stop being able to answer"
              yes="Log out"
              busy={busy}
              onYes={() => void act(() => logOut(cli.name))}
              onCancel={() => setAsking(null)}
            />
          )}
          {row.variables.length > 0 && (
            <div className="pv-keys">
              <p className="muted">
                {login.state === "yes" ? "Or a token or key instead" : "Or paste a token or key"} (kept as LADO's
                secret, never shown again; it wins over the login file):
              </p>
              {row.variables.map((variable) => (
                <VariableField
                  key={variable.name}
                  row={row}
                  variable={variable}
                  busy={busy}
                  asking={asking === variable.name}
                  onAsk={(yes) => setAsking(yes ? variable.name : null)}
                  act={act}
                />
              ))}
            </div>
          )}
        </>
      )}
      {refused && (
        <p className="field-note bad" role="alert">
          {refused}
        </p>
      )}
    </li>
  );
}

function VariableField({
  row,
  variable,
  busy,
  asking,
  onAsk,
  act,
}: {
  row: ProviderLogins;
  variable: ProviderLogins["variables"][number];
  busy: boolean;
  asking: boolean;
  onAsk: (yes: boolean) => void;
  act: (request: () => Promise<ProviderLogins>) => Promise<boolean>;
}) {
  const field = useRef<HTMLInputElement>(null);
  const [filled, setFilled] = useState(false);
  const save = async () => {
    const value = field.current?.value ?? "";
    if (await act(() => putLoginVariable(row.cli.name, variable.name, value))) {
      if (field.current) field.current.value = "";
      setFilled(false);
    }
  };
  const from = variable.layer && !variable.secret ? ` · from ${variable.layer}` : "";
  return (
    <div className="pv-key">
      <code>{variable.name}</code>
      <span className="muted pv-set">{variable.secret ? "set · LADO's secret" : `not set${from}`}</span>
      <div className="project-edit pv-field">
        <SecretField
          field={field}
          label={variable.name}
          placeholder={variable.secret ? "replace (not shown)" : "value (not shown after saving)"}
          onFilled={setFilled}
          onEnter={() => void save()}
        />
        <button type="button" className="primary" disabled={busy || !filled} onClick={() => void save()}>
          Save
        </button>
        {variable.secret && (
          <button type="button" className="quiet" disabled={busy} onClick={() => onAsk(true)}>
            Remove…
          </button>
        )}
      </div>
      {asking && (
        <Confirm
          text={`Remove ${variable.name} from LADO's secrets?`}
          running={row.running}
          then="keep it until they start again; new agents go without it"
          yes="Remove"
          busy={busy}
          onYes={() => void act(() => deleteLoginVariable(row.cli.name, variable.name))}
          onCancel={() => onAsk(false)}
        />
      )}
    </div>
  );
}

// Asks before a change of the CLI's login, naming its running agents and what `then`
// happens to them.
function Confirm({
  text,
  running,
  then,
  yes,
  busy,
  onYes,
  onCancel,
}: {
  text: string;
  running: Ref[];
  then: string;
  yes: string;
  busy: boolean;
  onYes: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="pv-confirm" role="group" aria-label={text}>
      <span>
        {text} {running.length > 0 ? `${who(running)} ${then}.` : "No agent of it runs now."}
      </span>
      <button type="button" className="danger" disabled={busy} onClick={onYes}>
        {yes}
      </button>
      <button type="button" className="quiet" disabled={busy} onClick={onCancel}>
        Cancel
      </button>
    </div>
  );
}

const MARK: Record<CheckInfo["level"], string> = { ok: "ok", info: "info", warn: "warn", fail: "FAIL" };

function DoctorChecks({ checks }: { checks: CheckInfo[] }) {
  return (
    <ul className="pv-doctor" aria-label="lado doctor about the providers">
      <li className="muted">
        <strong>lado doctor</strong> about the providers:
      </li>
      {checks.map((check) => (
        <li key={check.name} className={`pv-check pv-level-${check.level}`}>
          <span className="pv-mark">{`[${MARK[check.level]}]`}</span> {`${check.name}: ${check.detail}`}
          {check.hint && <span className="muted"> — {check.hint}</span>}
        </li>
      ))}
    </ul>
  );
}
