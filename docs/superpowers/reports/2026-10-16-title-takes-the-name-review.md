# LAD-84 title-takes-the-name: review report

Pull request #83 `fix/lad-84-title-tab` → `main`. Scale: tweak, reviewed for precision
(only the web UI's title field changed: no business logic or data). Head reviewed:
`4ad904b` (= the remote head). No change to `providers/`, `hooks.py`, `mcp_server.py`,
`runtime.py`, `agent_env.py` or `tests/live/`: no live tests needed.

## Rounds

- **Round 1, local** (precision and the spec over `0585e92..61324dc`): F1. The rule
  `suggests` (`TitleEdit.tsx`) offers the rest of the name only when the text is a proper
  case-sensitive start of the name (the empty text included), the caret is at the end,
  nothing is selected, nothing is being saved and no IME composition runs; Tab or →
  without modifiers take it, a key with `isComposing` is not taken. The hints come from
  `Sessions.tsx` word for word as the spec says.
- **Round 1, external** (Claude Code GitHub Action, request 09:40:46Z, "Claude finished"
  09:41:58Z): E1, E2, E3, no blockers.
- **Delta `61324dc..4ad904b`** (the fix of F1 and a vitest test "Esc after Tab sends
  nothing", asked by the supervisor): a precision pass found nothing new.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (reading) | The line `setText(session.name)` in `onKeyDown` of `TitleEdit.tsx` had an extra indent (no formatter runs over `web/`) | confirmed | minor | fixed in `4ad904b` (indent only) |
| E1 | ext 1 | external | The grey layer follows the `selection` state and may lag a moment after ← | confirmed as an observation | — | declined: the keys read the live selection (`currentTarget.selectionStart`); the lag is visual only and not seen |
| E2 | ext 1 | external | The `scrolled` flag relies on a `scroll` event when scrollLeft returns to 0 | refuted | — | declined: browsers fire `scroll` on an input at any scrollLeft change; the reviewer itself said no change is needed |
| E3 | ext 1 | external | An empty field during IME or saving shows the placeholder, only the hint switches | refuted | — | declined: the spec keeps the name as the native placeholder of an empty field, as before |

Blockers: 0. Important: 0.

## Checked

- Every scenario of the spec has a test: Tab in an empty field (unit and the head's UI
  e2e), a start of the name in a row (unit and the list's UI e2e), other text, `LA` and
  the whole name (unit; `zz` then Tab leaves and saves in UI e2e), → inside the text
  (unit), a session with a title (unit).
- Every task of `tasks.md` checked; D1–D5 kept. The grey rest has `opacity: 0.75` as in
  the approved mockup, within D2 (no new colours or tokens).
- The screenshots `shot-row-rest.png` and `shot-head-taken.png` match
  `docs/design/ui.md` and the mockup: the grey rest stands right at the caret.
- Architecture: web UI only; the name comes from `SessionInfo.name` (one source of
  truth); no new API fields; tests at the lowest fitting layer. `Layout.test.tsx` now
  checks both hints of the head, as the spec asks.
- Locally on `61324dc`: `npx vitest run TitleEdit Layout` 85 passed, `tsc --noEmit`
  clean; `openspec validate title-takes-the-name --strict` valid,
  `openspec validate --specs --strict` 32 passed. The grep of `openspec/specs/` found no
  contradiction.
- CI on `4ad904b` (run 38882248130): `ci-ok` passed; smoke skipped by rule (the pull
  request is within ci.yml's skip list).

## Not checked (residual risk)

- UI e2e, `make test` and `make lint` were not run by the reviewer: the developer
  (`make web` 841 passed, the head's and list's UI e2e 17 passed, `make test` 3360
  passed, lint green) and CI on `4ad904b` ran them.
- Behaviour in Firefox and Safari (`onSelect`, the caret after a programmatic value
  change) is checked only in Chromium and jsdom.
- The pull request's description names 840 vitest tests and not the test of `4ad904b`:
  a stale number, not a mismatch with the diff.

Found on the way: nothing.
