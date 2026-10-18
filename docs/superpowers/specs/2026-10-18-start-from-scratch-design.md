# Start from scratch: a first session without git or GitHub (LAD-98)

Change: `openspec/changes/start-from-scratch/` (proposal, delta specs of
`session-scratch`, `doctor` and `session-clone`, `design.md` with the decisions D1-D11).
This document is the human's view: what a user gets, what was decided with the human,
and how the human checks it. Mockup: run artifact `task/lad-98/mockup-from-scratch.html`.

## What a user gets

Today a person who is not a programmer opens LADO's New session window and is asked for
a folder that is a git repository with a commit, or for a git URL. They have neither,
believe they need a GitHub account, and stop. LADO needs no GitHub: only a local git
repository with one commit.

After this change:

- The window's switch reads **From scratch | Folder | Clone from URL**. A person who has
  never started a session finds the window already in **From scratch**; a developer with
  sessions finds it in Folder, as before.
- From scratch asks for a **Name**, in any words: `Сайт кофейни`. Under it the window
  says what LADO will make: `folder and session: sait-kofeini · title: Сайт кофейни`.
  **Create in** shows the folder (`<projects folder>/sait-kofeini` in the container,
  `~/lado/sait-kofeini` on a PyPI install) and can be changed to any new or empty folder.
- **Create and start** makes the folder, a git repository in it with one empty commit,
  and starts the session with that title. None of the human's files go into a commit.
- When git does not know whom to sign commits with (no `user.name` / `user.email`), the
  window says so before anything is made and shows what to do: in the container, set
  `LADO_GIT_NAME` and `LADO_GIT_EMAIL` in `.env` and run `docker compose up -d`; on a
  PyPI install, one `git config --global` command with Copy. `lado doctor` warns about it
  too.
- In Folder, an empty folder (one made in Finder, say) gets **Start from scratch here**
  instead of a terminal command.
- From the terminal: `lado start --new <folder>`.

## Decided with the human

1. The third source in the switch, chosen by itself only while LADO has no sessions
   (round 1, point 1).
2. An empty or new folder in Folder offers Start from scratch here; a folder with files
   keeps LAD-5's command; making a repository of a folder with files is a task of its own
   (point 2).
3. The folder goes where clones go: `LADO_REPOS`, else `~/lado` (point 3).
4. `lado start --new` for the CLI (point 4).
5. Not "project": that word is kept for Projects of several repositories; the source is
   **From scratch** (round 2).
6. The commits' author comes from git's settings, which in the container are
   `LADO_GIT_NAME` and `LADO_GIT_EMAIL`; no fields in the window, no made-up author; a
   refusal with what to do when it is missing (round 3).
7. A Cyrillic name is transliterated for the folder and the session, and the text itself
   becomes the session's title (round 4).

## Acceptance criteria

AC-1 … AC-8 of the proposal (`openspec/changes/start-from-scratch/proposal.md`).

## Manual check (for the PR)

1. With a fresh `LADO_HOME` (`LADO_HOME=$(mktemp -d) uv run lado ui`), open New
   session: From scratch is chosen.
2. Type `Сайт кофейни`: the note shows `sait-kofeini` and the title; Create in is
   `~/lado/sait-kofeini`, `✓ a new folder`.
3. Create and start: Activity opens, the session's head shows `Сайт кофейни`; in a
   terminal `git -C ~/lado/sait-kofeini log --oneline` shows one commit `Start from
   scratch`, and `ls -A` shows only `.git`.
4. `GIT_CONFIG_GLOBAL=/tmp/empty-gitconfig uv run lado ui` (an empty file): From scratch
   shows the author's refusal with the `git config --global` command; Create and start is
   off. `GIT_CONFIG_GLOBAL=/tmp/empty-gitconfig uv run lado doctor` warns `git author`.
5. `mkdir ~/Documents/coffee-site`, open New session in Folder, pick it: Start from
   scratch here; press it: From scratch with that folder, `✓ an empty folder`.
6. `lado start --new ~/lado/shop --no-attach`; then `lado start --new ~/Documents` is
   refused with LAD-5's hint.
7. Remove the folders and `lado forget` the sessions made.
