# The CLI in use

How the `lado` commands behave: starting, kits, logs, finishing, stopping, gates and the
rest. Moved from AGENTS.md's "Try it locally" (LAD-82).

`uv run lado start <repo>` runs the working copy (a repository without commits is refused:
make a first commit). `lado start <git-url> [<folder>] [--branch NAME]` clones the URL's
branch (the remote's default without `--branch`) into the folder, a full path, by default
`<workspace>/<repo>` (the workspace: an absolute `LADO_REPOS`, else `~/workspace`, made with
the clone when missing), then starts there as `lado start <folder>` does: the folder must be new or
empty (a clone of the same repository there is refused with the `lado start <folder>` that
uses it as it is; LADO never fetches into or switches a folder that exists), and a name a
session of another folder has is refused before the clone (`runtime.check_name`). git's
progress goes to stderr; Ctrl-C ends git's process group, removes the temporary folder and
exits 130 (`lado: clone cancelled`), a SIGTERM or SIGHUP the same way with 128 + its
number; a start refused after the clone says `the clone stays
in <folder>`. `<folder>` and `--branch` without a git URL exit 2. `--prompt TEXT` or
`--prompt-file FILE` (`-`: stdin; not both, exit 2) gives the supervisor a first message
from the human, for a folder, a git URL and a resume alike: read and checked
(`runtime.check_prompt`: not empty, at most `MAX_MESSAGE` characters; a file it cannot read
is exit 1) before any clone or start, stdin read once, and `first message: queued for the
supervisor` after the Started or Resumed line. The UI starts sessions too (Launch). Use `LADO_HOME=/tmp/some-dir` and
`LADO_TMUX_SOCKET=lado-dev` to keep test sessions apart from the LADO you work with.

`lado start --new [<folder>]` (default: the current folder; relative paths are taken from
it) starts from scratch (`lado.scratch`): the folder must be new or empty (nothing but
`.DS_Store`) and in no git repository, and git must know the commits' author (`user.name`
and `user.email`). It makes the folder (and the folders above it), `git init`, the branch
of `init.defaultBranch` (else `main`) and one empty commit `Start from scratch` (no file, no
signing, no hooks), prints `Made <folder> a git repository with an empty first commit`, and
starts the session as `lado start <folder>` does, named by `--name` or the folder. A refusal
is exit 1 with its hint and changes nothing: a folder with files gets LAD-5's `git init`
command, a folder of a repository `lado start <root>`, a git without the author the `git
config --global` command (in LADO's container: `LADO_GIT_NAME` and `LADO_GIT_EMAIL` in
`.env`); a git step that fails removes what it made. A start refused after the repository
was made says `the repository stays in <folder>`. `--new` with a git URL, a second folder or
`--branch` exits 2. Without `--new`, `lado start` never makes a repository.

