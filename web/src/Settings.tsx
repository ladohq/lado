// Settings (docs/design/ui.md, Settings): a page per section beside the list of their names
// and icons (settingsSections.ts), /settings/<section>. On a computer and a tablet /settings
// opens General; on a phone it is the list alone, and a section is its own page with
// "‹ Settings". Old addresses go to their new pages, replacing the history entry.
import { useEffect, useRef, type JSX } from "react";
import { Navigate, NavLink, Outlet, useLocation, useParams } from "react-router";

import { GeneralPage } from "./General";
import { ChevronIcon } from "./icons";
import { ModelSettings } from "./ModelSettings";
import { GENERAL_PATH } from "./paths";
import { usePhone } from "./phone";
import { Providers } from "./Providers";
import { SETTINGS_SECTIONS, sectionOf, settingsRedirect, type SectionSlug } from "./settingsSections";
import { useTitle } from "./Shell";
import { StatisticsSetting } from "./Telemetry";

const PAGES: Record<SectionSlug, () => JSX.Element> = {
  general: GeneralPage,
  "agent-clis": Providers,
  "model-servers": ModelSettings,
  statistics: StatisticsSetting,
};

export function Settings() {
  const phone = usePhone() !== null;
  const { section } = useParams();
  // On a phone, where the page stands alone, the top bar names its section.
  useTitle((phone && sectionOf(section)?.name) || "Settings");
  const { hash } = useLocation();
  const page = useRef<HTMLDivElement>(null);
  // The focus goes to the page's h2 when the human moves from one section, or from the
  // phone's list, to another; not on the first load, nor on an arrival at a row's anchor,
  // which places the focus itself (Providers.tsx, General.tsx).
  const shown = useRef<string | null>(null);
  const now = sectionOf(section) ? section! : phone && !section ? "list" : null;
  useEffect(() => {
    const before = shown.current;
    shown.current = now;
    if (before === null || now === null || now === "list" || before === now || hash) return;
    page.current?.querySelector<HTMLElement>(".spage-head h2")?.focus();
  }, [now, hash]);
  const listed = !phone || !section;
  return (
    <div className={`settings${phone ? (section ? " at-page" : " at-list") : ""}`}>
      {listed && (
        <nav className="snav" aria-label="Settings sections">
          <ul>
            {SETTINGS_SECTIONS.map(({ slug, name, icon: Icon }) => (
              <li key={slug}>
                <NavLink className="snav-item" to={`/settings/${slug}`}>
                  <span className="snav-ic">
                    <Icon />
                  </span>
                  <span className="snav-name">{name}</span>
                  {phone && (
                    <span className="snav-chev">
                      <ChevronIcon />
                    </span>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      )}
      <div className="settings-page" ref={page}>
        <Outlet />
      </div>
    </div>
  );
}

// /settings: an old anchor goes to its page; a computer or a tablet opens General, a phone
// shows the list alone.
export function SettingsIndex() {
  const phone = usePhone() !== null;
  const { pathname, hash } = useLocation();
  const to = settingsRedirect(pathname, hash) ?? (phone ? null : GENERAL_PATH);
  return to ? <Navigate to={to} replace /> : null;
}

// /settings/<section>: its page, or where an old or unknown section goes.
export function SettingsSection() {
  const { section } = useParams();
  const { pathname, hash } = useLocation();
  const to = settingsRedirect(pathname, hash);
  if (to) return <Navigate to={to} replace />;
  const Page = PAGES[section as SectionSlug];
  return <Page />;
}
