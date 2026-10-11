## Context

LADO runs git in four places: `runtime.git` (sessions, worktrees, the folder check),
`gitcache._git` (kits and marketplaces), `fingerprint.take` (read-only agents; it already
turns `OSError` into `FingerprintError`) and `providers/gitpaths.rev_parse` (the
providers' folder-trust lookup). The first two call `subprocess.run(["git", ...])` and let
`FileNotFoundError` out; `gitpaths` lets it out too. `runtime.check_repo` has two
refusals besides "does not exist": any failure of `rev-parse --show-toplevel` is "not
inside a git repository", any failure of `rev-parse --verify HEAD` "no commits yet".
`tmux.py` solved the same problem for tmux with `TmuxMissing`.

Root cause: the git calls take a running git for granted, and the folder check has one
error kind for every git failure.

## Options

1. **Text only**: catch `OSError` in the two git helpers, sharpen the texts, leave the API
   as is. Cheapest; the UI cannot tell the cases apart but by parsing text, and the hint
   would be part of the text, so the window could not show a command to copy. Later
   (LAD-6's clone, LAD-7's projects) every new caller re-parses text.
2. **Kinds and hints in the core** (chosen): one `FolderProblem(LadoError)` with `kind`
   and `hint`, raised by `check_repo`; the CLI and the API render it. One source of the
   texts for both surfaces; LAD-6 and LAD-7 reuse the kinds. Cost: an API field change and
   `make web-types`.
3. **A preflight service**: a separate "environment" endpoint the window asks first (git,
   tmux, providers). More moving parts than the task needs; the System panel already shows
   the environment. Not now ("Only what is used").

## Decisions

- **D1. `FolderProblem(LadoError)` in `runtime.py`** with `kind` (the seven kinds of the
  spec, a `Literal`) and `hint: Hint | None` (`Hint(text, command)`, a frozen dataclass).
  It stays a `LadoError`, so every existing `except LadoError` (the API's `core`, the
  CLI's `main`, `_root_or_none`) keeps working.
- **D2. One look at git: `runtime.git_version()`** runs `git --version` on the process's
  PATH and returns the version text, or raises `FolderProblem` of kind `no_git`
  (`FileNotFoundError`, the PATH named as `tmux.TmuxMissing` names it) or `git_broken`
  (another `OSError`, or a non-zero exit: git's first line of stderr, else stdout).
  `check_repo` calls it after the path checks and before `rev-parse`; `doctor.check_git`
  and `doctor.system_info` call it too, so the CLI, the UI and doctor cannot disagree.
  The cost is one short process per folder check; no cache, so installing git while the
  server runs takes effect at the next check.
- **D3. `not_repo` only on git's own words.** git translates its messages, so the two
  `rev-parse` calls of `check_repo` run with `LC_ALL=C` added to git's environment;
  `not_repo` is a failure whose stderr has "not a git repository", and any other failure
  is `git_refused` with git's first line.
- **D4. `runtime.git` and `gitcache._git` catch `OSError`**: `FileNotFoundError` gives the
  `no_git` text (as a `LadoError` / `GitError`), another `OSError` "cannot run git: ...".
  `gitpaths.rev_parse` catches `OSError` and returns None, as for any git failure: by then
  `check_repo` has proved git runs, so this only matters if git goes away mid-session.
- **D5. Hints by OS** come from `platform.system()` (WSL is Linux): Darwin `xcode-select --install` with "or `brew install git`" in the
  sentence; otherwise `sudo apt install git`, the sentence naming "your distribution's
  package manager" as the other way. The commands carry no path: the sentence says
  "in that folder".
- **D6. CLI rendering**: `cli.main` prints `lado: <text>`, then for a `FolderProblem` with
  a hint `lado: <hint.text> <hint.command>`, before the `__notes__`.
- **D7. API**: `FolderInfo.has_commits` is removed (no reader but tests), `problem_kind:
  FolderProblemKind | None` and `hint: HintInfo | None` added; `POST /api/sessions` keeps
  its 400 with the text. `SystemInfo` gets `git: str` (the version, `not installed` or
  `does not run`, never a path), the report a `- git:` line. `make web-types`.
- **D8. The window** renders the hint as the mockup's variant 2: the reason line in the
  `field-note bad` style, the sentence muted under it, the command in a code field with a
  Copy button built on `Copy.tsx`'s `useCopy` (its fallbacks included).
- **D9. doctor's git check** goes right after `tmux` in `run_checks`; below 2.31 is
  `WARN` (`runtime.GIT_MIN = (2, 31)`), parsed from `git version X.Y[.Z]...` (Apple's
  suffix ignored); an unparsable version is `OK` with the text.
- **D10. Version**: a new doctor check and an API change are a feature: 0.36.0. The
  CHANGELOG's `## 0.35.1 (unreleased)` heading becomes `## 0.36.0 (unreleased)`.

## Against the design principles and the roadmap

- Neutral core: nothing here depends on a provider; `gitpaths` only gets the same
  failure handling.
- One source of truth: the texts and hints live in the core; the CLI, the API, doctor and
  the panel render them.
- No silent drops: the old git that silently broke the trust lookup now warns; a git
  failure is no longer reported as "not a repository".
- Only what is used: the kinds are what the CLI and the window show today and what LAD-6
  will show after a clone.

## Risks

- D3's `LC_ALL=C` changes git's messages in the `git_refused` text to English; the rest
  of LADO's texts are English too.
- A folder check now runs one more process; measured in milliseconds, under the debounce
  of the window.
