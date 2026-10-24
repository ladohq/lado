## Context

`projects.unpushed(folder)` is the one scan behind every "what would be lost" preview:
`projects.deletion` (the CLI's `lado project delete`, `GET /api/projects/{id}/deletion`,
the project page's Delete window) and `projects.removal` of a real repository folder
(`lado project repo remove`, the server's removal preview and the repository's Remove
window). It lists the folder's entries that are folders holding a `.git`, using them three
ways: each gets a line of its own, their names are left out of a root repository's
`git status` (`skip`), and their worktrees' real paths hide an entry that is one of them
(`listed`). `entry.is_dir()` and `os.path.lexists(entry / ".git")` both follow a symbolic
link, so a link to a repository enters all three.

## Decisions

### D1. A link stays in the root's `skip`

When the project's folder is itself a repository's root, an untracked link in it would
otherwise become `the project's folder: uncommitted changes`: a new false line in place
of the old one. The link is one of the folder's entries the human sees as a repository
(`lado project show` lists it, marked as a link), and the living rule already keeps the
project's repositories out of the root's changes. So the list of entries with a `.git` is
read once, and `skip` takes all of it, links included.

### D2. A link is neither scanned nor used to hide an entry

The entries scanned (their own lines and the `listed` worktrees) are the ones that are no
symbolic link (`not entry.is_symlink()`). Removing the folder removes a link and never
follows it, so nothing behind it is lost. A worktree in the folder of the link's
repository is then no longer hidden as "the link's", and gets the line of its own that
any worktree of a repository outside the folder gets: its uncommitted changes are lost
with the folder.

### D3. No preview line for a link

The preview lists what is lost, not what stays; option B of the proposal is out of scope.

### D4. Tests at the unit layer

The scan runs git in-process on real repositories in a temp folder (the existing
`unpushed` tests do the same); no other process, tmux or agent takes part, so no
integration test. The CLI, the API and the UI show `Deletion.unpushed` as they are given
it, already covered by their tests.

### D5. No CHANGELOG line

Both previews are new in `## 0.43.0 (unreleased)`; no release has shown the false line,
and the items there already describe the previews (docs/release.md, CHANGELOG.md rules 6
and 7). Patch-level: no CLI, API, MCP or schema change.
