import json
import os
import subprocess
import sys

import pytest

from lado import agent_env


@pytest.fixture
def shell(tmp_path, monkeypatch):
    """Make $SHELL a script with the given rc lines before it runs the `-ilc` command, and
    the given lines after it."""

    def make(rc: str = "", after: str = "") -> str:
        path = tmp_path / "fake-shell"
        path.write_text(f'#!/bin/sh\n{rc}\n/bin/sh -c "$2"\nstatus=$?\n{after}\nexit $status\n')
        path.chmod(0o755)
        monkeypatch.setenv("SHELL", str(path))
        return str(path)

    monkeypatch.delenv(agent_env.SOURCE_VAR, raising=False)
    return make


def test_the_shell_is_run_as_a_login_interactive_shell(shell, tmp_path):
    seen = tmp_path / "args"
    shell(rc=f'echo "$1" > {seen}')
    agent_env.resolve()
    assert seen.read_text().strip() == "-ilc"


def test_variables_come_from_the_shell_between_its_noise(shell):
    shell(
        rc="echo 'Welcome to the machine'; printf 'prompt%% '; export FROM_RC=yes",
        after="echo 'bye'",
    )
    env = agent_env.resolve()
    assert env["FROM_RC"] == "yes"
    assert not any("Welcome" in v or "bye" in v for v in env.values())


def test_a_value_with_newlines_survives(shell):
    shell(rc="export MULTI='first\nsecond\n'")
    assert agent_env.resolve()["MULTI"] == "first\nsecond\n"


def test_the_callers_own_variables_do_not_reach_the_shell(shell, monkeypatch):
    shell(rc="export FROM_RC=yes")
    monkeypatch.setenv("ONLY_IN_CALLER", "1")
    monkeypatch.setenv("PATH", "/caller/bin:/usr/bin:/bin")
    env = agent_env.resolve()
    assert "ONLY_IN_CALLER" not in env
    assert "/caller/bin" not in env["PATH"]
    assert env["HOME"] == os.environ["HOME"]


def test_the_shells_own_bookkeeping_is_dropped(shell):
    shell()
    env = agent_env.resolve()
    assert not {"PWD", "OLDPWD", "SHLVL", "_"} & env.keys()


def test_exclusions_apply_to_the_shells_environment(shell):
    shell(rc="export TMUX=/tmp/x,1,0 TMUX_PANE=%1 CLAUDECODE=1 CLAUDE_CODE_SESSION_ID=s KEEP=1")
    env = agent_env.resolve()
    assert env["KEEP"] == "1"
    assert not {"TMUX", "TMUX_PANE", "CLAUDECODE", "CLAUDE_CODE_SESSION_ID"} & env.keys()


def test_a_missing_shell_is_an_error(shell, monkeypatch):
    monkeypatch.delenv("SHELL")
    with pytest.raises(agent_env.AgentEnvError, match=r"\$SHELL is not set.*LADO_AGENT_ENV"):
        agent_env.resolve()


