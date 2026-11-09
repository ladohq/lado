import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { ProbeInfo } from "./api";
import { MODEL_DEBOUNCE } from "./Launch";
import {
  CODEX_REFUSES,
  externalDefault,
  LMSTUDIO,
  LMSTUDIO_PROBE,
  LMSTUDIO_REAL,
  model,
  ModelServer,
  refusal,
} from "./modelFakes";
import { ModelSettings } from "./ModelSettings";
import { Found, orderOf, SERVERS_LEAD, tickState } from "./ModelSources";
import { UNDO_MS } from "./removedModels";

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

async function mount() {
  const view = render(
    <MemoryRouter>
      <ModelSettings />
    </MemoryRouter>,
  );
  await screen.findByRole("heading", { name: /^Model servers/ });
  return view;
}

// A source's row toggle, by its name.
const source = (name: string) => screen.findByRole("button", { name });
const item = (button: HTMLElement) => button.closest("li") as HTMLElement;
const json = (value: unknown) => new Response(JSON.stringify(value));
const ticks = (where: HTMLElement) =>
  within(where)
    .getAllByRole("checkbox")
    .map((b) => b.getAttribute("aria-label"));
const settle = async () => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(MODEL_DEBOUNCE + 10);
  });
};
const yours = () => screen.findByRole("table", { name: "Your models" });

// LM Studio дома open, the model `name` open under its row: its ticks show.
async function openModel(name: string, probe: ProbeInfo = LMSTUDIO_PROBE) {
  server.probes[LMSTUDIO.name] = probe;
  fireEvent.click(await source(LMSTUDIO.name));
  fireEvent.click(await screen.findByRole("button", { name }));
}
const tickOf = async (name: string) => (await screen.findByRole("checkbox", { name })) as HTMLInputElement;

test("tickState: on for a model saved with that CLI, model and server; several named", () => {
  const models = [
    model("Быстрая", "opencode", "OpenCode", "qwen3-8b", "work"),
    model("Сильная", "opencode", "OpenCode", "qwen3-8b", "work"),
    model("q", "opencode", "OpenCode", "qwen3-8b", "LM Studio дома"),
  ];
  expect(tickState(models, "opencode", "qwen3-8b", "work")).toEqual({
    on: true,
    several: ["Быстрая", "Сильная"],
  });
  expect(tickState(models, "opencode", "qwen3-8b", "lm studio ДОМА")).toEqual({
    on: true,
    several: [],
  });
  expect(tickState(models, "opencode", "qwen3-8b", "elsewhere")).toEqual({
    on: false,
    several: [],
  });
});

test("orderOf: the configured models gone from the list, then those listed, then the rest", () => {
  const own = [model("g", "opencode", "OpenCode", "gone"), model("b", "opencode", "OpenCode", "b")];
  expect(orderOf(["a", "b", "c"], own)).toEqual(["gone", "b", "a", "c"]);
});

test("the servers by name, all closed, each saying its models and address", async () => {
  server.entries = {
    models: [
      model("q", "opencode", "OpenCode", "qwen3-8b", "LM Studio дома"),
      model("r", "codex", "Codex CLI", "qwen3-8b", "LM Studio дома"),
    ],
    servers: [{ ...LMSTUDIO, name: "zeta", address: "http://zeta:1", has_key: true }, LMSTUDIO],
  };
  await mount();
  expect(screen.getByText(SERVERS_LEAD)).toBeTruthy();
  const rows = screen.getAllByRole("button", { expanded: false }).map((b) => b.getAttribute("aria-label"));
  expect(rows).toEqual(["LM Studio дома", "zeta"]);
  const lm = item(await source("LM Studio дома"));
  expect(lm.querySelector(".mx-l2")?.textContent).toBe("2 models added · http://localhost:1234");
  expect(within(lm).getByRole("tooltip").textContent).toBe(LMSTUDIO.address);
  expect(within(lm).getAllByText("LM Studio", { selector: ".badge" })).toHaveLength(1);
  const zeta = item(await source("zeta"));
  expect(zeta.querySelector(".mx-l2")?.textContent).toBe("no models added · http://zeta:1");
  expect(within(zeta).getByText("key", { selector: ".badge" })).toBeTruthy();
  expect(within(lm).getByRole("button", { name: "Change LM Studio дома" }).getAttribute("title")).toBe("Change");
  expect(within(lm).getByRole("button", { name: "Remove LM Studio дома" }).getAttribute("title")).toBe("Remove");
  expect(screen.getByRole("button", { name: "Add server" })).toBeTruthy();
  expect(server.calls.filter((c) => c.path.includes("/models?") || c.path.endsWith("/probe"))).toEqual([]);
});

test("a click on the row's name opens the source; ↻ is above its list and reads it again", async () => {
  server.entries = { models: [], servers: [LMSTUDIO] };
  server.probes[LMSTUDIO.name] = LMSTUDIO_PROBE;
  await mount();
  const lm = await source(LMSTUDIO.name);
  fireEvent.click(within(lm).getByText(LMSTUDIO.name));
  expect(lm.getAttribute("aria-expanded")).toBe("true");
  const row = await within(item(lm)).findByRole("button", { name: "qwen3-8b" });
  const refresh = within(item(lm)).getByRole("button", { name: "Read the models again" });
  expect(refresh.compareDocumentPosition(row) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  const probes = () => server.calls.filter((c) => c.path.endsWith("/probe"));
  expect(probes()).toHaveLength(1);
  fireEvent.click(refresh);
  await waitFor(() => expect(probes()).toHaveLength(2));
  fireEvent.click(lm);
  expect(lm.getAttribute("aria-expanded")).toBe("false");
});

test("a tick saves the model with no name; unticking removes it, its line and Undo under the tick", async () => {
  server.entries = { models: [], servers: [LMSTUDIO] };
  await mount();
  await openModel("qwen3-8b");
  const box = await tickOf("qwen3-8b on OpenCode");
  fireEvent.click(box);
  await waitFor(() => expect(box.checked).toBe(true));
  expect(server.of("POST", "/api/models").filter((c) => c.path === "/api/models")[0].body).toEqual({
    name: null,
    cli: "opencode",
    model: "qwen3-8b",
    server: LMSTUDIO.name,
  });
  const name = "qwen3-8b";
  expect(within(box.closest("label") as HTMLElement).getByText(`as ${name}`)).toBeTruthy();
  expect(box.title).toBe(`Unticking removes ${name}.`);
  fireEvent.click(box);
  await waitFor(() => expect(box.checked).toBe(false));
  expect(server.of("DELETE", "/api/models/")).toHaveLength(1);
  const line = (await screen.findByRole("button", { name: "Undo" })).closest(".mx-sub-undo");
  expect(line?.textContent).toBe(`Removed ${name}.Undo`); // no CLI's sentence: it was no default
  expect(box.closest("label")?.nextElementSibling).toBe(line);
  expect(screen.getAllByRole("button", { name: "Undo" })).toHaveLength(1); // none in Your models
});

// Сильная, OpenCode's qwen3-8b on LM Studio дома, unticked in its open list.
async function untickStrong() {
  server.entries = {
    models: [model("Сильная", "opencode", "OpenCode", "qwen3-8b")],
    servers: [LMSTUDIO],
  };
  await mount();
  await openModel("qwen3-8b");
  const box = await tickOf("qwen3-8b on OpenCode");
  box.focus();
  fireEvent.click(box);
  await waitFor(() => expect(box.checked).toBe(false));
  const list = screen.getByRole("group", { name: "Agent CLIs for qwen3-8b" });
  return { box, list, undo: await within(list).findByRole("button", { name: "Undo" }) };
}

test("Undo of an untick saves the model again under its name, the focus back on the tick", async () => {
  const { box, list, undo } = await untickStrong();
  expect(document.activeElement).toBe(box);
  fireEvent.click(undo);
  await waitFor(() => expect(box.checked).toBe(true));
  expect(server.of("POST", "/api/models").filter((c) => c.path === "/api/models")[0].body).toEqual({
    name: "Сильная",
    cli: "opencode",
    model: "qwen3-8b",
    server: LMSTUDIO.name,
  });
  await waitFor(() => expect(list.querySelector(".mx-sub-undo")).toBeNull());
  expect(server.of("PUT", "/api/model-defaults/opencode")).toEqual([]); // it was no default
  await waitFor(() => expect(document.activeElement).toBe(box));
});

test("after UNDO_MS only the untick's Undo goes; its line stays until the next change", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const { list } = await untickStrong();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(UNDO_MS + 10);
  });
  expect(within(list).queryByRole("button", { name: "Undo" })).toBeNull();
  expect(list.querySelector(".mx-sub-undo")?.textContent).toBe("Removed Сильная.");
  fireEvent.click(await tickOf("qwen3-8b on Codex CLI")); // the next change
  await waitFor(() => expect(list.querySelector(".mx-sub-undo")).toBeNull());
});

