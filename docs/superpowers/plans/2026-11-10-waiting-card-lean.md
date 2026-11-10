# The waiting card, 0.44's look with fewer words: Implementation Plan

**Goal:** The waiting card gets a filled question head, a report that alone scrolls with a fade, a
recommendation block whose text scrolls in its own box under a LADO splitter, chips with titles,
fields of 1 to 8 lines, Skip as a pill, and whole cards on Needs you and Flows; the computer's
composer fold and the one-line recommendation go.

**Architecture:** main's card stays (`waitingParts.tsx`'s three parts, LAD-194); the parts change
role (D1). One `Recommendation` serves every place (D4). The shared `Splitter` gets `hint` (D6)
and a second use in the panel (D5). The server adds `GateInfo.note_by` (D8).

**Tech Stack:** React, TypeScript, CSS, vitest; Python (pydantic models), pytest; Playwright.

**Spec:** `openspec/changes/waiting-card-lean/` (AC-1..AC-13, D1-D16),
`docs/superpowers/specs/2026-11-10-waiting-card-lean-design.md`, session artifacts
`ui-design/gate-card-lean-3/{spec,design-system,mockup.html}`.

## Global Constraints

- Colours by tokens only; the two new ones are `--human-head` and `--count-ink` (D15). UI texts
  word for word from the design doc's Words.
- Do not change the artifact panel, the loop limit's words, the feed's lines, minimize, expand,
  the card's edge (but its `title`), the phone's keyboard behaviour, LAD-195's Retry and waiting
  buttons, LAD-196's stopped note.
- CHANGELOG.md: rename `## 0.45.1 (unreleased)` to `## 0.46.0 (unreleased)` and add one item under
  Improved, by docs/release.md's rules.
- `make web-types` after the model change; commit `web/openapi.json` and `web/src/api.gen.ts`.
- UI tests with `-m ui`; suites with `-n auto`. Edit with edit tools, no sub-agents.

## Review Focus

- The splitter's `max` while the report is already at 56 px, and after the window shrinks: the
  footer never cut, the stored height applied narrowed and kept.
- The fade's class when the content changes without a scroll (a recommendation that comes, a
  chip list that loads, a tab switch): `useMore`'s observer covers the box and its first child.
- A tab of several questions: the line between questions and the footer's line are the same
  width and tone; no double line over the footer.
- A question with no choices: picked `{own: ""}` ahead must not count as answered, and Skip and
  back keep the draft.
- On a phone with a field in focus: the splitter hides with the report; the fold line still shows.
- Flows: `compact` gone, the note shown, the History still under the card; the closed gate's line
  still uses `gateTitle`.

## Tests per requirement

Nothing new crosses processes: `note_by` is read from the note the gate already keeps, so a unit
test of the model suffices, and the existing integration tests of gates stay as they are. Logic
goes to vitest; layout, scroll and drag to UI e2e with the fake agent.

