// Tests for the OpenCode-family TUI plugin (src/lado/providers/opencode_tui_plugin.js), which
// tells LADO that the prompt has focus (Kilo 7.8.8, OpenCode 1.18.35).
// Run: node --test tests/js/*.test.mjs
import assert from "node:assert/strict"
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { dirname, join } from "node:path"
import { afterEach, beforeEach, test } from "node:test"
import { fileURLToPath } from "node:url"

import plugin from "../../src/lado/providers/opencode_tui_plugin.js"

const RECORDER = fileURLToPath(new URL("record_hook.mjs", import.meta.url))
let log

beforeEach(() => {
  log = join(mkdtempSync(join(tmpdir(), "lado-tui-plugin-")), "hooks.jsonl")
})

afterEach(() => {
  rmSync(dirname(log), { recursive: true, force: true })
})

const hook = () => [process.execPath, RECORDER, log, "tui.ready"]

function calls() {
  if (!existsSync(log)) return []
  return readFileSync(log, "utf8").trim().split("\n").map((line) => JSON.parse(line))
}

// The hook runs in a process of its own: its record comes a moment after the frame.
async function hookRan() {
  for (let n = 0; n < 200 && calls().length === 0; n++) {
    await new Promise((resolve) => setTimeout(resolve, 10))
  }
  return calls()
}

// A renderer of the TUI that draws frames when the test says so.
function fakeRenderer() {
  const callbacks = new Set()
  return {
    currentFocusedRenderable: null,
    callbacks,
    setFrameCallback: (callback) => callbacks.add(callback),
    removeFrameCallback: (callback) => callbacks.delete(callback),
    frame: async () => {
      for (const callback of [...callbacks]) await callback(16)
    },
  }
}

test("the plugin has the id both CLIs require of a file plugin", () => {
  assert.equal(plugin.id, "lado-ready")
})

test("nothing is reported before the prompt has focus", async () => {
  const renderer = fakeRenderer()
  await plugin.tui({ renderer }, { hook: hook() })
  await renderer.frame()
  await renderer.frame()
  await new Promise((resolve) => setTimeout(resolve, 100))
  assert.deepEqual(calls(), [])
  assert.equal(renderer.callbacks.size, 1)
})

test("the first frame with a focused prompt reports it once and ends the watch", async () => {
  const renderer = fakeRenderer()
  await plugin.tui({ renderer }, { hook: hook() })
  await renderer.frame()
  renderer.currentFocusedRenderable = { id: "prompt" }
  await renderer.frame()
  await renderer.frame()
  assert.deepEqual(await hookRan(), [{ event: "tui.ready", payload: {} }])
  assert.equal(renderer.callbacks.size, 0)
})

test("a renderer without the frame callback reports at once", async () => {
  await plugin.tui({ renderer: { currentFocusedRenderable: null } }, { hook: hook() })
  assert.deepEqual(await hookRan(), [{ event: "tui.ready", payload: {} }])
})

test("a renderer that does not name the focused renderable reports at once", async () => {
  const renderer = fakeRenderer()
  delete renderer.currentFocusedRenderable
  await plugin.tui({ renderer }, { hook: hook() })
  assert.deepEqual(await hookRan(), [{ event: "tui.ready", payload: {} }])
  assert.equal(renderer.callbacks.size, 0)
})

test("an api with no renderer reports at once", async () => {
  await plugin.tui({}, { hook: hook() })
  assert.deepEqual(await hookRan(), [{ event: "tui.ready", payload: {} }])
})

test("no failure reaches the CLI", async () => {
  await plugin.tui({ renderer: fakeRenderer() }, undefined)
  await plugin.tui({}, {})
  await plugin.tui({}, { hook: ["/no/such/command"] })
  const throwing = {
    get currentFocusedRenderable() {
      throw new Error("gone")
    },
    setFrameCallback: () => {
      throw new Error("gone")
    },
    removeFrameCallback: () => {},
  }
  await plugin.tui({ renderer: throwing }, { hook: hook() })
})

test("a frame callback that fails does not break the frame", async () => {
  const renderer = fakeRenderer()
  await plugin.tui({ renderer }, { hook: ["/no/such/command"] })
  renderer.currentFocusedRenderable = { id: "prompt" }
  renderer.removeFrameCallback = () => {
    throw new Error("gone")
  }
  await renderer.frame()
})
