"""scripts/live_ci.py: one cell of the live tests in GitHub Actions (live.yml, the Windows
probe), and the scrub before every upload."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from lado.providers import claude, kilo, opencode

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "live_ci.py"
LIVE_CONFTEST = ROOT / "tests" / "live" / "conftest.py"
TOKEN = "sk-ant-oat01-secret-of-the-test"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


live_ci = _load("live_ci", SCRIPT)


def test_the_script_imports_only_the_standard_library():
    """On the Windows host it runs with `uv run --no-project`: no LADO, no dependency."""
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
    assert set(classes) == set(live_ci.PINS) | live_ci.LOCAL_ONLY
    assert not set(live_ci.PINS) & live_ci.LOCAL_ONLY
    assert live_ci.LOCAL_ONLY == {"codex"}


def test_providers_names_the_cloud_providers(capsys):
    """The Windows probe's provider `all`."""
    assert live_ci.main(["providers"], {}) == 0
    assert capsys.readouterr().out == " ".join(live_ci.PINS) + "\n"


@pytest.mark.parametrize(
    "provider, module", [("opencode", opencode), ("kilo", kilo), ("claude", claude)]
)
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


# The scrub before every upload (AC-7).


def test_scrub_deletes_every_file_that_holds_the_token_and_names_it(tmp_path, capsys):
    out = tmp_path / "out"
    (out / "evidence" / "deep" / "er").mkdir(parents=True)
    (out / "live-claude.log").write_text(f"env: CLAUDE_CODE_OAUTH_TOKEN={TOKEN}\n")
    (out / "evidence" / "deep" / "er" / "env.json").write_text(json.dumps({"t": TOKEN}))
    (out / "evidence" / "screen.bin").write_bytes(b"\x00\xff" + TOKEN.encode() + b"\x00")
    (out / "evidence" / "clean.txt").write_text("nothing here\n")
    assert live_ci.main(["scrub", str(out)], {"LADO_LIVE_CLAUDE_TOKEN": TOKEN}) == 0
    left = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    assert left == ["evidence/clean.txt"]
    printed = capsys.readouterr()
    assert TOKEN not in printed.out + printed.err
    for name in ("live-claude.log", "evidence/deep/er/env.json", "evidence/screen.bin"):
        assert f"{name}: held the token" in printed.out


def test_scrub_without_a_token_deletes_nothing(tmp_path):
    (tmp_path / "a.log").write_text("anything\n")
    assert live_ci.main(["scrub", str(tmp_path)], {}) == 0
    assert (tmp_path / "a.log").exists()


def test_scrub_of_a_missing_folder_fails(tmp_path, capsys):
    assert live_ci.main(["scrub", str(tmp_path / "gone")], {"LADO_LIVE_CLAUDE_TOKEN": TOKEN}) != 0
    assert "scrub:" in capsys.readouterr().err


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def test_scrub_fails_closed_on_a_file_it_cannot_read(tmp_path, capsys):
    locked = tmp_path / "locked.log"
    locked.write_text(TOKEN)
    locked.chmod(0)
    try:
        assert live_ci.main(["scrub", str(tmp_path)], {"LADO_LIVE_CLAUDE_TOKEN": TOKEN}) != 0
    finally:
        locked.chmod(0o600)
    printed = capsys.readouterr()
    assert "locked.log" in printed.err and TOKEN not in printed.out + printed.err


@pytest.mark.skipif(os.geteuid() == 0, reason="root walks any folder")
def test_scrub_fails_closed_on_a_folder_it_cannot_walk(tmp_path):
    shut = tmp_path / "shut"
    shut.mkdir()
    (shut / "a.log").write_text(TOKEN)
    shut.chmod(0)
    try:
        assert live_ci.main(["scrub", str(tmp_path)], {"LADO_LIVE_CLAUDE_TOKEN": TOKEN}) != 0
    finally:
        shut.chmod(0o700)


# The onboarding seed of a fresh CI home.


def test_onboarding_is_seeded_in_a_fresh_home(tmp_path):
    live_ci.seed_onboarding(tmp_path)
    assert json.loads((tmp_path / ".claude.json").read_text()) == {"hasCompletedOnboarding": True}


def test_onboarding_keeps_what_the_config_has(tmp_path):
    config = tmp_path / ".claude.json"
    config.write_text(json.dumps({"projects": {"/x": {}}}))
    live_ci.seed_onboarding(tmp_path)
    assert json.loads(config.read_text()) == {
        "projects": {"/x": {}},
        "hasCompletedOnboarding": True,
    }


def test_onboarding_never_changes_a_config_that_has_the_key(tmp_path):
    config = tmp_path / ".claude.json"
    config.write_text('{"hasCompletedOnboarding": false}')
    live_ci.seed_onboarding(tmp_path)
    assert config.read_text() == '{"hasCompletedOnboarding": false}'


# A cell's run, with npm, the CLI and uv stubbed on PATH.

NPM = """#!/bin/sh
printf 'npm %s\\n' "$*" >>"$CELL_RAN"
[ -n "$NPM_FAILS" ] && exit 1
mkdir -p "$HOME/.local/bin"
for cli in opencode kilo claude; do
  printf '#!/bin/sh\\necho %s 9.9.9\\n' "$cli" >"$HOME/.local/bin/$cli"
  chmod +x "$HOME/.local/bin/$cli"
done
"""
# uv stands in for `uv run pytest ...`: it records its argv and the tokens it sees, writes
# evidence as a failing live test would, prints the summary and exits with its code.
UV = """#!/bin/sh
printf 'uv %s\\n' "$*" >>"$CELL_RAN"
printf 'oauth=%s lado=%s\\n' \\
  "${CLAUDE_CODE_OAUTH_TOKEN:-}" "${LADO_LIVE_CLAUDE_TOKEN:-}" >>"$CELL_RAN"
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


def test_a_claude_cell_without_the_token_is_red_and_says_so(tmp_path):
    for token in ({}, {"LADO_LIVE_CLAUDE_TOKEN": ""}):
        done, _, ran = run_cell(tmp_path, "claude", **token)
        assert done.returncode != 0
        assert "LADO_LIVE_CLAUDE_TOKEN is not set: add the repository secret" in done.stderr
        assert "uv run" not in ran


def test_a_claude_cell_hands_the_token_to_the_tests_and_never_prints_it(tmp_path):
    done, _, ran = run_cell(tmp_path, "claude", LADO_LIVE_CLAUDE_TOKEN=TOKEN)
    assert done.returncode == 0, done.stdout + done.stderr
    # As Claude Code's OAuth token; LADO's own name of it stays out of the tests.
    assert f"oauth={TOKEN} lado=\n" in ran
    assert TOKEN not in done.stdout + done.stderr
    assert TOKEN not in [line for line in ran.splitlines() if line.startswith(("npm", "uv"))]
    config = json.loads((tmp_path / "home" / ".claude.json").read_text())
    assert config["hasCompletedOnboarding"] is True


def test_another_cell_gets_no_claude_token(tmp_path):
    done, _, ran = run_cell(tmp_path, "opencode", LADO_LIVE_CLAUDE_TOKEN=TOKEN)
    assert done.returncode == 0
    assert "oauth= lado=\n" in ran
    assert not (tmp_path / "home" / ".claude.json").exists()


def test_an_unknown_provider_is_refused(tmp_path):
    done, _, ran = run_cell(tmp_path, "codex")
    assert done.returncode != 0 and "codex" in done.stderr
    assert ran == ""
