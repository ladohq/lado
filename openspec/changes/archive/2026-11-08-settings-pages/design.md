# Design: settings-pages

The approved look is the r5 mockup (run artifact `r5-mockup.html`, frames 1-15) with the specs
and briefs of rounds 3-5 (`r3-models-spec`, `r3-models-brief`, `r4-concise-spec`,
`r4-concise-brief`, `r5-design-system`, and the r5 spec and brief attached to LAD-238), and
`mockup-help.html` for the rail. Where the rounds differ the later one wins: r5 over r4 over r3.
Nothing here is above the provider layer: the web UI, the names of the sections in a few server
texts, the same for every provider.

## Decisions

**D1. One list of sections.** `web/src/settingsSections.ts` exports `SETTINGS_SECTIONS: { slug,
name, icon, Page }[]` (General, Agent CLIs, Model servers, Statistics) and the map of old
addresses (`OLD_HASHES`, `OLD_SLUGS`). The list, the routes, the pages' headings and the
redirects read it; nothing else names a section. Rejected: a route per section written in
`App.tsx` (a second list that drifts).

**D2. A layout route.** `App.tsx`: `<Route path="settings" element={<Settings />}>` with an
index route and `:section`. `Settings` renders the list and `<Outlet />`; above 600 px the index
replaces itself by `/settings/general` unless the hash is an old one; on a phone the index is the
list alone and a section page has `‹ Settings`. `:section` unknown → `/settings`; an old slug →
its page. All with `<Navigate replace>`. The hash is read once on mount of the index.
The top bar and the tab say `Settings`, on a phone the section's name (the human's answer at the merge gate, LAD-238).

**D3. Focus on a section change.** A page's `h2` has `tabIndex={-1}` and takes the focus when the
section changes while Settings is mounted, and on arrival, except when an arrival at
`#<cli>` (D6) or `#notifications` places it. A first load of `/settings` from the rail focuses
nothing, as other pages.

**D4. Pages from today's sections.** General: Theme and Browser notifications as setting rows
(`.srows`, `.srow`, the switch `.sw` of r4); the cards Appearance and Notifications go.
Agent CLIs: `Providers.tsx` as a page. Model servers: `ModelSettings.tsx` as a page with Servers
(`ModelSources.tsx`, unchanged behaviour) then Your models. Statistics: `Telemetry.tsx`'s
`StatisticsSetting` as one `.srow.srow-wide`. The texts are the r4 and r5 tables' "After".

**D5. The model settings are shared by a hook, not by a parent.** The state that
`ModelSettings` keeps today (`getModelSettings`, the reload after each change, the defaults,
Undo, the probes' health) moves into `useModelSettings()`; Agent CLIs and Model servers each
call it, so each page reads `GET /api/model-settings` when it opens and after its own changes.
The picker part of `CliCard` (picker, `.mc-notes`, `OtherName`, the warnings and their buttons)
becomes `CliDefault`, rendered in a row of `Providers.tsx` (`.cli-model`). Rejected: one state
above both pages in `Settings` (state that outlives the page the human left, for nothing the
pages show at once). Consequence, approved (#4821, 6): the note that a server's removal cleared a
default is not carried to Agent CLIs.

**D6. Arrival at `#<cli>`.** Each row is `li#<cli.name>` (the provider's name). `Providers`
keeps the hash it has handled in a ref; when rows are first there for a new hash it scrolls the
row into view (`block: "center"`, `behavior: "smooth"` unless `prefers-reduced-motion`) and
focuses the row's login button, else the name (`tabIndex={-1}`). A poll never scrolls again.
`paths.ts`: `agentClisPath(cli?)`, `MODEL_SERVERS_PATH`, `STATISTICS_PATH`, `GENERAL_PATH`;
`PROVIDERS_PATH`, `PROVIDERS_ANCHOR` and `MODELS_ANCHOR` go, their old values living only in D1's
map. Needs you passes the waiting agent's provider, Launch the chosen one.

**D7. Rows of Agent CLIs and the model settings meet by the CLI's name.** The rows come from
`getProviderLogins` as today; `CliDefault` takes that CLI's slice of the model settings. A CLI
the model settings know and the logins do not (a CLI LADO does not know) gets no row: its models
are in Your models with the saved CLI name, last (spec "Your models is one table"). A CLI not
installed: no picker; with a default, the line and `Use <CLI>'s settings` (`clearModelDefault`),
approved (#4821, 5).

**D8. Your models is one table.** `role="table"`, columns Name · Model · From · Agent CLI · ×;
today's `ModelRow`, `Rename` and `UndoRow` render its rows unchanged in behaviour; the CLI cell
says `<CLI> · default` for a default (F17). Sorted by the logins' order of CLIs, then name.
`keepAtTop`, `FOLD_ABOVE`, `INTRO`, `LEAD`, `LEAD_NO_MODELS`, `AgentClis` and `CliCard` go.
`useScrollAnchor` and `overflow-anchor: none` stay on Model servers.

**D9. Help is a button with the UI's menu.** `Shell.tsx` replaces the rail's Report a bug with
`HelpButton`: a `button.rail-link` (`aria-haspopup="menu"`, `aria-expanded`, `title="Help"` when
folded) that opens `Menu` with Documentation (href), GitHub (href) and Report a bug (onSelect:
navigate to `/report`). `Menu` gains what Help uses and no more: an `icon` per item, a `divided`
flag (a line above the item), and `useBeside(anchor, floating, open)` in `Menu.tsx`, which places
it right of the rail with its bottom on the anchor's bottom, kept 8 px inside the window; in the
phone drawer it places it above Help across the drawer's width with 44 px items. Esc gives the
focus back to Help. Choosing an item closes the menu and, on a phone, the drawer. On `/report`
Help gets the rail's current look by a class (`is-current`), not `aria-current`, as it is no link.
`GITHUB` moves from `SystemPanel.tsx` to `paths.ts` with `DOCS_URL`; the panel keeps its icon
(#4821, 3).

**D10. Icons.** `SettingsIcon` is redrawn as a cogwheel with teeth (the mockup's path), so the
rail and General change together; `HelpIcon` (a question mark in a circle) is new. `BugIcon`,
`DocumentIcon`, `GitHubIcon` and `OpenTabIcon` serve the menu.

**D11. Server texts.** `logins.SETTINGS` becomes `Settings → Agent CLIs`, which changes the
refusals, the waiting agent's line and `lado doctor` at once; `model_settings.py`'s refusal says
`Settings → Model servers`. Docstrings and comments naming the sections follow; `models.py`'s
docstrings reach `web/openapi.json` and `web/src/api.gen.ts` (`make web-types`). The Docker
headers name `Settings → Agent CLIs`.

**D12. Links into Settings.** The model picker's foot → `/settings/agent-clis` (new tab);
the system panel's Statistics row → `STATISTICS_PATH`; Needs you's "Browser notifications are
on. Settings" → `/settings/general#notifications`; the statistics banner keeps no link.

**D13. Not built: groups and Find.** With four sections neither shows (r4: groups from six,
Find from eight); the thresholds are written into `docs/design/ui.md` (#4821, 4).

**D14. Test layers.** Nothing crosses processes anew: the API, hooks and MCP do not change.
Vitest for the routes, redirects, the list, the arrival's scroll and focus, `CliDefault`,
Your models, Help's menu and `useBeside`; UI e2e (`-m ui`) for the layout at 390/768/1440,
light and dark, the arrival from Needs you and New session, Help on a computer and a phone, and
no sideways scroll; unit pytest for the server texts. The integration tests that quote the
refusal change their text only.
