"""scripts/live_ci.py: one cell of the live tests in GitHub Actions (live.yml, the Windows
probe)."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

from lado.providers import kilo, opencode

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "live_ci.py"
LIVE_CONFTEST = ROOT / "tests" / "live" / "conftest.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


live_ci = _load("live_ci", SCRIPT)


def test_the_script_imports_only_the_standard_library():
    """It imports nothing of LADO: the tests compare it with LADO."""
    code = (
        "import sys; sys.path.insert(0, 'scripts'); before = set(sys.modules); "
        "import live_ci; "
        "print('\\n'.join(sorted(m for m in set(sys.modules) - before)))"
    )
    loaded = subprocess.run(
        [sys.executable, "-I", "-c", code], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    stdlib = sys.stdlib_module_names
    assert [m for m in loaded if m.split(".")[0] not in stdlib and m != "live_ci"] == []


# One source of truth for the providers (AC-3, AC-4).


def test_every_live_provider_runs_in_the_cloud_or_only_locally():
    classes = _load("live_conftest", LIVE_CONFTEST).CLASSES
    assert set(classes) == set(live_ci.PINS) | set(live_ci.LOCAL_ONLY)
    assert not set(live_ci.PINS) & set(live_ci.LOCAL_ONLY)


def test_claude_and_codex_run_only_locally_each_with_its_reason():
    assert set(live_ci.PINS) == {"opencode", "kilo"}
    assert set(live_ci.LOCAL_ONLY) == {"claude", "codex"}
    assert all(reason.strip() for reason in live_ci.LOCAL_ONLY.values())


def test_providers_names_the_cloud_providers(capsys):
    """The Windows probe's provider `all`."""
    assert live_ci.main(["providers"]) == 0
    assert capsys.readouterr().out == " ".join(live_ci.PINS) + "\n"


@pytest.mark.parametrize("provider, module", [("opencode", opencode), ("kilo", kilo)])
def test_each_pin_is_its_providers_tested_version(provider, module):
    _, version, _ = live_ci.PINS[provider]
    tested = module.TESTED_VERSION.split(".")
    # Compared by parts: 7.80.1 is no 7.8.
    assert version.split(".")[: len(tested)] == tested


def test_each_pins_command_is_its_providers_cli():
    classes = _load("live_conftest", LIVE_CONFTEST).CLASSES
    for provider, (_, _, command) in live_ci.PINS.items():
        assert command == classes[provider].command


# The pass rule (AC-6).


@pytest.mark.parametrize(
    "summary, code, passed",
    [
        ("============ 3 passed in 412.20s (0:06:52) ============", 0, True),
        ("====== 2 passed, 1 skipped in 300.00s (0:05:00) ======", 0, False),
        ("====== 3 skipped in 1.00s ======", 0, False),
        ("====== 3 deselected in 1.00s ======", 0, False),
        ("====== 1 failed, 2 passed in 600.00s ======", 1, False),
        ("============ 3 passed in 412.20s ============", 1, False),
        ("", 0, False),
    ],
)
def test_a_cell_passes_only_when_a_test_passed_none_skipped_and_pytest_exited_0(
    summary, code, passed
):
    assert live_ci.passed(summary, code) is passed


def test_the_summary_is_pytests_last_summary_line():
    log = (
        "tests/live/test_live.py::test_x[opencode] PASSED\n"
        "=========== short test summary info ===========\n"
        "========= 1 failed, 2 passed in 10.00s =========\n"
        "trailing noise\n"
    )
    assert live_ci.summary(log) == "========= 1 failed, 2 passed in 10.00s ========="
    assert live_ci.summary("no summary\n") == ""


# A cell's run, with npm, the CLI and uv stubbed on PATH.

NPM = """#!/bin/sh
printf 'npm %s\\n' "$*" >>"$CELL_RAN"
[ -n "$NPM_FAILS" ] && exit 1
mkdir -p "$HOME/.local/bin"
for cli in opencode kilo; do
  printf '#!/bin/sh\\necho %s 9.9.9\\n' "$cli" >"$HOME/.local/bin/$cli"
  chmod +x "$HOME/.local/bin/$cli"
done
"""
# uv stands in for `uv run pytest ...`: it records its argv, writes evidence as a failing
# live test would, prints the summary and exits with its code.
UV = """#!/bin/sh
printf 'uv %s\\n' "$*" >>"$CELL_RAN"
command -v opencode >>"$CELL_RAN"
if [ -n "$EVIDENCE_WRITES" ]; then
  mkdir -p "$TMPDIR/lado-live-evidence/20261010-test_w"
  echo "w1 never reported" >"$TMPDIR/lado-live-evidence/20261010-test_w/lado-log.txt"
fi
printf 'tests/live/test_live.py::t PASSED\\n%s\\n' "$SUMMARY"
exit "${CODE:-0}"
"""
PASSED = "============ 3 passed in 412.20s (0:06:52) ============"


