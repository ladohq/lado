import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { MODEL_DEBOUNCE } from "./Launch";
import { kiloRow, LMSTUDIO, LMSTUDIO_PROBE, model, ModelServer, refusal } from "./modelFakes";
import { ModelSettings } from "./ModelSettings";
import { tickState } from "./ModelSources";

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

function mount() {
  return render(
    <MemoryRouter>
      <ModelSettings />
    </MemoryRouter>,
  );
}

// A source's toggle, by its title alone (not a Rename button that holds it).
const source = (name: RegExp) => screen.findByRole("button", { name: new RegExp(`^${name.source}$`) });
const item = (button: HTMLElement) => button.closest("li") as HTMLElement;

test("tickState: on for a model saved with that CLI, model and server; several named", () => {
  const models = [
    model("Claude Opus", "claude", "Claude Code", "opus"),
    model("Сильная", "claude", "Claude Code", "opus"),
    model("q", "opencode", "OpenCode", "qwen3-8b", "LM Studio дома"),
  ];
  expect(tickState(models, "claude", "opus", null)).toEqual({ on: true, several: ["Claude Opus", "Сильная"] });
  expect(tickState(models, "opencode", "qwen3-8b", "lm studio ДОМА")).toEqual({ on: true, several: [] });
  expect(tickState(models, "opencode", "qwen3-8b", null)).toEqual({ on: false, several: [] });
});

test("the CLIs then the servers, closed; not installed greyed and closed, not logged in marked", async () => {
  server.logins = [...server.logins.slice(0, 3), kiloRow(false)];
  server.logins[2] = { ...server.logins[2], login: { ...server.logins[2].login, state: "no" } };
  server.entries = { models: [], servers: [LMSTUDIO] };
  mount();
  const kilo = await source(/Kilo CLI/);
  expect((kilo as HTMLButtonElement).disabled).toBe(true);
  expect(item(kilo).className).toContain("src-off");
  expect(within(item(kilo)).getByText("not installed")).toBeTruthy();
  expect(within(item(await source(/OpenCode/))).getByText("not logged in")).toBeTruthy();
  const names = screen.getAllByRole("button", { expanded: false }).map((b) => b.textContent);
  expect(names).toEqual(["▸Claude Code", "▸Codex CLI", "▸OpenCode", "▸Kilo CLI", "▸LM Studio дома"]);
  expect(server.calls.filter((c) => c.path.includes("/models?") || c.path.endsWith("/probe"))).toEqual([]);
});

test("opening a CLI reads its list fresh; ticking saves with no name, unticking removes", async () => {
  mount();
  fireEvent.click(await source(/Claude Code/));
  expect(await screen.findByText("reading the models…")).toBeTruthy();
  const box = await screen.findByRole("checkbox", { name: "sonnet on Claude Code" });
  expect(server.of("GET", "/api/providers/claude/models")[0].path).toContain("fresh=true");
  expect(within(box.closest("tr") as HTMLElement).getByText("alias")).toBeTruthy();
  fireEvent.click(box);
  await waitFor(() => expect((box as HTMLInputElement).checked).toBe(true));
  expect(server.of("POST", "/api/models")[0].body).toEqual({ name: null, cli: "claude", model: "sonnet", server: null });
  fireEvent.click(box);
  await waitFor(() => expect((box as HTMLInputElement).checked).toBe(false));
  expect(server.of("DELETE", "/api/models/")[0].path).toBe("/api/models/sonnet%20(default)");
});

test("a refused tick shows in its row, the tick stays off", async () => {
  server.answers["POST /api/models"] = () => refusal("the server went away", "server");
  mount();
  fireEvent.click(await source(/Claude Code/));
  const box = await screen.findByRole("checkbox", { name: "opus on Claude Code" });
  fireEvent.click(box);
  const note = await screen.findByText("the server went away");
  expect((box.closest("tr") as HTMLElement).contains(note)).toBe(true);
  await waitFor(() => expect((box as HTMLInputElement).checked).toBe(false));
});

