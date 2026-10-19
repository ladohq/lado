# LAD-110 image-chromium-libs: review report

Pull request #112 `fix/lad-110-image-chromium-libs` → `main`. Scale: tweak, reviewed for
precision over the whole diff (a Dockerfile layer, a new container test, one CI step,
docs). Head reviewed last: `f34058b` (= the remote head). `providers/`, `hooks.py`,
`mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` are not changed: no live
tests needed.

## Rounds

- **Round 1, local** (`ce4f403..f34058b`, precision; manual reading, spec and AGENTS.md
  check): F1.
- **Round 1, external** (Claude Code GitHub Action, request
  https://github.com/ladohq/lado/pull/112#issuecomment-6268246963 at 13:22:05Z,
  "Claude finished" at 13:23:17Z): E1, nothing blocking.

No second external round: the cap of 1 for a tweak was used. The external reviewer is of
the same model family, so its "nothing blocking" weighs less.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | `test_the_image_carries_no_browser` checks only that `command -v` prints nothing, not its exit code, so a `login` failing for another reason would pass, `tests/container/test_browser.py:64-65` | confirmed | minor | declined: `command -v` prints nothing exactly when the command is missing, and the `login` shell works in the neighbouring test and in `test_toolchains.py`; the external reviewer agreed it is minor |
| E1 | 1 | external | `SHOTS` comes from `tempfile.gettempdir()` while CI's upload path is a fixed `/tmp`; a runner with `TMPDIR` set would drop the screenshot silently (`container.log` always uploads, so `if-no-files-found: warn` stays quiet), `tests/container/test_browser.py:22` | confirmed (hypothetical) | minor | declined: GitHub's runners set no `TMPDIR`, the screenshot uploaded on both architectures (run 39258138223), and `tests/test_ci_workflow.py:240` notes the assumption |

No fixing commit. Confirmed 2 (both minor, declined), refuted 0.

## Spec check

- **The image carries the system libraries of Playwright's Chromium**: `docker/Dockerfile`,
  a layer of its own with the 21 packages, the same list as the spec package for
  package; container `test_playwrights_chromium_finds_its_libraries_and_renders_a_page`:
  Playwright's version from `uv.lock`, `ldd`, Chromium launched, the text read back. The
  screenshot was looked at: Latin and Cyrillic render, no boxes.
- **The image carries no browser**: container `test_the_image_carries_no_browser`.
- Every task of `tasks.md` is checked. D1-D5 are kept; the screenshot goes to
  `/tmp/lado-container-shots`, after `lado-ui-shots`, which the design does not forbid.
- Out of scope kept: no browser, fonts, xvfb or `install-deps` in the change. No second
  source of truth: Playwright's version only from `uv.lock`, no unit copy of the package
  list.
- Existing tests changed for a reason: `tests/test_docker.py:521` picks the first apt
  layer by `tmux`, as there are two now; `tests/test_ci_workflow.py` pins the new Image
  step and the upload paths.

## Checks

- `make lint`: green.
- Unit `tests/test_docker.py`, `tests/test_ci_workflow.py`, `tests/test_agents_md.py`:
  134 passed, 1 skipped. The full `make test` was not run by the reviewer (the build
  report: 3613 passed; green in CI).
- `openspec validate --specs --strict`: 41 passed; `openspec validate image-chromium-libs
  --strict`: valid.
- `tests/container/test_browser.py` collects 2 tests under `container`; not run locally
  (no Docker in the agent's container).
- CI on `f34058b`, run 39259306551: success on all 24 jobs, `container (amd64)`,
  `container (arm64)`, `ui (1/2)`, every smoke cell and `ci-ok` among them.

## Not checked (residual risk)

- **AC-5 / D4, the human's check, not done yet**: `make docker`, a container of
  `lado:local`, in it `make browser`, then `uv run pytest -m ui tests/ui/test_chat.py`.
  The container test proves the headless shell starts and renders a page, but the UI
  suite has not run in the image, while `docs/testing.md`, `docs/install.md` and
  CHANGELOG.md already say `make test-ui` runs in the container. `make browser` also
  installs the full Chromium; Playwright's library list is the same.
- The container tests were not run by the reviewer; they rest on CI's green cells on both
  architectures.
- The image's growth (30.7 MB amd64, 32.4 MB arm64) is taken from the pull request's
  description and the build report; the `docker history` log was not opened.

## Metrics

Rounds: 1 local and 1 external, no surrogates. Local findings: 1 confirmed (minor), 0
refuted; external: 1 confirmed (minor), 0 refuted. Findings in code the developer changed
while cleaning up: 0.
