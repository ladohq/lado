""".github/workflows/windows-shell.yml: the Windows (+ WSL2) probe, weekly on main, by hand,
and called by live.yml once per provider."""

import importlib.util
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "windows-shell.yml"
# The run's settings, as the settings job gives them: always the strings 'true' or 'false'.
SETTINGS = "needs.settings.outputs"
WSL = f"{SETTINGS}.wsl == 'true'"
LIVE = f"{SETTINGS}.live == 'true'"
NO_TESTS = f"{SETTINGS}.tests == 'false'"
INPUTS = ["runner", "wsl", "tests", "live", "minutes", "provider"]


def _pins() -> dict:
    spec = importlib.util.spec_from_file_location("live_ci", ROOT / "scripts" / "live_ci.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PINS


PINS = _pins()


@pytest.fixture(scope="module")
def text() -> str:
    return WORKFLOW.read_text()


@pytest.fixture(scope="module")
def workflow(text) -> dict:
    return yaml.safe_load(text)


@pytest.fixture(scope="module")
def settings_job(workflow) -> dict:
    return workflow["jobs"]["settings"]


@pytest.fixture(scope="module")
def probe_job(workflow) -> dict:
    return workflow["jobs"]["probe"]


@pytest.fixture(scope="module")
def steps(probe_job) -> list[dict]:
    return probe_job["steps"]


def run_settings(settings_job, tmp_path, **inputs) -> tuple[int, dict, str]:
    """Run the settings script with the inputs given (the others empty, as GitHub renders
    an input a run does not have): its exit code, its outputs and what it printed."""
    (step,) = settings_job["steps"]
    output = tmp_path / "github_output"
    output.touch()
    env = {"PATH": os.environ["PATH"], "GITHUB_OUTPUT": str(output)}
    env.update({name.upper(): str(inputs.get(name, "")) for name in INPUTS})
    done = subprocess.run(["bash", "-c", step["run"]], env=env, capture_output=True, text=True)
    lines = output.read_text().splitlines()
    return done.returncode, dict(line.split("=", 1) for line in lines), done.stdout


def step_using(steps, action: str) -> dict:
    (step,) = [s for s in steps if s.get("uses", "").startswith(action + "@")]
    return step


def step_named(steps, name: str) -> dict:
    (step,) = [s for s in steps if s.get("name") == name]
    return step


def test_started_by_hand_called_and_weekly(workflow):
    # PyYAML reads the key `on` as True.
    triggers = workflow[True]
    assert list(triggers) == ["workflow_dispatch", "workflow_call", "schedule"]
    # Once a week (a schedule runs on the default branch), at an off-peak minute.
    assert triggers["schedule"] == [{"cron": "17 3 * * 1"}]


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
    # The cloud providers of scripts/live_ci.py, or all of them.
    assert inputs["provider"]["type"] == "choice"
    assert inputs["provider"]["options"] == ["all", *PINS]
    assert inputs["provider"]["default"] == "all"
    assert list(inputs) == INPUTS


def test_a_call_takes_the_same_inputs_with_the_same_defaults(workflow):
    """workflow_call has no choice type: a choice is a string there, checked by settings."""
    by_hand = workflow[True]["workflow_dispatch"]["inputs"]
    called = workflow[True]["workflow_call"]
    assert list(called["inputs"]) == INPUTS
    for name in INPUTS:
        kind = by_hand[name]["type"]
        assert called["inputs"][name]["type"] == ("string" if kind == "choice" else kind)
        assert called["inputs"][name]["default"] == by_hand[name]["default"]
    assert "secrets" not in called


def test_settings_job_reads_each_input_once_and_gives_each_setting(settings_job, probe_job):
    (step,) = settings_job["steps"]
    assert step["shell"] == "bash" and settings_job["runs-on"] == "ubuntu-latest"
    assert step["env"] == {name.upper(): "${{ inputs." + name + " }}" for name in INPUTS}
    assert settings_job["outputs"] == {
        name: "${{ steps." + step["id"] + ".outputs." + name + " }}" for name in INPUTS
    }
    assert probe_job["needs"] == "settings"


def test_no_job_but_settings_reads_an_input(workflow, settings_job):
    jobs = dict(workflow["jobs"])
    jobs.pop("settings")
    assert "inputs." not in yaml.safe_dump(jobs)
    assert set(workflow["jobs"]) == {"settings", "probe"}


def test_a_run_without_inputs_takes_the_defaults_of_a_run_by_hand(workflow, settings_job, tmp_path):
    """A scheduled run has no inputs: each setting is its input's default."""
    code, outputs, _ = run_settings(settings_job, tmp_path)
    assert code == 0
    inputs = workflow[True]["workflow_dispatch"]["inputs"]
    defaults = {name: str(inputs[name]["default"]).lower() for name in INPUTS}
    assert outputs == defaults
    assert outputs == {
        "runner": "windows-latest",
        "wsl": "true",
        "tests": "true",
        "live": "false",
        "minutes": "120",
        "provider": "all",
    }


def test_no_live_tests_on_the_schedule(workflow, settings_job, tmp_path):
    _, outputs, _ = run_settings(settings_job, tmp_path)
    assert outputs["live"] == "false"
    assert workflow[True]["workflow_dispatch"]["inputs"]["live"]["default"] is False


@pytest.mark.parametrize(
    "given, setting",
    # From GitHub's web form a boolean input is a boolean (rendered true or false), from
    # the API a string, whose case GitHub ignores when it compares.
    [("true", "true"), ("false", "false"), ("True", "true"), ("FALSE", "false")],
)
def test_settings_take_a_boolean_in_either_form(settings_job, tmp_path, given, setting):
    code, outputs, _ = run_settings(settings_job, tmp_path, wsl=given, tests=given, live=given)
    assert code == 0
    assert (outputs["wsl"], outputs["tests"], outputs["live"]) == (setting,) * 3


@pytest.mark.parametrize(
    "inputs, error",
    [
        ({"wsl": "yes"}, "wsl must be true or false, not yes"),
        ({"live": "1"}, "live must be true or false, not 1"),
        ({"minutes": "0"}, "minutes must be 1 to 360 (GitHub's cap), not 0"),
        ({"minutes": "361"}, "minutes must be 1 to 360 (GitHub's cap), not 361"),
        ({"minutes": "ten"}, "minutes must be 1 to 360 (GitHub's cap), not ten"),
        ({"minutes": "1.5"}, "minutes must be 1 to 360 (GitHub's cap), not 1.5"),
        ({"provider": "codex"}, "provider must be all, opencode or kilo, not codex"),
        ({"provider": "claude"}, "provider must be all, opencode or kilo, not claude"),
        ({"provider": "Kilo"}, "provider must be all, opencode or kilo, not Kilo"),
    ],
)
def test_settings_refuse_a_wrong_input(settings_job, tmp_path, inputs, error):
    code, outputs, printed = run_settings(settings_job, tmp_path, **inputs)
    assert code == 1 and outputs == {}
    assert f"::error::{error}" in printed


@pytest.mark.parametrize("provider", ["all", *PINS])
def test_settings_take_each_cloud_provider_or_all(settings_job, tmp_path, provider):
    code, outputs, _ = run_settings(settings_job, tmp_path, provider=provider)
    assert code == 0 and outputs["provider"] == provider


def test_settings_name_the_cloud_providers_of_the_script(settings_job):
    (step,) = settings_job["steps"]
    assert f"all | {' | '.join(PINS)})" in step["run"]


def test_minutes_given_as_a_string_become_a_plain_number(settings_job, tmp_path):
    # From the API (gh workflow run -f minutes=090) the input is a string, which fromJSON
    # would refuse with a leading zero.
    code, outputs, _ = run_settings(settings_job, tmp_path, minutes="090")
    assert code == 0 and outputs["minutes"] == "90"


def test_job_runs_on_the_chosen_runner_for_the_chosen_minutes(probe_job):
    assert probe_job["runs-on"] == "${{ needs.settings.outputs.runner }}"
    # An output is a string, which timeout-minutes refuses; fromJSON makes it a number.
    assert probe_job["timeout-minutes"] == "${{ fromJSON(needs.settings.outputs.minutes) }}"
    # The steps without a shell are PowerShell, also to actionlint.
    assert probe_job["defaults"] == {"run": {"shell": "pwsh"}}


def test_report_folder_first_so_the_report_steps_work_after_a_guard(steps):
    folder = steps[0]
    assert folder["name"] == "Report folder" and "if" not in folder
    assert "PROBE=" in folder["run"] and "GITHUB_ENV" in folder["run"]


@pytest.mark.parametrize("name, condition", [("wsl", WSL), ("live", LIVE), ("tests", NO_TESTS)])
def test_boolean_settings_compared_as_a_string(steps, name, condition):
    # A job's output is a string: a bare `if: needs.settings.outputs.wsl` takes 'false'
    # as true.
    conditions = [s["if"] for s in steps if f"{SETTINGS}.{name}" in s.get("if", "")]
    assert conditions
    for line in conditions:
        assert f"{SETTINGS}.{name}" not in line.replace(condition, ""), line


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
        and f"{SETTINGS}.wsl" in s.get("if", "")
        and "exit 1" in s.get("run", "")
    ]
    assert guards and guards[0] < setup


