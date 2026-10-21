## 1. The fix

- [ ] 1.1 `web/src/Launch.tsx`: `ready` asks `providerInfo?.installed === true` in both
  modes and `current?.ok` only for a new session, e.g.
  `(resuming !== null || (current?.ok ?? false)) && providerInfo?.installed === true &&
  kits.length > 0 && !promptOver`; a comment says the provider's part is the same
  condition under which `ProviderNote` shows no refusal.
- [ ] 1.2 `web/src/Launch.test.tsx` (unit, vitest), under `// Resume`: a stopped session
  whose provider is listed with `installed: false` shows its refusal (`field-note bad`)
  and Resume session is disabled; choosing `claude` (installed) turns it on. A second
  case: a provider absent from the list (`unknown provider gone`) keeps it disabled.
  The existing Resume tests stay green (they wait for the button to turn on). Check:
  `make web`.

## 2. UI e2e (`tests/ui/test_launch.py`, `-m ui`)

- [ ] 2.1 A stopped session (`stopped_session`) whose provider is set in LADO's state to
  a name no provider has (an `UPDATE sessions SET provider = ?` through `state.connect()`
  in the test): its Resume window shows `unknown provider <name>` as a refusal panel and
  Resume session is disabled; after `select_option("fake")` the button is enabled.
  A screenshot of the window with the refusal for the reviewer. Check:
  `uv run pytest -m ui tests/ui/test_launch.py`.

## 3. Documents

- [ ] 3.1 `docs/design/ui.md`, "The window's notes in three levels": the list of buttons
  off while a refusal shows names Resume session too (LAD-122, 2026-10-21).
- [ ] 3.2 CHANGELOG.md, `## 0.42.1 (unreleased)`, a `### Fixed` group (add it after
  Improved when missing): "**Resume session waits for a provider that can run.** While
  the window says the session's provider cannot run, Resume session is off, as Start is
  in a new session."
- [ ] 3.3 Checks: `make lint`, `make test`, `make web`, `uv run pytest -m ui
  tests/ui/test_launch.py`, `openspec validate resume-off-on-provider-refusal --strict`.
