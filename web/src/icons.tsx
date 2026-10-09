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

// A magnifier: a tab's search.
export const FindIcon = () => (
  <Icon>
    <circle cx="10.5" cy="10.5" r="6" />
    <path d="m15 15 5 5" />
  </Icon>
);

// A plus in a square: a new session.
export const LaunchIcon = () => (
  <Icon>
    <rect x="4" y="4" width="16" height="16" rx="3" />
    <path d="M12 8.5v7M8.5 12h7" />
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

export const SettingsIcon = () => (
  <Icon>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 3.5v2.2M12 18.3v2.2M3.5 12h2.2M18.3 12h2.2M6 6l1.6 1.6M16.4 16.4 18 18M6 18l1.6-1.6M16.4 7.6 18 6" />
  </Icon>
);

// A column collapses to a strip at its side: the terminal panel on the right, the session
// list on the left.
export const CollapsePanelIcon = ({ side = "right" }: { side?: "left" | "right" }) => (
  <Icon>
    <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
    {side === "right" ? (
      <>
        <path d="M15 4.5v15" />
        <path d="m9 10 2 2-2 2" />
      </>
    ) : (
      <>
        <path d="M9 4.5v15" />
        <path d="m15 10-2 2 2 2" />
      </>
    )}
  </Icon>
);

// Something could not be loaded: what, in its tooltip.
export const ProblemIcon = () => (
  <Icon>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5v5.5M12 16.2v.3" />
  </Icon>
);

// A terminal over the page (arrows out), or back in its panel (arrows in).
export const ExpandIcon = ({ expanded }: { expanded: boolean }) => (
  <Icon>
    {expanded ? (
      <path d="M19 5l-5 5M14 6v4h4M5 19l5-5M10 18v-4H6" />
    ) : (
      <path d="M14 4h6v6M20 4l-6 6M10 20H4v-6M4 20l6-6" />
    )}
  </Icon>
);

export const CollapseIcon = ({ collapsed }: { collapsed: boolean }) => (
  <Icon>
    <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
    <path d="M9 4.5v15" />
    {collapsed ? <path d="m13 10 2 2-2 2" /> : <path d="m15 10-2 2 2 2" />}
  </Icon>
);

// A chevron down: an open group; turned to the right (CSS) when it is folded.
export const ChevronIcon = () => (
  <Icon>
    <path d="m6 9 6 6 6-6" />
  </Icon>
);

// A session's actions in its head: Stop (a square filled with the text's colour, no stroke
// around it), Resume (a triangle), Forget (a bin).
export const StopIcon = () => (
  <Icon>
    <rect x="7" y="7" width="10" height="10" rx="1.5" fill="currentColor" stroke="none" />
  </Icon>
);

export const ResumeIcon = () => (
  <Icon>
    <path d="M8 5.5v13l10-6.5z" />
  </Icon>
);

export const ForgetIcon = () => (
  <Icon>
    <path d="M4.5 7h15M9.5 7V4.5h5V7M6.5 7l.9 12.5h9.2L17.5 7" />
    <path d="M10.5 10.5v5.5M13.5 10.5v5.5" />
  </Icon>
);

// In a session's head: Copy link (two chain links), Copy path (a folder), and before the
// agents' CLI a chip.
export const LinkIcon = () => (
  <Icon>
    <path d="M10.5 13.5a4 4 0 0 0 5.7.3l2.6-2.6a4 4 0 0 0-5.7-5.7l-1.3 1.3" />
    <path d="M13.5 10.5a4 4 0 0 0-5.7-.3l-2.6 2.6a4 4 0 0 0 5.7 5.7l1.3-1.3" />
  </Icon>
);

export const FolderIcon = ProjectsIcon;

// Two commits and a branch: a session's git repository.
export const GitIcon = () => (
  <Icon>
    <circle cx="7" cy="6" r="2" />
    <circle cx="7" cy="18" r="2" />
    <circle cx="17" cy="9" r="2" />
    <path d="M7 8v8M17 11c0 3-4 3-8.5 5.5" />
  </Icon>
);

export const AgentCliIcon = () => (
  <Icon>
    <rect x="6" y="6" width="12" height="12" rx="1.5" />
    <path d="M9.5 3v3M14.5 3v3M9.5 18v3M14.5 18v3M3 9.5h3M3 14.5h3M18 9.5h3M18 14.5h3" />
  </Icon>
);

// The session's sections, on their tabs.
// A speech bubble: Activity, the messages.
export const ActivityIcon = () => (
  <Icon>
    <path d="M3.75 5.25h16.5v10.5h-9l-4.5 3.75v-3.75h-3z" />
  </Icon>
);

// Two people: Agents.
export const AgentsIcon = () => (
  <Icon>
    <circle cx="9" cy="9" r="3.45" />
    <path d="M3 19.5c.75-3.3 3-4.95 6-4.95s5.25 1.65 6 4.95M15.75 6a3.3 3.3 0 0 1 0 6.3M18 14.85c1.5.75 2.55 2.25 3 4.65" />
  </Icon>
);

// A path between two points: Flows.
export const FlowsIcon = () => (
  <Icon>
    <circle cx="5.25" cy="6" r="2.4" />
    <circle cx="18.75" cy="18" r="2.4" />
    <path d="M7.65 6h6.6a3 3 0 0 1 0 6h-4.5a3 3 0 0 0 0 6h6.6" />
  </Icon>
);

// A page with a folded corner: Artifacts.
export const ArtifactsIcon = () => (
  <Icon>
    <path d="M6 3.75h7.5l4.5 4.5v12H6zM13.5 3.75v4.5H18M9 12.75h6M9 16.5h6" />
  </Icon>
);

// A flag on its pole: a flow gate's row in the feed.
export const GateIcon = () => (
  <Icon>
    <path d="M6 21V4M6 4.5h10.5l-2.25 4 2.25 4H6" />
  </Icon>
);

// An artifact's media type (artifacts.kindOf), on its chip, row and page.
// Markdown: a page of lines.
export const DocumentIcon = () => (
  <Icon>
    <path d="M7 3.5h7l4 4v13H7z" />
    <path d="M14 3.5v4h4M9.5 12h6M9.5 15h6M9.5 18h4" />
  </Icon>
);

// A clipboard with lines: the system info to copy for an issue.
export const ClipboardIcon = () => (
  <Icon>
    <rect x="8" y="3.5" width="8" height="3.5" rx="1" />
    <path d="M16 5h1.5a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-11a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2H8" />
    <path d="M9 12h6M9 16h4" />
  </Icon>
);

// Text and code: two angle brackets.
export const CodeIcon = () => (
  <Icon>
    <path d="M8.5 7 4 12l4.5 5M15.5 7 20 12l-4.5 5" />
  </Icon>
);

// HTML: a window with angle brackets.
export const HtmlIcon = () => (
  <Icon>
    <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
    <path d="M3.5 8.5h17M9.5 12.5 7.5 14.5l2 2M14.5 12.5l2 2-2 2" />
  </Icon>
);

// An image: a frame with a sun and hills.
export const ImageIcon = () => (
  <Icon>
    <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
    <circle cx="9" cy="10" r="1.6" />
    <path d="m4 18 5-5 4 4 2.5-2.5L20 19" />
  </Icon>
);

// Anything else: a page with binary digits.
export const BinaryIcon = () => (
  <Icon>
    <path d="M7 3.5h7l4 4v13H7z" />
    <path d="M14 3.5v4h4" />
    <rect x="9.5" y="11.5" width="2.5" height="4" rx="1" />
    <path d="M14.5 11.5v4M14 11.5h1" />
  </Icon>
);

// Download: an arrow down onto a line.
export const DownloadIcon = () => (
  <Icon>
    <path d="M12 4v11M7.5 10.5 12 15l4.5-4.5M5 19.5h14" />
  </Icon>
);

// Open in a new tab: an arrow out of a box.
export const OpenTabIcon = () => (
  <Icon>
    <path d="M13.5 4.5h6v6M19.5 4.5l-8 8M17.5 13.5v6h-13v-13h6" />
  </Icon>
);

// A shield with a check: HTML runs sandboxed.
export const ShieldIcon = () => (
  <Icon>
    <path d="M12 3.5 19 6v5.5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" />
    <path d="m9 12 2 2 4-4" />
  </Icon>
);

// Close: a cross.
export const CloseIcon = () => (
  <Icon>
    <path d="m6 6 12 12M18 6 6 18" />
  </Icon>
);

// A paperclip: attach files.
export const ClipIcon = () => (
  <Icon>
    <path d="M20 11.5 12.2 19.3a5 5 0 0 1-7.1-7.1l8-8a3.3 3.3 0 0 1 4.7 4.7l-8 8a1.7 1.7 0 0 1-2.4-2.4L14.8 7" />
  </Icon>
);

// An eye struck through: an agent cannot see what the file holds.
export const UnseenIcon = () => (
  <Icon>
    <path d="m4 4 16 16" />
    <path d="M9.9 5.3A9.6 9.6 0 0 1 12 5c4.6 0 8 4 9 7a11 11 0 0 1-2.5 3.8M6.4 6.5C4.4 7.8 3.2 9.9 3 12c1 3 4.4 7 9 7a9 9 0 0 0 4.6-1.3" />
    <path d="M10 10.2a2.6 2.6 0 0 0 3.7 3.7" />
  </Icon>
);
