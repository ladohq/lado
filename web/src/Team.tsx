// The team above a session's Activity feed: a chip per agent, the supervisor first, with its
// status (a dot whose colour and shape differ), name and role. A chip opens the agent's
// terminal in the panel on the right, or selects it; the chip of the terminal shown is
// marked. Its tooltip: the run it works for and the first line of its task.
import { useEffect } from "react";

import type { AgentInfo } from "./api";
import { useLive, useLiveStore } from "./live";
import { useOpenTerminal, useShownTerminal } from "./Terminals";

export const SUPERVISOR = "supervisor";

// The supervisor first, the others as the server lists them.
export function teamOrder(agents: AgentInfo[]): AgentInfo[] {
  return [...agents.filter((one) => one.name === SUPERVISOR), ...agents.filter((one) => one.name !== SUPERVISOR)];
}

function hint(agent: AgentInfo): string {
  return [agent.run && `run ${agent.run}`, agent.task].filter(Boolean).join("\n") || agent.role;
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
  return (
    <div role="group" aria-label="Team" className="team">
      <span className="team-label" aria-hidden="true">
        Team
      </span>
      {teamOrder(loaded.items).map((agent) => (
        <button
          key={agent.name}
          type="button"
          className="chip"
          aria-label={`${agent.name}, ${agent.role}, ${agent.status}`}
          aria-pressed={agent.name === shown}
          title={hint(agent)}
          onClick={() => open(agent.name)}
        >
          <span className={`dot dot-${agent.status}`} aria-hidden="true" />
          <span className="chip-name">{agent.name}</span>
          {agent.role !== agent.name && <span className="chip-role">{agent.role}</span>}
        </button>
      ))}
    </div>
  );
}
