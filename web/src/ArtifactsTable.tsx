// The session's Artifacts tab (docs/design/ui.md, Artifacts): a table of the session's
// artifacts over the whole column, newest first by their latest record, filtered by scope
// (the session's or a run's) and by type, and found by name, title, change and author; a
// narrow column shows each row as a card. A row opens its latest record in the panel over
// the list (ArtifactPanel.tsx). The artifact's page, its row's link for a new tab and the
// panel's "Open in Artifacts tab", leads back with "← Artifacts": its latest record, or
// with ?record= the one an attachment keeps. Live from the feed: a new record moves its
// artifact to the top.
import { useEffect, useRef, useState, type MouseEvent } from "react";
import { Link, useSearchParams } from "react-router";

import { ApiError, getRecord, type ArtifactInfo, type RecordInfo } from "./api";
import { changed, kindOf, size, type Kind } from "./artifacts";
import { ArtifactView, FullName, KindIcon } from "./ArtifactView";
import { useView } from "./Attachments";
import { since } from "./ChatText";
import { MiniAvatar } from "./FeedRow";
import { useLive, useLiveStore, type ListLoaded } from "./live";
import { artifactPath, RECORD_PARAM, sessionPath } from "./paths";

const ALL = "*";

// The type filter's choices: every kind of artifacts.kindOf, or all.
const KINDS: [Kind | typeof ALL, string][] = [
  [ALL, "All types"],
  ["markdown", "Documents"],
  ["text", "Code and text"],
  ["image", "Images"],
  ["html", "HTML"],
  ["other", "Other"],
];

export function Artifacts({ session, artifact }: { session: string; artifact?: string }) {
  const live = useLiveStore();
  useEffect(() => live.watch("artifacts", session), [live, session]);
  const loaded = useLive().artifacts[session] ?? null;
  let shown;
  if (loaded === null) shown = <p className="muted">Loading…</p>;
  else if ("error" in loaded) {
    shown = (
      <p className="problem" role="alert">
        {loaded.error}
      </p>
    );
  } else if (artifact !== undefined) shown = <ArtifactPage session={session} id={artifact} artifacts={loaded} />;
  else shown = <ArtifactsTable session={session} artifacts={loaded.items} />;
  return (
    <section className="artifacts-tab" aria-label="Artifacts">
      {shown}
    </section>
  );
}

function ArtifactsTable({ session, artifacts }: { session: string; artifacts: ArtifactInfo[] }) {
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState(ALL);
  const [kind, setKind] = useState<string>(ALL);
  if (artifacts.length === 0) return <p className="empty">No artifacts yet</p>;
  const runs = [...new Set(artifacts.map((one) => one.scope).filter(Boolean))].sort();
  const wanted = query.trim().toLowerCase();
  const shown = artifacts.filter(
    (one) =>
      (scope === ALL || one.scope === scope) &&
      (kind === ALL || kindOf(one.latest.media_type) === kind) &&
      (!wanted ||
        [one.full_name, one.title ?? "", one.latest.summary ?? "", one.latest.author].some((text) =>
          text.toLowerCase().includes(wanted),
        )),
  );
  return (
    <div className="artifacts-list">
      <div className="artifacts-tools">
        <input
          type="search"
          className="search"
          placeholder="Find an artifact"
          aria-label="Find an artifact"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <select aria-label="Scope" value={scope} onChange={(event) => setScope(event.target.value)}>
          <option value={ALL}>All scopes</option>
          <option value="">Session</option>
          {runs.map((run) => (
            <option key={run} value={run}>
              {run}
            </option>
          ))}
        </select>
        <span className="segments" role="group" aria-label="Type">
          {KINDS.map(([value, label]) => (
            <button key={value} type="button" aria-pressed={kind === value} onClick={() => setKind(value)}>
              {label}
            </button>
          ))}
        </span>
      </div>
      <div className="artifacts-scroll">
        <table className="artifacts-table" aria-label="Artifacts">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Size</th>
              <th>Author</th>
              <th>Updated</th>
              <th>Latest change</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((one) => (
              <Row key={one.id} session={session} artifact={one} />
            ))}
          </tbody>
        </table>
        {shown.length === 0 && <p className="muted list-none">No match</p>}
      </div>
    </div>
  );
}

