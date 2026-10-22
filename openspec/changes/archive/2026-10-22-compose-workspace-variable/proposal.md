Task: LAD-124

## Why

Since steps S1 and S2 of the epic LAD-116 (`docs/design/projects.md`, the session artifact
`projects-concept`) the folder LADO keeps code in is the **workspace**, and a **project**
is a LADO project, a folder `<workspace>/projects/<id>`. Compose still takes the workspace
from a variable named `LADO_PROJECTS`, and a few texts of the image and its spec still
say "project" for the human's repository. A user who reads "projects" there now thinks of
LADO's projects.

This is step S2b of the epic: compose reads `LADO_WORKSPACE`, an installed `.env` with
`LADO_PROJECTS` keeps working (the human's decision Q2, gate #33), and "project" in the
sense of the human's repository becomes "repository" in the container's spec, the image's
comments, the guide and the agents' mise paragraph (the human's decision #615).

## What Changes

- **`docker/compose.yaml`**: the workspace is
  `${LADO_WORKSPACE:-${LADO_PROJECTS:-/set-LADO_WORKSPACE-to-your-workspace-folder}}`,
  for `LADO_REPOS` and for the mount. The mount becomes a long bind
  (`type: bind`, `create_host_path: false`), as `secrets` and the ssh agent are already,
  so a missing workspace is never made on the host: with neither variable set
  `docker compose up -d` refuses with Docker's `bind source path does not exist:
  /set-LADO_WORKSPACE-to-your-workspace-folder`. No `:?`: Compose v2 on GitHub's
  runners evaluates a nested `:?` even when the outer variable is set, so
  `${LADO_WORKSPACE:-${LADO_PROJECTS:?…}}` would refuse a `.env` with `LADO_WORKSPACE`
  only). Compose's other commands (`config`, `exec`, `logs`, `down`) no longer ask for the
  workspace; `LADO_VERSION` stays required.
- **The header of `docker/compose.yaml`**: `LADO_WORKSPACE=/Users/me/workspace` in the
  example `.env`, with one line that `LADO_PROJECTS`, the name before 0.43.0, is still
  accepted and `LADO_WORKSPACE` wins when both are set; the second LADO's `.env` names
  `LADO_WORKSPACE`.
- **"project" → "repository"** where it means the human's repository, checked by meaning
  over `docker/`, `openspec/specs/container`, `docs/install.md` and `src/lado/runtime.py`:
  - `docker/profile.sh`, `docker/Dockerfile`, `docker/mise.toml`: the comments;
  - `runtime.CONTAINER_INSTRUCTIONS` (the agents' mise paragraph): "a tool the repository
    needs", "in the repository's folder", "to the repository unless the human asks"; and
    the docstring at `runtime.py:2866` ("the repository's own files there");
  - `docs/install.md`: the mise and Python lines, the troubleshooting lines, the
    uninstall's "your repository's own files in `.lado/`", the example `~/my-project`;
  - the living spec `container`: this change's delta (three requirements replaced under new
    names, because openspec keeps a modified requirement's scenario names, with the
    scenarios "A repository's Go from its .tool-versions", "A repository's mise.toml needs
    no trust", "Outside a repository", "A repository's own Python", and the words of the
    requirements around them).
- **The documents** where `LADO_PROJECTS` stands: README.md, ROADMAP.md (S2b checked),
  `docs/install.md`, `docs/testing.md`, `docs/release.md`, `docs/design/modules.md`,
  `docs/design/projects.md`: `LADO_WORKSPACE` first; `LADO_PROJECTS` is named "still
  accepted" only where a reader meets it: the guide's `.env` (setup and update), the
  compose header, `docs/design/projects.md`, and `docs/release.md`'s update check (4.6),
  which runs the last final's `compose.yaml` and therefore keeps `LADO_PROJECTS`. The
  shell checks (`unset …`) name both.
- **CHANGELOG.md**, 0.43.0 (unreleased): one line under `### Changed`: compose's workspace
  variable is `LADO_WORKSPACE`; an installed `.env` with `LADO_PROJECTS` keeps working,
  renaming it is optional. The Improved line of S1 that says "`LADO_PROJECTS` and
  `LADO_REPOS` stay" is corrected to "`LADO_REPOS` stays".

## Scope

`docker/compose.yaml`, `docker/profile.sh`, `docker/Dockerfile` (comments only),
`docker/mise.toml` (comments only), `src/lado/runtime.py` (the mise paragraph and one
docstring), README.md, ROADMAP.md, CHANGELOG.md, `docs/install.md`, `docs/testing.md`,
`docs/release.md`, `docs/design/modules.md`, `docs/design/projects.md`, the spec
`container` (delta), `tests/test_docker.py`, `tests/container/conftest.py` (its `compose`
and `folder` fixtures, which every compose test uses), `tests/container/test_image.py`,
and a new container test of the workspace.

## Out of scope

- Renaming `LADO_REPOS` inside the container: the concept keeps it, so the image, the
  entrypoint and the core stay as they are.
- The image's own mount point `/projects` for `docker run` without compose
  (`docker/Dockerfile:137, 204`, `entrypoint.sh:65`): changing it breaks the installed
  `docker run` commands, and nothing of this step needs it; `docker run` users mount their
  workspace at its host path with `-e LADO_REPOS` as before.
- Sessions in a project: step S3.
- A compose-level refusal with LADO's own text (`:?`): impossible without breaking
  `LADO_WORKSPACE`-only installs on Compose that evaluates nested `:?` eagerly (What Changes); the human chose Docker's error with the variable's name in the path (question #694).
- "project" where it means something else: a LADO project (`lado project`,
  `<workspace>/projects/<id>`), a compose project (`COMPOSE_PROJECT_NAME`, "the compose
  project's own `home` volume"), Claude Code's `projects` key in `~/.claude.json` and its
  `~/.claude/projects/`, and the path `/projects` of the image.
- Historical documents: CHANGELOG.md's released sections, `docs/research/`,
  `docs/superpowers/`, `openspec/changes/archive/`, `docs/epics/` (the epic's files belong
  to the epic).
- Example paths in specs and tests (`/Users/me/projects`, `/home/runner/projects`): test
  data.

## Impact

- An installation sees one new name: `LADO_WORKSPACE` in `.env`; its `.env` with
  `LADO_PROJECTS` works unchanged. With neither set, the refusal moves from every compose
  command to `docker compose up -d` (Docker's bind error naming
  `/set-LADO_WORKSPACE-to-your-workspace-folder`).
- The agents in the container get the mise paragraph with "repository" for "project".
- No migration, no new command or MCP tool. Version: patch, one CHANGELOG line.
