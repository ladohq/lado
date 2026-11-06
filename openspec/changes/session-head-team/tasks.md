## 1. The failing tests

- [ ] 1.1 vitest by the plan's table: `teamFit.test.ts`, `Team.test.tsx`, `prefs.test.ts`,
  `Chat.test.tsx`, `Layout.test.tsx`, `Terminals.test.tsx`, `Agents.test.tsx`. Run: `make web`.
- [ ] 1.2 UI e2e by the plan's table: new `tests/ui/test_team_head.py`, and `test_layout.py`,
  `test_chat.py`, `test_launch.py`, `test_status_marks.py`, `test_narrow_layout.py`, `test_phone.py`,
  `test_tabs.py`. Run: `uv run pytest -m ui <files>`.

## 2. The rules

- [ ] 2.1 `teamFit.ts`: `fitLabel`, `agentMarks`, `chooseLevel` (D1). Check: `teamFit.test.ts`.
- [ ] 2.2 `useAgentMessages` in `prefs.ts` (D6). Check: `prefs.test.ts`, `Agents.test.tsx`.

## 3. The team in the head

- [ ] 3.1 The head's view of `Team`, its place in `HeadLine`, the new CSS (D4, D9, D12). Check: AC-1, AC-2.
- [ ] 3.2 The trial and the title's limit (D2, D3). Check: AC-3 to AC-6.
- [ ] 3.3 The list button and the team's list (D11). Check: AC-7.
- [ ] 3.4 The popup, on the head and the strip. Check: AC-8.
- [ ] 3.5 Marks and rings on the strip, the focus ring (D10). Check: AC-9.
- [ ] 3.6 The toolbar's keyboard and names (D9). Check: AC-10.

## 4. The tab bar and the feed

- [ ] 4.1 `Yours | All` in `SessionTabs`, `data-short`, the phone's icon (D6, D7). Check: AC-11, AC-12.
- [ ] 4.2 No gap under the tabs on Activity, no team row above a phone. Check: AC-13.

## 5. The composer

- [ ] 5.1 `.composer-frame`, the line out of the flow, the hint by the focus (D8). Check: AC-14.
- [ ] 5.2 `to <agent>` only for an agent other than the supervisor; a phone's empty line. Check: AC-15.

## 6. Documents

- [ ] 6.1 `docs/design/ui.md`: Session head, Activity, Composer, Terminal, the widths; the team row
  of 601 to 900 px. Check: read against the code.
- [ ] 6.2 `CHANGELOG.md`: one item under `## 0.45.0 (unreleased)`, by docs/release.md's rules.
- [ ] 6.3 The Purpose of `openspec/specs/session-head/spec.md` names the team, and that of
  `activity-agent-messages` says `Yours | All` at the tab bar's end. Check: read.

## 7. Regression

- [ ] 7.1 The settings' Checks, the UI suite's changed files with `-m ui`, the trial archive. Check:
  all green in `build-report`.
- [ ] 7.2 Screenshots of each changed screen as run artifacts, both themes.
