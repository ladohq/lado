## ADDED Requirements

### Requirement: The image carries the system libraries of Playwright's Chromium

The image SHALL carry, from Debian in an apt layer of its own, the packages Playwright
installs for Chromium on Debian 12: `libasound2`, `libatk-bridge2.0-0`, `libatk1.0-0`,
`libatspi2.0-0`, `libcairo2`, `libcups2`, `libdbus-1-3`, `libdrm2`, `libgbm1`,
`libglib2.0-0`, `libnspr4`, `libnss3`, `libpango-1.0-0`, `libx11-6`, `libxcb1`,
`libxcomposite1`, `libxdamage1`, `libxext6`, `libxfixes3`, `libxkbcommon0`, `libxrandr2`.

#### Scenario: Playwright's Chromium starts in a new container

- **WHEN** a login shell as `lado`, started from a clean environment as LADO starts an
  agent's, in a new container on a new home volume installs the headless shell of
  Playwright at the version `uv.lock` names
- **THEN** `ldd` of its `chrome-headless-shell` names no library `not found`, and that
  Playwright launches Chromium, which renders a page with Latin and Cyrillic text and
  gives the text back

### Requirement: The image carries no browser

The image SHALL NOT carry a browser: the project's Playwright installs it into the home
volume (`make browser`), at the project's own version.

#### Scenario: A new home volume has no browser

- **WHEN** a login shell as `lado` in a new container on a new home volume looks for
  Playwright's browsers (`~/.cache/ms-playwright`) and for `chromium`, `chromium-browser`
  or `google-chrome` on `PATH`
- **THEN** there is none
