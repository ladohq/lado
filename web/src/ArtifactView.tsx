// An artifact's record as the human sees it (docs/design/ui.md, Artifacts): one component
// for the artifact's page in the Artifacts tab and for the panel a chip opens. Its head
// names the artifact, who wrote the record when and what changed, with Download and Copy
// link, and Open in new tab for what the browser can show (the bare page of ArtifactTab, or
// HTML's content address); its body, ArtifactBody, by media type (artifacts.kindOf): Markdown as the chat shows it (no raw
// HTML), text and code with line numbers, an image (a click shows it at full size), HTML in
// a frame sandboxed without the UI's origin, anything else as facts and a download. Text is
// read up to TEXT_LIMIT bytes and no more. The content comes from the server under its
// sandbox headers (server/app.py, _content_headers).
import { useEffect, useState, type ReactNode } from "react";

import { ApiError, contentPath, getContent, type ArtifactInfo, type RecordInfo } from "./api";
import { kindOf, scopePart, size, type Kind } from "./artifacts";
import { Body, since } from "./ChatText";
import { CopyButton } from "./Copy";
import { MiniAvatar } from "./FeedRow";
import {
  BinaryIcon,
  CloseIcon,
  CodeIcon,
  DocumentIcon,
  DownloadIcon,
  HtmlIcon,
  ImageIcon,
  LinkIcon,
  OpenTabIcon,
  ShieldIcon,
} from "./icons";
import { artifactPath, viewPath } from "./paths";

// The bytes of a text the viewer reads at most; the rest is a download.
export const TEXT_LIMIT = 1024 * 1024;

const KIND_ICONS: Record<Kind, () => ReactNode> = {
  markdown: DocumentIcon,
  text: CodeIcon,
  html: HtmlIcon,
  image: ImageIcon,
  other: BinaryIcon,
};

// A media type's icon on its tile, coloured by kind.
export function KindIcon({ mediaType }: { mediaType: string }) {
  const kind = kindOf(mediaType);
  const Icon = KIND_ICONS[kind];
  return (
    <span className={`kind-icon kind-${kind}`} aria-hidden="true">
      <Icon />
    </span>
  );
}

// A full name with its run part muted: "feature/x/" then "design".
export function FullName({ scope, name }: { scope: string; name: string }) {
  return (
    <span className="full-name">
      {scope && <span className="scope-part">{scopePart(scope)}</span>}
      {name}
    </span>
  );
}

export function ArtifactView({
  session,
  artifact,
  record,
  latest,
}: {
  session: string;
  artifact: ArtifactInfo;
  record: RecordInfo; // the one shown: its latest, or one an attachment keeps
  latest?: () => void; // the artifact changed since this record: opens its latest
}) {
  const kind = kindOf(record.media_type);
  const download = contentPath(session, record.id, true);
  const link = `${window.location.origin}${artifactPath(session, artifact.id, record.id === artifact.latest.id ? undefined : record.id)}`;
  const where = record.run ? `${record.state ?? ""}` : "session";
  // The record shown alone: HTML at its content address, under the server's sandbox; the
  // other kinds the browser shows in the bare page; `other` only downloads, as Download does.
  const tab = kind === "html" ? contentPath(session, record.id) : viewPath(session, record.id);
  return (
    <div className="artifact-view">
      <header className="artifact-head">
        <div className="artifact-line">
          <span className="artifact-name">
            <KindIcon mediaType={record.media_type} />
            <FullName scope={artifact.scope} name={artifact.name} />
          </span>
          <span className="artifact-actions">
            {kind !== "other" && (
              <a className="quiet" href={tab} target="_blank" rel="noopener noreferrer">
                <OpenTabIcon />
                Open in new tab
              </a>
            )}
            <a className="quiet" href={download} download>
              <DownloadIcon />
              Download
            </a>
            <CopyButton
              label="Copy link"
              copied="Link copied"
              text={link}
              field={{ title: `Link to ${artifact.full_name}`, label: "Link" }}
              icon={<LinkIcon />}
            />
          </span>
        </div>
        {artifact.title && <h2 className="artifact-title">{artifact.title}</h2>}
        <p className="artifact-meta">
          <MiniAvatar who={record.author} />
          <span>{record.author}</span>
          <span aria-hidden="true">·</span>
          <time dateTime={record.created_at} title={new Date(record.created_at).toLocaleString()}>
            {since(record.created_at)} ago
          </time>
          <span aria-hidden="true">·</span>
          <span className="pill">{where}</span>
          <span aria-hidden="true">·</span>
          <span>{record.media_type}</span>
          <span aria-hidden="true">·</span>
          <span>{size(record.size)}</span>
        </p>
        {record.summary && (
          <p className="artifact-summary">
            <span className="muted">Change:</span> {record.summary}
          </p>
        )}
      </header>
      {latest && (
        <p className="artifact-stale" role="status">
          <span>
            <b>{artifact.full_name}</b> changed since this record
            {artifact.latest.summary ? `: ${artifact.latest.summary}` : ""}.
          </span>
          <button type="button" className="link-button" onClick={latest}>
            Open latest
          </button>
        </p>
      )}
      <div className="artifact-body">
        <ArtifactBody session={session} artifact={artifact} record={record} />
      </div>
    </div>
  );
}

