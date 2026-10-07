// The live store's list of a session's artifacts: loaded when a page watches it, newest
// first by their latest record, and kept by the feed's artifacts items.
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { ArtifactInfo } from "./api";
import { artifact, FakeEventSource, stream } from "./fakes";
import { Live } from "./live";

const plan = artifact({ id: "a2", name: "plan", full_name: "plan", scope: "" }, { id: "p1", created_at: "2026-10-07T11:00:00.000Z" });
const design = artifact({}, { created_at: "2026-10-07T12:00:00.000Z" });

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      if (path === "/api/sessions/lado/artifacts") return new Response(JSON.stringify([plan, design]));
      return new Response("[]");
    }),
  );
  FakeEventSource.all = [];
  FakeEventSource.autoStart = false;
  vi.stubGlobal("EventSource", FakeEventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const ids = (live: Live) => {
  const loaded = live.get().artifacts.lado;
  return loaded && "items" in loaded ? loaded.items.map((one) => `${one.id}@${one.latest.id}`) : loaded;
};

test("a session's artifacts come newest first and a new record moves its artifact to the top", async () => {
  const live = new Live();
  live.start();
  stream().start();
  const stop = live.watch("artifacts", "lado");
  await vi.waitFor(() => expect(ids(live)).toEqual(["a1@r1", "a2@p1"]));
  const written: ArtifactInfo = { ...plan, latest: { ...plan.latest, id: "p2", hash: "h9", created_at: "2026-10-07T13:00:00.000Z" } };
  stream().send("change", { kind: "artifacts", session: "lado", key: "a2", op: "update", item: written });
  expect(ids(live)).toEqual(["a2@p2", "a1@r1"]);
  stop();
  expect(live.get().artifacts.lado).toBeUndefined();
});
