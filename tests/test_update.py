import hashlib
import json
import os
import shlex
import sys
import zipfile

import pytest
from agent_helpers import init_repo, wheel
from agent_helpers import pypi_index as index

from lado import __version__, loop, runtime, state, tmux, update
from lado.cli import main
from lado.server import run as server_run


@pytest.mark.parametrize(
    "older, newer",
    [
        ("0.9.0", "0.10.0"),
        ("0.19.9", "0.20.0"),
        ("1.0.0rc1", "1.0.0"),
        ("1.0.0a2", "1.0.0b1"),
        ("1.0.0b3", "1.0.0rc1"),
        ("1.0.0rc1", "1.0.0rc2"),
        ("1.0.0.dev1", "1.0.0a1"),
        ("1.0.0", "1.0.0.post1"),
        ("1.0", "1.0.1"),
    ],
)
def test_versions_compare_as_pep_440_says(older, newer):
    assert update.newer(newer, older)
    assert not update.newer(older, newer)


def test_the_same_version_is_not_newer():
    assert not update.newer("1.0", "1.0.0")
    assert not update.newer("0.20.0", "v0.20.0")


def test_a_version_that_cannot_be_read_is_never_newer():
    assert not update.newer("banana", "0.1.0")
    assert not update.newer("0.1.0", "banana")


def test_the_latest_release_skips_pre_releases_yanked_and_empty_ones():
    data = index(
        **{
            "0.19.0": "2026-10-01",
            "0.20.0": "2026-10-04",
            "0.21.0rc1": "2026-10-05",
            "0.22.0": [{"upload_time_iso_8601": "2026-10-06T01:00:00Z", "yanked": True}],
            "0.23.0": [],
        }
    )
    assert update.latest(data) == update.Release("0.20.0", "2026-10-04")


def test_the_latest_of_all_releases_takes_pre_releases_but_not_yanked_ones():
    data = index(
        **{
            "0.36.0": "2026-10-01",
            "0.37.0rc1": "2026-10-05",
            "0.37.0rc2": [{"upload_time_iso_8601": "2026-10-06T01:00:00Z", "yanked": True}],
        }
    )
    assert update.latest(data, pre=True) == update.Release("0.37.0rc1", "2026-10-05")


@pytest.mark.parametrize(
    "current, releases, offered",
    [
        ("0.36.0", ["0.36.0", "0.37.0rc1"], "0.36.0"),
        ("0.36.0", ["0.37.0rc1", "0.37.0"], "0.37.0"),
        ("0.37.0rc1", ["0.36.0", "0.37.0rc1", "0.37.0rc2"], "0.37.0rc2"),
        ("0.37.0rc2", ["0.37.0rc2", "0.37.0"], "0.37.0"),
    ],
)
def test_a_release_candidate_is_offered_only_to_a_pre_release(current, releases, offered):
    data = index(**{version: "2026-10-01" for version in releases})
    assert update.offered(data, current).version == offered


def test_a_pre_release_is_shown_as_one():
    assert update.shown("0.37.0rc1") == "0.37.0rc1 (pre-release)"
    assert update.shown("0.36.0") == "0.36.0"


def test_the_check_keeps_the_kind_it_looked_for_and_looks_again_for_another(
    published, lado_home, monkeypatch
):
    import lado

    published(**{"0.36.0": "2026-10-01", "0.37.0rc1": "2026-10-05"})
    monkeypatch.setattr(lado, "__version__", "0.37.0rc1", raising=False)
    assert update.check().latest == "0.37.0rc1"
    cache = lado_home / "update-check.json"
    assert json.loads(cache.read_text())["pre"] is True
    monkeypatch.setattr(lado, "__version__", "0.36.0", raising=False)
    checked = update.check()  # a fresh cache of the other kind: looked at again
    assert checked.latest == "0.36.0" and checked.available is None
    assert json.loads(cache.read_text())["pre"] is False


def test_a_failed_look_keeps_no_release_of_the_other_kind(
    published, lado_home, tmp_path, monkeypatch
):
    import lado

    published(**{"0.36.0": "2026-10-01", "99.0.0rc1": "2026-10-05"})
    monkeypatch.setattr(lado, "__version__", "0.37.0rc1", raising=False)
    assert update.check().available == "99.0.0rc1"
    monkeypatch.setattr(lado, "__version__", "0.36.0", raising=False)
    monkeypatch.setenv("LADO_UPDATE_INDEX", str(tmp_path / "missing.json"))
    failed = update.check()
    assert failed.error and failed.latest is None and failed.available is None


