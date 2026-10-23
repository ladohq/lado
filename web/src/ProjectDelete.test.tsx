// The project's page's Delete project block and dialog (openspec change project-delete),
// against a fake server (projectFakes.ts).
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { App } from "./App";
import { FakeEventSource, FakeScreen, FakeSocket, stubDialogs } from "./fakes";
import { FakeProjects } from "./projectFakes";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));

let server: FakeProjects;
let at = "";

function Where() {
  at = useLocation().pathname;
  return null;
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
  vi.unstubAllGlobals();
});

async function open(id = "shop") {
  render(
    <MemoryRouter initialEntries={[`/projects/${id}`]}>
      <App />
      <Where />
    </MemoryRouter>,
  );
  return screen.findByRole("region", { name: `Project ${id}` });
}

const deleteDialog = (title = "Shop") => screen.getByRole("dialog", { name: `Delete project ${title}?` });
const deleteButton = (dialog: HTMLElement) =>
  within(dialog).getByRole("button", { name: "Delete project" }) as HTMLButtonElement;
const deletes = () => server.asked.filter((one) => one.method === "DELETE");

async function deleting(id = "shop", title = "Shop") {
  const page = await open(id);
  fireEvent.click(within(page).getByRole("button", { name: "Delete project…" }));
  const dialog = deleteDialog(title);
  await waitFor(() => expect(within(dialog).queryByText("Loading…")).toBeNull());
  return dialog;
}

test("the page ends with the block Delete project, its sentence and its button", async () => {
  const page = await open();
  const block = within(page).getByRole("region", { name: "Delete project" });
  expect(page.lastElementChild).toBe(block);
  expect(block.textContent).toContain(
    "Deletes its folder with every repository in it, its sessions, variables and secrets. Refused while a " +
      "session of the project runs.",
  );
  expect(within(block).getByRole("button", { name: "Delete project…" })).toBeTruthy();
  expect(page.textContent).not.toContain("not built yet");
});

test("the dialog shows the unpushed work, the sessions and the variables and secrets by name", async () => {
  server.deletions.shop = {
    unpushed: ["backend: uncommitted changes; branch feature/checkout not pushed; 2 stashes"],
    sessions: [
      { name: "shop-backend", open_runs: 1, project: "shop" },
      { name: "backend-old", open_runs: 0, project: null },
    ],
    variables: ["BOARD_URL"],
    secrets: ["GH_TOKEN", "YOUGILE_API_KEY"],
  };
  const dialog = await deleting();
  expect(server.calls("GET", "/api/projects/shop/deletion")).toHaveLength(1);
  expect(dialog.textContent).toContain(
    "Its folder /ws/projects/shop is deleted with everything in it, and so are its sessions, variables and " +
      "secrets. This cannot be undone.",
  );
  const headings = within(dialog)
    .getAllByRole("heading", { level: 4 })
    .map((one) => one.textContent);
  expect(headings).toEqual([
    "Work that is not on the remote",
    "Sessions that are forgotten",
    "Variables and secrets that are deleted",
  ]);
  expect(within(dialog).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
    "backend: uncommitted changes; branch feature/checkout not pushed; 2 stashes",
    "shop-backend (1 open run)",
    "backend-old — no project, started in this folder before projects",
    "BOARD_URL",
    "GH_TOKEN — secret",
    "YOUGILE_API_KEY — secret",
  ]);
  expect(deleteButton(dialog).disabled).toBe(true);
});

test("the id must be typed exactly, then Delete project deletes and opens the list", async () => {
  const dialog = await deleting();
  const remove = deleteButton(dialog);
  const typed = within(dialog).getByRole("textbox", { name: "Type shop to delete it" });
  for (const wrong of ["Shop", "shop ", "sho", " shop"]) {
    fireEvent.change(typed, { target: { value: wrong } });
    expect(remove.disabled).toBe(true);
  }
  fireEvent.change(typed, { target: { value: "shop" } });
  expect(remove.disabled).toBe(false);
  fireEvent.click(remove);
  await waitFor(() => expect(at).toBe("/projects"));
  expect(screen.queryByRole("dialog", { name: "Delete project Shop?" })).toBeNull();
  expect(deletes()).toEqual([{ method: "DELETE", path: "/api/projects/shop", body: undefined }]);
  const list = screen.getByRole("navigation", { name: "Projects" });
  await waitFor(() => expect(within(list).queryByRole("link", { name: /Shop/ })).toBeNull());
  expect(within(list).getByRole("link", { name: /ACME CRM/ })).toBeTruthy();
});

