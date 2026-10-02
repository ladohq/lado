// The UI's addresses (docs/design/ui.md, Structure). Every name in a path is one segment,
// encoded whole with encodeURIComponent: session names are free text, run names hold "/".
// A run's future address: /sessions/<name>/flows/<run, encoded whole>.

export const TABS = ["activity", "agents", "flows", "artifacts"] as const;
export type Tab = (typeof TABS)[number];

export const isTab = (tab: string): tab is Tab => (TABS as readonly string[]).includes(tab);

export function sessionPath(name: string, tab?: Tab): string {
  const path = `/sessions/${encodeURIComponent(name)}`;
  return tab ? `${path}/${tab}` : path;
}

export const gatePath = (id: number) => `/gates/${id}`;

// Where a placeholder's section is planned: an item of ROADMAP.md or of docs/design/ui.md.
const REPO = "https://github.com/ladohq/lado/blob/main";

export type Plan = { label: string; href: string };

const ui = (anchor: string, label: string): Plan => ({
  label: `UI design, ${label}`,
  href: `${REPO}/docs/design/ui.md#${anchor}`,
});

export const PLANS = {
  home: ui("home", "Home"),
  gates: ui("gates", "Gates"),
  kits: ui("kits", "Kits"),
  activity: ui("activity", "Activity"),
  agents: ui("agents", "Agents"),
  flows: ui("flows", "Flows"),
  artifacts: ui("artifacts", "Artifacts"),
  providers: ui("providers-and-environment", "Providers and environment"),
  projects: { label: "Roadmap, Later: Projects", href: `${REPO}/ROADMAP.md#later-after-stage-7` },
  marketplace: {
    label: "Roadmap, Later: Kit marketplace",
    href: `${REPO}/ROADMAP.md#later-after-stage-7`,
  },
} satisfies Record<string, Plan>;
