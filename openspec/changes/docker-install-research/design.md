## Context

LAD-52 is research: can LADO be installed and run through Docker so that a user who is
not a programmer avoids its system requirements, and what difficulties that brings. The
human chose (design dialogue): a report checked by hand on a prototype image on this Mac;
hands-on logins of Claude Code and Codex with the human's accounts, Kilo and OpenCode on a
local model; Windows and Linux from documentation; the web UI as the recommended way in;
a section on alternatives; drafts of implementation tasks at the end.

## Decisions

- D1. The report lives in `docs/research/docker-install.md`, a new `docs/research/`
  folder: it is neither a guide (docs/*.md), a design of something built
  (docs/design/) nor a review report (docs/superpowers/reports/). English, as the
  project's documents are; the human gets a Russian summary in the tracker.
- D2. The prototype is evidence, not a product: its Dockerfile and compose file sit under
  `docs/research/docker-install/` (or in the report's appendix), nowhere a build or CI
  picks them up. Shipping one is a drafted task.
- D3. The prototype pins each agent CLI at its provider's `TESTED_VERSION`
  (`providers/*.py`) and switches the CLIs' self-update off, so `lado doctor` inside
  warns about nothing it would warn about on a host; LADO itself from PyPI at the
  latest release (`uv tool install lado`).
- D4. LADO's state (LADO_HOME) and each CLI's login and config live in named volumes, the
  projects in one bind-mounted folder; the checks recreate the container to see what
  survives.
- D5. The human reaches LADO through the web UI on a published port of the host's
  loopback (`127.0.0.1:<port>`), the server started with `lado ui --host 0.0.0.0` inside;
  the report checks what the token guard and the Origin check do through the port map.
- D6. No change of LADO's code in this run: where the prototype needs one (e.g. Codex's
  login, `lado update` in a container), the check records the workaround used and the
  report drafts the task.
- D7. No CHANGELOG line and no version bump: users get nothing from this change.
- D8. Evidence is redacted before it is committed: no token, login file, account e-mail or
  home path of this machine (AC-7).

## Hands-on checks

Each is run on the prototype on this Mac and recorded in the report's section 4.

- H1. The image builds for linux/arm64; `lado doctor` inside passes (tmux, git, the four
  CLIs at their tested versions, the agents' environment from the container user's
  login shell).
- H2. `lado ui --host 0.0.0.0` inside, port published: the host's browser opens the UI
  with its token, starts a session on a bind-mounted repository from the New session
  window (what the folder picker shows), and opens an agent's terminal.
- H3. Claude Code: the human logs in with the subscription inside the container (the link
  opened in the host's browser); a LADO session's supervisor runs a turn on it; the login
  survives recreating the container (volume); `CLAUDE_CODE_OAUTH_TOKEN` from `claude
  setup-token` as the other way, by documentation or by hand.
- H4. Codex: the human logs in with ChatGPT inside (a published callback port or the
  device-code login, whichever works); whether a LADO Codex agent can use that login
  today (BACKLOG.md says LADO does not carry it) and which workaround makes it run.
- H5. Kilo and OpenCode: an agent of each runs a turn on LM Studio's model on the host
  through `host.docker.internal`.
- H6. A worker on the bind-mounted repository: its worktree and commit; then on the host,
  `git status`, `git worktree list` and the files' owner (the worktree's links hold the
  container's paths).
- H7. The container stopped and started again: what `lado ls` says, `lado start` resumes
  the session; recreated from the image: what survives on the volumes.
- H8. `git push` and `gh` from inside with the host's ssh agent (Docker Desktop's
  `/run/host-services/ssh-auth.sock`) on a scratch repository, never on the project's
  remote.

## Risks

- The human's logins take their time: the developer prepares everything else first and
  asks once, with the exact steps.
- A subscription login stored in a volume is a secret on disk: the report says where it
  is and the checks remove the volumes after the run.
