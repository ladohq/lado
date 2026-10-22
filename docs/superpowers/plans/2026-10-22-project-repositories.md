# Project repositories Implementation Plan

**Goal:** The human adds a repository to a project by a clone or from scratch, and
removes one with the checks of a project's delete, from the CLI and the server's API;
the refusals inside a project's folder offer adding a repository where that is what is
missing (S3's E3).

**Architecture:** `lado.projects` gains the name rule, the add target, `add_clone`,
`add_new`, `removal` and `remove_repo`, and splits the unpushed check of one checkout out
of `unpushed`; `clone.clone`/`check_target` and `scratch.make`/`check_target` take a
`project` that lets a path directly in that project's folder through the `in_project`
refusal; `projects.refusal` chooses its hint by what is there. The CLI gets `lado project
repo add|remove`; the server extends the clone job and adds three project endpoints. No
schema change, no change of the agents' protocol.

**Tech Stack:** Python 3.10+ (standard library), FastAPI/pydantic, pytest (unit, server,
integration with the fake agent).

**Spec:** `openspec/changes/project-repositories/` (proposal with AC-1..AC-10,
`design.md` D1-D12, delta specs `projects`, `session-clone`, `session-scratch`) and
`docs/superpowers/specs/2026-10-22-project-repositories-design.md` (the human's view and
the manual check).

## Global Constraints

- Python 3.10+, standard library only; no new dependency.
- Texts, verbatim (the spec's):
  - add: `Added repository <name> to project <id>: <folder>`; `Start a session in it: lado
    start --project <id> --repo <name>`; `Made <folder> a git repository with an empty
    first commit`; `the repository name <name> is not valid: Latin letters, digits, ., _
    and -, not starting with . or -, at most 100 characters`; `<folder> already exists in
    project <id>: choose another name with --name`; `the folder of project <id> is not
    found: <folder>`;
  - remove: `repository <name> of project <id> has sessions not stopped: <names>; stop them
    first with lado stop <name>`; `removing repository <name> of project <id> deletes its
    folder <folder> with everything in it[ and forgets its <n> session[s]]; run again with
    --yes`; `removing <name> of project <id> deletes the link only, not its target
    <target>; run again with --yes`; `<name> in project <id> is not a repository: LADO
    removes only repositories and links`; `Removed repository <name> from project <id>`;
    `Removed the link <name> from project <id>`;
  - hints: `Add a repository to the project:` + `lado project repo add <id> <url>[ --name
    <name>]` or `lado project repo add <id> --new <name>`; `See the project's
    repositories:` + `lado project show <id>`; none: `project <id> has no repositories yet:
    add one with lado project repo add <id> <git-url> or --new <name>`.
- `mcp_server.py`, `hooks.py`, `providers/`, `state.py`'s schema do not change (the brief's
  thresholds: if they must, stop and ask the human through the supervisor).
- `projects.unpushed`'s output for a project stays byte for byte (its tests unchanged).
- Never the user's real home in tests: `HOME`, `LADO_HOME`, `LADO_REPOS` into `tmp_path`;
  removals only in temporary folders.

## Review Focus

- Nothing outside `<ws>/projects/<id>/<name>` is removed: links in and to the repository,
  a project folder that is a link, a repository whose real path is elsewhere (Task 3).
- The `in_project` refusal stays for every path but one directly in the named project's
  folder (Task 2).
- A cancelled clone leaves no temporary folder in the project (Tasks 2, 7).

## Task 1: The name rule and the add target (D1, D2)

Files: `src/lado/projects.py`; test `tests/test_project_repos.py` (new, real git in
`tmp_path`).
- [ ] Write the failing tests: valid names (`frontend`, `Web.App_2`, 100 characters);
  refused (`.hidden`, `-x`, `a/b`, `..`, `сайт`, 101 characters, empty) with the rule's text;
  taken (folder, file, link, dangling link; `Frontend` beside `frontend` where the disk is
  case-insensitive, skipped elsewhere); unknown project; project folder not found.
- [ ] Implement `REPO_NAME`, `MAX_REPO_NAME`, `check_repo_name`, `NoSuchRepository`,
  `new_repo_folder`.
- [ ] `uv run pytest -n0 tests/test_project_repos.py`; commit.

## Task 2: Clone and fresh start into a project (D3, D4)

Files: `src/lado/clone.py`, `src/lado/scratch.py`, `src/lado/projects.py`; tests
`tests/test_clone.py`, `tests/test_scratch.py`, `tests/test_project_repos.py`.
- [ ] Tests: `check_target(url, <ws>/projects/shop/web, project="shop")` is `new`; the same
  path with `project="acme"`, a deeper path and `<ws>/projects/shop` itself stay
  `in_project`; `clone.clone(…, project=)` from a local bare repository lands in the
  folder; a failed clone (no such repository) and a cancelled one (`cancelled` set, fake git
  `slow`) leave neither the folder nor `.web.clone-*`; `scratch.make(path, name,
  project=)` makes the repository without asking `runtime.check_name` (a session of that
  name elsewhere does not refuse it), refuses without an author; `add_clone`, `add_new`
  return the `Repository` and `repositories("shop")` lists it.
- [ ] Implement the `project` keyword in `clone.check_target`, `clone.clone`,
  `scratch.check_target`, `scratch.make`; `projects.add_clone`, `projects.add_new`.
- [ ] `uv run pytest -n0 tests/test_clone.py tests/test_scratch.py tests/test_project_repos.py`; commit.

## Task 3: Removal (D6, D7, D8)

Files: `src/lado/projects.py`; tests `tests/test_project_repos.py`,
`tests/test_projects_core.py` (unpushed unchanged).
- [ ] Tests: `removal` of a repository with uncommitted changes, a branch with no upstream
  and a worktree under `.lado/worktrees/` with changes gives those lines; a link gives kind
  `link` and its target; a plain folder and a file are refused with the text; a missing
  name names the repositories (or `no repositories yet: add one …`); a running session in
  the repository (status mocked as in `test_projects_core.py`) refuses, one in another
  repository does not; stopped sessions of the project there are listed with open runs, a
  stopped one without a project is not. `remove_repo` without `yes` refuses and changes
  nothing; with `yes` the folder goes, the sessions are forgotten, the sibling repository,
  the project's folder and record stay; a link loses the link only and its target's files
  stay; a repository whose real path is outside the project's folder (the project folder
  a link elsewhere, or the entry swapped) is refused; a failed `rmtree` keeps the
  sessions. `unpushed`'s existing tests pass unchanged.