test("ticking again takes the untick's line away and sets no default", async () => {
  const { box, list } = await untickStrong();
  fireEvent.click(box);
  await waitFor(() => expect(box.checked).toBe(true));
  expect(list.querySelector(".mx-sub-undo")).toBeNull();
  expect(server.of("PUT", "/api/model-defaults/opencode")).toEqual([]);
});

test("closing the list drops the untick's line", async () => {
  const { list } = await untickStrong();
  expect(list.querySelector(".mx-sub-undo")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "qwen3-8b" }));
  await waitFor(() => expect(screen.queryByRole("group", { name: "Agent CLIs for qwen3-8b" })).toBeNull());
  fireEvent.click(screen.getByRole("button", { name: "qwen3-8b" }));
  const again = await screen.findByRole("group", { name: "Agent CLIs for qwen3-8b" });
  expect(again.querySelector(".mx-sub-undo")).toBeNull();
});

test("a renamed model unticked by mistake: its row says would be <name>, a tick saves it under that name", async () => {
  server.entries = {
    models: [model("Сильная", "opencode", "OpenCode", "qwen3-8b")],
    servers: [LMSTUDIO],
  };
  await mount();
  await openModel("qwen3-8b");
  const box = await tickOf("qwen3-8b on OpenCode");
  expect(box.title).toBe("Unticking removes Сильная.");
  fireEvent.click(box);
  await waitFor(() => expect(box.checked).toBe(false));
  const label = box.closest("label") as HTMLElement;
  expect(within(label).getByText("would be Сильная")).toBeTruthy();
  fireEvent.click(box);
  await waitFor(() => expect(box.checked).toBe(true));
  expect(server.of("POST", "/api/models").filter((c) => c.path === "/api/models")[0].body).toEqual({
    name: "Сильная",
    cli: "opencode",
    model: "qwen3-8b",
    server: LMSTUDIO.name,
  });
  expect(within(label).getByText("as Сильная")).toBeTruthy();
});

test("a kept name taken meanwhile: the tick saves the model under its default name", async () => {
  server.entries = {
    models: [model("Сильная", "opencode", "OpenCode", "qwen3-8b")],
    servers: [LMSTUDIO],
  };
  await mount();
  await openModel("qwen3-8b");
  const box = await tickOf("qwen3-8b on OpenCode");
  fireEvent.click(box);
  await waitFor(() => expect(box.checked).toBe(false));
  server.entries = {
    ...server.entries,
    models: [model("сильная", "codex", "Codex CLI", "gpt-5-codex")],
  };
  fireEvent.click(box);
  await waitFor(() => expect(box.checked).toBe(true));
  const posts = server.of("POST", "/api/models").filter((c) => c.path === "/api/models");
  expect(posts.map((c) => (c.body as { name: string | null }).name)).toEqual(["Сильная", null]);
});

test("ticks change no order: the configured models first as read", async () => {
  server.entries = {
    models: [model("Вторая", "opencode", "OpenCode", "second")],
    servers: [LMSTUDIO],
  };
  await mount();
  await openModel("first", { ...LMSTUDIO_PROBE, models: ["first", "second"], embeddings: [] });
  const rows = () =>
    within(document.querySelector(".mx-list") as HTMLElement)
      .getAllByRole("button")
      .map((b) => b.getAttribute("aria-label"));
  expect(rows()).toEqual(["second", "first"]);
  fireEvent.click(await tickOf("first on OpenCode"));
  await waitFor(() => expect(server.entries.models).toHaveLength(2));
  expect(rows()).toEqual(["second", "first"]);
});

test("a refused tick shows in its row, the tick stays off", async () => {
  server.entries = { models: [], servers: [LMSTUDIO] };
  server.answers["POST /api/models"] = () => refusal("the server went away", "server");
  await mount();
  await openModel("qwen3-8b");
  const box = await tickOf("qwen3-8b on OpenCode");
  fireEvent.click(box);
  expect(await screen.findByText("the server went away")).toBeTruthy();
  await waitFor(() => expect(box.checked).toBe(false));
});

test("the latest read wins and none fills a closed source", async () => {
  const pending: ((r: Response) => void)[] = [];
  server.probes["LM Studio дома"] = () => new Promise((resolve) => pending.push(resolve));
  server.entries = { models: [], servers: [LMSTUDIO] };
  await mount();
  const toggle = await source("LM Studio дома");
  fireEvent.click(toggle);
  await waitFor(() => expect(pending.length).toBe(1));
  fireEvent.click(toggle); // closed before its answer
  await act(async () => pending[0](json({ ...LMSTUDIO_PROBE, models: ["late"] })));
  expect(screen.queryByText("late")).toBeNull();
  fireEvent.click(toggle);
  await waitFor(() => expect(pending.length).toBe(2));
  fireEvent.click(toggle);
  fireEvent.click(toggle);
  await waitFor(() => expect(pending.length).toBe(3));
  await act(async () => pending[2](json({ ...LMSTUDIO_PROBE, models: ["newer"] })));
  await act(async () => pending[1](json({ ...LMSTUDIO_PROBE, models: ["older"] })));
  expect(screen.getByRole("button", { name: "newer" })).toBeTruthy();
  expect(screen.queryByText("older")).toBeNull();
});

