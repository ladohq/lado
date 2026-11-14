## Context

`LaunchDialog` (`web/src/Launch.tsx`) opens through `useModal` (`web/src/modal.ts`), whose
`showModal()` puts the focus on the window's first focusable control. Then `useOnce(getRecentFolders)`
asks for the recent places; its answer sets `opened`, and an effect on `opened` focuses Task or
Folder name unconditionally. A slow answer therefore takes a focus the human already moved.

## Decisions

### D1: The late focus moves only from where the window put it

`LaunchDialog` remembers the element that has the focus right after opening (an effect that runs
after `useModal`'s layout effect, as `modal.ts` says a window's own opening work does). The effect
on `opened` focuses Task or Folder name only when `document.activeElement` is still that element,
or the page's body (a focus lost, as Check again's guard already treats it). When `opened` is set
at once (a draft, a project or a path asked), the effect runs at mount and the focus is untouched,
so it moves as today.

Why: the rule is "do not take a focus the human moved", and the element showModal chose is the
one state that means "not moved yet". Alternatives: a flag set by any `focusin` or `pointerdown`
inside the dialog (two listeners and their cleanup for the same fact); dropping the late move and
waiting with Task focused until the answer (changes the requirement for every opening, and Where
would jump after the human started typing).

### D2: The regression test holds the answer back

A UI test (Chromium, `tests/ui/test_launch.py`) routes `**/api/folders/recent` through a handler
that answers only after the test focused Cancel (an event the test sets, not a fixed sleep longer
than the test's own steps), then checks the focus stays on Cancel, Where shows the last place, and
Enter closes the window; and with the focus untouched, that it lands in Task once the answer comes.
The UI layer is the lowest that sees it: the bug is the browser's focus against a network answer's
timing; a vitest test could check the guard with a mocked `getRecentFolders`, and the developer
may add one, but the UI test is required.

### D3: The flaky test stays as it is

`test_the_session_list_and_session_windows_give_the_focus_back` keeps its steps: with D1 it is
right as written, and its failure was the defect, not the test. No retry is added.
