// Settings → Providers and environment (docs/design/ui.md): each agent CLI LADO can run, its
// version, one line that says whether it is logged in, how and from which layer, as its own
// status command says, the agents that wait for its login and the projects with a login of
// their own, and one button that opens its login sheet (LoginSheet.tsx). Of `lado doctor`'s
// checks only what the user can fix: a CLI not installed, none installed, a version LADO is
// not tested with, a sign-in that cannot be checked, the agents' environment not read.
//
// The rows are the server's last check (GET /api/providers/logins), shown at once; the
// section asks for a fresh one (POST /api/providers/check) when it opens, on ↻ and when a
// sheet closes, and reads the rows every POLL_MS while it runs, ↻ turning; the latest answer
// wins. The CLIs' files change outside LADO, so not from the change feed. The page scrolls
// to it at #providers-and-environment.
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Link, useLocation } from "react-router";

import { checkProviders, getProviderLogins, type ProviderLogins, type ProvidersPage } from "./api";
import { LoginSheet } from "./LoginSheet";
import { PROVIDERS_ANCHOR, terminalPath } from "./paths";
import { messageOf } from "./SessionControl";

export const POLL_MS = 1000; // how often the rows are read while a check runs

export function Providers() {
  const id = useId();
  const [page, setPage] = useState<ProvidersPage | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [sheet, setSheet] = useState<string | null>(null); // the provider whose sheet is open
  const section = useRef<HTMLElement>(null);
  const latest = useRef(0); // the request whose answer counts
  const poll = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const { hash } = useLocation();

  const take = useCallback(async (ask: () => Promise<ProvidersPage>) => {
    const asked = ++latest.current;
    clearTimeout(poll.current);
    try {
      const found = await ask();
      if (asked !== latest.current) return; // a later one was asked, or the section left
      // A server of another version may answer otherwise (the banner says it is one).
      if (!Array.isArray(found?.providers)) throw new Error("the server gave no providers: reload the page");
      setPage(found);
      setProblem(null);
      if (found.checking) poll.current = setTimeout(() => void take(getProviderLogins), POLL_MS);
    } catch (error) {
      if (asked !== latest.current) return;
      setProblem(messageOf(error));
      // No more polling: ↻ stops turning, so a press asks again (the server may be back).
      setPage((now) => (now ? { ...now, checking: false } : now));
    }
  }, []);
  const check = useCallback(() => void take(checkProviders), [take]);
  useEffect(() => {
    check();
    return () => {
      latest.current++; // no answer counts once it left
      clearTimeout(poll.current);
    };
  }, [check]);
  // A link to the section (Needs you's "Log in…") scrolls to it once it is there.
  useEffect(() => {
    if (page && hash === `#${PROVIDERS_ANCHOR}`) section.current?.scrollIntoView({ block: "start" });
  }, [page, hash]);

  const changed = (row: ProviderLogins) =>
    setPage((now) =>
      now ? { ...now, providers: now.providers.map((p) => (p.cli.name === row.cli.name ? row : p)) } : now,
    );
  const open = page?.providers.find((p) => p.cli.name === sheet);
  const checking = page?.checking ?? problem === null; // before the first answer, unless it failed
  const noneInstalled = page !== null && page.providers.every((p) => p.ready && !p.cli.installed);

  return (
    <section className="setting" id={PROVIDERS_ANCHOR} ref={section} aria-labelledby={id}>
      <div className="pv-title">
        <h2 id={id}>Providers and environment</h2>
        <button
          type="button"
          className={`pv-refresh${checking ? " spinning" : ""}`}
          aria-label="Check the CLIs again"
          title={checking ? "Checking the CLIs…" : "Check the CLIs again"}
          onClick={() => {
            if (!checking) check();
          }}
        >
          <span aria-hidden="true">↻</span>
        </button>
      </div>
      <p className="muted">Sign-ins your agents use. Changes apply to agents started afterwards.</p>
      {problem && (
        <p className="problem" role="alert">
          {problem}
        </p>
      )}
      {page && (
        <>
          {noneInstalled && <p className="pv-none">No agent CLI is installed: install one of them to start a session.</p>}
          <ul className="pv-list">
            {page.providers.map((row) => (
              <ProviderRow key={row.cli.name} row={row} onOpen={() => setSheet(row.cli.name)} />
            ))}
          </ul>
          {page.environment && (
            <p className="pv-env">
              ⚠ Agents' environment could not be read from your login shell: {page.environment}.{" "}
              <code>lado doctor</code> shows more.
            </p>
          )}
        </>
      )}
      {open && (
        <LoginSheet
          row={open}
          onChanged={changed}
          onClose={() => {
            setSheet(null);
            check();
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
  return "Couldn't check the sign-in";
}

function ProviderRow({ row, onOpen }: { row: ProviderLogins; onOpen: () => void }) {
  const { cli, login } = row;
  if (!row.ready) {
    return (
      <li className="pv" aria-label={cli.title}>
        <div className="pv-head">
          <strong>{cli.title}</strong>
        </div>
        <span className="pv-checking">checking…</span>
      </li>
    );
  }
  if (!cli.installed) {
    return (
      <li className="pv pv-off" aria-label={cli.title}>
        <div className="pv-head">
          <strong>{cli.title}</strong>
          <span className="ver">not installed</span>
        </div>
        <p className="pv-src">{cli.install_hint}</p>
      </li>
    );
  }
  const missing = login.state === "no" && row.needs_login;
  const unknown = login.state === "unknown";
  const dot = login.state === "yes" ? "ok-dot" : missing || unknown ? "dot-waiting" : "off-dot";
  // One button that opens the sheet, for a CLI that logs in from the page; none for one that
  // cannot.
  const loginHere = row.choices.length > 0 || row.actions.length > 0;

  return (
    <li className="pv" aria-label={cli.title}>
      <div className="pv-head">
        <strong>{cli.title}</strong>
        <span className="ver">{cli.version || cli.detail}</span>
        {cli.warning && <span className="pv-tested">LADO is tested with {cli.tested_version}</span>}
      </div>
      <div className="pv-state">
        <span className={`dot ${dot}`} aria-hidden="true" />
        {missing ? <strong>{stateText(row)}</strong> : stateText(row)}
      </div>
      {unknown && login.problem && <p className="pv-src">{login.problem}</p>}
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
    </li>
  );
}
