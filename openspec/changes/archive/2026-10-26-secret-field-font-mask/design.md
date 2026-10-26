## Context

`SecretField` (`web/src/ProjectVariables.tsx`) is an uncontrolled `<input type="text">`
with the classes `project-in-value project-in-secret`; `.project-edit .project-in-secret`
in `web/src/styles.css` sets `-webkit-text-security: disc` (LAD-149). Safari's password
manager takes such a field for a password field (proposal, the bench). The UI has no
CSP (`server/app.py` sets one only on artifacts' sandboxed content), and Vite inlines an
asset under 4 KiB into the bundle as a `data:` URL. The bench's font (380 bytes, woff2)
drew Latin, Cyrillic, CJK and emoji as dots in Chromium, and kept Safari, Chrome and
Firefox silent.

## Decisions

### D1. One font, one glyph, every code point

`web/src/secret-dots.woff2`, family `LadoSecretDots`: a TrueType font with units per em
1000, one glyph, a filled disc (radius 200 units, centred at 300 units high, advance 600),
and a `cmap` of format 13 (platform 3, encoding 10) that maps every code point from
U+0020 to U+10FFFF but the surrogates to that glyph, so the space too is a dot, as with
`-webkit-text-security`, and no character falls back to another font. Format 13 is
OpenType's "many-to-one" map made for this (one glyph for a range); Chrome and Firefox
pass it through their font sanitizer, Safari's CoreText reads it. `.notdef` is the same
disc, so a code point outside the map is a dot as well. Why not `-webkit-text-security`
with a fallback: any field styled with it is what Safari detects.

### D2. The font is made by a script in the repository, and committed

`scripts/secret_dots_font.py` writes `web/src/secret-dots.woff2`; it is a PEP 723 script
(`# /// script` with `dependencies = ["fonttools", "brotli"]`), run as `uv run --script
scripts/secret_dots_font.py`, so the project gains no dependency and the web build needs
no Python. Its docstring says what the font is and why. The binary is committed: the
build never regenerates it. The script is our own (clean-room): no font or font code of
another project (e.g. text-security fonts) is copied.

### D3. The field shows nothing readable while the font is not there

`@font-face { font-family: LadoSecretDots; src: url("./secret-dots.woff2")
format("woff2"); font-display: block; }` in `styles.css`; Vite inlines the 380 bytes, so
there is no request and the font is ready with the stylesheet. `font-display: block`
keeps the typed text invisible, not drawn in another font, while the font is being
decoded. The field's font is `font-family: LadoSecretDots` alone, with no fallback family
in the list.

### D4. The placeholder keeps the UI's font

`.project-edit .project-in-secret::placeholder { font-family: var(--sans); }`: otherwise
`New value (the old one is not shown)` and `Value` would be dots too.

### D5. Test layers

- vitest (`web/src/ProjectVariables.test.tsx`): the field's type, attributes and class,
  copy and cut refused (as now); jsdom computes no fonts, so it checks only markup.
- UI e2e in Chromium (`tests/ui/test_projects_section.py`, `masked()`): no
  `input[type=password]`; the field is `type="text"`; its computed
  `-webkit-text-security` is `none` and its computed `font-family` is `LadoSecretDots`;
  `document.fonts.check('16px LadoSecretDots')` is true; and, on a canvas with that font,
  `measureText` gives `sk_live Пароль 秘密 🔑`'s characters one by one (by code point) the
  same width (Chromium gives 10 px each at 16 px, checked on the bench; in the UI's own
  font `i` and `W` differ). The screenshots show the dots.
- A real password manager stays the human's manual check on rc3 in Safari, Chrome and
  Firefox (docs/release.md, 4.3).

### D6. Version

A fix of an unreleased 0.43.0 feature: no bump, no CHANGELOG.md line.
