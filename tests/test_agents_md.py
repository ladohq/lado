"""AGENTS.md is a bounded map (openspec capability agent-instructions): at most
`MAX_LINES` lines, and every relative Markdown link in it names a path of the repository.
Behaviour goes to docs/design/agents.md, docs/design/modules.md, docs/testing.md and
docs/cli.md, which every agent reads only on demand."""

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
AGENTS_MD = ROOT / "AGENTS.md"
MAX_LINES = 200
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def problems(path: Path, root: Path = ROOT) -> list[str]:
    """What breaks the map's rule in the file at `path`, links read against `root`."""
    text = path.read_text()
    found = []
    lines = len(text.splitlines())
    if lines > MAX_LINES:
        found.append(f"{path.name} has {lines} lines, at most {MAX_LINES}")
    for target in LINK.findall(text):
        if re.match(r"[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            continue
        local = re.split(r"[#?]", target, maxsplit=1)[0]
        if not (root / local).exists():
            found.append(f"{path.name} links {target}, which is not in the repository")
    return found


def test_agents_md_is_a_bounded_map():
    assert problems(AGENTS_MD) == []


def test_too_many_lines_fails(tmp_path):
    copy = tmp_path / "AGENTS.md"
    copy.write_text("line\n" * (MAX_LINES + 1))
    assert problems(copy, tmp_path) == ["AGENTS.md has 201 lines, at most 200"]


def test_a_link_to_a_missing_file_fails(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "cli.md").write_text("")
    copy = tmp_path / "AGENTS.md"
    copy.write_text(
        "[here](docs/cli.md#section) [web](https://example.com) [top](#commands)\n"
        "[gone](docs/design/agents.md)\n"
    )
    assert problems(copy, tmp_path) == [
        "AGENTS.md links docs/design/agents.md, which is not in the repository"
    ]
