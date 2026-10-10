// One record alone in a tab of its own (docs/design/ui.md, The artifact's tab): only its
// body as the viewer shows it, no LADO around it; the artifact's full name as the title; a
// refusal said in the page; HTML sent to its content address under the server's sandbox.
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, test, vi } from "vitest";

import * as api from "./api";
import { App } from "./App";
import { ArtifactTab } from "./ArtifactTab";
import { artifact } from "./fakes";

// The Shell is the one listener for a 401 (api.ts): mocked to see that the tab never registers one.
vi.mock("./api", async (original) => ({ ...(await original<typeof api>()), onDenied: vi.fn(() => () => {}) }));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

const RECORD = "/api/sessions/lado/records/r1";

// The API: the record with its artifact, and its content.
function serve(shown: api.ArtifactInfo, content: string, refusal?: { status: number; detail: string }) {
  const fetch = vi.fn(async (path: string) => {
    if (refusal) return new Response(JSON.stringify({ detail: refusal.detail }), { status: refusal.status });
    if (path === RECORD) return new Response(JSON.stringify({ artifact: shown, record: shown.latest }));
    if (path === `${RECORD}/content`) return new Response(content);
    return new Response(JSON.stringify({ detail: `not served: ${path}` }), { status: 404 });
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

function open(path = "/view/lado/r1") {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

// Nothing of LADO around the body: no rail, top bar, session head, artifact head, author or summary.
function bare() {
  expect(document.querySelector(".rail")).toBeNull();
  expect(document.querySelector(".topbar")).toBeNull();
  expect(document.querySelector(".session-head")).toBeNull();
  expect(document.querySelector(".artifact-head")).toBeNull();
  expect(document.querySelector(".artifact-meta")).toBeNull();
  expect(screen.queryByText("architect")).toBeNull();
  expect(screen.queryByText(/the panel is wider/)).toBeNull();
  expect(screen.queryByRole("link", { name: "Download" })).toBeNull();
}

test("Markdown shows rendered, alone, with the artifact's full name as the title", async () => {
  const fetch = serve(artifact({}, { summary: "the panel is wider" }), "# Plan\n\n| a | b |\n| - | - |\n| 1 | 2 |");
  open();
  expect(screen.getByText("Loading…")).toBeTruthy();
  await screen.findByRole("heading", { name: "Plan" });
  expect(document.querySelector(".artifact-tab .artifact-markdown table")).not.toBeNull();
  expect(document.title).toBe("feature/x/design");
  bare();
  expect(fetch.mock.calls.map(([path]) => path)).toEqual([RECORD, `${RECORD}/content`]);
});

test("text shows with its line numbers", async () => {
  serve(artifact({ name: "tool.py", full_name: "feature/x/tool.py" }, { media_type: "text/x-python" }), "a = 1\nb = 2\n");
  open();
  const table = await screen.findByRole("table", { name: "feature/x/tool.py" });
  expect(within(table).getAllByRole("row").map((row) => row.querySelector(".line-number")?.textContent)).toEqual(["1", "2"]);
  expect(screen.getByRole("button", { name: "Wrap lines" })).toBeTruthy();
  bare();
});

test("an image shows as an image", async () => {
  serve(artifact({ name: "shot.png", full_name: "feature/x/shot.png", title: "The screen" }, { media_type: "image/png" }), "");
  open();
  const image = await screen.findByRole("img", { name: "The screen" });
  expect(image.getAttribute("src")).toBe(`${RECORD}/content`);
  expect(document.title).toBe("feature/x/shot.png");
  bare();
});

test("HTML goes to its content address, under the server's sandbox", async () => {
  serve(artifact({ name: "mockup.html", full_name: "feature/x/mockup.html" }, { media_type: "text/html" }), "<h1>x</h1>");
  const replace = vi.fn();
  render(
    <MemoryRouter>
      <ArtifactTab session="lado" record="r1" replace={replace} />
    </MemoryRouter>,
  );
  await vi.waitFor(() => expect(replace).toHaveBeenCalledWith(`${RECORD}/content`));
  expect(replace).toHaveBeenCalledTimes(1);
  expect(document.querySelector("iframe")).toBeNull();
});

test.each([
  [404, "no record r9 in session lado"],
  [401, "log in with the link lado ui printed"],
])("a refusal (%i) shows the server's message, and the Shell's 401 listener is left alone", async (status, detail) => {
  serve(artifact(), "", { status, detail });
  open("/view/lado/r9");
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toBe(detail);
  expect(alert.classList.contains("problem")).toBe(true);
  expect(api.onDenied).not.toHaveBeenCalled();
  bare();
});
