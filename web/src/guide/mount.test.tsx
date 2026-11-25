// The guide costs nothing once done: one GET per page load, and the engine's chunk only while
// something is left to show, or after Help → Getting started (also under LADO_GUIDE=0).
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { GuideInfo } from "../api";
import { resetFacts, restartGuide } from "./facts";
import { TIP_IDS } from "./hints";
import { GuideMount } from "./mount";

const engine = vi.hoisted(() => ({ loaded: 0 }));
vi.mock("./Guide", () => {
  engine.loaded++;
  return { default: ({ restarted }: { restarted: boolean }) => <p>{restarted ? "engine, restarted" : "engine"}</p> };
});
vi.mock("../live", () => ({ useLive: () => ({ link: "open" }) }));

const INFO: GuideInfo = { auto: true, completed: false, shown: [], tips_off: false, telemetry_asked: false, facts: null };

function serve(info: GuideInfo) {
  const fetch = vi.fn(async (_path: string, init?: RequestInit) =>
    new Response(JSON.stringify(init?.method === "POST" ? { ...info, completed: false } : info)),
  );
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  resetFacts();
  engine.loaded = 0;
  vi.resetModules();
});

describe("the guide's mount", () => {
  it("reads the record once and loads no engine when it is completed and every tip was shown", async () => {
    const fetch = serve({ ...INFO, completed: true, shown: TIP_IDS });
    render(<GuideMount />);
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    await act(async () => {});
    expect(fetch.mock.calls[0][0]).toBe("/api/guide");
    expect(engine.loaded).toBe(0);
    expect(screen.queryByText(/engine/)).toBeNull();
  });

  it("loads the engine while the guide is not completed", async () => {
    serve(INFO);
    render(<GuideMount />);
    expect(await screen.findByText("engine")).toBeTruthy();
    expect(engine.loaded).toBe(1);
  });

  it("starts nothing under LADO_GUIDE=0 until Getting started, which restarts it", async () => {
    const fetch = serve({ ...INFO, auto: false });
    render(<GuideMount />);
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    await act(async () => {});
    expect(engine.loaded).toBe(0);
    act(() => restartGuide());
    expect(await screen.findByText("engine, restarted")).toBeTruthy();
    expect(fetch.mock.calls[1][1]).toMatchObject({ method: "POST", body: JSON.stringify({ action: "restart" }) });
  });
});
