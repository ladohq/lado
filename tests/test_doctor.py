import os
import re
import time

import agent_helpers
import pytest

from lado import (
    __version__,
    agent_env,
    artifacts,
    artifacts_local,
    doctor,
    gui_session,
    providers,
    runtime,
    state,
)
from lado.gui_session import Place
from lado.providers import claude, codex, kilo, opencode


def _versions(
    monkeypatch,
    kilo_version=f"{kilo.TESTED_VERSION}.1",
    claude_version=f"{claude.TESTED_VERSION} (Claude Code)",
    tmux_version="tmux 3.7c",
    opencode_version=f"{opencode.TESTED_VERSION}.34",
    codex_version=f"codex-cli {codex.TESTED_VERSION}.0",
):
    versions = {
        "kilo": kilo_version,
        "claude": claude_version,
        "codex": codex_version,
        "tmux": tmux_version,
        "opencode": opencode_version,
    }
    monkeypatch.setattr(doctor, "_tool_version", lambda path, flag: versions.get(path, "v1"))


def test_all_checks_pass_when_tools_are_on_path(monkeypatch):
    _versions(monkeypatch)
    monkeypatch.setattr(gui_session.sys, "platform", "linux")  # its check: below
    checks = doctor.run_checks(which=lambda cmd: cmd)
    names = [
        "LADO",
        "Python",
        "tmux",
        "Agent environment",
        "Agent config folders",
        "Artifacts",
        "Claude Code",
        "Codex CLI",
        "Kilo CLI",
        "OpenCode",
    ]
    assert [c.name for c in checks] == names
    assert all(c.level == doctor.OK for c in checks)


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
    assert tmux.level == doctor.WARN
    assert hint in tmux.hint


@pytest.mark.parametrize("installed", ["claude", "codex", "kilo", "opencode"])
def test_a_missing_provider_is_info_when_another_is_installed(monkeypatch, capsys, installed):
    _versions(monkeypatch)
    checks = doctor.run_checks(which=lambda cmd: cmd if cmd in (installed, "tmux") else None)
    by_name = {c.name: c for c in checks[-4:]}
    for name in ("claude", "codex", "kilo", "opencode"):
        provider = providers.get(name)
        check = by_name[provider.title]
        if name == installed:
            assert check.level == doctor.OK
        else:
            assert (check.level, check.hint) == (doctor.INFO, provider.install_hint)
    monkeypatch.setattr(doctor, "run_checks", lambda: checks)
    assert doctor.main() == 0
    out = capsys.readouterr().out
    missing = next(providers.get(n) for n in providers.names() if n != installed)
    assert f"[info] {missing.title}: `{missing.command}` not found on PATH" in out
    assert "All checks passed." in out


def test_no_provider_installed_fails_once_with_every_install_hint(monkeypatch, capsys):
    _versions(monkeypatch)
    checks = doctor.run_checks(which=lambda cmd: cmd if cmd == "tmux" else None)
    assert [c.name for c in checks][-1] == "Agent CLI"
    agent_cli = checks[-1]
    assert agent_cli.level == doctor.FAIL
    assert agent_cli.detail == "no agent CLI installed"
    for name in providers.names():
        assert providers.get(name).install_hint in agent_cli.hint
    assert not any(c.name == "Claude Code" for c in checks)
    monkeypatch.setattr(doctor, "run_checks", lambda: checks)
    assert doctor.main() == 1
    assert "[FAIL] Agent CLI: no agent CLI installed" in capsys.readouterr().out


def test_untested_kilo_version_warns_but_passes(monkeypatch, capsys):
    _versions(monkeypatch, kilo_version="9.0.0")
    checks = doctor.run_checks(which=lambda cmd: cmd)
    monkeypatch.setattr(doctor, "run_checks", lambda: checks)
    assert doctor.main() == 0
    out = capsys.readouterr().out
    assert "[warn] Kilo CLI: 9.0.0" in out
    assert f"{kilo.TESTED_VERSION}.x" in out


def test_untested_opencode_version_warns_but_passes(monkeypatch, capsys):
    _versions(monkeypatch, opencode_version="2.0.1")
    checks = doctor.run_checks(which=lambda cmd: cmd)
    monkeypatch.setattr(doctor, "run_checks", lambda: checks)
    assert doctor.main() == 0
    out = capsys.readouterr().out
    assert "[warn] OpenCode: 2.0.1" in out
    assert "LADO is tested with OpenCode 1.18.x" in out


