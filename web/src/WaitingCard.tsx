// The waiting card (docs/design/ui.md, The waiting card): what waits for the human in a
// session, in one card above the chat's composer and on Needs you. A tab per agent with open
// questions (all of them) and a tab per open gate, in the order their first item was asked.
// An agent's tab picks an answer per question (a choice, Other… for own words, or Skip; the
// supervisor's recommended choice is picked ahead until the human picks) and sends them all
// in one request, so the agent gets them in one hand-over; a gate's tab is
// the gate's panel, whose buttons answer at once. Nothing shows ahead of the server: a tab
// goes when the live lists bring its items closed. The card is at most half the chat's
// height; expanded, it covers the window until Esc, its fold button, or nothing waits.
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";

import { answerQuestions, ApiError, type GateInfo, type MessageInfo, type Reply, type RunInfo } from "./api";
import { Attachments } from "./Attachments";
import { Body } from "./ChatText";
import { avatar } from "./FeedRow";
import { GatePanel } from "./GateCard";
import { Recommendation } from "./Recommendation";
import { ExpandIcon, FlowsIcon } from "./icons";
import { runColours } from "./Team";
import { Tooltip } from "./Tooltip";

type AgentTab = { key: string; agent: string; questions: MessageInfo[]; since: string };
export type WaitingTab = AgentTab | { key: string; gate: GateInfo; since: string };

export const agentTab = (name: string) => `agent:${name}`;
export const gateTab = (id: number) => `gate:${id}`;

// The tabs of a session's open questions and gates: one per agent that asked, its questions
// by id, and one per gate; by when their first item was asked, then by that item's id.
export function waitingTabs(questions: MessageInfo[], gates: GateInfo[]): WaitingTab[] {
  const byAgent = new Map<string, MessageInfo[]>();
  for (const question of [...questions].sort((a, b) => a.id - b.id)) {
    byAgent.set(question.from, [...(byAgent.get(question.from) ?? []), question]);
  }
  const first = (tab: WaitingTab) => ("gate" in tab ? tab.gate.id : tab.questions[0].id);
  const tabs: WaitingTab[] = [
    ...[...byAgent].map(([agent, asked]) => ({
      key: agentTab(agent),
      agent,
      questions: asked,
      since: asked.reduce((at, one) => (Date.parse(one.created_at) < Date.parse(at) ? one.created_at : at), asked[0].created_at),
    })),
    ...gates.map((gate) => ({ key: gateTab(gate.id), gate, since: gate.created_at })),
  ];
  return tabs.sort((a, b) => Date.parse(a.since) - Date.parse(b.since) || first(a) - first(b));
}

// A link or a line's arrow asks for an item: its tab shown, the item marked. `at` tells two
// asks for the same item apart.
export type Focus = { key: string; item: number; at: number } | null;

// The human's pick for a question: a choice, own words (Other…), or Skip with a comment;
// null, none (the human unpicked it).
type Pick = { choice: string } | { own: string } | { skip: string };
type Picks = Record<number, Pick | null>;

// A question's pick: the human's, else the supervisor's recommended choice when it is one of
// the question's choices.
function pickOf(picks: Picks, question: MessageInfo): Pick | undefined {
  if (question.id in picks) return picks[question.id] ?? undefined;
  const rec = question.recommendation;
  const choice = rec?.state === "given" ? rec.choice : null;
  return choice && question.choices?.includes(choice) ? { choice } : undefined;
}

const MARKED_FOR = 1500; // ms an item asked for stays marked

const answered = (pick: Pick | undefined) =>
  pick !== undefined && ("choice" in pick || "skip" in pick || pick.own.trim() !== "");

function toReply(question: number, pick: Pick): Reply {
  if ("choice" in pick) return { question, choice: pick.choice, skip: false };
  if ("own" in pick) return { question, text: pick.own, skip: false };
  return pick.skip.trim() ? { question, skip: true, text: pick.skip } : { question, skip: true };
}

const pickText = (pick: Pick | undefined) => (pick === undefined || "choice" in pick ? "" : "own" in pick ? pick.own : pick.skip);

