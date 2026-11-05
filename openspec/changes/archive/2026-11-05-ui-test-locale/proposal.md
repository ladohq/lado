Task: LAD-203

## Why

Symptom: `make web` fails on a machine with a Russian locale. Reproduced 2026-11-05 with
`LC_ALL=ru_RU.UTF-8 npx vitest run`; `web/` of `epic/lad-154-models`, 1447 tests, 3 fail:

- `SystemPanel.test.tsx`, "the check line says when it looked and how it went" (on main too):
  it wants `2 Oct` or `Oct 2` and gets `2 окт.`.
- `ModelCards.test.tsx`, "a card's models: the default first, the others by name, under Your
  models <n>" (epic branch only): it wants Latin names before Cyrillic ones.
- `ModelSettings.test.tsx`, "× leaves its row as Removed … Undo with the focus on Undo; Undo
  saves it again and focuses its name" (epic branch only): the same order.

Cause: the UI formats dates with `toLocale*([], …)` and sorts names with `localeCompare`, on
purpose: the human's locale decides. Under vitest that locale is the process's: Node's ICU
reads `LC_ALL`, then `LANG`, whether or not the system has that locale. Nothing fixes it, so
each test sees the locale of the machine it runs on, and its expected values are written for
en-US, CI's. BACKLOG.md has held the same defect since 2026-10-05 ("UI unit tests depend on
the process's locale and nothing guards it"), when it turned CI red the other way round.

The product is not at fault: a Russian date and a Russian order are right for a Russian
browser. Only the tests' environment is loose.

Options weighed:

- A (taken): one locale for vitest, set once in its configuration. Every test, present and
  future, runs alike on every machine and in CI. Long-term cost: a line of configuration; the
  suite proves nothing about another locale, which it does not prove today either.
- B: rewrite each test to expect what the running locale gives, or to pass in either. Three
  tests now, and every new date or order test after them must remember it; the defect comes
  back with the next test written on a machine of one locale, as it has twice.
- C: A or B, plus a second vitest run under `ru_RU.UTF-8`, as BACKLOG.md asks. It doubles the
  run in `make web` and CI. With A it proves nothing, as the pin overrides it; with B it is
  the guard B needs, at the price of forcing each test to be locale-free for good.

## What Changes

- vitest runs with `LC_ALL=en_US.UTF-8`, whatever the shell's locale (`test.env` in
  `web/vite.config.ts`).
- A unit test holds the pin, so that removing it goes red on any machine, CI's included.
- `docs/testing.md` says so; BACKLOG.md's entry goes, as this change closes it.
- A patch: tests only; users see nothing, so no CHANGELOG.md line, no API, no schema, no UI
  change and no mockup; docs/design/ui.md stays as it is.

## Scope

- `web/vite.config.ts`, a new `web/src/testLocale.test.ts`, `docs/testing.md`, `BACKLOG.md`.

## Out of scope

- The three tests themselves: they are right under the pin. Their expected values stay;
  `/2 Oct|Oct 2/` keeps its second form, harmless, as the change is not about it.
- The time zone: the tests that depend on it build their dates in local time, and no failure
  is known; it does not grow this task.
- UI e2e tests (`make test-ui`): another process, not vitest's, and the task names no failure
  there.
- A run of vitest under a second locale (option C): see Why.

## Impact

- Only the unit test run of the web UI. The bundle and `vite build` are untouched: `test.env`
  applies to vitest alone.
- The change goes to main; `epic/lad-154-models`, where two of the three tests live, gets it
  with its next merge of main.
- No delta (`skip_specs` in `.openspec.yaml`): a rule of the test tooling, recorded in
  `docs/testing.md`; archived with `--skip-specs`.
