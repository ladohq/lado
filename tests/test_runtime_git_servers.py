"""An agent's launch with git servers saved (lado.runtime, lado.git_servers): its
environment gets LADO's `GIT_CONFIG_*` entries after the layers' own, none without a
server; an old git on the agents' PATH refuses a launch only while a server is saved."""

from __future__ import annotations

import json
import os
import subprocess

import certificates
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


# A server's commit author.


def _with_author(address="https://gitlab.corp.ru"):
    server = _save(address)
    return state.set_git_server_author(server.id, 'Ivan "Boss" Petrov', "ivan@corp.ru")


def test_an_author_reaches_the_agent_through_a_file_in_its_config_folder(
    repo, fake_tmux, lado_home, monkeypatch, agents_path
):
    _, path = agents_path
    _shell(monkeypatch, {"PATH": path, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "a.b"})
    plain = _save("https://git.lan")
    server = _with_author()
    runtime.start_session(str(repo), "s", None, provider="claude")
    env = _launched(lado_home)
    file = lado_home / "agents" / "s" / "supervisor" / "git-authors" / f"{server.id}.gitconfig"
    assert (
        file.read_text() == '[user]\n\tname = "Ivan \\"Boss\\" Petrov"\n\temail = "ivan@corp.ru"\n'
    )
    expected = git_servers.variables(
        {"GIT_CONFIG_COUNT": "1"}, [plain, server], authors={server.id: file}
    )
    assert {k: env[k] for k in expected} == expected
    # Its author: 4 https forms (any case, with and without :443) and 4 ssh forms.
    assert env["GIT_CONFIG_COUNT"] == str(1 + 5 + 5 + 8)
    values = [env[f"GIT_CONFIG_VALUE_{n}"] for n in range(1, int(env["GIT_CONFIG_COUNT"]))]
    assert values.count(str(file)) == 8
    assert sorted(p.name for p in file.parent.iterdir()) == [file.name]  # none for git.lan


def test_no_author_no_include(repo, fake_tmux, lado_home, monkeypatch, agents_path):
    _, path = agents_path
    _shell(monkeypatch, {"PATH": path})
    _save()
    runtime.start_session(str(repo), "s", None, provider="claude")
    env = _launched(lado_home)
    assert not [k for k, v in env.items() if k.startswith("GIT_CONFIG_KEY") and "includeIf" in v]
    assert not (lado_home / "agents" / "s" / "supervisor" / "git-authors").exists()


def test_lados_own_git_gets_no_author(lado_home):
    _with_author()
    env = agent_env.for_git(remote="https://gitlab.corp.ru/team/app.git")
    count = int(env["GIT_CONFIG_COUNT"])
    assert count == int(os.environ.get("GIT_CONFIG_COUNT", "0")) + 5
    assert not [n for n in range(count) if "includeIf" in env[f"GIT_CONFIG_KEY_{n}"]]
    assert not (lado_home / "agents").exists()


def _git_version(folder, version):
    (folder / "git").write_text(f"#!/bin/sh\necho 'git version {version}'\n")
    (folder / "git").chmod(0o755)


def test_a_git_older_than_2_36_refuses_a_launch_while_an_author_is_set(
    repo, fake_tmux, lado_home, monkeypatch, agents_path
):
    folder, path = agents_path
    _git_version(folder, "2.34.1")
    _shell(monkeypatch, {"PATH": path})
    _with_author()
    with pytest.raises(runtime.LadoError) as raised:
        runtime.start_session(str(repo), "s", None, provider="claude")
    assert str(raised.value) == (
        "git 2.34.1 is older than 2.36, which a commit author of a git server needs; update "
        "git, or clear the author (lado git-server author https://gitlab.corp.ru --clear)"
    )
    assert fake_tmux == []


