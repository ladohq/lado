## 1. Core: `lado.clone`

- [x] 1.1 URL forms, `Address`, `default_folder`, `same_repo` (D1, D2, D3). Unit tests
  (`tests/test_clone.py`): "An ssh address in scp form", "A folder", "Default folder",
  "The same repository over another protocol" (pairs table), "A token in the URL is never
  shown".
- [x] 1.2 `check_target` with its six states and texts, the `other_repo` suggestion (D3).
  Unit tests with real git repos: each state, "Another repository with the same name", "A
  folder with other files", a subfolder of a repository is `not_empty`.
- [x] 1.3 The git runner without prompts and `KINDS` (D4, D5). Unit tests: each kind
  against a recorded git line ("An ssh key the host refuses", "A private https repository
  without a login", "A repository GitHub does not show", host key, unreachable, no
  branch, other), the hints for github.com and another host, `-p <port>`, git missing
  (LAD-5's `no_git`).
- [x] 1.4 `list_branches` (D6). Unit tests on a `file://` bare repo: "Branches and the
  default one", an empty repository, "A remote that does not answer" (a fake slow `git`
  on PATH, `LIST_TIMEOUT` patched).
- [x] 1.5 `clone` with progress and cancel (D7). Unit tests: a `file://` clone of branch
  `dev` lands in the target with the branch checked out and no temp folder left; into an
  empty folder; "A branch that is not there"; "Cancel during the clone" (fake slow git
  printing progress: `Progress` values seen, temp gone, target absent); the progress
  parser on recorded `\r` lines.

## 2. CLI

- [ ] 2.1 `lado start <git-url> [<folder>] [--branch NAME]` (D8). Unit tests
  (`tests/test_cli.py`): "--branch with a folder" and `<folder>` without a URL exit 2;
  "The clone is there already" (exit 1, the command printed, nothing changed); `other_repo`
  and `not_empty` refused; a name of a session of another folder refused before any
  clone; a clone then `start_session` with the folder; a refused start prints `the clone
  stays in`.
- [ ] 2.2 Integration (`tests/integration/test_clone_start.py`, `-m integration`): "Clone
  and start" with the fake agent; Ctrl-C (SIGINT) during a fake slow clone exits 130 with
  no temp folder and no target.

## 3. API

- [ ] 3.1 `server/clones.py` jobs, the five endpoints and models, shutdown cancel (D9,
  D10, D11). Unit tests (`tests/test_server_clones.py`): branches and refusals (400
  `CloneRefused` with kind and hint), clone target states with `default_name` and
  `name_state`, a job to `done`, `DELETE` cancels, "Two clones into one folder" (409), an
  unknown job 404, "A window that went away" (`ABANDONED` patched short), a finished job
  dropped after `KEPT`, the server's shutdown cancels a running job, the POSTs and DELETE
  refused without the Origin.
- [ ] 3.2 `make web-types`; commit `web/openapi.json` and `web/src/api.gen.ts`.

## 4. Web UI

- [ ] 4.1 `Launch.tsx` Clone from URL (D12, mockup v3): vitest in `Launch.test.tsx` for
  "Branches come by themselves", the default branch marked, a listing failure with the
  hint and Copy, `same_repo` → Use this clone switches to Folder, `other_repo` with the
  suggestion and the button off, the progress bar and Cancel clone (`DELETE` sent), "The
  window cannot be closed during a clone", "A name taken after the clone", a long branch
  list as the combobox.
- [ ] 4.2 UI e2e (`tests/ui/test_launch.py`, `-m ui`): clone a `file://` bare repo and
  start, Activity opens; screenshots of the form, the progress and Use this clone, attached
  to the build report.

## 5. Docs

- [ ] 5.1 `docs/design/ui.md` (Launch and session control), AGENTS.md (Layout, server
  endpoints, `lado start`), README's start, CHANGELOG.md under 0.36.0 (D13).

## 6. Regression

- [ ] 6.1 `make lint`, `make test`, `make web`, the new and changed integration files with
  `-m integration`, `tests/ui/test_launch.py` with `-m ui`, `openspec validate --specs
  --strict`; numbers in the build report. CI's full run on the pull request.
