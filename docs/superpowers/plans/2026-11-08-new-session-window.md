# The New session window, reorganized: Implementation Plan

**Goal:** The New session window opens on the last place with Task second and Team as one line,
offers Resume beside a new start under a free name, names permissions in words, sets a plain
folder up and starts it, and keeps its footer in view on every width.

**Architecture:** The core gains a free name, a fourth step of the agent's suggestion, each
provider's words for its modes, and `setup.py` (preview and make of a plain folder's first
commit). The server passes them on in the existing checks (`FolderInfo`, `ProjectLaunch`,
`CloneTarget`, `ProviderInfo`, `RecentFolder`) and takes `where: {kind: "setup"}`. The window is
rebuilt on these answers: `LaunchWhere.tsx` (the combobox), `LaunchTeam.tsx`, `LaunchSetup.tsx`,
`InfoTip.tsx`, and `Launch.tsx` keeping the dialog, the requests and the footer.

**Tech Stack:** Python 3.10+ (FastAPI, git through subprocess), React + TypeScript, CSS, vitest,
pytest, Playwright.

**Spec:** `openspec/changes/new-session-window/` (proposal, design.md D1–D16, specs),
`docs/superpowers/specs/2026-11-08-new-session-window-design.md` (the words, exactly), run
artifact `mockup-new-session.html` (states A(a)…A(k)), `ui-design/lad-239-design-2/spec` (sizes,
states, ARIA).

## Global Constraints

- Colours by tokens of `web/src/tokens.css` only; no new token. UI texts word for word from the
  design doc. "Resume", never "Continue". "LADO" in capitals.
- No schema migration. API changes go through `make web-types`; commit `web/openapi.json` and
  `web/src/api.gen.ts`.
