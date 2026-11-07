import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { FakeSocket, FakeXterm, lastSocket, stubLegacyCopy, unstubLegacyCopy } from "./fakes";
import { FALLBACK_MS, LoginWindow } from "./LoginWindow";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./fakes")).FakeXterm }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./fakes")).FakeFit }));
vi.mock("@xterm/addon-web-links", () => ({ WebLinksAddon: class { activate() {} } }));

const HELP = "This window closes by itself once you are signed in.";
const WARNING = "Continue only if you started this login in Codex. If a website or another person gave you this code, cancel.";
const PROMPT = {
  type: "prompt",
  link: "https://auth.openai.com/codex/device",
  code: "UBSY-FIU1O",
  expires: "expires in 15 minutes",
  lines: [WARNING],
};

beforeEach(() => {
  FakeSocket.all = [];
  FakeXterm.all = [];
  vi.stubGlobal("WebSocket", FakeSocket);
  vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 200 })));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
  unstubLegacyCopy();
});

function codeWindow() {
  const ended = vi.fn();
  const retry = vi.fn();
  const back = vi.fn();
  render(<LoginWindow provider="codex" title="Codex CLI" help={HELP} showsCode onEnded={ended} onRetry={retry} onBack={back} />);
  const socket = lastSocket();
  act(() => socket.open());
  act(() => socket.frame({ type: "size", cols: 80, rows: 24 }));
  return { socket, ended, retry, back, dialog: screen.getByRole("dialog", { name: "Log in: Codex CLI" }) };
}

const terminalShown = (dialog: HTMLElement) => !(dialog.querySelector(".login-term") as HTMLElement).hidden;

test("before its code the window says so, with no terminal, field or keys", () => {
  const { dialog } = codeWindow();
  expect(within(dialog).getByText("Asking Codex CLI for a sign-in code…")).toBeTruthy();
  expect(within(dialog).getByText(HELP)).toBeTruthy();
  expect(terminalShown(dialog)).toBe(false);
  expect(within(dialog).queryByLabelText("Text to send")).toBeNull();
  expect(within(dialog).queryByRole("button", { name: "Enter" })).toBeNull();
});

test("the code: the link to open, the code to copy, its expiry, the CLI's warning and a QR code", () => {
  const { socket, dialog } = codeWindow();
  act(() => socket.frame(PROMPT));
  expect(within(dialog).queryByText(/Asking/)).toBeNull();
  const open = within(dialog).getByRole("link", { name: "Open sign-in page" });
  expect(open.getAttribute("href")).toBe("https://auth.openai.com/codex/device");
  expect(open.getAttribute("target")).toBe("_blank");
  expect(open.getAttribute("rel")).toBe("noopener noreferrer");
  expect(within(dialog).getByText("auth.openai.com/codex/device")).toBeTruthy();
  expect(within(dialog).getByText("Open the sign-in page and sign in to ChatGPT")).toBeTruthy();
  expect(within(dialog).getByText("UBSY-FIU1O")).toBeTruthy();
  expect(within(dialog).getByText("(expires in 15 minutes)")).toBeTruthy();
  expect(within(dialog).getByText(WARNING)).toBeTruthy();
  expect(within(dialog).getByRole("img", { name: "QR code of the sign-in page" })).toBeTruthy();
  expect(within(dialog).getByText("Or scan it with your phone")).toBeTruthy();
  expect(within(dialog).getByRole("button", { name: "Copy code" })).toBeTruthy();
  expect(terminalShown(dialog)).toBe(false);
  expect(within(dialog).queryByLabelText("Text to send")).toBeNull();
});

test("a link that is not https is not shown", () => {
  const { socket, dialog } = codeWindow();
  act(() => socket.frame({ ...PROMPT, link: "http://auth.example/device" }));
  expect(within(dialog).queryByRole("link", { name: "Open sign-in page" })).toBeNull();
  expect(within(dialog).getByText("Asking Codex CLI for a sign-in code…")).toBeTruthy();
});

test("Copy code copies by the legacy copy where the Clipboard API is missing (http over the LAN)", async () => {
  Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
  const copied = stubLegacyCopy(true);
  const { socket, dialog } = codeWindow();
  act(() => socket.frame(PROMPT));
  await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: "Copy code" })));
  expect(copied).toEqual(["UBSY-FIU1O"]);
  expect(within(dialog).getByRole("status").textContent).toBe("Code copied");
});

