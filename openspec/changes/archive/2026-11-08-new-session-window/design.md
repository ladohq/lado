# Design: new-session-window

The approved look is the artifact `mockup-new-session.html` (from `ui-design/lad-239-design-2`,
variant A, laconic); its states are named A(a)…A(k) below. The review of the window before the
change is `ui-review/lad-239-review/critique` (findings F1–F20), the designer's spec
`ui-design/lad-239-design-2/spec`. The full design doc:
`docs/superpowers/specs/2026-11-08-new-session-window-design.md`.

Above `providers/` nothing depends on one CLI: each provider gives the words for its own
permission modes (D7); the set-up of a folder is git only, as every session folder is.

## Decisions

**D1. The last place comes from the server, not the browser.** The window opens on the first
item of the recent places (D2): the place of the latest started session. No `lastLaunch` in
browser storage: one source of truth, the same on every device and after a reload, and a place
that is gone falls out of the list by itself (the recent places are filtered as today). A clone
or a fresh start is a folder once started, so it comes back as a folder. With no sessions the
window opens on New empty folder, as today. `useLaunch()({kind: "new", project, repo})` (the
project's page) still wins.

**D2. `/api/folders/recent` lists project repositories too.** `RecentFolder` gains
`project: ProjectPlace | None` (`{id, title, repo}`, `projects.place` of the session's folder),
set for a session in a project's repository. `launch.recent_folders` stops leaving out folders
inside LADO's `projects/` when the session has a project and the folder is a repository of it;
any other folder there stays out (`repos-folder`'s rule). The window shows a folder item by the
folder's last segment, a project item by its repository's name with the badge `Project
<title>`; picking a project item is the Project way with that project and repository
(`where: {kind: "project"}`), so the start button names the project as before.

**D3. A free name is the core's, given with every place's check.** `runtime.free_name(base,
repo)`: `base` when no session has it, else the first of `base-2`, `base-3`, … no session has,
each checked by `runtime.check_name`. `FolderInfo`, `ProjectLaunch` and `CloneTarget` gain
`free_name: str | None` beside `default_name` and `name_state`. The window sends the free name
unless the human typed one. `name_state: "stopped_here"` gives the two footer buttons (Resume
`<default_name>`, Start new session `<free_name>`); `running` and `taken_elsewhere` give the
free name and one button. A 409 `Taken` stays for a race. From scratch is unchanged: there the
name is the folder's.

**D4. The agent's suggestion gets a step: the last session anywhere.**
`runtime.suggested_provider` becomes: the folder's last session's provider if installed
(`last_session`), else the provider of the latest started session of any folder if installed
(`last_any`, new, `_REASONS`: "your last session"), else the only one installed
(`only_installed`), else None. `lado start` uses the same function, so its printed choice and
`docs/cli.md` change with it. The login is not part of the rule (as today): the window keeps a
suggested CLI without its login off with "Log in first".

**D5. The primary of the two buttons follows Task.** Task empty after trim: `Resume <name>` is
`.primary`, `Start new session <free_name>` `.quiet`; with text, the other way round. The
buttons keep their places; Enter in Task is a new line, never a submit. `Resume <name>` calls
`POST /api/sessions/{name}/resume` with the Team fields the human changed and `prompt` = Task,
as the Resume window does.

**D6. The draft lives in `LaunchProvider`'s state.** Where's choice, Task and the Team fields
(the Model field's choice too, for the agent CLI it was made for) of
the New session window are kept in the provider's React state when the window closes without a
start, and cleared by a start; a reload of the page clears them (the human's answer #4841: "until
the start or a reload"). The Resume window keeps none: it opens from the session.

**D7. Each provider describes its own modes.** `base.Provider.permission_mode_words:
dict[str, ModeWords]`, `ModeWords(title, summary, description, risky)`; `ProviderInfo` gains
`mode_words: list[ModeWordsInfo]` in the order of `permission_modes`. The texts are the
designer's spec §6 (Claude Code, Codex); OpenCode and Kilo get theirs from their own
behaviour in `opencode_family.py` (default asks, `acceptEdits`, `bypassPermissions`, `plan`).
A mode without words (Claude Code's `auto` and `manual` until checked against `claude --help`)
is listed with its CLI value as title, no description, `risky: false`: never dropped. A CLI with
no modes shows "No permission modes." and no Permissions in the summary.

**D8. The folder set-up is a core module, `src/lado/setup.py`.** `preview(path) -> Preview`:
first the `home` refusal (the home folder, `/`, the workspace itself or a folder holding it),
asked of the path alone; then git itself lists what `git add -A` would take, so the preview
and the commit cannot disagree: `git --git-dir=<a temporary folder> --work-tree=<path> ls-files
--others --exclude-standard -z` (an existing `.gitignore` respected; a nested repository comes
as one `dir/` entry), read as a stream and stopped past `MAX_FILES = 20_000` files or `MAX_BYTES
= 2 GiB` (`too_big`, with the count so far). Of the listed: `secret` by name (`.env*`,
`*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa*`, `id_ed25519*`, `credentials*`, `.npmrc`,
`.netrc`), `large` over `MAX_FILE = 50 MiB`, `repository` a `dir/` entry (cannot be included);
the rest give `files` and `bytes`. The temporary git folder is removed after the call. `make(path, include) -> root`:
the author check (`scratch.author_problem`), `git init`, the branch as `scratch.make`, the
left-out paths not in `include` appended to `.gitignore` (made when missing), `git add -A`, one
commit `First commit` with no signing and no hooks. A failure removes the `.git` it made and
puts `.gitignore` back as it was (its bytes kept before the write, or removed when new):
`SetupError` with git's line. `include` naming a `repository` item, or a path the preview does
not leave out, is refused (`bad_include`), a folder in git too (`not_plain`). The preview also
refuses a folder git cannot list whole (`unreadable`, git's line) and one holding a path to
leave out whose name has a line break or bytes that are no UTF-8 (`odd_name`): no `.gitignore`
line can hold the one, no text the other. A refused preview lists nothing left out.

**D9. The set-up's API.** `GET /api/folders` gains `setup: SetupInfo | None` for a folder whose
check is `not_repo` and that is not empty (`scratch` false): `{files, bytes, left_out:
[{path, reason, size, line}], refusal: {kind, files, bytes, line} | null, author:
ScratchProblem | null, make, max_files}`: each left-out path's `line` is its `.gitignore`
line quoted for the shell by the core (`setup.shell_line`), `make` the command after them
(`NOT_REPO_HINT`'s), so the window builds "Do it yourself" from the ticks as `printf '%s\n'
<lines> >> .gitignore && <make>` with no quoting of its own (one source: the core). The
preview runs in the request's thread pool; the window cannot know a folder is outside git
before the check answers, so it shows "checking…" first, and "Counting files…" only while a
plain folder is checked again (Check again keeps the author's text, "Checking…"). `POST
/api/sessions` takes `where: {kind: "setup", path, include: [..]}`: the server runs
`setup.make`, then starts as for a folder; a refusal before the commit is 400 with nothing left
behind; a start refused after it switches the window to that folder (now a repository) with
the refusal, as after a clone or a fresh start.

**D10. One toggletip, `InfoTip.tsx`.** A button `aria-label="About <field>"`,
`aria-expanded`, and a `role="status"` region the text is put in when open; a popover in the
top layer (`popover="manual"`) placed by `useBelow` (Menu.tsx); click, Enter and Space open and
close it; Esc closes it and only it (`preventDefault`, so the dialog stays); a press outside,
another tip or Tab away closes it; hover does nothing. Outside the `<label>`, so a click on the
label still focuses its field.

**D11. Where is one combobox, `LaunchWhere.tsx`.** An input `role="combobox"` with a listbox
of groups Recent and Somewhere else; typing a path (`/`, `~`) lists "Use folder <path>" and the
subfolders by today's `/api/folders`; the four "other" items show their fields under it (Other
folder: today's path field with its hints; Clone from URL: Repository URL, Branch, Clone into;
New empty folder: Folder name; Project: today's `LaunchProject`). The list is placed by
`useBelow` in a fixed layer so the body's scroll does not cut it; at 760 px or less it opens in
the flow. The Workspace row goes: the workspace is the placeholder and the list of an empty
typed path, as today.

**D12. The window's frame.** Head, a body that scrolls, a footer that does not; `margin-top:
40px`, `max-height: calc(100dvh - 64px)`, width `min(640px, 100vw - 32px)`; at 760 px or less a
full-screen sheet, the footer above `env(safe-area-inset-bottom)`, targets of 44 px. The start
button stays focusable while it works (`aria-disabled`, not `disabled`), its text "Starting…",
"Setting up…" or "Resuming…".

**D13. Launch.tsx is split.** At 1830 lines it holds four sources; the change moves Where
(`LaunchWhere.tsx`), Team (`LaunchTeam.tsx`) and the set-up panel (`LaunchSetup.tsx`) out, and
keeps the dialog, the requests and the footer in `Launch.tsx`.

**D14. The words.** Labels and notes are the designer's spec §2–§10 and the mockup, with the
human's corrections: Resume, never Continue; LADO in capitals. The (i) texts are listed in the
design doc. `FolderInfo`'s check line becomes `✓ Ready · branch <b>` in the window only; the
core's texts (refusals, hints) are unchanged.

**D15. Team's summary names a model only off the default.** The summary reads Setup, Agent,
Permissions and Name; a model other than the CLI's default (a pick, or the CLI's settings past a
default) adds `Model <name>`, and a warning of the model's check adds its `⚠ <few words>`, as
Advanced's folded row did: otherwise a chosen model would be hidden under Change.

**D16. New empty folder names the folder when it differs.** Folder name takes the human's words;
when the slug differs from them (`Сайт кофейни` → `sait-kofeini`), a quiet note `folder
<slug>` stands under the field, since the folder and the session take the slug.

## Test layers

| Requirement | Layer | Test |
|---|---|---|
| Recent places with project repositories (D2) | unit (pytest) | `tests/test_server_launch.py`: a folder session, a project session, a folder in projects/ without a project |
| Free name (D3) | unit (pytest) | `tests/test_runtime.py`: free, `-2`, `-3`, a name over the length limit; `tests/test_server_launch.py`: `free_name` in the three checks |
| The agent's suggestion (D4) | unit (pytest) | `tests/test_runtime.py`: the four steps; `lado start` printing "your last session" |
| Modes in words (D7) | unit (pytest) | `tests/test_providers.py`: every mode of every provider has words or falls back to its value; `ProviderInfo.mode_words` |
| Folder set-up preview and make (D8) | unit (pytest) + integration | `tests/test_setup.py`: secrets, large, nested repository, `.gitignore` respected, home/too big refusals, include, rollback on a failing commit; `tests/integration/test_setup_start.py`: `POST /api/sessions` with `kind: "setup"` on a folder of files starts the fake agent's session, a worker's worktree has the saved files and not the left-out ones |
| The window's order, opening, Task, Team summary, footer reason, two buttons, draft, toggletip, Resume line (D1, D5, D6, D10–D12) | unit (vitest) | `web/src/Launch.test.tsx` (rewritten by state A(a)…A(k)), `InfoTip.test.tsx` |
| The combobox from the keyboard (D11) | unit (vitest) + UI e2e | vitest for keys and options; `tests/ui/test_launch.py`: pick a recent project repository and start in it |
| Phone sheet and footer in view, the focus after a refusal | UI e2e | `tests/ui/test_launch.py` at 390×844 and 1440×900 |
| End to end, scenario 1 | UI e2e | `tests/ui/test_launch.py`: a stopped session in a folder, the window opens on it, Resume primary, typing a task makes Start new primary, the session `<name>-2` starts with the task as the first message |
| End to end, plain folder | UI e2e | `tests/ui/test_launch.py`: a folder with `.env` and a file, "Set up and start" starts a session, `.gitignore` holds `.env` |
| Regression | all | `make lint`, `make test`, `make web`, `uv run pytest -m integration -n auto tests/integration/test_setup_start.py`, `uv run pytest -m ui tests/ui/test_launch.py`, the changed vitest files |
