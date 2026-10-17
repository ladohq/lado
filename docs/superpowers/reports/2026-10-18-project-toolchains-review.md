# LAD-93 project-toolchains: review report

Pull request #93 `fix/lad-93-mise-toolchains` → `main`. Scale: tweak, reviewed for
precision and widened in round 1, as the diff changes `src/lado/runtime.py` (the
container paragraph of LADO's instructions) and data on the home volume. Head reviewed
last: `570e878` (= the remote head). `runtime.py` changed: live tests were not run.

## Rounds

- **Round 1, local** (the whole pull request, `3070cb4..5a15d03`): F1, m1, m2.
- **Round 1, external** (Claude Code GitHub Action,
  https://github.com/ladohq/lado/pull/93#issuecomment-6240878314; triage:
  https://github.com/ladohq/lado/pull/93#issuecomment-6240928677): F2, m3, and the same
  point as F1.
- **Round 2, local** (`5a15d03..94bfd8a`, precision): F1 refuted, m1 and m2 resolved
  (https://github.com/ladohq/lado/pull/93#issuecomment-6241101969).
- **Round 3, local** (`94bfd8a..571d87d`, precision, back from the `merge_ok` gate after
  the human's manual check): H2 checked and resolved, no new findings
  (https://github.com/ladohq/lado/pull/93#issuecomment-6242823244).
- **Round 4, local** (`571d87d..570e878`, precision, after the archive `a44ef8b` and the
  merge of `main` `570e878`): the archive moved the change unedited, the living spec
  `container` took the modified requirement whole and the four new ones; the merge's only
  conflict was CHANGELOG.md's 0.41.0 section, both sides kept; nothing from `main` touches
  `docker/`, `runtime.py`, `agent_env.py` or the image's tests. No new findings
  (https://github.com/ladohq/lado/pull/93#issuecomment-6243045144).

No external round after round 1: the cap of 1 was used there.

The external reviewer is of the same model family, so its "nothing blocking" weighs
less.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local probe; external remark 3 | `idiomatic_version_file_enable_tools` in `/etc/mise/config.toml` seemed to have no effect | refuted (round 2) | — | dropped: the probe ran with `-e HOME=/tmp`, a folder the scratch image lacks; without it `.go-version` is read, and the container test of `94bfd8a` fails without the setting |
| F2 | 1 | external remark 1 | when `lado-repos.sh` cannot be written, `MISE_TRUSTED_CONFIG_PATHS` is exported empty | refuted | — | dropped: the image ships `lado-repos.sh` with `/projects` (`docker/Dockerfile:105`) |
| m1 | 1 | local | the manual check retagged the shared `lado:local` | confirmed | minor | fixed in the pull request's description (round 2) |
| m2 | 1 | local | step 6 of the manual check called `docker compose exec … bash -lc` the agent's login shell | confirmed | minor | fixed in the pull request's description (round 2) |
| m3 | 1 | external remark 2 | a nested login shell adds the paths to `PATH` twice | confirmed | minor | declined: harmless (`docker/profile.sh:7`) |
| H2 | 3 | the human's manual check, finding 2 | mise read the `go` line of go.mod: a deprecation `WARN` on every `go` call and Go picked by go.mod over `.go-version` (1.23.12 instead of 1.23.4) | confirmed | important | fixed in `571d87d`; probe on the pinned mise 2026.10.7: `go@1.23.4`, no `WARN`; a go.mod with only `toolchain go1.22.5` gives `go@1.22.5`. Tests: `tests/test_docker.py` (the setting), `tests/container/test_toolchains.py` (go.mod in `other-go`, no `WARN` from `go build` and `go version`) |

Metrics: 4 local rounds, 1 external, 0 substitutes. Local confirmed 2 (minor), refuted 1;
external confirmed 1 (minor), refuted 1; from the human's manual check confirmed 1
(important). Findings in code changed by the developer's cleanup: 0.

## Checks

- CI on `570e878`: run 39078398841 green with `ci-ok` (lint, unit, integration, ui,
  container, smoke); on `571d87d`: run 39077141661, 23/23 green.
- `openspec validate --specs --strict` after the merge of `main`: 34 passed.
- `make lint` and `make test` were not rerun locally in round 4 (the delta was CHANGELOG
  and the archive); CI ran them, and the developer's `make test` after the merge: 3418
  passed.
- The container tests were run by CI and by the developer (6 passed); the reviewer ran
  mise probes on the official image of the same digest.

## Residual risk (not checked)

- Ruby and Java through mise are not covered by container tests (Ruby from a Gemfile was
  probed by the developer).
- `src/lado/runtime.py` changed and live tests were not run; in the human's manual check
  the supervisor (Claude Code) installed Go through mise on its own.

## Found on the way

- An empty `~/.lado/server-token` lets anyone into the UI without a token (not from this
  pull request; the same on `main`): `auth.token()` (`src/lado/server/auth.py:30-40`)
  returns `""` for an empty file and `Guard._valid` (`auth.py:70-71`) accepts an empty
  token. Proposed P1; a tracker task only with the human's yes.