test("Refresh reads again; the latest answer wins and none fills a closed source", async () => {
  const pending: ((r: Response) => void)[] = [];
  server.probes["LM Studio дома"] = () => new Promise((resolve) => pending.push(resolve));
  server.entries = { models: [], servers: [LMSTUDIO] };
  mount();
  const toggle = await source(/LM Studio дома/);
  fireEvent.click(toggle);
  fireEvent.click(await screen.findByRole("button", { name: "↻ Refresh" }).catch(() => toggle));
  await waitFor(() => expect(pending.length).toBeGreaterThanOrEqual(1));
  fireEvent.click(toggle); // closed
  await act(async () => {
    for (const resolve of pending) resolve(new Response(JSON.stringify(LMSTUDIO_PROBE)));
  });
  expect(screen.queryByText("qwen3-8b")).toBeNull();
  server.probes["LM Studio дома"] = LMSTUDIO_PROBE;
  fireEvent.click(toggle);
  expect(await screen.findByText("qwen3-8b")).toBeTruthy();
  const before = server.of("POST", "/api/model-servers/").length;
  fireEvent.click(screen.getByRole("button", { name: "↻ Refresh" }));
  await waitFor(() => expect(server.of("POST", "/api/model-servers/").length).toBe(before + 1));
});

test("a server's columns are its CLIs that are installed; embeddings greyed; a gone model first", async () => {
  server.probes["LM Studio дома"] = LMSTUDIO_PROBE; // Kilo CLI is not installed here
  server.entries = {
    models: [
      model("mistral-7b · LM Studio дома", "opencode", "OpenCode", "mistral-7b", "LM Studio дома"),
      model("q", "opencode", "OpenCode", "qwen3-8b", "LM Studio дома"),
    ],
    servers: [LMSTUDIO],
  };
  mount();
  fireEvent.click(await source(/LM Studio дома/));
  const box = await screen.findByRole("checkbox", { name: "qwen3-8b on OpenCode" });
  const table = box.closest("table") as HTMLElement;
  const head = within(table).getAllByRole("columnheader").map((h) => h.textContent);
  expect(head).toEqual(["Model", "OpenCode", "Codex CLI"]);
  const rows = within(table).getAllByRole("row").slice(1);
  expect(rows[0].textContent).toContain("mistral-7b⚠ not in the server's list");
  expect((within(rows[0]).getByRole("checkbox", { name: "mistral-7b on OpenCode" }) as HTMLInputElement).checked).toBe(
    true,
  );
  const emb = within(table).getByText("text-embedding-nomic").closest("tr") as HTMLElement;
  expect(emb.className).toBe("src-emb");
  expect(within(emb).getByText("(embeddings)")).toBeTruthy();
  expect(within(emb).getAllByRole("checkbox").every((b) => (b as HTMLInputElement).disabled)).toBe(true);
  // Your models warns of the gone model.
  expect(await screen.findByText("⚠ not in LM Studio дома's list of models")).toBeTruthy();
});

test("several models of one tick: on, disabled, titled with them", async () => {
  server.entries = {
    models: [model("Claude Opus", "claude", "Claude Code", "opus"), model("Сильная", "claude", "Claude Code", "opus")],
    servers: [],
  };
  mount();
  fireEvent.click(await source(/Claude Code/));
  const box = (await screen.findByRole("checkbox", { name: "opus on Claude Code" })) as HTMLInputElement;
  expect([box.checked, box.disabled]).toEqual([true, true]);
  expect(box.title).toBe("Models: Claude Opus, Сильная; remove them in Your models");
});

test("a list longer than ten has a search; the missing models always show", async () => {
  const many = Array.from({ length: 12 }, (_, i) => `m-${i}`);
  server.probes["LM Studio дома"] = { ...LMSTUDIO_PROBE, models: [...many, "qwen3-coder"], embeddings: [] };
  server.entries = {
    models: [model("gone", "opencode", "OpenCode", "gone-model", "LM Studio дома")],
    servers: [LMSTUDIO],
  };
  mount();
  fireEvent.click(await source(/LM Studio дома/));
  const search = await screen.findByRole("searchbox", { name: "Search the models" });
  expect((search as HTMLInputElement).placeholder).toBe("Search 13 models");
  fireEvent.change(search, { target: { value: "QWEN" } });
  const table = screen.getByText("qwen3-coder").closest("table") as HTMLElement;
  expect(within(table).queryByText("m-1")).toBeNull();
  expect(within(table).getByText("gone-model")).toBeTruthy();
});

