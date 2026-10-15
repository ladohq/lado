## 1. The switch

- [ ] 1.1 `web/src/Sessions.tsx`, `Activity`: the label reads "Messages between agents";
  the `<label className="switch">` is wrapped in `Tooltip` with the text "Also show the
  messages agents send each other. Off: only your conversation with the agents."; the
  comment above `Activity` says what the switch shows. The tooltip shows on the
  checkbox's keyboard focus (see proposal.md, Decisions). Check: vitest cases next to the
  Activity tests: the checkbox's name, the tooltip after hover (`TOOLTIP_DELAY_MS`) and at
  once on focus, gone on Esc (AC-1, AC-2); the existing cases in `Chat.test.tsx` and
  `Agents.test.tsx` renamed to the new name and passing (AC-3).

## 2. Tests in the browser

- [ ] 2.1 `tests/ui/test_chat.py` and `tests/ui/test_layout.py`: the checkbox they look
  for is "Messages between agents"; in `test_chat.py`, before checking it, hover the
  switch, expect the tooltip's text, and save a screenshot (`shot`) light and dark.
  Check: `uv run pytest -m ui tests/ui/test_chat.py tests/ui/test_layout.py`.

## 3. Docs

- [ ] 3.1 `docs/design/ui.md`: the Activity tab's paragraph names the switch **Messages
  between agents** with its tooltip (decided 2026-10-15, LAD-77, mockup
  `task/lad-77/mockup-agent-messages.html`, variant 1), and the agent's page's **All in
  Activity** turns on Messages between agents. `grep -rn "Show agent messages"` over
  `web/src`, `tests`, `docs` finds nothing. Check: read through against the code.
- [ ] 3.2 `CHANGELOG.md` under `## 0.40.0 (unreleased)`: a line: the Activity tab's
  switch "Show agent messages" is now "Messages between agents", with a tooltip that
  says what it shows.

## 4. Regression

- [ ] 4.1 `make web` (vitest, tsc, build; no API change), `make lint`, `uv run pytest -m
  ui tests/ui/test_chat.py tests/ui/test_layout.py tests/ui/test_agents_tab.py`, `openspec validate
  agent-messages-switch-label --strict` (AC-4).
