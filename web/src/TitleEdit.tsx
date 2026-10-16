// The field that edits a session's title in place, in its head and in its list row
// (docs/design/ui.md, Session title). Enter or leaving the field saves, Esc cancels; empty
// clears the title. A text over the server's limit is said under the field and not sent; the
// server's refusal is said there too, the field kept open with the text. The same text as
// stored sends nothing. `onClose` gets the session as the server stored it after a save (the
// page shows it before the feed brings it), and puts the focus back on the opener.
//
// The session's name is a suggestion (Tab takes the session's name): while the text is a
// proper start of the name (case and all, the empty text included), the caret at its end
// with nothing selected, no save in flight and no input method composing, the rest of the
// name shows grey after the text (the placeholder while empty; a layer over the input,
// hidden while the input is scrolled), Tab or → without modifiers make the name the text,
// the caret at its end and the focus kept, and the hint is `suggestionHint`. Otherwise Tab
// and → do what they do in any field.
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { ApiError, getLimits, setSessionTitle, type SessionInfo } from "./api";
import { titleLength } from "./sessionLabel";

export function TitleEdit({
  session,
  hint,
  suggestionHint,
  onClose,
}: {
  session: SessionInfo;
  hint: string;
  suggestionHint: string;
  onClose: (saved?: SessionInfo) => void;
}) {
  const [text, setText] = useState(session.title ?? "");
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [limit, setLimit] = useState<number | null>(null);
  // The selection as the field last told it (selected whole on opening), whether an input
  // method composes and whether the input is scrolled: what the suggestion is drawn by.
  const [selection, setSelection] = useState<[number, number]>([0, text.length]);
  const [composing, setComposing] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const field = useRef<HTMLInputElement>(null);
  const closed = useRef(false); // Esc or a save: the blur that follows does nothing

  const suggests = (start: number | null, end: number | null) =>
    !saving &&
    !composing &&
    text.length < session.name.length &&
    session.name.startsWith(text) &&
    start === text.length &&
    end === text.length;
  const suggesting = suggests(...selection);

  const noted = () => {
    const input = field.current;
    if (input) setSelection([input.selectionStart ?? 0, input.selectionEnd ?? 0]);
  };

  // Tab or → taking the name, read from the field itself: the caret has not moved yet.
  const takesName = (event: KeyboardEvent<HTMLInputElement>) => {
    const { key, shiftKey, ctrlKey, altKey, metaKey } = event;
    if (key !== "Tab" && key !== "ArrowRight") return false;
    if (shiftKey || ctrlKey || altKey || metaKey || event.nativeEvent.isComposing) return false;
    return suggests(event.currentTarget.selectionStart, event.currentTarget.selectionEnd);
  };

  useEffect(() => {
    field.current?.select();
    let current = true;
    getLimits().then(
      (limits) => current && setLimit(limits.max_title),
      () => {}, // the server checks it anyway
    );
    return () => {
      current = false;
    };
  }, []);

  const length = titleLength(text);
  const over = limit !== null && length > limit;
  const close = (saved?: SessionInfo) => {
    closed.current = true;
    onClose(saved);
  };

  const save = async () => {
    if (closed.current || saving || over) return;
    const wanted = text.trim() === session.name ? "" : text.trim();
    if (wanted === (session.title ?? "")) return close();
    setSaving(true);
    setProblem(null);
    let saved: SessionInfo;
    try {
      saved = await setSessionTitle(session.name, wanted || null);
    } catch (error) {
      setSaving(false);
      setProblem(error instanceof ApiError ? error.message : String(error));
      return;
    }
    close(saved);
  };

  return (
    <span className="title-edit">
      <span className="title-edit-field">
        <input
          ref={field}
          type="text"
          aria-label="Session title"
          placeholder={session.name}
          value={text}
          readOnly={saving}
          autoFocus
          aria-invalid={over || problem !== null || undefined}
          onChange={(event) => {
            setText(event.target.value);
            setProblem(null);
            noted();
          }}
          onSelect={noted}
          onScroll={(event) => setScrolled(event.currentTarget.scrollLeft > 0)}
          onCompositionStart={() => setComposing(true)}
          onCompositionEnd={() => setComposing(false)}
          onKeyDown={(event) => {
            if (takesName(event)) {
              event.preventDefault();
                setText(session.name);
              setProblem(null);
            } else if (event.key === "Enter") {
              event.preventDefault();
              void save();
            } else if (event.key === "Escape") {
              event.preventDefault();
              event.stopPropagation();
              if (!closed.current) close();
            }
          }}
          onBlur={() => void save()}
        />
        {suggesting && text !== "" && !scrolled && (
          <span className="title-edit-rest" aria-hidden="true">
            <span className="title-edit-typed">{text}</span>
            {session.name.slice(text.length)}
          </span>
        )}
      </span>
      {over ? (
        <span className="title-edit-problem field-problem">
          {length} characters, the limit is {limit}
        </span>
      ) : problem !== null ? (
        <span className="title-edit-problem field-problem" role="alert">
          {problem}
        </span>
      ) : (
        <span className="title-edit-hint">{suggesting ? suggestionHint : hint}</span>
      )}
    </span>
  );
}