def test_a_cache_without_its_kind_is_one_of_final_releases(published, lado_home, monkeypatch):
    import lado

    published(**{"0.36.0": "2026-10-01", "0.37.0rc1": "2026-10-05"})
    monkeypatch.setattr(lado, "__version__", "0.36.0", raising=False)
    update.check()
    cache = lado_home / "update-check.json"
    old = json.loads(cache.read_text())
    del old["pre"]
    old["latest"] = "0.35.0"
    cache.write_text(json.dumps(old))
    assert update.check().latest == "0.35.0"  # read as `pre: false`: no new look
    monkeypatch.setattr(lado, "__version__", "0.37.0rc1", raising=False)
    assert update.check().latest == "0.37.0rc1"


def test_a_named_release_is_found_also_a_pre_release_and_not_an_unknown_one():
    data = index(**{"0.19.0": "2026-10-01", "0.21.0rc1": "2026-10-05"})
    assert update.release(data, "0.19.0") == update.Release("0.19.0", "2026-10-01")
    assert update.release(data, "v0.19.0") == update.Release("0.19.0", "2026-10-01")
    assert update.release(data, "0.21.0rc1") == update.Release("0.21.0rc1", "2026-10-05")
    assert update.release(data, "0.18.0") is None


def test_the_index_is_read_from_the_file_the_tests_name(tmp_path, monkeypatch):
    path = tmp_path / "index.json"
    path.write_text(json.dumps(index(**{"0.19.0": "2026-10-01"})))
    monkeypatch.setenv("LADO_UPDATE_INDEX", str(path))
    assert update.latest(update.fetch_index()) == update.Release("0.19.0", "2026-10-01")


def test_the_check_tells_a_newer_version_and_asks_the_index_once_a_day(published, lado_home):
    published(**{"99.0.0": "2026-10-04"})
    first = update.check()
    assert first.latest == "99.0.0" and first.error is None
    assert update.available_line(first) == "LADO 99.0.0 is available: lado update"
    published(**{"99.1.0": "2026-10-05"})
    assert update.check().latest == "99.0.0"  # from the cache, no new look
    cache = lado_home / "update-check.json"
    stale = json.loads(cache.read_text())
    stale["checked_at"] = "2026-01-01T00:00:00+00:00"
    cache.write_text(json.dumps(stale))
    assert update.check().latest == "99.1.0"


def test_the_check_says_nothing_for_the_installed_or_an_older_version(published):
    published(**{"0.0.1": "2020-01-01"})
    assert update.available_line(update.check()) is None


def test_a_failed_check_is_kept_in_the_cache_until_the_next_day(
    published, lado_home, tmp_path, monkeypatch
):
    index_path = published(**{"99.0.0": "2026-10-04"})
    monkeypatch.setenv("LADO_UPDATE_INDEX", str(tmp_path / "missing.json"))
    failed = update.check()
    assert failed.latest is None and "missing.json" in failed.error
    assert update.available_line(failed) is None
    assert "missing.json" in json.loads((lado_home / "update-check.json").read_text())["error"]
    monkeypatch.setenv("LADO_UPDATE_INDEX", str(index_path))
    assert update.check().error == failed.error  # no new look before a day has passed


@pytest.mark.parametrize(
    "value, inside", [(None, False), ("", False), ("0", False), ("1", True), ("yes", True)]
)
def test_lado_runs_in_a_container_only_when_lado_container_says_so(monkeypatch, value, inside):
    if value is None:
        monkeypatch.delenv("LADO_CONTAINER", raising=False)
    else:
        monkeypatch.setenv("LADO_CONTAINER", value)
    assert update.in_container() is inside


def test_the_line_of_a_newer_version_names_the_image_in_a_container(published, monkeypatch):
    published(**{"99.0.0": "2026-10-04"})
    monkeypatch.setenv("LADO_CONTAINER", "1")
    assert update.available_line(update.check()) == (
        "LADO 99.0.0 is available: a new image updates LADO in a container "
        "(ghcr.io/ladohq/lado:99.0.0)"
    )


