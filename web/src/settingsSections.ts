// Settings' sections, the one list (docs/design/ui.md, Settings): the list beside the page,
// the routes, the pages' headings and the old addresses read it. A section's page is
// Settings.tsx's PAGES, keyed by its slug, so a section without a page does not compile.
import type { JSX } from "react";

import { AgentCliIcon, ServerIcon, SettingsIcon, ShieldIcon } from "./icons";

export const SETTINGS_SECTIONS = [
  { slug: "general", name: "General", icon: SettingsIcon },
  { slug: "agent-clis", name: "Agent CLIs", icon: AgentCliIcon },
  { slug: "model-servers", name: "Model servers", icon: ServerIcon },
  { slug: "statistics", name: "Statistics", icon: ShieldIcon },
] as const satisfies readonly { slug: string; name: string; icon: () => JSX.Element }[];

export type SectionSlug = (typeof SETTINGS_SECTIONS)[number]["slug"];

export const sectionOf = (slug: string | undefined) => SETTINGS_SECTIONS.find((s) => s.slug === slug);

// The one page's anchors and the earlier designs' addresses (openspec settings-pages).
const OLD_HASHES: Record<string, string> = {
  "#providers-and-environment": "/settings/agent-clis",
  "#models": "/settings/model-servers",
  "#statistics": "/settings/statistics",
  "#notifications": "/settings/general#notifications",
  "#appearance": "/settings/general",
};
const OLD_SLUGS: Record<string, string> = {
  "agent-clis-and-environment": "agent-clis",
  models: "model-servers",
  "usage-statistics": "statistics",
};

// Where an address of Settings goes instead, null for one that stays: an old anchor of
// /settings its page, an old section its new one, an unknown section the list.
export function settingsRedirect(pathname: string, hash: string): string | null {
  const slug = pathname.replace(/^\/settings\/?/, "").replace(/\/$/, "");
  if (!slug) return OLD_HASHES[hash] ?? null;
  if (sectionOf(slug)) return null;
  return OLD_SLUGS[slug] ? `/settings/${OLD_SLUGS[slug]}` : "/settings";
}
