import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { externalDefault, LMSTUDIO, model, ModelServer, refusal } from "./modelFakes";
import { ModelSettings, UNDO_MS } from "./ModelSettings";

vi.mock("@xterm/xterm", async () => ({
  Terminal: (await import("./fakes")).FakeXterm,
}));
vi.mock("@xterm/addon-fit", async () => ({
  FitAddon: (await import("./fakes")).FakeFit,
}));
vi.mock("@xterm/addon-web-links", () => ({ WebLinksAddon: class {} }));

let server: ModelServer;

beforeEach(() => {
  server = new ModelServer();
  server.install();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function mount(path = "/settings") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ModelSettings />
    </MemoryRouter>,
  );
}

// Your models, the one table of every CLI's models.
const card = () => screen.findByRole("table", { name: "Your models" });
const names = (group: HTMLElement) =>
  within(group)
    .queryAllByRole("button", { name: /^Rename / })
    .map((b) => b.textContent);
const rowsOf = (group: HTMLElement) => within(group).getAllByRole("row").slice(1); // the head row first

const FOUR = [
  model("Claude Sonnet", "claude", "Claude Code", "sonnet"),
  model("gpt-5-codex", "codex", "Codex CLI", "gpt-5-codex"),
  model("qwen3-8b · LM Studio дома · OpenCode", "opencode", "OpenCode", "qwen3-8b", "LM Studio дома"),
  model("beta", "opencode", "OpenCode", "devstral"),
];

test("Servers, then Your models; no intro, no card of a CLI; opening reads no source", async () => {
  server.entries = {
    models: FOUR,
    servers: [LMSTUDIO, { ...LMSTUDIO, name: "LiteLLM" }],
  };
  mount();
  await card();
  expect(screen.queryByRole("tablist")).toBeNull();
  expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("Model servers");
  const blocks = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
  expect(blocks).toEqual(["Servers 2", "Your models 4"]);
  expect(screen.getByText("Any OpenAI-compatible server: LM Studio, Ollama, vLLM, LiteLLM.")).toBeTruthy();
  const lead = screen.getByText(/^Pick one as a default in/);
  expect(lead.textContent).toBe("Pick one as a default in Agent CLIs.");
  expect(within(lead).getByRole("link", { name: "Agent CLIs" }).getAttribute("href")).toBe("/settings/agent-clis");
  expect(screen.queryByRole("group", { name: "OpenCode" })).toBeNull();
  expect(screen.queryByRole("combobox")).toBeNull();
  const reads = (c: { path: string }) =>
    c.path.includes("/models?") || c.path.includes("/model-choices?") || c.path.endsWith("/probe");
  expect(server.calls.filter(reads)).toEqual([]);
});

test("opening the page asks for a check of the CLIs, and reads their rows while it runs", async () => {
  // A server just started: no check yet, every CLI's row not read.
  server.logins = server.logins.map((row) => ({ ...row, ready: false }));
  server.answers["POST /api/providers/check"] = () => {
    server.logins = server.logins.map((row) => ({ ...row, ready: true }));
    return new Response(JSON.stringify({ providers: server.logins, checking: true, environment: "" }));
  };
  mount();
  await waitFor(() => expect(server.of("POST", "/api/providers/check")).toHaveLength(1));
  // Read again while the check runs, and no more once it ended.
  await waitFor(() => expect(server.of("GET", "/api/providers/logins").length).toBeGreaterThan(0), {
    timeout: 3000,
  });
  const reads = server.of("GET", "/api/providers/logins").length;
  await new Promise((done) => setTimeout(done, 1500));
  expect(server.of("GET", "/api/providers/logins")).toHaveLength(reads);
});

