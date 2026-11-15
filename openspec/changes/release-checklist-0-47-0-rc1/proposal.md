Task: LAD-286

## Why

LADO 0.47.0 is a minor release: LAD-234 moves the database's schema from 39 to 40, and
docs/release.md (Versions) bumps the minor for a schema migration, so the release goes through
the release candidate 0.47.0rc1 (section 1: every `X.Y.0` needs one). Before the RC's commit its
release's checklist, `docs/releases/0.47.0.md`, gets the section `## 0.47.0rc1` (section 2, step
0, and 4.7), in a pull request of its own that the human reads; `scripts/rc_check.py` prints that
section's items after the checks of every RC. A schema migration also needs CHANGELOG.md's
`### Upgrade` group (rule 1 of its items: what a user must do when moving to this version), which
`## 0.47.0 (unreleased)` lacks; it is added in the same pull request.

Facts the section rests on (checked on `511d0c3d`, main):

- The last final is `v0.46.2`. `git log --first-parent v0.46.2..origin/main`: LAD-209 (#315),
  LAD-234 (#305), LAD-281 (#301), LAD-173 (#308), LAD-105 (#311), LAD-170 (#310), and changes of
  tests, CI and the smoke only (#295-#300, #302-#304, #306, #307, #309, #312-#314).
- `## 0.47.0 (unreleased)` holds 6 items, all under `### Fixed`, one per user-visible task above;
  they already follow docs/release.md's rules for its items (a bold title, at most three lines, the
  user's words, no task key) and stay as they are.
- `SCHEMA_VERSION` is 39 at `v0.46.2` and 40 on main. `MIGRATIONS[39]` adds the column
  `messages.read_reminded` and marks every message already there reminded, so no message of
  before the update is ever reminded. So 4.2, 4.4 with the user's own way back on a test home, and
  4.6 all hold. The upgrade prints `lado: upgraded lado.db from schema 39 to 40; its backup is
  …/backups/lado.db.schema-39` (`runtime.py`).
- Going back: `lado update 0.46.2` learns schema 39 from 0.46.2's wheel, warns `lado: WARNING:
  LADO 0.46.2 knows lado.db up to schema 39; lado.db has schema 40.` with `Everything LADO
  recorded since then is lost: sessions, runs, gates, messages, projects, model servers, models,
  default models.`, names the running sessions the copy lacks (`Sessions not in that copy are not
  started again: …`), and after the install says `Restored lado.db from … (schema 39)`
  (`self_update.py`). Nothing of 0.47.0 is kept outside `lado.db`.
- Since `v0.46.2` only a comment of `docker/Dockerfile` changed; `docker/install.sh` and
  `docker/install.ps1` did not: 4.5's installers are not run.
- The exact lines the checks quote are the code's: the reminder `hooks.UNREAD_REMINDER` (`you
  have not read message #<id> from <sender>: call read_messages to get its text; if it asks
  nothing of you, do nothing.`); Claude Code's login refusals (`providers/claude.py`); the kit's
  refusal `kit "sdlc" expects skill "tracker", which no kit of the session provides: …`
  (`kits.py`); `lado: removed <folder>, which this start made` (`cli.py`).
- What nothing automatic covers: the New session window on a phone's width in Safari and
  Firefox (the browser tests run Chromium only, at a phone's size); Firefox on iOS runs WebKit,
  so Firefox's own engine, Gecko, is tried in Firefox on the Mac at 390 px (the residual risk
  of LAD-209's review) and on Android if at hand; its focus in Safari and Firefox;
  Claude Code's real login sheet (the browser test runs a fake provider); an agent on a weak model
  that skips a message's text (the live tests run strong models since LAD-273). LAD-173's live
  test `test_a_worker_commits_unless_its_task_says_not_to` already passed on all four CLIs in
  `live.yml` on main after LAD-285 (#312; runs 43642033390 and 43642039014), and `live.yml` on
  the RC runs it again.

The human approved the task's draft (LAD-286) with this list of hand checks, and the draft of
this change (answer #6947, through the supervisor): the phone's checks on the iPhone in Safari
and in Firefox on the Mac at 390 px, both a must, Android's Firefox if at hand; the reminder on a
weak OpenCode model with a two-line message; the login check with the human's own token; one
Upgrade item, as 0.45.0's.

## What Changes

### `docs/releases/0.47.0.md`, a new file

Its form is 4.7's. The text below is the file as approved; the developer writes it as it
stands and changes an exact line only where the code says otherwise (tasks 1.2):

````markdown
# LADO 0.47.0: the release's checks

The last final is 0.46.2. The database's schema moves from 39 to 40, so 4.2, 4.4 (with the
user's own way back) and 4.6 of docs/release.md all hold. Those checks of every RC are not
repeated here; this file holds what 0.47.0 itself needs: the New session window at a
phone's width in Safari and Firefox, its focus, a refused start that leaves no folder,
Claude Code's login check, LADO's reminder to read a message, and going back to 0.46.2 over
the schema.
Only a comment of the image's `Dockerfile` changed since v0.46.2, and neither
`docker/install.sh` nor `docker/install.ps1`, so 4.5's installers are not run.

## 0.47.0rc1

The RC: tag `v0.47.0rc1`, commit `<filled in at the RC>`; `live.yml` on it is green (run
`<filled in at the RC>`). The exact lines below are the code's; where the code has no fixed
text, the line says what to look for.

### Before you start

- A Mac with your LADO 0.46.2 and sessions running, Docker Desktop, `uv`, `tmux`, `git`.
- Safari and Firefox on the Mac; a real iPhone on the Mac's Wi-Fi with Safari (Firefox there
  too, if at hand); an Android phone with Firefox, if at hand.
- The CLIs on the Mac: Claude Code logged in (with the human's yes); OpenCode needs no login
  for its free models.
- A model server saved in Settings → Model servers with a model of a short name (e.g.
  «Локальная Qwen»), and one that does not answer (e.g. `localhost:1239`) with a model.
- The kit `sdlc` installed (`lado kit list`): alone in a session, without a tracker kit, it
  lacks its skill `tracker`.

### Your own LADO after the upgrade (4.2)

- [ ] **The schema moves to 40.** 4.2's `upgrade` prints the migration and keeps the copy.
  - `lado: upgraded lado.db from schema 39 to 40; its backup is
    /Users/<you>/.lado/backups/lado.db.schema-39`, and `Kept a copy of LADO 0.46.2's
    database: /Users/<you>/.lado-rc/lado.db.0.46.2 (for rollback)`.
- [ ] **Old messages get no reminder.** The resumed sessions' agents get no `[from lado] you have not read …` line for a message of before the update.

### The New session window on a phone

In three places, each a must unless said otherwise: on the iPhone in Safari, by LADO's link
for the phone; in Firefox on the Mac, in Responsive Design Mode (Tools → Browser Tools →
Responsive Design Mode) at 390 × 844, which is Firefox's own engine, Gecko; and, if at hand,
in Firefox on an Android phone (Gecko too). Firefox on the iPhone runs Safari's engine,
WebKit, so it adds nothing to Safari there and may be skipped. New session opens as a
full-screen sheet.

- [ ] **Every field and button is easy to tap.** Agent, Folder, Folder name, Model and each button of a note under Model are as tall as a fingertip (44 px).
  - A kit chip's × hits on the first tap, and `+ Add kit` too; Name on Task's row stays
    small.
- [ ] **A short model name stays whole.** Model: the short-named model of your server.
  - The name shows whole beside `default`; the server's name gives way first, down to its
    icon.
- [ ] **A server that does not answer is marked as refused.** Model: the model of the server that does not answer.
  - The field's server mark shows the round «!» of the refusal under it, not ⚠; the list's
    rows keep ⚠.
  - Start: the refusal under Model and `To start: fix the model` say it, the focus goes to
    Model, and no `Not started: …` line stands above the buttons.

### The New session window's focus

In Safari and Firefox on the Mac, with the network slowed (Firefox: Developer tools →
Network → Throttling, `Regular 3G`; Safari: Develop → Network Conditions), so the recent
places come late.

- [ ] **A field you moved to keeps the focus.** Open New session and at once click Name (or press Tab to a button), then type.
  - When the recent places come, the focus and what you typed stay there; Where shows the
    last place.
- [ ] **An untouched window still starts in Task.** Open New session and touch nothing.
  - When the recent places come, the focus is in Task.

### A refused new session leaves no folder

- [ ] **New empty folder makes nothing when the kit lacks a skill.** New session → Where → New empty folder `rc-check-sdlc`, Kits `sdlc` only, Create and start.
  - Refused with `kit "sdlc" expects skill "tracker", which no kit of the session provides:
    …`; the window stays on New empty folder with Team open, and `ls ~/workspace` (or your
    workspace) has no `rc-check-sdlc`.
- [ ] **`lado start --new` makes nothing either.** `lado start --new ~/workspace/rc-check-cli --kit sdlc` (your workspace).
  - It is refused with the same line, and `~/workspace/rc-check-cli` does not exist.

### Claude Code's login check

Settings → Agent CLIs → Claude Code → Log in, on your own LADO. A refused value saves nothing:
your login stays as it was.

- [ ] **A value that is no token is refused.** Subscription — Claude Pro or Max, paste `hello`.
  - `This is not a Claude subscription token: a token starts with sk-ant-oat01-. Run claude
    setup-token and paste the whole token it prints.`; the sheet stays open.
- [ ] **A key of the other kind names the right choice.** Subscription, paste a value starting with `sk-ant-api03-`; then Pay per use, one starting with `sk-ant-oat01-`.
  - `This is an API key (sk-ant-api03-…), not a subscription token: to pay per use with it,
    choose “Pay per use — API billing”.`
  - `This is a subscription token (sk-ant-oat01-…), not an API key: to use your
    subscription, choose “Subscription — Claude Pro or Max”.`
- [ ] **A value with a space inside is refused.** Subscription, paste `sk-ant-oat01-ab cd`.
  - `This token or key has characters it cannot have (a space or a line break?): copy it
    again as one line.`
- [ ] **Your real token with a line break after it logs in.** Subscription, paste your own token followed by a line break.
  - Claude Code shows as logged in, and a new session of it answers.

### The reminder to read a message

A new session of the built-in supervisor on a test repository, OpenCode on one of its free
weak models (e.g. Qwen3-Coder-Next or Nemotron). Watch its terminal.

- [ ] **An agent that skips a message's text is told once.** Write a message of two lines: a short first line, and a question on the second (try a few until the model answers only the first line).
  - Its terminal then gets one line `[from lado] you have not read message #<id> from human:
    call read_messages to get its text; if it asks nothing of you, do nothing.`, and no
    second one for that message.
- [ ] **A one-line message gets no reminder.** Write a message of one line.
  - No `you have not read` line follows it.

### Going back (4.4)

Going back to 0.46.2 loses everything recorded on the RC: sessions, runs, gates, messages,
projects, model servers, models and default models made or changed since 4.2's upgrade.

- [ ] **The warning of going back names what is lost.** 4.4's `rollback`: read `lado update 0.46.2`'s warning before `y`.
  - `lado: WARNING: LADO 0.46.2 knows lado.db up to schema 39; lado.db has schema 40.` and
    `… Everything LADO recorded since then is lost: sessions, runs, gates, messages,
    projects, model servers, models, default models.`; the sessions started on the RC are
    named after `Sessions not in that copy are not started again:`.
- [ ] **0.46.2 starts on the database of before.** After the rollback.
  - `Restored lado.db from …/lado.db.schema-39 (schema 39)`; `lado ls` lists the sessions of
    before 4.2 on 0.46.2, and the UI opens their chats.
- [ ] **The user's own way back.** On the test home of 4.4, `X.Y.Z` 0.46.2.
  - `lado update 0.46.2` warns as above before it asks, and `lado ls` lists `back` on
    0.46.2.

### What covers the CHANGELOG's items

Each of the 7 items of `## 0.47.0 (unreleased)` at the RC's commit, with what covers it. An
item with a check above is tried there; the browser tests run Chromium only.

Fixed:

1. New session fits a phone: the phone's checks (vitest `web/src/Launch.test.tsx`,
   `web/src/ModelPicker.test.tsx`; the browser `tests/ui/test_launch.py`,
   `tests/ui/test_launch_model.py`).
2. An agent that skips a message's text is told so once: the reminder's checks (unit
   `tests/test_state.py`, `tests/test_runtime.py`; integration
   `tests/integration/test_unread_reminder.py`).
3. New session no longer takes the focus away from you: the focus checks (the browser
   `tests/ui/test_launch.py`).
4. A worker told not to commit leaves its work uncommitted: nothing by hand (unit
   `tests/test_runtime.py`; live `tests/live/test_live.py`'s worker commit test on every
   provider, green in `live.yml` on main since LAD-285, runs 43642033390 and 43642039014,
   and run again on this RC).
5. A refused new session leaves no empty folder behind: the refused session's checks (unit
   `tests/test_runtime.py`, `tests/test_scratch.py`, `tests/test_cli.py`,
   `tests/test_server_launch.py`; vitest `web/src/Launch.test.tsx`).
6. Claude Code's login checks what you paste: the login checks (unit
   `tests/test_providers.py`, `tests/test_logins.py`, `tests/test_server_providers.py`;
   vitest `web/src/LoginSheet.test.tsx`).

