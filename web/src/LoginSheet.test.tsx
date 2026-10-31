import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { ProviderLogins } from "./api";
import { claudeRow as claude, FakeSocket, FakeXterm, lastSocket, LOGIN, opencodeRow as opencode } from "./fakes";
import { LoginSheet } from "./LoginSheet";
import { KEYS, LoginWindow } from "./LoginWindow";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));
const links: { loaded: number } = { loaded: 0 };
vi.mock("@xterm/addon-web-links", () => ({
  WebLinksAddon: class {
    constructor() {
      links.loaded += 1;
    }
    activate() {}
  },
}));

let calls: { method: string; path: string; body: unknown }[];
let answer: () => Response;

beforeEach(() => {
  FakeSocket.all = [];
  FakeXterm.all = [];
  links.loaded = 0;
  calls = [];
  answer = () => new Response(JSON.stringify(claude()), { status: 200 });
  vi.stubGlobal("WebSocket", FakeSocket);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ method, path, body });
      return answer();
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function sheet(row: ProviderLogins) {
  const changed = vi.fn();
  const closed = vi.fn();
  render(<LoginSheet row={row} onChanged={changed} onClose={closed} />);
  return { changed, closed };
}

const TOKEN_LOGIN = {
  ...LOGIN,
  state: "yes" as const,
  method: "Subscription (token)",
  where: "LADO's secret",
  choice: "subscription",
};

test("Claude Code's sheet asks how the human pays, the current one marked", () => {
  sheet(claude({ login: TOKEN_LOGIN, from_lado: true }));
  const dialog = screen.getByRole("dialog", { name: "How do you pay for Claude?" });
  const subscription = within(dialog).getByRole("radio", { name: /Subscription — Claude Pro or Max/ });
  expect((subscription as HTMLInputElement).checked).toBe(true);
  expect(within(dialog).getByText("current")).toBeTruthy();
  expect(within(dialog).getByText("claude setup-token").tagName).toBe("CODE");
  // The chosen one's field only; no login command runs.
  expect(within(dialog).getAllByRole("textbox")).toHaveLength(1);
  expect(within(dialog).getByLabelText("CLAUDE_CODE_OAUTH_TOKEN")).toBeTruthy();
  expect(FakeSocket.all).toEqual([]);
  expect(calls).toEqual([]);
});

test("without a login the first choice is chosen and nothing is marked current", () => {
  sheet(claude());
  expect((screen.getByRole("radio", { name: /Subscription/ }) as HTMLInputElement).checked).toBe(true);
  expect(screen.queryByText("current")).toBeNull();
  expect(screen.queryByRole("button", { name: "Log out…" })).toBeNull();
});

test("a key is sent in the body once under its choice's variable, never shown", async () => {
  const { changed, closed } = sheet(claude());
  fireEvent.click(screen.getByRole("radio", { name: /Pay per use — API billing/ }));
  expect(screen.queryByLabelText("CLAUDE_CODE_OAUTH_TOKEN")).toBeNull();
  const field = screen.getByLabelText("ANTHROPIC_API_KEY") as HTMLInputElement;
  const save = screen.getByRole("button", { name: "Save" });
  expect((save as HTMLButtonElement).disabled).toBe(true); // nothing to save yet
  fireEvent.change(field, { target: { value: "canary-key" } });
  fireEvent.click(save);
  await waitFor(() => expect(closed).toHaveBeenCalled());
  expect(calls).toEqual([
    { method: "PUT", path: "/api/providers/claude/variables/ANTHROPIC_API_KEY", body: { value: "canary-key" } },
  ]);
  expect(changed).toHaveBeenCalledWith(claude());
  expect(document.body.textContent).not.toContain("canary-key");
});

test("a refused value is said and the sheet stays", async () => {
  answer = () => new Response(JSON.stringify({ detail: "the value is larger than 64 KiB" }), { status: 400 });
  const { closed } = sheet(claude());
  fireEvent.change(screen.getByLabelText("CLAUDE_CODE_OAUTH_TOKEN"), { target: { value: "x" } });
  fireEvent.keyDown(screen.getByLabelText("CLAUDE_CODE_OAUTH_TOKEN"), { key: "Enter" });
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "the value is larger than 64 KiB");
  expect(closed).not.toHaveBeenCalled();
});

