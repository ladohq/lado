## Context

docs/release.md section 4 is the human's checklist for each release candidate (RC): a
clean install in a home of its own with `uvx`, the upgrade of the human's own LADO with
`lado update X.Y.ZrcN`, an sdlc session to its first gate, the UI, each CHANGELOG line,
and going back. Each item is one line of prose with versions, paths and variables to fill
in by hand; nothing says how to clean up the scratch install (its `LADO_HOME`, its tmux
server `lado-rc`, its session), and the rollback leans on `~/.lado/backups/lado.db.<final>`,
which `lado update` deletes on the next update (`self_update._back_up` keeps exactly one
backup, `lado.db.<the version it updated from>`).

A LADO on a final release is never offered an RC (`update.offered`; the UI's update takes
only the offered version, else 409), so the one named `lado update X.Y.ZrcN` is the only
way onto the first RC of a cycle; on an RC, the next RCs and the final are offered as
usual.

Root cause: the checklist is prose to retype, and nothing keeps the file a rollback needs.

## Options

1. **A stdlib script that does the steps, and a short section that points to it**
   (chosen with the human). Long-term cost: one script of a few hundred lines and its
   unit tests, which must follow LADO's CLI (`lado start`, `ls`, `stop`, `uninstall`,
   `update`, `ui`, `server stop`, `telemetry status`, `doctor`); a CLI change that breaks
   it shows at the next RC, the only time it runs.
2. **A better-written section only.** No code to keep, but every RC is still a dozen
   commands retyped with versions filled in, and the rollback still needs the human to
   remember to copy a backup at the right moment.
3. **LADO commands (`lado rc check`, `lado update` keeping the final's backup).** Ships
   release tooling to every user and changes `lado update` for what only the RC tester
   meets; against "Only what is used".

Held against AGENTS.md's Design principles: *Neutral core*: the sandbox's session takes
any provider (`--provider`, `claude` by default); nothing in LADO changes. *One source of
truth*: the CHANGELOG section is read by `release_notes.py`'s own rules (D7); the final
to go back to is the copy's file name, not a second record (D5). *No silent drops*: every
check prints its line, a failure keeps the sandbox and says how to remove it, a missing
CHANGELOG section is a warning line. *Only what is used*: three commands the checklist
needs, no options beyond `--provider` and `--no-ui`. ROADMAP: release tooling is outside
the stages; later stages (Projects, the desktop app) do not touch it.

## Decisions

- **D1. One script, three commands, standard library only.** `scripts/rc_check.py
  {sandbox,upgrade,rollback}` with `argparse`, run as `python3 scripts/rc_check.py` from
  the repository's root, like the other release scripts. Not `uv run`: that puts the
  working copy's `.venv/bin/lado` first on PATH, and `upgrade` and `rollback` must run the
  human's own `lado`. Both refuse when `shutil.which("lado")` lies inside the repository
  (a `.venv`), naming the one they found.
- **D2. Versions: X.Y.Z and X.Y.ZrcN only.** PyPI's JSON (`https://pypi.org/pypi/lado/json`,
  10 s timeout) gives the releases; the script parses `(\d+)\.(\d+)\.(\d+)(?:rc(\d+))?`
  and ignores others (LADO publishes no other form). A final sorts after its RCs. Not
  `lado.update`: the script imports nothing of LADO (D1); `release_notes.py` keeps its own
  tag pattern the same way. The default `sandbox` version is the newest release; a final
  is refused (exit 2).
- **D3. The sandbox.** `tempfile.mkdtemp(prefix="lado-rc-")` holds `home/` (`LADO_HOME`),
  `tools/` (`UV_TOOL_DIR`), `bin/` (`UV_TOOL_BIN_DIR`) and `repo/`; the tmux socket is
  `lado-rc-<pid>`. One function builds the environment of every sandbox command:
  `os.environ` minus `LADO_SESSION`, `LADO_AGENT`, `LADO_INSTANCE`, `VIRTUAL_ENV`, plus
  those four and `LADO_TELEMETRY=0`. The install is `uv tool install --refresh-package
  lado lado==<version>` (uv's cache may lack a release PyPI's JSON shows, as
  `update.installer` notes), so the RC is installed as users install it; its commands run
  as `<sandbox>/bin/lado`. The scratch repository: `git init`, a README, one commit with
  `-c user.name=rc-check -c user.email=rc-check@localhost` (no global git identity
  needed). The session is `rc-check`, `lado start <repo> --name rc-check --provider <p>
  --no-attach`; Claude Code waits on its folder trust dialog, which is enough: `lado ls`
  shows the session with its supervisor, no model is called. The UI is `lado ui --no-open
  --port 0`, its output (the link) passed through, then `input()`.
