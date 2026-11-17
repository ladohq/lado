"""LADO's git credential helper (lado.git_credential), as git itself runs it: `git
credential fill|approve` with the variables of lado.git_servers, in an environment of its
own HOME and git configs. No network: git asks a helper before any request."""

from __future__ import annotations

import os
import subprocess

import pytest

from lado import git_kinds, git_servers, interpreter

TOKEN = "glpat-CANARY-41d0c3"
ADDRESS = "https://gitlab.corp.ru"
ASKED = "protocol=https\nhost=gitlab.corp.ru\npath=team/app.git\n\n"


@pytest.fixture
def server(lado_home):
    checked = git_servers.Checked(git_kinds.by_name("gitlab"), "ivan")
    saved, _ = git_servers.save(git_servers.address(ADDRESS), checked, TOKEN)
    return saved


@pytest.fixture
def git_env(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    # No system config: Apple's git reads its own (osxkeychain, whose keychain a HOME of
    # the test's has not: macOS asks in a window), which GIT_CONFIG_SYSTEM does not replace.
    return {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": str(home / ".gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1",
    }


def _credential(env, operation, given=ASKED, cwd=None):
    # A new session: git has no terminal to prompt on, so a prompt shows as an error.
    return subprocess.run(
        ["git", "credential", operation],
        input=given,
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        start_new_session=True,
        timeout=30,
    )


def _with_lado(env, servers):
    return env | git_servers.variables(env, servers)


def test_fill_gives_the_kinds_user_and_the_token(server, git_env):
    result = _credential(_with_lado(git_env, [server]), "fill")
    assert result.returncode == 0, result.stderr
    assert "username=oauth2\n" in result.stdout
    assert f"password={TOKEN}\n" in result.stdout
    assert TOKEN not in result.stderr


def test_it_needs_no_lado_home_nor_lado_on_path(server, git_env, monkeypatch):
    env = _with_lado(git_env, [server])
    assert "LADO_HOME" not in env
    env["PATH"] = "/usr/bin:/bin"
    assert f"password={TOKEN}\n" in _credential(env, "fill").stdout


def test_it_imports_nothing_from_its_working_folder(server, git_env, tmp_path):
    cwd = tmp_path / "work"
    (cwd / "lado").mkdir(parents=True)
    (cwd / "lado" / "__init__.py").write_text("raise SystemExit('imported from the cwd')\n")
    (cwd / "json.py").write_text("raise SystemExit('imported from the cwd')\n")
    (cwd / "os.py").write_text("raise SystemExit('imported from the cwd')\n")
    result = _credential(_with_lado(git_env, [server]), "fill", cwd=cwd)
    assert f"password={TOKEN}\n" in result.stdout, result.stderr


def test_it_never_opens_lado_db(server, git_env, lado_home):
    (lado_home / "lado.db").unlink()
    assert f"password={TOKEN}\n" in _credential(_with_lado(git_env, [server]), "fill").stdout
    assert not (lado_home / "lado.db").exists()


def test_a_global_store_helper_is_dropped_and_keeps_nothing(server, git_env, tmp_path):
    gitconfig = tmp_path / "home" / ".gitconfig"
    gitconfig.write_text("[credential]\n\thelper = store\n")
    before = gitconfig.read_bytes()
    env = _with_lado(git_env, [server])
    filled = _credential(env, "fill")
    assert f"password={TOKEN}\n" in filled.stdout
    approved = _credential(env, "approve", filled.stdout + "\n")
    assert approved.returncode == 0, approved.stderr
    assert not (tmp_path / "home" / ".git-credentials").exists()
    assert gitconfig.read_bytes() == before


def test_the_store_helper_would_keep_it_without_lados_variables(git_env, tmp_path):
    # The reverse of the test above: the same approve without them does write the file.
    (tmp_path / "home" / ".gitconfig").write_text("[credential]\n\thelper = store\n")
    given = f"{ASKED.rstrip()}\nusername=oauth2\npassword={TOKEN}\n\n"
    assert _credential(git_env, "approve", given).returncode == 0
    assert TOKEN in (tmp_path / "home" / ".git-credentials").read_text()


def test_another_host_is_not_given_the_token(server, git_env):
    other = "protocol=https\nhost=git.lan\n\n"
    result = _credential(_with_lado(git_env, [server]), "fill", other)
    assert TOKEN not in result.stdout
    assert "lado" not in result.stderr


def test_with_no_token_file_git_stops_without_a_prompt(server, git_env, lado_home):
    (lado_home / "git-servers" / server.id / "token").unlink()
    result = _credential(_with_lado(git_env, [server]), "fill")
    assert result.returncode != 0
    assert TOKEN not in result.stdout + result.stderr
    assert (
        f"lado: no token for {ADDRESS}; add it again: lado git-server add {ADDRESS} --token"
        in result.stderr
    )
    assert "Username" not in result.stderr  # git did not try to prompt


def test_a_link_for_the_token_file_is_not_read(server, git_env, lado_home, tmp_path):
    token = lado_home / "git-servers" / server.id / "token"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.write_text(TOKEN)
    token.unlink()
    token.symlink_to(elsewhere)
    result = _credential(_with_lado(git_env, [server]), "fill")
    assert TOKEN not in result.stdout
    assert "lado: no token for" in result.stderr


@pytest.mark.parametrize("operation", ["store", "erase"])
def test_store_and_erase_do_nothing(server, lado_home, operation):
    args = ["--home", str(lado_home), "--server", server.id, "--user", "u", "--address", ADDRESS]
    result = subprocess.run(
        interpreter.run_module("lado.git_credential", *args, operation),
        input=f"{ASKED.rstrip()}\nusername=u\npassword=other\n\n",
        capture_output=True,
        text=True,
        check=True,
    )
    assert (result.stdout, result.stderr) == ("", "")
    assert (lado_home / "git-servers" / server.id / "token").read_text() == TOKEN
