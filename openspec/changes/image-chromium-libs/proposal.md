Task: LAD-110

## Why

The UI tests (`make test-ui`, `uv run pytest -m ui`) do not run in LADO's image: Playwright's
`chrome-headless-shell` stops at once with `error while loading shared libraries:
libglib-2.0.so.0`. Checked on 2026-10-19 in an agent's container (arm64, Playwright 1.63.0
of `uv.lock`, browser build 1243): `ldd` finds 19 libraries missing (glib, gobject, gio,
nspr4, nss3, nssutil3, atk, atspi, dbus, X11, Xcomposite, Xdamage, Xext, Xfixes, Xrandr,
gbm, xcb, xkbcommon, asound). The agents cannot install apt packages in a running
container, so a developer working on LADO in the image cannot run the UI layer at all
(LAD-102, PR #107, could not check its attach test); the sessions lad-99 and lad-102 wait
for this.

Root cause: the image (`debian:bookworm-slim`) was built for LADO, the agent CLIs and the
projects' toolchains; a browser's system libraries are apt packages, which only the image
can carry. `make browser` puts the browser itself into the home volume's cache, so only the
libraries are missing.

## What Changes

- **Chromium's libraries from Debian** in a layer of their own after the first apt layer:
  the packages Playwright installs for Chromium on Debian 12 (`playwright install-deps
  chromium`, its `chromium` list): `libasound2 libatk-bridge2.0-0 libatk1.0-0
  libatspi2.0-0 libcairo2 libcups2 libdbus-1-3 libdrm2 libgbm1 libglib2.0-0 libnspr4
  libnss3 libpango-1.0-0 libx11-6 libxcb1 libxcomposite1 libxdamage1 libxext6 libxfixes3
  libxkbcommon0 libxrandr2`, with `--no-install-recommends`.
- **No browser in the image**: `make browser` (`uv run playwright install chromium`) still
  installs it into `~/.cache/ms-playwright` on the home volume, at the version of the
  project's own Playwright.
- **A container test**: in a new container, Playwright at `uv.lock`'s version installs its
  headless shell, `ldd` finds no library missing, and Chromium renders a page.
- **CI's container job prints the image's layers** (`docker history`), so the size of the
  new layer (the image's growth) is in every run's log.
- **Docs**: the Dockerfile's header, docs/install.md ("The projects' toolchains"),
  docs/design/modules.md (`docker/`), docs/testing.md (UI tests in the image),
  CHANGELOG.md.
- Release: under `## 0.42.0 (unreleased)`, which already bumps the minor (a feature of the
  image); on its own the change would be a minor too (the image carries something new).

## Scope

- `docker/Dockerfile`, `.github/workflows/ci.yml` (one print in the container job).
- Tests: container (`tests/container/`).
- Docs as listed above.

## Out of scope

- **The browser itself in the image**: its build is tied to the project's Playwright
  version (`uv.lock`); a baked-in one would be a second pin that drifts, and `make
  browser` already keeps it on the home volume across images.
- **Playwright's `tools` list** (`xvfb` and nine font packages, CJK among them, tens of
  MB): the UI tests run headless, and the UI's fonts (Inter, IBM Plex Mono) come in the
  web bundle; fontconfig brings DejaVu as the fallback font.
- **Firefox's and WebKit's libraries**: the UI tests use Chromium only.
- **Running `playwright install-deps` at build time**: it needs Playwright in the image at
  a pin of its own and installs what its host detection decides; the explicit list is
  reviewable and Debian's.
- **A unit test with the package list**: it would be a second copy of the list; the
  container test checks the list against the browser `uv.lock` names.
- **Running the UI tests in CI's container job**: decided with the human (design D4);
  `test_chat.py` in the image is checked once by hand.

## Impact

- The image grows by the new layer; the number comes from CI's `docker history` and goes
  into the pull request.
- An existing home volume needs no change; a browser `make browser` installed there before
  starts once the new image runs.
- No change to LADO's code, its MCP tools, CLI or schema.