`lado project` keeps the human's projects (`lado.projects`, [design/projects.md](design/projects.md)):
a project is an id (lowercase Latin letters, digits and `-`, starting with a letter or
digit, at most 40 characters; it never changes), a title (the session title's rule; none
shows the id) and a record in lado.db; its folder is `<workspace>/projects/<id>`, derived
and made by LADO. `lado project create <id> [--title TEXT]` makes the record and the folder
(with the workspace and `projects/` when missing) and prints `Made project <id> "<title>":
<folder>`; it refuses, naming why and making nothing, a bad id, a taken id, an existing
`projects/<id>` (a dangling link too), a `projects/` that is the human's own folder (it
holds visible entries and none is a project's folder; `.DS_Store` and other names starting
with `.` do not count) and a workspace that is not a folder LADO may write in. `lado
project list` prints one line per project by id, columns padded: the id, the title (the id
without one) and the folder, `  (folder not found)` when it is missing (another workspace,
or deleted by hand); with none, `No projects. Make one with: lado project create <id>`.
`lado project show <id>` prints `<id> "<title>"`, `  folder:  <folder>`, `  made:    <local
YYYY-MM-DD HH:MM>` and the project's repositories read from the disk (`projects.repositories`:
the folders directly in the project folder, not hidden and not links, each a git root of its
own): `  repositories:` and one line each by name, `    <name>  <branch>  <remote>` padded,
`(detached)` and `(no remote)` for none, a symbolic link listed among them as `(a link to
<target>: clone it into <folder> instead)`; with none, `  repositories: none`; then the
project's variables: `  variables:` and `    <NAME>  <value>` by name, names padded, a line
break in a value shown as `\n` (`\r` as `\r`); with none, `  variables: none`; then the
names of its secrets, never a value: `  secrets:` and `    <NAME>` by name, or `  secrets:
none` (listed without opening a file: each file of its secrets folder that is no link, has a
variable name and is not reserved, also one readable by others, which a new value through
`--secret` writes 600; one the agents still cannot take is named by `lado doctor`). `lado project
set <id> NAME VALUE` sets a plain variable of the project (over its old value) that every
agent of the project's sessions gets from its next start ([design/agents.md](design/agents.md),
The agent's environment); a value starting with `-` goes after `--` (`lado project set shop
FLAGS -- -v`). It prints `Set <NAME> in project <id>.` and `Agents started from now on get
it.`, or, while sessions of the project run, `Agents started from now on get it; running
sessions of <id> keep the old environment until restarted: <names>`. It refuses, exit 1,
storing nothing: a name that is no variable name (`the name <NAME> is not a variable name:
Latin letters, digits and _, not starting with a digit`), a reserved one (the names the
login shell and tmux keep, any `LADO_*`, and the names LADO sets for the agent CLIs:
`<NAME> is reserved: LADO or the agent CLIs set it`), a name with `TOKEN`, `KEY`, `SECRET` or
`PASSWORD` in it in any case (`<NAME> looks like a secret (<word>): … set it as a secret
with lado project set <id> <NAME> --secret`), a name that is a secret of the project (`<NAME>
is a secret of <id>; remove it first with lado project unset <id> <NAME>`), and a value over
64 KiB of UTF-8 or with a NUL; `lado project set <id> NAME` with no value and no `--secret`
is exit 1 too. `lado project set <id> NAME --secret` sets a secret of the project, stored
in its own file `<LADO_HOME>/projects/<id>/secrets/NAME` (the folders 700, the file 600,
written beside its name and renamed over it, so a reader finds the old value or the new
one whole) and never shown again; every agent of the project's sessions gets it as it gets
a plain variable. On a terminal it asks `Value of <NAME> (not shown): ` and reads one line
without echo; otherwise it reads the whole of stdin, one line break at its end (`\n` or
`\r\n`) dropped (`printf '%s' "$TOKEN" | lado project set shop GH_TOKEN --secret`); the
agents get the value so read whole, its own line breaks kept (its file holds one more when
it ends in one, as the reader drops one, so such a value counts a byte more against 64
KiB). It
prints `Set secret <NAME> in project <id>.` and the agents' line above. It refuses, exit 1,
storing nothing: a value on the command line, before it reads anything (`a secret's value
is never given on the command line (ps and the shell's history keep it); run lado project
set <id> <NAME> --secret and type it, or pipe it in`), an empty value, Ctrl-D at the prompt
too (`the secret <NAME> is empty; to remove it: lado project unset <id> <NAME>`), a name by the plain variables' name
rule above but for the secret's words (any other name may be a secret), a name that is a
plain variable of the project (`<NAME> is a plain variable of <id>; remove it first with
lado project unset <id> <NAME>`), a value over 64 KiB or with a NUL, an unknown project
(before it reads anything), and a symbolic link at `<LADO_HOME>/projects`, the project's
folder there, its `secrets` or the secret's file (`<path> is a symbolic link: LADO writes
and removes a project's secrets only in its own folders`); a write the disk refuses keeps
the old value (`could not write the secret <NAME> of <id>: <reason>`). No refusal holds the
value. `lado project unset <id> NAME` removes a plain variable or a secret with `Removed
<NAME> from project <id>.` and `Agents started from now on do not get it.`, or, while
sessions of the project run, `Agents started from now on do not get it; running sessions of
<id> keep the old environment until restarted: <names>`; a name the project lacks is exit 1
with `project <id> has no variable or secret <NAME>; its variables: <names>; its secrets:
<names>` (`none`), and a symbolic link on the way to a secret is refused as for `set`. `lado
project
rename <id> <title>` sets the title (`""` clears it); the id and the folder stay. `lado
project delete <id>` refuses, exit 1, changing nothing, while a session of the project, or
any session whose folder is inside the project folder (one started there before projects had
sessions; never through a project folder that is a link), is not stopped (`project <id> has
sessions not stopped: <names>; stop them first with lado stop <name>`); it prints the core's
preview, the one the UI shows: `Sessions to forget: <name> (<n> open run[s]), …` for the
project's stopped sessions and the stopped ones without a project in its folder (` (no
project)` after such one), then lists, under `Unpushed work in
<folder>:`, the folder itself when it is a repository's root (`the project's folder: …`,
first; the repositories in it are not its changes), each git repository directly in the
folder and each of its worktrees (one directly
in the folder once, under its repository) with uncommitted changes (untracked files too),
local branches with no upstream or ahead of it, as of the last fetch (LADO goes to no
network), `detached HEAD with <n> commit[s] on no branch` (commits no local or
remote-tracking branch holds) or `<n> stash[es]`, git's first line for a repository it
cannot read, and `the project's folder: could not check: <reason>` for a folder it cannot
list; `lado project repo remove` lists a repository's the same way. A project folder that
is a symbolic link lists nothing of its target. Without `--yes` it then refuses saying
what goes: `deleting project <id> removes its folder <folder> with everything in it`, for
a link `… removes the link <folder> only, not its target <target>`, for a folder not found
`… removes its record (its folder <folder> is not found)`, each followed by `[ and forgets
its <n> session[s]]; run again with --yes`. With `--yes` it removes the
folder whole, then forgets the project's sessions as `lado forget --force` does, then its
data folder `<LADO_HOME>/projects/<id>/` with its secrets, then the record (`Deleted project
<id>`): a folder that is a symbolic link loses the link only, nothing outside
`<workspace>/projects/` is removed, links inside are removed as links, a folder not removed
whole keeps the sessions and the record, and a session or a data folder not removed keeps
the record (run it again). A symbolic link on the way to the data folder or in it refuses
before anything is removed, naming the link. `lado project create` refuses an id whose data
folder `<LADO_HOME>/projects/<id>` is left from a failed deletion (`<path> is left from a
project <id>: remove it or choose another id`): a new project never inherits its secrets. A stopped session from before projects had sessions,
in the project's real folder, is forgotten with it; nothing in a link's target is. An
unknown id is exit 1 with `unknown project "<id>"`, also for a project deleted while `lado
project set` writes (no row and no secret file of it are kept). `create`, `rename`, `delete`, `set`, `unset`, `repo add` and `repo remove` are the
human's: inside an agent of LADO (`LADO_AGENT` set) they exit 1 with `lado project <command>
is for the human; agent "<agent>" cannot use it` (`set --secret` before it reads stdin),
while `list` and `show` work; no MCP tool changes projects, their repositories, their
variables or their secrets. `lado project` and `lado project repo` alone print their
help.

`lado project repo add <id> <git-url> [--name NAME] [--branch BRANCH]` clones the URL (its
default branch, or `BRANCH`) into `<workspace>/projects/<id>/<name>`, `<name>` being `NAME`
or the URL's repository name, as `lado start <git-url>` clones: `Cloning <which> of <url>
into <folder>` and git's progress on stderr, a hidden temporary folder beside the target
renamed only once git succeeded, Ctrl-C `lado: clone cancelled` (exit 130) and SIGTERM or
SIGHUP `lado: clone cancelled (<signal>)` (exit 128+n), leaving neither folder. `lado
project repo add <id> --new <name>` makes the folder a repository with one empty commit, as
`lado start --new` does (git's author checked first), and prints `Made <folder> a git
repository with an empty first commit`. Both then print `Added repository <name> to project
<id>: <folder>` and `Start a session in it: lado start --project <id> --repo <name>`. A
repository's name is 1 to 100 Latin letters, digits, `.`, `_` and `-`, not starting with `.`
or `-`, its case kept (`the repository name <name> is not valid: …`); a name any entry of
the project folder has is refused (`<folder> already exists in project <id>: choose another
name with --name`), as are an unknown project, a project whose folder is not found (`the
folder of project <id> is not found: <folder>`) and a URL that names no repository: exit 1,
nothing cloned or made. A URL with `--new`, neither, `--name` or `--branch` with `--new`,
and a source that is no git URL (a local path: give it as `file://<path>`) exit 2. An
empty `--name` is a name too, refused by the rule.

