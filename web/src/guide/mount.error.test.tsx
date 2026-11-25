// The engine's chunk that does not load (a tab opened before `lado update` asks for the old
// one, gone from the server) costs the guide only: the page stays, the error is said once.
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import type { GuideInfo } from "../api";
import { resetFacts } from "./facts";
import { GuideMount } from "./mount";

vi.mock("./Guide", () => {
  throw new Error("Failed to fetch dynamically imported module: /assets/Guide-old.js");
});
vi.mock("../live", () => ({ useLive: () => ({ link: "open" }) }));

const INFO: GuideInfo = { auto: true, completed: false, shown: [], tips_off: false, telemetry_asked: false, facts: null };

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  resetFacts();
});

it("draws nothing and keeps the page when the engine's chunk fails to load", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(INFO))));
  const said = vi.spyOn(console, "error").mockImplementation(() => {});
  render(
    <main>
      <p>the page</p>
      <GuideMount />
    </main>,
  );
  await waitFor(() =>
    expect(said.mock.calls.some((call) => String(call[0]).startsWith("The first-run guide could not load"))).toBe(true),
  );
  expect(screen.getByText("the page")).toBeTruthy();
});
