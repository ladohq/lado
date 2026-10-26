# Research: getting-started videos

A plan for a short series of videos that takes a new user from an empty computer to their
own work process in LADO. Decided with the human in a design conversation on 2026-10-26;
what was decided there is marked as such, the rest is marked as the writer's call or as
open. Production starts after the next release; nothing is recorded yet.

## Why

People install LADO and then do not know how to start: some wait for a newer version in the
hope that it gets clearer. The one user who works with LADO every day is an experienced
backend lead who came from Codex. The company means to bring LADO to managers and heads of
departments for their routine work, and many of them are not programmers.

What they lack is not a list of LADO's buttons but how to bring their own work into LADO:
in the end, their own kit. The videos show that path on one made-up manager and their real
kinds of tasks.

## Audience

- **This series**: managers and heads of departments. Not programmers; at ease with email,
  spreadsheets and a task tracker. They read English, but not always well. Each of them
  already pays for an AI agent of their own (Claude Code, OpenCode or Kilo; Codex, see Open
  decisions); there is no company subscription, and getting one is up to them.
- **Their computers are mixed** (decided): many use Windows, some macOS and Linux. Docker
  is the way in for all of them (decided: the Docker install was made for such users).
- **Later, a separate series** for experienced users (decided). Not planned here.

## Goals

- A new user installs LADO and gets to a useful first result by following the videos,
  without help.
- Each video solves one task of the hero and adds one or two LADO features to what the
  earlier videos showed (decided).
- Each video stands on its own: watch it, then repeat it on your own computer.
- The series can stop after any video and still be useful: the human doubts the idea may
  fly, so it starts small (decided).

## Non-goals and anti-goals

