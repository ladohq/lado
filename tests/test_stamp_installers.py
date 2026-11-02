"""scripts/stamp_installers.py: the release's install.sh and install.ps1, the tag's
docker/ copies with their version placeholder replaced (openspec capability
image-release)."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "stamp_installers.py"


def _module():
    spec = importlib.util.spec_from_file_location("stamp_installers", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stamp = _module()


def test_the_stamp_writes_both_copies(tmp_path):
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "0.44.0rc1", str(tmp_path)],
        capture_output=True, text=True, cwd=ROOT,
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    for name, line in (
        ("install.sh", "LADO_INSTALL_VERSION=0.44.0rc1"),
        ("install.ps1", "$LadoVersion = '0.44.0rc1'"),
    ):
        old = (ROOT / "docker" / name).read_text().split("\n")
        new = (tmp_path / name).read_text().split("\n")
        assert len(old) == len(new)
        changed = [(a, b) for a, b in zip(old, new, strict=True) if a != b]
        assert changed == [(stamp.PLACEHOLDERS[name], line)]
    assert (tmp_path / "install.sh").stat().st_mode & 0o111


def source(tmp_path: Path, sh: str, ps1: str = "$LadoVersion = ''\n") -> Path:
    folder = tmp_path / "docker"
    folder.mkdir()
    (folder / "install.sh").write_text(sh)
    (folder / "install.ps1").write_text(ps1)
    return folder


@pytest.mark.parametrize(
    "sh",
    [
        "#!/bin/sh\nmain\n",
        "LADO_INSTALL_VERSION=\nLADO_INSTALL_VERSION=\n",
        "LADO_INSTALL_VERSION=1\n",
    ],
)
def test_a_missing_or_doubled_placeholder_fails(tmp_path, sh):
    out = tmp_path / "out"
    with pytest.raises(stamp.StampError, match="install.sh"):
        stamp.stamp("0.44.0", out, source(tmp_path, sh))
    assert not (out / "install.sh").exists()


def test_a_lost_placeholder_exits_non_zero_naming_the_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(stamp, "DOCKER", source(tmp_path, "#!/bin/sh\n"))
    assert stamp.main(["0.44.0", str(tmp_path / "out")]) == 1
    assert "install.sh" in capsys.readouterr().err


@pytest.mark.parametrize("version", ["v0.44.0", "0.44", "latest", "0.44.0.dev1", ""])
def test_a_version_of_another_form_fails(tmp_path, version):
    with pytest.raises(stamp.StampError, match="version"):
        stamp.stamp(version, tmp_path / "out", ROOT / "docker")
