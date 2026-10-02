// Inline SVG icons: 24-unit grid, 1.6 strokes in the text's colour. Decorative only: the
// control that holds one carries the name (aria-label).
import type { ReactNode } from "react";

function Icon({ children }: { children: ReactNode }) {
  return (
    <svg
      className="icon"
      viewBox="0 0 24 24"
      width="20"
      height="20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

export const HomeIcon = () => (
  <Icon>
    <path d="M4 10.5 12 4l8 6.5" />
    <path d="M6 9v10h12V9" />
    <path d="M10 19v-5h4v5" />
  </Icon>
);

// A raised hand: someone waits for the human.
export const NeedsYouIcon = () => (
  <Icon>
    <path d="M8 13V6.5a1.5 1.5 0 0 1 3 0V12" />
    <path d="M11 11V4.5a1.5 1.5 0 0 1 3 0V12" />
    <path d="M14 11V6a1.5 1.5 0 0 1 3 0v7c0 4-2.5 7-6 7-2.5 0-3.8-1.2-5.2-3.4L4.2 14a1.4 1.4 0 0 1 2.3-1.6L8 14" />
  </Icon>
);

export const SessionsIcon = () => (
  <Icon>
    <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
    <path d="m7.5 9.5 3 2.5-3 2.5" />
    <path d="M12.5 15h4" />
  </Icon>
);

export const ProjectsIcon = () => (
  <Icon>
    <path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2v7.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z" />
  </Icon>
);

export const KitsIcon = () => (
  <Icon>
    <path d="m12 3.5 8 4v9l-8 4-8-4v-9z" />
    <path d="m4 7.5 8 4 8-4" />
    <path d="M12 11.5v9" />
  </Icon>
);

export const MarketplaceIcon = () => (
  <Icon>
    <path d="M4.5 9.5 6 4.5h12l1.5 5" />
    <path d="M4.5 9.5a2.5 2.5 0 0 0 5 0 2.5 2.5 0 0 0 5 0 2.5 2.5 0 0 0 5 0" />
    <path d="M5.5 11.5v8h13v-8" />
    <path d="M10 19.5v-4h4v4" />
  </Icon>
);

export const SettingsIcon = () => (
  <Icon>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 3.5v2.2M12 18.3v2.2M3.5 12h2.2M18.3 12h2.2M6 6l1.6 1.6M16.4 16.4 18 18M6 18l1.6-1.6M16.4 7.6 18 6" />
  </Icon>
);

export const CollapseIcon = ({ collapsed }: { collapsed: boolean }) => (
  <Icon>
    <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
    <path d="M9 4.5v15" />
    {collapsed ? <path d="m13 10 2 2-2 2" /> : <path d="m15 10-2 2 2 2" />}
  </Icon>
);