test("a server's model opens its CLIs under its row, each it can tick saying the name a tick would save; Esc closes it", async () => {
  server.probes["LM Studio дома"] = LMSTUDIO_PROBE; // Kilo CLI is not installed here
  server.entries = { models: [], servers: [LMSTUDIO] };
  await mount();
  fireEvent.click(await source("LM Studio дома"));
  const row = await screen.findByRole("button", { name: "qwen3-8b" });
  expect(row.getAttribute("aria-expanded")).toBe("false");
  expect(screen.queryByRole("checkbox")).toBeNull();
  fireEvent.click(row);
  const pop = screen.getByRole("group", { name: "Agent CLIs for qwen3-8b" });
  expect(within(pop).getByText("qwen3-8b", { selector: "b" }).parentElement?.textContent).toBe(
    "Agent CLIs that run qwen3-8b:",
  );
  expect(ticks(pop)).toEqual([
    "qwen3-8b on Claude Code",
    "qwen3-8b on Codex CLI",
    "qwen3-8b on OpenCode",
    "qwen3-8b on Kilo CLI",
  ]);
  // Each CLI's would-be name is the model's id: no model holds it yet.
  await waitFor(() => expect(within(pop).getAllByText("would be qwen3-8b").length).toBe(2));
  expect(server.of("POST", "/api/models/check").map((c) => c.body)).toEqual([
    { name: null, cli: "codex", model: "qwen3-8b", server: "LM Studio дома" },
    {
      name: null,
      cli: "opencode",
      model: "qwen3-8b",
      server: "LM Studio дома",
    },
  ]);
  fireEvent.click(within(pop).getByRole("checkbox", { name: "qwen3-8b on OpenCode" }));
  await waitFor(() => expect(row.textContent).toContain("in OpenCode"));
  expect(within(pop).getByText("as qwen3-8b")).toBeTruthy();
  // The id is taken now: the other CLI's would-be name says its CLI.
  expect(await within(pop).findByText("would be qwen3-8b · Codex CLI")).toBeTruthy();
  fireEvent.click(within(pop).getByRole("checkbox", { name: "qwen3-8b on Codex CLI" }));
  await waitFor(() => expect(row.textContent).toContain("in Codex CLI, OpenCode"));
  expect(
    server
      .of("POST", "/api/models")
      .filter((c) => c.path === "/api/models")
      .map((c) => c.body),
  ).toEqual([
    {
      name: null,
      cli: "opencode",
      model: "qwen3-8b",
      server: "LM Studio дома",
    },
    { name: null, cli: "codex", model: "qwen3-8b", server: "LM Studio дома" },
  ]);
  fireEvent.keyDown(pop, { key: "Escape" });
  expect(screen.queryByRole("group", { name: "Agent CLIs for qwen3-8b" })).toBeNull();
  fireEvent.keyDown(row, { key: "Enter" });
  expect(screen.getByRole("group", { name: "Agent CLIs for qwen3-8b" })).toBeTruthy();
});

test("after a tick the other CLIs keep their would-be names while the core is asked again: nothing moves", async () => {
  server.probes["LM Studio дома"] = LMSTUDIO_PROBE;
  server.entries = { models: [], servers: [LMSTUDIO] };
  await mount();
  fireEvent.click(await source("LM Studio дома"));
  fireEvent.click(await screen.findByRole("button", { name: "qwen3-8b" }));
  const pop = screen.getByRole("group", { name: "Agent CLIs for qwen3-8b" });
  await waitFor(() => expect(within(pop).getAllByText("would be qwen3-8b").length).toBe(2));
  server.answers["POST /api/models/check"] = () => new Promise(() => undefined); // asked again: no answer yet
  fireEvent.click(within(pop).getByRole("checkbox", { name: "qwen3-8b on OpenCode" }));
  await waitFor(() => expect(within(pop).getByText("as qwen3-8b")).toBeTruthy());
  await waitFor(() => expect(server.of("POST", "/api/models/check").length).toBeGreaterThan(2));
  expect(within(pop).getByText("would be qwen3-8b")).toBeTruthy();
});

test("the name a tick would save of a list closed meanwhile is dropped", async () => {
  const pending: ((r: Response) => void)[] = [];
  server.probes["LM Studio дома"] = LMSTUDIO_PROBE;
  server.entries = { models: [], servers: [LMSTUDIO] };
  server.answers["POST /api/models/check"] = () => new Promise((resolve) => pending.push(resolve));
  await mount();
  fireEvent.click(await source("LM Studio дома"));
  const row = await screen.findByRole("button", { name: "qwen3-8b" });
  fireEvent.click(row);
  await waitFor(() => expect(pending.length).toBe(2));
  fireEvent.click(row); // closed
  fireEvent.click(row); // and opened again: two new checks
  await waitFor(() => expect(pending.length).toBe(4));
  await act(async () => pending[0](json({ kind: "ok", text: "", field: "", name: "old name" })));
  const pop = screen.getByRole("group", { name: "Agent CLIs for qwen3-8b" });
  expect(within(pop).queryByText("would be old name")).toBeNull();
  await act(async () => pending[2](json({ kind: "ok", text: "", field: "", name: "new name" })));
  expect(within(pop).getByText("would be new name")).toBeTruthy();
});

// Each CLI under an open model: its title, whether it can be ticked, and what its row says.
const clisOf = (pop: HTMLElement) =>
  [...pop.querySelectorAll("label")].map((label) => [
    label.querySelector("span")?.textContent,
    (label.querySelector("input") as HTMLInputElement).disabled ? "off" : "tick",
    label.querySelector(".mx-as")?.textContent ?? "",
  ]);

test("every agent CLI under a server's model in LADO's order; one that cannot use the server says why", async () => {
  server.entries = { models: [], servers: [LMSTUDIO] };
  await mount();
  await openModel("qwen3-8b", LMSTUDIO_REAL); // Kilo CLI is not installed here
  const pop = screen.getByRole("group", { name: "Agent CLIs for qwen3-8b" });
  await within(pop).findByText("would be qwen3-8b");
  expect(clisOf(pop)).toEqual([
    ["Claude Code", "off", "cannot use this server: it has no Anthropic Messages API"],
    ["Codex CLI", "off", `cannot use this server: ${CODEX_REFUSES}`],
    ["OpenCode", "tick", "would be qwen3-8b"],
    ["Kilo CLI", "off", "not installed"],
  ]);
  const codex = await tickOf("qwen3-8b on Codex CLI");
  expect(codex.checked).toBe(false);
  expect(codex.getAttribute("aria-description")).toBe(`cannot use this server: ${CODEX_REFUSES}`);
  // The name a tick would save is asked only of the CLI that can be ticked.
  expect(server.of("POST", "/api/models/check").map((c) => (c.body as { cli: string }).cli)).toEqual(["opencode"]);
  fireEvent.click(codex);
  expect(server.of("POST", "/api/models").filter((c) => c.path === "/api/models")).toEqual([]);
});

test("a CLI that cannot use the server with a model of it saved: its tick on and disabled, its name and why", async () => {
  server.entries = {
    models: [
      model("Codex qwen", "codex", "Codex CLI", "qwen3-8b"),
      model("Kilo qwen", "kilo", "Kilo CLI", "qwen3-8b"), // Kilo CLI is not installed here
    ],
    servers: [LMSTUDIO],
  };
  await mount();
  await openModel("qwen3-8b", LMSTUDIO_REAL);
  const pop = screen.getByRole("group", { name: "Agent CLIs for qwen3-8b" });
  const said = (title: string) =>
    [...pop.querySelectorAll("label")]
      .find((label) => label.querySelector("span")?.textContent === title)
      ?.querySelectorAll(".mx-as");
  for (const [title, why] of [
    ["Codex CLI", `cannot use this server: ${CODEX_REFUSES}`],
    ["Kilo CLI", "not installed"],
  ]) {
    const box = await tickOf(`qwen3-8b on ${title}`);
    expect([box.checked, box.disabled]).toEqual([true, true]);
    const name = title === "Codex CLI" ? "Codex qwen" : "Kilo qwen";
    expect([...(said(title) ?? [])].map((s) => s.textContent)).toEqual([`as ${name}`, why]);
  }
  const claude = await tickOf("qwen3-8b on Claude Code");
  expect([claude.checked, claude.disabled]).toEqual([false, true]);
});

