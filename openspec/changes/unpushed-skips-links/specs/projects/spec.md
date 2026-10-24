## MODIFIED Requirements

### Requirement: lado project delete shows unpushed work and needs --yes

`lado project delete <id>` SHALL print the core's preview (`projects.deletion`): the
sessions it will forget, `Sessions to forget: <name> (<n> open run[s]), …` (` (no project)`
after one without a project; no line without sessions), then the unpushed work of the
project folder: itself when a repository's root, each repository directly in it, each
worktree of one, once. A symbolic link directly in the folder SHALL NOT count as a
repository of it: the delete removes the link only, so its target's work is not listed.
Without `--yes` it SHALL then refuse, exit 1, changing nothing.

#### Scenario: Unpushed work
- **WHEN** the project folder holds the repository `frontend` with an uncommitted file and
  a branch `feature-x` with no upstream, and the human runs `lado project delete shop`
- **THEN** the output has `Unpushed work in <folder>:` and `  frontend: uncommitted
  changes; branch feature-x not pushed`, then `lado: deleting project shop removes its
  folder <folder> with everything in it; run again with --yes`; it exits 1, and the
  folder and the record stay

#### Scenario: A repository git cannot read
- **WHEN** a subfolder `broken` has a `.git` git cannot read
- **THEN** the list has `  broken: could not check: <git's first line>`

#### Scenario: Nothing unpushed
- **WHEN** every repository of the folder is pushed and clean
- **THEN** no list is printed, and without `--yes` the command still refuses

#### Scenario: Stopped sessions
- **WHEN** `shop-frontend` (one open run) and `fix-login` of project `shop` are stopped and
  the human runs `lado project delete shop`
- **THEN** the output has `Sessions to forget: fix-login, shop-frontend (1 open run)` and
  ends with `… and forgets its 2 sessions; run again with --yes`; nothing changes

#### Scenario: A stopped session from before projects
- **WHEN** `old-site` has no project, was started in `<ws>/projects/shop/site` and is
  stopped, and the human runs `lado project delete shop`
- **THEN** the output has `Sessions to forget: old-site (no project)`

#### Scenario: The project folder is a repository
- **WHEN** `<ws>/projects/shop` itself is a git repository with a commit on a branch with
  no upstream, and the human runs `lado project delete shop`
- **THEN** the list has `  the project's folder: …; branch main not pushed`

#### Scenario: A worktree inside the project folder
- **WHEN** `<ws>/projects/shop/frontend-fix` is a worktree of `<ws>/projects/shop/frontend`
  with uncommitted changes
- **THEN** the list has the line `  frontend (worktree frontend-fix): uncommitted changes`
  once and no line of its own for `frontend-fix`

#### Scenario: An unreadable project folder
- **WHEN** `<ws>/projects/shop` cannot be listed (no read permission) and the human runs
  `lado project delete shop`
- **THEN** the list has `  the project's folder: could not check: Permission denied`, it
  exits 1 with a `lado: …` line, and no traceback is printed

#### Scenario: A link to a repository elsewhere
- **WHEN** `<ws>/projects/shop/docs` is a symbolic link to `/srv/docs`, a repository with
  an uncommitted file and a branch with no upstream, `frontend` beside it has a branch
  `feature-x` with no upstream, and the human runs `lado project delete shop`
- **THEN** the list has `  frontend: branch feature-x not pushed` and no line for `docs`

#### Scenario: A worktree of the link's repository
- **WHEN** `<ws>/projects/shop/docs` is a symbolic link to the repository `/srv/docs`, and
  `<ws>/projects/shop/docs-fix` is a worktree of `/srv/docs` with an uncommitted file
- **THEN** the list has a line `  docs-fix: …` that names `uncommitted changes`, and no
  line for `docs`

### Requirement: The unpushed check does not count a project's repositories as its folder's changes

When the project's folder is itself a repository's root, its line SHALL NOT name
`uncommitted changes` for the entries directly in it that are git repositories or
worktrees (the project's repositories), nor for a symbolic link directly in it to one; a
change of the root repository's own files SHALL still be named.

#### Scenario: A clean root around the project's repositories
- **WHEN** `<ws>/projects/shop` is a clean repository holding the repositories `frontend`
  and `backend`, all pushed
- **THEN** `lado project delete shop` prints no unpushed list

#### Scenario: A change of the root's own file
- **WHEN** the root repository has an uncommitted `README.md`
- **THEN** the list has `  the project's folder: uncommitted changes`

#### Scenario: A link in a clean root
- **WHEN** `<ws>/projects/shop` is a clean, pushed repository holding `docs`, a symbolic
  link to a repository elsewhere with an uncommitted file
- **THEN** `lado project delete shop` prints no unpushed list
