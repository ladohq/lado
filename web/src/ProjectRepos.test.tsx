// The project's page's repositories and sessions, Add repository and Delete repository
// (openspec change project-page), against a fake server (projectFakes.ts).
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { App } from "./App";
import { FakeEventSource, FakeScreen, FakeSocket, stream, stubDialogs } from "./fakes";
import { cloneJob, FakeProjects, repo, session } from "./projectFakes";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

let server: FakeProjects;

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  FakeScreen.computer();
  stubDialogs();
  server = new FakeProjects();
  server.projects.shop = {
    ...server.projects.shop,
    repos: [
      repo("backend", { branch: "feature/checkout", remote: "github.com/shop/backend" }),
      repo("frontend", { remote: "github.com/shop/frontend" }),
      repo("notes", { branch: null }),
    ],
  };
  FakeEventSource.all = [];
  FakeEventSource.autoStart = true;
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("WebSocket", FakeSocket);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function open(id = "shop") {
  render(
    <MemoryRouter initialEntries={[`/projects/${id}`]}>
      <App />
    </MemoryRouter>,
  );
  return screen.findByRole("region", { name: `Project ${id}` });
}

const block = (page: HTMLElement, name: string) => within(page).getByRole("region", { name });
const repoRows = (page: HTMLElement) =>
  within(block(page, "Repositories"))
    .getAllByRole("row")
    .map((row) => row.querySelector("td")!.textContent);
const rowOf = (page: HTMLElement, name: string) =>
  within(block(page, "Repositories"))
    .getAllByRole("row")
    .find((row) => row.querySelector(".repo-name")!.textContent === name)!;

// Repositories

test("the repositories with their branch and remote, each with Start session and Delete", async () => {
  const page = await open();
  expect(repoRows(page)).toEqual([
    "backendbranch feature/checkout · github.com/shop/backend",
    "frontendbranch main · github.com/shop/frontend",
    "notesdetached HEAD · no remote",
  ]);
  for (const name of ["backend", "frontend", "notes"]) {
    expect(within(rowOf(page, name)).getByRole("button", { name: "Start session" })).toBeTruthy();
    expect(within(rowOf(page, name)).getByRole("button", { name: "Delete" })).toBeTruthy();
  }
  expect(within(block(page, "Repositories")).getByRole("button", { name: "+ Add repository" })).toBeTruthy();
});

test("an empty project says so, with a primary + Add repository", async () => {
  const page = await open("sandbox");
  const repos = block(page, "Repositories");
  expect(repos.textContent).toContain(
    "No repositories yet. A session works in one of the project's repositories: clone one or start one from scratch.",
  );
  const add = within(repos).getByRole("button", { name: "+ Add repository" });
  expect(add.className).toContain("primary");
  expect(within(repos).queryByRole("table")).toBeNull();
});

test("Start session opens New session in Project with the project and the repository", async () => {
  const page = await open();
  fireEvent.click(within(rowOf(page, "frontend")).getByRole("button", { name: "Start session" }));
  const dialog = await screen.findByRole("dialog", { name: "New session" });
  expect(within(dialog).getByRole("button", { name: "Project" }).getAttribute("aria-pressed")).toBe("true");
  await waitFor(() => expect(server.calls("GET", "/api/project-launch?project=shop&repo=frontend")).toHaveLength(1));
});

// Sessions

test("the sessions of the project from the feed: running first, the latest started first, then stopped", async () => {
  server.sessions = [
    session("shop-backend", { project: "shop", status: "stopped", stopped_at: "2026-10-20T10:00:00Z", repo: "/ws/projects/shop/backend" }),
    session("shop-frontend", {
      project: "shop",
      title: "Checkout redesign",
      running_since: "2026-10-23T10:00:00Z",
      repo: "/ws/projects/shop/frontend",
    }),
    session("shop-notes", { project: "shop", status: "stopped", stopped_at: "2026-10-22T10:00:00Z", repo: "/ws/projects/shop/notes" }),
    session("fix-login", { project: "shop", running_since: "2026-10-23T12:00:00Z", repo: "/ws/projects/shop/frontend" }),
    session("acme-crm", { project: "acme", repo: "/ws/projects/acme/crm" }),
    session("loose", { repo: "/ws/projects/shop/frontend" }),
  ];
  const page = await open();
  const sessions = block(page, "Sessions");
  await waitFor(() => expect(within(sessions).getAllByRole("link")).toHaveLength(4));
  expect(within(sessions).getAllByRole("link").map((link) => [link.textContent, link.getAttribute("href")])).toEqual([
    ["fix-login", "/sessions/fix-login"],
    ["Checkout redesign", "/sessions/shop-frontend"],
    ["shop-notes", "/sessions/shop-notes"],
    ["shop-backend", "/sessions/shop-backend"],
  ]);
  const items = within(sessions).getAllByRole("listitem");
  expect(items[1].querySelector(".muted")!.textContent).toBe("shop-frontend · frontend");
  expect(items[1].querySelector(".when")!.textContent).toMatch(/^running /);
  expect(items[3].querySelector(".muted")!.textContent).toBe("backend");
  expect(items[3].querySelector(".when")!.textContent).toMatch(/^stopped .+ ago$/);
  expect(within(items[0]).getByRole("img")).toBeTruthy(); // the status mark
});

