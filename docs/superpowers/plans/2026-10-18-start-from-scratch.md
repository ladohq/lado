# Start from scratch Implementation Plan

**Goal:** A person with no repository and no GitHub account starts a first session from
the New session window (or `lado start --new`): LADO makes a new or empty folder a git
repository with an empty first commit, names it from any text (Cyrillic transliterated),
gives the session that text as its title, and says what to do when git does not know the
commits' author.

**Architecture:** One core module, `lado.scratch` (names, the target check, the author
check, `make`), used by the CLI (`lado start --new`), the server (`GET
/api/scratch-target`, `where: {kind: "scratch"}`, `FolderInfo.scratch`) and `lado doctor`.
`runtime.start_session` gains `title=`. The window gets a third source, From scratch,
and a button in Folder. The session itself starts exactly as from a folder.

**Tech Stack:** Python 3.10+ (standard library), FastAPI/pydantic models, React +
TypeScript (vitest), pytest (unit, integration with the fake agent, UI e2e in Chromium).

**Spec:** `openspec/changes/start-from-scratch/` (proposal with AC-1..AC-8, `design.md`
D1-D11, delta specs `session-scratch`, `doctor`, `session-clone`) and
`docs/superpowers/specs/2026-10-18-start-from-scratch-design.md` (manual check). Mockup:
run artifact `task/lad-98/mockup-from-scratch.html`.

## Global Constraints

