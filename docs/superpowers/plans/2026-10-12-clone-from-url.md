# Clone from URL: implementation plan

**Goal:** a session starts from a git URL: the core clones one branch into a chosen folder
(by default `~/lado/<repo>`) with progress and cancellation, for `lado start <git-url>`
and the New session window alike (LAD-6).

**Architecture:** a new core module `src/lado/clone.py`; `cli.cmd_start` and a new
`src/lado/server/clones.py` (jobs polled by the window) call it; `web/src/Launch.tsx` gets
the Clone from URL source and starts the session through the folder's existing path.

**Spec:** `openspec/changes/clone-from-url/` (proposal, delta `session-clone`,
`design.md` D1–D14). **Design doc:** `docs/superpowers/specs/2026-10-12-clone-from-url-design.md`.
**Mockup:** run artifact `task/lad-6/mockup-clone.html` (v3).

Each task: tests first, then the code, then the named test run, then a commit (message
in the repository's style, `(LAD-6)` at the end).

## Task 1: URLs, the default folder, the same repository (D1, D2, D3)

**Files:** `src/lado/clone.py`, `tests/test_clone.py`.

1. Tests: `is_url` true for `https://…`, `http://…`, `ssh://git@host:2222/a/b.git`,
   `git://…`, `file:///srv/app.git`, `git@github.com:a/b.git`; false for `~/app`, `app`,
   `/srv/app.git`, `host:path`, `C:/x`. `default_folder("https://github.com/ladohq/marketplace.git/")`
   is `~/lado/marketplace` expanded. `same_repo` pairs: ssh scp vs https vs ssh:// with a
   port (same), `.git` or not (same), another owner (not), host case (same), two `file://`
   to one real path through a symlink (same). A failure text built from
   `https://ghp_x@github.com/a/b` holds no `ghp_x`.
2. Code: `is_url`, `Address.parse`, `repo_name`, `owner`, `same_repo`, `default_folder`.
3. `uv run pytest tests/test_clone.py -n0`; commit.

## Task 2: The target check (D3)

**Files:** `src/lado/clone.py`, `tests/test_clone.py`.

1. Tests with real repos under `tmp_path`: `new`, `empty`, `same_repo` (origin over another
   protocol; the text names the branch), `other_repo` (text names the public origin and
   suggests `<parent>/ladohq-app` when free; no suggestion when that folder exists or the
   URL has no owner), `not_empty` (a file inside; a subfolder of a repository; a repository
   without `origin`), `not_folder`. Nothing in any folder changes (compare a listing and
   mtimes before and after).
2. Code: `Target`, `check_target(url, path)`.
3. Run; commit.

## Task 3: The git runner and the failure kinds (D4, D5)

**Files:** `src/lado/clone.py`, `tests/test_clone.py`.

1. Tests: `KINDS` on recorded lines — `git@github.com: Permission denied (publickey).`,
   `Host key verification failed.`, `fatal: could not read Username for
   'https://github.com': terminal prompts disabled`, `remote: Repository not found.` /
   `ERROR: Repository not found.`, `fatal: '/x' does not appear to be a git repository`,
   `ssh: Could not resolve hostname nohost: nodename nor servname provided, or not known`,
   `fatal: unable to access 'https://x/': Could not resolve host: x`, `warning: Could not
   find remote branch dev to clone.` + `fatal: Remote branch dev not found in upstream
   origin`, anything else. Hints: github.com vs `git.example.com`; `ssh -T -p 2222
   git@host` for a port; git's line chosen by the spec's rule. The runner's environment
   holds `GIT_TERMINAL_PROMPT=0`, `SSH_ASKPASS_REQUIRE=never`, `GCM_INTERACTIVE=never`,
   `LC_ALL=C` and runs with `start_new_session=True` and stdin closed (a fake `git` on
   PATH that dumps its env and `os.getsid`/`os.isatty(0)`). No git on PATH: LAD-5's
   `no_git` text and hint.
2. Code: the runner, `CloneError`, `KINDS`, the texts.
3. Run; commit.

## Task 4: Listing branches (D6)

**Files:** `src/lado/clone.py`, `tests/test_clone.py`.

1. Tests on a bare repo made in `tmp_path` (`git init --bare`, push `main`, `develop`,
   `release/1.2`, HEAD → main): branches with `main` first and `default == "main"`; a bare
   repo with no branch: `the repository has no branches yet`; a fake slow `git` on PATH
   with `LIST_TIMEOUT` patched to 0.5: refused as `did not answer`, the process gone.
2. Code: `Remote`, `list_branches`.
3. Run; commit.

## Task 5: Cloning with progress and cancel (D7)

**Files:** `src/lado/clone.py`, `tests/test_clone.py`.

1. Tests: clone `dev` of the bare repo into a new folder (its HEAD is `dev`, all history
   there, `origin` is the URL, no `.<name>.clone-*` left in the parent); into an empty
   folder; `no branch dev` for a missing branch with nothing left; parent folders made.
   A fake slow `git` printing `Receiving objects:  10% (1/10)\r…` then sleeping: the
   `on_progress` values carry phase, percent, detail; setting `cancelled` ends it within
   a second, its process group is gone, the temp folder and the target are absent.
   `KeyboardInterrupt` raised from `on_progress` cleans up the same way. A target that
   became non-empty while cloning: `not_empty`, temp removed.
2. Code: `Progress`, the line parser, `clone`.
3. Run; commit.

## Task 6: CLI (D8)

**Files:** `src/lado/cli.py`, `tests/test_cli.py`.

1. Tests (`cli.main` with `capsys`, tmux by the recorder): `lado start ~/x --branch dev`
   and `lado start ~/x ~/y` exit 2; `same_repo` exits 1 printing its text and `lado:
   To start a session in it as it is: lado start <folder>`, nothing changed; `other_repo`
   and `not_empty` exit 1; a session `app` of another folder exists → exit 1 before any
   clone (no git process run: a fake `git` that fails the test if called for `clone`);
   a `file://` URL with `--branch dev --no-attach` clones then calls `start_session` with
   the folder; a start refused after the clone prints `lado: the clone stays in <folder>`
   and the folder is there.
2. Code: the `folder` positional, `--branch`, the clone path in `cmd_start`, progress on
   stderr, `KeyboardInterrupt` → `lado: clone cancelled`, 130.
3. Run; commit.

## Task 7: CLI integration (spec "lado start clones a git URL")

**Files:** `tests/integration/test_clone_start.py`.

1. "Clone and start": `lado start file://<bare> <tmp>/app --branch dev --no-attach` with
   the fake agent: exit 0, `<tmp>/app` on `dev`, the session runs (`lado ls`), its
   supervisor idle. Ctrl-C: a fake slow git first on the PATH of `lado`'s process; send
   SIGINT to `lado` once a `.app.clone-*` folder exists: exit 130, `lado: clone
   cancelled`, no temp folder, no target, no git process left.
2. `uv run pytest -m integration -n auto tests/integration/test_clone_start.py`; commit.

## Task 8: Server jobs and endpoints (D9, D10, D11)

**Files:** `src/lado/server/clones.py`, `src/lado/server/app.py`,
`src/lado/server/models.py`, `tests/test_server_clones.py`.

1. Tests with FastAPI's client: `POST /api/remote-branches` on the bare repo → branches
   and default; on a missing path → 400 `CloneRefused` with `kind: "not_found"`; no
   Origin → refused by the guard. `GET /api/clone-target?url=` → the default folder,
   `state: "new"`, `default_name`, `name_state: "free"`; each other state; a name taken by
   a session of another folder → `name_state: "taken_elsewhere"`. `POST /api/clones` →
   `running`, then `GET` until `done` with the folder cloned; `DELETE` while a fake slow
   git runs → `cancelled`, temp gone; a second `POST` to the same folder → 409; `GET` of
   an unknown id → 404; with `ABANDONED` patched to 0.5 s and no `GET`, the job is
   `cancelled` within 2 s; a finished job is gone after `KEPT` (patched); the server's
   shutdown cancels a running job (temp gone). No answer is a 500.
2. Code: `Jobs`, the sweeper, the endpoints, the models, the shutdown hook.
3. `make web-types`; commit with `web/openapi.json` and `web/src/api.gen.ts`.

## Task 9: The window (D12)

**Files:** `web/src/Launch.tsx`, `web/src/api.ts`, `web/src/styles.css`,
`web/src/Launch.test.tsx`.

1. vitest first, `fetch` mocked: the switch shows the clone fields; typing a URL asks
   `/api/clone-target` (200 ms) and `/api/remote-branches` (500 ms, once per URL); the
   Branch select lists them with `main (default)` chosen; more than 30 branches → the
   combobox filters by what is typed; a `CloneRefused` shows under the URL with its hint
   and Copy, the button off; `same_repo` → **Use this clone** switches to Folder with the
   path and sends no POST; `other_repo` shows the text with the suggestion, button off;
   Clone and start → `POST /api/clones`, polling shows phase, percent and bar, × and Esc
   do nothing, Cancel clone sends `DELETE` and returns to the form; `done` →
   `startSession({kind: "folder", path})` and navigation to Activity; a 409 `Taken` after
   `done` → Folder with the path and the refusal.
2. Code to the mockup v3; styles beside `.file-progress`.
3. `make web`; commit.

## Task 10: UI e2e

**Files:** `tests/ui/test_launch.py`.

1. Clone a `file://` bare repo from the window and start: Activity opens; a fake slow
   `git` first on the server's PATH for the progress screenshot; Use this clone on a
   folder cloned before. `shot` of the form, the progress and Use this clone.
2. `uv run pytest -m ui tests/ui/test_launch.py`; commit; the screenshots go into the
   build report as run artifacts.

## Task 11: Docs (D13, D14)

**Files:** `docs/design/ui.md`, `AGENTS.md`, `README.md`, `CHANGELOG.md`.

1. ui.md, Launch and session control: Where's two sources, the clone's flow, the jobs
   (polling, `ABANDONED`, `KEPT`, shutdown), the server's environment caveat, mockup v3.
2. AGENTS.md: Layout (`clone.py`, `server/clones.py`, the endpoints), the `lado start`
   paragraph.
3. README: `lado start <git-url>` in the start section. CHANGELOG under `## 0.36.0
   (unreleased)`: "`lado start <git-url> [<folder>] [--branch NAME]` and the New session
   window's Clone from URL clone a repository (by default into `~/lado/<repo>`) and start
   a session in it."
4. Commit.

## Task 12: Regression

`make lint`; `make test`; `make web`; `uv run pytest -m integration -n auto
tests/integration/test_clone_start.py`; `uv run pytest -m ui tests/ui/test_launch.py`;
`openspec validate --specs --strict`; push; CI green (the full `make check` and the smoke
on Linux and macOS).
