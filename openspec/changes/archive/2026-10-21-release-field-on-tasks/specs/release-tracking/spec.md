## ADDED Requirements

### Requirement: A merge into main records the coming release on the task

After a pull request of a task merges into `main`, the task SHALL get the merge comment
by the template of `.lado/sdlc.md` (After the merge), move to the status `done`, get the
label `waiting for release`, and get the field `release` set to X.Y.Z of CHANGELOG.md's
`## X.Y.Z (unreleased)` heading on `main` after the merge. Without such a heading the
comment SHALL say «войдёт в следующий релиз» and the field SHALL stay as it was.

#### Scenario: The coming release is in CHANGELOG
- **WHEN** a pull request of LAD-119 merges into `main` and CHANGELOG.md starts with
  `## 0.42.1 (unreleased)`
- **THEN** LAD-119 has the comment «**Слит PR #<n>** — войдёт в релиз 0.42.1.», is in
  `done`, has the label `waiting for release`, and its `Release` sticker holds `0.42.1`

#### Scenario: No unreleased heading
- **WHEN** a pull request of a task merges into `main` and CHANGELOG.md has no
  `(unreleased)` heading
- **THEN** the comment says «войдёт в следующий релиз», the task is in `done` with the
  label `waiting for release`, and its `Release` sticker is as before

### Requirement: A merge into an epic branch only comments

After a pull request of a task merges into an epic branch, the task SHALL get only the
comment whose first line is «**Слит PR #<n> в эпик-ветку `<branch>`** — войдёт в релиз
вместе с эпиком.»; its status, labels and fields SHALL stay as they were.

#### Scenario: A task of an epic
- **WHEN** a pull request of a task in review merges into `epic/lad-116-projects`
- **THEN** the task has that comment, stays in review, gets no label `waiting for
  release` and no `release` value

### Requirement: The final release records its version on the tasks it ships

The final release X.Y.Z SHALL, on each task in `done` with the label `waiting for
release` whose change it ships, post the comment «Вышла в X.Y.Z», set the field `release`
to X.Y.Z, and remove the label; a task whose change it does not ship SHALL keep its
label and its field.

#### Scenario: The planned patch became a minor
- **WHEN** LAD-119 merged with `release` = `0.42.1`, and its change ships in the final
  0.43.0
- **THEN** LAD-119 has the comment «Вышла в 0.43.0», its `Release` sticker holds
  `0.43.0`, and the label `waiting for release` is gone

#### Scenario: A task merged before the field existed
- **WHEN** a task in `done` with the label and no `release` value ships in 0.42.1
- **THEN** its `Release` sticker holds `0.42.1` and the label is gone

#### Scenario: A task not in the release
- **WHEN** a task in `done` with the label merged after the release commit
- **THEN** it keeps the label and its `release` value
