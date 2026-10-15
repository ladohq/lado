"""scripts/rc_check.py: the human's checks of a release candidate (docs/release.md, section
4). Every command it runs goes through `rc.run`, which a recorder replaces here."""

import contextlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "rc_check.py"

CHANGELOG = """# Changelog

## 0.38.0 (unreleased)

- Something new.
- A fix
  wrapped over two lines.

## 0.37.0 (2026-10-13)

- An older item.
"""


def _module():
    spec = importlib.util.spec_from_file_location("rc_check", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["rc_check"] = module  # its dataclasses look their module up
    spec.loader.exec_module(module)
    return module


rc = _module()
MISSING_TOOLS = rc.missing_tools


@pytest.fixture(autouse=True)
def tools_on_path(monkeypatch):
    """uv, tmux and git are on PATH for every test but those that say otherwise."""
    monkeypatch.setattr(rc, "missing_tools", lambda: [])


def test_a_sandbox_without_tmux_or_git_stops_before_anything(
    monkeypatch, capsys, tmp_path, recorder
):
    """0.39.0rc1: a Mac without tmux installed the RC and failed only at `lado doctor`."""
    monkeypatch.setattr(rc, "missing_tools", MISSING_TOOLS)
    found = {"uv": "/opt/bin/uv"}
    monkeypatch.setattr(rc.shutil, "which", lambda name: found.get(name))
    monkeypatch.setattr(rc, "fetch_index", lambda: pytest.fail("no PyPI before the tools"))
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    assert rc.main(["sandbox", "0.38.0rc1"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    (line,) = captured.err.splitlines()
    assert line.startswith("rc_check: not on PATH: tmux, git; install first (")
    assert "tmux: brew install tmux, or sudo apt install tmux" in line
    assert "git: xcode-select --install, or sudo apt install git" in line
    assert "uv:" not in line
    assert recorder.calls == [] and list(tmp_path.iterdir()) == []


def test_with_every_tool_on_path_nothing_is_missing(monkeypatch):
    monkeypatch.setattr(rc.shutil, "which", lambda name: f"/opt/bin/{name}")
    assert MISSING_TOOLS() == []


def test_versions_sort_release_candidates_before_their_final():
    v = rc.parse
    assert sorted([v("0.38.0"), v("0.38.0rc2"), v("0.37.1"), v("0.38.0rc10"), v("0.38.0rc1")]) == [
        v("0.37.1"),
        v("0.38.0rc1"),
        v("0.38.0rc2"),
        v("0.38.0rc10"),
        v("0.38.0"),
    ]
    assert v("0.38.0rc2").final is False and v("0.38.0").final is True
    assert str(v("0.38.0rc2")) == "0.38.0rc2"
    for other in ("0.38.0.dev1", "0.38.0a1", "0.38", "v0.38.0", "0.38.0-rc1"):
        assert v(other) is None


def test_releases_skip_other_forms_and_yanked_ones():
    index = {
        "releases": {
            "0.37.0": [{"yanked": False}],
            "0.37.1": [{"yanked": True}],
            "0.38.0rc1": [],
            "0.38.0.dev1": [],
        }
    }
    assert rc.releases(index) == [rc.parse("0.37.0"), rc.parse("0.38.0rc1")]


def test_the_default_version_is_the_newest_release_candidate(monkeypatch):
    monkeypatch.setattr(rc, "fetch_index", lambda: {"releases": {"0.37.0": [], "0.38.0rc2": []}})
    called = []
    monkeypatch.setattr(rc, "sandbox", lambda *args: called.append(args) or 0)
    assert rc.main(["sandbox", "--no-ui"]) == 0
    assert called == [(rc.parse("0.38.0rc2"), "claude", False)]


def test_the_default_version_refuses_a_final(capsys, monkeypatch):
    monkeypatch.setattr(rc, "fetch_index", lambda: {"releases": {"0.37.0rc2": [], "0.38.0": []}})
    monkeypatch.setattr(rc, "sandbox", lambda *args: pytest.fail("no sandbox for a final"))
    assert rc.main(["sandbox"]) == 2
    assert "0.38.0 is a final release: name the RC to check" in capsys.readouterr().err


def test_a_named_final_is_refused(capsys, monkeypatch):
    monkeypatch.setattr(rc, "sandbox", lambda *args: pytest.fail("no sandbox for a final"))
    assert rc.main(["sandbox", "0.38.0"]) == 2
    assert rc.main(["upgrade", "0.38.0"]) == 2
    err = capsys.readouterr().err
    assert "0.38.0 is a final release" in err


def test_a_version_of_another_form_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as done:
        rc.main(["sandbox", "0.38.0a1"])
    assert done.value.code == 2
    assert "X.Y.ZrcN" in capsys.readouterr().err


def test_pypi_unreachable_is_one_fail_line(capsys, monkeypatch, tmp_path):
    def down():
        raise OSError("timed out")

    temp = tmp_path / "temp"
    temp.mkdir()
    monkeypatch.setattr(rc, "fetch_index", down)
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    assert rc.main(["sandbox"]) == 1
    assert capsys.readouterr().out == "[FAIL] PyPI: timed out\n"
    assert list(temp.iterdir()) == []


def test_checklist_lists_the_rc_section_items():
    lines = rc.checklist(rc.parse("0.38.0rc1"), CHANGELOG, 'version = "0.38.0rc1"\n')
    assert lines[-2:] == ["[ ] Something new.", "[ ] A fix wrapped over two lines."]
    assert any("sdlc" in line and "first gate" in line for line in lines)
    assert any("pre-release" in line for line in lines)
    assert not any(line.startswith("warning") for line in lines)
    assert "An older item." not in "\n".join(lines)


def test_checklist_without_the_section_warns():
    lines = rc.checklist(rc.parse("0.39.0rc1"), CHANGELOG, 'version = "0.39.0rc1"\n')
    assert lines[-1] == (
        'warning: CHANGELOG.md has no section "## 0.39.0 (unreleased)" for v0.39.0rc1'
    )
    lines = rc.checklist(rc.parse("0.39.0rc1"), None, 'version = "0.39.0rc1"\n')
    assert lines[-1] == "warning: no CHANGELOG.md here: run the script from the repository's root"


def test_checklist_warns_about_another_checkout():
    lines = rc.checklist(rc.parse("0.38.0rc1"), CHANGELOG, '[project]\nversion = "0.37.1"\n')
    assert (
        "warning: pyproject.toml says 0.37.1, not 0.38.0rc1: this checkout is not the RC's "
        "commit, and its CHANGELOG.md may not be the RC's"
    ) in lines


def test_the_real_run_passes_output_and_exit_code():
    done = rc.run([sys.executable, "-c", "import sys; print('out'); sys.exit(3)"])
    assert (done.code, done.output) == (3, "out\n")
    missing = rc.run(["no-such-command-of-rc-check"])
    assert missing.code == 127 and "no-such-command-of-rc-check" in missing.output


def verb(argv: list[str]) -> str:
    """What a recorded command does: `doctor`, `telemetry status`, `stop --all`,
    `uv tool install`, `git commit`, `tmux has-session`..."""
    program, rest = Path(argv[0]).name, argv[1:]
    if program == "tmux":
        rest = rest[2:] if rest[:1] == ["-L"] else rest
        return f"tmux {rest[0]}"
    if program in ("uv", "git"):
        return " ".join([program, *rest[: 2 if program == "uv" else 1]])
    if rest[0] in ("telemetry", "server") or rest[1:2] == ["--all"]:
        return " ".join(rest[:2])
    return rest[0]


class Recorder:
    """`rc.run` replaced: each call recorded with its environment, answered by its verb."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict | None, bool]] = []
        self.answers: dict[str, list] = {}
        self.alive: set[str] = set()
        self.target = "0.38.0rc1"  # the sandbox's RC: what its lado says it is

    def answer(self, what: str, code: int, output: str = "", then=None) -> None:
        """`what`'s answer from now on; `then` runs when it is called."""
        self.answers[what] = [(code, output, then)]

    def version(self, *versions: str) -> None:
        """`lado --version`'s answers in turn, the last one from then on."""
        self.answers["--version"] = [(0, f"lado {v}\n", None) for v in versions]

    def default(self, what: str, argv: list[str]) -> tuple[int, str]:
        if what == "--version":
            return 0, f"lado {self.target}\n"
        if what == "telemetry status":
            return 0, "statistics: off: LADO_TELEMETRY=0 is set (your choice: not chosen)\n"
        if what == "doctor":
            return 0, f"[ok  ] LADO: {self.target} (pre-release)\n[ok  ] tmux: 3.5a\n"
        if what == "ls":
            return 0, "rc-check  /tmp/lado-rc-x/repo\n  supervisor   supervisor claude  waiting\n"
        if what == "tmux list-sessions":
            return 1, "no server running on /private/tmp/tmux-501/lado-rc-1\n"
        if what == "tmux has-session":
            return (0, "") if argv[-1].lstrip("=") in self.alive else (1, "can't find session")
        return 0, ""

    def __call__(self, argv, env=None, terminal=False, cwd=None):
        self.calls.append((list(argv), env, terminal))
        what = verb(argv)
        queue = self.answers.get(what)
        if not queue:
            return rc.Result(*self.default(what, argv))
        code, output, then = queue.pop(0) if len(queue) > 1 else queue[0]
        if then:
            then()
        return rc.Result(code, "" if terminal else output)

    def verbs(self) -> list[str]:
        return [verb(argv) for argv, _, _ in self.calls]

    def argvs(self, what: str) -> list[list[str]]:
        return [argv for argv, _, _ in self.calls if verb(argv) == what]


@pytest.fixture
def recorder(monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(rc, "run", recorder)
    return recorder


DOCTOR_FAILED = (
    "[ok  ] LADO: 0.38.0rc1 (pre-release)\n"
    "[FAIL] tmux: `tmux` not found on PATH\n"
    "       install it: `brew install tmux` or `sudo apt install tmux`\n"
    "[ok  ] git: 2.50.1\n"
    + "".join(f"[ok  ] check {n}: fine\n" for n in range(12))
    + "[FAIL] Agent CLI: no agent CLI installed\n"
    + "       Claude Code: npm install -g @anthropic-ai/claude-code\n"
    + "[info] LADO_HOME: /tmp/home\n"
)


def test_a_failed_doctor_shows_its_fail_lines_with_their_hints(recorder, temp, capsys):
    """0.39.0rc1: the last lines of a long `lado doctor` cut off its [FAIL] line."""
    recorder.answer("doctor", 1, DOCTOR_FAILED)
    assert rc.sandbox(rc.parse("0.38.0rc1"), "claude", ui=False) == 1
    out = capsys.readouterr().out.splitlines()
    at = out.index("[FAIL] doctor: lado doctor exited 1")
    assert out[at + 1 : at + 6] == [
        "         [FAIL] tmux: `tmux` not found on PATH",
        "                install it: `brew install tmux` or `sudo apt install tmux`",
        "         [FAIL] Agent CLI: no agent CLI installed",
        "                Claude Code: npm install -g @anthropic-ai/claude-code",
        "",
    ]


def test_output_without_fail_lines_shows_its_last_lines():
    output = "".join(f"line {n}\n" for n in range(rc.OUTPUT_LINES + 5))
    assert rc.shown(output) == [f"line {n}" for n in range(5, rc.OUTPUT_LINES + 5)]
    assert rc.shown("") == []


@pytest.fixture
def temp(tmp_path, monkeypatch):
    """The temporary folder the sandbox is made in."""
    folder = tmp_path / "temp"
    folder.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(folder))
    return folder


def test_every_lado_call_of_the_sandbox_has_statistics_off_and_its_own_home(
    recorder, temp, lado_home, monkeypatch
):
    """D9: the rule LAD-50 held docs/release.md's scratch home to, now held by the script."""
    for name in ("LADO_AGENT", "LADO_SESSION", "LADO_INSTANCE", "VIRTUAL_ENV"):
        monkeypatch.setenv(name, "from-the-caller")
    monkeypatch.setenv("LADO_TELEMETRY", "1")
    assert rc.sandbox(rc.parse("0.38.0rc1"), "claude", ui=False) == 0
    calls = [(argv, env) for argv, env, _ in recorder.calls]
    assert {verb(argv) for argv, _ in calls} >= {"uv tool install", "doctor", "start", "uninstall"}
    for argv, env in calls:
        assert env is not None, argv
        assert env["LADO_TELEMETRY"] == "0", argv
        for name in ("LADO_HOME", "UV_TOOL_DIR", "UV_TOOL_BIN_DIR"):
            assert env[name].startswith(str(temp / "lado-rc-")), (argv, name)
        assert env["LADO_HOME"] != str(lado_home)
        assert env["LADO_TMUX_SOCKET"].startswith("lado-rc-")
        for name in ("LADO_AGENT", "LADO_SESSION", "LADO_INSTANCE", "VIRTUAL_ENV"):
            assert name not in env, (argv, name)
    sandbox_lado = [argv[0] for argv, _ in calls if verb(argv) == "doctor"][0]
    assert sandbox_lado.startswith(str(temp)) and sandbox_lado.endswith("/bin/lado")


def test_the_sandbox_steps_in_order_and_everything_removed(recorder, temp, capsys, monkeypatch):
    asked = []
    monkeypatch.setattr("builtins.input", lambda prompt: asked.append(prompt) or "")
    assert rc.sandbox(rc.parse("0.38.0rc1"), "codex", ui=True) == 0
    assert recorder.verbs() == [
        "uv tool install",
        "--version",
        "telemetry status",
        "doctor",
        "git init",
        "git add",
        "git commit",
        "start",
        "ls",
        "ui",
        "stop",
        "uninstall",
        "tmux list-sessions",
    ]
    assert recorder.argvs("uv tool install")[0][3:] == [
        "--refresh-package",
        "lado",
        "lado==0.38.0rc1",
    ]
    start = recorder.argvs("start")[0]
    assert start[3:] == ["--name", "rc-check", "--provider", "codex", "--no-attach"]
    assert start[2].startswith(str(temp)) and start[2].endswith("/repo")
    ui = [(argv, terminal) for argv, _, terminal in recorder.calls if verb(argv) == "ui"]
    assert ui == [([ui[0][0][0], "ui", "--no-open", "--port", "0"], True)]
    assert list(temp.iterdir()) == []
    out = capsys.readouterr().out
    assert out.count("[ok  ]") == 8 and "[FAIL]" not in out
    assert "Left to check by hand on LADO 0.38.0rc1:" in out
    assert len(asked) == 1 and "press Enter" in asked[0]


def test_without_ui_it_does_not_wait(recorder, temp, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("no question without the UI"))
    assert rc.sandbox(rc.parse("0.38.0rc1"), "claude", ui=False) == 0
    assert "ui" not in recorder.verbs()


def test_the_scratch_repository_needs_no_git_identity_or_hooks_of_the_human(recorder, temp):
    rc.sandbox(rc.parse("0.38.0rc1"), "claude", ui=False)
    commit = [(argv, env) for argv, env, _ in recorder.calls if verb(argv) == "git commit"][0]
    assert "--no-verify" in commit[0] and "--no-gpg-sign" in commit[0]
    assert commit[1]["GIT_AUTHOR_EMAIL"] == commit[1]["GIT_COMMITTER_EMAIL"] == "rc-check@localhost"


@pytest.mark.parametrize(
    ("what", "code", "output", "line"),
    [
        ("uv tool install", 2, "No solution found", "[FAIL] install: uv tool install exited 2"),
        ("--version", 0, "lado 0.37.1\n", "[FAIL] version: lado --version says lado 0.37.1"),
        ("telemetry status", 0, "statistics: not chosen\n", "[FAIL] statistics off"),
        (
            "doctor",
            0,
            "[ok  ] LADO: 0.38.0rc1\n",
            "[FAIL] doctor: it does not say 0.38.0rc1 (pre-release)",
        ),
        ("doctor", 1, "[FAIL] tmux: missing\n", "[FAIL] doctor: lado doctor exited 1"),
        (
            "start",
            1,
            "lado: claude is not installed\n",
            "[FAIL] session starts: lado start exited 1",
        ),
        ("ls", 0, "No sessions.\n", "[FAIL] session starts: lado ls does not show rc-check"),
        ("stop", 1, "lado: tmux\n", "[FAIL] session stops: lado stop exited 1"),
        ("uninstall", 1, "lado: refused\n", "[FAIL] uninstall: lado uninstall exited 1"),
        (
            "tmux list-sessions",
            0,
            "rc-check: 1 windows\n",
            "[FAIL] uninstall: its tmux server still runs",
        ),
    ],
)
def test_a_failed_check_stops_and_keeps_the_sandbox(
    recorder, temp, capsys, what, code, output, line
):
    recorder.answer(what, code, output)
    assert rc.sandbox(rc.parse("0.38.0rc1"), "claude", ui=False) == 1
    out = capsys.readouterr().out
    assert line in out
    assert [x for x in out.splitlines() if x.startswith("[FAIL]")] == [
        x for x in out.splitlines() if x.startswith(line)
    ]
    assert output.strip().splitlines()[-1] in out  # the command's own words, under the line
    assert recorder.verbs()[-1] == what  # no later check
    (kept,) = temp.iterdir()
    assert f"The sandbox is kept for a look: {kept}" in out
    socket = recorder.calls[0][1]["LADO_TMUX_SOCKET"]
    assert (
        f"LADO_HOME={kept}/home LADO_TMUX_SOCKET={socket} LADO_TELEMETRY=0 "
        f"{kept}/bin/lado uninstall --yes; tmux -L {socket} kill-server; rm -rf {kept}"
    ) in out
    assert "Left to check by hand" not in out


@pytest.fixture
def socket_file(tmp_path, monkeypatch):
    """The sandbox's tmux socket file, which tmux leaves behind when its server ends."""
    monkeypatch.setenv("TMUX_TMPDIR", str(tmp_path / "tmux"))
    path = tmp_path / "tmux" / f"tmux-{os.getuid()}" / f"lado-rc-{os.getpid()}"
    path.parent.mkdir(parents=True)
    path.touch()
    return path


def test_the_socket_file_tmux_leaves_is_removed(recorder, temp, socket_file):
    assert rc.sandbox(rc.parse("0.38.0rc1"), "claude", ui=False) == 0
    assert not socket_file.exists()


def test_a_kept_sandbox_names_its_socket_file_in_its_cleanup(recorder, temp, socket_file, capsys):
    recorder.answer("doctor", 1)
    assert rc.sandbox(rc.parse("0.38.0rc1"), "claude", ui=False) == 1
    assert socket_file.exists()
    assert capsys.readouterr().out.rstrip().endswith(f"rm -rf {next(temp.iterdir())} {socket_file}")


def test_ctrl_c_removes_the_socket_file_too(recorder, temp, socket_file, monkeypatch):
    def interrupt(*_):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupt)
    assert rc.sandbox(rc.parse("0.38.0rc1"), "claude", ui=True) == 130
    assert not socket_file.exists()


def test_ctrl_c_at_the_ui_removes_everything(recorder, temp, monkeypatch, capsys):
    def interrupt(*_):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupt)
    assert rc.sandbox(rc.parse("0.38.0rc1"), "claude", ui=True) == 130
    assert recorder.verbs()[-4:] == ["ui", "stop", "uninstall", "tmux kill-server"]
    assert list(temp.iterdir()) == []
    assert "Interrupted: the sandbox is removed." in capsys.readouterr().out


def test_ctrl_c_before_the_session_removes_everything_too(recorder, temp):
    def interrupt():
        raise KeyboardInterrupt

    recorder.answer("doctor", 0, "", then=interrupt)
    assert rc.sandbox(rc.parse("0.38.0rc1"), "claude", ui=False) == 130
    assert recorder.verbs()[-2:] == ["uninstall", "tmux kill-server"]
    assert "stop" not in recorder.verbs()
    assert list(temp.iterdir()) == []


def test_enter_at_the_end_of_input_is_enter(recorder, temp, monkeypatch):
    def eof(*_):
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    assert rc.sandbox(rc.parse("0.38.0rc1"), "claude", ui=True) == 0


LADO = "/home/u/.local/bin/lado"  # the human's own


class Homes:
    def __init__(self, user: Path, lado: Path) -> None:
        self.user = user  # HOME
        self.lado = lado  # LADO_HOME
        self.keep = user / ".lado-rc"
        self.backups = lado / "backups"

    def back_up(self, version: str, content: bytes = b"backup") -> None:
        """What `lado update` leaves: one backup, of the version it updated from."""
        self.backups.mkdir(parents=True, exist_ok=True)
        for old in self.backups.iterdir():
            old.unlink()
        (self.backups / f"lado.db.{version}").write_bytes(content)


@pytest.fixture
def homes(tmp_path, lado_home, monkeypatch):
    user = tmp_path / "user"
    user.mkdir()
    lado_home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(user))
    monkeypatch.setattr(rc.shutil, "which", lambda name: LADO if name == "lado" else None)
    return Homes(user, lado_home)


