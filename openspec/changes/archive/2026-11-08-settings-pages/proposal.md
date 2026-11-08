Task: LAD-238

## Why

Settings is one long page: Appearance, Notifications, Agent CLIs and environment, Models and
Usage statistics one under the other. Each new setting makes it longer, and two links already
land in its middle by an anchor (`#providers-and-environment`, `#models`). A CLI's login and
its default model are on two sections apart, though both say whether and how its agents start.
The rail's Settings icon, a circle with rays, reads as the light theme, and Report a bug takes a
rail item of its own.

Cause: Settings grew one section at a time (LAD-32 statistics, LAD-163 logins, LAD-187 and
LAD-205 models), each appended to `Settings.tsx`; the anchors were the cheapest way to reach a
section. The redesign (LADO session "settings", rounds 3-5, run artifacts `r3-models-*`,
`r4-concise-*`, `r5-*`) was approved with the human and never built: main still has the one
page.

Options weighed for the structure (decided at the design rounds, recorded here):

- A (taken): a page per section beside a list, `/settings/<section>`, the list alone on a
  phone. Each page is short; a link names its page; new sections add a list item. Long-term
  cost: routes and redirects to keep, one list of sections (`SETTINGS_SECTIONS`) as their one
  source.
- B: tabs on one page. Less code, but a phone has no room for five or more tabs, and the
  anchors stay.
- C: keep one page with a table of contents. No new routes, but the page keeps growing and the
  login and the default model stay apart.

Options weighed for the default models (round 5):

- A (taken): each CLI's default model in its row on Agent CLIs, under its login: "can it
  start" and "what it runs" together; Model servers keeps the servers and one table of the
  human's models. Long-term cost: Agent CLIs reads the model settings too.
- B: keep a block "Default models" on the models page. No move of code, but a CLI shows up on
  two pages with two halves of its state.

