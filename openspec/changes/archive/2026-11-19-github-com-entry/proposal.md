Task: LAD-299

## Why

Agents reach github.com today with whatever GitHub login sits around LADO: a `GH_TOKEN` in
the outside folder (`secrets/` in Docker) or in the login shell, a project's `GH_TOKEN`
secret, or the GitHub CLI's own login (`gh auth login`, on the home volume in Docker, in the
keychain without it). Every other git server is one entry of Settings → Git servers with
one token, a check, a commit author and a way to sign out; github.com alone is refused
there (`github.com uses the GitHub CLI's login`), so the human cannot see which account
agents use, check it, give it a commit author, or sign out, and four places can change it
behind LADO's back. GitHub Enterprise servers are saved entries, but `gh` of the agents
gets no token for them, so an agent cannot open a pull request there.

The human decided (#7388, #7389) that access to git servers is configured only in LADO's
settings, never outside. This change makes github.com an entry like any other: the login
there today is taken over once into it, and from then on LADO and its agents use only the
entry.

## What Changes

- **github.com is a saved git server.** `lado git-server add github.com --token` signs in
  (it was refused), `remove github.com` signs out, `check` and `author` work for it as for
  any server. Its API is `https://api.github.com/user`.
- **The GitHub login is taken over once.** On the first start of this LADO (`lado ui`,
  `lado server`, `lado start`, the restart after `lado update`, the container's start),
  before any agent starts, LADO looks for the login agents use today: `GH_TOKEN`, else
  `GITHUB_TOKEN`, of the agents' layers (outside folder, login shell), else `gh auth token
  --hostname github.com`. It checks the token on GitHub and saves it as the github.com entry
  (unchecked when GitHub does not answer; not saved when GitHub refuses it). The command
  that did it prints one line, also for a refused token; `lado doctor` names the source and
  the date. It runs once per `LADO_HOME`, recorded in lado.db; an entry already saved is
  left as it is. Nothing outside is changed or removed.
- **The login outside LADO is no longer used.** Agents and LADO's own git get no
  `GH_TOKEN`, `GITHUB_TOKEN`, `GH_ENTERPRISE_TOKEN`, `GITHUB_ENTERPRISE_TOKEN`, `GH_HOST` or
  `GH_CONFIG_DIR` from any layer (project secrets included) and a `GH_CONFIG_DIR` of their
  own, so `gh` sees neither the outside token nor its own login. `GH_TOKEN` comes only from
  the github.com entry. `lado doctor` names each outside token that is set but not used
  (and `gh`'s own login in one info line); `lado project set <project> GH_TOKEN --secret`
  says so too. The page shows none of it: github.com's row is like any other (#7403).
- **`gh` gets the GitHub Enterprise entry's token.** `GH_ENTERPRISE_TOKEN` and `GH_HOST`
  of the GitHub Enterprise server that holds the session's repository (else of the only
  one saved), so an agent opens a pull request there.
- **Settings → Git servers.** github.com is a row of Servers like any other (Check, Replace
  token, Commit author, Remove server); without an entry it is added with `+ Add server`,
  which tells `GitHub answers.` and links `https://github.com/settings/tokens` with the
  scope `repo`. Servers' ⓘ names GitHub too. Nothing of its own: no block, no
  "not signed in", no line about the takeover or the outside login (#7403).
- **Clone hints for github.com** follow a saved server's or an unsaved host's: check it,
  or add it. `gh auth login`, `gh auth status` and `lado project set … GH_TOKEN --secret`
  leave them.
- **Docker.** The image's system credential helper for github.com (`gh auth
  git-credential`) goes; `compose.yaml`, `install.sh` and the Dockerfile's comments no
  longer offer `GH_TOKEN` or `gh auth login` and say where the GitHub login is now.
- **Leftovers of the last git servers change.** A failed clone's hint gives each command on
  its own line; Edit and Set author are off while the author's Remove or Undo asks; a failed
  clone's reason names the host with its port beside a server with a port; doctor names a
  lado.db locked for longer than 10 s instead of failing.
- **Schema 43**: the record of the takeover (when, from where, its outcome).

Mockup: the run's `mockup-github-server.html` (after the human's corrections #7403).

## Scope

`src/lado/git_servers.py`, `src/lado/git_kinds/github.py`, a new module
`src/lado/github_takeover.py`, `src/lado/state.py` (schema 43), `src/lado/agent_env.py`,
`src/lado/runtime.py`, `src/lado/clone.py`, `src/lado/doctor.py`, `src/lado/cli.py`
(`git-server`, `project set`, the takeover's line), `src/lado/server/` (git entries,
the server's start), `web/src/GitServers.tsx`, `docker/Dockerfile`, `docker/compose.yaml`, `docker/install.sh`,
`tests/` (unit, integration, vitest, UI e2e, container, `agent_helpers.previous_schema`),
docs (`docs/cli.md`, `docs/design/ui.md`, `docs/design/modules.md`, `docs/install.md`,
`docs/design/projects.md`), AGENTS.md's module line, CHANGELOG.md.

## Out of scope

- The host's ssh agent (`LADO_SSH_AGENT`): a task of its own.
- A company certificate: a later task.
- `glab` and GitLab merge requests: a later task.
- ssh for a server: out by the epic's statement.
- Several GitHub accounts, a token of a project's own: LADO is single-user, and the human
  chose settings only.
- Signing in to GitHub through the browser (GitHub's device flow): github.com is added with
  a token, as any server; a browser sign-in is a new flow (the brief's scope rule).
- A block of its own for github.com on the page, a "not signed in" state, and the page
  naming the takeover or the outside login: the human's #7403, github.com's row is like
  any other; the command's line and `lado doctor` say these instead.
- Changing or removing the login outside LADO (`secrets/GH_TOKEN`, the shell's, `gh`'s own
  login, a project's secret): it stays for a rollback and for the human's own terminal.
- A takeover after the first start: a GitHub login made later outside LADO is not taken;
  the human signs in in Settings.
- `gh` for several GitHub Enterprise servers in one session: `GH_ENTERPRISE_TOKEN` holds one
  token; the session's repository's server wins.
- The hint of a server's kind without a token on a real GitHub Enterprise (seen only against
  the fake): named as not verified in the pull request, unless a GitHub Enterprise is at
  hand.

## Impact

- Version: 0.48.0 is the next minor and unreleased; the change adds to its git servers
  entries. Schema migration 42 → 43.
- CLI: `lado git-server add|remove|check|author github.com`; the takeover's line on a first
  start; `lado doctor`'s GitHub lines; `lado project set … GH_TOKEN --secret` warns; clone
  hints for github.com.
- API: no new field; the Add form's check and Add take github.com.
- UI: github.com in Servers as any server; the Add form's github.com; Servers' ⓘ.
- Agents: `GH_TOKEN` from the entry only, their own `GH_CONFIG_DIR`, GitHub Enterprise's
  `GH_ENTERPRISE_TOKEN` and `GH_HOST`.
- Docker: the image loses the system helper of github.com.
