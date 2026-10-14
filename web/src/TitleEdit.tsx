// The field that edits a session's title in place, in its head and in its list row
// (docs/design/ui.md, Session title). Enter or leaving the field saves, Esc cancels; empty
// clears the title. A text over the server's limit is said under the field and not sent; the
// server's refusal is said there too, the field kept open with the text. The same text as
// stored sends nothing. `onClose` puts the focus back on the opener.
import { useEffect, useRef, useState } from "react";

import { ApiError, getLimits, setSessionTitle, type SessionInfo } from "./api";
import { titleLength } from "./sessionLabel";

export function TitleEdit({ session, hint, onClose }: { session: SessionInfo; hint: string; onClose: () => void }) {
  const [text, setText] = useState(session.title ?? "");
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [limit, setLimit] = useState<number | null>(null);
  const field = useRef<HTMLInputElement>(null);
  const closed = useRef(false); // Esc or a save: the blur that follows does nothing

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
  const close = () => {
    closed.current = true;
    onClose();
  };

  const save = async () => {
    if (closed.current || saving || over) return;
    const wanted = text.trim() === session.name ? "" : text.trim();
    if (wanted === (session.title ?? "")) return close();
    setSaving(true);
    setProblem(null);
    try {
      await setSessionTitle(session.name, wanted || null);
    } catch (error) {
      setSaving(false);
      setProblem(error instanceof ApiError ? error.message : String(error));
      return;
    }
    close();
  };

  return (
    <span className="title-edit">
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
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
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
      {over ? (
        <span className="title-edit-problem field-problem">
          {length} characters, the limit is {limit}
        </span>
      ) : problem !== null ? (
        <span className="title-edit-problem field-problem" role="alert">
          {problem}
        </span>
      ) : (
        <span className="title-edit-hint">{hint}</span>
      )}
    </span>
  );
}