test("Your models: Name, Model, From, Agent CLI and ×, by CLI in LADO's order then by name", async () => {
  const unknown = model("Старая", "gemini", "gemini", "g-1");
  server.entries = { models: [unknown, ...FOUR], servers: [LMSTUDIO] };
  mount();
  const yours = await card();
  expect(within(yours).getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
    "Name",
    "Model",
    "From",
    "Agent CLI",
    "",
  ]);
  expect(rowsOf(yours).map((row) => within(row).getAllByRole("cell").map((c) => c.textContent))).toEqual([
    ["Claude Sonnet", "sonnet", FOUR[0].server, "Claude Code", ""],
    ["gpt-5-codex", "gpt-5-codex", FOUR[1].server, "Codex CLI", ""],
    ["beta", "devstral", FOUR[3].server, "OpenCode", ""],
    ["qwen3-8b · LM Studio дома · OpenCode", "qwen3-8b", "LM Studio дома", "OpenCode", ""],
    ["Старая", "g-1", unknown.server, "gemini", ""], // a CLI LADO does not know: last, as saved
  ]);
  expect(within(yours).getByRole("button", { name: "Remove Старая" })).toBeTruthy();
});

test("a CLI's default reads <CLI> · default in its row", async () => {
  server.entries = { models: FOUR, servers: [LMSTUDIO], defaults: [externalDefault(FOUR[3])] };
  mount();
  const yours = await card();
  const cli = (name: string) =>
    within(within(yours).getByRole("button", { name: `Rename ${name}` }).closest("[role=row]") as HTMLElement)
      .getAllByRole("cell")[3].textContent;
  expect(cli("beta")).toBe("OpenCode · default");
  expect(cli("Claude Sonnet")).toBe("Claude Code");
});

test("with servers and no model: None yet; with nothing saved: no Your models", async () => {
  server.entries = { models: [], servers: [LMSTUDIO] };
  mount();
  expect(await screen.findByText("None yet: open a server and tick the agent CLIs that run a model.")).toBeTruthy();
  expect(screen.queryByRole("table")).toBeNull();
  cleanup();
  server.entries = { models: [], servers: [] };
  mount();
  await screen.findByRole("heading", { name: "Servers" });
  expect(screen.queryByRole("heading", { name: /Your models/ })).toBeNull();
});

test("a click on a name gives a field: Enter renames, the model takes its place by name", async () => {
  server.entries = { models: FOUR, servers: [LMSTUDIO] };
  mount();
  const opencode = await card();
  const name = within(opencode).getByRole("button", {
    name: "Rename qwen3-8b · LM Studio дома · OpenCode",
  });
  expect(name.getAttribute("title")).toBe("Click to rename");
  fireEvent.click(name);
  const field = within(opencode).getByRole("textbox", {
    name: "Name of qwen3-8b · LM Studio дома · OpenCode",
  });
  expect(screen.queryByRole("button", { name: "Save" })).toBeNull(); // no buttons
  fireEvent.change(field, { target: { value: "Alpha" } });
  fireEvent.keyDown(field, { key: "Enter" });
  await waitFor(() => expect(names(opencode)).toEqual(["Claude Sonnet", "gpt-5-codex", "Alpha", "beta"]));
  expect(server.of("PATCH", "/api/models/")[0].body).toEqual({ name: "Alpha" });
});

test("Esc restores the name with no request and gives the focus back to it; leaving the field renames", async () => {
  server.entries = { models: FOUR.slice(0, 1), servers: [] };
  mount();
  const claude = await card();
  fireEvent.click(within(claude).getByRole("button", { name: "Rename Claude Sonnet" }));
  let field = within(claude).getByRole("textbox", {
    name: "Name of Claude Sonnet",
  });
  fireEvent.change(field, { target: { value: "Другая" } });
  fireEvent.keyDown(field, { key: "Escape" });
  const name = within(claude).getByRole("button", {
    name: "Rename Claude Sonnet",
  });
  await waitFor(() => expect(document.activeElement).toBe(name));
  expect(server.of("PATCH", "/api/models/")).toEqual([]);
  fireEvent.click(name);
  field = within(claude).getByRole("textbox", {
    name: "Name of Claude Sonnet",
  });
  fireEvent.change(field, { target: { value: "Сильная" } });
  fireEvent.blur(field);
  expect(await within(claude).findByRole("button", { name: "Rename Сильная" })).toBeTruthy();
});

