## Context

The row's status in words is `Status` in `web/src/Sessions.tsx`
(`<span class="status status-<status>">`), rendered only for `tmux_gone` and `loop_down`
(`session.status !== "running" && session.status !== "stopped"`). `.status::before` draws a
7 px dot in `currentColor`; the trouble rule turns it into a hollow ring and the text grey.

## Decisions

### D1. The colour by the existing rule, the dot by the base rule

`.status-tmux_gone, .status-loop_down { color: var(--danger); }`, and the rule
`.status-tmux_gone::before, .status-loop_down::before` (transparent ground, 1.5 px border)
goes: `.status::before` then draws a full dot in `currentColor`, which is `--danger`. No change
to `Sessions.tsx`: the class names already say the status. Not `.danger-text` added in the
component: the colour of a status belongs with its other status rules.

### D2. `.status-stopped` goes

`Status` is never rendered for a stopped session, so the selector styles nothing. Only what is
used (AGENTS.md).

### D3. The test is a UI e2e test

jsdom (vitest) does not compute the stylesheet's colours; the lowest layer that sees them is a
browser (AGENTS.md, Testing, layer 4). The test compares the computed colours with `--danger`
as the page resolves it, so it holds in both themes without copying the hex values.

## Risks

- `--danger` text on the panel's ground: `web/src/tokens.test.ts` already checks every text
  colour's contrast of 4.5:1 on its grounds in both themes; `--danger` is one of them.