def test_claude_code_2_1_295_is_the_tested_version(monkeypatch):
    """Its Stop's background_tasks checked by hand on 2.1.295 (2026-10-09)."""
    _versions(monkeypatch, claude_version="2.1.295 (Claude Code)")
    check = next(c for c in doctor.run_checks(which=lambda cmd: cmd) if c.name == "Claude Code")
    assert check.level == doctor.OK


@pytest.mark.parametrize("version", ["2.1.289", "2.1.296", "2.2.0", "2.1.2950"])
def test_claude_code_other_than_the_tested_version_warns(monkeypatch, version):
    """Whether LADO's tools load up front was checked on one Claude Code version only."""
    _versions(monkeypatch, claude_version=f"{version} (Claude Code)")
    check = next(c for c in doctor.run_checks(which=lambda cmd: cmd) if c.name == "Claude Code")
    assert check.level == doctor.WARN
    assert f"LADO is tested with Claude Code {claude.TESTED_VERSION};" in check.hint


def test_missing_tool_fails_with_hint():
    checks = doctor.run_checks(which=lambda cmd: None if cmd == "tmux" else f"/bin/{cmd}")
    tmux = next(c for c in checks if c.name == "tmux")
    assert tmux.level == doctor.FAIL
    assert "not found" in tmux.detail
    assert tmux.hint


def test_main_returns_nonzero_on_failure(monkeypatch, capsys):
    monkeypatch.setattr(
        doctor, "run_checks", lambda: [doctor.Check("tmux", doctor.FAIL, "missing", "install it")]
    )
    assert doctor.main() == 1
    assert "[FAIL] tmux" in capsys.readouterr().out


def test_lado_check_says_a_newer_version_is_available(published):
    published(**{"99.0.0": "2026-10-04"})
    check = doctor.check_lado()
    assert check.level == doctor.WARN
    assert check.detail == __version__
    assert check.hint == "LADO 99.0.0 is available: lado update"


def test_lado_check_says_why_the_update_check_failed(published, tmp_path, monkeypatch):
    monkeypatch.setenv("LADO_UPDATE_INDEX", str(tmp_path / "missing.json"))
    check = doctor.check_lado()
    assert check.level == doctor.WARN
    assert check.hint.startswith("cannot look up LADO's latest version: ")


def test_lado_check_of_the_latest_version_and_with_the_check_off(published, monkeypatch):
    published(**{__version__: "2026-10-04"})
    assert doctor.check_lado() == doctor.Check(
        "LADO", doctor.OK, f"{__version__}, the latest version"
    )
    monkeypatch.setenv("LADO_NO_UPDATE_CHECK", "1")
    assert doctor.check_lado() == doctor.Check(
        "LADO", doctor.OK, f"{__version__} (no update check: LADO_NO_UPDATE_CHECK=1)"
    )


def test_agent_environment_inherited():
    check = doctor.check_agent_env()  # the tests run with LADO_AGENT_ENV=inherit
    assert check.level == doctor.OK
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
    assert check.level == doctor.OK
    assert re.fullmatch(
        rf"from your login shell {login_shell}, resolved in \d+\.\d s", check.detail
    )


def test_a_slow_login_shell_warns(login_shell, monkeypatch):
    monkeypatch.setattr(agent_env, "SLOW", 0)
    check = doctor.check_agent_env()
    assert check.level == doctor.WARN
    assert "each agent's start waits for your shell" in check.hint


def test_a_failing_login_shell_fails(login_shell):
    login_shell.write_text("#!/bin/sh\necho 'rc is broken' >&2\nexit 2\n")
    check = doctor.check_agent_env()
    assert check.level == doctor.FAIL
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


def test_config_folders_of_agents_that_do_not_run_warn(repo, fake_tmux, lado_home):
    assert doctor.check_config_folders().level == doctor.OK  # no lado.db yet
    assert not (lado_home / "lado.db").exists()
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task", name="w1")
    assert doctor.check_config_folders() == doctor.Check(
        "Agent config folders", doctor.OK, "only those of running agents"
    )
    left = [lado_home / "agents" / "s" / "gone", lado_home / "agents" / "old"]
    for folder in left:
        (folder / "x").mkdir(parents=True)
    check = doctor.check_config_folders()
    assert check.level == doctor.WARN
    assert (
        check.detail
        == f"left by agents that do not run (they may hold secrets): {left[1]}, {left[0]}"
    )
    assert check.hint == f"remove them: rm -rf {left[1]} {left[0]}"


