from lado import doctor


def test_all_checks_pass_when_tools_are_on_path(monkeypatch):
    monkeypatch.setattr(doctor, "_tool_version", lambda path, flag: "v1")
    checks = doctor.run_checks(which=lambda cmd: f"/usr/bin/{cmd}")
    assert [c.name for c in checks] == ["Python", "tmux", "Claude Code"]
    assert all(c.ok for c in checks)


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
