// Sessions: the list on the left (from /api/sessions, searched by name here), the selected
// session on the right with its tabs. The list's width is dragged on its edge and remembered;
// the list collapses to a strip of the sessions' icons (remembered too).
import { useEffect, useRef, useState, type CSSProperties, type ReactNode, type RefObject } from "react";
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
  useOutletContext,
  useParams,
  useSearchParams,
} from "react-router";

import { Agents } from "./Agents";
import { ArtifactPanel } from "./ArtifactPanel";
import { Artifacts } from "./ArtifactsTable";
import { getSessionAbout, type ProviderInfo, type RepoInfo, type SessionAbout, type SessionKitInfo, type SessionInfo, type SessionStatus } from "./api";
import { Chat } from "./Chat";
import { duration } from "./ChatText";
import { CopyButton } from "./Copy";
import { Flows, isOpen } from "./Flows";
import { GroupHead, type Tone } from "./GroupHead";
import {
  ActivityIcon,
  AgentCliIcon,
  AgentsIcon,
  ArtifactsIcon,
  CollapsePanelIcon,
  FindIcon,
  FlowsIcon,
  FolderIcon,
  GitIcon,
  KitsIcon,
  LinkIcon,
  ProblemIcon,
} from "./icons";
import { useLaunch, type StartedState } from "./Launch";
import { isLive, useLive, useLiveStore, type Loaded } from "./live";
import { SessionActions } from "./SessionControl";
import { SessionRowMenu } from "./SessionRowMenu";
import { MAIN_MIN, TerminalPanel } from "./Terminals";
import { NotFound } from "./pages";
import { FIND_PARAM, isTab, sessionLink, sessionPath, TABS, VIEW_PARAM, type Tab } from "./paths";
import {
  PANEL_WIDTH,
  SESSIONS_WIDTH,
  storeAgentMessages,
  storedAgentMessages,
  storedSessionGroups,
  storedSessionsList,
  storeSessionGroups,
  storeSessionsList,
  type ColumnPrefs,
  type SessionGroup,
} from "./prefs";
import { shortRemote } from "./remote";
import { useTitle } from "./Shell";
import { fitWidth, Splitter, useStripFocus, useWidth } from "./Splitter";
import { Team } from "./Team";
import { Tooltip } from "./Tooltip";

// What each status means to the human, in the words of `lado ls`.
const STATUS: Record<SessionStatus, string> = {
  running: "running",
  stopped: "stopped",
  tmux_gone: "tmux session is gone",
  loop_down: "session loop not running",
};

