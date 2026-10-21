## 1. Compose

- [x] 1.1 `docker/compose.yaml`: `LADO_REPOS:` and the workspace's mount take
  `${LADO_WORKSPACE:-${LADO_PROJECTS:-/set-LADO_WORKSPACE-to-your-workspace-folder}}`; the
  mount is a long bind (`type: bind`, `source` and `target` that expression,
  `bind: create_host_path: false`), kept the second entry of `volumes` after
  `home:/home/lado`, its comment saying why (a missing workspace is never made on the
  host; Docker's refusal names `LADO_WORKSPACE`). No `:?` for the workspace; the image's
  line stays as it is. Check: `tests/test_docker.py` (1.3).
- [x] 1.2 The header of `docker/compose.yaml`: `LADO_WORKSPACE=/Users/me/workspace   # your
  workspace, absolute: …` in the example `.env`, then one line that `LADO_PROJECTS`, the
  name before 0.43.0, is still accepted and `LADO_WORKSPACE` wins over it; the second
  LADO's `.env` names `LADO_WORKSPACE`. Check: 1.3.
- [x] 1.3 `tests/test_docker.py` (unit): the mount and `LADO_REPOS` are the expression of
  1.1, the mount's `create_host_path` is false; the header's commands are preceded by
  `LADO_WORKSPACE` and `LADO_VERSION` in `.env` (the docstring: only `LADO_VERSION` is
  required by every command now); the second LADO names `LADO_WORKSPACE`; the header says
  `LADO_PROJECTS` is still accepted; `test_the_guides_env_names_every_variable_compose_reads`
  leaves `LADO_PROJECTS` out of the guide's `.env` as it does `LADO_IMAGE` (an old name,
  not a setting to write). `make test`.

## 2. The container tests (CI, `make test-container`)

- [x] 2.1 `tests/container/conftest.py`: the `compose` and `folder` fixtures set
  `LADO_WORKSPACE` (was `LADO_PROJECTS`). `tests/container/test_image.py`:
  `test_compose_serves_on_lado_port` reads `LADO_WORKSPACE`.
- [x] 2.2 `docker compose config` per `.env` (`tests/container/test_image.py`, the
  `compose` fixture): only `LADO_WORKSPACE` → its path mounted at itself and as
  `LADO_REPOS`; only `LADO_PROJECTS` (an installed `.env`) → the same with that path; both
  → `LADO_WORKSPACE`'s path only; neither → `config` succeeds, `up -d` fails, its stderr
  names `LADO_WORKSPACE`, and no folder `/set-LADO_WORKSPACE-to-your-workspace-folder` is
  made on the host. Replaces `test_compose_refuses_without_the_projects_folder`.
- [x] 2.3 A project's folder in the workspace (`tests/container/test_projects.py` or
  `test_image.py`): compose up with `LADO_WORKSPACE` a temporary folder;
  `docker compose exec -T lado lado project create acme`; the host sees
  `<workspace>/projects/acme`; `GET /api/folders?path=<workspace>/projects/acme` with the
  UI's token answers `warning: null`, and the same for `/home/lado/elsewhere` answers the
  "Outside the workspace" warning (the check is not blind).
- [x] 2.4 Run: `make docker` then `make test-container` when Docker is at hand; otherwise
  CI's container cells are the check, and the build report says so. No Docker on the
  build machine: CI's container (amd64) and (arm64) cells passed on `fc22acb`.

## 3. "project" → "repository"

- [x] 3.1 `src/lado/runtime.py`: `CONTAINER_INSTRUCTIONS` says "A tool the repository needs
  and lacks", "In the repository's folder", "Add no version file or other file to the
  repository unless the human asks"; the docstring at the `.lado/` rule (about line 2866)
  "the repository's own files there". The tests that hold the paragraph's words, if any:
  expected text only. `make test`.
- [x] 3.2 Comments of `docker/profile.sh` (lines 7, 11), `docker/Dockerfile` (53, 66, 86,
  117), `docker/mise.toml` (7, 10): "repository" where they mean the human's repository.
