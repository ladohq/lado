import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, test, vi } from "vitest";

import type { CliDefault, ConfiguredModelInfo, ModelChoices } from "./api";
import { type Health, ModelPicker, type ModelRead, type Pick, useModelChoices } from "./ModelPicker";
import { model } from "./modelFakes";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const CHECK = { kind: "default", text: "", field: "", name: "" } as const;
const OPENCODE = { name: "opencode", title: "OpenCode" };
const CLAUDE = { name: "claude", title: "Claude Code" };
const QWEN = model("Локальная Qwen", "opencode", "OpenCode", "qwen3-8b", "LM Studio дома");
const CODER = model("Рабочая Qwen", "opencode", "OpenCode", "qwen3-coder-30b", "LM Studio дома");

const choices = (given: Partial<ModelChoices> = {}): ModelChoices => ({
  aliases: [],
  models: ["a/one", "b/two"],
  why: "",
  external: [],
  other_name: false,
  whole_process: false,
  read_again: true,
  check: CHECK,
  ...given,
});

const list = (given: Partial<ModelRead> = {}): ModelRead => ({
  choices: choices(),
  checked: "",
  reading: false,
  problem: null,
  read: vi.fn(),
  ...given,
});

const builtin = (name: string): CliDefault => ({
  cli: "opencode",
  external: null,
  builtin: name,
  name,
  model: name,
  server: null,
  whole_process: false,
});

const external = (saved: ConfiguredModelInfo): CliDefault => ({
  cli: saved.cli,
  external: saved.id,
  builtin: null,
  name: saved.name,
  model: saved.model,
  server: saved.server,
  whole_process: false,
});

type Given = {
  cli?: { name: string; title: string };
  value?: CliDefault | null;
  own?: ConfiguredModelInfo[];
  read?: ModelRead;
  off?: boolean;
  lost?: boolean;
  health?: Record<string, Health>;
  where?: "settings" | "launch";
  fieldMark?: string | null;
};

function mount(first: Given = {}) {
  const onPick = vi.fn<(pick: Pick) => void>();
  const onOther = vi.fn<(text: string) => void>();
  const onOpen = vi.fn();
  const cli = first.cli ?? OPENCODE;
  const where = first.where ?? "settings";
  const element = (more: Given) => {
    const given = { ...first, ...more };
    const own = given.own ?? [];
    const read = given.read ?? list();
    if (read.choices) read.choices = { ...read.choices, external: own }; // the core's list agrees
    return (
      <>
        {where === "launch" && <label htmlFor="model-field">Model</label>}
        <ModelPicker
          cli={cli}
          value={given.value ?? null}
          where={where}
          own={own}
          list={read}
          off={given.off ?? false}
          lost={given.lost ?? false}
          health={given.health ?? {}}
          fieldId="model-field"
          fieldMark={given.fieldMark ?? null}
          onOpen={onOpen}
          onPick={onPick}
          onOther={onOther}
        />
      </>
    );
  };
  const { rerender } = render(element({}));
  const name = where === "launch" ? "Model" : `Default model of ${cli.title}`;
  const field = screen.getByRole("combobox", { name });
  return { field, onPick, onOther, onOpen, rerender: (more: Given) => rerender(element(more)) };
}

const texts = () =>
  within(screen.getByRole("listbox"))
    .getAllByRole("option")
    .map((row) => row.textContent);
const groups = () =>
  within(screen.getByRole("listbox"))
    .getAllByRole("group")
    .map((group) => group.getAttribute("aria-label"));

test("the rows: the CLI's settings, your models, built-in, each empty group left out", () => {
  const { field, onOpen } = mount({ own: [QWEN] });
  fireEvent.click(field);
  expect(onOpen).toHaveBeenCalledOnce();
  expect(groups()).toEqual(["YOUR MODELS", "BUILT-IN"]);
  const rows = texts();
  expect(rows[0]).toContain("OpenCode's settings");
  expect(rows[0]).toContain("no model set: the agent CLI chooses");
  expect(rows[1]).toContain("Локальная Qwen");
  expect(rows[1]).toContain("qwen3-8b");
  expect(rows[1]).toContain("LM Studio дома");
  expect(rows.slice(2)).toEqual(["a/one", "b/two"]);
  cleanup();
  fireEvent.click(mount().field);
  expect(groups()).toEqual(["BUILT-IN"]);
});