Both `repo add` and `repo remove` work only in the project's own folder: one that is a
symbolic link (to another project's folder, or anywhere), or whose real path is not
`<real projects/>/<id>`, is refused, exit 1, with `<folder> is a link or not where project
<id>'s folder belongs: LADO adds and removes repositories only in the project's own
folder`, nothing added or removed.

`lado project repo remove <id> <name> [--yes]` removes an entry of the project folder that
is a repository or a symbolic link. It refuses, exit 1, changing nothing, while any session
whose folder is inside the repository (one without a project too) is not stopped
(`repository <name> of project <id> has sessions not stopped: <names>; stop them first with
lado stop <name>`), an unknown project, a name no visible entry has (`project <id> has no
repository <name>; its repositories: <names>`, or the `no repositories yet` text), and an
entry that is neither (`<name> in project <id> is not a repository: LADO removes only
repositories and links`). It prints `Sessions to forget: …` for the stopped sessions in the
repository of the project and of none (from before projects, by their folder, each marked
` (no project)`; a session of another project never) and `Unpushed work in <folder>:` with
the repository's lines as `lado project delete` gives them, its workers' worktrees
included; without `--yes` it then
refuses (`removing repository <name> of project <id> deletes its folder <folder> with
everything in it[ and forgets its <n> session[s]]; run again with --yes`, or for a link
`removing <name> of project <id> deletes the link only, not its target <target>; run again
with --yes`). With `--yes` it removes the folder whole (links inside as links; refused when
its real path is not directly in the project folder's), then forgets those sessions as `lado forget --force` does, and prints
`Removed repository <name> from project <id>`; a link loses the link only (`Removed the
link <name> from project <id>`). A folder not removed whole keeps the sessions; a session not
forgotten is named with `lado forget <s> --force`. The project's record, its other entries
and sessions stay.

`lado start --project <id> --repo <name>` starts a session in the project's repository
`<name>` (one `lado project show` lists), named `<id>-<name>` without `--name`, and prints
`Started session "<session>" in <folder> (project <id>)`; the session refers to the project
in lado.db (`sessions.project`) and keeps it for good: a resume keeps it, a session its
supervisor starts with `start_session` is in the same project and repository, and a name a
session of another project or of none has is refused (`session "<s>" is in project <p>` or
`is not in a project`, `; a session's project never changes: give another name with
--name`). Its other options work as for a folder. An unknown project (`unknown project
"<id>"`), a name that is no repository (`project <id> has no repository <name>; its
repositories: <names>`, or `has no repositories yet: add one with lado project repo add <id>
<git-url> or --new <name>`) and a link (`<name> in project <id> is a link to <target>: clone it into <folder>
instead`) are exit 1. `--project` without `--repo`, `--repo` without `--project`, and
`--project` with a folder, a git URL, `--new`, `--branch` or a second folder exit 2.
While `<workspace>/projects/` is LADO's (a project's folder is in it), no new session
without a project starts inside it, by its real path, on any way: `lado start <folder>`
(a folder without git too), a clone, `--new`, the UI's folder, clone and fresh start, and
`start_session` from a session without a project. The refusal is exit 1 with the project
and its command: `<path> belongs to the project <title>: start a session in the project`
and `Start a session in the project: lado start --project <id> --repo <name>` when the path
is in the project's repository `<name>`; a clone or fresh start (the UI's folder check too)
aimed at a new folder `<workspace>/projects/<id>/<name>` with a good name gets `Add a
repository to the project: lado project repo add <id> <url>[ --name <name>]` or `… --new
<name>`; anything else, the project folder itself too, gets `See the project's
repositories: lado project show <id>`. For a
folder of no project, `<path> is in <workspace>/projects, which holds LADO's projects only:
start a session in a project, or move the folder out of projects/` with `See the projects:
lado project list`. A resume is never refused by it: a session started there before
projects had sessions keeps no project and resumes. `lado ls` prints `  project <id>` after
a session's folder.

