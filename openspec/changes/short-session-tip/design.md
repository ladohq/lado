## Context

`SessionTip` (`web/src/Sessions.tsx`) is the card of both a list row and a strip icon, in the
UI's `Tooltip` with `side="right"`. The task removes the row's and shortens the icon's.

## Decisions

### D1. The row drops its `Tooltip`; the icon keeps it, `side="right"`

The row's title wraps and is never cut, so a "tooltip when cut" (`Tooltip`'s `when`) would
never show: it would be dead code. The icon keeps `side="right"` so that the tooltip does not
cover the strip's other icons.

### D2. `SessionTip` becomes the icon's short tooltip

It keeps `.tip-top` (title, name) and `TipState`, and the line `Needs you: …` under a trouble;
the facts (`<dl class="tip-facts">`), the hint (`HOW_TO_GO_ON`) and `KITS_SHOWN` go. The state
line still needs the stopped text from `useRanParts`; `ran` is no longer read there.

### D3. The width is the UI tooltip's

The rules `.tooltip:has(.session-tip)` (360 px) and `.session-tip`'s `max-height` and
`overflow` go: the tooltip is as wide as its text up to `.tooltip`'s `max-width` (320 px), and
two lines need no height bound. `.tip-facts` and `.tip-hint` stay for the agents' popups
(`Team.tsx`).

### D4. The tooltip-focus tests move to the strip's icon

The tests of openspec tooltip-focus used a list row as the trigger; the row has no tooltip now,
so they fold the list (Collapse sessions) and use the session's icon, which has the same
`Tooltip` and the same focus paths.
