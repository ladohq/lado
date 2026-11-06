// The team of a session: a mark per agent, with its status (a dot whose colour and shape
// differ) and name; every mark alike, compact, the role only in the tooltip and the accessible
// name (decided 2026-10-10, fix/team-chip). The supervisor and its own workers come first; the
// agents of each flow run follow in a dashed frame, all in the same row (decided 2026-10-07,
// feature/activity-team; no state of the run: Flows and Agents show it). The frame shows no name
// (decided 2026-10-11, feature/team-run-frames): its dashes are in the run's colour (runColours),
// and the Flows icon in that colour is the link to the run's page, its tooltip naming the run;
// before the runs load, the dashes are grey. A mark opens the agent's terminal in the panel on
// the right, or selects it; the mark of the terminal shown is pressed.
//
// Two views. On a phone `Team` is a row of chips above the feed. Above a phone `HeadTeam` stands
// in the session's head on every tab (decided 2026-11-06, LAD-197, docs/design/ui.md, Session
// head): its level is one for all agents, chosen by trial (teamFit.ts), and from level 1 a
// button opens the team's list, with every agent by its whole name.
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type FocusEvent,
  type KeyboardEvent,
  type ReactNode,
  type RefObject,
} from "react";
import { flushSync } from "react-dom";
import { Link } from "react-router";

import type { AgentInfo, RunInfo } from "./api";
import { since } from "./ChatText";
import { avatar } from "./FeedRow";
import { AgentsIcon, ChevronIcon, FlowsIcon } from "./icons";
import { useLive, useLiveStore } from "./live";
import { useBelow, useDismiss } from "./Menu";
import { runPath } from "./paths";
import { plural } from "./SessionControl";
import { agentMarks, chooseLevel, fitLabel, stepFits, teamSteps, type TeamStep } from "./teamFit";
import { useOpenTerminal, useShownTerminal } from "./Terminals";
import { Tooltip } from "./Tooltip";

export const SUPERVISOR = "supervisor";

export type TeamGroups = { own: AgentInfo[]; runs: { run: string; agents: AgentInfo[] }[] };

// The supervisor's row: the supervisor first, then the agents of no run as the server lists
// them; then a group per run, in the order its first agent is listed, its agents likewise.
export function teamGroups(agents: AgentInfo[]): TeamGroups {
  const own = agents.filter((one) => one.run === null);
  const runs = new Map<string, AgentInfo[]>();
  for (const one of agents) if (one.run !== null) runs.set(one.run, [...(runs.get(one.run) ?? []), one]);
  return {
    own: [...own.filter((one) => one.name === SUPERVISOR), ...own.filter((one) => one.name !== SUPERVISOR)],
    runs: [...runs].map(([run, members]) => ({ run, agents: members })),
  };
}

// The team's agents in its order.
const inOrder = ({ own, runs }: TeamGroups): AgentInfo[] => [...own, ...runs.flatMap((one) => one.agents)];

// Each agent's mark, in the head and on the terminals' strip alike.
export const teamMarks = (agents: AgentInfo[]): Map<string, string> =>
  agentMarks(inOrder(teamGroups(agents)).map((one) => one.name));

export const RUN_COLOURS = 4; // --run-1 … --run-4 in tokens.css

// Each run's colour, 1 … RUN_COLOURS: its place among all the session's runs, ended ones
// too, counted oldest first. `runs` as the server lists them (by created_at and rowid,
// served newest first), with no sort of its own, so a run's colour never moves while
// others start and end.
export function runColours(runs: RunInfo[]): Map<string, number> {
  return new Map(runs.map((one, i) => [one.name, ((runs.length - 1 - i) % RUN_COLOURS) + 1]));
}

// An agent's status as a dot (its colour and shape: styles.css); small on a terminal's tab.
export function StatusDot({ status, small = false }: { status: AgentInfo["status"]; small?: boolean }) {
  return <span className={`dot${small ? " dot-small" : ""} dot-${status}`} aria-hidden="true" />;
}

