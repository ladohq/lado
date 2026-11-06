// The session's Artifacts tab (docs/design/ui.md, Artifacts): the session's artifacts over
// the whole column, newest first by their latest record, filtered by scope (the session's or
// a run's) and by type, and found by name, title, change and author. A column of TABLE_FROM
// px and wider shows a table, a narrower one a list of two lines a row, whose latest change
// is a tooltip. From GROUPS_FROM artifacts both go in groups by scope that fold (prefs.ts,
// lado.artifactGroups). A row opens its latest record in the panel over the list
// (ArtifactPanel.tsx). The artifact's page, its row's link for a new tab and the panel's
// "Open in Artifacts tab", leads back with "← Artifacts": its latest record, or with
// ?record= the one an attachment keeps. Live from the feed: a new record moves its artifact
// to the top.
import { useEffect, useId, useRef, useState, type MouseEvent } from "react";
import { Link, useSearchParams } from "react-router";

import { ApiError, getRecord, type ArtifactInfo, type RecordInfo } from "./api";
import { changed, groupByScope, GROUPS_FROM, kindOf, KINDS, size, type Kind, type ScopeGroup } from "./artifacts";
import { ArtifactView, FullName, KindIcon } from "./ArtifactView";
import { useView } from "./Attachments";
import { since } from "./ChatText";
import { MiniAvatar } from "./FeedRow";
import { isOpen } from "./Flows";
import { GroupHead, type Fold } from "./GroupHead";
import { useLive, useLiveStore, type ListLoaded } from "./live";
import { artifactPath, RECORD_PARAM, sessionPath } from "./paths";
import { storeArtifactGroups, storedArtifactGroups } from "./prefs";
import { useWidth } from "./Splitter";
import { Tooltip } from "./Tooltip";

const ALL = "*";

// From this width the table's six columns fit; narrower, the list.
const TABLE_FROM = 720;

// The type filter's choices: every kind of artifacts.kindOf, or all.
const TYPES: [Kind | typeof ALL, string][] = [
  [ALL, "All types"],
  ...(Object.keys(KINDS) as Kind[]).map((kind): [Kind, string] => [kind, KINDS[kind].filter]),
];

export function Artifacts({ session, artifact }: { session: string; artifact?: string }) {
  const live = useLiveStore();
  useEffect(() => live.watch("artifacts", session), [live, session]);
  useEffect(() => live.watch("runs", session), [live, session]); // which groups start folded
  const state = useLive();
  const loaded = state.artifacts[session] ?? null;
  const runs = state.runs[session];
  // Until the runs are read, or when they fail, no run counts as ended: nothing is hidden.
  const ended = runs && "items" in runs ? runs.items.filter((one) => !isOpen(one)).map((one) => one.name) : [];
  let shown;
  if (loaded === null) shown = <p className="muted">Loading…</p>;
  else if ("error" in loaded) {
    shown = (
      <p className="problem" role="alert">
        {loaded.error}
      </p>
    );
  } else if (artifact !== undefined) shown = <ArtifactPage session={session} id={artifact} artifacts={loaded} />;
  else shown = <ArtifactsTable key={session} session={session} artifacts={loaded.items} ended={ended} />;
  return (
    <section className="artifacts-tab" aria-label="Artifacts">
      {shown}
    </section>
  );
}

// A group as it shows now: its heading's name and fold, and the id `fold.controls` names.
type ShownGroup = ScopeGroup & { name: string; id: string; fold: Fold };

function ArtifactsTable({ session, artifacts, ended }: { session: string; artifacts: ArtifactInfo[]; ended: string[] }) {
  const [root, width] = useWidth<HTMLDivElement>();
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState(ALL);
  const [kind, setKind] = useState<string>(ALL);
  const [folds, setFolds] = useState(() => storedArtifactGroups(session));
  const ids = useId();
  if (artifacts.length === 0) {
    return (
      <div className="empty">
        <p className="empty-title">No artifacts yet</p>
        <p className="empty-line">Agents save plans, reviews, images and mockups here (write_artifact).</p>
      </div>
    );
  }
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
  const fold = (group: string, to: "open" | "folded") => {
    const next = { ...folds, [group]: to };
    setFolds(next);
    storeArtifactGroups(session, next);
  };
  // Counted over the session's artifacts: a filter never changes the look, one scope is flat.
  const groups: ShownGroup[] | null =
    scope === ALL && artifacts.length >= GROUPS_FROM
      ? groupByScope(shown).map((group, at) => {
          const id = `${ids}-${at}`;
          const open = (folds[group.scope] ?? (ended.includes(group.scope) ? "folded" : "open")) === "open";
          return {
            ...group,
            id,
            name: group.scope || "Session",
            fold: {
              open: wanted !== "" || open,
              controls: id,
              onToggle: () => fold(group.scope, open ? "folded" : "open"),
              disabled: wanted !== "",
            },
          };
        })
      : null;
  const View = width !== null && width >= TABLE_FROM ? Table : List;
  return (
    <div ref={root} className="artifacts-list">
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
          {TYPES.map(([value, label]) => (
            <button key={value} type="button" aria-pressed={kind === value} onClick={() => setKind(value)}>
              {label}
            </button>
          ))}
        </span>
      </div>
      <div className="artifacts-scroll">
        <View session={session} artifacts={shown} groups={groups} />
        {shown.length === 0 && <p className="muted list-none">No match</p>}
      </div>
    </div>
  );
}

