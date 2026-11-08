// Settings → Agent CLIs (docs/design/ui.md, Agent CLIs): a row per agent CLI LADO can run, its
// version, one line that says whether it is logged in, how and from which layer, as its own
// status command says, the agents that wait for its login and the projects with a login of
// their own, one button that opens its login sheet (LoginSheet.tsx), and under them its
// default model (CliDefault.tsx). Of `lado doctor`'s checks only what the user can fix: a CLI
// not installed, none installed, a version LADO is not tested with, a sign-in that cannot be
// checked, the agents' environment not read.
//
// The rows are the server's last check (GET /api/providers/logins), shown at once; the
// page asks for a fresh one (POST /api/providers/check) when it opens, on ↻ and when a
// sheet closes, and reads the rows every POLL_MS while it runs, ↻ turning; the latest answer
// wins. The CLIs' files change outside LADO, so not from the change feed. A link to
// #<provider name> (Needs you's and New session's Log in…) brings that CLI's row into view
// once it is read and focuses its login button, once per hash.
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Link, useLocation } from "react-router";

import { checkProviders, getProviderLogins, type ProviderLogins, type ProvidersPage } from "./api";
import { CliDefault } from "./CliDefault";
import { LoginSheet } from "./LoginSheet";
import { MODEL_SERVERS_PATH, terminalPath } from "./paths";
import { messageOf } from "./SessionControl";
import { SettingsPage } from "./SettingsPage";
import { type ModelSettingsState, useModelSettings } from "./useModelSettings";

export const POLL_MS = 1000; // how often the rows are read while a check runs

