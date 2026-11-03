import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { kiloRow, LMSTUDIO, model, ModelServer, refusal } from "./modelFakes";
import { EMPTY, EMPTY_HOW, INTRO, ModelSettings, UNDO_MS } from "./ModelSettings";
import { Settings } from "./Settings";

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

const card = (title: string) => screen.findByRole("group", { name: title });
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

test("the section comes after Agent CLIs and environment, before Usage statistics", async () => {
  vi.stubGlobal("WebSocket", class {});
  render(
    <MemoryRouter>
      <Settings />
    </MemoryRouter>,
  );
  await screen.findByRole("heading", { name: "Models" });
  const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
  const at = headings.indexOf("Models");
  expect(headings[at - 1]).toBe("Agent CLIs and environment");
  expect(headings[at + 1]).toBe("Usage statistics");
});

test("no tabs: the intro, then three blocks with their counts; opening reads no source", async () => {
  server.entries = {
    models: FOUR,
    servers: [LMSTUDIO, { ...LMSTUDIO, name: "LiteLLM" }],
  };
  mount();
  await card("Claude Code");
  expect(screen.queryByRole("tablist")).toBeNull();
  expect(screen.getByText(INTRO)).toBeTruthy();
  const blocks = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
  expect(blocks).toEqual(["Your models 4", "Model servers 2", "Models of your agent CLIs"]);
  expect(server.calls.filter((c) => c.path.includes("/models?") || c.path.endsWith("/probe"))).toEqual([]);
  expect(server.of("POST", "/api/providers/check")).toEqual([]); // no check of its own
});

test("with no model Your models says so and how to add one, with no card", async () => {
  mount();
  expect(await screen.findByText(EMPTY)).toBeTruthy();
  expect(screen.getByText(EMPTY_HOW)).toBeTruthy();
  expect(screen.getByRole("heading", { name: "Your models 0" })).toBeTruthy();
  expect(screen.queryByRole("group")).toBeNull();
});

test("a card only per agent CLI with models, in LADO's order; the others in one line", async () => {
  server.entries = {
    models: [...FOUR, model("Alpha", "opencode", "OpenCode", "a")],
    servers: [LMSTUDIO],
  };
  mount();
  await card("Claude Code");
  const titles = screen.getAllByRole("group").map((g) => g.getAttribute("aria-label"));
  expect(titles).toEqual(["Claude Code", "Codex CLI", "OpenCode"]);
  expect(screen.getByText("Kilo CLI has no models: its agents run on its default model.")).toBeTruthy();
  const opencode = await card("OpenCode");
  expect(names(opencode)).toEqual(["Alpha", "beta", "qwen3-8b · LM Studio дома · OpenCode"]);
  expect(within(opencode).getByText("3", { selector: ".mx-count" })).toBeTruthy();
  const row = within(opencode).getByRole("button", { name: "Rename beta" }).closest("[role=row]") as HTMLElement;
  expect(within(row).getByText("the agent CLI")).toBeTruthy();
  expect(within(opencode).getByText("LM Studio дома").getAttribute("title")).toBe(LMSTUDIO.address);
});

test("two agent CLIs without models are named in one line", async () => {
  server.entries = { models: FOUR.slice(0, 1), servers: [] };
  mount();
  await card("Claude Code");
  expect(
    screen.getByText("Codex CLI, OpenCode, Kilo CLI have no models: their agents run on their default model."),
  ).toBeTruthy();
});

test("an agent CLI not installed: its card says its models cannot run", async () => {
  server.logins = [...server.logins.slice(0, 3), kiloRow(false)];
  server.entries = {
    models: [model("Old Opus", "kilo", "Kilo CLI", "anthropic/claude-opus")],
    servers: [],
  };
  mount();
  const kilo = await card("Kilo CLI");
  expect(await within(kilo).findByText("⚠ not installed: its models cannot run")).toBeTruthy();
});

test("#models scrolls once, when the page opens, never after a change of the entries", async () => {
  const scrolled = vi.fn();
  Element.prototype.scrollIntoView = scrolled;
  server.entries = { models: FOUR.slice(0, 2), servers: [] };
  mount("/settings#models");
  const claude = await card("Claude Code");
  await waitFor(() => expect(scrolled).toHaveBeenCalledTimes(1));
  fireEvent.click(within(claude).getByRole("button", { name: "Remove Claude Sonnet" }));
  fireEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await screen.findByRole("button", { name: "Rename Claude Sonnet" });
  expect(scrolled).toHaveBeenCalledTimes(1);
});

test("a click on a name gives a field: Enter renames, the model takes its place in its card only", async () => {
  server.entries = { models: FOUR, servers: [LMSTUDIO] };
  mount();
  const opencode = await card("OpenCode");
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
  await waitFor(() => expect(names(opencode)).toEqual(["Alpha", "beta"]));
  expect(server.of("PATCH", "/api/models/")[0].body).toEqual({ name: "Alpha" });
  expect(names(await card("Claude Code"))).toEqual(["Claude Sonnet"]);
});

