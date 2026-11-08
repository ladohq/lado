# Settings as pages Implementation Plan

**Goal:** Settings becomes four pages beside a list, each CLI's default model moves into its row on
Agent CLIs, Model servers keeps the servers and one table of the human's models, and the rail gets a
cogwheel and one Help menu in place of Report a bug.

**Architecture:** One list of sections (`settingsSections.ts`) drives a layout route
`/settings/:section`, its list and its redirects. Today's sections become pages; the model settings'
state moves into a hook both pages use, and the picker part of a CLI card moves into Agent CLIs'
rows. Help is the UI's own `Menu`, placed beside the rail. The server changes only texts.

**Tech Stack:** React 19, react-router, TypeScript, CSS, vitest (`make web`), pytest with Playwright
(`-m ui`), Python for the texts.

**Spec:** `openspec/changes/settings-pages/` (AC-1..AC-9, D1-D14),
`docs/superpowers/specs/2026-11-08-settings-pages-design.md` (the words, the widths), run artifacts
`r5-mockup.html`, `r5-design-system`, `r4-concise-spec`, `r4-concise-brief`, `r3-models-spec`,
`mockup-help.html`, and the r5 spec and brief attached to LAD-238.

## Global Constraints

- Colours by tokens only (`web/src/tokens.css`); no new token. The only new icon is `HelpIcon`;
  `SettingsIcon` is redrawn (D10).
- UI texts word for word from the design doc's "Words, exactly"; texts not listed stay as today.
- Phone controls at least 44 px; no sideways scroll at 390, 768, 1440; a picked model's name never
  cut, its id gives way first (`.mp-value .mp-title { flex-shrink: 0 }`, `.mp-id { flex-shrink: 1 }`).
- No API, schema, MCP tool or CLI option change; `web/openapi.json` and `web/src/api.gen.ts` change
  only by docstrings (`make web-types`, commit both).
- CHANGELOG.md: one item under `## 0.45.0 (unreleased)`, group New, by docs/release.md's rules.
- UI tests with `-m ui`; suites with `-n auto`; edit with edit tools; no sub-agents.
- A mockup's CSS is a reference, not code to paste: write the rules into `web/src/styles.css` under
  the existing Settings sections, reusing today's class names where the r5 design system keeps them.

## Review Focus

- A window resized across 600 px on `/settings` or a section: the list and the page swap without a
  loop of redirects and without losing an open picker's or form's state (round 1: width changes keep
  state).
- `/settings/agent-clis#claude` reached while the rows are still `checking…`: the scroll and focus
  happen once the row is read, and a poll a second later does not steal the focus the human moved.
- A model removed on Model servers that was a CLI's default, then the human goes to Agent CLIs: the
  picker shows the CLI's settings (the page reads the model settings on open).
- Help's menu on the folded rail near the window's bottom on a short tablet (560 px high): the menu
  stays inside the window.
- Esc in Help's menu inside the phone drawer: the menu closes, the drawer stays, the focus is on
  Help; a second Esc closes the drawer.

## Tests per requirement

