// The panel a chip opens (docs/design/ui.md, Artifacts): the record an attachment keeps, on
// the right over the session's page, min(620px, 100%) wide, the whole screen on a narrow
// one; the page stays where it was. Its address is the page's with ?view=<record>. Esc,
// its close button or a click beside it close it, and the focus goes back where it was (the
// chip). "Open in Artifacts tab" leads to the artifact's page with that record.
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { ApiError, getRecord, type RecordView } from "./api";
import { changed } from "./artifacts";
import { ArtifactView } from "./ArtifactView";
import { useView } from "./Attachments";
import { CloseIcon } from "./icons";
import { useLive, useLiveStore } from "./live";
import { artifactPath, VIEW_PARAM } from "./paths";

export function ArtifactPanel({ session, record }: { session: string; record: string }) {
  const live = useLiveStore();
  useEffect(() => live.watch("artifacts", session), [live, session]);
  const artifacts = useLive().artifacts[session];
  const [, setParams] = useSearchParams();
  const view = useView(session);
  const [found, setFound] = useState<RecordView | { error: string } | null>(null);
  const opener = useRef<Element | null>(document.activeElement);
  const panel = useRef<HTMLElement>(null);

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
      return next;
    });
    const back = opener.current;
    if (back instanceof HTMLElement && back.isConnected) setTimeout(() => back.focus());
  };
  useEffect(() => {
    const key = (event: KeyboardEvent) => event.key === "Escape" && close();
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
      <aside className="artifact-panel" role="dialog" aria-label={`Artifact ${name}`} tabIndex={-1} ref={panel}>
        <div className="panel-top">
          {artifact && (
            <Link className="quiet" to={artifactPath(session, artifact.id, record)}>
              Open in Artifacts tab
            </Link>
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
              latest={stale ? () => view(artifact.latest.id) : undefined}
            />
          )}
        </div>
      </aside>
    </>
  );
}
