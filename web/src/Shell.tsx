// The frame around every page: the rail of sections on the left (with Launch after Home),
// the top bar with the page's title, or a head the page draws there (useTopBar), and the
// change feed's link, and the page itself. The one place that handles a 401: it shows the server's own message
// instead of the page. It holds the tab's one change feed (live.ts) for every page, and the
// New session window (Launch.tsx). On a phone (phone.ts) it says so on <html data-phone>,
// and the rail is a drawer that Menu, at the top bar's start, opens.
import {
  createContext,
  Fragment,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type Ref,
} from "react";
import { NavLink, Outlet } from "react-router";

import { getHealth, onDenied } from "./api";
import {
  BugIcon,
  CollapseIcon,
  HomeIcon,
  KitsIcon,
  LaunchIcon,
  MenuIcon,
  NeedsYouIcon,
  ProjectsIcon,
  SessionsIcon,
  SettingsIcon,
} from "./icons";
import { LaunchProvider, useLaunch } from "./Launch";
import { isLive, Live, LiveContext, useLive } from "./live";
import { Notifier } from "./Notifications";
import { NEEDS_YOU_PATH } from "./paths";
import { usePhone } from "./phone";
import { reloadedFor, storeRailCollapsed, storeReloadedFor, storedRailCollapsed } from "./prefs";
import { SelectionBar } from "./SelectionBar";
import { LiveButton, UpdateProvider, UpdateStatus } from "./SystemPanel";
import { StatisticsBanner } from "./Telemetry";
import { BUNDLE_VERSION } from "./version";

const SECTIONS: { to: string; name: string; icon: ReactNode }[] = [
  { to: "/", name: "Home", icon: <HomeIcon /> },
  { to: NEEDS_YOU_PATH, name: "Needs you", icon: <NeedsYouIcon /> },
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
  const phone = usePhone();

  // The key of styles.css's section "Phone layout".
  useLayoutEffect(() => {
    const root = document.documentElement;
    if (phone) root.dataset.phone = phone;
    else delete root.dataset.phone;
    return () => {
      delete root.dataset.phone;
    };
  }, [phone]);

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

  // On a phone the rail is a drawer that Menu opens over the page, always with its names
  // (the computer's collapsed rail is neither read nor written there). Choosing an item, the
  // dimmed page or Esc closes it, and the focus goes back to Menu.
  const [drawer, setDrawer] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const rail = useRef<HTMLElement>(null);
  const folded = phone === null && collapsed;
  const closeDrawer = useCallback(() => {
    setDrawer(false);
    menuButton.current?.focus();
  }, []);
  useEffect(() => {
    if (phone === null) setDrawer(false);
  }, [phone]);
  useEffect(() => {
    if (!drawer) return;
    rail.current?.querySelector<HTMLElement>(".rail-link")?.focus();
    const escape = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || (event.target as Element | null)?.closest?.("dialog")) return;
      closeDrawer();
    };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [drawer, closeDrawer]);

  const frame = (
    <div className={`app${folded ? " collapsed" : ""}`}>
      <TabTitle title={title} />
      <Notifier />
      <SelectionBar />
      {drawer && <button type="button" className="menu-scrim" aria-label="Close menu" onClick={closeDrawer} />}
      <nav
        ref={rail}
        className="rail"
        aria-label="Sections"
        data-open={drawer || undefined}
        onClick={(event) => {
          if (drawer && (event.target as Element).closest(".rail-link")) closeDrawer();
        }}
      >
        <div className="rail-head">
          <span className="mark">LADO</span>
          {phone === null && (
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
          )}
        </div>
        <ul>
          {SECTIONS.map((section) => (
            <Fragment key={section.to}>
              <li>
                {section.to === NEEDS_YOU_PATH ? (
                  <NeedsYouLink {...section} collapsed={folded} />
                ) : (
                  <RailLink {...section} collapsed={folded} />
                )}
              </li>
              {section.to === "/" && (
                <li>
                  <LaunchLink collapsed={folded} />
                </li>
              )}
            </Fragment>
          ))}
        </ul>
        <div className="rail-bottom">
          <RailLink to="/report" name="Report a bug" icon={<BugIcon />} collapsed={folded} />
          <RailLink to="/settings" name="Settings" icon={<SettingsIcon />} collapsed={folded} />
        </div>
      </nav>
      <div className="main">
        <header className="topbar">
          {phone !== null && <MenuButton ref={menuButton} open={drawer} onClick={() => setDrawer(!drawer)} />}
          {claims === 0 && <h1>{title}</h1>}
          <div ref={setSlot} className="topbar-slot" />
          <LinkState />
        </header>
        <VersionBanner />
        <UpdateStatus />
        <StatisticsBanner />
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
      <UpdateProvider>
        <LaunchProvider>{frame}</LaunchProvider>
      </UpdateProvider>
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

// The change feed's link: live, or reconnecting while it is down (what the page shows may
// be old), with the reason. Live opens the system panel (SystemPanel.tsx).
function LinkState() {
  const { link, problem } = useLive();
  if (link === "refused") return null; // the page says how to get in
  if (link !== "down") return <LiveButton link={link} />;
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

// Menu on a phone: the rail as a drawer; what waits counted on it, as on Needs you's link.
function MenuButton({ ref, open, onClick }: { ref: Ref<HTMLButtonElement>; open: boolean; onClick: () => void }) {
  const count = useWaitingCount();
  return (
    <button
      ref={ref}
      type="button"
      className="ghost menu-button"
      aria-label={count ? `Menu, ${count} waiting` : "Menu"}
      aria-expanded={open}
      onClick={onClick}
    >
      <MenuIcon />
      {count ? (
        <span className="rail-count" aria-hidden="true">
          {count}
        </span>
      ) : null}
    </button>
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