// What a tooltip says about an agent, compactly: name · role · provider (the role left out
// when it is the name), and the flow run it works for. `info` null: an agent not listed.
export function AgentTip({ name, info }: { name: string; info: AgentInfo | null }) {
  const about = info ? [name, info.role !== name && info.role, info.provider].filter(Boolean) : [name];
  return (
    <>
      <div className="tooltip-line">{about.join(" · ")}</div>
      {info?.run && <div className="tooltip-line">flow {info.run}</div>}
    </>
  );
}

// An agent's status in words, in its popup, the team's list and its accessible name.
const STATUS_WORDS: Record<AgentInfo["status"], string> = {
  busy: "working",
  background: "in the background",
  idle: "idle",
  waiting: "waits for you",
  starting: "starting",
  stopped: "stopped",
};

// An agent's popup in the head and on the terminals' strip: who it is, what it does and how
// long, and what a click does. `info` null: an agent not listed.
export function AgentPopup({ name, info }: { name: string; info: AgentInfo | null }) {
  return (
    <>
      <div className="tooltip-line tip-agent">{name}</div>
      {info && (
        <>
          <div className={`tooltip-line tip-status${info.status === "waiting" ? " waits" : ""}`}>
            {STATUS_WORDS[info.status]} · {since(info.since)}
          </div>
          <div className="tooltip-line">{[info.role !== name && info.role, info.provider].filter(Boolean).join(" · ")}</div>
          {info.run && <div className="tooltip-line">flow {info.run}</div>}
        </>
      )}
      <div className="tooltip-line">Click to open the terminal</div>
    </>
  );
}

// What the team of a session needs, for either view.
function useTeam(session: string) {
  const live = useLiveStore();
  const state = useLive();
  const loaded = state.agents[session] ?? null;
  const loadedRuns = state.runs[session] ?? null;
  const open = useOpenTerminal();
  const shown = useShownTerminal();
  useEffect(() => live.watch("agents", session), [live, session]);
  useEffect(() => live.watch("runs", session), [live, session]);
  const colours = loadedRuns !== null && !("error" in loadedRuns) ? runColours(loadedRuns.items) : new Map<string, number>();
  return { loaded, colours, open, shown };
}

export function Team({ session }: { session: string }) {
  const { loaded, colours, open, shown } = useTeam(session);
  if (loaded === null) return null;
  if ("error" in loaded) {
    return (
      <p className="problem" role="alert">
        {loaded.error}
      </p>
    );
  }
  const { own, runs } = teamGroups(loaded.items);
  return (
    <div role="group" aria-label="Team" className="team">
      <span className="team-label" aria-hidden="true">
        Team
      </span>
      {own.map((agent) => (
        <AgentChip key={agent.name} agent={agent} shown={shown} open={open} />
      ))}
      {runs.map(({ run, agents }) => (
        <RunFrame key={run} session={session} run={run} colour={colours.get(run) ?? null} agents={agents} shown={shown} open={open} />
      ))}
    </div>
  );
}

// A flow run's frame: the Flows icon, a link to the run's page, then its agents' chips, or
// what `children` shows of them; its dashes in the run's colour (`colour` null: not known yet,
// grey).
export function RunFrame({
  session,
  run,
  colour,
  agents,
  shown,
  open,
  children,
}: {
  session: string;
  run: string;
  colour: number | null;
  agents: AgentInfo[];
  shown: string | null;
  open: (name: string) => void;
  children?: ReactNode;
}) {
  return (
    <div role="group" aria-label={`run ${run}`} className="team-run" data-colour={colour ?? undefined}>
      <Tooltip tip={`flow ${run}`}>
        <Link className="team-run-link" to={runPath(session, run)} aria-label={`run ${run} in Flows`} data-team={`run:${run}`}>
          <FlowsIcon />
        </Link>
      </Tooltip>
      {children ?? agents.map((agent) => <AgentChip key={agent.name} agent={agent} shown={shown} open={open} />)}
    </div>
  );
}