test("a clean project with nothing else still asks the id", async () => {
  server.projects.shop = { ...server.projects.shop, variables: [], secrets: [] };
  const dialog = await deleting();
  for (const text of ["All its work is on the remote.", "No session is forgotten.", "No variables or secrets."]) {
    expect(within(dialog).getByText(text)).toBeTruthy();
  }
  expect(within(dialog).queryByRole("listitem")).toBeNull();
  expect(deleteButton(dialog).disabled).toBe(true);
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Type shop to delete it" }), {
    target: { value: "shop" },
  });
  expect(deleteButton(dialog).disabled).toBe(false);
});

test("a project folder that is a link says only the link goes, and lists no work", async () => {
  server.deletions.shop = { kind: "link", target: "/srv/shop" };
  const dialog = await deleting();
  expect(dialog.textContent).toContain(
    "Its folder /ws/projects/shop is a link to /srv/shop: only the link is deleted, /srv/shop and everything in " +
      "it stay. Its sessions, variables and secrets are deleted. This cannot be undone.",
  );
  expect(within(dialog).queryByText("Work that is not on the remote")).toBeNull();
  expect(within(dialog).queryByText("All its work is on the remote.")).toBeNull();
});

test("a project whose folder is not found says so", async () => {
  server.deletions.shop = { kind: "missing" };
  const dialog = await deleting();
  expect(dialog.textContent).toContain(
    "Its folder /ws/projects/shop is not found. Its sessions, variables and secrets are deleted. This cannot be " +
      "undone.",
  );
  expect(within(dialog).queryByText("All its work is on the remote.")).toBeNull();
});

test("a refused preview shows the core's text and only Close", async () => {
  const text = "project shop has sessions not stopped: shop-frontend; stop them first with lado stop <name>";
  server.refuse = (asked) => (asked.path === "/api/projects/shop/deletion" ? text : null);
  const dialog = await deleting();
  expect((await within(dialog).findByRole("alert")).textContent).toBe(text);
  expect(within(dialog).getAllByRole("button").map((button) => button.textContent)).toEqual(["Close"]);
  fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));
  expect(screen.queryByRole("dialog", { name: "Delete project Shop?" })).toBeNull();
  expect(deletes()).toEqual([]);
});

test("a refused delete shows the text and only Close; the project stays", async () => {
  const text = "project shop has sessions not stopped: shop-frontend; stop them first with lado stop <name>";
  server.refuse = (asked) => (asked.method === "DELETE" ? text : null);
  const dialog = await deleting();
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Type shop to delete it" }), {
    target: { value: "shop" },
  });
  fireEvent.click(deleteButton(dialog));
  expect((await within(dialog).findByRole("alert")).textContent).toBe(text);
  expect(within(dialog).getAllByRole("button").map((button) => button.textContent)).toEqual(["Close"]);
  expect(at).toBe("/projects/shop");
  expect(server.projects.shop).toBeTruthy();
});

test("Cancel closes the dialog and deletes nothing", async () => {
  const dialog = await deleting();
  fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("dialog", { name: "Delete project Shop?" })).toBeNull();
  expect(deletes()).toEqual([]);
});

test("Esc while the delete is on its way keeps the dialog", async () => {
  let release = () => {};
  server.heldDelete = new Promise((resolve) => (release = resolve));
  const dialog = await deleting();
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Type shop to delete it" }), {
    target: { value: "shop" },
  });
  fireEvent.click(deleteButton(dialog));
  await waitFor(() => expect(deletes()).toHaveLength(1));
  fireEvent(dialog, new Event("cancel", { cancelable: true }));
  expect(deleteDialog()).toBeTruthy();
  expect((within(dialog).getByRole("button", { name: "Cancel" }) as HTMLButtonElement).disabled).toBe(true);
  release();
  await waitFor(() => expect(at).toBe("/projects"));
});

test("an untitled project's dialog names it by its id", async () => {
  server.projects.shop = { ...server.projects.shop, title: null };
  const dialog = await deleting("shop", "shop");
  expect(within(dialog).getByRole("heading", { name: "Delete project shop?" })).toBeTruthy();
});
