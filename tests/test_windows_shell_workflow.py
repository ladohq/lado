""".github/workflows/windows-shell.yml: the Windows (+ WSL2) probe, started by hand."""

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "windows-shell.yml"
# A boolean input as GitHub's web form gives it (a boolean) or the API (a string).
WSL = "inputs.wsl == true || inputs.wsl == 'true'"
SHELL = "inputs.shell == true || inputs.shell == 'true'"
TESTS = "inputs.tests == true || inputs.tests == 'true'"


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
    assert inputs["shell"]["type"] == "boolean"
    assert inputs["shell"]["default"] is False
    assert inputs["tests"]["type"] == "boolean"
    assert inputs["tests"]["default"] is True
    assert inputs["minutes"]["type"] == "number"
    assert inputs["minutes"]["default"] == 120


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


@pytest.mark.parametrize("name, condition", [("wsl", WSL), ("shell", SHELL)])
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


def test_no_action_tmate_and_no_msys2(steps):
    """action-tmate hung on Windows after installing MSYS2's tmate (run 38001793230)."""
    assert not [s for s in steps if "action-tmate" in s.get("uses", "")]
    assert not [s for s in steps if "msys64" in s.get("run", "").lower()]


def test_wsl2_ubuntu_with_the_tools(steps):
    step = step_using(steps, "Vampire/setup-wsl")
    assert step["if"] == WSL
    assert step["with"]["distribution"] == "Ubuntu-24.04"
    assert str(step["with"]["wsl-version"]) == "2"
    packages = step["with"]["additional-packages"].split()
    assert {"tmux", "git", "curl", "build-essential", "less"} <= set(packages)
    # Ubuntu's own, dynamically linked tmate: the static release's resolver never found
    # ssh.tmate.io in WSL (run 38005117396); xz-utils only unpacked that release.
    assert "tmate" in packages and "xz-utils" not in packages
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


def test_a_shell_without_wsl_fails_before_setup(steps):
    guard = step_named(steps, "No shell without WSL")
    assert guard["if"] == f"({SHELL}) && !({WSL})"
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
    # Only doctor may fail: with no agent CLI installed it reports a FAIL.
    assert '"${4:-required}"' in run
    expected = [line for line in run.splitlines() if line.endswith(" expected")]
    assert expected == ["check lado-doctor 300 'cd ~/lado && uv run lado doctor' expected"]
    check = step_named(steps, "Check WSL")
    assert check["if"] == WSL and "wsl -l -v" in check["run"]
    order = [steps.index(s) for s in (check, user, clone, probe)]
    assert order == sorted(order)


def run_wsl_probe(steps, tmp_path, tests: str) -> list[list[str]]:
    """Run the WSL probe's script with a `timeout` that runs nothing: its checks.tsv rows."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "timeout"
    stub.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >>"$PROBE/ran"\n')
    stub.chmod(0o755)
    probe = tmp_path / "probe"
    probe.mkdir()
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "PROBE": str(probe),
        "UV_VERSION": "0",
        "TESTS": tests,
    }
    script = step_named(steps, "WSL probe")["run"]
    subprocess.run(["bash", "-c", script], env=env, check=True)
    rows = (probe / "checks.tsv").read_text().splitlines()
    return [row.split("\t") for row in rows]


def test_wsl_probe_gets_the_tests_input_as_a_boolean(steps):
    probe = step_named(steps, "WSL probe")
    assert probe["env"]["TESTS"] == "${{ " + TESTS + " }}"
    assert "TESTS" in probe["env"]["WSLENV"].split(":")


def test_wsl_probe_runs_the_make_checks_with_tests(steps, tmp_path):
    rows = {row[0]: row for row in run_wsl_probe(steps, tmp_path, "true")}
    assert rows["wsl make-test"][1:] == ["0", "required", "wsl-make-test.log"]
    assert rows["wsl make-test-integration"][1:3] == ["0", "required"]
    ran = (tmp_path / "probe" / "ran").read_text()
    assert "cd ~/lado && make test\n" in ran and "make test-integration" in ran


def test_wsl_probe_skips_the_make_checks_without_tests(steps, tmp_path):
    rows = {row[0]: row for row in run_wsl_probe(steps, tmp_path, "false")}
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


def test_shell_after_the_upload_only_with_shell_and_wsl(steps):
    shell = step_named(steps, "Shell")
    assert shell["if"] == f"({SHELL}) && ({WSL})"
    assert steps.index(step_using(steps, "actions/upload-artifact")) < steps.index(shell)
    assert steps.index(shell) == len(steps) - 2


def test_shell_is_ubuntus_tmate_and_only_for_the_starter(steps):
    shell = step_named(steps, "Shell")
    run = shell["run"]
    # Ubuntu's package (setup-wsl's additional-packages), no static release.
    assert "releases/download" not in run and "sha256sum" not in run
    assert "/usr/local/bin" not in run
    assert "https://github.com/$ACTOR.keys" in run
    assert shell["env"]["ACTOR"] == "${{ github.actor }}"
    # No keys: no session open to anyone.
    assert '[ -z "$keys" ]' in run
    assert "-a ~/.tmate-keys" in run and "su - lado -c" in run
    assert re.search(r"timeout \d+ su - lado -c '[^']*wait tmate-ready", run)
    assert "#{tmate_ssh}" in run and "GITHUB_STEP_SUMMARY" in run
    assert "~lado/continue" in run
