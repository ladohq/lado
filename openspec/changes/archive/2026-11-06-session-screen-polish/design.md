## Context

Spec: LAD-189 spec §7 and group 7 of `lad-189-mockup.html` (mini blocks, no frames of their own); the
human's answers #4114 and #4126; run artifact `mockup-session-tweaks.html`. Root cause and options:
proposal, Why. Sizes and words: `docs/superpowers/specs/2026-11-06-session-screen-polish-design.md`.

Against AGENTS.md: everything lies in the web UI and in one API field that names no CLI, so it works
with every provider (neutral core). A kit's flows come from `kit.flows` through the path Details
already uses, and the type's word lives beside `kindOf` (one source of truth). The summary moved out
of the row stays in the tooltip and the panel, and nothing a kit lists is left out (no silent drops).
One field is added because the empty tab reads it (only what is used). ROADMAP.md's coming stages
touch nothing here: the desktop app and ACP keep the same page.

The change bumps nothing: 0.45.0 is already the next minor.

## Decisions

**D1. The width picks the component.** `ArtifactsTable` measures itself with `useWidth` and renders
the table at 720 px and over, else the list. The stacked-cells CSS goes. Rejected: `@container` alone,
since the tooltip and the row's words depend on the width, and a `display: block` table is no list to
a screen reader. 720 stays the limit, not the spec's 600: the human's answer 1, as between 600 and 720
the table does not fit and a third look would remain. A first paint before the measure shows the list.

**D2. Grouping is one pure function.** `groupByScope(artifacts, order)` in `artifacts.ts` keeps the
input's order in a group, so its rows come newest first, and the groups go by `order` (D3).
`GROUPS_FROM = 100` counts the session's
artifacts before any filter, so a filter never flips the look. `ArtifactsTable` applies it to the
filtered list while the scope filter is All scopes.

**D3. Folds.** `prefs.ts` keeps `lado.artifactGroups`: `{ <session>: { <scope>: "open" | "folded" } }`,
by `storedGroups`' rule that any other value is the default. A scope with no stored value takes its
default: folded for a run `isOpen` calls ended, otherwise open. `Artifacts` watches the `runs` list;
until it is loaded, or if it fails, nothing is folded by default, so a failed list hides nothing. The
default is taken once per scope, on entering the tab or when its group first appears, never for a
group with the focus: a run that ends must not fold rows under the human (Design QA, F2). The
groups' order is taken the same way (the human's answer to Design QA, F1 and F8): Session and open
runs above ended runs, each by freshness, kept while the tab is open, a new group at the end of its
part. A run that ends keeps its place until the tab is entered again. A
forgotten session's entry stays in the browser: a few bytes, not worth a hook into Forget. Rejected:
"the newest group open", which folds and opens groups under the human's eyes as runs write.

**D4. Group headings are `GroupHead`.** Neutral tone, with `fold`. A scope is a run's exact name, so
the heading adds a class that drops the capitals and uses mono; Session keeps the word. This is the
session list's band, as the spec says, not the mini block's quiet line. In the list each group is a
`section` with `aria-labelledby`, as `ListGroup`. In the table each is a `tbody`, its first row a
`th colSpan={6} scope="rowgroup"` holding the heading. `ListGroup` itself does not fit: its rows are
`Link`s with no way to open the panel.

**D5. The list's row.** One `ArtifactItem`: the icon tile, then two lines. The link stretches over the
row by `::after`, so a hover or click anywhere is the link's: one `Tooltip` (the summary, `null` for
none, silent on a tap), and `open` as `Row` has it, shared. In a group the name is the bare name; a
search still reads `full_name`. Summary on a phone: the panel, as the tooltip stays silent on a tap.

**D6. The type's word.** `KINDS` moves to `artifacts.ts` beside `kindOf` as one table of filter label
and row word: Document, Code or text, Image, HTML, File. The filter's labels do not change.

**D7. The title against the H1.** `ArtifactView` reads a Markdown record's text with `useText` and
hands it to `ArtifactBody` as `read`, so there is one read; `ArtifactTab` still reads in `Text`.
`sameHeading(text, title)` in `artifacts.ts` takes the first non-blank line, needs `# `, strips closing
`#`s and compares trimmed text without regard to case. A Markdown record hides the title until the
read ends, so it never flashes and goes. Rejected: dropping the H1 from the body, which changes the
document, and asking the server, which has no reason to parse Markdown.

