# Installing LADO

LADO runs on macOS and Linux. On Windows it runs inside WSL2, in Ubuntu, exactly as on
Linux; native Windows is refused with a pointer to WSL2.

What LADO needs on every system:

- **tmux** (3.3 or newer for the best experience; 3.2 works, see
  [tmux older than 3.3](#lado-doctor-warns-about-tmux-older-than-33)),
- **git** (2.31 or newer, see [git older than 2.31](#lado-doctor-warns-about-git-older-than-231)),
- **[uv](https://docs.astral.sh/uv/)**, which installs LADO and the Python it runs on,
- **one agent CLI**: Claude Code, Codex, Kilo or OpenCode, logged in once.

`lado doctor` checks tmux, git and the agent CLIs and prints the command to install what is
missing. The short version of this guide is in [README.md](../README.md#install).

- [macOS](#macos)
- [Linux](#linux)
- [Windows](#windows)
- [Agent CLIs](#agent-clis)
- [Your first session](#your-first-session)
- [Update](#update)
- [Uninstall](#uninstall)
- [Common problems](#common-problems)

## macOS

### Prerequisites

[Homebrew](https://brew.sh). git comes with the Xcode command line tools
(`xcode-select --install`) or from Homebrew (`brew install git`).

### Steps

1. Install tmux and uv, then LADO:

   ```bash
   brew install tmux uv
   uv tool install lado
   ```

2. Install an agent CLI and log in to it once: [Agent CLIs](#agent-clis). Codex, Kilo and
   OpenCode install with npm, which comes with Node.js: `brew install node`.
3. Check:

   ```bash
   lado doctor
   ```

   It ends with `All checks passed.` when LADO can start a session.
4. Start a session: [Your first session](#your-first-session).

### If something goes wrong

- `lado: command not found` after `uv tool install lado`: uv's tool folder is not on your
  `PATH`. Run `uv tool update-shell` and open a new terminal.
- See also [Common problems](#common-problems).

## Linux

These steps are for Debian and Ubuntu (apt). They are also the steps inside Ubuntu on
Windows: the [Windows](#windows) section refers to them.

### Prerequisites

A user that can run `sudo`.

### Steps

1. Install git, tmux and curl:

   ```bash
   sudo apt update && sudo apt install -y git tmux curl
   ```

2. Install Node.js 22 from NodeSource, for the agent CLIs from npm (Codex, Kilo,
   OpenCode):

   ```bash
   curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash -
   sudo apt install -y nodejs
   ```

3. Install uv, then LADO:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   source ~/.local/bin/env
   uv tool install lado
   ```

   `source ~/.local/bin/env` puts uv on the `PATH` of this terminal; new terminals get it
   from your shell's startup file, which uv's installer changed.
4. Install an agent CLI, e.g. Kilo, and log in to it once ([Agent CLIs](#agent-clis)):

   ```bash
   npm install -g --prefix ~/.local @kilocode/cli
   ```

5. Check:

   ```bash
   lado doctor
   ```

   It ends with `All checks passed.` when LADO can start a session.
6. Start a session: [Your first session](#your-first-session).

### If something goes wrong

- `sudo apt install -y nodejs` fails with `trying to overwrite
  '/usr/include/node/common.gypi'`: an older Ubuntu (22.04) has Ubuntu's own Node 12
  installed. Remove it, then install again:

  ```bash
  sudo apt remove -y libnode-dev libnode72
  sudo apt install -y nodejs
  ```

- `npm install -g` without `--prefix` fails with a permission error (`EACCES`): the system
  Node installs global packages into a folder only root can write. Use
  `--prefix ~/.local`, as above, instead of `sudo`.
- See also [Common problems](#common-problems).

## Windows

LADO runs inside WSL2, in Ubuntu. An agent CLI installed on Windows itself does not count:
install it inside Ubuntu, as below.

### Prerequisites

Windows 10 or 11 with WSL2 available, and an account that can run cmd as administrator.

### Steps

1. Install Ubuntu. Open **cmd as administrator** (Start → type `cmd` → right click → Run
   as administrator) and run:

   ```
   wsl --install -d Ubuntu-24.04
   ```

   Restart if Windows asks. Ubuntu's window then asks for a user name (Latin letters) and
   a password; the password is for `sudo`. Later, open Ubuntu with `wsl` in cmd or
   "Ubuntu" in the Start menu.
2. In Ubuntu, do the [Linux steps](#steps-1) 1 to 4: git, tmux and curl from apt,
   Node.js 22 (for CLIs from npm), uv and LADO, and an agent CLI with
   `npm install -g --prefix ~/.local` (Kilo there, or another one).
3. Run `lado doctor` (it ends with `All checks passed.`), then `kilo` once to log in and
   pick a model (or your CLI's login, [Agent CLIs](#agent-clis)), then start a session in
   a git repository inside Ubuntu: [Your first session](#your-first-session). Later
   updates: `lado update` ([Update](#update)).

### If something goes wrong

- `sudo apt install -y nodejs` fails with `trying to overwrite
  '/usr/include/node/common.gypi'`: see [Linux](#if-something-goes-wrong-1).
- `lado doctor` does not see an agent CLI you installed on Windows (npm in cmd or
  PowerShell, `AppData\Roaming\npm`): by design. A Windows CLI does not work inside Ubuntu,
  and LADO does not pass the Windows `PATH` to agents (`lado doctor` says so: `Windows
  PATH: not passed to agents`). Install the CLI inside Ubuntu.
- `lado doctor` warns about tmux older than 3.3: see
  [Common problems](#lado-doctor-warns-about-tmux-older-than-33).
- See also [Common problems](#common-problems).

## Agent CLIs

Install one (or more) and log in to it once by starting it in a terminal. These are the
commands `lado doctor` prints for a missing CLI:

| CLI         | Install                                                          | Command    |
|-------------|------------------------------------------------------------------|------------|
| Claude Code | see [its docs](https://docs.anthropic.com/en/docs/claude-code)   | `claude`   |
| Codex       | `npm install -g @openai/codex`                                   | `codex`    |
| Kilo        | `npm install -g @kilocode/cli`                                   | `kilo`     |
| OpenCode    | `npm install -g opencode-ai`                                     | `opencode` |

On Linux and in WSL, with Node.js from apt, add `--prefix ~/.local` to `npm install -g`
(e.g. `npm install -g --prefix ~/.local @openai/codex`): a global install into the system
Node's folder needs `sudo`, and `~/.local/bin` is already on your `PATH` (uv's installer
uses it too). On macOS with Node from Homebrew, `npm install -g` works as is.

`lado doctor` warns when a CLI's version is not the one LADO is tested with: agent status
and message delivery may break with another version.

## Your first session

LADO works on a git repository with at least one commit:

```bash
cd ~/my-project
lado start .            # a supervisor in tmux; --provider NAME picks the agent CLI
lado ui                 # the web UI in your browser
```

A new folder needs `git init` and a first commit before `lado start`.
`lado start --help` lists the options; `lado update` installs a newer LADO later
([Update](#update)).

## Update

`lado update` installs the latest LADO, `lado update X.Y.Z` another version. The web UI
does the same: click `live` in the top bar, then **Update…** and **Restart and update**.

### What it does

1. It shows its plan (the version you have and the one it installs, the installer's
   command, the sessions and the UI server it restarts) and asks `Update? [y/N]`. The web
   UI shows the same plan in its window.
2. It stops your running sessions and the UI server.
3. It backs up `lado.db` to `~/.lado/backups/` (one backup, of the version before).
4. It installs exactly that version with the installer LADO came with:
   `uv tool install lado==X.Y.Z`, or `pipx install --force lado==X.Y.Z`.
5. It checks that the installed `lado --version` is that version.
6. It starts the sessions and the UI server again, on the new version.

`--yes` skips the question. Without a terminal (in a script) it is required: there
`lado update` refuses to go on without it. What happens to your sessions' work:
[README](../README.md#update).

### When something goes wrong

- The new version reports another version than the one asked for, or the UI server does
  not come up on it: LADO rolls back. It stops what the new version started, installs
  the old version again and starts your sessions on it. It restores `lado.db` from the
  backup only when the new version changed its schema.
- The installer fails: nothing changed; the sessions start again on the old version.
- Everything the update said and every command it ran, with their output, is in
  `~/.lado/update.log`.
- An update that stops half way leaves sessions stopped: `lado ls` names them, with the
  `lado start` that resumes each.

### Going back to an older version

`lado update 0.20.0` installs an older version the same way, as far as that version
accepts your database: an older LADO refuses a newer `lado.db` and says so when it starts.

### The check for a newer version

`lado ls`, `lado doctor` and the web UI look on PyPI at most once a day and say
`LADO X.Y.Z is available: lado update` (the web UI: `↑ X.Y.Z` next to `live`).
`LADO_NO_UPDATE_CHECK=1` in your environment switches the check off.

### Installed otherwise

LADO updates itself only when it was installed from PyPI with `uv tool install lado` or
`pipx install lado`. Installed with pip (e.g. in a virtual environment), from a working
copy or from a git address (also through uv tool or pipx), `lado update` and the web UI
show the commands to run by hand instead: stop the sessions and the UI server, install
the version with that environment's `pip install lado==X.Y.Z`, then start them again.

## Uninstall

```bash
lado uninstall --dry-run    # what it would do; changes nothing
lado uninstall              # shows the same plan and asks Uninstall? [y/N]
```

`--yes` skips the question; without a terminal (in a script) it is required.

### What it does

1. It stops the UI server and every session of this `LADO_HOME` (as `lado stop --all`),
   waits for their session loops and closes the web UI's terminals. LADO's tmux server
   ends with its last session; when sessions of another `LADO_HOME` run on the same tmux
   socket, it stays and the output names them.
2. In each repository a session ran in, it removes the worktrees under
   `.lado/worktrees/<session>/` and the branches `lado/<session>/*` that `lado finish`
   would remove without asking: merged into the repository's current branch, nothing
   uncommitted. It keeps every other one and prints the commands that remove it:

   ```bash
   git -C <repo> worktree remove --force <worktree>
   git -C <repo> branch -D <branch>
   ```

   Once no worktree is left, `.lado/worktrees` and its line `/.lado/worktrees/` in
   `.git/info/exclude` go too. Your project's own files in `.lado/` (e.g. `sdlc.md`) stay.
   A repository that is gone is named and passed over.
3. It deletes `~/.lado`: the history, artifacts, installed kits and their git cache,
   backups and logs.
4. Last, it removes the program with the tool that installed it: `uv tool uninstall lado`
   or `pipx uninstall lado`. Installed with pip or run from a working copy, the program
   stays and the output says where it runs from.

`--keep-data` stops everything and removes the program, but keeps `~/.lado` and the
repositories as they are: install LADO again and `lado start <repo> --name <session>`
resumes a session with its runs and history.

With another `LADO_HOME` (`LADO_HOME=/tmp/try lado uninstall`), it stops that folder's
sessions, cleans their repositories and deletes that folder; `~/.lado` and the program
stay, since `~/.lado` may still use it, and the output prints the command that removes
the program. It never deletes `/`, your home folder or a folder above it, nor a folder
without `lado.db` that is not `~/.lado`.

It refuses, changing nothing: inside an agent, while `lado update` runs, and when
`lado.db` was made by a newer LADO (uninstall with that LADO, or by hand below). An older
`lado.db` is upgraded as `lado stop --all` upgrades it.

### What stays

- Worktrees and branches with work that is not merged, listed with their commands.
- Repositories `lado start <git-url>` cloned into `~/lado/`: they are yours.
- tmux, uv, git and the agent CLIs.
- The agent CLIs' own records of the folders they ran in. LADO never writes to them, and
  removes nothing there:
  - Claude Code: the folder's entry in `~/.claude.json` (`projects`, with the trust you
    gave it; so a LADO installed again is not asked again) and its conversations in
    `~/.claude/projects/`.
  - Codex: nothing of LADO's agents; their Codex home was LADO's own, under `~/.lado`.
  - OpenCode and Kilo: their sessions in their data folders, `~/.local/share/opencode/`
    and `~/.local/share/kilo/`.

### By hand

For a LADO before 0.37 (no `lado uninstall`) or one installed with pip:

```bash
lado stop --all
lado server stop
sqlite3 ~/.lado/lado.db 'SELECT DISTINCT repo FROM sessions'   # the repositories
```

In each repository: `git worktree list` and `git branch --list 'lado/*'`; remove each
worktree under `.lado/worktrees/` and its branch whose work you do not need
(`git worktree remove <path>`, `git branch -D <branch>`), then the line
`/.lado/worktrees/` from `.git/info/exclude`. Then:

```bash
rm -rf ~/.lado
uv tool uninstall lado      # or: pipx uninstall lado, or pip uninstall lado
```

### Testing an upgrade as a new user meets it

```bash
lado uninstall --yes            # the machine as a new user's, but the agent CLIs' records
uv tool install lado==0.36.0    # the release users have
lado start ~/work/app           # use it as a user would
lado update                     # the upgrade under test
```

## Common problems

### `lado doctor` warns about tmux older than 3.3

Ubuntu 22.04 has tmux 3.2a. LADO works; gate popups have no coloured border. Ubuntu 24.04
has a newer tmux. Before 3.2 there are no gate popups (gates show only in `lado ls`) and no
agent terminals in the web UI.

### `git is not installed or not on PATH`

LADO runs git itself (`lado start`, the UI's New session window, `lado kits add`), on the
`PATH` of the terminal or of the server you started it from. On macOS install the Xcode
command line tools, `xcode-select --install` (or `brew install git`); on Linux and WSL
`sudo apt install git` (or your distribution's package manager). Then run `lado doctor`
again: its `git` line names the version it found.

### `git does not run: xcrun: error: invalid active developer path`

On a Mac without the Xcode command line tools, `/usr/bin/git` is only a stub that asks for
them. Run `xcode-select --install`, then `lado doctor` again. Before LADO 0.36 this showed
as "not inside a git repository".

### `lado doctor` warns about git older than 2.31

LADO works, but its look at whether an agent CLI trusts the folder (`git rev-parse
--path-format=absolute`) needs git 2.31: with an older git LADO may not foresee a CLI's
"trust this folder?" question, or expect one that does not come. Install a newer git.

### `Agent CLI: no agent CLI installed`

No agent CLI is on the `PATH` of the terminal you ran `lado doctor` in, which is where it
looks. Install one ([Agent CLIs](#agent-clis)), open a new terminal and run `lado doctor`
again. LADO starts agents with the `PATH` of your login shell, so a CLI that works in one
terminal but not for LADO is usually added to `PATH` only in a file your login shell does
not read; `lado doctor`'s `Agent environment` line says where LADO's `PATH` comes from.

### Without uv

`pip install lado` (Python 3.10 or newer) installs LADO too, e.g. into a virtual
environment. `lado update` then only prints the commands to run by hand
([Installed otherwise](#installed-otherwise)).
