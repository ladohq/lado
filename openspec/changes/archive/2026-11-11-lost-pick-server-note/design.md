## Context

`useLaunchModel` (`web/src/LaunchModel.tsx`) keeps the lost-pick note as a finished string
(`lostNote`), written in the effect on the change of agent CLI. The one-server-model effect
(`picksOne`, LAD-255) runs after it and sets `tookOne`; the note list shows the `tookOne` note
only while `lostNote` is null. So the string written first stays, and it is wrong once the field
has moved.

## Decisions

- **D1. Keep the facts, not the text.** The state holds the dropped pick's name and the title of
  the CLI it belonged to (`{ name, from }`, null when nothing was lost) instead of the sentence;
  the sentence is made at render: `<name> belongs to <from>.` followed by the `tookOne` sentence
  when `tookOne` is true, else `, so the model is back to <CLI>'s default.` as today. Why: the
  note follows whatever the field holds now, and no effect has to rewrite text another effect
  wrote. Clearing stays where it is (`changed`, the next change of CLI).
- **D2. One note, not two.** With a lost pick and `tookOne`, the window shows the combined note
  and not the separate `tookOne` note: the field's notes stay one line of meaning, as the
  scenario "The field takes the one server model" reads.
- **D3. The `tookOne` sentence is one constant-like expression** used by both notes, so the two
  places cannot drift apart.
- **D4. Test layer: vitest** (`web/src/Launch.test.tsx`), beside "another agent CLI takes the
  field to its default, and says what went", with the existing `onServer`, `cloud` and
  `loginCheck` helpers: the bug is rendering of one component's state; no process is crossed, no
  browser behaviour is needed.