test("when both copies fail, the code is shown selected to copy by hand", async () => {
  Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
  stubLegacyCopy(false);
  const { socket, dialog } = codeWindow();
  act(() => socket.frame(PROMPT));
  await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: "Copy code" })));
  const field = within(dialog).getByRole("dialog", { name: "Sign-in code" });
  expect((within(field).getByRole("textbox", { name: "Code" }) as HTMLInputElement).value).toBe("UBSY-FIU1O");
  expect(within(field).getByText("Press ⌘C / Ctrl+C to copy")).toBeTruthy();
});

test("signed in: the command ends with 0 and the window goes", () => {
  const { socket, ended } = codeWindow();
  act(() => socket.frame(PROMPT));
  act(() => socket.frame({ type: "ended", status: 0, said: "Successfully logged in" }));
  act(() => socket.end(4404, "the login window of codex ended"));
  expect(ended).toHaveBeenCalledTimes(1);
});

test("ended without a login: the CLI's last words, Get a new code and Back", () => {
  const { socket, ended, retry, back, dialog } = codeWindow();
  act(() => socket.frame(PROMPT));
  act(() => socket.frame({ type: "ended", status: 1, said: "device auth timed out after 15 minutes" }));
  act(() => socket.end(4404, "the login window of codex ended"));
  expect(ended).not.toHaveBeenCalled();
  expect(within(dialog).getByText("Codex CLI did not sign you in")).toBeTruthy();
  expect(within(dialog).getByText("device auth timed out after 15 minutes")).toBeTruthy();
  expect(within(dialog).queryByText("UBSY-FIU1O")).toBeNull();
  fireEvent.click(within(dialog).getByRole("button", { name: "Get a new code" }));
  expect(retry).toHaveBeenCalledTimes(1);
  fireEvent.click(within(dialog).getByRole("button", { name: "Back" }));
  expect(back).toHaveBeenCalledTimes(1);
});

test("a failure before any code is shown as well, its words kept", () => {
  const { socket, ended, dialog } = codeWindow();
  act(() => socket.frame({ type: "ended", status: null, said: "" }));
  act(() => socket.end(4404, "the login window of codex ended"));
  expect(ended).not.toHaveBeenCalled();
  expect(within(dialog).getByText("Codex CLI did not sign you in")).toBeTruthy();
});

test("without a code after FALLBACK_MS the CLI's terminal shows, with the field and the keys", () => {
  vi.useFakeTimers();
  const { dialog } = codeWindow();
  act(() => vi.advanceTimersByTime(FALLBACK_MS - 100));
  expect(terminalShown(dialog)).toBe(false);
  act(() => vi.advanceTimersByTime(200));
  expect(terminalShown(dialog)).toBe(true);
  expect(
    within(dialog).getByText("LADO could not find the link and the code in Codex CLI's output; here is Codex CLI's own window."),
  ).toBeTruthy();
  expect(within(dialog).getByLabelText("Text to send")).toBeTruthy();
  expect(within(dialog).getByRole("button", { name: "Escape" })).toBeTruthy();
  expect(within(dialog).queryByText(/Asking/)).toBeNull();
});

test("a code in time keeps the terminal hidden after FALLBACK_MS", () => {
  vi.useFakeTimers();
  const { socket, dialog } = codeWindow();
  act(() => socket.frame(PROMPT));
  act(() => vi.advanceTimersByTime(FALLBACK_MS + 100));
  expect(terminalShown(dialog)).toBe(false);
});

test("a window of a terminal (OpenCode) ignores how its command ended and goes", () => {
  const ended = vi.fn();
  render(<LoginWindow provider="opencode" title="OpenCode" onEnded={ended} />);
  const socket = lastSocket();
  act(() => socket.open());
  const dialog = screen.getByRole("dialog", { name: "Log in: OpenCode" });
  expect(terminalShown(dialog)).toBe(true);
  act(() => socket.frame({ type: "ended", status: 1, said: "Error" }));
  act(() => socket.end(4404, "ended"));
  expect(ended).toHaveBeenCalledTimes(1);
});
