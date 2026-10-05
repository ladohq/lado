// A flow gate in the session's feed (docs/design/ui.md, The human in the session): open, a
// card the human answers with one of its options and a comment for the next step; closed, a
// line with its answer that opens read only. The answer goes through the server to
// runs.answer, as `lado answer` and the popup do; the card changes only when the feed
// brings the closed gate, whoever answered it.
import { useState } from "react";

import { answerGate, ApiError, type GateInfo } from "./api";
import { Body, clock, Preview } from "./ChatText";

const NOTE_LINES = 20; // the lines of the note before the gate shown before Show all

// How a button names an option, by the gate's kind; a choice gate's options are its own.
const LABELS: Record<string, Record<string, string>> = {
  approval: { approve: "Approve", reject: "Reject" },
  loop: { continue: "Continue", cancel: "Cancel run" },
};

const title = (gate: GateInfo) => `Gate #${gate.id} · ${gate.run} · ${gate.state}`;

// `compact` (a run's page in Flows, where the notes are in the run's history): an open gate's
// card without the note that led to it and the notes it needs.
export function Gate({
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
  return gate.answer === null ? (
    <GateCard session={session} gate={gate} stopped={stopped} compact={compact} />
  ) : (
    <GateLine gate={gate} />
  );
}

// The DOM id of a gate's place in the feed, for the hint over the composer and the answer.
export const gateAnchor = (id: number) => `gate-${id}`;

// The human's answer to a gate, also as the human's own bubble where it was given (the
// gate's line stays where the gate opened): the answer, the comment; it leads to the line
// (`go`: the chat's way to a card, which loads up to it).
export function GateAnswer({ gate, go }: { gate: GateInfo; go: (anchor: string) => void }) {
  const when = gate.answered_at ?? gate.created_at;
  return (
    <article className="chat-message mine" aria-label={`Your answer to gate #${gate.id}`}>
      <header className="chat-meta">
        <span className="chat-from">you</span>
        <time dateTime={when}>{clock(when)}</time>
      </header>
      <h4 className="chat-summary">
        <a
          href={`#${gateAnchor(gate.id)}`}
          onClick={(event) => {
            event.preventDefault();
            go(gateAnchor(gate.id));
          }}
        >
          Gate #{gate.id} · {gate.answer}
        </a>
      </h4>
      {gate.comment && <p className="gate-comment">{gate.comment}</p>}
    </article>
  );
}

function GateCard({
  session,
  gate,
  stopped,
  compact,
}: {
  session: string;
  gate: GateInfo;
  stopped: boolean;
  compact: boolean;
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
    <article className="chat-gate open" id={gateAnchor(gate.id)} aria-label={`Gate #${gate.id}`}>
      <header className="chat-meta">
        <h4 className="gate-title">{title(gate)}</h4>
        <time dateTime={gate.created_at}>{clock(gate.created_at)}</time>
      </header>
      <p className="gate-question">{gate.question}</p>
      {!compact && <Note gate={gate} />}
      {!compact && gate.problem && <p className="problem gate-problem">Notes it needs cannot be shown: {gate.problem}</p>}
      {!compact && gate.needs && gate.needs.length > 0 && (
        <ul className="gate-needs" aria-label="Notes it needs">
          {gate.needs.map((need) => (
            <Needed key={need.state} need={need} />
          ))}
        </ul>
      )}
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
    </article>
  );
}

// The note of the step that led to the gate: its summary, then its body at once.
function Note({ gate }: { gate: GateInfo }) {
  if (!gate.note && !gate.note_body) return null;
  return (
    <div className="gate-note">
      {gate.note && (
        <p className="gate-note-summary">
          <strong>{gate.note}</strong>
        </p>
      )}
      {gate.note_body && <Preview text={gate.note_body} lines={NOTE_LINES} />}
    </div>
  );
}

type Need = NonNullable<GateInfo["needs"]>[number];

// A note the gate state needs: one line, its body behind a click; or that there is none yet.
function Needed({ need }: { need: Need }) {
  const [shown, setShown] = useState(false);
  const { note } = need;
  if (note === null) return <li className="gate-need muted">Note from {need.state}: no note yet</li>;
  return (
    <li className="gate-need">
      <button type="button" className="link-button" aria-expanded={shown} onClick={() => setShown(!shown)}>
        Note from {need.state}: {note.summary}
      </button>
      {shown && note.body && <Body text={note.body} />}
    </li>
  );
}

// A closed gate: who answered what, the comment; the question and the note on a click.
function GateLine({ gate }: { gate: GateInfo }) {
  const [shown, setShown] = useState(false);
  const when = gate.answered_at ?? gate.created_at;
  return (
    <article className="chat-gate closed" id={gateAnchor(gate.id)} aria-label={`Gate #${gate.id}`}>
      <div className="gate-line">
        <button type="button" className="gate-toggle" aria-expanded={shown} onClick={() => setShown(!shown)}>
          {title(gate)}: {gate.answer} by {gate.answered_by}
        </button>
        <time dateTime={when}>{clock(when)}</time>
      </div>
      {gate.comment && <p className="gate-comment">{gate.comment}</p>}
      {shown && (
        <div className="gate-closed-text">
          <p className="gate-question">{gate.question}</p>
          <Note gate={gate} />
        </div>
      )}
    </article>
  );
}
