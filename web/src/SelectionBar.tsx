// The selection bar (docs/design/ui.md, Selected text and copy buttons): over text the
// human selected in one readable area (an element marked by quoteArea, quote.ts, where it
// is rendered), two icon buttons: Copy, which copies the live selection as Ctrl+C does, and
// Quote in reply, which puts it into a composer (quotes.ts). Mounted once, in the shell.
// Above the selection, below it on a touch screen, where the system's own menu stands
// above; hidden on Esc, a press outside it, a scroll, or a selection that is gone.
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type SyntheticEvent } from "react";
import { useNavigate } from "react-router";

import { COPIED_MS } from "./Copy";
import { CopyIcon, QuoteIcon } from "./icons";
import { artifactLead, blockquote, fenced } from "./quote";
import { sendQuote } from "./quotes";
import { Tooltip } from "./Tooltip";

const GAP = 8; // pixels between the selection and the bar
const MARGIN = 8; // the least room to the window's edge
const NOT_AREAS = "input, textarea, [contenteditable]:not([contenteditable='false']), .xterm";
const TOUCH = "(hover: none)";

const elementOf = (node: Node | null) => (node instanceof Element ? node : (node?.parentElement ?? null));

// The readable area both ends of the selection lie in, or null: none for an empty or blank
// selection, one across two areas, or one inside a field, an editable element or a terminal.
export function areaOf(selection: Selection | null): HTMLElement | null {
  if (!selection || selection.isCollapsed || selection.rangeCount === 0) return null;
  if (!selection.toString().trim()) return null;
  const ends = [elementOf(selection.anchorNode), elementOf(selection.focusNode)];
  if (ends.some((end) => !end || end.closest(NOT_AREAS))) return null;
  const [first, second] = ends.map((end) => end!.closest<HTMLElement>("[data-quote]"));
  return first && first === second ? first : null;
}

// How many characters of `cell`'s text lie before the range's start (or end), or null when
// that end is not in the cell.
function offsetIn(cell: Element, range: Range, end: boolean): number | null {
  const [node, offset] = end ? [range.endContainer, range.endOffset] : [range.startContainer, range.startOffset];
  if (!cell.contains(node)) return null;
  const before = document.createRange();
  before.selectNodeContents(cell);
  before.setEnd(node, offset);
  return before.toString().length;
}

// A text artifact's selected lines from its rows (never the table's string, whose tabs and
// line breaks differ by browser): the first cut at the selection's start, the last at its
// end; a last row the selection only touches at its start is left out.
function codeLines(area: HTMLElement, range: Range): { lines: string[]; numbers: [number, number] } | null {
  const rows = [...area.querySelectorAll<HTMLElement>("tr[data-line]")].filter((row) => range.intersectsNode(row));
  const picked = rows.map((row) => {
    const cell = row.querySelector(".line");
    const text = cell?.textContent ?? "";
    const end = cell && offsetIn(cell, range, true);
    const from = (cell && offsetIn(cell, range, false)) ?? 0;
    return { line: Number(row.dataset.line), text: text.slice(from, end ?? text.length), touched: end === 0 };
  });
  while (picked.length > 1 && picked[picked.length - 1].touched) picked.pop();
  if (picked.length === 0) return null;
  return { lines: picked.map((one) => one.text), numbers: [picked[0].line, picked[picked.length - 1].line] };
}

// The quote of the selection in `area`: a Markdown quote; from an artifact under its lead
// line, a text artifact's lines fenced with their numbers in the lead.
export function quoteOf(area: HTMLElement, selection: Selection): string {
  const { quote: kind, quoteArtifact: artifact } = area.dataset;
  const earlier = area.hasAttribute("data-quote-earlier");
  if (kind === "code" && artifact && selection.rangeCount > 0) {
    const code = codeLines(area, selection.getRangeAt(0));
    if (code) return `${artifactLead(artifact, earlier, code.numbers)}\n${fenced(code.lines)}`;
  }
  const quoted = blockquote(selection.toString());
  return artifact ? `${artifactLead(artifact, earlier)}\n${quoted}` : quoted;
}

type Shown = { area: HTMLElement; rect: DOMRect };

