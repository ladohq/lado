Task: LAD-306

## Why

LADO 0.48.0 is a minor release: the git servers (LAD-162's epic) move the database's schema
from 40 to 43 and add the CLI command `lado git-server`, and docs/release.md (Versions) bumps
the minor for both, so the release goes through the release candidate 0.48.0rc1 (section 1:
every `X.Y.0` needs one). Before the RC's commit its release's checklist,
`docs/releases/0.48.0.md`, gets the rest of its section `## 0.48.0rc1` (section 2, step 0,
and 4.7), in a pull request of its own that the human reads; `scripts/rc_check.py` prints that
section's items after the checks of every RC. The epic started the file with the checks of
git servers that only an RC can make; the release's other changes, the upgrade to schema 43,
going back to 0.47.0 and the map of every CHANGELOG item to what covers it are still missing.
A schema migration also needs CHANGELOG.md's `### Upgrade` group (rule 1 of its items: what a
user must do when moving to this version), which `## 0.48.0 (unreleased)` lacks; it is added
in the same pull request.

Facts the section rests on (checked on `60fcc2e0`, main):

- The last final is `v0.47.0`. `git log --first-parent v0.47.0..origin/main`: the epic LAD-162
  (#319-#346: LAD-289, LAD-290, LAD-291, LAD-293, LAD-297, LAD-299, LAD-300, LAD-301,
  LAD-303, LAD-304), LAD-298 (#344), LAD-287 (#351), and changes of tests, CI, the release's
  own steps and dependencies only: LAD-296 (#343), LAD-305 (#347), LAD-302 (#348), LAD-288
  (#350), LAD-295 (#349), LAD-307 (#352), the test audit (#318, #323, #325-#328, #335-#337),
  Dependabot (#329-#334). The release's content is final: no task is added.
- `## 0.48.0 (unreleased)` holds 17 items: 10 under `### New`, 5 under `### Fixed` (one of
  LAD-293, one of LAD-298, three of LAD-287), 2 under `### Docker image`. They follow
  docs/release.md's rules for its items and stay as they are. LAD-288, LAD-295, LAD-296,
  LAD-302, LAD-305 and LAD-307 changed tests or the release's own documents only and have no
  item, by rule 6.
- `SCHEMA_VERSION` is 40 at `v0.47.0` and 43 on main (`MIGRATIONS[40]` the table
  `git_servers`, `[41]` its commit author, `[42]` the table `github_takeover`). So 4.2, 4.4
  with the user's own way back on a test home, and 4.6 all hold. The upgrade prints `lado:
  upgraded lado.db from schema 40 to 43; its backup is …/backups/lado.db.schema-40`
  (`runtime.py`); the first start after it takes the GitHub login into the list and says
  `LADO took your GitHub login (<source>) into Settings → Git servers: github.com, signed in
  as <login>.` (`github_takeover.py`); `lado doctor` then has `GitHub login: taken over from
  <source> on <day>` and, while the old login is still set, `GitHub login outside LADO:
  <names> set but not used: github.com takes its token from Settings → Git servers`
  (`doctor.py`).
- Going back: `lado update 0.47.0` warns `lado: WARNING: LADO 0.47.0 knows lado.db up to schema
  40; lado.db has schema 43.` with `Everything LADO recorded since then is lost: sessions, runs,
  gates, messages, projects, model servers, models, default models, git servers.` and, when
  their folders are left, `Git server tokens stay on disk; remove them when you no longer need
  them:` with each folder under `~/.lado/git-servers/` (`self_update.py`); after the install
  `Restored lado.db from … (schema 40)`. `rc_check.py rollback`'s plan names the sessions it
  will not start again on `- not started again, not in the copy: <names>` (LAD-288 made 4.4
  quote this line, not the update's `Sessions not in that copy are not started again:`).
- The image changed since `v0.47.0` (glab 1.130.0 added, the host's ssh agent gone), and so did
  `docker/install.sh` (it no longer asks for the ssh agent): 4.5's installers are run; the file's
  first paragraph already says so.
- The exact lines the new checks quote are the code's: the kit's refusal `kit "sdlc" expects
  skill "tracker", which no kit of the session provides: add a kit that provides it to the
  session` (`kits.py`); Claude Code's mode `Let Claude judge the risk` with `Checks each action
  for risk, runs what it judges safe and stops the rest. …` (`providers/claude.py`); Where's
  `Choose a place` (`web/src/Launch.tsx`).
- What nothing automatic covers: Where after an early close on a slow network in Firefox and
  Safari (LAD-287 was found in Firefox; the browser tests run Chromium only, with the recent
  places held back by the test); an open ⓘ tip or menu when a real phone is turned (vitest
  only); a kit chip's × under a finger on a real phone while Where changes (the browser's
  phone test presses it at a phone's size in Chromium).

The human approved this list of hand checks (answer #7770, all as recommended): Where after an
early close in Firefox and Safari on the Mac with a slowed network, both a must, with a chosen
place that stays chosen; the tip, the menu and the kit chip on a real iPhone in Safari; Claude
Code's modes in the window and `lado start --permission-mode manual`; one Upgrade item, as
0.47.0's.

## What Changes

### `docs/releases/0.48.0.md`

Its form is 4.7's. The text below is the whole file as approved: the epic's items stay word for
word, under the same headings; the first paragraph's last two sentences give way to the RC's
paragraph; new groups and items are added. The developer writes it as it stands and changes an
exact line only where the code says otherwise (tasks 1.2):

````markdown
# LADO 0.48.0: the release's checks

The last final is 0.47.0. The database's schema moves from 40 to 43, so 4.2, 4.4 (with the
user's own way back) and 4.6 of docs/release.md all hold. The image changed (glab added, the
host's ssh agent gone) and so did `docker/install.sh`, so 4.5's installers are run. Those
checks of every RC are not repeated here; this file holds what 0.48.0 itself needs: git
servers on a real company GitLab in Docker, a certificate given by stdin, the live tests'
push through a saved server, the GitHub login taken into Settings on your own LADO, New
session's fixes in Safari and Firefox and on a phone, and what going back to 0.47.0 loses.

## 0.48.0rc1

The RC: tag `v0.48.0rc1`, commit `<filled in at the RC>`; `live.yml` on it is green (run
`<filled in at the RC>`). The exact lines below are the code's; where the code has no fixed
text, the line says what to look for.

### Before you start

- A Mac with your LADO 0.47.0 and sessions running, its GitHub login as agents use it
  (`GH_TOKEN`, or `gh auth login`), Docker Desktop, `uv`, `tmux`, `git`.
- Safari and Firefox on the Mac; a real iPhone on the Mac's Wi-Fi with Safari.
- The kit `sdlc` installed (`lado kit list`): alone in a session, without a tracker kit, it
  lacks its skill `tracker`.
- For the company GitLab: the company's VPN on, and an account on the company GitLab
  that may make a personal access token with the scope `api`; a second token you can revoke,
  and one that expires (or has expired).
- A test repository on the company GitLab, and one on github.com, both of your own.
- The company's root authority as a PEM file from IT, if its GitLab is signed by the
  company's own authority.

### Your own LADO after the upgrade (4.2)

- [ ] **The schema moves to 43.** 4.2's `upgrade` prints the migration and keeps the copy.
  - `lado: upgraded lado.db from schema 40 to 43; its backup is
    /Users/<you>/.lado/backups/lado.db.schema-40`, and `Kept a copy of LADO 0.47.0's
    database: /Users/<you>/.lado-rc/lado.db.0.47.0 (for rollback)`.
- [ ] **Your GitHub login is taken into Settings once.** The update's resumed sessions, or the first `lado` command after it.
  - `LADO took your GitHub login (<GH_TOKEN of your shell, or gh's login>) into Settings →
    Git servers: github.com, signed in as <you>.`; Settings → Git servers shows github.com.
  - `lado doctor`: `GitHub login: taken over from <source> on <today>`, and, while that
    login is still set, `GitHub login outside LADO: <source> set but not used: github.com
    takes its token from Settings → Git servers`.
  - A resumed agent on a github.com repository pushes and runs `gh` as before.

### New session's fixes

In Safari and Firefox on the Mac, with the network slowed (Firefox: Developer tools →
Network → Throttling, `Regular 3G`; Safari: Develop → Network Conditions), so the recent
places come late.

- [ ] **Where keeps the last place after an early close.** Open New session, type a task, close it (×, Esc or Cancel) before Where shows a place, open it again.
  - Where shows the last place, not `Choose a place`, and the task you typed is there; so
    too at each later opening, without a reload.
- [ ] **A place you chose stays chosen.** Open New session, choose Where → New empty folder at once, close it before the recent places come, open it again.
  - Where is still New empty folder, not the last place.

Without a slowed network:

- [ ] **The kit advice speaks of the window.** New session on any folder, Kits `sdlc` only, Start.
  - Refused with `kit "sdlc" expects skill "tracker", which no kit of the session provides:
    add a kit that provides it to the session`; no `--kit` in the text.
- [ ] **Claude Code's modes in words.** New session, Agent Claude Code, Permissions.
  - A row `Let Claude judge the risk` with `Checks each action for risk, runs what it judges
    safe and stops the rest. …`; no row `auto` or `manual`.
  - `lado start <a test repository> --name rc-mode --provider claude --permission-mode
    manual` starts; the session's head shows `Asks before changes`. Stop it.

On the iPhone in Safari, by LADO's link for the phone:

- [ ] **A kit chip stays put while Where changes.** New session, add a kit, then change Where to another place and at once tap the kit chip's ×.
  - The chip does not lose its version or move, and the × removes it on the first tap.
- [ ] **An open tip or menu follows its button.** Settings → Git servers: open an ⓘ tip, turn the phone; then a row's menu, turn it back.
  - The tip and the menu stay by their button after each turn; so too on the Mac when the
    window is resized with one open.

### A company GitLab in Docker

Run the RC's image as 4.5 says (a temporary folder, a test workspace, a port of its own).

- [ ] **Check on the company GitLab is green.** Settings → Git servers → Add server with its address and the `api` token.
  - The line `Works: GitLab, signed in as <you>, may clone and push.`
  - When a company authority signs the server: the card "Trust this server?" with who signed
    it, until when it is valid and its SHA-256; Trust, and Check is green. Refuse once
    first: nothing is saved, and the next Check asks again.
- [ ] **An agent clones, commits, pushes over https and opens a merge request.** A session on the company test repository, its `git@…` address too.
  - The commit carries the server's commit author when one is set (Commit author on the
    server's row), else LADO's.
  - The push goes over https with the saved token, not an ssh key: the agent runs
    `GIT_SSH_COMMAND=false git push …`, and it works.
  - The agent is told the line naming the server's kind and `glab`; `glab mr create` opens
    the merge request; `glab auth status` says logged in, with glab's note `No token found`.
- [ ] **github.com works as before.** An agent on the github.com test repository clones, pushes and opens a pull request with `gh`.
- [ ] **A revoked and an expired token are named.** Check with each: `GitLab refused the token: it expired or was revoked`, and Replace token on the row.
- [ ] **A token without `api` is named.** Check, Add server and Replace token with a token without `api` end with `glab cannot open merge requests: the token lacks api`; `lado doctor` warns.
- [ ] **A certificate by stdin in Docker.** `docker compose exec -T lado lado git-server certificate <address> - < <file>` with the company's PEM file.
  - Prints `Trusted <name> for <address>.`, then the check's line; `lado git-server list`
    shows the certificate `until <date>`; clone and push work. Never run by anyone before.
- [ ] **When the company GitLab has a public certificate.** Then "Trust this server?" cannot be met there: run the integration tests' case by hand in the image instead, a local https git server under a test authority, Check asks "Trust this server?", Trust makes clone and push work.

### Live tests

- [ ] **`live.yml` on the RC pushes through a saved server.** Its run on the RC is green for Claude Code and Codex, the case of an agent with a model pushing through a server saved in the list included (the agents' environment changed: tokens, author, certificate and glab from the list).

### Platforms not checked

- [ ] **Apple's git (LibreSSL) and GnuTLS with an intermediate authority.** Natively on the Mac with Apple's `/usr/bin/git`, and on a Linux with a GnuTLS git, if at hand: a server signed by an intermediate authority, trusted by Check; clone and push work. Not checked before; say "not checked" if no such server is at hand.

### Going back to 0.47.0

Going back to 0.47.0 loses everything recorded on the RC: sessions, runs, gates, messages,
projects, model servers, models, default models and git servers made or changed since 4.2's
upgrade. The git servers' tokens stay on disk until removed.

- [ ] **The rollback's plan and warning name what is lost.** 4.4's `rollback`: read its plan before `Roll back? [y/N]`, then `lado update 0.47.0`'s warning before `y`.
  - The plan names the sessions started on the RC after `- not started again, not in the
    copy:`.
  - `lado: WARNING: LADO 0.47.0 knows lado.db up to schema 40; lado.db has schema 43.` and
    `… Everything LADO recorded since then is lost: sessions, runs, gates, messages,
    projects, model servers, models, default models, git servers.`, then `Git server tokens
    stay on disk; remove them when you no longer need them:` with the folder of github.com's
    token under `~/.lado/git-servers/`.
- [ ] **0.47.0 starts on the database of before.** After the rollback.
  - `Restored lado.db from …/lado.db.schema-40 (schema 40)`; `lado ls` lists the sessions of
    before 4.2 on 0.47.0, and their agents push to github.com with your old GitHub login.
- [ ] **The image's way back keeps the new `compose.yaml` and loses the host's ssh agent.** In 4.6, after going back to 0.47.0 with the new `compose.yaml` and a `LADO_SSH_AGENT` in `.env`: no ssh agent in the container.
  - With `cp compose.yaml.bak compose.yaml` before `docker compose up -d`, as docs/install.md
    "Go back to the version before" says, 0.47.0's ssh agent is back.
- [ ] **Going back forgets the git servers; the GitHub login works the old way.** 4.4's user's own way back, on a test home with a github.com entry taken over from `GH_TOKEN`.
  - `lado update 0.47.0` warns that the git servers are lost and names the folder of their
    tokens; on 0.47.0 the agents get `GH_TOKEN` as before; the tokens stay unused in
    `~/.lado/git-servers/` until removed.

### What covers the CHANGELOG's items

Each of the 18 items of `## 0.48.0 (unreleased)` at the RC's commit, with what covers it. An
item with a check above is tried there; the browser tests run Chromium only.

New:

1. Your own GitLab, GitHub or GitHub Enterprise server: the company GitLab's checks (unit
   `tests/test_git_servers.py`, `tests/test_cli_git_server.py`, `tests/test_git_kinds.py`,
   `tests/test_git_credential.py`; integration `tests/integration/test_git_server_access.py`;
   the browser `tests/ui/test_git_servers_section.py`). A real GitHub Enterprise: not checked,
   nobody has one at hand.
2. github.com in Settings → Git servers: 4.2's takeover and github.com's check (unit
   `tests/test_github_takeover.py`, `tests/test_doctor.py`; integration
   `tests/integration/test_github_login_takeover.py`; the image `tests/container/test_access.py`).
3. Your commit name and email per git server: the company GitLab's agent check (unit
   `tests/test_runtime_git_servers.py`; integration `tests/integration/test_git_server_author.py`;
   smoke `tests/smoke/test_codex_git_server.py`).
4. Check a git server again: the revoked, expired and `api` tokens' checks (unit
   `tests/test_git_servers.py`, `tests/test_server_git_servers.py`; vitest
   `web/src/GitServers.test.tsx`; the browser `tests/ui/test_git_servers_section.py`).
5. `lado doctor` checks your git servers: the `api` token's check (unit `tests/test_doctor.py`).
6. A failed clone says which git server to check: nothing by hand (unit `tests/test_clone.py`,
   `tests/test_server_clones.py`; integration `tests/integration/test_git_server_access.py`; the
   browser `tests/ui/test_launch.py`).
7. Trust your company's git server: the trust card and the certificate by stdin (unit
   `tests/test_git_certificates.py`; integration
   `tests/integration/test_git_server_certificate.py`; the browser
   `tests/ui/test_git_servers_certificate.py`); Apple's git and GnuTLS above.
8. Agents open GitLab merge requests with glab: the merge request's check (integration
   `tests/integration/test_git_server_host_tool.py`; the image `tests/container/test_glab.py`;
   live `tests/live/test_live.py` on the RC).
