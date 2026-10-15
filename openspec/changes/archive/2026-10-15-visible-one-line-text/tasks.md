## 1. The rule (D1, D5)

- [x] 1.1 `src/lado/text.py`: `hidden`, `first_hidden`, `named`, `one_line`;
  `tests/test_text.py`: each category (a tab, `\n`, U+2028, U+2029, U+202E, U+2066,
  U+200B, U+FEFF), U+200D kept (a family emoji), Cyrillic and CJK kept, `named` of a Cc
  and of U+202E, `one_line` of each. Check: `uv run pytest tests/test_text.py -n0`.

## 2. Refused: the title and agents' one-line texts (D2, D4)

- [x] 2.1 `runtime.set_title` through `text.first_hidden`; tests: U+202E, U+2028, U+200B
  refused with the named character and the title unchanged, a ZWJ emoji title stored.
  Check: `uv run pytest tests/test_runtime.py -n auto -k title`.
- [x] 2.2 `runtime._check_summary` (summary, question) and `ask_human`'s choices; tests per
  text. Check: `uv run pytest tests/test_runtime.py tests/test_mcp_server.py -n auto -k
  "summary or question or choice"`.
- [x] 2.3 `runs.start`'s `human_language` (review F1), `runs.advance`'s `note_summary` and `artifacts._line` (title, summary); tests.
  Check: `uv run pytest tests/test_runs.py tests/test_artifacts.py -n auto`.

## 3. Cleaned: the human's texts (D2, D3, D5)

- [x] 3.1 `runtime._human_text` through `text.one_line` (the chat message and an own
  answer), the body kept when the line was cleaned; tests: U+2028 and U+202E in the first
  line, the body holds the text as written.
  Check: `uv run pytest tests/test_runtime.py -n auto -k "human or answer"`.
- [x] 3.2 `runs._answer_note`, `runs.force` (note and body), the loop limit's cancel
  reason; tests. Check: `uv run pytest tests/test_runs.py -n auto -k "answer or force or
  limit"`.
- [x] 3.3 `artifacts.upload`'s title through `text.one_line` (an ESC and U+202E in a file
  name); test. Check: `uv run pytest tests/test_artifacts.py -n auto -k upload`.

## 4. No copy left, docs

- [x] 4.1 `grep -rn '"Cc"' src/lado` finds only `text.py`.
- [x] 4.2 AGENTS.md (Layout: `text.py`; `lado title`'s rule), `docs/design/ui.md` (the
  human's text), CHANGELOG.md (a line under `## 0.40.0 (unreleased)`).
- [x] 4.3 Regression: `make lint`, `make test`, `openspec validate --specs --strict`.
