# LAD-15 readme-update-section: review report

Pull request #3 `fix/lad-15-readme-update` → `main`. Scale: tweak, review depth: precision.
Head reviewed last: `0680432`; the archive commit follows it. Docs only: README.md,
docs/install.md, CHANGELOG.md and the openspec change; no code.

## Rounds

- **Round 1** (`2952259..0680432`): local precision pass over the whole diff, each claim of
  README's and docs/install.md's Update sections checked against the code it describes
  (`self_update.py`, `update.py`, `cli.py`, `doctor.py`, `web/src/SystemPanel.tsx`,
  `server/app.py`), and an external round by the Claude Code Action
  (https://github.com/ladohq/lado/pull/3#issuecomment-6118633362). No blockers, no
  important findings; F1–F4, all minor.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local: precision | docs/install.md says "The web UI does the same" after `lado update X.Y.Z`, as if the UI installed any version; it installs only the latest, and **Update…** shows only when one is out | confirmed | minor | declined: README says it right, in the context of `↑ X.Y.Z` |
| F2 | 1 | local: precision | "Installed otherwise" tells to run the environment's `pip install lado==X.Y.Z`; a uv environment (uv tool from git or a folder, a `uv sync` working copy) has no `pip` | confirmed | minor | declined: the text retells `Plan.by_hand` (`self_update.py`) as it is; the defect is in the code and older than the change, found on the way |
| F3 | 1 | external (Action) | The text does not say a rollback can fail itself (`rollback_failed`) | confirmed | minor | declined: a rare path, and `update.log` is named |
| F4 | 1 | external (Action) | `~/.lado/backups/` and `~/.lado/update.log` ignore `LADO_HOME` | confirmed | minor | declined: right for the default home |

| Source | Confirmed | Refuted | Unverifiable |
|---|---|---|---|
| local | 2 (F1, F2) | 0 | — |
| external, Claude Code Action | 2 (F3, F4) | 0 | — |

No blocker or important finding.

## Found on the way

- `Plan.by_hand` offers `<prefix>/bin/pip`, which a uv environment lacks, so the command
  by hand of `lado update` and the UI fails with "no such file" there
  (`src/lado/self_update.py`, F2). For BACKLOG.md, P2–P3.

## Checks

- On `0680432`: `make lint` clean (178 files), `openspec validate --specs --strict` 2
  passed, 0 failed, `openspec validate readme-update-section --strict` valid; CI green
  (check 3.10/3.13, js, ui, smoke on Linux and macOS for claude, codex, kilo, opencode).
- At archive (`--skip-specs`, no delta): `openspec validate --specs --strict` 2 passed,
  0 failed.

## Residual risk

- No local test run: docs only, CI ran everything green.
- The rendered Markdown and the anchors `#update` and `#installed-otherwise` were checked
  by their headings, not opened on GitHub.
