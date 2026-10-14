# LAD-67 selection-actions: review report

Pull request #52 `feature/lad-67-selection-actions` → `main`. Scale: full, reviewed for
breadth first, at most two external rounds. Head reviewed last: `4778aa9` (= the remote
head); the archive commit follows it. Only the web UI changed: `providers/`, `hooks.py`,
`mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not, so live tests
are not needed before the merge.

## Rounds

- **Round 1, local** (breadth over `origin/main..3f8e174`: spec, tests, silent failures,
  comments, general; types skipped, no new data types): F1–F5.
- **Round 2, local** (precision over `3f8e174..d40efb1`) and **round 1, external**
  (Claude Code GitHub Action, request 22:31:51Z, answer 22:32:53Z, on `d40efb1`; it read
  the delta and `SelectionBar.tsx`, `quote.ts` and the CSS, not the whole pull request):
  F6, F7, E1.
- **Round 3, local** (precision over `d40efb1..4778aa9`: the merge of main `6bbc159` and
  the fix of F6): F8. The pull request's changed lines were byte for byte the same against
  the new base as against the old one, plus the resolved CHANGELOG, so no second external
  round was asked for. The external reviewer is of the same model family, so its "nothing
  blocking" weighs less.

External rounds used: 1 of 2.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (general, probe in Chromium) | a triple click on a message's last paragraph (or a one-line message) showed no bar: Chrome ends the selection at the start of the next block, another area | confirmed | important | fixed in `78f9fe9`, with an e2e test (two cases) and a vitest, both seen red |
| F2 | 1 | local (spec) | Copy code showed on hover anywhere over the message, against the spec | confirmed | important | fixed in `78f9fe9`, e2e `test_copy_buttons_show_on_hover` |
| F3 | 1 | local (comments) | two comments away from their code (`ChatText.tsx`, `styles.css`) | confirmed | minor | fixed in `78f9fe9` |
| F4 | 1 | local (silent failures) | in a stopped session Quote puts the quote into the disabled composer with no word why | confirmed | minor | declined: a stopped session takes no messages, Copy works, the spec does not name the case; the human approved the merge without it |
| F5 | 1 | local (tests) | no e2e test of Quote from Needs you | confirmed | minor | declined: not a scenario of the spec; covered by vitest `quotes.test.ts` and the Flows e2e test |
| F6 | 2 | local (comments) | the change's documents still said both ends of a selection must be in one area | confirmed | minor | fixed in `4778aa9`: design.md D1, the design doc, the plan and the delta (scenario "A triple click on a message's last line") |
| F7 | 2 | process (CI) | the pull request conflicted with main (CHANGELOG), so CI did not run on `d40efb1` | confirmed | blocker | fixed in `6bbc159` (merge of `origin/main` `1c9bc18`, both groups of lines under 0.39.0) |
| E1 | ext. 1 | external | `look()` resets "Copied" on every `selectionchange` | refuted | — | dropped: a new selection is a new bar |
| F8 | 3 | local (comments) | one requirement line of the delta not wrapped after F6 | confirmed | minor | declined: Markdown cosmetics only |

## Checks

- On `4778aa9`: CI of PR #52 green, every job and `ci-ok` (unit 3.10/3.13, integration in
  six shards, UI in two shards, js, container amd64/arm64); the smoke skipped by CI's rule
  (`web/`, `docs/`, `openspec/`, `tests/ui/` only). `openspec validate --specs --strict`
  0, `openspec validate selection-actions --strict` valid.
- On `d40efb1`: `make lint` 0, `make web` 762 vitest passed, UI e2e 41 passed.
- The developer: `make test` 3172 passed, the whole UI e2e 141 passed.

## Not checked (residual risk)

- The external reviewer read only the delta and the key files, not the whole pull request.
- `preventDefault` on the bar's buttons is not proven on its own: Chromium does not drop
  the selection on a press of a `user-select: none` button anyway.
- A keyboard selection (Shift and the arrows) has no e2e test.
- `make test-smoke` and `make test-live` were not run: only the web UI changed.

## Found on the way

- None.
