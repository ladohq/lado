Task: LAD-239

## Why

The New session window is the dialog the human opens most often, and it is built in the order
LADO is built, not in the order the human works: the source first (From scratch | Folder |
Clone from URL | Project), then the path, the name, the kits, the agent CLI and the
permission mode in a grid of equal fields, the first message folded at the bottom as
"optional", the model and Switch off under Advanced. An audit of the running window (the
artifact `audit`) and the design-studio kit's review (`ui-review/lad-239-review/critique`, 20
findings, 9 of them to fix) found:

- **The most frequent start costs the most.** "Again where I worked, here is the task": the
  window opens empty, the recent folders are full paths in mono chips, the task is folded,
  and a folder whose last session is stopped (the usual case) has its default name taken —
  the window knows it beforehand but keeps Start on and refuses after the press, then shows
  "Resume it" twice.
- **The agent CLI is chosen again in every new place** when two are installed, though the
  human almost always uses one; a project's repository, a clone and a fresh start never
  have a folder history.
- **A project's sessions need the switch every time**: the window opens in Folder, and the
  recent folders leave out project repositories.
- **The words are a developer's**: Agent CLI, Kits, Permission mode with the CLI's own values
  (`acceptEdits`, `bypassPermissions`, `dontAsk`), `kind:name@kit`, "git repository". LADO
  is meant for non-technical people too.
- **A plain folder is a dead end**: a folder of documents outside git gets a red refusal and a
  `git init` command, which a human on a remote server, or one without a terminal, cannot run.
- **The phone**: the label stands apart from its field over the 2×2 switch, and Start falls
  below the screen in half the states; the window jumps up as notes appear; a refusal after
  Start leaves the focus on the page's body; the notes are not tied to their fields for a
  screen reader; Esc throws away a typed first message.

Root cause: the window grew one source and one field at a time (LAD-5, LAD-6, LAD-19, LAD-63,
LAD-98, LAD-137, the model), each added where the last one ended, with no pass over the
whole for the human's main scenarios.

Options weighed (rendered in `mockup-new-session.html`'s first version,
`ui-design/lad-239-design`):

