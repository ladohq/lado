## Context

`docker/compose.yaml` binds the secrets folder at `/run/secrets` with no default but
`./secrets` and `create_host_path: false` (LAD-76, D6), so compose refuses to start
without it. The ssh agent's bind already shows the optional form: `${LADO_SSH_AGENT:-/dev/null}`
(LAD-76, D9). `agent_env.outside()` already treats a missing `LADO_ENV_DIR` folder as "no
layer, no line" (`FileNotFoundError`): `docker run` without the folder and the new image
under 0.39.0's `compose.yaml` are silent today. Only the null device at `/run/secrets`
would warn: `os.scandir` raises `NotADirectoryError`, which gives `not a folder` in `lado
start`'s warnings, in a resume's (the server's lines in `docker logs`) and as `[warn]` in
`lado doctor`.

The human's decision (2026-10-16): option A, the same as the ssh agent; the null device is
"no secrets", silently; secrets are enabled by `LADO_SECRETS=./secrets` in `.env` and
`mkdir -m 700 secrets`. Answers to the design round (2026-10-16): doctor gives an `[info]`
line with the way to enable them; every update downloads the version's `compose.yaml`;
LADO noticing an old `compose.yaml` is a task of its own.

## Decisions

### D1. The null device is "no folder", in `agent_env.outside`

`outside()` returns `Outside(folder, {}, [])`, as for a missing folder, when the path is a
character device whose `st_rdev` equals that of `os.devnull` (`os.stat`, following links).
Anything else that is not a folder still gives `not a folder`.

Options:
- (a, chosen) The special case in `outside()`: one place, used by `resolve()`, the start's
  and resume's warnings (`runtime._outside_warnings`) and `lado doctor`, so all three
  agree with no second rule. It holds for any launcher, with every provider (it is above
  `providers/`), inside a container or out. Cost: one more branch of a small function.
- (b) The entrypoint unsets `LADO_ENV_DIR` when `/run/secrets` is not a folder. The
  variable is also set in the image's `ENV` (for `docker exec`) and in `profile.sh` (for
  the agents' login shells), so `docker compose exec lado lado doctor` would still see it
  and warn: two more places to keep in step. Rejected.
- (c) Any character device is "none". Broader than needed; another device there is a
  mistake worth naming (no silent drops). Rejected.

Comparing `st_rdev` rather than the path catches `/dev/null` bind-mounted at
`/run/secrets` (compose's default), where the path is not `/dev/null`.

### D2. compose's default is `/dev/null`, the bind otherwise unchanged

`source: ${LADO_SECRETS:-/dev/null}`, `target: /run/secrets`, `read_only: true`,
`create_host_path: false`, the long form: the ssh agent's pattern. A folder
`LADO_SECRETS` names but that is missing is still refused, never made root's.
`create_host_path: true` stays rejected (LAD-76, D6). With several LADO containers on one
machine each `.env` names its own folder or none; nothing is shared.

### D3. `lado doctor` in a container names the way to enable secrets

In a container (`update.in_container()`), no folder or the null device gives `[info]
Variables from outside: <folder>: none` with the hint `to give the agents variables:
LADO_SECRETS=./secrets in compose's .env and mkdir -m 700 secrets (docker run: -v
<folder>:/run/secrets:ro); docs/install.md#the-agents-variables`. Outside a container the
line stays `[info] … no folder` with no hint: compose means nothing there. `[info]` is not
a warning: doctor's exit code stays 0 and the check reads as green. Covers `docker run`
without the folder too, which gets no mount at all.

### D4. Every update downloads the version's compose.yaml; going back keeps it

The update in the header, the guide and README: `curl -fLO
https://github.com/ladohq/lado/releases/download/v<version>/compose.yaml` in the folder
of `compose.yaml`, then the new `LADO_VERSION` in `.env`, then `docker compose up -d`.
Every release from 0.40.0 carries the asset; the tag is `v<version>`
(`$GITHUB_REF_NAME` of the release workflow). Always, not "when the CHANGELOG says so":
nobody has to judge, and the step is never missed (the human's answer). The guide says a
change made to `compose.yaml` by hand must be carried over. Going back keeps the newer
`compose.yaml`: an older LADO ignores the mounts and variables it does not know, so the way
back stays as it is and its container test unchanged. The download is checked by its
address in unit tests, not run: the container tests run `lado:local` with no release.

### D5. The Dockerfile's `docker run` needs no folder

Its header drops `mkdir -m 700 secrets` and the `-v "$PWD/secrets:/run/secrets:ro"` line
from the first command, and gives that `-v` as the way to add secrets. Nothing at
`/run/secrets` is already silent (D1's context).

### D6. CHANGELOG: amend, not contradict

0.40.0 is unreleased. The LAD-76 line ("compose now refuses to start without the
`secrets` folder: `mkdir -m 700 secrets`") becomes: `secrets/` is optional, enabled by
`LADO_SECRETS=./secrets` in `.env` and `mkdir -m 700 secrets`. The LAD-83 line gets the
update: each update downloads the version's `compose.yaml`; who comes from 0.39.0 needs
the new one, without which the container has no git identity (`LADO_GIT_NAME`,
`LADO_GIT_EMAIL`), no ssh agent (`LADO_SSH_AGENT`) and no `secrets/`. No new line.

### D7. Test layers

- Unit (layer 1): `outside()` with `/dev/null`, with a regular file (still `not a
  folder`), with a missing path; `check_outside` in and out of a container
  (`LADO_CONTAINER`), with the null device, no folder, a regular file; the start's
  warnings with `LADO_ENV_DIR=/dev/null` (`tests/test_runtime.py`); `tests/test_docker.py`
  for compose's default, the headers (no `mkdir` in the first start, `LADO_SECRETS=./secrets`
  named), the guide's and README's start and update, the update's address against the
  release workflow.
- Container (layer 7): a compose project with no `LADO_SECRETS` and no folder starts,
  doctor's line, no `/run/secrets` line in the logs, a session with the fake endpoint
  reaches idle; a project in a folder of its own with `LADO_SECRETS=./secrets` and a fake
  `GH_TOKEN` gives it to an agent's shell. The `compose` fixture's own `LADO_SECRETS`
  becomes optional; `test_two_lados` keeps a folder per project.
- No integration test: the change is inside one function that the unit tests call the way
  the launch does; the existing integration test of the outside folder stays.
- The check by hand (steps in the pull request) covers the Mac: Docker Desktop's
  `/dev/null` bind, a Claude Code login inside, `gh api user` with `GH_TOKEN`, the update
  from 0.39.0's files.

## Risks

- Docker Desktop binds the host VM's `/dev/null`; its `st_rdev` is the Linux null device
  (1, 3), the same as the container's own `/dev/null`. The container test proves it on
  Linux, the check by hand on a Mac.
- A user who edited `compose.yaml` loses the edit on update if they skip the guide's
  sentence; their settings live in `.env`, which stays.
