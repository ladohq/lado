Task: LAD-68

## Why

A session's title and other one-line texts reach the human's terminal (`lado ls`,
`lado log`, `lado answer`, `lado artifacts list`) and the agents' tmux windows (a
message's summary is typed there). Their check refuses or cleans only control characters
(Unicode category Cc). Three other kinds of characters pass:

- U+2028 and U+2029 (line and paragraph separators, categories Zl and Zp): the text is no
  longer one line; a typed summary can break into two;
- bidi controls (U+202A–U+202E, U+2066–U+2069, category Cf): they reorder how the text
  is shown and can leak onto the rest of a line of `lado ls` (Trojan Source);
- zero-width characters (U+200B, U+FEFF and other Cf): a title looks empty or equal to
  the name while it is not.

Root cause: there is no one rule of "one line of visible text". The Cc check is written
five times in `runtime.py` (title, the human's summary, a summary, a question, a choice),
`runs.py` and `artifacts.py` check only `\n`, and a gate's comment, a `lado flow-set`
reason and an uploaded file's name are not checked at all (an ESC in a file name reaches
`lado artifacts list` as is).

Options weighed:

- A. Refuse more characters in the title only: cheapest, and the other texts keep the
  gap and five diverging copies of the check.
- B. One rule in one module, used by every one-line text: refused where the text is one
  field the writer gives (a title, an agent's summary), cleaned where it is a line taken
  from a longer text of the human whose whole text stays in the body. **Chosen.**
- C. Escape at print time: dozens of print sites (CLI, log, popup, typed lines), each new
  one a chance to forget; the stored data stays unsafe for the UI and the agents.

## What Changes

- **One rule** (`lado/text.py`, standard library only): a character is *hidden* when its
  Unicode category is Cc, Zl, Zp or Cf, except U+200D ZERO WIDTH JOINER (it joins emoji
  sequences). Every check below asks it; no other copy of the Cc check is left.
- **The session's title** (`runtime.set_title`, `lado title`, the UI's rename) refuses a
  text with a hidden character, naming the first one:
  `a title is one line of visible text: U+202E RIGHT-TO-LEFT OVERRIDE is not allowed`.
  The UI shows the core's text as today.
- **Agents' one-line texts** are refused the same way, with the character named and where
  the details go: `send_message`'s `summary`, `ask_human`'s `question` and each choice,
  `flow_advance`'s `note_summary`, `flow_start`'s `human_language`, `write_artifact`'s
  `title` and `summary`.
- **The human's longer texts** are cleaned, never refused, for their one-line form: the
  summary of the human's chat message and of an own answer to a question, the next step's
  note made from a gate's comment, the note made from a `lado flow-set` reason (and the
  reason a loop limit's cancel stores), and the title of an uploaded file's artifact. A
  hidden Cc, Zl or Zp character becomes a space, a hidden Cf character is removed. The
  whole text, as the human wrote it, stays in the body whenever the one-line form is not
  exactly it (cleaned, cut or more lines), so nothing is lost.

Not a minor feature: no new command, option, field or schema; refusing more is a fix.
The release is a **patch** (a line under the open `## X.Y.Z (unreleased)` of
CHANGELOG.md).

## Out of scope

- Bodies, details and other multi-line texts (message bodies, `ask_human`'s details,
  `note_body`, artifact content, `recommend`'s text): they are read with
  `read_messages` / `read_artifact` or in `less`, not typed as a line; `lado log` prints a
  body indented under its line. Cleaning them would change what the human wrote.
- Titles already stored with such characters: no migration. Titles came with 0.39.0, a
  day before this change, and only the human sets one, so such a title is unlikely; a
  stored one prints as it is until it is set again.
- Allowing more of Cf (U+200C ZERO WIDTH NON-JOINER, U+200E/U+200F direction marks,
  U+00AD SOFT HYPHEN, emoji tag characters): kept out for one simple rule; one line of
  text for a label does not need them. Can be widened when a real user needs one.
- Escaping at print time (option C above).
- Names (sessions, agents, artifacts, kits): already restricted to a slug or a name
  pattern.

## Impact

- `src/lado/text.py` (new), `runtime.py` (`set_title`, `_check_summary`, `ask_human`'s
  choices, `_human_text`), `runs.py` (`start`'s language, `advance`'s note, `_answer_note`, `force`, the loop
  limit's cancel), `artifacts.py` (`_line`, `upload`'s title).
- No API model, CLI option, MCP tool signature or schema change; the error texts change.
- AGENTS.md (Layout: `text.py`; the title's rule in `lado title`), `docs/design/ui.md`
  (the human's text: "hidden characters" for "control characters"), CHANGELOG.md.
- Tests: unit only (`tests/test_text.py`, the callers' tests); nothing crosses processes.
