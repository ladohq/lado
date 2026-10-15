Task: LAD-78

## Why

The text field on a gate's tab of the waiting card looks cut on the left (the task's
screenshot: the blue focus ring of "Comment for the next step (optional)" has its top and
bottom lines, but no left line). The task asks to check the other sides too.

Root cause: the card's list (`.waiting-list`, `web/src/styles.css`) scrolls
(`overflow: auto`), and a scrolling box clips whatever its children draw outside its
padding box. Its padding is `0 6px 4px 0`: 4 px below (LAD-70 added it for the same
ring), 6 px on the right, none on the left or at the top. Two rings are drawn outside a
child's box there:

- the gate's comment field (`.answer textarea`) has no focus rule of its own and takes the
  UI's `:focus-visible` outline, 2 px at an offset of 2 px: 4 px outside the field;
- the own answer and the Skip comment (`.waiting-field:focus`) and a question the human
  came to from the feed (`.waiting-question.marked`) draw a 3 px `box-shadow` ring.

Each of them starts at the list's left edge, so the list cuts their left side; a ring at
the list's top (the first question marked, or a field scrolled to the top edge as it gets
the focus) loses its top too. Right and bottom have room already. Reproduced on main with
the LAD-70 UI test (`test_a_gates_long_comment_grows_to_8_lines_and_stays_above_the_send_row`):
its screenshot shows the same cut.

## What Changes

- The card's list keeps room for a ring on every side: 4 px at the top, the left and the
  bottom (the right keeps its 6 px), and pulls itself out by as much at the top and the
  left, so the questions, the fields and the Send row stay where they are now.
- A field that gets the focus or grows scrolls into view with that room on every side
  (today only below).
- The look of the rings does not change (mockup `task/lad-78/mockup-focus-ring.html`:
  now and after, on the UI's real styles).
- Docs: `docs/design/ui.md` (The waiting card: the fields), CHANGELOG.md.
- A patch-level fix (no API, CLI, MCP or schema change); its CHANGELOG line goes under the
  open heading `## 0.40.0 (unreleased)`.

## Scope

- `web/src/styles.css`: `.waiting-list`, `.waiting-field`, `.answer textarea`.
- Tests: UI e2e in `tests/ui/test_gates.py` (a gate's comment) and `tests/ui/test_chat.py`
  (an own answer, a marked question, a narrow window), each measuring the ring against the
  list's visible box, with screenshots.

## Out of scope

- **One focus look for all the card's fields** (the gate's comment has the UI's blue
  outline, the own answer a blue border with a soft ring): a change of look the task does
  not ask for; the task is the cut. A task of its own if the human wants it.
- **A ring drawn inside the field** (an inset shadow or a negative outline offset): it
  would never be cut, but it changes the look and the field's text area, and the cut is
  the list's, not the field's.
- **Dropping the list's scrolling**: LAD-70 needs it (the fields grow inside the list
  under the fixed Send row).
- **The Flows tab's gate card**: checked, its frame has 14 px of padding and no scrolling
  box around the field; its ring shows whole already.
- **Other scrolling boxes of the UI**: not in the task; none was reported cut.

## Impact

- UI only, CSS only: the waiting card's list and its two field rules; no API, CLI, schema
  or provider change.