def test_no_check_when_switched_off(published, monkeypatch, lado_home):
    published(**{"99.0.0": "2026-10-04"})
    monkeypatch.setenv("LADO_NO_UPDATE_CHECK", "1")
    assert update.check() is None
    assert update.available_line(update.check()) is None
    assert not (lado_home / "update-check.json").exists()


def uv_tool(tmp_path, receipt: str):
    prefix = tmp_path / "uv-tools" / "lado"
    prefix.mkdir(parents=True)
    (prefix / "uv-receipt.toml").write_text(receipt)
    return prefix


PLAIN_RECEIPT = """\
[tool]
requirements = [{ name = "lado" }]
entrypoints = [
    { name = "lado", install-path = "/home/u/.local/bin/lado", from = "lado" },
]
"""


def test_a_uv_tool_install_installs_exactly_the_version(tmp_path):
    found = update.installer(uv_tool(tmp_path, PLAIN_RECEIPT))
    assert found.kind == "uv tool"
    assert found.command("0.22.0") == [
        "uv", "tool", "install", "lado==0.22.0", "--refresh-package", "lado",
    ]  # fmt: skip
    assert found.lost == []
    assert found.binary == tmp_path / "uv-tools" / "lado" / "bin" / "lado"


def test_a_uv_tool_install_keeps_its_python_extras_and_with(tmp_path):
    receipt = """\
[tool]
requirements = [
    { name = "lado", extras = ["x"], specifier = "==0.20.0" },
    { name = "rich", specifier = ">=13" },
    { name = "local", directory = "/src/local" },
]
python = "3.12"
constraints = [{ name = "fastapi", specifier = "<1" }]
entrypoints = []
"""
    found = update.installer(uv_tool(tmp_path, receipt))
    assert found.command("0.22.0") == [
        "uv", "tool", "install", "lado[x]==0.22.0", "--refresh-package", "lado",
        "--python", "3.12", "--with", "rich>=13",
    ]  # fmt: skip
    assert found.lost == ["--with local (not from an index)", "constraints"]


def pipx(tmp_path, pip_args: list[str]):
    prefix = tmp_path / "pipx" / "venvs" / "lado"
    prefix.mkdir(parents=True)
    metadata = {
        "main_package": {"package": "lado", "pip_args": pip_args, "suffix": ""},
        "injected_packages": {"rich": {}},
        "pipx_metadata_version": "0.5",
    }
    (prefix / "pipx_metadata.json").write_text(json.dumps(metadata))
    return prefix


@pytest.mark.parametrize(
    "pip_args, given",
    [
        ([], "--pip-args=--no-cache-dir"),
        (["--no-cache-dir"], "--pip-args=--no-cache-dir"),
        (
            ["--index-url", "https://x/simple"],
            "--pip-args=--index-url https://x/simple --no-cache-dir",
        ),
    ],
)
def test_a_pipx_install_installs_exactly_the_version_with_its_pip_args(tmp_path, pip_args, given):
    """pip's cache of the index may not have the release yet: pip gets --no-cache-dir, in
    the one --pip-args pipx takes."""
    found = update.installer(pipx(tmp_path, pip_args))
    assert found.kind == "pipx"
    assert found.command("0.22.0") == ["pipx", "install", "--force", "lado==0.22.0", given]
    assert found.lost == []


def test_another_install_is_none(tmp_path):
    assert update.installer(tmp_path) is None


@pytest.mark.parametrize(
    "lado",
    [
        '{ name = "lado", editable = "/src/lado" }',
        '{ name = "lado", directory = "/src/lado" }',
        '{ name = "lado", git = "https://github.com/ladohq/lado" }',
        '{ name = "lado", url = "https://example.com/lado-0.20.0.whl" }',
    ],
)
def test_a_uv_tool_install_of_lado_not_from_an_index_is_none(tmp_path, lado):
    """A working copy or a git install: `uv tool install lado==X` would replace it with
    PyPI's release."""
    receipt = f"[tool]\nrequirements = [{lado}]\nentrypoints = []\n"
    assert update.installer(uv_tool(tmp_path, receipt)) is None


