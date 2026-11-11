Task: LAD-272

## Why

LADO 0.46.1 is a patch (fixes only), released at the human's choice through the release
candidate 0.46.1rc1 (docs/release.md, section 1). Before the RC's commit its release's checklist,
`docs/releases/0.46.1.md`, gets the section `## 0.46.1rc1` (docs/release.md, section 2, step 0,
and 4.7), in a pull request of its own that the human reads; `scripts/rc_check.py` prints that
section's items after the checks of every RC. In the same pull request CHANGELOG.md's
`## 0.46.1 (unreleased)` section is brought in line with docs/release.md's rules for its items:
six of its eight items end with a task key `(LAD-…)`, which rule 4 forbids, and two speak of
LADO's inside (`TMPDIR`, the session's background loop) rather than of what the user sees.

Facts the section rests on (checked on `dc9375f1`, main):

- The last final is `v0.46.0`. `git log --first-parent v0.46.0..origin/main`: LAD-229 (#283),
  LAD-247 (#284), LAD-257 (#282), LAD-202 (#285), LAD-246 (#287, tests only), LAD-259 (#288),
  LAD-267 (#289), LAD-153 (#286).
- `## 0.46.1 (unreleased)` holds 8 items, all under `### Fixed`: each fix changes what a user sees
  or does (rule 6 keeps all eight); LAD-246 changed tests only and has no item.
- `SCHEMA_VERSION` is 39 at `v0.46.0` and on main: the schema does not move, so 4.4's `rollback`
  holds and the user's own way back on a test home is not needed; 4.2 and 4.6 hold as for every
  first RC of a cycle (0.46.1rc1 is the first RC of 0.46.1).
- Since `v0.46.0`, `docker/install.sh` changed (LAD-257: a Docker Desktop still quitting is
  asked again every 10 s; macOS only), `docker/install.ps1` and the image's `Dockerfile` did not.
  4.5 already holds the installer's new case (Docker Desktop → Quit, then the line at once),
  added by LAD-257.
- The live test `test_an_agent_s_shell_has_its_own_temporary_folder` (LAD-247) runs in `live.yml`
  on every provider, on Linux, and checks the `$TMPDIR` a worker's shell sees. Nothing automatic
  checks Claude Code's own temporary root (`CLAUDE_CODE_TMPDIR`, its scratchpad), a Mac whose
  login shell has `TMPDIR=/var/folders/…/T/`, or the folder's removal by the real CLI's session.
- LAD-153: `lado stop`, `--all` and the UI's Stop wait for the session's loop; `lado update` and
  `lado uninstall` stop with `wait=False` and keep their own wait (`loop.wait_stopped`). So 4.2's
  update to the RC runs 0.46.0's stop, and 4.4's `rollback` runs the RC's. The loop writes
  `<s>: loop started, pid <n>, a pass every 2 s` and `<s>: loop ended: <reason>` to
  `LADO_HOME/loop.log`; its process's command line ends in `lado.cli loop <s>`.
- The RC itself follows 0.46.0rc1's precedent (`9ba95536`, a commit on main changing only
  `pyproject.toml` and `uv.lock`).

The human approved the scale and the draft's content (answer #5923).

## What Changes

### `docs/releases/0.46.1.md`, a new file

Its form is 4.7's. The text below is the file as approved; the developer writes it as it
stands and changes an exact line only where the code says otherwise (tasks 1.2):

````markdown
# LADO 0.46.1: the release's checks

The last final is 0.46.0. The database's schema stays at 39, so 4.4's `rollback` holds but
not the user's own way back on a test home; 4.2 and 4.6 hold as for every first RC of a
cycle. Those checks of every RC are not repeated here; this file holds what 0.46.1 itself
needs: each agent's own temporary folder, `lado stop` that waits for the session's loop
(with `lado update`, which stops and resumes sessions, and the way back), `lado doctor` and
Finder's `.DS_Store`, the broken session's row, the Model field's note, the model picker, the
session's tabs. `docker/install.sh` changed since v0.46.0 (a Docker Desktop still quitting,
macOS only), so 4.5's installer runs on the Mac with its Quit case; `docker/install.ps1` did
not change and the changed part does not run under WSL, so the Windows installer is not run.

## 0.46.1rc1

The RC: tag `v0.46.1rc1`, commit `<filled in at the RC>`; `live.yml` on it is green (run
`<filled in at the RC>`). The exact lines below are the code's; where the code has no fixed
text, the line says what to look for.

### Before you start

- A Mac with your LADO 0.46.0 and two sessions running, one of Claude Code and one of
  OpenCode, each with a worker; Docker Desktop, `uv`, `tmux`, `git`; a Linux machine with
  Docker and compose v2 (without one, note Linux as not checked).
- Chrome, Safari and Firefox.
- The CLIs logged in on the Mac: Claude Code (with the human's yes); OpenCode needs no login.
- An OpenRouter key, for 4.5's container without a login.
- Before 4.2: `tail -n 5 ~/.lado/loop.log`, and note the time.

### The update and the session loop (4.2)

- [ ] **The update leaves one loop per session.** After 4.2's `upgrade`, each session runs again with one loop.
  - `~/.lado/loop.log`, for each session: `<s>: loop ended: the session is stopped` before
    `<s>: loop started, pid <n>, a pass every 2 s`, and no `loop ended` after it.
  - `ps ax -o pid,command | grep '[l]ado.cli loop'` lists each running session once, with
    the pid of its last `loop started`; `lado ls` shows no `session loop not running`.

### Each agent's own temporary folder

On the RC, in the sessions 4.2 resumed and in a new one.

- [ ] **Claude Code's scratchpad is the agent's own.** Ask the Claude Code supervisor: «Which is your scratchpad folder, and what is $TMPDIR in your shell?»
  - `$TMPDIR` is `<your login shell's TMPDIR>lado-<uid>/<session>/supervisor` (on the Mac
    `/var/folders/…/T/lado-501/<session>/supervisor`), and the scratchpad is under it, not
    under `/tmp/claude-<uid>`.
  - Its worker's are under `…/<session>/<worker>`; `ls -ld` of each shows `drwx------`.
- [ ] **OpenCode's agents have their own folder too.** In the OpenCode session, ask the supervisor and its worker for `echo $TMPDIR`.
  - Each names its own `…/lado-<uid>/<session>/<agent>`; no new `/tmp/opencode` or
    `$TMPDIR/opencode` outside these folders is made by them.
- [ ] **Two agents' drafts of one name stay apart.** Ask each of the two workers to write `$TMPDIR/pr.md` with its own name in it, then to print it.
  - Each prints its own name.
- [ ] **The folder goes with the agent, stays over a stop.** Stop and resume a session, then finish a worker.
  - After `lado stop <s>` and `lado start <s>` the agents' folders and their files are there.
  - After the supervisor finishes a worker, its folder is gone and the supervisor's stays;
    after `lado forget <s>` of a stopped session, `…/lado-<uid>/<s>` is gone.
- [ ] **A folder not safe to use refuses the start.** On a test home (`LADO_HOME`, `LADO_TMUX_SOCKET` of its own), with `TMPDIR` pointed at a fresh folder `T`.
  - `ln -s /tmp $T/lado-$(id -u)`, then `lado start <a test repository>`: it refuses with
    `cannot make the temporary folder of agent "supervisor": $T/lado-<uid> is a link`, and
    no session window opens. Remove `T` and the test home.

### `lado stop` waits for the session's loop

- [ ] **A stop and a start in a row leave one loop.** `lado stop <s> && lado start <s>` on a running session.
  - `loop.log`: `<s>: loop ended: the session is stopped`, then one `<s>: loop started …`;
    `ps ax -o pid,command | grep '[l]ado.cli loop <s>'` shows one process, of that pid.
  - `lado stop` takes up to about 2 s longer than on 0.46.0; the UI's Stop of a session
    (its page) returns the same way, and `lado stop --all` stops every session, then
    returns.
- [ ] **A home deleted right after a stop stays deleted.** On a test home: start a session, `lado stop <s>`, then `rm -rf "$LADO_HOME"` at once.
  - After 10 s the folder `LADO_HOME` does not exist (no new `lado.db`, no `loop.log`).
    Then `tmux -L <the test socket> kill-server`.

### `lado doctor` and Finder's `.DS_Store`

- [ ] **Finder's files are not agents' folders.** Open `~/.lado/agents/` and a running session's folder in it in Finder, so that it leaves `.DS_Store`.
  - `lado doctor`: `[ok  ] Agent config folders: only those of running agents`; it
    offers no `rm -rf` of a `.DS_Store`.

### The UI

In Chrome, then a glance in Safari and Firefox (the browser tests run Chromium only).

- [ ] **A broken session is red in the list.** Kill one session's tmux session (`tmux -L lado kill-session -t <s>`).
  - Its row in the session list says that in red after a full red dot, as its head does;
    `lado ls` says `(tmux session is gone)`. Then `lado stop <s>`.
- [ ] **The Model note names the server model.** In 4.5's container, before Claude Code's login, with OpenRouter saved and a model for Claude Code on it.
  - New session: Agent Kilo CLI, Model one of its own (`kilo/…`), then Agent Claude Code,
    which takes its one server model: the note reads `<model> belongs to Kilo CLI. For this
    session only: Claude Code is not logged in, so it runs on your server's model.`, not
    `… so the model is back to Claude Code's default.`
- [ ] **Model ids in the mono face.** Settings → Agent CLIs, a CLI's Default model picker, and Model servers.
  - Ids under the models' names, the built-in ids and a server's address show in IBM Plex
    Mono. The highlight after a failed read is the tests' (no way to fail the read by hand).
- [ ] **The session's last tab stays clear.** A narrow window (about 600 px), a session with every tab.
  - Tab to the last tab, then resize the window: the tab stays clear of the fade and ›
    is gone; the same after a reload with the cache off (the font arrives late).

### The image (4.5, 4.6)

- [ ] **The installer waits for a quitting Docker Desktop.** 4.5's Quit case of the installer, on the Mac.
  - Run right after Docker Desktop → Quit: it waits, starts Docker Desktop once it has quit,
    says the RC is installed and opens the link; it does not stop with `Docker Desktop did
    not answer in 2 minutes`.
- [ ] **The container's agents have their own folder.** In 4.5's container, a session's supervisor's `echo $TMPDIR`.
  - `/tmp/lado-1000/<session>/supervisor` (the image's user is uid 1000).

### Going back (4.4)

- [ ] **Going back to 0.46.0 leaves one loop per session.** `rollback` stops the sessions on the RC and resumes them on 0.46.0.
  - `loop.log`: each session's RC loop `loop ended` before 0.46.0's `loop started`; `ps` as
    above shows one loop per session; `lado ls` shows them running.
- [ ] **What 0.46.0 loses.** The schema does not move; nothing in `lado.db` is lost.
  - Agents resumed on 0.46.0 have no folder of their own: `$TMPDIR` is your login shell's
    again, and Claude Code's scratchpad is in `/tmp/claude-<uid>`, shared.
  - The folders `…/lado-<uid>/` stay on disk: 0.46.0 does not remove them. `rm -rf` them
    by hand when no session runs on a 0.46.1.

### What covers the CHANGELOG's items

Each of the 8 items of `## 0.46.1 (unreleased)` at the RC's commit, with what covers it. An
item with a check above is tried there; the browser tests run Chromium only.

Fixed:

1. Agents no longer overwrite each other's drafts: each agent's own temporary folder (unit
   `tests/test_temp_dirs.py`, `tests/test_agent_env.py`, `tests/test_runtime.py`; integration
   `tests/integration/test_agent_temp_folders.py`, `test_login_shell.py`; live
   `tests/live/test_live.py` on every provider).
2. A broken session stands out in the session list: the UI (the browser
   `tests/ui/test_session_list.py`).
3. The Mac installer waits for a Docker Desktop that is still quitting: the image (unit
   `tests/test_install_sh.py`).
4. The note under Model names the server model the field took: the UI (vitest
   `web/src/Launch.test.tsx`).
5. Model ids in the mono face, and the model picker's highlight stays put: the UI (vitest
   `web/src/ModelPicker.test.tsx`; the browser `tests/ui/test_models_section.py`).
6. A session's scrolled tabs keep their tab in view: the UI (the browser
   `tests/ui/test_narrow_layout.py`).
7. `lado stop` returns once the session has fully stopped: `lado stop` waits, the update and
   going back (unit `tests/test_runtime.py`, `tests/test_loop.py`; integration
   `tests/integration/test_session_loop.py`).
8. `lado doctor` no longer takes `.DS_Store` for an agent's folder: doctor (unit
   `tests/test_doctor.py`).
