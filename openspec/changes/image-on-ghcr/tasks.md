Tests first in each section; each task is one commit. The plan with the code is
`docs/superpowers/plans/2026-10-15-image-on-ghcr.md`.

## 1. LADO's words in a container name no commands

- [x] 1.1 Unit and UI tests (layers 1 and 4): the hint names `ghcr.io/ladohq/lado:<v>`
  (`test_update.py`, `test_doctor.py`), `lado update`'s refusal is the reason alone
  (`test_self_update.py`), `GET /api/update` has `by_hand` empty in a container
  (`test_server_system.py`), the migration's way back names the image of the version
  before (`test_cli.py`); `SystemPanel.test.tsx`'s container case has no `.system-by-hand`
  (H2); `tests/ui/test_system_panel.py`'s container case shows no command (D6).
- [x] 1.2 `update.IMAGE`, `available_line`, `CONTAINER_UPDATE` removed; `cli.cmd_update`,
  `app.update_state`, `runtime._migrate`, `SystemPanel.tsx`; `docs/design/ui.md`. `make
  test`, `make web`, `uv run pytest -m ui tests/ui/test_system_panel.py`.

## 2. The GitHub release names the image

- [x] 2.1 `tests/test_release_notes.py`: the footer's `Docker: \`docker pull
  ghcr.io/ladohq/lado:<version>\`.` for a final and an RC; `release_notes.IMAGE ==
  update.IMAGE`; then `scripts/release_notes.py` (D6). `uv run pytest
  tests/test_release_notes.py -n0`.

## 3. The four agent CLIs in the image

- [x] 3.1 Measure the image's size and a cold `make docker` before (D4).
- [x] 3.2 `tests/test_docker.py`: an ARG per `PINS` provider equal to its pin, each
  installed by its package, no other npm package; `tests/container/test_image.py`: the
  four CLIs `[ok  ]` in `lado doctor` (D3).
- [x] 3.3 `docker/Dockerfile`: the three installs and the header. `uv run pytest
  tests/test_docker.py -n0`, `make docker && make test-container`; measure after and
  compare (D4; over the threshold: stop and tell the supervisor).

## 4. Compose by version, the headers, two LADOs

- [x] 4.1 `tests/test_docker.py`: compose's image line, the update, way back and second
  LADO steps of the header, no `lado:previous` in `docker/`; `docker compose config`
  without a version refuses naming `LADO_VERSION`, with it names the published image,
  `LADO_IMAGE` wins (D5).
- [x] 4.2 `docker/compose.yaml` and the Dockerfile's header (D5).
- [x] 4.3 `tests/container/test_migration.py`: the header's way back by version and the
  failed migration's message, no `lado:previous`; new `tests/container/test_two_lados.py`:
  updating one of two compose projects leaves the other's container, start time and image
  reference (D7). `make docker && make test-container`.

## 5. The Release workflow

- [x] 5.1 `tests/test_release_workflow.py`: jobs `build`, `image` (matrix amd64/arm64 on
  their runners, `uv sync --locked`, one buildx build loaded and pushed by digest before the
  container tests), `pypi` after `build` and `image`, `image-tags` after `pypi` and `image`
  (`imagetools create`, `latest` only by `release_notes.py --flag`, both platforms
  inspected), `github-release` after `image-tags`; only the job token, `packages: write`
  where it pushes; the image's name is `update.IMAGE` (D1, D2).
- [x] 5.2 `.github/workflows/release.yml`; `docs/release.md`'s section "The image" and
  its lines in sections 2 and 5 (D8). `uv run pytest tests/test_release_workflow.py
  tests/test_workflow_security.py -n0`.

## 6. Docs and regression

- [x] 6.1 AGENTS.md (Commands, container tests, Layout: `update.py`, `self_update.py`,
  `state.py`'s way back, `docker/`, the Release workflow) and CHANGELOG.md (0.39.0: the
  LAD-71 item without `lado:previous`; the image on GHCR with four CLIs; compose by
  `LADO_VERSION`; the container hint). `grep -rn "lado:previous\|CONTAINER_UPDATE" src
  docker tests web/src AGENTS.md docs/release.md docs/design/ui.md CHANGELOG.md` prints
  nothing.
- [x] 6.2 Regression: `make lint`, `make test`, `make web`, `uv run pytest -m ui
  tests/ui/test_system_panel.py`, `make docker && make test-container`, `openspec validate
  image-on-ghcr --strict`, `openspec validate --specs --strict`; CI green (`ci-ok`, both
  `container` cells).
- [x] 6.3 The pull request's description has the manual check of
  `docs/superpowers/specs/2026-10-15-image-on-ghcr-design.md` (branch, folder, commands,
  expected results) and the after-merge check at the next RC (package made public,
  `docker pull` on Mac and Linux).

## 7. At archive (integrator)

- [ ] 7.1 After `openspec archive image-on-ghcr`, the Purpose of
  `openspec/specs/container/spec.md` names the update by version tag instead of
  `lado:previous` and `docker compose pull`, and the new `image-release` spec has a
  Purpose (archive leaves a placeholder).
