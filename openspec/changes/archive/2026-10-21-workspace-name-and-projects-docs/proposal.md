Task: LAD-117

## Why

LADO's documents still describe a project as the old idea of ROADMAP's "Later": a named
configuration of repositories, tracker filters, a default kit and flow, whose deletion
removes its clones. The human has settled a new model (the session artifact
`projects-concept`, 2026-10-21; the epic LAD-116, `docs/epics/lad-116/plan.md`): a project
is a folder `<workspace>/projects/<id>` and its environment variables, so that sessions for
different clients get different keys. The folder LADO keeps code in is called the
**workspace** in that model, while the documents, the UI, `lado doctor` and the Docker
files call it "projects folder" or "Repositories folder" today, two names for one folder,
and "project folder" now means a project's own folder inside it.

This is the epic's first step (S1, the concept's phase 0): the documents describe the new
model and say what is not built yet, and every text calls the folder the workspace. No
behaviour changes.

## What Changes

- **New `docs/design/projects.md`** (English), written from the concept, which is the only
  source of decisions: why projects; the words (workspace, project, project folder,
  repository folder: a project's git subfolder), with the concept's tree; the project (id,
  title, folder derived from the id, the special cases); repositories read from disk; the
  session with and without a project; variables and secrets and the layers of an agent's
  environment; where a project's data lives; the security boundary; deleting; the UI; the
  architectural frame; "Not now"; the steps S1–S7 with a link to the epic's plan. It says
  plainly:
  - which parts are not built yet (everything but the workspace's name: steps S2–S7), and
    that until S2 the workspace is `LADO_REPOS` only, with no `~/workspace` default;
  - the projects of one LADO are not isolated from each other; for clients that must not
    mix, run a separate LADO;
  - LADO is not a store: what matters belongs in a git remote or on a disk outside LADO,
    and a backup of LADO's home volume holds the project secrets;
  - `lado uninstall` deletes `LADO_HOME` with the secrets (unless `--keep-data`) and never
    touches the workspace; in Docker, removing the home volume deletes them.
  Linked from AGENTS.md (Read more) and from `docs/design/modules.md` where it describes
  `LADO_REPOS` (`clone.repos_folder`, `doctor.check_repos_folder`).
- **ROADMAP.md, Later → Projects**: rewritten to the new model and the epic's steps; the
  old "named configuration" and "deleting a project removes its clones too" go. Of the
  2026-10-03 lessons stay: a session refers to its project by a real reference, not a name
  found in its path; the CLI can do what the UI does; LADO itself makes each worker's
  worktree. Deleting is the concept's rule: the project folder goes after LADO shows the
  unpushed work, and LADO never deletes a folder outside `projects/`.
- **BACKLOG.md**: "Flows cannot work on another repository" and "Artifacts end with their
  session" point at the new model (sessions over several repositories of a project and a
  project's artifacts are the concept's "Not now", after the epic); a new P3 entry
  "Managing workspace folders outside projects".
- **`docs/design/ui.md`**: the Projects placeholder (its plan and its sentence), `repos` in
  the session's head, "so Projects can add theirs" in the New session window and the
  workspace hint of Where, in the new model's words.
- **The rename to workspace**, by text only, everywhere outside the historical documents:
  - `lado doctor`'s check `Repositories folder` is named `Workspace`
    (`[ok  ] Workspace: /Users/me/repos (LADO_REPOS)`);
  - the New session window's row `Repositories folder:` reads `Workspace:`;
  - the container's warning reads `Outside the workspace (<folder>): this folder is only in
    the container, your computer does not see it or the agents' work in it`;
  - compose's refusal reads `set LADO_PROJECTS to your workspace folder`;
  - the Projects placeholder's sentence reads `Each project is a folder in your workspace
    with its repositories and its own environment variables, so sessions for different
    clients get different keys.`;
  - README.md, `docs/install.md`, `docs/release.md`, `docs/testing.md`, `docs/design/*`,
    the comments of `docker/` and of the code, the docstring of the API model
    `ReposFolder`, and the example paths of the setup (`/Users/ann/workspace` in place of
    `/Users/ann/projects`);
  - the specs `repos-folder`, `container` and `session-clone` (this change's delta).
- CHANGELOG.md: one patch-level line.

## Scope

`docs/design/projects.md` (new), AGENTS.md, ROADMAP.md, BACKLOG.md, README.md,
CHANGELOG.md, `docs/install.md`, `docs/release.md`, `docs/testing.md`,
`docs/design/ui.md`, `docs/design/modules.md` (and any other `docs/design/*` with an old
name), `docker/compose.yaml`, `docker/profile.sh`, `docker/mise.toml`,
`src/lado/doctor.py`, `src/lado/runtime.py`, `src/lado/clone.py`,
`src/lado/server/models.py` with `web/openapi.json` and `web/src/api.gen.ts`,
`web/src/Launch.tsx`, `web/src/pages.tsx`, and the tests that hold these texts:
`tests/test_doctor.py`, `tests/test_runtime.py`, `tests/test_docker.py`,
`tests/test_server_launch.py`, `tests/ui/test_launch.py`, `web/src/Launch.test.tsx`,
`tests/container/*` (`conftest.py` included).

## Out of scope

- Any name an installation sees: `LADO_PROJECTS` (compose) and `LADO_REPOS` (the
  container) keep their names, the path `/api/repos-folder` and every flag and path stay.
  Compose's new name `LADO_WORKSPACE` is step S2b; it would break installed `.env` files
  without its fallback.
- Code identifiers (`repos_folder`, `check_repos_folder`, `OUTSIDE_REPOS`,
  `outside_repos`, `ReposFolder`, `DEFAULT_PARENT`) and the capability name `repos-folder`:
  names, not text; renaming them is churn with no reader's gain, and S2 reshapes this code
  (one function for the workspace) anyway.
- The default `~/workspace` without `LADO_REPOS`, and the Where field's placeholder
  `~/projects/app` used without a workspace: step S2, which makes that default; a
  placeholder that names `~/workspace` before then would point at a folder LADO does not
  use.
- Projects, variables, secrets and sessions in a project: steps S2–S7.
- Historical documents: CHANGELOG.md's released sections, `docs/research/*`,
  `docs/superpowers/*`, `openspec/changes/archive/*`, `docs/epics/*`; they record what was
  true then.
- The example paths inside specs and tests (`/Users/me/projects`, `/Users/ann/projects`):
  test data, which this step does not touch so no test changes more than its expected text.
- The small grey notes of the New session window the human mentioned at this design: the
  lead takes them up on their own.

## Impact

- Users see four new texts: `lado doctor`'s `Workspace` line, the New session window's
  `Workspace:` row and its container warning, compose's refusal; and the Projects
  placeholder's sentence. Behaviour, variables, paths and the API are as before.
- The API's OpenAPI description of `ReposFolder` changes (text only): `make web-types`.
- Version: patch (texts and documents only), one CHANGELOG line.
