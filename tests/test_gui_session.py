import os
import plistlib
import struct
import subprocess
from pathlib import Path

import pytest

from lado import gui_session, tmux
from lado.gui_session import Place

GUI_FLAGS = 0x6030  # read on the Mac host from Terminal.app (docs/design/macos-gui-session.md)
SSH_FLAGS = 0x5020  # and from ssh


def audit_info(flags: int) -> bytes:
    """The 48 bytes of an auditinfo_addr: auid, mask, termid (port, type, addr[4]), asid,
    flags."""
    return struct.pack("@I2I2I4Ii", 501, 0, 0, 0, 4, 0, 0, 0, 0, 100123) + struct.pack("@Q", flags)


@pytest.fixture
def darwin(monkeypatch):
    """A Mac, whose audit session flags and `launchctl print gui/<uid>` exit code the test
    sets: darwin.flags (an OSError for a failing call), darwin.domain."""

    class Mac:
        def __init__(self):
            self.flags: int | OSError = GUI_FLAGS
            self.domain = 0
            self.launchctl: list[list[str]] = []

    mac = Mac()
    monkeypatch.setattr(gui_session.sys, "platform", "darwin")
    monkeypatch.delenv("LADO_MACOS_PLACE", raising=False)

    def raw():
        if isinstance(mac.flags, OSError):
            raise mac.flags
        return audit_info(mac.flags)

    def run(argv, **kwargs):
        mac.launchctl.append(argv)
        return subprocess.CompletedProcess(argv, mac.domain, "", "")

    monkeypatch.setattr(gui_session, "_audit_raw", raw)
    monkeypatch.setattr(gui_session, "_launchctl", run)
    return mac


def test_flags_are_read_from_the_end_of_the_audit_info():
    assert gui_session.flags_from(audit_info(GUI_FLAGS)) == GUI_FLAGS
    assert gui_session.flags_from(audit_info(SSH_FLAGS)) == SSH_FLAGS


def test_a_process_with_graphic_access_is_in_the_gui(darwin):
    assert gui_session.place() == Place.GUI
    assert darwin.launchctl == []  # no need to ask for the domain


def test_a_process_without_graphic_access_is_remote_while_someone_is_logged_in(darwin):
    darwin.flags = SSH_FLAGS
    assert gui_session.place() == Place.REMOTE
    assert darwin.launchctl == [["launchctl", "print", f"gui/{os.getuid()}"]]
    darwin.domain = 112  # no graphical domain: nobody is logged in
    assert gui_session.place() == Place.NO_GUI


def test_unreadable_flags_are_unknown(darwin):
    darwin.flags = OSError("no getaudit_addr")
    assert gui_session.place() == Place.UNKNOWN


@pytest.mark.parametrize("flags", [GUI_FLAGS, SSH_FLAGS])
def test_the_place_never_comes_from_the_environment(darwin, monkeypatch, flags):
    darwin.flags = flags
    expected = gui_session.place()
    monkeypatch.setenv("SSH_CONNECTION", "10.0.0.1 50000 10.0.0.2 22")
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
    monkeypatch.setenv("SECURITYSESSIONID", "186bb")
    assert gui_session.place() == expected
    monkeypatch.delenv("SSH_CONNECTION")
    monkeypatch.delenv("TERM_PROGRAM")
    monkeypatch.delenv("SECURITYSESSIONID")
    assert gui_session.place() == expected


@pytest.mark.parametrize("value", ["gui", "remote", "no-gui"])
def test_tests_set_the_place_on_a_mac(darwin, monkeypatch, value):
    darwin.flags = OSError("not read")
    monkeypatch.setenv("LADO_MACOS_PLACE", value)
    assert gui_session.place() == Place(value)


def test_anything_but_a_mac_is_other_whatever_the_tests_set(monkeypatch):
    monkeypatch.setattr(gui_session.sys, "platform", "linux")
    monkeypatch.setenv("LADO_MACOS_PLACE", "remote")
    assert gui_session.place() == Place.OTHER


