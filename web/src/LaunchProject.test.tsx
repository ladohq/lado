// New session's Project field (LaunchProject.tsx) on its own: the projects, the repository
// list and the ways out when nothing can be chosen.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import type { ProjectLaunch, ProjectSummary } from "./api";
import { ProjectField } from "./LaunchProject";

afterEach(cleanup);

const summary = (id: string, more: Partial<ProjectSummary> = {}): ProjectSummary => ({
  id,
  title: null,
  folder: `/ws/projects/${id}`,
  found: true,
  repos: 0,
  running: [],
  ...more,
});

const repo = (name: string, more = {}) => ({
  name,
  path: `/ws/projects/shop/${name}`,
  branch: "main",
  remote: `https://github.com/shop/${name}`,
  ...more,
});

function launch(more: Partial<ProjectLaunch> = {}): ProjectLaunch {
  return {
    projects: [
      summary("acme", { title: "ACME CRM", repos: 1 }),
      summary("old", { title: "Old", found: false }),
      summary("shop", { title: "Shop", repos: 2, running: ["shop-backend"] }),
    ],
    project: "shop",
    repos: [repo("backend", { branch: "develop" }), repo("frontend")],
    repo: "frontend",
    root: "/ws/projects/shop/frontend",
    default_name: "shop-frontend",
    name_state: "free",
    provider: null,
    last: null,
    ...more,
  };
}

function field(shown: ProjectLaunch | null, problem: string | null = null) {
  const calls = { project: vi.fn(), repo: vi.fn(), leave: vi.fn() };
  render(
    <ProjectField
      launch={shown}
      problem={problem}
      head={null}
      disabled={false}
      onProject={calls.project}
      onRepo={calls.repo}
      onLeave={calls.leave}
    />,
  );
  return calls;
}

const projectSelect = () => screen.getByRole("combobox", { name: "Project" }) as HTMLSelectElement;
const repos = () => within(screen.getByRole("radiogroup", { name: "Repository" })).queryAllByRole("radio");

test("the projects in the server's order, a folder not found off, the chosen one's facts", () => {
  const calls = field(launch());
  const options = [...projectSelect().options];
  expect(options.map((one) => one.text)).toEqual(["ACME CRM · acme", "Old · old · folder not found", "Shop · shop"]);
  expect(options.map((one) => one.disabled)).toEqual([false, true, false]);
  expect(projectSelect().value).toBe("shop");
  expect(screen.getByText(/2 repositories · 1 session running · folder/)).toBeTruthy();
  expect(screen.getByText("/ws/projects/shop")).toBeTruthy();
  fireEvent.change(projectSelect(), { target: { value: "acme" } });
  expect(calls.project).toHaveBeenCalledWith("acme");
});

test("the repositories are listed with their branch and remote, one chosen", () => {
  const calls = field(launch());
  expect(repos().map((one) => one.textContent)).toEqual([
    "backenddevelop · https://github.com/shop/backend",
    "frontendmain · https://github.com/shop/frontend",
  ]);
  expect(repos().map((one) => one.getAttribute("aria-checked"))).toEqual(["false", "true"]);
  expect(screen.getByText("✓ git repository · branch main")).toBeTruthy();
  fireEvent.click(repos()[0]);
  expect(calls.repo).toHaveBeenCalledWith("backend");
  fireEvent.keyDown(repos()[1], { key: "ArrowUp" });
  expect(calls.repo).toHaveBeenLastCalledWith("backend");
  fireEvent.click(repos()[1]); // the chosen one: no change
  expect(calls.repo).toHaveBeenCalledTimes(2);
});

test("one repository is still a list, chosen, and the window adds none", () => {
  field(launch({ project: "acme", repos: [repo("crm")], repo: "crm", default_name: "acme-crm" }));
  expect(repos().map((one) => one.getAttribute("aria-checked"))).toEqual(["true"]);
  expect(screen.queryByText(/add|new repository|clone/i)).toBeNull();
});

test("a project without repositories leads to its page", () => {
  const calls = field(
    launch({ project: "acme", repos: [], repo: null, default_name: null, name_state: null, last: null }),
  );
  expect(screen.getByText(/No repositories yet. Add one on the project's page:/)).toBeTruthy();
  expect(repos()).toEqual([]);
  fireEvent.click(screen.getByRole("button", { name: "Open ACME CRM" }));
  expect(calls.leave).toHaveBeenCalledWith("/projects/acme");
});

test("no project leads to the Projects section", () => {
  const calls = field(launch({ projects: [], project: null, repos: [], repo: null, default_name: null }));
  expect(
    screen.getByText(/No projects yet. A project keeps its repositories and the variables its sessions get./),
  ).toBeTruthy();
  expect(screen.queryByRole("combobox", { name: "Project" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Make one in Projects" }));
  expect(calls.leave).toHaveBeenCalledWith("/projects");
});

test("while asking, and when the server fails", () => {
  field(null);
  expect(screen.getByText("checking…")).toBeTruthy();
  cleanup();
  field(null, "the server is down");
  expect(screen.getByText("the server is down")).toBeTruthy();
});
