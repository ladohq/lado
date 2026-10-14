// A flow step's direction, one rule for the chat and the Flows tab (docs/design/ui.md, Flow
// events): by the order the run's flow declares its states, never by which other steps are
// loaded. And what its outcome's tooltip says.
import type { RunInfo } from "./api";
import { BackIcon } from "./icons";
import { Tooltip } from "./Tooltip";

type State = RunInfo["states"][number];

export type Direction = "forward" | "back";

// A step goes back when it leads to a state the flow declares no later than the one it left
// (staying in its state too), else forward; null when either state is not in the flow.
export function direction(states: State[], from: string, to: string): Direction | null {
  const order = states.map((one) => one.name);
  const left = order.indexOf(from);
  const entered = order.indexOf(to);
  if (left < 0 || entered < 0) return null;
  return entered <= left ? "back" : "forward";
}

// What runs again after a step back from `from` to `to`: the shortest way through the flow's
// outcomes from `to` to `from`, both included (`[to]` when they are one), breadth-first with
// each state's next states in the flow's declared order, so the same flow gives the same way;
// null when no way leads there.
export function runsAgain(states: State[], from: string, to: string): string[] | null {
  const order = states.map((one) => one.name);
  if (!order.includes(from) || !order.includes(to)) return null;
  const outcomes = new Map(states.map((one) => [one.name, Object.values(one.outcomes)]));
  const came = new Map<string, string | null>([[to, null]]);
  const queue = [to];
  while (queue.length) {
    const state = queue.shift()!;
    if (state === from) {
      const way = [state];
      for (let step = came.get(state); step; step = came.get(step)) way.unshift(step);
      return way;
    }
    const next = [...new Set(outcomes.get(state) ?? [])]
      .filter((one) => order.includes(one) && !came.has(one))
      .sort((a, b) => order.indexOf(a) - order.indexOf(b));
    for (const one of next) {
      came.set(one, state);
      queue.push(one);
    }
  }
  return null;
}

// A step's outcome as a chip: green forward, orange with the return icon back, each in the
// UI's tooltip that says where the step goes; neutral, with no tooltip, when the direction
// is not known. Its accessible name says the direction, as the icon is decorative and the
// tooltip shows only on hover (the chips are no tab stops).
export function OutcomeChip({
  states,
  from,
  to,
  outcome,
  className,
}: {
  states: State[] | null;
  from: string;
  to: string;
  outcome: string;
  className: (way: Direction | null) => string;
}) {
  const way = states ? direction(states, from, to) : null;
  if (way === null) return <span className={className(null)}>{outcome}</span>;
  const chip = (
    <span className={className(way)} aria-label={`${outcome}, a step ${way}`}>
      {way === "back" && <BackIcon />}
      {outcome}
    </span>
  );
  const again = way === "back" ? runsAgain(states!, from, to) : null;
  return <Tooltip tip={<StepTip way={way} to={to} again={again} />}>{chip}</Tooltip>;
}

function StepTip({ way, to, again }: { way: Direction; to: string; again: string[] | null }) {
  if (way === "forward")
    return (
      <div className="tooltip-line">
        Forward in the flow, to <b>{to}</b>
      </div>
    );
  return (
    <>
      <div className="tooltip-line">
        Back: the work returns to <b>{to}</b>
      </div>
      {again && <div className="tooltip-line step-way">Runs again: {again.join(" › ")}</div>}
    </>
  );
}
