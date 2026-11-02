Task: LAD-160

## Why

Symptom: after LAD-157, Settings → Providers and environment is hard to read. A Claude
Code user who is logged in sees three buttons ("Log in with your Claude account…", "Log
in with Anthropic Console…", "Log out…"), two secret fields named by their variables
(`CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY`), the login file's path and the rule "it
wins over the login file". It does not say what they have now or what to press. And a
login made on the page can lose without a word: a login through the Claude account (its
file) loses to a token in the outside folder (`secrets/`) or the login shell, and a token
saved on the page loses to an `ANTHROPIC_API_KEY` of the login shell.

Cause: LAD-157 built the page from the mechanism (each login command, each variable) and
not from the human's question ("how do I pay for Claude?"). And the environment's layers
(login shell → outside folder → LADO's secrets → project) override one another only name
by name: a layer that sets `CLAUDE_CODE_OAUTH_TOKEN` does not hide an `ANTHROPIC_API_KEY`
of a lower one, and then Claude Code's own order decides (`ANTHROPIC_API_KEY`, then
`CLAUDE_CODE_OAUTH_TOKEN`, then its login file), not the layer the human set.

The human's decision, in session lad-157 (`decision-provider-login-ux`, mockup
`mockup-claude-login-v1.html`) and in this run's questions #1963, #1966, #1972, #1976
(mockup `mockup-login-ladder.html`):

- the page shows per CLI one state line, which says the layer the login comes from, and
  one button;
- Claude Code's sheet asks "How do you pay for Claude?": Subscription — Claude Pro or
  Max (paste a token made with `claude setup-token`) or Pay per use — API billing (paste
  an API key); LADO keeps it as its secret; LADO generates no token or key and runs no
  Claude login command;
- the layers stay as they are, each over the one before, and LADO says on which layer
  the agent is logged in; a project's login still wins;
- a login of the Claude account already in Claude Code's own file is shown as such and
  is the lowest step: any token or key overrides it;
- OpenCode and Kilo keep their own login command in the sheet; Codex its note.

Options weighed with the human:

- A, "the login chosen on the page wins" (#1963, proposed first): LADO remembers a choice
  and leaves out the competing variables of the lower layers. Rejected (#1965): one more
  rule and more words on the page ("set but not used").
- B, "the layers, and the account login saved as a secret by `claude setup-token`"
  (#1966): LADO would read the token out of the CLI's terminal (text that changes between
  versions, a token wrapped over lines). Rejected (#1971): LADO generates nothing; the
  human brings a ready token or key.
- C (taken), "the layers, ready values only, a login as a whole per layer" (#1972,
  #1976). Long-term cost: the agent's environment is built with one more rule (the
  highest layer that sets any of a provider's login variables gives all of them); the
  Claude login window goes, so a phone alone cannot make a new subscription token.
- Copying Claude Code's file login into a secret (#1976): not possible; the file holds a
  short-lived access token and a refresh token that only the CLI uses.

Held against ROADMAP.md and AGENTS.md's Design principles: neutral core (the rule uses
only a provider's `login_variables`; the sheet's choices come from the provider: Claude
Code two, OpenCode and Kilo none, Codex no button), one source of truth (the state is
the CLI's own status command, read in the environment the agents get; no file of
choices), no silent drop (the state line names the layer that gives the login; a project
with its own login is named), only what is used (the Claude login and logout commands and
the logout route go with their buttons).

## What Changes

- **The row**: name, version, a dot and one state line "Logged in · <how> · <layer>"
  (`Subscription (token) · LADO's secret`, `Pay per use (API key) · login shell`,
  `Subscription (Max) · Claude Code's login file`, …), "Not logged in" or "No login" or
  "Unknown: …"; the agents that wait for the login; the projects with their own login;
  the provider's note; one button: "Log in…" without a login (primary when its agents need
  one), "Change login…" with one, none for Codex.
- **Claude Code's sheet**: "How do you pay for Claude?" with Subscription — Claude Pro or
  Max (where a token comes from: `claude setup-token` on any computer with Claude Code)
  and Pay per use — API billing (an API key from the Anthropic Console), the current one
  marked; the chosen one's secret field and Save; "Log out…" while the login comes from
  LADO's secrets, asking first and naming the running Claude agents. Saving one removes
  the other login variable from LADO's secrets.
- **OpenCode's and Kilo's sheet**: opens on their own `auth login` in the terminal (LAD-157's
  window), with "Log out of one…" while logged in.
- **A login as a whole per layer**: of the layers below LADO's and the provider's own
  variables, the highest that sets any of the agent's provider's login variables gives
  them all; the provider's login variables of lower layers do not reach the agent. With
  one login variable per layer, nothing changes.
- **Gone**: Claude Code's login actions ("Log in with your Claude account…", "…Anthropic
  Console…"), its "Log out…" of the login file (`claude auth logout`, the route `POST
  /api/providers/{name}/logout`), the two secret fields on the row.
- Claude Code's methods are named by how the human pays: "Subscription (<Plan>)",
  "Subscription (token)", "Pay per use (API key)", "Pay per use (Console)"; `lado doctor`
  prints them with the layer.
- docs/design/ui.md, docs/design/agents.md, docs/design/modules.md, docs/cli.md,
  docs/install.md (Docker: a token from `claude setup-token` pasted on the page or put in
  `secrets/`), CHANGELOG.md (0.44.0's Added line).
- A feature in the unreleased minor 0.44.0 (already a minor). No schema migration.

## Scope

- Settings → Providers and environment: the row and its one button.
- The sheet: Claude Code's choice and paste, Log out; OpenCode's and Kilo's own login.
- The rule "a login as a whole per layer" for every agent, waiting window, login window
  and the page's state.
- Claude Code's method words, with the layer, in the page and `lado doctor`.
- Tests: unit, API, integration with the fake agent, vitest, UI e2e.

## Out of scope

- Refusing to start a session or a worker whose CLI needs a login and has none: LAD-161,
  run in a parallel session; it may touch `logins.py` and the session form, so whichever
  pull request lands second merges the other's.
- Making a token or key in LADO (`claude setup-token`, `claude auth login`): the human
  brings a ready one (#1971).
- Logging out of Claude Code's own login file from the page: the CLI keeps it, any token
  or key overrides it; `claude auth logout` in a terminal removes it (docs) (#1976).
- A login that Codex agents get: GitHub #113.
- Checking a token or key with the provider's server: a wrong token still shows as
  logged in, and the agent fails at its first turn.
- `ANTHROPIC_AUTH_TOKEN` and the cloud providers' variables as login variables: they
  serve gateways and clouds, not the two ways to pay the sheet offers.

## Decisions for the record

The technical decisions D1-D9 are in `design.md`.

## Acceptance criteria

- AC-1. A logged-in Claude Code row shows its version, one state line with how and from
  which layer ("Logged in · Subscription (token) · LADO's secret") and one button
  "Change login…"; no field, path or second button. Without a login: "Not logged in", the
  waiting agents and the primary "Log in…".
- AC-2. "Log in…"/"Change login…" opens "How do you pay for Claude?" with the two choices,
  the current one marked; a token saved under Subscription (or a key under Pay per use)
  is kept as LADO's secret, never shown or returned again, removes the other one from
  LADO's secrets, and the row shows the new state. The same at a phone's width.
- AC-3. With `CLAUDE_CODE_OAUTH_TOKEN` in the outside folder and an API key saved on the
  page, a new Claude agent gets the key and not the token; the row says "Pay per use (API
  key) · LADO's secret".
- AC-4. With `ANTHROPIC_API_KEY` in the login shell and a token saved on the page, a new
  Claude agent gets the token and not the key.
- AC-5. A project with its own login variable gives its sessions' agents its login, and
  none of the lower layers'; the row names such projects.
- AC-6. With a Claude account login in Claude Code's file and no variable, the row says
  "Logged in · Subscription (<Plan>) · Claude Code's login file"; a token saved on the
  page overrides it.
- AC-7. "Log out…" (login from LADO's secrets) asks first, naming the running Claude
  agents, removes the token or key, and the row shows what the other layers give.
- AC-8. OpenCode's and Kilo's button opens their own `auth login` in the sheet, with "Log
  out of one…" while logged in; Codex's row has its note and no button.
- AC-9. `lado doctor` prints Claude Code's login with the new words and the layer.