test("a refused name stays under the field; leaving it then restores the name", async () => {
  server.entries = { models: FOUR.slice(0, 2), servers: [] };
  server.answers["PATCH /api/models/Claude%20Sonnet"] = () =>
    refusal('The name is taken by the model "gpt-5-codex"', "name");
  mount();
  const claude = await card();
  fireEvent.click(within(claude).getByRole("button", { name: "Rename Claude Sonnet" }));
  const field = within(claude).getByRole("textbox", {
    name: "Name of Claude Sonnet",
  });
  fireEvent.change(field, { target: { value: "GPT-5-codex" } });
  fireEvent.keyDown(field, { key: "Enter" });
  const note = await within(claude).findByText('The name is taken by the model "gpt-5-codex"');
  expect(note.className).toContain("field-note bad");
  expect(field.getAttribute("aria-invalid")).toBe("true");
  expect(within(claude).getByRole("textbox")).toBe(field);
  fireEvent.blur(field);
  expect(within(claude).getByRole("button", { name: "Rename Claude Sonnet" })).toBeTruthy();
  expect(server.of("PATCH", "/api/models/")).toHaveLength(1);
});

test("a name refused on leaving the field stays under it too; leaving again restores the name", async () => {
  server.entries = { models: FOUR.slice(0, 2), servers: [] };
  server.answers["PATCH /api/models/Claude%20Sonnet"] = () =>
    refusal('The name is taken by the model "gpt-5-codex"', "name");
  mount();
  const claude = await card();
  fireEvent.click(within(claude).getByRole("button", { name: "Rename Claude Sonnet" }));
  const field = within(claude).getByRole("textbox", {
    name: "Name of Claude Sonnet",
  });
  fireEvent.change(field, { target: { value: "GPT-5-codex" } });
  fireEvent.blur(field);
  expect(await within(claude).findByText('The name is taken by the model "gpt-5-codex"')).toBeTruthy();
  expect(within(claude).getByRole("textbox")).toBe(field);
  fireEvent.blur(field);
  expect(within(claude).getByRole("button", { name: "Rename Claude Sonnet" })).toBeTruthy();
  expect(server.of("PATCH", "/api/models/")).toHaveLength(1);
});

test("× leaves its row as Removed … Undo with the focus on Undo; Undo saves it again and focuses its name", async () => {
  server.entries = {
    models: [model("Сонет для ревью", "opencode", "OpenCode", "qwen3-8b", "LM Studio дома"), FOUR[3]],
    servers: [LMSTUDIO],
  };
  mount();
  const opencode = await card();
  fireEvent.click(within(opencode).getByRole("button", { name: "Remove Сонет для ревью" }));
  const undo = await within(opencode).findByRole("button", { name: "Undo" });
  await waitFor(() => expect(document.activeElement).toBe(undo));
  expect(rowsOf(opencode).map((r) => r.textContent)).toEqual([
    expect.stringContaining("beta"),
    "Removed Сонет для ревью.Undo",
  ]);
  expect(server.of("DELETE", "/api/models/")[0].path).toBe(
    "/api/models/%D0%A1%D0%BE%D0%BD%D0%B5%D1%82%20%D0%B4%D0%BB%D1%8F%20%D1%80%D0%B5%D0%B2%D1%8C%D1%8E",
  );
  expect(screen.getByRole("heading", { name: /^Your models/ }).textContent).toBe("Your models 1");
  fireEvent.click(undo);
  const name = await within(opencode).findByRole("button", {
    name: "Rename Сонет для ревью",
  });
  await waitFor(() => expect(document.activeElement).toBe(name));
  expect(server.of("POST", "/api/models").filter((c) => c.path === "/api/models")[0].body).toEqual({
    name: "Сонет для ревью",
    cli: "opencode",
    model: "qwen3-8b",
    server: "LM Studio дома",
  });
  expect(screen.queryByRole("button", { name: "Undo" })).toBeNull();
});

