""".github/workflows/windows-shell.yml: the Windows (+ WSL2) probe, started by hand."""

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from lado.providers import kilo, opencode

ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "windows-shell.yml"
# A boolean input as GitHub's web form gives it (a boolean) or the API (a string).
WSL = "inputs.wsl == true || inputs.wsl == 'true'"
TESTS = "inputs.tests == true || inputs.tests == 'true'"
LIVE = "inputs.live == true || inputs.live == 'true'"


@pytest.fixture(scope="module")
def text() -> str:
    return WORKFLOW.read_text()


@pytest.fixture(scope="module")
def workflow(text) -> dict:
    return yaml.safe_load(text)


@pytest.fixture(scope="module")
def steps(workflow) -> list[dict]:
    (job,) = workflow["jobs"].values()
    return job["steps"]


def step_using(steps, action: str) -> dict:
    (step,) = [s for s in steps if s.get("uses", "").startswith(action + "@")]
    return step


def step_named(steps, name: str) -> dict:
    (step,) = [s for s in steps if s.get("name") == name]
    return step


def test_started_only_by_hand(workflow):
    # PyYAML reads the key `on` as True.
    triggers = workflow[True]
    assert list(triggers) == ["workflow_dispatch"]


def test_inputs(workflow):
    inputs = workflow[True]["workflow_dispatch"]["inputs"]
    assert inputs["runner"]["type"] == "choice"
    assert inputs["runner"]["options"] == ["windows-latest", "windows-11-arm"]
    assert inputs["runner"]["default"] == "windows-latest"
    assert inputs["wsl"]["type"] == "boolean"
    assert inputs["wsl"]["default"] is True
    assert inputs["tests"]["type"] == "boolean"
    assert inputs["tests"]["default"] is True
    assert inputs["live"]["type"] == "boolean"
    assert inputs["live"]["default"] is False
    assert inputs["minutes"]["type"] == "number"
    assert inputs["minutes"]["default"] == 120
    assert list(inputs) == ["runner", "wsl", "tests", "live", "minutes"]


def test_job_runs_on_the_chosen_runner_for_the_chosen_minutes(workflow, steps):
    (job,) = workflow["jobs"].values()
    assert job["runs-on"] == "${{ inputs.runner }}"
    # Started through the API (gh workflow run -f minutes=120), the input is the string
    # '120', which timeout-minutes refuses; fromJSON makes it a number either way.
    assert job["timeout-minutes"] == "${{ fromJSON(inputs.minutes) }}"
    # The steps without a shell are PowerShell, also to actionlint.
    assert job["defaults"] == {"run": {"shell": "pwsh"}}
    guard = step_named(steps, "Check the length")
    assert "-lt 1" in guard["run"] and "-gt 360" in guard["run"]
    assert steps.index(guard) == 1


def test_report_folder_first_so_the_report_steps_work_after_a_guard(steps):
    folder = steps[0]
    assert folder["name"] == "Report folder" and "if" not in folder
    assert "PROBE=" in folder["run"] and "GITHUB_ENV" in folder["run"]


@pytest.mark.parametrize("name, condition", [("wsl", WSL), ("live", LIVE)])
def test_boolean_inputs_compared_as_a_boolean_or_a_string(steps, name, condition):
    # From the API (gh workflow run -f wsl=false) the input may be the string 'false',
    # which a bare `if: inputs.wsl` takes as true.
    conditions = [s["if"] for s in steps if f"inputs.{name}" in s.get("if", "")]
    assert conditions
    for line in conditions:
        assert f"inputs.{name}" not in line.replace(condition, ""), line


def test_reads_contents_only(workflow):
    assert workflow["permissions"] == {"contents": "read"}
    for job in workflow["jobs"].values():
        assert "permissions" not in job


def test_actions_pinned_to_a_commit_with_its_version(text):
    uses = re.findall(r"uses:\s*(\S+)(.*)", text)
    assert uses
    for action, rest in uses:
        if action.startswith("actions/checkout@"):
            continue
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", action), action
        assert re.fullmatch(r"\s*# v\d+(\.\d+)*", rest), (action, rest)


def test_no_shell(text, steps):
    """No SSH shell into the runner: action-tmate hung on Windows (run 38001793230), and
    every *.tmate.io name is NXDOMAIN since (runs 38006655138, 38007048750)."""
    for word in ("tmate", "upterm", ".keys", "~/continue", "inputs.shell", "msys64"):
        assert word not in text.lower(), word
    assert not [s for s in steps if "shell" in s.get("name", "").lower()]


