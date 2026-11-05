// Settings → Models' cards of the agent CLIs: the default model on each, what the page reads and
// when, and removing what is a default. The rename, × and Undo of a model: ModelSettings.test.tsx.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { MODEL_DEBOUNCE } from "./Launch";
import {
  builtinDefault,
  externalDefault,
  kiloRow,
  LMSTUDIO,
  LMSTUDIO_PROBE,
  model,
  ModelServer,
  refusal,
} from "./modelFakes";
import { LEAD, LEAD_NO_MODELS, ModelSettings } from "./ModelSettings";

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

const card = (title: string) => screen.findByRole("group", { name: title });
const field = (title: string) => screen.findByRole("combobox", { name: `Default model of ${title}` });
const names = (where: HTMLElement) =>
  within(where)
    .queryAllByRole("button", { name: /^Rename / })
    .map((b) => b.textContent);
const reads = () => server.calls.filter((c) => c.path.includes("/model-choices"));
const probes = () => server.calls.filter((c) => c.path.endsWith("/probe"));

const QWEN = model("Локальная Qwen", "opencode", "OpenCode", "qwen3-8b");
const CODER = model("Рабочая Qwen", "opencode", "OpenCode", "qwen3-coder-30b");

test("a card per agent CLI: the installed ones in LADO's order, then the others, each on its settings", async () => {
  server.logins = [kiloRow(false), ...server.logins.slice(0, 3)];
  mount();
  await card("Claude Code");
  const titles = screen.getAllByRole("group").map((g) => g.getAttribute("aria-label"));
  expect(titles).toEqual(["Claude Code", "Codex CLI", "OpenCode", "Kilo CLI"]);
  expect((await field("OpenCode")).textContent).toContain("OpenCode's settings");
  expect(within(await card("Claude Code")).getByText("logged in")).toBeTruthy();
  expect(within(await card("OpenCode")).queryByRole("table")).toBeNull();
});

test("the blocks are Your agent CLIs then Model servers; the lead says how to add models", async () => {
  mount();
  await card("Claude Code");
  expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual([
    "Your agent CLIs",
    "Model servers ",
  ]);
  expect(screen.getByText(LEAD_NO_MODELS)).toBeTruthy();
  cleanup();
  server.entries = { ...server.entries, models: [QWEN], servers: [LMSTUDIO] };
  mount();
  await card("OpenCode");
  expect(screen.getByText(LEAD)).toBeTruthy();
});

test("a model of a CLI LADO does not know has a card of its own, its field off", async () => {
  server.entries = {
    ...server.entries,
    models: [model("Старая", "gemini", "gemini", "g-1")],
    servers: [LMSTUDIO],
  };
  mount();
  await card("gemini");
  expect(((await field("gemini")) as HTMLButtonElement).disabled).toBe(true);
});

test("opening the page reads only the lists of built-in defaults, and no server", async () => {
  server.entries = {
    models: [QWEN],
    servers: [LMSTUDIO],
    defaults: [builtinDefault("kilo", "a/one"), externalDefault(QWEN)],
  };
  server.logins = [...server.logins.slice(0, 3), kiloRow(true)];
  mount();
  await card("Kilo CLI");
  await waitFor(() => expect(reads()).toHaveLength(1));
  expect(reads()[0].path).toBe("/api/providers/kilo/model-choices?model=a%2Fone");
  expect(probes()).toEqual([]);
});

test("an older read that answers late changes nothing: the latest list stands", async () => {
  server.entries = { ...server.entries, defaults: [builtinDefault("opencode", "old/model")] };
  const answers: (() => void)[] = [];
  server.answers["GET /api/providers/opencode/model-choices"] = () =>
    new Promise((resolve) => {
      const path = server.calls.at(-1)?.path ?? "";
      answers.push(() => resolve(server.answer("GET", decodeURIComponent(path), undefined)));
    });
  mount();
  const opencode = await card("OpenCode");
  await waitFor(() => expect(answers).toHaveLength(1));
  fireEvent.click(await field("OpenCode"));
  await waitFor(() => expect(answers).toHaveLength(2));
  server.lists.opencode = { models: ["old/model"] }; // the latest read: it is listed
  await act(async () => answers[1]());
  server.lists.opencode = {}; // the older read, answering last: it is not
  await act(async () => answers[0]());
  expect(within(opencode).queryByText(/no longer lists/)).toBeNull();
});

