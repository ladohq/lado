# Releasing LADO

This file is the one description of how LADO is versioned and released: the version
rules, CHANGELOG.md, the steps, the human's checklist and what the Release workflow
checks. AGENTS.md only points here.

A minor release is first published as a release candidate (RC): a PyPI pre-release
`X.Y.0rcN` that the human installs on their own LADO and works with before anyone else
gets it. Users are never offered an RC: `pip install lado`, `uv tool install lado`,
`lado update`, the daily check and the System panel take final releases only. A LADO that
runs an RC is offered newer RCs and the final, and says it is a pre-release (`lado doctor`,
the System panel's `pre-release` pill).

## Versions

LADO is 0.x. Bump the minor (0.7.0) for a new feature, an MCP tool or CLI change that
older agents cannot use, or a database schema migration; running sessions must be
restarted after such an upgrade (`lado update` stops and resumes them). Bump the patch
(0.7.1) for fixes and docs only: no new feature, no API or schema change.

## CHANGELOG.md

Each change users see adds a line under `## X.Y.Z (unreleased)` in the pull request that
makes it (add that heading on top when it is missing; X.Y.Z is the next version by the
rules above). An RC adds no heading: its changes are the `(unreleased)` section. The
final's commit puts the date in place of `(unreleased)`.

A version's section is also its GitHub release's notes (section 7). They are read by
people who use LADO, in its UI, its CLI or its Docker image, not by its developers, so
each item is written for them:

1. **Groups.** Items go under these subheadings, in this order, and an empty group is
   left out: `### New`, `### Improved`, `### Fixed`, `### Docker image`, `### Upgrade`
   (what a user must do when moving to this version, e.g. `restart running sessions after
   the update; lado update does it`), `### For integrators` (items starting with `API:`
   or `MCP:`).
2. **A bold title, then one or two sentences.** The title is the result for the user in
   three to eight words (`**Phone: nothing hides the composer.**`); the sentences say what
   they now see or can do and, when needed, what they must do themselves.
3. **At most three lines** in the file. Details go to the documentation, named by a link
   (`docs/install.md`), not into the item.
4. **The user's words.** Name what they see: a button, a screen, a command they type
   themselves. No modules, source files, tests, internal mechanisms or task keys; an
   environment variable or a command only when the user sets or runs it.
5. **A fix says what works now**, not how the bug looked from inside: "Files attached
   right after a chat opens show their preview", not "a file's chip shows its type by the
   server's table once that is known".
6. **What users do not notice gets no item**: tests, CI, flaky tests, internal documents,
   the kits' rules.
7. **One change, one item.** A later pull request of the same feature edits its item
   instead of adding another.

An item may wrap over lines, the lines that go on indented by two spaces; the notes join
them into one. Past sections stay as they were written.

## 1. When an RC is needed

- Every minor release, `X.Y.0`: the Release workflow refuses its final without an RC.
- A patch, `X.Y.Z` with Z > 0, at the human's choice: with an RC, the same rules hold;
  without one, it is released directly (section 5 without the RC).

## 2. The RC

0. Write the RC's section `## X.Y.ZrcN` of its release's checklist, `docs/releases/X.Y.Z.md`
   (4.7; the first RC makes the file), in a pull request of its own that the human reads,
   or in the RC's commit: `rc_check.py` prints it from the RC's checkout.
1. `uv version X.Y.ZrcN` (N from 1), commit `Release candidate X.Y.ZrcN` on main, push.
   CHANGELOG.md is not touched: its `## X.Y.Z (unreleased)` stays until the final.
2. CI is green on that commit, the smoke on Linux and macOS with it.
3. `gh workflow run live.yml` on main at the RC's commit, every cell green. The button runs
   whatever main is at, so `gh run list --workflow live.yml --limit 1 --json
   headSha,conclusion` must show the SHA of `git rev-parse HEAD`; a run of another commit does
   not count, nor does a local `make test-live`, which without its endpoint skips and ends with
   no failure. A failed cell is rerun by the flaky rule of the checks (a pass on rerun is a
   flake, noted, no code changed for it).
4. Push the tag `vX.Y.ZrcN`. Its spelling is PEP 440's, no dash (`v0.37.0rc1`, never
   `v0.37.0-rc1`): the workflow compares the tag with `uv version --short`. The Release
   workflow tests LADO's image on both architectures, publishes `X.Y.ZrcN` to PyPI as a
   pre-release, tags the image `ghcr.io/ladohq/lado:X.Y.ZrcN` (section 8), then a GitHub
   pre-release with the `(unreleased)` section as its notes (section 7); then section 4.