Upgrade:

7. Running sessions restart with the update: 4.2 and 4.6 (unit `tests/test_self_update.py`;
   the image `tests/container/`).
````

The two placeholders of the RC's paragraph (`<filled in at the RC>`) stay in this pull request:
the commit and `live.yml`'s run exist only after it is merged, and are filled in with the RC.

### CHANGELOG.md, `## 0.47.0 (unreleased)`

After `### Fixed`, a new group (0.45.0's item, word for word):

```markdown
### Upgrade

- **Running sessions restart with the update.** `lado update` stops and resumes them; after
  an update made another way, restart them yourself.
```

### `tests/test_rc_check.py`

The test over the repository's real checklists (`test_the_repositorys_own_checklists_have_no_warning`)
also checks `0.47.0rc1` against `docs/releases/0.47.0.md`: no warning line, the every-RC lines
first, and the RC's own items after them.

### After the merge: the RC (no file of this pull request)

On main with this pull request merged, as docs/release.md section 2, steps 1-4:
`uv version 0.47.0rc1`, a commit `Release candidate 0.47.0rc1` of `pyproject.toml` and `uv.lock`
alone pushed to main, CI and the smoke green on it, `gh workflow run live.yml` on that commit with
every cell green, then the tag `v0.47.0rc1` pushed; each push with the human's yes. The session's
lead does it with the human; the freeze starts with the RC.

## Scope

- `docs/releases/0.47.0.md` (new), CHANGELOG.md's `### Upgrade` group, and the real-file test of
  `tests/test_rc_check.py`.

## Out of scope

- The six `### Fixed` items: they already follow docs/release.md's rules.
- The version bump, the RC's commit, `live.yml` and the tag: the session's lead does them with
  the human after the merge; the integrator never bumps the version or tags.
- `docs/release.md` and `scripts/rc_check.py`: no rule of the release changes, so the change has
  no delta.
- A hand check of LAD-173 (a worker told not to commit): its live test runs on every provider in
  `live.yml` on the RC.
- 4.5's installers: neither installer changed since v0.46.2.
- Moving the task to review: this pull request is not the task's last; LAD-286 stays in progress
  until the final 0.47.0.

## Impact

- Docs, CHANGELOG and one unit test; no code, API, MCP, CLI or schema change. The release it
  prepares is a minor (0.47.0: the schema moves to 40).