| Requirement (capability) | Unit / vitest | UI e2e (`tests/ui/`, `-m ui`) |
|---|---|---|
| A gate's tab names its step and who wrote its report (cqc) | `test_server_gates.py`: `note_by` with a note, `None` without; `WaitingCard.test.tsx`: tooltip lines, one line without a note | `test_gates.py`: tab text "ship/x 1", tooltip on hover and focus, none on a tap in `test_phone.py`; tab width ≤ 220 / 170 |
| A gate's documents are one row of chips with their titles (cqc) | `WaitingCard.test.tsx`: order, no duplicate, title else short name, no size, no "It reads" | `test_gates.py`: a chip opens the panel; `test_needs_you.py`: a chip is a button and opens the panel |
| The card's splitters have no tooltip (cqc) | `Splitter.test.tsx`: `hint={false}` has no `title`, default keeps it | `test_gates.py`: both separators have no `title`, have their aria-labels |
| The recommendation's height is set by a splitter in the chat (cqc) | `WaitingCard.test.tsx`: present only with a given recommendation in the chat; `prefs.test.ts`: the stored value | `test_gates.py`: drag up 60 px grows `.rec-text`, ↑ grows it, double click back to 82, kept after reload; absent without a recommendation; `test_needs_you.py`, `test_flows_tab.py`: absent |
| A question without choices shows its field at once (cqc) | `WaitingCard.test.tsx`: field with placeholder and aria-label, no Other…, answered only with words | `test_chat.py`: field shown, Send off until typed |
| Skip opens its comment and Send sends it (cqc) | `WaitingCard.test.tsx`: Skip pill after Other…, its field, second click back | `test_chat.py`: the skip with "not now" dismissed (rename the "Skip question" tests) |
| A tab shows whose items it holds (cqc) | `tokens.test.ts`: `--count-ink` on `--raised` ≥ 4.5:1 both themes | `test_gates.py`: count's computed colour |
| An agent's tab lists its questions … Other… and Skip (cqc) | `WaitingCard.test.tsx`: no Other… without free answer | |
| A gate's tab answers the gate at once (cqc) | `WaitingCard.test.tsx`: note without left band class; loop gate's head and buttons | `test_gates.py`: loop limit Continue / Cancel run as before |
| The card keeps the chat in view … (cqc) | | `test_gates.py`: card ≤ 50 % of `.chat` at 1440×900 and 800×800; report ≥ 56 px |
| Needs you shows each session's waiting card (cqc) | `NeedsYou.test.tsx`: `whole` passed | `test_needs_you.py`: no `max-height`, no `has-more` on `.waiting-scroll` and `.rec-text`, all four questions and the long recommendation visible |
| The human can resize the card / The card's chosen height is kept (cqc) | | `test_gates.py`: existing edge tests, "half the chat" in place of 40 % |
| The card's text fields grow … (cqc) | `fieldHeight.test.tsx` / `WaitingCard.test.tsx`: `cardLines` is [1, 8] | `test_gates.py`: one line 40 px, 12 lines → 8; `test_narrow_layout.py`: "Comment (optional)" at 600 |
| A card's field being typed in stays in view (cqc) | | `test_chat.py`: the existing tests with 8 lines |
| The card's footer stays in sight and only its context scrolls (cqc) | | `test_gates.py`: 1440, 768, 390 with a 60-line note; line over the footer without a splitter |
| The card's title is at most two lines (cqc) | `WaitingCard.test.tsx`: no meta; a clamped head has a tooltip of the whole text and is focusable, a short one neither; the report does not repeat it | `test_gates.py`: head outside `.waiting-scroll`, `--human-head` ground, one line high, tooltip on hover of a long question, stays when the report is scrolled; `test_phone.py`: the tooltip on a tap |
| The context says there is more … (cqc) | `waitingParts` / `WaitingCard.test.tsx`: `has-more` by `scrollHeight`, gone at the end; no "↓ more" | `test_gates.py`: mask present, gone at the end |
| A footer taller than its room gives way in order (cqc) | | `test_chat.py`: the 420 px chat with six choices; Send and Skip in sight |
| A single question stands in the footer's choices (cqc) | | `test_chat.py`: 4 and 6 rows |
| Several questions of a tab stand in the context (cqc) | | `test_chat.py`: lines between questions, the same x-range as the footer's line |
| The composer folds while an answer field is open (cqc) | `Chat.test.tsx`, `WaitingCard.test.tsx`: no fold on a computer, fold on a phone with the focus | `test_chat.py`: Other… open at 1440, composer whole; `test_phone.py`: fold lines as before |
| Write to supervisor instead keeps the field's draft (cqc) | `WaitingCard.test.tsx`: on a phone | `test_phone.py` |
| The height the human gave leaves the footer whole (cqc) | | `test_gates.py`: head and footer whole, report 56 px |
| At 601 to 900 px the footer and the composer stay in sight (cqc) | | `test_narrow_layout.py`: the splitter dragged up in place of the opened line |
| A disagreement is a frame and a sign … (lr) | `Recommendation.test.tsx`: aria-labels gate / question, ⚠ tooltip, none when `by` is the lead | `test_gates.py`: `--warn` border colour |
| A long recommendation scrolls in its own box in the chat (lr) | `Recommendation.test.tsx`: `has-more` | `test_gates.py`: 82 px, fade, gone at the end; `test_phone.py`: 42 px |
| The card shows the recommendation as part of the gate or question (lr) | `Recommendation.test.tsx`: head text with and without option, label of the option | `test_flows_tab.py`: the same block on a run's page |
| On a question the recommended choice is picked ahead (lr) | `WaitingCard.test.tsx`: the existing tests, block in place of the line | |
| The card says when a recommendation is being prepared or missing (lr) | `Recommendation.test.tsx`: `asked` line; `missing` and none render nothing | |
| On a phone the recommendation's splitter is easy to take (pl) | | `test_phone.py`: a drag 8 px above the line grows the text; hidden with a field in focus |
| On a phone the composer stays at hand (pl) | | `test_phone.py`: card ≤ 50 % of `.chat` |
| On a phone a field in focus keeps the card … (pl) | | `test_phone.py`: the existing 440 px tests, report and splitter hidden |
| On a phone the card's field and buttons stay above the keyboard (pl) | | `test_phone.py`: 350 and 340 px, Skip as a pill |
| On a phone the waiting card's targets are 44 px (pl) | | `test_phone.py`: tab, choice, Skip, Send 44 px; buttons share the width |
| A run's page shows its gate's whole card (fo) | `Flows.test.tsx`: no "Gate #n · run · state", note and chips shown, kicker in the head | `test_flows_tab.py`: whole recommendation, no splitter, no `max-height` |

