// The composer (docs/design/ui.md, Composer): the human's text to the supervisor, or to agent
// `to` (an agent's page), with files. One frame with the paperclip, the field, which grows
// with the text, and Send; the files' chips above the field; under it to whom and how to
// send. Send uploads each file not uploaded yet (an artifact of the session's scope, so a
// file uploaded before a failure is not uploaded again, whoever it goes to), then sends the
// message with their names. What the composer checks and how it marks a file comes from the
// server's limits, never a copy of them here.
import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ClipboardEvent,
  type KeyboardEvent,
  type RefObject,
} from "react";

import { ApiError, getLimits, uploadFile, writeMessage, type Limits } from "./api";
import { kindOf, size } from "./artifacts";
import { KindIcon } from "./ArtifactView";
import { ClipIcon, UnseenIcon } from "./icons";
import { Tooltip } from "./Tooltip";

// The lines the composer's field grows to before it scrolls.
const COMPOSER_LINES = 8;

// The field as tall as its text, from 1 line to COMPOSER_LINES, then it scrolls.
function grow(field: HTMLTextAreaElement | null) {
  if (!field) return;
  const style = getComputedStyle(field);
  const line = parseFloat(style.lineHeight) || 20;
  const padding = (parseFloat(style.paddingTop) || 0) + (parseFloat(style.paddingBottom) || 0);
  const most = line * COMPOSER_LINES + padding;
  field.style.height = "auto";
  const height = field.scrollHeight;
  field.style.height = `${Math.min(height, most)}px`;
  field.style.overflowY = height > most ? "auto" : "hidden";
}

// A file the human attached, until the message is sent: its upload's state, and once
// uploaded its artifact's full name.
type Attached = {
  key: number;
  file: File;
  name: string;
  mediaType: string;
  thumb: string | null; // an image's object URL, revoked when the chip goes
  state: "ready" | "uploading" | "uploaded" | "failed";
  uploaded: string | null;
  reason: string | null;
};

// A file's media type as the server gives it: by its extension in the server's table.
export function mediaTypeOf(name: string, limits: Limits | null): string {
  const dot = name.lastIndexOf(".");
  const extension = dot > 0 ? name.slice(dot + 1).toLowerCase() : "";
  return limits?.extensions[extension] ?? "application/octet-stream";
}

// The local time as HHMMSS: a pasted file's name.
function stamp(): string {
  const now = new Date();
  return [now.getHours(), now.getMinutes(), now.getSeconds()].map((n) => String(n).padStart(2, "0")).join("");
}

const renamed = (file: File, name: string) => new File([file], name, { type: file.type });

