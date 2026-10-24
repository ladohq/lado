import dataclasses
import os
import re
import sqlite3
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
    project_secrets,
    projects,
    providers,
    runtime,
    state,
    update,
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
    monkeypatch.setattr(
        doctor, "_tool_version", lambda path, flag, timeout=None: versions.get(path, "v1")
    )


@pytest.fixture(autouse=True)
def _own_git_config(git_config):
    """The `git author` check reads the test's git config, never the user's."""
    return git_config


def test_all_checks_pass_when_tools_are_on_path(tmp_path, monkeypatch):
    _versions(monkeypatch)
    monkeypatch.setenv("LADO_REPOS", str(tmp_path))  # a workspace made
    monkeypatch.setattr(gui_session.sys, "platform", "linux")  # its check: below
    checks = doctor.run_checks(which=lambda cmd: cmd)
    names = [
        "LADO",
        "Python",
        "tmux",
        "git",
        "git author",
        "Workspace",
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


def test_outside_lists_names_and_files_not_used(tmp_path, monkeypatch):
    folder = tmp_path / "s"
    folder.mkdir()
    (folder / "YOUGILE_API_KEY").write_text("canary-1")
    (folder / "GH_TOKEN").write_text("canary-2")
    (folder / "a-b").write_text("canary-3")
    monkeypatch.setenv("LADO_ENV_DIR", str(folder))
    check = doctor.check_outside()
    assert check == doctor.Check(
        "Variables from outside",
        doctor.WARN,
        f"{folder}: GH_TOKEN, YOUGILE_API_KEY; a-b not used: not a variable name",
    )
    assert "Variables from outside" in [c.name for c in doctor.run_checks(which=lambda c: c)]


def test_outside_ok_none_and_no_folder(tmp_path, monkeypatch):
    name = "Variables from outside"
    monkeypatch.setenv("LADO_ENV_DIR", str(tmp_path))
    assert doctor.check_outside() == doctor.Check(name, doctor.OK, f"{tmp_path}: none")
    (tmp_path / "KEY").write_text("v")
    assert doctor.check_outside() == doctor.Check(name, doctor.OK, f"{tmp_path}: KEY")
    monkeypatch.setenv("LADO_ENV_DIR", str(tmp_path / "x"))
    assert doctor.check_outside() == doctor.Check(name, doctor.INFO, f"{tmp_path / 'x'}: no folder")
    monkeypatch.setenv("LADO_ENV_DIR", str(tmp_path))
    if os.geteuid() != 0:  # root lists any folder
        tmp_path.chmod(0)
        try:
            check = doctor.check_outside()
        finally:
            tmp_path.chmod(0o700)
        assert (check.level, check.detail.split(": cannot")[0]) == (
            doctor.WARN,
            f"variable folder {tmp_path} (LADO_ENV_DIR) not used",
        )
    monkeypatch.setenv("LADO_ENV_DIR", "rel")
    assert doctor.check_outside() == doctor.Check(
        name, doctor.WARN, "variable folder rel (LADO_ENV_DIR) not used: not an absolute path"
    )
    monkeypatch.setenv("LADO_ENV_DIR", "")
    assert doctor.check_outside() is None
    monkeypatch.delenv("LADO_ENV_DIR")
    assert doctor.check_outside() is None
    assert "Variables from outside" not in [c.name for c in doctor.run_checks(which=lambda c: c)]


SECRETS_HINT = (
    "to give the agents variables: LADO_SECRETS=./secrets in compose's .env and "
    "mkdir -m 700 secrets (docker run: -v <folder>:/run/secrets:ro); "
    "docs/install.md#the-agents-variables"
)


def test_no_secrets_in_a_container_says_how_to_give_them(tmp_path, monkeypatch, capsys):
    name = "Variables from outside"
    monkeypatch.setenv("LADO_CONTAINER", "1")
    for folder in (os.devnull, str(tmp_path / "x")):  # compose's default, docker run's none
        monkeypatch.setenv("LADO_ENV_DIR", folder)
        assert doctor.check_outside() == doctor.Check(
            name, doctor.INFO, f"{folder}: none", SECRETS_HINT
        )
    monkeypatch.setattr(doctor, "run_checks", lambda: [doctor.check_outside()])
    assert doctor.main() == 0
    assert (
        f"[info] {name}: {tmp_path / 'x'}: none\n       {SECRETS_HINT}" in capsys.readouterr().out
    )


def test_the_null_device_outside_a_container_is_no_folder(monkeypatch):
    monkeypatch.delenv("LADO_CONTAINER", raising=False)
    monkeypatch.setenv("LADO_ENV_DIR", os.devnull)
    assert doctor.check_outside() == doctor.Check(
        "Variables from outside", doctor.INFO, f"{os.devnull}: no folder"
    )


@pytest.mark.parametrize("container", ["1", ""])
def test_a_file_in_place_of_the_folder_warns_in_a_container_or_out(
    tmp_path, monkeypatch, container
):
    (tmp_path / "f").write_text("x")
    monkeypatch.setenv("LADO_CONTAINER", container)
    monkeypatch.setenv("LADO_ENV_DIR", str(tmp_path / "f"))
    assert doctor.check_outside() == doctor.Check(
        "Variables from outside",
        doctor.WARN,
        f"variable folder {tmp_path / 'f'} (LADO_ENV_DIR) not used: not a folder",
    )


def test_the_report_has_no_variable_name_or_value(tmp_path, monkeypatch):
    folder = tmp_path / "s"
    folder.mkdir()
    (folder / "SECRET_NAME_X").write_text("canary-3")
    monkeypatch.setenv("LADO_ENV_DIR", str(folder))
    text = doctor.report(doctor.system_info(which=lambda cmd: cmd), doctor.ServerState(False, 0))
    assert "SECRET_NAME_X" not in text and "canary-3" not in text


@pytest.fixture
def overlap(tmp_path, monkeypatch, lado_home):
    """The outside folder gives BOARD_URL, MODEL_URL and GH_TOKEN; project shop sets
    BOARD_URL and MODEL_URL, acme BOARD_URL, empty none."""
    folder = tmp_path / "s"
    folder.mkdir()
    for name in ("BOARD_URL", "MODEL_URL", "GH_TOKEN"):
        (folder / name).write_text(f"out-{name}")
    monkeypatch.setenv("LADO_ENV_DIR", str(folder))
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    for id in ("shop", "acme", "empty"):
        projects.create(id, None)
    projects.set_variable("shop", "MODEL_URL", "canary-m")
    projects.set_variable("shop", "BOARD_URL", "canary-b")
    projects.set_variable("acme", "BOARD_URL", "canary-a")
    projects.set_variable("empty", "OTHER", "canary-o")
    return folder


def test_project_variables_over_the_outside_folder_are_named(overlap):
    check = doctor.check_project_variables()
    assert check == doctor.Check(
        "Project variables",
        doctor.INFO,
        "acme overrides BOARD_URL of LADO_ENV_DIR; shop overrides BOARD_URL, MODEL_URL of "
        "LADO_ENV_DIR",
    )
    names = [c.name for c in doctor.run_checks(which=lambda c: c)]
    assert names[names.index("Variables from outside") + 1] == "Project variables"


def test_no_project_variables_line_without_an_overlap(overlap, monkeypatch):
    projects.unset_variable("shop", "BOARD_URL")
    projects.unset_variable("shop", "MODEL_URL")
    projects.unset_variable("acme", "BOARD_URL")
    assert doctor.check_project_variables() is None
    projects.set_variable("shop", "BOARD_URL", "x")
    monkeypatch.delenv("LADO_ENV_DIR")
    assert doctor.check_project_variables() is None
    names = [c.name for c in doctor.run_checks(which=lambda c: c)]
    assert "Project variables" not in names


def test_no_project_variables_line_without_a_database(tmp_path, monkeypatch, lado_home):
    folder = tmp_path / "s"
    folder.mkdir()
    (folder / "BOARD_URL").write_text("v")
    monkeypatch.setenv("LADO_ENV_DIR", str(folder))
    assert doctor.check_project_variables() is None
    assert not (lado_home / "lado.db").exists()


def test_no_project_variables_line_from_an_older_schema(overlap):
    agent_helpers.previous_schema()
    assert doctor.check_project_variables() is None
    assert state.schema_version() == state.SCHEMA_VERSION - 1  # nothing migrated


def test_doctor_and_the_report_hold_no_project_variable_s_value(overlap, capsys):
    doctor.main()
    out = capsys.readouterr().out
    assert "[info] Project variables: acme overrides BOARD_URL" in out
    assert "canary-" not in out
    text = doctor.report(doctor.system_info(which=lambda cmd: cmd), doctor.ServerState(False, 0))
    assert "canary-" not in text and "MODEL_URL" not in text and "OTHER" not in text


def test_a_project_secret_over_the_outside_folder_is_named(overlap):
    projects.set_secret("empty", "GH_TOKEN", "canary-g")
    check = doctor.check_project_variables()
    assert check is not None
    assert "empty overrides GH_TOKEN of LADO_ENV_DIR" in check.detail
    assert "canary-" not in check.detail


@pytest.fixture
def secrets(tmp_path, monkeypatch, lado_home):
    """Projects shop and acme, each with a usable secret."""
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    monkeypatch.delenv("LADO_ENV_DIR", raising=False)
    for id in ("shop", "acme"):
        projects.create(id, None)
        projects.set_secret(id, "GH_TOKEN", f"canary-{id}")


def test_no_project_secrets_line_when_every_file_is_usable(secrets):
    assert doctor.check_project_secrets() is None
    names = [c.name for c in doctor.run_checks(which=lambda c: c)]
    assert "Project secrets" not in names


def test_project_secret_files_not_used_are_named_without_their_value(
    secrets, tmp_path, capsys, monkeypatch
):
    folder = project_secrets.folder("shop")
    (folder / "GH_TOKEN").chmod(0o644)
    (tmp_path / "t").write_text("canary-link")
    (folder / "X").symlink_to(tmp_path / "t")
    (folder / "BIG").write_bytes(b"canary-big" * 7000)
    (folder / "BIG").chmod(0o600)
    project_secrets.folder("acme").chmod(0o755)
    check = doctor.check_project_secrets()
    assert check == doctor.Check(
        "Project secrets",
        doctor.WARN,
        "acme: secrets folder not used: readable or writable by others: chmod 700 it; "
        "shop: BIG not used: larger than 64 KiB; "
        "shop: GH_TOKEN not used: readable or writable by others: chmod 600 it; "
        "shop: X not used: a symbolic link",
    )
    assert "canary-" not in "\n".join(c.detail for c in doctor.run_checks(which=lambda c: c))
    # The exit code with this check alone: a machine without agent CLIs fails others.
    monkeypatch.setattr(doctor, "run_checks", lambda: [doctor.check_project_secrets()])
    assert doctor.main() == 0
    out = capsys.readouterr().out
    assert "[warn] Project secrets: acme: secrets folder not used" in out
    assert "canary-" not in out


def test_no_project_secrets_line_without_a_database(lado_home):
    assert doctor.check_project_secrets() is None
    assert not (lado_home / "lado.db").exists()


def test_the_report_holds_no_project_secret(secrets):
    project_secrets.folder("shop").chmod(0o755)
    text = doctor.report(doctor.system_info(which=lambda cmd: cmd), doctor.ServerState(False, 0))
    assert "canary-" not in text and "GH_TOKEN" not in text


@pytest.fixture
def default_home(home_workspace, tmp_path, monkeypatch):
    """No LADO_REPOS, HOME in tmp_path: the workspace is <tmp>/workspace."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LADO_REPOS", raising=False)
    return tmp_path / "workspace"


def test_the_default_workspace_line(default_home):
    name = "Workspace"
    assert doctor.check_workspace() == doctor.Check(
        name,
        doctor.INFO,
        f"{default_home} (default), not made yet: the first clone or project makes it",
    )
    default_home.mkdir()
    assert doctor.check_workspace() == doctor.Check(name, doctor.OK, f"{default_home} (default)")
    default_home.rmdir()
    default_home.write_text("")
    assert doctor.check_workspace() == doctor.Check(
        name, doctor.WARN, f"the workspace is not a folder: {default_home}"
    )


def test_the_workspace_line_of_lado_repos(tmp_path, monkeypatch):
    name = "Workspace"
    monkeypatch.setenv("LADO_REPOS", str(tmp_path))
    assert doctor.check_workspace() == doctor.Check(name, doctor.OK, f"{tmp_path} (LADO_REPOS)")
    missing = tmp_path / "repos"
    monkeypatch.setenv("LADO_REPOS", str(missing))
    assert doctor.check_workspace() == doctor.Check(
        name,
        doctor.INFO,
        f"{missing} (LADO_REPOS), not made yet: the first clone or project makes it",
    )
    afile = tmp_path / "file"
    afile.write_text("")
    monkeypatch.setenv("LADO_REPOS", str(afile))
    assert doctor.check_workspace() == doctor.Check(
        name, doctor.WARN, f"LADO_REPOS is not a folder: {afile}"
    )


def test_a_relative_lado_repos_is_ignored_for_the_default(default_home, monkeypatch):
    monkeypatch.setenv("LADO_REPOS", "code")
    assert doctor.check_workspace() == doctor.Check(
        "Workspace",
        doctor.WARN,
        f"LADO_REPOS is not an absolute path: code; LADO uses {default_home}",
        "set it to a full path, e.g. ~/repos or /Users/me/repos",
    )


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any folder")
def test_a_repositories_folder_lado_may_not_look_at_warns_with_the_reason(tmp_path, monkeypatch):
    closed = tmp_path / "closed"
    closed.mkdir(mode=0)
    folder = closed / "repos"
    monkeypatch.setenv("LADO_REPOS", str(folder))
    try:
        check = doctor.check_workspace()
    finally:
        closed.chmod(0o700)
    assert (check.name, check.level) == ("Workspace", doctor.WARN)
    assert check.detail.startswith(f"cannot look at LADO_REPOS {folder}: ")
    assert "Permission denied" in check.detail


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes in any folder")
def test_a_repositories_folder_lado_may_not_write_in_warns(tmp_path, monkeypatch):
    folder = tmp_path / "repos"
    folder.mkdir(mode=0o555)
    monkeypatch.setenv("LADO_REPOS", str(folder))
    try:
        check = doctor.check_workspace()
    finally:
        folder.chmod(0o755)
    assert (check.name, check.level) == ("Workspace", doctor.WARN)
    assert check.detail.startswith(f"LADO may not write in LADO_REPOS {folder}: ")
    assert "Permission denied" in check.detail
    assert check.hint.startswith("give your user write access to it")
    assert list(folder.iterdir()) == []


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes in any folder")
def test_a_default_workspace_lado_may_not_write_in_warns(default_home):
    default_home.mkdir(mode=0o555)
    try:
        check = doctor.check_workspace()
    finally:
        default_home.chmod(0o755)
    assert check.level == doctor.WARN
    assert check.detail.startswith(f"LADO may not write in the workspace {default_home}: ")


def test_the_write_check_leaves_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("LADO_REPOS", str(tmp_path))
    assert doctor.check_workspace().level == doctor.OK
    assert list(tmp_path.iterdir()) == []


def test_the_checks_always_hold_the_workspace(tmp_path, monkeypatch):
    _versions(monkeypatch)
    monkeypatch.setattr(gui_session.sys, "platform", "linux")

    def names():
        return [c.name for c in doctor.run_checks(which=lambda cmd: cmd)]

    found = names()
    assert found[found.index("git author") + 1] == "Workspace"
    monkeypatch.setenv("LADO_REPOS", str(tmp_path))
    found = names()
    assert found[found.index("git author") + 1] == "Workspace"


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
    assert check.detail == update.shown(__version__)
    assert check.hint == "LADO 99.0.0 is available: lado update"


def test_lado_check_says_why_the_update_check_failed(published, tmp_path, monkeypatch):
    monkeypatch.setenv("LADO_UPDATE_INDEX", str(tmp_path / "missing.json"))
    check = doctor.check_lado()
    assert check.level == doctor.WARN
    assert check.hint.startswith("cannot look up LADO's latest version: ")


def test_lado_check_of_the_latest_version_and_with_the_check_off(published, monkeypatch):
    published(**{__version__: "2026-10-04"})
    shown = update.shown(__version__)  # a release candidate says so
    assert doctor.check_lado() == doctor.Check("LADO", doctor.OK, f"{shown}, the latest version")
    monkeypatch.setenv("LADO_NO_UPDATE_CHECK", "1")
    assert doctor.check_lado() == doctor.Check(
        "LADO", doctor.OK, f"{shown} (no update check: LADO_NO_UPDATE_CHECK=1)"
    )


def test_lado_check_says_this_lado_is_a_pre_release(published, monkeypatch):
    import lado

    monkeypatch.setattr(lado, "__version__", "0.37.0rc2", raising=False)
    published(**{"0.37.0rc2": "2026-10-04"})
    assert doctor.check_lado() == doctor.Check(
        "LADO", doctor.OK, "0.37.0rc2 (pre-release), the latest version"
    )
    published(**{"0.37.0rc2": "2026-10-04", "0.37.0": "2026-10-06"})
    update.cache_path().unlink()  # the next look reads the new index
    assert doctor.check_lado() == doctor.Check(
        "LADO", doctor.WARN, "0.37.0rc2 (pre-release)", "LADO 0.37.0 is available: lado update"
    )
    monkeypatch.setenv("LADO_NO_UPDATE_CHECK", "1")
    assert doctor.check_lado() == doctor.Check(
        "LADO", doctor.OK, "0.37.0rc2 (pre-release) (no update check: LADO_NO_UPDATE_CHECK=1)"
    )


def test_lado_check_says_lado_runs_in_a_container(published, monkeypatch):
    import lado

    monkeypatch.setattr(lado, "__version__", "0.38.0", raising=False)
    monkeypatch.setenv("LADO_CONTAINER", "1")
    published(**{"0.38.0": "2026-10-04"})
    assert doctor.check_lado() == doctor.Check(
        "LADO", doctor.OK, "0.38.0, the latest version, in a container"
    )
    published(**{"0.38.0": "2026-10-04", "0.39.0": "2026-10-06"})
    update.cache_path().unlink()  # the next look reads the new index
    assert doctor.check_lado() == doctor.Check(
        "LADO",
        doctor.WARN,
        "0.38.0, in a container",
        "LADO 0.39.0 is available: a new image updates LADO in a container "
        "(ghcr.io/ladohq/lado:0.39.0)",
    )
    monkeypatch.setenv("LADO_NO_UPDATE_CHECK", "1")
    assert doctor.check_lado() == doctor.Check(
        "LADO", doctor.OK, "0.38.0 (no update check: LADO_NO_UPDATE_CHECK=1), in a container"
    )


def test_system_info_and_the_report_say_lado_runs_in_a_container(monkeypatch):
    import lado

    monkeypatch.setattr(lado, "__version__", "0.38.0", raising=False)
    server = doctor.ServerState(False, 0)
    outside = doctor.system_info(which=lambda cmd: cmd)
    assert outside.container is False
    assert "in a container" not in doctor.report(outside, server)
    monkeypatch.setenv("LADO_CONTAINER", "1")
    inside = doctor.system_info(which=lambda cmd: cmd)
    assert inside.container is True
    uv_tool = dataclasses.replace(inside, installer="uv tool")
    assert "- LADO 0.38.0 (uv tool, in a container), Python " in doctor.report(uv_tool, server)
    none = dataclasses.replace(inside, installer=None)
    assert "- LADO 0.38.0 (no uv tool or pipx install, in a container), Python " in (
        doctor.report(none, server)
    )


def test_the_report_says_this_lado_is_a_pre_release(monkeypatch):
    import lado

    monkeypatch.setattr(lado, "__version__", "0.37.0rc1", raising=False)
    report = doctor.report(doctor.system_info(which=lambda cmd: cmd), doctor.ServerState(False, 0))
    assert "- LADO 0.37.0rc1 (pre-release) (" in report
    monkeypatch.setattr(lado, "__version__", "0.36.0", raising=False)
    report = doctor.report(doctor.system_info(which=lambda cmd: cmd), doctor.ServerState(False, 0))
    assert "- LADO 0.36.0 (" in report


def test_agent_environment_inherited():
    (check,) = doctor.check_agent_env()  # the tests run with LADO_AGENT_ENV=inherit
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


def _base(monkeypatch, *, source="path_helper", reason="", wsl=False):
    base = agent_env.BasePath("/usr/bin:/bin", source, reason, wsl)
    monkeypatch.setattr(agent_env, "base_path", lambda: base)


def test_agent_environment_from_the_login_shell(login_shell, monkeypatch):
    _base(monkeypatch, source="/etc/environment")
    (check,) = doctor.check_agent_env()
    assert check.level == doctor.OK
    assert re.fullmatch(
        rf"from your login shell {login_shell}, resolved in \d+\.\d s; "
        r"starting PATH from /etc/environment",
        check.detail,
    )


def test_agent_environment_names_why_the_path_starts_from_the_default(login_shell, monkeypatch):
    _base(monkeypatch, source="default", reason="no PATH in /etc/environment")
    (check,) = doctor.check_agent_env()
    assert check.level == doctor.OK
    assert check.detail.endswith("; starting PATH from the default (no PATH in /etc/environment)")


def test_on_wsl_doctor_says_the_windows_path_is_not_passed(login_shell, monkeypatch):
    _base(monkeypatch, source="/etc/environment", wsl=True)
    check, windows = doctor.check_agent_env()
    assert check.level == doctor.OK
    assert windows == doctor.Check(
        "Windows PATH",
        doctor.INFO,
        "not passed to agents",
        "add a Windows folder to PATH in ~/.profile to give it to them",
    )


def test_an_inherited_environment_on_wsl_says_nothing_of_the_windows_path(monkeypatch):
    _base(monkeypatch, wsl=True)
    (check,) = doctor.check_agent_env()
    assert "LADO_AGENT_ENV=inherit" in check.detail


def test_a_slow_login_shell_warns(login_shell, monkeypatch):
    _base(monkeypatch)
    monkeypatch.setattr(agent_env, "SLOW", 0)
    (check,) = doctor.check_agent_env()
    assert check.level == doctor.WARN
    assert "each agent's start waits for your shell" in check.hint


def test_a_failing_login_shell_fails(login_shell):
    login_shell.write_text("#!/bin/sh\necho 'rc is broken' >&2\nexit 2\n")
    (check,) = doctor.check_agent_env()
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
    assert check == doctor.Check("Artifacts", doctor.INFO, doctor.NOT_AT_SCHEMA)


OLDER = state.SCHEMA_VERSION - 1


def _unchanged(lado_home, version: int) -> None:
    """lado doctor read lado.db as it is: its schema `version`, no backup made."""
    assert state.schema_version() == version
    backups = lado_home / "backups"
    assert not backups.exists() or not any(backups.iterdir())


def _doctor_on_linux(monkeypatch, capsys) -> tuple[int, str]:
    _versions(monkeypatch)
    monkeypatch.setattr(gui_session.sys, "platform", "linux")
    return _doctor_output(monkeypatch, capsys)


def test_the_first_doctor_after_an_upgrade_says_what_upgrades_lado_db(
    repo, fake_tmux, lado_home, monkeypatch, capsys
):
    runtime.start_session(str(repo), "old", None, provider="claude")
    runtime.stop_session("old")
    status_before, _ = _doctor_on_linux(monkeypatch, capsys)
    agent_helpers.previous_schema()
    status = doctor.main()
    out = capsys.readouterr().out
    lines = out.splitlines()
    lado_line = next(i for i, line in enumerate(lines) if line.startswith("[ok  ] LADO: "))
    assert lines[lado_line + 1] == (
        f"[info] lado.db: schema {OLDER}, this LADO knows {state.SCHEMA_VERSION}: lado ls or "
        "lado start upgrades it (its backup goes to backups/)"
    )
    assert f"[info] Artifacts: {doctor.NOT_AT_SCHEMA}" in lines
    assert f"[info] Agent config folders: {doctor.NOT_AT_SCHEMA}" in lines
    assert "upgraded under a running session" not in out
    assert status == status_before
    _unchanged(lado_home, OLDER)


def test_lado_db_names_the_running_sessions_that_keep_it_older(repo, fake_tmux, lado_home):
    from lado import tmux

    for name in ("a", "b", "c"):
        runtime.start_session(str(repo), name, None, provider="claude")
    tmux.kill_session("c")  # not stopped, but gone from tmux
    agent_helpers.previous_schema()
    assert doctor.check_database() == doctor.Check(
        "lado.db",
        doctor.WARN,
        f'schema {OLDER}, this LADO knows {state.SCHEMA_VERSION}, and the sessions "a", "b" '
        "run on it",
        "stop them with lado stop --all (it upgrades lado.db), then lado start",
    )
    _unchanged(lado_home, OLDER)


def test_lado_db_of_a_newer_lado(lado_home):
    lado_home.mkdir()
    sqlite3.connect(lado_home / "lado.db").execute(
        f"PRAGMA user_version = {state.SCHEMA_VERSION + 1}"
    )
    check = doctor.check_database()
    assert (check.name, check.level) == ("lado.db", doctor.WARN)
    assert "newer LADO" in check.detail and "upgrade LADO" in check.detail
    _unchanged(lado_home, state.SCHEMA_VERSION + 1)


def test_an_incompatible_lado_db_fails_the_doctor(lado_home, monkeypatch, capsys):
    lado_home.mkdir()
    sqlite3.connect(lado_home / "lado.db").execute("CREATE TABLE sessions (name TEXT)")
    status, out = _doctor_on_linux(monkeypatch, capsys)
    assert status == 1
    assert "[FAIL] lado.db: " in out and "incompatible schema" in out
    _unchanged(lado_home, 0)


def test_no_lado_db_line_at_this_schema_or_with_no_lado_db(lado_home):
    assert doctor.check_database() is None
    assert not (lado_home / "lado.db").exists()
    state.list_sessions()
    assert doctor.check_database() is None
    _unchanged(lado_home, state.SCHEMA_VERSION)


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


def _git_on_path(tmp_path, monkeypatch, script: str | None) -> str:
    """PATH of one folder, with a `git` running `script` (sh) in it, or none."""
    bin_dir = tmp_path / "git-bin"
    bin_dir.mkdir()
    if script is not None:
        git = bin_dir / "git"
        git.write_text(f"#!/bin/sh\n{script}\n")
        git.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    return str(bin_dir)


def _git_check(which=lambda cmd: cmd) -> doctor.Check:
    return next(c for c in doctor.run_checks(which=which) if c.name == "git")


def test_git_missing_fails_with_the_install_hint(tmp_path, monkeypatch):
    _versions(monkeypatch)
    monkeypatch.setattr(runtime.platform, "system", lambda: "Linux")
    path = _git_on_path(tmp_path, monkeypatch, None)
    check = _git_check()
    assert (check.level, check.detail) == (
        doctor.FAIL,
        f"git is not installed or not on PATH ({path})",
    )
    assert "sudo apt install git" in check.hint
    names = [c.name for c in doctor.run_checks(which=lambda cmd: cmd)]
    assert names.index("git") == names.index("tmux") + 1


def test_doctor_exits_1_without_git(tmp_path, monkeypatch, capsys):
    _versions(monkeypatch)
    _git_on_path(tmp_path, monkeypatch, None)
    checks = doctor.run_checks
    monkeypatch.setattr(doctor, "run_checks", lambda: checks(which=lambda cmd: cmd))
    assert doctor.main() == 1
    assert "[FAIL] git" in capsys.readouterr().out


def test_the_macos_stub_fails_with_xcode_tools(tmp_path, monkeypatch):
    _versions(monkeypatch)
    monkeypatch.setattr(runtime.platform, "system", lambda: "Darwin")
    _git_on_path(
        tmp_path, monkeypatch, "echo 'xcrun: error: invalid active developer path' >&2\nexit 1"
    )
    check = _git_check()
    assert (check.level, check.detail) == (
        doctor.FAIL,
        "git does not run: xcrun: error: invalid active developer path",
    )
    assert "xcode-select --install" in check.hint


def test_an_old_git_warns_and_keeps_the_exit_status(tmp_path, monkeypatch, capsys):
    _versions(monkeypatch)
    monkeypatch.setattr(gui_session.sys, "platform", "linux")
    _git_on_path(tmp_path, monkeypatch, "echo 'git version 2.30.2'")
    check = _git_check()
    assert (check.level, check.detail) == (doctor.WARN, "git version 2.30.2")
    assert "2.31" in check.hint
    assert "--path-format=absolute" in check.hint
    checks = doctor.run_checks
    monkeypatch.setattr(doctor, "run_checks", lambda: checks(which=lambda cmd: cmd))
    assert doctor.main() == 0


@pytest.mark.parametrize("version", ["git version 2.47.1", "git version 2.39.5 (Apple Git-154)"])
def test_a_current_git_is_ok_with_its_version(tmp_path, monkeypatch, version):
    _versions(monkeypatch)
    _git_on_path(tmp_path, monkeypatch, f"echo '{version}'")
    check = _git_check()
    assert (check.level, check.detail, check.hint) == (doctor.OK, version, "")


def _doctor_output(monkeypatch, capsys) -> tuple[int, str]:
    checks = doctor.run_checks
    monkeypatch.setattr(doctor, "run_checks", lambda: checks(which=lambda cmd: cmd))
    status = doctor.main()
    return status, capsys.readouterr().out


def test_a_machine_whose_git_knows_the_author(monkeypatch, capsys):
    _versions(monkeypatch)
    status, out = _doctor_output(monkeypatch, capsys)
    assert "[ok  ] git author: user.name and user.email set\n" in out
    assert "LADO test" not in out and "test@lado.invalid" not in out


def test_a_fresh_machine(git_config, monkeypatch, capsys):
    _versions(monkeypatch)
    status_before, _ = _doctor_output(monkeypatch, capsys)  # git knows the author
    git_config.write_text("[user]\n\tname = Ann Example\n")
    status = doctor.main()
    out = capsys.readouterr().out
    assert (
        "[warn] git author: no user.name or user.email: agents cannot commit\n"
        "       Tell git who you are, once for this computer: git config --global user.name "
        '"Your Name" && git config --global user.email you@example.com\n'
    ) in out
    assert "Ann Example" not in out
    assert status == status_before


def test_the_containers_git_author_hint(git_config, monkeypatch):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    git_config.write_text("")
    check = doctor.check_git_author()
    assert (check.name, check.level) == ("git author", doctor.WARN)
    assert check.hint == (
        "Set LADO_GIT_NAME and LADO_GIT_EMAIL in the .env file next to compose.yaml, then "
        "restart LADO there: docker compose up -d"
    )


def test_no_git_author_line_without_git(tmp_path, monkeypatch):
    _versions(monkeypatch)
    _git_on_path(tmp_path, monkeypatch, None)
    assert doctor.check_git_author() is None
    names = [c.name for c in doctor.run_checks(which=lambda cmd: cmd)]
    assert "git" in names and "git author" not in names


@pytest.mark.parametrize(
    ("script", "shown"),
    [
        ("echo 'git version 2.47.1'", "2.47.1"),
        ("echo 'git version 2.39.5 (Apple Git-154)'", "2.39.5 (Apple Git-154)"),
        (None, "not installed"),
        ("echo 'xcrun: error' >&2\nexit 1", "does not run"),
    ],
)
def test_system_info_and_report_give_gits_version_never_its_path(
    tmp_path, monkeypatch, script, shown
):
    path = _git_on_path(tmp_path, monkeypatch, script)
    system = doctor.system_info(which=lambda cmd: cmd)
    assert system.git == shown
    report = doctor.report(system, doctor.ServerState(False, 0))
    assert f"- git: {shown}\n" in report
    assert path not in report


def test_system_info_and_report_give_only_the_kind_of_place(mac):
    mac("remote", "gui")
    system = doctor.system_info(which=lambda cmd: cmd)
    assert system.gui_session == (Place.REMOTE, Place.GUI)
    report = doctor.report(system, doctor.ServerState(False, 0))
    assert "- Graphical session: process remote, server gui\n" in report
    mac("no-gui", None)
    report = doctor.report(doctor.system_info(which=lambda cmd: cmd), doctor.ServerState(False, 0))
    assert "- Graphical session: process no-gui, no tmux server\n" in report


@pytest.mark.parametrize(
    ("consent", "env", "line"),
    [
        ("on", {}, "- Statistics: on"),
        ("off", {}, "- Statistics: off"),
        (None, {}, "- Statistics: not chosen"),
        ("on", {"DO_NOT_TRACK": "1"}, "- Statistics: off by DO_NOT_TRACK=1"),
    ],
)
def test_report_has_statistics_line(telemetry_on, monkeypatch, consent, env, line):
    from lado import telemetry

    if consent:
        telemetry.choose(consent)
    else:
        (state.home() / "telemetry" / "consent.json").unlink()
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    report = doctor.report(doctor.system_info(which=lambda cmd: None), doctor.ServerState(False, 0))
    assert line in report.splitlines()


def test_report_statistics_without_an_endpoint(monkeypatch):
    from lado import telemetry

    monkeypatch.delenv("LADO_TELEMETRY")
    monkeypatch.setattr(telemetry, "PROJECT_TOKEN", "")
    report = doctor.report(doctor.system_info(which=lambda cmd: None), doctor.ServerState(False, 0))
    assert "- Statistics: off: no endpoint" in report.splitlines()


@pytest.mark.parametrize(
    ("server", "line"),
    [
        (doctor.ServerState(False, 8040), "- Server: loopback only, up 2 h 14 min, schema "),
        (doctor.ServerState(True, 60), "- Server: open to the network, up 1 min, schema "),
        (doctor.ServerState(False, None), "- Server: running, loopback only, schema "),
        (doctor.ServerState(True, None), "- Server: running, open to the network, schema "),
        (None, "- Server: not running, schema "),
    ],
)
def test_report_server_line(server, line):
    report = doctor.report(doctor.system_info(which=lambda cmd: None), server)
    [found] = [text for text in report.splitlines() if text.startswith("- Server: ")]
    assert found.startswith(line)


@pytest.mark.parametrize(
    ("server", "line"),
    [
        (doctor.ServerState(True, 60), "- Server: in a container, up 1 min, schema "),
        (doctor.ServerState(True, None), "- Server: running, in a container, schema "),
        (doctor.ServerState(False, None), "- Server: running, in a container, schema "),
        (None, "- Server: not running, schema "),
    ],
)
def test_report_server_line_in_a_container(server, line):
    system = dataclasses.replace(doctor.system_info(which=lambda cmd: None), container=True)
    report = doctor.report(system, server)
    [found] = [text for text in report.splitlines() if text.startswith("- Server: ")]
    assert found.startswith(line)


# Projects (openspec change projects-in-core)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    return tmp_path / "ws"


def test_no_projects_line_before_any_project(ws):
    assert doctor.check_projects() is None
    ws.mkdir()
    assert doctor.check_projects() is None


def test_projects_all_well(ws):
    projects.create("shop", None)
    projects.create("acme", None)
    assert doctor.check_projects() == doctor.Check("Projects", doctor.OK, f"2 in {ws / 'projects'}")


def test_a_project_without_its_folder_and_a_foreign_folder(ws):
    projects.create("shop", None)
    projects.create("acme", None)
    (ws / "projects" / "acme").rmdir()
    (ws / "projects" / "old").mkdir()
    assert doctor.check_projects() == doctor.Check(
        "Projects",
        doctor.WARN,
        f"acme: folder not found {ws / 'projects' / 'acme'}; foreign folder in projects/: old",
    )


def test_projects_that_is_the_humans_own_folder(ws):
    (ws / "projects" / "notes").mkdir(parents=True)
    assert doctor.check_projects() == doctor.Check(
        "Projects",
        doctor.WARN,
        f"{ws / 'projects'} is your own folder (it holds notes): LADO cannot make projects there",
    )


def test_projects_that_is_a_file(ws):
    ws.mkdir()
    (ws / "projects").write_text("")
    assert doctor.check_projects() == doctor.Check(
        "Projects", doctor.WARN, f"{ws / 'projects'} is not a folder"
    )


def test_the_projects_line_follows_the_workspace(ws, monkeypatch):
    _versions(monkeypatch)
    monkeypatch.setattr(gui_session.sys, "platform", "linux")
    projects.create("shop", None)
    found = [c.name for c in doctor.run_checks(which=lambda cmd: cmd)]
    assert found[found.index("Workspace") + 1] == "Projects"


def test_the_projects_check_makes_no_lado_db(ws, lado_home):
    (ws / "projects" / "notes").mkdir(parents=True)
    assert doctor.check_projects().level == doctor.WARN
    assert not (lado_home / "lado.db").exists()


def test_the_projects_check_on_an_older_lado_db(ws, lado_home):
    projects.create("shop", None)
    agent_helpers.previous_schema()
    assert doctor.check_projects() == doctor.Check("Projects", doctor.INFO, doctor.NOT_AT_SCHEMA)
    assert state.schema_version() == state.SCHEMA_VERSION - 1  # nothing migrated
