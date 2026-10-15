"""The one rule of a line of visible text (openspec capability visible-text).

A one-line text the human or an agent writes (a session's title, a summary, a note, a
choice) reaches terminals and agents' windows as a line. A character is hidden when its
Unicode category is Cc (control characters: line breaks, tabs, ESC), Zl or Zp (the line
and paragraph separators) or Cf (format characters: bidi controls, zero-width
characters), but U+200D ZERO WIDTH JOINER, which joins emoji sequences. A field the writer
gives as one line is refused with the first one named (`first_hidden`, `named`); a line
LADO takes from the human's longer text is cleaned (`one_line`). Only the standard
library: hooks import it.
"""

import unicodedata

HIDDEN = frozenset({"Cc", "Zl", "Zp", "Cf"})
JOINER = "\u200d"


def hidden(char: str) -> bool:
    return char != JOINER and unicodedata.category(char) in HIDDEN


def first_hidden(text: str) -> str | None:
    return next((char for char in text if hidden(char)), None)


def named(char: str) -> str:
    """`U+XXXX NAME`, or `U+XXXX` for a character without a name (the Cc ones)."""
    code = f"U+{ord(char):04X}"
    name = unicodedata.name(char, "")
    return f"{code} {name}" if name else code


def refusal(char: str) -> str:
    """The words of a refusal after "... is one line" / "... must be one line"."""
    return f"of visible text: {named(char)} is not allowed"


def one_line(text: str) -> str:
    """`text` with each hidden Cf character removed and each other one made a space, its
    ends stripped."""
    kept = []
    for char in text:
        if hidden(char):
            if unicodedata.category(char) != "Cf":
                kept.append(" ")
        else:
            kept.append(char)
    return "".join(kept).strip()
