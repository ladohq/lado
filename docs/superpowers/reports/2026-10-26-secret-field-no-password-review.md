# LAD-149 secret-field-no-password: review report

Pull request #173 `hotfix/lad-149-secret-field` → `main`. Scale: hotfix, reviewed for
precision (the diff touches no business logic or user data). Head reviewed last:
`c6d8b2cb` (= the remote head), base `9d41c16c`. The secret's value field of the Add and
Replace forms is a text field masked by `-webkit-text-security: disc` with copy and cut
refused, so the page holds no password field for Chrome's or Safari's password manager
to save; vitest and UI e2e tests, docs/design/ui.md, docs/release.md (Firefox in the
manual check). `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py`
and `tests/live/` unchanged: no live tests needed. Schema migration: no.

## Rounds

- **Round 1** (`origin/main..c6d8b2cb`, commits 4be19722, 3209e046, c6d8b2cb): a local
  precision pass, a check against the `projects` delta and the architecture against
  AGENTS.md. The supervisor's point checked: `autoCorrect="off"`, `autoCapitalize="off"`
  and `spellCheck={false}` are on `SecretField`, the one component of Replace and Add,
  and vitest checks both forms. **External 1** (Claude Code GitHub Action, request at
  20:49:18Z, "Claude finished" at 20:51:16Z): read every changed code, test and docs
  file but the openspec texts; two minor findings.

External rounds used: 1 of 1. The external reviewer is of the same model family, so its
"nothing blocking" weighs less.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | dragging the selected value out of the field is not refused, which gets round the copy/cut ban | not testable (no real drag-and-drop in Chromium) | minor | declined: the spec and the human's decision ask for copy and cut; the one who drags is the one who typed it; residual risk |
| F2 | 1 | local | a screen reader may read the value of a CSS-masked text field (it says "dot" for a password field) | not testable without a screen reader | — | residual risk, the cost of option A the human chose |
| F3 | 1 | external 1 | the manual check in docs/release.md does not ask that Firefox draw the value as dots | confirmed | minor | declined: to be looked at in the manual check of rc2 |
| F4 | 1 | external 1 | the changed paragraph of docs/release.md is not rewrapped | confirmed | minor | declined: cosmetic |

## Checked against the spec

The requirement "A secret's value is typed into a hidden field emptied after use" and
its scenarios "No password field to save" and "Copy takes nothing out" are covered:
vitest (type, attributes, class, copy and cut prevented, value kept; Add and Replace),
UI e2e (no `input[type=password]`, `type=text`, computed `-webkit-text-security: disc`
in Add and Replace). Every task of `tasks.md` checked; nothing out of scope; no
CHANGELOG line and no version bump, as the design says.

## Checks

`npx vitest run src/ProjectVariables.test.tsx` 13 passed; `openspec validate
secret-field-no-password --strict` valid; `openspec validate --specs --strict` 49
passed; CI on `c6d8b2cb` `ci-ok` success (smoke skipped: the diff is within ci.yml's
skip list). A flake in CI on 3209e046 (`ui (1)`, `src/Launch.test.tsx`), outside this
diff.

## Not checked

Real password managers in Chrome, Safari and Firefox, and the masking in Firefox: the
human's manual check on rc2. A screen reader (F2) and drag-and-drop (F1).