- [ ] Implement `_checkout_lines`, `Removal`, `removal`, `remove_repo`; `unpushed` over
  `_checkout_lines`.
- [ ] `uv run pytest -n0 tests/test_project_repos.py tests/test_projects_core.py`; commit.

## Task 4: The refusal's hints (D10, E3)

Files: `src/lado/projects.py`, `src/lado/clone.py`, `src/lado/scratch.py`,
`src/lado/server/launch.py`; tests `tests/test_projects_core.py`, `tests/test_clone.py`,
`tests/test_scratch.py`, `tests/test_server_launch.py`, `tests/test_runtime_projects.py`.
- [ ] Tests: a repository keeps the session's hint (deeper paths too); a plain folder and a
  missing name without `url`/`fresh` give `lado project show shop`; a missing name with
  `fresh` gives `--new <name>`, with `url` the URL form, `--name` only when it differs; a
  missing name that breaks D1 gives `lado project show`; `GET /api/folders` on a missing
  folder in a project gives the `--new` hint; `start_session --project acme --repo crm` in
  a project without repositories gives the new text. Update the S3 tests whose hint
  changes (the clone and fresh start into `shop/web`).
- [ ] Implement `refusal(path, *, url=None, fresh=False)` and its callers; the new
  `repository` text.
- [ ] Run those files with `-n0`; commit.

## Task 5: The CLI (D5, D8)

