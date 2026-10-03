// Text in the session's feed, shared by its messages and its gate cards: an agent's body as
// Markdown, a long one behind Show all, and a time of day.
import { useState } from "react";
import Markdown from "react-markdown";

export const BODY_LINES = 8; // the lines of a body to the human shown before Show all
const BODY_CHARS = 1500; // and at most these characters of them

export function clock(iso: string): string {
  const when = new Date(iso);
  return Number.isNaN(when.getTime()) ? "" : when.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// The body is the agent's text: Markdown, with any HTML in it left out.
export function Body({ text }: { text: string }) {
  return (
    <div className="chat-body">
      <Markdown skipHtml>{text}</Markdown>
    </div>
  );
}

// A body shown at once: its first `lines` lines, the rest behind Show all.
export function Preview({ text, lines = BODY_LINES }: { text: string; lines?: number }) {
  const [all, setAll] = useState(false);
  const short = preview(text, lines);
  if (short === text) return <Body text={text} />;
  return (
    <>
      <Body text={all ? text : short} />
      <button type="button" className="link-button" aria-expanded={all} onClick={() => setAll(!all)}>
        {all ? "Show less" : "Show all"}
      </button>
    </>
  );
}

// The text up to its `lines`-th line that is not blank, and at most BODY_CHARS of it (more
// for more lines).
function preview(text: string, lines: number): string {
  const all = text.split("\n");
  let seen = 0;
  let end = all.length;
  for (let i = 0; i < all.length; i++) {
    if (all[i].trim() && ++seen === lines) {
      end = i + 1;
      break;
    }
  }
  const chars = Math.round((BODY_CHARS * lines) / BODY_LINES);
  const head = all.slice(0, end).join("\n");
  const cut = head.length > chars ? `${head.slice(0, chars)}…` : head;
  return cut.trimEnd() === text.trimEnd() ? text : cut;
}
