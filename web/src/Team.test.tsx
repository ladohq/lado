// The team's groups (Team.tsx: teamGroups), a run's frame and its colour (RunFrame,
// runColours), and the Stop icon of a session's head.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, test } from "vitest";

import type { AgentInfo, RunInfo } from "./api";
import { AGENT_REST, popupParts } from "./fakes";
import { ResumeIcon, StopIcon } from "./icons";
import { AgentChip, AgentPopup, AgentTip, headName, moreName, RunFrame, runColours, StatusDot, teamGroups, teamMarks } from "./Team";

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

test("the head names an agent by the popup's words, the role left out when it is the name", () => {
  expect(headName({ ...agent("reviewer"), role: "reviewer", status: "waiting" })).toBe("reviewer, waits for you");
  expect(headName({ ...agent("w1"), status: "background" })).toBe("w1, developer, in the background");
});

test("a phone's chip names its agent by the popup's words", () => {
  render(<AgentChip agent={{ ...agent("w1"), status: "waiting" }} shown={null} open={() => {}} />);
  expect(screen.getByRole("button").getAttribute("aria-label")).toBe("w1, developer, waits for you");
});

test("the list's button says how many it stands for and how many of them wait", () => {
  const waiting: AgentInfo = { ...agent("w2"), status: "waiting" };
  expect(moreName([agent("w1"), waiting, agent("w3"), agent("w4")], 8)).toBe("4 more agents, 1 waits for you");
  expect(moreName([waiting, { ...waiting, name: "w3" }, agent("w1")], 9)).toBe("3 more agents, 2 wait for you");
  expect(moreName([agent("w1")], 3)).toBe("1 more agent");
  expect(moreName([agent("w1"), agent("w2"), agent("w3"), agent("w4")], 0)).toBe("4 agents");
});

test("marks follow the team's order, the supervisor first, whatever the server's", () => {
  const marks = teamMarks([agent("ab-x", "feature/x"), agent("ab_x")]);
  expect(marks.get("ab_x")).toBe("A");
  expect(marks.get("ab-x")).toBe("A2");
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

test("a chip's tooltip names the agent's model when its CLI has named one", () => {
  const known = { ...agent("w1"), model: { name: "gpt-5.6-sol", source: "cli", detail: null, words: "CLI default" } };
  const line = (info: AgentInfo) => render(<AgentTip name={info.name} info={info} />).container.textContent;
  expect(line(known)).toBe("w1 · developer · claude · gpt-5.6-sol");
  expect(line(agent("w2"))).toBe("w2 · developer · claude");
});

// The head's popup (AgentPopup) by its parts.
const popup = (name: string, info: AgentInfo | null) =>
  popupParts(render(<AgentPopup name={name} info={info} />).container);

test("an agent's popup: the name, its status, the facts Role, CLI, Model and Flow, then the click's hint", () => {
  const analyst = {
    ...agent("analyst-254", "task/lad-254"),
    role: "analyst",
    model: { name: "claude-opus-5-5", source: "cli", detail: null, words: "CLI default" },
  };
  const shown = popup("analyst-254", analyst);
  expect(shown).toEqual({
    name: "analyst-254",
    status: expect.stringMatching(/^idle · \d+ d$/),
    facts: ["Role analyst", "CLI claude", "Model claude-opus-5-5", "Flow task/lad-254"],
    hint: "Click to open the terminal",
  });
  cleanup();
  const supervisor = { ...agent("supervisor"), role: "supervisor" };
  expect(popup("supervisor", supervisor).facts).toEqual(["CLI claude", "Model CLI default"]); // the role is its name
});

test("the popup's Model: a configured model's saved name, else the CLI's name in code, else a muted CLI default", () => {
  const configured = {
    ...agent("w1"),
    model: { name: "qwen3-coder", source: "configured", detail: null, words: "configured", configured: "Локальная Qwen" },
  };
  const model = (info: AgentInfo) => {
    const { container } = render(<AgentPopup name={info.name} info={info} />);
    const dt = [...container.querySelectorAll(".tip-facts dt")].find((one) => one.textContent === "Model")!;
    const dd = dt.nextElementSibling!;
    cleanup();
    return [dd.textContent, dd.firstElementChild?.tagName ?? null, dd.firstElementChild?.className ?? null];
  };
  expect(model(configured)).toEqual(["Локальная Qwen", null, null]);
  const named = { ...agent("w2"), model: { name: "gpt-5.6-sol", source: "cli", detail: null, words: "CLI default" } };
  expect(model(named)).toEqual(["gpt-5.6-sol", "CODE", ""]);
  expect(model(agent("w3"))).toEqual(["CLI default", "SPAN", "muted"]);
});

test("the popup names neither the effort nor a source; a waiting agent's status waits; an agent not listed: name and hint", () => {
  const waiting: AgentInfo = {
    ...agent("w1"),
    status: "waiting",
    model: { name: "gpt-5.6-sol", source: "config", detail: "~/.codex/config.toml", words: "from its Codex config" },
    effort: { name: "high", source: "config", detail: "~/.codex/config.toml", words: "from its Codex config" },
  };
  const { container } = render(<AgentPopup name="w1" info={waiting} />);
  expect(container.querySelector(".tip-status")!.className).toBe("tip-status waits");
  expect(container.textContent).not.toMatch(/high|Codex config|config\.toml|Effort/);
  cleanup();
  expect(popup("gone", null)).toEqual({ name: "gone", status: null, facts: [], hint: "Click to open the terminal" });
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
