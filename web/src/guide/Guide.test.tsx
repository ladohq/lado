import { act, cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { publish } from "./facts";
import { merged, MISSING_MS } from "./Guide";
import { card, cardTitle, INFO, publishLogins, Settings, showGuide } from "./harness";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const press = (name: string) => fireEvent.click(screen.getByRole("button", { name }));
const titled = async (title: string) => waitFor(() => expect(cardTitle()).toBe(title));
const eyebrow = () => card()?.querySelector(".gd-eyebrow")?.textContent ?? null;

describe("the main guide", () => {
  it("welcomes a fresh LADO, then Show me leads to Settings", async () => {
    showGuide("/");
    expect(await screen.findByRole("dialog", { name: "Welcome to LADO" })).toBeTruthy();
    expect(screen.getByText("You can open the guide again from Help.")).toBeTruthy();
    press("Show me");
    await titled("Open Settings");
    expect(eyebrow()).toBe("Connect a model · Step 1 of 3");
    expect(screen.getByRole("status").textContent).toBe("Waiting for you to open Settings");
  });

  it("waits for the statistics question to be answered", async () => {
    showGuide("/", { ...INFO, telemetry_asked: true });
    await act(async () => {});
    expect(card()).toBeNull();
    act(() => publish("statisticsAsked", false));
    expect(await screen.findByRole("dialog", { name: "Welcome to LADO" })).toBeTruthy();
  });

  it("shows no welcome while a model is connected, and goes on where it is", async () => {
    showGuide("/", { ...INFO, facts: { model: true, author: false } });
    await titled("Open Settings");
    expect(eyebrow()).toBe("Sign your work · Step 1 of 2");
    expect(card()?.querySelector(".gd-done")).toBeNull(); // the model was connected before
  });

  it("walks Settings: Agent CLIs, the rows, then Model servers", async () => {
    showGuide("/settings/general");
    press("Show me");
    await titled("Open Agent CLIs");
    fireEvent.click(screen.getByRole("link", { name: "Agent CLIs" }));
    publishLogins([{ name: "claude" }, { name: "codex" }]);
    await titled("Claude Pro or Max, or an Anthropic API key?");
    press("I have neither");
    await titled("A ChatGPT plan, or an OpenAI API key?");
    press("I have neither");
    await titled("An OpenRouter key, or a model on your computer?");
    fireEvent.click(screen.getByRole("link", { name: "Model servers" }));
    await titled("Add your server");
  });

  it("leads from a saved server to a model ticked for an agent CLI, then to the author", async () => {
    function Servers() {
      const [open, setOpen] = useState(false);
      const [model, setModel] = useState(false);
      return (
        <Settings>
          <ul>
            <li data-guide="model-server-row">
              <button type="button" onClick={() => setOpen(!open)}>
                Lab
              </button>
              {open && (
                <div data-guide="model-list">
                  <div role="button" tabIndex={0} onClick={() => setModel(true)}>
                    qwen3-8b
                  </div>
                  {model && (
                    <div role="group" data-guide="model-clis">
                      <label>
                        <input type="checkbox" onChange={() => publish("models", 1)} /> Codex CLI
                      </label>
                    </div>
                  )}
                </div>
              )}
            </li>
          </ul>
          <button type="button" data-guide="model-server-add">
            Add server
          </button>
        </Settings>
      );
    }
    showGuide("/settings/model-servers", INFO, { pages: [{ path: "/settings/model-servers", element: <Servers /> }] });
    press("Show me");
    publishLogins([{ name: "claude", installed: false }, { name: "codex", installed: false }]);
    act(() => publish("models", 0));
    await titled("Open your server"); // a saved server is no model yet
    fireEvent.click(screen.getByRole("button", { name: "Lab" }));
    await titled("Choose a model");
    fireEvent.click(screen.getByRole("button", { name: "qwen3-8b" }));
    await titled("Tick the agent CLIs that run it");
    expect(card()?.querySelector(".gd-done")).toBeNull();
    fireEvent.click(screen.getByRole("checkbox"));
    await titled("Sign the agents' work");
    expect(card()?.querySelector(".gd-done")?.textContent).toBe("✓ Model connected");
  });

  it("skips the row of a CLI not installed, and every row of a provider without texts", async () => {
    showGuide("/settings/agent-clis", INFO, { rows: ["claude", "codex", "kilo"] });
    press("Show me");
    publishLogins([{ name: "claude", installed: false }, { name: "codex" }, { name: "kilo" }]);
    await titled("A ChatGPT plan, or an OpenAI API key?");
    press("I have neither");
    await titled("An OpenRouter key, or a model on your computer?");
  });

  it("goes on to the author once a model is connected, the counter kept and the done line shown", async () => {
    showGuide("/settings/agent-clis");
    press("Show me");
    publishLogins([{ name: "claude" }, { name: "codex" }]);
    await titled("Claude Pro or Max, or an Anthropic API key?");
    publishLogins([{ name: "claude", loggedIn: true }, { name: "codex" }]);
    await titled("Sign the agents' work");
    expect(eyebrow()).toBe("Sign your work · Step 2 of 3");
    expect(card()?.querySelector(".gd-done")?.textContent).toBe("✓ Model connected");
    fireEvent.click(screen.getByRole("link", { name: "Git servers" }));
    await titled("Who signs the work?");
    act(() => publish("author", true));
    await titled("Start your first session");
    expect(card()?.querySelector(".gd-done")?.textContent).toBe("✓ Your work will be signed");
    expect(eyebrow()).toBe("Start working · Step 3 of 3");
  });

  it("is completed by the New session window, and its tip follows", async () => {
    const guide = showGuide("/", { ...INFO, facts: { model: true, author: true } });
    await titled("Start your first session");
    press("New session");
    await waitFor(() => expect(guide.posts()).toContainEqual({ action: "complete" }));
    expect(await screen.findByRole("region", { name: "Tip" })).toBeTruthy();
    expect(guide.posts()).toContainEqual({ action: "shown", ids: ["tip-launch"] });
  });

  it("offers a card to a person with none of these: four links, the IT line, Back", async () => {
    showGuide("/settings/agent-clis", INFO);
    press("Show me");
    publishLogins([{ name: "claude", installed: false }, { name: "codex", installed: false }]);
    await titled("An OpenRouter key, or a model on your computer?");
    press("I have none of these — what should I choose?");
    const dialog = await screen.findByRole("dialog", { name: "Don't have any of these yet?" });
    const links = [...dialog.querySelectorAll("a")];
    expect(links.map((a) => [a.textContent, a.getAttribute("href"), a.getAttribute("target")])).toEqual([
      ["Claude plans ↗", "https://claude.com/pricing", "_blank"],
      ["ChatGPT plans ↗", "https://chatgpt.com/pricing", "_blank"],
      ["OpenRouter keys ↗", "https://openrouter.ai/keys", "_blank"],
      ["Qwen (Alibaba Cloud) keys ↗", "https://www.alibabacloud.com/help/en/model-studio/get-api-key", "_blank"],
    ]);
    expect(screen.getByText("Not sure what any of this means? Ask your company's IT team, or someone who knows.")).toBeTruthy();
    press("Back");
    await titled("An OpenRouter key, or a model on your computer?");
  });

  it("counts New session as Step 2 of 2 when an author is in effect already", async () => {
    showGuide("/settings/agent-clis", { ...INFO, facts: { model: false, author: true } });
    press("Show me");
    publishLogins([{ name: "claude" }, { name: "codex" }]);
    await titled("Claude Pro or Max, or an Anthropic API key?");
    expect(eyebrow()).toBe("Connect a model · Step 1 of 2");
    publishLogins([{ name: "claude", loggedIn: true }, { name: "codex" }]);
    await titled("Start your first session");
    expect(eyebrow()).toBe("Start working · Step 2 of 2");
  });

  it("is completed by the New session window whichever step shows", async () => {
    const guide = showGuide("/");
    press("Show me");
    await titled("Open Settings");
    fireEvent.click(document.querySelector<HTMLElement>('[data-guide="rail-new-session"]')!);
    await waitFor(() => expect(guide.posts()).toContainEqual({ action: "complete" }));
  });

  it("closes on Not now until the next page load, and comes back then", async () => {
    const first = showGuide("/");
    press("Not now");
    await waitFor(() => expect(card()).toBeNull());
    expect(first.posts()).not.toContainEqual({ action: "complete" });
    cleanup();
    showGuide("/"); // the next page load: a new engine
    expect(await screen.findByRole("dialog", { name: "Welcome to LADO" })).toBeTruthy();
  });

  it("closes on Esc in a card", async () => {
    showGuide("/");
    press("Show me");
    await titled("Open Settings");
    fireEvent.keyDown(card()!, { key: "Escape" });
    await waitFor(() => expect(card()).toBeNull());
  });

  it("swallows a press on the dim: the step stays", async () => {
    showGuide("/");
    press("Show me");
    await titled("Open Settings");
    const block = document.querySelector<HTMLElement>(".gd-block")!;
    fireEvent.click(block);
    expect(cardTitle()).toBe("Open Settings");
  });

  it("hides while another window is over its step", async () => {
    showGuide("/settings/general");
    press("Show me");
    await titled("Open Agent CLIs");
    const other = document.createElement("div");
    other.setAttribute("role", "dialog");
    other.setAttribute("aria-modal", "true");
    act(() => {
      document.body.append(other);
    });
    await waitFor(() => expect(card()).toBeNull());
    act(() => other.remove());
    await titled("Open Agent CLIs");
  });

  it("skips a hint whose marker is missing for 2 s and journals it", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const guide = showGuide("/settings/model-servers", INFO, {
      pages: [{ path: "/settings/model-servers", element: <main><h2>Model servers</h2></main> }],
    });
    press("Show me");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(MISSING_MS + 100);
    });
    await waitFor(() =>
      expect(guide.posts()).toContainEqual({ action: "missing", ids: ["model-server-add"], marker: "model-server-add" }),
    );
  });
});

