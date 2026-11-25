// The guide by keyboard and screen reader: dialogs named by their titles, the focus taken and
// given back, the dimmed page inert and every inert the guide set removed, tips announced and
// reached by Tab from their target.
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { card, cardTitle, INFO, showGuide } from "./harness";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const inert = () => [...document.querySelectorAll<HTMLElement>("[inert]")];
const titled = (title: string) => waitFor(() => expect(cardTitle()).toBe(title));

describe("the guide's accessibility", () => {
  it("makes the welcome a modal dialog with the focus on Show me, the rest inert", async () => {
    showGuide("/");
    const dialog = await screen.findByRole("dialog", { name: "Welcome to LADO" });
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(dialog.getAttribute("aria-describedby")).toBeTruthy();
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("button", { name: "Show me" })));
    expect(inert().length).toBeGreaterThan(0);
    expect(inert().some((one) => one.contains(dialog))).toBe(false);
  });

  it("keeps Tab inside a centred card", async () => {
    showGuide("/");
    await screen.findByRole("dialog", { name: "Welcome to LADO" });
    const [show, later] = [screen.getByRole("button", { name: "Show me" }), screen.getByRole("button", { name: "Not now" })];
    show.focus();
    fireEvent.keyDown(show, { key: "Tab" });
    expect(document.activeElement).toBe(later);
    fireEvent.keyDown(later, { key: "Tab" });
    expect(document.activeElement).toBe(show);
  });

  it("names the highlighted element and leaves the target and the card out of the inert page", async () => {
    showGuide("/");
    fireEvent.click(screen.getByRole("button", { name: "Show me" }));
    await titled("Open Settings");
    const dialog = screen.getByRole("dialog", { name: "Open Settings" });
    expect(dialog.getAttribute("aria-modal")).toBe("false");
    expect(dialog.textContent).toContain("Highlighted: Settings");
    const target = document.querySelector<HTMLElement>('[data-guide="rail-settings"]')!;
    await waitFor(() => expect(inert().length).toBeGreaterThan(0));
    expect(inert().some((one) => one.contains(target) || one.contains(dialog))).toBe(false);
    expect(document.querySelector('[data-guide="rail-new-session"]')!.closest("[inert]")).not.toBeNull();
  });

  it("removes every inert it set when a step ends and when it closes", async () => {
    showGuide("/");
    fireEvent.click(screen.getByRole("button", { name: "Show me" }));
    await titled("Open Settings");
    fireEvent.click(document.querySelector<HTMLElement>('[data-guide="rail-settings"]')!);
    await titled("Open Agent CLIs");
    await waitFor(() => expect(inert().some((one) => one.contains(document.querySelector('[data-guide="rail-settings"]')))).toBe(true));
    fireEvent.keyDown(card()!, { key: "Escape" });
    await waitFor(() => expect(card()).toBeNull());
    expect(inert()).toEqual([]);
  });

  it("gives the focus back to where it was on Not now", async () => {
    const before = document.body.appendChild(document.createElement("button"));
    before.focus();
    showGuide("/");
    await screen.findByRole("dialog", { name: "Welcome to LADO" });
    expect(document.activeElement).not.toBe(before);
    fireEvent.click(screen.getByRole("button", { name: "Not now" }));
    await waitFor(() => expect(card()).toBeNull());
    expect(inert()).toEqual([]);
    expect(document.activeElement).toBe(before);
    before.remove();
  });

  it("announces a tip once, takes no focus, and is reached by Tab from its target", async () => {
    showGuide("/sessions/x", { ...INFO, completed: true, facts: null }, {
      pages: [
        {
          path: "/sessions/x",
          element: (
            <main>
              <nav data-guide="session-tabs">
                <a href="#a">Activity</a>
              </nav>
            </main>
          ),
        },
      ],
    });
    const tip = await screen.findByRole("region", { name: "Tip" });
    expect(document.activeElement).toBe(document.body);
    expect(inert()).toEqual([]);
    const live = document.querySelector('[aria-live="polite"]')!;
    expect(live.textContent).toBe(""); // the region is there before its text
    await waitFor(() => expect(live.textContent).toMatch(/^Tip: This is your session\. Activity shows/));
    const link = screen.getByRole("link", { name: "Activity" });
    link.focus();
    fireEvent.keyDown(link, { key: "Tab" });
    const gotIt = screen.getByRole("button", { name: "Got it" });
    expect(document.activeElement).toBe(gotIt);
    fireEvent.keyDown(gotIt, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(link);
    fireEvent.keyDown(link, { key: "Escape" });
    await waitFor(() => expect(tip.isConnected).toBe(false));
  });
});