// A record's content by its kind, the one renderer of the viewer and of the artifact's tab.
export function ArtifactBody({ session, artifact, record }: { session: string; artifact: ArtifactInfo; record: RecordInfo }) {
  const kind = kindOf(record.media_type);
  const src = contentPath(session, record.id);
  if (kind === "image") return <Picture src={src} alt={artifact.title ?? artifact.full_name} name={artifact.full_name} />;
  if (kind === "html") {
    return (
      <div className="html-frame">
        <p className="html-bar">
          <ShieldIcon />
          Runs sandboxed: its scripts work, it cannot reach LADO
        </p>
        {/* Never allow-same-origin: the page would be the UI's, with its cookie. */}
        <iframe sandbox="allow-scripts" src={src} title={artifact.full_name} />
      </div>
    );
  }
  if (kind === "other") {
    return (
      <section className="artifact-facts" aria-label="Not shown in the browser">
        <KindIcon mediaType={record.media_type} />
        <div>
          <p>
            <b>Not shown in the browser</b>
          </p>
          <dl>
            <dt>Media type</dt>
            <dd>{record.media_type}</dd>
            <dt>Size</dt>
            <dd>
              {size(record.size)} ({record.size} bytes)
            </dd>
            <dt>SHA-256</dt>
            <dd>{record.hash}</dd>
          </dl>
          <a className="primary" href={contentPath(session, record.id, true)} download>
            Download
          </a>
        </div>
      </section>
    );
  }
  return <Text session={session} artifact={artifact} record={record} markdown={kind === "markdown"} />;
}

type Read = { text: string; cut: boolean } | { error: string; missing: boolean } | null;

// A text record's content, read up to TEXT_LIMIT bytes, then the read is cancelled: a
// record may hold 25 MB the browser need not take.
function useText(session: string, record: string): Read {
  const [read, setRead] = useState<Read>(null);
  useEffect(() => {
    const abort = new AbortController();
    setRead(null);
    getContent(session, record, abort.signal)
      .then(readUpTo)
      .then(
        (got) => !abort.signal.aborted && setRead(got),
        (error: unknown) => {
          if (abort.signal.aborted) return;
          const missing = error instanceof ApiError && error.status === 500;
          setRead({ error: error instanceof Error ? error.message : String(error), missing });
        },
      );
    return () => abort.abort();
  }, [session, record]);
  return read;
}

async function readUpTo(answer: Response): Promise<{ text: string; cut: boolean }> {
  const reader = answer.body?.getReader();
  if (!reader) return { text: "", cut: false };
  const decoder = new TextDecoder();
  let text = "";
  let taken = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) return { text: text + decoder.decode(), cut: false };
    const room = TEXT_LIMIT - taken;
    if (value.length >= room) {
      text += decoder.decode(value.subarray(0, room));
      await reader.cancel();
      return { text, cut: true };
    }
    taken += value.length;
    text += decoder.decode(value, { stream: true });
  }
}

function Text({ session, artifact, record, markdown }: { session: string; artifact: ArtifactInfo; record: RecordInfo; markdown: boolean }) {
  const read = useText(session, record.id);
  const [wrap, setWrap] = useState(false);
  if (read === null) return <p className="muted">Loading…</p>;
  if ("error" in read) return <Failed error={read.error} missing={read.missing} />;
  const cut = read.cut && (
    <p className="artifact-cut">
      Shown: the first {size(TEXT_LIMIT)} of {size(record.size)}.{" "}
      <a href={contentPath(session, record.id, true)} download>
        Download
      </a>{" "}
      for all of it.
    </p>
  );
  if (markdown) {
    return (
      <>
        {cut}
        <article className="artifact-markdown">
          <Body text={read.text} />
        </article>
      </>
    );
  }
  const lines = read.text.replace(/\n$/, "").split("\n");
  return (
    <>
      {cut}
      <div className={`code-view${wrap ? " wrap" : ""}`}>
        <p className="code-bar">
          <span>
            {lines.length} {lines.length === 1 ? "line" : "lines"} · {record.media_type}
          </span>
          <button type="button" className="link-button" aria-pressed={wrap} onClick={() => setWrap(!wrap)}>
            Wrap lines
          </button>
        </p>
        <div className="code-scroll">
          <table aria-label={artifact.full_name}>
            <tbody>
              {lines.map((line, i) => (
                <tr key={i}>
                  <td className="line-number">{i + 1}</td>
                  <td className="line">{line}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

// Content the server could not give: missing from the store (a 500, the core's loud error)
// says what to do; any other failure as it came.
function Failed({ error, missing }: { error: string; missing: boolean }) {
  if (!missing) {
    return (
      <p className="problem" role="alert">
        {error}
      </p>
    );
  }
  return (
    <div className="artifact-missing" role="alert">
      <h4>The content of this artifact is missing</h4>
      <p>{error}</p>
      <p className="muted">
        Usually a file under <code>LADO_HOME/artifacts</code> was removed by hand. <code>lado doctor</code> shows the
        store; the agent can write the artifact again.
      </p>
    </div>
  );
}

// An image fitted to the column; a click shows it at its own size until Esc or a click.
function Picture({ src, alt, name }: { src: string; alt: string; name: string }) {
  const [full, setFull] = useState(false);
  return (
    <>
      <div className="image-frame">
        <img src={src} alt={alt} onClick={() => setFull(true)} />
      </div>
      {full && (
        <div
          className="lightbox"
          role="dialog"
          aria-label={`${name} at full size`}
          tabIndex={-1}
          ref={(box) => box?.focus()}
          onClick={() => setFull(false)}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.stopPropagation();
              setFull(false);
            }
          }}
        >
          <p className="lightbox-bar">
            <CloseIcon /> Esc or a click closes it
          </p>
          <img src={src} alt="" />
        </div>
      )}
    </>
  );
}