@pytest.mark.parametrize(
    "spec, from_index",
    [
        ("lado", True),
        ("lado==0.20.0", True),
        ("LADO[x]>=0.19", True),
        ("/src/lado", False),
        ("git+https://github.com/ladohq/lado", False),
        ("./lado", False),
    ],
)
def test_a_pipx_install_of_lado_not_from_an_index_is_none(tmp_path, spec, from_index):
    prefix = tmp_path / "pipx" / "venvs" / "lado"
    prefix.mkdir(parents=True)
    metadata = {"main_package": {"package": "lado", "package_or_url": spec, "pip_args": []}}
    (prefix / "pipx_metadata.json").write_text(json.dumps(metadata))
    found = update.installer(prefix)
    assert (found is not None) == from_index


def test_the_tests_name_the_installer_and_the_prefix(tmp_path, monkeypatch):
    prefix = uv_tool(tmp_path, PLAIN_RECEIPT)
    monkeypatch.setenv("LADO_UPDATE_PREFIX", str(prefix))
    monkeypatch.setenv("LADO_UPDATE_INSTALLER", "/bin/sh fake-installer")
    found = update.installer()
    assert found.prefix == prefix
    assert found.command("0.22.0") == ["/bin/sh", "fake-installer", "0.22.0"]


@pytest.mark.parametrize(
    "lado",
    [
        '{ name = "lado" }',
        '{ name = "lado", git = "https://github.com/ladohq/lado" }',
        '{ name = "lado", editable = "/src/lado" }',
    ],
)
def test_a_uv_tool_install_is_removed_by_uv_whatever_its_source(tmp_path, lado):
    receipt = f"[tool]\nrequirements = [{lado}]\nentrypoints = []\n"
    assert update.remover(uv_tool(tmp_path, receipt)) == ["uv", "tool", "uninstall", "lado"]


@pytest.mark.parametrize("suffix, name", [("", "lado"), ("@1", "lado@1")])
def test_a_pipx_install_is_removed_by_pipx_with_its_suffix(tmp_path, suffix, name):
    prefix = tmp_path / "pipx" / "venvs" / name
    prefix.mkdir(parents=True)
    metadata = {
        "main_package": {"package": "lado", "package_or_url": "/src/lado", "suffix": suffix}
    }
    (prefix / "pipx_metadata.json").write_text(json.dumps(metadata))
    assert update.remover(prefix) == ["pipx", "uninstall", name]


def test_another_install_has_no_remover(tmp_path):
    assert update.remover(tmp_path) is None


def test_the_tests_name_the_remover(tmp_path, monkeypatch):
    monkeypatch.setenv("LADO_UPDATE_PREFIX", str(tmp_path))
    monkeypatch.setenv("LADO_UNINSTALL_REMOVER", "/bin/sh fake-remover")
    assert update.remover() == ["/bin/sh", "fake-remover"]


@pytest.fixture
def installed(tmp_path, monkeypatch, published):
    """This LADO as a uv tool in a prefix of the test's; PyPI's index has 99.0.0, this
    version and 0.1.0."""
    prefix = uv_tool(tmp_path, PLAIN_RECEIPT)
    monkeypatch.setenv("LADO_UPDATE_PREFIX", str(prefix))
    published(**{"99.0.0": "2026-10-04", __version__: "2026-10-01", "0.1.0": "2026-01-01"})
    return prefix


def no_terminal(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)


def answering(monkeypatch, answer: str):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: print(prompt, end="") or answer)


def test_update_at_the_latest_version_says_so_and_stops_nothing(
    installed, published, repo, fake_tmux, capsys
):
    published(**{__version__: "2026-10-01"})
    assert main(["start", str(repo), "--provider", "claude", "--name", "s", "--no-attach"]) == 0
    capsys.readouterr()
    assert main(["update"]) == 0
    assert capsys.readouterr().out == f"LADO {__version__} is the latest version.\n"
    assert not state.get_session("s").stopped_at


def test_update_of_a_final_release_is_not_offered_a_release_candidate(
    installed, published, capsys, monkeypatch
):
    import lado

    monkeypatch.setattr(lado, "__version__", "0.36.0", raising=False)
    published(**{"0.36.0": "2026-10-01", "0.37.0rc1": "2026-10-05"})
    assert main(["update"]) == 0
    assert capsys.readouterr().out == "LADO 0.36.0 is the latest version.\n"


