import re

import pytest

from lado import agent_env, doctor
from lado.providers import claude, kilo


def _versions(
    monkeypatch,
    kilo_version=f"{kilo.TESTED_VERSION}.1",
    claude_version=f"{claude.TESTED_VERSION} (Claude Code)",
    tmux_version="tmux 3.7c",
):
    versions = {"kilo": kilo_version, "claude": claude_version, "tmux": tmux_version}
    monkeypatch.setattr(doctor, "_tool_version", lambda path, flag: versions.get(path, "v1"))


def test_all_checks_pass_when_tools_are_on_path(monkeypatch):
    _versions(monkeypatch)
    checks = doctor.run_checks(which=lambda cmd: cmd)
    names = ["Python", "tmux", "Agent environment", "Claude Code", "Kilo CLI"]
    assert [c.name for c in checks] == names
    assert all(c.ok and not c.warning for c in checks)


@pytest.mark.parametrize(
    ("version", "hint"),
    [
        ("tmux 3.2a", "gate popups have no coloured border before tmux 3.3"),
        ("tmux 3.1c", "no gate popups before tmux 3.2: gates show only in `lado ls`"),
        ("tmux 3.1c", "no agent terminals in the web UI before tmux 3.2"),
    ],
)
def test_old_tmux_warns_about_gate_popups_and_terminals(monkeypatch, version, hint):
    _versions(monkeypatch, tmux_version=version)
    tmux = next(c for c in doctor.run_checks(which=lambda cmd: cmd) if c.name == "tmux")
    assert tmux.ok and tmux.warning
    assert hint in tmux.hint


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


@pytest.mark.parametrize("version", ["2.1.286", "2.1.288", "2.2.0", "2.1.2870"])
def test_claude_code_other_than_the_tested_version_warns(monkeypatch, version):
    """Whether LADO's tools load up front was checked on one Claude Code version only."""
    _versions(monkeypatch, claude_version=f"{version} (Claude Code)")
    check = next(c for c in doctor.run_checks(which=lambda cmd: cmd) if c.name == "Claude Code")
    assert check.ok and check.warning
    assert f"LADO is tested with Claude Code {claude.TESTED_VERSION};" in check.hint


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


def test_agent_environment_inherited():
    check = doctor.check_agent_env()  # the tests run with LADO_AGENT_ENV=inherit
    assert check.ok and not check.warning
    assert "LADO_AGENT_ENV=inherit" in check.detail


@pytest.fixture
def login_shell(tmp_path, monkeypatch):
    shell = tmp_path / "login-shell"
    shell.write_text('#!/bin/sh\nexec /bin/sh -c "$2"\n')
    shell.chmod(0o755)
    monkeypatch.setenv("SHELL", str(shell))
    monkeypatch.delenv(agent_env.SOURCE_VAR)
    return shell


def test_agent_environment_from_the_login_shell(login_shell):
    check = doctor.check_agent_env()
    assert check.ok and not check.warning
    assert re.fullmatch(
        rf"from your login shell {login_shell}, resolved in \d+\.\d s", check.detail
    )


def test_a_slow_login_shell_warns(login_shell, monkeypatch):
    monkeypatch.setattr(agent_env, "SLOW", 0)
    check = doctor.check_agent_env()
    assert check.ok and check.warning
    assert "each agent's start waits for your shell" in check.hint


def test_a_failing_login_shell_fails(login_shell):
    login_shell.write_text("#!/bin/sh\necho 'rc is broken' >&2\nexit 2\n")
    check = doctor.check_agent_env()
    assert not check.ok
    assert "exit status 2" in check.detail and "rc is broken" in check.detail
