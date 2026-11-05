Task: LAD-192

## Why

Symptom (audit of LAD-189, finding F1): on a window 1100 to 1600 px wide the session's head
takes two or three lines, 66 to 98 px, of the height the chat needs. The human opened
LAD-189 for it: the head "began to take a lot of room after the feature Projects".

Cause: the head was decided on 2026-10-08 as one line of the top bar with all its facts
(folder, git, kits, CLI) in it; a head with the facts behind an ⓘ was turned down then. The
line had a flexible row of facts that wraps when it lacks room. LAD-125 added the fact
`project` in front, which pushed the row over its room on common window widths. Every new
fact does the same, so the fault is the facts' place in the line, not the width of one fact.
The same line also underlines facts that cannot be clicked (F4), puts Stop beside a
look-alike Copy link (F10), costs about 12 Tab stops before the content (F11) and cuts the
path so that it says little (F12).

Options weighed:

- A: keep the facts in the line and hide them by width (container queries). Smallest diff;
  each new fact needs its own width rule, and what a human sees depends on the window.
- B (taken, the human's decision of 2026-11-05, LAD-189 spec §1): one line of 48 px with the
  project, the title, the run time, Stop and the link; the facts in a popover Details with
  the same content as the phone's sheet. One place for facts at every width, new facts cost
  the line nothing. A fact needs one click more, which is why the branch stays in the line
  on a window of 1600 px or more.
- C: a fixed second line that scrolls sideways. Keeps every fact in sight, and costs about
  30 px of height for good; a second line was turned down on 2026-10-08 too.

## What Changes

- Above 600 px the head is one line of `--head-h` (48 px) that never wraps: the status dot,
  the project as a breadcrumb, the title as a button, the words of a broken session, the run
  time, the branch at 1600 px and more, Stop with its word, a line, the link.
- The title's button opens the popover Details: the state line, Folder with Copy path, Git
  with Copy URL, Kits, CLI, then Rename, Copy link and All sessions. The name of a titled
  session moves there too (`id <name>`).
- The pencil, the double click on the title and Copy link leave the line; Rename in Details
  edits the title in place in the line.
- The phone's sheet takes the same content (one component), keeping its × and its own title
  field. Its Menu and the head's actions become 44 px; the head is otherwise as it was.
- `Skip to chat` is the first stop of a session's page; the head has four stops: project,
  title, Stop, link. On a computer the status dot is no stop any more.
- The record of 2026-10-08 in docs/design/ui.md (the facts behind an ⓘ turned down) is
  replaced; the Session head, Session title, Phone layout and Look sections follow.

Decided with the human where the spec and the code differ (answer #3389, 2026-11-05):

- The words of a broken session (`tmux session is gone`) stay in the line.
- A click outside the popover on a field, button or link leaves the focus there; on an empty
  place, as with Esc and a second click on the title, it goes back to the title.
- On a computer the status dot has no Tab stop.
- The phone's sheet shares the popover's content.

Scale: full. Version: a feature, the minor; `## 0.45.0 (unreleased)` already holds it.

## Acceptance criteria

- AC-1 At 601, 768, 1101, 1280, 1440, 1600 and 1920 px the head's line is 48 px high and does
  not wrap, with 4 kits and long names (frame g1-long), and while the title is edited.
- AC-2 Left to right: dot, project, `/`, title with its chevron, run time, then at the right
  end Stop, the line, the link. No folder, git remote, kits, CLI, pencil, Copy link or name.
- AC-3 The project is cut at 16ch with "…", whole in its tooltip and in Details, and links to
  its page; a session without a project has no breadcrumb, nor has a phone.
- AC-4 The title is `h1 > button` with `aria-haspopup="dialog"` and `aria-expanded`; a double
  click no longer opens the title's field.
- AC-5 The branch shows only on a window of 1600 px or more.
- AC-6 Stop has its word above 900 px, only the icon at 900 px and less, and is named
  `Stop session…`; the link has its word above 1100 px, only the dot and the tooltip
  `live · LADO server` at 1100 px and less.
- AC-7 Details opens on a click, Enter and Space, with the focus on Copy path, and shows what
  `session-head` names.
- AC-8 Details closes on Esc, a click outside and a second click on the title; the focus goes
  by the rule above.
- AC-9 Rename in Details edits the title in the line; after it the focus is on the title.
- AC-10 Tab goes `Skip to chat` first, and through the head project, title, Stop, link.
- AC-11 The phone's head is as before but for its 44 px buttons and the title's chevron (frame
  g1-390, the human's answer #3441); its title opens the sheet with the popover's content.
- AC-12 A session whose tmux is gone or whose loop is down shows its words after the title.
- AC-13 docs/design/ui.md and CHANGELOG.md change in the same pull request.

## Out of scope

- The link's states when the connection is lost (spec §4): LAD-195, which owns them.
- Layout at narrow widths, `PHONE_QUERY` and a mouse window of 600 px or less (spec §2):
  LAD-193. Until then such a window shows this line, with no measure promised.
- The head of a stopped session, its Resume and Forget (spec §5): LAD-196; they stay icons.
- Stop's popover (spec §7, F27): LAD-198; it stays as it is.
- The sections "What works" of both critiques: the human's rule, not to be changed.

## Impact

- `web/src/`: `Sessions.tsx`, `SessionDetails.tsx`, `SessionControl.tsx`, `Shell.tsx`,
  `SystemPanel.tsx`, `Menu.tsx`, `Chat.tsx`, `styles.css` and their tests.
- `tests/ui/`: `test_session_head.py`, `test_phone.py`, `test_launch_project.py`,
  `test_project_page.py`.
- Docs: docs/design/ui.md, CHANGELOG.md.
- No API, schema, MCP or CLI change; nothing below `web/` changes, so no provider is touched.
