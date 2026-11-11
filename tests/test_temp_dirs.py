"""Each agent's temporary folder (providers.base.temp_path, LAD-247): made at each launch,
given as TMPDIR to every provider, removed with the agent's state."""

import os
import stat

import agent_helpers
import pytest

from lado import agent_env, projects, runtime, state
from lado.providers import base

UID = os.getuid()


def _agent(session="s", name="w1"):
    return state.Agent(session, name, "worker", "/repo", None, None, state.STARTING, "claude")


def _mode(path):
    return stat.S_IMODE(path.lstat().st_mode)


def test_the_folder_lies_under_the_parent_by_session_and_agent(tmp_path):
    path = base.temp_path(_agent(), {"TMPDIR": str(tmp_path)})
    assert path == tmp_path / f"lado-{UID}" / "s" / "w1"
    assert not path.exists()  # only named


def test_without_a_tmpdir_the_tests_parent_stands_for_tmp(tmp_path, monkeypatch):
    """The tests' LADO_TEMP_PARENT (conftest.agents_tmp) keeps an agent whose layers have no
    TMPDIR (a worker an agent's `lado mcp` spawns, D3) out of the real /tmp."""
    monkeypatch.setenv(base.TEMP_PARENT_VAR, str(tmp_path))
    assert base.temp_path(_agent(), {}) == tmp_path / f"lado-{UID}" / "s" / "w1"
    assert base.temp_path(_agent(), {"TMPDIR": "/x"}).parent.parent.parent == base.Path("/x")


def test_without_a_tmpdir_the_parent_is_tmp(monkeypatch):
    monkeypatch.delenv(base.TEMP_PARENT_VAR)
    assert base.temp_path(_agent(), {}) == base.Path("/tmp", f"lado-{UID}", "s", "w1")
    assert base.temp_path(_agent(), {"TMPDIR": ""}).parent.parent.parent == base.Path("/tmp")


def test_the_folder_is_made_for_the_owner_only_at_each_level(tmp_path):
    path = base.make_temp_dir(_agent(), {"TMPDIR": str(tmp_path)})
    assert path == base.temp_path(_agent(), {"TMPDIR": str(tmp_path)})
    for level in (path, path.parent, path.parent.parent):
        assert level.is_dir()
        assert _mode(level) == 0o700
    path.rmdir()
    assert base.make_temp_dir(_agent(), {"TMPDIR": str(tmp_path)}).is_dir()  # made again


def test_an_open_root_is_closed_to_others(tmp_path):
    root = tmp_path / f"lado-{UID}"
    root.mkdir(mode=0o777)
    root.chmod(0o777)
    base.make_temp_dir(_agent(), {"TMPDIR": str(tmp_path)})
    assert _mode(root) == 0o700


def test_a_missing_parent_is_made(tmp_path):
    path = base.make_temp_dir(_agent(), {"TMPDIR": str(tmp_path / "not" / "yet")})
    assert path.is_dir()


@pytest.mark.parametrize("kind", ["link", "file"])
def test_a_root_that_is_not_a_folder_is_refused(tmp_path, kind):
    root = tmp_path / f"lado-{UID}"
    if kind == "link":
        (tmp_path / "elsewhere").mkdir()
        root.symlink_to(tmp_path / "elsewhere")
        why = "is a link"
    else:
        root.write_text("")
        why = "is not a folder"
    with pytest.raises(base.UnsafeTempDir, match=f"^{root} {why}"):
        base.make_temp_dir(_agent(), {"TMPDIR": str(tmp_path)})
    assert not (tmp_path / "elsewhere" / "s").exists()


def test_a_root_of_another_owner_is_refused(tmp_path, monkeypatch):
    other = UID + 1
    root = tmp_path / f"lado-{other}"
    root.mkdir()  # owned by the test's user, not by `other`
    monkeypatch.setattr(base.os, "getuid", lambda: other)
    with pytest.raises(base.UnsafeTempDir, match=f"^{root} belongs to uid {UID}"):
        base.make_temp_dir(_agent(), {"TMPDIR": str(tmp_path)})
    assert not (root / "s").exists()


def test_the_folder_goes_with_the_agents_state(tmp_path):
    env = {"TMPDIR": str(tmp_path)}
    one, two = base.make_temp_dir(_agent(), env), base.make_temp_dir(_agent(name="w2"), env)
    (one / "pr.md").write_text("mine")
    base.remove_agent_state(_agent())
    assert not one.exists()
    assert two.is_dir()


def test_the_session_folder_goes_with_the_sessions_state(tmp_path):
    env = {"TMPDIR": str(tmp_path)}
    base.make_temp_dir(_agent(), env)
    base.make_temp_dir(_agent(name="w2"), env)
    other = base.make_temp_dir(_agent(session="t"), env)
    base.remove_session_state("s")
    assert not (tmp_path / f"lado-{UID}" / "s").exists()
    assert other.is_dir()


def test_a_folder_made_under_another_parent_goes_too(tmp_path):
    """The parent at the removal may be other than at the launch: the made folder goes."""
    base.make_temp_dir(_agent(), {"TMPDIR": str(tmp_path / "a")})
    base.remove_agent_state(_agent())
    assert not (tmp_path / "a" / f"lado-{UID}" / "s" / "w1").exists()


def test_removal_never_follows_a_record_off_its_agent(tmp_path):
    """The record of the folder points elsewhere (edited by hand): nothing there goes."""
    keep = tmp_path / "keep"
    keep.mkdir()
    record = base.state_path(_agent()) / base.TEMP_RECORD
    record.parent.mkdir(parents=True)
    record.symlink_to(keep)
    base.remove_agent_state(_agent())
    assert keep.is_dir()


# The launch (lado.runtime): every provider, the start and the spawn.


