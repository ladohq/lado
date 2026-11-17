"""docker/install.ps1, the Windows front of the Docker installer (openspec capability
docker-installer): it gets Windows to Ubuntu in WSL with Docker and runs its release's
install.sh there. CI has no Windows with Linux containers, so these tests read its text and,
where `pwsh` is on PATH, parse it; its behaviour is checked by hand on a real Windows
before a release (docs/release.md)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "docker" / "install.ps1"
TEXT = SCRIPT.read_text(encoding="utf-8") if SCRIPT.exists() else ""
ARROW = "\u2192"


def code() -> str:
    """The script without its comments and the contents of its strings, so a test of its
    syntax sees only code."""
    text = re.sub(r"<#.*?#>", "", TEXT, flags=re.S)
    text = re.sub(r"'[^'\n]*'", "''", text)
    text = re.sub(r'"(?:`.|[^"`\n])*"', '""', text)
    return "\n".join(line.split("#")[0] for line in text.splitlines())


def said(text: str) -> str:
    """`text` with `$Arrow` written as the arrow it stands for."""
    return text.replace("$Arrow", ARROW)


def test_it_never_calls_exit_under_iex():
    """`exit` under `irm | iex` would close the human's PowerShell window: only a file run
    (PSCommandPath) exits with the code."""
    exits = [line.strip() for line in code().splitlines() if re.search(r"\bexit\b", line)]
    assert exits == ["if ($PSCommandPath) { exit $State.ExitCode }"]


def test_it_uses_no_script_root():
    assert "$PSScriptRoot" not in TEXT


def test_the_text_is_ascii():
    """Windows PowerShell 5.1 reads a file without a BOM, and irm a release asset, in the
    system's code page: a non-ASCII character would come out garbled."""
    assert TEXT and TEXT.isascii()


def test_no_powershell_7_only_syntax():
    found = code()
    for token in ("?.", "??", "&&", "||", "?[", "-Parallel", "Clean {"):
        assert token not in found, token
    assert not re.search(r"\s\?\s.*\s:\s", found), "ternary"


def test_it_stops_on_errors_and_strict_mode():
    assert "Set-StrictMode -Version 2.0" in TEXT
    assert "$ErrorActionPreference = 'Stop'" in TEXT


needs_pwsh = pytest.mark.skipif(shutil.which("pwsh") is None, reason="pwsh is not on PATH")


def pwsh(command: str, *args: str) -> subprocess.CompletedProcess:
    """`command` in pwsh with a PATH of pwsh alone: no docker, no wsl.exe, as on a Windows
    without Docker Desktop."""
    env = {**os.environ, "PATH": str(Path(shutil.which("pwsh")).resolve().parent)}
    return subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", *args, "-Command", command],
        capture_output=True, text=True, timeout=120, env=env,
    )  # fmt: skip


def stamped(tmp_path: Path) -> Path:
    stamp = ROOT / "scripts" / "stamp_installers.py"
    subprocess.run([sys.executable, str(stamp), "0.44.0", str(tmp_path)], check=True)
    return tmp_path / "install.ps1"


@needs_pwsh
def test_iex_leaves_the_humans_powershell_as_it_was():
    """`irm | iex` runs the text in the caller's own scope: its strict mode, its 'Stop'
    and its functions would stay in the human's window after the install."""
    done = pwsh(
        f"Get-Content -Raw '{SCRIPT}' | Invoke-Expression; "
        "'EAP=' + $ErrorActionPreference; $x = $undefinedVar; 'STRICT=off'; "
        "'FUNCTIONS=' + [bool](Get-Command Install-Lado -ErrorAction SilentlyContinue); "
        "'VARIABLES=' + [bool](Get-Variable LadoVersion -ErrorAction SilentlyContinue)"
    )
    out = done.stdout
    assert "this install.ps1 carries no version" in out, out + done.stderr
    assert "EAP=Continue" in out and "STRICT=off" in out, out + done.stderr
    assert "FUNCTIONS=False" in out and "VARIABLES=False" in out, out
    assert "LASTEXITCODE" not in done.stderr


