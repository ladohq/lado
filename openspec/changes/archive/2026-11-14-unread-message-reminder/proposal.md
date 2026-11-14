Task: LAD-234

## Why

An agent on a weak model may end its turn without reading the text of a message it got. The
line `[from <sender>] <summary> (#<id>, <n> lines: call read_messages)` says the text must be
read, but nothing reminds the agent when it does not: the text, which may be the whole request
(a flow step, the human's instructions, another agent's answer), is lost to it without a trace.

Symptom: the live run 42408769152 (2026-11-07, first attempt, Kilo on `qwen/qwen3.7-flash`),
`test_worker_does_a_task_reports_and_gets_a_message`. w1 got `[from supervisor] Thanks, one
last note for you (#3, 1 line: call read_messages)` (body: "Reply with the single word ACK").
It did not call `read_messages` and answered the supervisor with `send_message` at once. LADO
refused the send (`supervisor's message #3 waits for you, so nothing was sent: read it with
read_messages, then send again if it still needs saying`, `runtime._refuse_while_waiting`),
with the line sent meanwhile, `No reply needed to this line`, in the same result. The model
wrote `No reply needed per supervisor's message` and ended its turn. #3 stayed `delivered`,
never read; the test timed out after 120 seconds. A rerun passed.

Cause, checked against the code at d4b68a82: a message with something to read (`state.TO_READ`)
that the agent got and left unread has no check at the turn's end. The one check there,
`state.check_replies` (LAD-274), covers only the human's messages and only whether the agent
answered in the chat, not whether it read the text.

Data, all runs of `live.yml` from LAD-231's merge to 2026-11-12 (8 runs, 13 attempts per cell;
the first 10 on `qwen/qwen3.7-flash`, the last 3 on `anthropic/claude-haiku-5.5`, LAD-273):

- Kilo: 2 red attempts of 13. One is this symptom (above); the other is OpenRouter's 429
  (`qwen/qwen3.7-flash` has one host, LAD-273).
- OpenCode: 0 red of 13. Its case in LAD-231's trial (the answer `red` written as text, not
  sent to the human) is the one LAD-274 fixed (0.46.1).
- Codex: 6 red of 13: five on qwen, agents busy until the tests' waits ran out (the host's 429,
  LAD-273's report), and one on haiku, a "hello" answered only in the terminal; neither is this
  symptom.
- So the symptom showed once in 20 attempts of Kilo and OpenCode on the weak model. Since
  LAD-273 (2026-11-11) the live tests no longer meet weak models; the product's users on weak
  models still can.

The complaints of users the task names are the answer left in the terminal, fixed by LAD-274
(the human's decision, #6597, after the check). No code changed since the failure touches this
path.

Options with their long-term cost:

- **One reminder from `lado` for a text left unread (taken, the human's decision #6597).** The
  shape of LAD-274's reminder, measured there on weak models (it caught 6 of 7 misses). Neutral
  code (`state`, `hooks`), the same for every provider; a short extra turn only when a text was
  left unread; a schema migration for the mark "reminded once".
- The text of a short message in its line, so no `read_messages` is needed: changes the
  delivery protocol for every provider (`format_message`, `confirm_sent`), and a typed line must
  be one line while bodies have several. Rejected: too wide for a rare miss.
- Only the tests (a looser check, another model): leaves the user on a weak model without the
  text. Rejected; the tests already moved to another model (LAD-273).

## What Changes

- At the end of an agent's turn that ended without an error, LADO looks for the messages to
  that agent that it got (`delivered`), have something to read (a body or artifacts), are not
  read and were never reminded. When there are any, it queues the agent one message from
  `lado` naming them: `you have not read message #3 from supervisor: call read_messages to get
  its text; if it asks nothing of you, do nothing.` (several: `messages #3 from supervisor, #5
  from w2 … their text …`), and marks them reminded. Each message gets at most one reminder.
- Messages left unread before the update are not reminded.
- Docs: `docs/design/agents.md` (the check at a turn's end), `docs/design/modules.md`
  (`state`, `hooks`), CHANGELOG under Fixed.
- Version: the minor, 0.47.0, for the schema migration; CHANGELOG's `## 0.46.3 (unreleased)`
  becomes `## 0.47.0 (unreleased)`.

## Scope

`src/lado/state.py` (the column, its migration, the check), `src/lado/hooks.py` (the reminder at
`TURN_END`), tests at the unit and integration layers, the docs above, CHANGELOG.

## Out of scope

- The refusal of `send_message` while a message waits unread: unchanged. It already says to
  read first; the reminder catches the turn that ignored it.
- A verdict in the chat for a text never read (as "replied only in its terminal"): nothing a
  user of the product acts on; the reminder is the whole fix (only what is used).
- A second reminder: a model that ignores one would loop and spend the user's money.
- A message handed over and not yet confirmed (`sent`), or confirmed in this very hook's
  hand-over: the agent has not had its turn with it yet; the next turn's end checks it.
- The live tests: no change; their cells run on a strong model (LAD-273), and a cell on a weak
  model would be red at random and paid.
- Codex's red cells of 2026-11-11: the host's 429, fixed by LAD-273.

## Impact

- An agent that left a text unread gets one short extra turn; a strong model rarely leaves one.
- While the reminder waits, a `reminded` message from the human waits for its verdict one turn
  longer (`state.check_replies` decides only when no message from `lado` waits), as it does for
  any message from `lado`.
- Schema 39 → 40, minor version.
