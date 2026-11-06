// LADO plugin for the OpenCode family (OpenCode, Kilo CLI): reports the agent's lifecycle to
// LADO (see lado/providers/opencode_family.py). Checked with Kilo 7.8.3 and OpenCode 1.18.34.
//
// Options, from the `plugin` entry of the agent's config (kilo.json, opencode.json):
// { hooks: { <native event>: [argv...] } }. For each native event that has an argv, the
// command runs with a JSON payload on stdin. When "session.idle" prints text, that text
// becomes the session's next user message; when the CLI refuses it, "plugin.error" says so
// with the error. A missing argv means "do not report this event".
// The plugin must never break the CLI, so every other failure is swallowed.
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

// A request larger than the model's context: OpenCode 1.18.35 compacts and resends it without
// end, and no "session.idle" comes (1107 requests in 45 s on a fake server). The compaction's
// own request is small, so it succeeds: its step says nothing of the turn.
const OVERFLOW = "ContextOverflowError"
const MAX_OVERFLOWS = 3

// LADO's words go first: the core cuts an error to one short line (base.error_line).
function stoppedBy(error) {
  const words =
    `LADO stopped the turn after ${MAX_OVERFLOWS} attempts: the model's context is too small ` +
    "for the agent's request"
  return { name: error.name, message: error.message ? `${words}; ${error.message}` : words }
}

export const LadoPlugin = async ({ client }, options = {}) => {
  const hooks = options?.hooks ?? {}
  // Sessions of subagents (task tool): their turns are not the agent's turns.
  const subagents = new Set()
  // A turn that ends on an error (Kilo 7.8.3, OpenCode 1.18.34): "session.error", then
  // "session.idle" of the same session. The error goes with that idle. A context overflow
  // the CLI compacts its way out of ("session.compacted") ends no turn.
  const errors = new Map()
  // Overflows in a row by session, the sessions stopped for them, those whose turn has ended on
  // an error, and the compactions' messages, whose steps do not count as the turn's. A turn
  // that ends on an error gives two "session.idle", 20 ms apart, an abort's too (OpenCode
  // 1.18.35, Kilo 7.8.8): the second, with no error, would pass as a clean end.
  const overflows = new Map()
  const stopped = new Set()
  const ended = new Set()
  const summaries = new Set()
  return {
    "chat.message": async (input, output) => {
      try {
        if (subagents.has(input.sessionID)) return
        overflows.delete(input.sessionID)
        ended.delete(input.sessionID)
        const prompt = (output.parts ?? [])
          .filter((part) => part.type === "text" && !part.synthetic)
          .map((part) => part.text)
          .join("\n")
        const payload = { sessionID: input.sessionID, prompt }
        // The user message names the model the prompt goes to, as the agent's or the
        // session's choice resolved it, and its variant, the reasoning effort (OpenCode
        // 1.18.35, read in its bundle).
        const model = output.message?.model
        if (model?.providerID && model?.modelID) {
          payload.model = `${model.providerID}/${model.modelID}`
          if (model.variant) payload.variant = model.variant
        }
        await run(hooks["chat.message"], payload)
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
        if (event.type === "message.updated" && props.info?.summary) summaries.add(props.info.id)
        if (event.type === "message.part.updated" && props.part?.type === "step-finish") {
          if (!summaries.has(props.part.messageID)) overflows.delete(props.sessionID)
        }
        if (event.type === "session.error" && props.sessionID && !stopped.has(props.sessionID)) {
          const error = errorOf(props.error)
          errors.set(props.sessionID, error)
          if (error.name === OVERFLOW) {
            const count = (overflows.get(props.sessionID) ?? 0) + 1
            overflows.set(props.sessionID, count)
            if (count >= MAX_OVERFLOWS) {
              errors.set(props.sessionID, stoppedBy(error))
              stopped.add(props.sessionID)
              await client.session.abort({ path: { id: props.sessionID } })
            }
          }
        }
        if (event.type === "session.compacted" && !stopped.has(props.sessionID)) {
          errors.delete(props.sessionID)
        }
        if (event.type === "session.idle") {
          if (ended.has(props.sessionID)) return
          const payload = { sessionID: props.sessionID }
          overflows.delete(props.sessionID)
          stopped.delete(props.sessionID)
          if (errors.has(props.sessionID)) {
            payload.error = errors.get(props.sessionID)
            errors.delete(props.sessionID)
            ended.add(props.sessionID)
          }
          const text = await run(hooks["session.idle"], payload)
          if (text) {
            try {
              await client.session.promptAsync({
                path: { id: props.sessionID },
                body: { parts: [{ type: "text", text }] },
              })
            } catch (error) {
              // LADO keeps the messages in that text unconfirmed and types them in later;
              // it logs why they did not go this way.
              const failure = { name: "promptAsync", message: String(error?.message ?? error) }
              await run(hooks["plugin.error"], { sessionID: props.sessionID, error: failure })
            }
          }
        }
      } catch {}
    },
    dispose: async () => {
      await run(hooks["dispose"], {})
    },
  }
}
