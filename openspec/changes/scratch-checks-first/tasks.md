## 1. The pre-check

- [x] 1.1 `runtime.check_new_session` (D1) and `start_session` on it (D2). Check: unit tests
  of each refusal before the folder exists (no kits, a kit that lacks a skill, a name of
  another folder, a taken name, a bad title, a permission mode, a missing command, no login,
  a model refused), and the existing `start_session` tests green.
- [x] 1.2 Remove `runtime.check_start_login`; `cli._start_new`, `cli._start_clone` and
  `app.start` (scratch, setup) call `check_new_session` before they change anything (D3).
  Check: unit tests: `lado start --new <folder> --kit <kit without its skill>` exits 1 and the
  folder does not exist; `lado start <git-url> --kit …` clones nothing (clone stubbed);
  `POST /api/sessions` scratch → 400 and no folder; setup → 400 and no `.git`.

## 2. A late refusal of a fresh start

- [x] 2.1 `scratch.make` returns what it made; `scratch.remove_unused` (D4); `cli._start_new`
  prints `lado: removed <folder>, which this start made` or keeps `the repository stays in
  <folder>`; `app.start` removes it too. Check: unit tests with real git: removed after a late
  refusal (an empty folder given: only `.git` goes); kept with a file in it, a second commit,
  or a session of that folder.

## 3. The window

- [x] 3.1 vitest of `Launch`: Create and start answered 400 with the folder not made → Where
  stays on New empty folder with Folder name, the refusal shown (D5); fix the comment above
  `createAndStart`. Check: `make web`.

## 4. Docs and CHANGELOG

- [ ] 4.1 `docs/cli.md` (`--new`: checked whole first, the late removal line; the clone:
  checked whole first), `docs/design/ui.md` (New empty folder: a refusal before the folder
  keeps Where), `docs/design/modules.md` (`runtime.check_new_session`, `scratch.remove_unused`).
- [ ] 4.2 CHANGELOG.md under `## 0.47.0 (unreleased)`, Fixed: a refused new session from an
  empty folder, a set-up or a clone in the terminal leaves no folder or repository behind.
- [ ] 4.3 Regression run: `make lint`, `make test`, `openspec validate scratch-checks-first
  --strict`, the trial archive of `.lado/sdlc.md`'s Checks.
