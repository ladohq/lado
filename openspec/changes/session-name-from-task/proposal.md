Task: LAD-265

## Why

In the New session window the session's name hides in Team: to see or change it the human opens
Team every time. The name it offers says little: in a project it is `<project>-<repo>`
(`runtime.project_session_name`), so the repository `lado` of the project `lado` gives
`lado-lado`, and a second session `lado-lado-2`, whatever the task is. A project's place takes
two lines in Where (its name, then the badge `Project <title>`), and Team calls the kits
"Setup", a word the rest of LADO does not use for them (the Kits page, the session's details,
`--kit`).

The design was settled with the human in two rounds of ui-design (session artifacts
`ui-design/new-session-dialog/*` and `ui-design/new-session-dialog-2/*`: spec, mockup, brief,
design system, critique); this change carries it, with the critic's open finding F8 (on a phone
`Task ⓘ Name ⓘ` reads as one label) settled by the human (run artifact
`mockup-task-name-phone.html`).

Root cause: the name was a Team field because it used to come from the place alone, and the
place's default joins project and repository without looking whether one repeats the other.

Options weighed (ui-design rounds 1 and 2):

- A: keep the name in Team, only fix `project_session_name`. Cheap, but the name stays hidden
  and still says nothing about the task.
- B: a Session name row of its own under Task, with a source tag (`auto · from LAD-263`) and
  `Use automatic` (round 1). Clear, but one more row and two more controls.
- C (taken, round 2): a compact **Name** field on Task's label row, made from the task until the
  human types; clearing the field gives LADO's name back. No new row; the name visibly follows
  the task it is made from. Long-term cost: a naming rule in the browser that the server does
  not repeat (design D1); the server stays the authority on what is taken.

## What Changes

- **Name** is a compact field on the right of Task's label row (`Task ⓘ ……… Name ⓘ [lad-263]`),
  shown for a folder, a project's repository and a clone; Team no longer has it (neither the
  summary nor the opened fields). A new empty folder has no Name field: its Folder name is the
  session's name and says so (`Also the session’s name.`). Resume has none.
- **The automatic name**: a tracker key at the start of the task's first line (`LAD-263: …`,
  `[LAD-263] …`) gives `lad-263`; else up to three words of the first line without filler words
  (`fix-login-redirect`, at most 32 characters); else the place's name. A taken name gets the
  next free number (`lad-263-2`), and a note says so. It follows the task (300 ms after the
  last keystroke), the place and the list of sessions until the human types in the field.
- **A typed name is kept**: the task and the place no longer change it; it is checked again for
  being taken. What the human typed is the session's title, its plain form the name
  (`Review Kao` → title `Review Kao`, name `review-kao`); a name with no plain form (Cyrillic,
  Chinese) stays the title, and the session takes the automatic name. Clearing the field gives
  the automatic name back (shown as the placeholder, the value again on leaving the field).
- A typed name that is taken is refused under Task before the press, with `Use <next>`; the
  footer says `choose another name`. Over 80 characters (`Limits.max_title`): `Name: at most 80
  characters.` and `shorten the name`. No automatic name (a clone before its URL, no task):
  `name the session`.
- **The place's name** joins project and repository without repeats (`lado` + `lado` → `lado`,
  `lado` + `lado-site` → `lado-site`, `acme-web` + `web` → `acme-web`, `shop` + `frontend` →
  `shop-frontend`), for the window and for `lado start --project <id> --repo <name>` without
  `--name`. Sessions that exist keep their names.
- **Where is one line**: icon, name, then a muted secondary: a project's repository `in project
  <title>` (no badge), a folder its path, New empty folder the workspace, Clone from URL none.
  The secondary is cut first, down to about 12 characters, then the name. The same in Recent.
- **Kits instead of Setup**: Team's summary `Kits <names>`, the opened section **Kits** with
  `+ Add kit`, an info text in plain words, the footer's `choose a kit`, Team's info `Kits and
  permissions are LADO's defaults.`
- Small: Team's summary wraps under its head on a phone; Change/Hide has one chevron; on a
  phone the free room of Task's label row falls between `Task ⓘ` and `Name ⓘ` (F8).
- A minor (0.46.0): a new feature of the window and a changed default of `lado start
  --project`; no API, MCP or schema change (`web/openapi.json` unchanged).

## Scope

- Web: `web/src/Launch.tsx` (the name's state and rule, the notes, the footer, the start
  request), a new `web/src/sessionName.ts` (the rule, pure), `LaunchTeam.tsx` (Name out, Kits),
  `LaunchWhere.tsx` (one line, no badge), `web/src/styles.css`.
- Core: `runtime.project_session_name`.
- Tests: pytest (unit) for the core, vitest for the rule and the window, UI e2e
  (`tests/ui/test_launch.py`, `tests/ui/test_launch_project.py`, others whose texts change).
- Docs: `docs/design/ui.md` (Launch and session control), `docs/cli.md` (`lado start
  --project`'s name), CHANGELOG.md (`## 0.46.0 (unreleased)`, the heading renamed from 0.45.1).

## Out of scope

- The start button's label (`Start in LADO`, `Start new session <name>`, …): the human kept it
  as it is.
- `Resume it` beside a taken name (ui-design round 2, state 6): New session offers no resume
  since new-session-without-resume (LAD-261); a stopped session is resumed from its page or the
  session list. The refusal offers `Use <next>` only.
- Renaming sessions that exist (`lado-lado` stays `lado-lado`): a session's name is its tmux
  session, its branches and its address.
- A naming rule in the server for a task (`lado start` with a prompt): the CLI names by
  `--name` or the place as before; the rule is the window's suggestion only (design D1).
- The server's `default_name`, `free_name` and `name_state`: unchanged in meaning; the line
  `Session <name> stopped here` still comes from them.
- Dark-mode or token changes: nothing in `web/src/tokens.css` changes.