def test_live_without_wsl_fails_before_setup(steps):
    guard = step_named(steps, "No live agents without WSL")
    assert guard["if"] == f"({LIVE}) && !({WSL})"
    assert "exit 1" in guard["run"]
    assert steps.index(guard) < steps.index(step_using(steps, "Vampire/setup-wsl"))


def test_native_probe_installs_lado_from_the_checkout_but_for_a_live_only_run(steps):
    step = step_named(steps, "Native probe")
    # A live-only call (live.yml) wants only its provider's verdict.
    assert step["if"] == f"!({LIVE} && {NO_TESTS})"
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
    expected = [line.strip() for line in run.splitlines() if line.endswith(" expected")]
    assert expected == ["check lado-doctor 300 'cd ~/lado && uv run lado doctor' expected"]
    check = step_named(steps, "Check WSL")
    assert check["if"] == WSL and "wsl -l -v" in check["run"]
    order = [steps.index(s) for s in (check, user, clone, probe)]
    assert order == sorted(order)


# The stub of `timeout`: it records the command and runs nothing; asked for the cloud
# providers it names those of scripts/live_ci.py; for a provider's live cell it exits with
# LIVE_<PROVIDER>_CODE.
TIMEOUT_STUB = f"""#!/bin/sh
printf '%s\\n' "$*" >>"$PROBE/ran"
case "$*" in
  *'live_ci.py providers'*) echo '{" ".join(PINS)}' ;;
  *'live_ci.py run opencode'*) exit "${{LIVE_OPENCODE_CODE:-0}}" ;;
  *'live_ci.py run kilo'*) exit "${{LIVE_KILO_CODE:-0}}" ;;
esac
"""


