Task: LAD-89

## Why

This is step T8b of the Docker install plan (docs/research/docker-install-plan.md), a
fix to T10 (LAD-76) and T8 (LAD-83) before the first release candidate of 0.40.0.

- **compose does not start without `secrets/`.** `docker/compose.yaml` binds
  `${LADO_SECRETS:-./secrets}` at `/run/secrets` with `create_host_path: false` (LAD-76,
  D6: on Linux Docker would make the folder root's). Many people need no secrets: Claude
  Code, gh, OpenCode and Kilo log in inside the container, and the login stays on the home
  volume. So `mkdir -m 700 secrets` is an extra step of the minimal start, and everyone
  who comes from 0.39.0 with the new `compose.yaml` stumbles on it.
- **An update never brings the new compose.yaml.** The guide's "Update the container",
  README's Update and the header of `compose.yaml` say to change only `LADO_VERSION` in
  `.env`. Someone who installed 0.39.0 runs the new image with the old file and silently
  goes without `secrets/`, `LADO_GIT_NAME`/`LADO_GIT_EMAIL` and the host's ssh agent. This
  happens at every release that changes `compose.yaml`.

Root cause: the secrets folder was made a required bind, unlike the ssh agent's optional
one (LAD-76, D9); and the update was written as if `compose.yaml` never changed.

## What Changes

- **`secrets/` is optional, as the ssh agent is.** compose binds
  `${LADO_SECRETS:-/dev/null}` at `/run/secrets`; the long form, `read_only: true` and
  `create_host_path: false` stay, so a folder `LADO_SECRETS` names but that is missing is
  still refused.
- **The null device is "no folder".** `agent_env.outside` takes `LADO_ENV_DIR` naming the
  null device as it takes a missing folder: no layer and no line. So `lado start`, a
  resume (the server's lines in `docker logs`) and `lado doctor` say nothing about it. A
  regular file there still warns `not a folder`, inside a container or out.
- **`lado doctor` in a container without secrets says how to give them.** In a container,
  for no folder or the null device: `[info] Variables from outside: /run/secrets: none`,
  with the hint `to give the agents variables: LADO_SECRETS=./secrets in compose's .env
  and mkdir -m 700 secrets (docker run: -v <folder>:/run/secrets:ro);
  docs/install.md#the-agents-variables`. Outside a container: `no folder`, as now. Exit
  code 0 either way.
- **Secrets are enabled by one line.** `LADO_SECRETS=./secrets` in `.env`, then `mkdir -m
  700 secrets`. Said in the headers of `compose.yaml` and the Dockerfile, README's Docker
  install and docs/install.md: the minimal start has no `mkdir`; "The agents' variables"
  enables them as a step of its own. The Dockerfile's `docker run` drops `mkdir` and gives
  `-v "$PWD/secrets:/run/secrets:ro"` as the optional addition.
- **Every update takes the version's compose.yaml.** In the header's update, the guide's
  "Update the container" and README's Update: in the folder of `compose.yaml`, download
  that version's file next to `.env` (`curl -fLO
  https://github.com/ladohq/lado/releases/download/v<version>/compose.yaml`), set the new
  `LADO_VERSION` in `.env`, then `docker compose up -d`. `.env`, `secrets/` and the home
  volume stay; a change made to `compose.yaml` by hand must be carried over (the guide
  says so). Going back keeps the current `compose.yaml`.
- **CHANGELOG.** The 0.40.0 lines of LAD-76 and LAD-83 are amended, not contradicted:
  `secrets/` is optional and enabled by `LADO_SECRETS=./secrets`; coming from 0.39.0 needs
  the new `compose.yaml`, without which there is no git identity (`LADO_GIT_NAME`,
  `LADO_GIT_EMAIL`), no ssh agent (`LADO_SSH_AGENT`) and no `secrets/`.
- Specs `container`, `agent-variables`, `image-release`; `docs/design/modules.md` and
  `docs/design/agents.md`.

## Scope

In: the compose bind's default, `agent_env.outside` and `doctor.check_outside`, the
headers, README, docs/install.md, CHANGELOG, design docs, unit and container tests, the
steps of the check by hand in the pull request.

## Out of scope

- **LADO noticing an old compose.yaml by itself** (a version mark in compose's
  `environment:`, a line in `docker logs` and System): task LAD-90, created on the
  human's yes (2026-10-16). Inside the container an old `compose.yaml` cannot be told from
  `docker run` (neither has a mark), so it would not help the step from 0.39.0 at all, and
  is not small.
- `create_host_path: true` for the secrets folder: rejected, the folder would be root's on
  Linux (LAD-76, D6).
- Any other character device, or another path, read as "no secrets": only the null device
  is the "none" compose gives; anything else is a mistake worth a warning.
- Spec `repos-folder`: none of its requirements names the secrets folder, so it has no
  delta.
- The plan file docs/research/docker-install-plan.md: not touched.
- Other containers and volumes: nothing in the steps or docs touches them; no `prune`.

## Impact

- Code: `src/lado/agent_env.py` (`outside`), `src/lado/doctor.py` (`check_outside`).
- Image: `docker/compose.yaml` (default and header), `docker/Dockerfile` (header).
- Docs: README.md, docs/install.md, docs/design/modules.md, docs/design/agents.md,
  CHANGELOG.md (0.40.0, amended lines).
- Tests: `tests/test_agent_env.py`, `tests/test_doctor.py`, `tests/test_runtime.py`,
  `tests/test_docker.py`, `tests/container/` (conftest, a start without secrets, secrets
  by `LADO_SECRETS=./secrets`).
- Version: inside 0.40.0 (unreleased), a minor already; no further bump. No schema change,
  no MCP or CLI change.
