// A flow gate (docs/design/ui.md, The human in the session): open, its panel (GatePanel),
// answered with one of its options and a comment for the next step, in its tab of the
// waiting card or as a whole card on a run's page (GateCard); closed, a folded card in the
// feed with its answer that opens read only (GateLine). The answer goes through the server to
// runs.answer, as `lado answer` and the popup do; the panel changes only when the feed brings
// the closed gate, whoever answered it.
import { useState, type ReactNode } from "react";

import { answerGate, ApiError, HUMAN, type GateInfo, type Limits, type RunEventInfo, type RunInfo } from "./api";
import { AnswerBox, filesLine, uploadFiles, useLimits, useOwnFiles, type Attached, type SetFiles } from "./attachFiles";
import { closedBy, gateAttempt, looks } from "./attempts";
import { KindIcon } from "./ArtifactView";
import { AttachmentChips, Attachments, useView } from "./Attachments";
import { Body, clock, Preview } from "./ChatText";
import { MiniAvatar } from "./FeedRow";
import { CARD_LINES, MOST_LINES } from "./fieldHeight";
import { OutcomeChip } from "./flowSteps";
import { ChevronIcon, GateIcon } from "./icons";
import { useLive, useLiveStore, useLocked } from "./live";
import { useMedia } from "./phone";
import { quoteArea } from "./quote";
import { disagreed, primaryOf } from "./Recommendation";
import { ActionProblem, CardBody, STOPPED_NOTE, WAITING_NOTE, type CardShape } from "./waitingParts";

const NOTE_LINES = 20; // the lines of the note before the gate shown before Show more
const CLOSED_NOTE_LINES = 6; // the same in a closed gate's card, its Note line opened
const COMMENT = "Comment for the next step (optional)";
const NARROW = "(max-width: 600px)"; // a narrow window's placeholder is shorter

// How a button names an option, by the gate's kind; a choice gate's options are its own.
const LABELS: Record<string, Record<string, string>> = {
  approval: { approve: "Approve", reject: "Reject" },
  loop: { continue: "Continue", cancel: "Cancel run" },
};

const label = (gate: GateInfo) => (option: string) => LABELS[gate.kind]?.[option] ?? option;

// What an error calls a button's action.
const whatOf = (gate: GateInfo, option: string) =>
  gate.kind !== "approval" ? "Answer" : option === "approve" ? "Approval" : option === "reject" ? "Rejection" : "Answer";

// How a gate is named wherever one title stands for it (a closed gate's line).
export const gateTitle = (gate: GateInfo) => `Gate #${gate.id} · ${gate.run} · ${gate.state}`;

// The DOM id of a gate's place in the feed: a link to it (Needs you, a notification) shows
// its tab while it is open, and scrolls to its line once closed.
export const gateAnchor = (id: number) => `gate-${id}`;

const noMeasure = () => {};

// An open gate on its run's page in Flows: the waiting card's panel without tabs, whole (the
// page scrolls), `kicker` over its question; its field opens on 3 lines.
export function GateCard({ session, gate, stopped, kicker }: { session: string; gate: GateInfo; stopped: boolean; kicker?: string }) {
  const card: CardShape = {
    expanded: false,
    whole: true,
    chat: false,
    phone: false,
    fieldLines: [CARD_LINES, MOST_LINES],
    headId: `gate-${gate.id}-head`,
    feedRoom: null,
    recHeight: null,
    setRecHeight: noMeasure,
    head: noMeasure,
    foot: noMeasure,
  };
  return (
    <section className="waiting-panel solo whole" aria-labelledby={card.headId}>
      <GatePanel session={session} gate={gate} stopped={stopped} card={card} kicker={kicker} />
    </section>
  );
}