@needs_pwsh
def test_the_scriptblock_form_takes_the_switches(tmp_path):
    script = stamped(tmp_path)
    done = pwsh(
        f"& ([scriptblock]::Create((Get-Content -Raw '{script}'))) -Yes; 'CODE=' + $LASTEXITCODE"
    )
    assert "lado install: Docker Desktop is not installed" in done.stdout, done.stdout + done.stderr
    assert "CODE=1" in done.stdout


# A fake Windows: docker, wsl.exe and Docker Desktop.exe as Python scripts on PATH (and
# under ProgramFiles), each set by the environment. Each wsl.exe call but the two it answers
# itself goes to LOG, and prints a line, which the human's console must show.
FAKE_DOCKER = r"""
import os, sys
# FAKE_DOCKER=down: `docker info` fails until Docker Desktop.exe has run.
if os.environ.get("FAKE_DOCKER") == "down" and not os.path.exists(STARTED):
    sys.exit(1)
"""
FAKE_DESKTOP = r"""
open(STARTED, "w").close()
"""
FAKE_WSL = r"""
import json, os, sys
args = sys.argv[1:]
if args == ["-l", "-q"]:  # as WSL answers: UTF-16, Docker Desktop's own first
    names = os.environ.get("FAKE_DISTROS", "docker-desktop,Ubuntu-24.04").split(",")
    sys.stdout.buffer.write("".join(n + "\r\n" for n in names).encode("utf-16-le"))
elif "docker" in args:  # Docker in the distribution, as Desktop's WSL integration gives it
    if os.environ.get("FAKE_INTEGRATION") == "off":
        sys.exit(1)
    print("27.0.0")
else:
    with open(LOG, "a") as log:
        log.write(json.dumps(args) + "\n")
    print("install.sh speaks")
"""


def on_fake_windows(
    tmp_path: Path,
    *switches: str,
    wsl: bool = True,
    docker: bool = True,
    desktop: bool = False,
    answer: str | None = None,
    **env: str,
) -> tuple[subprocess.CompletedProcess, list[list[str]]]:
    """The stamped script run with `switches` on a fake Windows (without wsl.exe, docker or
    Docker Desktop.exe where those are False): its run and the wsl.exe calls LOG got.
    `answer` is typed in at its question; without one it runs -NonInteractive."""
    script, fakes, log = stamped(tmp_path), tmp_path / "fakes", tmp_path / "wsl.jsonl"
    programs = tmp_path / "Program Files"
    started = tmp_path / "desktop-started"
    fakes.mkdir()
    exe = programs / "Docker" / "Docker" / "Docker Desktop.exe"
    wanted = [(fakes / "docker", FAKE_DOCKER, docker), (fakes / "wsl.exe", FAKE_WSL, wsl)]
    for path, body, made in [*wanted, (exe, FAKE_DESKTOP, desktop)]:
        if made:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                f"#!{sys.executable}\nLOG = {str(log)!r}\nSTARTED = {str(started)!r}\n{body}"
            )
            path.chmod(0o755)
    path = f"{Path(shutil.which('pwsh')).resolve().parent}{os.pathsep}{fakes}"
    mode = [] if answer is not None else ["-NonInteractive"]
    done = subprocess.run(
        ["pwsh", "-NoProfile", *mode, "-Command",
         f"& ([scriptblock]::Create((Get-Content -Raw '{script}'))) {' '.join(switches)}"],
        capture_output=True, text=True, timeout=120, input=answer,
        env={**os.environ, "PATH": path, "ProgramFiles": str(programs), **env},
    )  # fmt: skip
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return done, calls


URL = "https://github.com/ladohq/lado/releases/download/v0.44.0/install.sh"


