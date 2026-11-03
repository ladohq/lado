import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { kiloRow, LMSTUDIO, model, ModelServer, refusal } from "./modelFakes";
import { EMPTY, ModelSettings, UNDO_MS } from "./ModelSettings";
import { Settings } from "./Settings";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));
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

test("two tabs, Your models with its count, open first; opening reads no source", async () => {
  server.entries = { models: FOUR, servers: [LMSTUDIO] };
  mount();
  const tabs = await screen.findAllByRole("tab");
  expect(tabs.map((t) => t.textContent)).toEqual(["Your models 4", "Add models"]);
  expect(tabs[0].getAttribute("aria-selected")).toBe("true");
  await card("Claude Code");
  fireEvent.click(tabs[1]);
  await screen.findByRole("button", { name: "LM Studio дома" });
  expect(server.calls.filter((c) => c.path.includes("/models?") || c.path.endsWith("/probe"))).toEqual([]);
  expect(server.of("POST", "/api/providers/check")).toEqual([]); // no check of its own
});

test("with no model it says so, and its link opens Add models", async () => {
  mount();
  const line = await screen.findByText(EMPTY, { exact: false });
  expect(screen.queryByRole("table")).toBeNull();
  fireEvent.click(within(line).getByRole("button", { name: "Add models" }));
  expect(screen.getByRole("tab", { name: "Add models" }).getAttribute("aria-selected")).toBe("true");
  expect(await screen.findByRole("button", { name: "+ Add server" })).toBeTruthy();
});

test("a card per CLI in the order of the sources, its models by name ignoring case", async () => {
  server.entries = { models: [...FOUR, model("Alpha", "opencode", "OpenCode", "a")], servers: [LMSTUDIO] };
  mount();
  await card("Claude Code");
  const titles = screen.getAllByRole("group").map((g) => g.getAttribute("aria-label"));
  expect(titles).toEqual(["Claude Code", "Codex CLI", "OpenCode", "Kilo CLI"]);
  const opencode = await card("OpenCode");
  expect(names(opencode)).toEqual(["Alpha", "beta", "qwen3-8b · LM Studio дома · OpenCode"]);
  expect(within(opencode).getByText("3", { selector: ".tab-count" })).toBeTruthy();
  const row = within(opencode).getByRole("button", { name: "Rename beta" }).closest("tr") as HTMLElement;
  expect(within(row).getByText("the CLI itself")).toBeTruthy();
  const served = within(opencode).getByText("LM Studio дома");
  expect(served.closest("td")?.getAttribute("title")).toBe(LMSTUDIO.address);
});

