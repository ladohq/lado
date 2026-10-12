# LAD-20 marketplaces-guide: review report

Pull request #7 `fix/lad-20-marketplaces-docs` → `main`. Scale: tweak, review depth:
precision. Head reviewed last: `59e917a`; the archive commit follows it. Docs only:
README.md (`## Marketplaces`), docs/marketplaces.md (new), docs/kits.md section 7, links in
AGENTS.md and docs/design/ui.md, CHANGELOG.md and the openspec change; no code. Each claim
of the guide was checked against the code (`marketplaces.py`, `kits.py`, `gitcache.py`,
`cli.py`), `lado kits add --help` and github.com/ladohq/marketplace's README and workflows.

## Rounds

- **Round 1** (`origin/main...59e917a`): local precision pass over the diff and the change,
  each fact of the guide held against the code: `marketplaces.py` (`NAME`, `KIT_NAME`,
  `INDEX_VERSION`, `add`, `remove`, `index`, `_entry_problem`), `kits.py`
  (`needs_confirmation`, the name check with `-m`), `gitcache.py` (`GIT_TERMINAL_PROMPT=0`,
  `clone_branch`, `refresh`), `cli.py` (a kit's removed marketplace). Nothing found. The
  external round (1 of 1) by the Claude Code Action (request issuecomment-6122269793,
  "Claude finished" at 10:19:28Z): no blocker, F1-F3.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | external (Action) | docs/kits.md section 7, step 3: `lado kits add my-team -m team` uses a marketplace `team` the section no longer introduces | confirmed | minor | declined: section 2 of the same guide adds `team`, and the step links the new guide |
| F2 | 1 | external (Action) | The changed `marketplaces.py` line of AGENTS.md is 101 characters | confirmed | minor | declined: style only; AGENTS.md has many longer lines and no check reads it |
| F3 | 1 | external (Action) | docs/marketplaces.md section 2 could say a branch other than the default is not read | refuted | — | dropped: the text already says LADO reads the default branch (`origin/HEAD` in `gitcache.py`) |

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 0 | 0 | — |
| external, Claude Code Action | 2 (F1, F2) | 1 (F3) | — |

No blocker, no important finding.

## Found on the way

None.

## Checks

- On `59e917a`: `make lint` clean (194 files), `openspec validate marketplaces-guide
  --strict` valid, `openspec validate --specs --strict` 3 passed; CI green, all 12 checks
  (check 3.10/3.13, js, ui, 8 smoke cells).
- At archive (`--skip-specs`, no delta): `openspec validate --specs --strict` 3 passed,
  0 failed.

## Residual risk

- No local test run: docs only, CI ran everything green.
- The official marketplace's SECURITY.md link was not opened; its README, `scripts/` and
  workflows were.
- No change to `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or
  `tests/live/`: no live tests needed.
