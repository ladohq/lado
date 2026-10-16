## ADDED Requirements

### Requirement: In a container LADO warns about a session folder outside LADO_REPOS

In a container (`LADO_CONTAINER`), with a repositories folder (`LADO_REPOS`), LADO SHALL
warn about a session folder whose real path is not the repositories folder's real path or
below it. The warning is `Outside the repositories folder (<folder>): this folder is only
in the container, your computer does not see it or the agents' work in it`. One function
(`runtime.outside_repos`) SHALL give it, or None:
- for the UI's folder check, as `FolderInfo.warning`, shown under **Where** after the
  check mark;
- for the clone's target, as `CloneTarget.warning`, shown under **Clone into**;
- for a start and a resume, among its warnings: `lado start` on stderr, `Started.warnings`
  in the UI, the result of the supervisor's `start_session`.
It SHALL never refuse a folder: the check mark and Start stay as they are. Outside a
container, or without a repositories folder, there SHALL be no warning.

#### Scenario: A folder on the home volume
- **WHEN** in a container with `LADO_REPOS=/Users/ann/projects` the human types
  `/home/lado/app`, a git repository, into Where
- **THEN** the window shows `✓ git repository · branch main`, then `⚠ Outside the
  repositories folder (/Users/ann/projects): this folder is only in the container, your
  computer does not see it or the agents' work in it`, and Start is available

#### Scenario: A folder of the projects
- **WHEN** in that container the human types `/Users/ann/projects/app`
- **THEN** no warning shows

#### Scenario: The repositories folder through a link
- **WHEN** the folder is a symbolic link whose real path is below the repositories folder
- **THEN** no warning shows

#### Scenario: A start outside it
- **WHEN** in that container `lado start /home/lado/app` starts a session
- **THEN** stderr has the warning, and the session runs

#### Scenario: Outside a container
- **WHEN** LADO runs without `LADO_CONTAINER` and with `LADO_REPOS=/Users/ann/projects`,
  and the human types `/tmp/app`
- **THEN** no warning shows