````

The two placeholders of the RC's paragraph (`<filled in at the RC>`) stay in this pull request:
the commit and `live.yml`'s run exist only after it is merged, and are filled in with the RC.

### CHANGELOG.md, `## 0.46.1 (unreleased)`

Every task key `(LAD-…)` goes (rule 4). Two items are written anew in the user's words: the
temporary folders without `TMPDIR`, a variable the user does not set, and `lado stop` without
the loop's mechanism. The other six keep their text. No `### Upgrade` item: `lado update` and
the image's update restart running sessions, and an agent gets its folder at its resume. The
section, as approved:

```markdown
## 0.46.1 (unreleased)

### Fixed

- **Agents no longer overwrite each other's drafts.** Each agent keeps its temporary files in a
  folder of its own, Claude Code's scratchpad too, so two agents that write a draft of one name
  each keep their own.
- **A broken session stands out in the session list.** A session whose tmux session is gone or
  whose loop does not run says so on its row in red after a red dot, as in its head, not in grey.
- **The Mac installer waits for a Docker Desktop that is still quitting.** Run right after
  Docker Desktop's Quit, it starts Docker Desktop once it has quit and installs, instead of
  stopping after 2 minutes.
- **The note under Model names the server model the field took.** In New session, a change of
  Agent to a CLI that is not logged in and takes its one server model no longer says the model
  went back to the default.
- **Model ids in the mono face, and the model picker's highlight stays put.** Model ids and
  servers' addresses show in IBM Plex Mono as designed; after a failed read of the list the
  highlighted model stays highlighted, so Enter picks the one you pointed at.
- **A session's scrolled tabs keep their tab in view.** When the tabs change width, as the
  font arrives or the window is resized, the tab you reached with Tab, or the one shown, no
  longer stays half under the fade with › showing.
- **`lado stop` returns once the session has fully stopped.** `lado stop s && lado start s`
  leaves the session running with one loop, and a LADO home deleted right after a stop stays
  deleted.
- **`lado doctor` no longer takes `.DS_Store` for an agent's folder.** Files and hidden names
  under `~/.lado/agents/` are not listed as left by agents, nor offered for removal.
```