export function WaitingCard({
  session,
  questions,
  gates,
  runs,
  stopped,
  focus,
}: {
  session: string;
  questions: MessageInfo[]; // the session's open questions
  gates: GateInfo[]; // its open gates
  runs: RunInfo[] | null; // for the runs' colours; null while they load
  stopped: boolean;
  focus: Focus;
}) {
  const tabs = waitingTabs(questions, gates);
  const [chosen, setChosen] = useState<string | null>(null);
  const [picks, setPicks] = useState<Picks>({});
  const [comments, setComments] = useState<Record<number, string>>({}); // a gate's, by its id
  const [sending, setSending] = useState(false);
  const [problem, setProblem] = useState<{ key: string; text: string } | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [marked, setMarked] = useState<number | null>(null);
  const card = useRef<HTMLElement>(null);
  const tabList = useRef<HTMLDivElement>(null);
  const expander = useRef<HTMLButtonElement>(null);
  const folded = useRef(false); // focus goes back to the expand button after a fold
  const shown = tabs.find((tab) => tab.key === chosen) ?? tabs[0];
  const open = new Set(questions.map((one) => one.id));
  const colours = runs ? runColours(runs) : new Map<string, number>();

  // The tab the human chose (a click, a link) stays shown while it exists; when it goes, and
  // until they choose one, the first one shows.
  useEffect(() => {
    if (chosen !== null && !tabs.some((tab) => tab.key === chosen)) setChosen(null);
  });
  // Picks of questions no longer open go.
  const openKey = [...open].sort((a, b) => a - b).join(",");
  useEffect(() => {
    setPicks((now) => {
      const kept = Object.entries(now).filter(([id]) => open.has(Number(id)));
      return kept.length === Object.keys(now).length ? now : Object.fromEntries(kept);
    });
  }, [openKey]);
  // Comments of gates no longer open go.
  const gatesKey = gates.map((one) => one.id).sort((a, b) => a - b).join(",");
  useEffect(() => {
    const ids = new Set(gates.map((one) => one.id));
    setComments((now) => {
      const kept = Object.entries(now).filter(([id]) => ids.has(Number(id)));
      return kept.length === Object.keys(now).length ? now : Object.fromEntries(kept);
    });
  }, [gatesKey]);
  // Nothing waits: no card, so not expanded either.
  useEffect(() => {
    if (tabs.length === 0 && expanded) setExpanded(false);
  }, [tabs.length, expanded]);
  // An item asked for: its tab, marked for a moment and scrolled into view in the list.
  useEffect(() => {
    if (focus === null) return;
    setChosen(focus.key);
    setMarked(focus.item);
    const timer = setTimeout(() => setMarked(null), MARKED_FOR);
    return () => clearTimeout(timer);
  }, [focus?.at]);
  useLayoutEffect(() => {
    if (marked === null) return;
    card.current?.querySelector(`[data-item="${marked}"]`)?.scrollIntoView?.({ block: "nearest" });
  }, [marked, shown?.key]);
  // The shown tab scrolls into the tabs' view (the row scrolls sideways when they do not
  // fit): the row only, never scrollIntoView, which would scroll the feed or the page too.
  useLayoutEffect(() => {
    const row = tabList.current;
    const on = row?.querySelector<HTMLElement>('[aria-selected="true"]');
    if (!row || !on) return;
    if (on.offsetLeft < row.scrollLeft) row.scrollLeft = on.offsetLeft;
    else if (on.offsetLeft + on.offsetWidth > row.scrollLeft + row.clientWidth)
      row.scrollLeft = on.offsetLeft + on.offsetWidth - row.clientWidth;
  }, [shown?.key, expanded]);
  // Expanded: Esc folds it. Opened, the focus goes to the shown tab; folded, to the expand button.
  useEffect(() => {
    if (!expanded) return;
    const escape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      folded.current = true;
      setExpanded(false);
    };
    document.addEventListener("keydown", escape);
    card.current?.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]')?.focus();
    return () => document.removeEventListener("keydown", escape);
  }, [expanded]);
  useLayoutEffect(() => {
    if (!expanded && folded.current) {
      folded.current = false;
      expander.current?.focus();
    }
  }, [expanded]);

  if (!shown) return null;

  const fold = () => {
    folded.current = true;
    setExpanded(false);
  };

  function pick(id: number, next: Pick | undefined) {
    setPicks((now) => {
      return { ...now, [id]: next ?? null };
    });
  }

  async function send(tab: AgentTab) {
    setSending(true);
    setProblem(null);
    try {
      await answerQuestions(
        session,
        tab.questions.map((one) => toReply(one.id, pickOf(picks, one)!)),
      );
    } catch (error) {
      setProblem({ key: tab.key, text: error instanceof ApiError ? error.message : String(error) });
    } finally {
      setSending(false);
    }
  }

  const colour = (tab: WaitingTab) =>
    "gate" in tab
      ? colours.has(tab.gate.run)
        ? `var(--run-${colours.get(tab.gate.run)})`
        : "var(--line)"
      : `var(--avatar-${avatar(tab.agent).colour})`;
  const panelId = `waiting-${session}-panel`;

  const body = (
    <section
      ref={card}
      className={`waiting-card${expanded ? " expanded" : ""}`}
      aria-label={`What waits for you in ${session}`}
      role={expanded ? "dialog" : undefined}
      aria-modal={expanded ? true : undefined}
    >
      <div className="waiting-head">
        <div
          ref={tabList}
          className="waiting-tabs"
          role="tablist"
          aria-label="What waits for you"
          onWheel={(event) => {
            // The wheel scrolls the tabs sideways.
            if (event.deltaX === 0) event.currentTarget.scrollLeft += event.deltaY;
          }}
        >
          {tabs.map((tab) => {
            const on = tab.key === shown.key;
            const name = "gate" in tab ? tab.gate.run : tab.agent;
            return (
              <button
                key={tab.key}
                type="button"
                role="tab"
                id={`waiting-${session}-${tab.key}`}
                aria-selected={on}
                aria-controls={panelId}
                tabIndex={on ? 0 : -1}
                className={`waiting-tab${on ? " on" : ""}`}
                data-kind={"gate" in tab ? "gate" : "agent"}
                style={{ "--who": colour(tab), "--chars": name.length } as CSSProperties}
                onClick={() => setChosen(tab.key)}
              >
                {"gate" in tab ? (
                  <span className="waiting-tab-flow" aria-hidden="true">
                    <FlowsIcon />
                  </span>
                ) : (
                  <span className="waiting-tab-avatar" aria-hidden="true">
                    {avatar(tab.agent).letter}
                  </span>
                )}
                <span className="waiting-tab-name">{name}</span>{" "}
                <span className="waiting-tab-count">{"gate" in tab ? 1 : tab.questions.length}</span>
              </button>
            );
          })}
        </div>
        <Tooltip tip={expanded ? "Collapse the card (Esc)" : "Expand the card"}>
          <button
            ref={expanded ? undefined : expander}
            type="button"
            className="waiting-expand"
            aria-label={expanded ? "Collapse the card" : "Expand the card"}
            onClick={() => (expanded ? fold() : setExpanded(true))}
          >
            <ExpandIcon expanded={expanded} />
          </button>
        </Tooltip>
      </div>
      <div
        className="waiting-panel"
        role="tabpanel"
        id={panelId}
        aria-labelledby={`waiting-${session}-${shown.key}`}
        style={{ "--who": colour(shown) } as CSSProperties}
      >
        {"gate" in shown ? (
          <GatePanel
            key={shown.key}
            session={session}
            gate={shown.gate}
            stopped={stopped}
            inTab
            marked={marked === shown.gate.id}
            comment={comments[shown.gate.id] ?? ""}
            onComment={(text) => setComments((now) => ({ ...now, [shown.gate.id]: text }))}
          />
        ) : (
          <AgentPanel
            session={session}
            tab={shown}
            picks={picks}
            pick={pick}
            marked={marked}
            off={sending || stopped}
            problem={problem?.key === shown.key ? problem.text : null}
            send={() => void send(shown)}
          />
        )}
      </div>
    </section>
  );
  if (!expanded) return body;
  return createPortal(<div className="waiting-overlay">{body}</div>, document.body);
}

