// The sections that are placeholders for now, and Not found.
import { Link } from "react-router";

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

export function Projects() {
  useTitle("Projects");
  return (
    <Placeholder title="Projects" plan={PLANS.projects} toSessions>
      Sessions grouped by project, with each project's repository, kits and settings.
    </Placeholder>
  );
}

export function NotFound() {
  useTitle("Not found");
  return (
    <div className="empty">
      <p>There is no page at this address.</p>
      <Link to="/">Home</Link>
    </div>
  );
}
