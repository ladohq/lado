Task: LAD-167

## Why

Symptom: a session on Codex CLI 0.162.0 (main ca7548fc, Docker, `bypassPermissions`, a
ChatGPT login) starts without a question. Its supervisor gets `[from lado] session started;
wait for the human or a message`, calls `lado.read_messages`, then a tool of Codex's own
that its TUI labels "Waiting for agents", and stays busy for 38 s and longer. The human's
messages ("hi", "hello") stand in the feed and are not delivered, since LADO delivers a
Codex agent's queue at the end of its turn (`Capabilities.deliver_on_turn_end`) and the turn
does not end. The workaround is Take control and Esc in the agent's terminal.

Cause, checked in this run (Codex CLI 0.162.0 in the container, a local endpoint that
answers 401 and logs each request's tools, `codex exec` with the config LADO writes; its
source at `rust-v0.162.0`):

- "Waiting for agents" is Codex's event of `wait_agent`, the tool with which a model waits
  for the subagents Codex itself starts (`CollabWaitingBegin`).
- Codex has two versions of its subagents. LADO switches the first off
  (`features.multi_agent = false`), and with it older models (gpt-5.5, gpt-5.3-codex) get
  no subagent tools. Newer models (gpt-5.6-*, gpt-6-*, the ones a ChatGPT plan gets by
  default) turn the second version on through the model's metadata: a tool namespace
  `collaboration` with `spawn_agent`, `wait_agent`, `send_message`, `followup_task`,
  `interrupt_agent` and `list_agents`. `features.multi_agent = false` does not reach it,
  and neither does `features.multi_agent_v2 = false`: the model's choice wins over both.
- Codex has one switch that wins over the model's choice: `[agents] enabled = false`
  (`Config::multi_agent_version_override`: `features.multi_agent_v2` on gives version 2,
  otherwise `agents.enabled = false` gives none, and only then the model's metadata or
  `features.multi_agent` decide). With it, and `features.multi_agent_v2` left off, no
  model of the four got any subagent tool.
- The start line: LADO types `runtime.FIRST_INPUT` into a CLI that starts its session only
  on its first input and has nothing queued (`Capabilities.session_start_on_first_input`,
  Codex alone; Claude Code, Kilo and OpenCode never get it). "wait for the human or a
  message" asks the model to wait, and a model with a waiting tool takes it literally.

Why it is built so: `features.multi_agent = false` was right when LADO's Codex provider was
written (0.15x on a local model, no metadata): it was the only switch. The second version
came with Codex's newer models and is enabled by the model, not by the config's features.
The start line was written as a note to the agent, not as an instruction that ends a turn.

Options weighed:

- A (taken): the agent's config gets `[agents] enabled = false` and
  `features.multi_agent_v2 = false` beside `features.multi_agent = false`, and the start
  line asks the agent to end its turn. A smoke test on the real Codex checks the tools of
  the request a newer model gets. Long-term cost: two keys of Codex's config, pinned by a
  test that fails when a Codex release brings the subagents back another way.
- B: only reword the start line. The tools stay: an agent may still start Codex's own
  subagents in any turn, which LADO does not see, and wait for them; the next "wait" in a
  message brings the hang back.
- C: start Codex's session without a first input (its app-server protocol instead of the
  TUI). It would remove the start turn altogether, but it is a new way to run Codex, far
  beyond a fix.

Held against the design principles: the config keys stay in `providers/codex.py` (neutral
core: no other provider changes); the start line is the core's one text for every CLI that
needs it, and only Codex needs it today; no silent drop (a Codex that ignores the keys
fails the smoke test, not a user's session); only what is used (two keys, each named by the
cause above).

## What Changes

- A Codex agent's config.toml switches Codex's own subagents off for every model:
  `[agents] enabled = false` and `features.multi_agent_v2 = false`, beside
  `features.multi_agent = false`.
- `runtime.FIRST_INPUT` becomes `session started; nothing to do yet: end this turn, the next
  message starts a new one`.
- `docs/design/agents.md` (Status, background; the first input) and
  `docs/design/modules.md` (Codex CLI) say which keys switch the subagents off and why.
- CHANGELOG.md, `## 0.44.0 (unreleased)`, Fixed: a line on the Codex agent that hung on
  "Waiting for agents".
- A fix: the patch level; 0.44.0 is already the next version (unreleased, a minor), so the
  heading stays.

## Scope

- Codex agents' config: the subagents of both versions off, for every model.
- LADO's first input to a Codex agent with an empty queue.
- Tests: unit (the config, the line), smoke (the real Codex's request to a model with the
  second version's metadata), live (a Codex supervisor on a ChatGPT login answers the human's
  first message and calls no subagent tool).

## Out of scope

- Codex's `clock.sleep` (feature `sleep_tool`, given to gpt-6-* models) and the code mode's
  `wait` for its own cells: they wait for a time or a command, not for subagents, and end by
  themselves; an agent may need to wait for CI. Left on.
- Other providers' subagents: Claude Code's Task subagents are background work LADO tracks
  (`background`), OpenCode's task tool waits for its subagent inside the turn; neither hangs
  a turn on the start line, which they never get.
- Starting Codex without a first input (option C): a new way to run Codex, its own task if
  ever wanted.
- A user who turns `features.multi_agent_v2` on in their own config: LADO carries only the
  model settings (`CARRIED`) into an agent's config; of them only a profile could hold
  features, and Codex 0.162 refuses the legacy `profile` key and reads a profile only on
  `--profile`, which LADO never passes. So nothing of the user's turns it on again.

## Decisions for the record

- D1. Both keys, not one: `[agents] enabled = false` is the switch that wins over the
  model's metadata; `features.multi_agent_v2 = false` is set too because Codex checks it
  before `agents.enabled`, so a later carried setting that turns it on would win.
- D2. `features.multi_agent = false` stays: harmless, and it is what an older Codex reads.
- D3. The start line asks for the end of the turn in plain words and names no tool or
  waiting; it stays one line in `runtime.FIRST_INPUT`, the one source for the core and the
  tests.
- D4. The test of the real tools is a smoke test (real Codex, the local endpoint, no model):
  only the real CLI shows which tools a model's metadata brings. The endpoint
  (`tests/fake_endpoint.py`) keeps the tool names of each request. The test has a control: a
  plain `codex exec` on the same home without LADO's config shows the `collaboration` tools
  for that model, so a later Codex in which the model no longer brings them fails the test
  instead of passing it empty.
- D5. The live check goes into the ChatGPT-login live test (`tests/live/test_codex_login.py`):
  the second version comes only with OpenAI's newer models, which the local live model never
  is.

## Impact

- Code: `src/lado/providers/codex.py` (the agent's config), `src/lado/runtime.py`
  (`FIRST_INPUT`).
- Tests: `tests/test_codex.py`, `tests/test_runtime.py` (if it pins the text),
  `tests/fake_endpoint.py`, `tests/smoke/test_smoke.py`, `tests/live/test_codex_login.py`.
- Docs: `docs/design/agents.md`, `docs/design/modules.md`, `docs/testing.md` (the
  endpoint keeps tool names), CHANGELOG.md.
- Specs: a new capability `codex-agent-turns`.
