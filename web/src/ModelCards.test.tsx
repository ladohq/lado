// A CLI's default model in its row on Settings → Agent CLIs (CliDefault.tsx): the picker, what
// it reads and when, its warnings and their ways out; and on Model servers, removing what is a
// default and what LADO's server not answering does there. The table's rename, × and Undo:
// ModelSettings.test.tsx.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useEffect, useState } from "react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { getProviderLogins, LADO_DOWN, type ProviderLogins } from "./api";
import { CliDefault } from "./CliDefault";
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
import { ModelSettings } from "./ModelSettings";
import { UNDO_MS } from "./removedModels";
import { useModelSettings } from "./useModelSettings";

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

// Each CLI's default as Agent CLIs' rows hold it, a group per CLI, with the page's one `✓ Saved`
// (Providers.test.tsx: the rows, and what else takes `✓ Saved` away).
function Defaults() {
  const settings = useModelSettings();
  const [rows, setRows] = useState<ProviderLogins[]>([]);
  const [saved, setSaved] = useState<string | null>(null);
  useEffect(() => {
    void getProviderLogins().then((page) => setRows(page.providers));
  }, []);
  return rows.map((row) => (
    <div key={row.cli.name} role="group" aria-label={row.cli.title}>
      <CliDefault
        row={row}
        settings={settings}
        saved={saved}
        onSaving={() => setSaved(null)}
        onSaved={() => setSaved(row.cli.name)}
      />
    </div>
  ));
}

function mount() {
  return render(<Defaults />);
}

function mountPage() {
  return render(
    <MemoryRouter>
      <ModelSettings />
    </MemoryRouter>,
  );
}

const card = (title: string) => screen.findByRole("group", { name: title });
const table = () => screen.findByRole("table", { name: "Your models" });
const field = (title: string) => screen.findByRole("combobox", { name: `Default model of ${title}` });
const reads = () => server.calls.filter((c) => c.path.includes("/model-choices"));
// The row's `✓ Saved` slot: a status region the row always has, empty until a save succeeds.
const savedSlot = (row: HTMLElement) => row.querySelector<HTMLElement>(".cli-saved");
const probes = () => server.calls.filter((c) => c.path.endsWith("/probe"));

const QWEN = model("Локальная Qwen", "opencode", "OpenCode", "qwen3-8b");
const CODER = model("Рабочая Qwen", "opencode", "OpenCode", "qwen3-coder-30b");

test("each installed CLI has its picker, on its settings, whatever its login; one not installed has none", async () => {
  server.logins = [...server.logins.slice(0, 3), kiloRow(false)];
  mount();
  await card("Kilo CLI");
  for (const title of ["Claude Code", "Codex CLI", "OpenCode"])
    expect((await field(title)).textContent).toContain(`${title}'s settings`);
  expect(within(await card("Kilo CLI")).queryByRole("combobox")).toBeNull();
  expect((await card("Kilo CLI")).textContent).toBe("");
});