def test_update_of_a_release_candidate_is_offered_the_next_one(
    installed, published, capsys, monkeypatch
):
    import lado

    monkeypatch.setattr(lado, "__version__", "0.37.0rc1", raising=False)
    published(**{"0.36.0": "2026-10-01", "0.37.0rc1": "2026-10-05", "0.37.0rc2": "2026-10-06"})
    answering(monkeypatch, "n")
    assert main(["update"]) == 1
    assert capsys.readouterr().out.startswith(
        "LADO 0.37.0rc1 -> 0.37.0rc2 (PyPI, released 2026-10-06)\n"
    )


def test_update_shows_the_plan_and_asks(installed, repo, fake_tmux, capsys, monkeypatch):
    assert main(["start", str(repo), "--provider", "claude", "--name", "s", "--no-attach"]) == 0
    runtime.spawn_worker("s", "task", name="w1")
    state.set_status("s", "w1", state.BUSY)
    _gone(repo, "old")
    monkeypatch.setattr(server_run, "running", lambda: {"url": "http://127.0.0.1:8123"})
    capsys.readouterr()
    answering(monkeypatch, "n")
    assert main(["update"]) == 1
    out = capsys.readouterr().out
    assert out.startswith(
        f"LADO {__version__} -> 99.0.0 (PyPI, released 2026-10-04)\n"
        "Installed with uv tool: uv tool install lado==99.0.0 --refresh-package lado\n"
        "Restarts:\n"
        f"  session s  ({repo})  supervisor starting, w1 busy; no open runs\n"
        "  UI server  http://127.0.0.1:8123\n"
        "Busy agents lose their current turn. Runs, gates, branches and worktrees stay;\n"
        "each supervisor starts a new conversation and gets what its open runs wait for.\n"
        f"Not running, its tmux session is gone: old; resume it with lado start {repo} "
        "--name old\n"
        f'Only sessions on tmux socket "{tmux.socket()}" are seen.\n'
    )
    assert out.endswith("Update? [y/N] Not updated.\n")
    assert not state.get_session("s").stopped_at


def _gone(repo, name):
    state.add_session(state.Session(name, str(repo), None, provider="claude"))  # no tmux session


def test_update_without_a_terminal_needs_yes(installed, capsys, monkeypatch):
    no_terminal(monkeypatch)
    assert main(["update"]) == 1
    assert capsys.readouterr().err == "lado: not updated: confirm with --yes\n"


def test_update_to_an_older_version_without_lado_db_says_nothing_of_it(
    installed, capsys, monkeypatch
):
    """Its release has no wheel in the index: none is asked for (the warning of an older
    schema: test_self_update)."""
    no_terminal(monkeypatch)
    assert state.schema_version() is None
    assert main(["update", "0.1.0"]) == 1
    captured = capsys.readouterr()
    assert captured.out.startswith(f"LADO {__version__} -> 0.1.0 (PyPI, released 2026-01-01)\n")
    assert "lado.db" not in captured.err
    assert captured.err == "lado: not updated: confirm with --yes\n"


def test_update_to_a_version_pypi_does_not_have_stops_nothing(installed, repo, fake_tmux, capsys):
    assert main(["start", str(repo), "--provider", "claude", "--name", "s", "--no-attach"]) == 0
    assert main(["update", "98.0.0", "--yes"]) == 1
    assert capsys.readouterr().err == ("lado: PyPI has no LADO 98.0.0; nothing was stopped\n")
    assert not state.get_session("s").stopped_at


def test_update_inside_an_agent_is_refused(installed, repo, fake_tmux, capsys, monkeypatch):
    assert main(["start", str(repo), "--provider", "claude", "--name", "s", "--no-attach"]) == 0
    monkeypatch.setenv("LADO_AGENT", "supervisor")
    assert main(["update", "--yes"]) == 1
    assert "lado update is for the human" in capsys.readouterr().err
    assert not state.get_session("s").stopped_at