test("Esc restores the name with no request and gives the focus back to it; leaving the field renames", async () => {
  server.entries = { models: FOUR.slice(0, 1), servers: [] };
  mount();
  const claude = await card("Claude Code");
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
    refusal('the name is taken by the model "gpt-5-codex"', "name");
  mount();
  const claude = await card("Claude Code");
  fireEvent.click(within(claude).getByRole("button", { name: "Rename Claude Sonnet" }));
  const field = within(claude).getByRole("textbox", {
    name: "Name of Claude Sonnet",
  });
  fireEvent.change(field, { target: { value: "GPT-5-codex" } });
  fireEvent.keyDown(field, { key: "Enter" });
  const note = await within(claude).findByText('the name is taken by the model "gpt-5-codex"');
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
    refusal('the name is taken by the model "gpt-5-codex"', "name");
  mount();
  const claude = await card("Claude Code");
  fireEvent.click(within(claude).getByRole("button", { name: "Rename Claude Sonnet" }));
  const field = within(claude).getByRole("textbox", {
    name: "Name of Claude Sonnet",
  });
  fireEvent.change(field, { target: { value: "GPT-5-codex" } });
  fireEvent.blur(field);
  expect(await within(claude).findByText('the name is taken by the model "gpt-5-codex"')).toBeTruthy();
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
  const opencode = await card("OpenCode");
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
  expect(screen.getByRole("heading", { name: "Your models 1" })).toBeTruthy();
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
    within(await card("Claude Code")).getByRole("button", {
      name: "Remove Claude Sonnet",
    }),
  );
  const undo = (await screen.findByRole("button", {
    name: "Undo",
  })) as HTMLButtonElement;
  fireEvent.click(undo);
  await waitFor(() => expect(undo.disabled).toBe(true));
  fireEvent.click(undo);
  release();
  await screen.findByRole("button", { name: "Rename Claude Sonnet" });
  expect(server.of("POST", "/api/models").filter((c) => c.path === "/api/models")).toHaveLength(1);
});

test("after Undo its row stays until the reload brings the model back: nothing moves", async () => {
  server.entries = { models: FOUR.slice(0, 2), servers: [] };
  mount();
  const claude = await card("Claude Code");
  fireEvent.click(within(claude).getByRole("button", { name: "Remove Claude Sonnet" }));
  const undo = await within(claude).findByRole("button", { name: "Undo" });
  let release: () => void = () => undefined;
  server.answers["GET /api/model-settings"] = () =>
    new Promise((resolve) => {
      release = () => resolve(server.answer("GET", "/api/model-settings", undefined));
    });
  fireEvent.click(undo);
  await waitFor(() => expect(server.of("GET", "/api/model-settings").length).toBeGreaterThan(1));
  expect(rowsOf(claude)).toHaveLength(1);
  release();
  expect(await within(claude).findByRole("button", { name: "Rename Claude Sonnet" })).toBeTruthy();
  expect(rowsOf(claude)).toHaveLength(1);
});

test("after UNDO_MS only Undo goes: Removed … stays at its place until the next change", async () => {
  server.entries = { models: FOUR.slice(0, 2), servers: [] };
  mount();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const claude = await card("Claude Code");
  fireEvent.click(within(claude).getByRole("button", { name: "Remove Claude Sonnet" }));
  expect(await screen.findByRole("button", { name: "Undo" })).toBeTruthy();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(UNDO_MS + 10);
  });
  expect(screen.queryByRole("button", { name: "Undo" })).toBeNull();
  expect(rowsOf(claude).map((r) => r.textContent)).toEqual(["Removed Claude Sonnet."]);
  const codex = await card("Codex CLI");
  fireEvent.click(within(codex).getByRole("button", { name: "Remove gpt-5-codex" }));
  await within(codex).findByRole("button", { name: "Undo" });
  expect(screen.queryByText("Removed Claude Sonnet.")).toBeNull(); // the next change took it
});

test("a refused Undo says why in its row", async () => {
  server.entries = {
    models: [model("Claude Opus", "claude", "Claude Code", "opus")],
    servers: [],
  };
  server.answers["POST /api/models"] = () => refusal('no model server "gone" is saved', "server");
  mount();
  fireEvent.click(
    within(await card("Claude Code")).getByRole("button", {
      name: "Remove Claude Opus",
    }),
  );
  fireEvent.click(await screen.findByRole("button", { name: "Undo" }));
  const note = await screen.findByText('no model server "gone" is saved');
  expect(note.closest("[role=row]")?.textContent).toContain("Removed Claude Opus.");
});
