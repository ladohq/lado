# Projects

The model of projects in LADO, settled with the human on 2026-10-21 (the concept
`projects-concept`; the epic LAD-116, its plan [docs/epics/lad-116/plan.md](../epics/lad-116/plan.md)).
This file is the contract the epic's steps are built against; a step that changes the model
changes this file.

> **What is built.** Only the workspace's name (step S1): the UI, `lado doctor` and the
> documents call the folder LADO keeps code in the workspace. Everything else here is
> steps S2–S7 and is marked **not built yet** where it is described. Until S2 the
> workspace is `LADO_REPOS` alone: without it LADO has no workspace, and there is no
> `~/workspace` default.

## Why

Today every session of one LADO runs in one environment: each agent of each session gets
the variables LADO got at its start (from Docker or from the user's login files). While
the work is for one company that is enough. Once two sessions work for different clients,
with different Yougile boards and different GitHub accounts, one set of keys is not.

Projects solve that. They are also LADO's first step to knowing what it works on: today a
project is a folder and variables; later it may bring sessions over several repositories,
the tracker tie-in and shared kit settings. The model is shaped so those fit in without a
rework.

## Words

- **Workspace**: the folder LADO keeps code in. In LADO's image it is mounted from the host,
  and `LADO_REPOS` names its path (the variable keeps its name so installations do not
  break). Without Docker it is `LADO_REPOS` too, and `~/workspace` when that is unset
  (**not built yet**: step S2). `lado doctor` shows which workspace is in use. The
  workspace is the human's folder: LADO owns only its subfolder `projects/`, everything
  else in it is the human's.
- **Project**: a named record in LADO with a folder and environment variables.
- **Project folder**: `<workspace>/projects/<project id>`. LADO always makes it, and
  everything in it belongs to the project.
- **Repository folder**: a git subfolder of a project folder, one repository of the
  project. A project folder itself is never a repository.

An example: on the host `~/code` is mounted as the workspace, LADO has two projects, and
there are sessions without a project.

```
~/code/                          ← workspace (LADO_REPOS); the human's folder
├── projects/                    ← projects only; LADO manages it
│   ├── shop/                    ← project "Shop" (id shop)
│   │   ├── frontend/            ← repository: git clone github.com/shop/frontend
│   │   │   ├── .git/
│   │   │   ├── .lado/worktrees/…  ← the workers' worktrees of this repository's sessions
│   │   │   └── src/…
│   │   └── backend/             ← repository: git clone github.com/shop/backend
│   └── acme/                    ← project "ACME CRM" (id acme)
│       └── crm/                 ← its one repository (a monorepo)
├── lado/                        ← a session without a project (a clone by URL)
└── scratch-idea/                ← a session without a project (from scratch)

~/.lado/                         ← LADO's data (in the container: the home volume)
├── lado.db                      ← projects, their titles and plain variables, sessions
└── projects/
    ├── shop/
    │   └── secrets/             ← project shop's secrets (700)
    │       ├── YOUGILE_API_KEY  ← file = variable, content = value (600)
    │       └── GH_TOKEN
    └── acme/
        └── secrets/
            └── YOUGILE_API_KEY
```

Docker's outside secrets are elsewhere, in the container's `/run/secrets/`, and LADO only
reads them. Their format is the same (file = variable), their place is not (Variables and
secrets, below).

## The project

**Not built yet** (step S2).

A project has an **id**: Latin letters, digits and `-`. It never changes, and it is at once:
- the project folder's name;
- the path of its data under `~/.lado/projects/`;
- its name in CLI commands and in the UI's addresses.

A project also has a **title**, the human name the UI shows. It can change at any time, as a
session's title can; without one the id is shown.

The project folder is always `<workspace>/projects/<id>`; another cannot be given. The path
is stored nowhere: it is derived from the id, so there is nothing for it to drift from.
The special cases:
- **A folder of that name already exists in `projects/`.** The project is not made, and
  LADO says why.
- **`projects/` in the workspace is the human's own folder**: it exists and holds more than
  LADO's projects. The first project is not made, LADO says why, and `lado doctor` warns
  about it too.
- **A folder in `projects/` with no project in LADO** (made by hand, or left over).
  `lado doctor` shows it as foreign. LADO does not touch it or take it for a project.
- **The workspace changed (another `LADO_REPOS`) or a project folder was deleted by
  hand.** The project shows as "folder not found", and `lado doctor` warns.

Repositories are added to a project in two ways, by a clone of a git URL or from scratch
(**not built yet**: step S4). LADO already does both for ordinary sessions; a project uses
the same paths and puts the result in its folder. A repository no longer needed is removed
with its folder, so the workspace is tidied up without going to the host.

## How LADO knows a project's repositories

**Not built yet** (steps S3 and S4).

The list of repositories is stored nowhere: LADO reads it from the disk each time. A
repository is a subfolder of the project folder that holds git; its branch and remote come
from git too. So the list cannot drift from the disk:
- a folder deleted by hand is gone from the UI;
- one cloned by hand appears.

A clone that is still running or that failed is not listed: LADO clones into a temporary
folder and renames it only at the end.

Later, facts about a repository that git does not hold may be needed: an order, a
description, a role ("frontend"), an address to clone it again. Then the database gets
additions to repositories, but the disk stays the truth of whether a repository exists: a
record without its folder shows as "missing, clone again?".

## The session

**Not built yet** (step S3; the New session window's way, step S6).

A session can start **without a project**, as today: from scratch, in a folder or by a clone
of a URL, anywhere but `projects/`. Such a session has no variables of its own; it lives in
LADO's environment.

**Inside `projects/` a session without a project does not start.** The New session window
and `lado start` refuse ("this folder belongs to the project Shop: start a session in the
project") and offer the session in the project at once. The workspace hints of the New
session window do not offer `projects/` for an ordinary session. The reasons:
- one repository would get two sets of keys;
- deleting the project would delete the folder under another session.

**A session in a project** starts by the New session window's fourth way:
1. Pick the project.
2. Pick a repository from the list. The list always shows, even with one item, so it is
   clear the session works in one repository. When sessions over the whole project come,
   the same list gets an item "all repositories".
3. When the repository is not there yet, the same list has "+ new repository": a clone or
   from scratch. It becomes part of the project at once, and the session starts in it.

In the CLI: `lado start --project <project> --repo <repository>`.

A session refers to its project by a record in the database; it never guesses the project
from its folder's path. A session's project shows in its head and in `lado ls`, and does
not change while the session exists. A session the supervisor proposes (`start_session`)
starts in the same project and repository as its parent.

## Variables and secrets

**Not built yet** (steps S5a and S5b).

A project has two kinds of variables:
- **plain** ones (a local model's address, a board's name): shown and editable;
- **secrets** (keys and tokens): a value is set and never shown again.

In the UI a secret can be **replaced** (a new value typed over the old one, unseen) or
**deleted**, as secrets work on GitHub and other services. In the CLI:
- `lado project set <project> NAME VALUE`: a plain variable;
- `lado project set <project> NAME --secret`: a secret, its value asked for hidden;
- `lado project unset`: remove one.

A name that looks like a secret (`*TOKEN*`, `*KEY*`, `*SECRET*`, `*PASSWORD*`) is not taken
as a plain variable. Names LADO and the agent CLIs manage (`LADO_*`, `PATH`, `HOME`,
`CLAUDE_CONFIG_DIR` and the like) are not taken at all.

**The whole session in a project** gets the project's variables:
- its supervisor;
- every worker, flow runs' workers included;
- a session its supervisor proposed;
- the subagents the CLI starts itself and the kits' MCP servers: the agent's child
  processes, which inherit its environment with no help from LADO.

An agent's environment is built in layers, each later one over the one before:

```
login shell → outside (Docker: /run/secrets) → project variables → LADO and the agent CLI
```

**Docker's outside secrets and a project's secrets do not clash:**
- **Where they are.** The outside ones are files in `/run/secrets/` that the human gives at
  the container's start; LADO only reads them and never changes them from the UI. A
  project's secrets LADO keeps itself, in `~/.lado/projects/<project>/secrets/`, in the same
  "file = variable" format.
- **A name set in both** takes the project's value: overriding is the point. A session
  without a project gets the outside value, a session in a project the project's.
- **What is shown.** The project's variables page shows which outside values the project
  overrides.

One function of the core builds the environment, so it works alike with Claude Code,
Codex, OpenCode and Kilo, with Docker and without.

**Kit keys.** A kit can declare that its MCP server needs a variable, e.g. `YOUGILE_API_KEY`
for the Yougile tracker kit. When it is missing, LADO today does not start such an agent and
says `YOUGILE_API_KEY is not set`. With projects the check takes the project's variables
into account: a key set only in the project counts as set.

A new value reaches the agents started after the change. A running process cannot change
its environment; that is how the operating system works. The UI says so plainly and shows
which sessions of the project are running: for a change to reach every agent, the session
is restarted.

Only the human sets variables, through the UI or the CLI. An agent cannot change projects or
variables: the commands refuse inside an agent, and there is no MCP tool for it. Otherwise
an agent could slip every future agent, say, a model address of its own.

## Where a project's data lives

**Not built yet** (steps S2 and S5b).

- **The project's record** (id, title, plain variables): in `lado.db`.
- **Secrets**: in `~/.lado/projects/<id>/secrets/`, one file per secret. The format is that
  of Docker's outside secrets (`LADO_ENV_DIR`, `/run/secrets`): the file's name is the
  variable's, its content the value, exactly one trailing newline dropped, its size
  limited, a name that is not allowed refused. One function of the core reads both folders,
  with all its checks and `lado doctor`'s warnings. Modes: 700 for the folders, 600 for the
  files. Each secret is written atomically as its own file (a temporary file, then a
  rename), so no shared lock is needed and edits of different secrets from the UI and the
  CLI do not overwrite each other. The list of files shows which secrets are set without
  showing their values.
- **The project folder**: in `<workspace>/projects/`.

In LADO's image `~/.lado` is on the container's home volume, not in the workspace. So the
secrets are not visible from the host through the mounted folder, and never land in a
repository or a project folder.

A secret's value goes nowhere: not into the API, the UI's feed, the logs, `lado log`, a bug
report or the usage statistics. A test with a "canary" secret checks each of these places.

**LADO is not a store.** Whatever matters belongs in a git repository with a remote, or on
a disk outside LADO. **A backup of LADO's home volume holds the projects' secrets**: keep it
as you keep the keys themselves.

## The security boundary

**The projects of one LADO are not isolated from each other.** They separate environments,
not access: every agent of one LADO runs as one user of the operating system, and an agent
of one project can technically read another project's secrets. It is a convenience, not a
security boundary.

**For clients that must not mix, run a separate LADO.** The documentation and the UI's
variables section say so plainly. A separate operating-system user per project would cost
too much: root, the CLIs' own logins, its own git, tools and tmux, and on macOS without
administrator rights it is not possible at all. Real isolation is for later, with cloud
workers and the LADO manager.

## Deleting

**Not built yet** (steps S2 to S7; today `lado uninstall` alone, below).

Deleting a project removes the project, its secrets, all its sessions (as `lado forget`
does) and the whole project folder.
- While any session of the project runs, LADO refuses.
- Before deleting, LADO shows what will be lost: sessions, and repositories with changes
  not committed or branches not pushed to a remote, the workers' worktrees included (they
  are inside the repository).
- Deleting is confirmed: in the UI by typing the project's id, in the CLI by `--yes`.

Deleting a repository works the same way, within its folder and its sessions. LADO never
deletes a folder outside `projects/`.

**`lado uninstall` deletes `LADO_HOME`, and with it the projects' secrets**, unless
`--keep-data` is given. It never deletes the workspace or a repository in it: it removes
only the worktrees and branches LADO made there, as `lado finish` would (docs/cli.md). In
Docker, removing the home volume (`docker volume rm`) deletes the secrets the same way; the
workspace on the host stays.

## The UI

**Not built yet** (steps S6 and S7), but for the workspace's name.

- **The Projects section** (a placeholder now): the list of projects with their title,
  number of repositories and running sessions.
- **A project's page**:
  - its repositories with branch and remote, each with "Start session" and "Delete";
  - "+ Add repository";
  - its variables, marked where they override an outside value, with the warning of the
    security boundary;
  - the project's sessions;
  - renaming its title and deleting the project.
- **The New session window** gets the way Project; the workspace hint of its folder field is
  called Workspace (built: step S1, the row `Workspace:`, docs/design/ui.md).

The exact screens are mockups for the human's approval in the UI steps.

## The architectural frame

- **Neutral core.** Projects and variables do not depend on an agent CLI.
- **One source of truth.** The project folder is derived from the id, the repositories are
  read from the disk, a session's project is a reference in the database.
- **A project changes only the agents' environment.** Kits, flows and the agents' protocol
  stay as they are.
- **A project lives whole inside one instance.** Everything it owns is found by its id: its
  record in `lado.db`, `~/.lado/projects/<id>/`, `<workspace>/projects/<id>/`. Nothing lies in
  places shared by the host, and no path is hardcoded. So a future **LADO manager** (a
  separate product that runs several instances on one host) can run them side by side
  without them getting in each other's way. Moving a project to an instance of its own (the
  same answer to "clients that must not mix") comes down to moving its record, its data
  folder and its project folder.
- **Cloud workers** will get a project's environment the same way as local agents.

### How the LADO manager hands variables to a project

The manager works with instances from outside and can hand variables over at two levels:
1. **The whole instance**, as today: outside secrets at the container's start
   (`/run/secrets`). Nothing new is needed.
2. **One project**, through the instance's API, the same way as the UI: make a project,
   write a variable, replace a secret. A secret is only written through this API, never
   read. For this it is enough that the UI's project operations go through the ordinary
   documented API with its token, as every change of the UI does; the design does so.

If the manager ever needs to set a project's keys before the instance starts, there is a
spare way: outside secrets per project (`/run/secrets/projects/<id>/NAME`) in the same
"file = variable" format, so the manager only puts files there. It would be one more layer
between "outside" and "project". It is not made now, and the model does not close it off.

How the projects of one instance combine with the manager's instances in the product is an
open question for later.

## Not now

- global variables, and variables of a session without a project;
- profiles (LAD-80 stays a topic of its own; if profiles come, they hold no environment
  variables);
- sessions over several repositories, and tasks over several repositories at once;
- the tracker tie-in and a shared file of kit settings per project (`.lado/sdlc.md`,
  `.lado/tracker.yaml`);
- a project's artifacts that outlive its sessions;
- isolation of projects from each other; outside secrets per project;
- managing the workspace's folders outside projects (BACKLOG.md).

## How it is built

The epic LAD-116 builds the model in steps; each merges on its own into `main` and leaves
LADO working. The steps, their checks and notes: [docs/epics/lad-116/plan.md](../epics/lad-116/plan.md).

| Step | What | Where it shows |
|---|---|---|
| S1 | This document; ROADMAP rewritten; the folder called the workspace in the documents, the UI and `lado doctor` | documents, UI |
| S2 | The project in the core: id, title, folder in `<workspace>/projects/`, a schema migration; `lado project list/create/show/rename/delete`; `lado doctor`'s checks; `~/workspace` without `LADO_REPOS` | CLI |
| S2b | Compose's `LADO_WORKSPACE`, an installed `LADO_PROJECTS` still taken | Docker |
| S3 | A session in a project: `lado start --project --repo`, the reference and its inheritance, no session without a project in `projects/`, `lado ls` and the head, repositories from the disk | CLI, head |
| S4 | Adding and removing a project's repositories | CLI |
| S5a | Plain variables: the project's layer of an agent's environment, kit keys, `lado project set/unset`, protected names | CLI |
| S5b | Secrets: their store, replace and delete, the canary test | CLI |
| S6 | UI: the Projects section, making a project, variables, the Project way of New session | UI |
| S7 | UI: a project's page, removing a repository and a project with the work not pushed shown | UI |

The minor version goes up from the step that brings the schema migration and new commands.
