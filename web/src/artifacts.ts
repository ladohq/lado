// Artifacts in the UI (docs/design/ui.md, Artifacts): whether an attachment changed since it
// was attached, and how a media type is shown.
import type { ArtifactInfo, AttachmentInfo } from "./api";
import type { ListLoaded } from "./live";

// unknown: the session's artifacts are not loaded (or the artifact is not among them), so a
// chip says nothing rather than "unchanged".
export type Changed = "changed" | "unchanged" | "unknown";

// Whether the artifact's content changed since the attachment: its latest record's hash is
// another. The one place the UI compares them.
export function changed(attached: Pick<AttachmentInfo, "artifact" | "hash">, artifacts: ListLoaded<ArtifactInfo> | undefined): Changed {
  if (!artifacts || "error" in artifacts) return "unknown";
  const now = artifacts.items.find((one) => one.id === attached.artifact);
  if (now === undefined) return "unknown";
  return now.latest.hash === attached.hash ? "unchanged" : "changed";
}

export type Kind = "markdown" | "text" | "image" | "html" | "other";

// Each kind in words: the type filter's label and what a row of the narrow list says.
export const KINDS: Record<Kind, { filter: string; word: string }> = {
  markdown: { filter: "Documents", word: "Document" },
  text: { filter: "Code and text", word: "Code or text" },
  image: { filter: "Images", word: "Image" },
  html: { filter: "HTML", word: "HTML" },
  other: { filter: "Other", word: "File" },
};

// The types read as text besides text/*, as the core's artifacts.is_text says (SVG is an
// image here: the viewer draws it).
const TEXT = new Set(["application/json"]);
const IMAGES = new Set(["image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml"]);

// How the viewer shows a media type: Markdown as the chat does, text and code with line
// numbers, an image, HTML in a sandboxed frame, anything else as facts and a download.
export function kindOf(mediaType: string): Kind {
  if (mediaType === "text/markdown") return "markdown";
  if (mediaType === "text/html") return "html";
  if (IMAGES.has(mediaType)) return "image";
  if (mediaType.startsWith("text/") || TEXT.has(mediaType)) return "text";
  return "other";
}

// A size in bytes as people read it: "812 B", "7.2 KB", "1.4 MB".
export function size(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// The run part of a full name, "<run>/", or "" in the session's scope.
export const scopePart = (scope: string) => (scope ? `${scope}/` : "");

// Whether a Markdown text says `title` as its H1, on its first line that is not blank: the
// viewer then leaves out its title line. Closing #s and the case do not count.
export function sameHeading(text: string, title: string): boolean {
  const first = text.split("\n").find((line) => line.trim() !== "") ?? "";
  const heading = /^#\s+(.*?)(\s+#+)?\s*$/.exec(first)?.[1];
  return heading?.trim().toLowerCase() === title.trim().toLowerCase();
}

// From this many artifacts in the session, filtered or not, the tab shows them in groups.
export const GROUPS_FROM = 100;

export type ScopeGroup = { scope: string; artifacts: ArtifactInfo[] };

// The artifacts by scope, each group in the order they came, so newest first on such a list.
// The groups go by `order`; a scope it lacks, or with none, goes first as it came.
export function groupByScope(artifacts: ArtifactInfo[], order: string[] = []): ScopeGroup[] {
  const groups = new Map<string, ScopeGroup>();
  for (const one of artifacts) {
    const group = groups.get(one.scope) ?? { scope: one.scope, artifacts: [] };
    group.artifacts.push(one);
    groups.set(one.scope, group);
  }
  return [...groups.values()].sort((a, b) => order.indexOf(a.scope) - order.indexOf(b.scope));
}
