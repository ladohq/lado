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
  server.entries = {
    models: [model("gone", "opencode", "OpenCode", "gone-model", "LM Studio дома")],
    servers: [LMSTUDIO],
  };
  mount();
  const toggle = await source(/LM Studio дома/);
  fireEvent.click(toggle);
  await waitFor(() => expect(pending.length).toBe(1));
  fireEvent.click(toggle); // closed before its answer
  await act(async () => {
    pending[0](new Response(JSON.stringify(LMSTUDIO_PROBE)));
  });
  // The late list keeps nothing: no warning of a model it lacks.
  expect(screen.queryByText(/not in LM Studio дома's list/)).toBeNull();
  // Two reads at once: the later one's answer counts, whichever comes last.
  fireEvent.click(toggle);
  await waitFor(() => expect(pending.length).toBe(2));
  fireEvent.click(toggle);
  fireEvent.click(toggle); // opened again while the first read runs
  await waitFor(() => expect(pending.length).toBe(3));
  await act(async () => {
    pending[2](new Response(JSON.stringify({ ...LMSTUDIO_PROBE, models: ["newer"] })));
  });
  await act(async () => {
    pending[1](new Response(JSON.stringify({ ...LMSTUDIO_PROBE, models: ["older"] })));
  });
  expect(screen.getByText("newer")).toBeTruthy();
  expect(screen.queryByText("older")).toBeNull();
  fireEvent.click(toggle);
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
  // A gone model can be unticked, not ticked for another CLI: the add would be refused.
  expect((within(rows[0]).getByRole("checkbox", { name: "mistral-7b on OpenCode" }) as HTMLInputElement).disabled).toBe(
    false,
  );
  const other = within(rows[0]).getByRole("checkbox", { name: "mistral-7b on Codex CLI" }) as HTMLInputElement;
  expect(other.disabled).toBe(true);
  expect(other.title).toBe("mistral-7b is not in the server's list: ↻ Refresh reads it again");
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

test("Other model…: Add is off while the check refuses the model", async () => {
  server.answers["POST /api/models/check"] = () =>
    new Response(JSON.stringify({ kind: "refused", text: "gpt-9 is not in Codex CLI's list of models", field: "model" }));
  mount();
  fireEvent.click(await source(/Claude Code/));
  const field = await screen.findByRole("combobox");
  fireEvent.change(field, { target: { value: "gpt-9" } });
  expect(await screen.findByText("gpt-9 is not in Codex CLI's list of models", {}, { timeout: 3000 })).toBeTruthy();
  const add = screen.getByRole("button", { name: "Add" }) as HTMLButtonElement;
  expect(add.disabled).toBe(true);
  fireEvent.change(field, { target: { value: "gpt-9x" } }); // typing again: Add on until checked
  expect(add.disabled).toBe(false);
});

test("Change says the plain-http warning of the kept key before Save; a failed Save drops the old result", async () => {
  server.entries = { models: [], servers: [{ ...LMSTUDIO, has_key: true }] };
  server.probes["LM Studio дома"] = LMSTUDIO_PROBE;
  mount();
  const row = item(await source(/LM Studio дома/));
  fireEvent.click(within(row).getByRole("button", { name: "Change" }));
  fireEvent.change(within(row).getByLabelText("Address"), { target: { value: "http://gw.example.com:4000" } });
  const keyField = within(row).getByLabelText("New key").closest(".field") as HTMLElement;
  expect(
    await within(keyField).findByText("⚠ the key goes to gw.example.com over plain http://, unencrypted", {}, { timeout: 3000 }),
  ).toBeTruthy();
  expect(server.of("POST", "/api/model-servers").filter((c) => c.path === "/api/model-servers")).toEqual([]);
  fireEvent.click(within(row).getByRole("button", { name: "Save" }));
  expect(await within(row).findByText(/✓ Replaced model server/)).toBeTruthy();
  server.answers["POST /api/model-servers"] = () => refusal("http://gw:1299 does not answer (connection refused)", "address");
  fireEvent.click(within(row).getByRole("button", { name: "Change" }));
  fireEvent.click(within(row).getByRole("button", { name: "Save" }));
  expect(await within(row).findByText(/does not answer/)).toBeTruthy();
  expect(within(row).queryByText(/✓ Replaced model server/)).toBeNull();
});

test("a server's result goes once another server is removed or added", async () => {
  server.entries = { models: [], servers: [LMSTUDIO, { ...LMSTUDIO, name: "gateway" }] };
  server.probes["LM Studio дома"] = LMSTUDIO_PROBE;
  server.answers["POST /api/model-servers"] = () =>
    new Response(
      JSON.stringify({ server: LMSTUDIO, probe: LMSTUDIO_PROBE, notes: ['same address as model server "gateway"'], warnings: [] }),
    );
  mount();
  const row = item(await source(/LM Studio дома/));
  fireEvent.click(within(row).getByRole("button", { name: "Change" }));
  fireEvent.click(within(row).getByRole("button", { name: "Save" }));
  expect(await within(row).findByText('same address as model server "gateway"')).toBeTruthy();
  const gateway = item(await source(/gateway/));
  fireEvent.click(within(gateway).getByRole("button", { name: "Remove" }));
  const yes = within(gateway.querySelector(".mm-confirm") as HTMLElement).getByRole("button", { name: "Remove" });
  await waitFor(() => expect((yes as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(yes);
  await waitFor(() => expect(screen.queryByRole("button", { name: /^gateway$/ })).toBeNull());
  await waitFor(() => expect(within(row).queryByText(/same address as model server/)).toBeNull());
  expect(within(row).queryByText(/✓ Replaced model server/)).toBeNull();
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

test("Change of a closed server opens it with its result; a later opening shows no old line", async () => {
  server.entries = { models: [], servers: [LMSTUDIO, { ...LMSTUDIO, name: "gateway" }] };
  server.probes["LM Studio дома"] = LMSTUDIO_PROBE;
  server.answers["POST /api/model-servers"] = () =>
    new Response(
      JSON.stringify({
        server: LMSTUDIO,
        probe: LMSTUDIO_PROBE,
        notes: ['same address as model server "gateway"'],
        warnings: ["the key goes to gw over plain http://, unencrypted; use https:// if the server has it"],
      }),
    );
  mount();
  const toggle = await source(/LM Studio дома/);
  const row = item(toggle);
  fireEvent.click(within(row).getByRole("button", { name: "Change" }));
  fireEvent.click(within(row).getByRole("button", { name: "Save" }));
  expect(await within(row).findByText(/✓ Replaced model server "LM Studio дома"/)).toBeTruthy();
  expect(within(row).getByText('same address as model server "gateway"')).toBeTruthy();
  expect(within(row).getByText(/⚠ the key goes to gw over plain http/)).toBeTruthy();
  expect(toggle.getAttribute("aria-expanded")).toBe("true");
  fireEvent.click(toggle); // closed
  fireEvent.click(toggle); // opened again: read anew, no line of the change
  expect(await within(row).findByRole("checkbox", { name: "qwen3-8b on OpenCode" })).toBeTruthy();
  expect(within(row).queryByText(/Replaced model server/)).toBeNull();
});

test("a server with a key says so; one whose APIs cannot be told says why", async () => {
  server.entries = { models: [], servers: [{ ...LMSTUDIO, has_key: true }, { ...LMSTUDIO, name: "plain" }] };
  server.probes["LM Studio дома"] = {
    ...LMSTUDIO_PROBE,
    clis: [],
    apis_why: "http://localhost:1234 answers 400 to any POST",
  };
  mount();
  const keyed = item(await source(/LM Studio дома/));
  expect(within(keyed).getByText("key: yes")).toBeTruthy();
  expect(within(item(await source(/plain/))).queryByText("key: yes")).toBeNull();
  fireEvent.click(await source(/LM Studio дома/));
  expect(
    await within(keyed).findByText("⚠ APIs: cannot be told: http://localhost:1234 answers 400 to any POST"),
  ).toBeTruthy();
  expect(within(keyed).getByText("No installed CLI can use this server.")).toBeTruthy();
});

test("a server added again takes no late answer of the read before its removal", async () => {
  const pending: ((r: Response) => void)[] = [];
  server.probes["LM Studio дома"] = () => new Promise((resolve) => pending.push(resolve));
  server.entries = { models: [], servers: [LMSTUDIO] };
  server.answers["POST /api/model-servers"] = () => {
    server.entries = { ...server.entries, servers: [LMSTUDIO] };
    return new Response(
      JSON.stringify({ server: LMSTUDIO, probe: { ...LMSTUDIO_PROBE, models: ["newer"] }, notes: [], warnings: [] }),
    );
  };
  mount();
  const row = item(await source(/LM Studio дома/));
  fireEvent.click(await source(/LM Studio дома/)); // a read that will answer late
  await waitFor(() => expect(pending.length).toBe(1));
  fireEvent.click(within(row).getByRole("button", { name: "Remove" }));
  const asks = row.querySelector(".mm-confirm") as HTMLElement;
  const confirm = within(asks).getByRole("button", { name: "Remove" }) as HTMLButtonElement;
  await waitFor(() => expect(confirm.disabled).toBe(false));
  fireEvent.click(confirm);
  await waitFor(() => expect(screen.queryByRole("button", { name: /^LM Studio дома$/ })).toBeNull());
  fireEvent.click(screen.getByRole("button", { name: "+ Add server" }));
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "LM Studio дома" } });
  fireEvent.change(screen.getByLabelText("Address"), { target: { value: "localhost:1234" } });
  fireEvent.click(screen.getByRole("button", { name: "Add" }));
  expect(await screen.findByRole("checkbox", { name: "newer on OpenCode" })).toBeTruthy();
  await act(async () => {
    pending[0](new Response(JSON.stringify({ ...LMSTUDIO_PROBE, models: ["older"] })));
  });
  expect(screen.getByRole("checkbox", { name: "newer on OpenCode" })).toBeTruthy();
  expect(screen.queryByText("older")).toBeNull();
});

test("Remove asks with the models saved now, read when it asks", async () => {
  server.entries = {
    models: [model("a", "opencode", "OpenCode", "qwen3-8b", "LM Studio дома")],
    servers: [LMSTUDIO],
  };
  mount();
  const row = item(await source(/LM Studio дома/));
  // A model added from the CLI while the page is open.
  server.entries = {
    ...server.entries,
    models: [...server.entries.models, model("from-cli", "codex", "Codex CLI", "qwen3-8b", "LM Studio дома")],
  };
  fireEvent.click(within(row).getByRole("button", { name: "Remove" }));
  expect(await within(row).findByText("Remove LM Studio дома and its 2 models: a, from-cli?")).toBeTruthy();
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
  const confirm = within(row).getByRole("button", { name: "Remove server and models" }) as HTMLButtonElement;
  await waitFor(() => expect(confirm.disabled).toBe(false)); // once the models are read again
  fireEvent.click(confirm);
  await waitFor(() => expect(screen.queryByRole("button", { name: /LM Studio дома/ })).toBeNull());
  expect(server.of("DELETE", "/api/model-servers/")[0].path).toBe(
    `/api/model-servers/${encodeURIComponent("LM Studio дома")}?with_models=true&confirmed=a&confirmed=b`,
  );
});

test("Remove refused for a model added after it asked asks again, naming it", async () => {
  server.entries = {
    models: [model("a", "opencode", "OpenCode", "qwen3-8b", "LM Studio дома")],
    servers: [LMSTUDIO],
  };
  mount();
  const row = item(await source(/LM Studio дома/));
  fireEvent.click(within(row).getByRole("button", { name: "Remove" }));
  const confirm = within(row).getByRole("button", { name: "Remove server and models" }) as HTMLButtonElement;
  await waitFor(() => expect(confirm.disabled).toBe(false));
  server.entries = {
    ...server.entries,
    models: [...server.entries.models, model("late one", "kilo", "Kilo CLI", "qwen3-8b", "LM Studio дома")],
  };
  fireEvent.click(confirm);
  expect(await within(row).findByText(/has other models now: a, late one; nothing was removed/)).toBeTruthy();
  expect(await within(row).findByText("Remove LM Studio дома and its 2 models: a, late one?")).toBeTruthy();
  expect(server.entries.models).toHaveLength(2);
  await waitFor(() => expect(confirm.disabled).toBe(false));
  fireEvent.click(confirm);
  await waitFor(() => expect(screen.queryByRole("button", { name: /LM Studio дома/ })).toBeNull());
  expect(server.entries.models).toEqual([]);
});
