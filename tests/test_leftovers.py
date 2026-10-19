import os

import leftovers


def proc_entry(root, pid, environ: bytes, cmdline: bytes = b"sleep\x0060\x00"):
    folder = root / str(pid)
    folder.mkdir()
    (folder / "environ").write_bytes(environ)
    (folder / "cmdline").write_bytes(cmdline)
    return folder


def test_the_linux_reader_splits_the_environment_at_its_nuls(tmp_path):
    proc_entry(tmp_path, 41, b"LADO_HOME=/t/a b\x00LADO_TEST_PID=7\x00")
    (tmp_path / "self").mkdir()  # not a process: no digits
    (tmp_path / "meminfo").write_text("")

    [process] = leftovers.from_proc(tmp_path)

    assert (process.pid, process.command) == (41, "sleep 60")
    assert process.has("LADO_HOME", "/t/a b")
    assert not process.has("LADO_HOME", "/t/a")  # a value that only starts the same
    assert process.get("LADO_TEST_PID") == "7"
    assert process.get("LADO_AGENT") is None


def test_the_linux_reader_skips_a_process_that_vanished_or_is_not_readable(tmp_path):
    proc_entry(tmp_path, 41, b"LADO_HOME=/t\x00")
    (tmp_path / "42").mkdir()  # ended between the listing and the read: no files left
    unreadable = proc_entry(tmp_path, 43, b"LADO_HOME=/t\x00")
    (unreadable / "environ").chmod(0)
    proc_entry(tmp_path, 44, b"")  # a zombie: its environment reads empty

    pids = [p.pid for p in leftovers.from_proc(tmp_path)]

    assert pids == [41] if os.geteuid() != 0 else pids == [41, 43]


def test_the_linux_reader_lists_only_the_users_own_processes(tmp_path, monkeypatch):
    proc_entry(tmp_path, 41, b"LADO_HOME=/t\x00")
    monkeypatch.setattr(os, "getuid", lambda: os.stat(tmp_path).st_uid + 1)

    assert leftovers.from_proc(tmp_path) == []


PS_E = """\
  101 sleep 60 PATH=/bin LADO_HOME=/t/home LADO_TEST_PID=7
  102 tmux -L lado-test-1 new-session PATH=/bin LADO_HOME=/t/home2 TERM=xterm
  103 python fake_agent.py LADO_HOME=/t/home
  104 (zsh)
"""
PS = """\
  101 sleep 60
  102 tmux -L lado-test-1 new-session
  103 python fake_agent.py
  104 (zsh)
"""


def test_the_macos_reader_matches_a_value_followed_by_a_space_or_the_lines_end():
    processes = {p.pid: p for p in leftovers.from_ps(PS_E, PS)}

    assert processes[101].has("LADO_HOME", "/t/home")  # followed by a space
    assert processes[103].has("LADO_HOME", "/t/home")  # at the line's end
    assert not processes[102].has("LADO_HOME", "/t/home")  # /t/home2 only starts the same
    assert not processes[104].has("LADO_HOME", "/t/home")
    assert processes[101].get("LADO_TEST_PID") == "7"
    assert processes[102].get("LADO_TEST_PID") is None
    assert processes[102].command == "tmux -L lado-test-1 new-session"


def test_marked_names_the_processes_with_the_value_but_the_caller(monkeypatch):
    processes = leftovers.from_ps(PS_E, PS)
    monkeypatch.setattr(leftovers, "processes", lambda: processes)
    monkeypatch.setattr(os, "getpid", lambda: 103)

    assert [p.pid for p in leftovers.marked("LADO_HOME", "/t/home")] == [101]
