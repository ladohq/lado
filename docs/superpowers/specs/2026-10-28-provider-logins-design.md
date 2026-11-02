# Provider logins (LAD-157)

Change: `openspec/changes/provider-logins/` (proposal with AC-1..AC-10, delta specs of
`provider-logins` (new), `claude-folder-trust`, `agent-variables` and `container`,
`design.md` with the decisions D1-D14). This document is the human's view: what a user
gets, what was decided with the human, and how the human checks it. Mockup: the run's
artifact `mockup-providers.html`.

## What a user gets

- **Settings → Providers and environment** (the placeholder goes): one row per agent CLI.
  ```
  Claude Code 2.1.295
  ● Logged in · Claude subscription (Max)
    From the login file /home/lado/.claude/.credentials.json, shared by all Claude agents.
    [Log in again…] [Log out…]
    Or a token or key instead (LADO's secret, never shown again; it wins over the file):
    CLAUDE_CODE_OAUTH_TOKEN  [••••••••]  [Save]
    ANTHROPIC_API_KEY        [        ]  [Save]
  Codex 0.162.0
  ○ Not logged in
    Codex agents do not get a login yet: each has a Codex home of its own (GitHub #113).
  OpenCode 1.18.35
  ● 2 logins: Anthropic (API key), OpenRouter (oauth); from variables: OPENAI_API_KEY
    [Add a login…] [Log out of one…]
  Kilo 7.8.8
  ○ No login: only Kilo's free models          [Add a login…]
  lado doctor about the providers: …                         [Check again]
  ```
- **The login window**: the CLI's own `auth login` in a terminal on the page. The link is
  clickable; "Text to send" and ↑ ↓ Enter Esc make it work from a phone. It closes when
  the command ends, and the row is read again.
- **A Claude agent without a login waits and starts by itself.** Needs you: "Claude Code is
  not logged in: log in in Settings → Providers and environment, or set
  CLAUDE_CODE_OAUTH_TOKEN; the agent starts by itself once you do" with "Log in…"; `lado
  ls` prints the same. Once the login is there (from the page, a token, or a shell), the
  agent's window starts Claude Code within seconds, no restart.
- **No first-run screen**: LADO records Claude Code's `hasCompletedOnboarding` for a
  logged-in agent, and the approval of the `ANTHROPIC_API_KEY` it gives, as it records
  the folder trust (LAD-106).
- **Where a token goes**: `~/.lado/secrets/<NAME>` (600; in Docker on the home volume). The
  layers: login shell → outside folder (`secrets/`, `/run/secrets`) → LADO's secrets → the
  project → LADO and the CLI.
- **`lado doctor`**: `[ok] Claude Code login: Claude subscription (Max)`, `[warn] Claude
  Code login: not logged in: …`, `[info] Kilo login: none`.

## Decided with the human (question #1891, all recommendations)

1. One pull request.
2. LADO records Claude Code's first-run keys (the exception to "never touch the global
   config" grows by them).
3. A Claude agent without a login waits with the reason and starts by itself; other CLIs
   are not held.
4. The login window is the CLI's own command in a terminal, with phone helpers (not a form
   of LADO's).
5. A token or key from the UI goes to LADO's secrets folder; only the login variables a
   provider names.
6. Codex: status and the honest note, no login button until #113.
7. Log out and Remove ask first, naming the running agents.
8. `lado doctor` prints the logins; no `lado login` command.

## How the human checks it

- Docker, a fresh home volume, no Claude login: start a session from the UI on a phone →
  Needs you shows the login reason and "Log in…" → the section → "Log in with your Claude
  account…" → open the link, sign in, send the code → the window closes, "Logged in" → the
  supervisor starts by itself and reaches the chat; a new worker starts at once.
- Save a token on the page → the row says "token · LADO's secret"; a new agent runs on it;
  Remove → back to the subscription.
- `lado doctor` and `lado ls` print the login lines and reason.
