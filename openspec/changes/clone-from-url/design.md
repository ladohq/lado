## Context

A session starts from a folder only: `lado start [path]` (`cli.cmd_start` →
`runtime.start_session`) and the New session window (`web/src/Launch.tsx`, `POST
/api/sessions` with `where: {kind: "folder", path}`; another kind is refused "not
supported yet"). The window checks a folder with `GET /api/folders`
(`server/launch.folder_info` → `runtime.check_repo`, LAD-5's kinds and hints). LADO's
other git calls live in `runtime.git` (sessions) and `gitcache._git` (kits and
marketplaces: `GIT_TERMINAL_PROMPT=0`, a clone into a temporary folder then renamed,
`clone_branch`). Since LAD-22 the kit list does not depend on the folder; a fresh clone
has no last session, so the whole form can be filled before the clone.

Root cause: nothing in the core gets a repository from its address; the only way in is a
folder that exists.

## Options

1. **A core module plus a clone job in the server, polled by the window** (chosen). The
   core does the clone (`lado.clone`), the CLI calls it in its own process, the server runs
   it in a thread per job, held in memory, and the window asks for the job's state every
   0.5 s; a job nobody asks about is cancelled. Long-term cost: one small registry in the
   server and five endpoints; projects reuse `lado.clone` as is.
2. **One streaming request** (`POST` that streams progress, cancelled by aborting it).
   Fewer endpoints, but a reload or a network blip ends the clone with no way to tell a
   cancel from a drop, and detecting a client's disconnect from a streaming response is
   fragile to test. Rejected.
3. **Clone jobs as lado.db rows in the change feed.** Survives a server restart and needs
   no polling, but costs a schema migration and journal triggers for a job that lives
   seconds, and nothing needs it: the human chose no background clones. Rejected
   ("Only what is used").

Held against ROADMAP.md: Projects (Later) will make clones of a project's repositories
when a session starts; they take `lado.clone` (URL, default folder, target check,
clone) without the UI. Stage 7's desktop app runs the same server. Design principles:
*Neutral core*: no provider is involved; *One source of truth*: the URL rules, the
target check and the failure texts are one module, the CLI and the API only print what it
says; *No silent drops*: every failure is a text with git's line, a cancelled or failed
clone leaves nothing, an existing folder is never changed; *Explicit lookup*: the folder
is shown and editable before anything is made.

## Decisions

- **D1. `src/lado/clone.py`** (standard library only, git through its own runner like
  `gitcache._git`, not `runtime.git`, since it needs a process group and streamed stderr):
  `is_url(source) -> bool`; `Address` (`parse(url)`: scheme, user, host, port, path;
  `repo_name`, `owner`, `same_repo(other)`); `default_folder(url) -> Path`
  (`DEFAULT_PARENT = ~/lado`); `Target` and `check_target(url, path) -> Target` (state,
  text, origin through `runtime.public_remote`, branch, suggestion); `Remote` and
  `list_branches(url) -> Remote` (`branches`, `default`); `Progress(phase, percent,
  detail, line)`; `clone(url, path, branch, on_progress, cancelled: threading.Event) ->
  Path`; `CloneError(LadoError)` with `kind` and `hint` (`runtime.Hint`, LAD-5's).
  `runtime.LadoError` and `Hint` are imported from runtime; runtime does not import clone.
- **D2. URL forms.** `https?://`, `ssh://`, `git://`, `file://`, and scp form only with a
  user (`user@host:path`): a bare `host:path` would take a folder name with a colon.
  `.endswith(".git")` is not a URL (unlike `gitcache.is_git`): `/srv/app.git` stays a
  folder.
- **D3. Same repository.** Host lowercased, path stripped of leading/trailing `/`,
  trailing `.git` and, in ssh URLs, a leading `~`; scheme, user and port ignored; `file://`
  and plain paths compared by `os.path.realpath`. The folder's origin is read with
  `git -C <path> remote get-url origin` only when `<path>` is its repository's root
  (`rev-parse --show-toplevel` equals its real path); a subfolder of a repository is
  `not_empty`.
- **D4. No prompts.** Each git process: `start_new_session=True` (no controlling terminal,
  its own process group), `stdin=DEVNULL`, env `GIT_TERMINAL_PROMPT=0`,
  `SSH_ASKPASS_REQUIRE=never`, `GCM_INTERACTIVE=never`, `LC_ALL=C` on top of LADO's own
  environment. The user's `core.sshCommand`, ssh config, ssh-agent and credential helpers
  stay in force; LADO sets no `GIT_SSH_COMMAND`. Ctrl-C reaches `lado` (the foreground
  group), which then ends git's group (D7).
- **D5. Failure kinds by git's words** (`LC_ALL=C`), first match wins:
  `Permission denied (publickey` → `ssh_denied`; `Host key verification failed` →
  `host_key`; `could not read Username`, `Authentication failed`, `terminal prompts
  disabled` → `login_needed`; `Repository not found`, `does not appear to be a git
  repository`, `repository '…' not found` → `not_found`; `Could not resolve host`,
  `Connection refused`, `Connection timed out`, `Network is unreachable`, `Operation timed
  out` → `unreachable`; `Remote branch … not found` → `no_branch`; otherwise
  `git_failed`. The table of texts and hints is the spec's. One table in `clone.py`
  (`KINDS`), unit-tested line by line.
- **D6. Listing.** `git ls-remote --symref <url> HEAD 'refs/heads/*'`, killed after
  `LIST_TIMEOUT` (20 s); branches sorted with the default first; no `HEAD` symref (an old
  server) leaves `default` None and the window chooses `main`, else `master`, else the
  first.
- **D7. Clone.** Parent folders made (`mkdir -p`); `tempfile.mkdtemp(prefix=".<name>.clone-",
  dir=parent)`; `git clone --progress --branch <b> --no-recurse-submodules <url> <temp>`;
  stderr read in chunks split on `\r` and `\n`, each line matching `^(<phase>):\s+(\d+)%
  ?(.*)$` is a `Progress`; `cancelled` checked between reads and every 0.2 s; on cancel,
  failure or an exception (`KeyboardInterrupt` included): `os.killpg(SIGTERM)`, then
  `SIGKILL` after 2 s, `shutil.rmtree(temp)`. On success `os.rename(temp, target)`: a
  missing target or an empty folder (POSIX rename onto an empty directory); if the target
  became non-empty meanwhile, the temp is removed and it is `not_empty`.
- **D8. CLI.** `start.add_argument("folder", nargs="?")` and `--branch`. In `cmd_start`:
  `clone.is_url(args.path)` picks the clone path; `folder` or `--branch` without a URL is
  `parser.error` (exit 2). Order: target check → name check (`state.get_session(name)`
  with another repo → the core's `SessionExists` text) → clone (progress: each git line
  as is on stderr, `\r`-terminated when stderr is a terminal, the last line of each phase
  kept) → `runtime.start_session(folder, ...)` with `resume=None`. Without `--branch` the
  clone takes the remote's default (git's own, no listing). `KeyboardInterrupt` during the
  clone: `lado: clone cancelled`, exit 130.
- **D9. Server jobs (`src/lado/server/clones.py`).** `Jobs`, one per app: a dict of
  `Job(id: uuid4 hex, url, path, branch, state, progress, error, started, seen)` under a
  lock; each job a daemon thread running `clone.clone` with a `threading.Event`. `GET`
  sets `seen`; a sweeper (a timer every second while any job runs) cancels a running job
  whose `seen` is older than `ABANDONED` (150 s; the human's decision in review, F4: a tab
  in the background more than five minutes runs its timers once a minute in Chrome, so
  10 s cancelled live clones) and drops finished ones after `KEPT` (60 s). A page that goes
  away (`pagehide`) while its clone runs cancels it at once with `navigator.sendBeacon` to
  `POST /api/clones/{id}/cancel` (a beacon can only POST; it sends the cookie and the
  page's Origin, so it passes `Guard.changes` as it is); `ABANDONED` is the fallback for a
  window that could not say so (a lost connection, a sleeping laptop). One running job per real target path (409 `Busy`). `app.Server`'s shutdown cancels
  all jobs and waits up to 3 s for their threads. Models in `models.py`: `RemoteInfo`,
  `CloneTarget`, `CloneStart`, `CloneJob`, `CloneRefused`; `make web-types`.
- **D10. Why `POST /api/remote-branches`.** It goes to the network with the server's
  credentials; the UI's rule puts such calls under `Guard.changes` (as `POST
  /api/kits/plan`). `GET /api/clone-target` reads only the disk: token only.
- **D11. Name before the clone.** `CloneTarget` carries `default_name`
  (`runtime.slug(<folder name>)`) and `name_state` (`launch._name_state` with the target's
  real path as the root), so the Name field says "taken" before anything is cloned.
- **D12. The window** (`Launch.tsx`): `source: "folder" | "url"` state; a `CloneFields`
  component (URL, Clone into, Branch, progress) beside `WhereField`; `useAsked` for
  `/api/clone-target` (debounced 200 ms like the folder) and a 500 ms debounce for
  `/api/remote-branches`, cached per URL for the window's life; Branch is a `<select>` up
  to 30 branches, above that the Where field's combobox pattern; polling `GET
  /api/clones/{id}` every 500 ms; `busy` covers the clone, so × and Esc are off as during
  a start; Cancel clone sends `DELETE`. Done → `startSession({kind: "folder", path})`;
  refused → `source = "folder"`, `path = job.path`, the refusal shown as today. Use this
  clone → `source = "folder"`, `path = target.path`. The Folder source is unchanged.
  Styles: the progress block in `styles.css` next to `.file-progress` (the mockup's
  `.clone-progress`, `.clone-bar`, `.clone-line`), the switch reuses `.segments`.
- **D13. Docs.** `docs/design/ui.md`, Launch and session control: the Where field's two
  sources, the clone's flow, the job rules, mockup `task/lad-6/mockup-clone.html` v3.
  AGENTS.md: Layout (`clone.py`, `server/clones.py`), the server's endpoint list, the CLI
  paragraph of `lado start`. README: `lado start <git-url>` in the start section.
  CHANGELOG.md under 0.36.0.
- **D14. Version.** Minor (new CLI form and API); 0.36.0 is the unreleased minor. No
  schema change, no MCP tool change, no provider change.

## Tests by layer

- Unit (`tests/test_clone.py`): URL forms, default folder, same-repo pairs, every target
  state with real git repos, `KINDS` against recorded git lines, progress parsing, listing
  and cloning a local bare repo over `file://` (branch, default branch, empty repo, missing
  branch), cancel with a fake slow `git` on PATH (temp gone, target absent), no secret in
  texts.
- Unit (`tests/test_server_clones.py`): the five endpoints with FastAPI's client: refusals
  400 with kind and hint, 409, 404, a job to `done` on a `file://` repo, `DELETE`, the
  abandoned sweep with `ABANDONED` patched short, the shutdown cancel, `Guard.changes`.
- Unit (`tests/test_cli.py`): argument errors, `same_repo` / `other_repo` refusals, the
  name refusal before the clone, the clone then `start_session` called with the folder
  (tmux replaced by the recorder).
- Integration (`tests/integration/test_clone_start.py`, marker `integration`): `lado start
  file://<bare> --branch dev --no-attach` with the fake agent: the session runs in the
  clone on `dev`; SIGINT to `lado` while a fake slow git clones: exit 130, no temp folder,
  no target.
- Web (`web/src/Launch.test.tsx`, vitest): the switch, branches fetched and the default
  chosen, a listing failure with hint and Copy, the target states (Use this clone,
  other_repo with the suggestion), progress, Cancel clone, × and Esc off, start refused
  after the clone switching to Folder.
- UI e2e (`tests/ui/test_launch.py`, marker `ui`): clone a `file://` bare repo from the
  window and start; Activity opens; screenshots of the form, the progress (a fake slow git)
  and Use this clone.
- No smoke or live test: no provider, hook or agent launch changes.

## Risks

- Classifying by git's English words breaks if git changes them; `LC_ALL=C` pins the
  language and an unknown line is still told (`git_failed`, git's line).
- The server's environment may lack what a login shell has (an ssh-agent socket when the
  server was started from a service). The texts say "this machine"; hints point at the
  command to check it. Documented in `docs/design/ui.md`.
- A clone of a large repository through a slow link takes long; the window waits, as the
  human chose; Cancel clone is always there.