- **A, "place first" (taken, the human's answer #4867).** One field Where: a combobox that
  opens on the last place and lists recent folders and project repositories by name, with
  Other folder…, Clone from URL…, New empty folder… and Project… at its end. Long-term cost:
  a real ARIA combobox to keep; projects and folders in one list need a clear project badge
  (the start button keeps naming the project).
- **B, the current structure fixed.** The 4-way switch stays, the rest as A. Cheaper, but the
  source is still chosen first, project repositories stay out of the recent places, and the
  switch takes the phone's space before the field.
- **A wizard** (steps): rejected by the review — the frequent starts are one screen and one or
  two actions, and steps would tax every start for the rare ones.

For the plain folder (the human's answers #4850, then #4867):

- **Taken: LADO sets the folder up as part of the start**, with protection: before the press
  the window shows how many files and how much will be saved, leaves out what looks like a
  secret, files over 50 MB and nested git repositories (each but the last can be ticked in),
  writes what it left out to `.gitignore`, refuses a home folder or one too big, and leaves
  the folder as it was when a step fails. Long-term cost: a scan of the folder and a write
  to it, the first time the window makes a repository of a folder that holds files.
- **The command only, in plain words.** Rejected at #4867: a human on a remote server has no
  terminal to run it.

## What Changes

- **The window's order**: Where (one combobox), Task (a visible field, second), Team (a
  one-line summary: setup, agent, permissions in words, session name, with Change ▸ that
  opens Session name, Agent, Team setup, Permissions, Model and Switch off), and a footer
  that never scrolls: Cancel, the start button that names the place, and left of them, while
  the button is off, `To start: …` naming what is missing with links to the fields.
- **It opens on the last place**: the place of the latest started session, a folder or a
  project's repository; with no sessions, on New empty folder, as today. The focus goes to
  Task when Where is filled.
- **Recent places include project repositories** (with the project's badge), named by their
  folder or repository, the path muted, the time of the last start at the right.
- **A stopped session of the same name**: the window takes the first free name (`webapp-2`)
  and its footer has two buttons, `Resume webapp` and `Start new session webapp-2`; the
  primary one follows Task (empty: Resume; filled: Start new). A refusal after Start is left
  only for a race.
- **The agent by default**: the folder's last session's, else the last session's anywhere,
  else the only one installed; the same rule for `lado start`.
- **Plain words**: Agent, Team setup, Permissions with a title per mode in words (its
  description under the chosen one and always under the risky "Full access, never ask ⚠"),
  "Ready · branch main"; secondary explanations behind an (i) toggletip.
- **A plain folder is set up and started** with one button, `Set up and start in <folder>`,
  as above; the command stays under "Do it yourself".
- **The Resume window**: the line "<name> · stopped <when>" with "Start a new session
  instead"; Message in place of First message.
- **The phone**: a full-screen sheet with the footer always visible, targets of 44 px.
- **Focus and screen readers**: the start button keeps the focus while it works; a refusal
  takes it to the field to fix; the notes are each field's `aria-describedby`, a refusal
  sets `aria-invalid`. The window stands 40 px from the top and grows down.
- **The draft**: Where, Task and Team stay as typed when the window closes without a start,
  until a start or a reload of the page.
- **The rail's Launch** becomes **New session**.

## Scope

- The New session and Resume windows (`web/src/Launch.tsx`, `LaunchProject.tsx`,
  `LaunchModel.tsx`, a new toggletip, `styles.css`), the rail's item (`Shell.tsx`).
- The server: the recent places with project repositories, a free name with each place's
  check, the providers' permission modes in words, the folder set-up's preview and start
  (`src/lado/server/launch.py`, `models.py`, `app.py`, `web/openapi.json`,
  `web/src/api.gen.ts`).
- The core: the agent suggestion's new step (`runtime.suggested_provider`), the folder set-up
  (`src/lado/setup.py`, new), each provider's words for its permission modes
  (`providers/base.py`, `claude.py`, `codex.py`, `opencode_family.py`).
- `docs/design/ui.md` (Launch and session control), `docs/cli.md` (the agent of `lado
  start`), `docs/design/modules.md`, CHANGELOG.md.
- A feature with server API fields and a change of `lado start`'s behaviour: the minor, under
  `## 0.45.0 (unreleased)`, which already bumps it. No schema migration, no MCP tool.

## Out of scope

- **Showing who will lead the session** (BACKLOG "The New session window does not say who will
  lead the session"): an endpoint over `kits.resolve` of its own; the human's answer #4830.
- **Files attached to the task** (BACKLOG "Files only in the composer"): the upload has no
  recipient before the session exists; the human's answer #4830.
- **Switch off as ticks per agent**: the human's answer #4867 keeps today's text field; ticks
  need the kits' agents in the API.
- **Fields for git's author in the window**: when git has no `user.name` or `user.email`, the
  window keeps the command and Check again (in LADO's container, the `.env` text); a rare
  case, and a write of the human's name the core never does today. Left for later, no task
  filed (the human's answer #4882).
- **The word Continue**: the action stays Resume everywhere (the human's answer #4867).
- **Descriptions of Claude Code's `auto` and `manual` modes** not checked against the CLI: a
  mode without verified words shows its CLI value as its title and no description, never
  dropped.
- **A `lado start` flag for the folder set-up**: a human at a terminal runs the command; the
  window is the one that lacks it.
- **Variant B and the wizard**: weighed above.

## Impact

- `web/src/Launch.tsx` (split: `LaunchWhere.tsx`, `LaunchTeam.tsx`, `LaunchSetup.tsx`),
  `LaunchProject.tsx`, `LaunchModel.tsx`, `InfoTip.tsx` (new), `Shell.tsx`, `styles.css`,
  their vitest tests; `tests/ui/test_launch.py`.
- `src/lado/server/launch.py`, `models.py`, `app.py`; `src/lado/setup.py` (new);
  `src/lado/runtime.py`; `src/lado/providers/base.py`, `claude.py`, `codex.py`,
  `opencode_family.py`; their pytest tests; an integration test of the set-up's start.
- Specs: new `new-session-window`, new `folder-setup`; modified `session-first-message`,
  `session-folder`, `session-scratch`, `session-clone`, `repos-folder`, `projects`,
  `provider-logins`, `session-model`, `launch-notes`, `stopped-session`.
