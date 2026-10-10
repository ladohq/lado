// The UI's addresses (docs/design/ui.md, Structure). Every name in a path is one segment,
// encoded whole with encodeURIComponent: session names are free text, run names hold "/".

export const TABS = ["activity", "agents", "flows", "artifacts"] as const;
export type Tab = (typeof TABS)[number];

export const isTab = (tab: string): tab is Tab => (TABS as readonly string[]).includes(tab);

export function sessionPath(name: string, tab?: Tab): string {
  const path = `/sessions/${encodeURIComponent(name)}`;
  return tab ? `${path}/${tab}` : path;
}

// The session page's whole address, without the token (the login is the browser's cookie).
export function sessionLink(name: string): string {
  return `${window.location.origin}${sessionPath(name)}`;
}

// A flow run's page in the session's Flows tab: /sessions/<name>/flows/<run, encoded whole>.
export const runPath = (session: string, run: string) => `${sessionPath(session, "flows")}/${encodeURIComponent(run)}`;

// A live agent's page in the session's Agents tab: /sessions/<name>/agents/<agent>.
export const agentPath = (session: string, agent: string) =>
  `${sessionPath(session, "agents")}/${encodeURIComponent(agent)}`;

// The address's parameter of a tab's search (the tab bar's Find, Sessions.tsx: FINDS).
export const FIND_PARAM = "find";

// The address's parameter that opens an agent's terminal on its session's page.
export const TERMINAL_PARAM = "terminal";

export const terminalPath = (session: string, agent: string) =>
  `${sessionPath(session, "activity")}?${TERMINAL_PARAM}=${encodeURIComponent(agent)}`;

// An artifact's page in the session's Artifacts tab: /sessions/<name>/artifacts/<id>, its
// latest record, or with ?record= the record an attachment keeps.
export const RECORD_PARAM = "record";

export const artifactPath = (session: string, id: string, record?: string) =>
  `${sessionPath(session, "artifacts")}/${encodeURIComponent(id)}${
    record ? `?${RECORD_PARAM}=${encodeURIComponent(record)}` : ""
  }`;

// One record alone in a bare page outside the Shell (ArtifactTab): /view/<session>/<record>.
export const viewPath = (session: string, record: string) =>
  `/view/${encodeURIComponent(session)}/${encodeURIComponent(record)}`;

// The address's parameter of the panel over a session's tab that shows a record (a chip
// opens the one an attachment keeps, a row of the Artifacts tab the latest): ?view=<record id>.
export const VIEW_PARAM = "view";

// A card in the session's chat: the chat scrolls to the element of that id.
export const chatPath = (session: string, anchor?: string) =>
  `${sessionPath(session, "activity")}${anchor ? `#${anchor}` : ""}`;

// Where a placeholder's section is planned: an item of ROADMAP.md or of docs/design/ui.md.
const REPO = "https://github.com/ladohq/lado/blob/main";

export type Plan = { label: string; href: string };

const ui = (anchor: string, label: string): Plan => ({
  label: `UI design, ${label}`,
  href: `${REPO}/docs/design/ui.md#${anchor}`,
});

export const PLANS = {
  home: ui("home", "Home"),
  activity: ui("activity", "Activity"),
  agents: ui("agents", "Agents"),
  flows: ui("flows", "Flows"),
  artifacts: ui("artifacts", "Artifacts"),
  providers: ui("providers-and-environment", "Providers and environment"),
  projects: { label: "Roadmap, Later: Projects", href: `${REPO}/ROADMAP.md#later-after-stage-7` },
} satisfies Record<string, Plan>;
