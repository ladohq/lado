# Kits guide

A kit is a team for LADO: the agent roles, their skills and MCP servers, and the flows they
work by, in one git repository (or a folder). This guide shows how to find and install a
kit, use kits in a session, write your own, release new versions of it and share it.

- [1. What a kit is](#1-what-a-kit-is)
- [2. Find and install a kit](#2-find-and-install-a-kit)
- [3. Use kits in a session](#3-use-kits-in-a-session)
- [4. Create a kit](#4-create-a-kit)
- [5. Flows](#5-flows)
- [6. Improve and version a kit](#6-improve-and-version-a-kit)
- [7. Share your kit](#7-share-your-kit)
- [8. Troubleshooting](#8-troubleshooting)

## 1. What a kit is

A kit is a folder with a `kit.yaml` at its root; for others to install it, that folder is
the root of a git repository. Everything else is optional:

```
my-team/
├── kit.yaml                 # name, version, who leads, dependencies, expects
├── agents/                  # one file per role
│   ├── lead.md
│   └── reviewer.md
├── skills/                  # one folder per skill
│   └── house-style/
│       └── SKILL.md
└── flows/                   # one file per flow
    └── feature.yaml
```

- **Roles** (`agents/<role>.md`): a prompt with a short YAML header; LADO starts a worker
  of the role in its own git worktree and branch.
- **Skills** (`skills/<name>/SKILL.md`): instructions an agent loads when it needs them,
  through its CLI's own skill support. A kit can also take skill packs from other
  repositories, pinned to a version.
- **MCP servers**: tools a role's agent gets, listed in its header.
- **Flows** (`flows/<name>.yaml`): steps, who acts in each, the allowed outcomes and the
  points where you decide. LADO enforces them, not the agent.

A kit with no agents is fine too: it brings only skills to the session (a tracker kit
does that).

The kits you can start with:

- `default`, built into LADO: a supervisor that delegates to general-purpose coding
  workers. A session without `--kit` uses it.
- From the official marketplace (github.com/ladohq/marketplace):
  - `sdlc`: day-to-day development of a project whose tasks live in a tracker, one task
    per run, from the design to the merged pull request; you approve the design and the
    merge. It needs a tracker kit next to it.
  - `tracker-jira-server`: the skill `tracker` for Jira Server / Data Center; no agents.
  - `kit-builder`: builds and evaluates kits (see [Create a kit](#4-create-a-kit)).
- `tracker-yougile` (github.com/ladohq/kit-tracker-yougile): the skill `tracker` for
  YouGile; installed by its git address.

## 2. Find and install a kit

### From a marketplace

A marketplace is a git repository that lists kits by name. The official one is always
there:

```bash
lado kits add sdlc -m official          # the kit named sdlc in the marketplace official
lado kits add sdlc@v0.5.0 -m official   # a given version
```

Without `-m` LADO never looks in a marketplace. Manage the marketplaces you use:

```bash
lado marketplaces                       # list them (also: lado marketplaces list)
lado marketplaces add team https://github.com/<owner>/marketplace
lado marketplaces update                # fetch the latest list of each enabled one
lado marketplaces update team           # of one
lado marketplaces disable official      # and enable; official can only be disabled
lado marketplaces remove team           # the kits installed from it stay
```

### From git or a folder

```bash
lado kits add https://github.com/<owner>/my-team           # its latest release
lado kits add https://github.com/<owner>/my-team@v1.0.0    # that release
lado kits add https://github.com/<owner>/my-team --pre     # the latest, pre-releases too
lado kits add ./my-team                                    # a folder, read in place
```

A kit from git is installed by a version tag `vX.Y.Z` and the commit that tag points to
now; a branch or a bare commit is refused. A folder has no version: LADO reads it in place
each time, which is how you develop a kit.

A kit from anywhere but the official marketplace or a folder shows first what it would
install (address, version, commit, its MCP servers) and asks `Install? [y/N]`. `--yes`
skips the question; without a terminal it is required. A kit whose latest version needs a
newer LADO is refused.

### Keep them up to date

```bash
lado kits                               # every kit, its version and where it comes from
lado kits outdated                      # installed kits against their repositories' tags
lado kits update my-team                # to its latest release (--pre: pre-releases too)
lado kits update my-team v1.2.0         # to another version
lado kits remove my-team                # drops it from LADO; its folder stays
```

`update` does not ask, but warns about MCP servers the installed version did not start.
Running sessions take the new version only for agents they start from then on; the output
names those sessions. `remove` warns about the sessions that use the kit.

If a tag now points to another commit than the one installed, `outdated`, `update` and
`add` warn loudly: someone moved the tag.

### In the web UI

`lado ui`, then **Kits**: the installed kits, the kits the enabled marketplaces offer, the
updates (checked only when you press its button) and the marketplaces. Each install and
update shows the same plan the CLI prints before it asks.

### Project kits

A kit in `<repo>/.lado/kits/<name>/` belongs to that project and needs no install. LADO
looks a kit up by name in the project first, then among the installed kits, then among
the built-in ones; the first one found wins. `lado kits --repo <repo>` lists what a
project sees.

## 3. Use kits in a session

```bash
lado start . --kit sdlc --kit tracker-jira-server
```

Repeat `--kit` to combine kits; the order does not matter. A resumed session keeps its
kits unless you give `--kit` again. `lado kits show sdlc tracker-jira-server` prints what
they combine into without starting anything: who leads, each agent's skills and where
they come from, the MCP servers, the flows.

### Who leads

If exactly one of the session's kits has a supervisor (`supervisor:` in its kit.yaml),
that supervisor leads. Otherwise LADO's built-in supervisor leads, and each kit's
supervisor hands its rules to it as a skill `lead-<kit>`: its prompt, and where to read
the skills its `skills:` names, in that kit's versions. The lead reads those copies but
does not load them as its own skills, so two kits may bring two versions of one skill.
A kit supervisor's MCP servers are not passed on, and one without `skills:` passes no
skills: LADO warns about both. Such a supervisor's `skills:` is checked as if it led, so a
skill its kit does not have stops the start.

`lado start` prints who leads (`lead: ...`); `lado kits show` also lists the lead skills.

The lead starts workers with `spawn_worker(role=...)`; the role may be left out only when
the session has one worker role.

### Switch things off

`--without kind:name` switches off an agent, flow, skill or MCP server (kinds `agent`,
`flow`, `skill`, `mcp`) in the whole session. `--without kind:name@kit` switches it off in
that kit only, before the kits are combined. Repeat it as needed:

```bash
lado start . --kit default --kit my-team --without agent:supervisor@default
lado start . --kit kit-a --kit kit-b --without agent:reviewer@kit-b
lado start . --kit sdlc --kit tracker-jira-server --without mcp:playwright
```

### Shared names

Names are shared in a session: a flow of kit-b that calls `reviewer` gets kit-a's
`reviewer` when kit-b has none. A name that two kits both define (a role, a skill, a flow)
stops the start, and the error gives each `--without ...@<kit>` that
resolves it. A kit's supervisor is no role: `--without agent:<name>` that names one is
read as `agent:<name>@<its kit>` (so sessions of older LADOs resume as before); when
several kits' supervisors have that name, give the kit.

### Kits that expect each other

A process kit can use a skill another kit brings, such as `sdlc`'s roles using the skill
`tracker` of whichever tracker kit the project uses (see `expects` in
[Create a kit](#4-create-a-kit)). A session in which no kit provides an expected skill, or
whose `--without` switches it off, does not start, and the error says why. `lado kits show`
says which kit provides each one.

## 4. Create a kit

### With kit-builder

```bash
lado kits add kit-builder -m official
lado start . --kit kit-builder
```

Its supervisor interviews you about your process (or starts from an archetype) and writes
a blueprint that says why each part of the kit exists; an author writes the kit, and a
critic checks it against a complexity budget and a rubric before you tag a release. Its
flows: `create` takes a new kit from the interview to its tag, `improve` takes an existing
kit from the critic's report to a new tag, `evaluate` reports on any kit. The blueprint,
the plan and the reports are artifacts you read in the web UI.

### By hand: kit.yaml

```yaml
name: my-team             # lowercase letters, digits, - or _
version: 1.0.0            # required; X.Y.Z or X.Y.Z-<pre-release>
description: Reviews and ships small changes.
supervisor: lead          # optional: the agent of this kit that leads a session
dependencies:
  lado: ">=0.30"          # optional: the oldest LADO the kit runs with
  skills:                 # optional: skill packs, by name
    superpowers: https://github.com/obra/superpowers@v6.4.1
expects:
  skills: [tracker]       # skills another kit of the session must bring
  commands: [openspec]    # CLIs the kit's agents need on their PATH
```

- `supervisor` names one of the kit's agents. The agent name `supervisor` is reserved for
  the session's lead: a kit may use it only with `supervisor: supervisor`.
- `dependencies.lado` is `">=X.Y"` or `">=X.Y.Z"`. An older LADO refuses the kit and says
  to upgrade.
- `dependencies.skills` maps a pack name to `<git-url>@<tag or commit>` (a version is
  required), or to a folder relative to the kit (no version). A pack is a repository or
  folder of `SKILL.md` folders under its `skills/`, and no `kit.yaml`; to read other
  folders of it, give `{from: <git-url>@<ref>, folders: [path, ...]}`. Each version of a
  pack is cloned once into LADO's git cache. One skill name is one folder in a kit: a name
  both in the kit and in a pack, or in two packs, is an error.
- `expects.skills` (LADO 0.29 and newer) names skills another kit of the session must
  bring. `lado kits check` and `lado kits show` take them as there, so the kit checks
  alone; a session must have a kit that provides each.
- `expects.commands` (LADO 0.30 and newer) names the external CLIs the kit cannot work
  without, each as PATH finds it (`openspec`, `uv`; no path, spaces or arguments). LADO
  checks only that each is on the agents' PATH, the one of your login shell that agents
  start with: not its version, nor whether it is logged in or set up (the kit's own text
  checks that). `lado start`, a resume and each new worker look again; when one is
  missing, nothing starts, and one error names every missing command, its kit and the
  agents' PATH. A command that only some projects of the kit need (a code host's CLI
  chosen by the project's settings) does not belong there. `lado kits check` lists them
  (`expects commands: openspec`) and warns about one that is not on its own PATH, since a
  kit is also checked where it does not run (a marketplace's CI); `lado kits show` gives
  each one's place on the agents' PATH. LADO does not check the commands of a kit's MCP
  servers yet: list one there too to have it checked.

A kit with `expects` should say `dependencies.lado` of at least the LADO that reads the key:
`lado kits check` warns otherwise, since an older LADO refuses the key without saying to
upgrade.

What a kit installs (`dependencies`) comes with it; what it expects, another kit of the
session must bring:

```bash
lado kits check .                                  # passes alone: expects skills: tracker
lado start . --kit sdlc --kit tracker-jira-server  # the tracker kit provides tracker
```

### Roles

A role is `agents/<name>.md`: a YAML header between `---` lines, then the role's prompt.

```markdown
---
name: reviewer                       # the file's name
description: Reviews a branch and reports what to fix.
skills: [house-style]                # optional: the skills it gets; all it can see without it
read_only: true                      # optional: it must not change the repository
mcp:                                 # optional: its MCP servers, stdio only
  db:
    command: ["${KIT_DIR}/bin/db-mcp", "--read-only"]
    env: {DB_TOKEN: "${DB_TOKEN}", MODE: ro}
---
You review the branch your supervisor names. ...
```

- `description` is required; the lead's instructions list each role with it.
- Without `skills`, the agent gets every skill it can see: the session kits' own skills,
  the packs of kits without agents, and its own kit's packs. With `skills`, only those.
- `${KIT_DIR}` is the kit's folder, in the prompt and in an MCP server's `command` and
  `env`.
- LADO's own instructions (how to message, report, use flows) are added after the prompt:
  the prompt says only what the role does.

### Skills

A skill is `skills/<name>/SKILL.md`, the format the agent CLIs read: a YAML header with
`name` (the folder's name) and `description`, then the text. Files next to it in the
folder go with it. Inside a skill, refer to them by relative paths: the agent's CLI tells
the model where each skill lives.

### MCP servers

A role's `mcp` maps a server name (not `lado`) to `command` (a list: the program and its
arguments) and `env` (names to strings). Only stdio servers.

`${NAME}` in `env` is a variable of the agent's environment (your login shell's, as a new
terminal sees it): a missing one stops the agent's start. Its value is never written to
disk: the agent's CLI starts such a server through LADO's wrapper (`lado.mcp_exec`), whose
arguments name the variables only; the wrapper takes the values from the environment the
CLI passes on and starts the server. `lado doctor` warns about config folders under
`LADO_HOME/agents/` that no running agent uses: an older LADO wrote such values there.

Never write an absolute or home path (`/Users/...`, `~/...`) into a kit: use `${KIT_DIR}`
or a relative path. `lado kits check` fails on such paths.

### Read-only roles

A role that must not change the repository (a reviewer, a checker, a passive supervisor)
says `read_only: true`. Then:

- Its agent's CLI gets no tools that edit files, its subagents included:
  - Claude Code, OpenCode and Kilo: their edit tools are taken away in the agent's own
    config. An agent the repository's or your own CLI config defines with its own edit
    rule (a custom subagent) is not covered.
  - Codex CLI: its worktree tool is off; with a model Codex has no metadata for (any local
    one) no tool but the shell writes files. An OpenAI model may still get Codex's
    apply_patch tool, which no setting takes away: each launch of a read-only Codex agent
    warns about it.
- A read-only supervisor gets none of LADO's tools that start or end agents and runs.
- LADO compares the repository at each of the agent's turns: a commit, an edit or a new
  file it finds is one line to the supervisor (to you for a read-only supervisor) and an
  event in `lado log`.

The agent keeps its shell, for `git diff`, linters and tests, so this is no sandbox:
nothing is blocked or undone. `lado kits show` and `lado kits check` name the read-only
roles.

### Develop it from a folder

```bash
lado kits check ./my-team     # validate it, fetch its skill packs
lado kits add ./my-team       # install the folder, read in place
lado start . --kit my-team    # a session with it; edits apply to the next agent started
```

## 5. Flows

A flow is a kit's way of doing one kind of task, as states. A file `flows/<name>.yaml`:

```yaml
name: feature                  # the file's name
description: A feature from design to merge.   # the lead picks a flow by it
start: design                  # the first state
states:
  design:                      # a work state: the role in agent does do
    agent: lead
    do: Design the change with the human.
    produces: [design]         # optional: artifacts its step must write
    outcomes: {ready: design_ok}
  design_ok:                   # a gate: you answer ask
    gate: approval
    ask: Build this design?
    reads: [design]            # optional: artifacts you are shown
    outcomes: {approved: implement, rejected: design}
  implement:
    agent: developer
    do: Build it test-first and report what changed.
    reads: [design]
    produces: [report]
    outcomes: {done: review}
    max_visits: 3              # optional: how often the state may be entered
  review:
    agent: reviewer
    do: Review the branch.
    produces: [review]
    outcomes: {fix: implement, ok: merge_ok}
  merge_ok:
    gate: choice
    ask: Merge it, or send it back?
    reads: [review]
    outcomes: {merge: done, back: implement}
  done:
    end: true
```

Top-level keys: `name`, `description`, `start`, `states`. Each state is exactly one of:

- **Work** (`agent`): the agent of that role does `do` and reports one of its `outcomes`
  (outcome name -> next state). Optional: `max_visits` (a whole number of 1 or more),
  `produces` and `reads`. A state of the kit's supervisor is given to the session's lead,
  whoever leads.
- **Gate** (`gate`): the run waits for you. `gate: approval` has exactly the outcomes
  `approved` and `rejected` (you answer approve or reject); `gate: choice` offers its
  outcome names. `ask` is the question; `reads` is optional.
- **End** (`end: true`): the run ends.

State names are letters, digits and `_`, not starting with a digit.

**Artifacts.** `produces` names the documents a step must write (a design, a review, a
report): no outcome is accepted until each was written in that visit, and they go with
the step's note to whoever acts next. `reads` names artifacts of the run that a step or
gate is shown: their latest version's title and summary, never the whole content, so the
agent reads what it needs. Each name in `reads` must be one some state produces and not
one of the reading state's own `produces`. The short message about a step (its verdict,
questions for you) is its note, not an artifact; something a step writes only sometimes
(a mockup, a log) it attaches to its note.

**Loops.** When a run would enter a state more often than its `max_visits`, it waits for
you: continue (the visit counts) or cancel the run.

**Answering a gate.** When a run reaches a gate, LADO opens a tmux popup in each terminal
attached to the session, and the web UI shows the gate in the session's chat. Answer
there, or with `lado answer` (it lists the open gates; `lado ls` shows them too). You see the note that led to the gate and the
artifacts it reads; your comment goes with your answer to the next step. `lado flow-set
<session> <run> <state> --reason TEXT` moves a run anywhere, past a gate or a loop limit.

**Starting a run.** Ask the lead for a task; it picks the flow by its description. `lado
ls` shows each open run, its state and who acts next.

**Checks.** A flow that does not parse, has a state no `start` reaches, reaches no end, or
names an unknown state, stops the kit from loading. `lado kits check` also fails on what a
flow could run with but should not have: a state from which no end can be reached, a
cycle with no `max_visits` and no gate on it (agents could loop forever), and a name in
`reads` that no earlier state produces. It warns about a step whose role is not in the
kit (another kit of the session may have it) and a role that acts in none of the kit's
flows.

## 6. Improve and version a kit

A kit's versions are its repository's tags `vX.Y.Z`; pre-releases such as `v1.3.0-rc.1`
too. `version` in kit.yaml must say the same as the tag: `lado kits add` refuses a tag
whose kit.yaml says another version.

To release:

1. Change the kit; set `version` in kit.yaml to the new version.
2. Raise `dependencies.lado` when the kit uses something a newer LADO brought.
3. Pin each skill pack to a tag or commit; move a pin only on purpose, since a pack's new
   version changes how your agents work.
4. Check the release as `lado kits add` would, then tag and push:

   ```bash
   lado kits check . --tag v1.1.0
   git tag v1.1.0 && git push origin v1.1.0
   ```

Run `lado kits check . --tag "$TAG"` in the kit's CI on each tag: it fails on what `add`
would refuse and on `lint`'s problems (hardcoded paths, the flow checks above), and prints
warnings, such as a `version` that differs from the clone's tags.

Never move a released tag: users' LADO warns loudly when a tag points to another commit
than the one installed. Release a new version instead.

What users see: `lado kits outdated` (and the UI's Updates) lists your new release; `lado
kits update <kit>` takes it, and running sessions use it for the agents they start after
that. `outdated` names a newer pre-release too; `add` and `update` take one as the latest
only with `--pre`.

## 7. Share your kit

1. Publish the kit's repository where your users can clone it, with a release tag.
2. They can install it by its address right away:
   `lado kits add https://github.com/<owner>/my-team`.
3. To have it installed by name, add it to a marketplace: a git repository with a
   `marketplace.yaml` at its root that maps each kit's name (the `name` in its kit.yaml) to
   its repository:

   ```yaml
   kits:
     my-team: https://github.com/<owner>/my-team.git
   ```

   Your team adds the marketplace once (`lado marketplaces add team <its git url>`) and then
   installs with `lado kits add my-team -m team`.

What the UI's Kits page shows of a marketplace's kits comes from an `index.json` at the
marketplace's root, which its CI builds from the kits; LADO reads it from the marketplace's
clone, never the network. Version 1:

```json
{
  "index": 1,
  "kits": {
    "sdlc": {
      "address": "https://github.com/ladohq/kit-sdlc.git",
      "latest": "v0.5.0",
      "commit": "4be21c0…",
      "lado": ">=0.30",
      "description": "Day-to-day development of a project whose tasks live in a task tracker.",
      "agents": {"analyst": "the first line of the role's description"},
      "skills": ["openspec-changes"],
      "flows": ["task"],
      "mcp": {"playwright": "npx @playwright/mcp"}
    }
  }
}
```

`latest` is the latest release (no pre-release) and `commit` its commit, `lado` the kit's
`dependencies.lado`, `mcp` each MCP server's command on one line. Only `address` is
required, and it must be the one `marketplace.yaml` gives; keys LADO does not know are
passed over, so the CI may add some without a new version; a higher `index` needs a newer
LADO. `marketplace.yaml` stays the list of names and addresses: an entry of a kit it does
not list is left out. Without `index.json` the page shows each kit's name and address.

## 8. Troubleshooting

- **`kit.yaml says version X; the tag and kit.yaml must agree`**: `lado kits add` installs
  a tag only when kit.yaml says that version. Release a new tag with the right `version`; do not move
  the old one.
- **`kit "a" needs LADO >=X.Y, this is ...`**: the kit needs a newer LADO: `lado update`.
- **`kit "a" expects skill "tracker", which ...`**: no kit of the session provides it, or `--without`
  switched it off. Add a kit that provides it (`lado kits show` lists who provides what),
  or drop the `--without` the error names.
- **A missing command**: a kit's `expects.commands` is not on the agents' PATH. Install it
  so a new terminal finds it (the agents start with your login shell's PATH), then start
  again.
- **A name in two kits**: two kits define the same role, skill or flow. The
  error gives each `--without kind:name@kit` that resolves it; pick one.
- **`kit not found`**: check `lado kits` (and `lado kits --repo <repo>` for a project's
  kits). A kit installed by an older LADO in `LADO_HOME/kits` must be added again: `lado
  kits` prints the `lado kits add` of each.
- **`hardcoded path`** in `lado kits check`: use `${KIT_DIR}` or a relative path.
- **An installed kit's folder is missing**: `lado kits remove <name>`, then add it again.
