Task: LAD-102

## Why

The UI test `tests/ui/test_chat.py::test_the_human_attaches_files_and_the_agent_gets_them`
failed once in CI (run 39158393958, attempt 1, job "ui (1)", `-n 2 --shard 1/2`) at
line 781, `expect(eye).to_have_count(1)`: "Actual value: 3", the locator resolved to 3
elements 14 times in a row. A rerun passed. The flake is a product defect, not the test's.

Symptom: when files are attached before the server's limits (`GET /api/limits`) have
loaded, every chip gets the crossed-out eye ("The agent sees only this file's name and
size") once the limits arrive, and an image shows the generic icon instead of its
thumbnail. It stays so until the files are removed.

Root cause, in `web/src/attachFiles.tsx`:

1. `useLimits()` fetches the limits after the composer (or the waiting card) mounts, so
   for a moment `limits` is `null`.
2. `attachFiles()` fixes each file's media type when it is attached:
   `mediaTypeOf(name, null)` gives `application/octet-stream` for every name, and the
   thumbnail is made only when that type is an image, so none is.
3. `unseen()` returns null while the limits are `null` (no eye), and once they load it
   judges the stored `application/octet-stream`: neither an agent image nor text, so every
   chip gets the eye. The PNG, the log and the PDF of the test all show it: 3, not 1.

The test attaches with the picker right after "No messages yet" shows, which does not wait
for the limits; on a loaded CI runner the limits' answer sometimes comes after the picker.
A human on a slow link meets the same: a file picked or dropped right after the page opens.

Options weighed (long-term cost):

- A. (chosen) Derive the media type from the name and the current limits when the chip
  renders, instead of storing it at attach; make the object URL for every file at attach
  and show it as the thumbnail only when the server's type is an image. A chip attached
  early shows the generic icon and no eye until the limits come, then the right icon or
  thumbnail and the eye only where it belongs. One module changes; nothing to keep in sync
  afterwards: the server's limits stay the one source of the type.
- B. Re-derive the stored media types and thumbnails when the limits arrive, in each owner
  of files (the composer, the waiting card, the gate card): three places to keep the same,
  and a second copy of a value that can be computed (against "one source of truth").
- C. Keep the paperclip, the paste and the drop off until the limits load: changes what
  the human can do, and when the limits cannot be loaded at all the human could never
  attach a file, while today the server checks them (docs/design/ui.md says every file
  then shows its icon).
- D. Only make the test wait for the limits: the test goes green and the defect stays for
  users. Rejected: the task asks to fix the product when the cause is there.

## What Changes

- `web/src/attachFiles.tsx`: `Attached` keeps no `mediaType`; a chip's icon, thumbnail and
  crossed-out eye come from `mediaTypeOf(name, limits)` with the limits at render time.
  `attachFiles()` makes an object URL for every file it attaches (`release` revokes it as
  before); the chip shows it only when the server's type is an image.
- A new living spec `attached-file-chips` holds the rule: a chip's type follows the
  server's limits whenever they load, also for files attached before.
- `web/src/attachFiles.test.tsx`: a regression test (chips rendered with `limits` null,
  then with the limits).
- docs/design/ui.md, "Files in the composer", the Limits bullet: one sentence that a file
  attached before the limits load shows its generic icon and no eye until they do, then
  its type by the server's table.
- CHANGELOG.md: a line under the next patch's `(unreleased)` heading.

## Scope

- `web/src/attachFiles.tsx`, `web/src/attachFiles.test.tsx`, the built bundle
  (`make web`), docs/design/ui.md, CHANGELOG.md, the delta of `attached-file-chips`.

## Out of scope

- `tests/ui/test_chat.py`: no change. With the fix, the eye's count is 0 until the limits
  load and 1 after, and `expect(...).to_have_count(1)` waits for it; the regression is
  caught by the unit test. Leaving the file alone also avoids a merge conflict with the
  parallel session lad-99, which edits it.
- The size and count checks before the limits load: today a file attached in that moment
  skips them and the server refuses it on upload with its reason; documented as intended
  ("the server checks the rest"), and no one met it.
- A retry inside pytest (the task forbids it) or a wait for `GET /api/limits` in the test
  (option D).

## Impact

- Product code: `web/src/attachFiles.tsx` only; the composer and the waiting card's fields
  (Other…, a Skip's comment, a gate's comment) all take the fix through it. No API, MCP,
  CLI or schema change. A patch release.
- Users: a file attached right after the page opens shows its thumbnail or icon and the
  crossed-out eye by its real type, as one attached later does.
- Neutral core: the web UI only; no provider is involved.
- Test layer: unit (vitest, `make web`), the lowest that catches it: the chips are a
  React component of the files and the limits, no process boundary is crossed. The UI
  test stays as it is and is run repeatedly to show it stable.