test("no sessions of its own: the block says so; a session that starts shows without a read", async () => {
  server.sessions = [session("acme-crm", { project: "acme" }), session("loose")];
  const page = await open();
  const sessions = block(page, "Sessions");
  await waitFor(() => expect(sessions.textContent).toContain("No sessions in this project yet."));
  const started = session("shop-backend", { project: "shop", repo: "/ws/projects/shop/backend" });
  stream().send("change", { kind: "sessions", session: "shop-backend", key: "", op: "insert", item: started }, "11");
  expect(await within(sessions).findByRole("link", { name: "shop-backend" })).toBeTruthy();
});

// Add repository

const addDialog = () => screen.getByRole("dialog", { name: "Add a repository to Shop" });
const inDialog = (name: string) => within(addDialog()).getByRole("textbox", { name }) as HTMLInputElement;
const dialogButton = (name: string) => within(addDialog()).getByRole("button", { name }) as HTMLButtonElement;

async function addRepository(source: "Clone from URL" | "From scratch") {
  const page = await open();
  fireEvent.click(within(block(page, "Repositories")).getByRole("button", { name: "+ Add repository" }));
  fireEvent.click(dialogButton(source));
  return page;
}

test("From scratch makes the repository by its name; the dialog closes and the row shows", async () => {
  const page = await addRepository("From scratch");
  expect(addDialog().textContent).toContain("A new git repository with one empty commit.");
  expect(dialogButton("Create").disabled).toBe(true);
  fireEvent.change(inDialog("Name"), { target: { value: "web" } });
  expect(addDialog().textContent).toContain("Its folder: /ws/projects/shop/web");
  fireEvent.click(dialogButton("Create"));
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Add a repository to Shop" })).toBeNull());
  expect(server.calls("POST", "/api/projects/shop/repos")).toEqual([
    { method: "POST", path: "/api/projects/shop/repos", body: { name: "web" } },
  ]);
  await waitFor(() => expect(repoRows(page)).toContain("webbranch main · no remote"));
});

test("a refused name shows the core's text under Name, the dialog and the name kept", async () => {
  server.refuse = (asked) =>
    asked.path === "/api/projects/shop/repos"
      ? "/ws/projects/shop/notes already exists in project shop: choose another name"
      : null;
  await addRepository("From scratch");
  fireEvent.change(inDialog("Name"), { target: { value: "notes" } });
  fireEvent.click(dialogButton("Create"));
  expect((await within(addDialog()).findByRole("alert")).textContent).toBe(
    "/ws/projects/shop/notes already exists in project shop: choose another name",
  );
  expect(inDialog("Name").value).toBe("notes");
});

const URL_ = "git@github.com:shop/admin.git";

async function cloneReady() {
  server.remotes[URL_] = { url: URL_, branches: ["main", "develop"], default: "main", repo_name: "admin" };
  const page = await addRepository("Clone from URL");
  expect(dialogButton("Clone").disabled).toBe(true);
  fireEvent.change(inDialog("Git URL"), { target: { value: URL_ } });
  await waitFor(() => expect(inDialog("Name").value).toBe("admin"), { timeout: 3000 });
  expect(addDialog().textContent).toContain("✓ repository found · 2 branches");
  await waitFor(() => expect(dialogButton("Clone").disabled).toBe(false));
  return page;
}

