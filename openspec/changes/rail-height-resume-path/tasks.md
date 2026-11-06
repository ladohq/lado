## 1. The rail

- [x] 1.1 `web/src/styles.css`, `@media (min-width: 901px)`: `.rail { height: 100% }` becomes
  `.app .rail`, with a line of comment on why (the base `.rail` comes later in the file). The
  phone's `:root[data-phone] .rail` and its drawer stay more specific; change neither.
- [x] 1.2 `tests/ui/test_phone.py` (UI e2e, `-m ui`: only a browser resolves the cascade): a
  touch page at 1180x688 with `--phone-height` set to 560 as the tablet tests do: `.rail` is
  560 high and Settings ends within 560. Written first, red on the old rule.
- [x] 1.3 The same file: with a mouse at 1280x800 the rail is 800 high; a session's page on a
  touch screen at 820 wide with `--phone-height` 600 has a rail of 600.

## 2. Where in the Resume window

- [x] 2.1 `web/src/Launch.tsx`, `WhereField`: a prop `fixed` (`resuming !== null`). While it is
  set the field shows the path in a `div.where-fixed` with `role="group"` and
  `aria-labelledby` on the word Where (a `span.field-label` then, as `.kits-box` does) in place
  of `.where-box`; the notes under the field stay as they are. `disabled` keeps its meaning
  for New session.
- [x] 2.2 `web/src/styles.css`, after `.launch-where input`: `.where-fixed` looks as the
  disabled field of the mock-up: `--ground`, `--muted`, the field's border and radius, 13 px
  `--mono`, `min-height: 38px` with `box-sizing: border-box`, `overflow-wrap: anywhere`.
- [x] 2.3 `web/src/Launch.test.tsx` (unit): the tests that read Where in Resume mode (the one
  behind "Resume it" among them) read the text; no combobox Where in Resume mode; New session
  still has it.
- [x] 2.4 `tests/ui/test_launch.py`, `test_resume_a_stopped_session`, and any other UI test
  that reads Where in the Resume window: the group Where holds the repo's path.
- [x] 2.5 `tests/ui/test_phone.py` (UI e2e): the Resume window at 402 px wide on a touch screen
  for a repo in a folder deep enough to need two lines: `.where-fixed` holds the whole path,
  is higher than 38 px, its `scrollWidth` equals its `clientWidth`, and the page has no
  sideways scroll. A folder name of 80 characters with no break does the same.

## 3. Documents

- [x] 3.1 `docs/design/ui.md`: "The app's window" says the rail follows the app above 900 px;
  **Resume** says Where is text that wraps, and why.
- [x] 3.2 `CHANGELOG.md`, `## 0.45.0 (unreleased)`, `### Fixed`: one line per visible change,
  by docs/release.md's rules: the rail on a wide touch screen, the whole path in Resume.

## 4. The checks

- [x] 4.1 `make lint`, `make web`, `make test`, `uv run pytest -m ui tests/ui/test_phone.py
  tests/ui/test_launch.py`, `openspec validate rail-height-resume-path --strict` and the
  trial archive of the settings. `make check` as a whole is CI's, by `.lado/sdlc.md`.
- [x] 4.2 Screenshots as run artifacts, named in `build-report`: the rail at 1180x560 and the
  Resume window at 402 px.
