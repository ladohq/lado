## MODIFIED Requirements

### Requirement: lado doctor names the repositories folder

When `LADO_REPOS` is set and not empty, `lado doctor` SHALL print a check
`Repositories folder`: `ok` with `<path> (LADO_REPOS)` for a folder LADO may write in,
`info` with `<path> (LADO_REPOS), not made yet: the first clone makes it` for a missing
path, `warn` for a value that is not absolute, a path that is not a folder (`LADO_REPOS is
not a folder: <path>`), one LADO may not look at (`cannot look at LADO_REPOS <path>:
<reason>`) or a folder LADO may not write in (`LADO may not write in LADO_REPOS <path>:
<reason>`). Whether LADO may write SHALL be found by making a new hidden file in the
folder and removing it at once, never by its owner and mode bits alone, which a bind mount
of Docker Desktop shows wrong. When it is unset or empty, `lado doctor` SHALL print no
such line.

#### Scenario: The image's folder
- **WHEN** `lado doctor` runs with `LADO_REPOS=/Users/me/repos`, a folder
- **THEN** it prints `[ok  ] Repositories folder: /Users/me/repos (LADO_REPOS)`

#### Scenario: Unset
- **WHEN** `lado doctor` runs without `LADO_REPOS`
- **THEN** it prints no Repositories folder line

#### Scenario: A folder LADO may not write in
- **WHEN** `lado doctor` runs with `LADO_REPOS` a folder where LADO cannot make a file
- **THEN** it prints `[warn] Repositories folder: LADO may not write in LADO_REPOS
  <path>: <reason>`, and the folder holds no file the check made
