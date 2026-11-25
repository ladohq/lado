// The guide's steps inside the real login sheet of Claude Code and Codex CLI.
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ProviderLogins } from "../api";
import { claudeRow, codexRow, LOGIN } from "../fakes";
import { LoginSheet } from "../LoginSheet";
import { cardTitle, INFO, publishLogins, Settings, showGuide } from "./harness";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const codexOut = () => codexRow({ login: { ...LOGIN, state: "no" }, logout_file: false });

function Row({ row }: { row: ProviderLogins }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <li data-guide={`cli-row-${row.cli.name}`}>
        {row.cli.title}{" "}
        <button type="button" onClick={() => setOpen(true)}>
          {`Log in to ${row.cli.title}`}
        </button>
      </li>
      {open && <LoginSheet row={row} onChanged={() => {}} onClose={() => setOpen(false)} />}
    </>
  );
}

function open(rows: ProviderLogins[] = [claudeRow(), codexOut()]) {
  const guide = showGuide("/settings/agent-clis", INFO, {
    pages: [
      {
        path: "/settings/agent-clis",
        element: (
          <Settings>
            <ul>
              {rows.map((row) => (
                <Row key={row.cli.name} row={row} />
              ))}
            </ul>
          </Settings>
        ),
      },
    ],
  });
  fireEvent.click(screen.getByRole("button", { name: "Show me" }));
  publishLogins(rows.map((row) => ({ name: row.cli.name })));
  return guide;
}

const titled = (title: string) => waitFor(() => expect(cardTitle()).toBe(title));
const sheet = () => screen.getByRole("dialog", { name: /How do you pay/ });
const choose = (name: RegExp) => fireEvent.click(within(sheet()).getByRole("radio", { name }));

describe("the login window's steps", () => {
  it("asks Claude Code's choice first, then the token or the key", async () => {
    open();
    await titled("Claude Pro or Max, or an Anthropic API key?");
    fireEvent.click(screen.getByRole("button", { name: "Log in to Claude Code" }));
    await titled("Which one do you have?");
    expect(document.querySelector(".gd-block")).toBeNull(); // the sheet's own backdrop is the dim
    choose(/Pay per use/);
    await titled("Paste your API key");
    choose(/Subscription/);
    await titled("Make a token with Claude Code");
    expect(document.querySelector(".gd-card code")?.textContent).toBe("claude setup-token");
  });

  it("points at Codex CLI's sign-in code, and at the field of any other paste choice", async () => {
    open([codexOut()]);
    await titled("A ChatGPT plan, or an OpenAI API key?");
    fireEvent.click(screen.getByRole("button", { name: "Log in to Codex CLI" }));
    await titled("Sign in with a one-time code");
    choose(/Pay per use/);
    await titled("Paste it and press Save");
    choose(/access token/);
    await titled("Paste it and press Save");
  });

  it("says a refused value did not work, at the refusal line", async () => {
    open();
    await titled("Claude Pro or Max, or an Anthropic API key?");
    fireEvent.click(screen.getByRole("button", { name: "Log in to Claude Code" }));
    choose(/Pay per use/);
    await titled("Paste your API key");
    const guide = vi.mocked(fetch).getMockImplementation()!;
    vi.mocked(fetch).mockImplementation(async (path, init) =>
      String(path).includes("/variables/")
        ? new Response(JSON.stringify({ detail: "This is not an API key: it starts with sk-ant-oat01-" }), { status: 400 })
        : guide(path, init),
    );
    const field = within(sheet()).getByLabelText("ANTHROPIC_API_KEY");
    fireEvent.change(field, { target: { value: "sk-ant-oat01-x" } });
    fireEvent.input(field, { target: { value: "sk-ant-oat01-x" } });
    fireEvent.click(within(sheet()).getByRole("button", { name: "Save" }));
    await titled("That didn't work yet");
  });

  it("passes the row of a window closed without a login: the next row is the step", async () => {
    open();
    await titled("Claude Pro or Max, or an Anthropic API key?");
    fireEvent.click(screen.getByRole("button", { name: "Log in to Claude Code" }));
    await titled("Which one do you have?");
    publishLogins([{ name: "claude" }, { name: "codex" }], true); // the page checks again on close
    fireEvent.click(within(sheet()).getByRole("button", { name: "Close" }));
    publishLogins([{ name: "claude" }, { name: "codex" }]);
    await titled("A ChatGPT plan, or an OpenAI API key?");
  });
});
