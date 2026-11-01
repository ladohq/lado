import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { ProviderLogins } from "./api";
import {
  claudeRow as claude,
  CODEX_HELP,
  codexRow as codex,
  FakeSocket,
  FakeXterm,
  lastSocket,
  LOGIN,
  opencodeRow as opencode,
} from "./fakes";
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

test("a choice that runs the CLI's sign-in has a button for it and no field", async () => {
  answer = () => new Response(JSON.stringify(codex()), { status: 200 });
  const { closed } = sheet(codex({ login: { ...LOGIN, state: "no" }, logout_file: false }));
  const dialog = screen.getByRole("dialog", { name: "How do you pay for Codex?" });
  expect((within(dialog).getByRole("radio", { name: /ChatGPT plan/ }) as HTMLInputElement).checked).toBe(true);
  expect(within(dialog).getByText("Sign in with your ChatGPT account by a one-time code.")).toBeTruthy();
  expect(within(dialog).queryByRole("textbox")).toBeNull();
  expect(within(dialog).queryByRole("button", { name: "Log out…" })).toBeNull();
  const get = within(dialog).getByRole("button", { name: "Get a sign-in code" });
  expect(get.className).toBe("primary");
  expect(calls).toEqual([]); // nothing runs until asked
  fireEvent.click(get);
  const window_ = await screen.findByRole("dialog", { name: "Log in: Codex CLI" });
  expect(calls).toEqual([{ method: "POST", path: "/api/providers/codex/login", body: { action: "login" } }]);
  expect(within(window_).getByText(CODEX_HELP)).toBeTruthy(); // the action's help line
  expect(lastSocket().url).toBe("ws://localhost:3000/api/providers/codex/login/terminal");
  act(() => lastSocket().open());
  act(() => lastSocket().end(4404, "the login window of codex ended"));
  await waitFor(() => expect(closed).toHaveBeenCalled());
});

test("the sign-in code's window shows its code; a failure offers a new code and Back", async () => {
  answer = () => new Response(JSON.stringify(codex()), { status: 200 });
  const { closed } = sheet(codex({ login: { ...LOGIN, state: "no" }, logout_file: false }));
  fireEvent.click(screen.getByRole("button", { name: "Get a sign-in code" }));
  const window_ = await screen.findByRole("dialog", { name: "Log in: Codex CLI" });
  expect(within(window_).getByText("Asking Codex CLI for a sign-in code…")).toBeTruthy();
  expect(within(window_).queryByLabelText("Text to send")).toBeNull();
  const first = lastSocket();
  act(() => first.open());
  act(() => first.frame({ type: "prompt", link: "https://auth.openai.com/codex/device", code: "UBSY-FIU1O", expires: "", lines: [] }));
  expect(within(window_).getByText("UBSY-FIU1O")).toBeTruthy();
  act(() => first.frame({ type: "ended", status: 1, said: "device auth timed out after 15 minutes" }));
  act(() => first.end(4404, "the login window of codex ended"));
  expect(within(window_).getByText("device auth timed out after 15 minutes")).toBeTruthy();
  expect(closed).not.toHaveBeenCalled();
  // Get a new code runs the sign-in again, in a new window.
  fireEvent.click(within(window_).getByRole("button", { name: "Get a new code" }));
  await waitFor(() => expect(FakeSocket.all.length).toBe(2));
  expect(calls.filter((c) => c.method === "POST").length).toBe(2);
  expect(await screen.findByText("Asking Codex CLI for a sign-in code…")).toBeTruthy();
  const second = lastSocket();
  act(() => second.open());
  act(() => second.frame({ type: "ended", status: 1, said: "no network" }));
  act(() => second.end(4404, "the login window of codex ended"));
  // Back: the sheet's choices again.
  fireEvent.click(await screen.findByRole("button", { name: "Back" }));
  expect(screen.getByRole("dialog", { name: "How do you pay for Codex?" })).toBeTruthy();
  expect(closed).not.toHaveBeenCalled();
});

test("the other choices of the same sheet take a pasted value", () => {
  sheet(codex());
  fireEvent.click(screen.getByRole("radio", { name: /OpenAI API key/ }));
  expect(screen.getByLabelText("OPENAI_API_KEY")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Get a sign-in code" })).toBeNull();
});

test("Log out of the CLI's own file asks first, naming who shares it, then runs its logout", async () => {
  answer = () => new Response(JSON.stringify(codex()), { status: 200 });
  const { closed } = sheet(codex());
  fireEvent.click(screen.getByRole("button", { name: "Log out…" }));
  const ask = screen.getByRole("group", { name: "Log out of Codex CLI?" });
  expect(ask.textContent).toContain(
    "supervisor of my-app, developer of my-app share this login and stop working until you log in again. " +
      "Your own Codex CLI in a terminal is logged out too.",
  );
  expect(calls).toEqual([]);
  fireEvent.click(within(ask).getByRole("button", { name: "Log out" }));
  await screen.findByRole("dialog", { name: "Log in: Codex CLI" });
  expect(calls).toEqual([{ method: "POST", path: "/api/providers/codex/login", body: { action: "logout" } }]);
  act(() => lastSocket().open());
  act(() => lastSocket().end(4404, "the login window of codex ended"));
  await waitFor(() => expect(closed).toHaveBeenCalled());
});

test("Log out of the file with no agent running says so", () => {
  sheet(codex({ running: [] }));
  fireEvent.click(screen.getByRole("button", { name: "Log out…" }));
  expect(screen.getByRole("group").textContent).toContain(
    "No agent of it runs now. Your own Codex CLI in a terminal is logged out too.",
  );
});

test("OpenCode's sheet opens its own login window at once, with Log out of one… when logged in", async () => {
  answer = () => new Response(JSON.stringify(opencode()), { status: 200 });
  const { closed } = sheet(opencode());
  await screen.findByLabelText("Text to send"); // the terminal's window, after "opening…"
  const window_ = screen.getByRole("dialog", { name: "Log in: OpenCode" });
  expect(within(window_).getByText("Open the link, sign in, then send what it gives you (a code) from here.")).toBeTruthy();
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