type ViewProps = { session: string; artifacts: ArtifactInfo[]; groups: ShownGroup[] | null };

// A group's run goes by its exact name, so its heading drops the capitals; Session is a word.
const groupClass = (group: ScopeGroup) => `artifact-group${group.scope ? " of-run" : ""}`;

const groupHead = (group: ShownGroup) => (
  <GroupHead nameId={`${group.id}-name`} name={group.name} count={group.artifacts.length} fold={group.fold} />
);

function Table({ session, artifacts, groups }: ViewProps) {
  return (
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
      {groups === null ? (
        <tbody>
          {artifacts.map((one) => (
            <Row key={one.id} session={session} artifact={one} />
          ))}
        </tbody>
      ) : (
        groups.map((group) => (
          <tbody key={group.scope} id={group.id} className={groupClass(group)}>
            <tr>
              <th colSpan={6} scope="rowgroup">
                {groupHead(group)}
              </th>
            </tr>
            {group.fold.open &&
              group.artifacts.map((one) => <Row key={one.id} session={session} artifact={one} grouped />)}
          </tbody>
        ))
      )}
    </table>
  );
}

function List({ session, artifacts, groups }: ViewProps) {
  if (groups === null) {
    return (
      <ul className="artifact-items" aria-label="Artifacts">
        {artifacts.map((one) => (
          <ArtifactItem key={one.id} session={session} artifact={one} />
        ))}
      </ul>
    );
  }
  return groups.map((group) => (
    <section key={group.scope} className={groupClass(group)} aria-labelledby={`${group.id}-name`}>
      {groupHead(group)}
      <div id={group.id} hidden={!group.fold.open}>
        {group.fold.open && (
          <ul className="artifact-items">
            {group.artifacts.map((one) => (
              <ArtifactItem key={one.id} session={session} artifact={one} grouped />
            ))}
          </ul>
        )}
      </div>
    </section>
  ));
}

const Updated = ({ at }: { at: string }) => (
  <time dateTime={at} title={new Date(at).toLocaleString()}>
    {since(at)} ago
  </time>
);

// How a row opens: a plain click, or Enter on its name's link, opens its latest record in the
// panel over the list, with the focus on the link, so closing the panel brings it back there.
// The link keeps the page's address: a click with a modifier or the middle button opens the
// page in a new tab, as the browser does.
function useRowOpen(session: string, artifact: ArtifactInfo) {
  const view = useView(session);
  const link = useRef<HTMLAnchorElement>(null);
  const open = (event: MouseEvent) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    link.current?.focus();
    view(artifact.latest.id);
  };
  return { link, open };
}

// A row of the list: its link stretches over the row (styles.css), so a press anywhere on it
// is the link's and the tooltip, the latest change, is the row's. In a group the name goes
// without its run, which the heading says.
function ArtifactItem({ session, artifact, grouped = false }: { session: string; artifact: ArtifactInfo; grouped?: boolean }) {
  const { link, open } = useRowOpen(session, artifact);
  const { latest } = artifact;
  return (
    <li className="artifact-item">
      <KindIcon mediaType={latest.media_type} />
      <span className="artifact-item-text">
        <span className="artifact-item-line">
          <Tooltip tip={latest.summary || null}>
            <Link ref={link} to={artifactPath(session, artifact.id)} className="artifact-link" onClick={open}>
              <FullName scope={grouped ? "" : artifact.scope} name={artifact.name} />
            </Link>
          </Tooltip>
          {artifact.title && ` · ${artifact.title}`}
        </span>
        <span className="artifact-item-line artifact-item-meta">
          {KINDS[kindOf(latest.media_type)].word} · {latest.author} · <Updated at={latest.created_at} /> ·{" "}
          {size(latest.size)}
        </span>
      </span>
    </li>
  );
}

// A row of the table: a click anywhere on it opens it, as its link does.
function Row({ session, artifact, grouped = false }: { session: string; artifact: ArtifactInfo; grouped?: boolean }) {
  const { link, open } = useRowOpen(session, artifact);
  const { latest } = artifact;
  return (
    <tr onClick={(event) => !(event.target as Element).closest("a") && open(event)}>
      <td className="artifact-cell">
        <KindIcon mediaType={latest.media_type} />
        <span>
          <Link ref={link} to={artifactPath(session, artifact.id)} className="artifact-link" onClick={open}>
            <FullName scope={grouped ? "" : artifact.scope} name={artifact.name} />
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
        <Updated at={latest.created_at} />
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
