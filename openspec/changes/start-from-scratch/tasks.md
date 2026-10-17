Tests first in each section; each task is one commit. The plan with the steps is
`docs/superpowers/plans/2026-10-18-start-from-scratch.md`.

## 1. Core: `lado.scratch`

- [x] 1.1 `names` and the transliteration table (D1, D2). Unit tests
  (`tests/test_scratch.py`): "A Cyrillic name", "A name that is already a name", "A name
  with accents", "Another script", every table letter, empty, 81 characters, a hidden
  character. Plan, Task 1.
- [x] 1.2 `check_target`, `default_folder` (D4). Unit tests with real git: each state,
  "A folder Finder made", "A folder of a repository", a missing path under a repository,
  no access, "The default folder in the container". Plan, Task 2.
- [x] 1.3 `author_problem` (D5). Unit tests: "The container without the variables", "A
  developer's machine", the outside hint, no git. Plan, Task 3.
- [x] 1.4 `make` (D6). Unit tests: "A new folder", an empty folder, `init.defaultBranch`,
  gpgsign and hooks off, "A failed commit" (made folder or `.git` removed), a taken name.
  Plan, Task 4.

## 2. Runtime

- [x] 2.1 `check_title`, `start_session(title=)` (D3). Unit tests (`tests/test_runtime.py`):
  "A fresh start's title", a bad title refused before anything, a resume with a title
  refused. Plan, Task 5.

## 3. CLI and doctor

- [x] 3.1 `lado start --new` (D7) and `docs/cli.md`. Unit tests (`tests/test_cli.py`): "A
  folder with files", inside_repo, no author, usage errors, the start, "the repository
  stays in", `lado start` without `--new` unchanged. Plan, Task 6.
- [x] 3.2 `lado doctor`'s `git author` (D10). Unit tests (`tests/test_doctor.py`): "A
  machine whose git knows the author", "A fresh machine", no git, no value printed.
  Plan, Task 7.

## 4. Server

- [ ] 4.1 `GET /api/scratch-target`, `where` kind `scratch`, `Launch.title`,
  `FolderInfo.scratch` (D8); `make web-types`. Unit tests (`tests/test_server_launch.py`):
  "A name checked", "An empty folder in the folder check", the states, author, name
  state, warning, the start and its 400s. `make web`. Plan, Task 8.
- [ ] 4.2 Integration (`tests/integration/test_scratch_start.py`, `-m integration`): "A new
  folder from the terminal" with a worker's worktree; the API start with a title against a
  real server. Plan, Task 9.

## 5. Window

- [ ] 5.1 From scratch and Start from scratch here (D9), `docs/design/ui.md`. Vitest
  (`web/src/Launch.test.tsx`): "The first window", "A developer's window", "No author",
  "Start from scratch here", the request, a refused start to Folder. `make web`. Plan,
  Task 10.
- [ ] 5.2 UI e2e (`tests/ui/test_launch.py`, `-m ui`) with screenshots of each screen.
  Plan, Task 11.

## 6. Docs and regression

- [ ] 6.1 `docs/design/modules.md`, AGENTS.md's Layout, README, `docs/install.md`,
  CHANGELOG (`0.41.0 (unreleased)`). Plan, Task 12.
- [ ] 6.2 Regression run: `make lint`, `make test`, the changed integration and UI files
  with their markers, `make web`, `openspec validate --specs --strict`, the grep for
  contradictions. Plan, Task 13.
