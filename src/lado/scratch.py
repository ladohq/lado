"""A session from scratch (openspec change start-from-scratch): from a name the human types
in any script, the folder's and the session's name and the session's title; whether a
folder may take a fresh start; whether git knows whom to sign commits with; and the
repository itself, a new or empty folder with one empty commit. `lado start --new`, the UI
server and `lado doctor` all call it, and print only what it says.

None of the human's files ever goes into a commit: only a folder with nothing in it (but
Finder's `.DS_Store`) is made a repository."""

import re
import unicodedata
from dataclasses import dataclass

from lado import runtime
from lado import text as visible


class ScratchError(runtime.LadoError):
    """Why a fresh start cannot go on, by kind, with a hint when the human can act (LAD-5's
    `runtime.Hint`)."""

    def __init__(self, kind: str, text: str, hint: runtime.Hint | None = None) -> None:
        super().__init__(text)
        self.kind = kind
        self.hint = hint


# Russian, Ukrainian and Belarusian letters, lowercase (a capital is lowered first).
CYRILLIC = {
    **dict(zip("абвгґдеёзийіїклмнопрстуфыэ", "abvggdeeziiiiklmnoprstufye", strict=True)),
    **{"є": "ie", "ж": "zh", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch"},
    **{"ъ": "", "ь": "", "ю": "iu", "я": "ia"},
}
NO_LATIN = "the name needs a Latin letter or digit for its folder: type one"


@dataclass(frozen=True)
class Names:
    """What a typed name gives: the folder's and the session's name, and the session's
    title (None when it is the name itself, as `runtime.set_title` stores it)."""

    name: str
    title: str | None


def names(text: str) -> Names:
    """The names of a fresh start from the text the human typed, or a ScratchError: empty,
    over `runtime.MAX_TITLE` characters, a hidden character, or nothing left for a folder's
    name once Cyrillic is transliterated and Latin letters lose their accents."""
    title = text.strip()
    if not title:
        raise ScratchError("no_name", "type a name")
    if len(title) > runtime.MAX_TITLE:
        raise ScratchError("too_long", f"a name is at most {runtime.MAX_TITLE} characters")
    if (char := visible.first_hidden(title)) is not None:
        raise ScratchError("hidden", f"a name is one line {visible.refusal(char)}")
    latin = "".join(CYRILLIC.get(char, char) for char in title.lower())
    latin = "".join(
        char for char in unicodedata.normalize("NFKD", latin) if not unicodedata.combining(char)
    )
    # runtime.slug would make "lado" of a text with nothing it keeps: no name of the human's.
    if not re.search(r"[a-z0-9]", latin):
        raise ScratchError("no_latin", NO_LATIN)
    name = runtime.slug(latin)
    return Names(name, title if title != name else None)
