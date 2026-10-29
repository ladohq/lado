Task: LAD-159

## Why

Symptom: on a phone the project's page (`/projects/<id>`) does not scroll. The page shows
its head, Repositories, Sessions and the warning about isolation, and is cut at the
screen's bottom: Variables, Secrets and Delete project cannot be reached (the task's
screenshot, iPhone Safari, upright).

Cause: in the phone layout the window never scrolls; each page's content scrolls by itself
(phone-layout, "On a phone the composer stays at hand"). For Projects, as for Sessions, the
content area clips (`:root[data-phone] .content:has(> .projects)` has `overflow: hidden`)
and the section's own panes scroll: the list (`.session-list`, `overflow-y: auto`) and the
project (`.project-detail`, `overflow-y: auto`). A pane only scrolls when its height is
bounded. The narrow window's rule (`@media (max-width: 900px)`, LAD-138) sets
`.projects { height: auto }` so a computer's narrow window scrolls as a page, and a phone
matches that rule too. The phone's rule for Sessions puts `height: 100%` back
(`:root[data-phone] .sessions`); the phone's rule for Projects (LAD-134) does not. So on a
phone `.projects` grows to its content, the panes never overflow, and the clipping content
area cuts them: nothing scrolls. The list of projects has the same defect once it is longer
than the screen.

The UI tests did not catch it: `test_on_a_phone_the_delete_block_and_dialog_fit` reaches the
Delete block with `scroll_into_view_if_needed`, which scrolls a clipped (`overflow: hidden`)
box from script, which a finger cannot.

Options weighed:

- A (taken): `:root[data-phone] .projects` gets `height: 100%`, as `:root[data-phone]
  .sessions` has. The phone's Projects is then built as its Sessions: the window still,
  the list or the project scrolling under the top bar. Long-term cost: none new; one line
  in the phone section, the two sections' rules alike.
- B: on a phone let the content area scroll Projects (drop `overflow: hidden` from
  `:root[data-phone] .content:has(> .projects)`). Also works, but Projects becomes the one
  section of the phone whose content area scrolls while its panes are declared scrollers,
  two scrollers in one place; a later change of either breaks it again.
- C: drop `height: auto` from the narrow window's rule. It would change a computer's
  narrow window, which scrolls as a page by design (LAD-138, M1), to fix a phone.

Held against the design principles: a CSS rule of the web UI, no provider involved; one
source of truth (the phone's rules stay in the phone section of `styles.css`); nothing
silently dropped.

## What Changes

- On a phone the project's page scrolls by itself under the top bar to its end (Variables,
  Secrets, Delete project), and so does the project list when it is longer than the screen.
  The window still does not scroll.
- `docs/design/ui.md`, Projects, Layout: on a phone the list and the project each scroll
  by themselves under the top bar.
- CHANGELOG.md, `## 0.44.0 (unreleased)`, Fixed: a line on the phone's project page.
- A fix: the patch level; 0.44.0 is already the next version (unreleased, a minor), so
  the heading stays.

## Scope

- The Projects section in the phone layout: the project's page and the project list.
- A UI e2e test that scrolls the way the human does (the wheel, not script), and the
  existing phone test of the Delete block made to reach it so too.

## Out of scope

- A computer's narrow window (at most 900 px, a mouse): it scrolls as a page and works;
  not touched.
- Other sections on a phone: Sessions has its height already; the other pages scroll in the
  content area (`:root[data-phone] .content`, `overflow-y: auto`) and do not clip.
- A general check that every phone page scrolls to its end: no other page clips its
  content; a test per section where it clips is enough (only what is used).

## Decisions for the record

- D1. Option A: `height: 100%` on `:root[data-phone] .projects`, beside its
  `grid-template-rows: minmax(0, 1fr)`, as Sessions does.
- D2. The test scrolls with the mouse wheel over the page (`page.mouse.wheel`, as
  `test_layout.py` does), which Chromium sends to the box under the pointer only when it
  scrolls; script scrolling (`scroll_into_view_if_needed`, `scrollTop`) scrolls a clipped
  box too and proves nothing here. Playwright has no touch swipe; the wheel follows the
  same rule of which box scrolls.
- D3. The test layer is UI e2e (`tests/ui/`, marker `ui`): the defect is layout in a real
  browser; no unit test sees it.

## Impact

- Code: `web/src/styles.css` (the phone section, Projects).
- Tests: `tests/ui/test_project_page.py`, `tests/ui/test_projects_section.py`.
- Docs: `docs/design/ui.md`, CHANGELOG.md.
- Specs: `projects` (the requirement "The Projects section takes the phone's screen in
  turns").
