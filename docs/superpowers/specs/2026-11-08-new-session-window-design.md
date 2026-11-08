# The New session window, reorganized (LAD-239)

Change: `openspec/changes/new-session-window/` (proposal, `design.md` with D1–D16, the new
capabilities `new-session-window` and `folder-setup`, deltas of the window's older
capabilities). This document is the human's view. The look: run artifact
`mockup-new-session.html` (from `ui-design/lad-239-design-2`; its states A(a)…A(k) are named
below), the designer's spec `ui-design/lad-239-design-2/spec`, the review of the old window
`ui-review/lad-239-review/critique`, the analyst's audit `audit`.

## What a user gets

    New session                                              ×
    Where   [▭ webapp  ~/workspace/webapp                 ⌄]
            ✓ Ready · branch main · Session webapp stopped here 2 days ago
    Task ⓘ  [What should the team do?                       ]
            [                                                ]
    Team ⓘ  Setup default  Agent Claude Code                Change ›
            Permissions Asks before changes  Name webapp-2
    ─────────────────────────────────────────────────────────
                       Cancel  [Resume webapp] [Start new session webapp-2]

The window opens where the human worked last, with the focus in Task. Writing a task and
pressing the start button is the whole of the most frequent start. The rest is one line,
opened by Change. A stopped session of the place is offered beside the new start; which of
the two is blue follows Task (empty: Resume; filled: Start new).

## The scenarios

| Scenario | Before | After |
|---|---|---|
| 1. Again where I worked, with a task | open, find the Recent chip, type a name if the old one is stopped, unfold First message, type, Start | open, type the task, Start new session (the place, name and agent are there) |
| 2. The same in a project's repository | open, switch to Project, choose project and repository, choose the agent, Start in Shop | open (it is the last place, or pick it in Recent with its badge), type, Start in Shop |
| 3. Resume a stopped session | its page's Resume…, or Resume it after a refusal | its page's Resume…, or Resume webapp in New session's footer |
| 4. The first run | From scratch, Name, choose the agent | New empty folder, Folder name, the agent chosen once when two are installed |
| 5. Clone a repository | Clone from URL in the switch | Clone from URL… at the end of Where's list |
| A folder of documents outside git | a red refusal and a terminal command | Set up and start in notes, with what is saved and left out shown first |

## The window's parts

| Part | Content |
|---|---|
| Where | One combobox. Closed: the place's icon, name (15/600), path (12, muted), a project's badge `🔑 Project Shop`. Open: **Recent** (≤10, latest first, the time at the right), **Somewhere else**: Other folder…, Clone from URL…, New empty folder…, Project…. A typed `/` or `~` path: `Use folder <path>`, then subfolders. |
| Under Where | One line: `✓ Ready · branch main`, then ` · Session <name> stopped here <when>` when there is one. Refusals and warnings as today, in the three levels. |
| Task | Three lines, placeholder `What should the team do?`, Enter is a new line. No note under it. |
| Team | `Setup <kits>  Agent <CLI>  Permissions <summary>  Name <name>` and Change ›. Open (Hide ⌄): Session name, Agent (its version muted at the right), Team setup (the kit chips), Permissions (radio rows), Model (today's picker), Switch off (today's text field). No notes under the fields. |
| Footer | `To start: …` while the button is off; Cancel (a text button); the start button naming the place: `Start in webapp`, `Start in Shop`, `Clone and start in shop-site`, `Create and start` (New empty folder), `Set up and start in notes`; with a stopped session `Resume <name>` and `Start new session <free name>` (in a project `Start new session in Shop`). |

## Words, exactly

