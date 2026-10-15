# LADO's image on GHCR, updated by its version tag (LAD-73)

Change: `openspec/changes/image-on-ghcr/` (proposal, delta specs, `design.md` with the
decisions D1-D9). This document is the human's view: what a user gets and does, what is
accepted, and how the human checks it.

## What a user gets

From the next release candidate on, every release has an image beside its PyPI package:

```
docker pull ghcr.io/ladohq/lado:0.39.0rc1     # a release candidate: only its own tag
docker pull ghcr.io/ladohq/lado:0.39.0        # a final: also :latest
```

for linux/amd64 and linux/arm64 (Docker Desktop on an Apple Silicon Mac runs arm64). The
image holds LADO from the very wheel on PyPI and the four agent CLIs at the versions LADO
is tested with: Claude Code, Codex CLI, OpenCode, Kilo CLI (Codex installed only; its login
in the agents is step T15). The GitHub release's notes name the `docker pull` line.

## Running, updating, going back

`docker run` needs no file:

```
docker run -d --name lado -p 127.0.0.1:8765:8765 -v lado-home:/home/lado \
  -v "$HOME/projects:$HOME/projects" -e LADO_REPOS="$HOME/projects" \
  ghcr.io/ladohq/lado:0.39.0
```

- Update: `docker rm -f lado`, the same command with the new version. The home volume
  stays; the new LADO migrates `lado.db` after a backup (LAD-71).