- Texts, verbatim (the spec's):
  - names: `type a name`; `a name is at most 80 characters`; `a name is one line of
    visible text: <char> is not allowed` (`lado.text`'s refusal wording);
    `the name needs a Latin letter or digit for its folder: type one`;
  - target: `a new folder`; `an empty folder`; `<path> is inside the git repository
    <root>: choose a folder outside it`; `<path> is not empty: choose a new or empty
    folder`; `<path> is a file, not a folder`; `cannot look at <path>: <reason>`;
  - author: `git doesn't know who signs the agents' commits: it has no user.name or
    user.email`; hints `Set LADO_GIT_NAME and LADO_GIT_EMAIL in the .env file next to
    compose.yaml, then restart LADO there:` + `docker compose up -d` (container) and
    `Tell git who you are, once for this computer:` + `git config --global user.name
    "Your Name" && git config --global user.email you@example.com`;
  - make: commit message `Start from scratch`; failure `git could not make <path> a
    repository: <git's first line>`;
  - CLI: `Made <path> a git repository with an empty first commit`; `lado: the repository
    stays in <path>`; inside_repo hint `Start a session in that repository:` + `lado start
    <root>`; not_empty hint LAD-5's `not_repo` one;
  - doctor: `git author`, `user.name and user.email set`, `no user.name or user.email:
    agents cannot commit`;
  - window: `folder and session: <name>`, ` · title: <title>`, `✓ a new folder`,
    `✓ an empty folder`, `Create and start`, `Start from scratch here`, `The folder is
    empty: LADO can start it from scratch.`, `LADO can make this folder and start it from
    scratch.`
- Never the word "project" in a text, a name or a field of this feature.
- Tests never read the user's git config: `GIT_CONFIG_GLOBAL` points at a temp file
  (`GIT_CONFIG_NOSYSTEM=1`), `HOME` at `tmp_path`.
- No schema migration, no MCP tool. CHANGELOG: rename the heading `## 0.40.1 (unreleased)`
  to `## 0.41.0 (unreleased)` (a feature bumps the minor; keep its lines) and add this
  feature's line.
- `make web-types` after the model change; commit `web/openapi.json` and
  `web/src/api.gen.ts`.

## Review Focus

- `make` never commits a file of the human's and never leaves a half-made folder (Task 4).
- `lado start` without `--new` and the Folder source with past sessions behave as before
  (Tasks 6, 10).
- No provider detail above `providers/`; nothing in `providers/`, `hooks.py`,
  `mcp_server.py` or `agent_env.py` changes.

### Task 1: Names from any text (`scratch.names`)

**Files:** create `src/lado/scratch.py`, `tests/test_scratch.py`.

- [ ] Tests (layer 1): the spec's scenarios "A Cyrillic name" (`Сайт кофейни` →
  `sait-kofeini`, title), "A name that is already a name" (no title), "A name with accents"
  (`Café Noël` → `cafe-noel`), "Another script" (`東京` refused); every letter of the table
  in lower and upper case (one parametrized test from the spec's list); empty and blank
  refused; 81 characters refused, 80 taken; U+202E refused with its name.
- [ ] `ScratchError(LadoError)` with `kind` and `hint`; `CYRILLIC` table; `names(text) ->
  Names` (D1, D2), reusing `runtime.MAX_TITLE` and `lado.text` (`first_hidden`,
  `refusal`).
- [ ] `uv run pytest tests/test_scratch.py -n auto`; `make lint`; commit.

### Task 2: The target check (`scratch.check_target`, `default_folder`)

- [ ] Tests (layer 1, real git): `new` (path missing, parents missing), `empty`,
  `.DS_Store` only is `empty`, `.DS_Store` plus a file is `not_empty`, `not_folder`,
  `inside_repo` for a folder of a repository and for a missing path under one (root
  named), a symbolic link to an empty folder, an unreadable folder → `no_access`;
  `default_folder` with and without `LADO_REPOS` (spec "The default folder in the
  container").
- [ ] `check_target`, `default_folder` (D4), `CAN_START`.
- [ ] Run, lint, commit.

### Task 3: The author check (`scratch.author_problem`)

- [ ] Tests (layer 1): both set → None; `user.email` missing → the text with the outside
  hint; with `LADO_CONTAINER=1` the `.env` hint; `LADO_CONTAINER=0` is outside; a missing
  git → LAD-5's `no_git` (FolderProblem) raised, not an author problem.
- [ ] `author_problem(path)` (D5).
- [ ] Run, lint, commit.

### Task 4: Making the repository (`scratch.make`)

- [ ] Tests (layer 1, real git): spec "A new folder" (only `.git`, one commit `Start from
  scratch` on `main`, clean status, no file in the commit's tree); an empty folder given
  (`.DS_Store` stays untracked); `init.defaultBranch=trunk` honoured; global
  `commit.gpgsign=true` with no key still commits; a template dir with a failing
  `pre-commit` hook does not stop it; spec "A failed commit" (a fake `git` wrapper on
  PATH that fails `commit`): the folder LADO made is gone, and for an empty folder given
  only its `.git` is gone; the name of a session of another folder refused before
  anything (`runtime.check_name`); a target that became `not_empty` refused.
- [ ] `make(path, name)` (D6).
- [ ] Run, lint, commit.

### Task 5: A new session with a title (`runtime`)

**Files:** `src/lado/runtime.py`, `tests/test_runtime.py`.

- [ ] Tests (layer 1, the tmux recorder): spec "A fresh start's title" (stored, shown by
  `state.get_session`); a title with a hidden character refuses before anything starts
  (no tmux call, no session row); a title equal to the name stores none; a resume with a
  title refuses.
- [ ] `check_title(text, name)` factored out of `set_title`; `start_session(title=)` (D3).
- [ ] Run, lint, commit.

### Task 6: `lado start --new`

**Files:** `src/lado/cli.py`, `tests/test_cli.py`.

- [ ] Tests (layer 1): `--new` with a git URL, with a second folder → exit 2; spec "A
  folder with files" (exit 1, text and LAD-5's hint, folder unchanged); `inside_repo` with
  `lado start <root>`; no author with its hint; a new folder → the `Made …` line, then
  `start_session` called with the full path and the folder's slug (`--name` wins); a
  relative path made full; a refused start prints `the repository stays in`; `lado start
  <folder>` without `--new` unchanged (an existing test stays green).
- [ ] The flag and `_start_new` (D7); `docs/cli.md`'s `lado start` section.
- [ ] Run, lint, commit.

### Task 7: `lado doctor`'s `git author`

**Files:** `src/lado/doctor.py`, `tests/test_doctor.py`.

- [ ] Tests (layer 1): both scenarios of the doctor delta; no line when git does not run;
  the output holds neither the name nor the email; exit status unchanged by a warn.
- [ ] `check_git_author()` in `run_checks` after `check_git()` (D10).
- [ ] Run, lint, commit.

### Task 8: The server

**Files:** `src/lado/server/models.py`, `src/lado/server/launch.py`,
`src/lado/server/app.py`, `tests/test_server_launch.py`, `web/openapi.json`,
`web/src/api.gen.ts`.

- [ ] Tests (layer 1, FastAPI's client): spec "A name checked"; `LADO_REPOS` default; a
  given `path`; a refused name with `path: null`; each target state; `author` with each
  hint; `name_state` `taken_elsewhere`; `warning` in the container outside `LADO_REPOS`;
  `POST /api/sessions` with `scratch`: made and started with the title (the recorder),
  400 before anything for a refused target, a refused author, a taken name; another kind
  still 400; spec "An empty folder in the folder check" (`scratch: true`), a folder with
  files `scratch: false`, a missing path under a repository `scratch: false`.
- [ ] Models, `launch.scratch_target`, the endpoint, `start()`'s `scratch` kind,
  `FolderInfo.scratch` (D8); `make web-types`.
- [ ] Run, `make lint`, `make web` (stale-types check), commit.

### Task 9: Integration

**Files:** create `tests/integration/test_scratch_start.py`.

- [ ] Tests (layer 2, marker `integration`, fake agent, real tmux and git): spec "A new
  folder from the terminal" (`lado start --new <tmp>/shop --no-attach`; the session runs;
  `spawn_worker` from the fake supervisor makes a worktree of the new repository);
  `POST /api/sessions` with `scratch` and a title against a real `lado server` process:
  `GET /api/sessions` lists the session with its title.
- [ ] `uv run pytest -m integration -n auto tests/integration/test_scratch_start.py`;
  commit.

### Task 10: The window

**Files:** `web/src/Launch.tsx`, `web/src/styles.css` (only if a rule is missing; the
mockup uses existing classes), `web/src/Launch.test.tsx`.

- [ ] Tests (vitest): the switch's three buttons in order; From scratch chosen when
  recent is `[]`, Folder when it is not, and a pick before recent answers is kept; spec
  "The first window" (the note with the title, `✓ a new folder`); spec "No author"
  (hint, Copy, button off); a refused name under Name; `not_empty` under Create in;
  Create in edited stops following the default; the POST body (`where: {kind:
  "scratch", path}`, `name`, `title`); a 409 then `GET /api/folders` ok → Folder with the
  refusal; spec "Start from scratch here" (Name and Create in filled, From scratch
  chosen), and the `missing` sentence; Resume shows no switch.
- [ ] `SourceSwitch` with three sources, the From scratch fields (D9), the Folder
  button; `docs/design/ui.md` (Launch and session control: replace "The window makes no
  repository or commit itself" with the From scratch paragraph, name the mockup).
- [ ] `make web`; commit.

### Task 11: UI e2e

**Files:** `tests/ui/test_launch.py`.

- [ ] Tests (layer 4, marker `ui`): from an empty `LADO_HOME` with a temp
  `GIT_CONFIG_GLOBAL` that has the author, the window opens in From scratch; `Сайт
  кофейни` → Create and start → Activity with the title; Start from scratch here on an
  empty folder; without the author the hint shows and the button is off. Screenshots of
  each of these screens to `<temp dir>/lado-ui-shots/`, attached by the developer as run
  artifacts.
- [ ] `uv run pytest -m ui tests/ui/test_launch.py`; commit.

### Task 12: Docs and CHANGELOG

- [ ] `docs/design/modules.md` (`scratch.py`), AGENTS.md's Layout (one line under
  `clone.py`), README's and `docs/install.md`'s first session (one line each: "no
  repository yet? choose From scratch"), CHANGELOG (Global Constraints). Commit.

### Task 13: Regression run

- [ ] `make lint`; `make test`; the integration and UI files changed, each with its
  marker; `make web`; `openspec validate start-from-scratch --strict`; `openspec validate
  --specs --strict`; grep `openspec/specs/` for "Folder | Clone from URL" and "makes no
  repository" (only the delta's MODIFIED requirement may change them). Report the counts
  in `build-report`.
