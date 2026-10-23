// The Projects section (openspec change projects-section): the list, a project's page and
// New project, against a fake server (projectFakes.ts).
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { App } from "./App";
import { FakeEventSource, FakeScreen, FakeSocket, stream, stubDialogs } from "./fakes";
import { FakeProjects, project, session } from "./projectFakes";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

let server: FakeProjects;
let at = "";

function Where() {
  at = useLocation().pathname;
  return null;
}

function open(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
      <Where />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  FakeScreen.computer();
  stubDialogs();
  server = new FakeProjects();
  FakeEventSource.all = [];
  FakeEventSource.autoStart = true;
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("WebSocket", FakeSocket);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const list = () => screen.getByRole("navigation", { name: "Projects" });
const rows = () => within(list()).getAllByRole("link").map((link) => link.textContent);

test("the list shows each project's title, id, repositories and sessions running", async () => {
  open("/projects");
  await within(list()).findByRole("link", { name: /Shop/ });
  expect(rows()).toEqual([
    "ACME CRMacme · 1 repository · no sessions running",
    "sandboxfolder not foundsandbox · 0 repositories · no sessions running",
    "Shopshop · 2 repositories · 2 running",
  ]);
  expect(screen.getByRole("button", { name: "New project" })).toBeTruthy();
  expect(screen.getByRole("banner").querySelector("h1")!.textContent).toBe("Projects");
  expect(screen.getByText("Select a project")).toBeTruthy();
});

test("the search finds a project by title and by id", async () => {
  open("/projects");
  await within(list()).findByRole("link", { name: /Shop/ });
  const search = screen.getByRole("searchbox", { name: "Find a project" });
  fireEvent.change(search, { target: { value: "crm" } });
  expect(rows()).toEqual(["ACME CRMacme · 1 repository · no sessions running"]);
  fireEvent.change(search, { target: { value: "SANDB" } });
  expect(rows()).toHaveLength(1);
});

test("a row opens the project's page at the right", async () => {
  open("/projects");
  fireEvent.click(await within(list()).findByRole("link", { name: /Shop/ }));
  expect(at).toBe("/projects/shop");
  const page = await screen.findByRole("region", { name: "Project shop" });
  expect(within(page).getByRole("heading", { name: "Shop" })).toBeTruthy();
  expect(page.querySelector(".project-id")!.textContent).toBe("shop");
  expect(page.textContent).toContain("2 repositories · 2 sessions running · folder /ws/projects/shop");
  expect(within(page).getByRole("button", { name: "New session…" })).toBeTruthy();
  expect(within(page).getByRole("button", { name: "Rename" })).toBeTruthy();
  expect(within(page).getByRole("button", { name: "Delete project…" })).toBeTruthy();
  expect(page.textContent).not.toContain("not built yet");
  expect(within(list()).getByRole("link", { name: /Shop/ }).getAttribute("aria-current")).toBe("page");
  expect(list()).toBeTruthy(); // the list stays beside it
});

test("New session… opens the window in Project with the project", async () => {
  open("/projects/acme");
  const page = await screen.findByRole("region", { name: "Project acme" });
  fireEvent.click(within(page).getByRole("button", { name: "New session…" }));
  const dialog = await screen.findByRole("dialog", { name: "New session" });
  expect(within(dialog).getByRole("button", { name: "Project" }).getAttribute("aria-pressed")).toBe("true");
  const select = (await within(dialog).findByRole("combobox", { name: "Project" })) as HTMLSelectElement;
  expect(select.value).toBe("acme");
  expect(server.calls("GET", "/api/project-launch?project=acme")).toHaveLength(1);
  expect(within(dialog).getByRole("radio", { name: /^crm/ }).getAttribute("aria-checked")).toBe("true");
});

// Renaming (openspec change project-page): the session title's field, in the page's head.

const titleField = () => screen.getByRole("textbox", { name: "Project title" }) as HTMLInputElement;
const patches = () => server.asked.filter((one) => one.method === "PATCH");

async function rename(id = "shop") {
  open(`/projects/${id}`);
  const page = await screen.findByRole("region", { name: `Project ${id}` });
  fireEvent.click(within(page).getByRole("button", { name: "Rename" }));
  return page;
}

test("Rename opens the title in place, selected; Enter saves it, the head and the list follow", async () => {
  const page = await rename();
  const field = titleField();
  expect(field.value).toBe("Shop");
  expect([field.selectionStart, field.selectionEnd]).toEqual([0, 4]);
  expect(document.activeElement).toBe(field);
  expect(page.textContent).toContain("Enter to save · Esc to cancel");
  fireEvent.change(field, { target: { value: "Shop EU" } });
  fireEvent.keyDown(field, { key: "Enter" });
  expect(await within(page).findByRole("heading", { name: "Shop EU" })).toBeTruthy();
  expect(patches()).toEqual([{ method: "PATCH", path: "/api/projects/shop", body: { title: "Shop EU" } }]);
  await waitFor(() => expect(rows()[2]).toBe("Shop EUshop · 2 repositories · 2 running"));
  expect(page.querySelector(".project-id")!.textContent).toBe("shop");
});

test("a click on the title opens the field too; leaving it saves", async () => {
  open("/projects/acme");
  const page = await screen.findByRole("region", { name: "Project acme" });
  fireEvent.click(within(page).getByRole("heading", { name: "ACME CRM" }));
  fireEvent.change(titleField(), { target: { value: "ACME" } });
  fireEvent.blur(titleField());
  expect(await within(page).findByRole("heading", { name: "ACME" })).toBeTruthy();
  expect(patches()).toHaveLength(1);
});

test("Esc keeps the title and sends nothing; the same text sends nothing either", async () => {
  const page = await rename();
  fireEvent.change(titleField(), { target: { value: "Other" } });
  fireEvent.keyDown(titleField(), { key: "Escape" });
  expect(within(page).getByRole("heading", { name: "Shop" })).toBeTruthy();
  fireEvent.click(within(page).getByRole("button", { name: "Rename" }));
  fireEvent.keyDown(titleField(), { key: "Enter" });
  await waitFor(() => expect(screen.queryByRole("textbox", { name: "Project title" })).toBeNull());
  expect(patches()).toEqual([]);
});

test("an empty title clears it and the id shows", async () => {
  const page = await rename();
  fireEvent.change(titleField(), { target: { value: "  " } });
  fireEvent.keyDown(titleField(), { key: "Enter" });
  expect(await within(page).findByRole("heading", { name: "shop" })).toBeTruthy();
  expect(patches()).toEqual([{ method: "PATCH", path: "/api/projects/shop", body: { title: null } }]);
});

test("a refused title shows the server's text under the field, the field kept", async () => {
  server.refuse = (asked) => (asked.method === "PATCH" ? "a title is at most 80 characters" : null);
  const page = await rename();
  fireEvent.change(titleField(), { target: { value: "Too long" } });
  fireEvent.keyDown(titleField(), { key: "Enter" });
  expect((await within(page).findByRole("alert")).textContent).toBe("a title is at most 80 characters");
  expect(titleField().value).toBe("Too long");
});

test("in an untitled project the id is the suggestion: Tab takes it, nothing sent", async () => {
  const page = await rename("sandbox");
  const field = titleField();
  expect(field.value).toBe("");
  expect(field.placeholder).toBe("sandbox");
  fireEvent.change(field, { target: { value: "sa", selectionStart: 2, selectionEnd: 2 } });
  field.setSelectionRange(2, 2);
  fireEvent.select(field);
  expect(page.textContent).toContain("Tab takes the id · Enter to save · Esc to cancel");
  expect(page.querySelector(".title-edit-rest")!.textContent).toBe("sandbox");
  fireEvent.keyDown(field, { key: "Tab" });
  expect(titleField().value).toBe("sandbox");
  expect(document.activeElement).toBe(titleField());
  expect(patches()).toEqual([]);
});

test("a project with a title opens the field with no suggestion", async () => {
  const page = await rename();
  expect(page.querySelector(".title-edit-rest")).toBeNull();
  expect(page.textContent).not.toContain("Tab takes the id");
});

test("a project whose folder is gone says so in its head", async () => {
  open("/projects/sandbox");
  const page = await screen.findByRole("region", { name: "Project sandbox" });
  expect(page.textContent).toContain(
    "0 repositories · 0 sessions running · folder /ws/projects/sandbox folder not found",
  );
});

test("an unknown project is named", async () => {
  open("/projects/nope");
  expect(await screen.findByText("No project nope")).toBeTruthy();
});

test("without projects the section explains them and offers New project…", async () => {
  server.projects = {};
  open("/projects");
  expect(await screen.findByRole("heading", { name: "No projects yet" })).toBeTruthy();
  expect(screen.queryByRole("navigation", { name: "Projects" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "New project…" }));
  expect(screen.getByRole("dialog", { name: "New project" })).toBeTruthy();
});

test("the warning and the running line name the sessions by title, as links", async () => {
  server.sessions = [
    session("shop-frontend", { title: "Checkout redesign", project: "shop" }),
    session("shop-backend", { project: "shop" }),
  ];
  open("/projects/shop");
  const page = await screen.findByRole("region", { name: "Project shop" });
  expect(page.textContent).toContain(
    "⚠ Projects of one LADO are not isolated from each other: an agent of one project can read " +
      "another's variables and secrets. For clients that must not mix, run a separate LADO.",
  );
  const line = within(page).getByText(/New values reach the agents/);
  await waitFor(() => expect(within(line).getByRole("link", { name: "Checkout redesign" })).toBeTruthy());
  expect(line.textContent).toBe(
    "New values reach the agents started after a change; running agents keep the environment they " +
      "started with. Running now: shop-backend, Checkout redesign — restart a session to give it the change.",
  );
  expect(within(line).getByRole("link", { name: "Checkout redesign" }).getAttribute("href")).toBe(
    "/sessions/shop-frontend",
  );
  expect(within(line).getByRole("link", { name: "shop-backend" }).getAttribute("href")).toBe("/sessions/shop-backend");
});

test("a project with no session running says so", async () => {
  open("/projects/acme");
  const page = await screen.findByRole("region", { name: "Project acme" });
  expect(page.textContent).toContain(
    "New values reach the agents started after a change. No session of this project is running.",
  );
});

test("the list and the page are read anew when a session starts or stops", async () => {
  server.sessions = [session("shop-backend", { project: "shop" })];
  open("/projects/shop");
  const page = await screen.findByRole("region", { name: "Project shop" });
  const line = () => within(page).getByText(/New values reach the agents/); // the page's read
  await waitFor(() => expect(within(line()).getByRole("link", { name: "shop-backend" })).toBeTruthy());
  server.projects.shop = { ...server.projects.shop, running: ["shop-frontend"] };
  server.projects.acme = { ...server.projects.acme, running: ["acme-crm"] };
  const started = session("acme-crm", { project: "acme" });
  stream().send("change", { kind: "sessions", session: "acme-crm", key: "", op: "insert", item: started }, "11");
  await waitFor(() => expect(rows()[0]).toBe("ACME CRMacme · 1 repository · 1 running"));
  await waitFor(() => expect(within(line()).queryByRole("link", { name: "shop-backend" })).toBeNull());
  expect(within(line()).getByRole("link", { name: "shop-frontend" })).toBeTruthy();
});

test("the page is read anew when the window gets the focus", async () => {
  open("/projects/acme");
  await screen.findByRole("region", { name: "Project acme" });
  const before = server.calls("GET", "/api/projects/acme").length;
  act(() => {
    window.dispatchEvent(new Event("focus"));
  });
  await waitFor(() => expect(server.calls("GET", "/api/projects/acme").length).toBe(before + 1));
});

// On a phone (docs/design/ui.md, Phone layout): the list or a project, in turns.

test("on a phone the list fills the screen, and a project opens in its place", async () => {
  FakeScreen.phone();
  open("/projects");
  fireEvent.click(await within(list()).findByRole("link", { name: /Shop/ }));
  await screen.findByRole("region", { name: "Project shop" });
  expect(screen.queryByRole("navigation", { name: "Projects" })).toBeNull();
  fireEvent.click(screen.getByRole("link", { name: "← All projects" }));
  expect(at).toBe("/projects");
  expect(await within(list()).findByRole("link", { name: /Shop/ })).toBeTruthy();
  expect(screen.queryByText("Select a project")).toBeNull();
});

test("a narrow desktop window shows no Select a project pane beside the list", async () => {
  new FakeScreen("fine", 390, 800);
  open("/projects");
  await within(list()).findByRole("link", { name: /Shop/ });
  expect(screen.queryByText("Select a project")).toBeNull();
});

// New project

const dialog = () => screen.getByRole("dialog", { name: "New project" });
const field = (name: string) => within(dialog()).getByRole("textbox", { name }) as HTMLInputElement;
const create = () => within(dialog()).getByRole("button", { name: "Create project" }) as HTMLButtonElement;

async function newProject() {
  open("/projects");
  fireEvent.click(await screen.findByRole("button", { name: "New project" }));
  return dialog();
}

test("New project's id follows the title, with its folder, and Create makes the project", async () => {
  const shown = await newProject();
  expect(shown.textContent).toContain(
    "⚠ Projects of one LADO are not isolated from each other. For clients that must not mix, run a separate LADO.",
  );
  expect(create().disabled).toBe(true);
  fireEvent.change(field("Title (optional)"), { target: { value: "Shop EU" } });
  await waitFor(() => expect(field("Id").value).toBe("shop-eu"));
  expect(shown.textContent).toContain("Its folder: /ws/projects/shop-eu. The id never changes.");
  await waitFor(() => expect(create().disabled).toBe(false));
  fireEvent.click(create());
  await waitFor(() => expect(at).toBe("/projects/shop-eu"));
  expect(server.calls("POST", "/api/projects")[0].body).toEqual({ id: "shop-eu", title: "Shop EU" });
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(await screen.findByRole("heading", { name: "Shop EU" })).toBeTruthy();
});

test("a title that gives no id says so under Id, and Create stays off", async () => {
  server.suggest = (_title, id) =>
    id === null
      ? { id: null, folder: null, problem: "the name needs a Latin letter or digit for its folder: type one" }
      : { id, folder: `/ws/projects/${id}`, problem: null };
  const shown = await newProject();
  fireEvent.change(field("Title (optional)"), { target: { value: "!!!" } });
  expect(await within(shown).findByText("The title gives no id: type one.")).toBeTruthy();
  expect(field("Id").value).toBe("");
  expect(create().disabled).toBe(true);
  expect(shown.textContent).not.toContain("for its folder");
  fireEvent.change(field("Id"), { target: { value: "bang" } });
  await waitFor(() => expect(create().disabled).toBe(false));
  expect(shown.textContent).not.toContain("The title gives no id");
});

test("an edited id stays when the title changes, and is checked as typed", async () => {
  await newProject();
  fireEvent.change(field("Title (optional)"), { target: { value: "Shop EU" } });
  await waitFor(() => expect(field("Id").value).toBe("shop-eu"));
  fireEvent.change(field("Id"), { target: { value: "eu-shop" } });
  fireEvent.change(field("Title (optional)"), { target: { value: "Shop Europe" } });
  await waitFor(() => expect(server.asked.some((one) => one.path === "/api/project-id?id=eu-shop")).toBe(true));
  await new Promise((resolve) => setTimeout(resolve, 300));
  expect(field("Id").value).toBe("eu-shop");
  expect(server.asked.some((one) => one.path.includes("title=Shop+Europe"))).toBe(false);
});

test("a refused id shows the core's text under Id and disables Create", async () => {
  await newProject();
  fireEvent.change(field("Id"), { target: { value: "shop" } });
  expect(await within(dialog()).findByText("project shop exists")).toBeTruthy();
  expect(create().disabled).toBe(true);
});

test("a refusal of the create itself shows under Id, the dialog kept", async () => {
  server.refuse = () => "/ws/projects/x already exists: LADO makes a project's folder itself";
  await newProject();
  fireEvent.change(field("Id"), { target: { value: "x" } });
  await waitFor(() => expect(create().disabled).toBe(false));
  fireEvent.click(create());
  expect(await within(dialog()).findByText(/already exists: LADO makes/)).toBeTruthy();
  expect(field("Id").value).toBe("x");
  expect(at).toBe("/projects");
});

test("Cancel closes New project and makes nothing", async () => {
  await newProject();
  fireEvent.change(field("Id"), { target: { value: "x" } });
  fireEvent.click(within(dialog()).getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(server.calls("POST", "/api/projects")).toEqual([]);
});

test("the list follows a project made elsewhere on its next open", async () => {
  open("/projects");
  await within(list()).findByRole("link", { name: /Shop/ });
  server.projects.zeta = project("zeta");
  act(() => {
    window.dispatchEvent(new Event("focus"));
  });
  await waitFor(() => expect(rows()).toHaveLength(4));
});

test("an id typed while the title's answer is on its way stays", async () => {
  let release = () => {};
  server.held = new Promise((resolve) => (release = resolve));
  await newProject();
  fireEvent.change(field("Title (optional)"), { target: { value: "Shop EU" } });
  await waitFor(() => expect(server.asked.some((one) => one.path.includes("title=Shop+EU"))).toBe(true));
  fireEvent.change(field("Id"), { target: { value: "mine" } });
  await act(async () => release());
  server.held = null;
  await waitFor(() => expect(server.asked.some((one) => one.path === "/api/project-id?id=mine")).toBe(true));
  await waitFor(() => expect(dialog().textContent).toContain("Its folder: /ws/projects/mine."));
  expect(field("Id").value).toBe("mine");
});

test("Create waits for the id of the title as it is now", async () => {
  server.projects = { acme: project("acme") }; // "shop" and "shop-eu" are free
  await newProject();
  fireEvent.change(field("Title (optional)"), { target: { value: "Shop" } });
  await waitFor(() => expect(create().disabled).toBe(false));
  expect(field("Id").value).toBe("shop");
  fireEvent.change(field("Title (optional)"), { target: { value: "Shop EU" } });
  expect(create().disabled).toBe(true);
  await waitFor(() => expect(field("Id").value).toBe("shop-eu"));
  await waitFor(() => expect(create().disabled).toBe(false));
});

test("a read begun before a change does not bring the page back to before it", async () => {
  open("/projects/shop");
  const page = await screen.findByRole("region", { name: "Project shop" });
  let release = () => {};
  server.stale = { path: "/api/projects/shop", release: new Promise((resolve) => (release = resolve)) };
  act(() => {
    window.dispatchEvent(new Event("focus")); // the click that saves also focuses the window
  });
  await waitFor(() => expect(server.calls("GET", "/api/projects/shop").length).toBeGreaterThan(1));
  const variables = within(page).getByRole("region", { name: "Variables" });
  fireEvent.click(within(variables).getByRole("button", { name: "Edit" }));
  fireEvent.change(within(variables).getByRole("textbox", { name: "Value of BOARD_URL" }), {
    target: { value: "https://new" },
  });
  fireEvent.click(within(variables).getByRole("button", { name: "Save" }));
  await waitFor(() => expect(within(variables).getByText("https://new")).toBeTruthy());
  server.stale = null;
  await act(async () => release());
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  expect(within(variables).getByText("https://new")).toBeTruthy();
});
