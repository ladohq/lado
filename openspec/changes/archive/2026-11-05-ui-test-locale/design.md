## Decisions

### D1. The pin is `test.env` in `web/vite.config.ts`

`test: { env: { LC_ALL: "en_US.UTF-8" } }`, next to `environment: "jsdom"`, with a comment
saying why. `LC_ALL` because ICU reads it first and it beats `LANG`. Measured on `web/` of
`epic/lad-154-models` under `LC_ALL=ru_RU.UTF-8`: 3 failures without it, 1447 of 1447 passed
with it. `npm test`, `npx vitest run <file>` and `make web` all read this file, so it is one
place for all of them.

Rejected: `LC_ALL=… vitest run` in `package.json`'s `test` script (`npx vitest` goes round it,
and it is shell syntax that Windows' npm does not run); assigning `process.env.LC_ALL` at the
top of the config (works as well, but is a side effect in a config file where vitest has a
field).

### D2. A unit test holds the pin

CI's locale is en-US already, so a test of the formatted output alone stays green there
without the pin. `web/src/testLocale.test.ts` checks both halves: `process.env.LC_ALL` is
`en_US.UTF-8`, which goes red when the pin is removed (neither `ci.yml` nor the Makefile sets `LC_ALL`), and
`new Intl.DateTimeFormat().resolvedOptions().locale` is `en-US`, which goes red when the pin
stops reaching ICU.

### D3. The target is main

The task has no epic of its own: it grew out of LAD-200, but its first failure is on main, and
the fix is one line of a file that is the same on both branches. Main gets it at once, and the
epic's regular merges of main carry it there.
