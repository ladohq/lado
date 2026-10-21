## RENAMED Requirements

- FROM: `### Requirement: A fresh start's default folder is in the clone's parent`
- TO: `### Requirement: A fresh start's default folder is in the workspace`

## MODIFIED Requirements

### Requirement: A fresh start's default folder is in the workspace

The default folder of a fresh start SHALL be `<workspace>/<name>`, the workspace being the
clone's (`projects.workspace`: `LADO_REPOS`, else `~/workspace`), made when missing. A
given folder SHALL be a full path (`~` allowed).

#### Scenario: The default folder in the container
- **WHEN** `LADO_REPOS=/Users/ann/projects` and the human types the name `Сайт кофейни`
- **THEN** the folder is `/Users/ann/projects/sait-kofeini`, state `new`

#### Scenario: The default folder without LADO_REPOS
- **WHEN** `LADO_REPOS` is unset, `~/workspace` does not exist and the human types the
  name `shop`
- **THEN** the folder is `~/workspace/shop` (expanded), state `new`, and Create and start
  makes `~/workspace` with it

### Requirement: The server checks and starts a fresh start

`GET /api/scratch-target?text=<name>[&path=<folder>]` SHALL answer 200 with `path` (the
folder given, else the default one), `name`, `title`, `problem` (the name's refusal, or
null), `state` and `text` (the folder's), `author` (`{text, hint}` when git does not know
the author, else null), `name_state` (as `FolderInfo`'s), `provider` (as `CloneTarget`'s)
and `warning` (as `FolderInfo`'s, `runtime.outside_workspace`). With a name refused and no
folder given, `path` SHALL be null.

#### Scenario: A name checked
- **WHEN** the window asks `GET /api/scratch-target?text=Сайт кофейни` with no
  `LADO_REPOS`
- **THEN** the answer has `path` `~/workspace/sait-kofeini` (expanded), `name`
  `sait-kofeini`, `title` `Сайт кофейни`, `state` `new`
