## 1. The field (D1, D2, D3, D4)

- [x] 1.1 `web/src/TitleEdit.tsx`: the suggestion's rule (D1), the layer with the rest of
  the name (D2, its class in `web/src/styles.css` beside `.title-edit input`), Tab and →
  (D3), the second hint (D4); the module's comment says it. `web/src/Sessions.tsx`: the
  head's and the row's suggestion hints. Check: `make web`.
- [x] 1.2 `web/src/TitleEdit.test.tsx`: Tab on an empty field takes the name, caret at
  the end, nothing sent, field open (Tab takes the name in an empty field); `la` then Tab
  gives `lad-2`; → at the end does the same, → with the caret inside does not; `x`, `LA`
  and `lado-2` typed whole show no rest and Tab is not prevented; Shift+Tab is not
  prevented; a key during composition is not taken; the hint while the suggestion shows
  and after it; a title of the session: no suggestion, the text selected (A session with
  a title). Check: `cd web && npx vitest run TitleEdit`.

## 2. UI e2e

- [x] 2.1 `tests/ui/test_session_head.py`: the pencil on a session without a title, the
  hint names Tab, Tab, type ` (x)`, Enter: the title is `<name> (x)` and the focus is on
  the pencil (Tab, then the human types on); the pencil, type `zz`, Tab: the field closes
  and the title `zz` is saved (Tab with other text leaves the field). Screenshots. Check:
  `uv run pytest -m ui tests/ui/test_session_head.py -k tab`.
- [x] 2.2 `tests/ui/test_session_list.py`: Rename… in a row, type the name's first two
  letters, the rest shows grey, Tab, type ` 2`, Enter: the row shows `<name> 2` (A
  start of the name in a row; the name alone would be no title by session-title's
  rule). Screenshot. Check:
  `uv run pytest -m ui tests/ui/test_session_list.py -k tab`.

## 3. Docs

- [x] 3.1 `docs/design/ui.md` (Session title, Where it is set: the name as a suggestion,
  Tab and →, the hints; LAD-84, mockup `task/lad-84/mockup-title-tab.html`, variant A),
  CHANGELOG.md (a line under 0.40.0 (unreleased)).

## 4. Regression

- [x] 4.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui
  tests/ui/test_session_head.py tests/ui/test_session_list.py`, `openspec validate
  title-takes-the-name --strict`, `openspec validate --specs --strict`.
