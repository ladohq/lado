## 1. The scan

- [x] 1.1 `tests/test_projects_core.py`, beside the unpushed scan's tests (unit: real git,
  the lowest layer that holds the scan): a link `docs` in `shop` to a repository outside
  it, with an uncommitted file and a branch not pushed, gives `projects.unpushed(shop) ==
  []` and `projects.deletion("shop").unpushed == []` (AC-1); with `frontend` beside it
  holding a branch not pushed, the list is `frontend`'s line alone, as today (AC-2); a
  worktree `docs-fix` in `shop` of the link's repository, with an uncommitted file, gives
  one line starting `docs-fix: ` that names `uncommitted changes` (AC-4). Each fails
  before 1.3.
- [x] 1.2 `tests/test_project_repos.py`, beside the `rooted` tests: the clean, pushed root
  holding a link `docs` to a repository elsewhere with an uncommitted file gives
  `projects.unpushed(rooted) == []` (AC-3). It fails before 1.3 on the link's own line,
  and guards D1 after it: it fails when the root's `skip` leaves links out.
- [x] 1.3 `src/lado/projects.py`, `unpushed`: the entries scanned are the folder's
  repositories that are no symbolic link; the root's `skip` keeps every entry with a
  `.git`, links included (design D1, D2). Its docstring says a link is not scanned:
  removing the folder removes the link, never its target.

## 2. Documents

- [x] 2.1 `docs/design/projects.md`, "Deleting", the paragraph "What a removal would
  lose": a symbolic link in the folder is not scanned (it loses the link only), and is no
  change of a root repository either.

## 3. Checks

- [x] 3.1 `make lint`, `make test` pass; `openspec validate unpushed-skips-links --strict`
  passes; CI green on the pull request's last commit (AC-5).
