Task: LAD-212

## Why

Symptom: a message sent right after an OpenCode or Kilo agent starts does not go in with its
first hand-over. Design QA of LAD-211 saw it 5 of 5 times on Kilo: the agent is `busy` for 15 to
19 s without having the message, and the second attempt delivers it. The developer of LAD-211 saw
it not arrive at all, 2 of 4 times (`busy` after 45 s, or `message #1 not delivered`).

Cause, measured on Kilo 7.8.8 and OpenCode 1.18.35 with a 401 endpoint instead of a model:

- The plugin's init is LADO's session start, and it comes 1.5 to 3 s before the TUI can take
  input, later under load. LADO makes the agent idle and pastes the queue into a window whose
  input field does not exist yet. The paste is lost whole, and the sweep types it again only
  after `RETRY_DELAYS[0]`, 15 s.
- It is the family's defect, not Kilo's: OpenCode lost its first attempt 2 of 2 times as well.
  Kilo lost it 7 of 7 times. A paste before the TUI's first frame was lost, one after it arrived.
- The TUI can take much longer. With Kilo's outside traffic sent to a proxy that never answers,
  its window stayed blank for over 5 minutes; four pastes (at 3, 18, 48 and 109 s) went nowhere,
  and at 169 s the message failed and the agent was `waiting`. These are the developer's
  symptoms. That this is what happened on the developer's machine is likely, not proved: that
  stand was not seen.

Options weighed:

- A (taken): a TUI plugin. Both CLIs load one through a variable of their own and tell it when the
  prompt has focus, about 25 ms after the plugin starts. It reports that as the agent's session
  start, so nothing is typed before the TUI takes input. With the message sent at that moment,
  16 of 16 starts took one attempt, 9 of them at a load average of 42 on 16 cores. Long-term cost:
  a second small plugin file that rests on the TUI's API in both CLIs, which `lado doctor`'s
  tested versions already guard.
- B: read tmux's cursor flag for the window. It works, and it is reading the terminal, against
  "Events, not screens"; it would need polling.
- C: a shorter retry or a fixed wait after the init. A timeout in place of a cause: it stays wrong
  on a slower machine and does nothing for a TUI that takes minutes.

In the same step, what is left of LAD-211's local models:

- LM Studio refuses an overflow with HTTP 400 `exceed_context_size_error`, both CLIs report it as
  `UnknownError`, and the chat shows raw JSON.
- `docs/install.md` lacks four facts the human's check of LAD-211 found.
- The launch window names `docs/install.md` as plain text, and a wheel has no such file (F9 of
  the second design QA).
- The message of a stopped turn says the same words twice (F10).

## What Changes

- An OpenCode or Kilo agent stays `starting` until its TUI's prompt has focus; only then is it
  idle and its queue handed over. The plugin's init is no longer reported.
- A message sent while the TUI is not ready waits in the queue with no attempt counted. With no
  sign from the CLI at all, past 30 s the existing `Waiting for an answer in its terminal` reason
  shows, and goes when the TUI is ready.
- By the human's comment at the gate: when the TUI stays silent for 30 s while the server plugin
  lives, the agent is ready, its lead is told, and messages are typed in as before. A TUI that
  opens later gets what failed meanwhile.
- A server's refusal for context (`exceed_context_size_error`) reads in LADO's words, as an
  overflow does, with the server's whole text in the message's body.
- The message of a stopped turn holds only the server's text in its body.
- The launch window's `docs/install.md` is a link to its section on GitHub; the section becomes a
  heading. `lado start` keeps its text.
- `docs/install.md` gains the four facts; `docs/design/agents.md`, `docs/design/modules.md`,
  `docs/design/ui.md` and CHANGELOG.md follow.

## Scope

In: the above, for OpenCode and Kilo.

## Out of scope

- Claude Code and Codex: their session start already means they take input; the queue and the
  sweep do not change, and `hooks.py` gains only what two fields they never set ask (design.md,
  D1a, D1b). Their work on servers is the epic's next steps.
- `--prompt` for the first lines of a queue (`notice_on_argv`): it works, and Codex shares it.
  With the new signal OpenCode and Kilo may not need it, but removing it is a change of its own,
  with no defect behind it.
- A wording of the 30 s reason for a CLI that is merely slow: the human kept the existing line.
- The TUI that stays blank while outside traffic hangs: it is the CLI's own wait, and no setting
  shortens it (`docs/install.md`). LADO only stops losing the message.
- New settings, LAD-209, LAD-213.

## Impact

- `src/lado/providers/`: new `opencode_tui_plugin.js`; `opencode_plugin.js`,
  `opencode_family.py`, `kilo.py`, `opencode.py`.
- `src/lado/model_settings.py` is unchanged; `web/src/LaunchModel.tsx` makes the link.
- Tests: `tests/js/`, `tests/test_providers.py`, `tests/integration/`, `tests/smoke/`,
  `web/src/Launch.test.tsx`, `tests/ui/test_launch_model.py`.
- No schema change, no MCP tool or CLI change, no new dependency. It ships in 0.45.0, already
  a minor; on its own it would be a patch.
