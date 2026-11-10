# The session's name from the task, beside Task (LAD-265)

Change: `openspec/changes/session-name-from-task/` (proposal, design.md D1–D13, delta specs).
Approved look: session artifacts `ui-design/new-session-dialog-2/spec` and `mockup.html`
(states 1–12, 5b, 5c, 8b), round 1 `ui-design/new-session-dialog/*`; this run's
`mockup-task-name-phone.html` (option B).

## What a user gets

- The session's name is always in view, on the right of Task's label row, and one click edits
  it. Team no longer holds it.
- The name says what the session is for: `lad-263` for a task with the key `LAD-263` anywhere
  in it, and without a key the place's name, which no longer repeats itself (`lado`, not
  `lado-lado`).
- A typed name is the human's: kept, shown as typed in the session list (its title), its plain
  form in links and branches. Emptying the field gives LADO's name back.
- Where takes one line for every kind of place; Team says **Kits**, as the rest of LADO does.

## The scenarios

1. Open New session on the project `lado`'s repository `lado`: Where reads `lado  in project
   LADO` on one line, the focus is in Task, Name reads `lado`.
2. Type `LAD-263: the codex model must win…` in Task: 300 ms after the last key Name reads
   `lad-263`. With a session `lad-263` already there it reads `lad-263-2`, and a line under Task
   says `Name: lad-263 exists already, so this one is lad-263-2.`
3. Click Name, type `Review Kao`: under Task `Name shown as “Review Kao” · in links and
   branches: review-kao`. Changing Task or Where no longer changes Name.
4. Empty Name: `lad-263` (or whatever the task gives) shows grey as the placeholder;
   on leaving the field it is the value again.
5. Type a name a session has: Name turns red, `Name: a session named review-kao exists
   (stopped, in lado).` with `Use review-kao-2`, and the footer `To start: choose another name`.
6. Start: the request carries `name: "review-kao", title: "Review Kao"` (or the automatic name
   alone), and the session's page opens under that name.

## The window's parts

Top to bottom: **Where** on one line with its notes; **Task**, its label row carrying **Name**
on the right; the name's note under Task, if any; **Team** as a summary with Change; the footer.
The look is the mockups' (round 2's states, this run's option B on a phone).

## Words, exactly

| Where | Text |
|---|---|
| Name's label | `Name` |
| Name's info | `How you find this session in the list. LADO makes it from the task; type your own, or clear the field to get LADO’s back.` |
| Numbered | `Name: <base> exists already, so this one is <id>.` (`<id>` bold) |
| Typed, title ≠ id | `Name shown as “<title>” · in links and branches: <id>` (`<id>` bold) |
| Taken | `Name: a session named <id> exists (<status>, in <folder's last part>).` + `Use <next>` |
| Too long | `Name: at most <Limits.max_title> characters.` |
| Folder name's note | `Also the session’s name.` |
| Footer | `name the session`, `choose another name`, `shorten the name`, `choose a kit` (was `choose a team setup`) |
| Where, project | `<repo>` then muted `in project <title>` (no badge) |
| Team summary | `Kits <names>` · `Agent <title>` · `Permissions <summary>` (no Name) |
| Team opened | **Kits** ⓘ, chips, `+ Add kit` (`aria-label="Add kit"`) |
| Kits' info | `Kits add roles, skills and ways of working to the team. Install more on the Kits page.` then each chosen kit's `name: description` |
| Team's info | `Kits and permissions are LADO's defaults.` / `Agent as in your last session; kits and permissions are LADO's defaults.` / `As in the last session in this folder.` (the clause `"<name>" is taken by another session.` goes) |

## The rule, in plain words

Changed by the human during review (finding F2): the key anywhere in the task, no name from
its words.

1. The first tracker key anywhere in the task (two or more capital Latin letters, `-`, digits,
   a word of its own: `LAD-263: …`, `Fix LAD-263 …` → `lad-263`; `xLAD-263`, `LAD-263a`,
   `lad-263` are none; `HTTP-2` counts, and the human changes it).
2. (Dropped: up to three words of the task.)
3. Else the place's name (`default_name` of the folder check, the project's repository or the
   clone target).
4. Taken → the next free number (`-2`, `-3`, …).
5. Recomputed on a change of the task (300 ms), the place or the sessions, until the human
   types in Name; a typed name stays, checked again for being taken.
6. Typed text → title; its slug → name; a slug shorter than 2 → the automatic name.
7. Clearing the field → rule 1–5 again.

## Width by width

| Width | Task's label row | Where | Team |
|---|---|---|---|
| Phone 390 | `Task ⓘ` left; `Name ⓘ` and a field of at most 140 px right; the free room between them (F8, B) | one line, the secondary cut first, ≥ ~12 characters of it kept | summary under its head, wrapping; opened one column |
| Tablet 768, desktop | Name's part up to 300 px, right-aligned | one line | as today |
| Below ~300 px | Name drops under Task's label (`flex-wrap`) | — | — |

## What stays

The start button's labels, the line `Session <name> stopped here <when>` and the server's
`default_name`/`free_name`/`name_state`, the 409 as the last word on a taken name, the Resume
window, the draft (a typed name kept), New empty folder's own name and title.

## Not in this change

`Resume it` beside a taken name (New session offers no resume since LAD-261), renaming sessions
that exist, a server-side rule for a task's name, any token change.
