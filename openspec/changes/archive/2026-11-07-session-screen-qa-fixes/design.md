# Design: session-screen-qa-fixes

Mockups: `task/lad-224/mockup-sideways.html` (option 1 approved), `task/lad-224/mockup-notices.html`.

## D1. One hook closes every window

Root cause in the proposal. Checked in Chromium: removal only, and removal then `close()`, leave
the focus on `body`; `close()` then removal gives it back.

Options:

- A: restore the focus by hand in each `onClose` (a ref to the opener in 13 places). Each new window
  must remember it, and the defect comes back with the first one that does not.
- B: call `dialog.close()` in each window. Fewer lines, but the same rule still lives in 13 copies.
- C (taken): `useModal(ref)` in a new `web/src/modal.ts`, the one place with `showModal` and
  `close`. The browser remembers the opener, so no window keeps a ref. The long-term cost is one
  small hook; every new window gets the behaviour by using it.

The hook uses `useLayoutEffect`: its cleanup runs before React removes the node, a passive effect's
after. A window with work of its own at opening (Share, Finish, the system update, ForgetMany's
first focus) keeps that in its own effect, after the hook. StrictMode's second mount works because
the cleanup closes the window.

A unit test fails on any `showModal(` in `web/src` outside `modal.ts` and the test fakes, so the rule
stays in one place.

Added during the build, at the supervisor's question: the browser remembers the focused element, and
for a window from a kit card's ⋯ that was the menu item. `RowMenu` left its menu open, so Esc came
back to an open menu, and a press on Cancel closed the menu first, taking the remembered item away.
`RowMenu` now closes the menu and focuses ⋯ before the item's action. The fix is there, not in
`useModal`: the hook cannot know what stands for an element that is gone, and a menu left open under
a window was the defect itself. Only the Kits page's cards open windows from a menu.

## D2. A focus given back shows no tooltip

A focus that reached the opener's `Tooltip` would count as the keyboard's, also after Cancel pressed
with the mouse: `pressed` is set only by a press on the trigger. It does not reach it: `close()` runs
in a layout effect's cleanup, within React's commit, when React's root listener drops events
(`_enabled` in react-dom), so `onFocus` does not fire and no code is needed. The `givingBack()` flag
planned here was not built: no test could fail without it. `tests/ui/test_layout.py` holds the
behaviour, and a probe with `close()` called from Cancel's click, outside the commit, turned it red
(`to_have_count(0)`, actual 1), so a React that stopped dropping those events would be caught.

## D3. The toggle sideways

Options: the icon in the tab row (taken, the human's choice, mockup option 1); Yours | All as above a
phone, which takes a third of the row and adds a second look on phones; showing the team's row
sideways, which spends the height the feed was given.

`Session` renders `<MessagesToggle />` in `SessionTabs` when `tab === "activity" && phone === "short"`,
and `Activity` renders the team's row only when `phone === "tall"`, so the toggle is in the page
once. The rule `:root[data-phone="short"] .team-row` goes. `:root[data-phone="short"]
.session-tabs .between-toggle` is `display: grid`, 36 px by the existing phone rule, without the
top margin. A stopped session sideways has the plain icon; the words stay upright. An expanded card
hides the tabs and so the toggle, as upright it hides the team's row.

## D4. Notices

`.kit-alert` is replaced by `.kit-warning` in both places of `Kits.tsx` and its rules removed, so no
second warning style remains. In `Failed` of `LoginWindow.tsx` the heading is `<p class="problem">`
with its `<b>`, `.login-fail .problem` has no margin, `role="alert"` stays on the block, and the
quote loses `border-left`.

## D5. The task's tooltip

`taskTip(task)` in `Flows.tsx`, a pure function: the text cut at 12 lines or 600 characters, whichever
comes first, with "…" when cut, and then the line "The rest is on the run's page". 600 characters are
about 12 lines of the 320 px tooltip; that is a limit, not a height: long lines that wrap can make
the box higher than a window of 390 px, which only a very low window with a mouse would see.
Its lines keep their breaks (`white-space: pre-line`).

`ListEntry` gets `tip?: ReactNode` and `tipWhen?`, and `ListGroup` wraps the row's `Link` in `Tooltip`,
so hover and keyboard focus both work. Whether something is hidden depends on the row's width, so it
is measured when the row is entered or focused: a task of several lines always, a one-line task when
`.run-task-line` has `scrollWidth > clientWidth`. That answer goes through `Tooltip`'s new prop `when`,
asked in the same event: a tip set to `null` by state would come a render too late for that entry.
`card()` takes both from `entry()`.

## D6. The task's line stays muted

The rules `.list-row.waits .run-task-line` and `.list-card.waits .run-task-line` go. Contrast of
`--muted` on `--human-ground`: 5.5:1 light, 5.3:1 dark. `.run-about` stays `--human`.

## D7. Session first

`ArtifactsTable.tsx` puts `""` first among the fresh open scopes when it lays them out. `groupByScope`
keeps Session first while the order is still empty, so the runs' arrival does not move it. A Session
group that first appears while the tab is open still goes to the end of its part: the rule that
nothing moves under the human wins, and the next entry puts it first.

## D8. Console errors

The report holds a count, not the texts, and its stand is gone, so the 16 cannot be read. The
developer collects `console` errors and `pageerror` in the UI tests of Activity, Flows, Artifacts,
Kits and login, as `test_a_page_loads_without_a_console_error_and_with_its_icon` does, and sorts
them in `build-report`: caused by a test's stub, or real. A real one of this change is fixed; any
other is shown to the human, and a tracker task is created only on their yes. No permanent check is
added.

## Against the principles and the roadmap

UI only, so the neutral core is untouched. D1 and D4 remove copies, one rule each. D5's field has a
real user. The coming stages do not touch these windows' shape.

## Tests by layer

| Rule | Layer |
|---|---|
| `useModal`, the `showModal` guard | unit (vitest, `modal.test.ts`) |
| Focus back after Esc and Cancel, no tooltip | UI e2e: jsdom has no real focus return (`test_terminal_panel.py`, `test_stopped_session.py`, and one walk over Forget, Finish, Share, New session, Add kit in `test_layout.py`) |
| Toggle sideways, empty feed, works | UI e2e, `test_phone.py`, 844×390 with touch, 568×320 |
| Notices | unit for the class; UI e2e for computed style and a screenshot, live windows (`test_kits_page.py`, `test_providers_section.py`) |
| `taskTip`, when a tip is silent | unit (`Flows.test.tsx`); UI e2e for hover and focus (`test_flows_tab.py`) |
| Muted line | UI e2e computed colour, `test_flows_tab.py` |
| Session first | unit (`ArtifactsTable.test.tsx`); UI e2e with 100+ artifacts (`test_artifacts_tab.py`) |

No integration test: nothing crosses processes.
