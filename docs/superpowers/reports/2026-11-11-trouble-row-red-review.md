# LAD-229 trouble-row-red: review report

Pull request #283 `fix/lad-229-trouble-row-red` → `main`. Scale: tweak, depth precision. Head
reviewed: `801b9393`. A row of the session list whose session is in trouble (`tmux session is
gone`, `session loop not running`) now says its trouble in `--danger` after a full `--danger`
dot, the head's, instead of `--muted` after a ring. Screenshots in the light and the dark theme
match `docs/design/ui.md` and the chosen mockup (variant B). Delta: an added requirement of
`session-status-mark`.

## Rounds

1. Local, precision. The whole diff `origin/main...801b9393`, the change's spec against the code
   and tests, every task of `tasks.md` checked (6 of 6), decisions D1–D3 kept, the architecture
   against AGENTS.md, screenshots against `docs/design/ui.md` and the mockup. The change is in
   `web/` only; no provider detail, no second source of truth, no new field. Finding F1.
2. External 1, Claude Code GitHub Action: no blockers; F2 and F3 confirmed (minor), F4 refuted.
   It did not read the openspec files only; the local round did.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | local: the pair `--danger` on `--raised` (a hovered or open row) is not among the contrast pairs of `web/src/tokens.test.ts` | declined: no defect, a coverage gap; computed by hand 5.8:1 (light, #b42318 on #eef0f4) and 7.1:1 (dark, #ff8f85 on #20242c), both above 4.5:1 |
| F2 | minor | external: the UI test's `probe` element is added to `body` and never removed | declined: each test has its own page, thrown away after it |
| F3 | minor | external: the rows item of `docs/design/ui.md` is one long unwrapped line | declined: cosmetic, the line was long before the change |
| F4 | — | external: BACKLOG.md lacks the blank line before the next entry after the removal | refuted: the blank line is there (`BACKLOG.md:1895`); on `main` it was the removed entry that lacked one |

## Found on the way

None.

## Checks

On `801b9393`:
- `uv run pytest -m ui -n0 tests/ui/test_session_list.py -k trouble` 2 passed; `make lint`
  green; `openspec validate trouble-row-red --strict` valid.
- The new test fails on the old CSS (colour `--muted`, a transparent dot with a `solid` border):
  the developer's red run, 2 failed.
- CI of PR #283: `ci-ok` green, all unit, integration, web, UI and container jobs green. Smoke
  skipped: the pull request is within CI's skip list (`web/`, `docs/`, `openspec/`, `tests/ui/`,
  Markdown).

Not run locally: `make test`, `make web` and the whole UI suite; CI ran them, all green.
`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did
not change; no live tests needed.

## Stop

No blockers or important findings, CI green, the pull request's title and description match the
diff.
