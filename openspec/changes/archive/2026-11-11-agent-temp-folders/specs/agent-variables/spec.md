## ADDED Requirements

### Requirement: Each agent has a temporary folder of its own

For each agent it launches (a session's start, a resume, `spawn_worker`, a run's worker), LADO
SHALL make the folder `<parent>/lado-<uid>/<session>/<agent>` when missing, with mode 0700, and
SHALL give it to the agent as `TMPDIR`, for every provider; `<parent>` is the `TMPDIR` of the
agent's environment from its layers, else `/tmp`.

#### Scenario: Two workers of one session
- **WHEN** session `shop` runs the workers `dev-1` and `dev-2`, and the login shell has no
  `TMPDIR`
- **THEN** `dev-1` has `TMPDIR=/tmp/lado-<uid>/shop/dev-1` and `dev-2`
  `TMPDIR=/tmp/lado-<uid>/shop/dev-2`, both folders exist with mode 0700, and a file one writes
  as `$TMPDIR/pr.md` is not the other's

#### Scenario: The user's own TMPDIR
- **WHEN** the login shell exports `TMPDIR=/var/folders/x/T/` and a session `shop` starts
- **THEN** its supervisor has `TMPDIR=/var/folders/x/T/lado-<uid>/shop/supervisor`, and the
  start's warnings name no `TMPDIR`

#### Scenario: Every provider
- **WHEN** a worker of Claude Code, of Codex, of Kilo and of OpenCode is spawned
- **THEN** each has a `TMPDIR` of its own, and the Claude Code worker also has
  `CLAUDE_CODE_TMPDIR` set to the same folder

### Requirement: A temporary folder not safe to use refuses the launch

When `<parent>/lado-<uid>` exists and is a link, not a folder, or a folder of another owner,
LADO SHALL refuse the agent's launch, before its window opens, with one line naming the path
and why; it SHALL NOT give the agent any folder under it.

#### Scenario: A link in /tmp
- **WHEN** `/tmp/lado-<uid>` is a symbolic link and a worker is spawned
- **THEN** `spawn_worker` fails with a line naming `/tmp/lado-<uid>` as a link, and no worker
  window opens

### Requirement: An agent's temporary folder lives as long as its state

LADO SHALL keep an agent's temporary folder over a stop and a resume, and SHALL remove it when
it forgets the agent (`finish_worker`, a spawn undone) or its session (`lado forget`), the
session's folder with it.

#### Scenario: Stop and resume
- **WHEN** a run's worker writes `$TMPDIR/notes.txt`, the session is stopped and resumed
- **THEN** the run's worker, started again, has the same `TMPDIR` and `notes.txt` is in it

#### Scenario: The worker finished
- **WHEN** the supervisor finishes the worker `dev-1` of session `shop`
- **THEN** `/tmp/lado-<uid>/shop/dev-1` is gone, and `dev-2`'s folder stays

### Requirement: Every agent is told to keep its temporary files in its folder

The instructions of every agent (supervisor and workers, every provider, read-only roles too)
SHALL say that its temporary files go to its own `$TMPDIR` and never to a fixed path in `/tmp`.

#### Scenario: A worker's instructions
- **WHEN** a worker is spawned
- **THEN** its instructions hold the line on temporary files after the lines on messages

## MODIFIED Requirements

### Requirement: A name LADO sets keeps LADO's value

When a file of the outside folder, or a variable of the session's project, has a name that
LADO or the agent's provider sets for that launch (such as a provider's config variable),
the launch SHALL keep LADO's or the provider's value and SHALL name the file or the
variable once in that launch's warnings (a start's, a resume's or `spawn_worker`'s); but
`TMPDIR`, whose value is the parent of the agent's temporary folder, SHALL NOT be named.

#### Scenario: A provider's variable
- **WHEN** the folder holds a file named after a variable the agent's provider sets for
  its launch
- **THEN** the agent has the provider's value, and the start's warnings say `variable file
  <name> in <folder> not used: LADO sets <name> for <provider>`

#### Scenario: A project's variable stored under a name now reserved
- **WHEN** project `shop` holds in `lado.db` a variable named after a variable the agent's
  provider sets for its launch, and a session of `shop` starts
- **THEN** the agent has the provider's value, and the start's warnings say `project
  variable <name> of shop not used: LADO sets <name> for <provider>`

#### Scenario: A project's TMPDIR
- **WHEN** project `shop` has the variable `TMPDIR=/data/tmp` and a session of `shop` starts
- **THEN** its supervisor has `TMPDIR=/data/tmp/lado-<uid>/shop/supervisor`, and the start's
  warnings name no `TMPDIR`