def test_an_old_git_names_every_server_with_an_author(
    repo, fake_tmux, lado_home, monkeypatch, agents_path
):
    folder, path = agents_path
    _git_version(folder, "2.34.1")
    _shell(monkeypatch, {"PATH": path})
    _with_author()
    _save("https://corp.ru")  # no author: not named
    _with_author("http://git.lan")
    with pytest.raises(runtime.LadoError) as raised:
        runtime.start_session(str(repo), "s", None, provider="claude")
    assert str(raised.value) == (
        "git 2.34.1 is older than 2.36, which a commit author of a git server needs; update "
        "git, or clear the authors (lado git-server author http://git.lan --clear, "
        "lado git-server author https://gitlab.corp.ru --clear)"
    )
    assert fake_tmux == []


def test_a_git_older_than_2_36_without_an_author_starts(
    repo, fake_tmux, lado_home, monkeypatch, agents_path
):
    folder, path = agents_path
    _git_version(folder, "2.34.1")
    _shell(monkeypatch, {"PATH": path})
    _save()
    runtime.start_session(str(repo), "s", None, provider="claude")
    assert state.get_session("s") is not None


WINS = "{name} is set for {agent}: it wins over the commit author of the git servers"


def test_an_author_variable_of_the_environment_is_named_at_the_launch(
    repo, fake_tmux, lado_home, monkeypatch, agents_path
):
    _, path = agents_path
    _shell(monkeypatch, {"PATH": path, "GIT_AUTHOR_EMAIL": "me@home", "GIT_COMMITTER_NAME": "Me"})
    _with_author()
    started = runtime.start_session(str(repo), "s", None, provider="claude")
    for name in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME"):
        assert WINS.format(name=name, agent="supervisor") in started.warnings
    assert not [w for w in started.warnings if "GIT_AUTHOR_NAME" in w]
    warnings = []
    runtime.spawn_worker("s", "task", name="w1", warnings=warnings)
    assert WINS.format(name="GIT_AUTHOR_EMAIL", agent="w1") in warnings


def test_an_author_variable_without_an_author_is_not_named(
    repo, fake_tmux, lado_home, monkeypatch, agents_path
):
    _, path = agents_path
    _shell(monkeypatch, {"PATH": path, "GIT_AUTHOR_EMAIL": "me@home"})
    _save()
    started = runtime.start_session(str(repo), "s", None, provider="claude")
    assert not [w for w in started.warnings if "GIT_AUTHOR_EMAIL" in w]


# GitHub's variables: from the saved servers alone.

GH = ("GH_TOKEN", "GH_ENTERPRISE_TOKEN", "GH_HOST")


def _github(address, token):
    checked = git_servers.Checked(git_kinds.by_name("github"), "octo")
    return git_servers.save(git_servers.address(address), checked, token)[0]


def _origin(repo, url):
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", url], check=True)


def _gh(env):
    return {name: env[name] for name in GH if name in env}


def test_gh_token_from_the_entry(repo, fake_tmux, lado_home, monkeypatch, agents_path):
    _, path = agents_path
    _shell(monkeypatch, {"PATH": path, "GH_TOKEN": "shell", "GITHUB_TOKEN": "shell"})
    _github("github.com", "ghp_entry")
    runtime.start_session(str(repo), "s", None, provider="claude")
    env = _launched(lado_home)
    assert _gh(env) == {"GH_TOKEN": "ghp_entry"}
    assert "GITHUB_TOKEN" not in env
    assert {"GH_TOKEN", "GH_CONFIG_DIR"} <= set(env[agent_env.LAUNCH_VARS].split(","))


def test_gh_config_dir_is_the_agents_own_and_empty(
    repo, fake_tmux, lado_home, monkeypatch, agents_path
):
    _, path = agents_path
    _shell(monkeypatch, {"PATH": path, "GH_CONFIG_DIR": "/home/me/.config/gh"})
    folder = lado_home / "agents" / "s" / "supervisor" / "gh"
    runtime.start_session(str(repo), "s", None, provider="claude")
    env = _launched(lado_home)
    assert env["GH_CONFIG_DIR"] == str(folder)
    assert list(folder.iterdir()) == []
    assert _gh(env) == {}  # no server saved


def test_a_login_left_in_the_gh_folder_goes(tmp_path):
    folder = tmp_path / "gh"
    folder.mkdir()
    (folder / "hosts.yml").write_text("github.com:\n  oauth_token: left\n")
    (folder / "config.yml").write_text("prompt: disabled\n")
    assert git_servers.gh_variables([], folder, lambda: None) == {"GH_CONFIG_DIR": str(folder)}
    assert sorted(p.name for p in folder.iterdir()) == ["config.yml"]


