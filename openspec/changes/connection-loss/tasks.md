## 1. The failing tests

- [x] 1.1 vitest by the plan's table: `api.test.ts`, `live.test.ts`, `live.messages.test.ts`,
  `attempts.test.ts`, `App.test.tsx`, `Layout.test.tsx`, `WaitingCard.test.tsx`, `Composer.test.tsx`,
  `Flows.test.tsx`, `NeedsYou.test.tsx`. Run: `make web`. The store's cases went to a new
  `live.lost.test.ts`, the panels' to a new `connection.test.tsx`, which drives them all on one
  real store; the gate's panel is one component, so Flows and Needs you are covered there and
  in `test_connection.py`.
- [x] 1.2 `tests/ui/test_connection.py` by the plan's table. Run: `uv run pytest -m ui
  tests/ui/test_connection.py`.

## 2. Requests and the store

- [x] 2.1 `Unreached` in `api.ts` (D1). Check: `api.test.ts`, AC-14.
- [x] 2.2 `lost` in `live.ts` (D2). Check: `live.lost.test.ts`, AC-2.
- [x] 2.3 Reads that keep and recover (D10). Check: `live.lost.test.ts`, AC-15.

## 3. The mark

- [x] 3.1 The mark in `Shell.tsx`, `NoNetworkIcon`, CSS, the phone (D9). Move
  `test_live_updates.py` and the vitest cases to the 2 s. Check: AC-1, AC-3.
  `test_live_updates.py` needed no change: its wait outlasts the 2 s.
- [x] 3.2 The status region of `LinkState` (D13). Check: `App.test.tsx`, AC-17.

## 4. Attempts

- [x] 4.1 `attempts.ts` and when it looks (D3, D4). Check: `attempts.test.ts`.
- [x] 4.2 `closedRefusals.cases.json`, `tests/test_closed_refusals.py` (D6). Check: `make test`, AC-12.
- [x] 4.3 `ActionProblem`, `Waits` (D7, D8). Check: AC-5.

## 5. The actions

- [x] 5.1 `GatePanel`: lock, words, the attempt (D3, D7). Check: AC-4, AC-6 to AC-10.
- [x] 5.2 `WaitingCard`'s Send answer. Check: AC-6, AC-8.
- [x] 5.3 `Composer`, `Live.lastMessage` (D5). Check: AC-4, AC-11.
- [x] 5.4 `SessionActions`, `StopPopover` (D11). Check: AC-4, AC-16.
- [x] 5.5 Resume's head button and the Launch window (D11). Check: AC-4, AC-6.

## 6. Documents and the look

- [x] 6.1 `docs/design/ui.md` by the design doc's list; CHANGELOG.md.
- [x] 6.2 A screenshot of each state in the light and dark theme, as run artifacts. Check: AC-18.
- [x] 6.3 The plan's regression run.
