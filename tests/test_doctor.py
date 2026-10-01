from lado import doctor
from lado.providers import kilo


def _versions(monkeypatch, kilo_version=f"{kilo.TESTED_VERSION}.1"):
    versions = {"kilo": kilo_version, "claude": "2.1.0 (Claude Code)"}
    monkeypatch.setattr(doctor, "_tool_version", lambda path, flag: versions.get(path, "v1"))


def test_all_checks_pass_when_tools_are_on_path(monkeypatch):
    _versions(monkeypatch)
    checks = doctor.run_checks(which=lambda cmd: cmd)
    assert [c.name for c in checks] == ["Python", "tmux", "Claude Code", "Kilo CLI"]
    assert all(c.ok and not c.warning for c in checks)


def test_missing_default_provider_fails_other_providers_warn(monkeypatch):
    _versions(monkeypatch)
    checks = doctor.run_checks(which=lambda cmd: None if cmd in ("claude", "kilo") else cmd)
    claude, kilo_check = checks[-2:]
    assert not claude.ok
    assert kilo_check.ok and kilo_check.warning
    assert "--provider kilo" in kilo_check.hint


def test_untested_kilo_version_warns_but_passes(monkeypatch, capsys):
    _versions(monkeypatch, kilo_version="9.0.0")
    checks = doctor.run_checks(which=lambda cmd: cmd)
    monkeypatch.setattr(doctor, "run_checks", lambda: checks)
    assert doctor.main() == 0
    out = capsys.readouterr().out
    assert "[warn] Kilo CLI: 9.0.0" in out
    assert f"{kilo.TESTED_VERSION}.x" in out


def test_missing_tool_fails_with_hint():
    checks = doctor.run_checks(which=lambda cmd: None if cmd == "tmux" else f"/bin/{cmd}")
    tmux = next(c for c in checks if c.name == "tmux")
    assert not tmux.ok
    assert "not found" in tmux.detail
    assert tmux.hint


def test_main_returns_nonzero_on_failure(monkeypatch, capsys):
    monkeypatch.setattr(
        doctor, "run_checks", lambda: [doctor.Check("tmux", False, "missing", "install it")]
    )
    assert doctor.main() == 1
    assert "[FAIL] tmux" in capsys.readouterr().out
