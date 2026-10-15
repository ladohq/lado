# Docker install of LADO: review of research LAD-52 and the task plan

Based on: [docker-install.md](docker-install.md), the prototype
([docker-install/Dockerfile](docker-install/Dockerfile),
[docker-install/compose.yaml](docker-install/compose.yaml)) and the review report of
pull request #33.

How the work goes (the human's decision, 2026-10-14): this plan lives beside the
research; the tracker gets only the next task; after each task the plan is revisited.
Every task merges straight into `main`, with no epic.

## 0. Decisions taken

| Question | Decision |
|---|---|
| Platforms of the first version | Mac and Linux. Windows is a manual check with a speed measurement (T11); until then it is not called supported |
| Image | One image with Claude Code only (~1 GB instead of 2.5). The other CLIs later, as tasks of their own. Changed 2026-10-15 (the human): one image with all four CLIs, from T7 on (615 MB as built in LAD-73, not the prototype's 2.5 GB); mixed sessions (a worker on another CLI than the supervisor) work in one container |
| Project path | The host's path |
| Codex | Not in the first version (follows from an image with Claude only). Changed 2026-10-15: in the image from T7, as a CLI installed; its ChatGPT login reaching the agents is T15, later (the human: no Codex debugging now) |
| Epic | None; each task goes straight into `main` |

## 1. What the research showed (short)

- The prototype works on a Mac (Apple silicon, Docker Desktop): one image with LADO and
  four agent CLIs, the UI opens in the host's browser, sessions, workers, Claude Code's
  login, a restart and a recreation of the container work, and the project's toolchain
  through mise (H1-H3, H5-H7, H9).
- Verdict: make Docker the **main** way to install LADO, for the agents' isolation from the
  user's machine; a one-command install script is the fallback.
- 11 tasks proposed; the central one, "Docker image for LADO", is of size L.

## 2. Review: what is good

1. **Checked by hand, with evidence.** Each check has the commands' output; the pull
   request's review held the claims about LADO against the code.
2. **The difficulties are taken apart honestly**: each has its cause, what the user sees,
   and options with their cost (16 items).
3. **Real defects of LADO found**, useful without Docker too: `lado update` kills itself in
   a container; finish fails on a forgotten git worktree (already in BACKLOG); Codex's
   login does not reach the agents.
4. **The CLIs' versions are pinned** to those LADO is tested with (`TESTED_VERSION`): the
   right choice.

## 3. Review: gaps and risks

### 3.1 Not checked, but bearing on the verdict

| What | Why it matters | How it is closed |
|---|---|---|
| **Windows**: from documentation only | The gain is largest there (it replaces the manual WSL setup), and so is the slow host folder | T11, a manual check with a measurement (section 5) |
| **A Linux host**: not checked | File owner (uid), the ssh socket, `host-gateway` | In CI: GitHub's runner has uid 1001, not 1000, a natural test (T5) |
| **amd64 not built** | Intel Macs, most Linux and Windows | amd64 and arm64 builds in CI from the first step (T3) |
| **Codex** (H4) | No subscription; its login does not reach the agents either | Decided: not in the first version |
| **`LADO_AGENT_ENV=inherit` in a container** not run | It is the proposed way to pass the token | T10 |
| **An agent installs a tool through mise by itself** | Without it "thin image + mise" is a hypothesis | T9 |

### 3.2 Contradictions and debatable points in the proposals

1. **Project path.** The research recommends the host's path (5.3), while its tasks 2 and
   4 name `/projects`. Decided: the host's path; the UI's folder picker starts in that
   folder.
2. **Stopping the container versus resuming.** "stop runs `lado stop --all`" and "resume
   sessions at start" pull in different directions: `lado stop` forgets workers, and LADO
   does not remember which sessions ran. Designed together (T6).
3. **ssh through `group_add: ["0"]`** puts the agents' user in the root group. It works,
   but it is an extra right inside the isolation; better give access to the socket only
   (T10).
4. **`LADO_AGENT_ENV=inherit`** gives the agents the container's whole environment, every
   secret of compose. A separate file the login shell reads is safer for tokens (T10).
5. **Image update and the database.** A new image with a new schema of `lado.db` on an old
   volume: the UI server does not migrate the database (it answers 503), the CLI does.
   Check that a container started from a new image migrates the database with a backup;
   the research does not cover it (T6).
6. **Size 2.46 GB**, 1.8 GB of which are the four CLIs. Decided: the first image with
   Claude Code only.

### 3.3 The main remark on the plan

The task "Docker image for LADO" (L) is eight different jobs in one: mise, paths, uid,
stopping, tokens, two architectures, GHCR, documentation and a smoke test in CI. It cannot
be checked in one step. Below it is split so that **after each task there is something to
run and see**, and so that a working image in CI (a "walking skeleton") comes as early as
possible and is then improved.

## 4. Plan: small checkable steps

Goal: the user installs Docker, starts LADO with one command and uses it fully.

Size: S, up to a day; M, a few days. "Check" is how the human or CI makes sure the step
is done.

### Stage 0. LADO knows it is in a container (LADO's code, no image)

**T1. The "LADO in a container" sign, and no `lado update` there** (S; LAD-59, done:
pull request #40)
The variable `LADO_CONTAINER` (the image sets it). `lado update` and the UI's update
button refuse and name the way: `docker compose pull && docker compose up -d` (since
T7 LADO names only the new version's image and no command; the documentation gives the
commands, T8).
`lado doctor` and the System panel show "in a container". The same task puts this plan
into the repository beside the research.
Check: unit tests; in the prototype `lado update` no longer kills the container.

**T2. The UI server's links and warning in a container** (S; LAD-63, done: pull request
#45)
With `LADO_CONTAINER` there is no false "open to other machines", no dead link
`http://lado:8765`, and the link for the host is printed. The folder picker starts in the
projects folder (a variable).
Check: unit tests; the output of `lado ui --no-open` in the prototype.
Result: the variable is `LADO_REPOS` (the folder of the human's repositories, also without
Docker): Where's suggestions in the New session window, the default clone folder, a
`lado doctor` line. The link printed is `http://127.0.0.1:<port>/...`, the container's own
port: it works when the server listens on `0.0.0.0` and the host publishes the same port
number (T3). Not checked in Docker by hand: no image yet.

### Stage 1. The image in the repository and in CI (walking skeleton)

**T3. Dockerfile in the repository, the image's build and smoke test in CI** (M; LAD-64, done: pull request #50)
The prototype in a lasting place (`docker/`), with Claude Code only; built in CI on amd64
and arm64 (GitHub has arm runners); smoke: the container starts, `lado doctor` is green,
`/api/health` answers, a session with a fake endpoint (as in the existing smoke tests)
gets to idle. Nothing published. The image sets `LADO_CONTAINER` for the agents too (in
`/etc/profile.d`): their environment comes from the login shell (`agent_env.resolve`),
not from the image's `ENV`, so without it an agent's `lado doctor` does not say "in a
container" (LAD-59's review report, "Not checked"). The server runs on `0.0.0.0`. The
port is one compose variable, `LADO_PORT` (8765 by default): the server's `--port` inside
and the publication `127.0.0.1:${LADO_PORT}:${LADO_PORT}`, so the numbers always agree
and LADO's link is right; several containers on one host take different numbers. The
image's CI job is one of `ci-ok`'s `needs` (the one check main's ruleset requires since
LAD-60), and `docker/` is not on the smoke's skip list. The session smoke may be
`scripts/smoke_ci.py run claude` inside the container.
Check: a green CI job on both architectures; `lado doctor` run by an agent says "in a
container"; by hand on a Mac, the link from `docker logs` opens in the host's browser, and
a second container with `LADO_PORT=8766` and its own volume runs beside the first.
Result: `docker/` holds the image, an optional compose file and `profile.sh`; one
`docker run` with no other file starts LADO (every default is in the image), and compose
is the same kept in a file. `make docker` builds `lado:local` from the working copy. A new
test layer, container (`tests/container/`, `make test-container`), runs real Docker
against the built image; CI's job `container` runs it on amd64 and arm64, and `ci-ok`
needs it. Checked by the human on a Mac: two containers side by side, each UI in its own
browser tab. Not checked: a Linux host with a uid other than 1000 (T4), Claude Code's
login and a real model in the container (T8, T10).

**T4. The host's projects folder: the same path and the same owner** (M; LAD-69, done: pull
request #56; T4 and T5 of the first plan in one task)
The projects folder is mounted at the same path as on the host, and `LADO_REPOS` names it
(compose from `LADO_PROJECTS`; `docker run` with the host's path and the variable);
`safe.directory` for it. On Docker Engine (Linux) the entrypoint gives the user `lado`
the uid and gid of the projects folder's owner; with owner 0 (as Docker Desktop shows it)
it changes nothing; the home volume moves to the new uid. One task, since T4's check (a
worker commits into the host's folder) fails on a Linux CI runner (uid 1001, the image's
user 1000) until T5's part is done: apart, T4's test would need a work-around T5 removes.
Check: tests of the container layer, on amd64 and arm64: a worker in the container
commits into the host's folder; on the host `git -C <the worker's worktree> status`
works and `git worktree list` says no `prunable`; on the Linux runner the files an agent
makes belong to the runner's user; a container made again with another uid works with the
same home volume. By hand on a Mac: a session in the UI in a project of that folder.
Result: `docker/entrypoint.sh` gives `lado` the projects owner's uid and gid once, at the
first start (a one-shot sudo rule, then `setpriv`); hardened starts (`no-new-privileges`,
`--cap-drop ALL`, `--read-only`) keep uid 1000 with a warning. The human's check by hand
on a Mac passed in full, a real agent with Claude Code's login included: so the login and
a real model in the container work. Learned:
- The check by hand was hard to get through: an image built from another branch, compose
  run outside `docker/`, `LADO_PROJECTS` set in another terminal, `~/...` typed in the
  UI's folder field (in the container `~` is `/home/lado`). A user will trip the same way
  (T8, T14).
- Not checked: rootless Docker, Podman, seccomp, AppArmor, SELinux, where the entrypoint's
  root step may fail and the container not start (T11).
- Open minor findings: `docker run --user root --cap-drop ALL` does not start (F12); an
  owner change that half failed is not tried again (F13). Both rare and loud: documented
  in T8.
- `/opt` stays uid 1000's after the uid changes: an agent's global install (`npm i -g`,
  `uv tool install`) fails on a Linux host (T9).

**T5.** Merged into T4 (LAD-69).

**T6a. A new image on an old volume: `lado.db` migrated with a backup** (S; LAD-71, done: pull request #58)
`lado server` already migrates `lado.db` at the container's start (tmux is empty after a
restart, so no session runs), but with no backup: only `lado update` makes one, and it is
refused in a container. Before the migration LADO backs `lado.db` up as `lado update`
does; a failed migration says in `docker logs` what happened and how to go back to the
old image with the backup. A blocker before publishing (T7): the first image update after
a release must work.
Check: a test of the container layer: a volume with an old schema, the new image starts,
the database is migrated, the backup is there, the UI answers, the old sessions show.
Result: the backup is taken before every migration of `lado.db`, in or out of a container
(`state.migrate`, the one place migrations run): `backups/lado.db.schema-<N>`, one kept. A
backup that cannot be written stops the migration; a failed migration rolls back and says
in one message what failed, where the backup is and how to go back. The update in a
container became two steps: the image before is tagged `lado:previous` (after `docker
compose pull` it has no name otherwise), then `pull` and `up -d`; LADO's own hint says the
same, and the compose file's header has the steps back. Left for T7: `lado:previous` is
one name per machine, so a second compose project overwrites it (G2); a stale hint in a
fixture of `web/src/SystemPanel.test.tsx` (H2).

**T6b. Stopping and resuming the container's sessions** (M; LAD-74, done: pull request
#65, in 0.40.0)
On `docker stop` LADO records the sessions that ran and stops them properly (the agents'
config folders removed, `lado doctor` without warnings); when the container starts it
resumes them. Today a restart shows them as "tmux session is gone", resumed by hand from
the UI. Needs its own design: what `docker stop` means, which sessions resume, what of
the workers.
Check: a test of the container layer: "session, `docker compose down`, `up`, the session
runs again".
Result: on SIGTERM the server in a container marks its running sessions stopped in one
transaction with `resume_at_start` (schema 29), then kills their tmux and removes the
agents' config folders, well within Docker's ten seconds; at the next start the database
is migrated first, then the marked sessions, and those whose tmux went with a container
killed without SIGTERM, are resumed one by one. Sessions the human stopped stay stopped; a
failed resume is not retried; workers are not restarted (the supervisor gets "session
resumed" with the open runs). The human's decisions: container only, no chat message.
Review: F1 (a resume dropped `lado start`'s warnings) fixed; F4, F5 declined (minor).
Left: the check by hand on a Mac and the live tests go with 0.40.0's release candidate,
whose image update from 0.39.0 checks the migration to schema 29 and the resume at once;
the non-atomic first creation of `lado.db` is in BACKLOG.

### Stage 2. A programmer can use it (from the documentation)

**T7. Publishing the image to GHCR in the release workflow** (S/M; LAD-73, done: pull
request #61; done before T6b)
`ghcr.io/ladohq/lado:<version>` and `latest`, two architectures, through `GITHUB_TOKEN`,
no new secrets. The tags leave room for images with other agents. Built from the wheel
the release puts on PyPI and run through the container tests before it is pushed; a
release candidate gets its own tag only, `latest` only a final release. Compose takes the
published image by default. The update and the way back go by version tags: with a
version in `LADO_IMAGE` the image before always has a name, so `lado:previous` (T6a,
one per machine) can go, and several containers on one host update apart.
The image holds all four agent CLIs at their pins (`scripts/smoke_ci.py`'s `PINS`), the
human's decision of 2026-10-15: OpenCode and Kilo worked in the prototype (H5); Codex is
installed only, its login is T15. If adding the three CLIs slows T7 down (build time,
container tests), they go to a task of their own right after it. LADO's
update hint (`update.CONTAINER_UPDATE`) and the compose header change together; H2 of
LAD-71 fixed on the way. Moved before T6b: T6a removed the blocker, T6b is a comfort
(sessions resume by hand from the UI after a restart), the first image can come with
the release 0.39.0, and a published image spares the checks by hand `make docker` from a
branch.
Check: `docker pull` on a Mac and on Linux after a release candidate; an update to another
version and back by the compose header keeps the sessions; two containers on one host
update apart.
Result: the Release workflow builds the image from the release's wheel, runs the container
tests on amd64 and arm64, pushes by digest, then tags `:<version>` (and `latest` for a
final) before the GitHub release. All four CLIs stayed in T7: the image grew from 314 to
615 MB, a cold build from 48 to 99 s, CI's container job from about 2 to 2.5-3.5 minutes.
`lado:previous` is gone: compose runs `ghcr.io/ladohq/lado:${LADO_VERSION}` from `.env`,
an update is a new version and `up -d`, the way back the version before; a test checks
that a second LADO is left alone. In a container LADO names only the new version's image,
no command (the human's decision: the documentation gives them, T8). The human's check
by hand passed. Checked on 0.39.0rc1 and 0.39.0 (both Release runs green, the package made public,
`0.39.0` and `latest` pulled for amd64 and arm64 with no login); the image's checks of each
release candidate now live in docs/release.md, sections 4.5 and 4.6 (pull request #68).
What was open until then:
- the run green, the image built on both architectures (if buildx's two outputs fail on
  the runner, `--provenance=false` is the RC's fix, the review's E1);
- an org admin makes the package `ghcr.io/ladohq/lado` public once (GitHub makes it
  private, `GITHUB_TOKEN` cannot change that);
- `docker pull ghcr.io/ladohq/lado:<rc>` with no login on a Mac and on Linux, the UI
  answers, `lado doctor` sees the four CLIs.
Learned: the check by hand tripped again over `LADO_PORT` and `LADO_PROJECTS` left in the
shell from an earlier test, which beat `.env` (as in LAD-69): T8 and T14.

**T8. Section "Install with Docker" in docs/install.md and a ready compose file** (S)
Decided here, with T7: which way the documentation leads with, `docker run` or compose
(the image needs no file since LAD-64), and so which update line LADO prints in a
container (now `docker compose pull && docker compose up -d`, from T1).
Download the compose file, one command, Claude Code's login, open the UI; how to remove it.
From LAD-69's check by hand: one command to start, with no "go to this folder and set this
variable in this terminal" (an `.env` file beside the compose file, or the launcher); the
UI in a container warns when a session's folder is outside `LADO_REPOS` (the host does
not see it); F12 and F13 described.
From LAD-73: the update, the way back and a second LADO by version tags (`LADO_VERSION` in
`.env`); how users get `compose.yaml` (a release asset or a link); that variables of the
shell beat `.env`; that an older Compose v2 (GitHub's runners) asks for `LADO_VERSION`
also beside `LADO_IMAGE`.
Check: the human follows the instructions from scratch on a clean volume.

**T9. Project toolchains through mise** (S)
mise in the image, its shims on the login shell's PATH, its data on the home volume; in
the agents' instructions: "a tool is missing: install it through mise from the project's
files". Tools go to the home volume, never `/opt`, which stays uid 1000's after T4's uid
change.
Check: an agent in the container installs Go from `.tool-versions` by itself and builds
the project; after the container is made again, Go is still there.

**T10. Secrets and access: one place for secrets, and git** (M; LAD-76; widened
2026-10-15 by the human's decision, done right after T6b, before T8)
Without it the container cannot be used for real work: an agent has no git identity to
commit with, and a kit whose MCP server needs a variable (sdlc's tracker:
`YOUGILE_API_KEY`) refuses to start, as nothing puts it in the agents' environment.
- One place for secrets on the home volume: a file the login shell reads (mode 600), or
  Docker secrets read by a profile script; never `LADO_AGENT_ENV=inherit` nor compose's
  `environment:` (no secret in `docker inspect`). It holds every variable: Claude's token
  (`CLAUDE_CODE_OAUTH_TOKEN`), `GH_TOKEN`, kits' keys, model providers' keys.
- git's identity (`user.name`, `user.email`): the image has none; the container tests
  set it with `-c`.
- git over https: a credential helper (`gh auth setup-git`, or the token).
- `gh auth login` in the container, its token on the volume (research H8: not run).
- The host's ssh agent without the root group (Mac and Linux).
- OpenCode's and Kilo's login (`auth.json` in their data folders, or providers' keys), now
  that they are in the image (T7). Codex's stays T15.
If it grows, it splits into T10a (secrets and kits) and T10b (git: identity, ssh, https,
gh).
Check: an agent commits under the human's name, pushes over ssh and over https to a test
remote, runs `gh api user`; a session of a kit that needs `YOUGILE_API_KEY` starts; no
secret in `docker inspect`; no manual step but the logins.

**T11. A check on Windows and on a real Linux** (S, manual)
Docker Desktop with WSL2, the whole scenario of T8, a speed measurement (section 5). On a
real Linux host: Docker Engine, rootless Docker, and Podman where possible, with SELinux
or AppArmor on (LAD-69's "Not checked").
Check: a report with figures and screenshots; what is found goes into tasks of its own.

> After stage 2 the Docker install works for someone not afraid of a terminal. A good
> point for a release and feedback.

### Stage 3. A non-programmer can use it

**T12. The agent's login from the UI** (M)
In the UI a terminal opens with Claude Code's login (the link and the code visible in the
UI), without `docker exec`. Built on the agent's existing terminal in the UI.
Check: a UI e2e test with a fake CLI; by hand, Claude Code's login through the browser
only.

**T13. Choosing the model in the UI** (M)
For Claude Code the model (later, for other CLIs, the provider and the model too); written
into the CLI's settings.
Check: unit and e2e; by hand, changing the model without editing files.

**T14. A launcher** (M)
A script or shortcut per OS: checks Docker, starts compose, waits, opens the UI.
No setting typed into a terminal: twice (LAD-69, LAD-73) the human's check by hand ran
with variables left in the shell from an earlier test.
Check: on a Mac a double click opens the UI.

### Stage 4. Later

- **T15. Codex's login reaches the agents** (S/M): LADO carries Codex's `auth.json` into
  each agent's `CODEX_HOME` (BACKLOG.md, "Codex agents cannot log in"; research 5.1),
  needed without Docker too; checked live with the human's Codex account (2026-10-15).
  Then a Codex session in the container, by hand. Not now: the human does not want to
  debug Codex yet.
- **Resume all, outside a container** (S): after a machine's reboot or a tmux server
  killed, "Resume all" in the UI or `lado start --all`, on T6b's `resume_at_start`. Left
  out of T6b by the human's decision: outside a container the server starts often and a
  gone tmux may be the human's own doing.
- **Projects in a Docker volume** (M/L): faster and better isolated, but needs a UI for
  files and diffs.
- **LADO as a Dev Container Feature** (M).
- **A one-command install script without Docker** (M).
- **A container per session**: an item of ROADMAP, with its own research.
- **A container manager**: several LADO containers on one host (the human's plan). Each
  has its own `LADO_PORT` and volume from T3. If the manager puts one address in front of
  them (a proxy), LADO's link needs that outer address: decided with the manager.

### Dependencies

```
T1, T2 ──┐
         ├─> T3 ─> T4 (with T5) ─> T6a ─> T7 ─> T6b ─> T10 ─> T8 ─> T11
         │          └─> T9 (after T3)
T12, T13: independent of the image (useful for the usual install too)
T14: after T7
```

One task at a time; the first is T1.

## 5. Windows: how much slower

There are no measurements on Windows. What is known:

- **Mac (measured, H6 and 5.11):** git on a host folder is about 14 times slower than on a
  Docker volume (3000 files, `git commit`: 1.9 s against 0.14 s). On small projects it is
  not noticeable: an agent's turn is seconds and minutes of the model, not git.
- **Windows, a folder under `C:\Users\...`:** a longer path (Windows, WSL2, the
  container); Docker itself calls it slow and advises keeping files in WSL's file system.
  Usually several times slower than on a Mac, but there are no figures for LADO.
- **Windows, a folder in WSL (`\\wsl$\...`):** speed close to Linux; the downside is the
  unusual path to the projects in Explorer.

Proposal: the first version is Mac and Linux. In T11 measure the same test for a folder on
`C:` and a folder in WSL, and decide from the figures what to recommend to Windows users.