- **D4. Ending the sandbox.** After the checks: `lado stop rc-check`, then `lado uninstall
  --yes` (with a sandbox `LADO_HOME` it deletes only that home and keeps the program, and
  ends the tmux server when no session is left on the socket), then a check that the home
  is gone and `tmux -L <socket> list-sessions` fails, then `shutil.rmtree` of the folder.
  A `[FAIL]` stops at once and keeps everything; the last lines are the folder and one
  command: `LADO_HOME=… LADO_TMUX_SOCKET=… LADO_TELEMETRY=0 <bin>/lado uninstall --yes;
  tmux -L <socket> kill-server; rm -rf <folder>`. `KeyboardInterrupt` runs the same three
  steps without the checks (each one's failure ignored) and exits 130.
- **D5. The kept copy.** `~/.lado-rc/lado.db.<final>`, outside `LADO_HOME`, so neither
  `lado update` nor `lado uninstall` removes it. `upgrade` reads the human's `lado
  --version` before the update and again after it; when it was a final and is the RC
  after (whatever the update's exit code: `lado update` exits 1 for `partial`, a session
  that did not resume, after it installed the RC and made the final's backup), it copies
  `<LADO_HOME or ~/.lado>/backups/lado.db.<final>` there (`shutil.copy2`: the backup is a
  closed file the update wrote through SQLite's backup API) and removes the other files of
  `~/.lado-rc/`. A missing backup (a fresh install with no lado.db) is one warning line.
  `rollback` takes the final from the copy's name; more than one copy is refused.
- **D6. Rollback's steps.** Read before anything: the human's lado.db (`mode=ro`) for
  sessions with `stopped_at IS NULL` and their `repo`, kept only when `tmux -L
  <LADO_TMUX_SOCKET or lado> has-session -t =<name>` succeeds (a session whose tmux is
  gone is not "running"); `server.json` for `host` and `port`, kept only when its `pid`
  is alive; both databases' `PRAGMA user_version`. Print the plan, ask `Roll back? [y/N]`
  (no terminal: refused, there is no `--yes`, as the human decides). Then `lado stop
  --all`, `lado server stop`, `lado update <final>` with the terminal (its own question;
  a refusal or a failure stops the rollback with nothing restored and says so), `lado
  --version` must be the final, then the restore when planned:
  `sqlite3.connect(copy).backup(sqlite3.connect(live))`, checked by `user_version`; then
  `lado start <repo> --name <s> --no-attach` per session (a failure is a `[FAIL]` line,
  the others go on) and `lado ui --no-open --port <port>` (`--host` only when it was not
  127.0.0.1). The copy stays (a second rollback, or the next cycle's `upgrade` replaces it).
- **D7. The checklist.** `release_notes.py` gets `section(tag, changelog) -> str`, the
  unwrapped body `notes` builds on (same errors); `rc_check.py` imports it from its own
  folder (`sys.path[0]` is `scripts/` when run as a file) with the tag `v<rc>`, and prints
  each line that starts with `- ` as `[ ] <item>`. A `NotesError` becomes one warning
  line. The script also warns when `pyproject.toml`'s `version` is not the RC's (the
  checkout is not the RC's commit).
- **D8. Output.** English, like LADO's CLI. Each check one line, `[ok  ] <what>` or
  `[FAIL] <what>: <reason>` with the last lines of the command's output indented below;
  the commands that are the human's own (`lado update`, the sandbox UI link) keep the
  terminal. Exit 0 all checks passed, 1 a check failed or a refusal, 2 usage.
- **D9. LAD-50's documentation test.** LAD-50 adds a unit test that every line of
  docs/release.md with `LADO_HOME=$(mktemp -d)` has `LADO_TELEMETRY=0`, and asserts there
  is one. Section 4 no longer has such a line. Whichever pull request merges second
  replaces that test by `test_rc_check.py`'s check of the sandbox environment (D3) and
  keeps the no-`LADO_TELEMETRY=0`-line rule for any such line that remains.
- **D10. Tests.** Unit tests only (`tests/test_rc_check.py`, the module loaded by path as
  `tests/test_release_notes.py` does): a recording runner replaces `subprocess`, a stub
  replaces the PyPI fetch and `input`, real temporary SQLite files test the copy and the
  restore. No integration test: the script installs from PyPI and starts a real agent
  CLI. The developer runs `sandbox 0.37.0rc2 --no-ui` once and pastes its output into the
  build report; `upgrade` and `rollback` on the human's LADO are first run by the human at
  the next RC.
- **D11. Version.** No bump and no CHANGELOG line: the script and the docs are not in the
  package users install.
