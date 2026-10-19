Task: LAD-107

## Why

LADO's image (`docker/Dockerfile`) has git, Node 22, uv, mise and the build tools, and
none of the everyday tools the agents and the kits call. Found on 2026-10-19 after LADO's
own development moved from the PyPI install to the image:

- **openspec**: the kit sdlc expects it (`expects.commands: [git, openspec]`), so in a new
  container on a clean home volume LADO refuses to start an sdlc session at all. Today it
  exists in one container only, installed by hand through mise on that home volume
  (`npm:@fission-ai/openspec` 1.14.1).
- **python3**: there is no `python3` on an agent's `PATH`. uv's Python 3.13, which LADO
  itself runs on, sits in `/opt/uv/python` and is on no `PATH`. The kit
  tracker-jira-server runs `python3 ${SKILL_DIR}/jira.py`; the agents call `python3` for
  one-off scripts.
- **jq**: kits' scripts (superpowers' `bump-version.sh`, mattpocock-skills' hook
  `block-dangerous-git.sh`) and the agents' parsing of `gh` and `curl` output.
- **ripgrep (`rg`)**: Codex, OpenCode and Kilo search code with `rg`. Claude Code ships
  its own, which hid the gap.
- **unzip, zip, xz, bzip2, patch, file**: archives, toolchain installers, applying diffs.

Root cause: the image was built for LADO and the four agent CLIs and their logins. What
the agents run inside a project was left to mise, and mise does not cover system
commands (`jq`, `rg`, `file`) or the tools a kit expects before any project is chosen.

## What Changes

- **Base tools from Debian** in the image's first apt layer: `jq`, `ripgrep`, `unzip`,
  `zip`, `xz-utils`, `bzip2`, `patch`, `file`, and, of the task's optional list, `rsync`,
  `sqlite3`, `tree`, `lsof`, `netcat-openbsd`.
- **openspec at a pin**: the npm package `@fission-ai/openspec` at the build argument
  `OPENSPEC_VERSION` (default `1.14.1`), in a layer of its own under `/opt/tools`, on
  `PATH` with the image's programs. It comes before mise's shims, so a version a home
  volume installed through mise does not shadow it. A new version comes with a new image.
  Its usage statistics and its update check are off (`OPENSPEC_TELEMETRY=0`,
  `OPENSPEC_NO_UPDATE_CHECK=1`) for the server, `docker exec` and the agents.
- **python3 and python** run the image's Python 3.13 (the one LADO runs on), from a
  folder of fallbacks that comes on `PATH` **after** mise's shims: where mise has a Python
  for the folder (a version file, or a container-wide `mise use -g`), that Python
  answers. Everywhere else the image's answers. The image's Python becomes root's, so no
  agent can change the interpreter LADO itself runs on. pip refuses to install into it
  (uv marks it externally managed); `python3 -m venv` and uv make environments.
- **Docs**: the Dockerfile's header, docs/install.md (Docker, "The projects' toolchains"),
  docs/design/modules.md (`docker/`), CHANGELOG.md.
- A minor release (a feature of the image): the line goes under `## 0.42.0 (unreleased)`.

## Scope

- `docker/Dockerfile`, `docker/profile.sh`.
- Tests: unit (`tests/test_docker.py`), container (`tests/container/`).
- Docs as listed above.

## Out of scope

- **shellcheck**: about 20 MB for a tool few projects need. An agent installs it through
  mise when a project does (`mise install shellcheck`), as the instructions already say.
- **docker and kubectl**: the cloud stages of LAD-100's plan, and a security question of
  their own (a Docker socket in the container is root on the host).
- **Databases** (PostgreSQL, Redis): each is a project's own. Unchanged from the
  project-toolchains change.
- **Debian's python3 (3.11)**: decided against. It lands in `/usr/bin`, before mise's
  shims, and would silently answer instead of a project's `.python-version`.
- **Installing openspec when a kit asks for it**: LADO has no way for a kit to install a
  command, and today a missing expected command refuses the session. A pin in the image
  is the one way that works on a clean home volume.
- **A line in LADO's instructions naming the new tools**: the agents find them on `PATH`.
  The container paragraph already grows every agent's context, and it keeps naming only
  what an agent could not guess (mise, Node's rule, what cannot be installed).
- **Making the rest of `/opt` root's**: still out of scope as in project-toolchains. Only
  the Python LADO runs on becomes root's, because it is now on every agent's `PATH`.

## Impact

- The image grows by the Debian packages and openspec's npm tree; the measured numbers go
  in the pull request (design D6). python3 adds nothing: it is the Python already there.
- An existing home volume needs no change. Its mise-installed openspec stays installed
  and is shadowed by the image's.
- `python3` in a project without a Python version file now answers with 3.13 where it
  used to fail with "command not found" (or mise's "No version is set" once any mise
  Python was installed on the volume).
