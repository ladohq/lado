// What an install or an update brings (docs/design/ui.md, Kits: Update and Install): the
// counts as tiles, roles and flows by name, the skills behind "Show all", the MCP servers and
// the source. For an update with the installed version's contents (`before`), what it adds
// and drops is marked by name; which MCP servers are new is the core's word (`new_mcp`) only.
import { useState } from "react";

import type { KitContentsInfo, PlanInfo } from "./api";
import { shortAddress } from "./KitCard";

type Mark = "added" | "removed" | null;
type Change = { name: string; mark: Mark };

// The new version's names, then the installed version's ones it no longer has; marked only
// when the installed version is known.
function changes(now: string[], before: string[] | null): Change[] {
  if (before === null) return now.map((name) => ({ name, mark: null }));
  return [
    ...now.map((name): Change => ({ name, mark: before.includes(name) ? null : "added" })),
    ...before.filter((name) => !now.includes(name)).map((name): Change => ({ name, mark: "removed" })),
  ];
}

function Chip({ change }: { change: Change }) {
  if (change.mark === "added") return <ins className="kit-chip added">{`+ ${change.name}`}</ins>;
  if (change.mark === "removed") return <del className="kit-chip removed">{change.name}</del>;
  return <span className="kit-chip">{change.name}</span>;
}

function Chips({ list }: { list: Change[] }) {
  return (
    <div className="kit-chips">
      {list.map((change) => (
        <Chip key={`${change.mark}:${change.name}`} change={change} />
      ))}
    </div>
  );
}

function Fact({ name, list }: { name: string; list: Change[] }) {
  const count = list.filter((one) => one.mark !== "removed").length;
  const added = list.filter((one) => one.mark === "added").length;
  const removed = list.filter((one) => one.mark === "removed").length;
  return (
    <div className="kit-fact" role="group" aria-label={name}>
      <span className="kit-fact-name">{name}</span>
      <span className="kit-fact-value">
        {count}
        {added > 0 && <span className="kit-delta">{`+${added}`}</span>}
        {removed > 0 && <span className="kit-delta minus">{`−${removed}`}</span>}
      </span>
    </div>
  );
}

export function PlanContents({ plan, before }: { plan: PlanInfo; before: KitContentsInfo | null }) {
  const [allSkills, setAllSkills] = useState(false);
  const roles = changes(plan.agents, before?.agents ?? null);
  const skills = changes(plan.skills, before?.skills ?? null);
  const flows = changes(plan.flows, before?.flows ?? null);
  const changedSkills = skills.filter((one) => one.mark !== null);
  const servers = new Set(plan.mcp.map((m) => m.name));
  const goneServers = [...new Set(before?.mcp ?? [])].filter((name) => !servers.has(name));
  const isFolder = plan.tag === null;
  return (
    <>
      <div className="kit-facts">
        <Fact name="Roles" list={roles} />
        <Fact name="Skills" list={skills} />
        <Fact name="Flows" list={flows} />
      </div>
      {roles.length > 0 && (
        <div className="kit-group">
          <h4>Roles</h4>
          <Chips list={roles} />
        </div>
      )}
      {flows.length > 0 && (
        <div className="kit-group">
          <h4>Flows</h4>
          <Chips list={flows} />
        </div>
      )}
      {skills.length > 0 && (
        <div className="kit-group">
          <h4>Skills</h4>
          {(allSkills || changedSkills.length > 0) && <Chips list={allSkills ? skills : changedSkills} />}
          {plan.skills.length > 0 && (
            <button type="button" className="link-button" onClick={() => setAllSkills(!allSkills)}>
              {allSkills ? "Show only the changes" : `Show all ${plan.skills.length}`}
            </button>
          )}
        </div>
      )}
      <div className="kit-group">
        <h4>MCP servers</h4>
        {plan.mcp.length === 0 && goneServers.length === 0 ? (
          <p className="muted">none</p>
        ) : (
          <ul className="kit-mcp" aria-label="MCP servers">
            {plan.mcp.map((server) => {
              const isNew = plan.new_mcp.includes(server.name);
              return (
                <li key={server.name} aria-label={isNew ? `${server.name}, new` : server.name}>
                  <span className="kit-mcp-name">{server.name}</span>
                  <span className="kit-mcp-command">{server.command}</span>
                  {isNew && <span className="badge badge-new">new</span>}
                </li>
              );
            })}
            {goneServers.map((name) => (
              <li key={`gone:${name}`} aria-label={`${name}, removed`}>
                <del className="kit-mcp-name">{name}</del>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="kit-group">
        <h4>{isFolder ? "Folder" : "Source"}</h4>
        <p className="kit-where" title={plan.address}>
          {isFolder ? plan.address : shortAddress(plan.address)}
          {plan.commit && ` · commit ${plan.commit.slice(0, 12)}`}
        </p>
      </div>
    </>
  );
}
