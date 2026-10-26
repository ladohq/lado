# /// script
# requires-python = ">=3.10"
# dependencies = ["fonttools", "brotli"]
# ///
"""Write web/src/secret-dots.woff2, the font LadoSecretDots of the web UI's secret field.

Every character in the font is one and the same dot: a filled disc of one width. The
secret's value field (web/src/ProjectVariables.tsx, SecretField) is drawn in it, so what is
typed shows as dots while the field stays a plain text field. The field cannot be a
password field (Chrome and Safari offer to save one whatever its autocomplete, LAD-149) nor
a text field masked by -webkit-text-security (Safari's password manager takes that for a
password field as well, LAD-155).

The font has two glyphs, .notdef and dot, both the disc, so a code point the maps miss is a
dot too. Its cmap of format 13 (platform 3, encoding 10: one glyph for a whole range) maps
every code point from U+0020 to U+10FFFF but the surrogates to the dot, the space included,
as -webkit-text-security does; a small format 4 map (U+0020 and U+2022 to the dot) is there
for an engine that looks for a BMP table first.

The binary is committed and the web build never runs this script; run it after a change:

    uv run --script scripts/secret_dots_font.py
"""

import math
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

FAMILY = "LadoSecretDots"
OUT = Path(__file__).resolve().parent.parent / "web" / "src" / "secret-dots.woff2"

UNITS_PER_EM = 1000
ADVANCE = 600
CENTRE = (300, 300)  # the disc sits on the baseline's x-height, as a bullet does
RADIUS = 200
ASCENT, DESCENT = 800, -200


def disc():
    """A circle of eight quadratic arcs: on-curve points every 45 degrees, each control
    point on the bisector at the radius over cos(22.5 degrees)."""
    pen = TTGlyphPen(None)
    cx, cy = CENTRE
    control = RADIUS / math.cos(math.pi / 8)

    def at(radius: float, degrees: float) -> tuple[int, int]:
        angle = math.radians(degrees)
        return round(cx + radius * math.cos(angle)), round(cy + radius * math.sin(angle))

    pen.moveTo(at(RADIUS, 0))
    for step in range(8):
        pen.qCurveTo(at(control, 45 * step + 22.5), at(RADIUS, 45 * (step + 1)))
    pen.closePath()
    return pen.glyph()


def subtable(fmt: int, platform: int, encoding: int, cmap: dict[int, str]):
    table = CmapSubtable.newSubtable(fmt)
    table.platformID, table.platEncID, table.language = platform, encoding, 0
    table.cmap = cmap
    return table


def build() -> FontBuilder:
    builder = FontBuilder(UNITS_PER_EM, isTTF=True)
    builder.setupGlyphOrder([".notdef", "dot"])
    bmp = {0x20: "dot", 0x2022: "dot"}
    builder.setupCharacterMap(bmp)
    every = {code: "dot" for code in range(0x20, 0x110000) if not 0xD800 <= code <= 0xDFFF}
    builder.font["cmap"].tables = [
        subtable(4, 0, 3, bmp),
        subtable(4, 3, 1, bmp),
        subtable(13, 3, 10, every),
    ]
    builder.setupGlyf({".notdef": disc(), "dot": disc()})
    left = CENTRE[0] - RADIUS
    builder.setupHorizontalMetrics({".notdef": (ADVANCE, left), "dot": (ADVANCE, left)})
    builder.setupHorizontalHeader(ascent=ASCENT, descent=DESCENT)
    builder.setupNameTable({"familyName": FAMILY, "styleName": "Regular"})
    builder.setupOS2(
        sTypoAscender=ASCENT,
        sTypoDescender=DESCENT,
        sTypoLineGap=0,
        usWinAscent=ASCENT,
        usWinDescent=-DESCENT,
        usDefaultChar=0,
        usBreakChar=0x20,
    )
    builder.setupPost()
    return builder


def main() -> None:
    font = build().font
    font.flavor = "woff2"
    font.save(OUT)
    print(f"{OUT}: {OUT.stat().st_size} bytes")


if __name__ == "__main__":
    main()