// One agent's chip: its role is left to the tooltip and its name for assistive technology. In
// the head it shows `label`, says `named` and has the popup `tip`.
export function AgentChip({
  agent,
  shown,
  open,
  label = agent.name,
  named = `${agent.name}, ${agent.role}, ${agent.status}`,
  tip = <AgentTip name={agent.name} info={agent} />,
}: {
  agent: AgentInfo;
  shown: string | null;
  open: (name: string) => void;
  label?: string;
  named?: string;
  tip?: ReactNode;
}) {
  return (
    <Tooltip tip={tip}>
      <button
        type="button"
        className="team-chip"
        data-team={`agent:${agent.name}`}
        aria-label={named}
        aria-pressed={agent.name === shown}
        onClick={() => open(agent.name)}
      >
        <StatusDot status={agent.status} />
        <span className="team-chip-name">{label}</span>
      </button>
    </Tooltip>
  );
}

// How the head names an agent: by its popup's words, the role left out when it is the name.
export const headName = (agent: AgentInfo): string =>
  [agent.name, agent.role !== agent.name && agent.role, STATUS_WORDS[agent.status]].filter(Boolean).join(", ");

// One agent's avatar in the head: the terminals' strip's button, its mark told from the team.
function AgentAvatar({
  agent,
  mark,
  shown,
  open,
}: {
  agent: AgentInfo;
  mark: string;
  shown: string | null;
  open: (name: string) => void;
}) {
  return (
    <Tooltip tip={<AgentPopup name={agent.name} info={agent} />}>
      <button
        type="button"
        className={`strip-agent avatar-${avatar(agent.name).colour}`}
        data-team={`agent:${agent.name}`}
        aria-label={headName(agent)}
        aria-pressed={agent.name === shown}
        onClick={() => open(agent.name)}
      >
        {mark}
        <StatusDot status={agent.status} small />
      </button>
    </Tooltip>
  );
}

// What the list's button is named at level 3, by the agents it stands for: `visible` is how
// many avatars stand before it.
export function moreName(hidden: AgentInfo[], visible: number): string {
  const waiting = hidden.filter((one) => one.status === "waiting").length;
  const counted = visible > 0 ? plural(hidden.length, "more agent") : plural(hidden.length, "agent");
  return waiting > 0 ? `${counted}, ${waiting} waits for you` : counted;
}

