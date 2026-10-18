## Context

A session starts in a folder that `runtime.check_repo` accepts: a git repository with a
commit (LAD-5's kinds and hints), from `lado start <folder>`, from `lado start <git-url>`
after a clone (LAD-6, `lado.clone`), or from the New session window (`web/src/Launch.tsx`,
`POST /api/sessions` with `where: {kind: "folder", path}`; another kind is 400 "not
supported yet"). LADO needs no remote: the core reads `origin` only to show it. For a
folder that is not a repository the window prints `git init && git add -A && git commit
-m 'First commit'` to run in a terminal; LAD-5 decided that the window makes no
repository itself, as it would pick which of the human's files go into a commit.

In LADO's container (the recommended install), `docker/entrypoint.sh` writes
`LADO_GIT_NAME` and `LADO_GIT_EMAIL` into git's global config at every start and warns
on stderr when either is missing. A PyPI install uses the machine's git config.

`runtime.slug` turns any text into a name of `[a-z0-9_-]`, `lado` when nothing is left:
a Cyrillic name becomes `lado` today. A session has an optional title (LAD-66,
`runtime.set_title`).

Root cause: the only ways into LADO assume the human already has a repository or a URL;
nothing in the core makes one, though for a new, empty folder there is nothing to choose.

## Options

1. **A fresh start in the core for a new or empty folder, a third source in the window,
   `--new` in the CLI** (chosen). LADO makes the folder, `git init` and an empty commit;
   the human's files never go into it. Long-term cost: one small module and one endpoint;
   the coming Projects (ROADMAP, Later) can make a new repository of a project the same
   way.
2. **A button for any folder that is not a repository** (`git init && git add -A &&
   git commit`). Covers a folder of documents too, but brings back LAD-5's risk: secrets or
   gigabytes committed without the human seeing the list. Left for a task of its own, with
   a preview (the human's decision).
3. **Sessions without git** (all agents in one folder, no worktrees). No git to explain
   at all, but every flow, the workers' isolation and the review rely on branches and
   worktrees; a rewrite of the core. Rejected.

Held against ROADMAP.md: Stage 7's desktop app runs the same server and window; the coming
Projects (sessions over several repositories) keep the word "project" free, so this
feature says "from scratch". Design principles: *Neutral core*: no provider is involved,
every provider gets the same repository; *One source of truth*: the names, the
transliteration, the target check and the author check live in `lado.scratch`, and the
CLI, the API and `lado doctor` only print what it says; *No silent drops*: every refusal
has its text and, where the human can act, a hint; a failed step leaves nothing; no
made-up author; *Only what is used*: no MCP tool, no preview of files, no other scripts'
transliteration; *Explicit lookup*: the folder is shown and editable before anything is
made.

## Decisions

- **D1. `src/lado/scratch.py`** (standard library only; git through `runtime._run_git`
  and `runtime.git`, which turn a missing git into LAD-5's `no_git`): `Names(name, title)`
  and `names(text) -> Names` (raises `ScratchError`, a `LadoError` with `kind` and
  `hint`); `TargetState = Literal["new", "empty", "inside_repo", "not_empty",
  "not_folder"]`, `CAN_START = ("new", "empty")`, `Target(path, state, text, root)` and
  `check_target(path) -> Target`; `default_folder(name) -> Path` (`clone.default_parent()
  / name`); `author_problem(path) -> ScratchError | None`; `make(path, name) -> str` (the
  repository's root). It imports `runtime`, `clone`, `update` and `lado.text`; nothing
  below it imports it.
- **D2. Transliteration.** One table `CYRILLIC` (Russian, Ukrainian, Belarusian letters as
  the spec lists, capitals by `str.lower` first), then `unicodedata.normalize("NFKD")`
  without combining marks, then `runtime.slug`; an empty result (slug's fallback `lado`
  is not taken here: `scratch.names` checks the text before the fallback) is the refusal.
  `runtime.slug` itself is unchanged, so `lado start <folder>` names stay as they are.
- **D3. The title** is the trimmed text, passed to `runtime.start_session(title=)`, which
  checks it with `set_title`'s rule (factored out as `runtime.check_title(text, name) ->
  str | None`) before anything starts and stores it with the new session
  (`state.Session.title`, a field that exists since schema 28; no migration). A resume with
  a title raises `LadoError("a title is set with lado title on a resume")`.
- **D4. Empty** is `not any(entry.name != ".DS_Store" for entry in folder.iterdir())`.
  **inside_repo**: `git rev-parse --show-toplevel` (`LC_ALL=C`) in the path when it exists,
  else in its nearest existing ancestor; a 0 exit is inside, git's "not a git repository"
  is outside, any other failure is LAD-5's `git_refused`. A folder LADO may not read is
  `ScratchError("no_access", "cannot look at <path>: <reason>")`.
- **D5. The author** is `git -C <nearest existing folder> config --get user.name` and
  `user.email` (`LC_ALL=C`), both non-empty; the folder is in no repository (D4), so only
  the global and system configs (and their includes) answer, which are what the agents'
  git will read. Environment variables (`GIT_AUTHOR_NAME` …) are not looked at: the agents
  get their environment from the login shell (`agent_env`), not from the server's. The
  container is `update.in_container()`. `lado doctor` calls `author_problem("/")`, as the
  container's entrypoint looks from `/`.
- **D6. `make`**, in order: `names`-free checks again (`runtime.check_name(name, path)`,
  `check_target`, `author_problem`), then `Path.mkdir(parents=True)` remembering the
  topmost folder it created; `git init --quiet` (no `-b`, which needs 2.28); the branch:
  `git config --get init.defaultBranch` there, else `main`, set with `git symbolic-ref HEAD
  refs/heads/<branch>`; `git -c commit.gpgsign=false commit --allow-empty --no-verify
  --quiet -m "Start from scratch"`, with `GIT_TERMINAL_PROMPT=0` and stdin closed. On any
  failure: `shutil.rmtree` of the topmost folder it created, or of `<path>/.git` for an
  empty folder it was given; then `ScratchError("git_failed", "git could not make <path> a
  repository: <git's first line>")`.
- **D7. CLI.** `--new` on `lado start` (store_true). With it: a git URL or a second
  folder is a usage error; the path is made full (`os.path.abspath` after `~`, as
  `lado start` takes relative paths today); `scratch.make(path, slug(--name or folder
  name))`; the line `Made <path> a git repository with an empty first commit`; then
  `cmd_start`'s normal path with that folder. A start refused after `make` prints `lado:
  the repository stays in <path>` after the refusal, as the clone's `the clone stays in`.
  The refusals print `lado: <text>` and the hint line (`Hint.line`), exit 1. `--new` does
  not take a title (`lado title` sets one).
- **D8. API.** `models.ScratchTarget` (the spec's fields; `author: ScratchProblem |
  None`, `ScratchProblem(text, hint: HintInfo | None)`), `GET /api/scratch-target`
  (guarded as `/api/clone-target`), `Launch.title: str | None`, `Where.kind` `"folder" |
  "scratch"` (still a `str`, refused otherwise). `start()` for `scratch`: `scratch.make`
  in a `ScratchError` → 400 with the text; then `runtime.start_session(path, name, …,
  title=given.title, resume=False)`. `FolderInfo.scratch: bool = False`, set in
  `launch.folder_info` when `kind in ("missing", "not_repo")` and `check_target(path)`
  is `new` or `empty` (a check that fails is false). `make web-types` and both files
  committed.
- **D9. Window.** `source: "scratch" | "folder" | "url"`; the initial source is Folder,
  and becomes From scratch once `/api/folders/recent` answers `[]` unless the human has
  touched the switch or a field (one ref, as `touch` for kits). From scratch: the Name
  field (`aria-label` "Name"), `Create in` (`into` state as Clone into: null follows the
  server's default), `GET /api/scratch-target` 200 ms after typing, the answer of the
  latest request only; the notes as the spec says (`field-note`, `field-note ok`,
  `field-note bad` with `FolderHint` for the author). The session Name field and its
  `NameHint` are hidden; `name_state` shows under Name with NameHint's texts. Kits,
  Provider (the answer's `provider`), mode, first message, Advanced as for a clone's
  folder. `Create and start` posts the start; on a 400 or 409 it asks `GET /api/folders`
  for the path and, when `ok`, switches to Folder with it and keeps the refusal shown. In
  Folder, `FolderInfo.scratch` renders the sentence and a `chip-button` **Start from
  scratch here** inside the `folder-hint`, in place of LAD-5's command for `not_repo` and
  under the text for `missing`. The mockup is `task/lad-98/mockup-from-scratch.html`.
- **D10. lado doctor.** `check_git_author()` after `check_git()` in `run_checks`; `None`
  (no line) when `runtime.git_version()` raises. The bug report (`doctor.report`) gets no
  line: its facts are the System panel's, and the check names no value anyway.
- **D11. Version.** Minor: a UI, API and CLI feature (CHANGELOG under the next minor's
  unreleased heading). No schema migration, no MCP tool.

## Test plan

AGENTS.md's layers, the lowest that catches each requirement:

- Unit, `tests/test_scratch.py` (real git in `tmp_path`, `HOME` and
  `GIT_CONFIG_GLOBAL` pointed at a temp file): `names` (every spec scenario, the table
  letter by letter, capitals, hidden character, 81 characters, empty); `check_target`
  (each state, `.DS_Store`, a new path under a repository, a path through a symbolic
  link, a folder not readable); `author_problem` (both set, one missing, container hint
  with `LADO_CONTAINER=1`, outside hint); `make` (a new folder with parents, an empty
  folder, the branch from `init.defaultBranch` and `main`, one empty commit, clean
  status, a global `commit.gpgsign=true` with no key still commits, a failing commit by a
  fake `git` on PATH removes the made folder or `.git`, a name taken refuses before
  anything).
- Unit, `tests/test_runtime.py`: `start_session(title=)` stores the title, a bad title
  refuses before anything starts, a resume with a title refuses; `check_title`.
- Unit, `tests/test_cli.py`: `--new` with a URL or a second folder exits 2; `not_empty`,
  `inside_repo`, no author refused with their hints and nothing made; `make` then
  `start_session` called with the folder; a refused start prints `the repository stays
  in`; `lado start <folder>` without `--new` unchanged.
- Unit, `tests/test_server_launch.py`: `GET /api/scratch-target` (default path with and
  without `LADO_REPOS`, a refused name with `path: null`, states, author, `name_state`,
  `warning` in the container); `POST /api/sessions` with `scratch` (made and started, the
  title stored; 400 before anything for each refusal; another kind still 400);
  `FolderInfo.scratch` true and false.
- Unit, `tests/test_doctor.py`: the `git author` line ok, warn with each hint, no line
  without git, no name or email in the output.
- Integration, `tests/integration/test_scratch_start.py` (marker `integration`): `lado
  start --new <tmp>/shop --no-attach` with the fake agent: the session runs, its worker
  gets a worktree of the new repository; and `POST /api/sessions` with `scratch` against a
  real `lado server` process, title shown in `GET /api/sessions`. It crosses processes
  (tmux, git, the server).
- Web, `web/src/Launch.test.tsx` (vitest): the three-way switch; From scratch chosen with
  no recent folders and Folder with some; the name note with and without a title; the
  folder states; the author hint with Copy; the button's on and off; the request's
  `where` and `title`; a refused start switching to Folder; Start from scratch here
  filling Name and Create in.
- UI e2e, `tests/ui/test_launch.py` (marker `ui`): from an empty `LADO_HOME`, the window
  opens in From scratch, `Сайт кофейни` is created and started, Activity opens with the
  title; Start from scratch here on an empty folder. Screenshots of each screen of the
  mockup that the server can produce (a git config without the author by
  `GIT_CONFIG_GLOBAL`).
- Regression: `make lint`, `make test`, the changed integration and UI files with their
  markers, `make web`, `openspec validate --specs --strict`. No smoke or live test: no
  provider, hook or agent launch changes.

## Risks

- A git config the server's process reads differs from the agents' (a server started by a
  service with another `HOME`): the check would pass and an agent's commit fail. The
  agents run as the same user in practice; `lado doctor` names the author check, and a
  refused agent commit names git's own reason.
- `git init`'s templates (`init.templateDir`) may add hooks; `--no-verify` keeps them out
  of the first commit, and later commits are the agents' and the human's.
- Transliteration choices (`й` → `i`, `х` → `kh`) are one table; the human sees the name
  before anything is made and can edit Create in.
