## ADDED Requirements

### Requirement: Codex's login window shows the link and the code instead of a terminal

While Codex's "Get a sign-in code" runs, the login window SHALL show no terminal but the
sign-in link and the one-time code that the Codex provider reads from the command's
output: the link as "Open sign-in page", the code large with "Copy code", Codex's warning
about codes given by others, and on a window wider than a phone's a QR code of the link.
Only an `https` link SHALL be shown. The window names the CLI by its title, "Codex CLI",
as its head "Log in: Codex CLI" does.

#### Scenario: The code shown
- **WHEN** Codex prints its link `https://auth.openai.com/codex/device` and the code
  `UBSY-FIU1O`
- **THEN** the window shows step 1 "Open the sign-in page and sign in to ChatGPT" with
  "Open sign-in page" and `auth.openai.com/codex/device`, step 2 "Enter this one-time code
  there (expires in 15 minutes)" with `UBSY-FIU1O` and "Copy code", Codex's line "Continue
  only if you started this login in Codex. If a website or another person gave you this
  code, cancel.", and a QR code of the link

#### Scenario: Before the code
- **WHEN** the window opens and Codex has not printed its code yet
- **THEN** the window shows "Asking Codex CLI for a sign-in code…" and no terminal

#### Scenario: On a phone
- **WHEN** the window shows the code at a phone's width
- **THEN** it fills the screen with both steps and shows no QR code

#### Scenario: Copy over plain http
- **WHEN** the page is served by http from another machine (a phone over the LAN), where
  the Clipboard API is missing, and the human chooses "Copy code"
- **THEN** the code is copied by the legacy copy and "Code copied" shows; when that fails
  too, the code is shown selected with "Press ⌘C / Ctrl+C to copy"

### Requirement: Codex's login window keeps Codex's last words when it ends without a login

When Codex's login command ends with a non-zero exit status after its code was shown, the
login window SHALL stay open with "Codex CLI did not sign you in", "What Codex CLI said:"
and the last non-blank line of
the command's output as Codex wrote it, "Get a new code", which runs the command again,
and "Back", which returns to Codex's sheet. When the command ends with status 0 the window
SHALL close as before.

#### Scenario: The code expired
- **WHEN** the human does not enter the code and Codex ends after 15 minutes with an error
- **THEN** the window shows "Codex CLI did not sign you in" and Codex's last line, and "Get a
  new code" shows a new link and code

#### Scenario: Signed in
- **WHEN** the human enters the code and Codex ends with status 0
- **THEN** the window closes and the row shows "Logged in · ChatGPT plan · Codex's login
  file"

#### Scenario: The last line survives the exit
- **WHEN** the login command prints a line and exits at once
- **THEN** the window shows that line, read after the command ended

### Requirement: Codex's login window falls back to the terminal

When the link and the code are not read from Codex's output within 10 seconds of the
window opening, the login window SHALL show Codex's terminal, as for OpenCode and Kilo,
under the line "LADO could not find the link and the code in Codex CLI's output; here is
Codex CLI's own window.", with "Text to send" and the keys.

#### Scenario: Output LADO cannot read
- **WHEN** the login command prints no link and code LADO recognises for 10 seconds
- **THEN** the window shows the line and the command's terminal, in control

## MODIFIED Requirements

### Requirement: The login window runs the CLI's own login command

For a CLI that logs in by its own command (OpenCode, Kilo: the row's button; Codex: its
sheet's choice "ChatGPT plan"), the page SHALL open a terminal that runs it, in the
environment of the agents without a project, at most one per CLI, with "Log out of one…"
while logged in where the CLI asks which; when the command ends the window SHALL close and
the page SHALL read the state again, and Close SHALL end the command. LADO SHALL run no
login command of Claude Code.

#### Scenario: The login commands
- **WHEN** the login window opens for OpenCode, Kilo or Codex's "ChatGPT plan"
- **THEN** it runs `opencode auth login`, `kilo auth login` or `codex login --device-auth
  -c cli_auth_credentials_store="file"`, and "Log out of one…" runs `opencode auth logout`
  or `kilo auth logout`

#### Scenario: OpenCode's login from a phone
- **WHEN** the human chooses OpenCode's "Log in…" on a phone, picks a model provider with
  ↓ and Enter and sends its key with "Text to send"
- **THEN** the command ends, the window closes, and the row shows "Logged in"

#### Scenario: Claude Code's login from a phone
- **WHEN** the human chooses Claude Code's "Log in…" on a phone
- **THEN** the sheet asks "How do you pay for Claude?" with a field for a token or a key,
  and no login command of Claude Code runs

#### Scenario: Opened twice
- **WHEN** OpenCode's login window is open and its button is chosen again
- **THEN** the same window is shown and no second command starts

#### Scenario: The windows end with LADO
- **WHEN** a login window runs and the UI server stops, or `lado stop --all` runs
- **THEN** its tmux session is gone, found by its label, and `lado ls` never listed it

#### Scenario: Codex has no button
- **WHEN** Codex is installed
- **THEN** its row has no button that runs a Codex command at once: its one button opens
  Codex's sheet, where "Get a sign-in code" runs the login command

#### Scenario: Codex's sign-in code
- **WHEN** the human chooses "Get a sign-in code" in Codex's sheet
- **THEN** the login window shows Codex's link and one-time code (see "Codex's login window
  shows the link and the code instead of a terminal"), and once the human has entered the
  code the command ends, the window closes, and the row shows "Logged in · ChatGPT plan ·
  Codex's login file"

### Requirement: The login window works from a phone

While the login window shows a terminal, it SHALL make each link in it clickable, also one
wrapped over lines, and SHALL offer a "Text to send" field that sends its text followed by
Enter and the keys ↑ ↓ Enter Esc, at a phone's width too; without a terminal it SHALL show
neither the field nor the keys.

#### Scenario: The code sent from the field
- **WHEN** the login command waits for a code and the human types it in "Text to send" and
  chooses Send
- **THEN** the command receives the code and Enter as one input

#### Scenario: No field without a terminal
- **WHEN** Codex's login window shows its link and code
- **THEN** it shows no "Text to send" field and no keys ↑ ↓ Enter Esc

### Requirement: Codex's sheet asks how the human pays

Codex's sheet SHALL ask "How do you pay for Codex?" with the current choice marked:
"ChatGPT plan — Plus, Pro, Business or Enterprise" with the button "Get a sign-in code",
which opens the login window (see "The login window runs the CLI's own login command");
"ChatGPT Business or Enterprise — access token" with a secret field for
`CODEX_ACCESS_TOKEN`; "Pay per use — OpenAI API key" with a secret field for
`OPENAI_API_KEY`. Codex's row SHALL NOT say that its agents do not get the login.

#### Scenario: The sheet
- **WHEN** Codex is not logged in and the human chooses "Log in…" on Codex's row
- **THEN** the sheet asks "How do you pay for Codex?" with the three choices, "ChatGPT
  plan" chosen, and its button "Get a sign-in code"

#### Scenario: A key saved
- **WHEN** the human chooses "Pay per use — OpenAI API key", pastes a key and chooses Save
- **THEN** `<LADO_HOME>/secrets/OPENAI_API_KEY` holds it with mode 600, LADO's secrets hold
  no `CODEX_ACCESS_TOKEN`, and the row shows "Logged in · Pay per use (API key) · LADO's
  secret"

#### Scenario: From a phone
- **WHEN** the human opens Codex's sheet on a phone and chooses "Get a sign-in code"
- **THEN** the login window fills the screen, "Open sign-in page" opens the link in a new
  tab, and "Copy code" copies the code