def _supervisor_env(fake_tmux):
    [call] = [c for c in fake_tmux if c[0] == "new_session"]
    return agent_helpers.launched(call)[0]


def _worker_env(fake_tmux, name):
    [call] = [c for c in fake_tmux if c[0] == "new_window" and c[2] == name]
    return agent_helpers.launched(call)[0]


@pytest.mark.parametrize("provider", ["claude", "codex", "kilo", "opencode"])
def test_each_agent_has_a_tmpdir_of_its_own(repo, fake_tmux, agents_tmp, provider):
    runtime.start_session(str(repo), "s", None, provider=provider)
    runtime.spawn_worker("s", "one", name="dev-1", provider=provider)
    runtime.spawn_worker("s", "two", name="dev-2", provider=provider)
    root = agents_tmp / f"lado-{UID}" / "s"
    envs = {
        "supervisor": _supervisor_env(fake_tmux),
        "dev-1": _worker_env(fake_tmux, "dev-1"),
        "dev-2": _worker_env(fake_tmux, "dev-2"),
    }
    for name, env in envs.items():
        assert env["TMPDIR"] == str(root / name)
        assert (root / name).is_dir()
        assert _mode(root / name) == 0o700
        assert "TMPDIR" in env[agent_env.LAUNCH_VARS].split(",")
        # Claude Code's own temporary root, where its scratchpad is (D4); no other's.
        claude_own = env.get("CLAUDE_CODE_TMPDIR")
        assert claude_own == (str(root / name) if provider == "claude" else None)


def test_a_worker_an_agent_spawns_does_not_nest_its_folder(repo, fake_tmux, agents_tmp):
    """A worker spawned from within an agent (its `lado mcp`, LADO_AGENT_ENV=inherit) drops
    its spawner's TMPDIR with LADO's variables: its parent is /tmp, not the spawner's
    folder (D3)."""
    runtime.start_session(str(repo), "s", None, provider="claude")
    spawner = _supervisor_env(fake_tmux)
    assert agent_env.without_launch(spawner).get("TMPDIR") is None


def test_the_spec_names_the_folder(repo, fake_tmux, agents_tmp, monkeypatch):
    specs = []
    real = runtime._launch_command

    def launch_command(agent_cli, agent, sess, spec, note):
        specs.append(spec)
        return real(agent_cli, agent, sess, spec, note)

    monkeypatch.setattr(runtime, "_launch_command", launch_command)
    runtime.start_session(str(repo), "s", None, provider="codex")
    assert specs[0].temp_dir == agents_tmp / f"lado-{UID}" / "s" / "supervisor"


def test_an_unsafe_root_refuses_the_spawn_before_its_window(repo, fake_tmux, agents_tmp):
    runtime.start_session(str(repo), "s", None, provider="claude")
    root = agents_tmp / f"lado-{UID}"
    for child in sorted(root.rglob("*"), reverse=True):
        child.rmdir()
    root.rmdir()
    root.symlink_to(agents_tmp)
    with pytest.raises(runtime.LadoError, match=f"{root} is a link"):
        runtime.spawn_worker("s", "one", name="dev-1")
    assert not [c for c in fake_tmux if c[0] == "new_window"]
    assert state.get_agent("s", "dev-1") is None


def test_finishing_a_worker_removes_its_folder(repo, fake_tmux, agents_tmp):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "one", name="dev-1")
    runtime.spawn_worker("s", "two", name="dev-2")
    root = agents_tmp / f"lado-{UID}" / "s"
    (root / "dev-1" / "pr.md").write_text("one's")
    runtime.finish_worker("s", "dev-1")
    assert not (root / "dev-1").exists()
    assert (root / "dev-2").is_dir()


def test_stop_and_resume_keep_the_folder(repo, fake_tmux, agents_tmp):
    runtime.start_session(str(repo), "s", None, provider="claude")
    folder = agents_tmp / f"lado-{UID}" / "s" / "supervisor"
    (folder / "notes.txt").write_text("kept")
    runtime.stop_session("s")
    runtime.start_session(str(repo), "s", None)
    assert (folder / "notes.txt").read_text() == "kept"
    runtime.stop_session("s")
    runtime.forget_session("s")
    assert not folder.parent.exists()


@pytest.mark.parametrize("where", ["shell", "outside", "project"])
def test_the_users_tmpdir_is_the_parent_and_not_warned_of(
    repo, fake_tmux, tmp_path, monkeypatch, where
):
    own = tmp_path / "own-tmp"
    path, name, more = str(repo), "s", {}
    if where == "shell":
        monkeypatch.setenv("TMPDIR", str(own))
    elif where == "outside":
        folder = tmp_path / "outside"
        folder.mkdir()
        (folder / "TMPDIR").write_text(str(own))
        monkeypatch.setenv("LADO_ENV_DIR", str(folder))
    else:
        monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
        projects.create("shop", "Shop")
        agent_helpers.init_repo(projects.folder("shop") / "frontend")
        state.set_project_variable("shop", "TMPDIR", str(own))
        path, name, more = None, None, {"project": "shop", "repo_name": "frontend"}
    started = runtime.start_session(path, name, None, provider="claude", **more)
    session = started.session.name
    expected = own / f"lado-{UID}" / session / "supervisor"
    assert _supervisor_env(fake_tmux)["TMPDIR"] == str(expected)
    assert expected.is_dir()
    assert not [w for w in started.warnings if "TMPDIR" in w]
    warnings = []
    runtime.spawn_worker(session, "task", name="w1", warnings=warnings)
    assert _worker_env(fake_tmux, "w1")["TMPDIR"] == str(expected.parent / "w1")
    assert not [w for w in warnings if "TMPDIR" in w]
