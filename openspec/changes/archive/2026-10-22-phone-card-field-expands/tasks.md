## 1. The card

- [x] 1.1 `web/src/WaitingCard.tsx`: in a session's chat on a phone, the focus coming into
  an answer field of the panel expands the card (D1); an expansion from a field keeps the
  focus in it and scrolls it into the list's view, the expand button's still focuses the
  tab (D2); the header comment of the module says so.
- [x] 1.2 `web/src/styles.css`, section "Phone layout": an expanded card hides the
  session's tabs and the Team row (D3), with a comment naming LAD-126.
- [x] 1.3 `web/src/WaitingCard.test.tsx` (unit, the lowest layer for the card's state):
  on a phone (`FakeScreen.phone()`) in the chat, focusing a gate's comment expands the
  card and the field keeps the focus; tapping Other… expands it with the own answer
  focused; after the field's blur the card stays expanded; on a computer and without
  `chat` (Needs you) a field's focus does not expand it; Expand by its button still
  focuses the shown tab. Run `make web`.

## 2. The UI e2e tests

- [x] 2.1 `tests/ui/test_phone.py` (UI e2e: the layout needs a browser), at 402×874 with
  the fake visual viewport (`FAKE_VIEWPORT`) moved to 400 px: a gate waiting, a tap on its
  comment field expands the card, the field is focused, the field and Approve / Reject lie
  within 400 px, and the session's tabs (`nav` "Session sections") and the Team row are
  hidden (AC-1).
- [x] 2.2 The same file: a question waiting, a tap on Other… expands the card, its field
  focused, the field and "Send answer to supervisor" within 400 px (AC-2).
- [x] 2.3 The same file: the viewport moved back to 874 px leaves the card expanded;
  Collapse the card shows it above the composer with the session's tabs and the Team
  row (AC-3); expanding by the button on a phone hides them too (AC-4). Screenshots of
  the keyboard state and of the closed keyboard as run artifacts.
- [x] 2.4 Check that `tests/ui/` with a mouse still shows the session's tabs and the team
  row around an expanded card (the existing test of "The session around an expanded
  card", AC-4); add the check if no test asserts it.

## 3. Documents

- [x] 3.1 `docs/design/ui.md`, Phone layout, "The chat": a field of the card taking the
  focus expands it, the focus kept; an expanded card on a phone hides the session's tabs
  and the Team row; it stays expanded when the keyboard closes (LAD-126). The waiting
  card's expand paragraph: "the session's head, tabs and team row seen and usable" but on
  a phone.
- [x] 3.2 CHANGELOG.md, `### Fixed` under `## 0.43.0 (unreleased)`: on a phone, typing a
  gate's comment or an own answer no longer squeezes the waiting card to a strip: the
  card opens over the chat while you type.
- [x] 3.3 BACKLOG.md, in a commit of its own: the composer lies over the waiting card's
  tabs when the keyboard is opened from the composer on a phone (proposal, Out of scope).

## 4. Checks

- [x] 4.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_phone.py`
  pass; `openspec validate phone-card-field-expands --strict` passes; CI green on the
  pull request's last commit (AC-6). AC-5 is the human's check on an iPhone.