## 3. The freeze

From the first RC to the final, only fixes for the RC are merged to main. Each fix is
released as the next RC (section 2 again, N + 1), and the human's LADO is offered it. Any
other merge makes the final impossible: the workflow's check finds code the last RC did
not have, and a new RC from main is needed. Nothing in LADO enforces the freeze; the check
in section 6 catches a mistake before it is published.

## 4. The manual checklist

Each RC is checked with `scripts/rc_check.py`, run with `python3` from the repository's
root on the RC's commit (it needs `uv`, `tmux` and `git`, and stops at once, naming what
is missing and how to install it, when one is not on PATH). It does every step a machine
can and ends with the checklist left to the human, one line per check: the list below,
then the items of the RC's own section of its release's checklist, `docs/releases/X.Y.Z.md`
(4.7). The RC's image (4.5, 4.6) is checked by hand: `rc_check.py` does not do it yet.
The System panel below is the popover of `live` in the top bar, not a page of Settings.

This section holds the checks every RC needs. A check of one version, of what it changed,
goes to that version's checklist (4.7), never here.

### The checks of every RC

- [ ] 4.1 A clean install: `sandbox` passes every check; a look at its UI.
- [ ] 4.2 Your own LADO on the RC (first RC of a cycle): `upgrade`, one copy in `~/.lado-rc`.
- [ ] 4.3 A session of the built-in supervisor: the chat, a question card answered in the UI, pre-release.
- [ ] 4.4 Going back, last: `rollback`; the user's way back when the RC moved the schema.
- [ ] 4.5 The image: all on the Mac, the pull and a session on Linux; installers if changed.
- [ ] 4.6 The image's update from the last final (first RC of a cycle).

### 4.1 A clean install (every RC)

```
python3 scripts/rc_check.py sandbox [X.Y.ZrcN]
```

Without a version it takes the newest release on PyPI (and asks for one when that is a
final). In a temporary folder, with a LADO home and a tmux server of its own and
statistics off (`LADO_TELEMETRY=0` for every LADO command of it; a fresh home would be a
new install to the usage statistics, docs/telemetry.md), it installs the RC the way users
do (`uv tool install`) and checks, one line each, `[ok  ]` or `[FAIL]`:

- the installed version is the RC's, and statistics are off;
- `lado doctor` finds no problem and says `(pre-release)`;
- a session on a scratch repository starts (Claude Code; `--provider` for another) and
  `lado ls` shows it.

Then it opens the RC's UI and prints the link: look at the System panel (`live` in the
top bar, its `pre-release` pill) and at the session, then press Enter (`--no-ui` skips this). It
stops the session, removes everything with the RC's own `lado uninstall`, and prints
the list of what is left to check by hand. Your own `~/.lado` is never touched.

A check that fails stops the script and keeps the folder for a look, with its path and
the one command that removes it, and shows the failed command's output under its line
(for `lado doctor`, its `[FAIL]` lines with their hints). Ctrl-C stops and removes
everything.

### 4.2 Your own LADO on the RC (the first RC of a cycle)

```
python3 scripts/rc_check.py upgrade X.Y.ZrcN
```