// The pages inside (NoSession, Session) name themselves: a session's unknown tab is Not found.
// The list and the session's header follow the change feed (live.ts).
export function Sessions() {
  const loaded = useLive().sessions;
  const launch = useLaunch();
  const [query, setQuery] = useState("");
  const [folds, setFolds] = useState(storedSessionGroups);
  const current = useParams().name;

  const wanted = query.trim().toLowerCase();
  const found = loaded && "sessions" in loaded ? loaded.sessions.filter((one) => one.name.toLowerCase().includes(wanted)) : [];
  const groups = grouped(found);
  const toggle = (group: SessionGroup) => {
    const next = { ...folds, [group]: folds[group] === "open" ? "folded" : "open" } as const;
    setFolds(next);
    storeSessionGroups(next);
  };
  const group = (id: SessionGroup) => (
    <Group
      id={id}
      sessions={groups[id]}
      open={wanted !== "" || folds[id] === "open"}
      searching={wanted !== ""}
      current={current}
      onToggle={() => toggle(id)}
    />
  );
  const [list, setList] = useState(storedSessionsList);
  const focus = useStripFocus(list.collapsed);
  const [page, room] = useWidth<HTMLDivElement>();
  // The list leaves the session and the terminals their least widths; collapsed, the strip
  // gives the session the rest.
  const width = fitWidth(list.width, SESSIONS_WIDTH, room === null ? null : room - MAIN_MIN - PANEL_WIDTH.min);
  const keep = (change: Partial<ColumnPrefs>) => {
    const next = { ...list, ...change };
    setList(next);
    storeSessionsList(next);
  };
  const collapse = (collapsed: boolean) => {
    focus.toggled();
    keep({ collapsed });
  };
  const newSession = (
    <button type="button" className="plus" aria-label="New session" title="New session" onClick={() => launch()}>
      <span aria-hidden="true">+</span>
    </button>
  );
  // The session keeps its place in the page whether the list is open or not: its terminals
  // stay connected.
  return (
    <div
      ref={page}
      className={list.collapsed ? "sessions collapsed" : "sessions"}
      style={{ "--list-width": `${list.collapsed ? STRIP_WIDTH : width}px` } as CSSProperties}
    >
      {!list.collapsed && (
        <Splitter
          label="Resize the session list"
          edge="right"
          width={width}
          bounds={SESSIONS_WIDTH}
          onChange={(next) => keep({ width: next })}
        />
      )}
      {list.collapsed ? (
        <SessionStrip loaded={loaded} openRef={focus.open} onOpen={() => collapse(false)}>
          {newSession}
        </SessionStrip>
      ) : (
        <div className="session-list">
          <div className="session-list-head">
            <h2>Sessions</h2>
            {newSession}
            <button
              ref={focus.collapse}
              type="button"
              className="ghost"
              aria-label="Collapse sessions"
              title="Collapse sessions"
              onClick={() => collapse(true)}
            >
              <CollapsePanelIcon side="left" />
            </button>
          </div>
          <input
            type="search"
            className="search"
            placeholder="Find a session"
            aria-label="Find a session"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <nav aria-label="Sessions">
            {loaded === null && <p className="muted">Loading…</p>}
            {loaded && "error" in loaded && (
              <p className="problem" role="alert">
                {loaded.error}
              </p>
            )}
            {loaded && "sessions" in loaded && (
              <>
                {group("needs-you")}
                {group("running")}
                {group("stopped")}
              </>
            )}
          </nav>
        </div>
      )}
      <div className="session-detail">
        <Outlet context={loaded} />
      </div>
    </div>
  );
}

// The width of the list collapsed to a strip, in pixels.
const STRIP_WIDTH = 44;

// The list collapsed to a strip: Sessions opens it again, then New session (`children`), then
// an icon per session not stopped, in the open list's order (those that need the human first,
// a line after them). While the list loads the icons' column is empty and busy; when it
// cannot load, an alert says why, as the open list does.
function SessionStrip({
  loaded,
  openRef,
  onOpen,
  children,
}: {
  loaded: Loaded;
  openRef: RefObject<HTMLButtonElement | null>;
  onOpen: () => void;
  children: ReactNode;
}) {
  const groups = loaded && "sessions" in loaded ? grouped(loaded.sessions) : null;
  return (
    <nav className="sessions-strip" aria-label="Sessions">
      <button ref={openRef} type="button" className="strip-open sessions-open" title="Show the sessions" onClick={onOpen}>
        Sessions
      </button>
      {children}
      {loaded && "error" in loaded ? (
        <Tooltip tip={<div className="tooltip-line">{loaded.error}</div>}>
          <span className="strip-problem" role="alert" aria-label={loaded.error} tabIndex={0}>
            <ProblemIcon />
          </span>
        </Tooltip>
      ) : (
        <ul className="strip-icons" aria-busy={groups === null || undefined}>
          {groups?.["needs-you"].map((session) => <StripIcon key={session.name} session={session} />)}
          {groups && groups["needs-you"].length > 0 && groups.running.length > 0 && (
            <li className="strip-gap" aria-hidden="true" />
          )}
          {groups?.running.map((session) => <StripIcon key={session.name} session={session} />)}
        </ul>
      )}
    </nav>
  );
}