def test_upgrade_from_a_final_keeps_its_backup(recorder, homes, capsys):
    homes.back_up("0.36.0")  # an older update's
    (homes.keep).mkdir()
    (homes.keep / "lado.db.0.36.0").write_bytes(b"an older cycle's")
    recorder.version("0.37.1", "0.38.0rc1")
    recorder.answer("update", 0, then=lambda: homes.back_up("0.37.1", b"the final's"))
    assert rc.upgrade(rc.parse("0.38.0rc1")) == 0
    updates = [(argv, terminal) for argv, _, terminal in recorder.calls if verb(argv) == "update"]
    assert updates == [([LADO, "update", "0.38.0rc1"], True)]  # its own question, no --yes
    assert [p.name for p in homes.keep.iterdir()] == ["lado.db.0.37.1"]
    assert (homes.keep / "lado.db.0.37.1").read_bytes() == b"the final's"
    out = capsys.readouterr().out
    assert f"Kept a copy of LADO 0.37.1's database: {homes.keep / 'lado.db.0.37.1'}" in out
    assert "Left to check by hand on LADO 0.38.0rc1:" in out


def test_upgrade_from_an_rc_leaves_the_copy(recorder, homes, capsys):
    homes.keep.mkdir()
    (homes.keep / "lado.db.0.37.1").write_bytes(b"final")
    recorder.version("0.38.0rc1", "0.38.0rc2")
    recorder.answer("update", 0, then=lambda: homes.back_up("0.38.0rc1"))
    assert rc.upgrade(rc.parse("0.38.0rc2")) == 0
    assert [p.name for p in homes.keep.iterdir()] == ["lado.db.0.37.1"]
    assert (homes.keep / "lado.db.0.37.1").read_bytes() == b"final"
    assert "rollback goes back to LADO 0.37.1" in capsys.readouterr().out


