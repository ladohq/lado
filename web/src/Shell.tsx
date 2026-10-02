// The frame around every page: the rail of sections on the left, the top bar with the
// page's title, the server's address and Launch, and the page itself. The one place that
// handles a 401: it shows the server's own message instead of the page.
import {
  createContext,
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { NavLink, Outlet } from "react-router";

import { getSessions, onDenied } from "./api";
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
import { storeRailCollapsed, storedRailCollapsed } from "./prefs";

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

  useEffect(() => {
    const off = onDenied(setDenied);
    // Ask once, so a page that reads no data still learns that the token is missing.
    getSessions().catch(() => {});
    return off;
  }, []);

  useEffect(() => {
    document.title = title ? `${title} · LADO` : "LADO";
  }, [title]);

  const toggle = () => {
    setCollapsed(!collapsed);
    storeRailCollapsed(!collapsed);
  };

  return (
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
          <Launch />
        </header>
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

// Starting a session from the UI comes later; until then Launch says how.
function Launch() {
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
    <div className="launch">
      <button
        ref={button}
        type="button"
        className="primary"
        aria-expanded={open}
        aria-controls="launch-info"
        onClick={() => setOpen(!open)}
      >
        Launch
      </button>
      {open && (
        <div
          ref={panel}
          id="launch-info"
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
