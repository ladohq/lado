// The team above a session's Activity feed: a chip per agent, with its status (a dot whose
// colour and shape differ) and name; every chip alike, compact, the role only in the tooltip
// and the accessible name (decided 2026-10-10, fix/team-chip). The supervisor and its own
// workers come first; the agents of each flow run follow in a dashed frame, all in the same
// row (decided 2026-10-07, feature/activity-team; no state of the run: Flows and Agents show
// it). The frame shows no name (decided 2026-10-11, feature/team-run-frames): its dashes are
// in the run's colour (runColours), and the Flows icon in that colour is the link to the
// run's page, its tooltip naming the run; before the runs load, the dashes are grey. A chip opens the
// agent's terminal in the panel on the right, or selects it; the chip of the terminal shown
// is marked. Its tooltip (Tooltip.tsx): name · role · provider, and the flow run it works for.
import { useEffect } from "react";
import { Link } from "react-router";

import type { AgentInfo, RunInfo } from "./api";
import { FlowsIcon } from "./icons";
import { useLive, useLiveStore } from "./live";
import { runPath } from "./paths";
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

// What a tooltip says about an agent, compactly: name · role · provider · model (the role
// left out when it is the name, the model while its CLI has named none), and the flow run it
// works for. `info` null: an agent not listed.
export function AgentTip({ name, info }: { name: string; info: AgentInfo | null }) {
  const about = info
    ? [name, info.role !== name && info.role, info.provider, info.model.name].filter(Boolean)
    : [name];
  return (
    <>
      <div className="tooltip-line">{about.join(" · ")}</div>
      {info?.run && <div className="tooltip-line">flow {info.run}</div>}
    </>
  );
}

export function Team({ session }: { session: string }) {
  const live = useLiveStore();
  const state = useLive();
  const loaded = state.agents[session] ?? null;
  const loadedRuns = state.runs[session] ?? null;
  const open = useOpenTerminal();
  const shown = useShownTerminal();
  useEffect(() => live.watch("agents", session), [live, session]);
  useEffect(() => live.watch("runs", session), [live, session]);

  if (loaded === null) return null;
  if ("error" in loaded) {
    return (
      <p className="problem" role="alert">
        {loaded.error}
      </p>
    );
  }
  const { own, runs } = teamGroups(loaded.items);
  const colours = loadedRuns !== null && !("error" in loadedRuns) ? runColours(loadedRuns.items) : new Map<string, number>();
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

// A flow run's frame: the Flows icon, a link to the run's page, then its agents' chips; its
// dashes in the run's colour (`colour` null: not known yet, grey).
export function RunFrame({
  session,
  run,
  colour,
  agents,
  shown,
  open,
}: {
  session: string;
  run: string;
  colour: number | null;
  agents: AgentInfo[];
  shown: string | null;
  open: (name: string) => void;
}) {
  return (
    <div role="group" aria-label={`run ${run}`} className="team-run" data-colour={colour ?? undefined}>
      <Tooltip tip={`flow ${run}`}>
        <Link className="team-run-link" to={runPath(session, run)} aria-label={`run ${run} in Flows`}>
          <FlowsIcon />
        </Link>
      </Tooltip>
      {agents.map((agent) => (
        <AgentChip key={agent.name} agent={agent} shown={shown} open={open} />
      ))}
    </div>
  );
}

// One agent's chip: its role is left to the tooltip and its name for assistive technology.
export function AgentChip({ agent, shown, open }: { agent: AgentInfo; shown: string | null; open: (name: string) => void }) {
  return (
    <Tooltip tip={<AgentTip name={agent.name} info={agent} />}>
      <button
        type="button"
        className="team-chip"
        aria-label={`${agent.name}, ${agent.role}, ${agent.status}`}
        aria-pressed={agent.name === shown}
        onClick={() => open(agent.name)}
      >
        <StatusDot status={agent.status} />
        <span className="team-chip-name">{agent.name}</span>
      </button>
    </Tooltip>
  );
}
