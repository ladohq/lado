## MODIFIED Requirements

### Requirement: lado start refuses a target or a name before the clone

A folder that is not
`new` or `empty` SHALL be refused by `lado start <git-url>` with its text and nothing cloned; for `same_repo` the
next line SHALL be `lado: To start a session in it as it is: lado start <folder>`. A name
held by a session of another folder, and whatever else the new session's start would refuse
(capability session-scratch: "A new session is checked whole before its folder is made"),
SHALL be refused before the clone.

#### Scenario: The clone is there already
- **WHEN** `LADO_REPOS` is unset, `~/workspace/lado` is a clone of
  `https://github.com/ladohq/lado` and `lado start git@github.com:ladohq/lado.git` runs
- **THEN** it exits 1 printing the `same_repo` text and `lado start ~/workspace/lado`, and
  changes nothing

#### Scenario: A kit's refusal before the clone
- **WHEN** `lado start https://github.com/ladohq/lado --kit sdlc` runs and no kit gives the skill `tracker`
- **THEN** it exits 1 with the kit's refusal, and nothing is cloned