| Requirement (capability) | vitest (`make web`) | UI e2e (`tests/ui/`, `-m ui`) | pytest |
|---|---|---|---|
| A page per section beside a list (settings-pages) | `Settings.test.tsx`: routes from `SETTINGS_SECTIONS`, `/settings` → general above 600 px, focus on h2 on change | `test_settings_pages.py`: four pages at 1440, 768 | |
| The list shows names and icons only | `Settings.test.tsx`: no state text with a login missing | shots in light and dark | |
| On a phone the list is a page | `Settings.test.tsx` with `usePhone` true | `test_settings_pages.py` at 390: list, page, `‹ Settings` | |
| Old addresses lead to the new pages | `Settings.test.tsx`: each row of the table, `replace` | one old hash per page, history length unchanged | |
| A setting is a row; notifications switch | `Notifications.test.tsx` (new): switch, each refusal text | General at 390: switch target 44 px | |
| A CLI's row holds its default model; not installed | `Providers.test.tsx`: picker per installed CLI, none for not installed, the line + Use <CLI>'s settings, the no-servers line | `test_providers_section.py`: pick saves, warning under picker | |
| A link to a CLI's row focuses its login button | `Providers.test.tsx`: focus, once, unknown hash | `test_settings_pages.py`: Needs you → focus; Launch "Log in first" → focus | |
| Model servers page; Your models table; default mark; rename; narrow (model-settings-page) | `ModelSettings.test.tsx`, `ModelCards.test.tsx` rewritten for the table | `test_models_section.py`: table at 1440, two lines at 768 and 390 | |
| Help menu, current on /report, phone drawer, cogwheel (rail-help) | `Shell.test.tsx`: items, hrefs, Esc focus, current class; `Menu.test.tsx`: `placeBeside` | `test_settings_pages.py` or `test_report_bug_page.py`: Help → Report a bug; `test_phone.py`: drawer | |
| Report a bug in Help (bug-report), drawer (phone-layout), rail height (session-layout) | `ReportBug.test.tsx`, `Layout.test.tsx` | `test_report_bug_page.py`, `test_phone.py`, `test_main_screen.py` (rail height: Settings within) | |
| Texts of refusals and doctor (provider-logins, configured-models) | | | `test_logins.py`, `test_runtime.py`, `test_cli.py`, `test_server_launch.py`, `test_doctor.py`, `test_model_settings.py`; integration `test_provider_logins.py` texts |
| Statistics page (usage-telemetry) | `Telemetry.test.tsx`: each state's line; `SystemPanel.test.tsx`: link | Statistics at 390: segments stretch | |
| Launch notes and picker foot (session-model) | `ModelPicker.test.tsx`, `Launch.test.tsx` | `test_launch_model.py` texts | |
| Docker headers (container) | | | `test_docker.py` |

Regression: `make lint`, `make test`, `make web`, then each changed UI file alone with `-m ui`, then
`uv run pytest -m ui -n auto tests/ui` once, and `uv run pytest -m integration -n auto
tests/integration/test_provider_logins.py`. CI runs the rest.

---

### Task 1: Server texts name the new pages

**Files:** Modify `src/lado/logins.py:1,41`, `src/lado/model_settings.py:76,699,779`,
`src/lado/model_check.py:18`, `src/lado/state.py:1054`, `src/lado/doctor.py:186`,
`src/lado/server/provider_check.py:1`, `src/lado/server/model_entries.py:1`,
`src/lado/server/models.py:479,517,697,759`, `src/lado/server/launch.py:292,327`,
`src/lado/server/app.py:870,885`, `docker/compose.yaml:28`, `docker/Dockerfile:12`,
`web/openapi.json`, `web/src/api.gen.ts`. Test: `tests/test_logins.py`, `tests/test_runtime.py`,
`tests/test_cli.py`, `tests/test_server_launch.py`, `tests/test_doctor.py`,
`tests/test_model_settings.py:1190`, `tests/test_docker.py:923`,
`tests/integration/test_provider_logins.py:98,115,143`.

**Interfaces:** Produces `logins.SETTINGS == "Settings → Agent CLIs"`.

- [ ] **Step 1:** In each test above replace `Settings → Agent CLIs and environment` by
  `Settings → Agent CLIs`, `Settings → Models` (the refusal) by `Settings → Model servers`, and in
  `test_docker.py` `"Agent CLIs and environment"` by `"Settings → Agent CLIs"`. Run
  `uv run pytest -n auto tests/test_logins.py tests/test_docker.py tests/test_model_settings.py`: FAIL.
- [ ] **Step 2:** `logins.py`: `SETTINGS = "Settings → Agent CLIs"`; `model_settings.py:699`:
  `"rename the saved one: Settings → Model servers"`; the headers of `docker/compose.yaml` and
  `docker/Dockerfile` name `Settings → Agent CLIs`; every docstring and comment above names
  Settings → Agent CLIs or Settings → Model servers. Run `make web-types`.
- [ ] **Step 3:** `make lint`, `make test`, `uv run pytest -m integration -n auto
  tests/integration/test_provider_logins.py`: PASS.
- [ ] **Step 4:** Commit: "Server texts name Settings → Agent CLIs and Model servers (LAD-238)".

### Task 2: Paths and icons

**Files:** Modify `web/src/paths.ts:62-67`, `web/src/icons.tsx:128-133`, `web/src/SystemPanel.tsx:59`.
Test `web/src/paths.test.ts` (new).