test("an API that did not answer in time says so under its CLI", async () => {
  server.entries = { models: [], servers: [LMSTUDIO] };
  await mount();
  const late = "its Anthropic Messages API did not answer in time";
  await openModel("qwen3-8b", { ...LMSTUDIO_PROBE, cannot: [{ name: "claude", title: "Claude Code", why: late }] });
  const pop = screen.getByRole("group", { name: "Agent CLIs for qwen3-8b" });
  expect(clisOf(pop)[0]).toEqual(["Claude Code", "off", `cannot use this server: ${late}`]);
});

test("a server no installed CLI can use says so; its models open to the CLIs, none tickable, each saying why", async () => {
  server.entries = { models: [], servers: [LMSTUDIO] };
  await mount();
  const why = (title: string, api: string) => ({ name: title.split(" ")[0].toLowerCase(), title, why: `it has no ${api}` });
  await openModel("qwen3-8b", {
    ...LMSTUDIO_PROBE,
    clis: [{ name: "kilo", title: "Kilo CLI", api: "chat completions" }],
    cannot: [why("Claude Code", "Anthropic Messages API"), why("Codex CLI", "Responses API"), why("OpenCode", "chat")],
  });
  expect(screen.getByText("No installed CLI can use this server.")).toBeTruthy();
  const pop = screen.getByRole("group", { name: "Agent CLIs for qwen3-8b" });
  expect(clisOf(pop)).toEqual([
    ["Claude Code", "off", "cannot use this server: it has no Anthropic Messages API"],
    ["Codex CLI", "off", "cannot use this server: it has no Responses API"],
    ["OpenCode", "off", "cannot use this server: it has no chat"],
    ["Kilo CLI", "off", "not installed"],
  ]);
  expect(screen.queryByText("Open a model to tick the agent CLIs that run it.")).toBeNull();
  expect(server.of("POST", "/api/models/check")).toEqual([]);
});

test("embeddings are hidden and counted; a model gone from the list first, ticked, marked", async () => {
  server.probes["LM Studio дома"] = LMSTUDIO_PROBE;
  server.entries = {
    models: [model("mistral-7b · LM Studio дома", "opencode", "OpenCode", "mistral-7b", "LM Studio дома")],
    servers: [LMSTUDIO],
  };
  await mount();
  fireEvent.click(await source("LM Studio дома"));
  const gone = await screen.findByRole("button", { name: "mistral-7b" });
  const list = gone.closest(".mx-list") as HTMLElement;
  expect(
    within(list)
      .getAllByRole("button")
      .map((b) => b.getAttribute("aria-label")),
  ).toEqual(["mistral-7b", "qwen3-8b"]);
  expect(list.className).toContain("mx-short"); // shown whole on a phone
  expect(within(gone).getByText("no longer listed")).toBeTruthy();
  expect(screen.queryByText("text-embedding-nomic")).toBeNull();
  expect(screen.getByText("1 embeddings model hidden: agents cannot run on it.")).toBeTruthy();
  expect(screen.getByText("2 models")).toBeTruthy();
  const mark = within(await yours()).getByText("⚠ not in list");
  expect(mark.getAttribute("title")).toBe(
    "LM Studio дома no longer lists mistral-7b: agents on it stop at their first turn.",
  );
  fireEvent.click(gone);
  const pop = screen.getByRole("group", { name: "Agent CLIs for mistral-7b" });
  expect(
    (
      within(pop).getByRole("checkbox", {
        name: "mistral-7b on OpenCode",
      }) as HTMLInputElement
    ).checked,
  ).toBe(true);
  expect(
    (
      within(pop).getByRole("checkbox", {
        name: "mistral-7b on Codex CLI",
      }) as HTMLInputElement
    ).disabled,
  ).toBe(true);
  fireEvent.click(within(pop).getByRole("checkbox", { name: "mistral-7b on OpenCode" }));
  await waitFor(() => expect(within(pop).getByRole("button", { name: "Undo" })).toBeTruthy()); // kept for its Undo
  fireEvent.click(gone); // closed: its line goes, and the model with it
  await waitFor(() => expect(screen.queryByRole("button", { name: "mistral-7b" })).toBeNull());
});

test("a default the list no longer has, unticked: its row stays with the line and Undo, which brings both back", async () => {
  const mistral = model("Мистраль", "opencode", "OpenCode", "mistral-7b", "LM Studio дома");
  server.entries = { models: [mistral], servers: [LMSTUDIO], defaults: [externalDefault(mistral)] };
  await mount();
  await openModel("mistral-7b");
  const pop = await screen.findByRole("group", { name: "Agent CLIs for mistral-7b" });
  const box = await tickOf("mistral-7b on OpenCode");
  box.focus();
  fireEvent.click(box);
  await waitFor(() => expect(server.entries.models).toEqual([]));
  const undo = await within(pop).findByRole("button", { name: "Undo" });
  expect(undo.closest(".mx-sub-undo")?.textContent).toBe("Removed Мистраль. OpenCode is back on its settings.Undo");
  expect(pop.isConnected).toBe(true);
  expect(box.isConnected).toBe(true);
  expect(box.disabled).toBe(false); // a disabled box would drop the focus
  expect(box.getAttribute("aria-disabled")).toBe("true"); // not listed: only Undo brings it back
  expect(document.activeElement).toBe(box);
  fireEvent.click(box);
  expect(box.checked).toBe(false);
  expect(server.of("POST", "/api/models").filter((c) => c.path === "/api/models")).toEqual([]);
  fireEvent.click(undo);
  await waitFor(() => expect(box.checked).toBe(true));
  const back = server.entries.models.find((m) => m.name === "Мистраль");
  expect(back).toBeTruthy();
  expect(server.entries.defaults).toEqual([externalDefault(back!)]);
  await waitFor(() => expect(document.activeElement).toBe(box));
});

test("several models of one tick: on, disabled, titled with them", async () => {
  server.entries = {
    models: [model("Быстрая", "opencode", "OpenCode", "qwen3-8b"), model("Сильная", "opencode", "OpenCode", "qwen3-8b")],
    servers: [LMSTUDIO],
  };
  await mount();
  await openModel("qwen3-8b");
  const box = await tickOf("qwen3-8b on OpenCode");
  expect([box.checked, box.disabled]).toEqual([true, true]);
  expect(box.title).toBe("Быстрая, Сильная: remove them in Your models");
});

test("a list longer than ten: search above it, its count under it", async () => {
  const many = Array.from({ length: 12 }, (_, i) => `model-${i}`);
  server.entries = { models: [], servers: [LMSTUDIO] };
  server.probes[LMSTUDIO.name] = { ...LMSTUDIO_PROBE, models: many, embeddings: [] };
  await mount();
  fireEvent.click(await source(LMSTUDIO.name));
  const search = await screen.findByRole("searchbox", {
    name: "Search 12 models",
  });
  expect(search.getAttribute("placeholder")).toBe("Search 12 models");
  expect(screen.getByText("12 models")).toBeTruthy();
  fireEvent.change(search, { target: { value: "MODEL-1" } });
  const rows = within(document.querySelector(".mx-list") as HTMLElement).getAllByRole("button");
  expect(rows.map((b) => b.getAttribute("aria-label"))).toEqual(["model-1", "model-10", "model-11"]);
  expect(screen.getByText("3 of 12 models")).toBeTruthy();
});