test("opening the rows reads only the lists of built-in defaults, and no server", async () => {
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

test("a save says ✓ Saved in the row's status region, there and empty before it; the same value again too", async () => {
  server.entries = { ...server.entries, models: [QWEN], servers: [LMSTUDIO] };
  mount();
  const opencode = await card("OpenCode");
  const opening = await field("OpenCode");
  const slot = savedSlot(opencode)!;
  expect(slot.getAttribute("role")).toBe("status");
  expect(slot.textContent).toBe("");
  fireEvent.click(opening);
  fireEvent.click(await screen.findByRole("option", { name: /Локальная Qwen/ }));
  await waitFor(() => expect(slot.textContent).toBe("✓ Saved"));
  expect(savedSlot(opencode)).toBe(slot); // the same region, filled
  expect(slot.querySelector("[aria-hidden=true]")?.textContent).toBe("✓");
  fireEvent.click(opening);
  fireEvent.click(await screen.findByRole("option", { name: /Локальная Qwen/ }));
  await waitFor(() => expect(server.of("PUT", "/api/model-defaults/opencode")).toHaveLength(2));
  await waitFor(() => expect(slot.textContent).toBe("✓ Saved"));
  fireEvent.click(opening);
  fireEvent.click(await screen.findByRole("option", { name: /OpenCode's settings/ }));
  await waitFor(() => expect(server.of("DELETE", "/api/model-defaults/opencode")).toHaveLength(1));
  await waitFor(() => expect(slot.textContent).toBe("✓ Saved"));
});

test("Other name → Use and Use <CLI>'s settings under a warning each say ✓ Saved", async () => {
  server.lists.opencode = { models: null, why: "no list", other_name: true };
  mount();
  const opencode = await card("OpenCode");
  fireEvent.click(await field("OpenCode"));
  fireEvent.click(await screen.findByRole("option", { name: /Other name…/ }));
  const name = within(opencode).getByRole("textbox", { name: "Other name" });
  fireEvent.change(name, { target: { value: "a/typed" } });
  expect(savedSlot(opencode)!.textContent).toBe("");
  fireEvent.click(within(opencode).getByRole("button", { name: "Use" }));
  await waitFor(() => expect(savedSlot(opencode)!.textContent).toBe("✓ Saved"));

  cleanup();
  server = new ModelServer();
  server.install();
  server.entries = { ...server.entries, defaults: [builtinDefault("opencode", "old/model")] };
  mount();
  const again = await card("OpenCode");
  fireEvent.click(await within(again).findByRole("button", { name: "Use OpenCode's settings" }));
  await waitFor(() => expect(savedSlot(again)!.textContent).toBe("✓ Saved"));
});

test("a refused or unanswered save shows no ✓ Saved, and takes away the one shown before", async () => {
  mount();
  const opencode = await card("OpenCode");
  const opening = await field("OpenCode");
  fireEvent.click(opening);
  fireEvent.click(await screen.findByRole("option", { name: "a/one" }));
  await waitFor(() => expect(savedSlot(opencode)!.textContent).toBe("✓ Saved"));
  server.answers["PUT /api/model-defaults/opencode"] = () => refusal("OpenCode is not installed", "cli");
  fireEvent.click(opening);
  fireEvent.click(await screen.findByRole("option", { name: "b/two" }));
  expect((await within(opencode).findByRole("alert")).textContent).toBe("OpenCode is not installed");
  expect(savedSlot(opencode)!.textContent).toBe("");
  delete server.answers["PUT /api/model-defaults/opencode"];
  fireEvent.click(opening);
  fireEvent.click(await screen.findByRole("option", { name: "b/two" }));
  await waitFor(() => expect(savedSlot(opencode)!.textContent).toBe("✓ Saved"));
  offline("PUT /api/model-defaults/opencode");
  fireEvent.click(opening);
  fireEvent.click(await screen.findByRole("option", { name: "a/one" }));
  expect((await within(opencode).findByRole("alert")).textContent).toBe(
    "LADO's server does not answer: the value was not saved.",
  );
  expect(savedSlot(opencode)!.textContent).toBe("");
});

test("a save in another row moves ✓ Saved there", async () => {
  mount();
  const opencode = await card("OpenCode");
  const codex = await card("Codex CLI");
  fireEvent.click(await field("OpenCode"));
  fireEvent.click(await screen.findByRole("option", { name: "a/one" }));
  await waitFor(() => expect(savedSlot(opencode)!.textContent).toBe("✓ Saved"));
  fireEvent.click(await field("Codex CLI"));
  fireEvent.click(await screen.findByRole("option", { name: "a/one" }));
  await waitFor(() => expect(savedSlot(codex)!.textContent).toBe("✓ Saved"));
  expect(savedSlot(opencode)!.textContent).toBe("");
});

test("a CLI not installed has no ✓ Saved slot: its line going is the answer", async () => {
  server.logins = [...server.logins.slice(0, 3), kiloRow(false)];
  const saved = model("Qwen в Kilo", "kilo", "Kilo CLI", "qwen3-8b");
  server.entries = { models: [saved], servers: [LMSTUDIO], defaults: [externalDefault(saved)] };
  mount();
  const kilo = await card("Kilo CLI");
  await within(kilo).findByText(/cannot run: not installed/);
  expect(savedSlot(kilo)).toBeNull();
  fireEvent.click(within(kilo).getByRole("button", { name: "Use Kilo CLI's settings" }));
  await waitFor(() => expect(kilo.textContent).toBe(""));
});

test("a built-in default the list lost stays in the row with its warning and a way out", async () => {
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

test("a list that cannot be read: the row warns of a built-in default with Check again", async () => {
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
    "⚠ LM Studio дома does not answer (connection refused). Start it or pick another model.",
  );
  expect(probes()).toHaveLength(1);
  fireEvent.keyDown(await field("OpenCode"), { key: "Escape" });
  expect(line.isConnected).toBe(true);
  expect(server.of("DELETE", "/api/model-defaults")).toEqual([]);
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
    "⚠ qwen3-coder-30b is no longer in LM Studio дома's list of models. Load it there or pick another model.",
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

test("the row says an external default takes the whole process, by the provider's word", async () => {
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

test("a CLI not installed with a default: one line that it cannot run, and its settings clear it", async () => {
  server.logins = [...server.logins.slice(0, 3), kiloRow(false)];
  const saved = model("Qwen в Kilo", "kilo", "Kilo CLI", "qwen3-8b");
  server.entries = { models: [saved], servers: [LMSTUDIO], defaults: [externalDefault(saved)] };
  mount();
  const kilo = await card("Kilo CLI");
  expect(await within(kilo).findByText("Default model: Qwen в Kilo — cannot run: not installed")).toBeTruthy();
  expect(within(kilo).queryByRole("combobox")).toBeNull();
  expect(reads()).toEqual([]);
  fireEvent.click(within(kilo).getByRole("button", { name: "Use Kilo CLI's settings" }));
  await waitFor(() => expect(kilo.textContent).toBe(""));
  expect(server.of("DELETE", "/api/model-defaults/kilo")).toHaveLength(1);
});

test("Other name: a field with the search's text, the check once the typing settles, Use sets it", async () => {
  server.lists.claude = {
    aliases: ["opus"],
    models: null,
    why: "Claude Code gives no list",
    other_name: true,
    read_again: false,
  };
  server.answers["POST /api/model-defaults/claude/check"] = () =>
    new Response(
      JSON.stringify({ kind: "warn", text: "Claude Code gives no list: LADO cannot check claude-x", field: "", name: "" }),
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
  expect(server.of("PUT", "/api/model-defaults/claude")[0].body).toEqual({ typed: "claude-x" });
  expect(await within(claude).findByText(/LADO cannot check claude-x/)).toBeTruthy(); // stays
  expect((await field("Claude Code")).textContent).toContain("claude-x");
});

test("Other name: Cancel closes it with the focus on the field, a refused name turns Use off", async () => {
  server.lists.opencode = { models: null, why: "no list", other_name: true };
  server.answers["POST /api/model-defaults/opencode/check"] = () =>
    new Response(JSON.stringify({ kind: "refused", text: "bad name", field: "model", name: "" }));
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

test("Other name: Enter is Use, and off while refused", async () => {
  server.lists.opencode = { models: null, why: "no list", other_name: true };
  mount();
  const opencode = await card("OpenCode");
  fireEvent.click(await field("OpenCode"));
  fireEvent.click(await screen.findByRole("option", { name: /Other name…/ }));
  const name = within(opencode).getByRole("textbox", { name: "Other name" });
  fireEvent.change(name, { target: { value: "a/typed" } });
  fireEvent.keyDown(name, { key: "Enter" });
  await waitFor(() => expect(server.of("PUT", "/api/model-defaults/opencode")).toHaveLength(1));
  expect(server.of("PUT", "/api/model-defaults/opencode")[0].body).toEqual({ typed: "a/typed" });
});

test("Other name: the check is the core's for the name typed, and a row picked meanwhile closes the form", async () => {
  server.lists.opencode = { models: null, why: "no list", other_name: true };
  mount();
  const opencode = await card("OpenCode");
  const opening = await field("OpenCode");
  fireEvent.click(opening);
  fireEvent.click(await screen.findByRole("option", { name: /Other name…/ }));
  const name = within(opencode).getByRole("textbox", { name: "Other name" });
  fireEvent.change(name, { target: { value: "a/typed" } });
  await waitFor(() => expect(server.of("POST", "/api/model-defaults/opencode/check")).toHaveLength(1), {
    timeout: MODEL_DEBOUNCE + 1000,
  });
  expect(server.of("POST", "/api/model-defaults/opencode/check")[0].body).toEqual({ name: "a/typed" });
  fireEvent.click(opening);
  fireEvent.click(await screen.findByRole("option", { name: /OpenCode's settings/ }));
  await waitFor(() => expect(within(opencode).queryByRole("textbox", { name: "Other name" })).toBeNull());
});

test("Other name: the check of the typed name is a status tied to its field; the saved one's warning waits", async () => {
  server.lists.opencode = { models: null, why: "no list", other_name: true };
  server.entries = { ...server.entries, defaults: [builtinDefault("opencode", "saved/name")] };
  server.answers["POST /api/model-defaults/opencode/check"] = () =>
    new Response(JSON.stringify({ kind: "warn", text: "no list: LADO cannot check a/typed", field: "", name: "" }));
  mount();
  const opencode = await card("OpenCode");
  await within(opencode).findByText(/LADO cannot check saved\/name/);
  fireEvent.click(await field("OpenCode"));
  fireEvent.click(await screen.findByRole("option", { name: /Other name…/ }));
  const name = within(opencode).getByRole("textbox", { name: "Other name" });
  fireEvent.change(name, { target: { value: "a/typed" } });
  const note = await within(opencode).findByText("⚠ no list: LADO cannot check a/typed", undefined, {
    timeout: MODEL_DEBOUNCE + 1000,
  });
  expect(note.getAttribute("role")).toBe("status");
  expect(name.getAttribute("aria-describedby")).toBe(note.id);
  expect(within(opencode).queryByText(/LADO cannot check saved\/name/)).toBeNull();
  fireEvent.click(within(opencode).getByRole("button", { name: "Cancel" }));
  expect(within(opencode).getByText(/LADO cannot check saved\/name/)).toBeTruthy();
});

test("the picker shows what the core lists now, not what the page read at its opening", async () => {
  server.entries = { models: [QWEN], servers: [LMSTUDIO] };
  mount();
  await card("OpenCode");
  server.entries = { ...server.entries, models: [CODER] }; // another window, or `lado model add`
  fireEvent.click(await field("OpenCode"));
  expect(await screen.findByRole("option", { name: /Рабочая Qwen/ })).toBeTruthy();
  expect(screen.queryByRole("option", { name: /Локальная Qwen/ })).toBeNull();
});

test("Check again that finds the server well hands the focus to the field", async () => {
  server.entries = { models: [QWEN], servers: [LMSTUDIO], defaults: [externalDefault(QWEN)] };
  server.probes[LMSTUDIO.name] = () => refusal("http://localhost:1234 does not answer (connection refused)");
  mount();
  const opencode = await card("OpenCode");
  const opening = await field("OpenCode");
  fireEvent.click(opening);
  await within(opencode).findByText(/does not answer/);
  fireEvent.keyDown(opening, { key: "Escape" });
  server.probes[LMSTUDIO.name] = { ...LMSTUDIO_PROBE, models: ["qwen3-8b"] };
  const again = within(opencode).getByRole("button", { name: "Check again" });
  again.focus();
  fireEvent.click(again);
  await waitFor(() => expect(within(opencode).queryByText(/does not answer/)).toBeNull());
  await waitFor(() => expect(document.activeElement).toBe(opening));
});

test("Check again of a list that reads now hands the focus to the field", async () => {
  server.lists.opencode = { models: null, why: "timed out", other_name: true };
  server.entries = { ...server.entries, defaults: [builtinDefault("opencode", "a/one")] };
  mount();
  const opencode = await card("OpenCode");
  await within(opencode).findByText(/LADO cannot check a\/one/);
  server.lists.opencode = {};
  const again = within(opencode).getByRole("button", { name: "Check again" });
  again.focus();
  fireEvent.click(again);
  await waitFor(async () => expect(document.activeElement).toBe(await field("OpenCode")));
});

// LADO's server gone: every request rejects, as fetch does with no answer.
const serverStops = () => vi.stubGlobal("fetch", () => Promise.reject(new TypeError("Failed to fetch")));
const offline = (path: string) => {
  server.answers[path] = () => Promise.reject(new TypeError("Failed to fetch"));
};

test("a request LADO's server did not answer promises nothing of what became of it", () => {
  expect(LADO_DOWN).toBe("LADO's server does not answer: your request may or may not have reached it.");
});

test("LADO's server gone: one line of its own, the value as it was, no model server blamed", async () => {
  server.entries = { models: [QWEN, CODER], servers: [LMSTUDIO], defaults: [externalDefault(QWEN)] };
  mount();
  const opencode = await card("OpenCode");
  const opening = await field("OpenCode");
  offline(`POST /api/model-servers/${encodeURIComponent(LMSTUDIO.name)}/probe`);
  offline("PUT /api/model-defaults/opencode");
  fireEvent.click(opening);
  fireEvent.click(await screen.findByRole("option", { name: /Рабочая Qwen/ }));
  const alert = await within(opencode).findByRole("alert");
  expect(alert.textContent).toBe("LADO's server does not answer: the value was not saved.");
  await waitFor(() => expect(probes()).toHaveLength(1));
  expect(within(opencode).queryByText(/Start it/)).toBeNull();
  expect(within(opencode).queryByText(/Failed to fetch/)).toBeNull();
  expect(opening.querySelector(".srv.down")).toBeNull();
  expect(opening.textContent).toContain("Локальная Qwen");
});

// Removing what is a default, on Model servers.

test("× on any other model asks nothing", async () => {
  server.entries = { models: [QWEN, CODER], servers: [LMSTUDIO], defaults: [externalDefault(QWEN)] };
  mountPage();
  const yours = await table();
  fireEvent.click(within(yours).getByRole("button", { name: "Remove Рабочая Qwen" }));
  await within(yours).findByRole("button", { name: "Undo" });
  expect(within(yours).queryByRole("alertdialog")).toBeNull();
});

test("× on a default asks nothing: the row says the CLI is back on its settings, Undo focused brings both back", async () => {
  server.entries = { models: [QWEN, CODER], servers: [LMSTUDIO], defaults: [externalDefault(QWEN)] };
  mountPage();
  const yours = await table();
  fireEvent.click(within(yours).getByRole("button", { name: "Remove Локальная Qwen" }));
  expect(screen.queryByRole("alertdialog")).toBeNull();
  const undo = await within(yours).findByRole("button", { name: "Undo" });
  expect(server.of("DELETE", "/api/models/")).toHaveLength(1);
  expect(undo.closest("[role=row]")?.textContent).toContain(
    "Removed Локальная Qwen. OpenCode is back on its settings.",
  );
  await waitFor(() => expect(document.activeElement).toBe(undo));
  fireEvent.click(undo);
  const back = await within(yours).findByRole("button", { name: "Rename Локальная Qwen" });
  await waitFor(() => expect(back.closest("[role=row]")?.textContent).toContain("OpenCode · default"));
  const added = server.entries.models.find((m) => m.name === QWEN.name);
  expect(server.of("PUT", "/api/model-defaults/opencode")[0].body).toEqual({ external: added?.id });
});

test("Undo of a default whose second call is refused: the model is back, the row says why", async () => {
  server.entries = { models: [QWEN], servers: [LMSTUDIO], defaults: [externalDefault(QWEN)] };
  server.answers["PUT /api/model-defaults/opencode"] = () => refusal("OpenCode is not installed", "cli");
  mountPage();
  const yours = await table();
  fireEvent.click(within(yours).getByRole("button", { name: "Remove Локальная Qwen" }));
  fireEvent.click(await within(yours).findByRole("button", { name: "Undo" }));
  const row = (await within(yours).findByRole("button", { name: "Rename Локальная Qwen" })).closest("[role=row]");
  await waitFor(() => expect(row?.textContent).toContain("OpenCode is not installed"));
});

test("a server with a default on it: its question names the default, and confirmed it clears it", async () => {
  server.entries = { models: [QWEN], servers: [LMSTUDIO], defaults: [externalDefault(QWEN)] };
  mountPage();
  await table();
  fireEvent.click(screen.getByRole("button", { name: `Remove ${LMSTUDIO.name}` }));
  const question = await screen.findByRole("alertdialog");
  await waitFor(() =>
    expect(question.textContent).toContain(
      "Remove LM Studio дома and its 1 model: Локальная Qwen? Локальная Qwen is OpenCode's default model: OpenCode goes back to its settings.",
    ),
  );
  const confirm = within(question).getByRole("button", { name: "Remove server and 1 model" }) as HTMLButtonElement;
  await waitFor(() => expect(confirm.disabled).toBe(false));
  fireEvent.click(confirm);
  await waitFor(() => expect(server.entries.defaults).toEqual([]));
  expect(screen.queryByText(/was removed with/)).toBeNull(); // no line of it on this page
});

test("two defaults on a server: one sentence names them both", async () => {
  const kilo = model("Qwen в Kilo", "kilo", "Kilo CLI", "qwen3-8b");
  server.entries = {
    models: [kilo, QWEN],
    servers: [LMSTUDIO],
    defaults: [externalDefault(kilo), externalDefault(QWEN)],
  };
  mountPage();
  await table();
  fireEvent.click(screen.getByRole("button", { name: `Remove ${LMSTUDIO.name}` }));
  const question = await screen.findByRole("alertdialog");
  await waitFor(() =>
    expect(question.textContent).toContain(
      "Qwen в Kilo is Kilo CLI's default model and Локальная Qwen is OpenCode's: they go back to their settings.",
    ),
  );
});

// The open list of Agent CLIs under LM Studio's qwen3-8b, and OpenCode's tick in it.
async function openTick() {
  fireEvent.click(await screen.findByRole("button", { name: LMSTUDIO.name }));
  fireEvent.click(await screen.findByRole("button", { name: "qwen3-8b" }));
  const tick = (await screen.findByRole("checkbox", { name: "qwen3-8b on OpenCode" })) as HTMLInputElement;
  return { tick, list: screen.getByRole("group", { name: "Agent CLIs for qwen3-8b" }) };
}

test("unticking a default asks nothing: the line under its tick says so, Undo brings the model and the default back", async () => {
  server.entries = { models: [QWEN], servers: [LMSTUDIO], defaults: [externalDefault(QWEN)] };
  server.probes[LMSTUDIO.name] = LMSTUDIO_PROBE;
  mountPage();
  const yours = await table();
  const { tick, list } = await openTick();
  tick.focus();
  fireEvent.click(tick);
  expect(screen.queryByRole("alertdialog")).toBeNull();
  await waitFor(() => expect(tick.checked).toBe(false));
  expect(server.of("DELETE", "/api/models/")).toHaveLength(1);
  expect(server.entries.defaults).toEqual([]);
  const undo = await within(list).findByRole("button", { name: "Undo" });
  expect(undo.closest(".mx-sub-undo")?.textContent).toBe(
    "Removed Локальная Qwen. OpenCode is back on its settings.Undo",
  );
  expect(document.activeElement).toBe(tick); // the focus stays on the tick, Undo is next
  expect(tick.closest("label")?.nextElementSibling).toBe(undo.closest(".mx-sub-undo"));
  expect(within(yours).queryByRole("button", { name: "Undo" })).toBeNull(); // Undo only where the human acted
  fireEvent.click(undo);
  await waitFor(() => expect(tick.checked).toBe(true));
  await waitFor(() => expect(within(list).queryByText(/Removed/)).toBeNull());
  const added = server.entries.models.find((m) => m.name === QWEN.name);
  expect(added).toBeTruthy();
  expect(server.of("PUT", "/api/model-defaults/opencode")[0].body).toEqual({ external: added?.id });
  await waitFor(() => expect(document.activeElement).toBe(tick));
});

test("Undo of an untick whose default is refused: the model is back, the line says why", async () => {
  server.entries = { models: [QWEN], servers: [LMSTUDIO], defaults: [externalDefault(QWEN)] };
  server.probes[LMSTUDIO.name] = LMSTUDIO_PROBE;
  server.answers["PUT /api/model-defaults/opencode"] = () => refusal("OpenCode is not installed", "cli");
  mountPage();
  await table();
  const { tick, list } = await openTick();
  fireEvent.click(tick);
  fireEvent.click(await within(list).findByRole("button", { name: "Undo" }));
  await waitFor(() => expect(tick.checked).toBe(true));
  await waitFor(() => expect(list.querySelector(".mx-sub-undo")?.textContent).toContain("OpenCode is not installed"));
  expect(within(list).queryByRole("button", { name: "Undo" })).toBeNull();
});

// A default set in another window: this page shows none, and the removal finds one.
function setElsewhere(saved: ReturnType<typeof model>) {
  server.entries = { ...server.entries, defaults: [externalDefault(saved)] };
}

test("× on a default this page did not know of: its row says so, and Undo sets it again", async () => {
  server.entries = { models: [QWEN, CODER], servers: [LMSTUDIO] };
  mountPage();
  const yours = await table();
  setElsewhere(QWEN);
  fireEvent.click(within(yours).getByRole("button", { name: "Remove Локальная Qwen" }));
  const undo = await within(yours).findByRole("button", { name: "Undo" });
  expect(undo.closest("[role=row]")?.textContent).toContain(
    "Removed Локальная Qwen. OpenCode is back on its settings.",
  );
  fireEvent.click(undo);
  await within(yours).findByRole("button", { name: "Rename Локальная Qwen" });
  await waitFor(() => expect(server.of("PUT", "/api/model-defaults/opencode")).toHaveLength(1));
});

test("a tick off on a default this page did not know of: its line says so, and Undo sets it again", async () => {
  server.entries = { models: [QWEN], servers: [LMSTUDIO] };
  server.probes[LMSTUDIO.name] = LMSTUDIO_PROBE;
  mountPage();
  await table();
  const { tick, list } = await openTick();
  setElsewhere(QWEN);
  fireEvent.click(tick);
  await waitFor(() => expect(server.entries.defaults).toEqual([]));
  const undo = await within(list).findByRole("button", { name: "Undo" });
  expect(undo.closest(".mx-sub-undo")?.textContent).toContain("OpenCode is back on its settings.");
  fireEvent.click(undo);
  await waitFor(() => expect(server.of("PUT", "/api/model-defaults/opencode")).toHaveLength(1));
});

test("× with LADO's server gone says so in its own words, in its row", async () => {
  server.entries = { models: [QWEN, CODER], servers: [LMSTUDIO] };
  mountPage();
  const yours = await table();
  serverStops();
  fireEvent.click(within(yours).getByRole("button", { name: "Remove Рабочая Qwen" }));
  expect(await within(yours).findByText(LADO_DOWN)).toBeTruthy();
  expect(within(yours).queryByText(/Failed to fetch/)).toBeNull();
});

test("a rename with LADO's server gone says so under its field", async () => {
  server.entries = { models: [QWEN], servers: [LMSTUDIO] };
  mountPage();
  const yours = await table();
  serverStops();
  fireEvent.click(within(yours).getByRole("button", { name: "Rename Локальная Qwen" }));
  const name = within(yours).getByRole("textbox", { name: "Name of Локальная Qwen" });
  fireEvent.change(name, { target: { value: "Другая" } });
  fireEvent.keyDown(name, { key: "Enter" });
  expect(await within(yours).findByText(LADO_DOWN)).toBeTruthy();
});

test("a server's list with LADO's server gone blames no model server, and ↻ keeps the focus", async () => {
  server.entries = { models: [QWEN], servers: [LMSTUDIO] };
  server.probes[LMSTUDIO.name] = LMSTUDIO_PROBE;
  mountPage();
  fireEvent.click(await screen.findByRole("button", { name: LMSTUDIO.name }));
  const again = await screen.findByRole("button", { name: "Read the models again" });
  serverStops();
  again.focus();
  fireEvent.click(again);
  expect(await screen.findByText(`⚠ ${LADO_DOWN}`)).toBeTruthy();
  expect(screen.queryByText(/stays saved/)).toBeNull();
  await waitFor(() =>
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Read the models again" })),
  );
});

test("a model server's refusal says what it does, that its models stay saved, and ↻ keeps the focus", async () => {
  server.entries = { models: [QWEN], servers: [LMSTUDIO] };
  server.probes[LMSTUDIO.name] = LMSTUDIO_PROBE;
  mountPage();
  fireEvent.click(await screen.findByRole("button", { name: LMSTUDIO.name }));
  const again = await screen.findByRole("button", { name: "Read the models again" });
  server.probes[LMSTUDIO.name] = () => refusal(`${LMSTUDIO.address} does not answer (connection refused)`);
  again.focus();
  fireEvent.click(again);
  expect(await screen.findByText("⚠ Does not answer (connection refused)")).toBeTruthy();
  expect(
    screen.getByText("Its model stays saved; agents on it stop at their first turn until it answers."),
  ).toBeTruthy();
  await waitFor(() =>
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Read the models again" })),
  );
  // Your models marks its server too, the reason in its title.
  const from = within(await table()).getByText(`⚠ ${LMSTUDIO.name}`, { selector: ".mx-from" });
  expect(from.getAttribute("title")).toContain("does not answer (connection refused)");
});

test("↻ pressed while React still owes the first read's effects keeps the focus", async () => {
  server.entries = { models: [QWEN], servers: [LMSTUDIO] };
  server.probes[LMSTUDIO.name] = LMSTUDIO_PROBE;
  mountPage();
  // A slow machine: the scheduler's time slice is always over, so it yields between the commit
  // of the read and its effects, and the press below comes in between, as on a loaded runner.
  let now = 0;
  const clock = vi.spyOn(performance, "now").mockImplementation(() => (now += 100));
  const shown = new Promise<HTMLElement>((resolve) => {
    const seen = new MutationObserver(() => {
      const button = screen.queryByRole("button", { name: "Read the models again" });
      if (button) {
        seen.disconnect();
        resolve(button);
      }
    });
    seen.observe(document.body, { childList: true, subtree: true });
  });
  fireEvent.click(await screen.findByRole("button", { name: LMSTUDIO.name }));
  const again = await shown;
  server.probes[LMSTUDIO.name] = () => refusal("http://localhost:1234 does not answer (connection refused)");
  again.focus();
  fireEvent.click(again);
  clock.mockRestore();
  expect(await screen.findByText(/Its model stays saved/)).toBeTruthy();
  await waitFor(() =>
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Read the models again" })),
  );
});

test("a refused Undo keeps its button and the focus on it", async () => {
  server.entries = { models: [QWEN, CODER], servers: [LMSTUDIO] };
  mountPage();
  const yours = await table();
  fireEvent.click(within(yours).getByRole("button", { name: "Remove Рабочая Qwen" }));
  const undo = (await within(yours).findByRole("button", { name: "Undo" })) as HTMLButtonElement;
  await waitFor(() => expect(document.activeElement).toBe(undo));
  serverStops();
  fireEvent.click(undo);
  expect(undo.disabled).toBe(false); // a disabled button would drop the focus
  expect(await within(yours).findByText(LADO_DOWN)).toBeTruthy();
  expect(document.activeElement).toBe(undo);
  expect(undo.getAttribute("aria-disabled")).toBeNull();
});

test("Undo running out with the focus on it hands the focus to the table", async () => {
  server.entries = { models: [QWEN, CODER], servers: [LMSTUDIO] };
  mountPage();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const yours = await table();
  fireEvent.click(within(yours).getByRole("button", { name: "Remove Рабочая Qwen" }));
  const undo = await within(yours).findByRole("button", { name: "Undo" });
  await waitFor(() => expect(document.activeElement).toBe(undo));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(UNDO_MS + 10);
  });
  expect(within(yours).queryByRole("button", { name: "Undo" })).toBeNull();
  expect(document.activeElement).toBe(yours);
});

test("Undo running out with the focus elsewhere moves nothing", async () => {
  server.entries = { models: [QWEN, CODER], servers: [LMSTUDIO] };
  mountPage();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const yours = await table();
  fireEvent.click(within(yours).getByRole("button", { name: "Remove Рабочая Qwen" }));
  await within(yours).findByRole("button", { name: "Undo" });
  const elsewhere = screen.getByRole("button", { name: /Add server/ });
  elsewhere.focus();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(UNDO_MS + 10);
  });
  expect(document.activeElement).toBe(elsewhere);
});

test("a model renamed takes its place by name, the focus on it", async () => {
  const alpha = model("Alpha", "opencode", "OpenCode", "m-a");
  server.entries = { models: [alpha, QWEN, CODER], servers: [LMSTUDIO] };
  mountPage();
  const yours = await table();
  fireEvent.click(within(yours).getByRole("button", { name: "Rename Alpha" }));
  const name = within(yours).getByRole("textbox", { name: "Name of Alpha" });
  fireEvent.change(name, { target: { value: "я-последняя" } });
  fireEvent.keyDown(name, { key: "Enter" });
  const renamed = await within(yours).findByRole("button", { name: "Rename я-последняя" });
  await waitFor(() => expect(document.activeElement).toBe(renamed));
  const shown = within(yours)
    .getAllByRole("button", { name: /^Rename / })
    .map((b) => b.textContent);
  expect(shown).toEqual(["Локальная Qwen", "Рабочая Qwen", "я-последняя"]);
});

test("Remove server: Esc is Cancel, the focus back on its button", async () => {
  server.entries = { models: [QWEN], servers: [LMSTUDIO] };
  mountPage();
  await table();
  const remove = screen.getByRole("button", { name: `Remove ${LMSTUDIO.name}` });
  fireEvent.click(remove);
  const question = await screen.findByRole("alertdialog");
  fireEvent.keyDown(question, { key: "Escape" });
  expect(screen.queryByRole("alertdialog")).toBeNull();
  await waitFor(() => expect(document.activeElement).toBe(remove));
  fireEvent.click(remove);
  fireEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Cancel" }));
  await waitFor(() => expect(document.activeElement).toBe(remove));
});

test("a server removed: the focus goes to Add server", async () => {
  server.entries = { models: [], servers: [LMSTUDIO] };
  mountPage();
  fireEvent.click(await screen.findByRole("button", { name: `Remove ${LMSTUDIO.name}` }));
  const question = await screen.findByRole("alertdialog");
  const confirm = within(question).getByRole("button", { name: "Remove server" }) as HTMLButtonElement;
  await waitFor(() => expect(confirm.disabled).toBe(false));
  fireEvent.click(confirm);
  const add = await screen.findByRole("button", { name: /Add server/ });
  await waitFor(() => expect(document.activeElement).toBe(add));
});

test("a tick keeps the focus through its save and its removal", async () => {
  server.entries = { models: [QWEN], servers: [LMSTUDIO], defaults: [externalDefault(QWEN)] };
  server.probes[LMSTUDIO.name] = LMSTUDIO_PROBE;
  mountPage();
  await table();
  fireEvent.click(await screen.findByRole("button", { name: LMSTUDIO.name }));
  fireEvent.click(await screen.findByRole("button", { name: "qwen3-8b" }));
  const kilo = (await screen.findByRole("checkbox", { name: "qwen3-8b on Codex CLI" })) as HTMLInputElement;
  kilo.focus();
  fireEvent.click(kilo);
  expect(kilo.disabled).toBe(false); // a disabled box would drop the focus
  await waitFor(() => expect(kilo.checked).toBe(true));
  expect(document.activeElement).toBe(kilo);
  const tick = (await screen.findByRole("checkbox", { name: "qwen3-8b on OpenCode" })) as HTMLInputElement;
  tick.focus();
  fireEvent.click(tick);
  await waitFor(() => expect(tick.checked).toBe(false));
  await screen.findByRole("button", { name: "Undo" });
  expect(document.activeElement).toBe(tick);
});

test("From holds the server's name and address on hover", async () => {
  server.entries = { models: [QWEN], servers: [LMSTUDIO] };
  mountPage();
  const yours = await table();
  const from = within(yours).getByText("LM Studio дома", { selector: ".mx-from" });
  expect(from.getAttribute("title")).toBe(`LM Studio дома · ${LMSTUDIO.address}`);
});