**D8. Full page.** `useMatch` on the session's artifacts route tells the panel it lies over that tab.
The link keeps its address and its document icon, and its label becomes Full page. The frame's ⤢ is
not used: that icon is Expand's in the same bar, and two buttons alike doing different things would
mislead. Expand does not change.

**D9. The phone's bar.** `usePhone()` decides, not `compact`. The bar composes Download and Copy link
as today's icon buttons, then a button `aria-label="More actions"` with `aria-haspopup="menu"` that
opens the existing `Menu` under it (`useBelow`, `useDismiss`, Esc gives the focus back). Open in new
tab is a `href` item; the page's link is an `onSelect` item that navigates. So `ArtifactActions` takes
a `phone` prop leaving Open in new tab out, and its link is built once in a helper for both. The menu
always has an item, so "⋯" always shows.

**D10. The pill.** `where` in `ArtifactView` becomes `step ${record.state}` for a run's record. The
store sets `run` and `state` together, so a run's record always has a state.

**D11. The empty tabs.** `.empty` gets `<p class="empty-title">` and `<p class="empty-line">`, used by
both tabs. `RunsOverview` shows it in place of the groups when the session has no run and the search
is empty. It reads `getSessionAbout` once, in a `useEffect` of a component mounted only then. Text:
`flowsLine(kits)`, a pure function: `null` kits, or any `valid: false` and no flows: no list; all valid
and no flows: the no-flows line; else the list. A kit without flows is left out of the list.

**D12. `SessionKitInfo.flows`.** `list[str]`, `list(kit.flows)` in `launch._session_kit`, `[]` on both
failure paths; `make web-types` commits both generated files.

**D13. The run's task.** `firstLine(run.task)` beside `entry`, a `<span class="run-task">` between the
name and `run-about`, in `entry` and in `card`. Only a non-blank first line shows. `run-task` is 13 px
`--muted`, one line cut with "…". On an orange card it keeps the card's text colour rule.

**D14. Notices.** One rule list in `styles.css`, with the alert icon as a `::before` CSS mask on
`currentColor`, so none of the 175 uses of `.problem` changes:

| Level | Selectors |
|---|---|
| Error: `--danger-ground`, `--danger`, icon | `.problem`, `.update-bad`, `.field-problem`, `.started-problems`, `.kit-problem`, `.market-error`, `.term-notice`, `.artifact-missing` |
| Warning: `--warn-ground`, `--warn`, icon | `.share-warning`, `.update-warning` (Update's "An older LADO may refuse lado.db"), `.pv-warn`, `.pv-none`, `.kit-warning` |
| Stripe off only, text stays `--ink` | `.field-note.warn` (its ⚠ is its text), `.field-note.bad` (its `!` is drawn) |
| Stay | `.login-fail blockquote`, `.chat-body blockquote`, `.chat-gate.open`, `.rec`, `.gate-note`, `.waiting-tab.on`, `.chat-fold > .chat-body`, `.kit-who`, every 1 px divider |

Padding 8 12, radius 6, icon 16 px at the first line. `.pv-warn` and `.pv-none` leave `--human`, which
is only for what waits for the human; `.kit-warning` leaves `--danger`: it is a warning. A mask holds
no colour, so `tokens.test.ts`'s rule stands. `.term-notice` and `.field-problem` sit in tight rows:
4 8 padding there. Rejected: a `Notice` component, 190 edits in 31 files for the same pixels.

**D15. F24.** `facts` and the `.feed-facts` CSS go. The open row shows `<p class="feed-took">` under
the line, then `.feed-detail` only when there is a body or the human's "No comment.". The chevron and
`aria-expanded` stay.

**D16. F27.** `Stop and forget` renders only when `loaded !== null && !hasRuns`. The line moves below
`.question-buttons`, with the spec's words. A button that appears when the preview arrives beats a
dangerous one that shows and then goes. `stopAndForget` keeps its flow.

**D17. F26.** `.term-ask::backdrop { background: var(--scrim); }`. The dialog already uses
`showModal()`, in the top layer over the terminal.

**D18. One pull request.** F20 is the biggest part and the rest is small, and they share
`styles.css`, so splitting them buys conflicts. It is the task's last pull request. The commits keep
the brief's order, so F20 could still go alone.

## Risks

- `.problem` on `--danger-ground` shows on 31 screens at once. A page where `.problem` was not an error
  would read wrong: the UI test walks the known ones, and the build report names any found.
- A row's stretched link covers the row: the title's text cannot be selected by a drag. The wide table
  keeps that, and the panel shows it.
