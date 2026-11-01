Task: LAD-168

## Why

Symptom: Codex's login window (Settings → Providers and environment → Codex → Log in… →
"Get a sign-in code") is the terminal of `codex login --device-auth`, always in control. The
one-time code cannot be copied: a selection and the keys go to the terminal, and the
selection bar's Copy does not act on a terminal (`.xterm` is not a readable area). On a
phone the code has to be read and typed by hand into another tab.

Cause: change `codex-shared-login` (LAD-166) gave Codex the login window OpenCode and Kilo
have, the terminal of the CLI's own command. Theirs asks questions in menus; Codex's asks
nothing: it prints a link and a code and waits until the code is entered on OpenAI's site.
For that the terminal is the wrong tool, and when Codex ends with an error the window
closes and its words are lost.

The human's decision (questions #2279 and #2285 of run task/lad-168, mockup
`mockup-login-no-terminal.html`): Codex's window shows no terminal. It shows the link as a
button and the code large with a Copy button; a QR code of the link on a computer; Codex's
warning about codes from others; Codex's own last words when it ends without a login; and
the terminal again only when LADO cannot read the link and the code.

## What Changes

- Codex's login window reads the link, the code and Codex's warning from the command's
  output (the Codex provider's knowledge) and shows them in two steps: "Open sign-in page"
  (a link button) and the code with "Copy code"; on a computer a QR code of the link
  ("Or scan it with your phone"); until then "Asking Codex for a sign-in code…".
- "Copy code" copies as LADO's other Copy buttons do: the Clipboard API, without it (a
  phone over the LAN by http) the legacy copy, and when both fail the code shown selected.
- When Codex ends without a login, the window stays with "Codex did not sign you in",
  Codex's last line as Codex wrote it, and "Get a new code". When it signs in, the window
  closes as today.
- When the link and the code are not found within 10 seconds (Codex changed its output),
  the window shows Codex's terminal as today with a line saying why.
- The text field and the keys ↑ ↓ Enter Esc show only with a terminal.
- OpenCode's and Kilo's login windows do not change.

## Scope

In: Codex's login window ("Get a sign-in code"), on a computer and on a phone; the
provider's reading of Codex's output; the login window's output kept after its command
ends; docs/design/ui.md; the CHANGELOG line of 0.44.0.

## Out of scope

- A Copy for the selection in OpenCode's and Kilo's login terminals: their logins ask for
  nothing to carry to another place, and their links already open on a tap (human,
  #2279).
- LADO doing OpenAI's device-code flow itself without Codex's CLI: it would rest on
  OpenAI's internal protocol and duplicate Codex's login file handling.
- The last words of OpenCode's or Kilo's login command when it fails: their windows keep
  closing as today; a separate task if wanted.

## Impact

- `src/lado/providers/base.py`, `providers/codex.py`: the provider reads its login
  window's text; `LoginAction` says the window shows a code.
- `src/lado/logins.py`, `src/lado/tmux.py`, `src/lado/terminal.py`,
  `src/lado/server/terminals.py`: the window's text kept after its command; the login
  socket's new frames.
- `web/src/LoginWindow.tsx`, `web/src/styles.css`, the QR code shared with `Share.tsx`,
  `web/openapi.json`, `web/src/api.gen.ts`.
- `docs/design/ui.md`, `docs/design/modules.md`, CHANGELOG.md (the 0.44.0 line of Codex's
  login). No schema migration; the version is not bumped: 0.44.0 is unreleased and this
  completes its Codex login.