test("Undo is off while it runs: a second press sends nothing", async () => {
  server.entries = { models: FOUR.slice(0, 1), servers: [] };
  let release: () => void = () => undefined;
  server.answers["POST /api/models"] = (body) =>
    new Promise((resolve) => {
      release = () => resolve(server.answer("POST", "/api/models", body));
    });
  mount();
  fireEvent.click(
    within(await card()).getByRole("button", {
      name: "Remove Claude Sonnet",
    }),
  );
  const undo = (await screen.findByRole("button", {
    name: "Undo",
  })) as HTMLButtonElement;
  fireEvent.click(undo);
  await waitFor(() => expect(undo.getAttribute("aria-disabled")).toBe("true"));
  fireEvent.click(undo);
  release();
  await screen.findByRole("button", { name: "Rename Claude Sonnet" });
  expect(server.of("POST", "/api/models").filter((c) => c.path === "/api/models")).toHaveLength(1);
});

test("after Undo its row stays until the reload brings the model back: nothing moves", async () => {
  server.entries = { models: FOUR.slice(0, 2), servers: [] };
  mount();
  const claude = await card();
  fireEvent.click(within(claude).getByRole("button", { name: "Remove Claude Sonnet" }));
  const undo = await within(claude).findByRole("button", { name: "Undo" });
  let release: () => void = () => undefined;
  server.answers["GET /api/model-settings"] = () =>
    new Promise((resolve) => {
      release = () => resolve(server.answer("GET", "/api/model-settings", undefined));
    });
  fireEvent.click(undo);
  await waitFor(() => expect(server.of("GET", "/api/model-settings").length).toBeGreaterThan(1));
  expect(rowsOf(claude)).toHaveLength(2);
  release();
  expect(await within(claude).findByRole("button", { name: "Rename Claude Sonnet" })).toBeTruthy();
  expect(rowsOf(claude)).toHaveLength(2);
});

test("after UNDO_MS only Undo goes: Removed … stays at its place until the next change", async () => {
  server.entries = { models: FOUR.slice(0, 2), servers: [] };
  mount();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const claude = await card();
  fireEvent.click(within(claude).getByRole("button", { name: "Remove Claude Sonnet" }));
  expect(await screen.findByRole("button", { name: "Undo" })).toBeTruthy();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(UNDO_MS + 10);
  });
  expect(screen.queryByRole("button", { name: "Undo" })).toBeNull();
  expect(rowsOf(claude)[0].textContent).toBe("Removed Claude Sonnet.");
  fireEvent.click(within(claude).getByRole("button", { name: "Remove gpt-5-codex" }));
  await within(claude).findByRole("button", { name: "Undo" });
  expect(screen.queryByText("Removed Claude Sonnet.")).toBeNull(); // the next change took it
});

test("Undo runs out on time while the page renders again under it (the CLIs' rows still read)", async () => {
  server.entries = { models: FOUR.slice(0, 2), servers: [] };
  // The CLIs' last check not done: the page reads their rows every second meanwhile.
  server.logins = server.logins.map((row) => ({ ...row, ready: false }));
  mount();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const claude = await card();
  fireEvent.click(within(claude).getByRole("button", { name: "Remove Claude Sonnet" }));
  expect(await screen.findByRole("button", { name: "Undo" })).toBeTruthy();
  const polls = server.of("GET", "/api/providers/logins").length;
  for (let second = 0; second <= UNDO_MS / 1000; second++) {
    // A second at a time: each read of the rows renders the page before the next.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
  }
  expect(server.of("GET", "/api/providers/logins").length).toBeGreaterThan(polls + 5); // read meanwhile
  expect(screen.queryByRole("button", { name: "Undo" })).toBeNull();
});

test("a refused Undo says why in its row", async () => {
  server.entries = {
    models: [model("Claude Opus", "claude", "Claude Code", "opus")],
    servers: [],
  };
  server.answers["POST /api/models"] = () => refusal('no model server "gone" is saved', "server");
  mount();
  fireEvent.click(
    within(await card()).getByRole("button", {
      name: "Remove Claude Opus",
    }),
  );
  fireEvent.click(await screen.findByRole("button", { name: "Undo" }));
  const note = await screen.findByText('no model server "gone" is saved');
  expect(note.closest("[role=row]")?.textContent).toContain("Removed Claude Opus.");
});