test("Clone lists the branches, takes the URL's name until edited, and clones into the project", async () => {
  const page = await cloneReady();
  const branch = within(addDialog()).getByRole("combobox", { name: "Branch" }) as HTMLSelectElement;
  expect(branch.value).toBe("main");
  fireEvent.change(branch, { target: { value: "develop" } });
  fireEvent.change(inDialog("Name"), { target: { value: "admin-ui" } });
  server.polls = [cloneJob({ progress: { phase: "Receiving objects", percent: 62, detail: "" } }), cloneJob({ state: "done" })];
  fireEvent.click(dialogButton("Clone"));
  expect(await within(addDialog()).findByRole("progressbar", { name: "Clone" })).toBeTruthy();
  expect(inDialog("Name").disabled).toBe(true);
  expect(server.calls("POST", "/api/clones")[0].body).toEqual({ url: URL_, project: "shop", name: "admin-ui", branch: "develop" });
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Add a repository to Shop" })).toBeNull(), {
    timeout: 3000,
  });
  await waitFor(() => expect(repoRows(page)).toContain("admin-uibranch develop · no remote"));
});

test("a running clone cannot be closed; Cancel clone stops it and the dialog says so", async () => {
  await cloneReady();
  server.polls = [cloneJob(), cloneJob(), cloneJob({ state: "cancelled" })];
  fireEvent.click(dialogButton("Clone"));
  await within(addDialog()).findByRole("progressbar", { name: "Clone" });
  expect(within(addDialog()).queryByRole("button", { name: "Cancel" })).toBeNull();
  fireEvent(addDialog(), new Event("cancel", { cancelable: true })); // Esc
  expect(addDialog()).toBeTruthy();
  fireEvent.click(dialogButton("Cancel clone"));
  expect(await within(addDialog()).findByText("the clone was cancelled", undefined, { timeout: 3000 })).toBeTruthy();
  expect(server.asked.some((one) => one.method === "DELETE" && one.path === "/api/clones/j1")).toBe(true);
  expect(inDialog("Name").disabled).toBe(false);
});

test("leaving the page while the clone runs cancels it at once", async () => {
  await cloneReady();
  server.polls = [cloneJob()];
  fireEvent.click(dialogButton("Clone"));
  await within(addDialog()).findByRole("progressbar", { name: "Clone" });
  expect(server.calls("DELETE", "/api/clones/j1")).toEqual([]);
  const list = screen.getByRole("navigation", { name: "Projects" });
  fireEvent.click(within(list).getByRole("link", { name: /ACME CRM/ })); // another page in the app
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Add a repository to Shop" })).toBeNull());
  expect(server.calls("DELETE", "/api/clones/j1")).toHaveLength(1);
});

test("a failed clone shows its text and hint, the dialog kept", async () => {
  await cloneReady();
  const error = { message: "git could not read the repository", kind: "ssh_denied", hint: { text: "Add your key:", command: "ssh-add" } };
  server.polls = [cloneJob({ state: "failed", error })];
  fireEvent.click(dialogButton("Clone"));
  expect(await within(addDialog()).findByText("git could not read the repository", undefined, { timeout: 3000 })).toBeTruthy();
  expect(addDialog().textContent).toContain("Add your key:");
  expect(addDialog().textContent).toContain("ssh-add");
});

test("a refused clone start shows the core's text under Name", async () => {
  await cloneReady();
  server.refuse = (asked) =>
    asked.path === "/api/clones"
      ? { message: "/ws/projects/shop/admin already exists in project shop: choose another name", kind: "refused", hint: null }
      : null;
  fireEvent.click(dialogButton("Clone"));
  expect((await within(addDialog()).findByRole("alert")).textContent).toBe(
    "/ws/projects/shop/admin already exists in project shop: choose another name",
  );
});

test("a remote that cannot be listed says so under Git URL, Clone stays off", async () => {
  await addRepository("Clone from URL");
  fireEvent.change(inDialog("Git URL"), { target: { value: "git@github.com:shop/none.git" } });
  expect(await within(addDialog()).findByText("git@github.com:shop/none.git not found", undefined, { timeout: 3000 })).toBeTruthy();
  expect(dialogButton("Clone").disabled).toBe(true);
});

test("Cancel closes Add repository and makes nothing", async () => {
  await addRepository("From scratch");
  fireEvent.click(dialogButton("Cancel"));
  expect(screen.queryByRole("dialog", { name: "Add a repository to Shop" })).toBeNull();
  expect(server.calls("POST", "/api/projects/shop/repos")).toEqual([]);
});

// Delete repository

const deleteDialog = (name: string) => screen.getByRole("dialog", { name: `Delete repository ${name}?` });

async function deleting(name: string) {
  const page = await open();
  fireEvent.click(within(rowOf(page, name)).getByRole("button", { name: "Delete" }));
  return page;
}

