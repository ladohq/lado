"""scripts/release_notes.py: a release tag's notes from CHANGELOG.md, for its GitHub release
(the Release workflow, docs/release.md)."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "release_notes.py"

CHANGELOG = """# Changelog

## 0.38.0 (unreleased)

- Something new.
- Upgrade: schema 27, restart running sessions.

## 0.37.0 (2026-10-13)

- `lado uninstall` removes LADO.
- API: `prompt` in `POST /api/sessions`.

## 0.36.1 (2026-10-01)

- A fix.
"""


def _module():
    spec = importlib.util.spec_from_file_location("release_notes", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


notes = _module()


def test_a_final_gets_its_dated_section_and_the_install_footer():
    text = notes.notes("v0.37.0", CHANGELOG)
    body, footer = text.split("\n---\n")
    assert body.strip() == (
        "- `lado uninstall` removes LADO.\n- API: `prompt` in `POST /api/sessions`."
    )
    assert "`lado update`" in footer
    assert "`uv tool install lado==0.37.0`" in footer
    assert "https://pypi.org/project/lado/0.37.0/" in footer
    assert "0.36.1" not in text and "Something new" not in text


def test_a_release_candidate_gets_the_unreleased_section_and_names_its_version():
    text = notes.notes("v0.38.0rc2", CHANGELOG)
    body, footer = text.split("\n---\n")
    assert body.strip() == "- Something new.\n- Upgrade: schema 27, restart running sessions."
    assert "`lado update 0.38.0rc2`" in footer
    assert "`uv tool install lado==0.38.0rc2`" in footer
    assert "https://pypi.org/project/lado/0.38.0rc2/" in footer
    assert "pre-release" in footer


def test_the_footer_names_the_image_of_the_version():
    final = notes.notes("v0.37.0", CHANGELOG).split("\n---\n")[1]
    assert "Docker: `docker pull ghcr.io/ladohq/lado:0.37.0`." in final
    candidate = notes.notes("v0.38.0rc2", CHANGELOG).split("\n---\n")[1]
    assert "Docker: `docker pull ghcr.io/ladohq/lado:0.38.0rc2`." in candidate


def test_the_notes_name_lados_image():
    from lado import update

    assert notes.IMAGE == update.IMAGE


def test_the_section_is_the_notes_without_their_footer():
    """scripts/rc_check.py reads a release candidate's items by the notes' own rules."""
    for tag in ("v0.37.0", "v0.38.0rc1"):
        assert notes.section(tag, CHANGELOG) == notes.notes(tag, CHANGELOG).split("\n\n---\n\n")[0]
    with pytest.raises(notes.NotesError, match="no section"):
        notes.section("v0.39.0rc1", CHANGELOG)


def test_the_last_section_of_the_file_runs_to_its_end():
    assert notes.notes("v0.36.1", CHANGELOG).split("\n---\n")[0].strip() == "- A fix."


def test_an_item_wrapped_over_lines_is_one_line():
    """GitHub shows each newline of a release's notes as a line break."""
    changelog = (
        "## 0.37.0 (2026-10-13)\n\n- One item\n  wrapped twice\n  here.\n"
        "- Another:\n  - a nested one\n    wrapped.\n\nA paragraph\nof two lines.\n"
    )
    assert notes.notes("v0.37.0", changelog).split("\n---\n")[0].strip() == (
        "- One item wrapped twice here.\n- Another:\n  - a nested one wrapped.\n\n"
        "A paragraph\nof two lines."
    )


def test_a_final_whose_heading_is_not_dated_has_no_notes():
    with pytest.raises(notes.NotesError) as error:
        notes.notes("v0.38.0", CHANGELOG)
    assert str(error.value) == (
        'CHANGELOG.md has no section "## 0.38.0 (<date>)" for v0.38.0: '
        "its heading still says (unreleased); date it in the release commit"
    )


def test_a_missing_section_has_no_notes():
    with pytest.raises(notes.NotesError) as error:
        notes.notes("v0.39.0rc1", CHANGELOG)
    assert str(error.value) == (
        'CHANGELOG.md has no section "## 0.39.0 (unreleased)" for v0.39.0rc1'
    )
    with pytest.raises(notes.NotesError, match=r'no section "## 0\.35\.0 \(<date>\)"'):
        notes.notes("v0.35.0", CHANGELOG)


def test_an_empty_section_has_no_notes():
    changelog = "# Changelog\n\n## 0.38.0 (unreleased)\n\n\n## 0.37.0 (2026-10-13)\n\n- x\n"
    with pytest.raises(notes.NotesError) as error:
        notes.notes("v0.38.0rc1", changelog)
    assert str(error.value) == 'CHANGELOG.md\'s section "## 0.38.0 (unreleased)" is empty'
    with pytest.raises(notes.NotesError, match="is empty"):
        notes.notes("v0.37.0", "## 0.37.0 (2026-10-13)\n")


def test_a_tag_that_is_no_release_has_no_notes():
    for tag in ("v0.37", "0.37.0", "v0.37.0-rc1", "v0.37.0a1"):
        with pytest.raises(notes.NotesError, match="is no release tag"):
            notes.notes(tag, CHANGELOG)


def test_a_release_candidate_is_a_prerelease_and_a_final_the_latest():
    assert notes.flag("v0.38.0rc1") == "--prerelease"
    assert notes.flag("v0.37.0") == "--latest"


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True
    )


def test_the_command_prints_the_notes_and_the_flag(tmp_path):
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG)
    done = run("v0.37.0", cwd=tmp_path)
    assert done.returncode == 0, done.stderr
    assert done.stdout == notes.notes("v0.37.0", CHANGELOG)
    done = run("--flag", "v0.38.0rc1", cwd=tmp_path)
    assert (done.returncode, done.stdout) == (0, "--prerelease\n")


def test_the_command_fails_with_one_line_on_stderr(tmp_path):
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG)
    done = run("v0.39.0", cwd=tmp_path)
    assert done.returncode == 1
    assert done.stdout == ""
    assert done.stderr == (
        'release notes: CHANGELOG.md has no section "## 0.39.0 (<date>)" for v0.39.0\n'
    )


def test_the_repository_changelog_has_the_notes_of_its_newest_section():
    """The real CHANGELOG.md parses: its newest heading is a release's notes."""
    text = (ROOT / "CHANGELOG.md").read_text()
    heading = next(line for line in text.splitlines() if line.startswith("## "))
    version, kind = heading[3:].split(" ", 1)
    tag = f"v{version}rc1" if kind == "(unreleased)" else f"v{version}"
    assert notes.notes(tag, text).strip()