test("opening it reads the list now, for the built-in model on the field", () => {
  const read = list();
  fireEvent.click(mount({ read, value: builtin("a/one") }).field);
  expect(read.read).toHaveBeenCalledWith(true, "a/one");
});

test("aliases head their group, and an other name is offered only without a full list", () => {
  const read = list({ choices: choices({ aliases: ["opus"], models: null, other_name: true, read_again: false }) });
  fireEvent.click(mount({ cli: CLAUDE, read }).field);
  expect(groups()).toEqual(["BUILT-IN · aliases"]);
  expect(texts().at(-1)).toContain("Other name…");
  expect(screen.queryByRole("button", { name: "Read the models again" })).toBeNull();
  expect(screen.getByRole("status").textContent).toContain("1 aliases · 0 of yours");
  cleanup();
  fireEvent.click(mount().field);
  expect(texts().join(" ")).not.toContain("Other name");
});

test("YOUR MODELS come from the core's list once read, the page's only while it reads", () => {
  const props = {
    cli: OPENCODE,
    value: null,
    where: "settings" as const,
    own: [QWEN], // what the page last read
    off: false,
    lost: false,
    health: {},
    onOpen: vi.fn(),
    onPick: vi.fn(),
    onOther: vi.fn(),
  };
  const read = list({ choices: choices({ external: [CODER] }) });
  const view = render(<ModelPicker {...props} list={read} />);
  fireEvent.click(screen.getByRole("combobox"));
  expect(texts().join(" ")).toContain("Рабочая Qwen");
  expect(texts().join(" ")).not.toContain("Локальная Qwen");
  view.rerender(<ModelPicker {...props} list={{ ...read, reading: true }} />);
  expect(texts().join(" ")).toContain("Локальная Qwen");
  expect(texts().join(" ")).not.toContain("Рабочая Qwen");
});

test("a list being read shows your models and says so", () => {
  const read = list({ choices: null, reading: true });
  fireEvent.click(mount({ read, own: [QWEN] }).field);
  expect(texts().join(" ")).toContain("Локальная Qwen");
  expect(screen.getByRole("status").textContent).toContain("reading the models…");
});

test("a list that cannot be read says why, with Read again and an other name", () => {
  const why = "`kilo models` timed out after 15 s";
  const read = list({ choices: choices({ models: null, why, other_name: true }) });
  fireEvent.click(mount({ read, own: [QWEN] }).field);
  expect(screen.getByText(`⚠ ${why}`)).toBeTruthy();
  expect(texts().join(" ")).toContain("Локальная Qwen");
  expect(texts().at(-1)).toContain("Other name…");
  fireEvent.click(screen.getByRole("option", { name: "Read again" }));
  expect(read.read).toHaveBeenLastCalledWith(true, "");
  expect(screen.getByRole("listbox")).toBeTruthy(); // reading again closes nothing
});

test("Read again is a row the keyboard reaches, and it picks nothing", () => {
  const read = list({ choices: choices({ models: null, why: "timed out", other_name: true }) });
  const { field, onPick, onOther } = mount({ read });
  fireEvent.keyDown(field, { key: "Enter" });
  fireEvent.keyDown(field, { key: "ArrowDown" });
  const active = document.getElementById(field.getAttribute("aria-activedescendant") ?? "");
  expect(active?.textContent).toContain("Read again");
  fireEvent.keyDown(field, { key: "Enter" });
  expect(read.read).toHaveBeenLastCalledWith(true, "");
  expect(screen.getByRole("listbox")).toBeTruthy();
  expect(onPick).not.toHaveBeenCalled();
  expect(onOther).not.toHaveBeenCalled();
});

test("a press inside the list takes no focus from the field or the search", () => {
  const { field } = mount();
  fireEvent.click(field);
  field.focus();
  expect(fireEvent.mouseDown(screen.getByRole("option", { name: "a/one" }))).toBe(false);
  expect(fireEvent.mouseDown(screen.getByRole("button", { name: "Read the models again" }))).toBe(false);
});

