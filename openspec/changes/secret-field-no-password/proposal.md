Task: LAD-149

## Why

Symptom: on a project's page, Secrets → `+ Add secret` → Name, Value → Add, Chrome (Google
Password Manager) offers "Save password?" with the secret's name as the username and its
value as the password; Safari (Passwords) offers "Save Password?". Nothing else leaks: the
field is empty after Add, the row says `set · hidden`, the value is in neither
`server.log` nor `lado.db`. Found by the manual check of 0.43.0rc1 (docs/release.md, 4.3),
2026-10-25; it blocks the final 0.43.0.

Cause: `SecretField` in `web/src/ProjectVariables.tsx` is an `<input type="password"
autocomplete="off">` outside any `<form>` (LAD-139), next to the text field Name. The
design counted on two things: that no form submission means no save prompt, and that
`autocomplete="off"` keeps password managers away. Chrome and Safari honour neither for a
password field: they ignore `autocomplete="off"` there, and a text field and a password
field that disappear after a request look to them like a sign-in that succeeded. The
Replace field of a secret's row is the same component and gets the same prompt. The
report's note that `-webkit-text-security` already masks the field is not so: no style of
the UI sets it today.

Options weighed:

- A (taken): a text field masked by CSS (`-webkit-text-security: disc`), so the page has
  no password field at all and a password manager has nothing to save; it looks as it does
  now. Chrome, Edge, Safari and Firefox (114 and later) draw the dots. Copy and cut are
  turned off in the field, as a password field has them, so the dots never give the value
  away to the clipboard. Long-term cost: one CSS rule and two handlers; the field loses the
  browser's own protections of a password field beyond the dots (fewer extensions read
  it), which a page that never puts the value in state or storage does not rely on.
- B: an open text field, the value visible while typed: works everywhere, but shows the
  secret on screen, in a screen share and in a screenshot.
- C: a field of our own that draws the dots and keeps the value aside: much code, worse
  with screen readers, paste and input methods, no gain over A.
- Not an option: `autocomplete="new-password"` or more `data-*-ignore` attributes. The
  field stays a password field, so Chrome and Safari still offer to save (Chrome then also
  offers to generate one).

## What Changes

- `SecretField` is an `<input type="text">` with `autocomplete="off"`, the class that
  masks it with `-webkit-text-security: disc`, and copy and cut prevented; everything else
  of the field stays (uncontrolled, outside any form, emptied after a save, on Cancel and
  when it goes, `spellCheck` off).
- The UI's tests find the field by its role and label instead of `input[type=password]`;
  the vitest tests check the field's type and attributes and that copy and cut are
  refused; the UI e2e test checks in Chromium that the page has no password field and
  that the field is masked (its computed `-webkit-text-security` is `disc`).
- docs/design/ui.md ("A secret's value") and the module's comment describe the masked
  text field and why it is no password field; docs/release.md's manual check of Projects
  in the web UI names Firefox beside Chrome and Safari.
- A fix of 0.43.0's own unreleased feature for 0.43.0rc2: no version bump, no new
  CHANGELOG.md line (0.43.0's "Projects in the web UI" already describes it, and no final
  shipped the defect).

## Scope

- The secret's value field of the Add and the Replace forms of the Secrets block.

## Out of scope

- The plain variables' Value field: a variable is no secret and is shown in its row; its
  form is not a password form for any browser (no password field), so nothing changes.
- A test that a real password manager stays silent: no headless browser runs one; it
  stays the human's manual check on the RC (docs/release.md, 4.3).
- Other forms of the UI: none has a password field (`web/src` holds only this one).

## Impact

- Web UI: `web/src/ProjectVariables.tsx`, `web/src/styles.css`.
- Tests: `web/src/ProjectVariables.test.tsx` (vitest), `tests/ui/test_projects_section.py`
  (UI e2e).
- Docs: `docs/design/ui.md`, `docs/release.md`.
- Spec: `projects` (the hidden field's requirement).
