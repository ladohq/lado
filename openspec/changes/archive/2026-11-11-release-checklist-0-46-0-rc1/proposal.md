Task: LAD-269

## Why

LADO 0.46.0 is a minor release (CHANGELOG.md's `## 0.46.0 (unreleased)` has an item under
`### New`), so it is first published as the release candidate 0.46.0rc1. Before the RC's commit
its release's checklist, `docs/releases/0.46.0.md`, gets the section `## 0.46.0rc1`
(docs/release.md, section 2, step 0, and 4.7), in a pull request of its own that the human reads;
`scripts/rc_check.py` prints that section's items after the checks of every RC.

Facts the section rests on (checked on `8d35bb4b`, main):

- The last final is `v0.45.0`. `git log --first-parent v0.45.0..origin/main`: LAD-261, LAD-262,
  LAD-263, LAD-264, LAD-265, LAD-266, LAD-268 and two Dependabot pull requests (#278 GitHub
  Actions, #279 npm of `web/`).
- `## 0.46.0 (unreleased)` holds 8 items: 1 New (LAD-265's Name), 4 Improved (LAD-265's project
  name and Where/Kits, LAD-266's waiting card, LAD-264's session list), 3 Fixed (LAD-263 Codex's
  model, LAD-261 Resume, LAD-262 `lado doctor`).
- `SCHEMA_VERSION` is 39 at `v0.45.0` and on main: the schema does not move, so 4.4's user's own
  way back on a test home is not needed; 4.2 and 4.6 hold as for every first RC of a cycle.
- Since `v0.45.0`, `docker/` changed only in `Dockerfile` (mise 2026.11.0, LAD-268) and
  `mise.toml`; `docker/install.sh` and `docker/install.ps1` did not change, so the installers are
  not run. `scripts/rc_check.py` did not change, so the release's own steps need no check of
  their own.
- The RC itself follows 0.45.0rc1's precedent (`4f5ab92e`, a commit on main changing only
  `pyproject.toml` and `uv.lock`).

The human approved the scale, the plan of the RC after the merge and the draft's content (answer
#5648, "Всё по рекомендациям").

## What Changes

### `docs/releases/0.46.0.md`, a new file

Its form is 4.7's: the heading, a paragraph naming the last final, that the schema stays at 39,
what the checks of every RC already cover, then the section `## 0.46.0rc1` with top-level
`- [ ] **Title.** …` items, details nested, grouped by `###` subheadings. The text below is the
file as approved; the developer writes it as it stands and changes an exact line only where the
code says otherwise (tasks 1.2):

````markdown
# LADO 0.46.0: the release's checks

The last final is 0.45.0. The database's schema stays at 39, so 4.4's `rollback` holds but
not the user's own way back on a test home; 4.2 and 4.6 hold as for every first RC of a
cycle. Those checks of every RC are not repeated here; this file holds what 0.46.0 itself
needs: the New session window's Name and Where, the waiting card, the session list without
its card, Codex's model over a repository's config, Resume of a stopped session and `lado
doctor` without a login. The image's mise moved to 2026.11.0 (CI's container tests run it);
`docker/install.sh` and `docker/install.ps1` did not change since v0.45.0, so the
installers are not run (docs/release.md, 4.5).

## 0.46.0rc1

The RC: tag `v0.46.0rc1`, commit `<filled in at the RC>`; `live.yml` on it is green (run
`<filled in at the RC>`). The exact lines below are the code's; where the code has no fixed
text, the line says what to look for.

### Before you start

- A Mac with your LADO 0.45.0 and sessions running, Docker Desktop, `uv`, `tmux`, `git`;
  a Linux machine with Docker and compose v2 (without one, note Linux as not checked).