test("a press in the search keeps its caret", () => {
  fireEvent.click(mount({ read: list({ choices: choices({ models: many(11) }) }) }).field);
  expect(fireEvent.mouseDown(screen.getByPlaceholderText(/^Search/))).toBe(true);
});

test("a list read anew puts the active row back on the selected one: Enter never hits another", () => {
  const props = {
    cli: OPENCODE,
    value: null,
    where: "settings" as const,
    own: [],
    off: false,
    lost: false,
    health: {},
    onOpen: vi.fn(),
    onPick: vi.fn(),
    onOther: vi.fn(),
  };
  const view = render(<ModelPicker {...props} list={list({ choices: choices({ models: ["a", "b", "c"] }) })} />);
  const field = screen.getByRole("combobox");
  fireEvent.click(field);
  fireEvent.keyDown(field, { key: "End" }); // `c`, the fourth row
  const none = choices({ models: null, why: "timed out", other_name: true });
  view.rerender(<ModelPicker {...props} list={list({ choices: none })} />); // now the fourth is none
  fireEvent.keyDown(field, { key: "Enter" });
  expect(props.onOther).not.toHaveBeenCalled();
  expect(props.onPick).toHaveBeenCalledWith(null); // the selected row: the CLI's settings
});

test("a list no reading can bring has no Read again", () => {
  const why = "Codex CLI gives no list of models for the model provider `azure`";
  const read = list({ choices: choices({ models: null, why, other_name: true, read_again: false }) });
  fireEvent.click(mount({ read }).field);
  expect(screen.getByText(`⚠ ${why}`)).toBeTruthy();
  expect(screen.queryByRole("option", { name: "Read again" })).toBeNull();
});

test("a request that did not reach LADO says so in its own words, with Read again", () => {
  const read = list({ choices: null, problem: "LADO's server does not answer: the list was not read." });
  fireEvent.click(mount({ read, own: [QWEN] }).field);
  expect(screen.getByText("⚠ LADO's server does not answer: the list was not read.")).toBeTruthy();
  expect(screen.getByRole("option", { name: "Read again" })).toBeTruthy();
  expect(texts().join(" ")).not.toContain("not answering");
});

test("the whole-process line stands above your models by the provider's word", () => {
  const line = "On OpenCode a server's model takes the whole process: the agent runs only on that server.";
  fireEvent.click(mount({ read: list({ choices: choices({ whole_process: true }) }), own: [QWEN] }).field);
  expect(screen.getByText(line)).toBeTruthy();
  cleanup();
  fireEvent.click(mount({ own: [QWEN] }).field);
  expect(screen.queryByText(line)).toBeNull();
});

const many = (n: number) => Array.from({ length: n }, (_, i) => `vendor/model-${i}`);

test("no search up to ten models, yours counted; a search above", () => {
  fireEvent.click(mount({ read: list({ choices: choices({ models: many(9) }) }), own: [QWEN] }).field);
  expect(screen.queryByPlaceholderText(/^Search/)).toBeNull();
  cleanup();
  fireEvent.click(mount({ read: list({ choices: choices({ models: many(10) }) }), own: [QWEN] }).field);
  expect(screen.getByPlaceholderText("Search 11 models")).toBeTruthy();
});

test("a search finds by name, id and server, hides the settings row and counts", () => {
  const read = list({ choices: choices({ models: ["qwen/qwen3-max", ...many(10)] }) });
  fireEvent.click(mount({ read, own: [QWEN, CODER] }).field);
  const search = screen.getByPlaceholderText("Search 13 models");
  fireEvent.change(search, { target: { value: "РАБОЧАЯ" } });
  expect(texts()).toHaveLength(1);
  expect(texts()[0]).toContain("Рабочая Qwen");
  fireEvent.change(search, { target: { value: "lm studio" } });
  expect(texts()).toHaveLength(2);
  fireEvent.change(search, { target: { value: "qwen3-m" } });
  expect(texts()).toEqual(["qwen/qwen3-max"]);
  expect(screen.getByRole("status").textContent).toContain("1 of 13");
  fireEvent.change(search, { target: { value: "gpt-9" } });
  expect(screen.getByText("No model matches “gpt-9”.")).toBeTruthy();
});