| Where | Text |
|---|---|
| ⓘ Task | `The team gets this as its first message and answers in the chat. You can leave it empty.` |
| ⓘ Team | `As in the last session in this folder.` / `Agent as in your last session; setup and permissions are LADO's defaults.` / Resume: `As when it stopped. A change takes effect from now on.`; a taken name adds `"<name>" is taken by another session.` |
| ⓘ Team setup | the kit's description from its kit.yaml, e.g. `default: a supervisor that delegates to general-purpose coding workers.` |
| ⓘ Permissions | each mode: title — description — CLI value |
| ⓘ Switch off | `kind:name or kind:name@kit, separated by commas; kinds: agent, skill, mcp, flow.` |
| ⓘ Where (a project repository) | `<repo> is a repository of the project <title>: the team works with <title>'s keys and settings.` |
| ⓘ Folder name | `LADO creates it in <workspace>.` |
| ⓘ Set-up | `LADO keeps a history of changes in this folder (git), so you can see and undo what the team does. Your files stay where they are.` |
| ⓘ Resume | `The team continues where it stopped: its chat, tasks and work stay.` |
| Clone's notes | `✓ Found` under Repository URL, `✓ New folder` under Clone into |
| Set-up panel | `Not yet set up for LADO. Starting saves <n> files (<size>) as the starting point.`; `Counting files…`; `<k> left out · Review ›`; `Do it yourself ›`; `Tick to include:`; reasons `looks like a secret`, `<size>, larger than 50 MB`, `a separate git repository`; a ticked secret `Will be saved in the history`; `Run in this folder, then choose it again:` |
| Set-up refusals | `Choose a smaller folder: this one holds <n> files.` / `… holds <size>.` / `Choose a smaller folder: this is your home folder.`; author: `Git doesn't know who you are yet. Tell it once for this computer:` + command + Check again |
| A missing folder | `There is no such folder — LADO will create it.` + Start from scratch here |
| Footer reasons | `To start:` choose a place · name the folder · choose an agent · choose a smaller folder · tell git who you are · wait for the count · fix the model · shorten the task · log in to `<CLI>` |
| Resume window | title `Resume session`; `<name> · stopped <when>` ⓘ, `Start a new session instead`; field `Message`, placeholder `What should the team do next?`; button `Resume <name>` |
| Rail | `New session` (was Launch) |

### Permissions in words

| CLI | Mode | Title | Description | Summary |
|---|---|---|---|---|
| Claude Code | default | Ask before changes (recommended) | Asks before it edits files or runs commands. | Asks before changes |
| | plan | Plan only, no changes | Reads and proposes a plan; changes nothing. | Plan only |
| | acceptEdits | Edit files without asking | Still asks before commands. | Edits without asking |
| | dontAsk | Only what your settings allow | Never asks; refuses the rest. | Only what settings allow |
| | auto, manual | the CLI value, until checked against `claude --help` | — | the CLI value |
| | bypassPermissions | Full access, never ask ⚠ (risky) | Does anything, deleting files too. Only for a folder you can afford to lose. | Full access ⚠ |
| Codex | default | Work inside this folder (recommended) | Asks before going outside it. | Works inside the folder |
| | bypassPermissions | Full access, never ask ⚠ (risky) | No limits, outside this folder too. | Full access ⚠ |
| OpenCode, Kilo | default, acceptEdits, plan, bypassPermissions | as Claude Code's same modes, checked against `opencode_family.py`'s config | | |

The row's description shows under the chosen mode and always under a risky one.

## Width by width

| Window | Frame | Team open | Footer |
|---|---|---|---|
| above 760 | 640 px, 40 px from the top, grows down; the body scrolls | two columns | one row, right-aligned |
| 760 and less | full-screen sheet, head 56 px | one column | reason on top, then buttons of 44 px; with two actions a column (Resume on top) and no Cancel (× closes) |

## What stays

The checks and their texts (the core's), the three levels of notes, the clone's job and
progress, the Project way's fields inside Where, the model picker and its refusals, the
start's refusals and warnings, the Started notice above the session's tabs.

## Not in this change

Who will lead the session; files attached to the task; Switch off as ticks; fields for git's
author; a `lado start` flag for the set-up. Reasons in the proposal's Out of scope.
