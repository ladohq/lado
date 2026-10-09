// The team's groups (Team.tsx: teamGroups) and the Stop icon of a session's head.
import { cleanup, render } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import type { AgentInfo } from "./api";
import { AGENT_REST } from "./fakes";
import { ResumeIcon, StopIcon } from "./icons";
import { StatusDot, teamGroups } from "./Team";

afterEach(cleanup);

function agent(name: string, run: string | null = null): AgentInfo {
  return { name, role: "developer", provider: "claude", status: "idle", run, task: null, status_reason: null, ...AGENT_REST };
}

const names = (agents: AgentInfo[]) => agents.map((one) => one.name);

function shape(agents: AgentInfo[]) {
  const { own, runs } = teamGroups(agents);
  return { own: names(own), runs: runs.map(({ run, agents }) => [run, names(agents)]) };
}

test("with no runs, the supervisor comes first, then the others as the server lists them", () => {
  expect(shape([agent("w1"), agent("supervisor"), agent("w2")])).toEqual({ own: ["supervisor", "w1", "w2"], runs: [] });
});

test("a run's agents are a group of their own, out of the supervisor's row", () => {
  expect(shape([agent("supervisor"), agent("dev", "feature/x"), agent("w1"), agent("rev", "feature/x")])).toEqual({
    own: ["supervisor", "w1"],
    runs: [["feature/x", ["dev", "rev"]]],
  });
});

test("two runs come in the order their first agent is listed, each with its agents in the server's order", () => {
  const agents = [
    agent("a", "fix/b"),
    agent("supervisor"),
    agent("b", "feature/a"),
    agent("c", "fix/b"),
    agent("d", "feature/a"),
  ];
  expect(shape(agents)).toEqual({
    own: ["supervisor"],
    runs: [
      ["fix/b", ["a", "c"]],
      ["feature/a", ["b", "d"]],
    ],
  });
});

test("each status has its own mark, background too, and the dot itself is hidden from readers", () => {
  const statuses: AgentInfo["status"][] = ["starting", "busy", "idle", "background", "waiting", "stopped"];
  for (const status of statuses) {
    const dot = render(<StatusDot status={status} small />).container.firstElementChild!;
    expect(dot.className).toBe(`dot dot-small dot-${status}`);
    expect(dot.getAttribute("aria-hidden")).toBe("true");
    cleanup();
  }
});

test("Stop is a square filled with the text's colour, with no stroke; Resume stays an outline", () => {
  const stop = render(<StopIcon />).container.querySelector("rect")!;
  expect(stop.getAttribute("fill")).toBe("currentColor");
  expect(stop.getAttribute("stroke")).toBe("none");
  cleanup();
  const resume = render(<ResumeIcon />).container.querySelector("path")!;
  expect(resume.getAttribute("fill")).toBeNull();
  expect(resume.closest("svg")!.getAttribute("fill")).toBe("none");
});