9. Agents know their repository's server: the agent's line in the company GitLab's check
   (unit `tests/test_runtime_git_servers.py`, `tests/test_doctor.py`; integration
   `tests/integration/test_git_server_host_tool.py`).
10. A guide to connecting your git server: read at its merge (unit
    `tests/test_git_servers_guide.py`, its links and quotes).

Fixed:

11. An open tip or menu follows its button: the phone's check (vitest
    `web/src/InfoTip.test.tsx`, `web/src/Menu.test.tsx`).
12. A kit chip stays put when you change Where: the phone's check (vitest
    `web/src/Launch.test.tsx`; the browser `tests/ui/test_launch.py`).
13. Where shows the last place after an early close: the slowed network's checks (vitest
    `web/src/Launch.test.tsx`; the browser `tests/ui/test_launch.py`).
14. The kit advice fits New session: the kit advice's check (unit `tests/test_kits.py`,
    `tests/test_cli.py`; the browser `tests/ui/test_launch.py`).
15. Claude Code's auto mode in words: the modes' check (unit `tests/test_providers.py`,
    `tests/test_runtime.py`; the browser `tests/ui/test_launch.py`).

Docker image:

16. No ssh in LADO's container: the image's way back above, 4.5's installer (unit
    `tests/test_docker.py`, `tests/test_install_sh.py`; the image `tests/container/test_access.py`,
    `tests/container/test_image.py`).
