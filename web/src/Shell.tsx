// The frame around every page: the rail of sections on the left (with Launch after Home),
// the top bar with the page's title, or a head the page draws there (useTopBar), and the
// change feed's link, and the page itself. The one place that handles a 401: it shows the server's own message
// instead of the page. It holds the tab's one change feed (live.ts) for every page, and the
// New session window (Launch.tsx).
import {
  createContext,
  Fragment,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { NavLink, Outlet } from "react-router";

import { getHealth, getUpdate, onDenied } from "./api";
import {
  CollapseIcon,
  HomeIcon,
  KitsIcon,
  LaunchIcon,
  NeedsYouIcon,
  ProjectsIcon,
  SessionsIcon,
  SettingsIcon,
} from "./icons";
import { LaunchProvider, useLaunch } from "./Launch";
import { isLive, Live, LiveContext, useLive } from "./live";
import { Notifier } from "./Notifications";
import { reloadedFor, storeRailCollapsed, storeReloadedFor, storedRailCollapsed } from "./prefs";
import { Tooltip } from "./Tooltip";
import { BUNDLE_VERSION } from "./version";

const NEEDS_YOU = "/needs-you"; // its link counts what waits

const SECTIONS: { to: string; name: string; icon: ReactNode }[] = [
  { to: "/", name: "Home", icon: <HomeIcon /> },
  { to: NEEDS_YOU, name: "Needs you", icon: <NeedsYouIcon /> },
  { to: "/sessions", name: "Sessions", icon: <SessionsIcon /> },
  { to: "/projects", name: "Projects", icon: <ProjectsIcon /> },
  { to: "/kits", name: "Kits", icon: <KitsIcon /> },
];

const TitleContext = createContext<(title: string) => void>(() => {});

// A page names itself; the top bar and the browser tab show it.
export function useTitle(title: string): void {
  const setTitle = useContext(TitleContext);
  useLayoutEffect(() => setTitle(title), [setTitle, title]);
}

type TopBar = { slot: HTMLElement | null; claim: () => () => void };

const TopBarContext = createContext<TopBar>({ slot: null, claim: () => () => {} });

// A page with a head of its own draws it in the top bar, in place of the Shell's title
// (docs/design/ui.md, Session head): it renders into the element this returns with
// createPortal. The element is the top bar's slot, kept by the Shell in state through a
// callback ref, so its arrival renders the page again; null until it exists, and the page
// draws nothing there until then. The page claims the bar in a layout effect and gives it
// back in the effect's cleanup; the claims are counted, so a StrictMode remount (mount,
// unmount, mount) leaves the bar claimed and the Shell's title never shows between. The
// Shell draws its title only while no page claims the bar.
export function useTopBar(): HTMLElement | null {
  const { slot, claim } = useContext(TopBarContext);
  useLayoutEffect(claim, [claim]);
  return slot;
}

export function Shell() {
  const [title, setTitle] = useState("");
  const [slot, setSlot] = useState<HTMLElement | null>(null);
  const [claims, setClaims] = useState(0);
  const claim = useCallback(() => {
    setClaims((now) => now + 1);
    return () => setClaims((now) => now - 1);
  }, []);
  const topBar = useMemo(() => ({ slot, claim }), [slot, claim]);
  const [collapsed, setCollapsed] = useState(storedRailCollapsed);
  const [denied, setDenied] = useState<string | null>(null);
  const [live] = useState(() => new Live());

  useEffect(() => {
    const off = onDenied(setDenied);
    // The one stream of this tab: without the token it learns so, also on a page that
    // reads no data.
    live.start();
    return () => {
      live.stop();
      off();
    };
  }, [live]);

  const toggle = () => {
    setCollapsed(!collapsed);
    storeRailCollapsed(!collapsed);
  };

  const frame = (
    <div className={`app${collapsed ? " collapsed" : ""}`}>
      <TabTitle title={title} />
      <Notifier />
      <nav className="rail" aria-label="Sections">
        <div className="rail-head">
          <span className="mark">LADO</span>
          <button
            type="button"
            className="ghost"
            aria-expanded={!collapsed}
            aria-label={collapsed ? "Expand menu" : "Collapse menu"}
            title={collapsed ? "Expand menu" : "Collapse menu"}
            onClick={toggle}
          >
            <CollapseIcon collapsed={collapsed} />
          </button>
        </div>
        <ul>
          {SECTIONS.map((section) => (
            <Fragment key={section.to}>
              <li>
                {section.to === NEEDS_YOU ? (
                  <NeedsYouLink {...section} collapsed={collapsed} />
                ) : (
                  <RailLink {...section} collapsed={collapsed} />
                )}
              </li>
              {section.to === "/" && (
                <li>
                  <LaunchLink collapsed={collapsed} />
                </li>
              )}
            </Fragment>
          ))}
        </ul>
        <div className="rail-bottom">
          <RailLink to="/settings" name="Settings" icon={<SettingsIcon />} collapsed={collapsed} />
        </div>
      </nav>
      <div className="main">
        <header className="topbar">
          {claims === 0 && <h1>{title}</h1>}
          <div ref={setSlot} className="topbar-slot" />
          <LinkState />
        </header>
        <VersionBanner />
        <UpdateLine />
        <main className="content">
          {denied !== null ? (
            <p className="problem" role="alert">
              {denied}
            </p>
          ) : (
            <TitleContext.Provider value={setTitle}>
              <TopBarContext.Provider value={topBar}>
                <Outlet />
              </TopBarContext.Provider>
            </TitleContext.Provider>
          )}
        </main>
      </div>
    </div>
  );
  return (
    <LiveContext.Provider value={live}>
      <LaunchProvider>{frame}</LaunchProvider>
    </LiveContext.Provider>
  );
}

// A server of another LADO version than this bundle's answers an API this page does not
// know. Asked each time the change feed opens, so also after the server restarted. Mostly
// the tab is the old one (opened before an upgrade): a reload is enough. Only when the
// page is still another version after reloading for this server is the server the old
// one (left running across an upgrade): then it says to restart it.
function VersionBanner() {
  const { link } = useLive();
  const [server, setServer] = useState<string | null>(null);
  useEffect(() => {
    if (link !== "open") return;
    let current = true;
    getHealth().then(
      (health) => current && setServer(health.version),
      () => {}, // the feed's link says when the server cannot be reached
    );
    return () => {
      current = false;
    };
  }, [link]);
  useEffect(() => {
    if (server === BUNDLE_VERSION) storeReloadedFor(null);
  }, [server]);
  if (server === null || server === BUNDLE_VERSION) return null;
  if (reloadedFor() === server) {
    return (
      <p className="problem version-banner" role="alert">
        This page is LADO {BUNDLE_VERSION}, the server runs {server}, also after a reload: run{" "}
        <code>lado server stop</code>, then <code>lado ui</code>.
      </p>
    );
  }
  const reload = () => {
    storeReloadedFor(server);
    window.location.reload();
  };
  return (
    <p className="problem version-banner" role="alert">
      This page is LADO {BUNDLE_VERSION}, the server runs {server}: reload the page.
      <button type="button" className="primary" onClick={reload}>
        Reload
      </button>
    </p>
  );
}

// A newer LADO on PyPI, as the server's daily check found it: one quiet line. Asked, like
// the version, each time the change feed opens.
function UpdateLine() {
  const { link } = useLive();
  const [available, setAvailable] = useState<string | null>(null);
  useEffect(() => {
    if (link !== "open") return;
    let current = true;
    getUpdate().then(
      (update) => current && setAvailable(update.available ?? null),
      () => {}, // no line: `lado doctor` says why the check failed
    );
    return () => {
      current = false;
    };
  }, [link]);
  if (available === null) return null;
  return (
    <p className="update-line">
      LADO {available} is available: run <code>lado update</code>
    </p>
  );
}

// The change feed's link: live, or reconnecting while it is down (what the page shows may
// be old), with the reason. The server's address is in its tooltip.
function LinkState() {
  const { link, problem } = useLive();
  if (link === "refused") return null; // the page says how to get in
  if (link !== "down") {
    return (
      <Tooltip tip={`The LADO server this page talks to: ${window.location.host}`}>
        <span className={`link link-${link}`} role="status" tabIndex={0}>
          <span className="link-word">{link === "open" ? "live" : "connecting…"}</span>
        </span>
      </Tooltip>
    );
  }
  return (
    <span className="link reconnecting" role="status" title={problem ?? undefined}>
      reconnecting…{problem && <span className="reconnecting-why"> {problem}</span>}
    </span>
  );
}

// What waits for the human: the sum of the sessions' counts, of those not stopped (the
// server's rule; the length of /api/waiting).
function useWaitingCount(): number {
  const loaded = useLive().sessions;
  if (loaded === null || "error" in loaded) return 0;
  return loaded.sessions.filter(isLive).reduce((sum, one) => {
    const { gates, questions, agents } = one.waiting;
    return sum + gates + questions + agents;
  }, 0);
}

// The browser tab names the page, and with something waiting its count first: "(2) …".
function TabTitle({ title }: { title: string }) {
  const waiting = useWaitingCount();
  useEffect(() => {
    const named = title ? `${title} · LADO` : "LADO";
    document.title = waiting > 0 ? `(${waiting}) ${named}` : named;
  }, [title, waiting]);
  return null;
}

function RailLink(props: { to: string; name: string; icon: ReactNode; collapsed: boolean; count?: number }) {
  const label = props.count ? `${props.name}, ${props.count} waiting` : props.name;
  return (
    <NavLink
      to={props.to}
      end={props.to === "/"}
      className="rail-link"
      aria-label={label}
      title={props.collapsed ? label : undefined}
    >
      {props.icon}
      <span className="rail-name">{props.name}</span>
      {props.count ? (
        <span className="rail-count" aria-hidden="true">
          {props.count}
        </span>
      ) : null}
    </NavLink>
  );
}

function NeedsYouLink(props: { to: string; name: string; icon: ReactNode; collapsed: boolean }) {
  return <RailLink {...props} count={useWaitingCount()} />;
}

// Launch on the rail: it opens the New session window, as the session list's "+" does.
function LaunchLink({ collapsed }: { collapsed: boolean }) {
  const launch = useLaunch();
  return (
    <button
      type="button"
      className="rail-link"
      aria-label="Launch"
      title={collapsed ? "Launch" : undefined}
      onClick={() => launch()}
    >
      <LaunchIcon />
      <span className="rail-name">Launch</span>
    </button>
  );
}
