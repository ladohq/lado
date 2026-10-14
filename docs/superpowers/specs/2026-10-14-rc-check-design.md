# RC check script: design

Task: LAD-51. Change: `openspec/changes/rc-check-script/` (proposal, delta
`release-candidates`, `design.md` D1-D11).

## Problem

Checking a release candidate is six one-line items in docs/release.md section 4. The
human retypes a dozen commands with versions and paths filled in, cleans up a scratch
`LADO_HOME`, its tmux server and its session by guesswork, and the written rollback fails
when the RC moved the schema: `lado update` keeps one backup of lado.db and deletes the
final's on the next update.

## What the human does after the change

| When | Command | What it does |
|---|---|---|
| each RC | `python3 scripts/rc_check.py sandbox [X.Y.ZrcN]` | a clean install in a temporary folder, the checks, the sandbox's UI until Enter, all removed; then the checklist |
| first RC of a cycle | `python3 scripts/rc_check.py upgrade X.Y.ZrcN` | `lado update X.Y.ZrcN` on the human's own LADO, a copy of the final's backup in `~/.lado-rc/`; then the checklist |
| next RCs, the final | the UI's Update or `lado update` | as for any update: a LADO on an RC is offered them |
| when the RC is bad | `python3 scripts/rc_check.py rollback` | plan, question, back to the final, lado.db restored when the schema moved, sessions and UI started again |

By hand stay only the checks a person makes by looking: the sdlc session to its first
gate, the UI, each CHANGELOG item (the script prints them as a list).

## The sandbox, step by step

1. Version: the argument, or the newest release on PyPI (a final is refused).
2. Folder `lado-rc-*` in the temp folder: `home/`, `tools/`, `bin/`, `repo/`; socket
   `lado-rc-<pid>`. Every LADO command: `LADO_HOME`, `LADO_TMUX_SOCKET`, `UV_TOOL_DIR`,
   `UV_TOOL_BIN_DIR` there and `LADO_TELEMETRY=0`.
3. `[ok  ] install`: `uv tool install --refresh-package lado lado==<v>`;
   `[ok  ] version`: `lado --version` is `<v>`.
4. `[ok  ] statistics off`: `lado telemetry status`.
5. `[ok  ] doctor`: `lado doctor` exits 0 and names `<v> (pre-release)`.
6. `[ok  ] session starts`: scratch repo with one commit; `lado start … --name rc-check
   --provider claude --no-attach`; `lado ls` shows `rc-check`.
7. UI: `lado ui --no-open --port 0`, the link, `Press Enter when you are done`.
8. `[ok  ] session stops`: `lado stop rc-check`.
9. `[ok  ] uninstall`: `lado uninstall --yes`; the home and the tmux server are gone.
10. The folder removed; the checklist.

A `[FAIL]` stops there, keeps everything and prints the folder and the command that
removes it. Ctrl-C removes everything (exit 130).

## Upgrade and rollback

`upgrade` hands the terminal to `lado update X.Y.ZrcN` (its plan, its `Update? [y/N]`).
Coming from a final, it copies `backups/lado.db.<final>` to `~/.lado-rc/` (outside
`~/.lado`), removing older copies; from an RC it leaves the copy alone.

`rollback` reads what runs (sessions alive in tmux, the UI server), compares the schema
of lado.db with the copy's, prints the plan and asks. Then: stop all, stop the server,
`lado update <final>` (its own question), restore lado.db from the copy by SQLite's
backup API when the schema moved, start the sessions and the UI again.

## Holding it against the roadmap and the principles

- **Neutral core**: LADO does not change; the sandbox's session takes any provider.
- **One source of truth**: CHANGELOG items through `release_notes.py`'s rules; the final
  to go back to is the copy's own file name.
- **No silent drops**: one line per check; a failure keeps the sandbox and names the way
  out; a missing CHANGELOG section is a warning line.
- **Only what is used**: three commands and two options, nothing in the package.
- **Tested end to end**: not applicable in CI (PyPI, a real CLI); unit tests with a
  recording runner, and one real `sandbox` run on 0.37.0rc2 in the build report.

## Test layers

| Requirement | Layer | Why |
|---|---|---|
| A release candidate is checked in a scratch install | unit (recording runner) + one manual run | the commands and their environment are the logic; a real run needs PyPI and a CLI |
| Moving onto a release candidate keeps the final's database | unit, temp folders as `HOME`/`LADO_HOME` | file copy and choice of when |
| Going back from a release candidate | unit, real SQLite files, recording runner | plan, restore by backup API, resumes |
| The checklist names what is left by hand | unit | text from a CHANGELOG sample |

## Docs

docs/release.md section 4: the text below, shown to the human as the run artifact
`release-section-draft.md`.
AGENTS.md, Layout: `scripts/rc_check.py` next to the other release scripts.

## Appendix: docs/release.md section 4

````markdown
## 4. The manual checklist

Each RC is checked with `scripts/rc_check.py`, run with `python3` from the repository's
root on the RC's commit (it needs `uv`, `tmux` and `git`). It does every step a machine
can and ends with a list of what is left to the human.

### 4.1 A clean install (every RC)

```
python3 scripts/rc_check.py sandbox [X.Y.ZrcN]
```

Without a version it takes the newest release on PyPI (and asks for one when that is a
final). In a temporary folder, with a LADO home and a tmux server of its own and
statistics off, it installs the RC the way users do (`uv tool install`) and checks, one
line each, `[ok  ]` or `[FAIL]`:

- the installed version is the RC's, and statistics are off;
- `lado doctor` finds no problem and says `(pre-release)`;
- a session on a scratch repository starts (Claude Code; `--provider` for another) and
  `lado ls` shows it.

Then it opens the RC's UI and prints the link: look at the System panel (the
`pre-release` pill) and at the session, then press Enter (`--no-ui` skips this). It
stops the session, removes everything with the RC's own `lado uninstall`, and prints
the list of what is left to check by hand. Your own `~/.lado` is never touched.

A check that fails stops the script and keeps the folder for a look, with its path and
the one command that removes it. Ctrl-C stops and removes everything.

### 4.2 Your own LADO on the RC (the first RC of a cycle)

```
python3 scripts/rc_check.py upgrade X.Y.ZrcN
```

With your sessions running. It runs `lado update X.Y.ZrcN`, which shows its plan and
asks as usual. A LADO on a final release is never offered an RC, so this one named
update is the way onto it; after it, the next RCs and the final are offered as usual
(the UI's Update, or `lado update`).

Coming from a final, it then keeps a copy of that final's database backup in
`~/.lado-rc/`: `lado update` keeps only one backup, and the next update would replace
it. Check what the update printed: the migration when the schema moved, your sessions
back, the UI back.

### 4.3 By hand, on your own LADO

- A session with the sdlc kit through one run to its first gate, answered in the UI.
- The UI: the chat, a gate's card, the System panel with its `pre-release` pill.
- Each line of CHANGELOG.md's `## X.Y.Z (unreleased)` tried once (both commands above
  print them as a checklist).

There is no fixed soak time: the final follows your "ok".

### 4.4 Going back

```
python3 scripts/rc_check.py rollback
```

It says what it will do and asks first: stop your sessions and the UI, install the
final the copy in `~/.lado-rc/` was taken from, and, when the RC moved the database's
schema, put that copy back (what was done on the RC is then lost: it says so). Then it
starts your sessions and the UI again on the final.
````