17. glab in LADO's image: the merge request's check (the image `tests/container/test_glab.py`).

Upgrade:

18. Running sessions restart with the update: 4.2 and 4.6 (unit `tests/test_self_update.py`;
    integration `tests/integration/test_update_process.py`; the image `tests/container/`).

The changes of tests, CI and the release's own steps since 0.47.0 have no item and no check
here: the smoke's waits (Kilo's and Codex's lists of models), the clone-cancel and
multiline-paste tests' waits, the session screens test's wait for the feed, the container
tests' cleanup after an interruption, and 4.4's wording of the sessions not started again,
which the rollback's item above follows. CI on the RC's commit runs them.
````

The two placeholders of the RC's paragraph (`<filled in at the RC>`) stay in this pull request:
the commit and `live.yml`'s run exist only after it is merged, and are filled in with the RC.

### CHANGELOG.md, `## 0.48.0 (unreleased)`

After `### Docker image`, a new group (0.47.0's item, word for word):

```markdown
### Upgrade

- **Running sessions restart with the update.** `lado update` stops and resumes them; after
  an update made another way, restart them yourself.
```

### `tests/test_rc_check.py`

The test over the repository's real checklists (`test_the_repositorys_own_checklists_have_no_warning`)
also checks `0.48.0rc1` against `docs/releases/0.48.0.md`: no warning line, the every-RC lines
first, and the RC's own items after them.

### After the merge: the RC (no file of this pull request)

On main with this pull request merged, as docs/release.md section 2, steps 1-4:
`uv version 0.48.0rc1`, a commit `Release candidate 0.48.0rc1` of `pyproject.toml` and `uv.lock`
alone pushed to main, CI and the smoke green on it, `gh workflow run live.yml` on that commit with
every cell green, then the tag `v0.48.0rc1` pushed; each push with the human's yes. The session's
lead does it with the human; the freeze starts with the RC.

## Scope

- `docs/releases/0.48.0.md` (the RC's section completed), CHANGELOG.md's `### Upgrade` group,
  and the real-file test of `tests/test_rc_check.py`.

## Out of scope

- The 17 items already under `## 0.48.0 (unreleased)`: they follow docs/release.md's rules.
- The version bump, the RC's commit, `live.yml` and the tag: the session's lead does them with
  the human after the merge; the integrator never bumps the version or tags.
- `docs/release.md` and `scripts/rc_check.py`: no rule of the release changes, so the change has
  no delta.
- Hand checks of the test-only tasks (LAD-288's container cleanup, LAD-295, LAD-296, LAD-302,
  LAD-305, LAD-307): users see nothing of them, and CI on the RC runs them.
- A real GitHub Enterprise server: nobody has one at hand; item 1 says so.
- Moving the task to review or done: this pull request is not the task's last; LAD-306 stays in
  progress until the final 0.48.0, and the integrator leaves its status, label and field as
  they are.

## Impact

- Docs, CHANGELOG and one unit test; no code, API, MCP, CLI or schema change. The release it
  prepares is a minor (0.48.0: the schema moves to 43, a new CLI command).
