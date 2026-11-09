# Design: settings-one-rule

The approved look is the run artifact `mockup-settings-rule.html`, options 1A and 2A (the human's
answer #4907). The code is the one PR #256 (LAD-238) merges: `Telemetry.tsx`,
`ModelSettings.tsx`, `ModelSources.tsx`. Nothing here is above the provider layer: the web UI
only, the same for every agent CLI.

## Decisions

**D1. Statistics' switch is Notifications' switch.** `StatisticsSetting` renders the same markup
as `NotificationsSetting` (`.sw-hit` > `input.sw[type=checkbox][role=switch]`, the row's name a
`label` for it, the state line its description); checked is `choice === "on"` with no `off_by`;
disabled while the info is not read, `off_by` is set or there is no endpoint; a change posts
`on` or `off`. The row loses `.srow-wide`: a switch fits beside its name at every width.
Rejected: a third look for "not chosen" (a mixed switch), which no browser control draws and
the row's line already says.

**D2. × asks nothing.** `ModelRow`'s question goes with its state (`asking`, `backToCross`) and
the `.mx-confirm` row of Your models; × always calls `removeModel`, and the answer's `cleared`
tells whether a default went, as today for a page gone stale.

**D3. One Undo for both places.** The removed-model state (`Removed`: the model, `wasDefault`,
the problem, busy, expired), its undo (save the model again, then set the default again by the
id it got back) and `UNDO_MS` live once, in `useModelSettings` or a small module beside it, and
both Your models (`UndoRow`) and the ticks use it. The tick's line is the same component as the
row's text and Undo, laid out in the tick's list. Rejected: a second copy in `ModelSources.tsx`
(two timers and two undo paths that drift).

**D4. Where the tick's Undo shows, and the focus.** Under the unticked CLI's line in the open
model's list of CLIs (`.mx-sub`), keyed by the tick (`tickKey`); the focus stays on the tick,
Undo is the next stop of Tab. The model leaves Your models at once with no Undo row there:
Undo shows only where the human acted. A tick again saves the model as "A renamed model
unticked keeps its name" says, takes the line away and sets no default. A list closed, or the
page left, drops the line as the rows of Your models are dropped today.

**D5. The line's lifetime.** As Your models': Undo goes after `UNDO_MS` (10 s) unless it runs
or was refused; `Removed <name>.` stays until the human's next change on the page (`onTouch`).
Nothing moves under the pointer: the line grows the open list's area below the tick only, and
the page's scroll anchor (`useScrollAnchor`) already holds the element acted on.

**D6. Test layers.** Nothing crosses processes: the API and the core do not change. Vitest for
the switch's states, × without a question, the tick's Undo and its timer; UI e2e (`-m ui`) for
the switch on a real page and for unticking a default and its Undo against the real server.