- Back: the same with the old version (and the backup put back when the schema moved:
  the compose header's steps, or by hand on the volume).
- A second LADO: another `--name`, volume and port.

`docker/compose.yaml` keeps the same settings in a file: an `.env` next to it with
`LADO_VERSION`, `LADO_PROJECTS` (and `LADO_PORT`). Update: a new `LADO_VERSION`, then
`docker compose up -d`. Back: the old number. A second LADO: a second folder with a copy
of the file and its own `.env` (`COMPOSE_PROJECT_NAME=lado-2`, `LADO_PORT=8766`, …).

In both ways the image before an update keeps its version's name, locally and on GHCR, so
nothing has to be kept by hand: `lado:previous` is gone. Two LADOs never share a name, so
updating one leaves the other as it is.

Which way the documentation leads with, and how a user gets `compose.yaml`, is step T8.

## What LADO says in a container

The human's decision: LADO's own surfaces name no update commands; the documentation will.

| Where | Today | After |
|---|---|---|
| `lado update` | refusal + `on the host: docker tag … lado:previous && docker compose pull && docker compose up -d` | `lado: LADO runs in a container: a new image updates it, not lado update` |
| `lado ls`, `lado doctor` | `LADO 0.41.0 is available: docker tag …` | `LADO 0.41.0 is available: a new image updates LADO in a container (ghcr.io/ladohq/lado:0.41.0)` |
| System panel, Update block | version, What's new, reason, `On the host:` + command + Copy | version, What's new, reason (mockup `task/lad-73/mockup-container-update.html`, option 1) |
| A failed migration | `… keep as lado:previous: LADO_IMAGE=lado:previous docker compose up -d` | `To go back, run the image of the LADO version you ran before (ghcr.io/ladohq/lado:<that version>) on the same home volume.` |

## Acceptance criteria

- AC-1: A release tag (RC or final) publishes `ghcr.io/ladohq/lado:<version>` for amd64 and
  arm64 from the wheel uploaded to PyPI, with `GITHUB_TOKEN` only.
- AC-2: Each architecture's image passes the container tests before anything is
  published; a red one publishes nothing (no PyPI, no image tag, no GitHub release); the
  tagged image is the tested one.
- AC-3: `latest` moves only with a final; an RC gets only its own tag; the plain version
  tag is the image with all agents.
- AC-4: The image carries Claude Code, Codex CLI, OpenCode and Kilo CLI at `PINS`;
  `lado doctor` in the container reports each `ok` on both architectures.
- AC-5: `docker/compose.yaml` takes `ghcr.io/ladohq/lado:${LADO_VERSION}`, refuses without
  a version (unless `LADO_IMAGE`), never defaults to `latest`; its header and the
  Dockerfile's say how to update, go back and run a second LADO by version, and nothing
  names `lado:previous`.
- AC-6: Two LADO containers on one machine update independently: updating one leaves the
  other's container, image and image reference as they were.
- AC-7: In a container `lado update`, `lado ls`, `lado doctor`, the System panel and a
  failed migration name no update command; the hint names the image of the new version.
- AC-8: The GitHub release's notes hold `docker pull ghcr.io/ladohq/lado:<version>`.
- AC-9: `web/src/SystemPanel.test.tsx` has no stale container fixture (H2).
- AC-10: `docs/release.md` describes the image's jobs, tags, failures and the one-time
  public visibility.

## Questions for the human (answered 2026-10-15)

1. Hint in a container: version, What's new and the reason, no commands (option 1). Yes.
2. Compose needs `LADO_VERSION`, no `latest` default. Yes.
3. Tags: version (all agents), `latest` final only, RC its own tag, variants as
   `<version>-<agent>` later. Yes.
4. A red image test stops the whole release, PyPI too. Yes.
5. The GitHub release notes name `docker pull`. Yes.
6. Several LADOs: a folder (or `docker run` name) per LADO. Yes; `docker run` is the
   primary way, compose optional; publishing `compose.yaml` is T8's.

## Version

A feature: a minor. 0.39.0 is unreleased and a minor already; the items go into its notes.

## Manual check (goes into the pull request)

From the pull request's branch `feature/lad-73-image-on-ghcr`, in the repository's root
(`~/Projects/lado` or a fresh clone), Docker Desktop running:

1. `git fetch origin && git switch feature/lad-73-image-on-ghcr && make docker` — builds
   `lado:local`. Then `docker run --rm lado:local sh -lc 'claude --version; codex
   --version; opencode --version; kilo --version'` prints the four `PINS` versions.
2. Two LADOs: `mkdir -p /tmp/lado-a /tmp/lado-b ~/projects-lado-check`; copy
   `docker/compose.yaml` into both; `/tmp/lado-a/.env`: `LADO_IMAGE=lado:local`,
   `LADO_PROJECTS=$HOME/projects-lado-check` (the full path written out),
   `COMPOSE_PROJECT_NAME=lado-check-a`, `LADO_PORT=8791`; `/tmp/lado-b/.env` the same with
   `-b` and `8792`. `docker compose up -d` in each; both `http://127.0.0.1:8791/api/health`
   and `:8792` answer.
3. `docker tag lado:local lado:check-new`; in `/tmp/lado-a/.env` set
   `LADO_IMAGE=lado:check-new`; `docker compose up -d` there. Expected: `docker ps` shows
   `lado-check-a-lado-1` on `lado:check-new` and `lado-check-b-lado-1` still on
   `lado:local` with its old "Up" time; both health URLs answer.
4. `docker compose exec lado lado doctor` in `/tmp/lado-a`: no `[FAIL]`, the four CLIs
   `[ok  ]`, `in a container`.
5. Without `LADO_IMAGE` and `LADO_VERSION` in an `.env`: `docker compose config` refuses
   and names `LADO_VERSION`.
6. Clean up only what this made: `docker compose down -v` in both folders,
   `docker image rm lado:check-new`, `rm -rf /tmp/lado-a /tmp/lado-b ~/projects-lado-check`.

After the merge, at the next release candidate (it is the first run of the new jobs):
the Release run is green; an org admin makes the package `ghcr.io/ladohq/lado` public
(GitHub, the organisation's Packages, `lado`, Package settings, Change visibility); then
`docker pull ghcr.io/ladohq/lado:<rc>` works without login on the Mac and on Linux, a
container from it answers in the UI, and its `lado doctor` sees all four CLIs.
