## MODIFIED Requirements

### Requirement: LADO uses only the access the machine has

LADO's git calls of a clone or listing SHALL run with no terminal and no prompt (no
controlling terminal, stdin closed, `GIT_TERMINAL_PROMPT=0`, `GIT_ASKPASS` empty, `SSH_ASKPASS_REQUIRE=never`,
`GCM_INTERACTIVE=never`, `LC_ALL=C`), in the environment of LADO's own git calls (LADO's
process environment with the outside folder's variables over it, and a project's for a
clone into a project: capability `agent-variables`), so a missing credential is a
failure, never a wait. LADO SHALL neither ask for nor keep a password, passphrase or
token.

#### Scenario: A private https repository without a login
- **WHEN** the URL is `https://github.com/acme/private` and git cannot read a username
- **THEN** the kind is `login_needed` with the hint `gh auth login`, and LADO did not wait

### Requirement: A login or access failure points at the machine's login

The login and access kinds SHALL be:

| Kind | Reason | Hint (sentence: command) |
|---|---|---|
| `login_needed` | `<host> asks for a login` (other hosts: `…; set up a git credential helper for it on this machine`) | github.com, a clone or listing into project `<id>`: `Give the project a GitHub token:` `lado project set <id> GH_TOKEN --secret`; github.com otherwise, when the outside folder `<folder>` (`LADO_ENV_DIR`) is a folder: `Log in with GitHub's CLI, or put a token into the file GH_TOKEN of <folder> (LADO_ENV_DIR):` `gh auth login`; github.com otherwise: `Log in with GitHub's CLI on this machine:` `gh auth login`; other hosts none |
| `not_found` | `no repository there, or this machine's account cannot read it` | github.com: `See which GitHub account this machine uses:` `gh auth status`; other hosts none |

#### Scenario: A repository GitHub does not show
- **WHEN** git prints `ERROR: Repository not found.`
- **THEN** the kind is `not_found` with the hint `gh auth status`

#### Scenario: A login asked for in a project's clone
- **WHEN** `lado project repo add shop https://github.com/acme/private` fails because git
  cannot read a username
- **THEN** the kind is `login_needed` with the hint `Give the project a GitHub token:`
  `lado project set shop GH_TOKEN --secret`

#### Scenario: A login asked for with an outside folder
- **WHEN** `LADO_ENV_DIR=/run/secrets` names a folder, it has no `GH_TOKEN`, and a clone
  of `https://github.com/acme/private` without a project fails because git cannot read a
  username
- **THEN** the hint is `Log in with GitHub's CLI, or put a token into the file GH_TOKEN of
  /run/secrets (LADO_ENV_DIR):` `gh auth login`

#### Scenario: A login asked for with no outside folder
- **WHEN** `LADO_ENV_DIR` is unset, or names the null device, and the same clone fails
  the same way
- **THEN** the hint is `Log in with GitHub's CLI on this machine:` `gh auth login`

## ADDED Requirements

### Requirement: A kit's or marketplace's git failure is told by the clone's kinds

A git failure of LADO's network calls for kits, skill packs and marketplaces (a remote's
tags, a pinned clone, a marketplace's clone and update) SHALL be told by the kinds and
texts of a clone's failure, on one line: `<LADO's head>: <reason> (<git's line>)`, then
`. ` and the hint's sentence and command when the kind has one; a failure of no known kind
SHALL keep `<LADO's head>: <git's line>`. These calls SHALL run with the same no-prompt
variables as a clone, and never in a project's layer.

#### Scenario: A private kit without a token
- **WHEN** `lado kits add https://github.com/ladohq/kit-epic.git` runs, the outside folder
  `/run/secrets` has no `GH_TOKEN`, and git cannot read a username
- **THEN** it fails with `cannot read the tags of https://github.com/ladohq/kit-epic.git:
  github.com asks for a login (fatal: could not read Username for 'https://github.com':
  terminal prompts disabled). Log in with GitHub's CLI, or put a token into the file
  GH_TOKEN of /run/secrets (LADO_ENV_DIR): gh auth login`

#### Scenario: A failure of no known kind
- **WHEN** a kit's pinned clone fails with git's `fatal: bad object` line
- **THEN** the text ends with `: fatal: bad object` and carries no hint