def test_upgrade_from_an_rc_without_a_copy_warns(recorder, homes, capsys):
    recorder.version("0.38.0rc1", "0.38.0rc2")
    assert rc.upgrade(rc.parse("0.38.0rc2")) == 0
    assert "warning: ~/.lado-rc holds no copy of a final's database" in capsys.readouterr().out


def test_upgrade_from_a_final_without_a_backup_warns(recorder, homes, capsys):
    recorder.version("0.37.1", "0.38.0rc1")
    assert rc.upgrade(rc.parse("0.38.0rc1")) == 0
    assert not homes.keep.exists()
    out = capsys.readouterr().out
    assert f"warning: no backup {homes.backups / 'lado.db.0.37.1'}" in out


def test_an_update_that_installed_the_rc_but_failed_after_keeps_the_copy(recorder, homes, capsys):
    """`lado update` exits 1 for a session that did not resume (`partial`), after it
    installed the RC: its backup is the final's all the same, and the next update drops it."""
    recorder.version("0.37.1", "0.38.0rc1")
    recorder.answer("update", 1, then=lambda: homes.back_up("0.37.1", b"the final's"))
    assert rc.upgrade(rc.parse("0.38.0rc1")) == 1
    assert (homes.keep / "lado.db.0.37.1").read_bytes() == b"the final's"
    err = capsys.readouterr().err
    assert "lado update 0.38.0rc1 exited 1, but LADO is 0.38.0rc1 now" in err
    assert "nothing kept" not in err