// A session's two letters: the first of its first two words, else its first two letters.
// Two sessions may share them: the tooltip and the label tell them apart.
const initials = (name: string) => {
  const words = name.split(/[-_./\s]+/).filter(Boolean);
  return (words.length > 1 ? words[0][0] + words[1][0] : name.slice(0, 2)).toUpperCase();
};

function StripIcon({ session }: { session: SessionInfo }) {
  const needsYou = waits(session);
  return (
    <li>
      <Tooltip tip={<SessionTip session={session} />}>
        <NavLink
          to={sessionPath(session.name)}
          className={`strip-session${needsYou ? " waits" : ""}`}
          aria-label={needsYou ? `${session.name}, needs you` : session.name}
        >
          {initials(session.name)}
        </NavLink>
      </Tooltip>
    </li>
  );
}

// Who a session is, the card of its row and of its icon: its name, status and agents (by a
// dot of its group's tone), what waits for the human, its folder, its kits, provider and
// permission mode; a stopped one, how to bring it back (Resume is in the session's head).
function SessionTip({ session }: { session: SessionInfo }) {
  const mode = session.permission_mode ? ` · mode ${session.permission_mode}` : "";
  return (
    <div className={`session-tip tone-${TONES[groupOf(session)]}`}>
      <div className="tooltip-line">
        <span className="tip-dot" aria-hidden="true" />
        <b>{session.name}</b> · {STATUS[session.status]} · {count(session.agents, "agent")}
      </div>
      {waits(session) && <div className="tooltip-line waits">Needs you: {about(session)}</div>}
      <div className="tooltip-line">{session.repo}</div>
      <div className="tooltip-line">
        {session.kits.join(", ")} · {session.provider}
        {mode}
      </div>
      {!isLive(session) && <div className="tooltip-line">Stopped: open it and press Resume</div>}
    </div>
  );
}

// Whether something in a session waits for the human, from what the server counts
// (SessionInfo.waiting): never in a stopped session, since nothing in it can be answered.
const waits = (session: SessionInfo) => {
  const { gates, questions, agents } = session.waiting;
  return isLive(session) && gates + questions + agents > 0;
};

// The list's groups, by their ids (prefs.ts): a stopped session is Stopped whatever waits in
// it. Each has its name and its heading's tone (GroupHead), which its rows and cards take.
const groupOf = (session: SessionInfo): SessionGroup =>
  !isLive(session) ? "stopped" : waits(session) ? "needs-you" : "running";

const NAMES: Record<SessionGroup, string> = { "needs-you": "Needs you", running: "Running", stopped: "Stopped" };
const TONES: Record<SessionGroup, Tone> = { "needs-you": "human", running: "done", stopped: "neutral" };

function grouped(sessions: SessionInfo[]): Record<SessionGroup, SessionInfo[]> {
  const groups: Record<SessionGroup, SessionInfo[]> = { "needs-you": [], running: [], stopped: [] };
  for (const session of sessions) groups[groupOf(session)].push(session);
  return groups;
}

const count = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

// One line under a session's name: what waits for the human, or its agents and status.
function about(session: SessionInfo): string {
  const { gates, questions, agents } = session.waiting;
  const parts = [
    gates > 0 && count(gates, "gate"),
    questions > 0 && count(questions, "question"),
    agents > 0 && `${count(agents, "agent")} waiting`,
  ].filter(Boolean);
  if (!isLive(session)) return STATUS.stopped;
  return parts.length ? parts.join(" · ") : count(session.agents, "agent");
}