def test_wsl2_ubuntu_with_the_tools(steps):
    step = step_using(steps, "Vampire/setup-wsl")
    assert step["if"] == WSL
    assert step["with"]["distribution"] == "Ubuntu-24.04"
    assert str(step["with"]["wsl-version"]) == "2"
    packages = step["with"]["additional-packages"].split()
    assert {"tmux", "git", "curl", "build-essential", "less"} <= set(packages)
    # xz-utils only unpacked a tmate release.
    assert "xz-utils" not in packages
    assert all("continue-on-error" not in s for s in steps)


def test_wsl_on_arm_fails_before_setup(steps):
    """setup-wsl's Ubuntu 24.04 is an amd64 image: no silent WSL1 fallback on ARM."""
    setup = steps.index(step_using(steps, "Vampire/setup-wsl"))
    guards = [
        i
        for i, s in enumerate(steps)
        if "windows-11-arm" in s.get("if", "")
        and "inputs.wsl" in s.get("if", "")
        and "exit 1" in s.get("run", "")
    ]
    assert guards and guards[0] < setup


def test_live_without_wsl_fails_before_setup(steps):
    guard = step_named(steps, "No live agents without WSL")
    assert guard["if"] == f"({LIVE}) && !({WSL})"
    assert "exit 1" in guard["run"]
    assert steps.index(guard) < steps.index(step_using(steps, "Vampire/setup-wsl"))


def test_native_probe_installs_lado_from_the_checkout_on_every_runner(steps):
    step = step_named(steps, "Native probe")
    assert "if" not in step
    run = step["run"]
    assert "uv tool install" in run and "uv tool install lado" not in run
    for command in ("platform.machine(), sys.version", "--version", "doctor", "native.log"):
        assert command in run
    # Every native check is expected to fail today: none makes the job red.
    assert "expected" in run and "required" not in run
    assert steps.index(step_using(steps, "astral-sh/setup-uv")) < steps.index(step)


def test_wsl_probe_runs_as_a_non_root_user_in_a_login_shell(steps):
    user = step_named(steps, "Create the user lado")
    assert user["if"] == WSL
    assert "useradd --create-home --shell /bin/bash lado" in user["run"]
    clone = step_named(steps, "Clone the repo in Ubuntu")
    assert "su - lado -c" in clone["run"] and "~/lado" in clone["run"]
    probe = step_named(steps, "WSL probe")
    assert probe["if"] == WSL
    run = probe["run"]
    assert "su - lado -c" in run
    for command in (
        "uname -m",
        "tmux -V",
        "env -i HOME",
        "PATH=/usr/bin:/bin:/usr/sbin:/sbin bash -ilc",
        "astral.sh/uv",
        "uv sync",
        "uv run lado --version",
        "uv run lado doctor",
        "make test",
        "make test-integration",
    ):
        assert command in run, command
    # Each check under a timeout, so a hang leaves time for the report.
    assert "timeout" in run
    # Only doctor and Kilo may fail: with no agent CLI installed doctor reports a FAIL,
    # and Kilo is only recorded.
    assert '"${4:-required}"' in run
    expected = [line.strip() for line in run.splitlines() if line.endswith(" expected")]
    assert expected[0] == "check lado-doctor 300 'cd ~/lado && uv run lado doctor' expected"
    assert all("kilo" in line for line in expected[1:]), expected
    check = step_named(steps, "Check WSL")
    assert check["if"] == WSL and "wsl -l -v" in check["run"]
    order = [steps.index(s) for s in (check, user, clone, probe)]
    assert order == sorted(order)


# The stub of `timeout`: it records the command and runs nothing; for a live test it prints
# the pytest summary line of LIVE_<PROVIDER> and exits with LIVE_<PROVIDER>_CODE.
TIMEOUT_STUB = """#!/bin/sh
printf '%s\\n' "$*" >>"$PROBE/ran"
case "$*" in
  *'-m live'*opencode*) printf '%s\\n' "$LIVE_OPENCODE"; exit "${LIVE_OPENCODE_CODE:-0}" ;;
  *'-m live'*kilo*) printf '%s\\n' "$LIVE_KILO"; exit "${LIVE_KILO_CODE:-0}" ;;
esac
"""
PASSED = "============ 3 passed in 412.20s (0:06:52) ============"


