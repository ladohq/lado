"""Where a folder sits in its git repository, as the providers' CLIs look it up (each CLI's
own walk over these stays in its provider)."""

import subprocess
from pathlib import Path


def rev_parse(cwd: Path, *args: str) -> str | None:
    """`git rev-parse --path-format=absolute <args>` in `cwd`; None outside git."""
    done = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--path-format=absolute", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return done.stdout.strip() if done.returncode == 0 else None


def git_root(cwd: Path) -> Path:
    """The real path of `cwd`'s git work tree, or of the root folder outside git."""
    top = rev_parse(cwd, "--show-toplevel")
    return Path(top).resolve() if top else Path(cwd.resolve().anchor)


def main_root(cwd: Path) -> Path:
    """The real path of the main work tree of `cwd`'s repository (the main repo of a linked
    worktree); `cwd` itself outside git."""
    common = rev_parse(cwd, "--git-common-dir")
    return Path(common).resolve().parent if common else cwd.resolve()
