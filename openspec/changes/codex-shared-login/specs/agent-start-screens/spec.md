## ADDED Requirements

### Requirement: A Codex agent trusts its repository by its own config

Before a Codex agent starts, LADO SHALL write `trust_level = "trusted"` for the real path of
the session's repository's main root into the agent's own config.toml, unless the user's
Codex config has an entry Codex goes by for the agent's folder, which LADO SHALL carry as it
is (`untrusted` too); LADO SHALL write nothing into the user's Codex home. Codex's question
"Trust this folder?" SHALL then not hold the agent.

#### Scenario: A repository the user's Codex never saw
- **WHEN** a Codex session is started in a repository the user's Codex config has no entry
  for
- **THEN** the supervisor's config.toml trusts the repository's main root, the supervisor
  reaches its first hook with no human, and the user's config.toml is unchanged

#### Scenario: A worker in a worktree
- **WHEN** a Codex worker is spawned in its worktree
- **THEN** its config.toml trusts the main repository's root and it reaches its first hook
  with no human

#### Scenario: Untrusted by the user
- **WHEN** the user's Codex config marks the repository `untrusted`
- **THEN** the agent's config.toml carries `untrusted`, and the agent starts with no
  question

### Requirement: A Codex agent takes its repository's hooks without asking

When the agent's folder is trusted, LADO SHALL record in the agent's own config.toml the
hash Codex trusts each hook of the repository's own Codex config by (`.codex/hooks.json`
and the hooks of `.codex/config.toml` from the project root down), so Codex's question to
review them does not hold the agent, as a human who trusts the folder takes them; a hook
the user disabled in the user's Codex config SHALL stay disabled.

#### Scenario: A repository with hooks
- **WHEN** a Codex session starts in a repository whose `.codex/hooks.json` has a hook the
  user never reviewed
- **THEN** the supervisor reaches its first hook with no human and the repository's hook
  runs

#### Scenario: A hook the user disabled
- **WHEN** the user's Codex config has `enabled = false` for one of those hooks
- **THEN** the agent's config.toml keeps it disabled

### Requirement: A Codex agent starts without Codex's plugins

LADO SHALL write `features.plugins = false` into every Codex agent's config.toml, so Codex
does not fetch its plugins catalogue into the agent's home at the start.

#### Scenario: A new agent's home
- **WHEN** a Codex agent has started
- **THEN** its Codex home has no `.tmp/plugins`

### Requirement: A logged-in Codex agent starts with no screen in every mode

With a login and its repository trusted, a Codex agent SHALL reach its first hook with no
screen in each of LADO's permission modes for Codex (`default`, `bypassPermissions`) and
with none.

#### Scenario: Each mode
- **WHEN** a Codex session is started with `--permission-mode default`, with
  `bypassPermissions`, and with no mode, Codex logged in
- **THEN** each supervisor reaches its first hook with no human
