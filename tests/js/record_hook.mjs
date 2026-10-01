// Stand-in for `lado hook <event>`: record_hook.mjs <log> <event> [reply]
// Appends the event and the JSON payload from stdin to <log>, one JSON line, then prints [reply].
import { appendFileSync, readFileSync } from "node:fs"

const [log, event, reply] = process.argv.slice(2)
const payload = JSON.parse(readFileSync(0, "utf8"))
appendFileSync(log, JSON.stringify({ event, payload }) + "\n")
if (reply) process.stdout.write(reply + "\n")
