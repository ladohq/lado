## 1. The image (D1, D2)

- [ ] 1.1 `docker/Dockerfile`: a second apt layer after the first (before Node) with the
  21 packages of the spec, `--no-install-recommends`, `rm -rf /var/lib/apt/lists/*`, and a
  comment: Playwright's Debian 12 `chromium` list (`playwright install-deps chromium`),
  no fonts or xvfb, the browser itself from `make browser` on the home volume. Check: 2.1
  in CI.
- [ ] 1.2 `.github/workflows/ci.yml`, job `container`, step "Image": `docker history
  lado:local` after `make docker` (D5). Check: the step's log in the pull request's run.

## 2. Container tests (D3)

- [ ] 2.1 `tests/container/test_browser.py` (marker `container`): Playwright's version
  from `uv.lock`; in a clean login shell on a new home volume `uv tool run --from
  playwright==<version> playwright install --only-shell chromium`; `ldd` of
  `chrome-headless-shell` names no `not found` (the missing ones in the failure); Chromium
  launched by that Playwright renders a page with Latin and Cyrillic text, the text read
  back, a screenshot saved with the test's artifacts. Check: CI's container cells (amd64,
  arm64); the developer's container has no Docker.
- [ ] 2.2 The same file: a new home volume has no `~/.cache/ms-playwright` and no
  `chromium`, `chromium-browser` or `google-chrome` on `PATH`. Check: as 2.1.
- [ ] 2.3 The new layer's size from 1.2's log (amd64 and arm64) in the pull request's
  description.

## 3. Docs

- [ ] 3.1 The Dockerfile's header: the image carries Chromium's libraries for the UI
  tests; the browser comes from `make browser` on the home volume.
- [ ] 3.2 `docs/install.md`, "The projects' toolchains": the same, one sentence.
- [ ] 3.3 `docs/design/modules.md` (`docker/`): the second apt layer and where its list
  comes from.
- [ ] 3.4 `docs/testing.md`: the UI tests run in LADO's image after `make browser`; the
  container test of the libraries.
- [ ] 3.5 CHANGELOG.md under `## 0.42.0 (unreleased)`: the image carries the system
  libraries of Playwright's Chromium, so `make test-ui` runs in the container after
  `make browser`; the browser is not in the image.

## 4. Regression

- [ ] 4.1 `make lint`, `make test` (`tests/test_docker.py` still green with the second
  apt layer), `openspec validate --specs --strict`, `openspec validate
  image-chromium-libs --strict`; CI's container and smoke cells green.
- [ ] 4.2 The pull request's description carries the human's check (D4): `make docker`,
  a container of `lado:local`, in it `make browser` and `uv run pytest -m ui
  tests/ui/test_chat.py` passes.