test("a server's list past twenty models stays bounded on a phone", async () => {
  server.entries = { models: [], servers: [LMSTUDIO] };
  const many = Array.from({ length: 21 }, (_, i) => `model-${i}`);
  server.probes[LMSTUDIO.name] = { ...LMSTUDIO_PROBE, models: many, embeddings: [] };
  await mount();
  fireEvent.click(await source(LMSTUDIO.name));
  await screen.findByRole("button", { name: "model-0" });
  expect((document.querySelector(".mx-list") as HTMLElement).className).not.toContain("mx-short");
});

test("a server that does not answer says why with its hint, and that its models stay saved", async () => {
  server.probes["LM Studio дома"] = () =>
    refusal("http://localhost:1234 does not answer (connection refused)", "address", "LADO runs in a container…");
  server.entries = {
    models: [model("Локальная Gemma", "opencode", "OpenCode", "gemma", "LM Studio дома")],
    servers: [LMSTUDIO],
  };
  await mount();
  const lm = item(await source("LM Studio дома"));
  fireEvent.click(await source("LM Studio дома"));
  const warn = await within(lm).findByRole("alert");
  // Its address is in the row's head: the line says what it does.
  expect(warn.textContent).toBe("⚠ Does not answer (connection refused)LADO runs in a container…");
  expect(
    within(lm).getByText("Its model stays saved; agents on it stop at their first turn until it answers."),
  ).toBeTruthy();
});

const NO_LIST = { ...LMSTUDIO_PROBE, models: null, models_why: "GET /v1/models: 404" } as ProbeInfo;

test("Model id only for a server without a list, with a choice of its installed CLIs", async () => {
  server.probes[LMSTUDIO.name] = NO_LIST;
  server.entries = { models: [], servers: [LMSTUDIO] };
  await mount();
  fireEvent.click(await source(LMSTUDIO.name));
  const lm = item(await source(LMSTUDIO.name));
  await within(lm).findByLabelText("Model id");
  const choice = within(lm).getByLabelText("Agent CLI") as HTMLSelectElement;
  expect(choice.closest(".field")).toBeTruthy(); // the launch window's field look
  expect([...choice.options].map((o) => o.textContent)).toEqual(["Codex CLI", "OpenCode"]);
  cleanup();
  server.probes[LMSTUDIO.name] = LMSTUDIO_PROBE;
  await mount();
  fireEvent.click(await source(LMSTUDIO.name));
  await screen.findByRole("button", { name: "qwen3-8b" });
  expect(screen.queryByLabelText("Model id")).toBeNull();
});

test("Model id: the check after the typing settles, Add saves it, off while refused", async () => {
  server.probes[LMSTUDIO.name] = NO_LIST;
  server.entries = { models: [], servers: [LMSTUDIO] };
  await mount();
  fireEvent.click(await source(LMSTUDIO.name));
  const field = await screen.findByLabelText("Model id");
  vi.useFakeTimers({ shouldAdvanceTime: true });
  fireEvent.change(field, { target: { value: "gpt-x" } });
  expect(server.of("POST", "/api/models/check")).toEqual([]);
  await settle();
  vi.useRealTimers();
  expect((await screen.findByText("✓ in the list")).className).toBe("field-note ok");
  expect(server.of("POST", "/api/models/check")[0].body).toEqual({
    name: null,
    cli: "codex",
    model: "gpt-x",
    server: LMSTUDIO.name,
  });
  const lm = item(await source(LMSTUDIO.name));
  fireEvent.click(within(lm).getByRole("button", { name: "Add" }));
  await waitFor(() => expect(server.calls.filter((c) => c.path === "/api/models")).toHaveLength(1));
  expect(await screen.findByRole("button", { name: "gpt-x" })).toBeTruthy();
  server.answers["POST /api/models/check"] = () =>
    json({ kind: "refused", text: "a refusal", field: "model", name: "" });
  fireEvent.change(within(lm).getByLabelText("Model id"), {
    target: { value: "x" },
  });
  expect(await screen.findByText("a refusal", {}, { timeout: 3000 })).toBeTruthy();
  expect((within(lm).getByRole("button", { name: "Add" }) as HTMLButtonElement).disabled).toBe(true);
});

// A server's Change and Remove.

test("Change, Remove and the list: one at a time; Change checks what is typed; Save opens the list again", async () => {
  server.probes["LM Studio дома"] = LMSTUDIO_PROBE;
  server.entries = {
    models: [model("a", "opencode", "OpenCode", "qwen3-8b", "LM Studio дома")],
    servers: [LMSTUDIO],
  };
  await mount();
  const toggle = await source("LM Studio дома");
  const row = item(toggle);
  fireEvent.click(toggle);
  await screen.findByRole("button", { name: "qwen3-8b" });
  fireEvent.click(within(row).getByRole("button", { name: "Change LM Studio дома" }));
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  expect(screen.queryByRole("button", { name: "qwen3-8b" })).toBeNull();
  expect(within(row).getByLabelText("Address")).toBeTruthy();
  expect(within(row).getByText("Its 1 model keeps its name and moves with it.")).toBeTruthy();
  expect(server.of("POST", "/api/model-servers/check")).toEqual([]); // nothing typed yet
  fireEvent.click(within(row).getByRole("button", { name: "Remove LM Studio дома" }));
  expect(within(row).queryByLabelText("Address")).toBeNull();
  fireEvent.click(within(row).getByRole("button", { name: "Change LM Studio дома" }));
  fireEvent.change(within(row).getByLabelText("Address"), {
    target: { value: "http://localhost:1235" },
  });
  expect(await within(row).findByText("✓ LM Studio answers · 1 model")).toBeTruthy();
  expect(server.of("POST", "/api/model-servers/check").at(-1)?.body).toEqual({
    name: "LM Studio дома",
    address: "http://localhost:1235",
    key: null,
    key_typed: false,
    replace: true,
  });
  fireEvent.click(within(row).getByRole("button", { name: "Save" }));
  expect(await within(row).findByText('Saved model server "LM Studio дома".')).toBeTruthy();
  expect(toggle.getAttribute("aria-expanded")).toBe("true");
  expect(within(row).getByRole("button", { name: "qwen3-8b" })).toBeTruthy();
  expect(within(row).queryByText("Open a model to tick the agent CLIs that run it.")).toBeNull(); // only after Add
  expect(server.of("POST", "/api/model-servers").find((c) => c.path === "/api/model-servers")?.body).toEqual({
    name: "LM Studio дома",
    address: "http://localhost:1235",
    key: null,
    replace: true,
  });
});