With your sessions running; before it, `ls ~/.lado-rc` and note what is there. It runs `lado update X.Y.ZrcN` (your own install, counted
once as before), which shows its plan and asks as usual. A LADO on a final release is
never offered an RC, so this one named update is the way onto it; after it, the next RCs
and the final are offered as usual (the UI's Update, or `lado update`).

Then it runs `lado ls` once, which upgrades the database when no session resumed. Coming
from a final whose schema the RC moved, it keeps a copy of the migration's backup of that
final's database (`~/.lado/backups/lado.db.schema-<N>`) in `~/.lado-rc/`: the migration
keeps only one, and the next RC's migration would replace it. Without a schema change it
keeps nothing and says that `lado update <final>` alone goes back. Check what the update
printed: the migration when the schema moved, your sessions back, the UI back.

When the schema moved, `~/.lado-rc` then holds one file, `lado.db.<the final you came
from>`, and the script said `Kept a copy of LADO <final>'s database`. A copy of another
final left there (a LADO moved onto an RC without this script) is what `rollback` would go
back to.

### 4.3 By hand, on your own LADO

The release's check checks LADO itself, not its kits: no kit is needed here.

- New session on any folder with the built-in supervisor; it answers in the chat.
- Ask it in the chat to ask you a question with choices: its card shows, and the choice you
  press in the UI reaches it (it names it in the chat).
- The System panel with its `pre-release` pill.
- Then the RC's own section of its release's checklist (4.7), printed after this list.

Flows and gates are the tests': a gate's card in the browser tests with the fake agent
(`tests/ui/test_gates.py`), a flow run by a real CLI in the live tests
(`tests/live/test_live.py`, the flow `tiny` of a test kit).

There is no fixed soak time: the final follows your "ok".

### 4.4 Going back

```
python3 scripts/rc_check.py rollback
```

It says what it will do and asks first: stop your sessions and the UI, install the
final the copy in `~/.lado-rc/` was taken from, and, when the RC moved the database's
schema, put that copy back (what was done on the RC is then lost: it says so). It puts
the copy into `~/.lado/backups/lado.db.schema-<N>` and leaves the restore to the RC's own
`lado update <final>`, which warns, asks and restores, the way users go back too. Then it
starts again the sessions the copy has, and the UI, on the final. Read `lado update
<final>`'s warning before you answer `y`: it names what going back loses. Go back last,
after every other check of the RC.

Once per RC that moved the schema, also the user's own way back, on a test home (a
temp `LADO_HOME` and `LADO_TMUX_SOCKET`, never yours): `lado update <the final before>`
from the RC with a session in it, as `docs/install.md` "Going back to an older version"
says. It warns before it asks, and the old final starts with that session and the
database of before the RC. In a fresh terminal, `X.Y.Z` the final before:

```
export T=$(mktemp -d)
export HOME=$T LADO_HOME=$T/.lado LADO_TMUX_SOCKET=lado-rc-back LADO_TELEMETRY=0
export LADO_AGENT_ENV=inherit PATH=$T/.local/bin:$PATH
uv tool install lado==X.Y.Z
lado start <a test repository> --name back --provider opencode
lado update X.Y.ZrcN --yes
```

`LADO_AGENT_ENV=inherit`: the new `HOME` has no shell profile, so without it the agent's
CLI is not on the agents' PATH and LADO refuses with that hint. OpenCode needs no login.
Then the RC's own checks of the way back (its checklist, 4.7), and

```
lado update X.Y.Z
lado ls
```

`lado ls` lists `back` on X.Y.Z. Then remove it all and close the terminal:

```
lado stop --all
tmux -L lado-rc-back kill-server
rm -rf "$T"
```

### 4.5 The image (every RC)

On the Mac all of 4.5: CI has no Docker Desktop. On Linux, `lado doctor`, the log's
warnings, the missing workspace and the refusal of `lado update` are the container tests'
(`tests/container/`, run on the bytes published, section 8): there, pull the image and run
one session. Each in a fresh terminal with no `LADO_*` variable in its
environment: compose takes a shell variable over `.env`, so an old `LADO_PORT` or
`LADO_VERSION` there runs another port or version than the file says. `env | grep
'^LADO_'` prints nothing.

The image is public: a machine logged out of ghcr.io pulls it without a question, and
gets its own architecture (arm64 on Apple silicon and Linux arm64, amd64 on x86):

```
docker logout ghcr.io
docker pull ghcr.io/ladohq/lado:X.Y.ZrcN
```

Run it with compose from a temporary folder, with a test workspace (one small
git repository in it) and a port of its own, so it meets nothing of your own LADO. The
`compose.yaml` comes as a user gets it, the release's asset, which the guide's update
downloads too; `cmp` checks it is the repository's file at the tag:

```
mkdir -p /tmp/lado-rc-image && cd /tmp/lado-rc-image
curl -fLO https://github.com/ladohq/lado/releases/download/vX.Y.ZrcN/compose.yaml
git -C <repository> show vX.Y.ZrcN:docker/compose.yaml | cmp - compose.yaml
cat > .env <<'EOF'
LADO_VERSION=X.Y.ZrcN
LADO_WORKSPACE=/absolute/path/to/a/test/folder
LADO_PORT=8799
LADO_GIT_NAME="RC Check"
LADO_GIT_EMAIL=rc-check@example.com
EOF
docker compose up -d
docker compose logs lado
docker compose exec lado lado ui --no-open
```

`docker compose logs lado` has no warning about `LADO_REPOS` (not mounted, not
writable) nor about git's identity (`user.name`, `user.email`); the last command prints
the UI's link with its token. Then:

- Log in to Claude Code once: `docker compose exec -it lado claude`, log in, exit. The
  login stays in the home volume.
- `docker compose exec lado lado doctor` has no `[FAIL]`, finds the four agent CLIs,
  says LADO runs in a container and names `LADO_REPOS`.
- The UI: the System panel shows the `pre-release` and `container` pills, and no warning
  about a server open to the network (a note about the container's published port
  instead).
- A session: on a new home volume the New session window opens on New empty folder (no
  recent place yet); Where → Other folder… lists the folders of `LADO_WORKSPACE` under its
  Folder field. The session starts and its supervisor answers; the next window opens on
  that folder. A worker's worktree, if you start one, is on the host at the same path, its
  files yours (on Linux).
- `docker compose exec lado lado update` refuses at once, stops nothing and says a new
  image updates LADO in a container; the UI's Update does not start one either.
- A missing workspace, on the Mac (Docker Desktop): `docker compose down`,
  set `LADO_WORKSPACE` in `.env` to a folder that does not exist, `docker compose up -d`.
  It refuses with Docker's error, the path in it is that folder's, and the folder is
  not made on the host; the guide's troubleshooting line reads that error. Put `.env`
  back before going on.

Then remove it all, the home volume with Claude Code's login too:

```
docker compose down -v
cd / && rm -rf /tmp/lado-rc-image
```

The installers run only when one of them changed since the last final, `X.Y.Z` here
(`git diff --stat vX.Y.Z vX.Y.ZrcN -- docker/install.sh docker/install.ps1` prints
something); otherwise the RC's are the final's, which were checked at their release.

The installer, on the Mac, with Docker Desktop quit first: the RC's own `install.sh` (its
release stamps it with the RC's version) in a folder of its own, so it meets no LADO of
yours:

```
curl -fsSL https://github.com/ladohq/lado/releases/download/vX.Y.ZrcN/install.sh | sh -s -- --dir /tmp/lado-rc-install
```

It starts Docker Desktop and waits for it, asks for the workspace (give the test folder)
and about the phone after its warning (answer `y`); `/tmp/lado-rc-install/.env` has
`LADO_VERSION=X.Y.ZrcN` and `COMPOSE_PROJECT_NAME=lado-lado-rc-install`; the link opens
in the browser, the UI answers, and the link it prints for the phone opens on a phone of
the same Wi-Fi. Run the same line again: it says the RC is installed, rewrites nothing and
opens the same link. Then remove it:

```
cd /tmp/lado-rc-install && docker compose down -v
cd / && rm -rf /tmp/lado-rc-install
```

On Windows 11 with Docker Desktop (the human, by hand: CI has no Windows with Linux
containers), in PowerShell:

```
irm https://github.com/ladohq/lado/releases/download/vX.Y.ZrcN/install.ps1 | iex
```

With no Ubuntu in WSL it offers `wsl --install -d Ubuntu` and says to run it again after
Ubuntu's first start; with Docker Desktop's WSL integration off for Ubuntu it names
Settings → Resources → WSL integration; with it on, it asks install.sh's questions in
PowerShell, LADO's link opens in Windows' browser and the UI answers; the phone's link
(`<windows name>.local`) opens on a phone of the same Wi-Fi. Then, in Ubuntu: `cd
~/lado-docker && docker compose down -v`, and `rm -rf ~/lado-docker`.

### 4.6 The image's update (the first RC of a cycle)

