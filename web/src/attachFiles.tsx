// The human's files (docs/design/ui.md, Composer): one module for the composer and the
// waiting card's fields (an own answer, a skip's comment, a gate's comment), so they attach,
// show, upload and refuse files the same way. What they check and how a file is marked comes
// from the server's limits, never a copy of them here. Whoever keeps the files (the
// composer, the waiting card across its tabs) owns their thumbnails' object URLs: `release`
// revokes them when the files go.
import { useEffect, useLayoutEffect, useRef, useState, type ClipboardEvent, type RefObject } from "react";

import { ApiError, getLimits, uploadFile, type Limits } from "./api";
import { kindOf, size } from "./artifacts";
import { KindIcon } from "./ArtifactView";
import { CARD_LINES, MOST_LINES, useGrow } from "./fieldHeight";
import { ClipIcon, UnseenIcon } from "./icons";
import { Tooltip } from "./Tooltip";

// A file the human attached, until it is sent: its upload's state, and once uploaded its
// artifact's full name.
export type Attached = {
  key: number;
  file: File;
  name: string;
  mediaType: string;
  thumb: string | null; // an image's object URL, revoked when the chip goes
  state: "ready" | "uploading" | "uploaded" | "failed";
  uploaded: string | null;
  reason: string | null;
};

export type SetFiles = (update: (now: Attached[]) => Attached[]) => void;

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

// The server's limits, loaded once the component mounts; null until then (and when they
// cannot be loaded: every file shows its icon and the server checks the rest).
export function useLimits(): Limits | null {
  const [limits, setLimits] = useState<Limits | null>(null);
  useEffect(() => {
    let mounted = true;
    getLimits().then(
      (got) => mounted && setLimits(got),
      () => {},
    );
    return () => {
      mounted = false;
    };
  }, []);
  return limits;
}

// "up to <n> files, <size> each", or "" before the limits are loaded.
export const allowed = (limits: Limits | null) => (limits ? `up to ${limits.max_files} files, ${size(limits.max_size)} each` : "");

// "<n> file(s), <size>": how many files are attached and their size.
export function filesLine(files: Attached[]): string {
  const total = files.reduce((sum, one) => sum + one.file.size, 0);
  return `${files.length} file${files.length === 1 ? "" : "s"}, ${size(total)}`;
}

// The files `given` that the limits allow next to `count` attached already, each with an
// image's thumbnail; each one refused is named in `problem` (null when none is).
export function attachFiles(given: File[], count: number, limits: Limits | null): { added: Attached[]; problem: string | null } {
  const taken: File[] = [];
  const refused: string[] = [];
  for (const file of given) {
    if (limits && file.size > limits.max_size) {
      refused.push(`${file.name} was not attached: it is ${size(file.size)}, the limit is ${size(limits.max_size)}.`);
    } else if (limits && count + taken.length >= limits.max_files) {
      refused.push(`${file.name} was not attached: up to ${limits.max_files} files.`);
    } else {
      taken.push(file);
    }
  }
  const added = taken.map((file): Attached => {
    const mediaType = mediaTypeOf(file.name, limits);
    const thumb = kindOf(mediaType) === "image" ? URL.createObjectURL(file) : null;
    return { key: ++nextKey, file, name: file.name, mediaType, thumb, state: "ready", uploaded: null, reason: null };
  });
  return { added, problem: refused.length ? refused.join(" ") : null };
}

// What a paste attaches: the files in the clipboard (an image the browser calls image.png as
// screenshot-<time>.png), or a text longer than a message may be as a file; null for a
// shorter text, which is pasted as text. With files the browser's own paste is stopped.
export function pastedFiles(event: ClipboardEvent, limits: Limits | null): File[] | null {
  const given = Array.from(event.clipboardData.files ?? []);
  if (given.length) {
    event.preventDefault();
    return given.map((one) => (one.name === "image.png" ? renamed(one, `screenshot-${stamp()}.png`) : one));
  }
  const pasted = event.clipboardData.getData("text/plain");
  if (limits && pasted.length > limits.max_message) {
    event.preventDefault();
    return [new File([pasted], `pasted-${stamp()}.txt`, { type: "text/plain" })];
  }
  return null;
}

// Upload each file not uploaded yet (an artifact of the session's scope, so a file uploaded
// before a failure is not uploaded again), marking its chip as it goes. The full names of
// all of them, or, when any failed, why, ending with how to try again (`again`: "Send
// again", "answer again").
export async function uploadFiles(
  session: string,
  files: Attached[],
  setFiles: SetFiles,
  again: string,
): Promise<{ names: string[] } | { problem: string }> {
  const change = (key: number, update: Partial<Attached>) =>
    setFiles((now) => now.map((one) => (one.key === key ? { ...one, ...update } : one)));
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
  if (failed.length === 0) return { names };
  const them = failed.length === 1 ? "it" : "them";
  return { problem: `${failed.join(" ")} Remove ${them}, or ${again} to try ${them} again.` };
}

// The thumbnails of files that go (sent, removed, their question closed) are revoked.
export function release(files: Attached[]) {
  for (const one of files) if (one.thumb) URL.revokeObjectURL(one.thumb);
}

// Files kept by one component: those still there when it goes are released.
export function useOwnFiles(): [Attached[], SetFiles] {
  const [files, setFiles] = useState<Attached[]>([]);
  const latest = useRef(files);
  latest.current = files;
  useEffect(() => () => release(latest.current), []);
  return [files, setFiles];
}

