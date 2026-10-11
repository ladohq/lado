## Why

LADO works only on a git repository with a commit, yet it does not check git itself and
does not say clearly what a folder lacks:

- Without git, `lado start` ends in a Python traceback (`FileNotFoundError: 'git'` from
  `runtime.git`), the UI's folder check (`GET /api/folders`) and `POST /api/sessions`
  answer 500, and `lado kits add` crashes the same way (`gitcache._git`).
- On a Mac without the Xcode command line tools, `/usr/bin/git` is a stub that is on PATH
  but fails (`xcrun: error: invalid active developer path`); LADO reports that folder as
  "not inside a git repository". So it does a folder git refuses to read ("detected dubious
  ownership").
- `lado doctor` does not check git at all; LADO needs git 2.31 or newer
  (`rev-parse --path-format=absolute` in `providers/gitpaths.py`), and with an older one
  the providers' folder-trust lookup is silently wrong.
- The New session window shows the core's reason ("does not exist", "not inside a git
  repository", "has no commits yet") with no word on what to do; its `has_commits` is
  false for every refusal, and the UI does not use it.

The root cause is one: LADO's git calls take a running git for granted, and the folder
check has one error kind for every git failure. This is the first task of the "getting
started with LADO" series (LAD-6 starts a session from a git URL and builds on it).

## What Changes

- The core tells the cases of a folder apart (`runtime.check_repo`): the path does not
  exist; it is a file, not a folder; git is not installed or not on PATH; git does not
  run; the folder is not inside a git repository; git refuses to read it (git's own first
  line); the repository has no commits. Each refusal has a kind, and where the human can
  act, a hint: a sentence and one command to copy.
- `lado start` prints the reason and, on the next line, the hint. The UI's folder check
  gives the kind and the hint; the New session window shows the reason with the hint's
  command in a code field with a Copy button (mockup `mockup-folder-check.html`, variant 2).
- No LADO command and no API endpoint ends in a traceback or a 500 because git is missing:
  `runtime.git` and `gitcache._git` turn "cannot run git" into their usual errors.
- `lado doctor` checks git: missing or not running is `FAIL` with the install hint for
  this OS; older than 2.31 is `WARN` naming what is wrong then; else `OK` with its version.
- The System panel (`GET /api/system`) and its issue report show git's version beside
  tmux.
- **BREAKING (API)**: `FolderInfo.has_commits` is replaced by `problem_kind` and `hint`;
  only LADO's own UI reads it. New minor release: 0.36.0.

## Scope

- The folder check's kinds and hints in the core, the CLI and the New session window.
- No traceback or 500 for a missing git in every place LADO runs git.
- `lado doctor`'s git check; git's version in the System panel and its report.
- Docs: `docs/design/ui.md` (New session window, System panel), `docs/install.md`
  (Common problems), AGENTS.md (Layout), CHANGELOG.md.

## Out of scope

- A button that makes the repository and its first commit from the window: LADO would
  change the human's folder and choose what goes into the commit without them seeing it;
  "I have no repository yet" is LAD-6 (clone from a URL). The human's decision.
- Starting a session from a git URL, projects, sessions on a project: LAD-6, LAD-7, LAD-8.
- Checking git on the agents' PATH (the login shell's): agents run git through their
  CLIs, and a missing git there shows in the agent's own work; LADO's own git calls run
  on its process's PATH, which is what this change checks.
- Refusing git older than 2.31: most of LADO works with it; a warning names what does
  not. The human's decision.

## Acceptance criteria

- AC-1: With no git on PATH, `lado start <folder>` exits 1 with `lado: git is not
  installed or not on PATH (<PATH>)` and the install hint, no traceback.
- AC-2: With no git, `GET /api/folders` answers 200 with `ok: false`, `problem_kind:
  "no_git"` and the hint, and `POST /api/sessions` answers 400 with the reason; neither is
  a 500. `lado kits add` exits 1 with the same reason.
- AC-3: A git that is on PATH but fails `git --version` (the macOS stub) is reported as
  "git does not run: <its first line>" with the Xcode tools hint, not as "not inside a git
  repository".
- AC-4: The folder check names each case with its own kind and text: `missing`,
  `not_folder`, `no_git`, `git_broken`, `not_repo`, `git_refused`, `no_commits`; a hint
  with a command for `no_git`, `git_broken`, `not_repo` and `no_commits`, none for the
  others.
- AC-5: The New session window shows the reason and, when there is a hint, its sentence
  and its command in a code field with a Copy button; Start stays off.
- AC-6: `lado doctor` has a `git` line: `FAIL` when git is missing or does not run (with
  the install hint for the OS), `WARN` below 2.31, `OK` with the version otherwise.
- AC-7: The System panel shows `git <version>` (or "not installed" / "does not run") and
  the copied report has a `git:` line.
