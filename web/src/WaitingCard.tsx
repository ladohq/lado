// The waiting card (docs/design/ui.md, The waiting card): what waits for the human in a
// session, in one card above the chat's composer and on Needs you. A tab per agent with open
// questions (all of them) and a tab per open gate, in the order their first item was asked.
// An agent's tab picks an answer per question (a choice, Other… for own words, or Skip; the
// supervisor's recommended choice is picked ahead until the human picks) and sends them all
// in one request, so the agent gets them in one hand-over; a gate's tab is
// the gate's panel, whose buttons answer at once. Nothing shows ahead of the server: a tab
// goes when the live lists bring its items closed. The card is at most half the chat's
// height; expanded, it stays where it is and fills its page's area (the chat's, Needs you's
// content; its host hides the rest, styles.css) until Esc, its fold button, or nothing
// waits. It is no modal: an artifact panel a chip opens shows over it, and Esc closes that
// panel first (the card's Esc waits while the address has ?view=).
// In a session's chat (`chat`; not on Needs you) the human can minimize it to its tabs and
// one line, until they restore it or a new tab comes, and give it a height by the edge
// above it (prefs.ts keeps both).
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type DragEvent } from "react";
import { useSearchParams } from "react-router";

import { answerQuestions, ApiError, type GateInfo, type Limits, type MessageInfo, type Reply, type RunInfo } from "./api";
import { AnswerBox, release, uploadFiles, useLimits, type Attached, type SetFiles } from "./attachFiles";
import { Attachments } from "./Attachments";
import { Body } from "./ChatText";
import { avatar } from "./FeedRow";
import { GatePanel } from "./GateCard";
import { Recommendation } from "./Recommendation";
import { ExpandIcon, FlowsIcon, MinimizeIcon, RestoreIcon } from "./icons";
import { VIEW_PARAM } from "./paths";
import { storedMinimized, storedWaitingHeight, storeMinimized, storeWaitingHeight, WAITING_MIN } from "./prefs";
import { quoteArea } from "./quote";
import { onQuote } from "./quotes";
import { fitWidth, Splitter, useHeight } from "./Splitter";
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
const FEED_MIN = 160; // the chat feed's least height (styles.css, .chat-feed)
const NARROW = "(max-width: 900px)"; // the window that scrolls (styles.css)

// An own answer counts with its words or its files, as a message of files only does.
const answered = (pick: Pick | undefined, files: Attached[]) =>
  pick !== undefined && ("choice" in pick || "skip" in pick || pick.own.trim() !== "" || files.length > 0);

// The reply to a question, with the full names of its field's files: a choice has no field.
function toReply(question: number, pick: Pick, artifacts: string[]): Reply {
  if ("choice" in pick) return { question, choice: pick.choice, skip: false };
  const files = artifacts.length ? { artifacts } : {};
  if ("own" in pick) return { question, text: pick.own, skip: false, ...files };
  return pick.skip.trim() ? { question, skip: true, text: pick.skip, ...files } : { question, skip: true, ...files };
}

// Whose files a field's are in the card's state: a question's (its Other… and Skip share
// them) or a gate's.
const questionFiles = (id: number) => `question:${id}`;
const gateFiles = (id: number) => `gate:${id}`;
const fieldOf = (pick: Pick | undefined) => pick !== undefined && !("choice" in pick);

const stopFiles = (event: DragEvent) => {
  if (Array.from(event.dataTransfer?.types ?? []).includes("Files")) event.preventDefault();
};

const pickText = (pick: Pick | undefined) => (pick === undefined || "choice" in pick ? "" : "own" in pick ? pick.own : pick.skip);

