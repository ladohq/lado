// Settings → Providers and environment (docs/design/ui.md): each agent CLI LADO can run, its
// version, one line that says whether it is logged in, how and from which layer, as its own
// status command says (GET /api/providers/logins), the agents that wait for its login and the
// projects with a login of their own, and one button that opens its login sheet
// (LoginSheet.tsx). Under the rows `lado doctor`'s provider checks and Check again. The
// section is read when it opens, when a sheet closes and on Check again: the CLIs' files
// change outside LADO, so not from the change feed. The page scrolls to it at
// #providers-and-environment.
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Link, useLocation } from "react-router";

import { getProviderLogins, type CheckInfo, type ProviderLogins, type ProvidersPage } from "./api";
import { LoginSheet } from "./LoginSheet";
import { PROVIDERS_ANCHOR, terminalPath } from "./paths";
import { messageOf } from "./SessionControl";

export function Providers() {
  const id = useId();
  const [page, setPage] = useState<ProvidersPage | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [reading, setReading] = useState(false);
  const [sheet, setSheet] = useState<string | null>(null); // the provider whose sheet is open
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
  const open = page?.providers.find((p) => p.cli.name === sheet);

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
              <ProviderRow key={row.cli.name} row={row} onOpen={() => setSheet(row.cli.name)} />
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
      {open && (
        <LoginSheet
          row={open}
          onChanged={changed}
          onClose={() => {
            setSheet(null);
            void read();
          }}
        />
      )}
    </section>
  );
}

// The line under the CLI's name: its login's state, how and from which layer, in words.
export function stateText(row: ProviderLogins): string {
  const login = row.login;
  if (login.state === "yes") return ["Logged in", login.method, login.where].filter(Boolean).join(" · ");
  if (login.state === "no") return row.needs_login ? "Not logged in" : "No login";
  return `Unknown: ${login.problem}`;
}

function ProviderRow({ row, onOpen }: { row: ProviderLogins; onOpen: () => void }) {
  const { cli, login } = row;
  const missing = login.state === "no" && row.needs_login;
  const dot = login.state === "yes" ? "ok-dot" : missing ? "dot-waiting" : "off-dot";
  // A CLI with no way to log in from the page (Codex) has no button.
  const loginHere = row.choices.length > 0 || row.actions.length > 0;

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
          {row.projects.length > 0 && <p className="pv-src">Projects with their own login: {row.projects.join(", ")}</p>}
          {row.note && <p className="pv-warn">{row.note}</p>}
          {loginHere && (
            <div className="pv-actions">
              <button type="button" className={missing ? "primary" : "quiet"} onClick={onOpen}>
                {login.state === "yes" ? "Change login…" : "Log in…"}
              </button>
            </div>
          )}
        </>
      )}
    </li>
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
