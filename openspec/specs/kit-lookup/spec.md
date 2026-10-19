# kit-lookup Specification

## Purpose
Where LADO finds a kit by its name, for a session, the CLI and the UI alike, so that the
kits a human can use do not depend on the folder a session runs in.

## Requirements

### Requirement: Kits come only from the installed and the built-in ones

LADO SHALL look a kit up by name among the installed kits (the `kits` table of lado.db),
then among the kits built into LADO, and take the first one found. It SHALL NOT read a
repository's `.lado/kits` folder, for a new session, a resume, a spawned worker, a flow
run, `lado kits`, `kits show`, `kits check` or any API endpoint.

#### Scenario: A repository's own kit is not read
- **WHEN** a repository has `.lado/kits/team/kit.yaml` and no kit `team` is installed or
  built in, and `lado start <repo> --kit team` runs
- **THEN** the start is refused with `kit "team" not found; looked in the installed kits
  in …/lado.db, …/builtin_kits`, and no session is made

#### Scenario: An installed kit of the same name is used
- **WHEN** a repository has `.lado/kits/team/` and a different folder kit `team` is
  installed (`lado kits add <folder>`)
- **THEN** a session of that repository with `--kit team` takes the installed kit's agents

#### Scenario: An installed kit shadows a built-in one
- **WHEN** a kit named `default` is installed
- **THEN** sessions take the installed `default`, and `lado kits` lists the built-in one
  as `shadowed by user`

### Requirement: A kit found nowhere is refused with where LADO looked

A name found in neither the installed nor the built-in kits
SHALL be refused with `kit "<name>" not found; looked in the installed kits in
<LADO_HOME>/lado.db, <the built-in kits' folder>`, followed only by the hints about an
older LADO's `LADO_HOME` (`sources.yaml`, `LADO_HOME/kits`) when they apply; nothing about
project kits.

#### Scenario: A stopped session whose kit was a project kit
- **WHEN** a session was started with a kit that lived only in its repository's
  `.lado/kits`, and `lado start` resumes it
- **THEN** the resume is refused with the same `kit "<name>" not found` text, with no
  hint about project kits

### Requirement: The kit list does not depend on a folder

`lado kits` SHALL take no `--repo` option, and `lado kits`, `kits show` and `kits check
<name>` SHALL list and resolve the same kits whatever the current folder. `GET /api/kits`
SHALL take no folder and give the kit of each name the lookup takes, the same list for
every request; a `where` a page still sends SHALL be ignored, not refused.

#### Scenario: --repo is refused
- **WHEN** `lado kits --repo <repo>` runs
- **THEN** argparse refuses it as an unrecognized argument and exits 2

#### Scenario: The same list for every folder
- **WHEN** two repositories differ only in their `.lado/kits` folders
- **THEN** `lado kits` run in either prints the same kits

#### Scenario: The API's kit list ignores a folder
- **WHEN** `GET /api/kits?where=<repo>` is asked for a repository with `.lado/kits/team/`
  and no kit `team` is installed
- **THEN** it answers 200 with the same list as `GET /api/kits`, without `team`

### Requirement: A kit's users are every session that names it

The sessions that use a kit (`runtime.kit_users`: `lado kits remove`'s warning and the
Kits page's remove-preview) SHALL be every running and every stopped session whose kits
name it, whatever its repository holds.

#### Scenario: A session whose repository has a kit folder of that name
- **WHEN** a stopped session of a repository with `.lado/kits/team/` has the kit `team`,
  and the human asks to remove the installed kit `team`
- **THEN** the preview names that session as a stopped session that uses `team`