def test_a_failed_update_copies_nothing(recorder, homes, capsys):
    homes.back_up("0.37.0")
    recorder.version("0.37.1")
    recorder.answer("update", 1)
    assert rc.upgrade(rc.parse("0.38.0rc1")) == 1
    assert not homes.keep.exists()
    assert "lado update 0.38.0rc1 did not update (exit 1): nothing kept" in capsys.readouterr().err


def test_an_update_that_left_another_version_is_a_failure(recorder, homes, capsys):
    recorder.version("0.37.1", "0.37.1")
    recorder.answer("update", 0, then=lambda: homes.back_up("0.37.1"))
    assert rc.main(["upgrade", "0.38.0rc1"]) == 1
    assert not homes.keep.exists()
    assert "lado --version says lado 0.37.1 after the update" in capsys.readouterr().err


def test_the_working_copys_lado_is_refused(monkeypatch, capsys, recorder):
    found = str(ROOT / ".venv" / "bin" / "lado")
    monkeypatch.setattr(rc.shutil, "which", lambda _: found)
    assert rc.main(["upgrade", "0.38.0rc1"]) == 1
    err = capsys.readouterr().err
    assert f"lado on PATH is this repository's {found}" in err
    assert "python3 scripts/rc_check.py" in err
    assert recorder.calls == []


