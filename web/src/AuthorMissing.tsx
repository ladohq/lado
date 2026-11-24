// The note of a missing commit author (docs/design/ui.md, Launch and session control): where
// LADO would make a repository's first commit and nobody signs it (no project's, LADO's or
// git's own author), New empty folder, a plain folder's set-up and a project's Add
// repository → From scratch show one note: a link to LADO's author on Settings → Git servers
// in a new tab, and Check again. No author fields here. While it shows, the window asks again
// each time it gets the focus back; an author found replaces the note with who agents commit
// as, and the focus, when it was in the note, goes on to the window's next control.
import { useCallback, useEffect, useRef, useState, type RefObject } from "react";

import { type AuthorInfo, refusalOf } from "./api";

export const SETTINGS_AUTHOR = "/settings/git-servers?author";

export const authorText = (author: AuthorInfo) => `${author.name} <${author.email}>`;

export function KnownAuthor({ author }: { author: AuthorInfo }) {
  return (
    <span className="field-note ok" role="status">
      {`✓ Agents commit as ${authorText(author)}.`}
    </span>
  );
}

export function AuthorMissing({
  check,
  onFound,
  next,
  linkRef,
}: {
  check: () => Promise<AuthorInfo | null>; // who signs now; null: nobody
  onFound: (author: AuthorInfo) => void;
  next: () => HTMLElement | null | undefined; // where the focus goes from the note
  linkRef?: RefObject<HTMLAnchorElement | null>; // the footer's `set the commit author`
}) {
  const note = useRef<HTMLDivElement>(null);
  const [checking, setChecking] = useState(false);
  const [again, setAgain] = useState(false); // a Check again found nobody
  const [problem, setProblem] = useState<string | null>(null);
  const asking = useRef(false);
  const ask = useCallback(
    async (pressed: boolean) => {
      if (asking.current) return;
      asking.current = true;
      if (pressed) setChecking(true);
      try {
        const author = await check();
        setProblem(null);
        if (author) {
          const inNote = note.current?.contains(document.activeElement) ?? false;
          onFound(author);
          if (inNote) setTimeout(() => next()?.focus());
        } else if (pressed) setAgain(true);
      } catch (error) {
        if (pressed) setProblem(refusalOf(error).message);
      } finally {
        asking.current = false;
        setChecking(false);
      }
    },
    [check, onFound, next],
  );
  // Back from the other tab: once per return, never on a timer.
  useEffect(() => {
    const back = () => {
      if (document.visibilityState === "visible") void ask(false);
    };
    window.addEventListener("focus", back);
    document.addEventListener("visibilitychange", back);
    return () => {
      window.removeEventListener("focus", back);
      document.removeEventListener("visibilitychange", back);
    };
  }, [ask]);
  return (
    <div ref={note} className="field-note bad author-note" role="alert">
      <div>Agents need a name and email to sign their commits, and none is set yet.</div>
      {again && <div className="an-again">Checked again: still nobody. Save the name and email in Settings first.</div>}
      {problem && <div className="an-again">{problem}</div>}
      <div className="way-out">
        <a
          ref={linkRef}
          className="quiet"
          href={SETTINGS_AUTHOR}
          target="_blank"
          rel="noopener"
          aria-label="Set the commit author in Settings (opens a new tab)"
        >
          Set it in Settings ↗
        </a>
        <button
          type="button"
          className="quiet"
          aria-disabled={checking || undefined}
          onClick={() => !checking && void ask(true)}
        >
          {checking ? "Checking…" : "Check again"}
        </button>
      </div>
      <div className="an-hint">Then come back: this window checks again by itself.</div>
    </div>
  );
}
