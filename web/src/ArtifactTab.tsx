// One record alone in a tab of its own, a bare page outside the Shell (docs/design/ui.md,
// The artifact's tab): /view/<session>/<record>, the viewer's Open in new tab. Only the
// record's body, by ArtifactBody as the viewer shows it; no rail, top bar, head or buttons.
// The record is read once: it never changes, so no feed and no polling. A refusal shows the
// server's message here; the Shell stays the one listener for a 401 (api.ts). HTML goes to
// its content address, under the server's sandbox headers, with no frame inside a frame.
import { useEffect, useState } from "react";
import { useParams } from "react-router";

import { ApiError, contentPath, getRecord, type RecordView } from "./api";
import { kindOf } from "./artifacts";
import { ArtifactBody } from "./ArtifactView";

const leave = (url: string) => window.location.replace(url);

export function ArtifactTab({
  session,
  record,
  replace = leave,
}: {
  session: string;
  record: string;
  replace?: (url: string) => void; // leaves the page for another address (a test watches it)
}) {
  const [found, setFound] = useState<RecordView | { error: string } | null>(null);

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

  const shown = found && "artifact" in found ? found : null;
  const kind = shown && kindOf(shown.record.media_type);
  useEffect(() => {
    if (!shown) return;
    document.title = shown.artifact.full_name;
    if (kind === "html") replace(contentPath(session, shown.record.id));
  }, [shown, kind, session, replace]);

  if (found === null || kind === "html") {
    return (
      <main className="artifact-tab">
        <p className="muted">Loading…</p>
      </main>
    );
  }
  if ("error" in found) {
    return (
      <main className="artifact-tab">
        <p className="problem" role="alert">
          {found.error}
        </p>
      </main>
    );
  }
  return (
    <main className={`artifact-tab artifact-tab-${kind}`}>
      <ArtifactBody session={session} artifact={found.artifact} record={found.record} />
    </main>
  );
}

// The route's page: /view/:session/:record.
export function ArtifactTabPage() {
  const { session = "", record = "" } = useParams();
  return <ArtifactTab session={session} record={record} />;
}
