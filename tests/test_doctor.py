import re

import pytest

from lado import __version__, agent_env, doctor
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
    names = ["LADO", "Python", "tmux", "Agent environment", "Claude Code", "Kilo CLI"]
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


def test_claude_code_2_1_289_is_the_tested_version(monkeypatch):
    """make test-live PROVIDER=claude passed on 2.1.289 (2026-10-05)."""
    _versions(monkeypatch, claude_version="2.1.289 (Claude Code)")
    check = next(c for c in doctor.run_checks(which=lambda cmd: cmd) if c.name == "Claude Code")
    assert check.ok and not check.warning


@pytest.mark.parametrize("version", ["2.1.287", "2.1.290", "2.2.0", "2.1.2890"])
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


def test_lado_check_says_a_newer_version_is_available(published):
    published(**{"99.0.0": "2026-10-04"})
    check = doctor.check_lado()
    assert check.ok and check.warning
    assert check.detail == __version__
    assert check.hint == "LADO 99.0.0 is available: lado update"


def test_lado_check_says_why_the_update_check_failed(published, tmp_path, monkeypatch):
    monkeypatch.setenv("LADO_UPDATE_INDEX", str(tmp_path / "missing.json"))
    check = doctor.check_lado()
    assert check.ok and check.warning
    assert check.hint.startswith("cannot look up LADO's latest version: ")


def test_lado_check_of_the_latest_version_and_with_the_check_off(published, monkeypatch):
    published(**{__version__: "2026-10-04"})
    assert doctor.check_lado() == doctor.Check("LADO", True, f"{__version__}, the latest version")
    monkeypatch.setenv("LADO_NO_UPDATE_CHECK", "1")
    assert doctor.check_lado() == doctor.Check(
        "LADO", True, f"{__version__} (no update check: LADO_NO_UPDATE_CHECK=1)"
    )


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


def test_provider_status_of_an_installed_tested_cli(monkeypatch):
    _versions(monkeypatch)
    status = doctor.provider_status(claude.ClaudeProvider(), which=lambda cmd: cmd)
    assert status == doctor.ProviderStatus(
        installed=True,
        version=claude.TESTED_VERSION,
        detail=f"{claude.TESTED_VERSION} (Claude Code)",
        tested_version=claude.TESTED_VERSION,
        warning="",
    )


def test_provider_status_of_a_missing_cli(monkeypatch):
    _versions(monkeypatch)
    status = doctor.provider_status(kilo.KiloProvider(), which=lambda cmd: None)
    assert (status.installed, status.version, status.warning) == (False, "", "")
    assert status.detail == "`kilo` not found on PATH"


def test_provider_status_of_an_untested_version_warns(monkeypatch):
    _versions(monkeypatch, kilo_version="9.0.0")
    status = doctor.provider_status(kilo.KiloProvider(), which=lambda cmd: cmd)
    assert (status.installed, status.version) == (True, "9.0.0")
    assert status.warning.startswith(f"LADO is tested with Kilo CLI {kilo.TESTED_VERSION}.x;")