On one machine, as in 4.5 (a fresh terminal, a test workspace), from the last
final before the RC, `X.Y.Z` below, the way a user of `X.Y.Z` updates: with that
version's own `compose.yaml` and a session running. The old file comes from the tag (a
release before 0.40.0 has no `compose.yaml` asset). The `.env` names the workspace
`LADO_PROJECTS` on purpose: the `compose.yaml` of a final before 0.43.0 knows only that
name, and the update checks that an installed `.env` keeps working. A second LADO beside
it is the container tests' (`tests/container/test_two_lados.py`), not checked here:

```
mkdir -p /tmp/lado-rc-update && cd /tmp/lado-rc-update
git -C <repository> show vX.Y.Z:docker/compose.yaml > compose.yaml
cat > .env <<'EOF'
COMPOSE_PROJECT_NAME=lado-rc-update
LADO_VERSION=X.Y.Z
LADO_PROJECTS=/absolute/path/to/a/test/folder
LADO_PORT=8799
EOF
docker compose up -d
```

Log in to Claude Code and start a session as in 4.5, and a second one you stop (`docker
compose exec lado lado stop <session>`, or the UI); leave the first running, idle. Then
the update, by the guide's steps (docs/install.md, "Update the container"): put
`LADO_VERSION=X.Y.ZrcN` in `.env`, and

```
cp compose.yaml compose.yaml.bak
curl -fLO https://github.com/ladohq/lado/releases/download/vX.Y.ZrcN/compose.yaml
diff compose.yaml.bak compose.yaml
docker compose up -d
docker compose logs lado
docker compose exec lado lado ls
```

`diff` shows what the release changed in the file (mounts, settings, the header's text),
no setting of yours. When the RC moved the schema, the log has `lado: upgraded lado.db
from schema N to M; its backup is /home/lado/.lado/backups/lado.db.schema-N`. The running
session resumes: the log has `lado: resumed session "<session>" at the container's start`
and, a few seconds after the start, `lado ls` shows it running (before, it may still say
`(stopped)`); the stopped one stays stopped. The UI shows the RC's version.

Then back by the version's tag, as the guide's "Go back to the version before" says:
`LADO_VERSION=X.Y.Z` in `.env` again, keeping the new `compose.yaml`, and,
when the schema moved (N from the log above):

```
docker compose down
docker compose run --rm lado sh -c 'cd ~/.lado && rm -f lado.db-wal lado.db-shm && cp backups/lado.db.schema-N lado.db'
docker compose up -d
docker compose exec lado lado ls
```

`X.Y.Z` starts on the restored lado.db and lists the sessions; without a schema change,
`docker compose up -d` alone goes back. Remove it:

```
docker compose down -v
cd / && rm -rf /tmp/lado-rc-update
```

### 4.7 The release's checklist

What one version needs checked by hand, beyond the list above, is that version's own
checklist: `docs/releases/X.Y.Z.md`, one file per version, in English. It is how the next
release learns what this one was checked for, and `rc_check.py` prints its RC's part.

Its form: a heading `# LADO X.Y.Z: the release's checks`; a short paragraph naming the
last final, whether the schema moves (from N to M), and what the checks of every RC above
already cover; then one section `## X.Y.ZrcN` per RC, in order. A section's checks are
top-level `- [ ] **Title.** …` items, each one check, its detail (commands, the exact
lines expected) on nested lines under it; `###` subheadings may group them. `rc_check.py`
prints the first line of each top-level `- [ ] ` item of its RC's section, so that line
names the check on its own.

Who and when: the release task writes the RC's section before the RC's commit (section 2,
step 0). The first RC's section is the version's whole list; a later RC's holds only what
its fixes touch, and what of the earlier RC's list was left open. The human may edit the
file after the last RC (their notes, what they found): the final may differ from its last
RC in its own checklist (section 6), so this needs no new RC.

What goes in it:

- each item of CHANGELOG.md's `## X.Y.Z (unreleased)` section, with what covers it (the
  tests that run it, and at which layer: unit, integration, the browser, smoke, live, the
  image) and what is tried by hand because nothing does: a real model server, a real phone
  or tablet, Safari and Firefox (the browser tests run Chromium only), Docker Desktop, a
  real CLI's login;