test("a server that does not answer says why, its hint, and its models stay", async () => {
  server.probes["LM Studio дома"] = () =>
    refusal("http://localhost:1234 does not answer (connection refused)", "address", "LADO runs in a container…");
  server.entries = {
    models: [model("Локальная Gemma", "opencode", "OpenCode", "gemma", "LM Studio дома")],
    servers: [LMSTUDIO],
  };
  mount();
  fireEvent.click(await source(/LM Studio дома/));
  expect(
    await screen.findByText(
      "⚠ http://localhost:1234 does not answer (connection refused). Its models stay: Локальная Gemma.",
    ),
  ).toBeTruthy();
  expect(screen.getByText("⚠ LADO runs in a container…")).toBeTruthy();
});

test("Other model…: the check after the typing settles, then Add saves it", async () => {
  mount();
  fireEvent.click(await source(/Claude Code/));
  const field = await screen.findByRole("combobox");
  vi.useFakeTimers({ shouldAdvanceTime: true });
  fireEvent.change(field, { target: { value: "claude-opus-5-5" } });
  expect(server.of("POST", "/api/models/check")).toEqual([]);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(MODEL_DEBOUNCE + 10);
  });
  vi.useRealTimers();
  expect((await screen.findByText("✓ in the list")).className).toBe("field-note ok");
  expect(server.of("POST", "/api/models/check")[0].body).toEqual({
    name: null,
    cli: "claude",
    model: "claude-opus-5-5",
    server: null,
  });
  fireEvent.click(screen.getByRole("button", { name: "Add" }));
  await waitFor(() => expect(server.calls.filter((c) => c.path === "/api/models").length).toBe(1));
  expect(await screen.findByText("claude-opus-5-5 (default)")).toBeTruthy();
});

test("Change with an empty New key keeps the key: key null, replace", async () => {
  server.entries = { models: [], servers: [LMSTUDIO] };
  mount();
  const row = item(await source(/LM Studio дома/));
  fireEvent.click(within(row).getByRole("button", { name: "Change" }));
  const address = within(row).getByLabelText("Address");
  expect((address as HTMLInputElement).value).toBe("http://localhost:1234");
  fireEvent.change(address, { target: { value: "http://localhost:1235" } });
  fireEvent.click(within(row).getByRole("button", { name: "Save" }));
  await waitFor(() => expect(server.of("POST", "/api/model-servers").length).toBe(1));
  expect(server.of("POST", "/api/model-servers")[0].body).toEqual({
    name: "LM Studio дома",
    address: "http://localhost:1235",
    key: null,
    replace: true,
  });
});

test("Remove of a server with models asks, naming them, then removes it with them", async () => {
  server.entries = {
    models: [
      model("a", "opencode", "OpenCode", "qwen3-8b", "LM Studio дома"),
      model("b", "codex", "Codex CLI", "qwen3-8b", "LM Studio дома"),
    ],
    servers: [LMSTUDIO],
  };
  mount();
  const row = item(await source(/LM Studio дома/));
  fireEvent.click(within(row).getByRole("button", { name: "Remove" }));
  expect(within(row).getByText("Remove LM Studio дома and its 2 models: a, b?")).toBeTruthy();
  fireEvent.click(within(row).getByRole("button", { name: "Cancel" }));
  expect(server.of("DELETE", "/api/model-servers/")).toEqual([]);
  fireEvent.click(within(row).getByRole("button", { name: "Remove" }));
  fireEvent.click(within(row).getByRole("button", { name: "Remove server and models" }));
  await waitFor(() => expect(screen.queryByRole("button", { name: /LM Studio дома/ })).toBeNull());
  expect(server.of("DELETE", "/api/model-servers/")[0].path).toBe(
    `/api/model-servers/${encodeURIComponent("LM Studio дома")}?with_models=true`,
  );
});