**Interfaces:** Produces `agentClisPath(cli?: string): string`, `GENERAL_PATH = "/settings/general"`,
`MODEL_SERVERS_PATH = "/settings/model-servers"`, `STATISTICS_PATH = "/settings/statistics"`,
`DOCS_URL = "https://github.com/ladohq/lado#readme"`, `GITHUB = "https://github.com/ladohq/lado"`
(moved), `HelpIcon`. Removes `PROVIDERS_PATH`, `PROVIDERS_ANCHOR`, `MODELS_ANCHOR` (their users change
in Tasks 3, 6, 7; do this task's removal with them if the build needs it to stay green).

- [ ] **Step 1:** Test: `agentClisPath()` is `/settings/agent-clis`, `agentClisPath("claude")` is
  `/settings/agent-clis#claude`, a name is encoded with `encodeURIComponent`. `make web`: FAIL.
- [ ] **Step 2:** Implement:

```ts
// Settings' pages (Settings.tsx, settingsSections.ts). Agent CLIs scrolls to a CLI's row at
// #<provider name> and focuses its login button (Providers.tsx).
export const GENERAL_PATH = "/settings/general";
export const MODEL_SERVERS_PATH = "/settings/model-servers";
export const STATISTICS_PATH = "/settings/statistics";
export const agentClisPath = (cli?: string) => `/settings/agent-clis${cli ? `#${encodeURIComponent(cli)}` : ""}`;

// Help's links on the rail (Shell.tsx); GITHUB also in the system panel.
export const DOCS_URL = "https://github.com/ladohq/lado#readme";
export const GITHUB = "https://github.com/ladohq/lado";
```

  `SettingsIcon`: the cogwheel of `mockup-help.html` (its `<path d="M21.02 10.17L…Z"/>` and
  `<circle cx="12" cy="12" r="3"/>`); `HelpIcon`: `<circle cx="12" cy="12" r="8.5"/>`,
  `<path d="M9.7 9.6a2.4 2.4 0 1 1 3.3 2.2c-.6.3-1 .8-1 1.5v.6"/>`, `<path d="M12 16.6v.1"/>`.
- [ ] **Step 3:** `make web`: PASS. Commit: "Paths of Settings' pages, a cogwheel and a Help icon (LAD-238)".

### Task 3: Sections, routes and redirects

**Files:** Create `web/src/settingsSections.ts`, `web/src/Settings.test.tsx`. Modify
`web/src/Settings.tsx`, `web/src/App.tsx:36`, `web/src/styles.css` (Settings: `.settings` grid,
`.snav`, `.snav-item`, `.spage`, `.spage-head`, `.sback`). Test `web/src/App.test.tsx`.

**Interfaces:** Produces `SETTINGS_SECTIONS: readonly { slug: string; name: string; icon: () =>
JSX.Element; Page: () => JSX.Element }[]`, `settingsRedirect(pathname: string, hash: string): string
| null`, and the page head `SettingsHead({ children? })` (h2 from the section's name, focus per D3,
`‹ Settings` on a phone). Consumes Task 2's paths. The pages are today's components until Tasks 4-7
replace them.

- [ ] **Step 1: Write the failing tests** in `Settings.test.tsx`: each row of the redirect table of
  the design doc maps by `settingsRedirect` (`/settings` + `#models` → `/settings/model-servers`,
  `/settings/kits` → `/settings`, `/settings/general` → `null`); rendering `/settings/statistics`
  shows the list of four names with `aria-current="page"` on Statistics and the h2 `Statistics`;
  `/settings` renders General above 600 px and the list alone with `usePhone` true; a click on Model
  servers moves the focus to its h2; the list has no text but the four names.
- [ ] **Step 2:** `make web`: FAIL.
- [ ] **Step 3: Implement.**

```ts
// Settings' sections, the one list (docs/design/ui.md, Settings): the list beside the page,
// the routes, the pages' headings and the old addresses read it.
export const SETTINGS_SECTIONS = [
  { slug: "general", name: "General", icon: SettingsIcon, Page: GeneralPage },
  { slug: "agent-clis", name: "Agent CLIs", icon: AgentCliIcon, Page: Providers },
  { slug: "model-servers", name: "Model servers", icon: ServerIcon, Page: ModelSettings },
  { slug: "statistics", name: "Statistics", icon: ShieldIcon, Page: StatisticsSetting },
] as const;

// The one page's anchors and the earlier designs' addresses (openspec settings-pages).
const OLD_HASHES: Record<string, string> = {
  "#providers-and-environment": "/settings/agent-clis",
  "#models": "/settings/model-servers",
  "#statistics": "/settings/statistics",
  "#notifications": "/settings/general#notifications",
  "#appearance": "/settings/general",
};
const OLD_SLUGS: Record<string, string> = {
  "agent-clis-and-environment": "agent-clis",
  models: "model-servers",
  "usage-statistics": "statistics",
};

export function settingsRedirect(pathname: string, hash: string): string | null {
  const slug = pathname.replace(/^\/settings\/?/, "").replace(/\/$/, "");
  if (!slug) return OLD_HASHES[hash] ?? null;
  if (SETTINGS_SECTIONS.some((s) => s.slug === slug)) return null;
  return OLD_SLUGS[slug] ? `/settings/${OLD_SLUGS[slug]}` : "/settings";
}
```

  `App.tsx`: `<Route path="settings" element={<Settings />}><Route index element={<SettingsIndex />} /><Route path=":section" element={<SettingsSection />} /></Route>`.
  `SettingsIndex`: an old hash → `<Navigate replace>`; else above 600 px `<Navigate to={GENERAL_PATH} replace />`;
  on a phone nothing (the layout shows the list). `SettingsSection`: `settingsRedirect` → `<Navigate replace>`, else the
  section's `Page`. `Settings`: `useTitle("Settings")`, `<div className="settings">` with
  `<nav className="snav" aria-label="Settings sections">` (each item `NavLink`, icon `aria-hidden`,
  name) and `<Outlet />`; on a phone the nav only at the index, the outlet only on a section.
  Styles by `r5-design-system` and the r4 spec §1 (grid `232px minmax(0,680px)` gap 32; 601-900 px
  `196px 1fr` gap 20; phone one column, items 52 px with a chevron).
- [ ] **Step 4:** `make web`: PASS. Commit: "Settings is a page per section beside a list (LAD-238)".

### Task 4: General as setting rows

**Files:** Modify `web/src/Settings.tsx` (`GeneralPage`), `web/src/Notifications.tsx:84-127`,
`web/src/styles.css` (`.srows`, `.srow`, `.srow-text`, `.srow-name`, `.srow-desc`, `.srow-ctl`,
`.srow-wide`, `.sw`, `.sw-hit`). Create `web/src/Notifications.test.tsx`. Test
`web/src/NeedsYou.test.tsx`.

**Interfaces:** Produces the row classes and `Switch` (an `<input type="checkbox" role="switch"
className="sw">`) used by Tasks 5 and 7.

- [ ] **Step 1:** Tests: General has two rows, Theme's three radios without a `title`; Browser
  notifications is `role="switch"` labelled by its name, described by `When something waits for you
  and this tab is hidden.`; each refusal's text of the design doc; `#notifications` scrolls the row
  into view; Needs you's `Settings` link goes to `/settings/general#notifications`. `make web`: FAIL.
- [ ] **Step 2:** Implement by the r4 spec §2-§4 (rows, switch) and the design doc's words; the
  refusal constants of `Notifications.tsx` change once and Needs you shows them too.
- [ ] **Step 3:** `make web`: PASS. Commit: "General: theme and notifications as setting rows (LAD-238)".

### Task 5: Statistics as one row

**Files:** Modify `web/src/Telemetry.tsx` (`StatisticsSetting`, top comment), `web/src/SystemPanel.tsx:390`.
Test `web/src/Telemetry.test.tsx`, `web/src/SystemPanel.test.tsx`.

- [ ] **Step 1:** Tests: the row's name `Send anonymous statistics and errors to LADO's maintainers`;
  each state's one line of the design doc (not chosen: neither segment checked; environment and no
  endpoint: disabled); What the next report sends only when sending; the panel's Statistics row links
  to `/settings/statistics`. `make web`: FAIL.
- [ ] **Step 2:** Implement: one `.srow.srow-wide`, segments Send / Don't send; the about paragraph
  and the heading's tag go (r4 spec §4).
- [ ] **Step 3:** `make web`: PASS. Commit: "Statistics: one row with its state (LAD-238)".

### Task 6: Model servers and the shared model settings

**Files:** Create `web/src/useModelSettings.ts`, `web/src/CliDefault.tsx`. Modify
`web/src/ModelSettings.tsx` (becomes the page Model servers), `web/src/ModelSources.tsx` (heads,
leads, the r4 texts), `web/src/styles.css` (`.mx-mrow.yours`, the 900 px two-line rule). Test
`web/src/ModelSettings.test.tsx`, `web/src/ModelCards.test.tsx`, `web/src/ModelSources.test.tsx`.

**Interfaces:** Produces

```ts
export function useModelSettings(): {
  entries: Entries | null;
  problem: string | null;
  reads: Record<string, Read>;      // each CLI's list as read here
  reload: (given?: Entries) => Promise<void>;
  onRead: (cli: string) => void;    // as today's picker opening
  removed: Record<string, Removed>; // Undo rows, by folded name
  remove: (model: ConfiguredModelInfo, wasDefault: boolean) => void;
  undo: (gone: Removed) => Promise<void>;
};
export function CliDefault(props: { row: ProviderLogins; settings: ReturnType<typeof useModelSettings> }): JSX.Element | null;
```

  `CliDefault` is today's `CliCard` minus its head and its models table: the `ModelPicker`
  (`where="settings"`, `aria-label="Default model of <CLI>"`), `.mc-notes` with the warnings and their
  buttons, `OtherName`; for a CLI not installed, `null` without a default, else the line `Default model:
  <name> — cannot run: not installed` and `Use <CLI>'s settings` (`clearModelDefault`). `lostDefaults`,
  `onDefaultGone`, `unfolded`, `FOLD_ABOVE`, `keepAtTop`, `INTRO`, `LEAD`, `LEAD_NO_MODELS`, `AgentClis`
  and `CliCard` go (D5, D8).

- [ ] **Step 1: Tests.** Model servers: h2 `Model servers`, no intro; `Servers <n>` with its lead;
  Your models hidden with no model, `None yet: …` with servers and no model; one `role="table"`
  `aria-label="Your models"`, sorted by the logins' order of CLIs then name, a model of an unknown CLI
  last with its saved name; `Kilo CLI · default` on a default; From `⚠ lmstudio` after a probe found it
  down; rename, ×, Undo as before (move the cases of `ModelCards.test.tsx` that are about the table);
  the removal of a default asks first and leaves no note on another page. `CliDefault`: picks save at
  once; the warnings of a default in trouble; not installed with and without a default. `make web`:
  FAIL.
- [ ] **Step 2: Implement** the hook by moving today's state and callbacks out of `ModelSettings`
  unchanged, then the page and `CliDefault`. The table by the r5 spec §4 (grid `minmax(0,1.3fr)
  minmax(0,1fr) minmax(0,.8fr) minmax(0,.8fr) 28px`; at 900 px and narrower no head row, two lines).
- [ ] **Step 3:** `make web`: PASS. Commit: "Model servers: servers and one table of your models (LAD-238)".

### Task 7: Agent CLIs rows with the default model and the arrival

**Files:** Modify `web/src/Providers.tsx`, `web/src/NeedsYou.tsx:108`, `web/src/Launch.tsx:901`,
`web/src/LoginSheet.tsx:1`, `web/src/LoginWindow.tsx:1`, `web/src/fakes.ts:434`, `web/src/styles.css`
(`.pv.cli`, `.cli-model`, `.cli-ml`, `.cli-pick`, `.cli-more`, `.pv-tested` in `--warn`). Test
`web/src/Providers.test.tsx`, `web/src/NeedsYou.test.tsx`, `web/src/Launch.test.tsx`.

**Interfaces:** Consumes `useModelSettings`, `CliDefault`, `agentClisPath`. Needs you calls
`navigate(agentClisPath(agent.provider))`; Launch `navigate(agentClisPath(noLogin.name))` (the provider `ProviderNote` names as not logged in).

- [ ] **Step 1: Tests.** The page: h2 `Agent CLIs` with ↻; lede `Changes apply to agents started
  afterwards.`; a row `li#<cli>` per CLI with `aria-labelledby` its name; `LADO tested <v>`; the
  waiting line in singular and plural; `No agent CLI installed. Install one to start a session.`;
  `Couldn't read your login shell: <why>. Details: lado doctor`; a picker per installed CLI, none for
  one not installed; the no-servers line only with no server. Arrival: with `#claude` and rows read,
  `scrollIntoView` is called once with `block: "center"` and the focus is on Claude Code's `Log in…`;
  a CLI logged in gets the focus on its name; a second poll does not call `scrollIntoView` again; an
  unknown hash calls nothing. Needs you's `Log in…` goes to `/settings/agent-clis#claude`; Launch's
  `Log in first` to `/settings/agent-clis#codex`. `make web`: FAIL.
- [ ] **Step 2: Implement.** The arrival:

```ts
// Arrival at #<cli> (Needs you, New session): once its row is read, scroll it to the middle and
// focus its login button, else its name; once per hash, so a poll never moves the human's focus.
const handled = useRef<string | null>(null);
useEffect(() => {
  const cli = decodeURIComponent(hash.slice(1));
  if (!page || !cli || handled.current === hash) return;
  const row = document.getElementById(cli);
  if (!row || !page.providers.some((p) => p.cli.name === cli && p.ready)) return;
  handled.current = hash;
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  row.scrollIntoView({ block: "center", behavior: still ? "auto" : "smooth" });
  (row.querySelector<HTMLElement>(".pv-login") ?? row.querySelector<HTMLElement>(".pv-name"))?.focus();
}, [page, hash]);
```

  Rows by the r5 spec §3 (grid `minmax(0,1fr) auto`, `.cli-model` across both columns: label 104 px
  + picker up to 360 px; phone stacks). The login button gets `className="pv-login …"`; the name
  `className="pv-name"` with `tabIndex={-1}`.
- [ ] **Step 3:** `make web`: PASS. Commit: "Agent CLIs: each CLI's login and default model in its row (LAD-238)".

### Task 8: The launch window's words

**Files:** Modify `web/src/ModelPicker.tsx:628`, `web/src/LaunchModel.tsx:245,282`. Test
`web/src/ModelPicker.test.tsx`, `web/src/Launch.test.tsx`.

- [ ] **Step 1:** Tests: the foot reads `The default comes from Settings → Agent CLIs.`, its link
  `/settings/agent-clis` with `target="_blank"`; the note `<CLI>'s default model, from Settings →
  Agent CLIs.`; the lost model's line `… no longer in Settings → Model servers. …`. `make web`: FAIL.
- [ ] **Step 2:** Change the three texts and the href (`agentClisPath()`). `make web`: PASS.
- [ ] **Step 3:** Commit: "The launch window names Settings → Agent CLIs (LAD-238)".

### Task 9: Help on the rail

**Files:** Modify `web/src/Shell.tsx:24-34,211-213`, `web/src/Menu.tsx`, `web/src/styles.css`
(`.help-menu`, `.rail-link.is-current`, drawer rules). Test `web/src/Shell.test.tsx`,
`web/src/Menu.test.tsx`, `web/src/Layout.test.tsx`, `web/src/ReportBug.test.tsx`.

**Interfaces:** `MenuItem` gains `icon?: ReactNode` and `divided?: boolean`. Produces

```ts
// Where a menu `size` big goes beside a rail item `anchor`: right of it, its bottom on the
// anchor's bottom, kept MARGIN inside the window (Help on the rail).
export function placeBeside(
  anchor: { right: number; bottom: number },
  size: { width: number; height: number },
  viewport: { width: number; height: number },
): CSSProperties {
  const left = Math.min(anchor.right + 8, viewport.width - MARGIN - size.width);
  const top = Math.max(MARGIN, Math.min(anchor.bottom - size.height, viewport.height - MARGIN - size.height));
  return { position: "fixed", left: Math.max(MARGIN, left), top };
}
export function useBeside(anchor: RefObject<HTMLElement | null>, floating: RefObject<HTMLElement | null>, open: boolean): CSSProperties | undefined;
```

  In the drawer the menu is placed above Help across the drawer's width by CSS (`.drawer .help-menu`),
  not by `useBeside`.

- [ ] **Step 1: Tests.** `placeBeside`: right of the anchor; near the bottom kept inside; near the
  right edge kept inside. Shell: the rail has no `Report a bug` link; Help (`aria-haspopup="menu"`)
  opens a menu of `Documentation` (href `DOCS_URL`, new tab), `GitHub` (href `GITHUB`, new tab),
  `Report a bug` (navigates to `/report`); the first item focused; Esc closes and focuses Help; a press
  outside closes; on `/report` Help has `is-current`; folded, Help has `title="Help"`; on a phone,
  choosing an item closes the menu and the drawer, Esc closes only the menu. `make web`: FAIL.
- [ ] **Step 2: Implement** `HelpButton` in `Shell.tsx` with `Menu`, `useDismiss` and `useBeside`;
  the look of `mockup-help.html` frames 1-5.
- [ ] **Step 3:** `make web`: PASS. Commit: "Help on the rail: Documentation, GitHub, Report a bug (LAD-238)".

### Task 10: Browser tests

**Files:** Create `tests/ui/test_settings_pages.py`. Modify `tests/ui/test_providers_section.py`,
`tests/ui/test_models_section.py`, `tests/ui/test_phone.py`, `tests/ui/test_report_bug_page.py`,
`tests/ui/test_launch.py`, `tests/ui/test_launch_model.py`, `tests/ui/test_main_screen.py`.

- [ ] **Step 1:** Change every `/settings` address and section name of those files to the pages
  (Agent CLIs, Model servers), the rail's Report a bug to Help → Report a bug, and the Models cards to
  the rows and the table. Keep each test's point; drop only what tests a removed requirement (the
  anchor that stays at the top, a card's fold) and say which in the build report.
- [ ] **Step 2:** `test_settings_pages.py`: at 1440, 768 and 390, light and dark, each page:
  `document.documentElement.scrollWidth == innerWidth`, phone controls `>= 44` px high, no
  `.mp-title` with `scrollWidth > clientWidth`; the redirects (one per old address, `history.length`
  unchanged); Needs you's `Log in…` with a waiting fake agent → `document.activeElement` is Claude
  Code's `Log in…` and the row is in the viewport; Launch's `Log in first` likewise; Help at 1440 and in
  the 390 drawer → Report a bug. Screenshots of each page at each width into
  `<temp dir>/lado-ui-shots/`.
- [ ] **Step 3:** Each file alone: `uv run pytest -m ui <file>`: PASS; then `uv run pytest -m ui -n
  auto tests/ui`: PASS.
- [ ] **Step 4:** Commit: "Browser tests of Settings' pages and Help (LAD-238)".

### Task 11: Documents

**Files:** Modify `docs/design/ui.md` (Structure: the addresses; "### Agent CLIs and environment" →
"### Agent CLIs" and "### Models" → "### Model servers" as built, with the rows, the arrival and the
table; "### Usage statistics" → Statistics; "### Report a bug": in Help; "### System panel": the
Statistics link; a new "### Settings" with the list, the redirects, the groups and Find thresholds
(six, eight) as not built yet, and "### Help"), `docs/cli.md:291,306,642,713,761`,
`docs/install.md:270,297,435`, `docs/design/agents.md:216,229,465`, `docs/design/modules.md:883,1237`,
`docs/release.md:182`, `CHANGELOG.md`.

- [ ] **Step 1:** Write them true to the code; `grep -rn "Agent CLIs and environment\|Settings →
  Models\|Usage statistics" docs src web/src tests docker README.md` finds nothing but the archive
  and `docs/epics/` (history, left as it is).
- [ ] **Step 2:** CHANGELOG.md under `## 0.45.0 (unreleased)`, New: "**Settings in pages.** General,
  Agent CLIs, Model servers and Statistics each have a page; a CLI's default model is set in its row
  on Agent CLIs, and Help on the rail opens the documentation, GitHub and Report a bug."
- [ ] **Step 3:** `make lint`, `make test`, `make web`, `openspec validate settings-pages --strict`,
  the trial archive of `.lado/sdlc.md`'s Checks: PASS. Commit: "Docs: Settings' pages and Help (LAD-238)".
