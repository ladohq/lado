## 1. The secret's field is no password field

- [x] 1.1 `web/src/ProjectVariables.test.tsx` (vitest: the field's markup and events are
  the component's own, the lowest layer that sees them): `secretField()` finds the field
  by its label within Secrets instead of `input[type=password]`, and the closing checks
  look for that label; a new test opens `+ Add secret` and a row's Replace and checks for
  each that Secrets holds no `input[type=password]`, that the field is `type="text"` with
  `autocomplete="off"`, `autocorrect="off"`, `autocapitalize="off"`, `spellcheck="false"`
  (the supervisor's addition at the design gate) and the masking class, and that `copy` and `cut` events on it are
  default-prevented while the field keeps its value (scenarios "No password field to
  save", "Copy takes nothing out"). Fails before 1.2.
- [x] 1.2 `web/src/ProjectVariables.tsx`: `SecretField` renders `type="text"` with the
  class `project-in-secret` beside `project-in-value`, keeps `autoComplete="off"`,
  `spellCheck={false}`, `data-1p-ignore`, `data-lpignore`, adds `autoCorrect="off"` and
  `autoCapitalize="off"`, and prevents `onCopy` and
  `onCut`; the module's top comment says "an uncontrolled text field masked by CSS, no
  password field (a browser offers to save a password field's value whatever its
  autocomplete)". `web/src/styles.css`, beside `.project-edit .project-in-value`:
  `.project-in-secret { -webkit-text-security: disc; }` with a one-line comment why. 1.1
  passes; `make web`.
- [x] 1.3 `tests/ui/test_projects_section.py`,
  `test_new_project_and_its_variables_and_secrets` (UI e2e: only a browser computes the
  style): find the field by its label (`textbox` `Value` within Secrets, `New value of
  STRIPE_KEY`) instead of `input[type=password]`; after `Add STRIPE_KEY as a secret
  instead` and after Replace opens, `page.locator("input[type=password]")` has count 0,
  the field's `type` is `text`, and its computed `-webkit-text-security` is `disc`; the
  closing checks count the field by its label. Run with
  `uv run pytest -m ui tests/ui/test_projects_section.py`; the screenshots show the dots.

## 2. Docs

- [x] 2.1 docs/design/ui.md, "A secret's value": an uncontrolled `<input type="text"
  autocomplete="off">` masked by `-webkit-text-security: disc`, autocorrect,
  autocapitalize and spellcheck off, copy and cut refused,
  outside any `<form>`; why not `type="password"` (Chrome and Safari offer to save a
  password field whatever its autocomplete, LAD-149). docs/release.md, the manual check of
  Projects in the web UI: "once in Chrome, once in Safari and once in Firefox, each with a
  password manager on", the rest as it is. No CHANGELOG.md line (proposal).

## 3. Regression

- [x] 3.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui
  tests/ui/test_projects_section.py`, `openspec validate secret-field-no-password
  --strict`, `openspec validate --specs --strict`; the pull request's CI green. The manual
  check in Chrome, Safari and Firefox with a password manager stays the human's on rc2.
