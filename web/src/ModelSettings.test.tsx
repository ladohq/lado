import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { LMSTUDIO, LMSTUDIO_PROBE, model, ModelServer, refusal } from "./modelFakes";
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
  vi.unstubAllGlobals();
});

function mount(path = "/settings") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ModelSettings />
    </MemoryRouter>,
  );
}

test("the section comes after Providers and environment, before Usage statistics", async () => {
  vi.stubGlobal("WebSocket", class {});
  render(
    <MemoryRouter>
      <Settings />
    </MemoryRouter>,
  );
  await screen.findByRole("heading", { name: "Models" });
  const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
  const at = headings.indexOf("Models");
  expect(headings[at - 1]).toBe("Providers and environment");
  expect(headings[at + 1]).toBe("Usage statistics");
});

test("with no model it says so, Your models above Sources, and reads no source", async () => {
  mount();
  expect(await screen.findByText(EMPTY)).toBeTruthy();
  const titles = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
  expect(titles).toEqual(["Your models", "Sources"]);
  expect(document.getElementById("models")).toBeTruthy();
  await screen.findByRole("button", { name: /Claude Code/ });
  expect(server.of("GET", "/api/providers/claude/models")).toEqual([]);
  expect(server.of("POST", "/api/model-servers")).toEqual([]);
  expect(server.of("POST", "/api/providers/check")).toEqual([]); // no check of its own
});

test("#models scrolls to the section", async () => {
  const scrolled = vi.fn();
  Element.prototype.scrollIntoView = scrolled;
  mount("/settings#models");
  await screen.findByText(EMPTY);
  await waitFor(() => expect(scrolled).toHaveBeenCalled());
});

test("Your models: sorted as given, the source, a CLI not installed", async () => {
  server.entries = {
    models: [
      model("Claude Sonnet", "claude", "Claude Code", "sonnet"),
      model("Old Opus", "kilo", "Kilo CLI", "anthropic/claude-opus"),
      model("qwen3-8b · LM Studio дома", "opencode", "OpenCode", "qwen3-8b", "LM Studio дома"),
    ],
    servers: [LMSTUDIO],
  };
  mount();
  const table = await screen.findByRole("table");
  const rows = within(table).getAllByRole("row").slice(1);
  expect(rows.map((r) => within(r).getAllByRole("cell")[3].textContent)).toEqual([
    "Claude Code",
    "Kilo CLI⚠ Kilo CLI is not installed",
    "LM Studio дома",
  ]);
});

