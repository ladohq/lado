## Context

A login window (`lado.logins.open_window`) is a tmux session of its own,
`lado-login-<provider>`, labelled `@lado-login` and `@lado-home`, running the action's argv
through `agent_env.command`; it ends with its command. The UI attaches to it over
`/api/providers/{name}/login/terminal` (`server.terminals.serve_login`,
`terminal.open_login`): frames `size` and `error`, binary output, `input` and `resize`
from the browser; when the window is gone the socket closes for good and
`LoginWindow.tsx` calls `onEnded`, which closes the sheet and reads the logins again.

Codex 0.162.0's `codex login --device-auth` prints, with colours:

```
Follow these steps to sign in with ChatGPT using device code authorization:

1. Open this link in your browser and sign in to your account
   https://auth.openai.com/codex/device

2. Enter this one-time code (expires in 15 minutes)
   UBSY-FIU1O

Continue only if you started this login in Codex. If a website or another person gave you this code, cancel.
```

then polls OpenAI and ends with `Successfully logged in` (status 0) or an error line such as
`device auth timed out after 15 minutes`, `device code login is not enabled for this Codex
server. Use the browser login or verify the server URL.` or `failed to request device
code: …` (non-zero).

## Goals / Non-Goals

Goals: the code copied and the link opened with one tap each, on a computer and on a phone
(also over the LAN by http); Codex's last words kept when it fails; no dead end when Codex
changes its output. Non-goals: see the proposal's Out of scope.

## Decisions

**D1. The provider reads its login window's text.** `base.Provider.login_prompt(text) ->
base.LoginPrompt | None` (`link`, `code`, `expires`: the code's expiry as Codex wrote it,
"" when it does not say, and `lines`: the warning as Codex wrote it); the default is None. Codex's finds the first `https://` URL after
the line naming the link, the code as the first token of the line after "one-time code"
(letters and digits in groups joined by `-`) and keeps the expiry and the "Continue only
if…" line. Why: Codex's words are the Codex provider's knowledge (neutral core: nothing
above `providers/` knows a CLI's output, as `login_status` already does); a unit test on
the real output catches a change of Codex's text. Rejected: parsing in the browser from
xterm's buffer (a CLI's text in the web UI), and LADO doing OpenAI's device flow itself
(proposal, Out of scope).

**D2. `LoginAction.shows_code`.** The action says its window shows a code instead of a
terminal; Codex's `login` action sets it, and the API's `LoginAction` carries it, so the
UI knows to show "Asking Codex CLI for a sign-in code…" (the CLI's title, as in the
window's head) rather than a terminal from the start.
Why: only what is used, one field, true for one action today; any later CLI with a
device code sets it and implements `login_prompt`.

**D3. The window's text survives its command.** A login window is made with tmux's
`remain-on-exit on`: when the command ends, its pane stays dead with its text and exit
status (`#{pane_dead}`, `#{pane_dead_status}`). LADO reads the text with `capture-pane -p
-J` (wrapped lines joined, no colours) and then kills the session. The exit status
is not tmux's: under load tmux lists a pane dead and gives no `#{pane_dead_status}`, for
15 s and more, and a login that succeeded would show as failed. The window's command runs
under a wrapper (`python -m lado.logins <status file> <argv>`) that writes its command's
exit status to `<LADO_HOME>/logins/<provider>.status` before it exits with it; LADO reads
that file once, tmux's status only when it is missing. A dead window counts as
ended everywhere `open_windows` is asked (`open_window` replaces it, `close_window` and
`end_windows` kill it, `terminal.login_ended` reports it). Why: polling the pane while the
command runs misses a line printed just before the exit, which is exactly Codex's error;
a pipe to a file starts after the command and keeps the output on disk.

**D4. The login socket carries the prompt and the end.** While a window whose action
`shows_code` is open, `serve_login` reads the pane every 0.5 s until `login_prompt`
returns a prompt and sends `{"type": "prompt", "link", "code", "expires", "lines"}` once (again on a
reconnect). When the command ends it sends `{"type": "ended", "status", "said"}` (`said`:
the last non-blank line of the dead pane) before closing the socket. Windows of other
actions get the same `ended` frame and the UI ignores it for them. Why: the socket already
lives exactly as long as the window and reconnects; no polling endpoint.

**D5. The terminal stays attached but hidden.** `LoginWindow.tsx` keeps xterm and its
socket for every window (the socket is the window's life line and the fallback's terminal);
for a `shows_code` action it hides the terminal area until 10 s pass without a `prompt`
frame, then shows it with the fallback line, "Text to send" and the keys. Why: one window
component, the fallback costs nothing.

**D6. The end of a code window.** `ended` with status 0 closes the sheet as today; any
other status after a prompt shows "Codex CLI did not sign you in" with `said`; "Get a new
code" opens the action again (`POST …/login`), "Back" returns to the sheet's choices.
Before a prompt (the fallback terminal shown, or the command failed at once) a non-zero
end shows the same failure view, so `said` is never lost.

**D7. Copy, Open and QR reuse what exists.** "Copy code" is `Copy.tsx`'s `useCopy` and
`CopyField` (Clipboard API, legacy copy, the code selected); "Open sign-in page" is an
`<a target="_blank" rel="noopener noreferrer">` styled as the primary button; the QR code
is `Share.tsx`'s (`qrcode-generator`), made into a shared component, hidden at a phone's
width (≤ 600px, the login sheet's breakpoint).

## Risks / Trade-offs

- A new Codex version may print other words: D5's fallback shows the terminal after 10 s,
  and `tests/test_login_status.py` pins the text of the version LADO's image ships.
- `remain-on-exit` keeps a dead session until LADO reads it: the server's start and stop and
  `lado stop --all` already end every login window by its labels, dead ones too.

## Migration Plan

None: no schema change; login windows open before the update end with the server's stop.
