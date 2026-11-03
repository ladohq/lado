"""Whether a failed CI run is rerun because some of its jobs got no runner (ci-rerun.yml).

    python3 scripts/ci_rerun.py <run-id> [--rerun]

GitHub now and then cannot hand a job to a hosted runner, mostly a smoke cell on
`macos-latest` when it lacks macOS arm64 capacity: the job ends `cancelled` with no step,
no runner and the annotation "The job was not acquired by Runner of type hosted even after
multiple attempts", and `ci-ok` fails the run. Nothing in the work is at fault, and a rerun
of the failed jobs has passed every time.

The verdict is on the run's first attempt: rerun only when the attempt failed, and every
job of it that did not succeed, `ci-ok` aside, was cancelled with no step, no runner and
that annotation; and, for a pull request's run, when no newer CI run of its branch exists
(a rerun joins the group `ci-<pr>` and would cancel the newer run). It prints the verdict
and why. With `--rerun` it also reruns the failed jobs (`gh run rerun <id> --failed`), but
never a run already on a later attempt, so a run is rerun at most once.

Standard library and `gh` only: ci-rerun.yml runs it with the runner's python3, `GH_TOKEN`
and `GH_REPO` set; by hand it works from a clone with `gh` logged in.
"""

import argparse
import json
import subprocess
import sys
from urllib.parse import quote

NOT_ACQUIRED = "was not acquired by Runner"
REPO = "repos/{owner}/{repo}/"


def got_no_runner(job: dict, annotations: list[dict]) -> bool:
    """The job was cancelled before any runner took it, and GitHub says so."""
    return (
        job.get("conclusion") == "cancelled"
        and not job.get("steps")
        and not job.get("runner_name")
        and any(NOT_ACQUIRED in note.get("message", "") for note in annotations)
    )


def unsuccessful(jobs: list[dict]) -> list[dict]:
    """The jobs that did not succeed, `ci-ok` aside: it fails whenever another job does."""
    return [
        job
        for job in jobs
        if job.get("conclusion") not in ("success", "skipped") and job.get("name") != "ci-ok"
    ]


def verdict(
    run: dict, jobs: list[dict], annotations: dict[int, list[dict]], newest_run_id: int | None
) -> tuple[bool, str]:
    """Whether to rerun the run's failed jobs, and why: `run` and `jobs` are its first
    attempt, `annotations` each job's check-run annotations by job id, `newest_run_id` the
    newest CI run of a pull request's branch (None for another event)."""
    if run.get("run_attempt") != 1:
        return False, f"attempt {run.get('run_attempt')}: only a first attempt is rerun"
    if run.get("conclusion") != "failure":
        return False, f"the run's conclusion is {run.get('conclusion')}, not failure"
    odd = unsuccessful(jobs)
    if not odd:
        return False, "no job but ci-ok failed"
    other = [job for job in odd if not got_no_runner(job, annotations.get(job["id"], []))]
    if other:
        named = ", ".join(f"{job['name']} ({job.get('conclusion')})" for job in other)
        return False, f"not only jobs that got no runner: {named}"
    if run.get("event") == "pull_request" and newest_run_id != run.get("id"):
        return False, f"a newer CI run of the pull request exists: {newest_run_id}"
    named = ", ".join(job["name"] for job in odd)
    return True, f"got no runner: {named}"


def gh(*args: str):
    """`gh <args>`; for `gh api`, its JSON output parsed."""
    if args[0] != "api":
        subprocess.run(["gh", *args], check=True)
        return None
    out = subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def main(argv: list[str], gh=gh) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_id", type=int)
    parser.add_argument("--rerun", action="store_true", help="rerun the failed jobs")
    args = parser.parse_args(argv)
    rid = args.run_id

    latest_attempt = gh("api", f"{REPO}actions/runs/{rid}")["run_attempt"]
    run = gh("api", f"{REPO}actions/runs/{rid}/attempts/1")
    jobs = gh("api", f"{REPO}actions/runs/{rid}/attempts/1/jobs?per_page=100")["jobs"]
    annotations = {
        job["id"]: gh("api", f"{REPO}check-runs/{job['id']}/annotations")
        for job in unsuccessful(jobs)
    }
    newest = None
    if run.get("event") == "pull_request":
        branch = quote(run["head_branch"], safe="")
        found = gh(
            "api",
            f"{REPO}actions/workflows/ci.yml/runs?event=pull_request&branch={branch}&per_page=1",
        )["workflow_runs"]
        newest = found[0]["id"] if found else None

    rerun, reason = verdict(run, jobs, annotations, newest)
    if latest_attempt != 1:
        reason += f"; the run is on attempt {latest_attempt} now"
    if not args.rerun:
        print(f"{'would rerun' if rerun else 'would not rerun'} run {rid}: {reason}")
        return 0
    if rerun and latest_attempt == 1:
        print(f"rerunning run {rid}: {reason}")
        gh("run", "rerun", str(rid), "--failed")
    else:
        print(f"not rerunning run {rid}: {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
