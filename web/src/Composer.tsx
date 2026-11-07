// The composer (docs/design/ui.md, Composer): the human's text to the supervisor, or to agent
// `to` (an agent's page), with files. One frame with the paperclip, the field, which grows
// with the text, and Send; the files' chips above the field; under it an agent the human
// chose, the files, and how to send while the field is empty and has the focus. Send uploads each file not uploaded yet (an artifact of the session's scope, so a
// file uploaded before a failure is not uploaded again, whoever it goes to), then sends the
// message with their names. Its file handling is the module the waiting card's fields share
// (attachFiles.tsx). While a field of the waiting card answers, or the session is stopped, the
// chat folds it (`folded`): it stays mounted and hidden, so its text, files and quotes live on,
// and ComposerFold, or the stopped session's bar, stands in its place.
import { useEffect, useRef, useState, type ClipboardEvent, type KeyboardEvent, type RefObject } from "react";

import { ApiError, writeMessage } from "./api";
import {
  ClipButton,
  DropLine,
  FileChips,
  attachFiles,
  filesLine,
  pastedFiles,
  release,
  uploadFiles,
  useDropZone,
  useLimits,
  useOwnFiles,
} from "./attachFiles";
import { looks, sendAttempt } from "./attempts";
import { MOST_LINES, useGrow } from "./fieldHeight";
import { ActivityIcon } from "./icons";
import { useLiveStore, useLocked } from "./live";
import { withQuote } from "./quote";
import { registerComposer, takePending } from "./quotes";
import { SUPERVISOR } from "./Team";
import { ActionProblem, Waits } from "./waitingParts";
import type { Fold } from "./WaitingCard";

export function Composer({
  session,
  to,
  inputRef,
  folded = false,
}: {
  session: string;
  to?: string;
  inputRef?: RefObject<HTMLTextAreaElement | null>;
  folded?: boolean;
}) {
  const [text, setText] = useState("");
  const [files, setFiles] = useOwnFiles();
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const limits = useLimits();
  const live = useLiveStore();
  const target = to ?? SUPERVISOR;
  const named = target !== SUPERVISOR; // the field's placeholder says the rest
  const attempt = sendAttempt(session, target);
  const locked = useLocked(attempt);
  const own = useRef<HTMLTextAreaElement>(null);
  const field = inputRef ?? own;
  useGrow(field, text, 1, MOST_LINES);

  // A quote (the selection bar's Quote in reply, quotes.ts) is appended to the text; the
  // field takes the focus with the cursor at the end once it shows. One kept for the
  // session while no composer was mounted is taken on mount.
  const quoted = useRef(false);
  useEffect(() => {
    const insert = (quote: string) => {
      quoted.current = true;
      setText((now) => withQuote(now, quote));
    };
    const kept = takePending(session);
    if (kept) insert(kept.replace(/\s+$/, ""));
    return registerComposer(session, insert);
  }, [session]);
  useEffect(() => {
    if (!quoted.current || folded) return;
    quoted.current = false;
    const box = field.current;
    if (!box) return;
    box.focus();
    box.setSelectionRange(box.value.length, box.value.length);
    box.scrollTop = box.scrollHeight;
  }, [text, field, folded]);

  // Attach what the limits allow; each file refused is named at the field, the rest stay.
  function attach(all: File[]) {
    const { added, problem: refused } = attachFiles(all, files.length, limits);
    setProblem(refused);
    setFiles((now) => [...now, ...added]);
  }

  // Files dragged over the composer's area (the chat column, an agent's page) show the drop
  // zone in its frame; dropped anywhere there, they are attached to this composer, but on
  // the waiting card, whose fields take their own (WaitingCard.tsx).
  const form = useRef<HTMLFormElement>(null);
  const dropping = useDropZone(form, attach, { closest: ".chat, .agent-page", ignoreInside: ".waiting-card", off: folded });

  function remove(key: number) {
    release(files.filter((one) => one.key === key));
    setFiles((now) => now.filter((one) => one.key !== key));
  }

  async function send() {
    if ((!text.trim() && files.length === 0) || busy || locked) return;
    setBusy(true);
    setProblem(null);
    live.attempts.clear(attempt);
    try {
      const after = await live.messageCursor(session); // the same words before this click do not count
      const uploaded = await uploadFiles(session, files, setFiles, "Send again");
      if ("problem" in uploaded) {
        setProblem(uploaded.problem);
        return;
      }
      // Words written after the click stay. Only the files sent go: one dropped meanwhile
      // stays for the next message.
      const sent = new Set(files.map((one) => one.key));
      const delivered = () => {
        setText((now) => (now === text ? "" : now));
        release(files);
        setFiles((now) => now.filter((one) => !sent.has(one.key)));
      };
      const answered = await live.attempts.send(attempt, {
        what: "Message",
        repeat: () => writeMessage(session, text, to, uploaded.names),
        look: looks.send(session, target, after, text, uploaded.names),
        closed: () => false,
        reached: delivered,
      });
      if (answered) delivered();
    } catch (error) {
      setProblem(error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  // While the focus is in the composer: files in the clipboard are attached, and a text
  // longer than a message may be becomes a file (attachFiles.pastedFiles).
  function paste(event: ClipboardEvent<HTMLFormElement>) {
    if (busy) return;
    const given = pastedFiles(event, limits);
    if (given) attach(given);
  }

  function keyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void send();
    }
  }

  return (
    <form
      ref={form}
      className="composer"
      hidden={folded}
      onPaste={paste}
      onSubmit={(event) => {
        event.preventDefault();
        void send();
      }}
    >
      <div className="composer-frame">
        <div className={`composer-box${dropping ? " dropping" : ""}`}>
          {dropping && <DropLine limits={limits} />}
          <FileChips files={files} limits={limits} locked={busy} remove={remove} />
          <div className="composer-row">
            <ClipButton limits={limits} disabled={busy} attach={attach} />
            <textarea
              ref={field}
              aria-label={`Write to ${to ?? "the supervisor"}…`}
              placeholder={`Write to ${to ?? "the supervisor"}…`}
              rows={1}
              value={text}
              readOnly={busy}
              onChange={(event) => setText(event.target.value)}
              onKeyDown={keyDown}
            />
            <Waits>
              <button type="submit" className="send" disabled={busy || locked || (!text.trim() && files.length === 0)}>
                {busy ? "Sending…" : "Send"}
              </button>
            </Waits>
          </div>
        </div>
        <p className="composer-meta">
          {(named || files.length > 0) && (
            <span className="composer-to">
              {named && (
                <>
                  to <span className="composer-name">{to}</span>
                </>
              )}
              {named && files.length > 0 && " · "}
              {files.length > 0 && filesLine(files)}
            </span>
          )}
          <span className="composer-keys">
            Enter to send · Shift+Enter for a new line{files.length === 0 && " · paste or drop files"}
          </span>
        </p>
      </div>
      {problem && (
        <p className="field-problem" role="alert">
          {problem}
        </p>
      )}
      <ActionProblem attempt={attempt} />
    </form>
  );
}

// The composer folded: what the waiting card's field in its place answers, and the way back.
export function ComposerFold({ fold, write }: { fold: Fold; write: () => void }) {
  return (
    <p className="composer-fold">
      <ActivityIcon />
      <span>
        {fold.line}
        {fold.write && (
          <button type="button" className="link-button" onClick={write}>
            Write to supervisor instead
          </button>
        )}
      </span>
    </p>
  );
}