@needs_pwsh
@pytest.mark.parametrize(
    ("switches", "flags"),
    [(("-Yes", "-Phone"), "--yes --phone"), (("-NoPhone",), "--no-phone")],
)
def test_it_runs_its_install_sh_in_ubuntu_with_the_switches(tmp_path, switches, flags):
    """Ubuntu is taken, never docker-desktop (listed first, in UTF-16), and install.sh of
    its version runs there with the switches' flags, its output on the human's console."""
    done, calls = on_fake_windows(tmp_path, *switches)
    assert "Installing LADO 0.44.0 in Ubuntu-24.04" in done.stdout, done.stdout + done.stderr
    assert calls == [
        ["-d", "Ubuntu-24.04", "--cd", "~", "--", "sh", "-c",
         f"curl -fsSL '{URL}' | sh -s -- {flags}"],
    ]  # fmt: skip
    assert "install.sh speaks" in done.stdout


@needs_pwsh
def test_a_stopped_docker_desktop_is_started_and_waited_for(tmp_path):
    done, calls = on_fake_windows(tmp_path, "-Yes", desktop=True, FAKE_DOCKER="down")
    assert "Waiting for Docker Desktop to start" in done.stdout, done.stdout + done.stderr
    assert "Installing LADO 0.44.0 in Ubuntu-24.04" in done.stdout
    assert len(calls) == 1


DESKTOP = "https://www.docker.com/products/docker-desktop/"
INTEGRATION = f"Settings {ARROW} Resources {ARROW} WSL integration for Ubuntu-24.04"


@needs_pwsh
@pytest.mark.parametrize(
    ("windows", "said"),
    [
        ({"docker": False}, f"Docker Desktop is not installed: get it from {DESKTOP}"),
        ({"FAKE_DOCKER": "down"}, "Docker does not answer and Docker Desktop is not found"),
        ({"wsl": False}, "WSL is missing, and Docker Desktop needs WSL 2"),
        ({"FAKE_DISTROS": "docker-desktop"}, "install it (wsl --install -d Ubuntu)"),
        ({"FAKE_INTEGRATION": "off"}, f"in Docker Desktop turn on {INTEGRATION}"),
    ],
    ids=["no docker", "no desktop", "no wsl", "no ubuntu", "no integration"],
)
def test_a_stop_names_its_next_step_and_installs_nothing(tmp_path, windows, said):
    """With -Yes nothing is asked: Ubuntu is not installed either."""
    done, calls = on_fake_windows(tmp_path, "-Yes", **windows)
    assert "lado install: " in done.stdout and said in done.stdout, done.stdout + done.stderr
    assert calls == []


@needs_pwsh
def test_a_yes_to_its_question_installs_ubuntu_and_says_to_run_it_again(tmp_path):
    done, calls = on_fake_windows(tmp_path, answer="y\n", FAKE_DISTROS="docker-desktop")
    assert "LADO runs in Ubuntu inside WSL" in done.stdout, done.stdout + done.stderr
    assert calls == [["--install", "-d", "Ubuntu"]]
    said = " ".join(done.stdout.split())
    assert "open Ubuntu from the Start menu once, make its user, then run the same command" in said
    assert "irm https://github.com/ladohq/lado/releases/latest/download/install.ps1 | iex" in said


@needs_pwsh
def test_a_file_run_exits_with_the_code(tmp_path):
    script = stamped(tmp_path)
    env = {**os.environ, "PATH": str(Path(shutil.which("pwsh")).resolve().parent)}
    done = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(script), "-Yes"],
        capture_output=True, text=True, timeout=120, env=env,
    )  # fmt: skip
    assert done.returncode == 1, done.stdout + done.stderr
    assert "Docker Desktop is not installed" in done.stdout


@needs_pwsh
def test_it_parses():
    check = (
        "$errors = $null; $null = [System.Management.Automation.Language.Parser]::ParseFile("
        f"'{SCRIPT}', [ref]$null, [ref]$errors); $errors | ForEach-Object {{ $_.ToString() }}; "
        "exit $errors.Count"
    )
    done = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-Command", check],
        capture_output=True, text=True, timeout=120,
    )  # fmt: skip
    assert done.returncode == 0, done.stdout + done.stderr
