## Context

The Release workflow (`.github/workflows/release.yml`) has two jobs: `pypi` (the tag's
checks, `make dist`, the artifact `dist`, `uv publish`) and `github-release` (after PyPI,
`gh release create` with the same files). CI's job `container` builds `docker/Dockerfile`
from the run's wheel on `ubuntu-24.04` and `ubuntu-24.04-arm` and runs the container tests
with `scripts/smoke_ci.py container` (a skip is red); it pushes nothing. The image installs
Claude Code alone (`ARG CLAUDE_VERSION`, kept equal to `PINS["claude"]` by
`tests/test_docker.py`). LAD-71 made `docker/compose.yaml`'s header keep the running image
as `lado:previous` before `docker compose pull`, because the pull moves the image's name
and Docker's containerd store then removes the old image; `update.CONTAINER_UPDATE` repeats
that command for `lado ls`, `lado doctor`, `lado update`'s refusal and the System panel.

Facts checked for this design: Docker Compose (v5.4) expands the nested default
`${LADO_IMAGE:-ghcr.io/ladohq/lado:${LADO_VERSION:?...}}`, refuses with the message when
neither is set, and does not ask for `LADO_VERSION` when `LADO_IMAGE` is set;
`COMPOSE_PROJECT_NAME` in a folder's `.env` overrides the file's `name: lado`. Each of the
three new CLIs ships its Linux binary per architecture as an npm optional dependency, as
Claude Code does (`@openai/codex`, `opencode-ai`, `@kilocode/cli`, each with
`linux-x64` and `linux-arm64` packages).

Options for the root cause (an image named by a moving tag):

1. **Version tags (chosen).** The published image is named by its version and compose
   needs the version; an update changes the number. The image before always has its name
   and GHCR keeps it, so the way back needs nothing kept by hand, and two containers share
   no name. Long-term cost: the human writes a number once per update (the documentation,
   T8, says where); no state of LADO's.
2. **A per-project kept name** (`lado-<project>:previous`). Fixes G2 only, keeps the
   manual tag step and a local-only name that `docker image prune` loses. Rejected.
3. **`latest` by default, the version optional.** Simplest first start, but after a pull
   the image before is nameless again (the case LAD-71 had to patch). Rejected.

Against AGENTS.md's principles: one source of truth (the image's name is one constant,
`update.IMAGE`, that the workflow and compose are tested against; the CLIs' versions are
`PINS`); neutral core (all four providers in the image; Codex only installed, said in the
CHANGELOG); no silent drops (compose refuses without a version instead of taking
`latest`); only what is used (no floating tags but `latest`, no variant images yet). Against
ROADMAP's coming stages: T8 (documentation, compose delivery) builds on the version scheme,
the container manager gets independent containers.

## Decisions

**D1. Jobs of the Release workflow.** In order:
- `build`: what `pypi` does today up to the artifact (the version check, `release_check.py`,
  `check_telemetry.py`, `release_notes.py`, `make dist`, upload `dist`); it publishes
  nothing.
- `image` (needs `build`): a matrix `amd64` on `ubuntu-24.04`, `arm64` on
  `ubuntu-24.04-arm` (CI's runners), `fail-fast: true` (one red cell stops the release
  either way). Downloads `dist`,
  builds the image (D2), runs `uv run python scripts/smoke_ci.py container
  "$RUNNER_TEMP/container"` with `LADO_TEST_IMAGE` set to the loaded image, uploads the
  evidence as `container-<arch>` (`if: always()`), and outputs its digest. `permissions:
  contents: read, packages: write`.
- `pypi` (needs `build`, `image`): downloads `dist`, `uv publish` (environment `pypi`,
  `id-token: write`), as today.
- `image-tags` (needs `pypi`, `image`): `docker buildx imagetools create` of the two
  digests as `ghcr.io/ladohq/lado:<version>`, plus `:latest` when
  `python3 scripts/release_notes.py --flag "$GITHUB_REF_NAME"` is `--latest`; then
  `imagetools inspect` checks both platforms are listed. `packages: write`.
- `github-release` (needs `image-tags`): as today, the notes with the docker line (D6).

A red `image` cell stops everything before PyPI. A failure after PyPI (`image-tags`,
`github-release`) is rerun alone with `gh run rerun <id> --failed`, the digests coming from
the `image` jobs' outputs of the same run. The image's name in the workflow is the literal
`ghcr.io/ladohq/lado`, checked equal to `update.IMAGE` by a unit test.

**D2. The tested bytes are the pushed bytes.** Each `image` cell builds once with buildx
(a `docker-container` builder made with `docker buildx create --use`, no third-party
action) and two outputs of the same build: `type=docker` (loaded as a local name for the
tests) and `type=image,name=ghcr.io/ladohq/lado,push-by-digest=true,name-canonical=true,push=true`
(pushed untagged; its digest from `--metadata-file`). The push happens before the tests,
but an untagged digest is not published: no one can pull it by a name, and only digests
whose cell passed reach `image-tags`. Labels by `--label`:
`org.opencontainers.image.source=https://github.com/ladohq/lado` (links the package to the
repository, so the job token may push to it) and `org.opencontainers.image.version`. The
login is `docker login ghcr.io -u "$GITHUB_ACTOR" --password-stdin` from
`${{ github.token }}`, no login action. If buildx cannot give both outputs from one build on
the runner, the fallback keeps the rule: load and test, then push the loaded image by
digest with a tool that pushes an image by its content (the developer names it in the
build report); never a second build.

