// Settings → Git servers (docs/design/ui.md, Git servers): the human's GitLab and GitHub
// Enterprise servers, as `lado git-server` keeps them. On screen only values, states, one-line
// results and actions; every why stands behind an info button (InfoTip). The list is read when
// the page opens and after each change of its own (GET /api/git-servers asks no server). A
// server's row opens to its panel: Sign-in (Check, Replace token), Commit author (Set author,
// Edit, Remove with Undo) and Remove server at its foot. + Add server opens a form under the
// list; once the address's typing settles the server is asked with no token, and the kind it
// looks like is only a hint for Token's link. The page shows at most one result line: any
// action takes the last one away, opening or closing a row does not. The focus goes by rule
// after each action; nothing under the pointer moves (useScrollAnchor).
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useSearchParams } from "react-router";

import {
  ApiError,
  addGitServer,
  checkGitServer,
  checkSavedGitServer,
  clearGitServerAuthor,
  type EntryRefused,
  type GitEntryRefused,
  type GitKindInfo,
  type GitServerAdded,
  type GitServerCheck,
  type GitServerChecked,
  type GitServerInfo,
  type GitServers,
  getGitServers,
  gitRefusalOf,
  refusalOf,
  removeGitServer,
  setGitServerAuthor,
} from "./api";
import { ChevronIcon } from "./icons";
import { InfoTip } from "./InfoTip";
import { MODEL_DEBOUNCE, useDebounced } from "./Launch";
import { CheckNote, emptyKey } from "./ModelSources";
import { SecretField } from "./ProjectVariables";
import { SettingsPage } from "./SettingsPage";
import { useScrollAnchor } from "./useScrollAnchor";

export const GITLAB_COM = "https://gitlab.com";

// The info buttons' texts (the page spec's table).
export const TIPS = {
  servers:
    "Your GitLab, gitlab.com or GitHub Enterprise: agents clone and push there with the token you give. Running agents get a change after they restart.",
  signIn:
    "Agents clone and push here with this token. Check asks the server whether it still works. Replace the token when it expires or is revoked: the new one is checked before it is saved.",
  author:
    "The name and email on agents' commits to this server's repositories. Without one, they carry your own git author, as everywhere else.",
  address:
    "The address you open the server at in a browser. LADO asks the server what it is, GitLab or GitHub, as soon as you type it.",
  token:
    "Only LADO reads it; it is never shown again. Give it an expiry date you will remember: when it expires, replace it from the server's row.",
  kind: "LADO could not ask the server's API. If git reaches it anyway, choose its kind to save it now; check it later from its row.",
  plainHttp:
    "Anyone on the network between LADO and the server can read the token. Use https:// if the server has it.",
};

type Tip = { about: string; text: string };
type Way = "replace" | "check" | "undo";
// The one result line of the page: the server it is about, where it stands (the panel's top,
// under Sign-in or Commit author, or in a removed server's place), its sentence, an info tip
// at its end, its way out, a second line, and the author Undo sets again.
type Result = {
  host: string;
  place: "top" | "signin" | "author" | "gone";
  tone: "ok" | "warn" | "bad";
  text: string;
  tip?: Tip;
  way?: Way;
  then?: { text: string; tip?: Tip };
  undo?: { name: string; email: string };
};
type Form = { host: string; what: "replace" | "author" | "remove" };

// A failed Check of this visit, on the closed row's second line.
const FAILED: Record<string, string> = {
  token_refused: "✕ check failed: token refused",
  scopes_missing: "✕ check failed: a scope missing",
  cert_untrusted: "✕ check failed: certificate not trusted",
  redirect: "✕ check failed: redirect",
  other_kind: "✕ check failed: another kind",
  unrecognised: "✕ check failed: neither GitHub nor GitLab",
  no_answer: "⚠ check: no answer",
};

// A check's line: its sentence from the server, its tip, its way out.
function checkLine(host: string, found: GitServerChecked): Result {
  const line: Result = { host, place: "signin", tone: "bad", text: found.message };
  switch (found.outcome) {
    case "ok":
      return { ...line, tone: "ok" };
    case "token_refused":
      return { ...line, way: "replace" };
    case "scopes_missing":
      return { ...line, tip: { about: "the missing scope", text: found.hint }, way: "replace" };
    case "no_answer":
      return { ...line, tone: "warn", text: `⚠ ${found.message}`, tip: { about: "no answer", text: found.hint }, way: "check" };
    case "cert_untrusted":
      return { ...line, tip: { about: "the certificate", text: found.hint }, way: "check" };
    default:
      return line;
  }
}