test("a card's models: the default first, the others by name, under Your models <n>", async () => {
  const alpha = model("Alpha", "opencode", "OpenCode", "m-a");
  server.entries = {
    models: [alpha, QWEN, CODER],
    servers: [LMSTUDIO],
    defaults: [externalDefault(CODER)],
  };
  mount();
  const opencode = await card("OpenCode");
  expect(names(opencode)).toEqual(["Рабочая Qwen", "Alpha", "Локальная Qwen"]);
  expect(within(opencode).getByText("Your models")).toBeTruthy();
  expect(within(opencode).getByRole("table", { name: "Your models on OpenCode" })).toBeTruthy();
  expect(within(opencode).getAllByText("LM Studio дома")[1].getAttribute("title")).toBe(LMSTUDIO.address);
});

const nine = () => "abcdefghi".split("").map((c) => model(`m-${c}`, "opencode", "OpenCode", `id-${c}`));

test("more than five models fold to five with the default among them; the state lasts through a reload", async () => {
  const models = nine();
  server.entries = { models, servers: [LMSTUDIO], defaults: [externalDefault(models[8])] };
  mount();
  const opencode = await card("OpenCode");
  expect(names(opencode)).toEqual(["m-i", "m-a", "m-b", "m-c", "m-d"]);
  const more = within(opencode).getByRole("button", { name: "Show all 9 models" });
  expect(more.getAttribute("aria-expanded")).toBe("false");
  more.focus();
  fireEvent.click(more);
  expect(names(opencode)).toHaveLength(9);
  const fewer = within(opencode).getByRole("button", { name: "Show fewer" });
  expect(fewer).toBe(more);
  expect(document.activeElement).toBe(fewer);
  fireEvent.click(within(opencode).getByRole("button", { name: "Remove m-a" }));
  await within(opencode).findByRole("button", { name: "Undo" });
  expect(names(opencode)).toHaveLength(8); // no removal folds it
});

test("exactly five models do not fold", async () => {
  server.entries = { ...server.entries, models: nine().slice(0, 5), servers: [LMSTUDIO] };
  mount();
  const opencode = await card("OpenCode");
  expect(names(opencode)).toHaveLength(5);
  expect(within(opencode).queryByRole("button", { name: /^Show/ })).toBeNull();
});