// What answers an open gate, as a tab of the waiting card (waitingParts.tsx) or on a run's
// page: the question its head, the note that led to it and its documents' chips its report,
// then in the footer the supervisor's recommendation (Recommendation.tsx), the comment for the
// next step and a button per option, the recommended one primary. `marked`, the gate a link
// asked for. `comment` and `onComment`, `files` and `onFiles`: the comment and its files kept
// by who shows the panel (the waiting card, across its tabs and its expanded view), else here.
// The comment takes files as the composer does (attachFiles.AnswerBox); their count and size
// stand beside the buttons, and a button uploads those not uploaded yet, then answers with
// their names.
export function GatePanel({
  session,
  gate,
  stopped,
  card,
  kicker,
  marked = false,
  comment: kept,
  onComment,
  files: keptFiles,
  onFiles,
  limits: given,
}: {
  session: string;
  gate: GateInfo;
  stopped: boolean;
  card: CardShape;
  kicker?: string;
  marked?: boolean;
  comment?: string;
  onComment?: (comment: string) => void;
  files?: Attached[];
  onFiles?: SetFiles;
  limits?: Limits | null; // the card's; alone, the panel loads its own
}) {
  const loaded = useLimits(given === undefined);
  const limits = given !== undefined ? given : loaded;
  const [own, setOwn] = useState("");
  const comment = kept ?? own;
  const setComment = onComment ?? setOwn;
  const [ownFiles, setOwnFiles] = useOwnFiles();
  const files = keptFiles ?? ownFiles;
  const setFiles = onFiles ?? setOwnFiles;
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const primary = primaryOf(gate.options, gate.recommendation);
  const live = useLiveStore();
  const { lost } = useLive();
  const narrow = useMedia(NARROW);
  const attempt = gateAttempt(session, gate.id);
  const locked = useLocked(attempt);

  async function answer(option: string) {
    setBusy(true);
    setProblem(null);
    live.attempts.clear(attempt);
    try {
      const uploaded = await uploadFiles(session, files, setFiles, "answer again");
      if ("problem" in uploaded) {
        setProblem(uploaded.problem);
        return;
      }
      await live.attempts.send(attempt, {
        what: whatOf(gate, option),
        repeat: () => answerGate(session, gate.id, option, comment, uploaded.names),
        look: looks.gate(session, gate.id),
        closed: closedBy.gate,
        reached: () => {}, // the card goes by the live lists
      });
    } catch (error) {
      setProblem(error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  const buttons = [
    ...gate.options.map((option) => (
      <button
        key={option}
        type="button"
        className={`${option === primary ? "primary" : "quiet"}${lost ? " locked" : ""}`}
        disabled={busy || stopped || locked}
        onClick={() => void answer(option)}
      >
        {label(gate)(option)}
      </button>
    )),
    files.length > 0 && (
      <span key="files" className="waiting-count">
        {filesLine(files)}
      </span>
    ),
    lost && (
      <span key="waits" className="lost-note">
        {WAITING_NOTE}
      </span>
    ),
  ];
  const area = quoteArea(session);
  const reads = (gate.reads ?? []).filter((name) => !gate.attachments.some((one) => one.full_name === name));
  const report = (gate.note || gate.note_body || gate.attachments.length > 0 || gate.problem || reads.length > 0) && (
    <>
      <Note gate={gate} />
      {gate.problem && <p className="problem gate-problem">Artifacts it reads cannot be shown: {gate.problem}</p>}
      {(gate.attachments.length > 0 || reads.length > 0) && (
        <div className="chips">
          <AttachmentChips session={session} attachments={gate.attachments} titled />
          <Reads session={session} names={reads} />
        </div>
      )}
    </>
  );
  return (
    <CardBody
      card={card}
      title={gate.question}
      kicker={kicker}
      item={gate.id}
      marked={marked}
      area={area}
      report={report}
      rec={{ rec: gate.recommendation, options: gate.options, label: label(gate), kind: "gate", area }}
    >
      <form className="answer" onSubmit={(event) => event.preventDefault()}>
        <AnswerBox
          label={COMMENT}
          placeholder={narrow ? "Comment (optional)" : COMMENT}
          text={comment}
          change={setComment}
          off={stopped}
          locked={busy}
          files={files}
          setFiles={setFiles}
          limits={limits}
          lines={card.fieldLines}
        />
      </form>
      <div className="waiting-send">
        {buttons}
        {stopped && <p className="chat-note">{STOPPED_NOTE}</p>}
        {problem && (
          <p className="field-problem" role="alert">
            {problem}
          </p>
        )}
        <ActionProblem attempt={attempt} off={stopped} />
      </div>
    </CardBody>
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

// The artifacts the gate reads but its note does not carry, as chips beside the note's: each
// as of its latest record among the feed's artifacts, so a write while the gate is open shows
// at once, by its title, else its short name. A chip opens that record; before the session's
// artifacts are loaded, a name alone.
function Reads({ session, names }: { session: string; names: string[] }) {
  const artifacts = useLive().artifacts[session];
  const view = useView(session);
  const items = artifacts && "items" in artifacts ? artifacts.items : undefined;
  return names.map((name) => {
    const found = items?.find((one) => one.full_name === name);
    const short = name.slice(name.lastIndexOf("/") + 1);
    if (!found) {
      return (
        <span key={name} className="gate-read muted">
          {short}
          {items && ": no record yet"}
        </span>
      );
    }
    return (
      <button
        key={name}
        type="button"
        className="chip"
        aria-label={`Open artifact ${found.full_name}`}
        onClick={() => view(found.latest.id)}
      >
        <KindIcon mediaType={found.latest.media_type} />
        <span className="chip-name">{found.title || found.name}</span>
      </button>
    );
  });
}

// A closed gate (docs/design/ui.md, Flow gates): a folded card, its head one button that
// opens it down in the same frame. The head: a chevron, the gate's flag, "Gate #<id>", run
// and state, the answer's chip, who answered and the time, last; no comment, whoever closed it:
// the comment stands under the move it made, and an override's or a cancel's reason on its
// event's line. Opened: the question, the answer on the human's ground (an agent's quieter)
// with its files' chips (their previews stand under the move), and the note and the
// recommendation folded into a line each. `move`: the run's move that
// closed it (moveOf), which gives the chip its direction by the run's flow `states` and the
// answer its target; without one, the answer's word, neutral.
export function GateLine({
  session,
  gate,
  move,
  states,
}: {
  session: string;
  gate: GateInfo;
  move?: RunEventInfo;
  states: RunInfo["states"] | null;
}) {
  const [shown, setShown] = useState(false);
  const when = gate.answered_at ?? gate.created_at;
  const by = gate.answered_by ?? "";
  const chip =
    move?.transition && gate.answer ? (
      <OutcomeChip states={states} from={move.transition.from_state} to={move.transition.to_state} outcome={gate.answer} base="run-outcome" />
    ) : (
      <span className="run-outcome">{gate.answer}</span>
    );
  const time = <time dateTime={when}>{clock(when)}</time>;
  return (
    <article
      className={`chat-gate closed${shown ? " expanded" : ""}`}
      id={gateAnchor(gate.id)}
      aria-label={`Gate #${gate.id}`}
      {...quoteArea(session)}
    >
      <button
        type="button"
        className="gate-head"
        aria-label={`${gateTitle(gate)}: ${gate.answer} by ${by}`}
        aria-expanded={shown}
        onClick={() => setShown(!shown)}
      >
        <span className="gate-chevron" aria-hidden="true">
          <ChevronIcon />
        </span>
        <span className="avatar mini avatar-gate" aria-hidden="true">
          <GateIcon />
        </span>
        <span className="gate-head-title">Gate #{gate.id}</span>
        <span className="gate-head-where">
          {gate.run} · {gate.state}
        </span>
        {chip}
        <span className="gate-head-by">by {by === HUMAN ? "you" : by}</span>
        {time}
      </button>
      {shown && (
        <div className="gate-closed-card">
          <p className="gate-question">{gate.question}</p>
          <div className={`question-answer${by === HUMAN ? "" : " dismissed"}`}>
            <div className="answer-top">
              <MiniAvatar who={by} />
              <b className="answer-who">{by === HUMAN ? "You" : by}</b>
              {chip}
              {move?.transition && <span className="answer-target">→ {move.transition.to_state}</span>}
              {time}
            </div>
            {gate.comment && <Body text={gate.comment} breaks />}
            <Attachments session={session} attachments={gate.answer_attachments} />
          </div>
          <NoteLine session={session} gate={gate} />
          <SupervisorLine gate={gate} />
        </div>
      )}
    </article>
  );
}

// A folded line of an opened closed gate: its label in a fixed column, its head cut on one
// line; the rest on a click.
function FoldedLine({ name, head, children }: { name: string; head: ReactNode; children: ReactNode }) {
  return (
    <details className="gate-row">
      <summary>
        <span className="gate-row-label">{name}</span>
        <span className="gate-row-head">{head}</span>
      </summary>
      <div className="gate-row-body">{children}</div>
    </details>
  );
}

// The note that led to a closed gate: its summary and how many artifacts it carries; opened,
// its body's first CLOSED_NOTE_LINES lines with Show more, and its artifacts.
function NoteLine({ session, gate }: { session: string; gate: GateInfo }) {
  const count = gate.attachments.length;
  if (!gate.note && !gate.note_body && count === 0) return null;
  const artifacts = count > 0 && `${count} artifact${count === 1 ? "" : "s"}`;
  return (
    <FoldedLine
      name="Note"
      head={
        <>
          {gate.note && <b>{gate.note}</b>}
          {gate.note && artifacts && " · "}
          {artifacts}
        </>
      }
    >
      <div className="gate-note">
        {gate.note_body && <Preview text={gate.note_body} lines={CLOSED_NOTE_LINES} />}
        <Attachments session={session} attachments={gate.attachments} short />
      </div>
    </FoldedLine>
  );
}

// The supervisor's recommendation on a closed gate: the option it recommended (named as the
// card's buttons) and whether the human's answer agreed; the lead's disagreement with the
// agent in orange; opened, its text. Only a recommendation that was given.
function SupervisorLine({ gate }: { gate: GateInfo }) {
  const rec = gate.recommendation;
  if (rec?.state !== "given") return null;
  const agreed =
    rec.choice && gate.answered_by === HUMAN ? (gate.answer === rec.choice ? " · you agreed" : " · you answered otherwise") : "";
  return (
    <FoldedLine
      name="Supervisor"
      head={
        <>
          {rec.choice ? (
            <>
              recommended <b>{label(gate)(rec.choice)}</b>
            </>
          ) : (
            "Supervisor's recommendation"
          )}
          {agreed}
          {rec.disagrees && <span className="rec-closed-differs"> · {disagreed(rec, "disagreed")}</span>}
        </>
      }
    >
      <Body text={rec.text} />
    </FoldedLine>
  );
}
