# Brief: Git servers (LAD-162)

## The human's statement

The tracker task LAD-162 (an epic; its description was rewritten before this run) and the
session brief `brief-lad-162`, with the design `git-servers-design`, the code map
`git-hosts-analysis` and the research `git-servers-research` (session artifacts, in
Russian). In short:

> LADO and its agents in practice work with github.com only: the Docker image sets up https
> access for github.com alone (through `gh`'s credential helper), ssh knows GitHub's host
> keys only, there is no company certificate and no access check, and the clone hints and
> `docs/install.md` speak of GitHub only. So LADO does not work with a company GitLab on an
> internal domain — and the human means to try LADO on exactly that.
>
> Goal: the user adds a git server in **Settings → Git servers** (kind GitHub or GitLab,
> address, a token with a "where to get it" link, optionally the commit author's name and
> email and the company certificate, a "Check" button), and LADO itself gives agents the
> token, the author and the certificate by the host of the repository's address.

On running it (2026-11-15): «я предлагаю работать по одной задаче. Находки и недоделки
смогут войти в очередной этап по эпику» — one tracker task per step, created when the step
is reached; findings and leftovers go into the next step.

The statement's decisions (not reopened):
- LADO is single-user: one token per server; no several accounts on one server.
- The server is chosen only by the host of the repository's address; nothing is chosen
  per session or project.
- https with a token only; `git@server:…` addresses go over https. ssh comes later as an
  optional field of a server.
- The company certificate is needed now.
- The host's ssh agent (`LADO_SSH_AGENT`) is not developed further; where it is set up it
  keeps working.
- GitHub and GitLab first; the server kind is an extensible module (Bitbucket, Gitea later).
- The user's global git config is never touched: everything is given to the agent's
  process (`GIT_CONFIG_*`, LADO's own credential helper, `GIT_AUTHOR_*`, `GIT_COMMITTER_*`).
- Today's GitHub login (`GH_TOKEN`, `gh auth login`) becomes the github.com entry; nothing
  breaks for existing users.
- Explain to the human in plain words.

Proposed steps: 1 Git servers (Settings section, credentials for agents, ssh addresses over
https, clone hints and `lado doctor` from the list, GitHub login migrated; large, minor
version, maybe two pull requests: core, then UI); 2 company certificate; 3 GitLab (`glab`
in the image configured from the server entry, agents open merge requests); 4 the guide
"Connect your own git server"; 5 kit sdlc's GitLab example (repository kit-sdlc).

## Goal and done

Done when, in LADO in Docker on a Mac with the company GitLab reached through the
company's VPN: a GitLab server with its token in Settings checks green; an agent clones,
commits with the given author, pushes and opens a merge request; github.com works as
before, also for a user who logged in with `GH_TOKEN` or `gh auth login`; a host not in the
list behaves as today and the UI suggests adding it; `~/.gitconfig` is unchanged.

## Readiness checklist

- Goal and "done": covered by S5, Check: "Then the human's check, on the release
  candidate that carries S5 … github.com works as before."
- Users and how they use it: covered by S1b, Check: "a UI e2e test adds a gitlab.com and
  a self-hosted server … and removes one".
- Scope and what is out: covered by the plan's Steps and Later.
- Data and migrations: covered by S1a, Check: "the upgrade and rollback test of the way
  back"; S2a and S4 the same; S3, Check: "an integration test of an upgrade".
- Secrets and credentials: covered by S1a, Check: "clone and push by https with no
  prompt"; the token in LADO's secret store under `LADO_HOME`, never in a git config file.
- Update and rollback: covered by the plan's way back and S3, Check: "after a rollback
  … the old path works — checked by running it after the rollback". A rollback restores
  lado.db from before the migration: the entries are gone, their files stay unused.
- Removal: covered by S1a, Check: "a removed server's host behaves as before".
- Platforms: covered by S1a, Check: "git older than … (2.31) is refused loudly" and "a
  real CLI's git uses the entry — the smoke layer for Claude Code and Codex"; S5 the image.
- Observability: covered by S2b, Check: "'Check' … say 'works, this is <name>' or why not
  in plain words"; S4 the untrusted server.
- Tests and what only a human can check: covered by each step's Check; the human's check
  in S5.
- Documentation: covered by each step ("docs describe what was built") and S6.

## Branch strategy

Every step merges into `main` and leaves the product working (D2).

## Tracker

Epic task: LAD-162. Step tasks are created one at a time, when the step is reached, linked
`derived` to LAD-162.

## Verdict

Ready to plan.
