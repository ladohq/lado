# LAD-89 optional-secrets-folder: review report

Pull request #86 `fix/lad-89-optional-secrets` → `main`. Scale: tweak, reviewed for
precision; in round 1 the whole diff was read, because the change touches the user's
guide (start, update, the way back) and commit `e7e89a9` arrived mid-round. Head reviewed
last: `6438c43`. `src/lado/agent_env.py` changed, so live tests before the merge were the
human's call.

## Rounds

- **Round 1, local** (`origin/main...e7e89a9`; lenses spec, tests, silent failures,
  comments/descriptions, general and the architecture against AGENTS.md; types skipped,
  no new types): L1 (important), L2 and L3 (minor).
- **Round 1, external** (Claude Code GitHub Action, request 14:02:05Z, "Claude
  finished"; it read the diff and documents, ran no tests): E1-E6. Triage:
  https://github.com/ladohq/lado/pull/86#issuecomment-6217209361
- **Round 2, local** (precision over `e7e89a9..6438c43`, only design.md, proposal.md and
  the PR body changed): L1 and L2 resolved, no new findings.

External rounds used: 1 of 1 (tweak).

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| L1 | 1 | local (comments, spec) | after `e7e89a9` the PR description, design D4 and the proposal described the update without `cp compose.yaml compose.yaml.bak` and without "each LADO in its own folder" | confirmed (`git grep compose.yaml.bak` found it only in spec.md) | important | fixed in `6438c43` and the PR description |
| L2 | 1 | local (comments) | step 3 of the check by hand promised a doctor line but gave no command, and had no `cp … .bak` | confirmed | minor | fixed in the PR description |
| L3 | 1 | local (style) | `docs/design/agents.md:44`, `docs/design/modules.md:939,965` not rewrapped after the edit | confirmed | minor | declined: these files had long lines before, no rule broken |
| E1 | ext 1 | external | rolling back to 0.39.0 with the new compose.yaml warns "not a folder" about `/dev/null` at `/run/secrets` | refuted: 0.39.0 has no `LADO_ENV_DIR`, the bind is ignored | — | dropped |
| E2 | ext 1 | external | `null_device` calls stat on `os.devnull` needlessly | refuted: reached only after `NotADirectoryError` | — | dropped |
| E3 | ext 1 | external | the `[info]` hint also shows for `docker run` without `-v` | refuted: intended (D3) | — | dropped |
| E4 | ext 1 | external | an empty `LADO_SECRETS=` falls back to `/dev/null` | confirmed | minor | declined: intended, the same pattern as `${LADO_SSH_AGENT:-/dev/null}` |
| E5 | ext 1 | external | repeating the update block after a success overwrites `.bak` | confirmed | minor | declined: needs a repeat of a finished update; `cp -n` differs between BSD and GNU |
| E6 | ext 1 | external | a `LADO_IMAGE` pinned in `.env` survives the update | refuted as a defect | minor | declined: by the header `LADO_IMAGE` is for `lado:local` and tests |

Metrics: 2 local rounds, 1 external, 0 substitutes. Local confirmed 3 (1 important, 2
minor), refuted 0; external confirmed 2 (minor), refuted 4 as defects. Findings in code
changed by the developer's cleanup: 0.

## Checks

- Local on the reviewed heads: `make lint` green, 696 unit tests of the touched files
  passed, `openspec validate --specs --strict` valid (33 passed).
- CI on `6438c43` (run 38912919145): 23 jobs success, `ci-ok` pass.
- The human's check by hand on macOS, Docker Desktop 29.8.2, Compose v5.5.1, image built
  from `6438c43`: start without `secrets/` up to the UI and Claude Code's login link,
  doctor `[info] … /run/secrets: none` and no warning; secrets by one `.env` line, an
  OpenCode agent's `gh api user` answered with the login; update from 0.39.0's
  compose.yaml and `.env` by the guide's step, same volume, session resumed; a missing
  `LADO_SECRETS` folder refused by Docker and not created. Notes, not blocking: the
  expected diff of step 3 also holds large header comment changes; right after
  `up -d` `lado ls` shows `(tmux session is gone)` until the resume a few seconds later.

## Residual risk (not checked)

- The download `curl …/releases/download/v<version>/compose.yaml`: only the address was
  checked, no release of this version exists yet.
- Full `make test` was run by CI only.
- Live tests after the change of `src/lado/agent_env.py` were not run.