export function Providers() {
  const [page, setPage] = useState<ProvidersPage | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [sheet, setSheet] = useState<string | null>(null); // the provider whose sheet is open
  const latest = useRef(0); // the request whose answer counts
  const poll = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

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

  // Arrival at #<cli>: once its row is read, scroll it to the middle and focus its login
  // button, else its name; once per hash, so a later read never moves the human's focus.
  const { hash } = useLocation();
  const handled = useRef<string | null>(null);
  useEffect(() => {
    const cli = decodeURIComponent(hash.slice(1));
    if (!page || !cli || handled.current === hash) return;
    if (!page.providers.some((p) => p.cli.name === cli && p.ready)) return;
    const row = document.getElementById(cli);
    if (!row) return;
    handled.current = hash;
    const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? true;
    row.scrollIntoView({ block: "center", behavior: still ? "auto" : "smooth" });
    (row.querySelector<HTMLElement>("[data-login]") ?? row.querySelector<HTMLElement>(".pv-name"))?.focus({
      preventScroll: true,
    });
  }, [page, hash]);

  const models = useModelSettings();
  const changed = (row: ProviderLogins) =>
    setPage((now) =>
      now ? { ...now, providers: now.providers.map((p) => (p.cli.name === row.cli.name ? row : p)) } : now,
    );
  const open = page?.providers.find((p) => p.cli.name === sheet);
  const checking = page?.checking ?? problem === null; // before the first answer, unless it failed
  const noneInstalled = page !== null && page.providers.every((p) => p.ready && !p.cli.installed);
  const noServers = models.entries !== null && models.entries.servers.length === 0;

  return (
    <SettingsPage
      slug="agent-clis"
      tools={
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
      }
    >
      <p className="lede">Changes apply to agents started afterwards.</p>
      {problem && (
        <p className="problem" role="alert">
          {problem}
        </p>
      )}
      {problem && !page && <p className="srow-desc">Not checked yet. Press ↻ to try again.</p>}
      {models.problem && <p className="problem">{models.problem}</p>}
      {page && (
        <>
          {noneInstalled && <p className="pv-none">No agent CLI installed. Install one to start a session.</p>}
          <ul className="srows pv-list">
            {page.providers.map((row) => (
              <ProviderRow key={row.cli.name} row={row} models={models} onOpen={() => setSheet(row.cli.name)} />
            ))}
            {page.environment && (
              <li className="srow pv-env-row">
                <p className="pv-warn-line">
                  Couldn't read your login shell: {page.environment}. Details: <code>lado doctor</code>
                </p>
              </li>
            )}
          </ul>
          {noServers && !noneInstalled && (
            <p className="srow-desc cli-more">
              Models of your own come from a model server: <Link to={MODEL_SERVERS_PATH}>Model servers</Link>
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
    </SettingsPage>
  );
}

// The line under the CLI's name: its login's state, how and from which layer, in words.
export function stateText(row: ProviderLogins): string {
  const login = row.login;
  if (login.state === "yes") return ["Logged in", login.method, login.where].filter(Boolean).join(" · ");
  if (login.state === "no") return row.needs_login ? "Not logged in" : "No login";
  return "Couldn't check the sign-in";
}

// A CLI's row (`li#<provider name>`): its text on the left, its login button on the right,
// its default model under them across the row; a row not read yet or a CLI not installed
// has its name and one line.
function ProviderRow({ row, models, onOpen }: { row: ProviderLogins; models: ModelSettingsState; onOpen: () => void }) {
  const id = useId();
  const { cli, login } = row;
  const name = (
    <span className="srow-name pv-name" id={id} tabIndex={-1}>
      {cli.title}
    </span>
  );
  if (!row.ready) {
    return (
      <li className="srow pv cli" id={cli.name} aria-labelledby={id}>
        <div className="srow-text">
          <p className="pv-head">{name}</p>
          <p className="srow-desc pv-checking">checking…</p>
        </div>
      </li>
    );
  }
  if (!cli.installed) {
    return (
      <li className="srow pv cli pv-off" id={cli.name} aria-labelledby={id}>
        <div className="srow-text">
          <p className="pv-head">
            {name}
            <span className="ver">not installed</span>
          </p>
          <p className="srow-desc">{cli.install_hint}</p>
        </div>
        <CliDefault row={row} settings={models} />
      </li>
    );
  }
  const missing = login.state === "no" && row.needs_login;
  const unknown = login.state === "unknown";
  const dot = login.state === "yes" ? "ok-dot" : missing || unknown ? "dot-waiting" : "off-dot";
  // One button that opens the sheet, for a CLI that logs in from the page; none for one that
  // cannot.
  const loginHere = row.choices.length > 0 || row.actions.length > 0;
  const one = row.waiting.length === 1;

  return (
    <li className={`srow pv cli${missing ? " pv-need" : ""}`} id={cli.name} aria-labelledby={id}>
      <div className="srow-text">
        <p className="pv-head">
          {name}
          <span className="ver">{cli.version || cli.detail}</span>
          {cli.warning && <span className="pv-tested">LADO tested {cli.tested_version}</span>}
        </p>
        <p className="pv-state">
          <span className={`dot ${dot}`} aria-hidden="true" />
          {missing ? <strong>{stateText(row)}</strong> : stateText(row)}
        </p>
        {unknown && login.problem && <p className="srow-desc">{login.problem}</p>}
        {row.waiting.length > 0 && (
          <p className="srow-desc">
            {row.waiting.map((a, i) => (
              <span key={`${a.session}/${a.agent}`}>
                {i > 0 && ", "}
                <Link to={terminalPath(a.session, a.agent)}>{`${a.agent} of ${a.session}`}</Link>
              </span>
            ))}
            {one ? " waits; it starts once you log in." : " wait; they start once you log in."}
          </p>
        )}
        {row.projects.length > 0 && (
          <p className="srow-desc">Projects with their own login: {row.projects.join(", ")}</p>
        )}
        {row.note && <p className="pv-warn">{row.note}</p>}
      </div>
      {loginHere && (
        <div className="srow-ctl pv-actions">
          <button type="button" className={missing ? "primary" : "quiet"} data-login="" onClick={onOpen}>
            {login.state === "yes" ? "Change login…" : "Log in…"}
          </button>
        </div>
      )}
      <CliDefault row={row} settings={models} />
    </li>
  );
}
