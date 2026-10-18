# Forget stopped sessions — design

Task: LAD-92. Change: `openspec/changes/forget-stopped-sessions/` (proposal AC-1…AC-9,
delta `specs/session-forget/spec.md`, `design.md` D1–D8). Mockup: run artifact
`task/lad-92/mockup-bulk-forget.html` (variant 1 and the Stop popover chosen; variant 2,
ticks in the list, turned down).

## Goal

The human clears out the stopped sessions they no longer need in one go, or picks
several, and can stop and forget a running session in one press. The single Forget… in a
session's head stays as it is.

## Screens

### The session list

- The Stopped band: chevron · `STOPPED` · count · bin button ("Forget stopped
  sessions…", danger colour, 26 px). Folded or open, searching or not. No button on
  Needs you or Running, none on the strip.

### The window "Forget stopped sessions?"

- "Their history (messages, runs, notes, gates) is deleted. This cannot be undone."
- A bordered list that scrolls inside (max 50vh): first "All N", then one row per stopped
  session the list showed when the window opened: tick · title or name (bold) · `stopped
  2 d ago` (muted) · on the right `1 open run` / `N open runs` (human colour). A row whose
  preview was refused: no tick, off, the core's reason under it in danger colour.
- `<details>` "Left on disk: N worktrees of M sessions (remove them yourself if you need
  to)", folded; its list `<path> · branch <branch>` of the ticked sessions.
- When a ticked session has open runs: the switch "Also forget their N open runs (a, b)"
  and, while off, "While this is off, a and b stay."
- Buttons: Cancel (focused first) · `Forget N sessions` (danger; off while loading or at 0).
- Pressing: rows of the counted sessions show a mark (✓ forgotten, ✕ the reason, … the
  one in progress); `Forgetting K of N…`; the rest off. End: all forgotten → closes; any
  refused → one Close button. The open session forgotten → `/sessions`.

### The Stop popover

- `Stop session "<name>"?`, its consequences as today, then Cancel · `Stop and forget`
  (danger, tooltip "Stops it, then deletes its history for good") · `Stop <name>`.
- With open runs: `Stop and forget` off and the muted line "It has open runs: stop it,
  then forget it from the Stopped list."
- Pressed: `Stopping…`, `Forgetting…`, then `/sessions`; a refused forget shows its
  reason in the popover, the session stays stopped.

## Flow of a bulk forget

```
open      → snapshot = Stopped group as shown (search applied)
          → parallel getForgetPreview(each) → open_runs, worktrees | reason
tick/All  → counted = ticked ∧ previewed ∧ (no open runs ∨ switch on)
press     → for name in counted (list order):
               forgetSession(name, force = switch on ∧ has open runs)
               row ← forgotten | reason
end       → all ok: close; else stay with Close; open session forgotten: /sessions
```

## What does not change

Server, API, schema, CLI, the core's rules, the single Forget… window, the list's rows,
the strip. No `make web-types`.

## Version

A UI feature: a minor. main already holds `## 0.41.0 (unreleased)`; the line goes there.
