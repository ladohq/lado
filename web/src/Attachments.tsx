// The artifacts a message, a gate's note or a run's note carries, as chips (docs/design/ui.md,
// Artifacts): its type's icon, its name and size. In the chat the full name, its run part
// muted; on a gate and in a run's notes, which are of that run, the short name. A chip opens
// the record that was attached in the panel over the page (?view=<record>); when the
// artifact changed since, "changed since · open latest" beside it opens its latest record.
import { useNavigate, useParams, useSearchParams } from "react-router";

import type { AttachmentInfo } from "./api";
import { changed, size } from "./artifacts";
import { FullName, KindIcon } from "./ArtifactView";
import { useLive } from "./live";
import { sessionPath, VIEW_PARAM } from "./paths";

// Opens a record of the session in the panel, as a step of the browser's history (Back
// closes it): over the session's page where it is, else (Needs you) over its Activity tab.
export function useView(session: string): (record: string) => void {
  const [, setParams] = useSearchParams();
  const here = useParams().name === session;
  const navigate = useNavigate();
  return (record) => {
    if (!here) {
      navigate(`${sessionPath(session, "activity")}?${VIEW_PARAM}=${encodeURIComponent(record)}`);
      return;
    }
    setParams((now) => {
      const next = new URLSearchParams(now);
      next.set(VIEW_PARAM, record);
      return next;
    });
  };
}

export function Attachments({
  session,
  attachments,
  short = false,
}: {
  session: string;
  attachments: AttachmentInfo[];
  short?: boolean; // the name without the run: shown where the run is known
}) {
  const artifacts = useLive().artifacts[session];
  const view = useView(session);
  if (attachments.length === 0) return null;
  return (
    <div className="chips">
      {attachments.map((attached) => {
        const chip = (
          <button
            type="button"
            className="chip"
            aria-label={`Open artifact ${attached.full_name}`}
            title={attached.title ? `${attached.full_name} · ${attached.title}` : attached.full_name}
            onClick={() => view(attached.record)}
          >
            <KindIcon mediaType={attached.media_type} />
            <span className="chip-name">
              {short ? <span className="full-name">{attached.name}</span> : <FullName scope={attached.scope} name={attached.name} />}
            </span>
            <span className="chip-size">{size(attached.size)}</span>
          </button>
        );
        const latest = changed(attached, artifacts) === "changed" && artifacts && "items" in artifacts
          ? artifacts.items.find((one) => one.id === attached.artifact)
          : undefined;
        if (!latest) return <span key={attached.record}>{chip}</span>;
        return (
          <span key={attached.record} className="chip-wrap">
            {chip}
            <span className="chip-latest">
              <span className="changed-dot" aria-hidden="true" />
              changed since ·{" "}
              <button
                type="button"
                className="link-button"
                aria-label={`Open latest ${attached.full_name}`}
                onClick={() => view(latest.latest.id)}
              >
                open latest
              </button>
            </span>
          </span>
        );
      })}
    </div>
  );
}
