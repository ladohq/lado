## ADDED Requirements

### Requirement: The unpushed check does not scan a link in a project's folder

A symbolic link directly in a project's folder SHALL NOT count as a repository of it in
the unpushed check: removing the folder removes the link only, so its target's work is
not listed, and a worktree in the folder of the link's repository is named by a line of
its own.

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

## MODIFIED Requirements

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
