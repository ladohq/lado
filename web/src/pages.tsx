// The sections that are placeholders for now, and Not found.
import { Link, useParams } from "react-router";

import { PLANS } from "./paths";
import { Placeholder } from "./Placeholder";
import { useTitle } from "./Shell";

export function Home() {
  useTitle("Home");
  return (
    <Placeholder title="Home" plan={PLANS.home} toSessions>
      An overview of all sessions: what runs, what is stuck and what waits for you.
    </Placeholder>
  );
}

export function NeedsYou() {
  useTitle("Needs you");
  return (
    <Placeholder title="Needs you" plan={PLANS.gates} toSessions>
      Every gate of every session that waits for your answer, oldest first.
    </Placeholder>
  );
}

export function Projects() {
  useTitle("Projects");
  return (
    <Placeholder title="Projects" plan={PLANS.projects} toSessions>
      Sessions grouped by project, with each project's repository, kits and settings.
    </Placeholder>
  );
}

export function Kits() {
  useTitle("Kits");
  return (
    <Placeholder title="Kits" plan={PLANS.kits} toSessions>
      The kits LADO knows and where they come from: their roles, skills, MCP servers and flows.
    </Placeholder>
  );
}

export function Marketplace() {
  useTitle("Marketplace");
  return (
    <Placeholder title="Marketplace" plan={PLANS.marketplace} toSessions>
      Find kits and skill packs and add them to LADO.
    </Placeholder>
  );
}

export function Gate() {
  const { id = "" } = useParams();
  const valid = /^[1-9]\d*$/.test(id);
  useTitle(valid ? `Gate #${id}` : "Not found");
  if (!valid) return <NotFoundBody />;
  return (
    <Placeholder title={`Gate #${id}`} plan={PLANS.gates} toSessions>
      The gate's question, the notes it needs, and its answers.
    </Placeholder>
  );
}

export function NotFound() {
  useTitle("Not found");
  return <NotFoundBody />;
}

function NotFoundBody() {
  return (
    <div className="empty">
      <p>There is no page at this address.</p>
      <Link to="/">Home</Link>
    </div>
  );
}
