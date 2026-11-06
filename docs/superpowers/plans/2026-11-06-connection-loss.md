# A lost connection and actions without an answer Implementation Plan

**Goal:** the buttons that write wait while the connection is lost, and an action with no answer
is settled by what LADO reads once it can.

**Architecture:** `api.ts` turns a request with no answer into `Unreached`; `Live` derives `lost`;
a new store `attempts.ts` keeps each action without an answer, looks at its outcome and repeats
it; the panels only show it. The web UI alone: no API, schema, MCP or CLI change.

**Tech Stack:** React, TypeScript, CSS, vitest, pytest with Playwright.

**Spec:** `openspec/changes/connection-loss/` (AC-1..AC-18, D1-D14),
`docs/superpowers/specs/2026-11-06-connection-loss-design.md`, run artifact
`mockup-connection.html`, the task comment of 2026-11-06. LAD-189 spec §4 only where these are silent.

## Global Constraints

- No strip and no green state: frames g4-* do not rule on them.
- UI texts word for word, from the design doc's table.
- Colours by tokens only: `--warn`, `--warn-ground`, `--danger`, `--danger-ground`, `--muted`.
- The server does not change: nothing under `src/lado/`; the new pytest is under `tests/`.
- Do not touch a stopped session's look (LAD-196) or an iPad's targets (LAD-216).
- CHANGELOG.md: one item under `## 0.45.0 (unreleased)`, by docs/release.md's rules.
- UI tests with `-m ui`; suites with `-n auto`.

## Tests per requirement (capability `connection-loss` unless named)

| Requirement | Unit: vitest (`make web`), pytest | UI e2e (`tests/ui/test_connection.py`) |
|---|---|---|
| the mark says it | `App.test.tsx`, `live.test.ts`: 2 s with fake timers, short drop, 401 | stop the server: 2 s, word at 1440, icon at 390; start it: Live |
| phone-layout: the mark | `Layout.test.tsx`: icon, named | in the row above |
| a screen reader hears it | `App.test.tsx`: the same element before and after the loss, its text, also on 401 | the status region's text across a stop and start |
| the buttons wait | `GateCard` in `WaitingCard.test.tsx`, `Flows.test.tsx`, `NeedsYou.test.tsx`, `Composer.test.tsx` (Enter), `Layout.test.tsx` (Stop, Resume) | chat, Needs you and a run's page; comment and draft intact; Send's tooltip |
| could not confirm | `attempts.test.ts`, each kind's words; `attachFiles` upload line | a failed request per kind, by `page.route` abort |
| settled by the state | `attempts.test.ts`: each look, an `Unreached` look, every 3 s | gate closed and gate open across a real stop and start |
| goes only when known | `attempts.test.ts`, `Flows.test.tsx`: same error on another page | Reject after "Approval not delivered"; going to the run's page |
| Send by the feed | `attempts.test.ts`: found, not found, same words earlier, files alone, field changed | answer lost by `page.route` after the server took it: one message in the feed |
| Retry, closed | `attempts.test.ts` on `closedRefusals.cases.json`; `tests/test_closed_refusals.py` makes each refusal for real | Retry on a gate closed meanwhile |
| Stop and forget | `Layout.test.tsx` or a new `SessionControl.test.tsx` | not needed |
| no raw text | `api.test.ts`: rejection, `AbortError`, `console.error`; `live.test.ts`: `problem` | grep the page's text for `TypeError` while away |
| reads recover | `live.test.ts`, `live.messages.test.ts`: failed reload, resumed stream | a tab opened while away loads after the return |

No integration test: nothing crosses processes but the browser and the server, which UI e2e runs
for real. Regression run: `make lint`, `make test`, `make web`, `uv run pytest -m ui
tests/ui/test_connection.py tests/ui/test_live_updates.py tests/ui/test_gates.py
tests/ui/test_needs_you.py tests/ui/test_phone.py tests/ui/test_session_head.py`,
`openspec validate connection-loss --strict` and the trial archive of `.lado/sdlc.md`.

## Steps

1. The failing tests of the table, unit first, then `test_connection.py`.
2. `api.ts`: `Unreached` (D1). `test_live_updates.py` and `App.test.tsx`, `Layout.test.tsx` move to
   the 2 s.
3. `live.ts`: `lost`, reads that keep and recover (D2, D10); `Shell.tsx`, `icons.tsx`, `styles.css`:
   the mark and its status region
   (D9, D13).
4. `attempts.ts`, `closedRefusals.cases.json`, `tests/test_closed_refusals.py` (D3, D4, D6).
5. `ActionProblem`, `Waits` (D7, D8).
6. `GatePanel`, then `WaitingCard`'s Send answer, each key and look.
7. `Composer` with `Live.lastMessage` (D5).
8. `SessionControl.tsx`, `Launch.tsx` (D11).
9. `docs/design/ui.md`, CHANGELOG.md.
10. Screenshots of each state, light and dark, against the mock-up; the regression run.
