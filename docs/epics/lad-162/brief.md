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

- Goal and "done": covered by S1–S5, the done of the epic is S5's human check (above).
- Users and how they use it: covered by S1, Check: a server added in Settings is used by
  agents by host. The single LADO user; nothing per session or project.
- Scope and what is out: covered by the plan's Steps and Later. Out: ssh, Bitbucket/Gitea, several accounts per
  server, the host's ssh agent; kit sdlc's example (step 5) is in another repository and
  goes to Later (D6).
- Data and migrations: covered by S1 (the server list, its way back) and S3, Check: an
  upgrade test; the GitHub login becomes the github.com entry without removing its
  sources (D5).
- Secrets and credentials: covered by S1, Check: clone and push with no prompt, no token
  in a git config file. Tokens in LADO's secret store; a credential
  helper per agent process; no interactive password prompt.
- Update and rollback: covered by S1 and S3, Check: the old path runs after the upgrade. Rollback to 0.47 keeps working: `GH_TOKEN` and
  `gh`'s login are kept (D5).
- Removal: covered by S1, Check: a removed server's host behaves as before. A server removed from the list: its host works as today (D5).
- Platforms: covered by S1 (native and Docker, integration tests), S5 (the image). Docker (main, the human's check: Docker on a Mac, D3) and
  native macOS/Linux, where `GIT_CONFIG_*` per process works too.
- Observability: covered by S2 and S4, Check: each failure reason in plain words. "Check" in Settings with a reason in plain words (bad
  token, missing rights, untrusted server, unreachable), `lado doctor`, clone hints.
- Tests and what only a human can check: covered by each step's Check; the human's check
  after S5. Tests with a fake git server
  over https; only the human checks the company GitLab (D3).
- Documentation: covered by each step ("docs describe what was built") and S6. Each step documents what it built; step 4 writes the
  plain guide (D4).

## Branch strategy

Every step merges into `main` and leaves the product working (D2).

## Tracker

Epic task: LAD-162. Step tasks are created one at a time, when the step is reached, linked
`derived` to LAD-162.

## Verdict

Ready to plan.
