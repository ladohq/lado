// Team on its own (LaunchTeam.tsx): the one-line summary, Change and Hide, and Permissions in
// the agent CLI's words.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { createRef, useState, type ReactNode } from "react";
import { afterEach, expect, test } from "vitest";

import type { ProviderInfo } from "./api";
import { LaunchTeam } from "./LaunchTeam";

afterEach(cleanup);

const CODEX: ProviderInfo = {
  name: "codex",
  title: "Codex CLI",
  permission_modes: ["default", "bypassPermissions"],
  mode_words: [
    {
      value: "default",
      title: "Work inside this folder (recommended)",
      summary: "Works inside the folder",
      description: "Asks before going outside it.",
      risky: false,
    },
    {
      value: "bypassPermissions",
      title: "Full access, never ask ⚠",
      summary: "Full access ⚠",
      description: "No limits, outside this folder too.",
      risky: true,
    },
  ],
  install_hint: "",
  installed: true,
  version: "0.162.0",
  detail: "",
  tested_version: "",
  warning: "",
  login_missing: false,
  starts_on_server: false,
};

function Team({ info = CODEX, peek = null }: { info?: ProviderInfo; peek?: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState("default");
  return (
    <LaunchTeam
      open={open}
      onOpen={setOpen}
      about="As in the last session in this folder."
      modelPeek={peek}
      kits={["default"]}
      onKits={() => {}}
      known={[]}
      kitsError={null}
      providers={[info]}
      providersNote={null}
      chosen={info.name}
      info={info}
      onProvider={() => {}}
      agentNote={null}
      mode={mode}
      onMode={setMode}
      modeNote={null}
      modelField={null}
      without=""
      onWithout={() => {}}
      switchOff={[]}
      disabled={false}
      refs={{ agent: createRef(), kits: createRef() }}
    />
  );
}

const summary = () => document.querySelector(".team-sum")?.textContent;

test("the summary reads Kits, Agent, Permissions in the CLI's words, and a model off the default, no Name", () => {
  render(<Team peek={<span>Model kilo/large</span>} />);
  expect(summary()).toBe("Kits defaultAgent Codex CLIPermissions Works inside the folderModel kilo/large");
});

test("Kits says what kits are also when none has a description", () => {
  render(<Team />);
  fireEvent.click(screen.getByRole("button", { name: "Change" }));
  expect(screen.getByRole("group", { name: /^Kits/ })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "About Kits" }));
  expect(screen.getByText("Kits add roles, skills and ways of working to the team. Install more on the Kits page.")).toBeTruthy();
});

test("Change opens the fields and reads Hide; Hide folds them", () => {
  render(<Team />);
  fireEvent.click(screen.getByRole("button", { name: "Change" }));
  expect(screen.getByRole("combobox", { name: "Agent" })).toBeTruthy();
  expect(screen.queryByRole("textbox", { name: "Session name" })).toBeNull();
  expect(summary()).toBeUndefined();
  fireEvent.click(screen.getByRole("button", { name: "Hide" }));
  expect(screen.queryByRole("combobox", { name: "Agent" })).toBeNull();
});

test("the chosen mode and the risky one show their description; a pick changes the summary", () => {
  render(<Team />);
  fireEvent.click(screen.getByRole("button", { name: "Change" }));
  expect(screen.getByText("Asks before going outside it.")).toBeTruthy();
  expect(screen.getByText("No limits, outside this folder too.")).toBeTruthy();
  fireEvent.click(screen.getByRole("radio", { name: /^Full access/ }));
  fireEvent.click(screen.getByRole("button", { name: "Hide" }));
  expect(summary()).toContain("Permissions Full access ⚠");
});

test("an agent with no modes: No permission modes., and no Permissions in the summary", () => {
  render(<Team info={{ ...CODEX, permission_modes: [], mode_words: [] }} />);
  expect(summary()).not.toContain("Permissions");
  fireEvent.click(screen.getByRole("button", { name: "Change" }));
  expect(screen.getByText("No permission modes.")).toBeTruthy();
});

test("a CLI without its login is offered for its server's models only when it can start on one", () => {
  const option = (info: ProviderInfo) => {
    render(<Team info={info} />);
    fireEvent.click(screen.getByRole("button", { name: "Change" }));
    const found = screen.getByRole("combobox", { name: "Agent" }).querySelector("option[value=codex]") as HTMLOptionElement;
    const seen = [found.textContent, found.disabled];
    cleanup();
    return seen;
  };
  expect(option({ ...CODEX, login_missing: true, starts_on_server: true })).toEqual([
    "Codex CLI 0.162.0 · not logged in: your server's models only",
    false,
  ]);
  expect(option({ ...CODEX, login_missing: true })).toEqual(["Codex CLI · not logged in", true]);
  expect(option(CODEX)).toEqual(["Codex CLI 0.162.0", false]);
});
