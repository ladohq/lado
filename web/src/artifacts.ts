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
