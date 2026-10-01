// LADO plugin for Kilo CLI: reports the agent's lifecycle to LADO (see lado/providers/kilo.py).
//
// Options, from the agent's kilo.json `plugin` entry: { hooks: { <native event>: [argv...] } }.
// For each native event that has an argv, the command runs with a JSON payload on stdin.
// When "session.idle" prints text, that text becomes the session's next user message.
// A missing argv means "do not report this event". The plugin must never break Kilo, so
// every failure is swallowed.
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

export const LadoPlugin = async ({ client, directory }, options = {}) => {
  const hooks = options?.hooks ?? {}
  // Sessions of subagents (task tool): their turns are not the agent's turns.
  const subagents = new Set()
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
        if (subagents.has(props.sessionID)) return
        if (event.type === "permission.asked" || event.type === "question.asked") {
          await run(hooks[event.type], { sessionID: props.sessionID, permission: props.permission })
        } else if (event.type === "session.idle") {
          const text = await run(hooks["session.idle"], { sessionID: props.sessionID })
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