def test_artifacts_show_the_stores_size_and_warn_only_of_old_orphans(lado_home):
    assert doctor.check_artifacts() == doctor.Check("Artifacts", doctor.OK, "none")
    assert not (lado_home / "lado.db").exists()  # not made by the check
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    state.add_agent(state.Agent("s", "supervisor", "x", "/r", None, None, "idle", "claude"))
    artifacts.write("s", "supervisor", "big", content="x" * 3 * 1024 * 1024)
    artifacts.write("s", "supervisor", "big", content="y")
    assert doctor.check_artifacts() == doctor.Check(
        "Artifacts", doctor.OK, "1 artifact, 2 records, 3.0 MB"
    )
    young = lado_home / "artifacts" / "ab" / ("ab" + "0" * 62)
    young.parent.mkdir()
    young.write_bytes(b"1" * 1024 * 1024)  # a write in progress, maybe
    assert doctor.check_artifacts().level == doctor.OK
    old = time.time() - 2 * artifacts_local.ORPHAN_AGE
    os.utime(young, (old, old))
    assert doctor.check_artifacts() == doctor.Check(
        "Artifacts",
        doctor.WARN,
        "1 artifact, 2 records, 4.0 MB; 1 file no record refers to (1.0 MB)",
        "removed by the next lado forget",
    )


def test_artifacts_are_not_checked_on_another_schema(lado_home):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    agent_helpers.previous_schema()
    check = doctor.check_artifacts()
    assert (check.level, check.detail[:13]) == (doctor.INFO, "not checked: ")


@pytest.fixture
def mac(monkeypatch):
    """A Mac (gui_session): mac(process, server) sets where this process and LADO's tmux
    server run; Claude Code needs the keychain (no other login)."""
    monkeypatch.setattr(gui_session.sys, "platform", "darwin")
    monkeypatch.setattr(claude.sys, "platform", "darwin")
    for name in claude.LOGINS:
        monkeypatch.delenv(name, raising=False)

    def place(process, server):
        monkeypatch.setattr(gui_session, "place", lambda: Place(process))
        monkeypatch.setattr(gui_session, "server_place", lambda socket: server and Place(server))

    return place


def _graphical(which=lambda cmd: cmd):
    return next(c for c in doctor.run_checks(which=which) if c.name == "Graphical session")


def test_no_graphical_session_check_but_on_a_mac(monkeypatch):
    monkeypatch.setattr(gui_session.sys, "platform", "linux")
    names = [c.name for c in doctor.run_checks(which=lambda cmd: cmd)]
    assert "Graphical session" not in names
    assert doctor.system_info(which=lambda cmd: cmd).gui_session is None


@pytest.mark.parametrize(
    ("process", "server"),
    [("gui", "gui"), ("remote", "gui"), ("gui", None), ("remote", None), ("no-gui", "gui")],
)
def test_agents_in_the_graphical_session_are_ok(mac, process, server):
    mac(process, server)
    check = _graphical()
    assert check.level == doctor.OK
    assert check.detail == f"process: {process}, server: {server or 'none'}"


def _hint():
    return providers.get("claude").keychain_login({})


@pytest.mark.parametrize(
    ("process", "server", "text"),
    [
        ("gui", "remote", gui_session.OUTSIDE_GUI),
        ("remote", "no-gui", gui_session.OUTSIDE_GUI),
        ("no-gui", None, gui_session.NO_GUI),
        ("no-gui", "no-gui", gui_session.OUTSIDE_GUI),
    ],
)
def test_agents_that_cannot_read_the_keychain_are_a_warning(mac, process, server, text):
    mac(process, server)
    check = _graphical()
    assert check.level == doctor.WARN
    assert check.detail == f"process: {process}, server: {server or 'none'}"
    assert check.hint == gui_session.fill(text, [("Claude Code", _hint())])
    # With no provider installed that needs the keychain: the same fact, for information.
    check = _graphical(which=lambda cmd: None if cmd == "claude" else cmd)
    assert check.level == doctor.INFO
    assert check.hint == gui_session.fill(text, [])


@pytest.mark.parametrize(("process", "server"), [("unknown", None), ("gui", "unknown")])
def test_a_place_that_cannot_be_read_is_not_checked(mac, process, server):
    mac(process, server)
    check = _graphical()
    assert check.level == doctor.INFO
    assert check.detail.startswith("not checked: ")


def test_system_info_and_report_give_only_the_kind_of_place(mac):
    mac("remote", "gui")
    system = doctor.system_info(which=lambda cmd: cmd)
    assert system.gui_session == (Place.REMOTE, Place.GUI)
    report = doctor.report(system, False, 0)
    assert "- Graphical session: process remote, server gui\n" in report
    mac("no-gui", None)
    report = doctor.report(doctor.system_info(which=lambda cmd: cmd), False, 0)
    assert "- Graphical session: process no-gui, no tmux server\n" in report
