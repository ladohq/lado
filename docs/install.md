# Installing LADO

LADO runs on macOS and Linux. On Windows it runs inside WSL2, in Ubuntu, exactly as on
Linux; native Windows is refused with a pointer to WSL2.

What LADO needs on every system:

- **tmux** (3.3 or newer for the best experience; 3.2 works, see
  [tmux older than 3.3](#lado-doctor-warns-about-tmux-older-than-33)),
- **git**,
- **[uv](https://docs.astral.sh/uv/)**, which installs LADO and the Python it runs on,
- **one agent CLI**: Claude Code, Codex, Kilo or OpenCode, logged in once.

`lado doctor` checks tmux and the agent CLIs and prints the command to install what is
missing. The short version of this guide is in [README.md](../README.md#install).

- [macOS](#macos)
- [Linux](#linux)
- [Windows](#windows)
- [Agent CLIs](#agent-clis)
- [Your first session](#your-first-session)

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
   updates: `lado update`.

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
`lado start --help` lists the options; `lado update` installs a newer LADO later.

## Common problems

### `lado doctor` warns about tmux older than 3.3

Ubuntu 22.04 has tmux 3.2a. LADO works; gate popups have no coloured border. Ubuntu 24.04
has a newer tmux. Before 3.2 there are no gate popups (gates show only in `lado ls`) and no
agent terminals in the web UI.

### `Agent CLI: no agent CLI installed`

No agent CLI is on the `PATH` of your login shell, which is where LADO looks. Install one
([Agent CLIs](#agent-clis)), open a new terminal and run `lado doctor` again. A CLI that
works in one terminal but not for LADO is usually added to `PATH` only in a file your
login shell does not read; `lado doctor`'s `Agent environment` line says where LADO's
`PATH` comes from.

### Without uv

`pip install lado` (Python 3.10 or newer) installs LADO too, e.g. into a virtual
environment. `lado update` then only prints the commands to run by hand.
