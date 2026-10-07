// A flow gate in the session's feed (docs/design/ui.md, The human in the session): open, a
// card in the gate's row (FeedRow) the human answers with one of its options and a comment
// for the next step; closed, a quiet line with its answer that opens read only. The card has
// no head of its own: the row, Needs you's row or a run's page names the gate (gateTitle).
// The answer goes through the server to runs.answer, as `lado answer` and the popup do; the
// card changes only when the feed brings the closed gate, whoever answered it.
import { useState } from "react";

import { answerGate, ApiError, type GateInfo } from "./api";
import { Body, clock, Preview } from "./ChatText";
import { FeedRow } from "./FeedRow";

const NOTE_LINES = 20; // the lines of the note before the gate shown before Show all

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
    <GateLine gate={gate} />
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

// The human's answer to a gate, also as the human's own row where it was given (the gate's
// line stays where the gate opened): the answer, which leads to the line (`go`: the chat's
// way to a card, which loads up to it), and the comment.
export function GateAnswer({ gate, go }: { gate: GateInfo; go: (anchor: string) => void }) {
  const link = (
    <a
      href={`#${gateAnchor(gate.id)}`}
      onClick={(event) => {
        event.preventDefault();
        go(gateAnchor(gate.id));
      }}
    >
      gate #{gate.id}: {gate.answer}
    </a>
  );
  return (
    <FeedRow kind="human" who="You" aside={link} at={gate.answered_at ?? gate.created_at} label={`Your answer to gate #${gate.id}`}>
      {gate.comment && <p className="gate-comment">{gate.comment}</p>}
    </FeedRow>
  );
}

// The card of an open gate, no head. `compact` (a run's page in Flows, where the notes are
// in the run's history): without the note that led to it and the notes it needs.
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
    </div>
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
          {gateTitle(gate)}: {gate.answer} by {gate.answered_by}
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
