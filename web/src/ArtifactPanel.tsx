// The panel a chip or a row of the Artifacts tab opens (docs/design/ui.md, Artifacts): the
// record an attachment keeps, or an artifact's latest, on the right over the session's
// page or Needs you; the page stays where it was. Its width is the human's: they drag its
// left edge (the shared Splitter, with a grip) between 400 px and the window's width less
// ROOM_GAP, or Expand it to all that room; both are remembered (prefs.ts,
// lado.artifactPanel). A window with less room than 400 px shows it on the whole screen,
// with no edge or Expand. Its address is the page's with ?view=<record> (on Needs you also
// &session=<name>). Esc, its close button or a click beside it close it, and the focus goes
// back where it was (the chip, the row's link). Its top bar holds every button in one row:
// "Open in Artifacts tab" (the artifact's page with that record) and the viewer's
// ArtifactActions, then Expand and Close; while the record loads or fails, Expand and
// Close only. Below COMPACT_BELOW px (the panel's width, or the
// window's when it takes the whole screen) the actions are icons with tooltips.
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { ApiError, getRecord, type RecordView } from "./api";
import { changed } from "./artifacts";
import { Action, ArtifactActions, ArtifactView } from "./ArtifactView";
import { useView } from "./Attachments";
import { ArtifactsIcon, CloseIcon, ExpandIcon } from "./icons";
import { useLive, useLiveStore } from "./live";
import { artifactPath, VIEW_PARAM, VIEW_SESSION_PARAM } from "./paths";
import { ARTIFACT_PANEL_WIDTH, type ArtifactPanelPrefs, storeArtifactPanel, storedArtifactPanel } from "./prefs";
import { fitWidth, Splitter } from "./Splitter";

// The strip of the page the panel always leaves on its left: a click there closes it.
const ROOM_GAP = 64;
// Under this width the bar's actions lose their labels.
const COMPACT_BELOW = 560;

// The room the window leaves the panel, read again when the window is resized.
function useRoom(): number {
  const [room, setRoom] = useState(() => window.innerWidth - ROOM_GAP);
  useEffect(() => {
    const resized = () => setRoom(window.innerWidth - ROOM_GAP);
    window.addEventListener("resize", resized);
    return () => window.removeEventListener("resize", resized);
  }, []);
  return room;
}

export function ArtifactPanel({ session, record }: { session: string; record: string }) {
  const live = useLiveStore();
  useEffect(() => live.watch("artifacts", session), [live, session]);
  const artifacts = useLive().artifacts[session];
  const [, setParams] = useSearchParams();
  const view = useView(session);
  const [found, setFound] = useState<RecordView | { error: string } | null>(null);
  const opener = useRef<Element | null>(document.activeElement);
  const panel = useRef<HTMLElement>(null);
  const room = useRoom();
  const [prefs, setPrefs] = useState(storedArtifactPanel);
  const choose = (next: ArtifactPanelPrefs) => {
    setPrefs(next);
    storeArtifactPanel(next);
  };
  const narrow = room < ARTIFACT_PANEL_WIDTH.min;
  const width = prefs.expanded ? room : fitWidth(prefs.width, ARTIFACT_PANEL_WIDTH, room);
  const compact = (narrow ? room + ROOM_GAP : width) < COMPACT_BELOW;

  useEffect(() => {
    let current = true;
    setFound(null);
    getRecord(session, record).then(
      (got) => current && setFound(got),
      (error: unknown) => current && setFound({ error: error instanceof ApiError ? error.message : String(error) }),
    );
    return () => {
      current = false;
    };
  }, [session, record]);

  useEffect(() => panel.current?.focus(), []);

  const close = () => {
    setParams((now) => {
      const next = new URLSearchParams(now);
      next.delete(VIEW_PARAM);
      next.delete(VIEW_SESSION_PARAM);
      return next;
    });
    const back = opener.current;
    if (back instanceof HTMLElement && back.isConnected) setTimeout(() => back.focus());
  };
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      console.debug(`[lad99] ${performance.now().toFixed(1)} panel esc key=${event.key}`);
      return event.key === "Escape" && close();
    };
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  });

  // The artifact as the feed has it now, else as it was when the record was asked for.
  const shown = found && "artifact" in found ? found : null;
  const artifact =
    (shown && artifacts && "items" in artifacts && artifacts.items.find((one) => one.id === shown.artifact.id)) ||
    shown?.artifact;
  const stale = shown && artifact && changed({ artifact: artifact.id, hash: shown.record.hash }, artifacts) === "changed";
  const name = artifact ? artifact.full_name : "an artifact";
  return (
    <>
      <div className="panel-scrim" aria-hidden="true" onClick={close} />
      <aside
        className="artifact-panel"
        role="dialog"
        aria-label={`Artifact ${name}`}
        tabIndex={-1}
        ref={panel}
        style={narrow ? undefined : { width }}
      >
        {!narrow && (
          <Splitter
            label="Artifact panel width"
            edge="left"
            width={width}
            bounds={{ ...ARTIFACT_PANEL_WIDTH, max: Math.min(room, ARTIFACT_PANEL_WIDTH.max) }}
            onChange={(chosen) => choose({ width: chosen, expanded: false })}
            grip
          />
        )}
        <div className="panel-top">
          {shown && artifact && (
            <span className="panel-actions">
              <Action label="Open in Artifacts tab" icon={<ArtifactsIcon />} compact={compact}>
                {(look) => <Link {...look} to={artifactPath(session, artifact.id, record)} />}
              </Action>
              <ArtifactActions session={session} artifact={artifact} record={shown.record} compact={compact} />
            </span>
          )}
          {!narrow && (
            <button
              type="button"
              className="icon-button panel-expand"
              aria-label={prefs.expanded ? "Restore width" : "Expand"}
              title={prefs.expanded ? "Restore width" : "Expand"}
              onClick={() => choose({ ...prefs, expanded: !prefs.expanded })}
            >
              <ExpandIcon expanded={prefs.expanded} />
            </button>
          )}
          <button type="button" className="icon-button panel-close" aria-label="Close" onClick={close}>
            <CloseIcon />
          </button>
        </div>
        <div className="panel-body">
          {found === null && <p className="muted">Loading…</p>}
          {found && "error" in found && (
            <p className="problem" role="alert">
              {found.error}
            </p>
          )}
          {shown && artifact && (
            <ArtifactView
              session={session}
              artifact={artifact}
              record={shown.record}
              actions={false}
              latest={stale ? () => view(artifact.latest.id) : undefined}
            />
          )}
        </div>
      </aside>
    </>
  );
}