- [x] 3.3 `docs/install.md`: the mise and Python lines (about 246–278), the troubleshooting
  lines (`No version is set for shim`, mise refuses a Python, `Config files … are not
  trusted`: "the repository is outside the workspace"), the uninstall's "Your repository's
  own files in `.lado/`", the example `cd ~/my-project` → `cd ~/my-repo`.
- [x] 3.4 Grep by meaning: `grep -n -i project` over `docker/`, `openspec/specs/container`
  (after the archive), the change's delta, `docs/install.md`, `src/lado/runtime.py`; every
  hit left is a LADO project, a compose project (`COMPOSE_PROJECT_NAME`, "compose
  projects"), Claude Code's `projects`, the path `/projects`, an example path, or
  `LADO_PROJECTS` named as still accepted. The build report lists the kinds kept.

## 4. The documents

- [x] 4.1 `docs/install.md`: the shell check `unset LADO_VERSION LADO_WORKSPACE
  LADO_PROJECTS LADO_PORT LADO_IMAGE COMPOSE_PROJECT_NAME`; both `.env` examples
  `LADO_WORKSPACE=…`; "`LADO_WORKSPACE` is the only folder of your computer the agents
  see"; the second LADO's `.env`; the troubleshooting "Put the repository under
  `LADO_WORKSPACE`" and "Move it under `LADO_WORKSPACE`". Update the container: one
  sentence that a `.env` with `LADO_PROJECTS` keeps working, renaming it to
  `LADO_WORKSPACE` is optional, and `LADO_WORKSPACE` wins when both are set. The
  troubleshooting: a line for `bind source path does not exist:
  /set-LADO_WORKSPACE-to-your-workspace-folder` (set `LADO_WORKSPACE` in `.env`).
- [x] 4.2 README.md: the `unset` line and the `.env` example (`LADO_WORKSPACE`).
- [x] 4.3 `docs/release.md`: 4.5's `.env` `LADO_WORKSPACE=…` and its check of the New
  session window ("the folders of `LADO_WORKSPACE`"); 4.6 keeps `LADO_PROJECTS` in both
  `.env` files, with a sentence that this is on purpose: the last final's `compose.yaml`
  knows only that name, and the update checks that an installed `.env` keeps working.
- [x] 4.4 `docs/testing.md` (the container layer's compose sentences: refuses at `up`
  without the workspace, naming `LADO_WORKSPACE`; `.env` per test with `LADO_WORKSPACE`),
  `docs/design/modules.md` (compose's `LADO_WORKSPACE`, else `LADO_PROJECTS`, no `:?` and
  why), `docs/design/projects.md` (the workspace in Docker is `LADO_WORKSPACE`, the old
  name still accepted; S2b in the steps table marked built if the table marks steps),
  ROADMAP.md (S2b checked).
- [x] 4.5 CHANGELOG.md, `## 0.43.0 (unreleased)`, `### Changed`: one line, e.g.
  "**Compose takes the workspace from `LADO_WORKSPACE`.** An installed `.env` with
  `LADO_PROJECTS` keeps working; renaming it is optional." In the Improved line of S1,
  "(`LADO_PROJECTS` and `LADO_REPOS` stay)" → "(`LADO_REPOS` stays)".
- [x] 4.6 Grep `LADO_PROJECTS` over the tree without `.git`, `node_modules`, `.venv`,
  `src/lado/server/static`, `docs/research/`, `docs/superpowers/`, `docs/epics/`,
  `openspec/changes/archive/`, CHANGELOG.md's released sections: every hit is compose's
  fallback, a "still accepted" sentence, an `unset` line, `docs/release.md` 4.6, the
  delta's scenario of the old `.env`, or a test of the fallback.

## 5. The checks

- [x] 5.1 `make lint`, `make test`, `openspec validate compose-workspace-variable --strict`,
  `openspec validate --specs --strict`; CI green with its container and smoke cells.
- [x] 5.2 The pull request's manual check: the branch, the folder (a temporary one with a
  copy of `docker/compose.yaml`), `env | grep -E '^(LADO|COMPOSE)_'` and `unset` first,
  then `docker compose config` with each `.env` (only `LADO_WORKSPACE`, only
  `LADO_PROJECTS`, both, neither) and `docker compose up -d` with neither, each with its
  expected result.
