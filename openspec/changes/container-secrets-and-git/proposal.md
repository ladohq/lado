Task: LAD-76

## Why

LADO's image (`docker/`) runs LADO and its agents, but they cannot do real work there.
This is step T10 of the Docker install plan (docs/research/docker-install-plan.md).

- **No git identity.** The image has no `user.name` or `user.email`, so an agent's commit
  fails. The container tests set both with `-c`.
- **No way in for a variable.** An agent's environment comes from its login shell
  (`agent_env.resolve`), which in the container reads only the image's profile. A kit
  whose MCP server needs a variable (kit tracker-yougile: `${YOUGILE_API_KEY}`) is refused
  at the start (`kits.ResolvedAgent.mcp_servers`). `GH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`
  and model providers' keys have the same problem. Compose's `environment:` and
  `LADO_AGENT_ENV=inherit` would carry them, but both put the values in `docker inspect`,
  and `inherit` gives the agents the container's whole environment.
- **No GitHub over https.** git has no credential helper, and `gh` is not logged in (on a
  Mac its login is in the host's keychain).
- **ssh needs root's group.** Docker Desktop's ssh agent socket is `root:root`, mode 660,
  inside the container. The research prototype reached it with `group_add: ["0"]`, which
  is an extra right inside the isolation (research H8).
- **Logins are undocumented.** How Claude Code, OpenCode and Kilo log in inside the
  container is written nowhere.

Root cause: the image gives the agents nothing of the human's identity and access. Their
environment's one source, the login shell, cannot be fed from outside the container
without putting values in its configuration.

## What Changes

- **Variables from outside (core, `agent-variables`).**
  - `LADO_ENV_DIR` names a folder of files, one per variable: the file name is the
    variable's name, the content its value (one trailing newline dropped).
  - LADO lays them over the login shell's environment for each agent it launches, read
    anew at each launch.
  - A file LADO cannot take is not applied, and LADO names it with why in `lado doctor`
    and in the warnings of a session's start and resume (`lado start` on stderr, the UI's
    `Started.warnings`). Such a file is one in a subfolder, a hidden file, an invalid or
    reserved name, unreadable, too large, or not text.
  - Without `LADO_ENV_DIR`, nothing changes.
  - The image sets `LADO_ENV_DIR=/run/secrets`; compose mounts `./secrets` next to
    compose.yaml there, read-only.
  - No value reaches `docker inspect`, a log, the API or a bug report.
  - This folder is meant to become the read-only base of the profile `default` of the
    later profiles task.
- **git identity.** `LADO_GIT_NAME` and `LADO_GIT_EMAIL` (compose's `.env`, `docker run
  -e`) are written to the global git config on the home volume at every container start.
  Without them, and with none configured, `docker logs` gets one warning line.
- **GitHub over https.** The image's system git config makes `gh` git's credential helper
  for `https://github.com`. A `GH_TOKEN` file in `secrets/`, or `gh auth login` inside
  (its token on the home volume), gives `git push` over https and `gh api`.
- **The host's ssh agent without root's group.**
  - `LADO_SSH_AGENT` (in `.env`) names the host's socket. The default is `/dev/null`,
    which means no ssh. On a Mac it is `/run/host-services/ssh-auth.sock`; on Linux, the
    host's `$SSH_AUTH_SOCK`.
  - Compose mounts it at `/run/lado/ssh-agent.sock`, and the image's profile points the
    agents' `SSH_AUTH_SOCK` there when it is a socket.
  - At every start, a socket owned by uid 0 (Docker Desktop's) is given to `lado` by a
    second sudo rule for one fixed program with no arguments and no environment.
  - A socket `lado` still cannot use is one warning line in `docker logs`.
  - `group_add` is not needed.
- **Logins documented.** The headers of `docker/compose.yaml` and `docker/Dockerfile`
  say how Claude Code (`CLAUDE_CODE_OAUTH_TOKEN` in `secrets/`, or a login inside),
  OpenCode and Kilo (`opencode auth login` / `kilo auth login` inside, or providers' keys
  in `secrets/`) log in, and how to set up `secrets/`, git and ssh.
- **Tests.**
  - Unit: the folder's rules, precedence, warnings, `lado doctor`, compose and the
    Dockerfile.
  - Integration: a fake agent gets the variable, and a kit whose MCP server needs it
    starts.
  - Container: an agent commits under the given name, the credential helper gives
    `GH_TOKEN`, an ssh agent's key is listed through a root-owned socket and through a
    socket of the projects' owner, a kit with a variable starts, and no value is in
    `docker inspect`.
- **Version:** a minor (feature of the image and a new variable of LADO); CHANGELOG under
  `0.40.0 (unreleased)`.

## Scope

- `src/lado/agent_env.py`: the outside folder, its rules and the layer over the login
  shell.
- `src/lado/runtime.py`: the warnings of a start and resume, and a name LADO or the
  provider sets.
- `src/lado/doctor.py`: the check of the folder.
- `docker/` (Dockerfile, compose.yaml, profile.sh, entrypoint.sh, a new
  `ssh-agent-socket.sh`).
- The tests named above. AGENTS.md (Layout, How agents talk, Commands' container
  paragraph) and CHANGELOG.md.

## Out of scope

- **Profiles** (named sets of variables chosen per session, edited in the UI and with
  `lado profile`). The human decided it is a task of its own, outside the Docker plan
  (artifacts `profiles.md`, `critique.md`, `research.md` of run task/lad-76). Until then
  a container's variables are the same for every session; sessions that need other
  values run in another LADO container.
- **Setting variables from the UI.** That comes with profiles.
- **Values for one session from outside** (subfolders per session). Not needed before
  profiles.
- **https for hosts other than GitHub.** Those use ssh; a credential helper per host is
  not asked for.
- **Codex's login in the container.** That is T15; the human does not want Codex
  debugged now.
- **Masking secrets in agents' output, MCP-only secrets, short-lived tokens, a
  credential proxy.** These are later ideas from the research, listed with the profiles
  task.
- **Isolating secrets between agents of one LADO.** All agents run as one OS user and
  can read each other's environment; the headers say so.
- **`docs/research/docker-install-plan.md`.** lad-52's supervisor keeps it.

## Impact

- New behaviour only where `LADO_ENV_DIR` is set (the image), so a native install is
  unchanged.
- The image keeps one more sudo rule. It runs one fixed program that can only change the
  owner of a root-owned socket at a fixed path to `lado`.
- No schema, MCP tool, API or UI change.
