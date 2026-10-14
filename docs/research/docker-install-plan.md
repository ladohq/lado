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
| Image | One image with Claude Code only (~1 GB instead of 2.5). The other CLIs later, as tasks of their own |
| Project path | The host's path |
| Codex | Not in the first version (follows from an image with Claude only) |
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
button refuse and name the way: `docker compose pull && docker compose up -d`.
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

**T3. Dockerfile in the repository, the image's build and smoke test in CI** (M; LAD-64)
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

**T4. Projects at the host's path** (S)
Compose mounts the projects folder at the same path as on the host and sets
`LADO_REPOS` to it (the UI's start folder and the default clone folder, from T2);
`safe.directory` for it.
Check: a worker in the container commits; on the host `git -C <the worker's worktree>
status` works and `git worktree list` says no `prunable`.

**T5. File owner on Linux (uid)** (S/M)
On Docker Engine (Linux) the entrypoint gives the user `lado` the uid and gid of the
projects folder's owner; with owner 0 (as Docker Desktop shows it) it changes nothing; the
home volume moves to the new uid.
Check: a smoke test in CI on a Linux runner (uid 1001): the files an agent makes belong to
the runner's user.

**T6. Stopping and resuming the container's sessions** (M)
On `docker stop` LADO records the sessions that ran and stops them properly (the agents'
config folders removed, `lado doctor` without warnings); when the container starts it
resumes them. Also: a new image on an old volume migrates `lado.db` with a backup.
Check: a test "session, `docker compose down`, `up`, the session runs again"; a test "an
old schema on the volume".

### Stage 2. A programmer can use it (from the documentation)

**T7. Publishing the image to GHCR in the release workflow** (S/M)
`ghcr.io/ladohq/lado:<version>` and `latest`, two architectures, through `GITHUB_TOKEN`,
no new secrets. The tags leave room for images with other agents.
Check: `docker pull` on a Mac and on Linux after a release candidate.

**T8. Section "Install with Docker" in docs/install.md and a ready compose file** (S)
Download the compose file, one command, Claude Code's login, open the UI; how to remove it.
Check: the human follows the instructions from scratch on a clean volume.

**T9. Project toolchains through mise** (S)
mise in the image, its shims on the login shell's PATH, its data on the home volume; in
the agents' instructions: "a tool is missing: install it through mise from the project's
files".
Check: an agent in the container installs Go from `.tool-versions` by itself and builds
the project; after the container is made again, Go is still there.

**T10. Secrets and git access** (S)
Claude's token (`CLAUDE_CODE_OAUTH_TOKEN`) through a file the login shell reads, not
through `inherit`; the ssh agent without the root group (Mac and Linux); `gh auth login`
in the container, in the documentation.
Check: an agent runs `git push` to a test remote and `gh api user`, with no manual step
but the login.

**T11. A check on Windows** (S, manual)
Docker Desktop with WSL2, the whole scenario of T8, a speed measurement (section 5).
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
Check: on a Mac a double click opens the UI.

### Stage 4. Later

- **Other CLIs in the image**: OpenCode and Kilo (they worked in the prototype, H5; low
  risk); Codex: first carrying its login into the agents (S/M, needed without Docker too).
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
         ├─> T3 ─> T4 ─> T5 ─> T6 ─> T7 ─> T8 ─> T11
         │          └─> T9, T10 (after T3)
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