def test_update_of_another_install_prints_the_commands_and_stops_nothing(
    installed, tmp_path, repo, fake_tmux, capsys, monkeypatch
):
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "pip").write_text("#!/bin/sh\n")
    (venv / "bin" / "pip").chmod(0o755)
    monkeypatch.setenv("LADO_UPDATE_PREFIX", str(venv))
    assert main(["start", str(repo), "--provider", "claude", "--name", "s", "--no-attach"]) == 0
    monkeypatch.setattr(
        server_run, "running", lambda: {"url": "http://127.0.0.1:8123", "port": 8123}
    )
    capsys.readouterr()
    assert main(["update", "--yes"]) == 1
    out = capsys.readouterr().out
    assert out.endswith(
        f"LADO runs from {venv}, not a uv tool or pipx install of lado from PyPI; "
        "lado update does not "
        "upgrade it. By hand:\n"
        "  lado stop s\n"
        "  lado server stop\n"
        f"  {venv}/bin/pip install lado==99.0.0\n"
        f"  lado start {shlex.quote(str(repo))} --name s\n"  # "My Repo"
        "  lado ui\n"
    )
    assert not state.get_session("s").stopped_at


WHEEL_RECEIPT = """\
[tool]
requirements = [{ name = "lado", path = "/home/u/lado-0.42.0-py3-none-any.whl" }]
entrypoints = []
"""


def pipx_of_a_folder(tmp_path):
    prefix = tmp_path / "pipx" / "venvs" / "lado"
    prefix.mkdir(parents=True)
    metadata = {"main_package": {"package": "lado", "package_or_url": "/src/lado"}}
    (prefix / "pipx_metadata.json").write_text(json.dumps(metadata))
    return prefix


def nothing_known(tmp_path):
    prefix = tmp_path / "some env"
    prefix.mkdir(parents=True)
    return prefix


@pytest.mark.parametrize(
    "make, line",
    [
        (
            lambda tmp_path: uv_tool(tmp_path / "tool dir", WHEEL_RECEIPT),
            "UV_TOOL_DIR='{prefix.parent}' uv tool install lado==99.0.0",
        ),
        (pipx_of_a_folder, "pipx install --force lado==99.0.0"),
        (
            nothing_known,
            "# install lado==99.0.0 with the installer of '{prefix}': LADO does not know it",
        ),
    ],
)
def test_the_commands_by_hand_name_the_installer_the_prefix_holds(
    installed, tmp_path, repo, fake_tmux, capsys, monkeypatch, make, line
):
    """Not from an index, so installer() is None, and the prefix has no pip."""
    prefix = make(tmp_path / "other")
    monkeypatch.setenv("LADO_UPDATE_PREFIX", str(prefix))
    assert update.installer() is None
    assert main(["start", str(repo), "--provider", "claude", "--name", "s", "--no-attach"]) == 0
    capsys.readouterr()
    assert main(["update", "--yes"]) == 1
    assert capsys.readouterr().out.endswith(
        "upgrade it. By hand:\n"
        "  lado stop s\n"
        f"  {line.format(prefix=prefix)}\n"
        f"  lado start {shlex.quote(str(repo))} --name s\n"
    )
    assert not state.get_session("s").stopped_at


def test_a_loop_that_does_not_end_stops_the_update_before_the_installer(
    installed, repo, fake_tmux, capsys, monkeypatch, tmp_path
):
    calls = tmp_path / "calls"
    for path, line in ((installed / "bin" / "lado", "$*"), (tmp_path / "installer", "install")):
        path.parent.mkdir(exist_ok=True)
        path.write_text(f'#!/bin/sh\necho "{line}" >> "{calls}"\n')
        path.chmod(0o755)
    monkeypatch.setenv("LADO_UPDATE_INSTALLER", str(tmp_path / "installer"))
    assert main(["start", str(repo), "--provider", "claude", "--name", "s", "--no-attach"]) == 0
    monkeypatch.setattr(loop, "wait_stopped", lambda session, timeout=0: False)
    capsys.readouterr()
    assert main(["update", "--yes"]) == 1
    assert capsys.readouterr().err == (
        f"lado: the session loop of s did not end; see {state.home() / 'loop.log'}; nothing "
        "was upgraded. Resuming the sessions:\n"
    )
    assert calls.read_text().splitlines() == [f"start {repo} --name s --no-attach"]


