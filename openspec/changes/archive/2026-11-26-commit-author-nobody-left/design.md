## Context

LAD-312 gave LADO three commit authors over git's own (project → git server → LADO → git) and
one answer to "who signs a commit here": `lado.commit_authors.in_effect(path, project_id)`,
source `none` when nobody does. The CLI asks it only for LADO's own line
(`cli._lado_author_line`); the project's and a server's lines are fixed texts, and every
change ends with `git_servers.AUTHOR_RESTART`.

## Decisions

- D1. One helper, `commit_authors.unsigned(paths, project_id=None) -> list[str]`: the paths of
  `paths` whose `in_effect(path, project_id).source` is `NONE`, in the given order. It raises
  what `in_effect` raises (`Unreadable`, LAD-5's `FolderProblem`). Why: one source of truth,
  the launch's own order; no second judgement of "nobody" in the CLI.
- D2. A project's places are its repositories (`projects.repositories(id)`), named by their
  folder name in the line; a project without repositories is judged at its folder
  (`projects.folder(id)`), which gives "all". All unsigned → the "nobody else signs" line;
  some → the line naming them, joined by `, `. Why: a repository's remote decides a server's
  author, so only the repositories can tell.
- D3. A server and LADO are judged outside any repository: `lado()` is None and
  `git_own("/")` is None (as `_lado_author_line` does now). Why: a server's repositories are
  not known to LADO; its fallback is LADO's and git's global author.
- D4. The texts are constants next to their kin: in `commit_authors` the hint `SET_HINT`
  (`Set one in Settings → Git servers, or run: lado git-server author --name "Your Name"
  --email you@example.com`, also the second line of `LADO_NOBODY`) and `RUNNING_KEEP`
  (`Running agents keep the author they started with until they restart.`); in `cli.py`
  the project's lines next to `PROJECT_AUTHOR_NONE`; in `git_servers` the server's next to
  `AUTHOR_CLEARED`. The running-agents line replaces `AUTHOR_RESTART` whenever any place is
  unsigned after a clear. Why: the existing layout of these texts.
- D5. Order of a clear: clear first, then judge, as `_lado_author` does now. A clear's first
  line (`LADO has no commit author now.`) is flushed before git is asked; a git that cannot
  read its config or does not run is the one-line error and exit 1 that `_lado_author_line`
  gives, the clear kept. For a project or a server, whose clear printed nothing before, the
  error comes alone and the clear is kept; the show of a project or a server can now exit 1
  the same way. Why: one behaviour for the three levels; a show that cannot know must not
  guess.
- D6. The exit status of a clear that leaves nobody stays 0; nothing is refused. Why: the
  clear is done, and the choice of who signs is the human's (option C of the proposal).
- D7. No UI, API or schema change. Why: the UI shows "Nobody" already (LAD-312); a patch.

## Tests

All unit (`tests/test_cli.py`, `tests/test_cli_git_server.py`), with the existing
`git_config` fixture writing an empty git config for "git knows none": the commands are one
process and git's config reading is already proved by LAD-312's tests; no integration test
is needed, as nothing crosses processes beyond the git `in_effect` already runs.
