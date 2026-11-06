## 1. The failing tests

- [ ] 1.1 vitest by the plan's table: `api.test.ts`, `live.test.ts`, `live.messages.test.ts`,
  `attempts.test.ts`, `App.test.tsx`, `Layout.test.tsx`, `WaitingCard.test.tsx`, `Composer.test.tsx`,
  `Flows.test.tsx`, `NeedsYou.test.tsx`. Run: `make web`.
- [ ] 1.2 `tests/ui/test_connection.py` by the plan's table. Run: `uv run pytest -m ui
  tests/ui/test_connection.py`.

## 2. Requests and the store

- [ ] 2.1 `Unreached` in `api.ts` (D1). Check: `api.test.ts`, AC-14.
- [ ] 2.2 `lost` in `live.ts` (D2). Check: `live.test.ts`, AC-2.
- [ ] 2.3 Reads that keep and recover (D10). Check: `live.test.ts`, AC-15.

## 3. The mark

- [ ] 3.1 The mark in `Shell.tsx`, `NoNetworkIcon`, CSS, the phone (D9). Move
  `test_live_updates.py` and the vitest cases to the 2 s. Check: AC-1, AC-3.

## 4. Attempts

- [ ] 4.1 `attempts.ts` and when it looks (D3, D4). Check: `attempts.test.ts`.
- [ ] 4.2 `closedRefusals.cases.json`, `tests/test_closed_refusals.py` (D6). Check: `make test`, AC-12.
- [ ] 4.3 `ActionProblem`, `Waits` (D7, D8). Check: AC-5.

## 5. The actions

- [ ] 5.1 `GatePanel`: lock, words, the attempt (D3, D7). Check: AC-4, AC-6 to AC-10.
- [ ] 5.2 `WaitingCard`'s Send answer. Check: AC-6, AC-8.
- [ ] 5.3 `Composer`, `Live.lastMessage` (D5). Check: AC-4, AC-11.
- [ ] 5.4 `SessionActions`, `StopPopover` (D11). Check: AC-4, AC-16.
- [ ] 5.5 Resume's head button and the Launch window (D11). Check: AC-4, AC-6.

## 6. Documents and the look

- [ ] 6.1 `docs/design/ui.md` by the design doc's list; CHANGELOG.md.
- [ ] 6.2 A screenshot of each state in the light and dark theme, as run artifacts. Check: AC-17.
- [ ] 6.3 The plan's regression run.