End to end, and the regression run before the pull request: `make lint`, `make test`, `make web`,
`uv run pytest -m ui tests/ui/test_gates.py tests/ui/test_chat.py tests/ui/test_phone.py
tests/ui/test_needs_you.py tests/ui/test_flows_tab.py tests/ui/test_narrow_layout.py`,
`openspec validate waiting-card-lean --strict` and the trial archive; CI runs the rest. Screenshots
of each place at 1440, 768 and 390, light and dark, as run artifacts.

## Tasks

### Task 1: The failing tests

Files: the vitest files and UI tests of the table. Write them first, the replaced LAD-194 tests
("Skip question", "↓ more", "Supervisor recommends … ·", the 40 % limit, the computer's fold)
rewritten to the new rules. Run: `make web` (red), `uv run pytest -m ui <files>` (red).

### Task 2: The server's `note_by`

`src/lado/server/models.py`: `GateInfo.note_by: str | None`, set in `gate_info` (D8);
`tests/test_server_gates.py`; `make web-types`. Run: `uv run pytest tests/test_server_gates.py
-n0`, `make web`. Commit.

### Task 3: Tokens and the Splitter

`tokens.css` (D15), `tokens.test.ts`; `Splitter.tsx` `hint` (D6), `Splitter.test.tsx`. Commit.

### Task 4: Head, report, footer

`waitingParts.tsx`: `CardHead`, the report with `has-more` (D1, D3); `styles.css` for
`.waiting-head`, `.waiting-scroll`, the footer's line; the card's 50 % (D2); "↓ more" out. The
tabs' row renamed. Check: the head and height tests. Commit.

### Task 5: The recommendation

`Recommendation.tsx` (D4): one block, aria-labels, ⚠, `asked` / `missing`; `RecommendationBar`,
`oneLine` out. Check: `Recommendation.test.tsx`. Commit.

### Task 6: The recommendation's splitter

`WaitingCard.tsx` / `GateCard.tsx`: the splitter (D5), `prefs.ts` `lado.recommendationHeight`.
Check: the drag, keys, reset and reload tests. Commit.

### Task 7: Tabs and chips

The tab's tooltip and width (D7); chips with titles in one row (D9), `Attachments` `titled`; the
note's look (D10). Check: tab and chip tests. Commit.

### Task 8: Fields and questions

`cardLines` (D11), placeholders; Skip pill, no-choice field, the lines between questions (D12).
Check: field and question tests. Commit.

### Task 9: The composer

`foldLine` only for the phone (D13); `Chat.tsx`, `Composer.tsx` as needed. Check: the fold tests.
Commit.

### Task 10: Needs you and Flows

`whole` (D14) on Needs you; Flows' `Now` with the head and kicker, `compact` out. Check:
`test_needs_you.py`, `test_flows_tab.py`. Commit.

### Task 11: The phone

The 2-line box, the 24 px splitter, the splitter hidden while typing, 44 px targets. Check:
`test_phone.py`. Commit.

### Task 12: Docs and the regression run

`docs/design/ui.md`: The waiting card (head, report, footer; the height; the recommendation's
splitter; chips; fields; Skip; the composer's fold on a phone only), The supervisor's
recommendation (one block), Needs you, Flows' run page, Look (the two tokens), Splitter (`hint`).
CHANGELOG.md. The regression run above; screenshots as run artifacts. Commit.
