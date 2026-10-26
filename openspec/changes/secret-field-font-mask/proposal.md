Task: LAD-155

## Why

Symptom: on a project's page, Secrets → `+ Add secret` → Name, Value → Add, Safari
(Passwords) still offers "Save Password? Securely store your password in the Passwords
app…" in 0.43.0rc2. Chrome and Firefox offer nothing there since LAD-149. Nothing leaks: the
field is empty after Add, the row says `set · hidden`, the value is in neither
`server.log` nor `lado.db`. Found by the manual check of 0.43.0rc2 (docs/release.md, 4.3,
finding Н-0), 2026-10-26; it blocks the final 0.43.0.

Cause, checked: LAD-149 (change `secret-field-no-password`) made `SecretField` in
`web/src/ProjectVariables.tsx` an `<input type="text">` drawn as dots by
`-webkit-text-security: disc`. Chrome decides that a field holds a password by its
`type` only; Safari's password manager also takes a text field with
`-webkit-text-security` for a password field, and a name field beside it that goes away
after a request reads to it as a sign-in. WebKit's own code decides by `type` alone
(`HTMLInputElement::isSecureField`); the heuristic is in Safari's closed password manager,
so the human checked it on a bench page (four fields, each alone on a page load, each
with a name field and an Add that sends a request and removes the form) in Safari, Chrome
and Firefox on 2026-10-26:

| Field | Safari | Chrome | Firefox |
|---|---|---|---|
| `type="password"` (rc1) | offers | offers | silent |
| `type="text"` + `-webkit-text-security: disc` (rc2) | **offers** | silent | silent |
| `type="text"`, no mask | silent | silent | silent |
| `type="text"` drawn by a font of dots | silent | silent | silent |

The font of dots drew dots, not letters, in all three browsers. Firefox's own password
manager stayed silent even for the password field, so its column proves little.

The Replace field of a secret's row is the same component and has the same cause.

Options weighed:

- A (taken): keep the text field and draw its dots with a font of our own in which every
  character is a dot, instead of `-webkit-text-security`. The page then has neither a
  password field nor a field styled as one, and nothing for any of the three password
  managers to save; it looks as it does now. The font is 380 bytes, made by a script in
  the repository and inlined into the bundle. Long-term cost: one small binary with its
  generator, and a field whose dots depend on the font loading (D3 of `design.md`); a
  screen reader reads the value aloud, as it already does for the rc2 field.
- B: an open text field, the value visible while typed: works everywhere, no code, but
  shows the secret on screen, in a screen share and in a screenshot.
- C: a field of our own that draws the dots and keeps the value aside: much code, worse
  with screen readers, paste and input methods, no gain over A.
- Not an option: `autocomplete` values or `data-*-ignore` attributes: Safari ignores them
  (LAD-149's option list), and any rule built on `-webkit-text-security` is what Safari
  detects.

## What Changes

- `SecretField` keeps everything it has (`type="text"`, `autocomplete="off"`, autocorrect,
  autocapitalize and spellcheck off, copy and cut refused, uncontrolled, outside any form,
  emptied after a save, on Cancel and when it goes) but its class `project-in-secret`
  draws the dots with the font `LadoSecretDots` instead of `-webkit-text-security`; its
  placeholder stays in the UI's font.
- The font `web/src/secret-dots.woff2` and its generator `scripts/secret_dots_font.py`
  (D1, D2 of `design.md`).
- The tests check that no style of the Secrets block sets `-webkit-text-security`, that
  the field uses the font, and in Chromium that the font loaded and draws every kind of
  character as the same dot.
- docs/design/ui.md ("A secret's value"), the module's comment and the CSS comment say
  why the dots come from a font and not from `-webkit-text-security` (Safari, LAD-155).
- A fix of 0.43.0's own unreleased feature for 0.43.0rc3: no version bump (patch nor
  minor), no new CHANGELOG.md line (0.43.0's "Projects in the web UI" already describes it,
  and no final shipped the defect).

## Scope

- The secret's value field of the Add and the Replace forms of the Secrets block.

## Out of scope

- The plain variables' Value field: a variable is no secret and is shown in its row;
  Safari did not offer to save an unmasked text field (bench, row 3).
- A test that a real password manager stays silent: no headless browser runs one; it
  stays the human's manual check on the RC (docs/release.md, 4.3), now with Safari's
  result the deciding one.
- Masking in the terminal (`lado project set --secret` asks without echo already).
- Other forms of the UI: none has a masked field (`web/src` holds only this one).

## Impact

- Web UI: `web/src/ProjectVariables.tsx` (comment), `web/src/styles.css`, new
  `web/src/secret-dots.woff2`.
- Tooling: new `scripts/secret_dots_font.py` (its own inline dependencies, none added to
  the project).
- Tests: `web/src/ProjectVariables.test.tsx` (vitest), `tests/ui/test_projects_section.py`
  (UI e2e).
- Docs: `docs/design/ui.md`, AGENTS.md (the `scripts/` line names the font's generator);
  docs/release.md unchanged (it already names Chrome, Safari and Firefox).
- Spec: `projects` (the hidden field's requirement).