- Chrome, Safari and Firefox; a real iPhone and iPad on the Mac's Wi-Fi.
- The CLIs logged in on the Mac: Claude Code (with the human's yes), Codex, OpenCode.
- An OpenRouter key, for 4.5's container without a login.
- A project `lado` with a repository `lado` (`lado project create lado`, `lado project repo
  add lado <a clone of LADO>`), and, from 0.45.0, a session `lado-lado` in it, stopped.

### The New session window: Name and Where

In Chrome, then a glance in Safari and Firefox (the browser tests run Chromium only).

- [ ] **Name follows the task's tracker key.** Task `Fix LAD-263 in the login form`: Name reads `lad-263`.
  - Name is on Task's label row (`Task ⓘ … Name ⓘ`), not in Team. A task without a key
    gives the place's name; the task's other words give none.
  - With a session `lad-263` running: `Name: lad-263 exists already, so this one is
    lad-263-2.`
- [ ] **A typed name is kept.** Type `Review Kao`, then change the task and the place: Name stays.
  - `Name shown as “Review Kao” · in links and branches: review-kao`; the session's title
    is `Review Kao`, `lado ls` lists it as `review-kao`.
  - A Cyrillic name (`Ревью`) stays the title; the session takes the automatic name.
  - Emptying the field gives LADO's name back.
- [ ] **A taken name is refused before Start.** Type the name of a running session.
  - `Name: a session named <name> exists (running, in <folder>).` with `Use <name>-2`; the
    footer says `To start: choose another name.`
  - Over 80 characters: `Name: at most 80 characters.`, the footer `shorten the name`.
- [ ] **A new empty folder has no Name field.** New empty folder… : under its name `Also the session’s name.`
- [ ] **Where is one line; Team says Kits.** A project's repository reads `<repo> in project <title>`, no badge.
  - A folder shows its path muted after its name, cut first on a narrow window; the same
    in Recent. Team's summary says `Kits <names>`; opened, **Kits** with `+ Add kit`.

### A project's session name

- [ ] **A repeated name is said once.** `lado start --project lado --repo lado` without `--name` starts `lado`.
  - The stopped `lado-lado` of 0.45.0 is still listed by `lado ls` under its name and
    resumes with `lado start --project lado --repo lado --name lado-lado`.
  - In the window, Where → Project… → `lado` → `lado`: Name reads `lado` when the task has
    no key.

### The waiting card

A worker's question gets the supervisor's recommendation: ask the built-in supervisor for a
worker that writes a report of some 40 lines and then asks you a question with three
choices (`ask_human`).

- [ ] **The question stands on top; only the report scrolls.** In the chat, Chrome.
  - The question is a filled band the card's width, on one line with "…" and the whole
    text in its tooltip; no mono line beside it.
  - The report scrolls with a fade at its lower edge; the recommendation and the buttons
    stay in sight; the card is at most half the chat.
- [ ] **The recommendation's box can be made taller.** Drag the splitter above it; reload: the height is kept.
  - `supervisor recommends <option>` and its time, the text in a box of 4 lines that
    scrolls; no "more". The splitter has no tooltip.
- [ ] **A click picks, Send answers.** Click a choice: nothing is sent; Send answers with it.
  - The recommended choice is picked already; a second click unpicks it. Skip is a pill
    among the choices.
- [ ] **Needs you shows the whole card.** No scroll inside it, no splitter; the page scrolls.
- [ ] **The card in Safari, Firefox and the dark theme.** The same three checks, a glance each.
- [ ] **iPhone: the card above the keyboard.** The phone's link of the System panel.
  - The recommendation's box is 2 lines; its splitter drags by a finger without scrolling
    the feed; your own answer's field and Send stay above the keyboard.

### The session list without its card

- [ ] **Hovering a session shows no card.** The pointer over a row of the session list: the chat stays uncovered.
  - Folded list: the pointer on a session's icon shows only its title, name and state.
  - Details, opened by the session's title, holds the rest.
- [ ] **iPad held sideways.** A tap on a row opens the session; no card is left open.

### Codex's model over a repository's config

- [ ] **Codex runs on the model you chose.** A repository with `.codex/config.toml` holding `model = "<another model of Codex's list>"`.
  - `lado start <that repository> --provider codex --model <a model of Codex's list>`;
    after its first turn `lado ls` names the chosen model, without `changed in the agent
    CLI`; the agent's window's header names it too.
  - Without `--model`, and nothing in Settings or your Codex config: `lado ls` names the
    repository's model from the start.

### Resume of a stopped session

- [ ] **A stopped session resumes on its own agent CLI and model.** A Claude Code session `a` stopped; then a Codex session in the same folder.
  - New session on that folder offers only `Start new session …`, no Resume button.
  - Resume `a` from its page (or the session list): it starts on Claude Code and its own
    model (`lado ls`), not Codex's.

### `lado doctor` without a login (in the image of 4.5)

- [ ] **doctor names the server's models.** In 4.5's container, before Claude Code and Codex are logged in.
  - `docker compose exec lado lado doctor` prints for each `[warn] … login: not logged in:
    only its agents on your model server's models start; log in in Settings → Agent CLIs
    for its own models`.
  - With OpenRouter saved and a model for Claude Code on it (`CloudClaude`), a New session
    on it starts and its supervisor answers; then log them in and go on with 4.5.

### Going back (4.4)

- [ ] **Going back to 0.45.0 loses nothing.** The schema does not move; sessions keep their names.
  - On 0.45.0 Codex is again told its model only through its config, so a repository's
    `.codex/config.toml` wins again; names typed in the window are kept.

### What covers the CHANGELOG's items

Each of the 8 items of `## 0.46.0 (unreleased)` at the RC's commit, with what covers it. An
item with a check above is tried there; the browser tests run Chromium only.

New:

1. The session's name beside Task, made from the task: the New session window's checks
   (vitest `web/src/sessionName.test.ts`, `web/src/Launch.test.tsx`; the browser
   `tests/ui/test_launch.py`, `tests/ui/test_launch_project.py`).

Improved:

2. A project's session name says a repeated name once: a project's session name (unit
   `tests/test_runtime_projects.py`, `tests/test_server_project_launch.py`).
3. New session reads more easily: Where is one line; Team says Kits (vitest
   `web/src/LaunchWhere.test.tsx`; the browser `tests/ui/test_launch.py`).
4. The waiting card: the waiting card's checks (vitest `web/src/WaitingCard.test.tsx`,
   `Recommendation.test.tsx`, `Splitter.test.tsx`; the browser `tests/ui/test_gates.py`,
   `test_chat.py`, `test_phone.py`, `test_needs_you.py`, `test_flows_tab.py`).
