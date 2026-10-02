import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import type { SessionInfo } from "./api";
import { Sessions } from "./Sessions";

function answer(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      expect(path).toBe("/api/sessions");
      return new Response(JSON.stringify(body), { status });
    }),
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("lists the sessions the API returns", async () => {
  const sessions: SessionInfo[] = [
    { name: "lado", repo: "/src/lado", status: "running", agents: 3 },
    { name: "old", repo: "/src/old", status: "loop_down", agents: 0 },
  ];
  answer(200, sessions);
  render(<Sessions />);
  const row = (await screen.findByText("lado")).closest("tr")!;
  expect(within(row).getByText("/src/lado")).toBeTruthy();
  expect(within(row).getByText("running")).toBeTruthy();
  expect(within(row).getByText("3")).toBeTruthy();
  const other = screen.getByText("old").closest("tr")!;
  expect(within(other).getByText("session loop not running")).toBeTruthy();
});

test("says how to start a session when there is none", async () => {
  answer(200, []);
  render(<Sessions />);
  expect(await screen.findByText(/No sessions/)).toBeTruthy();
  expect(screen.getByText("lado start <repo>")).toBeTruthy();
});

test("says how to get in without the token", async () => {
  answer(401, { detail: "no valid token: open the link `lado ui` prints" });
  render(<Sessions />);
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    "no valid token: open the link `lado ui` prints",
  );
});