def test_a_shell_that_cannot_run_is_an_error(shell, monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL", str(tmp_path / "no-such-shell"))
    with pytest.raises(agent_env.AgentEnvError, match="no-such-shell"):
        agent_env.resolve()


def test_a_failing_shell_is_an_error_with_its_command_and_stderr(shell):
    path = shell(rc="echo one >&2; echo 'rc is broken' >&2; exit 3")
    with pytest.raises(agent_env.AgentEnvError) as error:
        agent_env.resolve()
    text = str(error.value)
    assert path in text and "-ilc" in text
    assert "exit status 3" in text
    assert "rc is broken" in text


def test_a_shell_that_prints_no_environment_is_an_error(shell):
    path = shell(rc="echo 'no dump here' >&2; exit 0")
    with pytest.raises(agent_env.AgentEnvError, match="printed no environment") as error:
        agent_env.resolve()
    assert path in str(error.value) and "no dump here" in str(error.value)


def test_a_slow_shell_times_out(shell, monkeypatch):
    monkeypatch.setattr(agent_env, "TIMEOUT", 0.5)
    shell(rc="echo stuck >&2; sleep 30 & wait")
    with pytest.raises(agent_env.AgentEnvError, match=r"did not finish in 0.5 s") as error:
        agent_env.resolve()
    assert "stuck" in str(error.value)


def test_a_background_program_of_the_rc_files_does_not_hold_it_up(shell, monkeypatch):
    # It keeps the shell's output open after the shell is done, as a daemon started
    # without redirection does.
    monkeypatch.setattr(agent_env, "TIMEOUT", 2)
    shell(rc="sleep 4 & export FROM_RC=yes")
    assert agent_env.resolve()["FROM_RC"] == "yes"


def test_it_is_resolved_anew_each_time(shell, tmp_path):
    rc = tmp_path / "rc"
    rc.write_text("export VALUE=1\n")
    shell(rc=f". {rc}")
    assert agent_env.resolve()["VALUE"] == "1"
    rc.write_text("export VALUE=2\n")
    assert agent_env.resolve()["VALUE"] == "2"


def test_inherit_takes_the_callers_environment_without_the_exclusions(monkeypatch):
    monkeypatch.setenv(agent_env.SOURCE_VAR, "inherit")
    monkeypatch.setenv("SHELL", "/no/such/shell")  # not run
    monkeypatch.setenv("ONLY_IN_CALLER", "1")
    monkeypatch.setenv("TMUX", "/tmp/x,1,0")
    monkeypatch.setenv("CLAUDECODE", "1")
    env = agent_env.resolve()
    assert env["ONLY_IN_CALLER"] == "1"
    assert not {"TMUX", "CLAUDECODE"} & env.keys()
    assert agent_env.source() == "inherit"


def test_an_unknown_source_is_an_error(monkeypatch):
    monkeypatch.setenv(agent_env.SOURCE_VAR, "login")
    with pytest.raises(agent_env.AgentEnvError, match='LADO_AGENT_ENV="login"'):
        agent_env.resolve()


def test_the_launch_runs_its_command_with_exactly_that_environment(tmp_path):
    file = tmp_path / "agent" / "env.json"
    file.parent.mkdir()
    argv = agent_env.command(file, {"A": "1", "MULTI": "x\ny", "TERM": "dumb"}, ["env", "-0"])
    assert (file.stat().st_mode & 0o777) == 0o600
    # The pane's process has tmux's server environment and tmux's own variables.
    pane = {"PATH": os.environ["PATH"], "STRAY": "1", "TERM": "tmux-256color", "TMUX_PANE": "%3"}
    out = subprocess.run(argv, env=pane, capture_output=True, text=True, check=True).stdout
    got = dict(item.split("=", 1) for item in out.split("\0") if item)
    assert got == {"A": "1", "MULTI": "x\ny", "TERM": "tmux-256color", "TMUX_PANE": "%3"}
    assert not file.exists()  # it holds the user's keys: gone once read


def test_an_env_file_left_readable_by_all_is_made_the_users_only(tmp_path):
    file = tmp_path / "env.json"
    file.write_text("{}")  # left by a launch whose window never read it
    file.chmod(0o644)
    agent_env.command(file, {"KEY": "k"}, ["env"])
    assert (file.stat().st_mode & 0o777) == 0o600


def test_the_launch_finds_its_program_on_the_resolved_path(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    program = bin_dir / "only-here"
    program.write_text("#!/bin/sh\necho found\n")
    program.chmod(0o755)
    argv = agent_env.command(
        tmp_path / "env.json", {"PATH": f"{bin_dir}:/usr/bin:/bin"}, ["only-here"]
    )
    out = subprocess.run(argv, env={}, capture_output=True, text=True, check=True).stdout
    assert out == "found\n"


def test_the_dump_is_json_between_markers():
    # Guard the format the parser expects: one JSON object, nothing else, between markers.
    script, begin, end = agent_env.dump_script()
    out = subprocess.run(["/bin/sh", "-c", script], capture_output=True, text=True, check=True)
    inner = out.stdout.split(begin, 1)[1].split(end, 1)[0]
    assert json.loads(inner)["PATH"] == os.environ["PATH"]
    assert sys.executable in script


@pytest.fixture
def linux(tmp_path, monkeypatch):
    """A Linux machine of temporary files: no /etc/environment yet, not WSL, with a
    /usr/lib/wsl/lib folder (that alone makes no WSL)."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(agent_env, "ENVIRONMENT_FILE", tmp_path / "environment")
    monkeypatch.setattr(agent_env, "WSL_INTEROP", tmp_path / "WSLInterop")
    version = tmp_path / "version"
    version.write_text("Linux version 6.8.0-45-generic (buildd@lcy02-amd64-075) #45-Ubuntu\n")
    monkeypatch.setattr(agent_env, "PROC_VERSION", version)
    wsl_lib = tmp_path / "wsl-lib"
    wsl_lib.mkdir()
    monkeypatch.setattr(agent_env, "WSL_LIB", wsl_lib)
    return agent_env.ENVIRONMENT_FILE


def test_on_macos_the_path_starts_as_path_helper_rebuilds_it(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert agent_env.base_path() == agent_env.BasePath(
        agent_env.SHELL_PATH, "path_helper", "", False
    )


def test_on_linux_the_path_starts_from_etc_environment(linux):
    linux.write_text('PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/snap/bin"\n')
    assert agent_env.base_path() == agent_env.BasePath(
        "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/snap/bin", str(linux), "", False
    )


@pytest.mark.parametrize(
    ("text", "path"),
    [
        ("PATH=/a:/b\n", "/a:/b"),
        ('PATH="/a:/b"\n', "/a:/b"),
        ("export PATH=/a\n", "/a"),
        ('export PATH="/a"\n', "/a"),
        ("# PATH=/commented\n\n  \nLANG=C\nPATH=/a\n", "/a"),
        ("PATH=/first\nPATH=/last\n", "/last"),
    ],
)
def test_etc_environment_is_read_as_pam_env_reads_its_simple_form(linux, text, path):
    linux.write_text(text)
    assert agent_env.base_path().path == path


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("LANG=C.UTF-8\n", "no PATH in {file}"),
        ('PATH=""\n', "no PATH in {file}"),
        ("# PATH=/a\n", "no PATH in {file}"),
        ('PATH="/opt/bin:$PATH"\n', "a `$` in the PATH of {file}"),
    ],
)
def test_without_a_usable_path_there_the_linux_login_default_is_taken(linux, text, reason):
    linux.write_text(text)
    assert agent_env.base_path() == agent_env.BasePath(
        agent_env.LINUX_PATH, "default", reason.format(file=linux), False
    )


def test_a_missing_etc_environment_gives_the_default(linux):
    base = agent_env.base_path()
    assert (base.path, base.source) == (agent_env.LINUX_PATH, "default")
    assert base.reason == f"no {linux}"


def test_an_unreadable_etc_environment_gives_the_default_with_the_error(linux):
    linux.mkdir()  # reading a folder fails
    base = agent_env.base_path()
    assert (base.path, base.source) == (agent_env.LINUX_PATH, "default")
    assert base.reason.startswith(f"cannot read {linux}: ")


def test_wsl_is_told_by_its_interop_file_or_proc_version(linux):
    assert not agent_env.is_wsl()
    agent_env.WSL_INTEROP.write_text("enabled\n")
    assert agent_env.is_wsl()
    agent_env.WSL_INTEROP.unlink()
    agent_env.PROC_VERSION.write_text("Linux version 5.15.153.1-microsoft-standard-WSL2\n")
    assert agent_env.is_wsl()


def test_on_wsl_its_lib_folder_is_added_and_no_windows_path(linux, monkeypatch):
    agent_env.WSL_INTEROP.write_text("enabled\n")
    monkeypatch.setenv("PATH", "/usr/bin:/bin:/mnt/c/Windows/system32")  # the caller's
    linux.write_text('PATH="/usr/local/bin:/usr/bin:/bin"\n')
    assert agent_env.base_path() == agent_env.BasePath(
        f"/usr/local/bin:/usr/bin:/bin:{agent_env.WSL_LIB}", str(linux), "", True
    )
    linux.unlink()
    base = agent_env.base_path()
    assert base.path == f"{agent_env.LINUX_PATH}:{agent_env.WSL_LIB}" and base.wsl
    assert "/mnt/c" not in base.path


def test_on_wsl_a_missing_lib_folder_is_not_added(linux):
    agent_env.WSL_INTEROP.write_text("enabled\n")
    agent_env.WSL_LIB.rmdir()
    assert agent_env.base_path().path == agent_env.LINUX_PATH


def test_the_shell_starts_from_the_base_path(shell, linux, monkeypatch):
    linux.write_text("PATH=/opt/from-etc:/usr/bin:/bin\n")
    shell()
    assert agent_env.resolve()["PATH"] == "/opt/from-etc:/usr/bin:/bin"
