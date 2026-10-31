"""docker/install.ps1, the Windows front of the Docker installer (openspec capability
docker-installer): it gets Windows to Ubuntu in WSL with Docker and runs its release's
install.sh there. CI has no Windows with Linux containers, so these tests read its text and,
where `pwsh` is on PATH, parse it; its behaviour is checked by hand on a real Windows
before a release (docs/release.md)."""

from __future__ import annotations

import re
import shutil
import subprocess
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


def test_the_stamp_and_the_versions_install_sh():
    assert re.findall(r"(?m)^\$LadoVersion = .*$", TEXT) == ["$LadoVersion = ''"]
    assert (
        '"https://github.com/ladohq/lado/releases/download/v$LadoVersion/install.sh"' in TEXT
    )


def test_an_unstamped_copy_refuses():
    assert "if (-not $LadoVersion)" in TEXT
    assert (
        "this install.ps1 carries no version: take the release's "
        "(https://github.com/ladohq/lado/releases/latest/download/install.ps1)"
    ) in TEXT


def test_the_switches_map_to_the_flags():
    assert re.search(r"param\(\s*\[switch\]\$Yes,\s*\[switch\]\$Phone,\s*\[switch\]\$NoPhone", TEXT)
    for switch, flag in (("Yes", "--yes"), ("Phone", "--phone"), ("NoPhone", "--no-phone")):
        assert f"if (${switch}) {{ $Flags += '{flag}' }}" in TEXT


def test_install_sh_runs_in_the_distribution_with_its_terminal():
    """Not captured or piped, so install.sh's questions reach the human's console."""
    assert "& wsl.exe -d $Distro --cd '~' -- sh -c $Line" in TEXT
    assert "$Line = \"curl -fsSL '$Url' | sh -s -- $($Flags -join ' ')\"" in TEXT


def test_it_never_calls_exit_under_iex():
    """`exit` under `irm | iex` would close the human's PowerShell window: only a file run
    (PSCommandPath) exits with the code."""
    exits = [line.strip() for line in code().splitlines() if re.search(r"\bexit\b", line)]
    assert exits == ["if ($PSCommandPath) { exit $script:ExitCode }"]


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


def test_no_docker_names_docker_desktop():
    assert "Get-Command docker -ErrorAction SilentlyContinue" in TEXT
    assert "https://www.docker.com/products/docker-desktop/" in TEXT
    assert "Docker Desktop is not installed" in TEXT


def test_a_stopped_docker_desktop_is_started_and_waited_for():
    assert "Docker\\Docker\\Docker Desktop.exe" in TEXT
    assert "Start-Process $Exe" in TEXT
    assert "AddSeconds(120)" in TEXT


def test_ubuntu_is_found_and_docker_desktop_skipped():
    assert "[System.Text.Encoding]::Unicode" in TEXT  # wsl -l -q answers in UTF-16
    assert "-replace \"`0\", ''" in TEXT
    assert "$_ -notlike 'docker-desktop*' -and $_ -like 'Ubuntu*'" in TEXT


def test_no_ubuntu_offers_wsl_install_and_a_rerun():
    assert "LADO runs in Ubuntu inside WSL" in TEXT
    assert "Read-Host 'Install Ubuntu now? [y/N]'" in TEXT
    assert "& wsl.exe --install -d Ubuntu" in TEXT
    assert "administrator" in TEXT and "restart" in TEXT
    assert "open Ubuntu from the Start menu once, make its user, then run the same command" in TEXT


def test_no_wsl_says_docker_desktop_needs_wsl2():
    assert "Docker Desktop needs WSL 2" in TEXT


def test_no_integration_names_the_setting():
    assert "Settings $Arrow Resources $Arrow WSL integration" in TEXT
    assert said("Settings $Arrow Resources $Arrow WSL integration") == (
        f"Settings {ARROW} Resources {ARROW} WSL integration"
    )
    assert "$Arrow = [char]0x2192" in TEXT
    assert "'docker', 'version', '--format', '{{.Server.Version}}'" in TEXT


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="pwsh is not on PATH")
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