def run_wsl_probe(
    steps, tmp_path, tests="true", live="false", stub=TIMEOUT_STUB, **env
) -> dict[str, list]:
    """Run the WSL probe's script with a stub `timeout`: its checks.tsv rows by name."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "timeout").write_text(stub)
    (bin_dir / "timeout").chmod(0o755)
    probe = tmp_path / "probe"
    probe.mkdir()
    (tmp_path / "tmp").mkdir()
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "PROBE": str(probe),
        "TMPDIR": str(tmp_path / "tmp"),
        "UV_VERSION": "0",
        "OPENCODE_VERSION": "0",
        "KILO_VERSION": "0",
        "TESTS": tests,
        "LIVE": live,
        "LIVE_OPENCODE": PASSED,
        "LIVE_KILO": PASSED,
        **env,
    }
    script = step_named(steps, "WSL probe")["run"]
    subprocess.run(["bash", "-c", script], env=env, check=True)
    rows = (probe / "checks.tsv").read_text().splitlines()
    return {row.split("\t")[0]: row.split("\t") for row in rows}


def test_wsl_probe_gets_the_tests_input_as_a_boolean(steps):
    probe = step_named(steps, "WSL probe")
    assert probe["env"]["TESTS"] == "${{ " + TESTS + " }}"
    assert "TESTS" in probe["env"]["WSLENV"].split(":")


def test_wsl_probe_runs_the_make_checks_with_tests(steps, tmp_path):
    rows = run_wsl_probe(steps, tmp_path, tests="true")
    assert rows["wsl make-test"][1:] == ["0", "required", "wsl-make-test.log"]
    assert rows["wsl make-test-integration"][1:3] == ["0", "required"]
    ran = (tmp_path / "probe" / "ran").read_text()
    assert "cd ~/lado && make test\n" in ran and "make test-integration" in ran


def test_wsl_probe_skips_the_make_checks_without_tests(steps, tmp_path):
    rows = run_wsl_probe(steps, tmp_path, tests="false")
    for name in ("wsl make-test", "wsl make-test-integration"):
        assert rows[name][1:3] == ["skipped", "skipped"], rows[name]
    # The other checks still run.
    assert rows["wsl uv-sync"][1:3] == ["0", "required"]
    ran = (tmp_path / "probe" / "ran").read_text()
    assert "make test" not in ran and "uv sync" in ran


def test_a_skipped_check_neither_passes_nor_fails(steps):
    summary = step_named(steps, "Summary")["run"]
    # The summary names it, and lists no log for it as a failure.
    assert "'skipped'" in summary and "skipped" in summary.split("$failed")[1]
    verdict = step_named(steps, "Verdict")["run"]
    # Only `required` rows decide; a skipped row is not one.
    assert "$_.kind -eq 'required' -and $_.code -ne '0'" in verdict


def test_report_uploaded_always_then_the_verdict_last(steps):
    summary = step_named(steps, "Summary")
    assert summary["if"] == "always()"
    assert "GITHUB_STEP_SUMMARY" in summary["run"]
    upload = step_using(steps, "actions/upload-artifact")
    assert upload["if"] == "always()"
    assert upload["with"]["name"] == "windows-probe-${{ inputs.runner }}"
    assert 1 <= upload["with"]["retention-days"] <= 7
    verdict = step_named(steps, "Verdict")
    assert verdict["if"] == "always()"
    assert "required" in verdict["run"] and "exit 1" in verdict["run"]
    probes = [steps.index(step_named(steps, n)) for n in ("Native probe", "WSL probe")]
    assert max(probes) < steps.index(summary) < steps.index(upload)
    assert steps[-1] is verdict


def test_verdict_red_when_wsl_ran_no_check(steps):
    """A WSL probe that recorded nothing (a $PROBE it cannot write) is no green."""
    verdict = step_named(steps, "Verdict")
    assert verdict["env"]["WSL"] == "${{ inputs.wsl }}"
    run = verdict["run"]
    assert "$env:WSL -eq 'true'" in run and "'^wsl '" in run
    probe = step_named(steps, "WSL probe")["run"]
    # It fails at once when it cannot write the report, and on a row it cannot append.
    assert probe.startswith('set -u\ntouch "$PROBE/checks.tsv" || exit 1\n')
    assert '>>"$PROBE/checks.tsv" || exit 1' in probe


def test_wsl_probe_gets_the_live_input_and_the_pinned_cli_versions(steps):
    probe = step_named(steps, "WSL probe")
    env = probe["env"]
    assert env["LIVE"] == "${{ " + LIVE + " }}"
    # The versions LADO is tested with (`lado doctor` warns about others).
    assert env["OPENCODE_VERSION"].startswith(opencode.TESTED_VERSION + ".")
    assert env["KILO_VERSION"].startswith(kilo.TESTED_VERSION + ".")
    for version in (env["OPENCODE_VERSION"], env["KILO_VERSION"]):
        assert re.fullmatch(r"\d+\.\d+\.\d+", version), version
    assert {"LIVE", "OPENCODE_VERSION", "KILO_VERSION"} <= set(env["WSLENV"].split(":"))


def test_no_live_test_without_live(steps, tmp_path):
    rows = run_wsl_probe(steps, tmp_path, live="false")
    assert not [name for name in rows if "live" in name or "opencode" in name]
    assert "test-live" not in (tmp_path / "probe" / "ran").read_text()


def test_live_installs_the_pinned_clis_and_runs_opencode_required_kilo_recorded(steps, tmp_path):
    rows = run_wsl_probe(steps, tmp_path, tests="false", live="true", OPENCODE_VERSION="1.18.35")
    assert rows["wsl live-opencode"][1:] == ["0", "required", "wsl-live-opencode.log"]
    assert rows["wsl live-kilo"][1:] == ["0", "expected", "wsl-live-kilo.log"]
    ran = (tmp_path / "probe" / "ran").read_text().splitlines()
    names = list(rows)
    # After the other checks; each CLI installed before its test.
    assert names.index("wsl make-test-integration") < names.index("wsl opencode-install")
    assert names.index("wsl opencode-install") < names.index("wsl live-opencode")
    assert names.index("wsl kilo-install") < names.index("wsl live-kilo")
    assert rows["wsl opencode-install"][2] == "required"
    assert rows["wsl kilo-install"][2] == "expected"
    (install,) = [line for line in ran if "opencode-ai@" in line]
    assert "opencode-ai@1.18.35" in install and "su - lado -c" in install
    assert [line for line in ran if "@kilocode/cli@" in line]
    # The live tests as `make test-live PROVIDER=...` runs them, but the image test: the
    # free models take no image input, and that test skips.
    live = [line for line in ran if "-m live" in line]
    assert [line.split("cd ~/lado && ")[1] for line in live] == [
        "uv run pytest -m live -n0 -v -k 'opencode and not image'",
        "uv run pytest -m live -n0 -v -k 'kilo and not image'",
    ]
    # Never a paid provider, nor one without a model there.
    assert not [line for line in ran if "claude" in line or "codex" in line]


@pytest.mark.parametrize(
    "summary, code",
    [
        (PASSED, "0"),
        ("====== 2 passed, 1 skipped in 300.00s (0:05:00) ======", "not-passed"),
        ("====== 3 skipped in 1.00s ======", "not-passed"),
        ("====== 3 deselected in 1.00s ======", "not-passed"),
        ("", "not-passed"),
    ],
)
def test_a_live_check_passes_only_when_a_test_passed_and_none_skipped(
    steps, tmp_path, summary, code
):
    rows = run_wsl_probe(steps, tmp_path, live="true", LIVE_OPENCODE=summary)
    assert rows["wsl live-opencode"][1] == code


def test_a_failing_live_test_keeps_its_code_and_its_evidence(steps, tmp_path):
    evidence = tmp_path / "tmp" / "lado-live-evidence" / "20261010-test_worker"
    # The live test writes its evidence while it runs (the script clears the folder first).
    writes = f'mkdir -p "{evidence}" && echo "w1 never reported" >"{evidence}/lado-log.txt"'
    stub = TIMEOUT_STUB.replace("*'-m live'*opencode*) ", f"*'-m live'*opencode*) {writes}; ")
    rows = run_wsl_probe(
        steps,
        tmp_path,
        live="true",
        stub=stub,
        LIVE_OPENCODE="====== 1 failed, 2 passed in 600.00s ======",
        LIVE_OPENCODE_CODE="1",
    )
    assert rows["wsl live-opencode"][1:3] == ["1", "required"]
    kept = tmp_path / "probe" / "live-evidence-opencode" / evidence.name / "lado-log.txt"
    assert kept.read_text() == "w1 never reported\n"
    # A passing one keeps none.
    assert not (tmp_path / "probe" / "live-evidence-kilo").exists()
