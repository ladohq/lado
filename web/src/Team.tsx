// The team above a session's Activity feed: a chip per agent, with its status (a dot whose
// colour and shape differ), name and role. The supervisor and its own workers come first;
// the agents of each flow run follow in a dashed frame named by the run, a link to its page
// in Flows, as compact chips without the role, all in the same row (decided 2026-10-07,
// feature/activity-team; no state of the run: Flows and Agents show it). A chip opens the
// agent's terminal in the panel on the right, or selects it; the chip of the terminal shown
// is marked. Its tooltip (Tooltip.tsx): name · role · provider, and the flow run it works for.
import { useEffect } from "react";
import { Link } from "react-router";

import type { AgentInfo } from "./api";
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

export function Team({ session }: { session: string }) {
  const live = useLiveStore();
  const loaded = useLive().agents[session] ?? null;
  const open = useOpenTerminal();
  const shown = useShownTerminal();
  useEffect(() => live.watch("agents", session), [live, session]);

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
        <div key={run} role="group" aria-label={`run ${run}`} className="team-run">
          <Link className="team-run-name" to={runPath(session, run)}>
            {run}
          </Link>
          {agents.map((agent) => (
            <AgentChip key={agent.name} agent={agent} shown={shown} open={open} compact />
          ))}
        </div>
      ))}
    </div>
  );
}

// One agent's chip; a compact one, in a run's frame, leaves its role to the tooltip and its
// name for assistive technology.
function AgentChip({
  agent,
  shown,
  open,
  compact = false,
}: {
  agent: AgentInfo;
  shown: string | null;
  open: (name: string) => void;
  compact?: boolean;
}) {
  return (
    <Tooltip tip={<AgentTip name={agent.name} info={agent} />}>
      <button
        type="button"
        className={compact ? "chip chip-compact" : "chip"}
        aria-label={`${agent.name}, ${agent.role}, ${agent.status}`}
        aria-pressed={agent.name === shown}
        onClick={() => open(agent.name)}
      >
        <StatusDot status={agent.status} />
        <span className="chip-name">{agent.name}</span>
        {!compact && agent.role !== agent.name && <span className="chip-role">{agent.role}</span>}
      </button>
    </Tooltip>
  );
}