def test_ls_and_update_name_the_sessions_an_unfinished_update_left_stopped(
    installed, published, tmp_path, fake_tmux, capsys
):
    published(**{__version__: "2026-10-01"})
    repos = {name: init_repo(tmp_path / name) for name in ("a", "b")}
    for name, repo in repos.items():
        assert (
            main(["start", str(repo), "--provider", "claude", "--name", name, "--no-attach"]) == 0
        )
    update.write_pending(update.Pending({n: str(r) for n, r in repos.items()}, None))
    runtime.stop_session("a")
    capsys.readouterr()
    line = (
        "lado: an update did not finish: sessions a may be stopped; resume them with "
        f"lado start {repos['a']} --name a\n"
    )
    assert main(["ls"]) == 0
    assert capsys.readouterr().err == line
    assert main(["update"]) == 0
    assert capsys.readouterr().err == line
    runtime.stop_session("b")
    assert main(["ls"]) == 0
    assert "sessions a, b may be stopped" in capsys.readouterr().err


def test_the_tests_switch_the_check_off():
    assert os.environ.get("LADO_NO_UPDATE_CHECK") == "1"


def test_the_result_of_an_update_is_read_in_format_1_and_unknown_keys_are_passed_over():
    update.write_result(
        update.Result(
            outcome="ok", from_="0.32.0", to="0.33.0", started_at="2026-10-09T10:00:00+00:00"
        )
    )
    written = json.loads(update.result_path().read_text())
    assert written["format"] == 1 and written["from"] == "0.32.0"
    written["later_key"] = "from a later LADO of format 1"
    update.result_path().write_text(json.dumps(written))
    read = update.read_result()
    assert (read.outcome, read.from_, read.to, read.newer_format) == (
        "ok",
        "0.32.0",
        "0.33.0",
        False,
    )


def test_a_result_of_a_higher_format_is_named_as_a_newer_lado_s():
    update.result_path().write_text(json.dumps({"format": 2, "outcome": "something"}))
    read = update.read_result()
    assert read.newer_format
    assert read.problem == "written by a newer LADO (format 2)"


def test_no_result_without_the_file_or_with_one_that_is_no_json():
    assert update.read_result() is None
    update.result_path().write_text("{not json")
    assert update.read_result() is None


def test_the_schema_of_a_release_is_read_from_its_wheel(tmp_path):
    sdist = {"packagetype": "sdist", "filename": "lado-0.42.0.tar.gz", "url": "file:///nope"}
    data = index(**{"0.42.0": [sdist, wheel(tmp_path, 31, "0.42.0")]})
    assert update.release_schema(data, "0.42.0") == 31


@pytest.mark.parametrize(
    "files, reason",
    [
        (lambda p: [wheel(p, 31, digests={"sha256": "0" * 64})], "sha256"),
        (lambda p: [{"packagetype": "sdist", "filename": "lado-0.42.0.tar.gz"}], "no wheel"),
        (lambda p: [wheel(p, None)], "SCHEMA_VERSION"),
        (lambda p: [wheel(p, 31, yanked=True)], "no wheel"),
        (lambda p: [wheel(p, 31, url=(p / "gone.whl").as_uri())], "gone.whl"),
        (lambda p: [], "no wheel"),
    ],
)
def test_a_wheel_that_cannot_give_the_schema_says_why(tmp_path, files, reason):
    data = index(**{"0.42.0": files(tmp_path)})
    with pytest.raises((OSError, ValueError)) as raised:
        update.release_schema(data, "0.42.0")
    assert reason in str(raised.value)


def test_a_release_the_index_does_not_have_has_no_schema(tmp_path):
    with pytest.raises(ValueError, match="no release 0.41.0"):
        update.release_schema(index(**{"0.42.0": [wheel(tmp_path, 31)]}), "0.41.0")


def test_a_wheel_without_its_state_module_says_why(tmp_path):
    file = wheel(tmp_path, 31)
    path = tmp_path / file["filename"]
    with zipfile.ZipFile(path, "w") as zipped:
        zipped.writestr("lado/__init__.py", "")
    file["digests"] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    with pytest.raises(ValueError, match="lado/state.py"):
        update.release_schema(index(**{"0.42.0": [file]}), "0.42.0")
