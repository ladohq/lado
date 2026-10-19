## 1. Test first (red on main)

- [ ] 1.1 `web/src/attachFiles.test.tsx`, a test "a chip attached before the limits load
  takes its type when they load": render `FileChips` with three files made by
  `attachFiles([...], 0, null)` (`shot.png` of type `image/png`, `server.log`, `spec.pdf`)
  and `limits={null}`: no button "The agent sees only this file's name and size", no
  `<img>`; rerender with limits whose `extensions` map `png`, `log` (`text/plain`) and
  `pdf` (`application/pdf`): exactly one such button, in the chip of `spec.pdf`, and one
  `<img>` (`blob:thumb-…`), in the chip of `shot.png`. Check: red on main (3 buttons, no
  `<img>`), `cd web && npx vitest run src/attachFiles.test.tsx`.

## 2. The fix

- [ ] 2.1 `web/src/attachFiles.tsx` (D1): drop `mediaType` from `Attached`; `unseen()` and
  `FileChip` take the type from `mediaTypeOf(attached.name, limits)` (pass `limits` to
  `FileChip`, or the computed type); update the module's comments. Check: 1.1 green.
- [ ] 2.2 `attachFiles()` (D2): `thumb` is `URL.createObjectURL(file)` for every file
  taken; `FileChip` shows `<img>` only when `kindOf(type) === "image"`, else `KindIcon`.
  Update the existing test "attaching over the limits names each refused file and keeps
  the rest" (no `mediaType`; `a.txt` now has a `thumb`). Check: `make web` green
  (tsc, vitest, build).
- [ ] 2.3 docs/design/ui.md, "Files in the composer", the bullet "Limits from the
  server": add that a file attached before the limits load shows the generic icon and no
  eye until they load, then its type by the server's table; the chips bullet: the
  thumbnail's object URL is made for every file and shown for an image.
- [ ] 2.4 CHANGELOG.md, under the next patch's `## X.Y.Z (unreleased)` heading (AGENTS.md
  Versions rule): files attached right after a chat opens no longer all show the
  crossed-out eye and lose the image's thumbnail; a chip shows its type by the server's
  table once it is known.

## 3. Checks

- [ ] 3.1 `make lint`, `make test` (counts in the build report), `make web`;
  `openspec validate file-type-after-limits --strict`, `openspec validate --specs
  --strict`.
- [ ] 3.2 `uv run pytest -m ui tests/ui/test_chat.py` green, then the attach test 20 times
  in a row with two workers, e.g. `for i in $(seq 20); do uv run pytest -m ui -n 2
  tests/ui/test_chat.py -k "attaches_files or file_only" > /tmp/lad-102-ui-$i.log 2>&1 ||
  echo "run $i red"; done`: no red run (the count in the build report).
- [ ] 3.3 By hand, the defect reproduced and gone: a one-off Playwright script (not
  committed) that delays `**/api/limits` by 2 s with `page.route`, attaches the test's
  three files at once and counts the eye after the limits come: 3 on main, 1 with the fix.
  Name the counts in the build report.