test("a card without models says so, its link opens that CLI's source", async () => {
  server.entries = { models: FOUR.slice(0, 1), servers: [] };
  mount();
  const codex = await card("Codex CLI");
  expect(within(codex).getByText(/No models: its agents run on Codex CLI's default model\./)).toBeTruthy();
  fireEvent.click(within(codex).getByRole("button", { name: "Add from Codex CLI" }));
  const toggle = await screen.findByRole("button", { name: "Codex CLI" });
  expect(toggle.getAttribute("aria-expanded")).toBe("true");
  expect(await screen.findByRole("checkbox", { name: "gpt-5-codex on Codex CLI" })).toBeTruthy();
  expect(server.of("GET", "/api/providers/codex/models")).toHaveLength(1);
});

test("a CLI not installed: its card and each of its models say so", async () => {
  server.logins = [...server.logins.slice(0, 3), kiloRow(false)];
  server.entries = { models: [model("Old Opus", "kilo", "Kilo CLI", "anthropic/claude-opus")], servers: [] };
  mount();
  const kilo = await card("Kilo CLI");
  await waitFor(() => expect(within(kilo).getAllByText(/Kilo CLI is not installed/)).toHaveLength(2));
});

test("#models scrolls once, when the page opens, never after a change of the entries", async () => {
  const scrolled = vi.fn();
  Element.prototype.scrollIntoView = scrolled;
  server.entries = { models: FOUR.slice(0, 2), servers: [] };
  mount("/settings#models");
  const claude = await card("Claude Code");
  await waitFor(() => expect(scrolled).toHaveBeenCalledTimes(1));
  fireEvent.click(within(claude).getByRole("button", { name: "Remove Claude Sonnet" }));
  await screen.findByRole("button", { name: "Undo" });
  fireEvent.click(screen.getByRole("button", { name: "Undo" }));
  await screen.findByRole("button", { name: "Rename Claude Sonnet" });
  expect(scrolled).toHaveBeenCalledTimes(1);
});

test("a click on a name gives a field: Enter renames, the model takes its place in its card only", async () => {
  server.entries = { models: FOUR, servers: [LMSTUDIO] };
  mount();
  const opencode = await card("OpenCode");
  fireEvent.click(within(opencode).getByRole("button", { name: "Rename qwen3-8b · LM Studio дома · OpenCode" }));
  const field = within(opencode).getByRole("textbox", { name: "Name of qwen3-8b · LM Studio дома · OpenCode" });
  expect(screen.queryByRole("button", { name: "Save" })).toBeNull(); // no buttons
  fireEvent.change(field, { target: { value: "Alpha" } });
  fireEvent.keyDown(field, { key: "Enter" });
  await waitFor(() => expect(names(opencode)).toEqual(["Alpha", "beta"]));
  expect(server.of("PATCH", "/api/models/")[0].body).toEqual({ name: "Alpha" });
  expect(names(await card("Claude Code"))).toEqual(["Claude Sonnet"]);
});

test("Esc restores the name with no request; leaving the field renames", async () => {
  server.entries = { models: FOUR.slice(0, 1), servers: [] };
  mount();
  const claude = await card("Claude Code");
  fireEvent.keyDown(within(claude).getByRole("button", { name: "Rename Claude Sonnet" }), { key: "Enter" });
  let field = within(claude).getByRole("textbox", { name: "Name of Claude Sonnet" });
  fireEvent.change(field, { target: { value: "Другая" } });
  fireEvent.keyDown(field, { key: "Escape" });
  expect(within(claude).getByRole("button", { name: "Rename Claude Sonnet" })).toBeTruthy();
  expect(server.of("PATCH", "/api/models/")).toEqual([]);
  fireEvent.click(within(claude).getByRole("button", { name: "Rename Claude Sonnet" }));
  field = within(claude).getByRole("textbox", { name: "Name of Claude Sonnet" });
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
  const field = within(claude).getByRole("textbox", { name: "Name of Claude Sonnet" });
  fireEvent.change(field, { target: { value: "GPT-5-codex" } });
  fireEvent.keyDown(field, { key: "Enter" });
  const note = await within(claude).findByText('the name is taken by the model "gpt-5-codex"');
  expect(note.className).toContain("field-note bad");
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
  const field = within(claude).getByRole("textbox", { name: "Name of Claude Sonnet" });
  fireEvent.change(field, { target: { value: "GPT-5-codex" } });
  fireEvent.blur(field);
  const note = await within(claude).findByText('the name is taken by the model "gpt-5-codex"');
  expect(note.className).toContain("field-note bad");
  expect(within(claude).getByRole("textbox")).toBe(field);
  fireEvent.blur(field);
  expect(within(claude).getByRole("button", { name: "Rename Claude Sonnet" })).toBeTruthy();
  expect(server.of("PATCH", "/api/models/")).toHaveLength(1);
});

test("× removes at once and leaves its row as Undo, which saves the model again", async () => {
  server.entries = {
    models: [model("Сонет для ревью", "opencode", "OpenCode", "qwen3-8b", "LM Studio дома"), FOUR[3]],
    servers: [LMSTUDIO],
  };
  mount();
  const opencode = await card("OpenCode");
  fireEvent.click(within(opencode).getByRole("button", { name: "Remove Сонет для ревью" }));
  const undo = await within(opencode).findByRole("button", { name: "Undo" });
  const rows = within(opencode).getAllByRole("row").slice(1);
  expect(rows.map((r) => r.textContent)).toEqual([expect.stringContaining("beta"), "Removed Сонет для ревью.Undo"]);
  expect(server.of("DELETE", "/api/models/")[0].path).toBe("/api/models/%D0%A1%D0%BE%D0%BD%D0%B5%D1%82%20%D0%B4%D0%BB%D1%8F%20%D1%80%D0%B5%D0%B2%D1%8C%D1%8E");
  expect(screen.getByRole("tab", { name: "Your models 1" })).toBeTruthy();
  fireEvent.click(undo);
  expect(await within(opencode).findByRole("button", { name: "Rename Сонет для ревью" })).toBeTruthy();
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
  fireEvent.click(within(await card("Claude Code")).getByRole("button", { name: "Remove Claude Sonnet" }));
  const undo = (await screen.findByRole("button", { name: "Undo" })) as HTMLButtonElement;
  fireEvent.click(undo);
  await waitFor(() => expect(undo.disabled).toBe(true));
  fireEvent.click(undo);
  release();
  await screen.findByRole("button", { name: "Rename Claude Sonnet" });
  expect(server.of("POST", "/api/models").filter((c) => c.path === "/api/models")).toHaveLength(1);
});

test("Undo goes after UNDO_MS, and a refused Undo says why", async () => {
  server.entries = { models: FOUR.slice(0, 1), servers: [] };
  mount();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  fireEvent.click(within(await card("Claude Code")).getByRole("button", { name: "Remove Claude Sonnet" }));
  expect(await screen.findByRole("button", { name: "Undo" })).toBeTruthy();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(UNDO_MS + 10);
  });
  expect(screen.queryByRole("button", { name: "Undo" })).toBeNull();
  expect(screen.getByText(EMPTY, { exact: false })).toBeTruthy();
  vi.useRealTimers();
  cleanup();
  server.entries = { models: [model("Claude Opus", "claude", "Claude Code", "opus")], servers: [] };
  server.answers["POST /api/models"] = () => refusal('no model server "gone" is saved', "server");
  mount();
  fireEvent.click(within(await card("Claude Code")).getByRole("button", { name: "Remove Claude Opus" }));
  fireEvent.click(await screen.findByRole("button", { name: "Undo" }));
  expect(await screen.findByText('no model server "gone" is saved')).toBeTruthy();
});