test("✎ renames in place; a refusal shows under the field; Cancel restores", async () => {
  server.entries = { models: [model("Claude Sonnet", "claude", "Claude Code", "sonnet")], servers: [] };
  server.answers["PATCH /api/models/Claude%20Sonnet"] = () =>
    refusal('the name is taken by the model "Other"', "name");
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Rename Claude Sonnet" }));
  const field = screen.getByRole("textbox", { name: "New name of Claude Sonnet" });
  fireEvent.change(field, { target: { value: "other" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  const note = await screen.findByText('the name is taken by the model "Other"');
  expect(note.className).toBe("field-note bad");
  expect(server.of("PATCH", "/api/models/")[0].body).toEqual({ name: "other" });
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.getByText("Claude Sonnet")).toBeTruthy();
  delete server.answers["PATCH /api/models/Claude%20Sonnet"];
  fireEvent.click(screen.getByRole("button", { name: "Rename Claude Sonnet" }));
  fireEvent.change(screen.getByRole("textbox", { name: "New name of Claude Sonnet" }), {
    target: { value: "Сильная" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Сильная")).toBeTruthy();
});

test("Remove removes the model at once", async () => {
  server.entries = { models: [model("Claude Sonnet", "claude", "Claude Code", "sonnet")], servers: [] };
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Remove" }));
  expect(await screen.findByText(EMPTY)).toBeTruthy();
  expect(server.of("DELETE", "/api/models/")[0].path).toBe("/api/models/Claude%20Sonnet");
});

test("a model removed offers Undo, which saves it again under its name", async () => {
  server.entries = {
    models: [model("Сонет для ревью", "opencode", "OpenCode", "qwen3-8b", "LM Studio дома")],
    servers: [LMSTUDIO],
  };
  mount();
  const table = (await screen.findByText("Сонет для ревью")).closest("table") as HTMLElement;
  fireEvent.click(within(table).getByRole("button", { name: "Remove" }));
  const undo = await screen.findByRole("button", { name: "Undo" });
  expect(screen.getByText('Removed "Сонет для ревью"')).toBeTruthy();
  fireEvent.click(undo);
  expect(await screen.findByText("Сонет для ревью")).toBeTruthy();
  expect(server.of("POST", "/api/models").filter((c) => c.path === "/api/models")[0].body).toEqual({
    name: "Сонет для ревью",
    cli: "opencode",
    model: "qwen3-8b",
    server: "LM Studio дома",
  });
  expect(screen.queryByRole("button", { name: "Undo" })).toBeNull();
});

test("Undo goes after a while, and a refused Undo says why", async () => {
  server.entries = { models: [model("Claude Sonnet", "claude", "Claude Code", "sonnet")], servers: [] };
  mount();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  try {
    fireEvent.click(await screen.findByRole("button", { name: "Remove" }));
    expect(await screen.findByRole("button", { name: "Undo" })).toBeTruthy();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(UNDO_MS + 10);
    });
    expect(screen.queryByRole("button", { name: "Undo" })).toBeNull();
  } finally {
    vi.useRealTimers();
  }
  cleanup();
  server.entries = { models: [model("Claude Opus", "claude", "Claude Code", "opus")], servers: [] };
  server.answers["POST /api/models"] = () => refusal("no model server \"gone\" is saved", "server");
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Remove" }));
  fireEvent.click(await screen.findByRole("button", { name: "Undo" }));
  expect(await screen.findByText('no model server "gone" is saved')).toBeTruthy();
});

async function openAdd() {
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "+ Add server" }));
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "work" } });
  fireEvent.change(screen.getByLabelText("Address"), { target: { value: "https://gw.corp/llm" } });
}

test("+ Add server: checking the server…, then the source open with its saved line", async () => {
  let release: () => void = () => undefined;
  server.answers["POST /api/model-servers"] = (body) =>
    new Promise((resolve) => {
      release = () => resolve(server.answer("POST", "/api/model-servers", body));
    });
  server.probes.work = LMSTUDIO_PROBE;
  await openAdd();
  const key = screen.getByLabelText("Key") as HTMLInputElement;
  fireEvent.change(key, { target: { value: "k-secret" } });
  fireEvent.click(screen.getByRole("button", { name: "Add" }));
  const busy = await screen.findByRole("button", { name: "checking the server…" });
  expect((busy as HTMLButtonElement).disabled).toBe(true);
  expect(key.value).toBe(""); // emptied once sent
  release();
  expect(await screen.findByText(/✓ Saved model server "work"\. For: Kilo CLI, OpenCode/)).toBeTruthy();
  const posts = server.of("POST", "/api/model-servers").filter((c) => c.path === "/api/model-servers");
  expect(posts.map((c) => c.body)).toEqual([
    { name: "work", address: "https://gw.corp/llm", key: "k-secret", replace: false },
  ]);
  expect(JSON.stringify(server.calls.filter((c) => c !== posts[0]))).not.toContain("k-secret");
  expect(await screen.findByText("qwen3-8b")).toBeTruthy(); // open, its list the add's probe
  expect(server.of("POST", "/api/model-servers/work/probe")).toEqual([]);
});