def run_wsl_probe(
    steps, tmp_path, tests="true", live="false", provider="all", stub=TIMEOUT_STUB, **env
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
        "TESTS": tests,
        "LIVE": live,
        "PROVIDER": provider,
        **env,
    }
    script = step_named(steps, "WSL probe")["run"]
    subprocess.run(["bash", "-c", script], env=env, check=True)
    rows = (probe / "checks.tsv").read_text().splitlines()
    return {row.split("\t")[0]: row.split("\t") for row in rows}


def test_wsl_probe_gets_the_tests_input_as_a_boolean(steps):
    probe = step_named(steps, "WSL probe")
    assert probe["env"]["TESTS"] == "${{ needs.settings.outputs.tests }}"
    assert "TESTS" in probe["env"]["WSLENV"].split(":")


def test_wsl_probe_runs_the_make_checks_with_tests(steps, tmp_path):
    rows = run_wsl_probe(steps, tmp_path, tests="true")
    assert rows["wsl make-test"][1:] == ["0", "required", "wsl-make-test.log"]
    assert rows["wsl make-test-integration"][1:3] == ["0", "required"]
    ran = (tmp_path / "probe" / "ran").read_text()
    assert "cd ~/lado && make test\n" in ran and "make test-integration" in ran


def test_the_agents_path_is_lados_own_after_uv_sync(steps):
    run = step_named(steps, "WSL probe")["run"]
    lines = [line.strip() for line in run.splitlines()]
    (agents,) = [line for line in lines if line.startswith("check agents-path ")]
    (sync,) = [line for line in lines if line.startswith("check uv-sync ")]
    assert lines.index(sync) < lines.index(agents)
    assert "env -u LADO_AGENT_ENV uv run python" in agents
    assert "agent_env.from_shell()" in agents
    # No PATH built by hand: LADO is the one source of it.
    assert "/usr/bin:/bin:/usr/sbin:/sbin" not in run and "env -i" not in run


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
    # One name per call of live.yml (a live-only run: its provider), else `tests`.
    assert upload["with"]["name"] == (
        "windows-probe-${{ needs.settings.outputs.runner }}-${{ "
        f"({LIVE} && {NO_TESTS}) && {SETTINGS}.provider || 'tests' }}}}"
    )
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
    assert verdict["env"]["WSL"] == "${{ needs.settings.outputs.wsl }}"
    run = verdict["run"]
    assert "$env:WSL -eq 'true'" in run and "'^wsl '" in run
    probe = step_named(steps, "WSL probe")["run"]
    # It fails at once when it cannot write the report, and on a row it cannot append.
    assert probe.startswith('set -u\ntouch "$PROBE/checks.tsv" || exit 1\n')
    assert '>>"$PROBE/checks.tsv" || exit 1' in probe


