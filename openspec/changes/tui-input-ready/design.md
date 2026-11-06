# Design: tui-input-ready

Root cause and the options weighed: `proposal.md`. Measured on Kilo 7.8.8 and OpenCode 1.18.35.

## Decisions

**D1. The TUI plugin's report is the session start.** `EVENTS` maps a new native event `tui.ready` to
`base.SESSION_START`, and `plugin.init` leaves `EVENTS` and `opencode_plugin.js`: a session start moves a
`starting` agent to idle and hands its queue over, and does nothing to an agent already `busy`. No neutral
event is added.

**D1a. A silent TUI, by the human's comment at the gate.** When the TUI plugin has not reported and the
server plugin lives, the agent is ready after 30 s and messages are typed in as before, so a CLI that stops
loading the TUI plugin (a renamed variable, a changed `tui.json`) never leaves it `starting` with a silent
chat. The server plugin's timer is that sign of life: at init it waits `tuiWait` (`TUI_WAIT`, 30 s, as
`runtime.START_SILENCE`), not holding the process and dropped at `dispose`, then runs the hook `tui.silent`,
a `SESSION_START` with `Event.note`. `hooks.handle` tells the lead that note (`runtime.start_note`) when the
start makes the agent ready; after `tui.ready` the agent is no longer `starting`, so it says nothing. This
departs from "the core does not change": `base.Event`, `hooks.py` and `runtime.py` each gain a few lines,
accepted by the supervisor. Claude Code and Codex set neither field, and a test holds that. The label is that
line in the chat, not a mark on the agent's card: `status_reason` shows only for `waiting` and `stopped`, and
this is a rare case.

The price, named to the human: 30 s cannot tell a TUI plugin that did not load from a TUI that is slow. With
hanging outside traffic the server plugin lives at 3 s and the window stays blank for minutes, so messages are
typed into it again, and the agent is `busy` without them. The protection against that is whole for 30 s only.
What D1b brings back softens it.

**D1b. A late TUI gets what was lost.** Messages that failed leave the agent `waiting`, and `state.seen`
brings them back at the next hook, but a session start ends no such wait, as a compaction starts a session
too. So `tui.ready` carries `Event.ready`, and `hooks.handle` ends a wait with no key (`waiting_for`) on it:
the queue goes in. A dialog's wait has its key and stays.

A paste still unconfirmed at `tui.ready` needs its own care (F1 of the review). `_plan` reads a hook after a
paste as a turn under way, so an agent `busy` for the paste alone would stay so, its message `sent`, for good.
`state.restart_typed` makes that paste a first attempt from this hook and the agent idle. It goes back to the
queue after `RETRY_DELAYS[0]` rather than at once: a CLI that held the paste confirms it meanwhile, so it is not
typed twice, at the price of 15 s for a TUI that lost it. A real turn has nothing unconfirmed and stays `busy`.
`tui.silent` also comes after `tui.ready`, as the timer cannot know of it: once the agent is ready that hook
stops before `state.seen`, so it cannot pass for a sign after a paste.

**D2. A plugin file of its own.** `src/lado/providers/opencode_tui_plugin.js`, default export
`{ id: "lado-ready", tui }`. Both CLIs require the `id` of a file plugin and pass the entry's options as
the second argument (checked on both). The server plugin keeps its shape: a TUI plugin runs in the TUI's
process, and the two have nothing to share.

