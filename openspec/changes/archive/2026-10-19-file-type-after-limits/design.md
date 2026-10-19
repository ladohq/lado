## Context

`web/src/attachFiles.tsx` is the one module of the human's attached files for the composer
and the waiting card's fields. Its chips judge a file by the server's limits
(`GET /api/limits`), which load after the component mounts. The media type is fixed when a
file is attached, so a file attached before the limits load keeps
`application/octet-stream` (see proposal.md, Why).

## Decisions

- **D1. The media type is computed, not stored.** `Attached` drops `mediaType`; `FileChip`
  and `unseen()` call `mediaTypeOf(attached.name, limits)` on each render. The type is a
  pure function of the name and the limits, so storing it was a second copy that went
  stale. Nothing else reads `Attached.mediaType` (the upload sends only the bytes and the
  name; the server types the artifact).
- **D2. Every attached file gets an object URL at attach.** `attachFiles()` calls
  `URL.createObjectURL(file)` for each file, image or not; `FileChip` shows it as `<img>`
  only when `kindOf(mediaTypeOf(name, limits)) === "image"`, else `KindIcon`. An object URL
  references the `File` without copying its bytes, so the cost is one string per chip;
  `release()` already revokes every `thumb`. Making it lazily in the chip instead would
  move the URL's ownership into a component that unmounts across the waiting card's tabs,
  against the module's rule that the owner of the files owns their URLs.
- **D3. Before the limits load** a chip shows the generic icon of
  `application/octet-stream` and no eye, as today; when they load it re-renders with the
  real type. If the limits never load, it stays so (unchanged).
- **D4. The UI test is not changed.** Its auto-retrying `to_have_count(1)` already waits
  out the moment with no eye; the defect's regression test is a vitest one (the lowest
  layer that catches it). Stability is shown by running the UI test repeatedly with
  `-n 2`, not by a retry inside pytest.

## Risks

- A chip of a file attached early changes its icon to a thumbnail when the limits come: a
  one-time change within the first moment after the page opens, the same as any late
  data.
