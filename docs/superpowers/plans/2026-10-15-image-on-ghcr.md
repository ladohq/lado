# LADO's image on GHCR Implementation Plan

**Goal:** Every release publishes `ghcr.io/ladohq/lado:<version>` (amd64, arm64, all four
agent CLIs), tested before anything is published; containers update by version tag, with
no `lado:previous` and no update commands in LADO's own surfaces.

**Architecture:** The Release workflow gains a `build` job (the checks and `dist`), an
`image` matrix (build once per architecture, container tests, push untagged by digest),
`pypi` after both, `image-tags` (the multi-arch tag, `latest` for a final) and
`github-release` last. The Dockerfile installs the four CLIs of `PINS`; compose takes
`ghcr.io/ladohq/lado:${LADO_VERSION}`; `update.IMAGE` is the one name of the image in code.

**Tech Stack:** GitHub Actions, Docker buildx, Docker Compose, Python (pytest, PyYAML),
React (vitest), Playwright.

**Spec:** `openspec/changes/image-on-ghcr/` (proposal, `design.md` D1-D9, delta specs
`image-release`, `container`, `schema-migration`) and
`docs/superpowers/specs/2026-10-15-image-on-ghcr-design.md` (AC-1..AC-10, manual check).

## Global Constraints

- The image's name: `ghcr.io/ladohq/lado`, in code only as `update.IMAGE`; the workflow,
  `docker/compose.yaml` and `scripts/release_notes.py` (standard library only) hold it as a
  literal that a unit test compares with `update.IMAGE`.
- Image tag = the git tag without `v` (PEP 440: `0.39.0rc1`); `latest` only when
  `scripts/release_notes.py --flag <tag>` prints `--latest`.
- No secret but `${{ github.token }}`; no new third-party action (login by `docker login
  --password-stdin`, builder by `docker buildx create --use`); every `uses:` stays pinned
  by SHA with `# vX.Y.Z` (`tests/test_workflow_security.py`).
- The CLIs: exactly `scripts/smoke_ci.py`'s `PINS` (package, version), one `ARG
  <NAME>_VERSION` each: `CLAUDE_VERSION`, `CODEX_VERSION`, `OPENCODE_VERSION`,
  `KILO_VERSION`.
- Texts, verbatim:
  - refusal: `LADO runs in a container: a new image updates it, not lado update`
  - hint: `LADO {v} is available: a new image updates LADO in a container (ghcr.io/ladohq/lado:{v})`
  - migration's way back in a container: `run the image of the LADO version you ran before
    (ghcr.io/ladohq/lado:<that version>) on the same home volume`
  - notes: a paragraph `Docker: \`docker pull ghcr.io/ladohq/lado:{version}\`.`
- `lado:previous` appears nowhere in `src/`, `docker/`, `tests/`, `web/src/`, AGENTS.md,
  `docs/release.md`, `docs/design/ui.md` after this change (the archived changes and
  reports keep their history).
- Only the test run's own containers, volumes and image tags, by name, are removed; never
  `docker system prune` or `docker volume prune`.
- Don't touch `docs/research/docker-install-plan.md`.
- Commit messages: a plain English sentence ending in `(LAD-73)`.

## Review Focus

