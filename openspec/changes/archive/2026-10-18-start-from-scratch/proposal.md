Task: LAD-98

## Why

A new user who is not a programmer cannot start a first session: the New session window
takes only a folder that already holds a git repository with a commit, or a git URL to
clone. Such a user has neither. They are told "for any task you need an external
repository", believe they need a GitHub account, and stop there.

The premise is wrong, and that is the root cause: LADO needs no GitHub and no remote, only
a local git repository with one commit (each worker gets a git worktree of it). What
stands between the user and that repository is a terminal command the window prints
(`git init && git add -A && git commit …`, LAD-5) and, on a fresh machine, a git that does
not yet know whom to sign commits with. LAD-5 kept the window from making repositories
because LADO would choose what goes into the commit of the human's files; LAD-6 answered
"I have no repository yet" with a clone, which needs a URL this user does not have.

A new, empty folder has no such files: LADO can make it a repository with an empty first
commit and choose nothing on the human's behalf.

## What Changes

- **Core**, a module `lado.scratch`: from a name the human types in any script (Cyrillic
  is transliterated to Latin) it derives the folder's and the session's name and the
  session's title; it checks the target folder (only a new folder, or an empty one outside
  any git repository, will do), checks that git knows the commits' author
  (`user.name`, `user.email`; in LADO's container these come from `LADO_GIT_NAME` and
  `LADO_GIT_EMAIL`), and makes the folder a repository with an empty first commit, undoing
  what it made when a step fails.
- `runtime.start_session` takes the new session's `title` (the rule of `runtime.set_title`),
  checked before anything starts.
- **CLI**: `lado start --new <folder>` makes a new or empty folder a repository with an
  empty first commit, then starts the session there as `lado start <folder>` does. Without
  `--new`, `lado start` is unchanged.
- **API**: `GET /api/scratch-target` (the target folder, the names and title, the author
  check); `POST /api/sessions` takes `where: {kind: "scratch", path}` and `title`;
  `FolderInfo.scratch` says that a folder can be started from scratch.
- **UI**: the New session window's switch becomes **From scratch | Folder | Clone from
  URL**. From scratch shows a **Name** and **Create in** (`$LADO_REPOS/<name>`, else
  `~/lado/<name>`) and starts with **Create and start**. The window opens in From scratch
  only while LADO has no sessions at all (no recent folders); otherwise in Folder, as
  today. In Folder, a new or empty folder outside git offers **Start from scratch here**.
  When git does not know the author, the window says what to do (in the container: set
  `LADO_GIT_NAME` and `LADO_GIT_EMAIL` in `.env` and restart; else the `git config
  --global` command) and keeps the button off (mockup `mockup-from-scratch.html`).
- **lado doctor**: a check `git author`, a warning when git has no `user.name` or
  `user.email`, in and out of the container.
- New minor release (a UI, API and CLI feature). No schema migration, no MCP tool change.

## Scope

- `lado.scratch` (names, transliteration, the target check, the author check, making the
  repository), `runtime.start_session(title=)`.
- `lado start --new <folder>`.
- `GET /api/scratch-target`, the `scratch` kind of `Where`, `Launch.title`,
  `FolderInfo.scratch`; `make web-types`.
- The New session window's From scratch source and Start from scratch here.
- `lado doctor`'s `git author` check.
- Docs: `docs/design/ui.md` (Launch and session control), `docs/cli.md` (`lado start`),
  `docs/design/modules.md` (`scratch.py`), AGENTS.md's Layout (one line), README's and
  `docs/install.md`'s first session (one line each), CHANGELOG.md.

## Out of scope

- A button that makes a repository of a folder that already holds files (with a preview
  of what goes into the first commit): it brings back LAD-5's risk (secrets or gigabytes in
  a commit); a task of its own if wanted. The human's decision. Such a folder keeps LAD-5's
  hint with its command.
- Publishing the new repository to GitHub or another host later: not needed to work in
  LADO; a task of its own.
- Sessions without git (workers in one folder, no worktrees): a rewrite of the core that
  every flow relies on.
- The supervisor's MCP tool `start_session` with a new folder: no kit asks for it ("Only
  what is used").
- The word "project" anywhere in this feature: it is kept for the coming Projects (ROADMAP,
  Later), sessions over several repositories. The human's decision.
- Fields for the author's name and email in the window: LADO uses git's own settings (in
  the container `LADO_GIT_NAME` and `LADO_GIT_EMAIL`), and says how to set them. The
  human's decision.
- A made-up author ("LADO") for the first commit: it would hide a git that cannot sign the
  agents' commits until the first agent fails.
- Transliteration of scripts other than Cyrillic, and of `lado start <folder>`'s session
  names: a name with no Latin letter or digit after transliteration is refused with what to
  do; existing sessions keep their names.

## Acceptance criteria

- AC-1: In the window's From scratch, the name `Сайт кофейни` gives the folder
  `<parent>/sait-kofeini` (`<parent>` is `LADO_REPOS`, else `~/lado`), the session
  `sait-kofeini` and its title `Сайт кофейни`; Create and start makes the folder, a git
  repository in it with one empty commit `Start from scratch` on the branch of git's
  `init.defaultBranch` (else `main`), and starts the session; Activity opens and the
  session shows its title.
- AC-2: The window opens in From scratch when LADO has no sessions (no recent folders), and
  in Folder otherwise; Resume is unchanged.
- AC-3: Create in pointing at a folder that holds files, at a file, or at a folder inside
  a git repository is refused under the field with its reason, and nothing on disk
  changes; a folder holding only `.DS_Store` counts as empty.
- AC-4: When git has no `user.name` or `user.email`, the window shows, in LADO's container,
  `Set LADO_GIT_NAME and LADO_GIT_EMAIL in the .env file next to compose.yaml, then restart
  LADO there:` with `docker compose up -d` and Copy, outside it `Tell git who you are, once
  for this computer:` with the `git config --global` command and Copy, and Create and start
  stays off; `lado start --new` is refused with the same text; `lado doctor` warns
  `git author`.
- AC-5: In Folder, a new or empty folder outside git shows **Start from scratch here**,
  which switches the window to From scratch with that folder in Create in and its name in
  Name; a folder that holds files keeps LAD-5's command.
- AC-6: `lado start --new <folder>` makes a new or empty folder a repository with an empty
  first commit and starts the session; a folder that holds files is refused with LAD-5's
  hint and is not changed; `lado start <folder>` without `--new` behaves as before.
- AC-7: A failed step leaves nothing LADO made: no folder LADO created, no `.git` in an
  empty folder the human gave. A start refused after the repository was made (a name taken
  meanwhile) keeps it, and the window switches to Folder with it and shows the refusal.
- AC-8: A name that leaves no Latin letter or digit after transliteration (`東京`), an empty
  one, or one longer than 80 characters or with a hidden character is refused under Name
  with what to do, and Create and start stays off.