test("a refusal shows under its field, warnings under Key; the form keeps all but the key", async () => {
  server.answers["POST /api/model-servers"] = () =>
    refusal(
      "https://gw.corp/llm asks for a key (401): enter it in Key",
      "key",
      "",
      ["the key goes to gw.corp over plain http://, unencrypted; use https:// if the server has it"],
    );
  await openAdd();
  const key = screen.getByLabelText("Key") as HTMLInputElement;
  fireEvent.change(key, { target: { value: "k-1" } });
  fireEvent.click(screen.getByRole("button", { name: "Add" }));
  const note = await screen.findByText(/asks for a key \(401\)/);
  const keyField = key.closest(".field") as HTMLElement;
  expect(keyField.contains(note)).toBe(true);
  expect(within(keyField).getByText(/over plain http/).className).toBe("field-note warn");
  expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("work");
  expect((screen.getByLabelText("Address") as HTMLInputElement).value).toBe("https://gw.corp/llm");
  expect(key.value).toBe("");
});

test("the plain-http warning shows under Key while a key is typed, before Add", async () => {
  await openAdd();
  fireEvent.change(screen.getByLabelText("Address"), { target: { value: "gw.example.com:4000" } });
  const key = screen.getByLabelText("Key") as HTMLInputElement;
  const keyField = key.closest(".field") as HTMLElement;
  fireEvent.change(key, { target: { value: "k-1" } });
  expect(
    await within(keyField).findByText("⚠ the key goes to gw.example.com over plain http://, unencrypted", {}, { timeout: 3000 }),
  ).toBeTruthy();
  expect(server.calls.filter((c) => c.path === "/api/model-servers")).toEqual([]);
  expect(JSON.stringify(server.calls)).not.toContain("k-1");
  fireEvent.change(key, { target: { value: "" } });
  await waitFor(() => expect(within(keyField).queryByText(/over plain http/)).toBeNull(), { timeout: 3000 });
});

test("a refusal under a field goes once that field is edited", async () => {
  server.answers["POST /api/model-servers"] = () =>
    refusal("https://gw.corp/llm asks for a key (401)", "key");
  await openAdd();
  fireEvent.click(screen.getByRole("button", { name: "Add" }));
  expect(await screen.findByText(/asks for a key \(401\)/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Address"), { target: { value: "https://gw.corp/v2" } });
  expect(screen.getByText(/asks for a key \(401\)/)).toBeTruthy(); // another field: it stays
  fireEvent.change(screen.getByLabelText("Key"), { target: { value: "k-1" } });
  expect(screen.queryByText(/asks for a key \(401\)/)).toBeNull();
  server.answers["POST /api/model-servers"] = () => refusal("https://gw.corp/v2 does not answer", "address");
  fireEvent.click(screen.getByRole("button", { name: "Add" }));
  expect(await screen.findByText(/does not answer/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Address"), { target: { value: "https://gw.corp/v3" } });
  expect(screen.queryByText(/does not answer/)).toBeNull();
});

test("an address that does not answer shows under Address, its hint under it", async () => {
  server.answers["POST /api/model-servers"] = () =>
    refusal("http://localhost:4000 does not answer (connection refused)", "address", "LADO runs in a container…");
  await openAdd();
  fireEvent.click(screen.getByRole("button", { name: "Add" }));
  const note = await screen.findByText(/does not answer/);
  const field = screen.getByLabelText("Address").closest(".field") as HTMLElement;
  expect(field.contains(note)).toBe(true);
  expect(within(field).getByText(/LADO runs in a container/).className).toBe("field-note warn");
});

test("Cancel empties the key; the form opens empty again", async () => {
  await openAdd();
  fireEvent.change(screen.getByLabelText("Key"), { target: { value: "k-1" } });
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  fireEvent.click(screen.getByRole("button", { name: "+ Add server" }));
  expect((screen.getByLabelText("Key") as HTMLInputElement).value).toBe("");
});

test("a refusal of no field shows under the buttons", async () => {
  server.answers["POST /api/model-servers"] = () => refusal("the disk refused it");
  await openAdd();
  fireEvent.click(screen.getByRole("button", { name: "Add" }));
  const note = await screen.findByText("the disk refused it");
  expect(note.closest(".field")).toBeNull();
});