@pytest.fixture
def launchd(monkeypatch, darwin, tmp_path):
    """launchctl and the tmux server recorded: launchd.bootstrap is its exit code, and
    launchd.server whether a server runs after it; launchd.plists the plists it was given."""

    class Launchd:
        def __init__(self):
            self.bootstrap = 0
            self.server = True
            self.running = False
            self.plists: list[dict] = []
            self.calls: list[list[str]] = []

    fake = Launchd()

    def launchctl(argv, **kwargs):
        fake.calls.append(argv)
        if argv[1] == "bootstrap":
            fake.plists.append(plistlib.loads(Path(argv[3]).read_bytes()))
            fake.running = fake.server
            return subprocess.CompletedProcess(argv, fake.bootstrap, "", "Bootstrap failed: 5")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(gui_session, "_launchctl", launchctl)
    monkeypatch.setattr(tmux, "server_running", lambda socket=None: fake.running)
    monkeypatch.setattr(gui_session, "START_POLL", 0)
    return fake


def _plists(home: Path) -> list[Path]:
    return list(home.rglob("*.plist"))


def test_start_server_starts_tmux_in_the_graphical_domain(launchd, lado_home, monkeypatch):
    env = {"LANG": "en_US.UTF-8", "TMUX_TMPDIR": "/tmp/t", "PATH": "/x", "SSH_CONNECTION": "a"}
    assert gui_session.start_server("sock", "/opt/bin/tmux", env) is None
    label = f"{gui_session.LABEL_PREFIX}.sock.{os.getpid()}"
    domain = f"gui/{os.getuid()}"
    bootstrap, bootout = launchd.calls
    assert bootstrap[:3] == ["launchctl", "bootstrap", domain]
    assert bootout == ["launchctl", "bootout", f"{domain}/{label}"]
    assert launchd.plists == [
        {
            "Label": label,
            "ProgramArguments": [
                "/opt/bin/tmux",
                "-L",
                "sock",
                "start-server",
                ";",
                "set-option",
                "-g",
                "exit-empty",
                "off",
            ],
            "RunAtLoad": True,
            "AbandonProcessGroup": True,
            "EnvironmentVariables": {"LANG": "en_US.UTF-8", "TMUX_TMPDIR": "/tmp/t"},
        }
    ]
    assert Path(bootstrap[3]).is_relative_to(lado_home)
    assert _plists(lado_home) == []


def test_without_locale_variables_the_plist_has_no_environment(launchd, lado_home):
    assert gui_session.start_server("sock", "/opt/bin/tmux", {"PATH": "/x"}) is None
    assert "EnvironmentVariables" not in launchd.plists[0]


def test_a_failed_bootstrap_is_the_reason_and_leaves_no_plist(launchd, lado_home):
    launchd.bootstrap, launchd.server = 5, False
    why = gui_session.start_server("sock", "/opt/bin/tmux", {})
    assert why is not None and "Bootstrap failed: 5" in why
    assert [c[1] for c in launchd.calls] == ["bootstrap", "bootout"]
    assert _plists(lado_home) == []


def test_a_failed_bootstrap_with_a_server_after_it_is_no_failure(launchd, lado_home):
    """Two starts at once: the other's server is there."""
    launchd.bootstrap = 5
    assert gui_session.start_server("sock", "/opt/bin/tmux", {}) is None
    assert _plists(lado_home) == []


def test_a_server_that_does_not_come_is_a_timeout_and_leaves_no_plist(
    launchd, lado_home, monkeypatch
):
    launchd.server = False
    monkeypatch.setattr(gui_session, "START_TIMEOUT", 0.05)
    why = gui_session.start_server("sock", "/opt/bin/tmux", {})
    assert why is not None and "0.05" in why
    assert [c[1] for c in launchd.calls] == ["bootstrap", "bootout"]
    assert _plists(lado_home) == []


