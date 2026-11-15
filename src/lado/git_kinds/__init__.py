"""The kinds of git server LADO knows, one module each (`base.Kind`). KINDS is the one place
that names them: `lado git-server add --kind`'s choices and the probe's requests come from
it, so a new kind is a module and its entry here."""

from __future__ import annotations

from lado.git_kinds import github, gitlab
from lado.git_kinds.base import Kind

KINDS: tuple[Kind, ...] = (github.KIND, gitlab.KIND)


def by_name(name: str) -> Kind | None:
    return next((kind for kind in KINDS if kind.name == name), None)