// A row: a plain click anywhere on it, or on its name's link (also Enter), opens its latest
// record in the panel over the list, with the focus on the link, so closing the panel
// brings it back there. The link keeps the page's address: a click with a modifier or the
// middle button opens the page in a new tab, as the browser does.
function Row({ session, artifact }: { session: string; artifact: ArtifactInfo }) {
  const view = useView(session);
  const link = useRef<HTMLAnchorElement>(null);
  const { latest } = artifact;
  const open = (event: MouseEvent) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    link.current?.focus();
    view(latest.id);
  };
  return (
    <tr onClick={(event) => !(event.target as Element).closest("a") && open(event)}>
      <td className="artifact-cell">
        <KindIcon mediaType={latest.media_type} />
        <span>
          <Link ref={link} to={artifactPath(session, artifact.id)} className="artifact-link" onClick={open}>
            <FullName scope={artifact.scope} name={artifact.name} />
          </Link>
          {artifact.title && <span className="artifact-row-title">{artifact.title}</span>}
        </span>
      </td>
      <td className="numeric">{latest.media_type}</td>
      <td className="numeric">{size(latest.size)}</td>
      <td>
        <span className="artifact-author">
          <MiniAvatar who={latest.author} />
          {latest.author}
        </span>
      </td>
      <td className="numeric">
        <time dateTime={latest.created_at} title={new Date(latest.created_at).toLocaleString()}>
          {since(latest.created_at)} ago
        </time>
      </td>
      <td className="artifact-change">{latest.summary}</td>
    </tr>
  );
}

// An artifact's page: its latest record, or the one ?record= names, which says so when the
// artifact changed since; its Open latest shows the latest in the panel over it.
function ArtifactPage({ session, id, artifacts }: { session: string; id: string; artifacts: ListLoaded<ArtifactInfo> & object }) {
  const view = useView(session);
  const [params] = useSearchParams();
  const wanted = params.get(RECORD_PARAM);
  const artifact = "items" in artifacts ? artifacts.items.find((one) => one.id === id) : undefined;
  const record = useRecord(session, artifact && wanted && wanted !== artifact.latest.id ? wanted : null);
  const back = (
    <p className="crumbs">
      <Link to={sessionPath(session, "artifacts")}>← Artifacts</Link>
    </p>
  );
  if (artifact === undefined) {
    return (
      <div className="artifact-page">
        {back}
        <p className="empty">No artifact {id} in this session</p>
      </div>
    );
  }
  let shown: RecordInfo | null = artifact.latest;
  if (record !== undefined) {
    if (record === null) return <div className="artifact-page">{back}<p className="muted">Loading…</p></div>;
    if ("error" in record) {
      return (
        <div className="artifact-page">
          {back}
          <p className="problem" role="alert">
            {record.error}
          </p>
        </div>
      );
    }
    shown = record;
  }
  const stale = changed({ artifact: artifact.id, hash: shown.hash }, artifacts) === "changed";
  return (
    <div className="artifact-page">
      {back}
      <ArtifactView
        session={session}
        artifact={artifact}
        record={shown}
        latest={stale ? () => view(artifact.latest.id) : undefined}
      />
    </div>
  );
}

// A record that is not the artifact's latest, asked for once: undefined for none wanted.
function useRecord(session: string, record: string | null): RecordInfo | { error: string } | null | undefined {
  const [found, setFound] = useState<{ id: string; got: RecordInfo | { error: string } } | null>(null);
  useEffect(() => {
    if (record === null) return;
    let current = true;
    getRecord(session, record).then(
      (view) => current && setFound({ id: record, got: view.record }),
      (error: unknown) => current && setFound({ id: record, got: { error: error instanceof ApiError ? error.message : String(error) } }),
    );
    return () => {
      current = false;
    };
  }, [session, record]);
  if (record === null) return undefined;
  return found?.id === record ? found.got : null;
}