- Nothing above `providers/` names a CLI: the modes' words live in each provider.
- The core's texts (refusals, hints) do not change; only the window's own words do.
- CHANGELOG.md: items under `## 0.45.0 (unreleased)` (New: the window and the set-up; Changed:
  `lado start`'s agent), by docs/release.md's rules.
- `docs/design/ui.md` "Launch and session control" rewritten for the window as built, with this
  change's name and the mockup; `docs/cli.md` for the agent's rule; `docs/design/modules.md` for
  `setup.py` and the new web files.
- UI tests with `-m ui`, integration with `-m integration`; suites with `-n auto`. Edit with edit
  tools; no sub-agents.

## Review Focus

- A recent place that is gone (folder deleted, project removed): the window must not open on it
  nor offer it; it opens on the next one or on New empty folder. Test in Task 2 and Task 7.
- A folder of 20,001 files, or one whose listing git refuses (unreadable subfolder): a refusal with
  git's line, never a 500 or a hang. Test in Task 4.
- A name `webapp-2` already taken too, and a base name at the length limit: the free name must be
  `webapp-3`, and a long name must stay valid for `check_name`. Test in Task 1.
- Esc while an info popover is open, while Where's list is open, and while a clone runs: only the
  popover, only the list, nothing (as today). Test in Task 6 and Task 7.
- A paste of a path with spaces or quotes into the set-up's left-out list: the "Do it yourself"
  command must quote it as the core does. Test in Task 4 and Task 8.

## Tests per requirement

| Requirement | Layer | Test |
|---|---|---|
| Where lists the recent places (D2) | pytest | `tests/test_server_launch.py` |
| free name, stopped-session offer (D3) | pytest + vitest | `tests/test_runtime.py`, `tests/test_server_launch.py`, `tests/test_server_project_launch.py`, `tests/test_server_clones.py`; `web/src/Launch.test.tsx` |
| the agent's rule (D4) | pytest | `tests/test_runtime.py` |
| permissions in words (D7) | pytest + vitest | `tests/test_providers.py`, `tests/test_server_providers.py`; `web/src/LaunchTeam.test.tsx` |
| set-up preview, make, rollback (D8) | pytest | `tests/test_setup.py` |
| set-up through the server and a worker's worktree (D9) | integration | `tests/integration/test_setup_start.py` |
| order, opening, Task, Team, footer reason, draft, Resume window (D1, D5, D6, D12) | vitest | `web/src/Launch.test.tsx` |
| info button (D10) | vitest | `web/src/InfoTip.test.tsx` |
| combobox (D11) | vitest + UI e2e | `web/src/LaunchWhere.test.tsx`; `tests/ui/test_launch.py` |
| phone sheet, focus after refusal, scenario 1 end to end, set-up end to end | UI e2e | `tests/ui/test_launch.py` |

Regression: `make lint`; `make test`; `make web`; `uv run pytest -m integration -n auto
tests/integration/test_setup_start.py tests/integration/test_scratch_start.py
tests/integration/test_clone_start.py tests/integration/test_session_start.py`; `uv run pytest -m
ui tests/ui/test_launch.py tests/ui/test_launch_project.py tests/ui/test_launch_model.py
tests/ui/test_stopped_session.py`. The existing UI and vitest tests that press the source switch,
`Launch`, `Start session`, `Resume it`, open Advanced or First message move to the new controls.

### Task 1: The free name and the agent's fourth step (core)

**Files:** Modify `src/lado/runtime.py`. Test `tests/test_runtime.py`.

**Interfaces:** Produces `runtime.free_name(base: str) -> str`; `runtime.LAST_ANY = "last_any"`;
`suggested_provider(repo, installed)` unchanged in signature.

- [ ] **Step 1: Write the failing tests.**

```python
def test_free_name_is_the_name_when_no_session_has_it(home):
    assert runtime.free_name("webapp") == "webapp"

def test_free_name_counts_past_taken_ones(home, make_session):
    make_session("webapp"); make_session("webapp-2")
    assert runtime.free_name("webapp") == "webapp-3"

def test_the_last_session_anywhere_is_the_third_step(home, make_session):
    make_session("old", repo="/w/a", provider="claude")
    found = runtime.suggested_provider("/w/new", lambda p: p.name in ("claude", "codex"))
    assert found == runtime.Suggestion("claude", runtime.LAST_ANY)
    assert found.line() == "claude (your last session)"
```

(`make_session` as the existing tests of `suggested_provider` make sessions.)

- [ ] **Step 2: Run** `uv run pytest tests/test_runtime.py -n0 -k "free_name or last_session_anywhere"`: FAIL.
- [ ] **Step 3: Implement.**

```python
LAST_ANY = "last_any"  # the provider of the latest started session of any folder
_REASONS = {
    LAST_SESSION: "the folder's last session",
    LAST_ANY: "your last session",
    ONLY_INSTALLED: "the only one installed",
}

def free_name(base: str) -> str:
    """`base` when no session has it, else the first `base-2`, `base-3`, … none has: the name
    the New session window offers beside a stopped session of `base`."""
    n, name = 1, base
    while state.get_session(name) is not None:
        n += 1
        name = f"{base}-{n}"
    return name

# in suggested_provider, after the folder's last session:
    latest = next(iter(state.sessions_by_start()), None)
    if latest and latest.provider in providers.names() and installed(providers.get(latest.provider)):
        return Suggestion(latest.provider, LAST_ANY)
```

Update its docstring. If `slug` caps a name's length, cut `base` so `base-<n>` fits, with a test.

- [ ] **Step 4: Run** the file: PASS. `docs/cli.md`: the agent of `lado start` (the three steps).
**Commit** `A new session takes the agent of the last session when its folder has none (LAD-239)`.

### Task 2: The server's checks carry the free name and the recent project repositories

**Files:** Modify `src/lado/server/models.py`, `src/lado/server/launch.py`, `web/openapi.json`,
`web/src/api.gen.ts`. Test `tests/test_server_launch.py`, `tests/test_server_project_launch.py`,
`tests/test_server_clones.py`.

**Interfaces:** Consumes `runtime.free_name`. Produces `FolderInfo.free_name`,
`ProjectLaunch.free_name`, `CloneTarget.free_name: str | None`; `RecentFolder.project:
ProjectPlace | None`.

- [ ] **Step 1: Write the failing tests:** a folder with a stopped session `webapp` gives
  `free_name: "webapp-2"`, `name_state: "stopped_here"`; a free one gives `free_name ==
  default_name`; a session in project `shop`'s repository `backend` is in `/api/folders/recent`
  with `project: {id: "shop", title: "Shop", repo: "backend"}`; a session in `projects/shop/notes`
  that is no repository of the project stays out; a session whose folder was deleted stays out.
- [ ] **Step 2: Implement.** In `launch.recent_folders`, for a folder under `owned`, keep it only
  when `projects.place(folder)` names a repository and the session has that project, and set
  `project`; skip a folder that no longer exists. Fill `free_name` where `default_name` is set
  (`runtime.free_name(name)`). `make web-types`.
- [ ] **Step 3: Run** the three files: PASS. **Commit** `The folder, project and clone checks
  give a free session name; recent places include project repositories (LAD-239)`.

### Task 3: Permission modes in words (providers)

**Files:** Modify `src/lado/providers/base.py`, `claude.py`, `codex.py`, `opencode_family.py`,
`src/lado/server/models.py`, the providers' endpoint, `web/openapi.json`, `web/src/api.gen.ts`.
Test `tests/test_providers.py`, `tests/test_server_providers.py`.

**Interfaces:** Produces `base.ModeWords(title: str, summary: str, description: str, risky:
bool)`, `Provider.permission_mode_words: dict[str, ModeWords]`, `Provider.mode_words() ->
list[tuple[str, ModeWords]]`; `ProviderInfo.mode_words: list[ModeWordsInfo]` with `{value,
title, summary, description, risky}`.

- [ ] **Step 1: Write the failing tests:** every provider's `mode_words()` lists exactly its
  `permission_modes` in order; a mode missing from `permission_mode_words` comes as
  `ModeWords(value, value, "", False)`; Claude Code's `bypassPermissions` is risky; `/api/providers`
  carries them.
- [ ] **Step 2: Implement.**

```python
@dataclass(frozen=True)
class ModeWords:
    """How the UI names a permission mode: its title, its few words in a summary, one line of
    what it does, and whether it risks the folder."""
    title: str
    summary: str
    description: str
    risky: bool = False

# Provider:
    permission_mode_words: dict[str, ModeWords] = {}

    def mode_words(self) -> list[tuple[str, ModeWords]]:
        """Each mode with its words, in `permission_modes`' order; a mode without words is
        named by its value, never dropped."""
        plain = lambda mode: ModeWords(mode, mode, "")
        return [(m, self.permission_mode_words.get(m) or plain(m)) for m in self.permission_modes]
```

The texts: the design doc's table. Claude Code's `auto` and `manual`: run `claude --help` (and
its docs) on the machine; write words only for what is confirmed, in a comment naming the
version; else leave them out.

- [ ] **Step 3: Run**, `make web-types`. **Commit** `Each agent CLI names its permission modes in
  words (LAD-239)`.

### Task 4: The folder set-up (core)

**Files:** Create `src/lado/setup.py`. Test `tests/test_setup.py`.

**Interfaces:** Consumes `scratch.author_problem`, `runtime.NOT_REPO_HINT`, `projects.workspace`.
Produces `setup.preview(path: str) -> Preview`, `setup.make(path: str, include: list[str]) ->
str` (the root), `Preview(files: int, bytes: int, left_out: list[LeftOut], refusal: Refusal |
None, command: str)`, `LeftOut(path: str, reason: Literal["secret", "large", "repository"],
size: int | None)`, `Refusal(kind: Literal["home", "too_big"], files: int, bytes: int)`,
`SetupError(kind, text)`, constants `MAX_FILES = 20_000`, `MAX_BYTES = 2 * 1024**3`, `MAX_FILE =
50 * 1024**2`, `SECRETS` (the name patterns of the spec).

- [ ] **Step 1: Write the failing tests** (`git_config` fixture as `test_scratch.py`):
  - a folder with `a.txt`, `.env`, `deploy/server.key`, a 51 MiB sparse `big.bin` and `old/.git`:
    files 1, the four left out with their reasons, `old/` as `repository`;
  - a `.gitignore` naming `build/` with `build/x`: not counted;
  - `MAX_FILES` monkeypatched to 3 and 5 files: `too_big`; the home folder and the workspace:
    `home`;
  - `make(path, [])`: one commit `First commit`, `.gitignore` gains the four lines, `.env` on disk;
    `make(path, [".env"])`: `.env` committed; `make(path, ["old/"])`: refused;
  - a failing commit (`core.hooksPath` cannot help: monkeypatch `_git` to fail on `commit`): no
    `.git`, `.gitignore` byte for byte as before (and absent when it was absent);
  - `command` quotes `my notes.txt` as `'my notes.txt'`.
- [ ] **Step 2: Run** `uv run pytest tests/test_setup.py -n0`: FAIL.
- [ ] **Step 3: Implement.**

```python
def _listed(path: str) -> Iterator[str]:
    """What `git add -A` would take in `path`, as git itself lists it: a temporary GIT_DIR, the
    folder as the work tree, `.gitignore` respected, a nested repository as one `dir/`."""
    with tempfile.TemporaryDirectory() as gitdir:
        subprocess.run(["git", "init", "--quiet", "--bare", gitdir], check=True, ...)
        proc = subprocess.Popen(
            ["git", f"--git-dir={gitdir}", f"--work-tree={path}", "ls-files", "--others",
             "--exclude-standard", "-z"],  # a nested repository comes as `dir/` by itself
            stdout=subprocess.PIPE, stdin=subprocess.DEVNULL, env=_english(), cwd=path)
        ...  # yield each NUL-separated path; kill the process when the caller stops early
```

`preview` refuses `home` first (`Path.home()`, `/`, the workspace and any folder holding it,
by real path), then counts from `_listed`, stopping past the limits. `make` re-runs the author
check and `preview` (refusing what it refuses), keeps `.gitignore`'s bytes, appends the left-out
paths not in `include` (one per line, a leading `/` so a name matches only at its place), runs
`git init`, the branch as `scratch.make`, `git add -A`, the commit with `-c commit.gpgsign=false
-c core.hooksPath=/dev/null --no-verify`; on any failure removes `.git` and restores
`.gitignore`, raising `SetupError("git_failed", "git could not set up <path>: <line>")`.

- [ ] **Step 4: Run**: PASS. **Commit** `LADO can set up a plain folder: a first commit that
  leaves out secrets, large files and nested repositories (LAD-239)`.

### Task 5: The set-up through the server

**Files:** Modify `src/lado/server/models.py` (`SetupInfo`, `LeftOutInfo`, `Where.include`),
`launch.py` (`FolderInfo.setup`), `app.py` (`start` for `kind == "setup"`), `web/openapi.json`,
`web/src/api.gen.ts`. Test `tests/test_server_launch.py`; create
`tests/integration/test_setup_start.py`.

**Interfaces:** Consumes Task 4. Produces `FolderInfo.setup: SetupInfo | None` (`files, bytes,
left_out, refusal, author, command`), `Where{kind: "setup", path, include}`.

- [ ] **Step 1: Write the failing tests:** `GET /api/folders` on a folder of files gives `setup`,
  on an empty one `scratch: true` and no `setup`; `POST /api/sessions` with `kind: "setup"` and
  `include` on another kind is 400; a `SetupError` is 400 with its text and the folder untouched.
  Integration (`-m integration`, the fake agent, as `test_scratch_start.py`): the server sets up a
  folder with `a.txt` and `.env` and starts; the supervisor goes idle; a spawned worker's worktree
  has `a.txt` and no `.env`; `.gitignore` names `.env`.
- [ ] **Step 2: Implement.** In `start`: `if where.kind == "setup": runtime.check_start_login(...);
  setup.make(path, where.include or [])`, then the same `runtime.start_session`. `_where` accepts
  `setup` with `path` and `include` only.
- [ ] **Step 3: Run** the unit file and `uv run pytest -m integration -n0
  tests/integration/test_setup_start.py`: PASS. `make web-types`. **Commit** `The server sets up a
  plain folder and starts a session in it (LAD-239)`.

### Task 6: The info button

**Files:** Create `web/src/InfoTip.tsx`, `web/src/InfoTip.test.tsx`; modify `web/src/styles.css`.

**Interfaces:** Produces `<InfoTip about="Task">{text}</InfoTip>` (button `aria-label="About
Task"`, `aria-expanded`, a `role="status"` region holding the text while open).

- [ ] **Step 1: Write the failing tests:** press opens and puts the text in the status region,
  press again closes; Enter and Space open; Esc closes and calls `preventDefault` (a parent's
  Escape handler sees `defaultPrevented`); a press outside closes; opening a second closes the
  first; hover opens nothing; the focus stays on the button.
- [ ] **Step 2: Implement** with one module-level "open tip" setter so a second tip closes the
  first; placement by `useBelow` (`Menu.tsx`), in a `popover="manual"` element; CSS `.info-tip`
  (16 px circle in a 24 px target, 44 px at ≤760 by `::after`), `.info-pop` (the spec §9).
- [ ] **Step 3: Run** `make web`: PASS. **Commit** `An info button shows a field's explanation on
  press (LAD-239)`.

### Task 7: Where as one combobox

**Files:** Create `web/src/LaunchWhere.tsx`, `web/src/LaunchWhere.test.tsx`; modify
`web/src/Launch.tsx`, `web/src/LaunchProject.tsx`, `web/src/styles.css`.

**Interfaces:** Consumes `RecentFolder.project`, `FolderInfo`, `useAsked`, `useDebounced`.
Produces `type Place = {kind: "folder", path} | {kind: "project", project, repo} | {kind: "url"}
| {kind: "scratch"} | {kind: "other-folder"} | {kind: "project-pick"}`; `<LaunchWhere place
onPlace recent workspace checked …/>`, rendering the chosen way's own fields under the field
(today's path field and hints, `UrlField`/`BranchField`/Clone into, the Folder name field,
`ProjectField`).

- [ ] **Step 1: Write the failing tests:** the closed field shows the place's name, path and a
  project's badge; ↓, Alt+↓, a typed letter open the list; Recent then Somewhere else; arrows and
  Enter pick; the first Esc closes only the list; a typed `~/w` lists `Use folder ~/w` and the
  subfolders; picking Clone from URL… shows Repository URL, Branch, Clone into; picking a project
  item gives `{kind: "project"}`; the listbox has `role="listbox"` and options `aria-selected`.
- [ ] **Step 2: Implement**; move the source switch's state into `Place`; drop `SourceSwitch`, the
  Workspace row and the Recent chips. The list is placed by `useBelow` in a fixed layer above
  760 px and in the flow at 760 px or less.
- [ ] **Step 3: Run** `make web`: PASS. **Commit** `Where is one list of recent places and other
  ways (LAD-239)`.

### Task 8: Task, Team, the set-up panel and the footer

**Files:** Create `web/src/LaunchTeam.tsx`, `web/src/LaunchTeam.test.tsx`,
`web/src/LaunchSetup.tsx`, `web/src/LaunchSetup.test.tsx`; modify `web/src/Launch.tsx`,
`web/src/LaunchModel.tsx`, `web/src/styles.css`, `web/src/Launch.test.tsx`.

**Interfaces:** Consumes Tasks 2, 3, 5, 6, 7. Produces `<LaunchTeam …/>` (summary + Change; open:
Session name, Agent, Team setup, Permissions radio rows from `mode_words`, Model, Switch off),
`<LaunchSetup setup include onInclude/>`, `missingReasons(state) -> {text, focus}[]`,
`shellQuote(path)` (the core's quoting, ported).

- [ ] **Step 1: Write the failing tests,** one per mockup state: A(a) (stopped session: free name,
  two buttons, Resume primary while Task is empty, Start new primary with text, places kept), A(c)
  (`Start in Shop`), A(d) (Team open, risky mode's description always shown, Hide), A(e) (`Clone
  and start in shop-site`), A(f) (New empty folder, `Create and start`, no message above Where),
  A(g)/A(g0)/A(g2)/A(g3)/A(g4)/A(g5) (counting, ticking `.env` counts 129 and drops it from the
  command, too big, no author with Check again, Do it yourself: one disclosure open at a time),
  A(h) (the Resume window's line, Message, `Start a new session instead` → New session with the
  free name), the footer's `To start:` links focusing their fields, Task's limit, the draft kept
  after Esc and cleared by a start, `aria-describedby` and `aria-invalid` on refusals, the start
  button `aria-disabled` and focusable while it works, a refusal's focus on its field.
- [ ] **Step 2: Implement.** Keep the requests and their refusals in `Launch.tsx`; the draft in
  `LaunchProvider`'s state (D6); `Resume <name>` posts the resume with the changed Team fields and
  `prompt`; the frame of D12 in CSS (`margin-top: 40px`, sticky footer, sheet at ≤760). Remove
  `FirstMessage`, Advanced and the 2×2 grid.
- [ ] **Step 3: Run** `make web`: PASS. **Commit** `The window asks for the place and the task,
  and shows the team as one line (LAD-239)`.

### Task 9: The rail, the documents and the browser tests

**Files:** Modify `web/src/Shell.tsx` (Launch → New session), its tests; `tests/ui/test_launch.py`,
`tests/ui/test_launch_project.py`, `tests/ui/test_launch_model.py`, `tests/ui/test_stopped_session.py`;
`docs/design/ui.md`, `docs/design/modules.md`, `docs/cli.md`, CHANGELOG.md.

- [ ] **Step 1: Write the browser tests** (fake agent): scenario 1 end to end (a stopped session
  in a folder; the window opens on it with Resume primary; typing a task makes Start new primary;
  `webapp-2` starts and its Activity shows the task); a recent project repository picked from the
  list starts `Start in Shop`; a plain folder with `.env` and `a.txt`: Set up and start, then
  `.gitignore` holds `.env`; at 390×844 the start button is in view with Team open; a refused start
  leaves the focus on the field, not on `body`; Esc returns the focus to the opener. Move the
  existing tests off the switch, Advanced, First message, `Launch` and `Resume it`.
- [ ] **Step 2: Run** `uv run pytest -m ui -n auto tests/ui/test_launch.py
  tests/ui/test_launch_project.py tests/ui/test_launch_model.py tests/ui/test_stopped_session.py`:
  PASS. Screenshots of A(a), A(b), A(d), A(g), A(h) at 1440 and 390 as run artifacts.
- [ ] **Step 3: Documents.** `docs/design/ui.md` "Launch and session control": the window as built
  (the order, Where's list, the free name and two buttons, Team, the footer, the info button, the
  set-up, the Resume window, the frame), replacing the switch's paragraphs; drop "The window makes
  no repository of a folder that holds files". `docs/design/modules.md`: `setup.py`,
  `LaunchWhere.tsx`, `LaunchTeam.tsx`, `LaunchSetup.tsx`, `InfoTip.tsx`. CHANGELOG.md.
- [ ] **Step 4: The regression run** of "Tests per requirement". **Commit** `The rail says New
  session; the window's documents and browser tests (LAD-239)`.