`lado doctor` never migrates or writes lado.db (`cli.NOT_MIGRATING`). When lado.db is not at
this LADO's schema, a `lado.db` line follows the `LADO` line; at this schema, or with no
lado.db, there is none. Older with no session running: `info`, `schema <n>, this LADO knows
<m>: lado ls or lado start upgrades it (its backup goes to backups/)`. Older with sessions
running in tmux (those that keep `lado ls` from migrating, `runtime.migration_due`): a
warning, `schema <n>, this LADO knows <m>, and the sessions "<a>", … run on it`, with
`stop them with lado stop --all (it upgrades lado.db), then lado start`; when tmux cannot
run, a warning `schema <n>, this LADO knows <m>; the sessions running on it not checked:
<tmux's error>`, and the rest of the report follows. Newer: a warning
with the newer-LADO refusal's words; incompatible: `FAIL` with that refusal's words, and the
doctor exits 1. The checks that read lado.db (`Projects`, `Artifacts`, `Agent config
folders`) then say `not checked: lado.db is not at this LADO's schema (see lado.db)`.

`lado doctor` prints a login line after each installed agent CLI's version, read by the CLI's
own status command in the environment its agents get without a project, the login taken
whole from one layer (`claude auth status --json`, `codex login status -c
cli_auth_credentials_store="file"`, `opencode auth list`, `kilo auth list`; Codex's
`OPENAI_API_KEY`, which LADO hands its agents, without the command): `[ok] <CLI> login:
<how> · <where from>`, where from the layer that gives it (`LADO's secret`, `outside
folder`, `login shell`, `the process that starts LADO`) or the CLI's own login file
(`Claude Code's login file`, `Codex's login file`, or the file's path), e.g.
`[ok] Claude Code login: Subscription (token) · LADO's secret`; `[warn] Claude Code login: not logged in: new
sessions and workers of it are refused, a resumed agent waits (Settings → Providers and
environment)` for a CLI whose agents need one (Claude Code; Codex on OpenAI's models, its
default, by the model provider of the user's Codex config); `[warn] Codex CLI login: not
logged in: Your Codex keeps its login in the system keyring, which Codex agents cannot
read. …` when the user's Codex is logged in only there;
`[info] <CLI> login: none` for the others; `[warn] <CLI> login: unknown: <why>` when the
command fails, times out (10 s) or prints what LADO cannot read. None of them changes the exit
code. LADO's secrets (the login variables set in Settings, `<LADO_HOME>/secrets/`) get a line
after `Variables from outside` only when one takes the place of the outside folder's (`[info]
LADO secrets: <NAME>[, …] overrides LADO_ENV_DIR`) or a file there is not used (a warning, by
name with why, never a value).

A new session of a CLI that needs a login and has none, read in the environment its agents
would get (with the project's secrets for `--project`), is refused with exit 1 before
anything is stored: `lado: Claude Code is not logged in, so the session was not started: log
in in LADO's UI (Settings → Providers and environment, `lado ui`), or set
CLAUDE_CODE_OAUTH_TOKEN as LADO's secret or a project secret` (Codex: `lado: Codex CLI is
not logged in, so the session was not started: … or set OPENAI_API_KEY as LADO's secret or
a project secret`). `lado start <git-url>` and
`lado start --new` say so before the clone or the new folder when the provider is known
(`--provider`, or the only one installed). A supervisor's `spawn_worker` of such a CLI gets
`… so the worker was not started: ask the human to log in in Settings → Providers and
environment, or start the worker with another provider`; each worker is checked by its own
provider, so a Claude session's supervisor can still start Kilo workers. A resume by hand
(`lado start` of a stopped session) is refused the same way by the provider of the
supervisor it starts: `lado: Claude Code is not logged in, so the session was not resumed:
…`, the session stays stopped; `--provider kilo` resumes it with a Kilo supervisor. LADO's
own resume is not refused (at the container's start, and `lado update`'s, which runs
`lado start --wait-for-login`, a flag for LADO, not listed in `--help`): its Claude agent
waits, and `lado ls` prints under it `waiting: Claude Code is not
logged in: log in in Settings → Providers and environment, or set CLAUDE_CODE_OAUTH_TOKEN;
the agent starts by itself once you do`; it starts by itself once there is one. A login
that cannot be read refuses nothing and holds no agent: `lado start` warns `cannot tell
whether Claude Code is logged in: <why>; the agent starts all the same`.
There is no `lado login`: in a terminal the CLIs' own commands log in. Every Codex agent
shares the login of the user's own Codex (`codex login`, `codex login --device-auth`).

`lado doctor` always has a `Workspace` line: `<path> (LADO_REPOS)` or `<path> (default)`, `info`
with `, not made yet: the first clone or project makes it` while the folder is missing, and a
warning for a `LADO_REPOS` that is not absolute (ignored: `LADO uses <home>/workspace`), a path
that is not a folder, one LADO may not look at, or a folder it may not write in. Once LADO has
a project or `projects/` exists, a `Projects` line follows: `<n> in <workspace>/projects`, or a
warning naming projects whose folder is not found, foreign entries of `projects/` (no project's
folder) and a `projects/` that is the human's own folder. While a project's variable or
secret its agents get has the name of a variable the outside folder (`LADO_ENV_DIR`) gives, an `info` line
after `Variables from outside` names it: `Project variables: <id> overrides <NAME>[, …] of
LADO_ENV_DIR`, the projects by id joined by `; `, never a value; with no such name, or no
lado.db, there is no such line. When a file of a project's secrets folder is not given to
its agents, or the folder itself is not used, a warning follows: `Project secrets: <id>:
<name> not used: <reason>[; …]` (`<id>: secrets folder not used: …` for the folder), by
project and file name, never a value; the reasons are the outside folder's, and `a symbolic
link` and `readable or writable by others: chmod 600 it` (`chmod 700 it` for the folder),
as only LADO writes that folder. With every file usable there is no such line, and the
warning leaves the exit code 0.

`lado kits add <git-url>[@vX.Y.Z]` installs the kit of a repository (a row in lado.db; its
clone in the git cache): without a tag its latest release, with `--pre` its latest version
of all. A folder (read in place, the way to develop a kit) has no version. `lado kits add <kit>[@vX.Y.Z]
-m <marketplace>` takes the kit's address from that marketplace's list; without `-m` LADO
never looks in a marketplace. A kit not from the official marketplace or a folder shows
what would be installed (address, version, commit, MCP servers) and asks `Install? [y/N]`;
`--yes` skips the question, and without a terminal it is required. A kit whose latest
version needs a newer LADO is refused. `lado kits update <name> [vX.Y.Z]` moves a kit
installed from git to its latest or another version without asking, and warns on stderr
about the MCP servers the installed version did not start: running sessions build their
kits again at each spawn and run start, so only their new agents get it (the output says
so and names the running sessions that use it, `kits.update_line`); the old clone stays
in the cache. `lado kits outdated` checks each installed kit
against its remote's tags and says why it does not check a folder or a kit whose folder is
missing. `lado kits check <folder> --tag vX.Y.Z`
(a kit's CI) gives the verdict add would give for that tag without installing
(`kits.load_release`, shared with add), and fails on `kits.lint`'s problems (hardcoded
paths, the graph rules of `flows.lint`); `kits.warnings` are printed as `warning:` and do
not fail it (a flow step's role not in the kit, a role that acts in none of the kit's
flows, a version that differs from the clone's tags). A tag that points to another commit
than the installed one is a loud warning (outdated, update, add). `lado kits remove <name>`
drops the row; its folder stays (one already gone is no error); it warns on stderr about
the running and stopped sessions that use the kit (`runtime.kit_users`, the lines the UI
shows too). `lado kits` lists every kit
with its version and where it comes from (the marketplace it was added from, `removed` when
that marketplace is gone), and on stderr what to do with an older LADO's `LADO_HOME/kits`;
`lado kits show` names each kit's packs and where each agent's skills come from.
`lado marketplaces [list]`, `add <name> <git-url>`, `remove <name>`, `enable|disable
<name>` and `update [<name>]` manage the marketplaces; `official`
(github.com/ladohq/marketplace) is always there and can only be disabled. `remove` names
the installed kits from it, which stay. The UI's Kits page does all of this too.

`lado log <session>` shows what happened in a session: messages between agents (one line
with their delivery state and summary, the body indented below) and agent events (spawned,
status changes). `--agent NAME` keeps one agent's
lines, `-n N` the last N entries, `--follow` keeps printing new ones until Ctrl-C.
With `--follow` a message is printed once, with the state it had then; a later delivery
is not printed again.

`lado finish <session> <agent>` ends a worker whose branch is merged into the session repo's
current branch: it removes the worktree and branch, drops the agent from `lado ls` (its
messages and events stay in `lado log`, with a `finished` event), then closes the window (a
window already gone is fine, as for a worker that ended by itself; one that does not close
is an error that says the worker is finished and gives the `tmux kill-window` for it).
Messages it never got and bodies it never read are dropped, so a later worker of the same
name starts fresh. It refuses an unmerged branch or uncommitted changes; `--discard` ends
the worker anyway and throws that work away. "Merged" is LADO's own check against the
repo's current branch, the one gate: the branch then goes with `git branch -D`, as `-d`
would check a pushed branch against its upstream instead (`runtime.remove_work`, also a
run's end). A worktree or branch already gone (deleted by hand, an end that stopped half
way; `runtime.gone`) is no reason to refuse: the finish removes what is left and says
what was gone (`work_state`'s `gone`, the UI's Agents tab). With the branch gone, the work
is the worktree's HEAD (`runtime.tip`): commits there not in the current branch, or
uncommitted changes, are still refused without `--discard`. The supervisor does the same
with the MCP tool `finish_worker`. A worker of a flow run only has its window closed while
the run is open: the worktree and branch belong to the run; the run's end removes them by
the same rules, so a gone worktree or branch never keeps it from closing its workers.

`lado stop <session>` marks the session stopped, kills its tmux windows, then closes the
UI's terminals of its agents (their viewer sessions). A kill that fails leaves it marked
stopped: the error says its agents may still run and gives `tmux -L <socket> kill-session -t
<session>`, after which `lado start` resumes it (`lado stop` refuses a stopped session). Its history,
runs and gates stay, and so do worktrees and branches. Its agents are forgotten (their names
are free again; `lado log` keeps what they did), and messages they never got or whose body
they never read are dropped, with the count in the output: new agents start fresh.
`lado stop --all` stops every session not stopped yet (also one whose tmux or loop is gone),
prints each as soon as it is stopped and says which tmux socket it sees; one it cannot stop
does not keep the others running, and the error names it and the ones stopped (exit 1). On an older `lado.db` (a LADO upgraded by hand) this
LADO cannot mark a session stopped without migrating: `lado stop <session>` is refused,
with nothing changed, while another session runs, and points to `lado stop --all`;
otherwise the stop kills the tmux sessions, waits for their loops (one that does not end
stops it before the migration: run it again), migrates, then marks them stopped.
`lado ls` shows the session as `(stopped)` with its open runs and gates; `lado log` works
as before. `lado start` with the same name resumes it (also when
its tmux server died without `lado stop`): the repo must be the same, and `--kit`,
`--without`, `--provider` and `--permission-mode`, when given, replace the stored ones
(the output says what changed). The new supervisor starts with one message from `lado`,
`session resumed: <n> open runs`, whose body says per open run what waits: the human at a
gate (answer with `lado answer`), the supervisor's own step (its step message follows), or a
worker to start with `spawn_worker(run=...)`. Such a worker opens in the run's worktree on
its branch, made again from the branch if the folder is gone. An open run that needs a role
the resumed session lacks is reported on stderr and in that body; `flow_cancel` or
`lado flow-set` move it on. While a session is stopped, nothing starts or moves in it:
`lado answer`, `lado flow-set`, spawning workers and starting, advancing or cancelling runs
are refused (`runtime.running_session`); `lado answer` with no session skips its gates.
`spawn_worker` needs `role` unless the session has one worker role (`Environment.role`);
the lead's instructions say which, and list each role and flow with its kit.
`lado start` (also a resume) prints who leads (`lead: ...`) and, on stderr, how each kit
supervisor that does not lead is used (its lead skill, the MCP servers the lead does not
get, a supervisor that lists no skills).
When LADO's built-in supervisor leads, each kit supervisor that does not lead (but the
default kit's) gives it a skill `lead-<kit>` (`runtime._write_lead_skills`, at each start
and resume, once the session is taken): in the lead's config folder,
`lead-skills/lead-<kit>/SKILL.md` holds that supervisor's prompt and the paths of the
skills its `skills:` names, copied (links followed) into `lead-files/<kit>/<skill>/` in
that kit's versions. `lead-files` is no skills folder of any CLI (Kilo and OpenCode find
SKILL.md at any depth under their skill paths) but `AgentSpec.read`; the lead's instructions name the
kits with a lead skill.
A worker started without a name (`spawn_worker`, also for a run) is named after its role,
made valid like a given name (`slug`: `Code Reviewer` gives `code-reviewer`): `developer`,
or `developer-2`, `developer-3`… when that is taken. A name is taken by a running agent of
that name or a branch `lado/<session>/<name>` still there (from a stopped launch or a
worker not finished); `human`, `lado` and `supervisor` are never chosen. A given name wins
and is checked as before.
`lado forget <session>` deletes a stopped session with its history and its artifacts (the
store's `remove_session` first, which also removes content files no record refers to that
are more than an hour old; the output counts the artifacts); it refuses a running one, and
one with open runs unless `--force`; worktrees and branches stay on disk and are listed.

`lado title <session>` prints a session's title (or `<session> has no title`); `lado title
<session> TEXT` sets it and `--clear` clears it (both together exit 2), through
`runtime.set_title`, printing `<session>: title "<title>"` or that it has none; for a
running or stopped session alike, the name and everything named by it unchanged. A title
with a hidden character (a line break, a tab, a line separator, a bidi control, a
zero-width space; `text.py`) is refused naming it (`a title is one line of visible text:
U+202E RIGHT-TO-LEFT OVERRIDE is not allowed`). Setting
or clearing is refused inside an agent (`LADO_AGENT` set), as `lado answer` is; reading is
not. `lado ls` prints the title, quoted, after the name; each agent's line has its name,
role, provider, status, for how long, the model it runs on (`-` while its CLI has named
none; docs/design/agents.md), then a worker's branch. The UI sets it too (the pencil in
the session's head, Rename… in the list; docs/design/ui.md, Session title). A title is
never set at the start and by no MCP tool.

`lado uninstall [--dry-run] [--keep-data] [--yes]` removes LADO (`uninstall.py`): it prints
its plan and asks `Uninstall? [y/N]` (`--yes` is required without a terminal; `--dry-run`
only prints), then stops the UI server and every session of this `LADO_HOME` with their
loops and viewers, waits up to 10 s for the agents' processes to end (an agent may run its
session-end hook first; one still running stops the uninstall with exit 1 before any
repository or file is touched, naming its session, its pid and `kill <pid>`, after which
`lado uninstall` runs again), ends LADO's tmux server when no other session is on its socket, removes
in each session's repository the worktrees and branches `lado finish` would remove without
asking and lists the others with their `git worktree remove --force` and `git branch -D`,
deletes `LADO_HOME`, and, only for the default `~/.lado`, removes the program last (`uv
tool uninstall lado`, `pipx uninstall lado<suffix>`). With another `LADO_HOME` the program
stays and its command is printed. Refused inside an agent, while `lado update` runs and on
a newer `lado.db`. `--keep-data` keeps `LADO_HOME` and the repositories, so a LADO installed
again resumes the sessions. The agent CLIs' own records of the folders stay
(docs/install.md, Uninstall).

Supervisor-started sessions: the supervisor proposes a new, independent session for a
problem it found or a new ticket by `ask_human` with the brief attached and the choice
`runtime.START_CHOICE` (`Start session <name>`, the one spelling, also in its
instructions); once the human picks it in the UI, its MCP tool `start_session(name,
question)` (`runtime.start_approved_session`) checks that the question is the calling
supervisor's of its session, answered with exactly that choice, and carries at least one
attachment (no two of one name), and starts the session with `resume=False` (a taken name
is `SessionExists`, so one approval starts one session) in the caller's repo with its kits,
provider, permission mode and without. Each attachment is copied into the new session's
scope (author `lado`, the summary naming where it came from), and its supervisor's first
message from `lado` carries them with the question, each artifact's author and the human's
comment; the brief never goes on argv or into the role. Nothing is stored for a proposal:
an unanswered one dies with its session's stop (its questions close); an answer stays
valid for a resumed supervisor, and after `lado forget <name>` it can start the session
again. The new session reports nothing back.

`lado artifacts list <session> [--run RUN]`, `lado artifacts show <session> <full-name>`
and `lado artifacts get <session> <full-name> [-o FILE]` list a session's artifacts, print
a text one and write one's bytes, also for a stopped session (docs/design/artifacts.md, The
human's side). `lado doctor` shows the store's size and warns about content no record
refers to that is older than an hour (the next `lado forget` removes it).

`lado telemetry [status]` says whether LADO sends anonymous usage statistics and its errors
to its maintainers, why not, and when it last sent (`telemetry.status_lines`); `lado
telemetry on|off` keeps the human's choice (refused inside an agent; `off` drops what is
queued), `lado telemetry show` prints the next daily report and the queued errors as the
sender posts them (no token); `lado telemetry send` (hidden) is the detached sender. None of
them migrates lado.db. `lado start` and `lado ui` ask once on a terminal before their work
(`telemetry.ask_if_needed`; Enter is off, EOF or Ctrl-C keeps no choice). What is sent and
where: docs/telemetry.md; how: `telemetry.py` (docs/design/modules.md).

`lado stats [--days N | --all]` prints how LADO was used on this machine in the last 30
days (`--days N`: N days, `--all`: everything kept; both, or an N that is no positive whole
number, exit 2), from lado.db's `usage` table (`state.py`, schema 27) and LADO's error
journal: sessions started and resumed; agents started per agent CLI and per role
(`<role>@<kit>`, `@?` for one spawned before 0.38.0, with a note), agents ended by
themselves, turn errors per CLI and kind; flow runs started per flow, ended, cancelled;
gates opened per kind, closed per answer, and how many of the human's answers with a
recommended choice took it (a cancelled or overridden gate is closed, never in that); questions to the human; messages failed and dropped; LADO's own errors. A
breakdown lists the larger first, then by name, and wraps under itself. The first line
names the period in UTC and says nothing is sent; `Earliest record:` follows with `--all`
or when the earliest row is later than the period's start. It reads only, opens no
connection and starts no statistics sender (`cli.main` does not kick after it); it
migrates lado.db as `lado ls` does.

`lado ui` prints (or opens) the local link with the token, then, when the running server
has a link for another device, `From another machine: <link>`: it asks the server
(`GET /api/access` with the token, `run.access`), so `LADO_PUBLIC_HOST` and, in a
container, `LADO_LISTEN` of the server's environment decide, not the shell's; a server that
does not answer it (an older one) gets no such line. In a container with `--no-open` that
line goes to stderr, so stdout stays the one local link. The rule for the link:
docs/design/ui.md, Server, Host.

`lado bug-report` prints a warning (the issue is public, nothing is sent until the human
submits GitHub's form, a vulnerability goes to private reporting), the bug report and
`Open a new issue: <link>` (`bug_report.build`; docs/design/modules.md); then, only when stdin and stdout
are terminals and a browser can show (`bug_report.can_show_browser`), asks `Open it in the
browser? [y/N]`: `y` runs `webbrowser.open`, one that fails prints `could not open a
browser: open the link above`, anything else (Enter, EOF, Ctrl-C) opens nothing; exit 0.
It does not migrate lado.db (a newer one is reported as it is) and is refused nowhere,
also not inside an agent. Its `Server:` line says `not running` or `running, loopback
only` / `open to the network` by the running server's `server.json`. The UI's Report a bug
page shows the same report (docs/design/ui.md, Report a bug).

Gates: a run that enters a gate state, or would enter a state more often than its
`max_visits`, waits for the human with an open gate (`lado ls`: `gate #<id> waiting:
<question>`). An approval gate has exactly the outcomes `approved` and `rejected` and is
answered `approve` / `reject`; a choice gate with one of its outcome names; a loop limit with
`continue` (enter the state anyway, the visit counts) or `cancel` (cancel the run). The
supervisor gets LADO's request for its recommendation, `recommend on gate #<id>: <run> at
<state>` (docs/design/agents.md; in its own `flow_advance`'s `notices` when its move opened the
gate). The answer and its comment become the next step's note, after which the note that led to the gate
follows in the body; when a worker gets the next step, the supervisor gets one line
`flow <run>: human answered <option> at <state>`.

A step's text (`runs.step_text`) has the task, the step's `do` (with `This step must
write: ...`, the `produces` names as its agent writes them, bare for a run's worker and
`<run>/<name>` for the lead), then the previous step's note with its artifacts, then
`Artifacts this step reads (read each with read_artifact):`, a line per name in its `reads`
with the artifact's latest record (`- <name>: <title> — <summary>`, named as its agent
writes it; `no record yet`; never the content), then on a later visit of the state
`Your artifacts so far` of its own `produces` that have a record, then the outcomes. A
record attached to the previous step's note is named only there. The records are read when
the step is told, so `lado flow-set` keeps them: a run set to `implement` with
`reads: [design]` is shown the latest design, and the flow-set reason is the previous
step's note. A human's comment at a gate reaches the next step only (its note).

`lado answer <session> <gate-id|run> <option> [-m COMMENT]` answers a gate. Without the
option it asks: with no arguments about the open gates of all sessions (a list to pick from
when there are several), and after each answer it goes on with the open gates of that session
until none is left or the human presses Enter on an empty line. It shows the question, the
one-line summary of the note that led to the gate with its artifacts, the supervisor's
recommendation (`Supervisor recommends: <option>`, or `Supervisor's recommendation:`
without one, ` (disagrees with <agent>)`, its first line; `Supervisor is preparing a
recommendation…` while asked, `The supervisor gave no recommendation.` when missing;
`cli._recommendation_lines`), then under
`Artifacts it reads:` a line per artifact of the gate state's `reads` but those the note
carries (`runs.gate_reads`: `<run>/<name>: <title> — <summary>` of its latest record, or
`no record yet`), and the numbered options, the recommended one marked `← supervisor
recommends`; when the note has a body or an artifact, the gate reads one, or a
recommendation is asked or given, `v` shows the whole text in `less -R` (printed when there
is no `less`): the note, the recommendation in full, each of its artifacts as attached,
then each artifact the gate reads as of its latest
record (a text one's content, else its type and size); then it asks again. The records and
the gate are read at each show, also after `v`: a write while the gate is open shows, and
the human approves the latest. A loop limit reads none. A gate whose run's flow cannot be read is
shown with its problem and left open (the supervisor's `flow_cancel` moves it), and
`lado answer` goes on with the other gates. When a gate opens, LADO opens a tmux popup (`display-popup -E`, titled
`LADO: waiting for you (session <name>)`, a rounded soft orange border around the
terminal's own colours from tmux 3.3 on, tmux's plain border on 3.2, none before 3.2;
`lado doctor` warns about both) running `lado answer <session> <gate-id>` on each client
attached to the session; with no client attached, nothing opens and the gate waits in
`lado ls`. tmux does not stack popups: a second gate is asked about in the open popup after
the first answer. Closing the popup leaves the gate open. `lado answer` and `lado flow-set`
refuse to run inside an agent (`LADO_AGENT` set).

A gate is answered with `lado answer`, the popup, or the UI server's API (the gate's card in
the session's chat; docs/design/ui.md, Flow gates); all go through `runs.answer`, and
`runs.answer_text` is the one line that says what the answer did. Two answers at once: the
second is refused (`closed already`). While `lado answer` waits for the human on a terminal
(the option, the comment), it checks every second (`cli.POLL`) that the gate is still open;
when it was answered elsewhere, it drops what was typed (`tcflush`), prints `Gate #<id> was
answered elsewhere: <answer> by <who>` and goes on with the session's open gates, or ends
with `No more open gates.`, which closes the popup. Without a terminal (a pipe) it does not
check.

Flow tools return short results: the run, flow, state, status, who acts, outcomes, the
artifacts the step `produces` (full names), gate, visits, the note's summary and the run's language; `flow_status(run=...)` adds the task,
reason, worktree and branch. What the supervisor's own `flow_start` or `flow_advance`
causes (a step that needs a worker, a gate, the run's end) comes back in the result's
`notices` instead of as a message; what others cause (a worker's advance, the human's
answer) still comes as a message. A "step <x> needs a <role>" message still waiting in the
queue is dropped when that worker is spawned for the run. `flow_start(human_language=...)`
stores the human's language with the run (e.g. `ru`), and every step message asks for
`note_summary` and `note_body` in it, since the human reads them at gates; the flow's gate
questions stay as written.

`lado flow-set <session> <run> <state> --reason TEXT` puts a flow run into a state: the
human's override, past a gate or a loop limit; it closes the run's open gate as `overridden`.
`lado ls` shows each open run with its state and who acts next.
A run whose flow snapshot cannot be read (`runs.SnapshotError`) is shown with its problem
and the rest goes on: `lado ls` prints the reason instead of who acts or the gate it waits at, `flow_status` gives
it `problem` and no outcomes, a resume reports it on stderr and in the `session resumed`
body; only `flow_cancel` moves it (advancing, answering and `lado flow-set` refuse with
the error), and who acts without the flow is `runs.acting_or_problem`, for the core and
the UI alike.
