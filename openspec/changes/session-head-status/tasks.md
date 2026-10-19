## 1. The one rule

- [x] 1.1 `web/src/Sessions.tsx`: `sessionMark(session)` returns the mark (`needs-you`,
  `working`, `idle`, `stopped`, `tmux_gone`, `loop_down`) and its words, from `isLive`,
  `status`, `waiting` and `busy`; the words of the running marks are the card's
  (`running · 2 of 3 agents working`, `running · idle · 3 agents`), of `needs-you`
  `needs you · ` and the row's line (`about`), of the rest `STATUS`. `groupOf`, `tracked`,
  `workWord`, `SessionTip`'s status part, `SessionRow` and `StripIcon` take it in place of
  their own tests; the row's and the icon's looks and names stay as they are. Vitest:
  a table over the six states checks the mark and the words (requirement "A session's
  mark comes from one rule"), and the existing list and card tests stay green unchanged.

## 2. The head

- [x] 2.1 `web/src/Sessions.tsx`: `StatusDot` takes the session and draws its mark: the
  list's `dot activity-working` / `dot activity-idle` for working and idle, a diamond in
  `--human` for needs you, `session-dot-stopped` / `-tmux_gone` / `-loop_down` as before;
  its tooltip and accessible name are the mark's words. `HeadLine` and `PhoneHead` pass
  the session. `web/src/styles.css`: the head's marks keep the dot's size and place in
  the top bar (`.session-dot`'s margins), the diamond defined once with the waiting
  agent's (`.dot-waiting`) or beside it, no new colour.
- [x] 2.2 `PhoneHead`: the details sheet's `state` is the mark's words and the run time.
- [x] 2.3 Vitest, `web/src/Layout.test.tsx`: for each of the six states the head's dot and
  the session's row (or icon) agree, both named from `sessionMark` (AC-1, AC-5); the
  screenshot's case, a question waiting and the agents idle, gives the diamond named
  `needs you · 1 question` and no `activity-working` or plain `session-dot` in the head
  (AC-2); working and idle names and classes (AC-3); a feed change of `busy` turns the
  head's dot as the row's (requirement "The session's head shows the list's mark",
  scenario "The head follows the session"). The test now named "…the running dot with no
  word…" says the idle ring instead. `web/src/SessionDetails.test.tsx`: the phone's head
  dot is named by the mark's words; the sheet's state line starts with them (AC-4,
  phone-layout's "The state in the sheet").

## 3. On a phone, in a browser

- [x] 3.1 `tests/ui/test_phone.py::test_the_top_bar_is_one_line_and_the_name_opens_the_details`:
  its gated session waits at a gate, so the bar's dot is named `needs you · 1 gate` (not
  `running`); a tap on the dot shows that tooltip; the sheet contains the same words
  (AC-4). Run with `-m ui`.

## 4. Documents

- [x] 4.1 `docs/design/ui.md`: Sessions (the row's paragraph: the mark is `sessionMark`'s,
  shared with the head), the session's head paragraph ("The dot: …": the list's mark,
  needs you an orange diamond, its words in the tooltip), Session head's first items, and
  Phone layout's sheet line; dated 2026-10-19, LAD-108, mockup artifact
  `task/lad-108/mockup-head-status.html`.
- [x] 4.2 CHANGELOG.md under `## 0.42.0 (unreleased)`: the session's head shows the same
  state as the session list (needs you, working, idle), on a phone too.

## 5. Checks

- [x] 5.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_phone.py
  tests/ui/test_session_head.py tests/ui/test_session_list.py` pass; CI is green (AC-6).
