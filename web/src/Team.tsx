// The team above a session's Activity feed: a chip per agent, the supervisor first, with its
// status (a dot whose colour and shape differ), name and role. A chip opens the agent's
// terminal in the panel on the right, or selects it; the chip of the terminal shown is
// marked. Its tooltip (Tooltip.tsx): name · role · provider, and the flow run it works for.
import { useEffect } from "react";

import type { AgentInfo } from "./api";
import { useLive, useLiveStore } from "./live";
import { useOpenTerminal, useShownTerminal } from "./Terminals";
import { Tooltip } from "./Tooltip";

export const SUPERVISOR = "supervisor";

// The supervisor first, the others as the server lists them.
export function teamOrder(agents: AgentInfo[]): AgentInfo[] {
  return [...agents.filter((one) => one.name === SUPERVISOR), ...agents.filter((one) => one.name !== SUPERVISOR)];
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
  return (
    <div role="group" aria-label="Team" className="team">
      <span className="team-label" aria-hidden="true">
        Team
      </span>
      {teamOrder(loaded.items).map((agent) => (
        <Tooltip key={agent.name} tip={<AgentTip name={agent.name} info={agent} />}>
          <button
            type="button"
            className="chip"
            aria-label={`${agent.name}, ${agent.role}, ${agent.status}`}
            aria-pressed={agent.name === shown}
            onClick={() => open(agent.name)}
          >
            <StatusDot status={agent.status} />
            <span className="chip-name">{agent.name}</span>
            {agent.role !== agent.name && <span className="chip-role">{agent.role}</span>}
          </button>
        </Tooltip>
      ))}
    </div>
  );
}
