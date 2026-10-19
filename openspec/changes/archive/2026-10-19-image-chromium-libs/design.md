## Context

The image installs Debian packages as root in one apt layer (`docker/Dockerfile`), whose
first `apt-get install` `tests/test_docker.py` checks for the agents' base tools. The UI
tests run Playwright's Chromium headless (pytest-playwright); `make browser` installs it
with `uv run playwright install chromium` into `~/.cache/ms-playwright`, on the home
volume in a container. Playwright (1.63.0 in `uv.lock`) keeps, per distribution, the apt
packages each browser needs; for Debian 12 (amd64 and arm64 alike) Chromium's list is 21
packages, and a separate `tools` list adds `xvfb` and nine font packages. The web bundle
carries the UI's fonts (`@fontsource/inter`, `@fontsource/ibm-plex-mono`); fontconfig,
which `libcairo2` and `libpango-1.0-0` pull in, brings `fonts-dejavu-core`. The agents'
container has no Docker: only CI's container job builds the image and runs
`tests/container/`.

## Decisions

### D1. Chromium's libraries are an explicit Debian list in a layer of their own

A second `RUN apt-get update && apt-get install -y --no-install-recommends <21 packages>
&& rm -rf /var/lib/apt/lists/*`, as root, after the first apt layer (before Node), with a
comment naming where the list comes from (Playwright's Debian 12 `chromium` list, what
`playwright install-deps chromium` installs) and that the browser is the home volume's.

Options:
1. (chosen) The explicit list, its own layer. Debian's signed packages, no new pin; the
   layer's size is the image's growth, and a change of the list rebuilds one layer. Cost:
   a Playwright upgrade that needs a new library makes the container test red (D3), and
   the list is moved by hand.
2. `playwright install-deps chromium` at build time. Needs Playwright in the image at a
   pin of its own (a second source of the version beside `uv.lock`), and installs what
   its host detection picks, `tools` included (xvfb, CJK fonts).
3. The libraries in the first apt layer. One layer less, but the base tools' layer would
   rebuild for a browser's change and the growth would not be measurable apart.

### D2. No fonts, no xvfb, no browser

Playwright's `tools` list is left out: headless needs no X server, the UI's fonts come
with the bundle and DejaVu is the fallback. The browser stays out of the image (its build
follows `uv.lock`; `make browser` keeps it on the home volume across images).

### D3. The container test takes Playwright's version from uv.lock

A new `tests/container/test_browser.py` (marker `container`) reads Playwright's version
from `uv.lock` (`tomllib`), and in a login shell from a clean environment (as
`test_toolchains.py`'s `login`) on a new home volume runs
`uv tool run --from playwright==<version> playwright install --only-shell chromium`, then
`ldd` on the installed `chrome-headless-shell` (a glob under `~/.cache/ms-playwright`,
amd64 and arm64), asserting no `not found` and naming the missing ones when red; then a
Python snippet through the same `uv tool run` launches Chromium headless, sets a page with
Latin and Cyrillic text, reads it back and saves a screenshot into the test's artifact
folder. A second test: on a new home volume no `~/.cache/ms-playwright` and no
`chromium`, `chromium-browser` or `google-chrome` on `PATH`. So a Dependabot move of
Playwright that needs a library the list lacks is red in CI's container job.

### D4. The UI tests themselves run in the image once, by hand

Decided with the human (question #217). The container test proves the browser starts;
`uv run pytest -m ui tests/ui/test_chat.py` in a container of the new image is the
acceptance check of the pull request, run once by the human (or a session in the
rebuilt image) and named in its description. Running the UI suite in CI's container job
would add `uv sync`, a full Chromium download and the suite to each architecture's run.

### D5. CI prints the image's layers

The container job's "Image" step runs `docker history lado:local` after `make docker`, so
every run's log shows each layer's size; the new apt layer's size is the image's growth,
reported in the pull request.
