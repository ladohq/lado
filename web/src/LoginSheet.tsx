// The login sheet of Settings → Providers and environment (docs/design/ui.md), opened by a
// CLI's one button. For a CLI whose provider names choices (Claude Code: "How do you pay for
// Claude?") it asks its question, the current choice marked, and keeps the value pasted under
// the chosen one as LADO's secret in place of the CLI's other login there (PUT
// …/variables/{name}: written, never shown); "Log out…" while the login comes from LADO's
// secrets removes it (DELETE …/login-secrets) after asking, naming the CLI's running agents.
// LADO runs no login command for such a CLI. For a CLI that logs in by its own command
// (OpenCode, Kilo) the sheet is its login window at once (LoginWindow.tsx), with "Log out of
// one…" while logged in. A sheet over the page; the whole screen on a phone.
import { useEffect, useId, useRef, useState } from "react";

import { closeLogin, deleteLoginSecrets, openLogin, putLoginVariable, type ProviderLogins } from "./api";
import { LoginWindow } from "./LoginWindow";
import { SecretField } from "./ProjectVariables";
import { messageOf } from "./SessionControl";

type Props = { row: ProviderLogins; onChanged: (row: ProviderLogins) => void; onClose: () => void };

export function LoginSheet(props: Props) {
  return props.row.choices.length > 0 ? <ChoiceSheet {...props} /> : <WindowSheet {...props} />;
}

type Ref = ProviderLogins["running"][number];

const who = (agents: Ref[]) => agents.map((a) => `${a.agent} of ${a.session}`).join(", ");

// A choice's detail with its `commands` as code.
function Detail({ text }: { text: string }) {
  return (
    <p className="muted">
      {text.split("`").map((part, i) => (i % 2 ? <code key={i}>{part}</code> : part))}
    </p>
  );
}

function ChoiceSheet({ row, onChanged, onClose }: Props) {
  const id = useId();
  const { login } = row;
  const current = login.state === "yes" ? login.choice : "";
  const [chosen, setChosen] = useState(current || row.choices[0].id);
  const [filled, setFilled] = useState(false);
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const field = useRef<HTMLInputElement>(null);
  const choice = row.choices.find((c) => c.id === chosen) ?? row.choices[0];

  const act = async (request: () => Promise<ProviderLogins>) => {
    setBusy(true);
    try {
      onChanged(await request());
      onClose();
    } catch (error) {
      setRefused(messageOf(error));
      setBusy(false);
    }
  };
  const save = () => {
    const value = field.current?.value ?? "";
    if (value) void act(() => putLoginVariable(row.cli.name, choice.variable, value));
  };

  return (
    <div className="login-sheet" role="dialog" aria-modal="true" aria-labelledby={id}>
      <div className="login-window">
        <div className="login-top">
          <h3 id={id}>{row.question}</h3>
          <button type="button" className="quiet" disabled={busy} onClick={onClose}>
            Close
          </button>
        </div>
        <div className="login-help">
          {asking ? (
            <Confirm
              running={row.running}
              busy={busy}
              onYes={() => void act(() => deleteLoginSecrets(row.cli.name))}
              onCancel={() => setAsking(false)}
            />
          ) : (
            <>
              {row.choices.map((c) => (
                <div key={c.id} className={c.id === chosen ? "login-choice login-chosen" : "login-choice"}>
                  <label>
                    <input
                      type="radio"
                      name={id}
                      checked={c.id === chosen}
                      onChange={() => {
                        setChosen(c.id);
                        setFilled(false);
                        setRefused(null);
                      }}
                    />
                    <strong>{c.title}</strong>
                    {c.id === current && <span className="login-current">current</span>}
                  </label>
                  <Detail text={c.detail} />
                  {c.id === chosen && (
                    <div className="login-send">
                      <SecretField
                        key={c.id}
                        field={field}
                        label={c.variable}
                        placeholder="paste it here (not shown after saving)"
                        onFilled={setFilled}
                        onEnter={save}
                      />
                      <button type="button" className="primary" disabled={busy || !filled} onClick={save}>
                        Save
                      </button>
                    </div>
                  )}
                </div>
              ))}
              {row.from_lado && (
                <div className="pv-actions login-out">
                  <button type="button" className="quiet" disabled={busy} onClick={() => setAsking(true)}>
                    Log out…
                  </button>
                </div>
              )}
            </>
          )}
          {refused && (
            <p className="field-note bad" role="alert">
              {refused}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

// Asks before Log out, naming the CLI's running agents: they keep the login they started with.
function Confirm({
  running,
  busy,
  onYes,
  onCancel,
}: {
  running: Ref[];
  busy: boolean;
  onYes: () => void;
  onCancel: () => void;
}) {
  const text = "Remove this login from LADO's secrets?";
  return (
    <div className="pv-confirm" role="group" aria-label={text}>
      <span>
        {text}{" "}
        {running.length === 0
          ? "No agent of it runs now."
          : `${who(running)} ${running.length === 1 ? "keeps it until it starts" : "keep it until they start"} again; new agents go without it.`}
      </span>
      <button type="button" className="danger" disabled={busy} onClick={onYes}>
        Log out
      </button>
      <button type="button" className="quiet" disabled={busy} onClick={onCancel}>
        Cancel
      </button>
    </div>
  );
}

// The CLI's own login command in its window; "Log out of one…" ends it and runs the logout
// command in its place. Each window counts: only the end of the one shown closes the sheet.
function WindowSheet({ row, onChanged, onClose }: Props) {
  const id = useId();
  const name = row.cli.name;
  const count = useRef(0);
  const [shown, setShown] = useState<{ action: string; count: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);

  const start = async (action: string, replacing: boolean) => {
    const mine = ++count.current;
    setBusy(true);
    try {
      if (replacing) await closeLogin(name);
      const opened = await openLogin(name, action);
      if (mine !== count.current) return;
      onChanged(opened);
      setShown({ action, count: mine });
    } catch (error) {
      setRefused(messageOf(error));
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    void start("login", false); // once, as the sheet opens
  }, []);

  if (!shown) {
    return (
      <div className="login-sheet" role="dialog" aria-modal="true" aria-labelledby={id}>
        <div className="login-window">
          <div className="login-top">
            <h3 id={id}>{`Log in: ${row.cli.title}`}</h3>
            {!refused && <span className="muted login-link">opening…</span>}
            <button type="button" className="quiet" onClick={onClose}>
              Close
            </button>
          </div>
          {refused && (
            <div className="login-help">
              <p className="field-note bad" role="alert">
                {refused}
              </p>
            </div>
          )}
        </div>
      </div>
    );
  }
  const logout = row.actions.find((a) => a.id === "logout");
  const offerLogout = logout && row.login.state === "yes" && shown.action !== "logout";
  return (
    <LoginWindow
      key={shown.count}
      provider={name}
      title={row.cli.title}
      extra={
        offerLogout && (
          <button type="button" className="quiet" disabled={busy} onClick={() => void start(logout.id, true)}>
            {logout.label}
          </button>
        )
      }
      onEnded={() => {
        if (shown.count === count.current) onClose();
      }}
    />
  );
}
