Plan: `docs/superpowers/plans/2026-11-08-settings-pages.md` (each section below is one of its tasks,
with its files, interfaces and tests).

## 1. Server texts

- [ ] 1.1 `logins.SETTINGS`, `model_settings.py`'s refusal, the Docker headers, docstrings and
  comments name `Settings → Agent CLIs` and `Settings → Model servers`; `make web-types`; the unit
  tests and `tests/integration/test_provider_logins.py` quote the new texts (AC-7). Checked: `make
  test`, `uv run pytest -m integration -n auto tests/integration/test_provider_logins.py`.

## 2. Paths and icons

- [ ] 2.1 `paths.ts`: `agentClisPath`, `GENERAL_PATH`, `MODEL_SERVERS_PATH`, `STATISTICS_PATH`,
  `DOCS_URL`, `GITHUB`; `SettingsIcon` a cogwheel, `HelpIcon` new (AC-6). Checked: `make web`
  (`paths.test.ts`).

## 3. Sections, routes, redirects

- [ ] 3.1 `settingsSections.ts`, the layout route, the list (names and icons only), the phone's list
  and `‹ Settings`, focus on the h2, the redirects (AC-1, AC-2). Checked: `make web`
  (`Settings.test.tsx`, `App.test.tsx`).

## 4. General

- [ ] 4.1 Theme and Browser notifications as setting rows, the switch, the refusal texts shared with
  Needs you, Needs you's link to `/settings/general#notifications` (AC-1, AC-7). Checked: `make web`
  (`Notifications.test.tsx`, `NeedsYou.test.tsx`).

## 5. Statistics

- [ ] 5.1 One row with its state's line; the system panel's row links to `/settings/statistics`
  (AC-1, AC-7). Checked: `make web` (`Telemetry.test.tsx`, `SystemPanel.test.tsx`).

## 6. Model servers

- [ ] 6.1 `useModelSettings`, `CliDefault`; Model servers with Servers and one Your models table, the
  default marked, the cards and their code removed (AC-5, AC-7). Checked: `make web`
  (`ModelSettings.test.tsx`, `ModelCards.test.tsx`, `ModelSources.test.tsx`).

## 7. Agent CLIs

- [ ] 7.1 Rows with the login and Default model, a CLI not installed, the no-servers line, the r4/r5
  texts (AC-4, AC-7). Checked: `make web` (`Providers.test.tsx`).
- [ ] 7.2 Arrival at `#<cli>` with focus on the login button; Needs you's and Launch's links pass the
  CLI (AC-3). Checked: `make web` (`Providers.test.tsx`, `NeedsYou.test.tsx`, `Launch.test.tsx`).

## 8. Launch window

- [ ] 8.1 The picker's foot and the Model notes name Settings → Agent CLIs and Model servers (AC-7).
  Checked: `make web` (`ModelPicker.test.tsx`, `Launch.test.tsx`).

## 9. Help

- [ ] 9.1 `Menu` with icons, a divider and `useBeside`; Help on the rail in place of Report a bug,
  current on `/report`, in the phone drawer (AC-6). Checked: `make web` (`Shell.test.tsx`,
  `Menu.test.tsx`, `Layout.test.tsx`, `ReportBug.test.tsx`).

## 10. Browser tests

- [ ] 10.1 `tests/ui/test_settings_pages.py` and the changed UI tests: pages at 390/768/1440 light and
  dark, redirects, arrival focus, Help, no sideways scroll, 44 px targets, names whole; screenshots of
  each page as run artifacts (AC-1..AC-8). Checked: each file `uv run pytest -m ui <file>`, then
  `uv run pytest -m ui -n auto tests/ui`.

## 11. Documents and the regression run

- [ ] 11.1 `docs/design/ui.md` (Settings, Agent CLIs, Model servers, Statistics, Help, Report a bug,
  System panel), `docs/cli.md`, `docs/install.md`, `docs/design/agents.md`, `docs/design/modules.md`,
  `docs/release.md`, CHANGELOG.md; the grep for the old names finds only the archive and
  `docs/epics/` (AC-7). Checked: the grep.
- [ ] 11.2 At archive (integrator): the `## Purpose` of `openspec/specs/provider-logins/spec.md`
  and `openspec/specs/model-settings-page/spec.md` name Settings → Agent CLIs and Settings → Model
  servers (a delta cannot change a Purpose). Checked: `openspec validate --specs --strict`.
- [ ] 11.3 `make lint`, `make test`, `make web`, `openspec validate settings-pages --strict` and the
  trial archive pass; CI's `ci-ok` green (AC-9).