Files: `src/lado/cli.py`; test `tests/test_cli.py`.
- [ ] Tests: `lado project repo add shop <bare>` prints the lines of the spec; `--new site`;
  usage errors (both, neither, `--name`/`--branch` with `--new`, a folder that is no URL);
  exit 1 texts of Task 1; `LADO_AGENT` set → the human-only text for `repo add` and `repo
  remove`, nothing made; `repo remove` prints `Sessions to forget`, `Unpushed work in`, the
  refusal without `--yes`, `Removed repository …` / `Removed the link …` with it;
  `lado project repo` alone prints its help.
- [ ] Implement the `repo` subparser, `cmd_project_repo` (the clone's progress and signals
  shared with `_start_clone`).
- [ ] `uv run pytest -n0 tests/test_cli.py -k project`; commit.

## Task 6: The server (D9)

Files: `src/lado/server/models.py`, `src/lado/server/clones.py`, `src/lado/server/app.py`,
`web/openapi.json`, `web/src/api.gen.ts`; tests `tests/test_server_clones.py`,
`tests/test_server_projects.py` (new).
- [ ] Tests: `POST /api/clones` with `project` (and `name`) runs to `done` in the project's
  folder and `GET /api/projects/shop` lists it; with `path` too → 400; `name` without
  `project` → 400; an unknown project → 404; a taken name → 400 `CloneRefused`; two jobs
  into the same folder → 409. `POST /api/projects/shop/repos` → `ProjectRepo`, taken → 400,
  unknown → 404. `GET …/removal` gives kind, sessions, unpushed; a plain folder → 400; a
  running session → 400; unknown project or name → 404. `DELETE …` removes and answers the
  `ProjectInfo` without it; its refusals as for `removal`. Each change endpoint without the
  token → 401, with a foreign Origin → 403 (as the other `guard.changes` tests).
- [ ] Implement the models (`CloneStart.project/name`, `RepoNew`, `RepoRemoval`,
  `SessionToForget`), `Jobs.start` with a project, the endpoints, 404 mapping;
  `make web-types`.
- [ ] `uv run pytest -n0 tests/test_server_clones.py tests/test_server_projects.py`;
  `make web`; commit.

## Task 7: End to end

File: `tests/integration/test_project_repositories.py` (new; fake agent, real tmux, git,
`lado` processes, temporary `LADO_HOME`, `LADO_REPOS`, tmux socket).
- [ ] A repository added by a clone of a local bare repository and one from scratch lie in
  `<ws>/projects/shop`, are listed by `lado project show shop`, and `lado start --project
  shop --repo <name> --no-attach` starts a session (fake agent) in each.
- [ ] A clone ended by SIGTERM (fake git `slow`) and a clone that fails leave nothing in
  the project's folder and nothing listed.
- [ ] Removal: refused while `shop-frontend` runs; after `lado stop`, with a worker whose
  worktree has a commit not pushed on its branch, it lists `Sessions to forget` and the
  worker's branch, refuses without `--yes` with everything still there; with `--yes` the
  folder and the session are gone (`lado ls`), `backend`, the project's record, a file
  beside the workspace and the bare remote are as they were.
- [ ] From an agent's environment (`LADO_AGENT` set in the process) both commands refuse.
- [ ] `uv run pytest -m integration -n auto tests/integration/test_project_repositories.py`; commit.

## Task 8: Documents and version (D12)

- [ ] `docs/cli.md`, `docs/design/projects.md`, `docs/design/modules.md`,
  `docs/design/ui.md`; `uv run pytest -n0 tests/test_agents_md.py`.
- [ ] CHANGELOG: one line under `## 0.43.0 (unreleased)`, Added.
- [ ] Commit.

## Task 9: Regression

- [ ] `make lint`; `make test` (report the counts); `uv run pytest -m integration -n auto`
  on `tests/integration/test_project_repositories.py`, `test_project_sessions.py`,
  `test_projects_process.py`, `test_clone_start.py`, `test_scratch_start.py`; `make web`;
  `openspec validate project-repositories --strict`; `openspec validate --specs --strict`.
- [ ] The trial archive: copy `openspec/` to the scratchpad, `openspec archive
  project-repositories -y` there, then `openspec validate --specs --strict` on the copy.
- [ ] CI `ci-ok` green on the pull request, the container and smoke cells included.
