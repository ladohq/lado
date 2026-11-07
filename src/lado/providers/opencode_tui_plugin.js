// LADO's TUI plugin for the OpenCode family (OpenCode, Kilo CLI): tells LADO that the TUI takes
// input (see lado/providers/opencode_family.py). Checked with Kilo 7.8.8 and OpenCode 1.18.35.
//
// Options, from the `plugin` entry of the agent's tui.json: { hook: [argv...] }, run once with an
// empty JSON payload on stdin. `tui` runs before the first frame, with nothing focused; the
// prompt takes the focus about 25 ms later, and text typed before that is lost whole.
// A renderer without this API (a CLI's change) reports at once: a paste may be lost then and LADO
// types it again, which is better than an agent that never starts.
// The plugin must never break the CLI, so every failure is swallowed.
import { spawn } from "node:child_process"

function run(argv) {
  try {
    if (!argv) return
    const child = spawn(argv[0], argv.slice(1), { stdio: ["pipe", "ignore", "ignore"] })
    child.on("error", () => {})
    child.stdin.on("error", () => {})
    child.stdin.end("{}")
  } catch {}
}

async function tui(api, options) {
  let reported = false
  const ready = () => {
    if (!reported) run(options?.hook)
    reported = true
  }
  try {
    const renderer = api?.renderer
    if (typeof renderer?.setFrameCallback !== "function") return ready()
    if (!("currentFocusedRenderable" in renderer)) return ready()
    const watch = async () => {
      try {
        if (reported || !renderer.currentFocusedRenderable) return
        ready()
        renderer.removeFrameCallback?.(watch)
      } catch {
        ready()
      }
    }
    renderer.setFrameCallback(watch)
  } catch {
    ready()
  }
}

export default { id: "lado-ready", tui }
