"""scripts/rc_check.py: the human's checks of a release candidate (docs/release.md, section
4). Every command it runs goes through `rc.run`, which a recorder replaces here."""

import importlib.util
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "rc_check.py"

CHANGELOG = """# Changelog

## 0.38.0 (unreleased)

- Something new.
- A fix
  wrapped over two lines.

## 0.37.0 (2026-10-13)

- An older item.
"""


def _module():
    spec = importlib.util.spec_from_file_location("rc_check", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["rc_check"] = module  # its dataclasses look their module up
    spec.loader.exec_module(module)
    return module


rc = _module()


def test_versions_sort_release_candidates_before_their_final():
    v = rc.parse
    assert sorted([v("0.38.0"), v("0.38.0rc2"), v("0.37.1"), v("0.38.0rc10"), v("0.38.0rc1")]) == [
        v("0.37.1"),
        v("0.38.0rc1"),
        v("0.38.0rc2"),
        v("0.38.0rc10"),
        v("0.38.0"),
    ]
    assert v("0.38.0rc2").final is False and v("0.38.0").final is True
    assert str(v("0.38.0rc2")) == "0.38.0rc2"
    for other in ("0.38.0.dev1", "0.38.0a1", "0.38", "v0.38.0", "0.38.0-rc1"):
        assert v(other) is None


def test_releases_skip_other_forms_and_yanked_ones():
    index = {
        "releases": {
            "0.37.0": [{"yanked": False}],
            "0.37.1": [{"yanked": True}],
            "0.38.0rc1": [],
            "0.38.0.dev1": [],
        }
    }
    assert rc.releases(index) == [rc.parse("0.37.0"), rc.parse("0.38.0rc1")]


def test_the_default_version_is_the_newest_release_candidate(monkeypatch):
    monkeypatch.setattr(rc, "fetch_index", lambda: {"releases": {"0.37.0": [], "0.38.0rc2": []}})
    called = []
    monkeypatch.setattr(rc, "sandbox", lambda *args: called.append(args) or 0)
    assert rc.main(["sandbox", "--no-ui"]) == 0
    assert called == [(rc.parse("0.38.0rc2"), "claude", False)]


def test_the_default_version_refuses_a_final(capsys, monkeypatch):
    monkeypatch.setattr(rc, "fetch_index", lambda: {"releases": {"0.37.0rc2": [], "0.38.0": []}})
    monkeypatch.setattr(rc, "sandbox", lambda *args: pytest.fail("no sandbox for a final"))
    assert rc.main(["sandbox"]) == 2
    assert "0.38.0 is a final release: name the RC to check" in capsys.readouterr().err


def test_a_named_final_is_refused(capsys, monkeypatch):
    monkeypatch.setattr(rc, "sandbox", lambda *args: pytest.fail("no sandbox for a final"))
    assert rc.main(["sandbox", "0.38.0"]) == 2
    assert rc.main(["upgrade", "0.38.0"]) == 2
    err = capsys.readouterr().err
    assert "0.38.0 is a final release" in err


def test_a_version_of_another_form_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as done:
        rc.main(["sandbox", "0.38.0a1"])
    assert done.value.code == 2
    assert "X.Y.ZrcN" in capsys.readouterr().err


def test_pypi_unreachable_is_one_fail_line(capsys, monkeypatch, tmp_path):
    def down():
        raise OSError("timed out")

    temp = tmp_path / "temp"
    temp.mkdir()
    monkeypatch.setattr(rc, "fetch_index", down)
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    assert rc.main(["sandbox"]) == 1
    assert capsys.readouterr().out == "[FAIL] PyPI: timed out\n"
    assert list(temp.iterdir()) == []


def test_checklist_lists_the_rc_section_items():
    lines = rc.checklist(rc.parse("0.38.0rc1"), CHANGELOG, 'version = "0.38.0rc1"\n')
    assert lines[-2:] == ["[ ] Something new.", "[ ] A fix wrapped over two lines."]
    assert any("sdlc" in line and "first gate" in line for line in lines)
    assert any("pre-release" in line for line in lines)
    assert not any(line.startswith("warning") for line in lines)
    assert "An older item." not in "\n".join(lines)


def test_checklist_without_the_section_warns():
    lines = rc.checklist(rc.parse("0.39.0rc1"), CHANGELOG, 'version = "0.39.0rc1"\n')
    assert lines[-1] == (
        'warning: CHANGELOG.md has no section "## 0.39.0 (unreleased)" for v0.39.0rc1'
    )
    lines = rc.checklist(rc.parse("0.39.0rc1"), None, 'version = "0.39.0rc1"\n')
    assert lines[-1] == "warning: no CHANGELOG.md here: run the script from the repository's root"


def test_checklist_warns_about_another_checkout():
    lines = rc.checklist(rc.parse("0.38.0rc1"), CHANGELOG, '[project]\nversion = "0.37.1"\n')
    assert (
        "warning: pyproject.toml says 0.37.1, not 0.38.0rc1: this checkout is not the RC's "
        "commit, and its CHANGELOG.md may not be the RC's"
    ) in lines


def test_the_real_run_passes_output_and_exit_code():
    done = rc.run([sys.executable, "-c", "import sys; print('out'); sys.exit(3)"])
    assert (done.code, done.output) == (3, "out\n")
    missing = rc.run(["no-such-command-of-rc-check"])
    assert missing.code == 127 and "no-such-command-of-rc-check" in missing.output