// An agent's tab: its questions, numbered when more than one, each with the supervisor's
// recommendation (Recommendation.tsx), its choices, Other… (a question with a free answer)
// and Skip; then Send, on once each has an answer.
function AgentPanel({
  session,
  tab,
  picks,
  pick,
  marked,
  off,
  problem,
  send,
}: {
  session: string;
  tab: AgentTab;
  picks: Picks;
  pick: (id: number, next: Pick | undefined) => void;
  marked: number | null;
  off: boolean;
  problem: string | null;
  send: () => void;
}) {
  const many = tab.questions.length > 1;
  const done = tab.questions.filter((one) => answered(pickOf(picks, one))).length;
  const all = done === tab.questions.length;
  return (
    <>
      <ol className="waiting-list" aria-label={`Questions from ${tab.agent}`}>
        {tab.questions.map((question, n) => {
          const now = pickOf(picks, question);
          const text = pickText(now);
          return (
            <li
              key={question.id}
              className={`waiting-question${marked === question.id ? " marked" : ""}`}
              data-item={question.id}
              aria-label={`Question #${question.id}`}
            >
              <h4 className="waiting-question-text">
                {many && <span className="waiting-question-n">{n + 1}.</span>}
                {question.summary}
              </h4>
              {question.body && <Body text={question.body} />}
              <Attachments session={session} attachments={question.attachments} />
              <Recommendation rec={question.recommendation} />
              <div className="waiting-options" role="group" aria-label={`Answer to question #${question.id}`}>
                {(question.choices ?? []).map((choice) => {
                  const on = now !== undefined && "choice" in now && now.choice === choice;
                  return (
                    <button
                      key={choice}
                      type="button"
                      className={`waiting-option${on ? " on" : ""}`}
                      aria-pressed={on}
                      disabled={off}
                      onClick={() => pick(question.id, on ? undefined : { choice })}
                    >
                      {choice}
                    </button>
                  );
                })}
                {question.free_answer && (
                  <button
                    type="button"
                    className={`waiting-option other${now && "own" in now ? " on" : ""}`}
                    aria-pressed={now !== undefined && "own" in now}
                    disabled={off}
                    onClick={() => pick(question.id, now && "own" in now ? undefined : { own: text })}
                  >
                    Other…
                  </button>
                )}
                <button
                  type="button"
                  className={`waiting-option other${now && "skip" in now ? " on" : ""}`}
                  aria-pressed={now !== undefined && "skip" in now}
                  disabled={off}
                  onClick={() => pick(question.id, now && "skip" in now ? undefined : { skip: text })}
                >
                  Skip
                </button>
              </div>
              {now !== undefined && !("choice" in now) && (
                <textarea
                  key={"own" in now ? "own" : "skip"}
                  className="waiting-field"
                  rows={1}
                  autoFocus
                  aria-label={"own" in now ? "Your own answer" : "Why you skip it (optional)"}
                  placeholder={"own" in now ? "Your own answer" : "Why you skip it (optional)"}
                  value={text}
                  disabled={off}
                  onChange={(event) =>
                    pick(question.id, "own" in now ? { own: event.target.value } : { skip: event.target.value })
                  }
                />
              )}
            </li>
          );
        })}
      </ol>
      <div className="waiting-send">
        <button type="button" className="primary" disabled={!all || off} onClick={send}>
          {many ? `Send ${tab.questions.length} answers to ${tab.agent}` : `Send answer to ${tab.agent}`}
        </button>
        {many && !all && (
          <span className="waiting-count">
            {done} of {tab.questions.length} answered
          </span>
        )}
        {problem && (
          <p className="field-problem" role="alert">
            {problem}
          </p>
        )}
      </div>
    </>
  );
}