def test_ensure_server_starts_one_only_from_outside_the_gui_with_no_server(launchd, monkeypatch):
    started = []
    monkeypatch.setattr(
        gui_session, "start_server", lambda *a: started.append(a) or "launchd said no"
    )
    for place in ("gui", "no-gui"):
        monkeypatch.setenv("LADO_MACOS_PLACE", place)
        assert gui_session.ensure_server("sock") is None
    monkeypatch.setenv("LADO_MACOS_PLACE", "remote")
    launchd.running = True
    assert gui_session.ensure_server("sock") is None
    assert started == []
    launchd.running = False
    said = gui_session.ensure_server("sock")
    assert said == gui_session.LAUNCHD_FAILED.format(why="launchd said no")
    ((socket, path, env),) = started
    assert socket == "sock" and Path(path).name == "tmux" and Path(path).is_absolute()
    assert "CLAUDECODE" not in env  # tmux's own clean environment


def test_ensure_server_does_nothing_but_on_a_mac(monkeypatch):
    monkeypatch.setattr(gui_session.sys, "platform", "linux")
    monkeypatch.setattr(gui_session, "start_server", lambda *a: pytest.fail("started"))
    assert gui_session.ensure_server("sock") is None


def test_server_place_with_no_server_is_none_and_runs_nothing(darwin, monkeypatch):
    monkeypatch.setattr(tmux, "server_running", lambda socket=None: False)
    monkeypatch.setattr(tmux, "_run_once", lambda *a, **k: pytest.fail("ran tmux"))
    assert gui_session.server_place("sock") is None


@pytest.mark.parametrize(
    ("flags", "domain", "expected"),
    [(GUI_FLAGS, 0, Place.GUI), (SSH_FLAGS, 0, Place.REMOTE), (SSH_FLAGS, 112, Place.NO_GUI)],
)
def test_server_place_reads_the_servers_flags(darwin, monkeypatch, flags, domain, expected):
    darwin.domain = domain
    darwin.flags = OSError("the process's own flags are not asked")
    shells = []
    monkeypatch.setattr(tmux, "server_running", lambda socket=None: True)

    def run_once(args, input, sock=None):
        shells.append((sock, args))
        return audit_info(flags).hex() + "\n"

    monkeypatch.setattr(tmux, "_run_once", run_once)
    assert gui_session.server_place("sock") == expected
    ((sock, (command, probe)),) = shells
    assert sock == "sock" and command == "run-shell" and " -I -c " in probe


def test_a_server_place_that_cannot_be_read_is_unknown(darwin, monkeypatch):
    monkeypatch.setattr(tmux, "server_running", lambda socket=None: True)
    monkeypatch.setattr(tmux, "_run_once", lambda *a, **k: "error\n")
    assert gui_session.server_place("sock") == Place.UNKNOWN

    def fails(*a, **k):
        raise tmux.TmuxError("lost")

    monkeypatch.setattr(tmux, "_run_once", fails)
    assert gui_session.server_place("sock") == Place.UNKNOWN


def test_the_probe_reads_this_process_flags():
    """The probe runs as is in a Python of its own (not on a Mac it fails: unknown)."""
    done = subprocess.run([*gui_session.probe_argv()], capture_output=True, text=True, check=False)
    if gui_session.sys.platform != "darwin":
        assert done.returncode != 0
        return
    assert gui_session.flags_from(bytes.fromhex(done.stdout)) == gui_session.flags_from(
        gui_session._audit_raw()
    )


def test_the_texts_name_the_providers_and_their_hints():
    users = [("Claude Code", ", or set a token")]
    text = gui_session.fill(gui_session.NO_GUI, users)
    assert "so Claude Code cannot read its login" in text and text.endswith(", or set a token")
    two = gui_session.fill(gui_session.OUTSIDE_GUI, [("A", ""), ("B", "; hint")])
    assert "so A and B cannot read" in two and two.endswith("; hint")
    assert "Claude" not in Path(gui_session.__file__).read_text()


def test_ensure_server_that_cannot_ask_tmux_says_why(darwin, monkeypatch):
    monkeypatch.setenv("LADO_MACOS_PLACE", "remote")

    def fails(socket=None):
        raise tmux.TmuxError("tmux timed out: list-sessions")

    monkeypatch.setattr(tmux, "server_running", fails)
    monkeypatch.setattr(gui_session, "start_server", lambda *a: pytest.fail("started"))
    said = gui_session.ensure_server("sock")
    assert said == gui_session.LAUNCHD_FAILED.format(why="tmux timed out: list-sessions")
