## Context

All agents of a machine run as one user with one `/tmp`, and LADO sets no `TMPDIR` for them
(proposal, Why). The fix is a folder per agent, made by the core at each launch, given as
`TMPDIR` to every provider and as `CLAUDE_CODE_TMPDIR` to Claude Code, and a line in every
agent's instructions.

## Decisions

### D1. The folder: `<parent>/lado-<uid>/<session>/<agent>`

`<parent>` is `TMPDIR` of the agent's merged layers (`agent_env.merge`: login shell, outside
folder, project), else `/tmp`; `<uid>` is `os.getuid()`. The path is readable (a human finds an
agent's files by its names) and short enough for Claude Code's own subfolder
(`<folder>/claude-<uid>`) on Linux and on macOS, whose default `TMPDIR` is already the user's
own `/var/folders/…/T/`. `lado-<uid>` keeps users of a shared host apart, as tmux's
`tmux-<uid>` does.

Why not under `LADO_HOME/agents/<session>/<agent>` (the config folder): that folder is written
anew and removed at a stop, and in the container it is the home volume, which outlives the
temporary files' purpose; `/tmp` is where tools and the system expect them and clean them.

### D2. Made safely at each launch

At each launch the core makes `lado-<uid>`, the session's and the agent's folders when missing,
each with mode 0700, and checks `lado-<uid>`: a real folder (not a link), owned by the user;
it sets its mode to 0700. Anything else refuses the launch with one line naming the path and
why (`<path> is a link`, `<path> belongs to uid 501`), before the agent's window opens
(No silent drops; a folder another user made in `/tmp` must not receive the agents' files).
The folder made, it is put in `AgentSpec.temp_dir`, so the provider sees it.

### D3. `TMPDIR` is set by the core, for every provider

`_launch_env` puts `TMPDIR=<folder>` among LADO's own variables (`ours`), so it wins over every
layer and is named in `LADO_LAUNCH_VARS`: a worker that an agent's `lado mcp` launches does not
nest its folder inside its spawner's. Both sources drop it: `LADO_AGENT_ENV=inherit` by
`without_launch`, and the login shell, which `agent_env.from_shell` starts from the caller's
variables without those of its launch (found in review: it took the spawner's `TMPDIR` among
`SHELL_BASE`). That worker's parent is then the `TMPDIR` its shell's startup files export,
else `/tmp`, not the user's own `TMPDIR` the spawner had (macOS's `/var/folders/…/T/` comes
from the login session, not from the startup files); accepted: the folders still differ.
Each CLI honours `TMPDIR` for its own and its commands' temporary files: Claude Code, Kilo and
OpenCode through Node's `os.tmpdir()`, Codex through Rust's `std::env::temp_dir()` and the
variables it hands its MCP servers (`TMPDIR` among them, `providers/codex.py`). Codex's sandbox
(workspace-write and LADO's profile) keeps `TMPDIR` writable, as it does `/tmp`; the build checks
it by hand on macOS, where Codex keeps its sandbox.

### D4. Claude Code also gets `CLAUDE_CODE_TMPDIR`

Claude Code takes its own temporary root, where its scratchpad and its tools' files are, from
`CLAUDE_CODE_TMPDIR` (else `/tmp/claude`), not from `TMPDIR`. `providers/claude.py` adds
`CLAUDE_CODE_TMPDIR=<spec.temp_dir>` to its `Launch.env`. A provider detail stays in
`providers/` (Neutral core); the other three need nothing of their own.

### D5. Lifetime: an agent's state

The folder is not removed at a stop: a resumed agent finds its files. It is removed where LADO
removes the agent's state: `providers.base.remove_agent_state` (a finished worker, a spawn
undone) and `remove_session_state` (`lado forget`, a start undone), the session's folder with
it. A machine's restart empties `/tmp` as it does for any program.

### D6. A user's `TMPDIR` is the parent, not a variable lost

`TMPDIR` is in `agent_env.SHELL_BASE`, so the login shell always gives one on macOS. The launch
warnings `variable file TMPDIR … not used` / `project variable TMPDIR … not used`
(`_layer_warnings`) leave `TMPDIR` out: its value is used, as the parent.

### D7. The instructions' line

A constant beside `MESSAGING` in `runtime.py`, appended for every agent (supervisor and workers,
in and out of the container, read-only roles too):

> Temporary files: keep them in your own folder `$TMPDIR`, which LADO made for you alone; the
> other agents of this machine share `/tmp`. Never write to a fixed path in `/tmp` (such as
> `/tmp/pr.md`): another agent may use the same name.

Neutral words (LADO's core texts serve every field, not only code). A read-only role may still
write there: its temporary files are outside the repository.

### D8. Test layers

- Unit: the folder's path, modes, refusals and removal (`tmp_path` as the parent); the launch
  environment of each provider (claude, codex, kilo, opencode) has `TMPDIR` of its own, two
  agents of a session differ; Claude's `Launch.env` has `CLAUDE_CODE_TMPDIR`; the warnings leave
  `TMPDIR` out; the instructions hold the line.
- Integration with the fake agent: two workers of one session, each in its tmux window through
  `lado.agent_env`, run `sh` and write `$TMPDIR`: two different existing folders, each 0700,
  under the test's parent; a stop and resume keeps a file there; `finish_worker` removes it.
  This crosses tmux, the launch module and the MCP server.
- Live (two providers or more, by the human's run): an agent of Claude Code and one of Codex
  run `echo $TMPDIR` in their shell; each prints its own folder. Written, not run in a normal
  round (paid).

### D9. Version

A patch, 0.46.1: a fix of the agents' environment, no MCP tool, CLI option or schema change.