test("Change: Save off while the address does not answer; a refused Save takes the check's place", async () => {
  server.entries = { models: [], servers: [LMSTUDIO] };
  await mount();
  const row = item(await source("LM Studio дома"));
  fireEvent.click(within(row).getByRole("button", { name: "Change LM Studio дома" }));
  const save = () => within(row).getByRole("button", { name: "Save" }) as HTMLButtonElement;
  const address = within(row).getByLabelText("Address");
  fireEvent.change(address, { target: { value: "http://localhost:1243" } });
  expect(await within(row).findByText(/does not answer/, {}, { timeout: 3000 })).toBeTruthy();
  expect(save().disabled).toBe(true);
  fireEvent.change(address, { target: { value: "http://localhost:1235" } });
  expect(await within(row).findByText("✓ LM Studio answers · 1 model", {}, { timeout: 3000 })).toBeTruthy();
  expect(save().disabled).toBe(false);
  server.answers["POST /api/model-servers"] = () =>
    refusal("http://localhost:1235 does not answer (connection refused)", "address");
  fireEvent.click(save());
  expect(await within(row).findByText(/localhost:1235 does not answer/)).toBeTruthy();
  expect(within(row).queryByText("✓ LM Studio answers · 1 model")).toBeNull();
  expect(save().disabled).toBe(true);
});

test.each([
  ["no field (the server failed)", ""],
  ["the name (removed meanwhile by the CLI)", "name"],
])("Change: a Save refused for %s shows under Address in the check's place; Save stays on", async (_, field) => {
  server.entries = { models: [], servers: [LMSTUDIO] };
  await mount();
  const row = item(await source("LM Studio дома"));
  fireEvent.click(within(row).getByRole("button", { name: "Change LM Studio дома" }));
  const address = within(row).getByLabelText("Address");
  fireEvent.change(address, { target: { value: "http://localhost:1235" } });
  expect(await within(row).findByText("✓ LM Studio answers · 1 model", {}, { timeout: 3000 })).toBeTruthy();
  server.answers["POST /api/model-servers"] = () => refusal("it went wrong", field);
  fireEvent.click(within(row).getByRole("button", { name: "Save" }));
  const line = await within(row).findByText("it went wrong");
  expect(line.closest(".field")).toBe(address.closest(".field"));
  expect(within(row).queryByText("✓ LM Studio answers · 1 model")).toBeNull();
  expect(within(row).getAllByText("it went wrong")).toHaveLength(1);
  expect((within(row).getByRole("button", { name: "Save" }) as HTMLButtonElement).disabled).toBe(false);
});

test.each([
  ["no field", "", "Add server"],
  ["the name", "name", "Name"],
])("Add server: a refusal for %s shows where its field is", async (_, field, where) => {
  server.entries = { models: [], servers: [] };
  await openForm("alpha", "localhost:1234");
  await waitFor(() => expect(addButton().disabled).toBe(false));
  server.answers["POST /api/model-servers"] = () => refusal("it went wrong", field);
  fireEvent.click(addButton());
  const line = await screen.findByText("it went wrong");
  const at = where === "Name" ? screen.getByLabelText("Name").closest(".field") : addButton().parentElement;
  expect(at?.contains(line)).toBe(true);
});

test("Change: a refused New key stays in its field, the refusal under it, Save off until the key is edited or erased", async () => {
  server.entries = { models: [], servers: [{ ...LMSTUDIO, has_key: true }] };
  await mount();
  const row = item(await source("LM Studio дома"));
  fireEvent.click(within(row).getByRole("button", { name: "Change LM Studio дома" }));
  const save = () => within(row).getByRole("button", { name: "Save" }) as HTMLButtonElement;
  const key = within(row).getByLabelText("New key") as HTMLInputElement;
  fireEvent.change(key, { target: { value: "sk-wrong" } });
  await waitFor(() => expect(save().disabled).toBe(false), { timeout: 3000 });
  server.answers["POST /api/model-servers"] = () => refusal("http://localhost:1234 refused the key (401)", "key");
  fireEvent.click(save());
  const line = await within(row).findByText("http://localhost:1234 refused the key (401)");
  expect(line.closest(".field")).toBe(key.closest(".field"));
  expect(key.value).toBe("sk-wrong");
  expect(save().disabled).toBe(true);
  fireEvent.keyDown(key, { key: "Enter" });
  expect(server.of("POST", "/api/model-servers").filter((c) => c.path === "/api/model-servers")).toHaveLength(1);
  fireEvent.change(key, { target: { value: "sk-wrong2" } });
  expect(within(row).queryByText(/refused the key/)).toBeNull();
  await waitFor(() => expect(save().disabled).toBe(false), { timeout: 3000 });
  fireEvent.click(save());
  await within(row).findByText("http://localhost:1234 refused the key (401)");
  fireEvent.change(key, { target: { value: "" } });
  expect(within(row).queryByText(/refused the key/)).toBeNull();
  await waitFor(() => expect(save().disabled).toBe(false), { timeout: 3000 });
  expect(JSON.stringify(server.calls.filter((c) => c.path !== "/api/model-servers"))).not.toContain("sk-wrong");
});

test("Add server: a refused key stays in Key, the refusal under it, Add off until the key is edited", async () => {
  server.entries = { models: [], servers: [] };
  await openForm("alpha", "localhost:1234");
  const key = screen.getByLabelText("Key") as HTMLInputElement;
  fireEvent.change(key, { target: { value: "k-wrong" } });
  await waitFor(() => expect(addButton().disabled).toBe(false));
  server.answers["POST /api/model-servers"] = () => refusal("http://localhost:1234 refused the key (401)", "key");
  fireEvent.click(addButton());
  const line = await screen.findByText("http://localhost:1234 refused the key (401)");
  expect(line.closest(".field")).toBe(key.closest(".field"));
  expect(key.value).toBe("k-wrong");
  expect(addButton().disabled).toBe(true);
  fireEvent.change(key, { target: { value: "k-right" } });
  expect(screen.queryByText(/refused the key/)).toBeNull();
  await waitFor(() => expect(addButton().disabled).toBe(false));
});

test("Change checks with the kept key: its plain-http warning and what answers before Save", async () => {
  server.entries = { models: [], servers: [{ ...LMSTUDIO, has_key: true }] };
  await mount();
  const row = item(await source("LM Studio дома"));
  fireEvent.click(within(row).getByRole("button", { name: "Change LM Studio дома" }));
  fireEvent.change(within(row).getByLabelText("Address"), {
    target: { value: "http://gw.example.com:4000" },
  });
  expect(await within(row).findByText(/over plain http/, {}, { timeout: 3000 })).toBeTruthy();
  expect(server.of("POST", "/api/model-servers/check").at(-1)?.body).toEqual({
    name: "LM Studio дома",
    address: "http://gw.example.com:4000",
    key: null,
    key_typed: false, // New key empty: the server sends the kept key
    replace: true,
  });
  expect(within(row).getByText("✓ LiteLLM answers · 1 model")).toBeTruthy(); // with the kept key
});