- the steps of the release that the automatic tests do not cover, with the exact lines the
  code prints;
- what going back to the last final loses, when the release adds something it loses;
- an earlier version's check again only when this release touches what it checked: a
  check does not stay in the list because a release once needed it.

## 5. The final

1. `uv version X.Y.Z`, the date in place of `(unreleased)` in CHANGELOG.md's heading,
   commit `Release X.Y.Z` on main, push. CI is green on that commit.
2. Push the tag `vX.Y.Z`. The Release workflow checks it, LADO's telemetry token and
   its release notes (section 6), then builds with `make dist`, tests LADO's image,
   publishes to PyPI, tags the image with the version and `latest` (section 8), and then
   the GitHub release, marked the latest (section 7).
3. The tracker (Yougile, through LADO's skill `tracker`): each task in the status `done`
   with the label `waiting for release` whose change the release ships gets the comment
   «Вышла в X.Y.Z» and the field `release` set to X.Y.Z (unchanged when it already holds
   it), and the label is removed; a task whose change is not in the release keeps its
   label and its field. The merge sets that label and the coming version in the field
   (`.lado/sdlc.md`, After the merge), so the final corrects a planned patch that became
   a minor and fills the field of a task merged before it existed; the label's and the
   field's stickers are named in `.lado/tracker.yaml`.

The live tests are not run again: the code is the last RC's, which they ran on. A patch
released without an RC gets all of section 2's checks (CI, `live.yml`) on its
release commit before its tag.

The Windows probe (docs/testing.md, Test infrastructure) is not a release step: Docker,
not PyPI, is LADO's main install, and few install it from PyPI on Windows. It runs weekly
on main, and a red run there is fixed as any other regression; a release does not wait
for it.

## 6. What the workflow refuses

First the Release workflow checks that the tag is `v` and the package's version
(`uv version --short`). Then, before it builds, it runs `scripts/release_check.py <tag>`
on a checkout with every tag and the history (`fetch-depth: 0`). A tag that is no final
`vX.Y.Z` (an RC) passes. A final fails, and nothing is published, when:

- it is `vX.Y.0` and no `vX.Y.0rcN` tag exists: `vX.Y.0 needs a release candidate: tag
  vX.Y.0rc1 first`;
- it differs from its last RC (the highest N) in a file other than CHANGELOG.md, its own
  checklist `docs/releases/X.Y.Z.md` (4.7; another version's is refused), pyproject.toml
  and uv.lock: `vX.Y.Z differs from vX.Y.ZrcN in <path>`, one line per file;
- it changes a line of pyproject.toml that is not its `version = "..."` line, or a line of
  uv.lock that is not the `version = "..."` line of the `lado` package's own block (a
  dependency upgraded after the RC is code the RC did not test): `vX.Y.Z changes a line
  of <path> that is not its version: <line>`.

There is no way round it: a refused final is fixed by a new RC of what main has now
(section 2), then the final again. Delete the refused tag first (`git push --delete origin
vX.Y.Z`, `git tag -d vX.Y.Z`); PyPI got nothing.

Then, for every tag, an RC too, it runs `scripts/check_telemetry.py`: it asks the host of
LADO's telemetry endpoint whether it accepts LADO's project token (PostHog's `/batch/`
silently drops the events of another region's token). Nothing is published when:

- the host refuses the token: `telemetry: <host> refuses the project token: it is not a
  token of a project in this region`. `telemetry.PROJECT_TOKEN` is a token of a project in
  another region than `telemetry.ENDPOINT`: fix the pair on main, then tag again as above;
- the check cannot be made: `telemetry: cannot check the project token: <reason>` (no
  answer within 10 seconds, another HTTP status, an empty token). For a network or PostHog
  outage, rerun the job once PostHog answers; the tag stays. Run it locally the same way:
  `uv run python scripts/check_telemetry.py`.

Then, for every tag, it checks that CHANGELOG.md has the tag's release notes
(`scripts/release_notes.py <tag>`, section 7). Nothing is published, on PyPI or GitHub,
when:

- the section is missing: `release notes: CHANGELOG.md has no section "## X.Y.Z
  (unreleased)" for vX.Y.ZrcN`, or `"## X.Y.Z (<date>)" for vX.Y.Z`, with `its heading
  still says (unreleased); date it in the release commit` when the final's commit forgot
  the date;
- the section is empty: `release notes: CHANGELOG.md's section "<heading>" is empty`.

Fix CHANGELOG.md on main, delete the tag as above and push it again on the fixed commit:
PyPI got nothing, so the same version may be tagged again.

## 7. The GitHub release

After PyPI accepted the release, the workflow's job `github-release` creates the tag's
GitHub release with `gh release create` (the runner's own `gh`, the job's token with
`contents: write`, nothing else):

- its title is `LADO <version>`, its notes the tag's CHANGELOG.md section (a final's
  `## X.Y.Z (<date>)`, an RC's `## X.Y.Z (unreleased)`), each wrapped item on one line,
  then how to install or update (`lado update`, for an RC `lado update X.Y.ZrcN`, and `uv
  tool install lado==<version>`), the image (`docker pull ghcr.io/ladohq/lado:<version>`)
  and the version's page on PyPI;
- an RC is a pre-release, never the latest; a final is the latest release;
- it attaches the wheel and the sdist that `make dist` built in the job `build` and the
  job `pypi` published: the same files, passed on as the workflow artifact `dist`;
- it attaches the tag's `docker/compose.yaml` as the asset `compose.yaml`, which the
  install guide downloads from `releases/latest/download/compose.yaml` (docs/install.md,
  Docker): the newest final's file. An RC's is on its own release page.
- it attaches the Docker installers `install.sh` and `install.ps1`: the tag's
  `docker/install.sh` and `docker/install.ps1` with their version placeholder replaced by
  the tag's version (`scripts/stamp_installers.py`, a step before, which fails the job when
  a placeholder is lost or doubled). Each installs its own version's `compose.yaml` and
  image, so README's `releases/latest/download/install.sh` installs the newest final, and
  an RC's installs the RC.

Run `python3 scripts/release_notes.py <tag>` in the repository's root to see the notes
before tagging. When the job fails after PyPI took the release (GitHub down), rerun the
failed job only (`gh run rerun <id> --failed`); the PyPI job is not run again. A release
the failed job left half made is deleted first, `gh release delete <tag>` (the tag stays).
The tags before 0.37.1 have no GitHub release.

## 8. The image

Every tag, an RC too, publishes LADO's image `ghcr.io/ladohq/lado` for linux/amd64 and
linux/arm64, with the job's own token (`packages: write`, no secret). The workflow's jobs,
in order:

1. `build`: the checks of section 6 and `make dist`, the artifact `dist`; it publishes
   nothing.
2. `image`, one cell per architecture on its own runner (`ubuntu-24.04`,
   `ubuntu-24.04-arm`): one `docker buildx build` of `docker/Dockerfile` from `dist`'s
   wheel, loaded as `lado:release` for the container tests and pushed to ghcr.io by its
   digest with no tag, then the container tests (`scripts/smoke_ci.py container`, a skip
   is red; their evidence the artifact `container-<arch>`). The bytes tested are the bytes
   pushed. An untagged digest is no release: nobody pulls it by a name.
3. `pypi`, only when both cells passed: `uv publish`.
4. `image-tags`: the two digests as one image of both platforms (`docker buildx imagetools
   create`), tagged with the version (`0.39.0rc1`, `0.39.0`) and, for a final only,
   `latest`; then `imagetools inspect` checks both platforms are there. An RC never moves
   `latest`.
5. `github-release` (section 7).

A red `image` cell stops the release: nothing is published, on PyPI, ghcr.io or GitHub.
Fix the cause on main, delete the tag (section 6) and tag again. The untagged digests a
failed run pushed stay in the package; they name no version. A failure after PyPI
(`image-tags`, `github-release`) is rerun alone, `gh run rerun <id> --failed`: the
digests are the run's artifacts `digest-<arch>`, and nothing is built again.

Once, after the first RC that publishes the image: GitHub makes a new package private, and
the job's token cannot change that. An admin of ladohq opens the package `lado` in the
organisation's packages, sets its visibility to public (Package settings, Danger Zone),
and checks on a machine logged out of ghcr.io that `docker pull
ghcr.io/ladohq/lado:<that RC>` works.