test("Delete shows what goes; with unpushed work the name must be typed first", async () => {
  server.removals.backend = {
    unpushed: [
      "backend: uncommitted changes; branch feature/checkout not pushed; 2 stashes",
      "backend (worktree .lado/worktrees/shop-backend/dev-1): uncommitted changes",
    ],
    sessions: [
      { name: "shop-backend", open_runs: 1, project: "shop" },
      { name: "backend-old", open_runs: 0, project: null },
    ],
  };
  const page = await deleting("backend");
  const dialog = deleteDialog("backend");
  await within(dialog).findByText("Work that is not on the remote");
  expect(dialog.textContent).toContain(
    "Its folder /ws/projects/shop/backend is deleted with everything in it. This cannot be undone.",
  );
  const items = within(dialog).getAllByRole("listitem").map((item) => item.textContent);
  expect(items).toEqual([
    "backend: uncommitted changes; branch feature/checkout not pushed; 2 stashes",
    "backend (worktree .lado/worktrees/shop-backend/dev-1): uncommitted changes",
    "shop-backend (1 open run)",
    "backend-old — no project, started in this folder before projects",
  ]);
  const remove = within(dialog).getByRole("button", { name: "Delete repository" }) as HTMLButtonElement;
  expect(remove.disabled).toBe(true);
  const typed = within(dialog).getByRole("textbox", { name: "Type backend to delete it" });
  for (const wrong of ["Backend", "backend ", "back"]) {
    fireEvent.change(typed, { target: { value: wrong } });
    expect(remove.disabled).toBe(true);
  }
  fireEvent.change(typed, { target: { value: "backend" } });
  expect(remove.disabled).toBe(false);
  fireEvent.click(remove);
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Delete repository backend?" })).toBeNull());
  expect(server.asked.filter((one) => one.method === "DELETE")).toEqual([
    { method: "DELETE", path: "/api/projects/shop/repos/backend", body: undefined },
  ]);
  await waitFor(() => expect(repoRows(page)).toHaveLength(2));
});

test("a clean repository asks no name", async () => {
  const page = await deleting("frontend");
  const dialog = deleteDialog("frontend");
  expect(await within(dialog).findByText("All its work is on the remote. No session is forgotten.")).toBeTruthy();
  expect(within(dialog).queryByRole("textbox")).toBeNull();
  fireEvent.click(within(dialog).getByRole("button", { name: "Delete repository" }));
  await waitFor(() => expect(repoRows(page).some((row) => row!.startsWith("frontend"))).toBe(false));
});

test("sessions alone ask no name", async () => {
  server.removals.frontend = { sessions: [{ name: "shop-frontend", open_runs: 0, project: "shop" }] };
  await deleting("frontend");
  const dialog = deleteDialog("frontend");
  expect(await within(dialog).findByText("All its work is on the remote.")).toBeTruthy();
  expect(within(dialog).queryByRole("textbox")).toBeNull();
  expect((within(dialog).getByRole("button", { name: "Delete repository" }) as HTMLButtonElement).disabled).toBe(false);
});

test("a refused preview shows the core's text and only Close", async () => {
  const text =
    "repository frontend of project shop has sessions not stopped: shop-frontend; stop them first with lado stop <name>";
  server.refuse = (asked) => (asked.path.endsWith("/frontend/removal") ? text : null);
  await deleting("frontend");
  const dialog = deleteDialog("frontend");
  expect((await within(dialog).findByRole("alert")).textContent).toBe(text);
  expect(within(dialog).getAllByRole("button").map((button) => button.textContent)).toEqual(["Close"]);
  fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));
  expect(screen.queryByRole("dialog", { name: "Delete repository frontend?" })).toBeNull();
});

test("a refused delete after a clean preview shows the text and only Close; nothing goes", async () => {
  const text = "repository frontend of project shop has sessions not stopped: shop-frontend; stop them first with lado stop <name>";
  server.refuse = (asked) => (asked.method === "DELETE" ? text : null);
  const page = await deleting("frontend");
  const dialog = deleteDialog("frontend");
  await within(dialog).findByText("All its work is on the remote. No session is forgotten.");
  fireEvent.click(within(dialog).getByRole("button", { name: "Delete repository" }));
  expect((await within(dialog).findByRole("alert")).textContent).toBe(text);
  expect(within(dialog).getAllByRole("button").map((button) => button.textContent)).toEqual(["Close"]);
  expect(repoRows(page)).toHaveLength(3);
});

test("Cancel closes Delete and removes nothing", async () => {
  await deleting("frontend");
  const dialog = deleteDialog("frontend");
  await within(dialog).findByText("All its work is on the remote. No session is forgotten.");
  fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("dialog", { name: "Delete repository frontend?" })).toBeNull();
  expect(server.asked.filter((one) => one.method === "DELETE")).toEqual([]);
});