test("Remove asks under the row as an alertdialog, the focus on Cancel; with a key it says so", async () => {
  server.entries = {
    models: [
      model("a", "opencode", "OpenCode", "qwen3-8b", "LM Studio дома"),
      model("b", "codex", "Codex CLI", "qwen3-8b", "LM Studio дома"),
    ],
    servers: [
      { ...LMSTUDIO, has_key: true },
      { ...LMSTUDIO, name: "zeta", address: "http://zeta:1" },
    ],
  };
  await mount();
  const row = item(await source("LM Studio дома"));
  fireEvent.click(within(row).getByRole("button", { name: "Remove LM Studio дома" }));
  const ask = within(row).getByRole("alertdialog");
  expect(ask.querySelector("p")?.textContent).toBe(
    "Remove LM Studio дома and its 2 models: a, b? Its key is deleted too. This cannot be undone.",
  );
  expect(document.activeElement).toBe(within(ask).getByRole("button", { name: "Cancel" }));
  fireEvent.click(within(ask).getByRole("button", { name: "Cancel" }));
  expect(server.of("DELETE", "/api/model-servers/")).toEqual([]);
  fireEvent.click(within(row).getByRole("button", { name: "Remove LM Studio дома" }));
  const confirm = within(row).getByRole("button", {
    name: "Remove server and 2 models",
  }) as HTMLButtonElement;
  await waitFor(() => expect(confirm.disabled).toBe(false)); // once the models are read again
  fireEvent.click(confirm);
  expect(await screen.findByText("Removed LM Studio дома and its 2 models.")).toBeTruthy();
  expect(server.of("DELETE", "/api/model-servers/")[0].path).toBe(
    `/api/model-servers/${encodeURIComponent("LM Studio дома")}?with_models=true&confirmed=a&confirmed=b`,
  );
  const lines = screen.getAllByRole("listitem").map((li) => li.textContent);
  expect(lines.indexOf("Removed LM Studio дома and its 2 models.")).toBeLessThan(
    lines.findIndex((t) => t?.includes("zeta")),
  );
  const zeta = item(await source("zeta"));
  fireEvent.click(within(zeta).getByRole("button", { name: "Remove zeta" }));
  expect(within(zeta).getByRole("alertdialog").querySelector("p")?.textContent).toBe(
    "Remove zeta? This cannot be undone.",
  );
  expect(within(zeta).getByRole("button", { name: "Remove server" })).toBeTruthy();
});

test("Remove refused for a model added after it asked asks again, naming it", async () => {
  server.entries = {
    models: [model("a", "opencode", "OpenCode", "qwen3-8b", "LM Studio дома")],
    servers: [LMSTUDIO],
  };
  await mount();
  const row = item(await source("LM Studio дома"));
  fireEvent.click(within(row).getByRole("button", { name: "Remove LM Studio дома" }));
  const confirm = within(row).getByRole("button", {
    name: "Remove server and 1 model",
  }) as HTMLButtonElement;
  await waitFor(() => expect(confirm.disabled).toBe(false));
  server.entries = {
    ...server.entries,
    models: [...server.entries.models, model("late one", "kilo", "Kilo CLI", "qwen3-8b", "LM Studio дома")],
  };
  fireEvent.click(confirm);
  expect(await within(row).findByText(/has other models now: a, late one; nothing was removed/)).toBeTruthy();
  expect(await within(row).findByText(/Remove LM Studio дома and its 2 models: a, late one\?/)).toBeTruthy();
  expect(server.entries.models).toHaveLength(2);
});

// Add server.

async function openForm(name = "work", address = "https://gw.corp/llm") {
  await mount();
  fireEvent.click(await screen.findByRole("button", { name: "Add server" }));
  expect(document.activeElement).toBe(screen.getByLabelText("Name"));
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: name } });
  fireEvent.change(screen.getByLabelText("Address"), {
    target: { value: address },
  });
}
const fieldOf = (label: string) => screen.getByLabelText(label).closest(".field") as HTMLElement;
const addButton = () => screen.getByRole("button", { name: "Add server" }) as HTMLButtonElement;
const keyLabel = () => (screen.getByText("Key", { selector: "label" }).textContent ?? "").replace(/^Key\s*/, "");
const panel = async () => (await screen.findByText(/answers at/)).closest(".mx-found") as HTMLElement;

test("the form says why no API could be told, not only that no CLI can use the server", async () => {
  const late = "the Anthropic Messages API of http://localhost:1234 did not answer in time: try again";
  expect(render(<Found probe={{ ...LMSTUDIO_PROBE, clis: [], apis_why: late }} />).container.textContent).toContain(
    `⚠ APIs: cannot be told: ${late}`,
  );
});

test("the form names a CLI the server's type does not suit, and no other line without one", () => {
  const note = "Codex CLI: its Responses API loses Codex CLI's MCP tools, so the agent could not talk to LADO";
  const noted = render(<Found probe={{ ...LMSTUDIO_PROBE, cli_notes: [note] }} />).container;
  expect(noted.querySelector(".field-note.warn")?.textContent).toBe(`⚠ ${note}`);
  expect(render(<Found probe={LMSTUDIO_PROBE} />).container.querySelector(".field-note")).toBeNull();
});

test("the form checks once the typing settles, without a key: the found panel, the name free", async () => {
  await openForm("LM Studio дома", "localhost:1234");
  expect(addButton().disabled).toBe(true);
  expect(within(fieldOf("Address")).getByText(/checking localhost:1234 …/)).toBeTruthy();
  const found = await panel();
  expect(found.querySelector(".mx-found-t")?.textContent).toBe("✓ LM Studio answers at http://localhost:1234");
  expect(within(found).getByText("Models").nextElementSibling?.textContent).toBe(
    "1 · 1 embeddings model hidden: agents cannot run on it.",
  );
  expect(within(found).getByText("Agent CLIs").nextElementSibling?.textContent).toBe("Codex CLI, Kilo CLI, OpenCode");
  expect(within(fieldOf("Name")).getByText("free").className).toBe("field-note ok");
  expect(keyLabel()).toBe("optional");
  expect(within(fieldOf("Key")).getByText("Only LADO reads it; never shown again.")).toBeTruthy();
  await waitFor(() => expect(addButton().disabled).toBe(false));
  const checks = server.of("POST", "/api/model-servers/check");
  expect(checks.at(-1)?.body).toEqual({
    name: "LM Studio дома",
    address: "localhost:1234",
    key: null,
    key_typed: false,
    replace: false,
  });
  expect(server.calls.filter((c) => c.path === "/api/model-servers")).toEqual([]);
});

test("a typo in the port shows under Address before any Add, and Add stays off", async () => {
  await openForm("lab", "http://localhost:1243");
  const note = await within(fieldOf("Address")).findByText(
    "http://localhost:1243 does not answer (connection refused)",
  );
  expect(screen.getByLabelText("Address").getAttribute("aria-invalid")).toBe("true");
  expect(note.className).toBe("field-note bad");
  expect(addButton().disabled).toBe(true);
});

test("a taken name shows under Name, and Add stays off", async () => {
  server.entries = { models: [], servers: [LMSTUDIO] };
  await openForm("lm studio ДОМА", "localhost:1234");
  expect(await within(fieldOf("Name")).findByText('A model server "LM Studio дома" is saved already')).toBeTruthy();
  expect(await within(fieldOf("Address")).findByText('same address as model server "LM Studio дома"')).toBeTruthy();
  expect(within(fieldOf("Name")).queryByText("free")).toBeNull();
  expect(addButton().disabled).toBe(true);
});

