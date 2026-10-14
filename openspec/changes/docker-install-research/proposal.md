Task: LAD-52

## Why

Installing LADO asks a lot of a user who is not a programmer: tmux, git, uv, Node.js and an
agent CLI, each installed and found on the right `PATH`, and on Windows a whole Ubuntu in
WSL2 first (docs/install.md). The question of LAD-52 is whether LADO could ship as a Docker
image instead, so that such a user installs Docker and runs one command, and what that
would cost: above all whether the agent CLIs work inside a container and log in to their
subscriptions correctly, and what else breaks.

This change answers that question with a research report checked by hand on a prototype
image. It builds nothing users get: implementation tasks are drafted at the report's end
and created in the tracker only on the human's yes.

## What Changes

- A new research report, `docs/research/docker-install.md` (English), with these sections
  in this order:
  1. **Summary**: the verdict (is a Docker install worth building, for whom, in what
     shape) in at most 15 lines, with the three largest difficulties.
  2. **Today and with Docker**: what a non-programmer installs and types today on macOS,
     Windows and Linux, and what they would with the image.
  3. **The prototype**: what the image holds (base, user, init process, tmux, git, uv,
     LADO, Node.js, the four agent CLIs pinned at their `TESTED_VERSION`), its volumes
     (LADO_HOME, each CLI's login and config, the projects folder), its port, how it is
     started (a compose file or one `docker run`), and how the human reaches it (the web
     UI from the host's browser, the agents' terminals in the UI).
  4. **Hands-on checks**: one row per check H1-H8 of the design (what was done, the
     result `works` / `works with a workaround` / `does not work` / `not checked`, the
     evidence: a command and its output, or a screenshot).
  5. **Difficulties**: each with its cause, what the user would see, and 1-3 ways out
     with their cost: the logins of each provider; the project's own toolchains the
     agents need (compilers, runtimes, test tools); paths of the container against the
     host (stored repo paths, the UI's folder picker, git worktree links seen from the
     host); file ownership on a Linux host; git credentials and push (ssh agent, `gh`);
     the UI server inside (host, port, token, no browser to open); updates (`lado update`
     against a new image); the container's life (tmux and agents end with it, resume,
     an init that reaps processes); Docker in the agents' tools (a project whose tests
     need Docker); local models on the host; speed of bind mounts; images for arm64 and
     amd64; Docker Desktop's licence and resources; security (the container as a sandbox
     for agents with bypassed permissions); what `lado doctor`, telemetry's installer and
     the macOS keychain logic (`gui_session`) mean in a container.
  6. **Platforms**: macOS (checked), Windows with Docker Desktop over WSL2 and Linux
     (from documentation, marked not checked).
  7. **Alternatives**: a one-command install script, a Homebrew formula, the desktop app
     of ROADMAP stage 7, a dev container; each against the same pain, with a
     recommendation of what to build first.
  8. **Proposed tasks**: drafts of implementation tasks (title in Russian, what it does,
     size S/M/L, what it depends on), in the order to build them.
- An appendix of the report, or files beside it under `docs/research/docker-install/`,
  holds the prototype's Dockerfile and compose file as checked; they are evidence, not a
  shipped artifact.
- A comment on LAD-52 in Russian with the report's summary and the list of proposed tasks.

## Scope

- Desk research of every difficulty in section 5 and of the platforms and alternatives.
- A prototype image built and run on this Mac (Docker Desktop 4.88, arm64), with the
  hands-on checks H1-H8 of the design.
- The human's part in the checks: opening the login links of Claude Code (subscription)
  and Codex (ChatGPT login) and signing in. The developer asks the human for it when the
  image is ready.

## Out of scope

- Shipping an image (a release workflow, a registry such as GHCR, a `docs/install.md`
  section): implementation tasks drafted in the report, the human's decision to research
  first.
- Any change of LADO's code, e.g. carrying Codex's login to its agents (BACKLOG.md) or
  refusing `lado update` inside a container: the report names what is needed; the tasks
  come after.
- Hands-on checks on Windows and Linux hosts: from documentation only, the human's
  decision (no such host here); the report marks them not checked.
- Hands-on logins of Kilo and OpenCode with an account: they are checked on LM Studio's
  local model on the host, their account logins from documentation (the human's
  decision).
- Creating tracker tasks from the report: only on the human's separate yes.

## Acceptance criteria

- AC-1: `docs/research/docker-install.md` exists, in English, with the eight sections of
  What Changes in that order, and its Summary gives a verdict and the three largest
  difficulties.
- AC-2: Section 4 has a row for each of H1-H8 with a result and its evidence; a check not
  done says `not checked` and why.
- AC-3: Section 5 covers each difficulty listed in What Changes, each with its cause, what
  the user sees and at least one way out with its cost; every claim about LADO's own
  behaviour names the code or doc it comes from, every claim about a CLI or Docker names
  its source (a link, or the hands-on check).
- AC-4: The prototype's Dockerfile and compose file are in the report's appendix or under
  `docs/research/docker-install/`, as they were when the checks ran, and pin each agent
  CLI at its provider's `TESTED_VERSION`.
- AC-5: Section 8 lists draft implementation tasks, each with a size and dependencies;
  no tracker task is created.
- AC-6: LAD-52 has a Russian comment with the summary and the proposed tasks.
- AC-7: No secret, token, login file or personal path of the machine is in the report,
  its evidence or the commits (outputs redacted).

## Impact

- Docs only: `docs/research/docker-install.md` (new) and its prototype files. No code,
  API, schema, spec or CHANGELOG change: nothing users get, no release bump.
