// The text a quote puts into the composer (docs/design/ui.md, Selected text and copy
// buttons): a Markdown quote, an artifact's lead line, a text artifact's lines fenced.

// The attributes of a readable area, set by the component that renders it: what it holds
// (text, a Markdown or a text artifact), its session, and an artifact's full name and
// whether its record is older than the latest. The selection bar reads them (SelectionBar.tsx).
export type AreaKind = "text" | "markdown" | "code";

export function quoteArea(session: string, kind: AreaKind = "text", artifact?: { fullName: string; earlier: boolean }) {
  return {
    "data-quote": kind,
    "data-quote-session": session,
    ...(artifact && { "data-quote-artifact": artifact.fullName }),
    ...(artifact?.earlier && { "data-quote-earlier": "" }),
  };
}

// Each line prefixed with "> ", an empty one with a bare ">"; trailing blank lines dropped.
export function blockquote(text: string): string {
  const lines = text.replace(/\r\n?/g, "\n").replace(/\s+$/, "").split("\n");
  return lines.map((line) => (line.trim() ? `> ${line}` : ">")).join("\n");
}

// The lines as a fenced code block whose fence is longer than any run of backticks in them.
export function fenced(lines: string[]): string {
  const runs = lines.flatMap((line) => (line.match(/`+/g) ?? []).map((run) => run.length));
  const fence = "`".repeat(Math.max(3, Math.max(0, ...runs) + 1));
  return [fence, ...lines, fence].join("\n");
}

// "In <full name>:", for a record older than the latest "In <full name>, an earlier
// record:", with " (lines a–b)" or " (line a)" before the colon for a text artifact.
export function artifactLead(fullName: string, earlier: boolean, lines?: [number, number]): string {
  const where = lines ? (lines[0] === lines[1] ? ` (line ${lines[0]})` : ` (lines ${lines[0]}–${lines[1]})`) : "";
  return `In ${fullName}${earlier ? ", an earlier record" : ""}${where}:`;
}

// The composer's text with the quote appended after one blank line, ending on a new line.
export function withQuote(current: string, quote: string): string {
  const before = current.replace(/\s+$/, "");
  return before ? `${before}\n\n${quote}\n` : `${quote}\n`;
}
