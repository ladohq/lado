Task: LAD-140

## Why

Symptom: a symbolic link directly in a project's folder (`<ws>/projects/shop/docs` → a
repository elsewhere) is scanned as one of the folder's repositories. When the link's
target has uncommitted changes, branches not pushed or stashes, `lado project delete shop`,
`GET /api/projects/shop/deletion` and the project page's Delete window list them as work
the delete loses (`docs: uncommitted changes; …`), and so does `lado project repo remove`
and the server's removal preview for a repository folder that holds such a link. Nothing
extra is deleted: the folder is removed with `shutil.rmtree`, which removes a link and
never follows it, so the target stays. The warning is false, and it may scare the human
off a safe delete or train them to ignore the list.

Cause: `projects.unpushed` (`src/lado/projects.py:813-817`) picks the folder's entries by
`entry.is_dir() and os.path.lexists(entry / ".git")`; both follow a link, so a link to a
repository passes as a repository directly in the folder. The rest of the code already
treats a link as no repository (living spec `projects`, "A project's repositories are read
from the disk"; `removal` gives a link no unpushed work). Found by the external review of
LAD-139 (E6); the scan predates the delete screens that show it.

Options weighed:

- A (taken): `unpushed` scans no link: a link directly in the folder is neither a
  repository of its own line nor counted through it. A few lines and two unit tests; no
  long-term cost, and the scan agrees with the repositories' rule of the living spec.
- B: skip links and add a line to the preview, `docs: a link, its target stays`. New text
  in the CLI, the API and two UI windows, with their spec scenarios and UI tests, to say
  what the folder's kind already implies; nothing in the preview names other things that
  stay either.
- C: follow a link and list its target's work only when the target lies inside the
  project's folder. The delete never follows a link, so such work is not lost either: a
  second source of the same false warning, with more code.

## What Changes

- `projects.unpushed` leaves symbolic links out of the repositories directly in the folder
  it scans: no line of their own, and their repositories' worktrees are no longer used to
  hide an entry of the folder.
- When the project's folder is itself a repository's root, a link directly in it stays out
  of the root's `uncommitted changes`, as the project's repositories do (no new false
  line).
- The living spec `projects` says so in two requirements, with a scenario each.
- `docs/design/projects.md`, "Deleting": a link in the folder is not scanned.

## Scope

`src/lado/projects.py` (`unpushed` and its docstring), `tests/test_projects_core.py`,
`tests/test_project_repos.py`, the spec delta, `docs/design/projects.md`.

## Out of scope

- A preview line that names the folder's links (option B): the reason is under option B;
  a separate task if the human wants it.
- The other gaps between `unpushed`'s entries and the repositories' rule (an entry whose
  name starts with `.`, a subfolder of a repository that holds its own `.git`): no symptom
  reported; a change of the scan's reach, not of this defect.
- `lado project show` and `GET /api/projects/{id}`: they already name a link as a link.
- CHANGELOG.md: the project delete and the repository removal are new in
  `## 0.43.0 (unreleased)` and no release has shown the false line; their items there
  already promise the unpushed work (docs/release.md, CHANGELOG.md rules 6 and 7).

## Acceptance criteria

- AC-1: A project folder holding `docs`, a link to a repository outside it with an
  uncommitted file and a branch not pushed, gives no unpushed line: `projects.unpushed`
  and `projects.deletion("shop").unpushed` are `[]`.
- AC-2: Beside that link, a real repository `frontend` of the folder with work not pushed
  is still named, its line unchanged.
- AC-3: When the project's folder is a clean, pushed repository's root holding such a link,
  the list is empty: no `the project's folder: uncommitted changes` for the link.
- AC-4: A worktree directly in the folder, of the repository the link points to, with an
  uncommitted file, is still named by a line of its own (`<name>: uncommitted changes`),
  no longer hidden behind the link.
- AC-5: `make lint`, `make test` and `openspec validate unpushed-skips-links --strict`
  pass; CI green on the pull request's last commit.

## Impact

A patch-level fix (no CLI, API, MCP or schema change); it ships in 0.43.0 with the
feature. Neutral core: `projects.py` has no provider code; nothing differs per provider.