test("a gateway that asks for a key: Key required; Check key sends the key once, leaves it for Add", async () => {
  await openForm();
  const asks = await within(fieldOf("Address")).findByText(
    "⚠ https://gw.corp/llm asks for a key (401): enter it in Key",
  );
  expect(asks.className).toBe("field-note warn");
  expect(keyLabel()).toBe("required by this server");
  expect(screen.queryByRole("button", { name: "Check key" })).toBeNull();
  const key = screen.getByLabelText("Key") as HTMLInputElement;
  fireEvent.change(key, { target: { value: "wrong" } });
  await waitFor(() => expect(addButton().disabled).toBe(false)); // asks for a key, one is typed
  expect(
    within(fieldOf("Key")).getByText(/The key is sent to the server only when you press Check key or Add server\./),
  ).toBeTruthy();
  expect(JSON.stringify(server.calls)).not.toContain("wrong");
  const actions = screen.getByRole("button", { name: "Check key" }).parentElement as HTMLElement;
  expect(
    within(actions)
      .getAllByRole("button")
      .map((b) => b.textContent),
  ).toEqual(["Check key", "Add server", "Cancel"]);
  fireEvent.click(screen.getByRole("button", { name: "Check key" }));
  expect(await within(fieldOf("Key")).findByText("https://gw.corp/llm refused the key (401)")).toBeTruthy();
  expect(keyLabel()).toBe("required by this server");
  expect(addButton().disabled).toBe(true);
  fireEvent.change(key, { target: { value: "right" } });
  fireEvent.click(await screen.findByRole("button", { name: "Check key" }));
  expect((await panel()).textContent).toContain("✓ LiteLLM answers at");
  expect(addButton().disabled).toBe(false);
  const sent = server.calls.filter((c) => JSON.stringify(c.body ?? "").includes("right"));
  expect(sent.map((c) => c.path)).toEqual(["/api/model-servers/check"]);
  expect(key.value).toBe("right"); // kept for Add
  fireEvent.click(addButton());
  await waitFor(() =>
    expect(server.of("POST", "/api/model-servers").filter((c) => c.path === "/api/model-servers")).toHaveLength(1),
  );
  expect(
    (server.of("POST", "/api/model-servers").find((c) => c.path === "/api/model-servers")?.body as { key: string }).key,
  ).toBe("right");
});

test("an older check's answer is dropped", async () => {
  const pending: ((r: Response) => void)[] = [];
  server.answers["POST /api/model-servers/check"] = () => new Promise((resolve) => pending.push(resolve));
  await openForm("a", "localhost:1243");
  await waitFor(() => expect(pending.length).toBe(1));
  fireEvent.change(screen.getByLabelText("Address"), {
    target: { value: "localhost:1234" },
  });
  await waitFor(() => expect(pending.length).toBe(2));
  await act(async () => pending[1](json({ probe: LMSTUDIO_PROBE, refusals: [], warnings: [], notes: [] })));
  await act(async () =>
    pending[0](
      json({
        probe: null,
        refusals: [{ message: "old", hint: "", field: "address", warnings: [] }],
        warnings: [],
        notes: [],
      }),
    ),
  );
  expect(screen.queryByText("old")).toBeNull();
  expect((await panel()).textContent).toContain("✓ LM Studio answers at");
});

test("the plain-http warning shows under Key while a key is typed, nothing sent", async () => {
  await openForm("ext", "gw.example.com:4000");
  const key = screen.getByLabelText("Key") as HTMLInputElement;
  fireEvent.change(key, { target: { value: "k-1" } });
  expect(
    await within(fieldOf("Key")).findByText("⚠ the key goes to gw.example.com over plain http://, unencrypted"),
  ).toBeTruthy();
  expect(JSON.stringify(server.calls)).not.toContain("k-1");
  fireEvent.change(key, { target: { value: "" } });
  await waitFor(() => expect(within(fieldOf("Key")).queryByText(/over plain http/)).toBeNull());
});

test("Add saves; the new server takes the form's place, open, says how to go on and takes the focus", async () => {
  server.entries = {
    models: [],
    servers: [{ ...LMSTUDIO, name: "zeta", address: "http://zeta:1" }],
  };
  await openForm("alpha", "localhost:1234");
  const key = screen.getByLabelText("Key") as HTMLInputElement;
  fireEvent.change(key, { target: { value: "k-secret" } });
  await waitFor(() => expect(addButton().disabled).toBe(false));
  fireEvent.click(addButton());
  expect(await screen.findByText('Saved model server "alpha".')).toBeTruthy();
  expect(screen.getByText("Open a model to tick the agent CLIs that run it.")).toBeTruthy();
  expect(key.value).toBe("");
  const posts = server.calls.filter((c) => c.path === "/api/model-servers");
  expect(posts.map((c) => c.body)).toEqual([
    {
      name: "alpha",
      address: "localhost:1234",
      key: "k-secret",
      replace: false,
    },
  ]);
  expect(JSON.stringify(server.calls.filter((c) => c !== posts[0]))).not.toContain("k-secret");
  const alpha = await source("alpha");
  expect(alpha.getAttribute("aria-expanded")).toBe("true");
  await waitFor(() => expect(document.activeElement).toBe(alpha));
  const order = screen
    .getAllByRole("listitem")
    .map((li) => li.querySelector(".mx-hit")?.getAttribute("aria-label") ?? li.textContent);
  expect(order.slice(0, 3)).toEqual(["zeta", "alpha", expect.stringContaining("Add server")]);
  expect(await screen.findByRole("button", { name: "qwen3-8b" })).toBeTruthy(); // its list the add's probe
  expect(server.of("POST", "/api/model-servers/alpha/probe")).toEqual([]);
});

test("Add's refusal shows under its field; the form keeps all but the key; Cancel empties it", async () => {
  server.answers["POST /api/model-servers"] = () => refusal("the disk refused it");
  await openForm("LM", "localhost:1234");
  const key = screen.getByLabelText("Key") as HTMLInputElement;
  fireEvent.change(key, { target: { value: "k-1" } });
  await waitFor(() => expect(addButton().disabled).toBe(false));
  fireEvent.click(addButton());
  const note = await screen.findByText("the disk refused it");
  expect(note.closest(".field")).toBeNull(); // no field: under the buttons
  expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("LM");
  expect(key.value).toBe("");
  fireEvent.change(key, { target: { value: "k-2" } });
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  fireEvent.click(screen.getByRole("button", { name: "Add server" }));
  expect((screen.getByLabelText("Key") as HTMLInputElement).value).toBe("");
});

test("a server's saved line goes with the human's next change, as a Removed line does", async () => {
  server.entries = { models: [], servers: [] };
  await openForm("alpha", "localhost:1234");
  await waitFor(() => expect(addButton().disabled).toBe(false));
  fireEvent.click(addButton());
  expect(await screen.findByText('Saved model server "alpha".')).toBeTruthy();
  fireEvent.click(await screen.findByRole("button", { name: "qwen3-8b" }));
  const box = await tickOf("qwen3-8b on OpenCode");
  fireEvent.click(box);
  await waitFor(() => expect(box.checked).toBe(true));
  expect(screen.queryByText('Saved model server "alpha".')).toBeNull();
});

test("a server's saved lines go once another server is removed", async () => {
  server.entries = {
    models: [],
    servers: [{ ...LMSTUDIO, name: "zeta", address: "http://zeta:1" }],
  };
  await openForm("alpha", "localhost:1234");
  await waitFor(() => expect(addButton().disabled).toBe(false));
  fireEvent.click(addButton());
  expect(await screen.findByText('Saved model server "alpha".')).toBeTruthy();
  const zeta = item(await source("zeta"));
  fireEvent.click(within(zeta).getByRole("button", { name: "Remove zeta" }));
  const confirm = within(zeta).getByRole("button", {
    name: "Remove server",
  }) as HTMLButtonElement;
  await waitFor(() => expect(confirm.disabled).toBe(false));
  fireEvent.click(confirm);
  expect(await screen.findByText("Removed zeta.")).toBeTruthy();
  expect(screen.queryByText('Saved model server "alpha".')).toBeNull();
});
