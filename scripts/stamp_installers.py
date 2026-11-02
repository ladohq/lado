"""The release's Docker installers: docker/install.sh and docker/install.ps1 with their
version placeholder replaced by the release's version.

    python3 scripts/stamp_installers.py <version> <out-dir>

Run by the Release workflow's job github-release with the tag's version (the tag without
its `v`), which uploads `<out-dir>/install.sh` and `<out-dir>/install.ps1` beside
compose.yaml (docs/release.md); so `releases/latest/download/install.sh` installs exactly
the newest final's compose.yaml and image, and never asks GitHub which is the newest. Each
placeholder must be a line of its own found exactly once: a lost or doubled one, or a
version that is no release's (X.Y.Z or X.Y.ZrcN), is one line on stderr, exit 1, and the
release is not created.

Standard library only.
"""

from __future__ import annotations  # the runner's python3 may be older than LADO's

import re
import sys
from pathlib import Path

DOCKER = Path(__file__).parents[1] / "docker"
VERSION = re.compile(r"\d+\.\d+\.\d+(rc\d+)?")
PLACEHOLDERS = {"install.sh": "LADO_INSTALL_VERSION=", "install.ps1": "$LadoVersion = ''"}
STAMPED = {"install.sh": "LADO_INSTALL_VERSION={}", "install.ps1": "$LadoVersion = '{}'"}


class StampError(Exception):
    pass


def stamp(version: str, out: Path, source: Path = DOCKER) -> None:
    """Both installers of `source`, stamped with `version`, written into `out`; none is
    written when either cannot be stamped."""
    if not VERSION.fullmatch(version):
        raise StampError(f"not a release's version (X.Y.Z or X.Y.ZrcN): {version!r}")
    stamped = {}
    for name, placeholder in PLACEHOLDERS.items():
        lines = (source / name).read_text().split("\n")
        found = [i for i, line in enumerate(lines) if line == placeholder]
        if len(found) != 1:
            raise StampError(
                f"{source / name}: the line {placeholder!r} is there {len(found)} times, not once"
            )
        lines[found[0]] = STAMPED[name].format(version)
        stamped[name] = "\n".join(lines)
    out.mkdir(parents=True, exist_ok=True)
    for name, text in stamped.items():
        (out / name).write_text(text)
    (out / "install.sh").chmod(0o755)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: stamp_installers.py <version> <out-dir>", file=sys.stderr)
        return 2
    try:
        stamp(argv[0], Path(argv[1]), DOCKER)
    except (StampError, OSError) as error:
        print(f"stamp_installers: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
