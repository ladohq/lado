# LAD-142 projects-docs-built: review report

Pull request #161 `fix/lad-142-projects-docs-built` → `main`. Scale: tweak, reviewed for
precision. Head reviewed last: `6ba078b9` (= the remote head), base `c0bf2518`. Text only
(ROADMAP.md, AGENTS.md, `docs/design/projects.md`, `docs/design/ui.md`, `docs/install.md`,
CHANGELOG.md, the openspec change); no code, and `providers/`, `hooks.py`,
`mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` unchanged, so no live
tests are needed before the merge. Schema migration: no.

## Rounds

- **Round 1** (`c0bf2518..6ba078b9`, the whole pull request): a local precision pass with
  the check against the change's spec, and **external 1** (Claude Code GitHub Action,
  comment 6376052737): E1, E2. The external reviewer read every document of the diff and
  `state.py`, `self_update.py`, `projects.py`, `doctor.py`, `project_secrets.py`; not the
  openspec change's files (not risky, read locally).

External rounds used: 1 of 1. The external reviewer is of the same model family, so its
"nothing blocking" weighs less.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | the box "What is built" of `docs/design/projects.md` says all of the file is built in 0.43.0 but Not now, while The architectural frame and "Later, facts about a repository…" describe the future outside Not now | confirmed | minor | declined: those parts call themselves future ("will", "not made now", "Later"); no built claim about a thing that is not |
| E1 | 1 | external 1 | `docs/install.md`: the comment of the pip line does not say that `pip install` leaves `backups/` alone | confirmed | minor | declined: copying the backup aside is harmless on every path; no other 0.42.x on PyPI |
| E2 | 1 | external 1 | `docs/install.md` does not forbid other `lado` commands between `lado update 0.42.0` and the restore | refuted | — | 0.42.0 on schema 35 only raises `SchemaError` and writes nothing (`src/lado/state.py:1215-1220`) |

## Checked against the spec

AC-1 to AC-7 hold: the grep of the brief finds only `docs/design/ui.md:442` (the
placeholder rule, not about projects); ROADMAP ticks Projects and S1-S7b as in the epic
plan's Results; AGENTS.md has 195 lines; the going-back paragraph matches the code
(schema 35, the refusal's text, the backup name, `_back_up` deleting other backups,
`projects.check_new`'s refusals, doctor's "your own folder") and was run literally by the
epic's lead; the CHANGELOG item is under `## 0.43.0 (unreleased)`, `### Improved`.

## Checks

`make lint` 0; `tests/test_agents_md.py` 3 passed; `openspec validate projects-docs-built
--strict` valid, `--specs --strict` 47 passed; CI 15 success, smoke skipped (docs only),
`ci-ok` pass. The developer's `make test`: 4235 passed, 2 skipped.

## Not checked

A real `lado update 0.42.0` from the PyPI release of 0.43.0 (the lead's run used the
branch's wheel); the pipx path.
