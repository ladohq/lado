// Tests for the Kilo plugin (src/lado/providers/kilo_plugin.js). Run: node --test tests/js/*.test.mjs
import assert from "node:assert/strict"
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { dirname, join } from "node:path"
import { afterEach, beforeEach, test } from "node:test"
import { fileURLToPath } from "node:url"

import { LadoPlugin } from "../../src/lado/providers/kilo_plugin.js"

const RECORDER = fileURLToPath(new URL("record_hook.mjs", import.meta.url))
let log

beforeEach(() => {
  log = join(mkdtempSync(join(tmpdir(), "lado-kilo-")), "hooks.jsonl")
})

afterEach(() => {
  rmSync(dirname(log), { recursive: true, force: true })
})

// A hook argv that records its call; `reply` is what the hook prints.
function hook(event, reply) {
  return [process.execPath, RECORDER, log, event, ...(reply ? [reply] : [])]
}

function calls() {
  if (!existsSync(log)) return []
  return readFileSync(log, "utf8").trim().split("\n").map((line) => JSON.parse(line))
}

// A fake Kilo client that records the prompts the plugin sends.
function fakeClient() {
  const prompts = []
  return { prompts, session: { promptAsync: async (request) => prompts.push(request) } }
}

async function load(hooks, client = fakeClient()) {
  const plugin = await LadoPlugin({ client, directory: "/repo" }, { hooks })
  return { plugin, client }
}

test("init runs the plugin.init hook", async () => {
  await load({ "plugin.init": hook("plugin.init") })
  assert.deepEqual(calls(), [{ event: "plugin.init", payload: { directory: "/repo" } }])
})

test("chat.message passes the prompt without synthetic parts", async () => {
  const { plugin } = await load({ "chat.message": hook("chat.message") })
  await plugin["chat.message"](
    { sessionID: "s1" },
    {
      parts: [
        { type: "text", text: "[from w1] done" },
        { type: "text", text: "added by Kilo", synthetic: true },
        { type: "file", url: "file:///x" },
        { type: "text", text: "second line" },
      ],
    },
  )
  assert.deepEqual(calls(), [
    { event: "chat.message", payload: { sessionID: "s1", prompt: "[from w1] done\nsecond line" } },
  ])
})

test("session.idle sends what the hook prints as the next message", async () => {
  const { plugin, client } = await load({ "session.idle": hook("session.idle", "[from w1] hi") })
  await plugin.event({ event: { type: "session.idle", properties: { sessionID: "s1" } } })
  assert.deepEqual(calls(), [{ event: "session.idle", payload: { sessionID: "s1" } }])
  assert.deepEqual(client.prompts, [
    { path: { id: "s1" }, body: { parts: [{ type: "text", text: "[from w1] hi" }] } },
  ])
})

test("session.idle sends nothing when the hook prints nothing", async () => {
  const { plugin, client } = await load({ "session.idle": hook("session.idle") })
  await plugin.event({ event: { type: "session.idle", properties: { sessionID: "s1" } } })
  assert.equal(calls().length, 1)
  assert.deepEqual(client.prompts, [])
})

test("permission.asked and question.asked run their hooks", async () => {
  const { plugin } = await load({
    "permission.asked": hook("permission.asked"),
    "question.asked": hook("question.asked"),
  })
  const properties = { sessionID: "s1", permission: "edit" }
  await plugin.event({ event: { type: "permission.asked", properties } })
  await plugin.event({ event: { type: "question.asked", properties: { sessionID: "s1" } } })
  assert.deepEqual(calls(), [
    { event: "permission.asked", payload: properties },
    { event: "question.asked", payload: { sessionID: "s1" } },
  ])
})

test("events of subagent sessions are ignored", async () => {
  const { plugin, client } = await load({
    "chat.message": hook("chat.message"),
    "session.idle": hook("session.idle", "queued"),
    "permission.asked": hook("permission.asked"),
  })
  const info = { id: "sub", parentID: "s1" }
  await plugin.event({ event: { type: "session.created", properties: { info } } })
  await plugin["chat.message"]({ sessionID: "sub" }, { parts: [{ type: "text", text: "x" }] })
  await plugin.event({ event: { type: "session.idle", properties: { sessionID: "sub" } } })
  await plugin.event({ event: { type: "permission.asked", properties: { sessionID: "sub" } } })
  assert.deepEqual(calls(), [])
  assert.deepEqual(client.prompts, [])
  // The main session is still reported.
  await plugin.event({ event: { type: "session.idle", properties: { sessionID: "s1" } } })
  assert.deepEqual(calls(), [{ event: "session.idle", payload: { sessionID: "s1" } }])
})

test("events without a hook are skipped", async () => {
  const plugin = await LadoPlugin({ client: fakeClient(), directory: "/repo" })
  await plugin["chat.message"]({ sessionID: "s1" }, { parts: [] })
  await plugin.event({ event: { type: "session.idle", properties: { sessionID: "s1" } } })
  await plugin.event({ event: { type: "permission.asked", properties: { sessionID: "s1" } } })
  await plugin.dispose()
  assert.deepEqual(calls(), [])
})

test("a failing hook never throws", async () => {
  const failing = { "session.idle": ["/nonexistent/lado"] }
  for (const event of ["plugin.init", "chat.message", "permission.asked", "dispose"]) {
    failing[event] = [process.execPath, "-e", "process.exit(3)"]
  }
  const { plugin, client } = await load(failing)
  await plugin["chat.message"]({ sessionID: "s1" }, { parts: [] })
  await plugin.event({ event: { type: "session.idle", properties: { sessionID: "s1" } } })
  await plugin.event({ event: { type: "permission.asked", properties: { sessionID: "s1" } } })
  await plugin.event({ event: { type: "session.idle" } }) // no properties at all
  await plugin.dispose()
  assert.deepEqual(client.prompts, [])
})

test("a failing client never throws", async () => {
  const client = { session: { promptAsync: async () => Promise.reject(new Error("closed")) } }
  const { plugin } = await load({ "session.idle": hook("session.idle", "hi") }, client)
  await plugin.event({ event: { type: "session.idle", properties: { sessionID: "s1" } } })
  assert.equal(calls().length, 1)
})

test("dispose runs its hook", async () => {
  const { plugin } = await load({ dispose: hook("dispose") })
  await plugin.dispose()
  assert.deepEqual(calls(), [{ event: "dispose", payload: {} }])
})