5. Hovering a session no longer covers the chat: the session list's checks (vitest
   `web/src/Layout.test.tsx`; the browser `tests/ui/test_session_list.py`).

Fixed:

6. Codex agents run on the model you chose: Codex's model (unit `tests/test_codex.py`;
   smoke `tests/smoke/test_smoke.py` with Codex on a local endpoint).
7. A stopped session resumes on its own agent CLI and model: Resume of a stopped session
   (vitest `web/src/Launch.test.tsx`; the browser `tests/ui/test_launch.py`,
   `test_launch_model.py`).
8. `lado doctor` says which agents start without a login: doctor in the image (unit
   `tests/test_doctor.py`).
````

The two placeholders of the RC's paragraph (`<filled in at the RC>`) stay in this pull request:
the commit and `live.yml`'s run exist only after it is merged, and are filled in with the RC
(0.45.0rc1's paragraph was filled in so).

### `tests/test_rc_check.py`

The test over the repository's real checklists (`test_the_repositorys_own_checklist_of_045_has_no_warning`)
also checks `0.46.0rc1` against `docs/releases/0.46.0.md`: no warning line, the every-RC lines
first, and the RC's own items after them.

### After the merge: the RC (no file of this pull request)

On main with this pull request merged, as docs/release.md section 2, steps 1-4:
`uv version 0.46.0rc1`, a commit `Release candidate 0.46.0rc1` of `pyproject.toml` and `uv.lock`
alone pushed to main, CI and the smoke green on it, `gh workflow run live.yml` on that commit with
every cell green (`gh run list --workflow live.yml --limit 1 --json headSha,conclusion` shows
its SHA), then the tag `v0.46.0rc1` pushed. The push to main and the push of the tag each wait for
the human's yes on a card of their own. The freeze starts with the RC.

## Scope

- `docs/releases/0.46.0.md` (new), the real-file test of `tests/test_rc_check.py`.

## Out of scope

- CHANGELOG.md: an RC adds no heading and changes no item (docs/release.md, CHANGELOG.md).
- `docs/release.md` and `scripts/rc_check.py`: the form of a release's checklist does not
  change; no rule changes, so the change has no delta.
- The version bump in this pull request: the RC's commit is its own commit on main, as
  0.45.0rc1's, so that the tag points at a commit that changes only the version.
- 4.4's user's own way back on a test home: the schema does not move.
- The installers: `docker/install.sh` and `docker/install.ps1` did not change since v0.45.0.
- Checks of 0.45.0's features (model servers, projects, Kilo, the folder of documents): 0.46.0
  does not touch them (4.7: an earlier check comes back only when a release touches what it
  checked).
- Moving the task to review: this pull request is not the task's last; LAD-269 stays in
  progress until the final 0.46.0.

## Impact

- Docs and one unit test only; no code, API, MCP, CLI or schema change, no CHANGELOG line. The
  release it prepares is a minor (0.46.0).
