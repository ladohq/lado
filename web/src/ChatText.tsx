// Text in the session's feed, shared by its messages and its gate cards: a body as Markdown,
// a long one cut behind Show more, and a time of day.
import { useId, useState } from "react";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

// The characters a line that is not blank counts for: a text of n such lines may have
// n * CHARS_PER_LINE characters before it is long, and a cut one shows as many.
const CHARS_PER_LINE = 200;
// A message's text in the chat shows whole up to MESSAGE_OVER lines that are not blank
// (and their characters); a longer one shows its first MESSAGE_LINES, then Show more.
export const MESSAGE_OVER = 30;
export const MESSAGE_LINES = 12;

// A time of day in 24 hours ("19:53"), whatever the browser's locale says.
export function clock(iso: string): string {
  const when = new Date(iso);
  return Number.isNaN(when.getTime())
    ? ""
    : when.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
}

export function day(iso: string): string {
  const when = new Date(iso);
  return Number.isNaN(when.getTime()) ? "" : when.toLocaleDateString([], { month: "short", day: "numeric" });
}

// The local day a time falls on, as a heading of a list by days: "Today", "Yesterday", else
// its date ("Oct 2").
export function dayName(iso: string, now = new Date()): string {
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return "";
  const midnight = (at: Date) => new Date(at.getFullYear(), at.getMonth(), at.getDate()).getTime();
  const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1).getTime();
  if (midnight(when) === midnight(now)) return "Today";
  if (midnight(when) === yesterday) return "Yesterday";
  return day(iso);
}

// How long, in its largest unit ("<1 min", "12 min", "3 h", "2 d"), or `exact` with the
// next unit too ("2 h 14 min", "1 d 3 h").
export function duration(seconds: number, exact = false): string {
  const minutes = Math.floor(seconds / 60);
  if (!(minutes >= 1)) return "<1 min";
  if (minutes < 60) return `${minutes} min`;
  const [big, unit, rest, small] =
    minutes < 60 * 24
      ? [Math.floor(minutes / 60), "h", minutes % 60, "min"]
      : [Math.floor(minutes / (60 * 24)), "d", Math.floor(minutes / 60) % 24, "h"];
  return exact && rest ? `${big} ${unit} ${rest} ${small}` : `${big} ${unit}`;
}

// How long ago, roughly: "<1 min", "12 min", "3 h", "2 d".
export function since(iso: string): string {
  return duration((Date.now() - new Date(iso).getTime()) / 1000);
}

// Whether an agent's summary only repeats its body, so the body alone says it: the body's
// first line that is not blank is the summary, or the summary is that line cut with "…".
export function repeatsSummary(summary: string, body: string): boolean {
  const first = body.split("\n").find((line) => line.trim())?.trim();
  if (first === undefined) return false;
  if (first === summary.trim()) return true;
  const cut = summary.trim();
  return cut.endsWith("…") && first.startsWith(cut.slice(0, -1));
}

// Markdown's single line breaks as breaks (<br>), as the human typed them: the text nodes of
// the tree split at each "\n". Code keeps its own nodes and is not touched.
type Node = { type: string; value?: string; children?: Node[] };
function lineBreaks() {
  const split = (node: Node) => {
    if (!node.children) return;
    node.children = node.children.flatMap((child) => {
      if (child.type !== "text" || !child.value?.includes("\n")) {
        split(child);
        return [child];
      }
      return child.value.split(/\r?\n/).flatMap((part, i): Node[] => [
        ...(i > 0 ? [{ type: "break" }] : []),
        ...(part ? [{ type: "text", value: part }] : []),
      ]);
    });
  };
  return split;
}

// GitHub-flavoured Markdown: tables, task lists, autolinks, footnotes, and strikethrough
// only by a double tilde ("5~10 min" stays text).
const GFM: [typeof remarkGfm, { singleTilde: boolean }] = [remarkGfm, { singleTilde: false }];
// A table in a frame of its own, which scrolls sideways when the table is wider than the body.
const COMPONENTS: Components = {
  table: ({ node: _node, ...props }) => (
    <div className="md-table">
      <table {...props} />
    </div>
  ),
};

// A text as GitHub-flavoured Markdown, with any HTML in it left out. `breaks`: the human's
// text, whose single line breaks are breaks; an agent's body wraps lines by width. Each body's
// footnote ids are its own, so a footnote link never jumps to another message's footnote.
export function Body({ text, breaks = false }: { text: string; breaks?: boolean }) {
  const prefix = `md${useId().replace(/[^a-zA-Z0-9]/g, "")}-`;
  return (
    <div className="chat-body">
      <Markdown
        skipHtml
        remarkPlugins={breaks ? [GFM, lineBreaks] : [GFM]}
        remarkRehypeOptions={{ clobberPrefix: prefix }}
        components={COMPONENTS}
      >
        {text}
      </Markdown>
    </div>
  );
}

// A text shown at once: whole when it has no more than `over` lines that are not blank (and
// their characters), else its first `lines` lines and the rest behind Show more.
export function Preview({
  text,
  lines,
  over = lines,
  breaks = false,
}: {
  text: string;
  lines: number;
  over?: number;
  breaks?: boolean;
}) {
  const [all, setAll] = useState(false);
  const short = clamp(text, lines, over);
  if (short === null) return <Body text={text} breaks={breaks} />;
  return (
    <>
      <Body text={all ? text : short} breaks={breaks} />
      <button type="button" className="link-button" aria-expanded={all} onClick={() => setAll(!all)}>
        {all ? "Show less" : "Show more"}
      </button>
    </>
  );
}

// The text cut to its first `lines` lines that are not blank and at most their characters
// (CHARS_PER_LINE each), or null when it is no longer than `over` such lines and their
// characters and shows whole.
export function clamp(text: string, lines: number, over = lines): string | null {
  const all = text.trimEnd().split("\n");
  const filled = all.filter((line) => line.trim()).length;
  if (filled <= over && all.join("\n").length <= over * CHARS_PER_LINE) return null;
  let seen = 0;
  let end = all.length;
  for (let i = 0; i < all.length; i++) {
    if (all[i].trim() && ++seen === lines) {
      end = i + 1;
      break;
    }
  }
  const chars = lines * CHARS_PER_LINE;
  const head = all.slice(0, end).join("\n");
  return head.length > chars ? `${head.slice(0, chars)}…` : head;
}
