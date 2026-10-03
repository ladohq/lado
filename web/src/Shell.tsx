// The frame around every page: the rail of sections on the left, the top bar with the
// page's title, the server's address, the change feed's link and Launch, and the page
// itself. The one place that handles a 401: it shows the server's own message instead of the page. It holds the tab's
// one change feed (live.ts) for every page.
import {
  createContext,
  useContext,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { NavLink, Outlet } from "react-router";

import { getHealth, onDenied } from "./api";
import {
  CollapseIcon,
  HomeIcon,
  KitsIcon,
  MarketplaceIcon,
  NeedsYouIcon,
  ProjectsIcon,
  SessionsIcon,
  SettingsIcon,
} from "./icons";
import { Live, LiveContext, useLive } from "./live";
import { storeRailCollapsed, storedRailCollapsed } from "./prefs";
import { BUNDLE_VERSION } from "./version";

const SECTIONS: { to: string; name: string; icon: ReactNode }[] = [
  { to: "/", name: "Home", icon: <HomeIcon /> },
  { to: "/needs-you", name: "Needs you", icon: <NeedsYouIcon /> },
  { to: "/sessions", name: "Sessions", icon: <SessionsIcon /> },
  { to: "/projects", name: "Projects", icon: <ProjectsIcon /> },
  { to: "/kits", name: "Kits", icon: <KitsIcon /> },
  { to: "/marketplace", name: "Marketplace", icon: <MarketplaceIcon /> },
];

const TitleContext = createContext<(title: string) => void>(() => {});

// A page names itself; the top bar and the browser tab show it.
export function useTitle(title: string): void {
  const setTitle = useContext(TitleContext);
  useLayoutEffect(() => setTitle(title), [setTitle, title]);
}

export function Shell() {
  const [title, setTitle] = useState("");
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

  useEffect(() => {
    document.title = title ? `${title} · LADO` : "LADO";
  }, [title]);

  const toggle = () => {
    setCollapsed(!collapsed);
    storeRailCollapsed(!collapsed);
  };

  const frame = (
    <div className={`app${collapsed ? " collapsed" : ""}`}>
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
            <li key={section.to}>
              <RailLink {...section} collapsed={collapsed} />
            </li>
          ))}
        </ul>
        <div className="rail-bottom">
          <RailLink to="/settings" name="Settings" icon={<SettingsIcon />} collapsed={collapsed} />
        </div>
      </nav>
      <div className="main">
        <header className="topbar">
          <h1>{title}</h1>
          <span className="server" title="The LADO server this page talks to">
            {window.location.host}
          </span>
          <LinkState />
          <Launch variant="top" />
        </header>
        <VersionBanner />
        <main className="content">
          {denied !== null ? (
            <p className="problem" role="alert">
              {denied}
            </p>
          ) : (
            <TitleContext.Provider value={setTitle}>
              <Outlet />
            </TitleContext.Provider>
          )}
        </main>
      </div>
    </div>
  );
  return <LiveContext.Provider value={live}>{frame}</LiveContext.Provider>;
}

// A server of another LADO version than this bundle's (one left running across an
// upgrade, or upgraded under an open tab) answers an API this page does not know. Asked
// each time the change feed opens, so also after the server restarted.
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
  if (server === null || server === BUNDLE_VERSION) return null;
  return (
    <p className="problem version-banner" role="alert">
      This page is LADO {BUNDLE_VERSION}, the server runs {server}: run <code>lado server stop</code>, then{" "}
      <code>lado ui</code>.
    </p>
  );
}

// The change feed's link: live, or reconnecting while it is down (what the page shows may
// be old), with the reason.
function LinkState() {
  const { link, problem } = useLive();
  if (link === "refused") return null; // the page says how to get in
  if (link !== "down") {
    return (
      <span className={`link link-${link}`} role="status">
        {link === "open" ? "live" : "connecting…"}
      </span>
    );
  }
  return (
    <span className="link reconnecting" role="status" title={problem ?? undefined}>
      reconnecting…{problem && <span className="reconnecting-why"> {problem}</span>}
    </span>
  );
}

function RailLink(props: { to: string; name: string; icon: ReactNode; collapsed: boolean }) {
  return (
    <NavLink
      to={props.to}
      end={props.to === "/"}
      className="rail-link"
      aria-label={props.name}
      title={props.collapsed ? props.name : undefined}
    >
      {props.icon}
      <span className="rail-name">{props.name}</span>
    </NavLink>
  );
}

// Starting a session from the UI comes later; until then Launch (in the top bar, and the
// session list's "+") says how.
export function Launch({ variant }: { variant: "top" | "plus" }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    panel.current?.focus();
    const away = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!panel.current?.contains(target) && !button.current?.contains(target)) setOpen(false);
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);

  const close = () => {
    setOpen(false);
    button.current?.focus();
  };

  return (
    <div className={`launch launch-${variant}`}>
      <button
        ref={button}
        type="button"
        className={variant === "top" ? "primary" : "plus"}
        aria-label={variant === "top" ? undefined : "New session"}
        title={variant === "top" ? undefined : "New session"}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
      >
        {variant === "top" ? "Launch" : <span aria-hidden="true">+</span>}
      </button>
      {open && (
        <div
          ref={panel}
          id={id}
          className="popover"
          role="dialog"
          aria-label="Launch a session"
          tabIndex={-1}
          onKeyDown={(event) => event.key === "Escape" && close()}
        >
          <p>Starting a session from here comes later. For now, run this in a terminal:</p>
          <code className="command">lado start &lt;repo&gt;</code>
          <p className="muted">The session then shows up under Sessions.</p>
        </div>
      )}
    </div>
  );
}