export function WaitingCard({
  session,
  questions,
  gates,
  runs,
  stopped,
  focus,
  chat,
}: {
  session: string;
  questions: MessageInfo[]; // the session's open questions
  gates: GateInfo[]; // its open gates
  runs: RunInfo[] | null; // for the runs' colours; null while they load
  stopped: boolean;
  focus: Focus;
  // In a session's chat: the feed's height (null: not laid out), and whether its open
  // questions and gates are both loaded.
  chat?: { feed: number | null; loaded: boolean };
}) {
  const tabs = waitingTabs(questions, gates);
  // Minimized: the tab keys the card had when the human minimized it, per session (the chat
  // keeps its card from one session to the next).
  const [minimizedOf, setMinimizedOf] = useState(() => ({ session, keys: chat ? storedMinimized(session) : null }));
  if (minimizedOf.session !== session) setMinimizedOf({ session, keys: chat ? storedMinimized(session) : null });
  const keys = minimizedOf.session === session ? minimizedOf.keys : null;
  const minimized = keys !== null && tabs.length > 0 && tabs.every((tab) => keys.includes(tab.key));
  const [height, setHeight] = useState(() => (chat ? storedWaitingHeight() : null)); // null: the stylesheet's
  const [measured, cardHeight] = useHeight<HTMLElement>();
  const [chosen, setChosen] = useState<string | null>(null);
  const [picks, setPicks] = useState<Picks>({});
  const [comments, setComments] = useState<Record<number, string>>({}); // a gate's, by its id
  // The files of each field, by questionFiles / gateFiles, kept as the comments are.
  const [files, setFiles] = useState<Record<string, Attached[]>>({});
  const keptFiles = useRef(files);
  keptFiles.current = files;
  const limits = useLimits(); // with the card, before any field shows
  const [sending, setSending] = useState(false);
  const [problem, setProblem] = useState<{ key: string; text: string } | null>(null);
  const [expanded, setExpanded] = useState(false);
  const viewing = useSearchParams()[0].has(VIEW_PARAM); // an artifact panel is open over the page
  const [marked, setMarked] = useState<number | null>(null);
  const card = useRef<HTMLElement>(null);
  const tabList = useRef<HTMLDivElement>(null);
  const expander = useRef<HTMLButtonElement>(null);
  const folded = useRef(false); // focus goes back to the expand button after a fold
  const minimizer = useRef<HTMLButtonElement>(null);
  const toggled = useRef(false); // focus goes to the minimize button after the human's toggle
  const dragBelow = useRef(false); // the edge is dragged below the card's least height
  const cardRef = useCallback(
    (element: HTMLElement | null) => {
      card.current = element;
      measured(element);
    },
    [measured],
  );
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
  // Files of questions and gates no longer open go, and so do all of them with the card.
  useEffect(() => {
    const still = new Set([...[...open].map(questionFiles), ...gates.map((one) => gateFiles(one.id))]);
    const gone = Object.keys(keptFiles.current).filter((key) => !still.has(key));
    if (gone.length === 0) return;
    gone.forEach((key) => release(keptFiles.current[key]));
    setFiles((now) => Object.fromEntries(Object.entries(now).filter(([key]) => still.has(key))));
  }, [openKey, gatesKey]);
  useEffect(() => () => Object.values(keptFiles.current).forEach(release), []);
  const filesOf = (key: string) => files[key] ?? [];
  const setFilesOf =
    (key: string): SetFiles =>
    (update) =>
      setFiles((now) => ({ ...now, [key]: update(now[key] ?? []) }));
  // A quote of the session folds it, so the composer it goes to shows (the focus goes there).
  useEffect(() => onQuote(session, () => setExpanded(false)), [session]);
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
  // Expanded: Esc folds it, unless an artifact panel is open, whose own Esc closes it first.
  // Opened, the focus goes to the shown tab; folded, to the expand button.
  useEffect(() => {
    if (!expanded) return;
    card.current?.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]')?.focus();
    // A narrow window scrolls (styles.css): the card goes under the top bar. A wide one
    // scrolls nothing, nor a frame that hides its overflow.
    if (window.matchMedia?.(NARROW).matches) card.current?.scrollIntoView?.({ block: "start" });
  }, [expanded]);
  useEffect(() => {
    if (!expanded || viewing) return;
    const escape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      folded.current = true;
      setExpanded(false);
    };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [expanded, viewing]);
  useLayoutEffect(() => {
    if (!expanded && folded.current) {
      folded.current = false;
      expander.current?.focus();
    }
  }, [expanded]);
  // A new tab restores a minimized card, which forgets it was minimized. Once what waits is
  // loaded, the kept keys narrow to the tabs there are (none left: forgotten), so an agent
  // whose tab went away has a new tab when it asks again.
  const tabKeys = tabs.map((tab) => tab.key).join(" ");
  const loaded = chat?.loaded ?? false;
  useEffect(() => {
    if (keys === null) return;
    if (tabs.length > 0 && !minimized) remember(null);
    else if (loaded && tabs.length === 0) remember(null);
    else if (loaded && keys.length > tabs.length) remember(keys.filter((key) => tabs.some((tab) => tab.key === key)));
  }, [keys, tabKeys, loaded]);
  // Minimized by the human, the focus goes to Restore; restored by its icon or line, to
  // Minimize (a tab clicked keeps it).
  useLayoutEffect(() => {
    if (!toggled.current) return;
    toggled.current = false;
    minimizer.current?.focus();
  }, [minimized]);

  if (!shown) return null;

  const fold = () => {
    folded.current = true;
    setExpanded(false);
  };

  function remember(minimizedKeys: string[] | null) {
    setMinimizedOf({ session, keys: minimizedKeys });
    storeMinimized(session, minimizedKeys);
  }
  const minimize = () => {
    toggled.current = true;
    remember(tabs.map((tab) => tab.key));
  };
  const restore = (focusMinimize = true) => {
    toggled.current = focusMinimize;
    remember(null);
  };
  const folds = minimized && !expanded; // expanded, a minimized card shows whole
  // The edge's bounds: the card and the feed share their room, and the feed keeps its least
  // height; the card's height is the one the human gave, narrowed to that room (kept for a
  // taller chat), or the stylesheet's.
  const room = chat?.feed != null && cardHeight !== null ? chat.feed + cardHeight - FEED_MIN : null;
  // Below its least height the card minimizes: the edge goes down to 0.
  const max = Math.max(WAITING_MIN, Math.floor(room ?? height ?? 0));
  const given =
    chat && !folds && !expanded && height !== null
      ? fitWidth(height, { initial: height, min: WAITING_MIN, max }, room)
      : null;
  // Below its least height: a key minimizes at once; a drag shows the least height and
  // minimizes when the edge is let go (`dragEnded`), so the release, which the edge still
  // holds, lands on no line or tab of the minimized card. The height stays for the restore.
  const resize = (next: number, dragging: boolean) => {
    dragBelow.current = dragging && next < WAITING_MIN;
    if (next < WAITING_MIN && !dragging) {
      minimize();
      return;
    }
    setHeight(Math.max(WAITING_MIN, next));
    storeWaitingHeight(Math.max(WAITING_MIN, next));
  };
  const dragEnded = () => {
    if (!dragBelow.current) return;
    dragBelow.current = false;
    minimize();
  };

  function pick(id: number, next: Pick | undefined) {
    setPicks((now) => {
      return { ...now, [id]: next ?? null };
    });
  }

  // Send uploads the files of the tab's fields not uploaded yet, then answers with their
  // names in one request; a failed upload stops it, its chip red.
  async function send(tab: AgentTab) {
    setSending(true);
    setProblem(null);
    try {
      const keys = tab.questions.filter((one) => fieldOf(pickOf(picks, one))).map((one) => questionFiles(one.id));
      const all = keys.flatMap(filesOf);
      // Each update maps the files by their key: applied to each field's own list.
      const setAll: SetFiles = (update) =>
        setFiles((now) => ({ ...now, ...Object.fromEntries(keys.map((key) => [key, update(now[key] ?? [])])) }));
      const uploaded = await uploadFiles(session, all, setAll, "Send again");
      if ("problem" in uploaded) {
        setProblem({ key: tab.key, text: uploaded.problem });
        return;
      }
      const names = new Map(all.map((one, n) => [one.key, uploaded.names[n]]));
      await answerQuestions(
        session,
        tab.questions.map((one) => {
          const pick = pickOf(picks, one)!;
          const given = fieldOf(pick) ? filesOf(questionFiles(one.id)).map((f) => names.get(f.key)!) : [];
          return toReply(one.id, pick, given);
        }),
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

  return (
    <section
      ref={cardRef}
      className={`waiting-card${expanded ? " expanded" : ""}${folds ? " minimized" : ""}${given !== null ? " sized" : ""}`}
      aria-label={`What waits for you in ${session}`}
      style={given !== null ? ({ "--waiting-height": `${given}px` } as CSSProperties) : undefined}
      // Files go to a field under them (its own drop zone); dropped elsewhere on the card,
      // nowhere: neither the composer (it leaves the card alone) nor the browser opens them.
      onDragOver={stopFiles}
      onDrop={stopFiles}
    >
      {chat && !folds && !expanded && (
        <Splitter
          label="Resize the card"
          edge="top"
          width={Math.round(given ?? cardHeight ?? 0)}
          bounds={{ initial: WAITING_MIN, min: 0, max }}
          onChange={resize}
          onEnd={dragEnded}
          onReset={() => {
            setHeight(null);
            storeWaitingHeight(null);
          }}
          grip
        />
      )}
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
            const on = !folds && tab.key === shown.key; // minimized, no tab is shown
            const name = "gate" in tab ? tab.gate.run : tab.agent;
            return (
              <button
                key={tab.key}
                type="button"
                role="tab"
                id={`waiting-${session}-${tab.key}`}
                aria-selected={on}
                aria-controls={folds ? undefined : panelId}
                tabIndex={tab.key === shown.key ? 0 : -1}
                className={`waiting-tab${on ? " on" : ""}`}
                data-kind={"gate" in tab ? "gate" : "agent"}
                style={{ "--who": colour(tab), "--chars": name.length } as CSSProperties}
                onClick={() => {
                  setChosen(tab.key);
                  if (folds) restore(false);
                }}
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
        <div className="waiting-actions">
          {chat && !expanded && (
            <Tooltip tip={folds ? "Restore the card" : "Minimize the card"}>
              <button
                ref={minimizer}
                type="button"
                className="waiting-expand"
                aria-label={folds ? "Restore the card" : "Minimize the card"}
                aria-expanded={!folds}
                onClick={() => (folds ? restore() : minimize())}
              >
                {folds ? <RestoreIcon /> : <MinimizeIcon />}
              </button>
            </Tooltip>
          )}
          <Tooltip tip={expanded ? "Collapse the card (Esc)" : "Expand the card"}>
            <button
              ref={expander}
              type="button"
              className="waiting-expand"
              aria-label={expanded ? "Collapse the card" : "Expand the card"}
              aria-expanded={expanded}
              onClick={() => (expanded ? fold() : setExpanded(true))}
            >
              <ExpandIcon expanded={expanded} />
            </button>
          </Tooltip>
        </div>
      </div>
      {folds ? (
        <button
          type="button"
          className="waiting-line"
          style={{ "--who": colour(shown) } as CSSProperties}
          onClick={() => restore()}
        >
          {"gate" in shown ? shown.gate.question : shown.questions[0].summary}
        </button>
      ) : (
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
              files={filesOf(gateFiles(shown.gate.id))}
              onFiles={setFilesOf(gateFiles(shown.gate.id))}
              limits={limits}
            />
          ) : (
            <AgentPanel
              session={session}
              tab={shown}
              picks={picks}
              pick={pick}
              filesOf={(id) => filesOf(questionFiles(id))}
              setFilesOf={(id) => setFilesOf(questionFiles(id))}
              limits={limits}
              marked={marked}
              off={sending || stopped}
              problem={problem?.key === shown.key ? problem.text : null}
              send={() => void send(shown)}
            />
          )}
        </div>
      )}
    </section>
  );
}

// An agent's tab: its questions, numbered when more than one, each with the supervisor's
// recommendation (Recommendation.tsx), its choices, Other… (a question with a free answer)
// and Skip, whose field (an own answer, a skip's comment) takes files (attachFiles.AnswerBox);
// then Send, on once each has an answer.
function AgentPanel({
  session,
  tab,
  picks,
  pick,
  filesOf,
  setFilesOf,
  limits,
  marked,
  off,
  problem,
  send,
}: {
  session: string;
  tab: AgentTab;
  picks: Picks;
  pick: (id: number, next: Pick | undefined) => void;
  filesOf: (id: number) => Attached[];
  setFilesOf: (id: number) => SetFiles;
  limits: Limits | null;
  marked: number | null;
  off: boolean;
  problem: string | null;
  send: () => void;
}) {
  const many = tab.questions.length > 1;
  const done = tab.questions.filter((one) => answered(pickOf(picks, one), filesOf(one.id))).length;
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
              {...quoteArea(session)}
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
                <AnswerBox
                  key={"own" in now ? "own" : "skip"}
                  label={"own" in now ? "Your own answer" : "Why you skip it (optional)"}
                  text={text}
                  off={off}
                  autoFocus
                  change={(value) => pick(question.id, "own" in now ? { own: value } : { skip: value })}
                  files={filesOf(question.id)}
                  setFiles={setFilesOf(question.id)}
                  limits={limits}
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
