## Context

The workspace is `clone.repos_folder()` today: `LADO_REPOS` or None. Its callers are the
clone's and a fresh start's default parent (`clone.default_parent`, falling back to
`clone.DEFAULT_PARENT = "~/lado"`), the container's warning (`runtime.outside_repos`),
`lado doctor` (`doctor.check_repos_folder`, no line without `LADO_REPOS`) and the server's
`GET /api/repos-folder` (`ReposFolder{path: str | None}`), which the New session window
reads for its placeholders, its Workspace row and its subfolder hints. The root cause of
the step's workspace part: the workspace is optional in the code, so every caller has its
own fallback (`~/lado`, `~/projects/app`, no line, no row).

LADO has no project at all. `lado.db` is at schema 31; a migration is a step of
`state.MIGRATIONS`, backed up by `state.migrate`, undone in tests by
`tests/agent_helpers.schema_before`. The human-only rule of the CLI is `cli._human_only`
(`LADO_AGENT`), used by `flow-set` and `answer`. The session title's rule is
`runtime.check_title` (trim, empty or equal to the name is none, 80 characters,
`lado.text`'s line rule).

Model and decisions: `docs/design/projects.md`, the concept `projects-concept`, the epic's
plan (S2) and `decisions.md` (D3, Q3). The human's answers of this step: question #613.

## Goals / Non-Goals

Goals: one workspace function with the `~/workspace` default; a project record, its
derived folder and `lado project`; `lado doctor` on the workspace and projects; S1's
leftover names.

Non-goals: sessions in projects, repositories, variables, UI of projects (S3–S7);
`LADO_WORKSPACE` in compose (S2b).

## Options

For the workspace:
1. **One function `projects.workspace() -> Path`, never None** (chosen). Every caller loses
   its fallback; the default lives in one constant. Long-term cost: none; S3's refusal
   inside `projects/` and S4's repositories take the same function.
2. Keep `repos_folder() -> Path | None` and add the default in `default_parent` only.
   Cheaper now, but the server, doctor and projects would each add `or ~/workspace`: the
   second source of truth the brief forbids.

For "projects/ is the human's own folder":
1. **Derived from the disk and `lado.db`** (chosen, #613): no marker file in the human's
   folder; the rule reads what is there. Cost: after the last project is deleted, a stray
   folder blocks the next `create` until it is moved; the refusal names it.
2. A marker file `projects/.lado`: a simpler rule, but a file of LADO in the human's
   folder that can be copied, synced or deleted, and a second truth beside `lado.db`.

For the project module:
1. **A new core module `src/lado/projects.py`** (chosen): the workspace, the id rule, the
   folder, the ownership rule, create, rename, delete, the unpushed scan; the CLI and
   doctor only print what it says. S3–S5 grow it.
2. Inside `runtime.py`: already the largest module; projects are not about running agents.

## Decisions

**D1. `projects.workspace()`.** `WORKSPACE_VAR = "LADO_REPOS"`,
`DEFAULT_WORKSPACE = "~/workspace"`. Returns `LADO_REPOS` expanded when absolute, else
`~/workspace` expanded; never None, never makes the folder. `projects.workspace_source()`
gives `"LADO_REPOS"`, `"default"` or `"ignored"` (set but not absolute) for doctor. It
lives in `projects.py`, which imports only `state`, `runtime` (errors, `check_title`) and
the standard library; `clone` and `scratch` import it.

**D2. Renames around it.** `clone.repos_folder`, `clone.REPOS`, `clone.DEFAULT_PARENT` and
`clone.default_parent` are removed; `clone.default_folder` and `scratch.default_folder`
call `projects.workspace()`. `runtime.OUTSIDE_REPOS`/`outside_repos` become
`OUTSIDE_WORKSPACE`/`outside_workspace` (same text); its "no workspace" branch goes, so
in a container every folder outside the workspace is warned about (the image always sets
`LADO_REPOS`). `doctor.check_repos_folder` becomes `check_workspace`, always a Check. The
API model `ReposFolder` becomes `Workspace{path: str, made: bool}`; the path
`/api/repos-folder`, the capability `repos-folder` and the handler's URL stay (an
installation's API; openspec cannot rename a capability). `web/src/api.ts`:
`getReposFolder` becomes `getWorkspace`, the type `Workspace`; `Launch.tsx`'s `repos`
becomes `workspace` (path) and `made`. Old names are not kept as aliases (only what is
used).

**D3. Making the workspace.** Nothing makes it eagerly. A clone already makes its parents
(`clone.py`, `folder.parent.mkdir(parents=True)`); a fresh start makes its folder with
parents (`scratch.py`); `projects.create` makes `<ws>/projects/<id>` with parents. The
doctor's write probe runs only on an existing folder; for a missing one the line is
`info, not made yet`.

**D4. `LADO_REPOS` not absolute** (#613, point 1): ignored, the default is used, doctor
warns `LADO_REPOS is not an absolute path: <value>; LADO uses <default>` with the hint it
has today. The default folder's own state is not checked on that line (one finding per
line, as today).

**D5. The table.** `projects(id TEXT PRIMARY KEY, title TEXT, created_at TEXT NOT NULL)`,
`created_at` in the format of `sessions.created_at`. `SCHEMA_VERSION = 32`,
`MIGRATIONS[32] = [PROJECTS_TABLE]`, `PROJECTS_TABLE` also in the fresh schema;
`schema_before` drops the table for 32. No journal triggers (`changes`): the UI feed
does not show projects until S6, which adds them (only what is used). One new table, no
existing table changes: within the brief's threshold.

**D6. Create order.** Id rule → agent refusal (`cli._human_only`) → workspace usable (a
missing workspace is fine; an existing non-folder or unwritable one refuses with
doctor's text) → the record exists → the folder exists (`lexists`, so a dangling link
counts) → `projects/` is the human's → in one `lado.db` transaction: insert, `mkdir
(parents=True, exist_ok=False)`, commit; a failed mkdir rolls the insert back. A race
with another `create` of the same id fails on the primary key or the `exist_ok=False`.

**D7. The ownership rule** (#613, point 2): `projects/` exists and is a folder; entries =
names not starting with `.`; owned by the human when entries is non-empty and none is the
id of a project in `lado.db`. Foreign entries (for doctor) = entries that are no
project's id, files included. Names are listed sorted, at most three, then `…`.

**D8. Delete.** Refuse without `--yes` after the scan, exit 1. The scan: each direct
subfolder holding `.git` (folder or file), and each worktree `git worktree list
--porcelain` names inside or outside the folder; per one, `git status --porcelain
--untracked-files=normal` (non-empty: `uncommitted changes`) and
`git for-each-ref refs/heads --format=%(refname:short)%00%(upstream)%00%(upstream:track)`
(no upstream, or `ahead` in track: `branch <b> not pushed`); git runs with the clone's
`NO_PROMPT` environment and a timeout; a failure is `could not check: <first line>`.
No network: what "pushed" means is the last fetch's view, said in `docs/cli.md`. Removal:
`<ws>/projects/<id>` is checked to be a direct child of `realpath(<ws>/projects)` by its
own parent's real path; a symbolic link is `unlink`ed; a folder goes by `shutil.rmtree`
without following links; then the record is deleted. An rmtree error keeps the record
and names the first path left.

**D9. Agents.** `create`, `rename`, `delete` call `cli._human_only("project <command>")`,
the one rule of human-only commands (`LADO_AGENT`, which every agent has beside
`LADO_SESSION`, `providers/base.py`). No MCP tool. `list` and `show` are open.

**D10. Output.** As #613, point 3: `list` columns padded to the longest id and title,
ids sorted; `show` with `made` in local time `YYYY-MM-DD HH:MM`; refusals are
`runtime.LadoError` subclasses printed as `lado: <text>`, exit 1, as other commands do.
`lado project` with no subcommand prints its help (as `lado kits`).

**D11. Doctor's Projects check** (#613, point 4): placed after Workspace; none when no
project and no `projects/`; `ok`/`warn` as the spec says; a `projects` that is a file is
`warn` `<ws>/projects is not a folder`. The Workspace line shows the full path (not
`~/workspace`), as the `LADO_REPOS` line does.

**D12. The window** (#613, point 5; mockup `mockup-workspace-where.html`): placeholders
always from `workspace.path`; the Workspace row, the focus list of an empty Where and
`toCheck`'s skip of the workspace itself use `made` for the row and the list (the skip
stays by path). The server's `CloneTarget.path` and `ScratchTarget.path` already come
from the core, so they follow D1 with no UI change.

**D13. S1's leftover** "the projects' toolchains" → "the repositories' toolchains" in
the four places the brief names, and the anchor `#the-projects-toolchains` wherever it is
linked. The container spec's scenarios that say "a project under `LADO_REPOS`" are left
to step S2b, which changes that spec anyway (the human, #615; proposal, Out of scope).

**D14. Version.** Minor: a schema migration and a new CLI command. CHANGELOG's
`## 0.42.1 (unreleased)` becomes `## 0.43.0 (unreleased)`; two lines under Added and
Changed.

## Risks / Trade-offs

- A human who relied on `~/lado` as the clone default finds new clones in `~/workspace`.
  Mitigation: CHANGELOG, `lado doctor`'s Workspace line, and the window's placeholders say
  where.
- `delete` trusts the last fetch for "pushed". Mitigation: the text says so; `--yes` is
  always needed.
- `rmtree` of a large folder can fail halfway (a file in use, permissions). The record
  stays and the command names what stayed, so it can be run again.

## Test layers

| Requirement | Layer | Where |
|---|---|---|
| workspace function, relative and unset values | unit | `tests/test_projects.py`, `tests/test_clone.py` |
| doctor Workspace line (LADO_REPOS, default, not made, file, unwritable, relative) | unit | `tests/test_doctor.py` |
| doctor Projects line (ok, foreign, missing, human's own, none) | unit | `tests/test_doctor.py` |
| id rule, title rule, ownership rule, create order and rollback | unit | `tests/test_projects.py` |
| unpushed scan (dirty, no upstream, ahead, worktree, broken repo) | unit with real git in tmp | `tests/test_projects.py` |
| delete: link, outside check, rmtree failure keeps the record | unit | `tests/test_projects.py` |
| schema 31 → 32 with backup | unit | `tests/test_state.py` (via `previous_schema`) |
| clone and fresh start default in `~/workspace` (HOME = tmp) | unit | `tests/test_clone.py`, `tests/test_scratch.py`, `tests/test_server_launch.py`, `tests/test_server_clones.py` |
| `GET /api/repos-folder` `{path, made}` | unit | `tests/test_server_launch.py` |
| `lado project` commands end to end, folders made and removed, refusals, agent refusal, delete with unpushed work | integration (real processes, git) | `tests/integration/test_projects.py` |
| `lado doctor` as a process with and without `LADO_REPOS` | integration | `tests/integration/test_projects.py` |
| the window: no row or hints while not made, row and hints once made, placeholders | vitest + UI e2e | `web/src/Launch.test.tsx`, `tests/ui/test_launch.py` |

No provider is involved: the change is above `providers/` and works the same for every CLI.
