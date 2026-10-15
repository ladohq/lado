## 1. The button

- [ ] 1.1 `web/src/icons.tsx`: `BetweenIcon`, two speech bubbles facing each other (the
  mockup's paths: `M3 4.5h10.5v7.5H8.25L5.25 14.5V12H3z` and `M16.5 9H21v7.5h-2.25V19l-3-2.5H10.5V15`,
  or the developer's equal), with its one-line comment as the others have. Check: it
  renders in the button (1.2).
- [ ] 1.2 `web/src/Sessions.tsx`, `Activity`: the `<label className="switch">` with its
  checkbox becomes `<Tooltip tip={…}>` around `<button type="button"
  className="icon-button between-toggle" aria-label="Messages between agents"
  aria-pressed={agentMessages}>` with `BetweenIcon`; a click flips and stores the
  choice as the checkbox did. The tooltip's two lines (`tooltip-line` as `AgentTip`'s):
  off "Messages between agents: hidden" / "Click to also show what agents write to each
  other."; on "Messages between agents: shown" / "Click to show only your conversation
  with the agents.". The comment above `Activity` says what the button shows.
  `web/src/styles.css`, next to `.team-row`: `.between-toggle` 26 px square, no border,
  transparent, muted; hover as `.tab-find .icon-button:hover`; `[aria-pressed="true"]`
  as `.team-chip[aria-pressed="true"]` with the icon in `--action`; the icon 18 px; the
  `.team-row` comment no longer says "switch". Check: vitest cases next to the Activity
  tests: the button's name and `aria-pressed`, the tooltip's texts in both states after
  hover (`TOOLTIP_DELAY_MS`) and at once on focus, gone on Esc (AC-1, AC-2); the cases in
  `Chat.test.tsx` (the toggle, the windows, kept after a remount) and `Agents.test.tsx`
  (All in Activity) moved from the checkbox to the button and passing (AC-3).

## 2. Tests in the browser

- [ ] 2.1 `tests/ui/test_chat.py`: the button instead of the checkbox; before clicking
  it, hover it, expect the tooltip's "Messages between agents: hidden", and save a
  screenshot (`shot`), then one with it pressed, light and dark. `tests/ui/test_layout.py`
  (the terminal panel open, the column narrow): the button is on the chips' first line
  and, with three agents, the last chip too (AC-4). Check: `uv run pytest -m ui
  tests/ui/test_chat.py tests/ui/test_layout.py`.

## 3. Docs

- [ ] 3.1 `docs/design/ui.md`: the Activity tab's paragraph describes the button
  (Messages between agents, its icon, pressed look, the tooltip's texts; decided
  2026-10-15, LAD-77, mockups `task/lad-77/mockup-placement.html` variant Б and
  `task/lad-77/mockup-agent-messages.html` for the texts), and the agent's page's **All
  in Activity** presses Messages between agents. `grep -rn "Show agent messages"` over
  `web/src`, `tests`, `docs/design` finds nothing. Check: read through against the code.
- [ ] 3.2 `CHANGELOG.md` under `## 0.40.0 (unreleased)`: a line: the Activity tab's
  "Show agent messages" checkbox is now a small icon at the end of the team's row,
  "Messages between agents", with a tooltip that says what it shows; the agents' chips
  no longer wrap for it.

## 4. Regression

- [ ] 4.1 `make web` (vitest, tsc, build; no API change), `make lint`, `uv run pytest -m
  ui tests/ui/test_chat.py tests/ui/test_layout.py tests/ui/test_agents_tab.py`,
  `openspec validate agent-messages-switch-label --strict` (AC-5).