// The team's list, under its button (`children`, named `name`; `chevron` when it hides nothing;
// `pressed` when the terminal shown is among what it hides), closing as Details does: Esc and
// a second click put the focus back on the button; a press outside, or the focus going past
// it, leave the focus where it went. `showing` is its row's, as a trial may pass through level
// 0, which has no button; `stays` says the button stays once the list closes, or the focus
// goes to the team's first item.
function TeamList({
  session,
  groups,
  colours,
  shown,
  open,
  name,
  chevron,
  pressed,
  showing,
  setShowing,
  stays,
  children,
}: {
  session: string;
  groups: TeamGroups;
  colours: Map<string, number>;
  shown: string | null;
  open: (name: string) => void;
  name: string;
  chevron: boolean;
  pressed: boolean;
  showing: boolean;
  setShowing: (showing: boolean) => void;
  stays: boolean;
  children: ReactNode;
}) {
  const box = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const popover = useRef<HTMLDivElement>(null);
  const below = useBelow(button, popover, showing, true);
  const close = useCallback(() => {
    setShowing(false);
    const first = box.current?.closest("[role=toolbar]")?.querySelector<HTMLElement>("[data-team]");
    (stays ? button.current : first)?.focus();
  }, [setShowing, stays]);
  const pressedAway = useCallback(() => setShowing(false), [setShowing]);
  useDismiss(showing, box, pressedAway);
  useEffect(() => {
    if (!showing) return;
    const escape = (event: globalThis.KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      event.preventDefault();
      close();
    };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [showing, close]);
  // Looked at after the event, as Details does.
  const focusLeft = () => {
    setTimeout(() => {
      const now = document.activeElement;
      if (now && now !== document.body && !box.current?.contains(now)) setShowing(false);
    });
  };
  const row = (agent: AgentInfo) => (
    <li key={agent.name}>
      <button
        type="button"
        className="team-popover-agent"
        aria-current={agent.name === shown ? "true" : undefined}
        onClick={() => {
          close();
          open(agent.name);
        }}
      >
        <StatusDot status={agent.status} />
        <span className="team-popover-name">{agent.name}</span>
        <span className={`team-popover-about${agent.status === "waiting" ? " waits" : ""}`}>{STATUS_WORDS[agent.status]}</span>
      </button>
    </li>
  );
  return (
    <div ref={box} className="team-list" onBlur={focusLeft}>
      <button
        ref={button}
        type="button"
        className={`team-more${chevron ? " chevron" : ""}`}
        aria-label={name}
        aria-haspopup="dialog"
        aria-expanded={showing}
        data-shown={pressed || undefined}
        data-team="list"
        onClick={() => {
          if (showing) return close();
          flushSync(() => setShowing(true));
          popover.current?.querySelector("button")?.focus();
        }}
      >
        {children}
      </button>
      {showing && (
        <div ref={popover} role="dialog" aria-label="Team" className="team-popover" style={below}>
          <h2>Team · {plural(inOrder(groups).length, "agent")}</h2>
          <ul>{groups.own.map(row)}</ul>
          {groups.runs.map(({ run, agents }) => (
            <div key={run}>
              <div className="team-popover-run" data-colour={colours.get(run)}>
                <FlowsIcon />
                <Link to={runPath(session, run)} onClick={() => setShowing(false)}>
                  <span>{run}</span>
                </Link>
              </div>
              <ul>{agents.map(row)}</ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Whether the title keeps its limit: as wide as its first 24 characters need, or all of a
// shorter one. Measured by the text, as `24ch` is the digit's width, wider than letters. With
// the title's field open (`text` null) there is no text, and the limit does not count.
const TITLE_LIMIT = 24;

function titleKept(text: HTMLElement | null): boolean {
  const words = text?.firstChild;
  if (!text || !words) return true;
  const range = document.createRange();
  range.setStart(words, 0);
  range.setEnd(words, Math.min(TITLE_LIMIT, words.textContent?.length ?? 0));
  return text.getBoundingClientRect().width >= range.getBoundingClientRect().width - 0.5;
}

function rowFits(team: HTMLElement): boolean {
  const last = team.lastElementChild;
  return !last || last.getBoundingClientRect().right <= team.getBoundingClientRect().right + 0.5;
}

// What puts the keyboard's focus back after a trial, which renders other elements for the same
// items: on its item, or, gone behind the list's button, on that.
function holdFocus(team: HTMLElement): () => void {
  const held = document.activeElement as HTMLElement | null;
  const key = held && team.contains(held) ? held.dataset.team : undefined;
  return () => {
    if (key === undefined || team.contains(held)) return;
    const items = [...team.querySelectorAll<HTMLElement>("[data-team]")];
    (items.find((one) => one.dataset.team === key) ?? items.find((one) => one.dataset.team === "list") ?? items[0])?.focus();
  };
}

// The step the team shows, chosen by rendering each candidate and measuring it (`trial`: the
// list's button then holds its diamond's room, so a status change needs no new trial). A
// microtask, as flushSync cannot render inside an effect; it still runs before the paint.
// Again on a change of the top bar's width (not the team's, whose box the trial changes), the
// agents, what else stands in the line (`line`: the title, the project, which comes late, the
// link's mark), the fonts, the run time while it shows (`ran`: level 0), and when the title's
// field closes. Not when it opens: its room is the title's, and the team stays as it stands
// until something else changes.
function useTeamFit(
  box: RefObject<HTMLDivElement | null>,
  names: string[],
  line: string,
  ran: string,
  titleText: RefObject<HTMLElement | null>,
  editing: boolean,
): { step: TeamStep; trial: boolean } {
  const [fit, setFit] = useState<{ step: TeamStep; trial: boolean }>({ step: { level: 0 }, trial: false });
  const key = names.join("\n");
  const again = useRef(() => {});
  useLayoutEffect(() => {
    const team = box.current;
    const bar = team?.closest(".topbar");
    if (!team) return;
    let gone = false;
    let queued = false;
    const steps = teamSteps(key.split("\n"));
    const show = (step: TeamStep, trial: boolean) => flushSync(() => setFit({ step, trial }));
    const choose = () => {
      queued = false;
      if (gone) return;
      const putBack = holdFocus(team);
      const chosen = chooseLevel(steps, (step) => {
        show(step, true);
        return stepFits(step, rowFits(team), titleKept(titleText.current));
      });
      show(chosen, false);
      putBack();
    };
    const queue = () => {
      if (queued) return;
      queued = true;
      queueMicrotask(choose);
    };
    again.current = queue;
    queue();
    // Not `fonts.ready`, which hears only the load under way: a font may start after this trial.
    document.fonts?.addEventListener("loadingdone", queue);
    let width = bar?.clientWidth;
    const widthChanged = () => {
      if (bar?.clientWidth === width) return; // an observer speaks once on its own
      width = bar?.clientWidth;
      queue();
    };
    const observer = typeof ResizeObserver === "undefined" || !bar ? null : new ResizeObserver(widthChanged);
    if (bar) observer?.observe(bar);
    return () => {
      gone = true;
      document.fonts?.removeEventListener("loadingdone", queue);
      observer?.disconnect();
    };
  }, [box, key, line, titleText]);
  useLayoutEffect(() => {
    if (!editing) again.current();
  }, [editing]);
  const ranShows = useRef(true);
  ranShows.current = fit.step.level === 0; // a ref: as a dependency, each trial would start another
  useLayoutEffect(() => {
    if (ranShows.current) again.current();
  }, [ran]);
  return fit;
}

// The toolbar's one Tab stop: the item last focused, else the first, and the keys that move
// among its items (`data-team`, which a trial's new elements keep; the team's list has its own
// keys). A key with a modifier is the browser's: Alt+← goes back.
function useToolbar(box: RefObject<HTMLDivElement | null>) {
  const stop = useRef<string | undefined>(undefined);
  const items = useCallback(() => [...(box.current?.querySelectorAll<HTMLElement>("[data-team]") ?? [])], [box]);
  const mark = useCallback(() => {
    const all = items();
    const kept = all.find((one) => one.dataset.team === stop.current) ?? all[0];
    for (const one of all) one.tabIndex = one === kept ? 0 : -1;
  }, [items]);
  useLayoutEffect(mark);
  return {
    onFocus: (event: FocusEvent<HTMLDivElement>) => {
      const key = event.target.dataset.team;
      if (key === undefined) return;
      stop.current = key;
      mark();
    },
    onKeyDown: (event: KeyboardEvent<HTMLDivElement>) => {
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      const all = items();
      const at = all.indexOf(event.target as HTMLElement);
      if (at < 0) return;
      const to = { ArrowRight: at + 1, ArrowLeft: at - 1, Home: 0, End: all.length - 1 }[event.key];
      if (to === undefined) return;
      event.preventDefault();
      all[(to + all.length) % all.length]?.focus();
    },
  };
}

function HeadRow({
  session,
  agents,
  colours,
  shown,
  open,
  line,
  ran,
  titleText,
  editing,
}: {
  session: string;
  agents: AgentInfo[];
  colours: Map<string, number>;
  shown: string | null;
  open: (name: string) => void;
  line: string;
  ran: string;
  titleText: RefObject<HTMLElement | null>;
  editing: boolean;
}) {
  const box = useRef<HTMLDivElement>(null);
  const groups = teamGroups(agents);
  const all = inOrder(groups);
  const names = all.map((one) => one.name);
  const marks = agentMarks(names);
  const { step, trial } = useTeamFit(box, names, line, ran, titleText, editing);
  const toolbar = useToolbar(box);
  const [showing, setShowing] = useState(false);
  const visible = step.level === 3 ? step.visible : all.length;
  const seen = new Set(names.slice(0, visible));
  const hidden = all.slice(visible);
  const item = (agent: AgentInfo) =>
    step.level >= 2 ? (
      <AgentAvatar key={agent.name} agent={agent} mark={marks.get(agent.name)!} shown={shown} open={open} />
    ) : (
      <AgentChip
        key={agent.name}
        agent={agent}
        shown={shown}
        open={open}
        label={step.level === 1 ? fitLabel(agent.name, step.k, names) : agent.name}
        named={headName(agent)}
        tip={<AgentPopup name={agent.name} info={agent} />}
      />
    );
  const inSight = (one: AgentInfo) => seen.has(one.name);
  return (
    <div ref={box} role="toolbar" aria-label="Team" className="team head-team" data-fit={step.level} {...toolbar}>
      {step.level === 0 && (
        <span className="team-label" aria-hidden="true">
          Team
        </span>
      )}
      {groups.own.filter(inSight).map(item)}
      {groups.runs
        .filter(({ agents: members }) => members.some(inSight))
        .map(({ run, agents: members }) => (
          <RunFrame key={run} session={session} run={run} colour={colours.get(run) ?? null} agents={members} shown={shown} open={open}>
            {members.filter(inSight).map(item)}
          </RunFrame>
        ))}
      {(step.level > 0 || showing) && (
        <TeamList
          session={session}
          groups={groups}
          colours={colours}
          shown={shown}
          open={open}
          name={step.level === 3 ? moreName(hidden, visible) : `All ${plural(all.length, "agent")}`}
          chevron={step.level !== 3}
          pressed={hidden.some((one) => one.name === shown)}
          showing={showing}
          setShowing={setShowing}
          stays={step.level > 0}
        >
          {step.level !== 3 ? (
            <ChevronIcon />
          ) : (
            <>
              {(trial || hidden.some((one) => one.status === "waiting")) && <StatusDot status="waiting" small />}
              {visible > 0 ? (
                `+${hidden.length}`
              ) : (
                <>
                  <AgentsIcon />
                  {hidden.length}
                </>
              )}
            </>
          )}
        </TeamList>
      )}
    </div>
  );
}

// The team in the head. Before the agents load, and with none, the head is as without a team;
// a team that fails to load says so, and why in its tooltip. `line` says what else stands in
// the head and `ran` is the run time; `titleText` is the element that shows the title;
// `editing`, that its field is open.
export function HeadTeam({
  session,
  line,
  ran,
  titleText,
  editing,
}: {
  session: string;
  line: string;
  ran: string;
  titleText: RefObject<HTMLElement | null>;
  editing: boolean;
}) {
  const { loaded, colours, open, shown } = useTeam(session);
  if (loaded === null) return null;
  if ("error" in loaded) {
    return (
      <div className="team head-team" data-fit="0">
        <Tooltip tip={loaded.error}>
          <span className="session-state danger-text" role="alert" tabIndex={0}>
            team not loaded
          </span>
        </Tooltip>
      </div>
    );
  }
  if (loaded.items.length === 0) return null;
  return (
    <HeadRow
      session={session}
      agents={loaded.items}
      colours={colours}
      shown={shown}
      open={open}
      line={line}
      ran={ran}
      titleText={titleText}
      editing={editing}
    />
  );
}