describe("on a phone", () => {
  afterEach(() => {
    delete document.documentElement.dataset.phone;
  });
  const section = (sentence: boolean) => ({
    path: "/settings/agent-clis",
    element: (
      <main>
        <a href="/settings" data-guide="settings-back">
          ‹ Settings
        </a>
        <ul>
          <li data-guide="cli-row-claude">Claude Code</li>
        </ul>
        {sentence && (
          <a href="/settings/model-servers" data-guide="model-servers-link">
            Model servers
          </a>
        )}
      </main>
    ),
  });

  it("goes back to the Settings list only when the next target is not on the section's page", async () => {
    document.documentElement.dataset.phone = "portrait";
    showGuide("/settings/agent-clis", INFO, { pages: [section(true)] });
    press("Show me");
    publishLogins([{ name: "claude" }, { name: "codex", installed: false }]);
    await titled("Claude Pro or Max, or an Anthropic API key?");
    press("I have neither");
    await titled("An OpenRouter key, or a model on your computer?");
    cleanup();
    document.documentElement.dataset.phone = "portrait";
    showGuide("/settings/agent-clis", INFO, { pages: [section(false)] });
    press("Show me");
    publishLogins([{ name: "claude", installed: false }, { name: "codex", installed: false }]);
    await titled("Back to Settings");
  });

  it("opens the menu before a step on the rail", async () => {
    document.documentElement.dataset.phone = "portrait";
    showGuide("/");
    press("Show me");
    await titled("Open the menu");
  });
});

