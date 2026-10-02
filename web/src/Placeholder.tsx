// A section that is not built yet: its name, one sentence on what it will hold, and the
// plan item that builds it (docs/design/ui.md, Structure: a placeholder needs a plan item).
import { useId, type ReactNode } from "react";
import { Link } from "react-router";

import type { Plan } from "./paths";

export function Placeholder(props: {
  title: string;
  plan: Plan;
  children: ReactNode; // what will be here
  level?: 2 | 3;
  toSessions?: boolean; // say where the work is meanwhile
}) {
  const id = useId();
  const Heading = props.level === 3 ? "h3" : "h2";
  return (
    <section className="placeholder" aria-labelledby={id}>
      <Heading id={id}>{props.title}</Heading>
      <p>{props.children}</p>
      <p className="muted">
        Not built yet.{" "}
        <a href={props.plan.href} target="_blank" rel="noreferrer">
          Plan: {props.plan.label}
        </a>
        {props.toSessions && (
          <>
            . Meanwhile your sessions are in <Link to="/sessions">Sessions</Link>
          </>
        )}
        .
      </p>
    </section>
  );
}
