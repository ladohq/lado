Task: LAD-73

## Why

LADO's image is built only from a checkout (`make docker`, `lado:local`): a user has
nothing to download. And the update of a container rests on one local name,
`lado:previous`, that `docker/compose.yaml`'s header has the human tag before `docker
compose pull`: it is one name per machine, so a second LADO container (`-p lado-2`)
overwrites the first one's (finding G2 of LAD-71). The human plans several LADO containers
on one machine; updating one must not touch another. This is step T7 of the Docker install
plan.

Root cause: the image a container runs is named by a tag that moves (`lado:local`, a
pulled `latest`), so after an update the image before has no name, and LADO had to invent
a machine-wide one. A published image named by its version never moves: the image before
an update always has its name, and GHCR keeps it.

## What Changes

- **The Release workflow publishes LADO's image to GHCR**, `ghcr.io/ladohq/lado:<version>`
  for linux/amd64 and linux/arm64, each built on its architecture's own runner from the
  very wheel the release uploads to PyPI, through the job's `GITHUB_TOKEN` (no new
  secret). Before anything is published (PyPI included), each architecture's image passes
  the container tests; a red one stops the whole release. A release candidate gets only
  its own tag (`:0.39.0rc1`); `latest` names the newest final release only. The plain
  version tag is the image with every agent CLI; images with one agent can come later as
  `:<version>-<agent>`.
- **The image carries all four agent CLIs** (Claude Code, Codex CLI, OpenCode, Kilo CLI)
  at `scripts/smoke_ci.py`'s `PINS`; `lado doctor` in a container finds each `ok`. Codex
  is only installed: carrying its login into the agents is step T15.
- **An update is a version tag, not a kept name.** `docker/compose.yaml` takes
  `ghcr.io/ladohq/lado:${LADO_VERSION}` (required; `LADO_IMAGE` still overrides it, for
  `lado:local` and the tests); its header says: set `LADO_VERSION` in `.env` next to the
  file, update by changing it and `docker compose up -d`, go back by putting the number
  before back (with the migration's backup when the schema moved). A second LADO is a
  folder of its own with its own `.env` (`COMPOSE_PROJECT_NAME`, `LADO_PORT`,
  `LADO_VERSION`, `LADO_PROJECTS`). The Dockerfile's header names the published image and
  `docker run`'s update, way back and second LADO. `lado:previous` is gone everywhere.
- **LADO names no update commands in a container** (the human's decision): `lado update`
  refuses with the reason alone; the line `lado ls` and `lado doctor` print when a newer
  LADO is out reads `LADO 0.41.0 is available: a new image updates LADO in a container
  (ghcr.io/ladohq/lado:0.41.0)`; the System panel's Update block says the version is out
  and why LADO does not update itself, with no `On the host:` commands (`by_hand` empty);
  a failed migration's way back is the image of the version run before. How to update goes
  into the documentation (T8). The stale fixture of `web/src/SystemPanel.test.tsx` (H2 of
  LAD-71) goes with it.
- **The GitHub release's notes** add `docker pull ghcr.io/ladohq/lado:<version>` beside
  `uv tool install`.

## Scope

Changed: `.github/workflows/release.yml` (jobs `build`, `image`, `pypi`, `image-tags`,
`github-release`), `docker/Dockerfile` (the four CLIs, header), `docker/compose.yaml`
(image by version, header), `src/lado/update.py` (`IMAGE`, `available_line`;
`CONTAINER_UPDATE` removed), `src/lado/cli.py` (`cmd_update`'s refusal),
`src/lado/server/app.py` (`update_state`: no `by_hand` in a container),
`src/lado/runtime.py` (`_migrate`'s way back), `scripts/release_notes.py` (the docker
line), `web/src/SystemPanel.tsx` (the dead `On the host:` branch) and its test; tests
`tests/test_release_workflow.py`, `tests/test_docker.py`, `tests/test_release_notes.py`,
`tests/test_update.py`, `tests/test_doctor.py`, `tests/test_self_update.py`,
`tests/test_server_system.py`, `tests/test_cli.py`, `tests/ui/test_system_panel.py`,
`tests/container/test_image.py`, `tests/container/test_migration.py`, a new
`tests/container/test_two_lados.py`; docs `docs/release.md`, `docs/design/ui.md`,
AGENTS.md, CHANGELOG.md. Capabilities: new `image-release`; `container` and
`schema-migration` modified. No schema change, no MCP tool, no CLI option. Version: a
feature, so a minor; 0.39.0 is unreleased and a minor already, so it goes into 0.39.0's
notes with no further bump (its LAD-71 item that names `lado:previous` is rewritten).

## Out of scope

- How to update, go back and run several LADOs in the user documentation
  (`docs/install.md`), and whether and how `compose.yaml` is handed to users (a release
  asset, a link): step T8. The human's decision: LADO's own surfaces name no update
  commands; the documentation will.
- Carrying Codex's login into the agents and checking Codex in the container: step T15.
  The human's decision.
- Images with fewer agents (`:<version>-claude`): only the room in the tag scheme; no
  kit or user asks for one yet.
- Floating tags (`:0.41`, `:0`): nobody uses them; `latest` and the version are enough.
- Signing the image or an SBOM: not asked for; can follow without changing the tags.
- Making the GHCR package public: GitHub creates a new package private, and
  `GITHUB_TOKEN` cannot change its visibility; an org admin does it once by hand after the
  first release candidate (docs/release.md, the PR's manual check).
- A container manager for several LADOs: the human's later plan; this change only makes
  their updates independent.
- `docs/research/docker-install-plan.md`: updated by another session's supervisor.

## Impact

- Users get `docker pull ghcr.io/ladohq/lado:<version>` from the next release candidate
  on, on Mac (arm64) and Linux (amd64, arm64).
- A container's update and way back need no name kept by hand, and two containers never
  share one.
- The image grows by the three CLIs' native binaries (a few hundred MB); the build time is
  measured in the build report.
- The release takes longer: two image builds and the container tests before PyPI.
- Spec: new `image-release`; `container` (update hint, image contents, compose, way back,
  two LADOs) and `schema-migration` (the way back in a container) modified.
