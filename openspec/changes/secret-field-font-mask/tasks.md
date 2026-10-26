## 1. The dots come from a font

- [x] 1.1 `scripts/secret_dots_font.py` (D1, D2 of `design.md`): a PEP 723 script
  (`dependencies = ["fonttools", "brotli"]`) that writes `web/src/secret-dots.woff2`, the
  font `LadoSecretDots` with one disc glyph and a format 13 `cmap` over U+0020–U+10FFFF
  but the surrogates; its docstring says what the font is, why (Safari takes
  `-webkit-text-security` for a password field, LAD-155) and how to run it (`uv run
  --script scripts/secret_dots_font.py`). Run it and commit the script and the font
  (about 400 bytes). AGENTS.md's `scripts/` line names "the secret field's font".
- [x] 1.2 `tests/ui/test_projects_section.py`, `masked()` (UI e2e: only a browser loads a
  font and computes styles; D5): keeps "no `input[type=password]`" and `type` `text`;
  the field's computed `-webkit-text-security` is `none` and its computed `font-family`
  is `LadoSecretDots`; `document.fonts.check('16px LadoSecretDots')` is true; a canvas
  with `16px LadoSecretDots` measures each code point of `sk_live Пароль 秘密 🔑` at one
  and the same width (scenarios "No password field to save", "Every character is a
  dot"). The docstring names LAD-155 beside LAD-149. Fails before 1.3.
- [x] 1.3 `web/src/styles.css`: `@font-face` for `LadoSecretDots` from
  `./secret-dots.woff2` with `font-display: block` (D3); `.project-edit
  .project-in-secret` sets `font-family: LadoSecretDots` instead of
  `-webkit-text-security: disc`, and `::placeholder` sets `font-family: var(--sans)`
  (D4); the one-line comment says the dots come from a font because Safari offers to save
  a field with `-webkit-text-security` (LAD-155). `web/src/ProjectVariables.tsx`: the
  top comment says "an uncontrolled text field drawn as dots by a font of dots, neither a
  password field nor one styled as such"; the component is otherwise unchanged. 1.2
  passes with `uv run pytest -m ui tests/ui/test_projects_section.py`; the screenshots
  show dots and the placeholder in letters. `make web` (the bundle holds the font
  inlined; no new file under `static/` beyond what Vite emits).
- [x] 1.4 `web/src/ProjectVariables.test.tsx` (vitest): the test of the field's markup
  keeps its checks (type, autocomplete, autocorrect, autocapitalize, spellcheck, the class
  `project-in-secret`, copy and cut refused); add that no element of the Secrets block has
  an inline `-webkit-text-security`, and that the stylesheet (`styles.css?raw`, as
  `tokens.test.ts` reads it) has no `-webkit-text-security` rule left.

## 2. Docs

- [x] 2.1 docs/design/ui.md, "A secret's value": the text field is drawn as dots by the
  font `LadoSecretDots` (`web/src/secret-dots.woff2`, made by
  `scripts/secret_dots_font.py`), not by `-webkit-text-security`: Safari's password
  manager takes a field with that style for a password field and offers to save it
  (LAD-155), as Chrome and Safari do for `type="password"` (LAD-149). No CHANGELOG.md line
  (proposal).

## 3. Regression

- [ ] 3.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui
  tests/ui/test_projects_section.py`, `openspec validate secret-field-font-mask
  --strict`, `openspec validate --specs --strict`; the pull request's CI green. The
  manual check in Safari, Chrome and Firefox with a password manager on stays the human's
  on rc3 (docs/release.md, 4.3).