def test_wsl_probe_gets_the_live_settings_and_no_cli_version(text, steps):
    env = step_named(steps, "WSL probe")["env"]
    assert env["LIVE"] == "${{ needs.settings.outputs.live }}"
    assert env["PROVIDER"] == "${{ needs.settings.outputs.provider }}"
    assert {"LIVE", "PROVIDER"} <= set(env["WSLENV"].split(":"))
    # scripts/live_ci.py's PINS is the one place of a cloud CLI's version.
    for package, version, _ in PINS.values():
        assert package not in text and version not in text, package
    assert "_VERSION" not in str(env).replace("UV_VERSION", "")


def test_no_live_test_without_live(steps, tmp_path):
    rows = run_wsl_probe(steps, tmp_path, live="false")
    assert not [name for name in rows if "live" in name or "node" in name]
    assert "live_ci.py" not in (tmp_path / "probe" / "ran").read_text()


def test_live_runs_a_required_cell_of_the_script_for_each_cloud_provider(steps, tmp_path):
    rows = run_wsl_probe(steps, tmp_path, tests="false", live="true")
    names = list(rows)
    # Node and npm from Ubuntu first, a check of its own that counts.
    assert rows["wsl node"][1:3] == ["0", "required"]
    for provider in PINS:
        assert rows[f"wsl live-{provider}"][1:] == ["0", "required", f"wsl-live-{provider}.log"]
        assert names.index("wsl node") < names.index(f"wsl live-{provider}")
    assert names.index("wsl make-test-integration") < names.index("wsl node")
    ran = (tmp_path / "probe" / "ran").read_text().splitlines()
    cells = [line for line in ran if "live_ci.py run" in line]
    out = tmp_path / "tmp" / "lado-live-out"
    assert [line.split("cd ~/lado && ")[1] for line in cells] == [
        f"uv run python scripts/live_ci.py run {p} {out}/{p}" for p in PINS
    ]
    for line in cells:
        assert "su - lado -c" in line
    assert [line for line in ran if "live_ci.py providers" in line]


def test_a_live_run_with_no_provider_listed_is_red(steps, tmp_path):
    stub = TIMEOUT_STUB.replace(f"echo '{' '.join(PINS)}'", "exit 1")
    rows = run_wsl_probe(steps, tmp_path, tests="false", live="true", stub=stub)
    assert rows["wsl live-providers"][1:3] == ["none", "required"]


@pytest.mark.parametrize("provider", list(PINS))
def test_a_live_call_runs_only_its_provider(steps, tmp_path, provider):
    rows = run_wsl_probe(steps, tmp_path, tests="false", live="true", provider=provider)
    assert [name for name in rows if name.startswith("wsl live-")] == [f"wsl live-{provider}"]


def test_a_cells_exit_code_is_its_verdict(steps, tmp_path):
    rows = run_wsl_probe(steps, tmp_path, live="true", LIVE_KILO_CODE="1")
    assert rows["wsl live-kilo"][1:3] == ["1", "required"]
    assert rows["wsl live-opencode"][1:3] == ["0", "required"]


def test_a_failing_cell_keeps_its_code_and_its_evidence(steps, tmp_path):
    evidence = tmp_path / "tmp" / "lado-live-out" / "opencode" / "evidence" / "20261010-test_w"
    # The script copies a failing cell's evidence into its out folder.
    writes = f'mkdir -p "{evidence}" && echo "w1 never reported" >"{evidence}/lado-log.txt"'
    stub = TIMEOUT_STUB.replace(
        "*'live_ci.py run opencode'*) ", f"*'live_ci.py run opencode'*) {writes}; "
    )
    rows = run_wsl_probe(steps, tmp_path, live="true", stub=stub, LIVE_OPENCODE_CODE="1")
    assert rows["wsl live-opencode"][1:3] == ["1", "required"]
    kept = tmp_path / "probe" / "live-evidence-opencode" / evidence.name / "lado-log.txt"
    assert kept.read_text() == "w1 never reported\n"
    # A passing one keeps none.
    assert not (tmp_path / "probe" / "live-evidence-kilo").exists()