- Not a reference manual: no tour of every button or option.
- Not overloaded: a video that needs a second task or more than two new features is split.
- No real personal data on screen: the CV task uses made-up CVs (writer's call, see Risks).
- No step that the viewer cannot repeat with what the earlier videos gave them.
- A failure even if it "works": a video that a non-programmer stops watching halfway, or one
  that teaches them a habit that breaks company rules (sending real candidates' data to a
  model provider without checking).

## Format (decided)

- **Length**: 5 to 7 minutes each, never more. Waits for an agent's answer are sped up.
- **Language**: English everywhere, plain English: short sentences, no idioms, no jargon.
  A LADO term (kit, gate, artifact, session) gets a one-line explanation the first time.
- **No voice-over.** On-screen captions carry the story: one or two short captions per
  step ("Step 2. Make a folder for LADO").
- **Subtitles** in English and Russian.
- **Number of videos**: few at first; the series grows only if the first ones work.

Writer's calls on the format, to confirm while reading:

- Each video opens with its result (the first 5 to 10 seconds), then the steps.
- The cursor and the control it clicks are highlighted; small terminal text is zoomed in.
- Each video ends with one card: what comes next, and a link to its companion page.
- Each video has a short **companion page** with the commands and settings to copy, since
  copying from a video is painful. It also says what you need before you start.
- No music, or a quiet background track: not discussed.

## The hero

**Anna, a head of department in an IT company** (writer's call; the human asked for a
made-up manager). Not a programmer. Already pays for an AI agent. Her tasks come from the
real routine the human named: quarterly reports, project reports, and filling the
production team's needs (picking candidates by their CVs). The human will check these tasks
with real managers later.

## The series

| # | Title (working) | Anna's task | New in LADO | Length |
|---|---|---|---|---|
| 0 | What LADO is | none | the idea: a team of AI helpers with a lead; you set the task and decide, they do the work | 1–2 min, optional |
| 1 | Install LADO (Windows, macOS, Linux) | none: LADO opens in her browser | Docker, the LADO folder, `.env`, start, the UI's link | 5–7 min each |
| 2 | Connect your AI agent | say hello to her first team | what you need (a subscription or a key), logging in inside the container, the trust question, a first session | ≤ 5 min |
| 3 | Pick candidates from CVs | compare a few CVs with a vacancy | a session started From scratch, attaching files in the chat, Needs you, a result as an artifact | 5–7 min |
| 4 | A project report from your tracker | a status report of one project from its tasks | projects, a secret (the tracker's key), a tracker kit from the marketplace | 5–7 min |
| 5 | Your own process: the quarterly report | describe how she makes the report, get a team for it | kits, built with the kit-builder kit: roles and a flow | 5–7 min, may become two |
| 6 | Approve before it goes out | run the quarterly report with her approval points | gates: approve or send back with a comment; running the next quarter with one message | 5–7 min |

Order and the split of installation into 1 and 2 are the writer's calls: one installation
video does not fit into 7 minutes with today's steps (see Pain points 1–3).

### Video 1: Install LADO

Video 1 comes in one version per system: Windows first (most of the audience), then macOS,
then Linux (writer's call on the order). The versions share their captions and steps where
the systems agree; only the scenes that differ are recorded apart. Videos 2 to 6 happen in
the browser and need one version.

Starts: a computer with Docker Desktop installed (Docker Engine on Linux), nothing else.
Installing Docker itself is not shown: the companion page links to Docker's own guide and
says that a company computer may need IT for it (admin rights; Docker Desktop's licence is
paid for larger companies). Ends: LADO's UI open in the browser.

Steps: what you need (Docker, a subscription to one supported agent); a folder for LADO;
`compose.yaml`; the settings file `.env` (version, workspace folder, port, your name
and email for the agents' commits); start; the link to open. The companion page holds the
commands and a ready `.env` to fill in.

### Video 2: Connect your AI agent

Starts: the UI open. Ends: Anna's first session answers her. Steps: log in to her agent
inside LADO (Claude Code's link and code; or OpenCode's or Kilo's key); start a session
From scratch; the trust question in Needs you, and why Enter alone closes the agent;
"Hello, what can you do?"

### Video 3: Pick candidates from CVs

Starts: a session. Ends: a table of candidates against the vacancy, as an artifact Anna can
open and download. Steps: a new session for the hiring task; attach three made-up CVs and
the vacancy in the chat; ask for a comparison; the supervisor delegates, Anna waits; Needs
you if it asks something; the artifact. One caption: real CVs are personal data; check your
company's rules before you give them to an AI provider.

### Video 4: A project report from your tracker

Starts: a working LADO. Ends: a project status report built from the tracker's tasks.
Steps: a project in LADO; the tracker's kit from the marketplace (Kits page); the tracker's
key as the project's secret (set and hidden); a session in the project; ask for the report.
Which tracker is shown: open (YouGile or Jira).

### Video 5: Your own process

Starts: a working LADO. Ends: Anna's own kit for the quarterly report, installed. Steps:
install kit-builder; tell it how she makes the report today (where the numbers come from,
who reads it, what it must hold); it proposes a team (for example a collector, an analyst
and a writer) and writes the kit; install it. If it does not fit 7 minutes: one video for
the interview, one for the result.

### Video 6: Approve before it goes out

Starts: Anna's kit. Ends: a quarterly report approved by her. Steps: start the flow; the
team works; a gate asks her to approve the draft; she sends it back once with a comment,
then approves; next quarter is one message.

## Pain points of a new user

Found by walking `docs/install.md` (Docker) and the first session in the UI as a newcomer,
and in the 0.43.0rc1 check. Each says how the series handles it; some are better fixed in
LADO before recording (Open decisions).

1. **The terminal cannot be avoided at install.** Make a folder, `curl` the compose file,
   write `.env`, `docker compose up -d`, then `docker compose exec lado lado ui --no-open`
   for the link. `.env` is a hidden file: Finder does not show it, and TextEdit saves it as
   `.env.txt` or rich text by default; on Windows, Notepad saves `.env.txt` and Explorer
   hides the extension, so the mistake does not show. The Windows commands differ too
   (PowerShell has no `mkdir -p` or `~/` the way the guide writes them). Series: video 1 and
   its companion page, every command copied from there. Product candidate: a way to install
   without writing `.env` by hand.
2. **`.env` is full of developer words**: a version number ("without v", from the releases
   page), a full path to the workspace, a port, a git name and email (without them a project
   repository cannot be made, found in the rc1 check), an ssh agent's path. The guide also
   opens with checking shell variables (`env | grep`). Series: video 1 shows a ready `.env`
   with only the name, email and folder to change; ssh is left out.
3. **Logging in to the agent** is a terminal step too (`docker compose exec -it lado
   claude`, a link, a code, `/exit`). Codex cannot be used in the container at all yet;
   OpenCode and Kilo need a provider's key. Series: video 2.
4. **The first session meets git words**: repository, first commit, branch, worktree. From
   scratch helps, but the words stay. Then the trust question: the agent waits in Needs you,
   and its terminal asks with arrow keys; Enter alone answers "No, exit" and closes the
   agent. Series: video 2 shows it slowly, with a caption on Enter.
5. **Interface words**: permission mode (default, acceptEdits, bypassPermissions…), the
   amber "untested version", kit, role, skill, flow, gate. Series: each word explained once,
   when it first matters; permission mode left at its default and not explained in this
   series.
6. **Opening LADO again** after a restart needs the link with its token again (a command).
   Series: video 1 shows bookmarking the link. Product candidate: an easier way back in.
7. **Updating** means editing `.env`, downloading a new `compose.yaml` and starting again.
   Series: not covered at first; the companion pages link to the guide.
8. **A manager's kit has no git repository of its own.** kit-builder releases a kit with a
   tag; a non-programmer may have no GitHub. Series (writer's call): Anna's kit is a folder
   in her workspace, installed with `lado kits add <folder>` (a folder kit is read in
   place), so no GitHub account is needed. Before writing video 5: check that kit-builder
   can leave a kit as a folder; if it cannot, this joins Open decision 2.
9. **Results of non-code work**: what a manager wants is a document, not a commit. Series:
   artifacts from video 3 on.
10. **Keys for trackers and other services** go into `secrets/` or a project's secret.
    Series: video 4, the project's secret in the UI, no files.

## Risks

- **Personal data.** CVs hold candidates' personal data, and the agent sends them to a
  model provider. The videos use made-up CVs and say it once (video 3).
- **The interface changes.** A video recorded on one version goes stale. Recording by script
  (below) lets each video be recorded again on a new version.
- **Agents answer differently each time** and need a real model; long waits must be cut.

## How the videos are made (writer's calls)

- The human gave the production to the agent, keeping the choices and the final review.
- Every scene is recorded by script, so a video can be recorded again on a new version.
  Scenes in LADO's page: Playwright drives the browser. Scenes outside it (Explorer or
  Finder, the system's terminal, Docker Desktop, the agent's login page, the browser's
  address and bookmarks bars) are recorded as the whole screen while a script drives the
  apps, so the viewer sees the same terminal and windows they will open. Video 1's Windows
  and Linux versions need a Windows and a Linux computer to record on. Then ffmpeg cuts,
  speeds up, adds the captions and the subtitles. Needed on the recording machine: `brew
  install ffmpeg`.
- **Two layers of text, never both at once in one place**: the step's short label (for
  example "Step 2. Make a folder for LADO") is burned into the picture in English; the
  explanations are a subtitle track, English and Russian, which the viewer switches. One
  video file, two subtitle files.
- A real agent and model for the agents' answers; whether LADO's fake agent may stand in
  for repeatable takes is open.
- Made-up data (CVs, a vacancy, a tracker board, quarterly numbers) is written once and kept
  with the scripts, so a video can be recorded again.
- **Where it is kept** (decided): the private repository `ladohq/lado-videos`, so LADO's
  repository carries no large binary files. Its git holds what the videos are made from,
  all of it text: the scripts, the subtitles, the made-up data, the build. Raw recordings
  stay out of git, since the scripts make them again. Finished videos are the assets of that
  repository's GitHub Releases, out of Git LFS and its quota. This plan stays here because
  its pain points and open decisions are about LADO itself.

## Before recording

- **LADO in Docker on Windows is checked by hand**: the guide says it is not checked yet,
  and most of the audience is on Windows. What the check finds may change video 1's Windows
  version or LADO itself.
- **Demo accounts are made** (decided: to be made), so nothing personal is on camera and
  nothing is blurred afterwards:
  - a demo name and email for `.env`;
  - an agent subscription for the videos (Open decision 3 says which agent);
  - a demo tracker workspace with the made-up board for video 4 (Open decision 4 says which
    tracker).
- The made-up data is written: three CVs and a vacancy, the tracker board's tasks, the
  quarter's numbers.

## Open decisions (the human's)

1. **Codex in the container.** Fix it before recording, or say in video 2 that Codex works
   only without Docker for now. Today a Codex user who follows the recommended path stops
   at video 2; that is the daily user's story.
2. **What to fix in LADO before recording**: pain points 1, 2 and 6 (installing without
   writing `.env`, an easier way back into the UI), and the Docker image's defaults (git
   author, Codex's sandbox in the container, found in the rc1 check).
3. **Which agent the videos use** (Claude Code is the writer's guess).
4. **Which tracker** video 4 shows (YouGile or Jira).
5. **The first video to make**: the writer suggests video 1, since installation is where
   people stop today; the human wants to start with something simple.
6. **Where the videos and companion pages are published** (YouTube, the site); until then
   they are kept in `ladohq/lado-videos`.
7. **The managers' real tasks**: the human checks the three tasks with them; the series
   follows what they say.
8. **When**: after the next release (decided); which version the videos show.
9. **How we judge that the first videos work**: for example, a manager who has not seen
   LADO gets to an open LADO alone with video 1 before it is published; or views and how
   much of a video people watch, which depends on where the videos live (6).

## Where this goes next

After the human's answers to the open decisions: a script for the first video (captions,
steps, the made-up data, the scenes), a test recording of one minute to judge the look, then
the video. Scripts and made-up data go to `ladohq/lado-videos`.