// Files dragged over an area show its drop zone (the returned `dropping`); dropped there,
// they go to `attach`. The area is `ref`'s element, or with `closest` its nearest ancestor
// that matches. A drag inside `ignoreInside` is left alone: the region's own fields take
// it. `own`: the drag stops at the area, so no area around it sees it too.
export function useDropZone(
  ref: RefObject<HTMLElement | null>,
  attach: (files: File[]) => void,
  { closest, ignoreInside, off = false, own = false }: { closest?: string; ignoreInside?: string; off?: boolean; own?: boolean } = {},
): boolean {
  const [dropping, setDropping] = useState(false);
  const attachRef = useRef(attach);
  useLayoutEffect(() => {
    attachRef.current = attach;
  });
  useEffect(() => {
    const area = closest ? ref.current?.closest<HTMLElement>(closest) : ref.current;
    if (!area || off) return;
    const files = (event: DragEvent) => Array.from(event.dataTransfer?.types ?? []).includes("Files");
    const ignored = (event: DragEvent) =>
      ignoreInside !== undefined && event.target instanceof Element && event.target.closest(ignoreInside) !== null;
    const over = (event: DragEvent) => {
      if (!files(event)) return;
      if (ignored(event)) {
        setDropping(false);
        return;
      }
      event.preventDefault();
      if (own) event.stopPropagation();
      setDropping(true);
    };
    const leave = (event: DragEvent) => {
      if (!area.contains(event.relatedTarget as Node | null)) setDropping(false);
    };
    const dropped = (event: DragEvent) => {
      if (!files(event) || ignored(event)) return;
      event.preventDefault();
      if (own) event.stopPropagation();
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
  }, [off, closest, ignoreInside, own, ref]);
  return dropping;
}

// The drop zone's line in a frame.
export const DropLine = ({ limits }: { limits: Limits | null }) => (
  <p className="composer-drop">
    Drop to attach{allowed(limits) && ` · ${allowed(limits)}`}
  </p>
);

// The attached files' chips, above the field.
export function FileChips({
  files,
  limits,
  locked,
  remove,
}: {
  files: Attached[];
  limits: Limits | null;
  locked: boolean;
  remove: (key: number) => void;
}) {
  if (files.length === 0) return null;
  return (
    <ul className="composer-files" aria-label="Attached files">
      {files.map((one) => (
        <FileChip key={one.key} attached={one} unseen={unseen(one, limits)} locked={locked} remove={() => remove(one.key)} />
      ))}
    </ul>
  );
}

// The paperclip at a field's left, with its hidden picker of several files.
export function ClipButton({ limits, disabled, attach }: { limits: Limits | null; disabled: boolean; attach: (files: File[]) => void }) {
  const picker = useRef<HTMLInputElement>(null);
  const said = allowed(limits);
  return (
    <span className="composer-clip">
      <button
        type="button"
        className="clip"
        aria-label="Attach files"
        title={`Attach files${said && `: ${said}`} (or paste, or drop them here)`}
        disabled={disabled}
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
  );
}

// A field of the waiting card that takes files as the composer does (an own answer, a skip's
// comment, a gate's comment): the composer's frame with the files' chips, the paperclip and
// the text, which grows with it from CARD_LINES to MOST_LINES. Files are attached by the
// paperclip, a paste while the focus is in it, or a drop on its frame, which is its own drop
// zone; a file the limits refuse is named under it. `files` are kept by who shows it, and
// the `limits` loaded with it, so a file attached as soon as the field shows is marked by
// them.
export function AnswerBox({
  label,
  text,
  change,
  off,
  locked = false,
  autoFocus = false,
  files,
  setFiles,
  limits,
}: {
  label: string;
  text: string;
  change: (value: string) => void;
  off: boolean; // the field and its files can not change (a stopped session)
  locked?: boolean; // its files upload: no file is removed meanwhile
  autoFocus?: boolean;
  files: Attached[];
  setFiles: SetFiles;
  limits: Limits | null;
}) {
  const [problem, setProblem] = useState<string | null>(null);
  const frame = useRef<HTMLDivElement>(null);
  const field = useRef<HTMLTextAreaElement>(null);
  useGrow(field, text, CARD_LINES, MOST_LINES, frame);
  const attach = (given: File[]) => {
    const { added, problem: refused } = attachFiles(given, files.length, limits);
    setProblem(refused);
    setFiles((now) => [...now, ...added]);
  };
  const remove = (key: number) => {
    release(files.filter((one) => one.key === key));
    setFiles((now) => now.filter((one) => one.key !== key));
  };
  const dropping = useDropZone(frame, attach, { off: off || locked, own: true });
  return (
    <>
      <div
        ref={frame}
        className={`composer-box answer-box${dropping ? " dropping" : ""}`}
        onPaste={(event) => {
          if (off || locked) return;
          const given = pastedFiles(event, limits);
          if (given) attach(given);
        }}
      >
        {dropping && <DropLine limits={limits} />}
        <FileChips files={files} limits={limits} locked={locked || off} remove={remove} />
        <div className="composer-row">
          <ClipButton limits={limits} disabled={off || locked} attach={attach} />
          <textarea
            ref={field}
            className="waiting-field"
            rows={CARD_LINES}
            autoFocus={autoFocus}
            aria-label={label}
            placeholder={label}
            value={text}
            disabled={off}
            onChange={(event) => change(event.target.value)}
          />
        </div>
      </div>
      {problem && (
        <p className="field-problem" role="alert">
          {problem}
        </p>
      )}
    </>
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