// One group of the list under its heading, which folds it; a group without sessions is not
// drawn. Folded, its list stays in the page (the heading's aria-controls) and shows only the
// open session, when it is in the group: the open session is always seen. While the search
// has text the group is open and its heading off: a click would change only what is
// remembered, not what is seen.
function Group({
  id,
  sessions,
  open,
  searching,
  current,
  onToggle,
}: {
  id: SessionGroup;
  sessions: SessionInfo[];
  open: boolean;
  searching: boolean;
  current?: string;
  onToggle: () => void;
}) {
  if (sessions.length === 0) return null;
  const rows = open ? sessions : sessions.filter((one) => one.name === current);
  return (
    <section className={`session-group tone-${TONES[id]}`} aria-labelledby={`group-${id}-name`}>
      <GroupHead
        nameId={`group-${id}-name`}
        name={NAMES[id]}
        count={sessions.length}
        tone={TONES[id]}
        fold={{ open, controls: `group-${id}`, onToggle, disabled: searching }}
      />
      <ul id={`group-${id}`} hidden={rows.length === 0}>
        {rows.map((session) => (
          <li key={session.name} className="session-row">
            <Tooltip tip={<SessionTip session={session} />}>
              <NavLink to={sessionPath(session.name)} className="session-link">
                <span className="session-name">{session.name}</span>
                <span className="session-about">{about(session)}</span>
                {session.status !== "running" && session.status !== "stopped" && <Status status={session.status} />}
              </NavLink>
            </Tooltip>
            <SessionRowMenu name={session.name} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function Status({ status }: { status: SessionStatus }) {
  return <span className={`status status-${status}`}>{STATUS[status]}</span>;
}

export function NoSession() {
  useTitle("Sessions");
  const loaded = useOutletContext<Loaded>();
  if (loaded && "sessions" in loaded && loaded.sessions.length === 0) {
    return <p className="empty">No sessions yet. Start one with Launch.</p>;
  }
  return <p className="empty">Select a session</p>;
}

const TAB_NAMES: Record<Tab, string> = {
  activity: "Activity",
  agents: "Agents",
  flows: "Flows",
  artifacts: "Artifacts",
};

// The tabs whose page without an item has a search in the tab bar, by its name; the search
// is the address's ?find=, which the tab reads.
const FINDS: Partial<Record<Tab, string>> = { flows: "Find a run" };

const TAB_ICONS: Record<Tab, typeof ActivityIcon> = {
  activity: ActivityIcon,
  agents: AgentsIcon,
  flows: FlowsIcon,
  artifacts: ArtifactsIcon,
};

export function Session() {
  const { name = "", tab = "activity", item } = useParams();
  const loaded = useOutletContext<Loaded>();
  // Only the Flows, Agents and Artifacts tabs have pages of their own: their runs', agents'
  // and artifacts'.
  if (!isTab(tab) || (item !== undefined && tab === "activity")) return <NotFound />;
  return <SessionTab name={name} tab={tab} item={item} loaded={loaded} />;
}

function SessionTab({ name, tab, item, loaded }: { name: string; tab: Tab; item?: string; loaded: Loaded }) {
  useTitle("Sessions");
  const started = (useLocation().state as StartedState | null)?.started;
  if (loaded === null || "error" in loaded) return null; // the list, or its strip, says what is wrong
  // Just started here: the change feed may bring it a moment after the start's answer.
  const session =
    loaded.sessions.find((one) => one.name === name) ?? (started?.session.name === name ? started.session : undefined);
  if (session === undefined) {
    return (
      <div className="empty">
        <p>Session {name} not found</p>
        <Link to="/sessions">All sessions</Link>
      </div>
    );
  }
  return (
    // The panel keeps its terminals while the tabs change: keyed by the session only.
    <TerminalPanel key={name} session={name}>
      <SessionView name={name} tab={tab} item={item} session={session} />
    </TerminalPanel>
  );
}

function SessionView({ name, tab, item, session }: { name: string; tab: Tab; item?: string; session: SessionInfo }) {
  const live = useLiveStore();
  const runs = useLive().runs[name] ?? null;
  const agents = useLive().agents[name] ?? null;
  useEffect(() => live.watch("runs", name), [live, name]);
  useEffect(() => live.watch("agents", name), [live, name]);
  const counts: Partial<Record<Tab, number>> = {
    flows: runs && "items" in runs ? runs.items.filter(isOpen).length : 0,
    agents: agents && "items" in agents ? agents.items.length : 0,
  };
  const stopped = session.status === "stopped";
  const view = useSearchParams()[0].get(VIEW_PARAM); // a chip's record, in the panel over the tab
  return (
    <section className="session" aria-label={`Session ${name}`}>
      <SessionHead session={session} />
      <StartedNotice name={name} />
      <nav className="tab-bar session-tabs" aria-label="Session sections">
        {TABS.map((one) => {
          const SectionIcon = TAB_ICONS[one];
          return (
            <Link
              key={one}
              to={sessionPath(name, one)}
              className="tab-item"
              aria-current={one === tab ? "page" : undefined}
            >
              <SectionIcon />
              {TAB_NAMES[one]}
              {counts[one] ? (
                <>
                  {" "}
                  {/* Named "Agents · 3"; the dot is for the ear only. */}
                  <span className="tab-count">
                    <span className="visually-hidden">·</span> {counts[one]}
                  </span>
                </>
              ) : null}
            </Link>
          );
        })}
        {FINDS[tab] !== undefined && item === undefined && <Find key={tab} label={FINDS[tab]} />}
      </nav>
      {tab === "agents" ? (
        <Agents session={name} agent={item} stopped={stopped} />
      ) : tab === "activity" ? (
        <Activity session={name} stopped={stopped} />
      ) : tab === "flows" ? (
        <Flows session={name} run={item} stopped={stopped} />
      ) : (
        <Artifacts session={name} artifact={item} />
      )}
      {view && <ArtifactPanel session={name} record={view} />}
    </section>
  );
}

// A tab's search at the right end of the tab bar: a magnifier that opens a field on a click
// or "/" (not while typing in another field: an input, a textarea, a select, an editable
// element, xterm's own textarea too). The field writes the address's ?find= in place, so
// typing adds no step to the browser's history; the other parameters stay, and an empty
// search drops it. Esc clears and closes it; left empty, it closes; with text, it stays.
function Find({ label }: { label: string }) {
  const [params, setParams] = useSearchParams();
  const query = params.get(FIND_PARAM) ?? "";
  const [opened, setOpened] = useState(false);
  const [focus, setFocus] = useState(0); // bumped to focus the field once it is drawn
  const field = useRef<HTMLInputElement>(null);
  const shown = opened || query !== "";

  useEffect(() => {
    if (focus > 0) field.current?.focus();
  }, [focus]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest?.("input, textarea, select") || target?.isContentEditable) return;
      event.preventDefault();
      setOpened(true);
      setFocus((one) => one + 1);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const write = (value: string) =>
    setParams(
      (now) => {
        const next = new URLSearchParams(now);
        if (value === "") next.delete(FIND_PARAM);
        else next.set(FIND_PARAM, value);
        return next;
      },
      { replace: true, preventScrollReset: true },
    );
  return (
    <div className={shown ? "tab-find open" : "tab-find"}>
      {shown && (
        <input
          ref={field}
          type="search"
          className="search"
          placeholder={label}
          aria-label={label}
          value={query}
          onChange={(event) => write(event.target.value)}
          onBlur={(event) => event.currentTarget.value === "" && setOpened(false)}
          onKeyDown={(event) => {
            if (event.key !== "Escape") return;
            write("");
            setOpened(false);
          }}
        />
      )}
      <button
        type="button"
        className="icon-button"
        aria-label={label}
        title={`${label} (/)`}
        onClick={() => {
          setOpened(true);
          setFocus((one) => one + 1);
        }}
      >
        <FindIcon />
      </button>
    </div>
  );
}

// The session's head (docs/design/ui.md, Structure and Session head): its name, status and
// how long it ran, Copy link and its actions; below, small, its folder (Copy path on the
// folder's icon), its git remote and branch (Copy URL on the git icon), its kits and its
// agents' CLI with the permission mode; the versions in their tooltips. Until its about
// comes, or when it fails, the line has the session's settings alone.
function SessionHead({ session }: { session: SessionInfo }) {
  const { name, repo, kits, provider, permission_mode: mode } = session;
  const about = useAbout(session);
  const repository = about?.repos[0];
  const cli = about?.provider;
  return (
    <header className="session-head">
      <div className="session-title">
        <h2 title={name}>{name}</h2>
        <Status status={session.status} />
        <Ran session={session} />
        <div className="session-head-actions">
          <CopyButton
            label="Copy link"
            copied="Link copied"
            text={sessionLink(name)}
            field={{ title: `Link to ${name}`, label: "Link" }}
            icon={<LinkIcon />}
          />
          <SessionActions session={session} />
        </div>
      </div>
      <div className="session-meta">
        <span className="session-folder">
          <CopyButton
            label="Copy path"
            copied="Path copied"
            text={repo}
            field={{ title: `Path of ${name}`, label: "Path" }}
            icon={<FolderIcon />}
          />
          {/* Cut at its start, so the end of the path stays in view. */}
          <span className="session-path" title={repo}>
            <bdi>{repo}</bdi>
          </span>
        </span>
        {repository && <GitFact name={name} repo={repository} />}
        <span className="session-fact">
          <KitsIcon />
          <span className="session-kits">
            {kits.map((kit, at) => {
              const found = about?.kits.find((one) => one.name === kit);
              return (
                <span key={kit}>
                  {at > 0 && ", "}
                  {found ? (
                    <Tooltip tip={<KitTip kit={found} />}>
                      <span className="session-kit session-hint" tabIndex={0}>
                        {kit}
                      </span>
                    </Tooltip>
                  ) : (
                    kit
                  )}
                </span>
              );
            })}
          </span>
        </span>
        <span className="session-fact">
          <AgentCliIcon />
          <span className="session-agent-cli">
            {cli ? (
              <Tooltip tip={<CliTip cli={cli} />}>
                <span className="session-hint" tabIndex={0}>
                  {provider}
                </span>
              </Tooltip>
            ) : (
              provider
            )}
            {cli?.warning && (
              <span role="img" aria-label="untested version" className="session-warn">
                !
              </span>
            )}
            {mode && ` · ${mode}`}
          </span>
        </span>
      </div>
    </header>
  );
}

const NEXT_AGENT = "installed now: the next agent starts with it";

// The session's about, asked when its head opens and again when what it is read from may
// have changed: the session's folder, kits or provider, or an installed kit (the feed's
// `kits`). No change in the feed says the CLI's version changed: it is read at the head's
// opening only.
function useAbout(session: SessionInfo): SessionAbout | null {
  const kitChanges = useLive().kitChanges;
  const [about, setAbout] = useState<SessionAbout | null>(null);
  const { name, repo, provider } = session;
  const kits = session.kits.join("\n");
  useEffect(() => {
    let current = true;
    getSessionAbout(name).then(
      (got) => current && setAbout(got),
      () => current && setAbout(null),
    );
    return () => {
      current = false;
    };
  }, [name, repo, kits, provider, kitChanges]);
  return about;
}

// The repository's remote, short, and its branch; the remote's whole URL is copied from
// the git icon and shown in the tooltip with the branch and the path.
function GitFact({ name, repo }: { name: string; repo: RepoInfo }) {
  const { remote, branch, path } = repo;
  if (!remote && !branch) return null;
  const text = [remote && shortRemote(remote), branch].filter(Boolean).join(" · ");
  const where = [branch && `branch ${branch}`, path].filter(Boolean).join(" · ");
  return (
    <span className="session-fact session-git">
      {remote ? (
        <CopyButton
          label="Copy URL"
          copied="URL copied"
          text={remote}
          field={{ title: `Remote of ${name}`, label: "URL" }}
          icon={<GitIcon />}
        />
      ) : (
        <GitIcon />
      )}
      <Tooltip
        tip={
          <>
            {remote && <div className="tooltip-line">{remote}</div>}
            <div className="tooltip-line">{where}</div>
          </>
        }
      >
        <span className="session-hint" tabIndex={0}>
          {text}
        </span>
      </Tooltip>
    </span>
  );
}

function KitTip({ kit }: { kit: SessionKitInfo }) {
  if (!kit.valid) {
    return (
      <div className="tooltip-line">
        <b>{kit.name}</b>: {kit.problem}
      </div>
    );
  }
  return (
    <>
      <div className="tooltip-line">
        <b>{kit.name}</b> v{kit.version}
      </div>
      <div className="tooltip-line">{kit.source}</div>
      <div className="tooltip-line">{NEXT_AGENT}</div>
    </>
  );
}

function CliTip({ cli }: { cli: ProviderInfo }) {
  if (!cli.installed) {
    return (
      <div className="tooltip-line">
        <b>{cli.title}</b> not installed: {cli.detail}
      </div>
    );
  }
  return (
    <>
      <div className="tooltip-line">
        <b>{cli.title}</b> {cli.version || cli.detail}
      </div>
      {cli.warning && <div className="tooltip-line session-warn">tested with {cli.tested_version}</div>}
      <div className="tooltip-line">{NEXT_AGENT}</div>
    </>
  );
}

const TICK_MS = 60_000; // how often the times in a session's head are counted on

// How long the session ran: while it runs, its closed spans and the time since its last
// start; stopped, how long ago too; both counted on each minute.
function Ran({ session }: { session: SessionInfo }) {
  const { running_since: since, stopped_at: stopped } = session;
  const from = since ?? stopped; // the time counted from
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    if (!from) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), TICK_MS);
    return () => clearInterval(timer);
  }, [from]);
  const seconds = (iso: string) => Math.max(0, (now - new Date(iso).getTime()) / 1000);
  const ran = duration(session.ran_seconds + (since ? seconds(since) : 0), true);
  const text = since ? ran : stopped ? `stopped ${duration(seconds(stopped))} ago · ran ${ran}` : `ran ${ran}`;
  return <span className="session-ran">{text}</span>;
}

// What a start or resume from the New session window said: the settings a resume changed,
// open runs that cannot go on as they are, and its warnings (e.g. what the supervisor's CLI
// asks the human before it starts), until the human closes it.
function StartedNotice({ name }: { name: string }) {
  const location = useLocation();
  const navigate = useNavigate();
  const started = (location.state as StartedState | null)?.started;
  if (!started || started.session.name !== name) return null;
  const { changes, problems, resumed, warnings } = started;
  if (changes.length === 0 && problems.length === 0 && warnings.length === 0) return null;
  const close = () => navigate(`${location.pathname}${location.search}`, { replace: true, state: null });
  return (
    <div className="started-notice">
      {changes.length > 0 && (
        <div role="status">
          <span>{resumed ? "Resumed with new settings:" : "Started:"}</span>
          <ul>
            {changes.map((change) => (
              <li key={change}>{change}</li>
            ))}
          </ul>
        </div>
      )}
      {problems.length > 0 && (
        <div role="alert" className="started-problems">
          <span>Open runs that cannot go on as they are:</span>
          <ul>
            {problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        </div>
      )}
      {warnings.length > 0 && (
        <div role="alert" className="started-problems">
          <span>Warnings:</span>
          <ul>
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
      <button type="button" className="quiet" onClick={close}>
        Close
      </button>
    </div>
  );
}

// The Activity tab: the team, the switch for the agents' messages to each other (it changes
// only what the feed shows, and is remembered), and the feed with the composer.
function Activity({ session, stopped }: { session: string; stopped: boolean }) {
  const [agentMessages, setAgentMessages] = useState(storedAgentMessages);
  return (
    <div className="activity">
      <div className="team-row">
        <Team session={session} />
        <label className="switch">
          <input
            type="checkbox"
            checked={agentMessages}
            onChange={(event) => {
              setAgentMessages(event.target.checked);
              storeAgentMessages(event.target.checked);
            }}
          />
          Show agent messages
        </label>
      </div>
      <Chat session={session} stopped={stopped} agentMessages={agentMessages} />
    </div>
  );
}