- A `.env` that sets `LADO_IMAGE` and `LADO_VERSION` both: `LADO_IMAGE` wins (the tests' and
  `make docker`'s case) — pinned in Task 4 by `docker compose config`.
- A red `image` cell: `pypi`, `image-tags` and `github-release` must all `needs` it
  (directly or through another job) — pinned in Task 5.
- A release candidate must never move `latest` — Task 5 pins the flag check in the
  `image-tags` step.
- The container tests on the release runner need the host's `lado.state` (`old_home`), so
  the `image` job runs `uv sync --locked` before them — Task 5 checks the step.
- A provider added to `PINS` without the Dockerfile — Task 3's test names it.

---

### Task 1: LADO's words in a container name no commands

**Files:**
- Modify: `src/lado/update.py` (remove `CONTAINER_UPDATE`, add `IMAGE`, `available_line`)
- Modify: `src/lado/cli.py:571-572` (`cmd_update`'s container refusal)
- Modify: `src/lado/server/app.py` (`update_state`: no `by_hand` in a container)
- Modify: `src/lado/runtime.py:910-914` (`_migrate`'s way back)
- Modify: `web/src/SystemPanel.tsx` (`UpdateBlock`: only `By hand:`)
- Test: `tests/test_update.py`, `tests/test_doctor.py`, `tests/test_self_update.py`,
  `tests/test_server_system.py`, `tests/test_cli.py`, `web/src/SystemPanel.test.tsx`,
  `tests/ui/test_system_panel.py`
- Docs: `docs/design/ui.md` (lines ~92 and ~1483)

**Interfaces:**
- Produces: `update.IMAGE: str = "ghcr.io/ladohq/lado"` (Tasks 2, 4, 5 compare with it).

- [ ] **Step 1: Write the failing tests.** Replace the `lado:previous` expectations:

```python
# tests/test_update.py (the in-container hint test, today line ~194)
assert update.available_line(checked) == (
    "LADO 99.0.0 is available: a new image updates LADO in a container "
    "(ghcr.io/ladohq/lado:99.0.0)"
)

# tests/test_self_update.py (~170): the CLI's refusal is the reason alone
assert err.strip() == "lado: LADO runs in a container: a new image updates it, not lado update"
assert "docker" not in err and "lado:previous" not in err

# tests/test_server_system.py (~186): by_hand is empty in a container
assert body["by_hand"] == []
assert body["why_not"] == "LADO runs in a container: a new image updates it, not lado update"

# tests/test_cli.py (~1880): the migration's way back in a container
assert (
    "To go back, run the image of the LADO version you ran before "
    "(ghcr.io/ladohq/lado:<that version>) on the same home volume."
) in err
assert "lado:previous" not in err
```

`tests/test_doctor.py` (~308): the hint `LADO 0.39.0 is available: a new image updates
LADO in a container (ghcr.io/ladohq/lado:0.39.0)`.

`web/src/SystemPanel.test.tsx` (the container test, ~363-389; H2): the fixture has
`by_hand: []`, and the test asserts
`expect(block.querySelector(".system-by-hand")).toBeNull()` and no `Copy commands` button,
keeping the pill, the reason and no `Update…`.

`tests/ui/test_system_panel.py` (~157): the container case asserts the Update block shows
the version and the reason and has no `On the host:` text and no `.system-by-hand`.

- [ ] **Step 2: Run them, expect failures.**
`uv run pytest tests/test_update.py tests/test_doctor.py tests/test_self_update.py tests/test_server_system.py tests/test_cli.py -n auto`
and `cd web && npx vitest run src/SystemPanel.test.tsx`: FAIL on the old texts.

- [ ] **Step 3: Implement.**

```python
# src/lado/update.py, in place of CONTAINER_UPDATE
# LADO's published image (the Release workflow pushes it, docker/compose.yaml pulls it):
# a container is updated by running the image of a newer version.
IMAGE = "ghcr.io/ladohq/lado"

def available_line(checked: Check | None) -> str | None:
    """`LADO X is available: lado update` when the check found a newer release; in a
    container the image of that version, no command (the documentation has them)."""
    if checked is None or checked.available is None:
        return None
    if in_container():
        return (
            f"LADO {checked.available} is available: a new image updates LADO in a "
            f"container ({IMAGE}:{checked.available})"
        )
    return f"LADO {checked.available} is available: lado update"
```

`cli.cmd_update`: `if refused and refused.kind == self_update.CONTAINER: raise
runtime.LadoError(refused.why)` (or fold it into the `!= NO_INSTALLER` branch).
`app.update_state`: drop the `CONTAINER` branch, so `by_hand` stays `[]` there.
`runtime._migrate`'s `way_back` in a container: `f"run the image of the LADO version you
ran before ({update.IMAGE}:<that version>) on the same home volume"`.
`SystemPanel.tsx`: `<span>By hand:</span>` without the `info.container` choice.
`docs/design/ui.md`: `by_hand` "empty in a container"; the container paragraph: the block
says why and shows no commands (LAD-73, mockup `task/lad-73/mockup-container-update.html`,
option 1).

- [ ] **Step 4: Run them, expect PASS**, plus `uv run pytest -m ui tests/ui/test_system_panel.py`
and `make web` (no API model changed, the stale-types check stays green).

- [ ] **Step 5: Commit** `LADO names no update command in a container, only the image of the new version (LAD-73)`.

### Task 2: The GitHub release names the image

**Files:**
- Modify: `scripts/release_notes.py` (`_footer`, an `IMAGE` literal)
- Test: `tests/test_release_notes.py`

**Interfaces:**
- Consumes: `update.IMAGE` (test only).

- [ ] **Step 1: Failing tests.**

```python
def test_the_footer_names_the_image_of_the_version():
    final = release_notes.notes("v0.37.0", CHANGELOG)
    assert "Docker: `docker pull ghcr.io/ladohq/lado:0.37.0`." in final
    rc = release_notes.notes("v0.38.0rc2", CHANGELOG)
    assert "Docker: `docker pull ghcr.io/ladohq/lado:0.38.0rc2`." in rc

def test_the_notes_name_lados_image():
    from lado import update
    assert release_notes.IMAGE == update.IMAGE
```

(`CHANGELOG` is the fixture text the file's other tests use.)

- [ ] **Step 2: Run** `uv run pytest tests/test_release_notes.py -n0`: FAIL.
- [ ] **Step 3: Implement.** `IMAGE = "ghcr.io/ladohq/lado"  # update.IMAGE; this script
  imports nothing of lado`; `_footer` returns
  `f"{update}, or install it with \`uv tool install lado=={version}\`.\n\nDocker: \`docker pull {IMAGE}:{version}\`.\n\nPyPI: ...\n"`.
- [ ] **Step 4: Run** again: PASS; `python3 scripts/release_notes.py v0.38.0` still exits 0
  on the repository's CHANGELOG (or its newest section's tag).
- [ ] **Step 5: Commit** `The GitHub release's notes name the release's Docker image (LAD-73)`.

### Task 3: The image carries the four agent CLIs

**Files:**
- Modify: `docker/Dockerfile` (ARGs, one install per CLI, header comment)
- Test: `tests/test_docker.py`, `tests/container/test_image.py`

- [ ] **Step 0: Measure before** (D4): `docker image rm lado:local` (only that tag), `time
  make docker`, `docker image inspect -f '{{.Size}}' lado:local`; note both for the build
  report.

- [ ] **Step 1: Failing unit tests** (replace `test_claude_codes_default_is_its_pin`,
  `test_claude_code_is_installed_at_that_version`, `test_no_other_agent_cli`):

```python
ARGS = {"claude": "CLAUDE_VERSION", "codex": "CODEX_VERSION",
        "opencode": "OPENCODE_VERSION", "kilo": "KILO_VERSION"}

def test_every_provider_of_pins_has_its_build_argument():
    assert set(ARGS) == set(_pins()), f"PINS {sorted(_pins())}, Dockerfile {sorted(ARGS)}"

@pytest.mark.parametrize("provider", sorted(ARGS))
def test_each_clis_default_is_its_pin(provider):
    name = ARGS[provider]
    [arg] = [line for line in lines() if line.startswith(f"ARG {name}=")]
    pinned = _pins()[provider][1]
    assert arg == f"ARG {name}={pinned}", f"Dockerfile {arg}, PINS {pinned}"

@pytest.mark.parametrize("provider", sorted(ARGS))
def test_each_cli_is_installed_at_that_version(provider):
    package = _pins()[provider][0]
    installs = [line for line in lines() if "npm install -g" in line]
    assert any(f'"{package}@${{{ARGS[provider]}}}"' in line for line in installs), installs

def test_no_other_npm_package_is_installed():
    packages = {pin[0] for pin in _pins().values()}
    for line in lines():
        if "npm install -g" in line:
            named = re.findall(r'"(@?[^"@]+)@\$\{', line)
            assert set(named) <= packages, line
```

Container test (`tests/container/test_image.py::test_lado_doctor_is_clean_in_the_container`):

```python
    for cli in ("Claude Code", "Codex CLI", "OpenCode", "Kilo CLI"):
        assert any(line.startswith(f"[ok  ] {cli}:") for line in printed), doctor.stdout
```

(Use the provider titles `lado doctor` prints; check them in `doctor.py`.)

- [ ] **Step 2: Run** `uv run pytest tests/test_docker.py -n0`: FAIL.
- [ ] **Step 3: Implement** in `docker/Dockerfile`, after Claude Code's block:

```dockerfile
# The agent CLIs at the versions LADO is tested with (scripts/smoke_ci.py's PINS;
# tests/test_docker.py keeps them the same), one layer each, so a moved pin rebuilds one.
# Each is a native binary its npm package puts in place. LADO switches their update
# checks off per agent; Codex is installed only (its login: a later step).
ARG CODEX_VERSION=0.162.0
RUN npm install -g --prefix /opt/agents "@openai/codex@${CODEX_VERSION}" \
 && npm cache clean --force
ARG OPENCODE_VERSION=1.18.35
RUN npm install -g --prefix /opt/agents "opencode-ai@${OPENCODE_VERSION}" \
 && npm cache clean --force
ARG KILO_VERSION=7.8.8
RUN npm install -g --prefix /opt/agents "@kilocode/cli@${KILO_VERSION}" \
 && npm cache clean --force
```

The header: "Claude Code at its pin" → "the four agent CLIs at their pins"; "nothing
publishes it yet" → "the Release workflow publishes it as ghcr.io/ladohq/lado:<version>"
(the run/update lines are Task 4's).

- [ ] **Step 4: Run** `uv run pytest tests/test_docker.py -n0` (PASS), `make docker`, then
  `docker run --rm lado:local sh -lc 'claude --version; codex --version; opencode --version; kilo --version'`
  prints the four pins, and `make test-container` (all pass, no skip). Measure after (Step
  0's commands) and compare (D4: stop and tell the supervisor when CI's container job grows
  by more than 5 minutes or the tests turn flaky).
- [ ] **Step 5: Commit** `LADO's image carries Codex CLI, OpenCode and Kilo CLI at their pins too (LAD-73)`.

### Task 4: Compose and the headers update by version; two LADOs are independent

**Files:**
- Modify: `docker/compose.yaml` (image, header), `docker/Dockerfile` (header's run, update,
  way back, second LADO)
- Test: `tests/test_docker.py` (header steps), `tests/container/test_migration.py` (way back),
  Create: `tests/container/test_two_lados.py`
- Modify: `tests/container/conftest.py` only if a fixture for a compose project in its own
  folder is shared (D7)

**Interfaces:**
- Consumes: `update.IMAGE`.
- Produces: header headings the tests parse: `To update`, `Back to the version you had
  before`, `A second LADO`.

- [ ] **Step 1: Failing unit tests** (remove `PREVIOUS`, `keep_previous`,
  `test_the_compose_header_keeps_a_name_for_the_image_before_an_update`,
  `test_lados_own_update_hint_is_the_compose_headers_update`,
  `test_the_compose_header_says_to_keep_lado_image_after_going_back`):

```python
def test_compose_runs_the_published_image_of_lado_version(compose):
    assert compose["services"]["lado"]["image"] == (
        f"${{LADO_IMAGE:-{update.IMAGE}:${{LADO_VERSION:?set LADO_VERSION to the LADO "
        "version to run, e.g. in .env next to this file}}}"
    )

def test_an_update_is_a_new_version_and_up():
    assert header_steps("To update") == ["docker compose up -d"]
    header = " ".join(l.lstrip("#").strip() for l in COMPOSE_TEXT.splitlines())
    assert "LADO_VERSION" in header and "lado:previous" not in header

def test_the_compose_header_says_how_to_go_back_to_the_backup():
    down, restore, up = way_back()   # header_steps("Back to the version you had before")
    assert down == "docker compose down"
    assert restore.startswith("docker compose run --rm lado sh -c '")
    assert "rm -f lado.db-wal lado.db-shm" in restore
    assert "cp backups/lado.db.schema-<N> lado.db" in restore
    assert up == "docker compose up -d"

def test_a_second_lado_is_a_folder_with_its_own_env():
    header = " ".join(l.lstrip("#").strip() for l in COMPOSE_TEXT.splitlines())
    for name in ("COMPOSE_PROJECT_NAME", "LADO_PORT", "LADO_VERSION", "LADO_PROJECTS"):
        assert name in header

def test_nothing_names_lado_previous():
    for path in (DOCKER / "compose.yaml", DOCKER / "Dockerfile"):
        assert "lado:previous" not in path.read_text(), path
```

A test with real compose (skips when `docker compose` is missing, like the container
tests; put it under `tests/container/` with marker `container` if it needs Docker):
`docker compose -f docker/compose.yaml config` in an env with `LADO_PROJECTS` only fails
naming `LADO_VERSION`; with `LADO_VERSION=0.39.0` names `ghcr.io/ladohq/lado:0.39.0`; with
both `LADO_IMAGE=x:y` and `LADO_VERSION` names `x:y`.

- [ ] **Step 2: Run** `uv run pytest tests/test_docker.py -n0`: FAIL.

- [ ] **Step 3: Implement** compose's image line as in the test and the header (D5),
  replacing the `-p lado-2` and `lado:previous` paragraphs. Shape:

```yaml
# Keep the settings in .env next to this file (compose reads it):
#
#   LADO_VERSION=0.39.0                 # the LADO version to run
#   LADO_PROJECTS=/Users/me/projects    # absolute: the container sees it at this path
#   LADO_PORT=8765                      # optional
#
#   docker compose up -d                # from this folder
#   docker compose exec lado lado ui --no-open               # the UI's link with its token
#
# LADO_IMAGE, when set, runs another image instead (lado:local, which `make docker` builds).
#
# To update, set the new LADO_VERSION in .env, then (compose pulls that version's image):
#
#   docker compose up -d
#
# A new version upgrades the home volume's lado.db at its start, after a copy of it in
# ~/.lado/backups/lado.db.schema-<N>, N its schema before (`docker compose logs lado`
# names it); an older one refuses the upgraded lado.db. The version before keeps its image
# and its name. Back to the version you had before: put it back in .env, then (when a
# migration failed, lado.db is as it was, and the first and the last command do it):
#
#   docker compose down
#   docker compose run --rm lado sh -c 'cd ~/.lado && rm -f lado.db-wal lado.db-shm && cp backups/lado.db.schema-<N> lado.db'
#   docker compose up -d
#
# A second LADO beside the first: a folder of its own with a copy of this file and an .env
# with its own COMPOSE_PROJECT_NAME (lado-2), LADO_PORT (8766), LADO_VERSION and
# LADO_PROJECTS. It has its own container, home volume and version: updating one leaves
# the other as it is.
```

Check `header_steps`' rule (the lines after the paragraph that says the heading, up to the
next empty line) against this text and keep each step block preceded by its heading
sentence.

The Dockerfile's header: the `docker run` with `ghcr.io/ladohq/lado:<version>`, then:
"Update: `docker rm -f lado`, then the same `docker run` with the new version (the home
volume stays). Back: the same with the version before (lado.db's backup: compose.yaml's
header). A second LADO: another --name, volume and port."

Container test (`tests/container/test_migration.py::test_the_compose_headers_steps_put_the_backup_back`):
run `way_back()`'s steps with the compose fixture's env (`LADO_IMAGE` the image under test
stands for "the version before"); no `docker tag`, no `PREVIOUS`; assert the schema before
and the container's image. `test_a_migration_that_fails_is_one_message_in_docker_logs`:
the message names `ghcr.io/ladohq/lado:<that version>` and the same home volume, no
`lado:previous`.

`tests/container/test_two_lados.py` (D7):

```python
"""Two LADO containers on one machine update independently (openspec capability
container): each a compose project in its own folder with its own .env."""

def test_updating_one_lado_leaves_the_other_as_it_is(request, tmp_path):
    a, b = (two_folder(request, tmp_path / n) for n in ("a", "b"))   # helper below
    for p in (a, b):
        p.up()
    before = b.inspect()                     # container id, StartedAt, Config.Image
    newer = tag_of_run(request, IMAGE)       # docker tag IMAGE <run prefix>-newer, removed after
    a.set_env(LADO_IMAGE=newer)
    a.up()
    assert a.inspect()["Config"]["Image"] == newer
    after = b.inspect()
    assert (after["Id"], after["State"]["StartedAt"], after["Config"]["Image"]) == (
        before["Id"], before["State"]["StartedAt"], before["Config"]["Image"])
    assert health(a.port)["ok"] and health(b.port)["ok"]
```

`two_folder` copies `docker/compose.yaml` and the quiet override into the folder, writes
`.env` (`COMPOSE_PROJECT_NAME` = `new_name()`, `LADO_PORT` = `free_port()`, `LADO_IMAGE` =
a run-prefixed tag of `IMAGE`, `LADO_PROJECTS` = a temporary folder), runs `docker compose`
with `--project-directory` that folder and no `-p` (so `.env` decides the name), registers
the container with `keep(...)` for evidence, and a finalizer `down -v` plus `docker volume
rm -f <project>_home` and `docker image rm` of its own tags only.

- [ ] **Step 4: Run** `uv run pytest tests/test_docker.py -n0` and `make docker && make test-container`: PASS.
- [ ] **Step 5: Commit** `Compose runs the published image by LADO_VERSION; an update is a new version, no lado:previous (LAD-73)`.

### Task 5: The Release workflow publishes the tested image

**Files:**
- Modify: `.github/workflows/release.yml`
- Test: `tests/test_release_workflow.py`
- Docs: `docs/release.md` (a section "The image", D8; sections 2, 5 and 7 name it)

**Interfaces:**
- Consumes: `update.IMAGE`; `scripts/smoke_ci.py container <out>`; `scripts/release_notes.py --flag`.

- [ ] **Step 1: Failing tests** (`steps()` now reads `jobs["build"]`; keep the existing
  tests on it, `uv publish` moves to `pypi`):

```python
def test_jobs_run_in_order_and_nothing_is_published_before_the_image_passed():
    j = jobs()
    assert j["image"]["needs"] == "build"
    assert set(j["pypi"]["needs"]) == {"build", "image"}
    assert set(j["image-tags"]["needs"]) == {"pypi", "image"}
    assert j["github-release"]["needs"] == "image-tags"
    assert not any("uv publish" in s.get("run", "") for s in j["build"]["steps"])

def test_the_image_is_built_on_each_architectures_runner():
    m = jobs()["image"]["strategy"]["matrix"]["include"]
    assert {(c["arch"], c["runner"]) for c in m} == {
        ("amd64", "ubuntu-24.04"), ("arm64", "ubuntu-24.04-arm")}

def test_the_image_job_tests_the_image_it_pushes():
    s = jobs()["image"]["steps"]
    runs = [x.get("run", "") for x in s]
    build = next(i for i, r in enumerate(runs) if "docker buildx build" in r)
    tests = next(i for i, r in enumerate(runs) if "scripts/smoke_ci.py container" in r)
    assert build < tests
    assert "push-by-digest=true" in runs[build] and "type=docker" in runs[build]
    assert any("uv sync --locked" in r for r in runs[:tests])
    assert any(x.get("uses", "").startswith("actions/download-artifact@") for x in s[:build])

def test_the_image_name_is_lados():
    text = WORKFLOW.read_text()
    assert f"{update.IMAGE}" in text
    assert text.count("ghcr.io/") == text.count(update.IMAGE)

def test_latest_only_for_a_final():
    run = "\n".join(s.get("run", "") for s in jobs()["image-tags"]["steps"])
    assert 'scripts/release_notes.py --flag "$GITHUB_REF_NAME"' in run
    assert "--latest" in run and ":latest" in run
    assert "imagetools create" in run and "imagetools inspect" in run

def test_only_the_job_token():
    assert "secrets." not in WORKFLOW.read_text()
    for name in ("image", "image-tags"):
        assert jobs()[name]["permissions"]["packages"] == "write"
    assert jobs()["pypi"]["permissions"] == {"id-token": "write"}
    assert jobs()["github-release"]["permissions"] == {"contents": "write"}
```

Update `test_the_github_release_comes_only_after_pypi_accepted_the_release` to
`needs == "image-tags"`.

- [ ] **Step 2: Run** `uv run pytest tests/test_release_workflow.py tests/test_workflow_security.py -n0`: FAIL.

- [ ] **Step 3: Implement** (D1, D2). The `image` job's core step:

```yaml
      - name: Build the image, load it for the tests and push it by digest
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          echo "$GH_TOKEN" | docker login ghcr.io -u "$GITHUB_ACTOR" --password-stdin
          docker buildx create --use --driver docker-container
          version="${GITHUB_REF_NAME#v}"
          docker buildx build -f docker/Dockerfile \
            --label org.opencontainers.image.source=https://github.com/ladohq/lado \
            --label "org.opencontainers.image.version=$version" \
            --output "type=docker,name=lado:release" \
            --output "type=image,name=ghcr.io/ladohq/lado,push-by-digest=true,name-canonical=true,push=true" \
            --metadata-file "$RUNNER_TEMP/metadata.json" .
          echo "digest=$(jq -r '."containerimage.digest"' "$RUNNER_TEMP/metadata.json")" >> "$GITHUB_OUTPUT"
      - name: Container tests
        env:
          LADO_TEST_IMAGE: lado:release
        run: uv run python scripts/smoke_ci.py container "$RUNNER_TEMP/container"
```

with `id:` on the build step, the digest as a job output per arch (a matrix job's outputs
collide: write each digest to a small artifact `digest-<arch>` or name outputs
`digest-amd64` / `digest-arm64` by `matrix.arch`; the developer picks one and the test
follows it). The local name `lado:release` and `dist/` come first (download-artifact of
`dist` into `dist/`), `uv sync --locked` before the tests. If buildx refuses two outputs on
the runner, D2's fallback.

`image-tags`:

```yaml
      - run: |
          echo "$GH_TOKEN" | docker login ghcr.io -u "$GITHUB_ACTOR" --password-stdin
          version="${GITHUB_REF_NAME#v}"
          tags=(-t "ghcr.io/ladohq/lado:$version")
          if [ "$(python3 scripts/release_notes.py --flag "$GITHUB_REF_NAME")" = "--latest" ]; then
            tags+=(-t ghcr.io/ladohq/lado:latest)
          fi
          docker buildx imagetools create "${tags[@]}" \
            "ghcr.io/ladohq/lado@$AMD64" "ghcr.io/ladohq/lado@$ARM64"
          docker buildx imagetools inspect "ghcr.io/ladohq/lado:$version" | tee "$RUNNER_TEMP/inspect.txt"
          grep -q linux/amd64 "$RUNNER_TEMP/inspect.txt" && grep -q linux/arm64 "$RUNNER_TEMP/inspect.txt"
```

(checkout with `persist-credentials: false` for `release_notes.py`).

`docs/release.md`: a section "8. The image" (D8) and lines in sections 2.5 and 5.2 that the
workflow also publishes the image, tested first; the one-time public visibility after the
first RC.

- [ ] **Step 4: Run** `uv run pytest tests/test_release_workflow.py tests/test_workflow_security.py -n0`: PASS;
  `uv run python -c "import yaml;yaml.safe_load(open('.github/workflows/release.yml'))"`; if
  `actionlint` is installed, run it on the file.
- [ ] **Step 5: Commit** `The Release workflow publishes LADO's image to GHCR after its container tests (LAD-73)`.

### Task 6: AGENTS.md, CHANGELOG.md, regression

**Files:** `AGENTS.md` (Commands' `make docker` line, Container tests paragraph about
`lado:previous`, Layout `update.py` `CONTAINER_UPDATE` → `IMAGE`, `self_update.py`'s
container refusal, `state.py`'s way back, `docker/` paragraph: four CLIs, compose by
version, the second LADO, the Release workflow's image), `CHANGELOG.md` (0.39.0: rewrite
the LAD-71 item's `lado:previous` parts; add items: the image on GHCR per release with all
four CLIs; compose by `LADO_VERSION`; LADO names the new image instead of commands in a
container).

- [ ] **Step 1:** `grep -rn "lado:previous\|CONTAINER_UPDATE" src docker tests web/src AGENTS.md docs/release.md docs/design/ui.md CHANGELOG.md`
  prints nothing.
- [ ] **Step 2: Regression run** (each its own command, logs outside the tree, exit status
  read): `make lint`; `make test`; `make web`; `uv run pytest -m ui tests/ui/test_system_panel.py`;
  `make docker && make test-container`; `openspec validate image-on-ghcr --strict`;
  `openspec validate --specs --strict`. CI then runs the integration, UI and smoke suites
  and the `container` job on both architectures.
- [ ] **Step 3: Build report** with D4's numbers (size and cold build before/after, CI's
  container job time on the PR vs main) and the manual check of the design doc copied into
  the PR's description.
- [ ] **Step 4: Commit** `AGENTS.md and the changelog describe LADO's published image (LAD-73)`.

## Tests per requirement

| Requirement (capability) | Layer | Tests |
|---|---|---|
| A release publishes LADO's image to GHCR (image-release) | unit; manual at the next RC | `test_release_workflow.py`: jobs, matrix, labels, token; RC run by the human |
| The image is tested before anything is published (image-release) | unit | `test_jobs_run_in_order…`, `test_the_image_job_tests_the_image_it_pushes` |
| latest names only the newest final (image-release) | unit | `test_latest_only_for_a_final` |
| The GitHub release names the image (image-release) | unit | `test_release_notes.py` footer tests |
| lado update refuses in a container at once (container) | unit | `test_self_update.py`, `test_cli.py` |
| The UI's update refuses in a container (container) | unit, vitest, UI e2e | `test_server_system.py`, `SystemPanel.test.tsx`, `tests/ui/test_system_panel.py` |
| lado doctor and the report (container) | unit | `test_doctor.py`, `test_update.py` |
| The compose file publishes one port number (container) | unit; container | `test_docker.py`; `docker compose config` cases |
| A new image starts on an old home volume (container) | container | `test_migration.py` |
| The image carries the four agent CLIs (container) | unit; container | `test_docker.py`; `test_image.py` doctor |
| Two LADO containers update independently (container) | container | `test_two_lados.py` |
| A failed migration says how to go back (schema-migration) | unit; container | `test_cli.py`; `test_migration.py` |

End to end: the container layer (layer 7) runs the image as users do, on amd64 and arm64
in CI. Regression: Task 6's run plus CI.