### `tests/test_rc_check.py`

The test over the repository's real checklists (`test_the_repositorys_own_checklists_have_no_warning`)
also checks `0.46.1rc1` against `docs/releases/0.46.1.md`: no warning line, the every-RC lines
first, and the RC's own items after them.

### After the merge: the RC (no file of this pull request)

On main with this pull request merged, as docs/release.md section 2, steps 1-4:
`uv version 0.46.1rc1`, a commit `Release candidate 0.46.1rc1` of `pyproject.toml` and `uv.lock`
alone pushed to main, CI and the smoke green on it, `gh workflow run live.yml` on that commit with
every cell green, then the tag `v0.46.1rc1` pushed; each push with the human's yes. The session's
lead does it with the human; the freeze starts with the RC.

## Scope

- `docs/releases/0.46.1.md` (new), CHANGELOG.md's `## 0.46.1 (unreleased)` section, the
  real-file test of `tests/test_rc_check.py`.

## Out of scope

- The version bump, the RC's commit, `live.yml` and the tag: the session's lead does them with
  the human after the merge; the integrator never bumps the version or tags.
- `docs/release.md` and `scripts/rc_check.py`: no rule of the release changes, so the change has
  no delta.
- The Windows installer (4.5): `docker/install.ps1` did not change, and the part of
  `docker/install.sh` that changed runs only on macOS (the human's answer #5923, 2).
- Codex and Kilo by hand for the temporary folder: the live test checks every provider; the
  hand check takes Claude Code (its own temporary root, the scratchpad) and OpenCode (no login,
  its own folder that was in `/tmp`) (#5923, 1).
- 4.4's user's own way back on a test home: the schema does not move.
- Checks of 0.46.0's features: 0.46.1 does not touch them (4.7).
- `docs/releases/0.46.0.md`'s two placeholders: that file belongs to 0.46.0's release.
- Moving the task to review: this pull request is not the task's last; LAD-272 stays in
  progress until the final 0.46.1.

## Impact

- Docs, CHANGELOG.md and one unit test; no code, API, MCP, CLI or schema change. The release it
  prepares is a patch (0.46.1).
