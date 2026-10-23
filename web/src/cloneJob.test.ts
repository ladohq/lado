// The clone job client (openspec change project-page, D3): start, the poll, the 404 rule,
// Cancel clone and the beacon of a page that goes away.
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { ApiError, type CloneJob } from "./api";
import * as api from "./api";
import { CLONE_POLL, useCloneJob, type CloneEnd } from "./cloneJob";

vi.mock("./api", async (original) => ({
  ...(await original<typeof import("./api")>()),
  startClone: vi.fn(),
  getClone: vi.fn(),
  cancelClone: vi.fn(),
  cancelCloneOnLeave: vi.fn(),
}));

const startClone = vi.mocked(api.startClone);
const getClone = vi.mocked(api.getClone);
const cancelClone = vi.mocked(api.cancelClone);
const cancelCloneOnLeave = vi.mocked(api.cancelCloneOnLeave);

function job(more: Partial<CloneJob> = {}): CloneJob {
  return {
    id: "j1",
    url: "https://github.com/shop/admin",
    path: "/ws/projects/shop/admin",
    branch: "main",
    state: "running",
    progress: null,
    error: null,
    seconds: 0,
    ...more,
  };
}

const START = { url: "https://github.com/shop/admin", project: "shop", name: "admin", branch: "main" };

beforeEach(() => {
  vi.useFakeTimers();
  vi.resetAllMocks();
  startClone.mockResolvedValue(job());
  cancelClone.mockResolvedValue(job({ state: "cancelled" }));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

// Runs the hook's job; answers is the poll's answers in turn (an Error is thrown).
async function run(answers: (CloneJob | Error)[], isThere = async () => false) {
  for (const answer of answers) {
    if (answer instanceof Error) getClone.mockRejectedValueOnce(answer);
    else getClone.mockResolvedValueOnce(answer);
  }
  const hook = renderHook(() => useCloneJob());
  let end: CloneEnd | undefined;
  await act(async () => {
    const running = hook.result.current.run(START, isThere).then((e) => (end = e));
    for (let i = 0; i < answers.length; i++) await vi.advanceTimersByTimeAsync(CLONE_POLL);
    await running;
  });
  return { hook, end: end! };
}

test("a clone followed to its end: started with the screen's body, asked every poll", async () => {
  const done = job({ state: "done", seconds: 3 });
  const { hook, end } = await run([job({ progress: { phase: "Receiving objects", percent: 40, detail: "" } }), done]);
  expect(startClone).toHaveBeenCalledWith(START);
  expect(getClone).toHaveBeenCalledTimes(2);
  expect(end).toEqual({ done, late: false });
  expect(hook.result.current.job).toBeNull();
});

test("the running job is there for its progress while it runs", async () => {
  getClone.mockResolvedValue(job({ progress: { phase: "Receiving objects", percent: 40, detail: "" } }));
  const hook = renderHook(() => useCloneJob());
  await act(async () => {
    void hook.result.current.run(START, async () => false);
    await vi.advanceTimersByTimeAsync(CLONE_POLL);
  });
  expect(hook.result.current.job?.progress?.percent).toBe(40);
});

test("a failed clone ends failed with its error", async () => {
  const failed = job({ state: "failed", error: { message: "not found", kind: "not_found", hint: null } });
  const { end } = await run([failed]);
  expect(end).toEqual({ ended: "failed", job: failed });
});

test("a failed poll is asked again", async () => {
  const done = job({ state: "done" });
  const { end } = await run([new ApiError(0, "offline"), new ApiError(500, "busy"), done]);
  expect(end).toEqual({ done, late: false });
  expect(getClone).toHaveBeenCalledTimes(3);
});

test("a job the server forgot: away when the clone is there, gone when not", async () => {
  const lost = new ApiError(404, "no clone job j1");
  const there = vi.fn(async () => true);
  expect((await run([lost], there)).end).toEqual({ ended: "away", job: job() });
  expect(there).toHaveBeenCalledWith(job());
  expect((await run([lost], async () => false)).end).toEqual({ ended: "gone", job: job(), error: lost });
  const failing = async () => Promise.reject(new Error("offline"));
  expect((await run([lost], failing)).end).toMatchObject({ ended: "gone" });
});

test("a refused start throws the server's error and runs nothing", async () => {
  const refused = new ApiError(400, "admin already exists in project shop");
  startClone.mockRejectedValueOnce(refused);
  const hook = renderHook(() => useCloneJob());
  await act(async () => {
    await expect(hook.result.current.run(START, async () => false)).rejects.toBe(refused);
  });
  expect(getClone).not.toHaveBeenCalled();
  expect(hook.result.current.job).toBeNull();
});

test("Cancel clone asks the server to cancel; the job ends cancelled", async () => {
  getClone.mockResolvedValueOnce(job({ state: "cancelled" }));
  const hook = renderHook(() => useCloneJob());
  let end: CloneEnd | undefined;
  await act(async () => {
    const running = hook.result.current.run(START, async () => false).then((e) => (end = e));
    await Promise.resolve();
    hook.result.current.cancel();
    await vi.advanceTimersByTimeAsync(CLONE_POLL);
    await running;
  });
  expect(cancelClone).toHaveBeenCalledWith("j1");
  expect(end).toEqual({ ended: "cancelled", job: job({ state: "cancelled" }) });
});

test("a Cancel clone that comes too late: done, and late", async () => {
  getClone.mockResolvedValueOnce(job({ state: "done" }));
  const hook = renderHook(() => useCloneJob());
  let end: CloneEnd | undefined;
  await act(async () => {
    const running = hook.result.current.run(START, async () => false).then((e) => (end = e));
    await Promise.resolve();
    hook.result.current.cancel();
    await vi.advanceTimersByTimeAsync(CLONE_POLL);
    await running;
  });
  expect(end).toEqual({ done: job({ state: "done" }), late: true });
});

test("a page that goes away cancels the running clone by the beacon, and not after its end", async () => {
  getClone.mockResolvedValueOnce(job()).mockResolvedValueOnce(job({ state: "done" }));
  const hook = renderHook(() => useCloneJob());
  let running: Promise<CloneEnd> | undefined;
  await act(async () => {
    running = hook.result.current.run(START, async () => false);
    await Promise.resolve();
  });
  window.dispatchEvent(new Event("pagehide"));
  expect(cancelCloneOnLeave).toHaveBeenCalledWith("j1");
  await act(async () => {
    await vi.advanceTimersByTimeAsync(2 * CLONE_POLL);
    await running;
  });
  cancelCloneOnLeave.mockClear();
  window.dispatchEvent(new Event("pagehide"));
  expect(cancelCloneOnLeave).not.toHaveBeenCalled();
});

test("a screen that goes away stops asking", async () => {
  getClone.mockResolvedValue(job());
  const hook = renderHook(() => useCloneJob());
  let end: CloneEnd | undefined;
  await act(async () => {
    void hook.result.current.run(START, async () => false).then((e) => (end = e));
    await Promise.resolve();
  });
  hook.unmount();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(CLONE_POLL);
  });
  expect(end).toEqual({ ended: "left", job: job() });
  expect(getClone).not.toHaveBeenCalled();
});
