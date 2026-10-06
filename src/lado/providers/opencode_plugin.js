// LADO plugin for the OpenCode family (OpenCode, Kilo CLI): reports the agent's lifecycle to
// LADO (see lado/providers/opencode_family.py). Checked with Kilo 7.8.3 and OpenCode 1.18.34.
//
// Options, from the `plugin` entry of the agent's config (kilo.json, opencode.json):
// { hooks: { <native event>: [argv...] } }. For each native event that has an argv, the
// command runs with a JSON payload on stdin. When "session.idle" prints text, that text
// becomes the session's next user message. A missing argv means "do not report this event".
// The plugin must never break the CLI, so every failure is swallowed.
import { spawn } from "node:child_process"

function run(argv, payload) {
  return new Promise((resolve) => {
    if (!argv) return resolve("")
    try {
      const child = spawn(argv[0], argv.slice(1), { stdio: ["pipe", "pipe", "ignore"] })
      let out = ""
      child.stdout.on("data", (chunk) => (out += chunk))
      child.stdin.on("error", () => {})
      child.on("error", () => resolve(""))
      child.on("close", () => resolve(out.trim()))
      child.stdin.end(JSON.stringify(payload))
    } catch {
      resolve("")
    }
  })
}

// Requests for the human and their answers (Kilo 7.8.3, OpenCode 1.18.34): a request has its
// `id`, an answer names it as `requestID`. A refused permission is a "permission.replied" too.
const REQUESTS = new Set([
  "permission.asked",
  "permission.replied",
  "question.asked",
  "question.replied",
  "question.rejected",
])

// What a "session.error" says, for the turn's end: the error's name, and the message an API
// error carries (an APIError's data.message).
function errorOf(error) {
  const message = error?.data?.message
  return { name: String(error?.name ?? "UnknownError"), ...(message ? { message: String(message) } : {}) }
}

export const LadoPlugin = async ({ client, directory }, options = {}) => {
  const hooks = options?.hooks ?? {}
  // Sessions of subagents (task tool): their turns are not the agent's turns.
  const subagents = new Set()
  // A turn that ends on an error (Kilo 7.8.3, OpenCode 1.18.34): "session.error", then
  // "session.idle" of the same session. The error goes with that idle. A context overflow
  // the CLI compacts its way out of ("session.compacted") ends no turn.
  const errors = new Map()
  await run(hooks["plugin.init"], { directory })
  return {
    "chat.message": async (input, output) => {
      try {
        if (subagents.has(input.sessionID)) return
        const prompt = (output.parts ?? [])
          .filter((part) => part.type === "text" && !part.synthetic)
          .map((part) => part.text)
          .join("\n")
        await run(hooks["chat.message"], { sessionID: input.sessionID, prompt })
      } catch {}
    },
    event: async ({ event }) => {
      try {
        const props = event.properties ?? {}
        if (event.type === "session.created" && props.info?.parentID) {
          subagents.add(props.info.id)
        }
        if (REQUESTS.has(event.type)) {
          // A subagent's request waits for the human as much as the agent's own; the id
          // tells the answer to one request from the answer to another.
          const id = props.id ?? props.requestID
          await run(hooks[event.type], { sessionID: props.sessionID, id })
          return
        }
        if (subagents.has(props.sessionID)) return
        if (event.type === "session.error" && props.sessionID) {
          errors.set(props.sessionID, errorOf(props.error))
        }
        if (event.type === "session.compacted") errors.delete(props.sessionID)
        if (event.type === "session.idle") {
          const payload = { sessionID: props.sessionID }
          if (errors.has(props.sessionID)) {
            payload.error = errors.get(props.sessionID)
            errors.delete(props.sessionID)
          }
          const text = await run(hooks["session.idle"], payload)
          if (text) {
            await client.session.promptAsync({
              path: { id: props.sessionID },
              body: { parts: [{ type: "text", text }] },
            })
          }
        }
      } catch {}
    },
    dispose: async () => {
      await run(hooks["dispose"], {})
    },
  }
}
