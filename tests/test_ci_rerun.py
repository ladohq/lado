"""scripts/ci_rerun.py: whether a failed CI run is rerun because some of its jobs got no
runner, and the command ci-rerun.yml runs."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "ci_rerun.py"

spec = importlib.util.spec_from_file_location("ci_rerun", SCRIPT)
ci_rerun = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci_rerun)

NOT_ACQUIRED = "The job was not acquired by Runner of type hosted even after multiple attempts"
CAPACITY = "Due to capacity constraints, jobs targeting macOS arm64 runners may experience longer queue times."
SUPERSEDED = "Canceling since a higher priority waiting request for ci-207 exists"


def run(**facts) -> dict:
    """A CI run's attempt 1 as `actions/runs/<id>/attempts/1` gives it: a push to main that
    failed unless named."""
    return {
        "id": 100,
        "event": "push",
        "head_branch": "main",
        "run_attempt": 1,
        "status": "completed",
        "conclusion": "failure",
        **facts,
    }


def job(id_: int, name: str, conclusion="success", steps=5, runner="GitHub Actions 1") -> dict:
    return {
        "id": id_,
        "name": name,
        "status": "completed",
        "conclusion": conclusion,
        "steps": [{"number": n} for n in range(steps)],
        "runner_name": runner,
    }


def runnerless(id_: int, name="smoke macos-latest opencode") -> dict:
    return job(id_, name, conclusion="cancelled", steps=0, runner="")


def note(message: str, level="failure") -> dict:
    return {"annotation_level": level, "message": message}


def jobs(*odd: dict) -> list[dict]:
    """The run's jobs: unit, a smoke cell and ci-ok, then the odd ones; ci-ok failed when any
    is odd."""
    return [
        job(1, "unit (3.10)"),
        job(2, "smoke ubuntu-latest claude"),
        *odd,
        job(9, "ci-ok", conclusion="failure" if odd else "success"),
    ]


def test_a_cell_that_got_no_runner_on_main_is_rerun():
    rerun, reason = ci_rerun.verdict(
        run(), jobs(runnerless(5)), {5: [note(NOT_ACQUIRED), note(CAPACITY, "notice")]}, None
    )
    assert rerun is True
    assert "smoke macos-latest opencode" in reason


def test_several_runnerless_cells_are_rerun_together():
    rerun, reason = ci_rerun.verdict(
        run(),
        jobs(runnerless(5), runnerless(6, "smoke macos-latest kilo")),
        {5: [note(NOT_ACQUIRED)], 6: [note(NOT_ACQUIRED)]},
        None,
    )
    assert rerun is True
    assert "smoke macos-latest opencode" in reason and "smoke macos-latest kilo" in reason


def test_a_real_failure_beside_a_runnerless_cell_is_not_rerun():
    rerun, reason = ci_rerun.verdict(
        run(),
        jobs(runnerless(5), job(3, "unit (3.13)", conclusion="failure")),
        {5: [note(NOT_ACQUIRED)], 3: [note("Process completed with exit code 1.")]},
        None,
    )
    assert rerun is False
    assert "unit (3.13)" in reason


def test_a_job_cancelled_after_it_started_is_not_rerun():
    """A job that ran steps on a runner and was then cancelled (its timeout) got a runner."""
    started = job(5, "smoke macos-latest opencode", conclusion="cancelled", steps=4)
    rerun, reason = ci_rerun.verdict(run(), jobs(started), {5: [note(NOT_ACQUIRED)]}, None)
    assert rerun is False
    assert "smoke macos-latest opencode" in reason


def test_a_runnerless_cancel_without_the_annotation_is_not_rerun():
    rerun, reason = ci_rerun.verdict(run(), jobs(runnerless(5)), {5: [note(SUPERSEDED)]}, None)
    assert rerun is False
    assert "smoke macos-latest opencode" in reason


def test_a_runnerless_cancel_with_no_annotations_at_all_is_not_rerun():
    rerun, _ = ci_rerun.verdict(run(), jobs(runnerless(5)), {}, None)
    assert rerun is False


def test_the_second_attempt_is_not_rerun():
    rerun, reason = ci_rerun.verdict(
        run(run_attempt=2), jobs(runnerless(5)), {5: [note(NOT_ACQUIRED)]}, None
    )
    assert rerun is False
    assert "attempt 2" in reason


def test_a_superseded_run_is_not_rerun():
    superseded = job(5, "smoke macos-latest opencode", conclusion="cancelled", steps=0, runner="")
    rerun, reason = ci_rerun.verdict(
        run(event="pull_request", head_branch="fix/x", conclusion="cancelled"),
        jobs(superseded),
        {5: [note(SUPERSEDED)]},
        100,
    )
    assert rerun is False
    assert "cancelled" in reason


def test_a_green_run_is_not_rerun():
    rerun, reason = ci_rerun.verdict(run(conclusion="success"), jobs(), {}, None)
    assert rerun is False
    assert "success" in reason


def test_a_failed_run_with_only_ci_ok_red_is_not_rerun():
    """Nothing but ci-ok did not succeed: no job got no runner, so nothing proves the cause."""
    rerun, _ = ci_rerun.verdict(
        run(), [job(1, "unit (3.10)"), job(9, "ci-ok", "failure")], {}, None
    )
    assert rerun is False


def test_a_pull_requests_newest_run_is_rerun():
    rerun, _ = ci_rerun.verdict(
        run(event="pull_request", head_branch="fix/x"),
        jobs(runnerless(5)),
        {5: [note(NOT_ACQUIRED)]},
        100,
    )
    assert rerun is True


def test_a_pull_requests_run_with_a_newer_run_is_not_rerun():
    """Its rerun would join the group ci-<pr> and cancel the newer run."""
    rerun, reason = ci_rerun.verdict(
        run(event="pull_request", head_branch="fix/x"),
        jobs(runnerless(5)),
        {5: [note(NOT_ACQUIRED)]},
        101,
    )
    assert rerun is False
    assert "101" in reason


def test_skipped_jobs_count_as_fine():
    skipped = job(5, "smoke macos-latest opencode", conclusion="skipped", steps=0, runner="")
    rerun, _ = ci_rerun.verdict(
        run(), [*jobs(runnerless(6)), skipped], {6: [note(NOT_ACQUIRED)]}, None
    )
    assert rerun is True


# The command.


class FakeGh:
    """`gh` answering from recorded facts: `api <path>` gives the JSON for that path, `run
    rerun` is recorded."""

    def __init__(self, *, first: dict, latest_attempt=1, run_jobs, annotations, newest=None):
        self.first = first
        self.latest_attempt = latest_attempt
        self.run_jobs = run_jobs
        self.annotations = annotations
        self.newest = newest
        self.calls: list[list[str]] = []

    def __call__(self, *args: str):
        self.calls.append(list(args))
        if args[0] == "run":
            return None
        assert args[0] == "api"
        path = args[1]
        rid = self.first["id"]
        base = "repos/{owner}/{repo}/"
        if path == f"{base}actions/runs/{rid}":
            return {**self.first, "run_attempt": self.latest_attempt}
        if path == f"{base}actions/runs/{rid}/attempts/1":
            return self.first
        if path == f"{base}actions/runs/{rid}/attempts/1/jobs?per_page=100":
            return {"jobs": self.run_jobs}
        if path.startswith(f"{base}check-runs/") and path.endswith("/annotations"):
            return self.annotations.get(int(path.split("/")[-2]), [])
        if path.startswith(f"{base}actions/workflows/ci.yml/runs?"):
            return {"workflow_runs": [{"id": self.newest}] if self.newest else []}
        raise AssertionError(f"unexpected gh api {path}")

    def reruns(self) -> list[list[str]]:
        return [c for c in self.calls if c[0] == "run"]


def runnerless_gh(**facts) -> FakeGh:
    return FakeGh(
        first=run(**facts.pop("first", {})),
        run_jobs=jobs(runnerless(5)),
        annotations={5: [note(NOT_ACQUIRED)]},
        **facts,
    )


def test_without_rerun_the_command_only_says_it_would(capsys):
    gh = runnerless_gh()
    assert ci_rerun.main(["100"], gh=gh) == 0
    assert gh.reruns() == []
    assert capsys.readouterr().out.startswith("would rerun run 100:")


def test_with_rerun_the_command_reruns_the_failed_jobs_once(capsys):
    gh = runnerless_gh()
    assert ci_rerun.main(["100", "--rerun"], gh=gh) == 0
    assert gh.reruns() == [["run", "rerun", "100", "--failed"]]
    assert capsys.readouterr().out.startswith("rerunning run 100:")


def test_the_command_does_not_rerun_a_run_already_on_its_second_attempt(capsys):
    gh = runnerless_gh(latest_attempt=2)
    assert ci_rerun.main(["100", "--rerun"], gh=gh) == 0
    assert gh.reruns() == []
    out = capsys.readouterr().out
    assert out.startswith("not rerunning run 100:")
    assert "attempt 2" in out


def test_without_rerun_a_rerun_run_still_shows_attempt_1s_verdict(capsys):
    """By hand on a past run (AC-3): what the workflow would have done after attempt 1."""
    gh = runnerless_gh(latest_attempt=2)
    assert ci_rerun.main(["100"], gh=gh) == 0
    out = capsys.readouterr().out
    assert out.startswith("would rerun run 100:")
    assert "attempt 2" in out


def test_the_command_does_not_rerun_a_real_failure(capsys):
    gh = FakeGh(
        first=run(),
        run_jobs=jobs(job(3, "unit (3.13)", conclusion="failure")),
        annotations={},
    )
    assert ci_rerun.main(["100", "--rerun"], gh=gh) == 0
    assert gh.reruns() == []
    assert capsys.readouterr().out.startswith("not rerunning run 100:")


def test_the_command_reads_annotations_only_of_jobs_that_did_not_succeed():
    gh = runnerless_gh()
    ci_rerun.main(["100"], gh=gh)
    read = [c[1] for c in gh.calls if c[1].endswith("/annotations")]
    assert read == ["repos/{owner}/{repo}/check-runs/5/annotations"]


def test_the_command_asks_for_a_pull_requests_newest_run_by_its_branch(capsys):
    gh = runnerless_gh(first={"event": "pull_request", "head_branch": "fix/a b"}, newest=101)
    assert ci_rerun.main(["100", "--rerun"], gh=gh) == 0
    assert gh.reruns() == []
    (asked,) = [c[1] for c in gh.calls if "workflows/ci.yml/runs" in c[1]]
    assert asked == (
        "repos/{owner}/{repo}/actions/workflows/ci.yml/runs"
        "?event=pull_request&branch=fix%2Fa%20b&per_page=1"
    )


def test_the_command_does_not_ask_for_newer_runs_of_a_push():
    gh = runnerless_gh()
    ci_rerun.main(["100"], gh=gh)
    assert not [c for c in gh.calls if "workflows/ci.yml/runs" in c[1]]


@pytest.mark.parametrize("argv", [[], ["x"], ["100", "--force"]])
def test_the_command_refuses_bad_arguments(argv):
    with pytest.raises(SystemExit) as exit_:
        ci_rerun.main(argv, gh=FakeGh(first=run(), run_jobs=[], annotations={}))
    assert exit_.value.code == 2