test("Log out asks first, naming the running agents, then removes LADO's login", async () => {
  const { closed } = sheet(claude({ login: TOKEN_LOGIN, from_lado: true }));
  fireEvent.click(screen.getByRole("button", { name: "Log out…" }));
  const ask = screen.getByRole("group", { name: "Remove this login from LADO's secrets?" });
  expect(ask.textContent).toContain(
    "supervisor of my-app, developer of my-app keep it until they start again; new agents go without it",
  );
  expect(calls).toEqual([]);
  fireEvent.click(within(ask).getByRole("button", { name: "Log out" }));
  await waitFor(() => expect(closed).toHaveBeenCalled());
  expect(calls).toEqual([{ method: "DELETE", path: "/api/providers/claude/login-secrets", body: undefined }]);
});

test("Log out names one running agent in the singular", () => {
  sheet(claude({ login: TOKEN_LOGIN, from_lado: true, running: [{ session: "my-app", agent: "supervisor" }] }));
  fireEvent.click(screen.getByRole("button", { name: "Log out…" }));
  expect(screen.getByRole("group").textContent).toContain(
    "supervisor of my-app keeps it until it starts again; new agents go without it",
  );
});

test("no Log out for a login of another layer", () => {
  sheet(claude({ login: { ...TOKEN_LOGIN, where: "outside folder" }, from_lado: false }));
  expect(screen.queryByRole("button", { name: "Log out…" })).toBeNull();
});

test("OpenCode's sheet opens its own login window at once, with Log out of one… when logged in", async () => {
  answer = () => new Response(JSON.stringify(opencode()), { status: 200 });
  const { closed } = sheet(opencode());
  await screen.findByLabelText("Text to send"); // the terminal's window, after "opening…"
  const window_ = screen.getByRole("dialog", { name: "Log in: OpenCode" });
  expect(calls[0]).toEqual({ method: "POST", path: "/api/providers/opencode/login", body: { action: "login" } });
  expect(lastSocket().url).toBe("ws://localhost:3000/api/providers/opencode/login/terminal");
  const first = lastSocket();
  act(() => first.open());
  // Ending the login command closes its socket while the sheet still shows it.
  answer = () => {
    if (calls.at(-1)?.method === "DELETE") first.end(4404, "the login window of opencode ended");
    return new Response(JSON.stringify(opencode()), { status: 200 });
  };
  // Log out of one…: the login command ends, the logout one runs in its place.
  fireEvent.click(within(window_).getByRole("button", { name: "Log out of one…" }));
  await waitFor(() => expect(calls.at(-1)?.body).toEqual({ action: "logout" }));
  expect(calls.slice(1).map((c) => c.method)).toEqual(["DELETE", "POST"]);
  await waitFor(() => expect(FakeSocket.all).toHaveLength(2));
  expect(closed).not.toHaveBeenCalled(); // the old window's end closes nothing
  const second = lastSocket();
  act(() => second.open());
  act(() => second.end(4404, "the login window of opencode ended"));
  await waitFor(() => expect(closed).toHaveBeenCalled());
});

test("no Log out of one… without a login", async () => {
  answer = () => new Response(JSON.stringify(opencode("no")), { status: 200 });
  sheet(opencode("no"));
  await screen.findByLabelText("Text to send");
  const window_ = screen.getByRole("dialog", { name: "Log in: OpenCode" });
  expect(within(window_).queryByRole("button", { name: "Log out of one…" })).toBeNull();
});

function window_() {
  const ended = vi.fn();
  render(<LoginWindow provider="opencode" title="OpenCode" onEnded={ended} />);
  const socket = lastSocket();
  act(() => socket.open());
  return { socket, ended };
}

test("Send sends the text and Enter as one input; the keys send theirs", () => {
  const { socket } = window_();
  const field = screen.getByLabelText("Text to send") as HTMLInputElement;
  fireEvent.change(field, { target: { value: "code-42" } });
  fireEvent.click(screen.getByRole("button", { name: "Send ⏎" }));
  const inputs = () => socket.frames.filter((f) => (f as { type: string }).type === "input");
  expect(inputs()).toEqual([{ type: "input", data: "code-42\r" }]);
  expect(field.value).toBe("");
  for (const key of KEYS) fireEvent.click(screen.getByRole("button", { name: key.name }));
  expect(inputs().slice(1)).toEqual([
    { type: "input", data: "\x1b[A" },
    { type: "input", data: "\x1b[B" },
    { type: "input", data: "\r" },
    { type: "input", data: "\x1b" },
  ]);
});

test("links in the window are clickable: the web links addon is loaded", () => {
  window_();
  expect(links.loaded).toBe(1);
});

test("Close ends the command first", async () => {
  const { ended } = window_();
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  await waitFor(() => expect(ended).toHaveBeenCalled());
  expect(calls).toContainEqual({ method: "DELETE", path: "/api/providers/opencode/login", body: undefined });
});