def run_cell(tmp_path, provider, **env):
    """Run `live_ci.py run <provider> <out>` with the stubs: its process, out and the log of
    what it ran."""
    stubs = tmp_path / "stubs"
    stubs.mkdir(exist_ok=True)
    for name, text in (("npm", NPM), ("uv", UV)):
        (stubs / name).write_text(text)
        (stubs / name).chmod(0o755)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    temp = tmp_path / "tmp"
    temp.mkdir(exist_ok=True)
    out = tmp_path / "out"
    full = {
        "PATH": f"{stubs}{os.pathsep}/usr/bin:/bin",
        "HOME": str(home),
        "TMPDIR": str(temp),
        "CELL_RAN": str(tmp_path / "ran"),
        "SUMMARY": PASSED,
        **env,
    }
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "run", provider, str(out)],
        env=full,
        capture_output=True,
        text=True,
        timeout=60,
    )
    ran = tmp_path / "ran"
    return done, out, ran.read_text() if ran.exists() else ""


def test_a_cell_installs_the_pinned_cli_then_runs_its_live_tests(tmp_path):
    done, out, ran = run_cell(tmp_path, "opencode")
    assert done.returncode == 0, done.stdout + done.stderr
    package, version, _ = live_ci.PINS["opencode"]
    home = tmp_path / "home"
    assert f"npm install -g --prefix {home}/.local {package}@{version}\n" in ran
    # As `make test-live PROVIDER=opencode`, nothing deselected.
    assert "uv run pytest -m live -n0 -v -k opencode\n" in ran
    # The installed CLI is first on PATH for the tests.
    assert f"{home}/.local/bin/opencode\n" in ran
    assert "opencode 9.9.9" in done.stdout
    # The output goes to the terminal and to the cell's log.
    assert PASSED in done.stdout
    assert PASSED in (out / "live-opencode.log").read_text()
    assert not (out / "evidence").exists()


def test_a_cell_whose_install_fails_is_red_and_runs_no_test(tmp_path):
    done, _, ran = run_cell(tmp_path, "kilo", NPM_FAILS="1")
    assert done.returncode != 0
    assert "uv run" not in ran


@pytest.mark.parametrize(
    "summary, code", [("====== 2 passed, 1 skipped in 3.00s ======", "0"), (PASSED, "1")]
)
def test_a_cell_is_red_unless_the_pass_rule_holds(tmp_path, summary, code):
    done, _, _ = run_cell(tmp_path, "kilo", SUMMARY=summary, CODE=code)
    assert done.returncode != 0


def test_a_failing_cell_keeps_its_evidence_in_out(tmp_path):
    done, out, _ = run_cell(
        tmp_path, "opencode", SUMMARY="=== 1 failed in 3.00s ===", CODE="1", EVIDENCE_WRITES="1"
    )
    assert done.returncode != 0
    kept = out / "evidence" / "20261010-test_w" / "lado-log.txt"
    assert kept.read_text() == "w1 never reported\n"


def test_evidence_of_an_earlier_run_is_cleared_first(tmp_path):
    stale = tmp_path / "tmp" / "lado-live-evidence" / "old"
    stale.mkdir(parents=True)
    done, out, _ = run_cell(tmp_path, "opencode", SUMMARY="=== 1 failed in 3.00s ===", CODE="1")
    assert done.returncode != 0
    assert not (out / "evidence" / "old").exists()


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_a_local_only_provider_is_refused_with_its_reason(tmp_path, provider):
    done, _, ran = run_cell(tmp_path, provider)
    assert done.returncode != 0
    assert f"{provider}: {live_ci.LOCAL_ONLY[provider]}" in done.stderr
    assert ran == ""


def test_an_unknown_provider_is_refused(tmp_path):
    done, _, ran = run_cell(tmp_path, "gemini")
    assert done.returncode != 0 and "gemini: no cloud provider" in done.stderr
    assert ran == ""
