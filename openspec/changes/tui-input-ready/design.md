# Design: tui-input-ready

Root cause and the options weighed: `proposal.md`. Measured on Kilo 7.8.8 and OpenCode 1.18.35.

## Decisions

**D1. The TUI plugin's report is the session start.** `EVENTS` maps a new native event `tui.ready` to
`base.SESSION_START`, and `plugin.init` leaves `EVENTS` and `opencode_plugin.js`. `hooks.handle` does not
change: a session start moves a `starting` agent to idle and hands its queue over, and does nothing to an
agent already `busy`. No neutral event is added, so the core stays as it is for every provider.
Against keeping `plugin.init` as a sign of life: an agent seen but not ready would never reach
`runtime.check_starts`, and a TUI plugin that fails to load would leave it `starting` in silence. With one
signal, that case gets the 30 s reason (No silent drops).

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
| A message right after the start, `attempts` 1, on the real CLI | smoke, `kilo` and `opencode` | `tests/smoke/test_smoke.py` |
| The two errors' lines and bodies, another `UnknownError` as it is | unit, plugin, integration | `tests/test_providers.py`, `tests/js/opencode_plugin.test.mjs`, the integration test of the server's words with the key's canary |
| The link, no link on another warning | vitest, UI e2e | `web/src/Launch.test.tsx`, `tests/ui/test_launch_model.py` |

Five starts of Kilo under load (`attempts` 1, none lost) are a measure for `build-report`, by hand on real
Kilo, and OpenCode the same: CI's smoke gives one start per CLI with no load of its own.

## Principles and what comes next

- Events, not screens: the signal is the CLI's own plugin API; the terminal is not read.
- Neutral core: nothing above `providers/` changes. It works on the two CLIs of the family; Claude Code and
  Codex need none of it, as their session start already means input.
- One source of truth: one readiness signal (D1), LADO's words in one place (D6).
- Never touch the user's global config: D4.
- The coming steps put Claude Code and Codex on servers and do not touch this path.

## Risks

- The TUI plugin API is young in both CLIs, and Kilo's binary is not readable, so its behaviour is known by
  test only. A change shows in the smoke, and `lado doctor` warns off the tested versions.
- The 30 s reason now also fires for a CLI merely slow to open its TUI (the human's choice to keep it).
- With hanging outside traffic Kilo once took a pasted line while its window was blank, and no hook confirmed
  it; not understood, and not reachable any more, as nothing is typed before the prompt has focus.
