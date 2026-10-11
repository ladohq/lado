// The team's groups (Team.tsx: teamGroups), a run's frame and its colour (RunFrame,
// runColours), and the Stop icon of a session's head.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, test } from "vitest";

import type { AgentInfo, RunInfo } from "./api";
import { AGENT_REST } from "./fakes";
import { ResumeIcon, StopIcon } from "./icons";
import { AgentChip, RunFrame, runColours, StatusDot, teamGroups } from "./Team";

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

test("every chip is one chip: the supervisor's, a worker's and a run's alike, with no role shown", () => {
  const chips = [agent("supervisor"), agent("w1"), agent("dev", "feature/x")].map((one) => {
    const { container } = render(<AgentChip agent={one} shown={null} open={() => {}} />);
    return container.querySelector("button")!;
  });
  for (const chip of chips) {
    expect(chip.className).toBe("team-chip");
    expect(chip.textContent).toBe(chip.querySelector(".team-chip-name")!.textContent); // the name only
    expect(chip.querySelector(".chip-role")).toBeNull();
  }
  expect(chips.map((chip) => chip.getAttribute("aria-label"))).toEqual([
    "supervisor, developer, idle",
    "w1, developer, idle",
    "dev, developer, idle",
  ]); // the role stays for the ear
});

// A run as the server lists it; only its name and status matter to its colour.
function run(name: string, status: RunInfo["status"] = "active"): RunInfo {
  return { name, status } as RunInfo;
}

test("a run's colour is its place among the session's runs as served (newest first), counted oldest first", () => {
  const served = [run("d"), run("c"), run("b"), run("a")]; // a started first
  expect([...runColours(served)]).toEqual([
    ["d", 4],
    ["c", 3],
    ["b", 2],
    ["a", 1],
  ]);
});

test("the colours wrap after four: the fifth run takes the first's colour", () => {
  const served = [run("e"), run("d"), run("c"), run("b"), run("a")];
  expect(runColours(served).get("e")).toBe(1);
  expect(runColours(served).get("a")).toBe(1);
});

test("an ended run keeps its place, so a run started later moves no earlier run's colour", () => {
  const before = runColours([run("b"), run("a", "ended")]);
  const after = runColours([run("c"), run("b"), run("a", "ended")]);
  expect(after.get("a")).toBe(before.get("a"));
  expect(after.get("b")).toBe(before.get("b"));
  expect(after.get("c")).toBe(3);
});

function frame(colour: number | null) {
  return render(
    <MemoryRouter>
      <RunFrame session="lado" run="feature/x" colour={colour} agents={[agent("dev", "feature/x")]} shown={null} open={() => {}} />
    </MemoryRouter>,
  );
}

test("a run's frame shows no name: a link to the run in Flows with the Flows icon, then its chips", () => {
  frame(2);
  const group = screen.getByRole("group", { name: "run feature/x" });
  expect(group.textContent).toBe("dev"); // only the chips' names
  const link = within(group).getByRole("link", { name: "run feature/x in Flows" });
  expect(link.getAttribute("href")).toBe(`/sessions/lado/flows/${encodeURIComponent("feature/x")}`);
  expect(link.querySelector("svg")).not.toBeNull();
  expect(group.firstElementChild).toBe(link);
  expect(group.getAttribute("data-colour")).toBe("2");
});

test("a run's frame with no colour yet has no data-colour", () => {
  frame(null);
  expect(screen.getByRole("group", { name: "run feature/x" }).hasAttribute("data-colour")).toBe(false);
});

test("the link's tooltip names the flow on keyboard focus and on hover", async () => {
  frame(1);
  const link = screen.getByRole("link", { name: "run feature/x in Flows" });
  fireEvent.focus(link);
  expect(screen.getByRole("tooltip").textContent).toBe("flow feature/x");
  fireEvent.blur(link);
  expect(screen.queryByRole("tooltip")).toBeNull();
  fireEvent.mouseEnter(link);
  expect((await screen.findByRole("tooltip")).textContent).toBe("flow feature/x");
});
