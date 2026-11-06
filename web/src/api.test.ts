// A request the server never answered is a kind of its own, with human words; the exception
// goes to the console, and a refusal or a request the UI aborted stays as it was.
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { ApiError, getContent, getGates, probeStream, stopSession, Unreached, uploadFile } from "./api";

let logged: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  logged = vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const away = () => vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));

test.each([
  ["a read", () => getGates("lado")],
  ["a write", () => stopSession("lado")],
  ["an upload", () => uploadFile("lado", new File(["x"], "x.txt"), "x.txt")],
  ["a record's content", () => getContent("lado", "r1")],
  ["the stream's probe", () => probeStream("/api/events")],
])("%s with no answer is Unreached, its exception in the console", async (_, request) => {
  away();
  const error = await request().catch((one: unknown) => one);
  expect(error).toBeInstanceOf(Unreached);
  expect(error).toBeInstanceOf(ApiError);
  expect((error as ApiError).status).toBe(0);
  expect((error as ApiError).message).toBe("No connection");
  expect(String((error as ApiError).message)).not.toMatch(/TypeError|Failed to fetch/);
  expect(logged).toHaveBeenCalledWith(expect.objectContaining({ message: "Failed to fetch" }));
});

test("an answer cut in its body is no answer", async () => {
  const cut = new Response("{}");
  vi.spyOn(cut, "json").mockRejectedValue(new TypeError("network error"));
  vi.stubGlobal("fetch", vi.fn(async () => cut));
  await expect(stopSession("lado")).rejects.toBeInstanceOf(Unreached);
});

test("a request the UI aborted stays an AbortError, silent", async () => {
  const aborted = new DOMException("The user aborted a request.", "AbortError");
  vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(aborted)));
  await expect(getContent("lado", "r1")).rejects.toBe(aborted);
  expect(logged).not.toHaveBeenCalled();
});

test("a refusal stays a refusal with the server's words", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "gate #1 is closed already" }), { status: 400 })));
  const error = await stopSession("lado").catch((one: unknown) => one);
  expect(error).not.toBeInstanceOf(Unreached);
  expect((error as ApiError).status).toBe(400);
  expect((error as ApiError).message).toBe("gate #1 is closed already");
});