Options weighed for Help (the human's answer #4821):

- A (taken): one rail item Help with a menu: Documentation ↗, GitHub ↗, Report a bug. Long-term
  cost: a menu that opens beside the rail.
- B: Documentation in the Settings list (round 4) and Report a bug on the rail as now. Help
  would be split over two places, and the rail keeps an item used rarely.

## What Changes

- Settings becomes pages: General `/settings/general`, Agent CLIs `/settings/agent-clis`,
  Model servers `/settings/model-servers`, Statistics `/settings/statistics`, with a list of
  their names and icons beside the page; on a phone `/settings` is the list and a section its
  own page with "‹ Settings". `/settings` opens General on a computer and a tablet.
- Old links land on the new pages: `/settings#providers-and-environment`, `#models`,
  `#statistics`, `#notifications`, `#appearance`, `/settings/models`, `/settings/usage-statistics`,
  `/settings/agent-clis-and-environment`; any other `/settings/<unknown>` goes to `/settings`.
- Setting rows instead of cards: a name and at most one short line on the left, the control on
  the right, thin lines between rows. Browser notifications becomes a switch. Texts are cut by
  the briefs' before → after tables (r4, r5).
- Agent CLIs: each CLI's row holds its login and, under it, "Default model" with today's picker
  and its warnings. Needs you's "Log in…" and New session's "Log in first" open
  `/settings/agent-clis#<cli>`: the page scrolls to that row and focuses its login button (F18).
- Model servers: Servers, then one table "Your models" (Name · Model · From · Agent CLI · ×),
  a CLI's default marked `· default` (F17). The per-CLI cards go.
- The rail: a cogwheel for Settings (and the General section); one item **Help** with a menu
  Documentation ↗ (README), GitHub ↗, Report a bug replaces the item Report a bug. The system
  panel keeps its GitHub icon.
- Texts naming the sections change everywhere: the server's refusals and `lado doctor`
  ("Settings → Agent CLIs"), `lado model default`'s refusal ("Settings → Model servers"), the
  launch window's Model notes, the Docker headers, the docs.

## Scope

- The web UI: `Settings.tsx` and new section pages, `Providers.tsx`, `ModelSettings.tsx`,
  `ModelSources.tsx`, `ModelPicker.tsx`, `LaunchModel.tsx`, `Launch.tsx`, `NeedsYou.tsx`,
  `Notifications.tsx`, `Telemetry.tsx`, `SystemPanel.tsx`, `Shell.tsx`, `Menu.tsx`,
  `icons.tsx`, `paths.ts`, `App.tsx`, `styles.css`.
- Texts of the server and the CLI that name a section: `logins.py` (`SETTINGS`),
  `model_settings.py`, `doctor.py`'s message through `logins.SETTINGS`; `docker/compose.yaml`,
  `docker/Dockerfile`; docs (`docs/design/ui.md`, `docs/cli.md`, `docs/install.md`,
  `docs/design/agents.md`, `docs/design/modules.md`), docstrings and comments.
- No API, schema, MCP tool or CLI option changes. The version bumps the minor: a feature of the
  UI under `## 0.45.0 (unreleased)`, whose heading already bumps it.

## Out of scope

- Groups (from six sections) and Find a setting (from eight), frame 16 of the r5 mockup: with
  four sections neither would show; built with the sixth section (the human's answer #4821,
  AGENTS.md "Only what is used"). The thresholds go into `docs/design/ui.md`.
- Documentation ↗ in the Settings list (round 4): it moved to Help (LAD-238).
- Removing GitHub from the system panel: kept (the human's answer #4821).
- The note `Its default model <name> was removed with <server>.` after a server's removal: it is
  not carried to Agent CLIs; the removal's question names the default already (#4821).
- A tab title per section (round 3): the r5 spec keeps `Settings`.
- The Report a bug page itself, the login sheet and window, the picker's behaviour, the
  servers' rows, form and ticks: unchanged apart from the words listed in the deltas.

## Acceptance criteria

- AC-1: `/settings/general`, `/settings/agent-clis`, `/settings/model-servers` and
  `/settings/statistics` show their page beside a list of four names with icons and no state
  line, at 1440 and 768; at 390 `/settings` is the list alone and each section its own page
  with "‹ Settings"; at 1440 and 768 `/settings` opens General. They match the r5 mockup
  (frames 1-15) in light and dark.
- AC-2: each old link of the redirect table lands on its new page, replacing the history entry;
  `/settings/<unknown>` lands on `/settings`.
- AC-3: Needs you's "Log in…" and New session's "Log in first" open
  `/settings/agent-clis#<cli>`; the row of that CLI is scrolled into view and its login button
  has the focus; an unknown `#<cli>` leaves the page at its top.
- AC-4: each installed CLI's row on Agent CLIs has a Default model picker that saves at once,
  with the warnings and ways out of today's Models card under it; a CLI not installed has no
  picker, and with a default it shows `Default model: <name> — cannot run: not installed` and
  `Use <CLI>'s settings`.
- AC-5: Model servers shows Servers, then one Your models table sorted by CLI then name, with
  rename, × with Undo, the default marked `· default`, and From `⚠ <server>` for a server that
  does not answer; no per-CLI card is left.
- AC-6: the rail shows a cogwheel for Settings and a Help item whose menu gives Documentation ↗
  (`https://github.com/ladohq/lado#readme`), GitHub ↗ (`https://github.com/ladohq/lado`) and
  Report a bug (`/report`); Help is marked current on `/report`; on a phone the drawer's Help
  opens the same menu with 44 px items. The rail has no item Report a bug.
- AC-7: the texts of the r4 and r5 before → after tables show as written; the server's refusals,
  `lado doctor` and `lado model default` name `Settings → Agent CLIs` and
  `Settings → Model servers`; no UI text, doc or test names `Agent CLIs and environment`,
  `Settings → Models` or `Usage statistics` as a section.
- AC-8: no horizontal scroll at 390, 768 and 1440 on any Settings page; every phone control is at
  least 44 px; no picked model's name is cut.
- AC-9: `make lint`, `make test`, `make web`, the changed UI and integration tests and
  `openspec validate settings-pages --strict` pass; CI's `ci-ok` is green.

## Impact

- Users: the addresses of Settings change, the old ones keep working; Report a bug moves into
  Help.
- Code: the web UI as in Scope, a few texts of `logins.py` and `model_settings.py`; tests that
  open `/settings` or name the old sections.
- Specs: new `settings-pages` and `rail-help`; deltas of `model-settings-page`,
  `provider-logins`, `usage-telemetry`, `bug-report`, `phone-layout`, `session-layout`,
  `session-model`, `configured-models`, `model-servers`, `container`.