export function SelectionBar() {
  const navigate = useNavigate();
  const [shown, setShown] = useState<Shown | null>(null);
  const [note, setNote] = useState(""); // "Copied", or how to copy by hand
  const [place, setPlace] = useState<CSSProperties>({ visibility: "hidden" });
  const bar = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const look = useCallback(() => {
    if (dragging.current) return;
    const selection = document.getSelection();
    const area = areaOf(selection);
    setNote("");
    setShown(area && selection ? { area, rect: selection.getRangeAt(0).getBoundingClientRect() } : null);
  }, []);

  useEffect(() => {
    let frame = 0;
    const later = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(look);
    };
    const hide = () => setShown(null);
    const down = (event: PointerEvent) => {
      if (bar.current?.contains(event.target as Node)) return;
      dragging.current = event.pointerType === "mouse" && event.button === 0;
      hide();
    };
    const up = () => {
      if (!dragging.current) return;
      dragging.current = false;
      later();
    };
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") hide();
      else if (event.shiftKey || event.key.startsWith("Arrow")) later(); // a selection by keys
    };
    const scrolled = (event: Event) => {
      if (!bar.current?.contains(event.target as Node)) hide();
    };
    document.addEventListener("selectionchange", later);
    document.addEventListener("pointerdown", down, true);
    document.addEventListener("pointerup", up, true);
    document.addEventListener("keyup", key);
    document.addEventListener("scroll", scrolled, true);
    window.addEventListener("resize", later); // placed again where the selection now is
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("selectionchange", later);
      document.removeEventListener("pointerdown", down, true);
      document.removeEventListener("pointerup", up, true);
      document.removeEventListener("keyup", key);
      document.removeEventListener("scroll", scrolled, true);
      window.removeEventListener("resize", later);
    };
  }, [look]);

  // Over the selection's middle, or under it on a touch screen or with no room above; never
  // past the window's edge.
  useLayoutEffect(() => {
    if (!shown || !bar.current) return;
    const { rect } = shown;
    const size = bar.current.getBoundingClientRect();
    const left = Math.max(MARGIN, Math.min(rect.left + rect.width / 2 - size.width / 2, window.innerWidth - size.width - MARGIN));
    const above = rect.top - GAP - size.height;
    const below = window.matchMedia?.(TOUCH).matches || above < MARGIN;
    const top = Math.min(below ? rect.bottom + GAP : above, window.innerHeight - size.height - MARGIN);
    setPlace({ left, top: Math.max(MARGIN, top) });
  }, [shown, note]);

  useEffect(() => {
    if (note !== "Copied") return;
    const timer = setTimeout(() => setNote(""), COPIED_MS);
    return () => clearTimeout(timer);
  }, [note]);

  if (!shown) return null;

  // The bar's buttons never take the focus or the selection away.
  const keep = (event: SyntheticEvent) => event.preventDefault();

  async function copy() {
    const selection = document.getSelection();
    let done = false;
    try {
      done = document.execCommand("copy");
    } catch {
      done = false;
    }
    if (!done && navigator.clipboard && selection) {
      try {
        await navigator.clipboard.writeText(selection.toString());
        done = true;
      } catch {
        done = false;
      }
    }
    setNote(done ? "Copied" : "Press ⌘C / Ctrl+C to copy");
  }

  function quote() {
    const selection = document.getSelection();
    if (!shown || !selection) return;
    const text = quoteOf(shown.area, selection);
    const session = shown.area.dataset.quoteSession ?? "";
    setShown(null);
    selection.removeAllRanges();
    sendQuote(session, text, navigate);
  }

  return (
    <div
      ref={bar}
      className="selection-bar"
      role="toolbar"
      aria-label="Selection"
      style={place}
      onPointerDown={keep}
      onMouseDown={keep}
    >
      {note ? (
        <span role="status" className="selection-note">
          {note}
        </span>
      ) : (
        <>
          <Tooltip tip="Copy">
            <button type="button" className="icon-button" aria-label="Copy" onClick={() => void copy()}>
              <CopyIcon />
            </button>
          </Tooltip>
          <Tooltip tip="Quote in reply">
            <button type="button" className="icon-button" aria-label="Quote in reply" onClick={quote}>
              <QuoteIcon />
            </button>
          </Tooltip>
        </>
      )}
    </div>
  );
}
