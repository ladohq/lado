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

// From this many artifacts in the session, filtered or not, the tab shows them in groups.
export const GROUPS_FROM = 100;

export type ScopeGroup = { scope: string; artifacts: ArtifactInfo[] };

// The artifacts by scope, in the order they came: on a list that is newest first, the group
// with the newest record comes first and each group keeps the newest first.
export function groupByScope(artifacts: ArtifactInfo[]): ScopeGroup[] {
  const groups = new Map<string, ArtifactInfo[]>();
  for (const one of artifacts) groups.set(one.scope, [...(groups.get(one.scope) ?? []), one]);
  return [...groups].map(([scope, items]) => ({ scope, artifacts: items }));
}