let nextKey = 0;

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
  const [files, setFiles] = useState<Attached[]>([]);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [limits, setLimits] = useState<Limits | null>(null);
  const own = useRef<HTMLTextAreaElement>(null);
  const picker = useRef<HTMLInputElement>(null);
  const field = inputRef ?? own;
  const thumbs = useRef(new Set<string>());
  useLayoutEffect(() => grow(field.current), [text, field]);

  useEffect(() => {
    let mounted = true;
    getLimits().then(
      (got) => mounted && setLimits(got),
      () => {}, // without limits every file shows its icon and the server checks the rest
    );
    return () => {
      mounted = false;
    };
  }, []);

  // Files dragged over the composer's area (the chat column, an agent's page) show the drop
  // zone in its frame; dropped anywhere there, they are attached to this composer.
  const form = useRef<HTMLFormElement>(null);
  const [dropping, setDropping] = useState(false);
  const attachRef = useRef<(files: File[]) => void>(() => {});
  useEffect(() => {
    const area = form.current?.closest<HTMLElement>(".chat, .agent-page");
    if (!area || stopped) return;
    const files = (event: DragEvent) => Array.from(event.dataTransfer?.types ?? []).includes("Files");
    const over = (event: DragEvent) => {
      if (!files(event)) return;
      event.preventDefault();
      setDropping(true);
    };
    const leave = (event: DragEvent) => {
      if (!area.contains(event.relatedTarget as Node | null)) setDropping(false);
    };
    const dropped = (event: DragEvent) => {
      if (!files(event)) return;
      event.preventDefault();
      setDropping(false);
      attachRef.current(Array.from(event.dataTransfer?.files ?? []));
    };
    area.addEventListener("dragenter", over);
    area.addEventListener("dragover", over);
    area.addEventListener("dragleave", leave);
    area.addEventListener("drop", dropped);
    return () => {
      area.removeEventListener("dragenter", over);
      area.removeEventListener("dragover", over);
      area.removeEventListener("dragleave", leave);
      area.removeEventListener("drop", dropped);
    };
  }, [stopped]);

  // Every thumbnail still made goes with the composer.
  useEffect(() => {
    const made = thumbs.current;
    return () => made.forEach((url) => URL.revokeObjectURL(url));
  }, []);

  const drop = (url: string | null) => {
    if (!url) return;
    URL.revokeObjectURL(url);
    thumbs.current.delete(url);
  };

  // Attach what the limits allow; each file refused is named at the field, the rest stay.
  function attach(all: File[]) {
    const given: File[] = [];
    const refused: string[] = [];
    for (const file of all) {
      if (limits && file.size > limits.max_size) {
        refused.push(`${file.name} was not attached: it is ${size(file.size)}, the limit is ${size(limits.max_size)}.`);
      } else if (limits && files.length + given.length >= limits.max_files) {
        refused.push(`${file.name} was not attached: up to ${limits.max_files} files.`);
      } else {
        given.push(file);
      }
    }
    setProblem(refused.length ? refused.join(" ") : null);
    const added = given.map((file): Attached => {
      const mediaType = mediaTypeOf(file.name, limits);
      const thumb = kindOf(mediaType) === "image" ? URL.createObjectURL(file) : null;
      if (thumb) thumbs.current.add(thumb);
      return { key: ++nextKey, file, name: file.name, mediaType, thumb, state: "ready", uploaded: null, reason: null };
    });
    setFiles((now) => [...now, ...added]);
  }
  useLayoutEffect(() => {
    attachRef.current = attach;
  });

  function remove(key: number) {
    drop(files.find((one) => one.key === key)?.thumb ?? null);
    setFiles((now) => now.filter((one) => one.key !== key));
  }

  const change = (key: number, update: Partial<Attached>) =>
    setFiles((now) => now.map((one) => (one.key === key ? { ...one, ...update } : one)));

  async function send() {
    if ((!text.trim() && files.length === 0) || busy) return;
    setBusy(true);
    setProblem(null);
    try {
      const names: string[] = [];
      const failed: string[] = [];
      for (const one of files) {
        if (one.uploaded) {
          names.push(one.uploaded);
          continue;
        }
        change(one.key, { state: "uploading", reason: null });
        try {
          const artifact = await uploadFile(session, one.file, one.name);
          change(one.key, { state: "uploaded", uploaded: artifact.full_name });
          names.push(artifact.full_name);
        } catch (error) {
          const reason = error instanceof ApiError ? error.message : String(error);
          change(one.key, { state: "failed", reason });
          failed.push(`${one.name} was not uploaded: ${reason}.`);
        }
      }
      if (failed.length) {
        const them = failed.length === 1 ? "it" : "them";
        setProblem(`${failed.join(" ")} Remove ${them}, or Send again to try ${them} again.`);
        return;
      }
      await writeMessage(session, text, to, names);
      setText("");
      // Only the files sent go: one dropped meanwhile stays for the next message.
      const sent = new Set(files.map((one) => one.key));
      files.forEach((one) => drop(one.thumb));
      setFiles((now) => now.filter((one) => !sent.has(one.key)));
    } catch (error) {
      setProblem(error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  // While the focus is in the composer: files in the clipboard are attached (an image the
  // browser calls image.png as screenshot-<time>.png), and a text longer than a message may
  // be becomes a file; a shorter one is pasted as text.
  function paste(event: ClipboardEvent<HTMLFormElement>) {
    if (stopped || busy) return;
    const given = Array.from(event.clipboardData.files ?? []);
    if (given.length) {
      event.preventDefault();
      attach(given.map((one) => (one.name === "image.png" ? renamed(one, `screenshot-${stamp()}.png`) : one)));
      return;
    }
    const pasted = event.clipboardData.getData("text/plain");
    if (limits && pasted.length > limits.max_message) {
      event.preventDefault();
      attach([new File([pasted], `pasted-${stamp()}.txt`, { type: "text/plain" })]);
    }
  }

  function keyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void send();
    }
  }

  const total = files.reduce((sum, one) => sum + one.file.size, 0);
  const allowed = limits ? `up to ${limits.max_files} files, ${size(limits.max_size)} each` : "";
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
        {dropping && <p className="composer-drop">Drop to attach{allowed && ` · ${allowed}`}</p>}
        {files.length > 0 && (
          <ul className="composer-files" aria-label="Attached files">
            {files.map((one) => (
              <FileChip
                key={one.key}
                attached={one}
                unseen={unseen(one, limits)}
                locked={busy}
                remove={() => remove(one.key)}
              />
            ))}
          </ul>
        )}
        <div className="composer-row">
          <span className="composer-clip">
            <button
              type="button"
              className="clip"
              aria-label="Attach files"
              title={`Attach files${allowed && `: ${allowed}`} (or paste, or drop them here)`}
              disabled={stopped || busy}
              onClick={() => picker.current?.click()}
            >
              <ClipIcon />
            </button>
            <input
              ref={picker}
              type="file"
              multiple
              hidden
              tabIndex={-1}
              onChange={(event) => {
                attach(Array.from(event.target.files ?? []));
                event.target.value = "";
              }}
            />
          </span>
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
          {files.length > 0 && ` · ${files.length} file${files.length === 1 ? "" : "s"}, ${size(total)}`}
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

const UNSEEN = "The agent sees only this file's name and size";

// Why an agent would see only the file's name and size, by the server's limits: a type it
// cannot read, or an image larger than it is shown; null when it reads the file.
function unseen(attached: Attached, limits: Limits | null): string | null {
  if (!limits) return null;
  const { mediaType, file } = attached;
  if (limits.agent_images.includes(mediaType)) {
    if (file.size <= limits.image_limit) return null;
    return `${UNSEEN}: an image over ${size(limits.image_limit)} is not shown to agents.`;
  }
  if (mediaType.startsWith("text/") || limits.text_types.includes(mediaType)) return null;
  return `${UNSEEN}. Agents read text and PNG, JPEG, GIF and WebP images.`;
}

// One attached file: an image's thumbnail or its type's icon (with the crossed-out eye when
// an agent cannot read it), its name and size (its upload's state while it goes, its reason
// when it failed), and × to remove it.
function FileChip({
  attached,
  unseen,
  locked,
  remove,
}: {
  attached: Attached;
  unseen: string | null;
  locked: boolean;
  remove: () => void;
}) {
  const { name, file, thumb, state } = attached;
  return (
    <li className={`file-chip${state === "failed" ? " failed" : ""}`}>
      <span className="file-tile">
        {thumb ? <img src={thumb} alt="" /> : <KindIcon mediaType={attached.mediaType} />}
        {unseen && (
          <Tooltip tip={unseen}>
            <button type="button" className="file-unseen" aria-label={UNSEEN}>
              <UnseenIcon />
            </button>
          </Tooltip>
        )}
      </span>
      <span className="file-text">
        <span className="file-name">{name}</span>
        {state === "uploading" ? (
          <span className="file-progress" role="progressbar" aria-label={`Uploading ${name}`} />
        ) : (
          <span className="file-size">
            {state === "failed" ? attached.reason : state === "uploaded" ? "uploaded" : size(file.size)}
          </span>
        )}
      </span>
      {!locked && (
        <button type="button" className="file-remove" aria-label={`Remove ${name}`} onClick={remove}>
          ×
        </button>
      )}
    </li>
  );
}