**D3. The four CLIs in the Dockerfile.** One `ARG <CLI>_VERSION` per provider
(`CLAUDE_VERSION`, `CODEX_VERSION`, `OPENCODE_VERSION`, `KILO_VERSION`), its default the
pin; one `RUN npm install -g --prefix /opt/agents "<package>@${..._VERSION}" && npm cache
clean --force` per CLI, so a moved pin rebuilds one layer. `tests/test_docker.py`: every
provider of `PINS` has its ARG equal to its version and its install of `PINS`' package;
no npm package is installed that `PINS` does not name. The container test
`test_lado_doctor_is_clean_in_the_container` expects `[ok  ]` for each of the four.
Nothing else per CLI: LADO configures each agent's update check, config and home itself
(providers/); their state (Codex's `~/.codex`, OpenCode's and Kilo's XDG folders) lives on
the home volume.

**D4. The cost of the three CLIs is measured.** The developer measures, before and after
D3, the image's size (`docker image inspect -f '{{.Size}}'`) and a cold `make docker`, and
reads CI's `container` job duration on the pull request against main's; the build report
gives the numbers. When the job grows by more than 5 minutes, or the container tests turn
flaky because of the CLIs, the developer stops and tells the supervisor: per the human's
instruction the three CLIs then move to a task of their own right after this one.

**D5. Compose and the headers.** `image: ${LADO_IMAGE:-ghcr.io/ladohq/lado:${LADO_VERSION:?set
LADO_VERSION to the LADO version to run, e.g. in .env next to this file}}`. The header:
keep `LADO_VERSION`, `LADO_PROJECTS` (and `LADO_PORT`) in `.env` next to the file; start;
update = a new `LADO_VERSION` in `.env`, then `docker compose up -d` (compose pulls an image
it does not have); back after a migration = the version before in `.env`, `docker compose
down`, `docker compose run --rm lado sh -c 'cd ~/.lado && rm -f lado.db-wal lado.db-shm &&
cp backups/lado.db.schema-<N> lado.db'`, `docker compose up -d` (after a failed migration
the first and last only); a second LADO = another folder with a copy of the file and an
`.env` with `COMPOSE_PROJECT_NAME`, `LADO_PORT`, `LADO_VERSION`, `LADO_PROJECTS`. The
Dockerfile's header names `ghcr.io/ladohq/lado:<version>` in its `docker run`, and in a few
lines the update (`docker rm -f lado`, the same `docker run` with the new tag on the same
volume), the way back (the same with the old tag) and a second LADO (another `--name`,
volume and port). `lado:previous`, `PREVIOUS`, `keep_previous` go;
`tests/test_docker.py` parses the new steps by their headings as before.

**D6. LADO's own words in a container name no commands** (the human's decision). Remove
`update.CONTAINER_UPDATE`; add `update.IMAGE = "ghcr.io/ladohq/lado"`.
`available_line`: `LADO {v} is available: a new image updates LADO in a container
({IMAGE}:{v})`. `cli.cmd_update`: in a container raises `LadoError(refused.why)`.
`server/app.py`'s `update_state`: in a container `by_hand = []`.
`runtime._migrate`: `run the image of the LADO version you ran before
({IMAGE}:<that version>) on the same home volume`. `web/src/SystemPanel.tsx`: the
`info.container ? "On the host:" : "By hand:"` choice goes (only `By hand:` is left), and
the container test of `SystemPanel.test.tsx` checks the block has no `.system-by-hand`
(H2 of LAD-71). `scripts/release_notes.py`'s footer adds a paragraph `Docker: \`docker pull
ghcr.io/ladohq/lado:<version>\`` for both kinds; it is standard library only, so it holds
the image's name as its own literal, which a unit test keeps equal to `update.IMAGE`.

**D7. Two LADOs, tested in the container layer.** A new
`tests/container/test_two_lados.py`: two compose projects in two temporary folders, each a
copy of `docker/compose.yaml` with its own `.env` (the run's prefix as
`COMPOSE_PROJECT_NAME`, a free `LADO_PORT`, `LADO_IMAGE` a tag of the run's prefix on the
image under test, `LADO_PROJECTS`), both up; the first's `.env` gets a second tag of the
run's prefix (`docker tag` of the image under test: same image, another reference) and
`docker compose up -d` there; then the first container runs the second reference, the
second container has the same id and `StartedAt` as before and the first reference, and
both answer `/api/health`. Tags and projects are named with the run's prefix and removed by
finalizers (never a prune).

**D8. The release document.** `docs/release.md` gets a section "The image": the jobs and
their order, the tags, what a red `image` cell means (nothing published; fix, delete the
tag, tag again, as for the release check) and a failure after PyPI (rerun the failed job),
and the one-time step after the first release candidate: an org admin makes the package
`ghcr.io/ladohq/lado` public in its settings (GitHub creates it private, and the job token
cannot change that), then checks `docker pull` without login.

**D9. Tests per layer.** Unit (layer 1): the workflow's jobs, needs, permissions, matrix,
the tags and `latest` rule, no secret but the token (`tests/test_release_workflow.py`); the
Dockerfile's CLIs vs `PINS`, compose's image and header steps (`tests/test_docker.py`);
the notes' docker line (`tests/test_release_notes.py`); the hint, the refusal, the API's
`by_hand`, the migration message (`test_update.py`, `test_doctor.py`, `test_self_update.py`,
`test_cli.py`, `test_server_system.py`); vitest for the panel. UI e2e (layer 4):
`tests/ui/test_system_panel.py`'s container case shows no command. Container (layer 7):
the four CLIs `ok`, the header's way back by version, two LADOs. The release workflow
itself runs only on a tag: its first run is the next release candidate, the human's check
after the merge (proposal, Impact). No integration test: nothing crosses LADO's processes
anew.