def test_ghe_token_of_the_origins_server(repo, fake_tmux, lado_home, monkeypatch, agents_path):
    _, path = agents_path
    _shell(monkeypatch, {"PATH": path, "GH_ENTERPRISE_TOKEN": "shell", "GH_HOST": "x"})
    _origin(repo, "https://ghe.test:8443/team/app.git")
    _github("https://ghe.other", "ghe_other")
    _github("https://ghe.test:8443", "ghe_entry")
    _github("github.com", "ghp_entry")
    runtime.start_session(str(repo), "s", None, provider="claude")
    assert _gh(_launched(lado_home)) == {
        "GH_TOKEN": "ghp_entry",
        "GH_ENTERPRISE_TOKEN": "ghe_entry",
        "GH_HOST": "ghe.test:8443",
    }


def test_the_only_ghe(repo, fake_tmux, lado_home, monkeypatch, agents_path):
    _, path = agents_path
    _shell(monkeypatch, {"PATH": path})
    _origin(repo, "https://gitlab.corp.ru/team/app.git")
    _save()
    _github("https://ghe.test", "ghe_entry")
    runtime.start_session(str(repo), "s", None, provider="claude")
    assert _gh(_launched(lado_home)) == {"GH_ENTERPRISE_TOKEN": "ghe_entry"}


def test_two_ghe_neither_origin(repo, fake_tmux, lado_home, monkeypatch, agents_path):
    _, path = agents_path
    _shell(monkeypatch, {"PATH": path})
    _github("https://ghe.one", "ghe_1")
    _github("https://ghe.two", "ghe_2")
    runtime.start_session(str(repo), "s", None, provider="claude")
    assert _gh(_launched(lado_home)) == {}


def test_a_worker_gets_its_own_gh_variables(repo, fake_tmux, lado_home, monkeypatch, agents_path):
    _, path = agents_path
    _shell(monkeypatch, {"PATH": path})
    _github("github.com", "ghp_entry")
    runtime.start_session(str(repo), "s", None, provider="claude")
    launched = _launched(lado_home)
    back = agent_env.without_launch(launched)
    assert [name for name in agent_env.GITHUB_VARIABLES if name in back] == []
    runtime.spawn_worker("s", "task", name="w1")
    worker = json.loads((lado_home / "agents" / "s" / "w1" / "env.json").read_text())
    assert worker["GH_TOKEN"] == "ghp_entry"
    assert worker["GH_CONFIG_DIR"] == str(lado_home / "agents" / "s" / "w1" / "gh")


# A server's certificate.

GH_NOTE = (
    "gh does not get the certificate of https://ghe.corp.example: agents' gh cannot reach it; "
    "git can"
)


def test_a_github_server_with_a_certificate_is_named_at_the_launch(
    repo, fake_tmux, lado_home, monkeypatch, agents_path
):
    _, path = agents_path
    _shell(monkeypatch, {"PATH": path})
    root = certificates.authority("Corp Root CA")
    ghe = _github("https://ghe.corp.example", "ghp-CANARY")
    _save()  # a GitLab with a certificate: gh does not reach it anyway
    git_servers.set_certificate(git_servers.address("gitlab.corp.ru"), root.pem)
    git_servers.set_certificate(git_servers.address(ghe.address), root.pem)
    started = runtime.start_session(str(repo), "s", None, provider="claude")
    assert started.warnings.count(GH_NOTE) == 1
    assert not [w for w in started.warnings if "gitlab.corp.ru" in w]
    env = _launched(lado_home)
    ca = str(git_servers.certificate_file(ghe.id))
    assert ca in env.values()  # git gets it
    assert not {"SSL_CERT_FILE", "GIT_SSL_CAINFO", "NODE_EXTRA_CA_CERTS"} & env.keys()
    warnings = []
    runtime.spawn_worker("s", "task", name="w1", warnings=warnings)
    assert warnings.count(GH_NOTE) == 1
