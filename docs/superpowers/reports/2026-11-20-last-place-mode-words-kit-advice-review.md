# LAD-287 last-place-mode-words-kit-advice: review report

Pull request #351 `fix/lad-287-new-session-fixes` → `main`. Scale: tweak. Head reviewed:
`77f7f3ef` (the whole pull request, `98ef4bb7..77f7f3ef`). Three fixes of the 0.47.0rc1
manual check: New session's Where keeps the last place after a window closed before the
recent places came (the draft remembers whether its place was chosen); a kit's unmet
expectation advises in words that fit the CLI and the window (no `--kit`); Claude Code's
`auto` mode is named in words, and `manual` is another name of `default` (a provider's mode
aliases, resolved in `runtime` before the session is stored).

## Rounds

1. Local, precision over `98ef4bb7..77f7f3ef`, widened by hand over every place the
   permission mode is stored or checked (`check_new_session`, a resume, `spawn_worker`, the
   resume's change comparison, `lado start --help`, the server's start), as the diff touches
   `runtime.py` and `providers/`. Found F1.
2. External 1, Claude Code GitHub Action (request 2026-11-20T08:02:55Z, finished
   08:03:51Z): read the changed sources; not the tests, docs or openspec, which the local
   round covered. Found E1, E2.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | the change's `design.md` (D5, Risks) describes a local HTTP proxy, while the UI test holds the request with `page.route` | declined: the deviation is recorded in tasks.md 1.2 and the build report |
| E1 | — | a late empty answer of the recent places could move the focus to Folder name in a window with a draft | refuted: `openingFocus` keeps the element `showModal()` focused, so a late answer leaves the focus (LAD-281) |
| E2 | — | the Resume window of a session stored with `manual` has no chosen Permissions row | refuted as a defect of this change: out of scope by the proposal; such a session resumes and is stored as `default` (`test_manual_starts_and_resumes_claude_code_as_default`) |

## Metrics

- Rounds: 1 local, 1 external, 0 stand-ins.
- Confirmed: local 1 (minor), external 0.
- Refuted: external 2.
- Findings in code changed by the developer's cleanup (`resolve_permission_mode`,
  `dd8d56f5`): 0.

## Checks

- At `77f7f3ef`: `make lint` clean; `make test` 6075 passed, 14 skipped; the four new UI
  tests passed; `openspec validate last-place-mode-words-kit-advice --strict` valid; trial
  archive, 89 passed.
- CI of PR #351 at `77f7f3ef`: 27/27, `ci-ok` green.

## Found on the way

- The session's details line `permissions: <mode>` shows the raw value (`auto`).
- `openspec/specs/agent-start-screens/spec.md`, scenario "Another mode", names `manual` as
  the mode a session starts in; it still holds, but the session is now stored as `default`.

## Residual risk

- Live tests with Claude Code were not run: that `--permission-mode default` and `auto`
  really start is covered by unit and smoke tests only.
- The full `make web` and the whole `tests/ui/test_launch.py` ran in CI only, on the same
  head.
- A in Firefox on a slow network, the texts of C in the window and Claude Code's
  Permissions (D) are the 0.48.0 RC's manual check.
