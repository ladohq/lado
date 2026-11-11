# LAD-267 tab-row-keeps-tab-in-view: review report

Pull request #289 `hotfix/lad-267-tab-row-keeps-tab-in-view` → `main`. Scale: hotfix, depth
precision. Head reviewed: `a7f079c4`. The flaky UI test
`test_tab_brings_each_tab_clear_of_the_bars_ends` had its cause in the product: when the
session's scrolled tabs changed width at the same level (the font arriving late under load),
the row kept its scroll and the tab reached by the keyboard went under the fade. Now the
level's trial keeps the keyboard's tab, else the shown one, clear (`keepTabInView`). Delta: an
added requirement of `session-layout`.

## Rounds

1. Local, precision. The whole diff `b448dd28..a7f079c4`, the spec against the code and tests,
   every task of `tasks.md` checked (7 of 7), decisions D1–D4 kept, the architecture against
   AGENTS.md. Finding F1.
2. External 1, Claude Code GitHub Action: no blockers; F3 confirmed (minor), F2 refuted, its
   note 1 merged into F1. It did not read the openspec files only; the local round did.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | a row scrolled aside by hand comes back to the kept tab on any change of the tabs' widths, a counter changing too, not only a resize or the font | declined: the cost of option 1, which the human chose |
| F2 | — | external: `test_wider_tabs_keep_the_tab_shown_clear` guards against a hollow pass only by `scrollWidth > before` | refuted: that assert fails loudly when the style changes nothing |
| F3 | minor | external: the levels test uses the literal `56` instead of `TAB_ROOM` | declined: the same file checks the fade's width with the same literal, which catches a drift |

## Found on the way

None.

## Checks

On `a7f079c4`:
- `uv run pytest -m ui tests/ui/test_narrow_layout.py tests/ui/test_tabs.py -n auto` 45
  passed; `make lint` green; `openspec validate tab-row-keeps-tab-in-view --strict` valid.
- CI: `ci-ok` pass; smoke skipped by the skip list (only `web/`, `tests/ui/`, `docs/`,
  `openspec/` and CHANGELOG changed).
- Under load (the developer's build report): 144 of 144 green, no retries.

Not checked by the reviewer: the red run before the fix (read-only role; the developer reports
both new tests failed without it), and the run under load was not repeated.
