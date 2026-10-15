# LAD-73 image-on-ghcr: review report

Pull request #61 `feature/lad-73-image-on-ghcr` → `main`. Scale: full, reviewed for
breadth first, at most two external rounds. Head reviewed last: `edde5b5` (= the remote
head; merge base `cfc1b7e`); the archive commit follows it. `providers/`, `hooks.py`,
`mcp_server.py`, `agent_env.py` and `tests/live/` did not change; `runtime.py` got only the
text of the way back after a failed migration, so live tests are not needed before the
merge.

## Rounds

- **Round 1, local** (breadth over `cfc1b7e..edde5b5`: spec, tests, silent failures,
  comments and descriptions, general; no new types; the architecture against AGENTS.md:
  nothing leaks above `providers/`, the image's name is one, `update.IMAGE`, tested against
  the workflow, compose and `release_notes.py`, no silent drop), against the deltas of
  `container`, `image-release`, `schema-migration` and `tasks.md`: F1.
- **Round 1, external** (Claude Code GitHub Action, request 14:01:08 UTC, answer
  "Claude finished" 14:01:26 UTC, on `edde5b5`): E1–E5. The answer is posted on the pull
  request (issuecomment-6193961044). The external reviewer is of the same model family, so
  its "nothing blocking" weighs less.

External rounds used: 1 of 2.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local (spec) | the requirement "The compose file publishes one port number" says `LADO_IMAGE` replaces `ghcr.io/ladohq/lado:${LADO_VERSION}`, but Compose v2 asks for `LADO_VERSION` also when `LADO_IMAGE` is set | confirmed | minor | declined: only the spec's text; the compose header and the tests (`tests/container/conftest.py`, `test_two_lados.py`) say and do so; only `LADO_IMAGE` users (developers, tests) meet it |
| E1 | ext. 1 | external | buildx with two outputs (`type=docker` and a push by digest) and default provenance may make an index `type=docker` cannot export | unverifiable | — | residual risk: passed locally (buildx 0.36, containerd store); the runner's daemon is seen only at the first RC; cheap guard `--provenance=false`; a red `image` cell publishes nothing |
| E2 | ext. 1 | external | a failed `image` cell leaves an untagged digest in the package; document it | refuted | — | dropped: docs/release.md, section 8, says so |
| E3 | ext. 1 | external | compose's `:?` message should say `LADO_VERSION` is needed with `LADO_IMAGE` too | confirmed (= F1) | minor | declined with F1 |
| E4 | ext. 1 | external | `image-tags` decides `latest` by a string comparison in shell | confirmed | minor | declined: `release_notes.flag` prints only `--latest` or `--prerelease` today; hypothetical robustness |
| E5 | ext. 1 | external | the pins are written in three places | refuted | — | dropped: the workflow builds without `--build-arg`, so the `ARG` defaults are the one source, checked against `PINS` by `tests/test_docker.py` |

## Checks

- `make lint`: green. `make test`: 3214 passed.
- `openspec validate --specs --strict`: 27 passed; `openspec validate image-on-ghcr
  --strict`: valid.
- CI on `edde5b5` (run 38747001733): success, `ci-ok` green, both `container` cells
  (amd64, arm64) and the smoke on Linux and macOS for the four providers green.
- Not run by the reviewer: the container tests (CI on both architectures; the developer
  locally, 22 passed, 0 skipped), UI e2e and `make web` (CI green; the `web/` change is one
  line of `SystemPanel.tsx` and a vitest fixture), the integration tests as a whole (CI).
- The screenshot `screenshot-container-update.png` matches `docs/design/ui.md` (the
  container's update block with no command and no button).

## Metrics

- Rounds: 1 local, 1 external, 0 substitute.
- Local findings: 1 confirmed (minor), 0 refuted.
- External findings: 2 confirmed (minor; one the same as F1), 2 refuted, 1 unverifiable.
- Findings in code the developer's cleanup lens changed: 0 (it changed nothing).

## Residual risk (not checked)

1. The Release workflow's new jobs (`image`, `pypi` without checkout, `image-tags`,
   `github-release` after `image-tags`) never ran; the first run is the next RC. Their
   shape is pinned by `tests/test_release_workflow.py`.
2. E1: buildx's two outputs with `push=true` on the runner's daemon.
3. A rerun of a failed `image` cell (`gh run rerun --failed`) uploads the artifact
   `container-<arch>` again under the same name; how upload-artifact takes that is not
   checked.
4. The GHCR package is private after its first publication; an organisation admin makes it
   public once (docs/release.md, section 8); until then the RC notes' `docker pull` fails.

## Found on the way

Nothing outside the task.