test("an other name stays while searching and takes the search's text", () => {
  const read = list({ choices: choices({ models: null, aliases: many(12), other_name: true, read_again: false }) });
  const { field, onOther } = mount({ cli: CLAUDE, read });
  fireEvent.click(field);
  fireEvent.change(screen.getByPlaceholderText(/^Search/), { target: { value: "claude-opus-4-1" } });
  fireEvent.click(screen.getByRole("option", { name: /Other name…/ }));
  expect(onOther).toHaveBeenCalledWith("claude-opus-4-1");
  expect(screen.queryByRole("listbox")).toBeNull();
});

test("a pick says what was picked and hands the focus back", () => {
  const { field, onPick } = mount({ own: [QWEN] });
  fireEvent.click(field);
  fireEvent.click(screen.getByRole("option", { name: /Локальная Qwen/ }));
  expect(onPick).toHaveBeenLastCalledWith({ external: QWEN.id });
  expect(screen.queryByRole("listbox")).toBeNull();
  expect(document.activeElement).toBe(field);
  fireEvent.click(field);
  fireEvent.click(screen.getByRole("option", { name: "a/one" }));
  expect(onPick).toHaveBeenLastCalledWith({ builtin: "a/one" });
  fireEvent.click(field);
  fireEvent.click(screen.getByRole("option", { name: /OpenCode's settings/ }));
  expect(onPick).toHaveBeenLastCalledWith(null);
});

test("the field shows its value: settings, a built-in id, a name with its id and server", () => {
  const { field } = mount();
  expect(field.textContent).toContain("OpenCode's settings");
  cleanup();
  expect(mount({ value: builtin("a/one") }).field.textContent).toContain("a/one");
  cleanup();
  const shown = mount({ value: external(QWEN), own: [QWEN] }).field.textContent;
  for (const part of ["Локальная Qwen", "qwen3-8b", "LM Studio дома"]) expect(shown).toContain(part);
});

test("the selected row is marked, and an other name heads the built-in models", () => {
  const read = list({ choices: choices({ aliases: ["opus"], models: null, other_name: true, read_again: false }) });
  fireEvent.click(mount({ cli: CLAUDE, read, value: builtin("claude-x") }).field);
  const rows = within(screen.getByRole("listbox")).getAllByRole("option");
  expect(rows[1].textContent).toContain("claude-x");
  expect(rows[1].textContent).toContain("other name");
  expect(rows[1].getAttribute("aria-selected")).toBe("true");
  expect(rows[0].getAttribute("aria-selected")).toBe("false");
});

test("a built-in default the list lost shows on the field and heads the list", () => {
  const { field } = mount({ value: builtin("old/model"), lost: true });
  expect(field.textContent).toContain("⚠ no longer listed");
  fireEvent.click(field);
  const rows = within(screen.getByRole("listbox")).getAllByRole("option");
  expect(rows[1].textContent).toContain("old/model");
  expect(rows[1].textContent).toContain("no longer listed");
});

test("a server's state marks its rows and the field", () => {
  const health = { "lm studio дома": { down: "does not answer" } };
  const { field } = mount({ value: external(QWEN), own: [QWEN, CODER], health });
  expect(field.querySelector(".srv.down")).toBeTruthy();
  fireEvent.click(field);
  expect(texts()[1]).toContain("not answering");
  expect(texts()[2]).toContain("not answering");
  cleanup();
  const listing = { "lm studio дома": { models: ["qwen3-8b"] } };
  fireEvent.click(mount({ own: [QWEN, CODER], health: listing }).field);
  expect(texts()[1]).not.toContain("not on the server");
  expect(texts()[2]).toContain("not on the server");
});

test("a server's name past 24 characters goes under the id in its row", () => {
  const long = model("Длинная", "opencode", "OpenCode", "m", "LM Studio дома на втором компьютере");
  fireEvent.click(mount({ own: [QWEN, long] }).field);
  expect(screen.getByRole("option", { name: /Длинная/ }).className).toContain("mp-long");
  expect(screen.getByRole("option", { name: /Локальная Qwen/ }).className).not.toContain("mp-long");
});

test("a field that is off shows its value and does not open", () => {
  const { field } = mount({ off: true, value: builtin("a/one") });
  expect((field as HTMLButtonElement).disabled).toBe(true);
  expect(field.textContent).toContain("a/one");
  fireEvent.click(field);
  expect(screen.queryByRole("listbox")).toBeNull();
});

test("the keyboard without a search: opens on the selected row, moves, picks", () => {
  const { field, onPick } = mount({ value: builtin("a/one") });
  field.focus();
  fireEvent.keyDown(field, { key: "ArrowDown" });
  const active = () => document.getElementById(field.getAttribute("aria-activedescendant") ?? "")?.textContent;
  expect(active()).toContain("a/one");
  fireEvent.keyDown(field, { key: "ArrowDown" });
  expect(active()).toBe("b/two");
  fireEvent.keyDown(field, { key: "Home" });
  expect(active()).toContain("OpenCode's settings");
  fireEvent.keyDown(field, { key: "End" });
  expect(active()).toBe("b/two");
  fireEvent.keyDown(field, { key: " " });
  expect(onPick).toHaveBeenCalledWith({ builtin: "b/two" });
  expect(screen.queryByRole("listbox")).toBeNull();
});

test("Esc and Tab close without a pick", () => {
  const { field, onPick } = mount({ read: list({ choices: choices({ read_again: false }) }) });
  fireEvent.keyDown(field, { key: "Enter" });
  fireEvent.keyDown(field, { key: "ArrowDown" });
  fireEvent.keyDown(field, { key: "Escape" });
  expect(screen.queryByRole("listbox")).toBeNull();
  expect(document.activeElement).toBe(field);
  fireEvent.keyDown(field, { key: "Enter" });
  fireEvent.keyDown(field, { key: "Tab" }); // nothing in the foot to go to
  expect(screen.queryByRole("listbox")).toBeNull();
  expect(onPick).not.toHaveBeenCalled();
});

test("Tab goes into the list's foot, on past its last control the list closes", () => {
  const { field } = mount();
  fireEvent.keyDown(field, { key: "Enter" });
  fireEvent.keyDown(field, { key: "Tab" });
  const refresh = screen.getByRole("button", { name: "Read the models again" });
  expect(document.activeElement).toBe(refresh);
  fireEvent.keyDown(refresh, { key: "Tab" });
  expect(screen.queryByRole("listbox")).toBeNull();
  expect(document.activeElement).toBe(field); // the browser's Tab goes on from there
});

test("Shift+Tab goes back out of the foot, Esc there closes the list", () => {
  const { field } = mount({ read: list({ choices: choices({ models: many(11) }) }) });
  fireEvent.click(field);
  const search = screen.getByPlaceholderText(/^Search/);
  fireEvent.keyDown(search, { key: "Tab" });
  const refresh = screen.getByRole("button", { name: "Read the models again" });
  expect(document.activeElement).toBe(refresh);
  fireEvent.keyDown(refresh, { key: "Tab", shiftKey: true });
  expect(document.activeElement).toBe(search);
  fireEvent.keyDown(search, { key: "Tab" });
  fireEvent.keyDown(refresh, { key: "Escape" });
  expect(screen.queryByRole("listbox")).toBeNull();
  expect(document.activeElement).toBe(field);
});

test("in the launch window Tab reaches the link, then the button of the foot", () => {
  const { field } = mount({ where: "launch" });
  fireEvent.keyDown(field, { key: "Enter" });
  fireEvent.keyDown(field, { key: "Tab" });
  const link = screen.getByRole("link", { name: "Settings → Agent CLIs" });
  expect(document.activeElement).toBe(link);
  fireEvent.keyDown(link, { key: "Tab" }); // not the last: the browser goes on
  expect(screen.getByRole("listbox")).toBeTruthy();
});

test("the foot stays while a list already read is read again, with the focus in it", () => {
  const { field, rerender } = mount();
  fireEvent.keyDown(field, { key: "Enter" });
  fireEvent.keyDown(field, { key: "Tab" });
  const refresh = screen.getByRole("button", { name: "Read the models again" });
  rerender({ read: list({ reading: true }) });
  expect(document.activeElement).toBe(refresh);
});

test("a read that takes ↻ away hands the focus back to the list", () => {
  const { field, rerender } = mount();
  fireEvent.keyDown(field, { key: "Enter" });
  fireEvent.keyDown(field, { key: "Tab" });
  rerender({ read: list({ choices: choices({ read_again: false }) }) });
  expect(document.activeElement).toBe(field);
  fireEvent.keyDown(field, { key: "Escape" });
  expect(screen.queryByRole("listbox")).toBeNull();
});

test("the search stands while the list is first read, and keeps what was typed", () => {
  const { field, rerender } = mount({ read: list({ choices: null, reading: true }) });
  fireEvent.click(field);
  const search = screen.getByPlaceholderText(/^Search/) as HTMLInputElement;
  expect(document.activeElement).toBe(search);
  fireEvent.change(search, { target: { value: "model-1" } });
  rerender({ read: list({ choices: choices({ models: many(11) }) }) });
  expect((screen.getByPlaceholderText(/^Search/) as HTMLInputElement).value).toBe("model-1");
  expect(document.activeElement).toBe(screen.getByPlaceholderText(/^Search/));
});

test("while the list is read the search counts nothing", () => {
  const { field, rerender } = mount({ read: list({ choices: null, reading: true }) });
  fireEvent.click(field);
  expect(screen.getByRole("combobox", { name: "Search models" })).toBeTruthy();
  rerender({ read: list({ choices: choices({ models: many(11) }) }) });
  expect(screen.getByRole("combobox", { name: "Search 11 models" })).toBeTruthy();
});

test("Shift+Tab in the search closes the list with the focus on the field", () => {
  const { field } = mount({ read: list({ choices: choices({ models: many(11) }) }) });
  fireEvent.click(field);
  // Prevented: the browser's own Shift+Tab would go on from the field, past it.
  const browsers = fireEvent.keyDown(screen.getByPlaceholderText(/^Search/), { key: "Tab", shiftKey: true });
  expect(browsers).toBe(false);
  expect(screen.queryByRole("listbox")).toBeNull();
  expect(document.activeElement).toBe(field);
});

test("a short list read after the search hands the focus back to the field", () => {
  const { field, rerender } = mount({ read: list({ choices: null, reading: true }) });
  fireEvent.click(field);
  rerender({ read: list() });
  expect(screen.queryByPlaceholderText(/^Search/)).toBeNull();
  expect(document.activeElement).toBe(field);
});

test("a kept model no longer saved stands above the groups, marked, in no group", () => {
  const { field, onPick } = mount({
    where: "launch",
    value: builtin("Удалённая Qwen"),
    fieldMark: "not in Settings",
  });
  fireEvent.click(field);
  const row = screen.getByRole("option", { name: "Удалённая Qwen" });
  expect(row.textContent).toContain("not in Settings");
  expect(row.closest("[role=group]")).toBeNull();
  expect(row.getAttribute("aria-selected")).toBe("true");
  expect(field.querySelector(".mp-title")!.classList.contains("mono")).toBe(false);
  fireEvent.click(row);
  expect(screen.queryByRole("listbox")).toBeNull();
  expect(onPick).not.toHaveBeenCalled();
});

test("Esc in a search first clears it, then closes with the focus on the field", () => {
  const { field } = mount({ read: list({ choices: choices({ models: many(11) }) }) });
  fireEvent.click(field);
  const search = screen.getByPlaceholderText(/^Search/) as HTMLInputElement;
  expect(document.activeElement).toBe(search);
  fireEvent.change(search, { target: { value: "model-1" } });
  fireEvent.keyDown(search, { key: "Escape" });
  expect(search.value).toBe("");
  expect(screen.getByRole("listbox")).toBeTruthy();
  fireEvent.keyDown(search, { key: "Escape" });
  expect(screen.queryByRole("listbox")).toBeNull();
  expect(document.activeElement).toBe(field);
});

test("Enter in a search picks the row moved to", () => {
  const { field, onPick } = mount({ read: list({ choices: choices({ models: many(11) }) }) });
  fireEvent.click(field);
  const search = screen.getByPlaceholderText(/^Search/);
  fireEvent.change(search, { target: { value: "model-10" } });
  fireEvent.keyDown(search, { key: "ArrowDown" });
  fireEvent.keyDown(search, { key: "Enter" });
  expect(onPick).toHaveBeenCalledWith({ builtin: "vendor/model-10" });
});

test("a click outside closes it without a pick, the focus back on the field", async () => {
  const { field, onPick } = mount({ read: list({ choices: choices({ models: many(11) }) }) });
  fireEvent.click(field);
  fireEvent.pointerDown(document.body);
  (document.activeElement as HTMLElement).blur(); // as the press on nothing does
  expect(screen.queryByRole("listbox")).toBeNull();
  expect(onPick).not.toHaveBeenCalled();
  await waitFor(() => expect(document.activeElement).toBe(field));
});

test("a click outside on something that takes the focus leaves it there", async () => {
  const { field } = mount();
  const other = document.body.appendChild(document.createElement("button"));
  fireEvent.click(field);
  fireEvent.pointerDown(other);
  other.focus();
  await new Promise((done) => setTimeout(done, 5));
  expect(document.activeElement).toBe(other);
  other.remove();
});

test("Tab in a search with nothing in the foot closes it through the field", () => {
  const read = list({ choices: choices({ models: many(11), read_again: false }) });
  const { field } = mount({ read });
  fireEvent.click(field);
  fireEvent.keyDown(screen.getByPlaceholderText(/^Search/), { key: "Tab" });
  expect(screen.queryByRole("listbox")).toBeNull();
  expect(document.activeElement).toBe(field);
});

const placed = (top: number, bottom: number) =>
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
    top,
    bottom,
    left: 100,
    right: 500,
    width: 400,
    height: bottom - top,
    x: 100,
    y: top,
    toJSON: () => ({}),
  });

test("it lies over the page by the field, opening down", () => {
  placed(100, 138);
  vi.stubGlobal("innerHeight", 800);
  fireEvent.click(mount().field);
  const pop = document.querySelector(".mp-pop") as HTMLElement;
  expect(pop.style.position).toBe("fixed");
  expect(pop.style.top).toBe("142px");
  expect(pop.style.maxHeight).toBe("420px");
});

test("near the window's end it opens upward", () => {
  placed(700, 738);
  vi.stubGlobal("innerHeight", 800);
  fireEvent.click(mount().field);
  const pop = document.querySelector(".mp-pop") as HTMLElement;
  expect(pop.style.bottom).toBe("104px");
  expect(pop.style.top).toBe("");
});

test("a wheel outside the list closes it, one inside does not", () => {
  const { field } = mount({ read: list({ choices: choices({ models: many(11) }) }) });
  fireEvent.click(field);
  fireEvent.wheel(screen.getByRole("listbox"));
  expect(screen.getByRole("listbox")).toBeTruthy();
  fireEvent.wheel(document.body);
  expect(screen.queryByRole("listbox")).toBeNull();
  expect(document.activeElement).toBe(field);
});

test("useModelChoices drops an answer older than the last read", async () => {
  const answers: ((value: Response) => void)[] = [];
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((resolve) => answers.push(resolve))));
  function Reader() {
    const read = useModelChoices("kilo");
    const [count] = useState(0);
    return (
      <button type="button" data-count={count} onClick={() => read.read(true, "")}>
        {read.choices?.models?.join(" ") ?? "none"}
      </button>
    );
  }
  render(<Reader />);
  const button = screen.getByRole("button");
  fireEvent.click(button);
  fireEvent.click(button);
  await act(async () => {
    answers[1](new Response(JSON.stringify(choices({ models: ["new"] }))));
  });
  await waitFor(() => expect(button.textContent).toBe("new"));
  await act(async () => {
    answers[0](new Response(JSON.stringify(choices({ models: ["old"] }))));
  });
  expect(button.textContent).toBe("new");
});