**D3. Ready means the prompt has focus.** `tui` runs before the first frame, with
`api.renderer.currentFocusedRenderable` null; about 25 ms later it is the prompt's textarea (both CLIs).
The plugin registers `api.renderer.setFrameCallback`, and on the first frame with a focused renderable it
removes the callback and runs the hook once. When the renderer lacks either of them (a CLI's change), it
runs the hook at once: a paste may be lost then and the sweep retries, as today, rather than the agent
never starting. Like the server plugin it swallows every other failure and must never break the CLI.

**D4. The TUI config is the agent's own file.** `launch_command` writes `tui.json`,
`{"plugin": [[<uri>, {"hook": <argv>}]]}`, beside `kilo.json` or `opencode.json`, and sets
`OPENCODE_TUI_CONFIG` or `KILO_TUI_CONFIG` to its path, named by a class attribute `tui_config_variable`
of each subclass. The CLI merges it with the user's and the repository's `tui.json`, which stay untouched.
The argv is `base.hook_argv(agent, "tui.ready")`; no secret is in the file.

**D5. `--prompt` stays.** Its lines are taken at launch, before any of this, and `chat.message` may now
come before `tui.ready`. Either order is safe by D1. The comments that say no event tells when the TUI
takes input (`OpenCodeFamily.capabilities`, `docs/design/agents.md`) are corrected.

**D6. LADO's words of an error live in one place, `parse_event`.** The plugin stops composing them: for a
stopped turn it sends `{name, message, stopped: <attempts>}`, the server's text as it came.
`opencode_family` holds `TOO_SMALL = "the model's context is too small for the agent's request"` and builds
both lines: `LADO stopped the turn after <n> attempts: <TOO_SMALL>; <message>` with `details` the server's
message alone (F10), and for a message holding `exceed_context_size_error` the error of the requirement
with `details` `<name>: <message>`. Recognising it in Python, not in the plugin, keeps it out of the overflow
count, which that turn does not need: it ends at once. `base.error_line`'s cut applies as before.
`runtime.turn_failed` does not change.

**D7. The link is the UI's.** The warning's text stays one string from `model_settings.context_warning`, for
`lado start` and the window alike. `LaunchModel.tsx` renders a warning that holds `docs/install.md` with that
part as an `<a target="_blank" rel="noreferrer">` to `INSTALL_DOCS`, with ` ↗` as `What LADO collects ↗` has;
any other text stays plain. In `docs/install.md` the paragraph becomes `#### What to expect of a small
model`, and the `Others:` paragraph after its list moves above it, so it stays under `### The agents'
variables`. The anchor reaches `main` with the epic's merge.

**D8. Tests by layer.**

| Requirement | Layer | Test |
|---|---|---|
| Ready on focus, once, the callback removed, a renderer without the API, never throws | plugin (`make test-js`) | new `tests/js/opencode_tui_plugin.test.mjs`, a fake `api` |
| `tui.ready` is the session start, `plugin.init` is gone, `tui.json` and the variable per CLI | unit | `tests/test_providers.py` |
| A queue waits past every retry delay while no session start comes, then goes in once; the 30 s reason comes and goes | integration, fake agent | `tests/integration/`, a fake agent that delays its session start |
| A silent TUI: the agent ready, the lead told, the queue typed in; a late TUI gets what failed; a dialog's wait stays; Claude Code and Codex set neither field | plugin, unit, integration, smoke | `tests/js/opencode_plugin.test.mjs`, `tests/test_runtime.py`, `tests/integration/test_session_loop.py`, `tests/smoke/test_smoke.py` |
| A message right after the start, `attempts` 1, on the real CLI | smoke, `kilo` and `opencode` | `tests/smoke/test_smoke.py` |
| The two errors' lines and bodies, another `UnknownError` as it is | unit, plugin, integration | `tests/test_providers.py`, `tests/js/opencode_plugin.test.mjs`, the integration test of the server's words with the key's canary |
| The link, no link on another warning | vitest, UI e2e | `web/src/Launch.test.tsx`, `tests/ui/test_launch_model.py` |

Five starts of Kilo under load (`attempts` 1, none lost) are a measure for `build-report`, by hand on real
Kilo, and OpenCode the same: CI's smoke gives one start per CLI with no load of its own.

## Principles and what comes next

- Events, not screens: the signal is the CLI's own plugin API; the terminal is not read.
- Neutral core: above `providers/` only `Event.note` and `Event.ready`, neutral fields (D1a, D1b), and what
  reads them. It works on the two CLIs of the family; Claude Code and
  Codex need none of it, as their session start already means input.
- One source of truth: one readiness signal and its fallback (D1, D1a), LADO's words in one place (D6).
- Never touch the user's global config: D4.
- The coming steps put Claude Code and Codex on servers and do not touch this path.

## Risks

- The TUI plugin API is young in both CLIs, and Kilo's binary is not readable, so its behaviour is known by
  test only. A change shows in the smoke, and `lado doctor` warns off the tested versions.
- The 30 s reason now also fires for a CLI merely slow to open its TUI (the human's choice to keep it).
- With hanging outside traffic Kilo once took a pasted line while its window was blank, and no hook confirmed
  it; not understood. Nothing is typed before the prompt has focus for 30 s; after that (D1a) this path is
  reachable again.