def test_no_lado_on_path_is_refused(monkeypatch, capsys, recorder):
    monkeypatch.setattr(rc.shutil, "which", lambda _: None)
    assert rc.main(["upgrade", "0.38.0rc1"]) == 1
    assert "no lado on PATH" in capsys.readouterr().err


def test_upgrade_and_rollback_inside_an_agent_are_refused(monkeypatch, capsys, recorder, homes):
    monkeypatch.setenv("LADO_AGENT", "w1")
    assert rc.main(["upgrade", "0.38.0rc1"]) == 1
    assert rc.main(["rollback"]) == 1
    assert "not in an agent" in capsys.readouterr().err
    assert recorder.calls == []


def make_db(path: Path, schema: int, sessions: list[tuple[str, str, str | None]]) -> None:
    """A lado.db as far as rollback reads it: its sessions and its schema."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.closing(sqlite3.connect(path)) as db:
        db.execute("CREATE TABLE sessions (name TEXT PRIMARY KEY, repo TEXT, stopped_at TEXT)")
        db.executemany("INSERT INTO sessions VALUES (?, ?, ?)", sessions)
        db.execute(f"PRAGMA user_version = {schema}")
        db.commit()


def schema(path: Path) -> int:
    with contextlib.closing(sqlite3.connect(path)) as db:
        return db.execute("PRAGMA user_version").fetchone()[0]


def names(path: Path) -> list[str]:
    with contextlib.closing(sqlite3.connect(path)) as db:
        return [row[0] for row in db.execute("SELECT name FROM sessions ORDER BY name")]


@pytest.fixture
def on_rc(recorder, homes, monkeypatch):
    """The human's LADO on 0.38.0rc1 (schema 27) with session `app` running, the copy of
    0.37.1 (schema 26) kept, a terminal, and `y` to the question."""
    make_db(homes.lado / "lado.db", 27, [("app", "/r/app", None), ("done", "/r/done", "2026")])
    make_db(homes.keep / "lado.db.0.37.1", 26, [("app", "/r/app", "2026"), ("old", "/r/old", None)])
    recorder.version("0.38.0rc1", "0.37.1")
    recorder.alive = {"app"}
    asked = []
    monkeypatch.setattr(rc, "_terminal", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: asked.append(prompt) or "y")
    return asked


def test_rollback_restores_a_newer_schema_and_resumes(recorder, homes, on_rc, capsys):
    assert rc.rollback() == 0
    out = capsys.readouterr().out
    assert on_rc == ["Roll back? [y/N] "]
    assert "Roll back LADO 0.38.0rc1 to 0.37.1:" in out
    assert "start them again on 0.37.1: app (/r/app)\n" in out  # not `done`: it is stopped
    assert "restore lado.db from" in out and "schema 26" in out and "lost" in out
    assert recorder.verbs() == [
        "--version",
        "tmux has-session",
        "stop --all",
        "server stop",
        "update",
        "--version",
        "start",
    ]
    assert [LADO, "update", "0.37.1"] in recorder.argvs("update")
    terminal = {verb(argv): t for argv, _, t in recorder.calls}
    assert terminal["update"] and terminal["stop --all"]
    assert schema(homes.lado / "lado.db") == 26
    assert names(homes.lado / "lado.db") == ["app", "old"]  # the copy's content
    assert recorder.argvs("start") == [[LADO, "start", "/r/app", "--name", "app", "--no-attach"]]
    assert (homes.keep / "lado.db.0.37.1").exists()  # kept for a second rollback
    assert "[ok  ] lado.db restored: schema 26" in out
    assert "[ok  ] session app started on 0.37.1" in out


def test_the_has_session_check_names_the_session_exactly(recorder, homes, on_rc, monkeypatch):
    monkeypatch.setenv("LADO_TMUX_SOCKET", "lado-other")
    rc.rollback()
    checks = recorder.argvs("tmux has-session")
    assert ["tmux", "-L", "lado-other", "has-session", "-t", "=app"] in checks


def test_same_schema_restores_nothing(recorder, homes, on_rc, capsys):
    (homes.keep / "lado.db.0.37.1").unlink()
    make_db(homes.keep / "lado.db.0.37.1", 27, [("old", "/r/old", None)])
    assert rc.rollback() == 0
    out = capsys.readouterr().out
    assert "lado.db is kept: its schema 27 is the copy's" in out
    assert names(homes.lado / "lado.db") == ["app", "done"]
    assert "restored" not in out


def test_a_session_whose_tmux_is_gone_is_not_resumed(recorder, homes, on_rc, capsys):
    recorder.alive = set()
    assert rc.rollback() == 0
    assert recorder.argvs("start") == []
    assert "no session runs" in capsys.readouterr().out


def test_the_server_is_started_again_on_its_port(recorder, homes, on_rc, capsys):
    info = {"url": "http://127.0.0.1:8003", "host": "127.0.0.1", "port": 8003, "pid": os.getpid()}
    (homes.lado / "server.json").write_text(json.dumps(info))
    assert rc.rollback() == 0
    assert recorder.argvs("ui") == [[LADO, "ui", "--no-open", "--port", "8003"]]
    out = capsys.readouterr().out
    assert "stop the UI server and start it again on 127.0.0.1:8003" in out
    assert "[ok  ] UI server started on 0.37.1" in out


def test_a_server_on_another_host_gets_its_host_again(recorder, homes, on_rc):
    info = {"url": "http://127.0.0.1:8003", "host": "0.0.0.0", "port": 8003, "pid": os.getpid()}
    (homes.lado / "server.json").write_text(json.dumps(info))
    rc.rollback()
    assert recorder.argvs("ui") == [
        [LADO, "ui", "--no-open", "--port", "8003", "--host", "0.0.0.0"]
    ]


def test_a_dead_servers_file_is_no_server(recorder, homes, on_rc, capsys):
    dead = subprocess.Popen([sys.executable, "-c", ""])
    dead.wait()
    info = {"host": "127.0.0.1", "port": 8003, "pid": dead.pid}
    (homes.lado / "server.json").write_text(json.dumps(info))
    rc.rollback()
    assert recorder.argvs("ui") == []
    assert "the UI server does not run" in capsys.readouterr().out


def test_no_copy_is_refused_with_nothing_run(recorder, homes, on_rc, capsys):
    (homes.keep / "lado.db.0.37.1").unlink()
    assert rc.main(["rollback"]) == 1
    err = capsys.readouterr().err
    assert "~/.lado-rc holds no copy of a final's lado.db" in err
    assert "upgrade from a final makes it" in err
    assert "lado update <final>" in err
    assert recorder.verbs() == ["--version"]
    assert on_rc == []


def test_two_copies_are_refused(recorder, homes, on_rc, capsys):
    make_db(homes.keep / "lado.db.0.36.0", 25, [])
    assert rc.main(["rollback"]) == 1
    assert "holds more than one copy" in capsys.readouterr().err
    assert on_rc == []


def test_not_on_an_rc_is_refused(recorder, homes, on_rc, capsys):
    recorder.version("0.37.1")
    assert rc.main(["rollback"]) == 1
    assert "your LADO is 0.37.1, no pre-release: nothing to roll back" in capsys.readouterr().err
    assert recorder.verbs() == ["--version"]


def test_answer_no_changes_nothing(recorder, homes, on_rc, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "")
    assert rc.rollback() == 1
    assert "Not rolled back." in capsys.readouterr().out
    assert "stop --all" not in recorder.verbs()
    assert schema(homes.lado / "lado.db") == 27


def test_without_a_terminal_rollback_refuses(recorder, homes, on_rc, monkeypatch, capsys):
    monkeypatch.setattr(rc, "_terminal", lambda: False)
    assert rc.main(["rollback"]) == 1
    assert "rollback asks first: run it on a terminal" in capsys.readouterr().err
    assert on_rc == [] and "stop --all" not in recorder.verbs()


def test_update_refused_stops_before_the_restore(recorder, homes, on_rc, capsys):
    (homes.lado / "server.json").write_text(
        json.dumps({"host": "127.0.0.1", "port": 8003, "pid": os.getpid()})
    )
    recorder.answer("update", 1)
    assert rc.rollback() == 1
    assert schema(homes.lado / "lado.db") == 27
    assert "start" not in recorder.verbs() and "ui" not in recorder.verbs()
    err = capsys.readouterr().err
    assert "lado update 0.37.1 did not update (exit 1): lado.db is not restored" in err
    assert "lado start /r/app --name app" in err
    assert "lado ui --port 8003" in err
    assert "your sessions are stopped" in err


def test_a_failed_stop_does_not_say_the_sessions_are_stopped(recorder, homes, on_rc, capsys):
    recorder.answer("stop --all", 1)
    assert rc.rollback() == 1
    assert "update" not in recorder.verbs()
    err = capsys.readouterr().err
    assert "lado stop --all exited 1: lado.db is not restored" in err
    assert "your sessions are stopped" not in err
    assert "some of your sessions may be stopped (lado ls)" in err
    assert "lado start /r/app --name app" in err


def test_an_update_to_another_version_stops_before_the_restore(recorder, homes, on_rc, capsys):
    recorder.version("0.38.0rc1", "0.38.0rc1")
    assert rc.rollback() == 1
    assert schema(homes.lado / "lado.db") == 27
    assert "start" not in recorder.verbs()
    assert "lado --version says lado 0.38.0rc1, not 0.37.1" in capsys.readouterr().err


def test_a_failing_resume_goes_on_with_the_others(recorder, homes, on_rc, capsys):
    (homes.lado / "lado.db").unlink()
    make_db(homes.lado / "lado.db", 27, [("app", "/r/gone", None), ("web", "/r/web", None)])
    recorder.alive = {"app", "web"}
    # The first start (app's, by name) fails, the next one works.
    recorder.answers["start"] = [(1, "lado: /r/gone does not exist\n", None), (0, "", None)]
    assert rc.rollback() == 1
    out = capsys.readouterr().out
    assert [argv[2] for argv in recorder.argvs("start")] == ["/r/gone", "/r/web"]
    assert "[FAIL] session app: lado start exited 1" in out
    assert "/r/gone does not exist" in out
    assert "[ok  ] session web started on 0.37.1" in out


def test_the_working_copys_lado_is_refused_for_rollback(monkeypatch, capsys, recorder):
    found = str(ROOT / ".venv" / "bin" / "lado")
    monkeypatch.setattr(rc.shutil, "which", lambda _: found)
    assert rc.main(["rollback"]) == 1
    assert f"lado on PATH is this repository's {found}" in capsys.readouterr().err
    assert recorder.calls == []