describe("the marks' answers", () => {
  it("never take back a completion, tips off or a hint shown in this page load", () => {
    const now = { ...INFO, completed: true, tips_off: true, shown: ["welcome"], facts: null };
    const older = { ...INFO, shown: ["tip-launch"] };
    expect(merged(now, older)).toEqual({ ...INFO, completed: true, tips_off: true, shown: ["welcome", "tip-launch"], facts: null });
  });
});

describe("tips", () => {
  const sessionPage = {
    path: "/sessions/x",
    element: (
      <main>
        <nav data-guide="session-tabs">
          <a href="#a">Activity</a>
        </nav>
        <section data-guide="gate-card">
          <button type="button">Approve</button>
        </section>
      </main>
    ),
  };
  const done = { ...INFO, completed: true, facts: null };

  it("show one at a time, in order, each marked shown as it appears", async () => {
    const guide = showGuide("/sessions/x", done, { pages: [sessionPage] });
    const tip = await screen.findByRole("region", { name: "Tip" });
    expect(tip.textContent).toContain("This is your session.");
    expect(document.querySelectorAll(".gd-card")).toHaveLength(1);
    await waitFor(() => expect(guide.posts()).toContainEqual({ action: "shown", ids: ["tip-session"] }));
    press("Got it");
    await waitFor(() => expect(screen.getByRole("region", { name: "Tip" }).textContent).toContain("The team waits for your decision."));
  });

  it("never repeat a tip shown, and stop for good on Don't show tips like this", async () => {
    const guide = showGuide("/sessions/x", { ...done, shown: ["tip-session"] }, { pages: [sessionPage] });
    expect((await screen.findByRole("region", { name: "Tip" })).textContent).toContain("The team waits");
    press("Don't show tips like this");
    await waitFor(() => expect(screen.queryByRole("region", { name: "Tip" })).toBeNull());
    expect(guide.posts()).toContainEqual({ action: "tips_off" });
  });

  it("stay off when an older mark's answer comes after Don't show tips like this", async () => {
    showGuide("/sessions/x", done, { pages: [sessionPage] });
    const answers: ((value: Response) => void)[] = [];
    const late = { ...done, shown: ["tip-session"], tips_off: false };
    vi.mocked(fetch).mockImplementation(async (_path, init) => {
      const body = JSON.parse(String(init?.body ?? "{}"));
      if (body.action === "shown") return new Promise<Response>((resolve) => answers.push(resolve));
      return new Response(JSON.stringify({ ...late, tips_off: true }));
    });
    await screen.findByRole("region", { name: "Tip" });
    await waitFor(() => expect(answers).toHaveLength(1));
    press("Don't show tips like this");
    await waitFor(() => expect(screen.queryByRole("region", { name: "Tip" })).toBeNull());
    await act(async () => answers[0](new Response(JSON.stringify(late)))); // the older answer, last
    await act(async () => new Promise((resolve) => setTimeout(resolve, 100)));
    expect(screen.queryByRole("region", { name: "Tip" })).toBeNull();
  });

  it("never show over a guiding step", async () => {
    showGuide("/sessions/x", INFO, { pages: [sessionPage] });
    await screen.findByRole("dialog", { name: "Welcome to LADO" });
    expect(screen.queryByRole("region", { name: "Tip" })).toBeNull();
  });
});
