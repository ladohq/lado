// A flow gate in the session's feed (docs/design/ui.md, The human in the session): open, a
// card in the gate's row (FeedRow) the human answers with one of its options and a comment
// for the next step; closed, a quiet line with its answer that opens read only. The card has
// no head of its own: the row, Needs you's row or a run's page names the gate (gateTitle).
// The answer goes through the server to runs.answer, as `lado answer` and the popup do; the
// card changes only when the feed brings the closed gate, whoever answered it.
import { useState } from "react";

import { answerGate, ApiError, type GateInfo } from "./api";
import { size } from "./artifacts";
import { KindIcon } from "./ArtifactView";
import { Attachments, useView } from "./Attachments";
import { clock, Preview } from "./ChatText";
import { FeedRow } from "./FeedRow";
import { useLive } from "./live";

const NOTE_LINES = 20; // the lines of the note before the gate shown before Show more

// How a button names an option, by the gate's kind; a choice gate's options are its own.
const LABELS: Record<string, Record<string, string>> = {
  approval: { approve: "Approve", reject: "Reject" },
  loop: { continue: "Continue", cancel: "Cancel run" },
};

// How a gate is named wherever one title stands for it (a closed gate's line, a run's page).
export const gateTitle = (gate: GateInfo) => `Gate #${gate.id} · ${gate.run} · ${gate.state}`;

// A gate in the chat: open, its row with the card; closed, its line.
export function Gate({ session, gate, stopped }: { session: string; gate: GateInfo; stopped: boolean }) {
  return gate.answer === null ? (
    <GateRow session={session} gate={gate} stopped={stopped} aside={`${gate.run} · ${gate.state}`} />
  ) : (
    <GateLine session={session} gate={gate} />
  );
}

// An open gate's row: the flag, "Gate #id", `aside`, when it opened, and its card.
export function GateRow({ session, gate, stopped, aside }: { session: string; gate: GateInfo; stopped: boolean; aside: string }) {
  return (
    <FeedRow kind="gate" who={`Gate #${gate.id}`} aside={aside} at={gate.created_at} label={`Gate #${gate.id}`} id={gateAnchor(gate.id)}>
      <GateCard session={session} gate={gate} stopped={stopped} />
    </FeedRow>
  );
}

// The DOM id of a gate's place in the feed, for the hint over the composer and the answer.
export const gateAnchor = (id: number) => `gate-${id}`;

// The card of an open gate, no head: the question, the note that led to it in full with its
// chips, then the artifacts it reads. `compact` (a run's page in Flows, where the notes are
// in the run's history): without the note and the artifacts.
export function GateCard({
  session,
  gate,
  stopped,
  compact = false,
}: {
  session: string;
  gate: GateInfo;
  stopped: boolean;
  compact?: boolean;
}) {
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function answer(option: string) {
    setBusy(true);
    setProblem(null);
    try {
      await answerGate(session, gate.id, option, comment);
    } catch (error) {
      setProblem(error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="chat-gate open">
      <p className="gate-question">{gate.question}</p>
      {!compact && <Note session={session} gate={gate} />}
      {!compact && gate.problem && <p className="problem gate-problem">Artifacts it reads cannot be shown: {gate.problem}</p>}
      {!compact && <Reads session={session} names={gate.reads ?? []} />}
      <form className="answer" onSubmit={(event) => event.preventDefault()}>
        <textarea
          aria-label="Comment for the next step (optional)"
          placeholder="Comment for the next step (optional)"
          rows={2}
          value={comment}
          onChange={(event) => setComment(event.target.value)}
        />
        <div className="choices">
          {gate.options.map((option, i) => (
            <button
              key={option}
              type="button"
              className={i === 0 ? "primary" : "quiet"}
              disabled={busy || stopped}
              onClick={() => void answer(option)}
            >
              {LABELS[gate.kind]?.[option] ?? option}
            </button>
          ))}
        </div>
        {stopped && <p className="chat-note">The session is stopped: resume it to answer.</p>}
        {problem && (
          <p className="field-problem" role="alert">
            {problem}
          </p>
        )}
      </form>
    </div>
  );
}

// The note of the step that led to the gate: its summary, then its body at once, and its
// artifacts as chips with their short names (they are the run's).
function Note({ session, gate }: { session: string; gate: GateInfo }) {
  if (!gate.note && !gate.note_body && gate.attachments.length === 0) return null;
  return (
    <div className="gate-note">
      {gate.note && (
        <p className="gate-note-summary">
          <strong>{gate.note}</strong>
        </p>
      )}
      {gate.note_body && <Preview text={gate.note_body} lines={NOTE_LINES} />}
      <Attachments session={session} attachments={gate.attachments} short />
    </div>
  );
}

// The artifacts the gate reads, by their full names (the core leaves out those its note
// carries), under a muted "It reads": each as of its latest record among the feed's
// artifacts, so a write while the gate is open shows at once. A chip opens that record;
// before the session's artifacts are loaded, a name alone.
function Reads({ session, names }: { session: string; names: string[] }) {
  const artifacts = useLive().artifacts[session];
  const view = useView(session);
  if (names.length === 0) return null;
  const items = artifacts && "items" in artifacts ? artifacts.items : undefined;
  return (
    <>
      <p className="gate-reads-label" aria-hidden="true">It reads</p>
      <ul className="gate-reads" aria-label="Artifacts it reads">
        {names.map((name) => {
          const found = items?.find((one) => one.full_name === name);
          const short = name.slice(name.lastIndexOf("/") + 1);
          if (!found) return <li key={name} className="gate-read muted">{short}{items && ": no record yet"}</li>;
          const about = [found.title, found.latest.summary].filter(Boolean).join(" — ");
          return (
            <li key={name} className="gate-read">
              <button
                type="button"
                className="chip"
                aria-label={`Open artifact ${found.full_name}`}
                title={found.title ? `${found.full_name} · ${found.title}` : found.full_name}
                onClick={() => view(found.latest.id)}
              >
                <KindIcon mediaType={found.latest.media_type} />
                <span className="chip-name">
                  <span className="full-name">{found.name}</span>
                </span>
                <span className="chip-size">{size(found.latest.size)}</span>
              </button>
              {about && <span className="gate-read-about">{about}</span>}
            </li>
          );
        })}
      </ul>
    </>
  );
}

// A closed gate: who answered what, the comment; the question and the note on a click.
function GateLine({ session, gate }: { session: string; gate: GateInfo }) {
  const [shown, setShown] = useState(false);
  const when = gate.answered_at ?? gate.created_at;
  return (
    <article className="chat-gate closed" id={gateAnchor(gate.id)} aria-label={`Gate #${gate.id}`}>
      <div className="gate-line">
        <button type="button" className="gate-toggle" aria-expanded={shown} onClick={() => setShown(!shown)}>
          {gateTitle(gate)}: {gate.answer} by {gate.answered_by}
        </button>
        <time dateTime={when}>{clock(when)}</time>
      </div>
      {gate.comment && <p className="gate-comment">{gate.comment}</p>}
      {shown && (
        <div className="gate-closed-text">
          <p className="gate-question">{gate.question}</p>
          <Note session={session} gate={gate} />
        </div>
      )}
    </article>
  );
}
