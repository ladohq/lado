Task: LAD-201

## Why

Symptom: on Settings → Model servers, with the page scrolled to its very end, closing a form
at the bottom (Add server, a server's Change, the Remove question) moves what the human acted
on: the page gets shorter and everything on the screen goes down. In the UI e2e test of Add
server the form's place moved by 89 px at 1280×900. It became common in PR #216 (LAD-200),
which made the servers the page's last block: there is nothing below them to scroll.

Cause: `useScrollAnchor` keeps the anchor in place by scrolling by what the height above it
changed. Here the height changes below the anchor. The scrolling container (`.content`, or
the window at or under 900 px) then has less to scroll than its scroll position, and the
browser clamps the position to the new end: the whole section moves down. The hook measures
the anchor from the section's top, so it sees no change, and even if it did, it could not
scroll past the end. The living spec calls this a limit (model-settings-page, scenario "The
very end of the page"). No scroll can fix it; only a page that does not get shorter there
can.

Options weighed:

- A (taken): the hook keeps the lost height as blank room under the section. When the scroll
  it needs to keep the anchor in place lies past the container's end, it first adds that
  much bottom padding to the section, then scrolls. On every scroll of the container the
  padding shrinks to the part of it that is in view, so taking it away never moves what
  shows; after a scroll up it is gone, and the page ends at its real end again. Leaving the
  page drops it. Long-term cost: a few lines in the one shared hook; every page that uses it
  (Model servers, Git servers) gets the rule without code of its own.
- B: the same room, kept until the human leaves the page. A little simpler, but the human
  who scrolls down later finds a blank tail that means nothing.
- C: keep the limit and drop the task: the shift shows only at the very end of the page.
  Long-term cost: the rule "nothing moves under the pointer" keeps an exception that the
  page's layout since LAD-200 hits on every add at the bottom.

## What Changes

- `web/src/useScrollAnchor.ts`: a correction that the container cannot scroll to (past its
  end) is made possible by bottom padding on the section, as tall as is missing; the padding
  shrinks on each scroll of the container to the part in view, and goes when the hook's
  section leaves the page. The case of a change below the anchor at the end (the anchor's
  distance from the section's top unchanged, the browser's clamp the only move) becomes a
  correction too.
- The model-settings-page requirement "Nothing moves under the pointer" covers a change below
  the element as well as above it; its scenario "The very end of the page" now says the
  element stays and blank room is left below.
- `docs/design/ui.md`, **Nothing moves under the pointer**: the end-of-page limit is replaced
  by the blank room and how it goes.
- The UI e2e test `test_a_server_added_ticked_renamed_unticked_refreshed_and_removed` loses
  its `margin-bottom` room under the section; Add server and Remove at the page's very end
  keep their place within 1 px.
- A patch: a fix users see, so a CHANGELOG.md line under the unreleased patch heading.

## Scope

- `web/src/useScrollAnchor.ts` and its unit tests, `tests/ui/test_models_section.py`,
  `docs/design/ui.md`, CHANGELOG.md. Settings → Git servers uses the same hook and gets the
  same behaviour with no code of its own.

## Out of scope

- The tick's shift at the page's end found in design QA (F14): another cause (a double
  correction in `useScrollAnchor`), fixed in PR #216.
- Option B (the room kept until the page is left) and option C (the limit kept): see Why.
- An e2e test of Git servers at the page's end: the hook's rule is one, proved by its unit
  tests and the Model servers e2e; Git servers renders nothing of its own for it.
- The browser's own scroll anchoring (`overflow-anchor`): still off in the section, as Safari
  has none.

## Acceptance criteria

- AC-1: At 1280×900, with the page scrolled to its very end and no room added under the
  section, Add server keeps the new server where the form's top was (within 1 px), and the
  Remove question's confirm leaves the server's line where the server was (within 1 px).
- AC-2: The same with a server's Change form closing by Save at the page's end: the server's
  row keeps its place.
- AC-3: After such a change, scrolling up shrinks the blank room under the section to what is
  in view, so nothing on the screen moves; scrolled back to the end, the page ends at its last
  block (no room left).
- AC-4: With room to scroll under the anchor, nothing changes: no blank room is added, and the
  existing scenarios of "Nothing moves under the pointer" hold as they are.
- AC-5: Nothing acted on in the section: no blank room is ever added.
- AC-6: `make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_models_section.py`,
  `openspec validate page-end-keeps-place --strict` and the trial archive pass; the pull
  request's CI is green.

## Impact

- `web/src/useScrollAnchor.ts`, `web/src/useScrollAnchor.test.tsx`,
  `tests/ui/test_models_section.py`, `docs/design/ui.md`, CHANGELOG.md, the
  model-settings-page spec.
- Users: at the bottom of Model servers and Git servers a form that closes no longer moves the
  page; a blank room shows under the last block until they scroll up.
