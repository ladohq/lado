# Provider login layers (LAD-160)

Change: `openspec/changes/provider-login-layers/` (proposal with AC-1..AC-9, delta specs
of `provider-logins` and `agent-variables`, `design.md` with the decisions D1-D9). This
document is the human's view: what a user gets, what was decided with the human, and how
the human checks it. Mockup: the run's artifact `mockup-login-ladder.html`.

## What a user gets

- **One line and one button per CLI** in Settings → Providers and environment:
  ```
  Claude Code 2.1.295
  ● Logged in · Subscription (token) · LADO's secret      [Change login…]
  OpenCode 1.18.35
  ● Logged in · 2 credentials, 1 variable                 [Change login…]
  Kilo 7.8.8
  ○ No login                                              [Log in…]
  Codex 0.162.0
  ● Logged in · ChatGPT
    Codex agents do not get this login yet (GitHub #113) …
  ```
  Without a Claude login: "Not logged in" in bold, the waiting agents as links, and the
  primary "Log in…". The layer is one of: LADO's secret, outside folder, login shell,
  Claude Code's login file.
- **"How do you pay for Claude?"**: Subscription — Claude Pro or Max (paste a token made
  with `claude setup-token` on any computer with Claude Code) or Pay per use — API billing
  (paste an API key); Save keeps it as LADO's secret and replaces the other one; "Log
  out…" removes it after naming the running Claude agents.
- **OpenCode and Kilo**: the button opens their own login in a terminal, as in LAD-157,
  with "Log out of one…".
- **The ladder**: login shell → outside folder (`secrets/`) → LADO's secrets → project;
  each layer overrides the one before, and the layer that sets any login variable of the
  CLI gives the whole login. Claude Code's own login file is below them all.

## Decided with the human

- Session lad-157 (`decision-provider-login-ux`): one state line and one button; the sheet
  asks how the human pays; OpenCode and Kilo follow the pattern; Codex keeps its note.
- #1963 → #1965: no remembered choice and no "set but not used"; keep the ladder and say
  on which layer the agent is logged in; the account login can be a secret.
- #1966 → #1971: LADO generates no token or key; the human pastes a ready one.
- #1972, #1976: the Claude login window and the logout of Claude Code's file go; the
  file's login is shown as the lowest step (it cannot be copied into a secret: its token
  lives hours and is refreshed by the CLI); a login comes whole from one layer; Log out
  only for LADO's secrets.

## Engineering decisions (design.md)

D1 `agent_env.layers`/`merge` with the whole-login rule, applied per agent's provider;
D2 the layer's words; D3 Claude's method words; D4 the provider's question and choices;
D5 Claude's login and logout commands and the logout route go; D6 Save replaces, Log out
removes LADO's login; D7 API fields; D8 the row and `LoginSheet.tsx`; D9 LAD-161, 0.44.0,
tests.

## How the human checks it

1. A clean LADO in Docker (`make docker`, compose without secrets): Claude Code's row says
   "Not logged in" with "Log in…"; paste a token from `claude setup-token` (from a phone
   too); the row says "Logged in · Subscription (token) · LADO's secret" and the waiting
   supervisor starts.
2. Put an API key into `secrets/ANTHROPIC_API_KEY`: the row still says the token from
   LADO's secret, and a new Claude agent works with the token (its `/status`).
3. Log out in the sheet: the confirmation names the running agents; the row then says
   "Pay per use (API key) · outside folder".
4. A project with its own `CLAUDE_CODE_OAUTH_TOKEN`: the row names it; its sessions use it.
5. OpenCode: "Change login…" opens `opencode auth login` directly.
