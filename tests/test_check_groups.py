"""scripts/check_groups.py: make check's test groups, one after another (Makefile)."""

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "check_groups.py"


def exits(code: int, mark: Path) -> list[str]:
    """A command that appends its mark's name to `mark`'s log, then exits with `code`."""
    program = (
        f"open({str(mark.parent / 'ran')!r}, 'a').write({mark.name!r} + '\\n'); "
        f"raise SystemExit({code})"
    )
    return [sys.executable, "-c", program]


def run_script(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *argv], capture_output=True, text=True, timeout=30
    )


def run_groups(tmp_path, *groups: tuple[str, int]) -> subprocess.CompletedProcess:
    argv = []
    for name, code in groups:
        argv += ["--group", name, *exits(code, tmp_path / name)]
    return run_script(*argv)


def ran(tmp_path) -> list[str]:
    log = tmp_path / "ran"
    return log.read_text().splitlines() if log.exists() else []


def test_every_group_runs_in_order_and_all_passing_is_success(tmp_path):
    result = run_groups(tmp_path, ("unit", 0), ("integration", 0), ("ui", 0))

    assert result.returncode == 0, result.stdout + result.stderr
    assert ran(tmp_path) == ["unit", "integration", "ui"]
    assert result.stdout.splitlines()[-1] == "check: passed: unit, integration, ui"


def test_a_failing_group_does_not_stop_the_next_and_fails_at_the_end(tmp_path):
    result = run_groups(tmp_path, ("unit", 0), ("integration", 1), ("ui", 2))

    assert result.returncode == 1
    assert ran(tmp_path) == ["unit", "integration", "ui"]
    assert result.stdout.splitlines()[-1] == "check: failed: integration, ui"


def test_a_group_that_collects_no_tests_is_no_failure(tmp_path):
    result = run_groups(tmp_path, ("unit", 0), ("integration", 5), ("ui", 5))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "check: integration collected no tests" in result.stdout
    assert result.stdout.splitlines()[-1] == "check: passed: unit, integration, ui"


def test_each_group_says_how_it_ended_and_how_long_it_took(tmp_path):
    result = run_groups(tmp_path, ("unit", 0), ("integration", 3))

    lines = result.stdout.splitlines()
    assert any(line.startswith("check: unit passed in ") for line in lines)
    assert any(line.startswith("check: integration failed (exit 3) in ") for line in lines)


def test_a_command_that_cannot_start_fails_its_group_and_the_next_still_run(tmp_path):
    missing = str(tmp_path / "no-such-command")
    result = run_script("--group", "unit", missing, "--group", "ui", *exits(0, tmp_path / "ui"))

    assert result.returncode == 1
    assert ran(tmp_path) == ["ui"]
    assert "check: unit failed (cannot run " in result.stdout
    assert "Traceback" not in result.stderr
    assert result.stdout.splitlines()[-1] == "check: failed: unit"


@pytest.mark.parametrize(
    "pytest_args, expected",
    [
        ("-n0 -k gate", ["-n0", "-k", "gate"]),
        ('-n0 -k "gate or flow"', ["-n0", "-k", "gate or flow"]),
        ("-n0 -k 'gate or flow'", ["-n0", "-k", "gate or flow"]),
    ],
)
def test_make_check_runs_unit_integration_and_ui_with_pytest_args(pytest_args, expected):
    """`make -n` prints _check's commands without running them; the shell parses them."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("MAKE")}
    result = subprocess.run(
        ["make", "-n", "--no-print-directory", "_check", f"PYTEST_ARGS={pytest_args}"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    commands = result.stdout.replace("\\\n", " ").splitlines()
    groups = [line for line in commands if "check_groups.py" in line]
    assert len(groups) == 1, result.stdout
    argv = shlex.split(groups[0])
    start = argv.index("scripts/check_groups.py") + 1
    assert argv[start:] == [
        *["--group", "unit", "uv", "run", "pytest", *expected],
        *["--group", "integration", "uv", "run", "pytest", "-m", "integration", *expected],
        *["--group", "ui", "uv", "run", "pytest", "-m", "ui", *expected],
    ]
    assert "pytest -m 'not live'" not in result.stdout
