"""An agent's launch with git servers saved (lado.runtime, lado.git_servers): its
environment gets LADO's `GIT_CONFIG_*` entries after the layers' own, none without a
server; an old git on the agents' PATH refuses a launch only while a server is saved."""

from __future__ import annotations

import json
import os

import pytest

from lado import agent_env, git_kinds, git_servers, runtime, state


def _shell(monkeypatch, env):
    monkeypatch.setattr(
        agent_env, "layers", lambda project=None: agent_env.Layers(dict(env), {}, {}, {})
    )


def _launched(lado_home) -> dict[str, str]:
    return json.loads((lado_home / "agents" / "s" / "supervisor" / "env.json").read_text())


def _save(address="https://gitlab.corp.ru"):
    checked = git_servers.Checked(git_kinds.by_name("gitlab"), "ivan")
    return git_servers.save(git_servers.address(address), checked, "glpat-CANARY")[0]


@pytest.fixture
def agents_path(fake_clis, tmp_path):
    folder = tmp_path / "agents-bin"
    folder.mkdir()
    return folder, f"{folder}{os.pathsep}{fake_clis}{os.pathsep}{os.environ['PATH']}"


def test_no_server_no_git_variable(repo, fake_tmux, lado_home, monkeypatch, agents_path):
    _, path = agents_path
    _shell(monkeypatch, {"PATH": path, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "a.b"})
    runtime.start_session(str(repo), "s", None, provider="claude")
    env = _launched(lado_home)
    assert {k: v for k, v in env.items() if k.startswith("GIT_CONFIG")} == {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "a.b",
    }
    assert "GIT_CONFIG" not in env[agent_env.LAUNCH_VARS]


def test_a_saved_server_reaches_the_agent_after_its_own_entries(
    repo, fake_tmux, lado_home, monkeypatch, agents_path
):
    _, path = agents_path
    _shell(monkeypatch, {"PATH": path, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "a.b"})
    server = _save()
    runtime.start_session(str(repo), "s", None, provider="claude")
    env = _launched(lado_home)
    assert env["GIT_CONFIG_KEY_0"] == "a.b"
    expected = git_servers.variables({"GIT_CONFIG_COUNT": "1"}, [server])
    assert {k: env[k] for k in expected} == expected
    assert env["GIT_CONFIG_COUNT"] == "6"
    launch_vars = env[agent_env.LAUNCH_VARS].split(",")
    assert set(expected) <= set(launch_vars)
    assert "GIT_CONFIG_KEY_0" not in launch_vars
    assert "glpat-CANARY" not in json.dumps(env)


@pytest.mark.parametrize(
    "own",
    [
        {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "a.b", "GIT_CONFIG_VALUE_0": "c"},
        {},
    ],
)
def test_a_worker_spawned_from_an_agent_starts_from_the_humans_own_git_entries(
    repo, fake_tmux, lado_home, monkeypatch, agents_path, own
):
    """Under LADO_AGENT_ENV=inherit a worker starts from its spawner's environment without
    what the spawner's launch set: the human's own GIT_CONFIG_* come back as they were."""
    _, path = agents_path
    _shell(monkeypatch, {"PATH": path, **own})
    _save()
    runtime.start_session(str(repo), "s", None, provider="claude")
    launched = _launched(lado_home)
    assert launched["GIT_CONFIG_COUNT"] == str(int(own.get("GIT_CONFIG_COUNT", 0)) + 5)
    back = agent_env.without_launch(launched)
    assert {k: v for k, v in back.items() if k.startswith("GIT_CONFIG")} == own


def _old_git(folder):
    (folder / "git").write_text("#!/bin/sh\necho 'git version 2.30.2'\n")
    (folder / "git").chmod(0o755)


def test_an_old_git_refuses_a_launch_while_a_server_is_saved(
    repo, fake_tmux, lado_home, monkeypatch, agents_path
):
    folder, path = agents_path
    _old_git(folder)
    _shell(monkeypatch, {"PATH": path})
    _save()
    with pytest.raises(runtime.LadoError) as raised:
        runtime.start_session(str(repo), "s", None, provider="claude")
    assert str(raised.value) == (
        "git 2.30.2 is older than 2.31, which git servers need; update git, or remove the "
        "servers (lado git-server remove <address>)"
    )
    assert fake_tmux == []


def test_an_old_git_without_a_server_is_not_even_asked(
    repo, fake_tmux, lado_home, monkeypatch, agents_path
):
    folder, path = agents_path
    _old_git(folder)
    _shell(monkeypatch, {"PATH": path})
    asked = []
    monkeypatch.setattr(git_servers, "check_git", lambda env: asked.append(env))
    runtime.start_session(str(repo), "s", None, provider="claude")
    assert asked == []
    assert state.get_session("s") is not None