// The closed row's second line: a failed check of this visit first, then what is wrong.
function secondLine(server: GitServerInfo, failed: string | undefined): { text: string; tone: string } {
  if (failed) return { text: failed, tone: failed.startsWith("✕") ? "bad" : "warn" };
  if (!server.has_token) return { text: "⚠ token missing", tone: "warn" };
  if (server.login === null) return { text: "⚠ not checked", tone: "warn" };
  return { text: `signed in as ${server.login}`, tone: "" };
}

const authorOf = (server: GitServerInfo) =>
  server.author_name !== null ? `${server.author_name} <${server.author_email}>` : null;

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
      setEntries({ servers: found.servers, kinds: found.kinds });
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
  // One server as a change gave it back, in its place; `added` puts a new one at the end (a
  // server gone meanwhile is not brought back otherwise).
  const put = (server: GitServerInfo, added = false) =>
    setEntries((now) => {
      if (!now) return now;
      const there = now.servers.some((s) => s.host === server.host);
      if (!there && !added) return now;
      const servers = there
        ? now.servers.map((s) => (s.host === server.host ? server : s))
        : [...now.servers, server];
      return { ...now, servers };
    });
  // The servers by host at the first read, then each one added here at the end, where its form
  // was; a server removed here leaves its line in its place while that line is the result.
  const order = useRef<string[] | null>(null);
  if (entries && order.current === null) order.current = entries.servers.map((s) => s.host);
  for (const server of entries?.servers ?? [])
    if (order.current && !order.current.includes(server.host)) order.current.push(server.host);
  const [opened, setOpened] = useState<string[]>([]);
  const open = (host: string) => setOpened((now) => (now.includes(host) ? now : [...now, host]));
  const [form, setForm] = useState<Form | null>(null);
  // The open Add form's number (0: none): a late answer closes only the form it came from.
  const [adding, setAdding] = useState(0);
  const addForms = useRef(0);
  const [result, setResult] = useState<Result | null>(null);
  const [checking, setChecking] = useState<string[]>([]); // the servers being checked
  const [failed, setFailed] = useState<Record<string, string>>({});
  const failedAs = (host: string, line: string | null) =>
    setFailed((now) => {
      const next = { ...now };
      if (line) next[host] = line;
      else delete next[host];
      return next;
    });
  // Where the focus goes after an action: a key of `targets`, each time anew after the render.
  const targets = useRef(new Map<string, HTMLElement>());
  const target = (key: string) => (node: HTMLElement | null) => {
    if (node) targets.current.set(key, node);
    else if (targets.current.get(key)?.isConnected === false) targets.current.delete(key);
  };
  const [focus, setFocus] = useState<{ key: string; n: number } | null>(null);
  const focusOn = (key: string) => setFocus((now) => ({ key, n: (now?.n ?? 0) + 1 }));
  useEffect(() => {
    if (focus) targets.current.get(focus.key)?.focus();
  }, [focus]);
  // An action: the last result goes. Its number: an answer that comes after a later action
  // (`stale`) keeps the list true and touches no result, form or focus.
  const actions = useRef(0);
  const act = () => {
    setResult(null);
    return ++actions.current;
  };
  const stale = (mine: number) => mine !== actions.current;
  const servers = entries?.servers ?? [];
  const kindOf = (server: GitServerInfo) => entries?.kinds.find((k) => k.name === server.kind);

  const check = async (server: GitServerInfo) => {
    const mine = act();
    const host = server.host;
    setChecking((now) => [...now, host]);
    try {
      const found = await checkSavedGitServer(host);
      if (found.server) put(found.server);
      else void reload();
      failedAs(host, found.outcome === "ok" ? null : (FAILED[found.outcome] ?? null));
      if (stale(mine)) return;
      setResult(checkLine(host, found));
      focusOn(`check:${host}`);
    } catch (error) {
      void reload();
      if (stale(mine)) return;
      // A server gone meanwhile (removed elsewhere): the line stands in its place.
      const gone = error instanceof ApiError && error.status === 404;
      setResult({ host, place: gone ? "gone" : "signin", tone: "bad", text: refusalOf(error).message });
      if (!gone) focusOn(`check:${host}`);
    } finally {
      setChecking((now) => now.filter((h) => h !== host));
    }
  };
  // A form whose save is done closes when it is still open, also after a later action; only
  // the result line and the focus are the latest action's.
  const closeOwn = (started: Form | null) => setForm((now) => (now === started ? null : now));
  const replaced = (server: GitServerInfo, done: GitServerAdded, mine: number, started: Form | null) => {
    put(done.server);
    failedAs(server.host, null);
    closeOwn(started);
    if (stale(mine)) return;
    const now = done.server.login;
    if (done.warning) setResult({ host: server.host, place: "signin", tone: "warn", text: `⚠ ${done.warning}`, way: "replace" });
    else if (now === null)
      setResult({ host: server.host, place: "signin", tone: "ok", text: `Saved without a check as ${done.server.kind_title}.` });
    else {
      const before = server.login;
      setResult({
        host: server.host,
        place: "signin",
        tone: "ok",
        text: `Token replaced: signed in as ${now}.`,
        then:
          before && before !== now
            ? {
                text: `⚠ Before, it was ${before}.`,
                tip: {
                  about: "the other user",
                  text: `Agents' commits and pushes now go as ${now}. If that is not what you meant, replace the token again.`,
                },
              }
            : undefined,
      });
    }
    focusOn(`replace:${server.host}`);
  };
  const author = async (server: GitServerInfo, call: () => Promise<{ server: GitServerInfo }>, line: Result) => {
    const mine = act();
    try {
      put((await call()).server);
      if (stale(mine)) return;
      setResult(line);
      focusOn(line.way === "undo" ? `undo:${server.host}` : `edit:${server.host}`);
    } catch (error) {
      if (!stale(mine)) setResult({ host: server.host, place: "author", tone: "bad", text: refusalOf(error).message });
    }
  };
  const removeAuthor = (server: GitServerInfo) =>
    void author(server, () => clearGitServerAuthor(server.host), {
      host: server.host,
      place: "author",
      tone: "ok",
      text: "Author removed.",
      way: "undo",
      undo: { name: server.author_name ?? "", email: server.author_email ?? "" },
    });
  const undoAuthor = (server: GitServerInfo, undo: { name: string; email: string }) =>
    void author(server, () => setGitServerAuthor(server.host, undo.name, undo.email), {
      host: server.host,
      place: "author",
      tone: "ok",
      text: "Author saved.",
    });
  const way = (server: GitServerInfo, line: Result) => {
    if (line.way === "check") void check(server);
    else if (line.way === "undo" && line.undo) undoAuthor(server, line.undo);
    else if (line.way === "replace") {
      act();
      setAdding(0); // one form at a time on the page
      setForm({ host: server.host, what: "replace" });
    }
  };
  const toggleForm = (host: string, what: Form["what"]) => {
    act();
    setAdding(0); // one form at a time on the page
    setForm((now) => (now?.host === host && now.what === what ? null : { host, what }));
  };
  const closeForm = (key: string) => {
    act(); // a save still under way answers to no form
    setForm(null);
    focusOn(key);
  };
  // A clone's note opens the page to check a saved server (`?check=<host>`) or to add one
  // (`?add=<address>`, the focus in Token), once the list is read; the query then leaves the
  // address bar, so a reload does neither again. A host no server is saved for opens nothing.
  const [params, setParams] = useSearchParams();
  const [addAt, setAddAt] = useState<string | null>(null);
  const fromQuery = useRef(false);
  useEffect(() => {
    if (!entries || fromQuery.current) return;
    const host = params.get("check");
    const at = params.get("add");
    if (host === null && at === null) return;
    fromQuery.current = true;
    setParams({}, { replace: true });
    const server = host ? entries.servers.find((s) => s.host === host) : undefined;
    if (server) {
      open(server.host);
      void check(server);
    } else if (at) {
      act();
      setForm(null);
      setAddAt(at);
      setAdding(++addForms.current);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, when the list is read
  }, [entries, params]);

  return (
    <SettingsPage slug="git-servers" className="setting mx" ref={section}>
      {problem && (
        <p className="problem" role="alert">
          {problem}
        </p>
      )}
      {entries && (
        <section className="mx-block" aria-labelledby={id}>
          <div className="mx-h">
            <h3 id={id}>Servers {servers.length > 0 && <span className="mx-count">{servers.length}</span>}</h3>
            <InfoTip about="Servers">{TIPS.servers}</InfoTip>
          </div>
          {servers.length === 0 && result?.place !== "gone" && (
            <p className="mx-empty">
              <b>No git servers yet.</b>
            </p>
          )}
          <ul className="mx-srcs">
            {(order.current ?? []).map((host) => {
              const server = servers.find((s) => s.host === host);
              const mine = result?.host === host ? result : null;
              if (!server)
                return mine?.place === "gone" ? (
                  <li key={host} className="mx-src" data-anchor="">
                    <div className="mx-done" role="status">
                      {mine.text}
                    </div>
                    {mine.then && <span className="field-note warn">{mine.then.text}</span>}
                  </li>
                ) : null;
              const kind = kindOf(server);
              const isOpen = opened.includes(host);
              const formHere = form?.host === host ? form.what : null;
              const commits = authorOf(server);
              return (
                <li key={host} className={`mx-src${isOpen ? " mx-open" : ""}`} data-anchor="">
                  <GitHead
                    server={server}
                    open={isOpen}
                    second={secondLine(server, failed[host])}
                    hit={target(`head:${host}`)}
                    onToggle={() => setOpened((now) => (now.includes(host) ? now.filter((h) => h !== host) : [...now, host]))}
                  />
                  {isOpen && (
                    <div className="gx-body">
                      {mine?.place === "top" && (
                        <div className="gx-top">
                          <ResultLine line={mine} server={server} target={target} onWay={() => way(server, mine)} />
                        </div>
                      )}
                      <ul className="gx-rows">
                        <li className="gx-row">
                          <div>
                            <div className="gx-name">
                              Sign-in <InfoTip about="Sign-in">{TIPS.signIn}</InfoTip>
                            </div>
                            <p className="gx-val">
                              {!server.has_token ? (
                                <span className="w">⚠ Token missing</span>
                              ) : server.login === null ? (
                                <span className="w">⚠ Not checked</span>
                              ) : (
                                <>
                                  Signed in as <b>{server.login}</b>
                                </>
                              )}
                            </p>
                          </div>
                          <div className="gx-ctl">
                            {server.has_token && (
                              <button
                                ref={target(`check:${host}`)}
                                type="button"
                                className="quiet"
                                aria-label={`Check ${server.address}`}
                                disabled={checking.includes(host)}
                                onClick={() => void check(server)}
                              >
                                Check
                              </button>
                            )}
                            <button
                              ref={target(`replace:${host}`)}
                              type="button"
                              className={server.has_token ? "quiet" : "primary"}
                              aria-label={`Replace the token of ${server.address}`}
                              aria-pressed={formHere === "replace"}
                              onClick={() => toggleForm(host, "replace")}
                            >
                              Replace token
                            </button>
                          </div>
                          <div className="gx-under">
                            {checking.includes(host) && (
                              <span className="field-note mx-check" role="status">
                                <span className="mx-spin" aria-hidden="true" /> Checking…
                              </span>
                            )}
                            {formHere === "replace" && kind && (
                              <ReplaceToken
                                server={server}
                                kind={kind}
                                onTouch={act}
                                onCancel={() => closeForm(`replace:${host}`)}
                                onDone={(done, mine) => replaced(server, done, mine, form)}
                              />
                            )}
                            {mine?.place === "signin" && (
                              <ResultLine line={mine} server={server} target={target} onWay={() => way(server, mine)} />
                            )}
                          </div>
                        </li>
                        <li className="gx-row">
                          <div>
                            <div className="gx-name">
                              Commit author <InfoTip about="Commit author">{TIPS.author}</InfoTip>
                            </div>
                            <p className="gx-val">{commits ? <b>{commits}</b> : "Your own git author"}</p>
                          </div>
                          <div className="gx-ctl">
                            <button
                              ref={target(`edit:${host}`)}
                              type="button"
                              className="quiet"
                              aria-label={`${commits ? "Edit" : "Set"} the commit author of ${server.address}`}
                              aria-pressed={formHere === "author"}
                              onClick={() => toggleForm(host, "author")}
                            >
                              {commits ? "Edit" : "Set author"}
                            </button>
                            {commits && (
                              <button
                                type="button"
                                className="quiet"
                                aria-label={`Remove the commit author of ${server.address}`}
                                onClick={() => {
                                  setForm(null);
                                  removeAuthor(server);
                                }}
                              >
                                Remove
                              </button>
                            )}
                          </div>
                          <div className="gx-under">
                            {formHere === "author" && (
                              <GitAuthor
                                server={server}
                                onTouch={act}
                                onCancel={() => closeForm(`edit:${host}`)}
                                onDone={(done, mine) => {
                                  put(done.server);
                                  closeOwn(form);
                                  if (stale(mine)) return;
                                  setResult({ host, place: "author", tone: "ok", text: "Author saved." });
                                  focusOn(`edit:${host}`);
                                }}
                              />
                            )}
                            {mine?.place === "author" && (
                              <ResultLine line={mine} server={server} target={target} onWay={() => way(server, mine)} />
                            )}
                          </div>
                        </li>
                      </ul>
                      <div className="gx-foot">
                        {formHere === "remove" ? (
                          <RemoveGitServer
                            server={server}
                            onTouch={act}
                            onCancel={() => closeForm(`remove:${host}`)}
                            onGone={(left, mine) => {
                              void reload(left);
                              if (stale(mine)) return;
                              setForm(null);
                              setOpened((now) => now.filter((h) => h !== host));
                              setResult({
                                host,
                                place: "gone",
                                tone: "ok",
                                text: `Removed ${server.address}.`,
                                then: left.warning ? { text: `⚠ ${left.warning}` } : undefined,
                              });
                              focusOn("add");
                            }}
                          />
                        ) : (
                          <button
                            ref={target(`remove:${host}`)}
                            type="button"
                            className="quiet danger-text"
                            aria-label={`Remove ${server.address}`}
                            onClick={() => toggleForm(host, "remove")}
                          >
                            Remove server
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </li>
              );
            })}
            <li className="mx-add-slot">
              {adding ? (
                <AddGitServer
                  initial={addAt ?? (servers.some((s) => s.host === "gitlab.com") ? "" : GITLAB_COM)}
                  toToken={addAt !== null}
                  kinds={entries.kinds}
                  servers={servers}
                  onTouch={act}
                  onCancel={() => {
                    act(); // an Add still under way answers to no form
                    setAdding(0);
                    focusOn("add");
                  }}
                  onReplace={(host) => {
                    act();
                    setAdding(0);
                    open(host);
                    setForm({ host, what: "replace" });
                  }}
                  onAdded={(done, mine) => {
                    const host = done.server.host;
                    failedAs(host, null);
                    put(done.server, true); // its row is there for the focus before the list is read
                    void reload();
                    const started = adding;
                    setAdding((now) => (now === started ? 0 : now)); // its own form only
                    if (stale(mine)) return;
                    setForm(null);
                    open(host);
                    const info = done.server;
                    setResult(
                      done.warning
                        ? { host, place: "top", tone: "warn", text: `⚠ ${done.warning}`, way: "replace" }
                        : {
                            host,
                            place: "top",
                            tone: "ok",
                            text: info.login
                              ? `Saved: ${info.kind_title}, signed in as ${info.login}.`
                              : `Saved without a check as ${info.kind_title}.`,
                          },
                    );
                    focusOn(`head:${host}`);
                  }}
                />
              ) : (
                <button
                  ref={target("add")}
                  type="button"
                  className="quiet mx-add"
                  onClick={() => {
                    act();
                    setForm(null);
                    setAddAt(null);
                    setAdding(++addForms.current);
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

// A server's head: one button that opens and closes its panel, named by the address; the
// address whole, the kind and `plain http`, then while closed its second line and whom
// agents commit as (described by them).
function GitHead({
  server,
  open,
  second,
  hit,
  onToggle,
}: {
  server: GitServerInfo;
  open: boolean;
  second: { text: string; tone: string };
  hit: (node: HTMLElement | null) => void;
  onToggle: () => void;
}) {
  const id = useId();
  const commits = authorOf(server);
  return (
    <div className="mx-head">
      <button
        ref={hit}
        type="button"
        className="mx-hit"
        aria-expanded={open}
        aria-label={server.address}
        aria-describedby={open ? undefined : id}
        onClick={onToggle}
      >
        <span className="mx-disc" aria-hidden="true">
          <ChevronIcon />
        </span>
        <span className="mx-src-title">
          <span className="mx-l1">
            <span className="mx-src-name">{server.address}</span>
            <span className="badge">{server.kind_title}</span>
            {server.address.startsWith("http://") && <span className="badge badge-warn">plain http</span>}
          </span>
          <span id={id}>
            <span className={`mx-l2${second.tone ? ` ${second.tone}` : ""}`}>{second.text}</span>
            {commits && <span className="mx-l2">{` commits as ${commits}`}</span>}
          </span>
        </span>
      </button>
    </div>
  );
}

// A result line: its sentence and tip, its way out at its end, a second line under it.
function ResultLine({
  line,
  server,
  target,
  onWay,
}: {
  line: Result;
  server: GitServerInfo;
  target: (key: string) => (node: HTMLElement | null) => void;
  onWay: () => void;
}) {
  const label = { replace: "Replace token", check: "Check again", undo: "Undo" } as const;
  const named = {
    replace: `Replace the token of ${server.address}`,
    check: `Check ${server.address} again`,
    undo: `Undo the removal of the commit author of ${server.address}`,
  } as const;
  return (
    <>
      <p className={`gx-result ${line.tone}`} role={line.tone === "ok" ? "status" : "alert"}>
        <span className="t">
          {line.text}
          {line.tip && (
            <>
              {" "}
              <InfoTip about={line.tip.about}>{line.tip.text}</InfoTip>
            </>
          )}
        </span>
        {line.way && (
          <button
            ref={line.way === "undo" ? target(`undo:${server.host}`) : undefined}
            type="button"
            className="quiet"
            aria-label={named[line.way]}
            onClick={onWay}
          >
            {label[line.way]}
          </button>
        )}
      </p>
      {line.then && (
        <span className="field-note warn">
          {line.then.text}
          {line.then.tip && (
            <>
              {" "}
              <InfoTip about={line.then.tip.about}>{line.then.tip.text}</InfoTip>
            </>
          )}
        </span>
      )}
    </>
  );
}


// Make one on its token page with the scopes … (the kind's token page on this server).
function TokenPage({ root, kind }: { root: string; kind: GitKindInfo }) {
  return (
    <span className="field-note">
      {"Make one on "}
      <a href={root + kind.token_path} target="_blank" rel="noreferrer">
        its token page
      </a>
      {` with the ${kind.scopes}.`}
    </span>
  );
}

// Replace token under Sign-in: New token, the kind's token page, Save token and Cancel; it
// sends the saved address and the token to Add's API. A server that does not answer offers
// to save it without a check under its saved kind; the token stays for that.
function ReplaceToken({
  server,
  kind,
  onTouch,
  onCancel,
  onDone,
}: {
  server: GitServerInfo;
  kind: GitKindInfo;
  onTouch: () => number;
  onCancel: () => void;
  onDone: (done: GitServerAdded, mine: number) => void;
}) {
  const id = useId();
  const token = useRef<HTMLInputElement>(null);
  const [filled, setFilled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<GitEntryRefused | null>(null);
  const silent = refused?.choose_kind === true;
  useEffect(() => token.current?.focus(), []);
  const save = async (withoutCheck: boolean) => {
    if (busy || !filled || (refused?.field === "token" && !withoutCheck)) return;
    const mine = onTouch();
    setBusy(true);
    try {
      const done = await addGitServer(server.address, token.current?.value ?? "", withoutCheck ? server.kind : null);
      emptyKey(token, setFilled);
      onDone(done, mine);
    } catch (error) {
      const why = gitRefusalOf(error);
      if (why.field !== "token" && !why.choose_kind) emptyKey(token, setFilled);
      setRefused(why);
      setBusy(false);
    }
  };
  return (
    <div
      className="gx-form"
      onKeyDown={(event) => {
        if (event.key === "Escape" && !event.defaultPrevented) {
          event.stopPropagation();
          onCancel();
        }
      }}
    >
      <div className="field">
        <span className="field-head" id={`${id}-label`}>
          New token
        </span>
        <SecretField
          field={token}
          label="New token"
          placeholder="Paste the token"
          onFilled={(now) => {
            setFilled(now);
            setRefused(null);
          }}
          onEnter={() => void save(silent)}
        />
        {refused?.field === "token" && <CheckNote note={refused} />}
        <TokenPage root={server.address} kind={kind} />
      </div>
      {silent && (
        <span className="field-note warn" role="alert">
          {`⚠ ${refused.message.replace(/\.$/, "")}: save it without a check, as ${server.kind_title}.`}
        </span>
      )}
      <div className="mx-form-acts">
        <button
          type="button"
          className="primary"
          disabled={busy || !filled || refused?.field === "token"}
          onClick={() => void save(silent)}
        >
          {busy ? "Checking the token…" : silent ? "Save without a check" : "Save token"}
        </button>
        <button type="button" className="quiet" onClick={onCancel}>
          Cancel
        </button>
        {refused && refused.field !== "token" && !silent && <CheckNote note={refused} />}
      </div>
    </div>
  );
}

// Add server: Address and Token, and Kind only for a server that cannot be told. An older
// check's answer is dropped. An address already saved leads to its server's Replace token.
function AddGitServer({
  initial,
  toToken,
  kinds,
  servers,
  onTouch,
  onCancel,
  onReplace,
  onAdded,
}: {
  initial: string;
  toToken: boolean; // the focus in Token, the address given (Settings opened to add it)
  kinds: GitKindInfo[];
  servers: GitServerInfo[];
  onTouch: () => number;
  onCancel: () => void;
  onReplace: (host: string) => void;
  onAdded: (done: GitServerAdded, mine: number) => void;
}) {
  const id = useId();
  const [address, setAddress] = useState(initial);
  const [kind, setKind] = useState<string | null>(null);
  const [filled, setFilled] = useState(false);
  const [refused, setRefused] = useState<GitEntryRefused | null>(null); // Add's
  const [lost, setLost] = useState(false); // it answered the check, not Add
  const [busy, setBusy] = useState(false);
  const field = useRef<HTMLInputElement>(null);
  const token = useRef<HTMLInputElement>(null);
  const settled = useDebounced(address, MODEL_DEBOUNCE);
  const asked = useRef(0);
  const [check, setCheck] = useState<{ for: string; found?: GitServerCheck } | null>(null);
  useEffect(() => {
    if (toToken) token.current?.focus();
    else if (initial) field.current?.select(); // typing replaces it
  }, [initial, toToken]);
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
            refusals: [gitRefusalOf(error)],
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
  const choose = !checking && (result?.choose_kind === true || lost);
  const saved = !checking && result?.saved === true;
  // The saved server of the address's host and port, as LADO tells it (by its key, not its
  // address: one saved as http:// or under a path is the same server).
  const savedHost = saved && result?.address ? servers.find((s) => s.host === new URL(result.address!).host)?.host : undefined;
  // Token's link: the hint's kind, or the one chosen.
  const chosen = choose ? kinds.find((k) => k.name === kind) : undefined;
  const hinted = !checking && result?.hint ? kinds.find((k) => k.name === result.hint) : undefined;
  const linked = chosen ?? hinted;
  const of = (field: string) => (!checking && result ? result.refusals.filter((r) => r.field === field) : []);
  const ready =
    !busy &&
    !checking &&
    !saved &&
    result !== undefined &&
    result.address !== null &&
    result.refusals.length === 0 &&
    filled &&
    refused?.field !== "token" &&
    (!choose || chosen !== undefined);
  // A refusal of Add under a field goes once that field is edited.
  const edited = (field: string) => setRefused((was) => (was?.field === field ? null : was));
  const add = async (again = false) => {
    if (!ready && !again) return;
    const mine = onTouch();
    const given = token.current?.value ?? "";
    const as = choose && chosen ? chosen.name : null;
    setBusy(true);
    setRefused(null);
    setLost(false); // this answer says anew whether it stopped answering
    try {
      const done = await addGitServer(address, given, as);
      emptyKey(token, setFilled);
      onAdded(done, mine);
    } catch (error) {
      const why = gitRefusalOf(error);
      if (why.choose_kind) setLost(true);
      else {
        if (why.field !== "token") emptyKey(token, setFilled);
        setRefused(why);
      }
      setBusy(false);
    }
  };
  const mine = (field: string) => (refused?.field === field ? [refused] : []);
  const addressBad = [...of("address"), ...mine("address")];
  return (
    <div
      className="mx-form"
      onKeyDown={(event) => {
        if (event.key === "Escape" && !event.defaultPrevented) {
          event.stopPropagation();
          onCancel();
        }
      }}
    >
      <div className="launch-grid">
        <div className="field launch-wide">
          <div className="field-head">
            <label htmlFor={`${id}-address`}>Address</label>
            <InfoTip about="Address">{TIPS.address}</InfoTip>
          </div>
          <input
            ref={field}
            id={`${id}-address`}
            value={address}
            placeholder="gitlab.example.com"
            aria-invalid={addressBad.length ? true : undefined}
            autoFocus
            onChange={(event) => {
              setAddress(event.target.value);
              setKind(null);
              setLost(false);
              edited("address");
              edited("kind");
            }}
          />
          {checking ? (
            <span className="field-note mx-check" role="status">
              <span className="mx-spin" aria-hidden="true" /> Checking…
            </span>
          ) : (
            <>
              {addressBad.map((r) => (
                <CheckNote key={r.message} note={r} />
              ))}
              {(result?.warnings.length ?? 0) > 0 && (
                <span className="field-note warn">
                  ⚠ <b>Plain http://</b>: the token travels unencrypted.{" "}
                  <InfoTip about="plain http">{TIPS.plainHttp}</InfoTip>
                </span>
              )}
              {saved && (
                <p className="gx-result warn">
                  <span className="t">Already saved.</span>
                  {savedHost && (
                    <button type="button" className="quiet" onClick={() => onReplace(savedHost)}>
                      Replace its token
                    </button>
                  )}
                </p>
              )}
              {!saved && lost && (
                <p className="gx-result warn" role="alert">
                  <span className="t">⚠ It stopped answering when you pressed Add.</span>
                  <button type="button" className="quiet" disabled={busy} onClick={() => void add(true)}>
                    Try again
                  </button>
                </p>
              )}
              {!saved && !lost && result?.unchecked && (
                <span className="field-note warn">{`⚠ ${result.unchecked.message} ${result.unchecked.hint}`.trim()}</span>
              )}
              {!saved && hinted && (
                <span className="mx-found">
                  <b>{hinted.title}</b> answers.
                </span>
              )}
            </>
          )}
        </div>
        {choose && !saved && (
          <div className="field launch-wide">
            <div className="field-head">
              <span id={`${id}-kind`}>Kind</span>
              <InfoTip about="Kind">{TIPS.kind}</InfoTip>
            </div>
            <fieldset className="choice" aria-labelledby={`${id}-kind`}>
              <div className="segments">
                {kinds.map((option) => (
                  <label key={option.name} className={kind === option.name ? "on" : undefined}>
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
          <div className="field-head">
            <span>Token</span>
            <InfoTip about="Token" place="above">
              {TIPS.token}
            </InfoTip>
          </div>
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
          {!checking && !saved && result?.address && linked && <TokenPage root={result.address} kind={linked} />}
        </div>
      </div>
      <div className="mx-form-acts">
        <button type="button" className="primary" disabled={!ready} onClick={() => void add()}>
          {busy ? "Checking the token…" : choose ? "Add without a check" : "Add server"}
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

// The commit author: Name and Email under its row, the saved ones else empty, the focus on
// Name; Save author once both are filled and differ from the saved; Esc cancels. A refusal
// stands under its field, one of no field under the buttons.
function GitAuthor({
  server,
  onTouch,
  onCancel,
  onDone,
}: {
  server: GitServerInfo;
  onTouch: () => number;
  onCancel: () => void;
  onDone: (done: { server: GitServerInfo }, mine: number) => void;
}) {
  const id = useId();
  const [name, setName] = useState(server.author_name ?? "");
  const [email, setEmail] = useState(server.author_email ?? "");
  const [refused, setRefused] = useState<EntryRefused | null>(null);
  const [busy, setBusy] = useState(false);
  const changed = name.trim() !== (server.author_name ?? "") || email.trim() !== (server.author_email ?? "");
  const ready = !busy && name.trim() !== "" && email.trim() !== "" && changed;
  const save = async () => {
    if (!ready) return;
    const mine = onTouch();
    setBusy(true);
    setRefused(null);
    try {
      onDone(await setGitServerAuthor(server.host, name, email), mine);
    } catch (error) {
      setRefused(refusalOf(error));
      setBusy(false);
    }
  };
  const under = (field: string) => (refused?.field === field ? [refused] : []);
  const other = refused && refused.field !== "name" && refused.field !== "email" ? [refused] : [];
  const edited = (field: string) => setRefused((was) => (was?.field === field ? null : was));
  return (
    <div
      className="gx-form"
      onKeyDown={(event) => {
        if (event.key === "Escape" && !event.defaultPrevented) {
          event.stopPropagation();
          onCancel();
        } else if (event.key === "Enter" && event.target instanceof HTMLInputElement) void save();
      }}
    >
      <div className="launch-grid">
        <div className="field">
          <label htmlFor={`${id}-name`}>Name</label>
          <input
            id={`${id}-name`}
            className="words"
            value={name}
            placeholder="Ivan Petrov"
            aria-invalid={under("name").length ? true : undefined}
            autoFocus
            onChange={(event) => {
              setName(event.target.value);
              edited("name");
            }}
          />
          {under("name").map((r) => (
            <CheckNote key={r.message} note={r} />
          ))}
        </div>
        <div className="field">
          <label htmlFor={`${id}-email`}>Email</label>
          <input
            id={`${id}-email`}
            value={email}
            placeholder="ivan.petrov@example.com"
            aria-invalid={under("email").length ? true : undefined}
            onChange={(event) => {
              setEmail(event.target.value);
              edited("email");
            }}
          />
          {under("email").map((r) => (
            <CheckNote key={r.message} note={r} />
          ))}
        </div>
      </div>
      <div className="mx-form-acts">
        <button type="button" className="primary" disabled={!ready} onClick={() => void save()}>
          Save author
        </button>
        <button type="button" className="quiet" onClick={onCancel}>
          Cancel
        </button>
        {other.map((r) => (
          <CheckNote key={r.message} note={r} />
        ))}
      </div>
    </div>
  );
}

// Remove server: asks in the panel's foot, the focus on Cancel; Esc cancels.
function RemoveGitServer({
  server,
  onTouch,
  onCancel,
  onGone,
}: {
  server: GitServerInfo;
  onTouch: () => number;
  onCancel: () => void;
  onGone: (left: GitServers & { warning: string | null }, mine: number) => void;
}) {
  const id = useId();
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const remove = async () => {
    const mine = onTouch();
    setBusy(true);
    setProblem(null);
    try {
      onGone(await removeGitServer(server.host), mine);
    } catch (error) {
      setProblem(refusalOf(error).message);
      setBusy(false);
    }
  };
  return (
    <div
      className="mx-confirm"
      role="alertdialog"
      aria-labelledby={id}
      onKeyDown={(event) => {
        if (event.key === "Escape" && !event.defaultPrevented) {
          event.stopPropagation();
          onCancel();
        }
      }}
    >
      <p id={id}>
        <b>{`Remove ${server.address}?`}</b>
        <span className="sub">Its token and commit author go too. This cannot be undone.</span>
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
