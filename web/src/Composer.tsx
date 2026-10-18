// The composer (docs/design/ui.md, Composer): the human's text to the supervisor, or to agent
// `to` (an agent's page), with files. One frame with the paperclip, the field, which grows
// with the text, and Send; the files' chips above the field; under it to whom and how to
// send. Send uploads each file not uploaded yet (an artifact of the session's scope, so a
// file uploaded before a failure is not uploaded again, whoever it goes to), then sends the
// message with their names. Its file handling is the module the waiting card's fields share
// (attachFiles.tsx).
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
import { MOST_LINES, useGrow } from "./fieldHeight";
import { withQuote } from "./quote";
import { registerComposer, takePending } from "./quotes";

export function Composer({
  session,
  stopped,
  to,
  inputRef,
}: {
  session: string;
  stopped: boolean;
  to?: string;
  inputRef?: RefObject<HTMLTextAreaElement | null>;
}) {
  const [text, setText] = useState("");
  const [files, setFiles] = useOwnFiles();
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const limits = useLimits();
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
    if (!quoted.current) return;
    quoted.current = false;
    const box = field.current;
    if (!box) return;
    box.focus();
    box.setSelectionRange(box.value.length, box.value.length);
    box.scrollTop = box.scrollHeight;
  }, [text, field]);

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
  const dropping = useDropZone(form, attach, { closest: ".chat, .agent-page", ignoreInside: ".waiting-card", off: stopped });

  function remove(key: number) {
    release(files.filter((one) => one.key === key));
    setFiles((now) => now.filter((one) => one.key !== key));
  }

  async function send() {
    if ((!text.trim() && files.length === 0) || busy) return;
    setBusy(true);
    setProblem(null);
    try {
      const uploaded = await uploadFiles(session, files, setFiles, "Send again");
      if ("problem" in uploaded) {
        setProblem(uploaded.problem);
        return;
      }
      await writeMessage(session, text, to, uploaded.names);
      setText("");
      // Only the files sent go: one dropped meanwhile stays for the next message.
      const sent = new Set(files.map((one) => one.key));
      release(files);
      setFiles((now) => now.filter((one) => !sent.has(one.key)));
    } catch (error) {
      setProblem(error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  // While the focus is in the composer: files in the clipboard are attached, and a text
  // longer than a message may be becomes a file (attachFiles.pastedFiles).
  function paste(event: ClipboardEvent<HTMLFormElement>) {
    if (stopped || busy) return;
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
      onPaste={paste}
      onSubmit={(event) => {
        event.preventDefault();
        void send();
      }}
    >
      <div className={`composer-box${dropping ? " dropping" : ""}`}>
        {dropping && <DropLine limits={limits} />}
        <FileChips files={files} limits={limits} locked={busy} remove={remove} />
        <div className="composer-row">
          <ClipButton limits={limits} disabled={stopped || busy} attach={attach} />
          <textarea
            ref={field}
            aria-label={`Write to ${to ?? "the supervisor"}…`}
            placeholder={stopped ? "The session is stopped: resume it to write" : `Write to ${to ?? "the supervisor"}…`}
            rows={1}
            value={text}
            disabled={stopped}
            readOnly={busy}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={keyDown}
          />
          <button type="submit" className="send" disabled={stopped || busy || (!text.trim() && files.length === 0)}>
            {busy ? "Sending…" : "Send"}
          </button>
        </div>
      </div>
      <p className="composer-meta">
        <span className="composer-to">
          to <span className="composer-name">{to ?? "supervisor"}</span>
          {files.length > 0 && ` · ${filesLine(files)}`}
        </span>
        <span className="composer-keys">
          Enter to send · Shift+Enter for a new line{files.length === 0 && " · paste or drop files to attach"}
        </span>
      </p>
      {problem && (
        <p className="field-problem" role="alert">
          {problem}
        </p>
      )}
    </form>
  );
}