test("a pick saves at once by reference and keeps the focus on the field", async () => {
  server.entries = { ...server.entries, models: [QWEN], servers: [LMSTUDIO] };
  mount();
  const opening = await field("OpenCode");
  fireEvent.click(opening);
  fireEvent.click(await screen.findByRole("option", { name: /Локальная Qwen/ }));
  await waitFor(() => expect(opening.textContent).toContain("Локальная Qwen"));
  expect(server.of("PUT", "/api/model-defaults/opencode")[0].body).toEqual({ external: QWEN.id });
  expect(document.activeElement).toBe(opening);
  fireEvent.click(opening);
  fireEvent.click(await screen.findByRole("option", { name: "a/one" }));
  await waitFor(() => expect(opening.textContent).toContain("a/one"));
  expect(server.of("PUT", "/api/model-defaults/opencode")[1].body).toEqual({ builtin: "a/one" });
  fireEvent.click(opening);
  fireEvent.click(await screen.findByRole("option", { name: /OpenCode's settings/ }));
  await waitFor(() => expect(opening.textContent).toContain("OpenCode's settings"));
  expect(server.of("DELETE", "/api/model-defaults/opencode")).toHaveLength(1);
});

test("a refused pick shows under the field as an alert, the value as it was", async () => {
  server.entries = { ...server.entries, defaults: [builtinDefault("opencode", "b/two")] };
  server.answers["PUT /api/model-defaults/opencode"] = () => refusal("OpenCode is not installed", "cli");
  mount();
  const opening = await field("OpenCode");
  fireEvent.click(opening);
  fireEvent.click(await screen.findByRole("option", { name: "a/one" }));
  const note = await screen.findByRole("alert");
  expect(note.textContent).toBe("OpenCode is not installed");
  expect(opening.textContent).toContain("b/two");
  expect(opening.getAttribute("aria-describedby")).toBe(note.closest("[id]")?.id);
  delete server.answers["PUT /api/model-defaults/opencode"];
  fireEvent.click(opening);
  fireEvent.click(await screen.findByRole("option", { name: "a/one" }));
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
});

test("a built-in default the list lost stays on the card with its warning and a way out", async () => {
  server.entries = { ...server.entries, defaults: [builtinDefault("opencode", "old/model")] };
  mount();
  const opencode = await card("OpenCode");
  const line = await within(opencode).findByText(
    "⚠ OpenCode no longer lists old/model: agents on it stop at their first turn.",
  );
  expect(line.closest("[role=status]")).toBeTruthy();
  expect((await field("OpenCode")).textContent).toContain("⚠ no longer listed");
  expect(server.of("DELETE", "/api/model-defaults")).toEqual([]);
  fireEvent.click(within(opencode).getByRole("button", { name: "Use OpenCode's settings" }));
  await waitFor(async () => expect((await field("OpenCode")).textContent).toContain("OpenCode's settings"));
  expect(document.activeElement).toBe(await field("OpenCode"));
});

test("a list that cannot be read: the card warns of a built-in default with Check again", async () => {
  server.lists.opencode = { models: null, why: "`opencode models` timed out", other_name: true };
  server.entries = { ...server.entries, defaults: [builtinDefault("opencode", "a/one")] };
  mount();
  const opencode = await card("OpenCode");
  await within(opencode).findByText(/`opencode models` timed out: LADO cannot check a\/one/);
  server.lists.opencode = {};
  const before = reads().length;
  fireEvent.click(within(opencode).getByRole("button", { name: "Check again" }));
  await waitFor(() => expect(within(opencode).queryByText(/LADO cannot check/)).toBeNull());
  expect(reads()).toHaveLength(before + 1);
  expect(reads().at(-1)?.path).toContain("fresh=true");
});

test("a silent server shows on opening the picker, and stays until Check again finds it well", async () => {
  server.entries = { models: [QWEN], servers: [LMSTUDIO], defaults: [externalDefault(QWEN)] };
  server.probes[LMSTUDIO.name] = () => refusal("http://localhost:1234 does not answer (connection refused)");
  mount();
  const opencode = await card("OpenCode");
  expect(within(opencode).queryByText(/does not answer/)).toBeNull(); // the page asks no server
  fireEvent.click(await field("OpenCode"));
  const line = await within(opencode).findByText(
    "⚠ LM Studio дома does not answer (connection refused); Локальная Qwen is on it. Start the server or pick another model.",
  );
  expect(probes()).toHaveLength(1);
  fireEvent.keyDown(await field("OpenCode"), { key: "Escape" });
  expect(line.isConnected).toBe(true);
  expect(server.of("DELETE", "/api/model-defaults")).toEqual([]);
  server.probes[LMSTUDIO.name] = LMSTUDIO_PROBE;
  server.probes[LMSTUDIO.name] = { ...LMSTUDIO_PROBE, models: ["qwen3-8b"] };
  fireEvent.click(within(opencode).getByRole("button", { name: "Check again" }));
  await waitFor(() => expect(within(opencode).queryByText(/does not answer/)).toBeNull());
});

test("Check again keeps its focus while it asks, saying so", async () => {
  server.entries = { models: [QWEN], servers: [LMSTUDIO], defaults: [externalDefault(QWEN)] };
  server.probes[LMSTUDIO.name] = () => refusal("http://localhost:1234 does not answer (connection refused)");
  mount();
  const opencode = await card("OpenCode");
  fireEvent.click(await field("OpenCode"));
  await within(opencode).findByText(/does not answer/);
  fireEvent.keyDown(await field("OpenCode"), { key: "Escape" });
  let release: () => void = () => undefined;
  server.probes[LMSTUDIO.name] = () =>
    new Promise((resolve) => {
      release = () => resolve(refusal("http://localhost:1234 does not answer (connection refused)"));
    });
  const again = within(opencode).getByRole("button", { name: "Check again" });
  again.focus();
  fireEvent.click(again);
  expect(await within(opencode).findByText("checking LM Studio дома …")).toBeTruthy();
  expect(again.getAttribute("aria-disabled")).toBe("true");
  expect(document.activeElement).toBe(again);
  fireEvent.click(again);
  expect(probes()).toHaveLength(2);
  await act(async () => release());
  expect(again.getAttribute("aria-disabled")).toBeNull();
});

test("a model gone from its server is marked on opening the picker, with the warning", async () => {
  server.entries = { models: [QWEN, CODER], servers: [LMSTUDIO], defaults: [externalDefault(CODER)] };
  server.probes[LMSTUDIO.name] = { ...LMSTUDIO_PROBE, models: ["qwen3-8b"] };
  mount();
  const opencode = await card("OpenCode");
  fireEvent.click(await field("OpenCode"));
  await within(opencode).findByText(
    "⚠ LM Studio дома no longer lists qwen3-coder-30b: agents on it stop at their first turn.",
  );
  expect(screen.getByRole("option", { name: /Рабочая Qwen/ }).textContent).toContain("not on the server");
  expect(screen.getByRole("option", { name: /Локальная Qwen/ }).textContent).not.toContain("not on the server");
});

test("each server of the CLI's models is asked once per opening", async () => {
  const other = model("Другая", "opencode", "OpenCode", "m", "LiteLLM");
  server.entries = { ...server.entries, models: [QWEN, CODER, other], servers: [LMSTUDIO, { ...LMSTUDIO, name: "LiteLLM" }] };
  server.probes[LMSTUDIO.name] = LMSTUDIO_PROBE;
  server.probes.LiteLLM = LMSTUDIO_PROBE;
  mount();
  fireEvent.click(await field("OpenCode"));
  await waitFor(() => expect(probes()).toHaveLength(2));
});

test("the card says an external default takes the whole process, by the provider's word", async () => {
  const gateway = model("Шлюз Opus", "claude", "Claude Code", "claude-opus-4-5", "work");
  server.entries = {
    models: [gateway],
    servers: [{ ...LMSTUDIO, name: "work" }],
    defaults: [externalDefault(gateway, true)],
  };
  mount();
  expect(
    await screen.findByText("On Claude Code this model takes the whole process: an agent on it runs only on work."),
  ).toBeTruthy();
  cleanup();
  server.entries = { ...server.entries, defaults: [externalDefault(gateway, false)] };
  mount();
  await card("Claude Code");
  expect(screen.queryByText(/takes the whole process/)).toBeNull();
});

test("a CLI not installed: the field shows its value, does not open, and the default clears", async () => {
  server.logins = [...server.logins.slice(0, 3), kiloRow(false)];
  const saved = model("Qwen в Kilo", "kilo", "Kilo CLI", "qwen3-8b");
  server.entries = { models: [saved], servers: [LMSTUDIO], defaults: [externalDefault(saved)] };
  mount();
  const kilo = await card("Kilo CLI");
  expect(await within(kilo).findByText("⚠ not installed: its default model cannot run")).toBeTruthy();
  const off = (await field("Kilo CLI")) as HTMLButtonElement;
  expect(off.disabled).toBe(true);
  expect(off.textContent).toContain("Qwen в Kilo");
  expect(reads()).toEqual([]);
  expect(within(kilo).getByRole("button", { name: "Rename Qwen в Kilo" })).toBeTruthy();
  fireEvent.click(within(kilo).getByRole("button", { name: "Use Kilo CLI's settings" }));
  await within(kilo).findByText("⚠ not installed: its models cannot run");
  expect(off.textContent).toContain("Kilo CLI's settings");
});

test("a CLI not installed with nothing saved says only that", async () => {
  server.logins = [...server.logins.slice(0, 3), kiloRow(false)];
  mount();
  const kilo = await card("Kilo CLI");
  expect(await within(kilo).findByText("⚠ not installed")).toBeTruthy();
});

test("Other name: a field with the search's text, the check once the typing settles, Use sets it", async () => {
  server.lists.claude = {
    aliases: ["opus"],
    models: null,
    why: "Claude Code gives no list",
    other_name: true,
    read_again: false,
  };
  server.answers["GET /api/providers/claude/models"] = () =>
    new Response(
      JSON.stringify({
        aliases: ["opus"],
        models: null,
        why: "",
        check: { kind: "warn", text: "Claude Code gives no list: LADO cannot check claude-x", field: "" },
      }),
    );
  mount();
  const claude = await card("Claude Code");
  fireEvent.click(await field("Claude Code"));
  fireEvent.click(await screen.findByRole("option", { name: /Other name…/ }));
  const name = within(claude).getByRole("textbox", { name: "Other name" }) as HTMLInputElement;
  await waitFor(() => expect(document.activeElement).toBe(name));
  expect((within(claude).getByRole("button", { name: "Use" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(name, { target: { value: "claude-x" } });
  await within(claude).findByText(/LADO cannot check claude-x/, undefined, { timeout: MODEL_DEBOUNCE + 1000 });
  fireEvent.click(within(claude).getByRole("button", { name: "Use" }));
  await waitFor(() => expect(within(claude).queryByRole("textbox", { name: "Other name" })).toBeNull());
  expect(server.of("PUT", "/api/model-defaults/claude")[0].body).toEqual({ builtin: "claude-x" });
  expect(await within(claude).findByText(/LADO cannot check claude-x/)).toBeTruthy(); // stays
  expect((await field("Claude Code")).textContent).toContain("claude-x");
});

test("Other name: Cancel closes it with the focus on the field, a refused name turns Use off", async () => {
  server.lists.opencode = { models: null, why: "no list", other_name: true };
  server.answers["GET /api/providers/opencode/models"] = () =>
    new Response(
      JSON.stringify({
        aliases: [],
        models: null,
        why: "",
        check: { kind: "refused", text: "bad name", field: "" },
      }),
    );
  mount();
  const opencode = await card("OpenCode");
  fireEvent.click(await field("OpenCode"));
  fireEvent.click(await screen.findByRole("option", { name: /Other name…/ }));
  const name = within(opencode).getByRole("textbox", { name: "Other name" });
  fireEvent.change(name, { target: { value: "x y" } });
  await within(opencode).findByText("bad name", undefined, { timeout: MODEL_DEBOUNCE + 1000 });
  expect((within(opencode).getByRole("button", { name: "Use" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(within(opencode).getByRole("button", { name: "Cancel" }));
  expect(within(opencode).queryByRole("textbox", { name: "Other name" })).toBeNull();
  expect(document.activeElement).toBe(await field("OpenCode"));
});

// Removing what is a default.

test("× on a default asks in place, the focus on Cancel; Cancel and Esc keep the model", async () => {
  server.entries = { models: [QWEN, CODER], servers: [LMSTUDIO], defaults: [externalDefault(QWEN)] };
  mount();
  const opencode = await card("OpenCode");
  const remove = within(opencode).getByRole("button", { name: "Remove Локальная Qwen" });
  fireEvent.click(remove);
  const question = within(opencode).getByRole("alertdialog");
  expect(question.textContent).toContain(
    "Remove Локальная Qwen? It is OpenCode's default model: OpenCode goes back to its settings.",
  );
  const cancel = within(question).getByRole("button", { name: "Cancel" });
  await waitFor(() => expect(document.activeElement).toBe(cancel));
  fireEvent.click(cancel);
  expect(within(opencode).queryByRole("alertdialog")).toBeNull();
  const again = within(opencode).getByRole("button", { name: "Remove Локальная Qwen" });
  await waitFor(() => expect(document.activeElement).toBe(again));
  fireEvent.click(again);
  fireEvent.keyDown(within(opencode).getByRole("alertdialog"), { key: "Escape" });
  expect(within(opencode).queryByRole("alertdialog")).toBeNull();
  expect(server.of("DELETE", "/api/models/")).toEqual([]);
});

test("× on any other model asks nothing", async () => {
  server.entries = { models: [QWEN, CODER], servers: [LMSTUDIO], defaults: [externalDefault(QWEN)] };
  mount();
  const opencode = await card("OpenCode");
  fireEvent.click(within(opencode).getByRole("button", { name: "Remove Рабочая Qwen" }));
  await within(opencode).findByRole("button", { name: "Undo" });
  expect(within(opencode).queryByRole("alertdialog")).toBeNull();
});

test("a default removed says the CLI is back on its settings; Undo brings the model and the default back", async () => {
  server.entries = { models: [QWEN, CODER], servers: [LMSTUDIO], defaults: [externalDefault(QWEN)] };
  mount();
  const opencode = await card("OpenCode");
  fireEvent.click(within(opencode).getByRole("button", { name: "Remove Локальная Qwen" }));
  fireEvent.click(within(opencode).getByRole("button", { name: "Remove model" }));
  const undo = await within(opencode).findByRole("button", { name: "Undo" });
  expect(undo.closest("[role=row]")?.textContent).toContain(
    "Removed Локальная Qwen. OpenCode is back on its settings.",
  );
  expect((await field("OpenCode")).textContent).toContain("OpenCode's settings");
  fireEvent.click(undo);
  await within(opencode).findByRole("button", { name: "Rename Локальная Qwen" });
  await waitFor(async () => expect((await field("OpenCode")).textContent).toContain("Локальная Qwen"));
  const added = server.entries.models.find((m) => m.name === QWEN.name);
  expect(server.of("PUT", "/api/model-defaults/opencode")[0].body).toEqual({ external: added?.id });
});

test("Undo of a default whose second call is refused: the model is back, the row says why", async () => {
  server.entries = { models: [QWEN], servers: [LMSTUDIO], defaults: [externalDefault(QWEN)] };
  server.answers["PUT /api/model-defaults/opencode"] = () => refusal("OpenCode is not installed", "cli");
  mount();
  const opencode = await card("OpenCode");
  fireEvent.click(within(opencode).getByRole("button", { name: "Remove Локальная Qwen" }));
  fireEvent.click(within(opencode).getByRole("button", { name: "Remove model" }));
  fireEvent.click(await within(opencode).findByRole("button", { name: "Undo" }));
  const row = (await within(opencode).findByRole("button", { name: "Rename Локальная Qwen" })).closest("[role=row]");
  await waitFor(() => expect(row?.textContent).toContain("OpenCode is not installed"));
});

test("a default gone with its server says so on the card until the next change", async () => {
  server.entries = { models: [QWEN], servers: [LMSTUDIO], defaults: [externalDefault(QWEN)] };
  mount();
  const opencode = await card("OpenCode");
  fireEvent.click(within(screen.getByRole("list")).getByRole("button", { name: `Remove ${LMSTUDIO.name}` }));
  const question = await screen.findByRole("alertdialog");
  await waitFor(() =>
    expect(question.textContent).toContain(
      "Remove LM Studio дома and its 1 model: Локальная Qwen? Локальная Qwen is OpenCode's default model: OpenCode goes back to its settings.",
    ),
  );
  const confirm = within(question).getByRole("button", { name: "Remove server and 1 model" }) as HTMLButtonElement;
  await waitFor(() => expect(confirm.disabled).toBe(false));
  fireEvent.click(confirm);
  await within(opencode).findByText("Its default model Локальная Qwen was removed with LM Studio дома.");
  expect((await field("OpenCode")).textContent).toContain("OpenCode's settings");
  fireEvent.click(await field("OpenCode"));
  fireEvent.click(await screen.findByRole("option", { name: "a/one" }));
  await waitFor(() => expect(within(opencode).queryByText(/was removed with/)).toBeNull());
});

test("a default removed elsewhere with its server shows the same line at the next reload", async () => {
  server.entries = { models: [QWEN, CODER], servers: [LMSTUDIO], defaults: [externalDefault(QWEN)] };
  mount();
  const opencode = await card("OpenCode");
  server.entries = { models: [], servers: [], defaults: [] };
  fireEvent.click(within(opencode).getByRole("button", { name: "Remove Рабочая Qwen" }));
  await within(opencode).findByText("Its default model Локальная Qwen was removed with LM Studio дома.");
});

test("two defaults on a server: one sentence names them both", async () => {
  const kilo = model("Qwen в Kilo", "kilo", "Kilo CLI", "qwen3-8b");
  server.entries = {
    models: [kilo, QWEN],
    servers: [LMSTUDIO],
    defaults: [externalDefault(kilo), externalDefault(QWEN)],
  };
  mount();
  await card("OpenCode");
  fireEvent.click(screen.getByRole("button", { name: `Remove ${LMSTUDIO.name}` }));
  const question = await screen.findByRole("alertdialog");
  await waitFor(() =>
    expect(question.textContent).toContain(
      "Qwen в Kilo is Kilo CLI's default model and Локальная Qwen is OpenCode's: they go back to their settings.",
    ),
  );
});

test("unticking a default asks under its row, the tick staying on until the answer", async () => {
  server.entries = { models: [QWEN], servers: [LMSTUDIO], defaults: [externalDefault(QWEN)] };
  server.probes[LMSTUDIO.name] = LMSTUDIO_PROBE;
  mount();
  await card("OpenCode");
  fireEvent.click(await screen.findByRole("button", { name: LMSTUDIO.name }));
  fireEvent.click(await screen.findByRole("button", { name: "qwen3-8b" }));
  const tick = (await screen.findByRole("checkbox", { name: "qwen3-8b on OpenCode" })) as HTMLInputElement;
  fireEvent.click(tick);
  const question = await screen.findByRole("alertdialog");
  expect(question.textContent).toContain(
    "Remove Локальная Qwen? It is OpenCode's default model: OpenCode goes back to its settings.",
  );
  expect(tick.checked).toBe(true);
  expect(server.of("DELETE", "/api/models/")).toEqual([]);
  fireEvent.click(within(question).getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("alertdialog")).toBeNull();
  expect(tick.checked).toBe(true);
  fireEvent.click(tick);
  fireEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Remove model" }));
  await waitFor(() => expect(tick.checked).toBe(false));
  expect(server.of("DELETE", "/api/models/")).toHaveLength(1);
  expect(screen.queryByRole("button", { name: "Undo" })).toBeNull(); // a tick leaves no Undo
});
