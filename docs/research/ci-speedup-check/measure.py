#!/usr/bin/env python3
"""Measure CI before and after its speedup of 2026-11-09 (LAD-252): a pull request's wait,
the critical path, the browser and the image steps with their caches, the runner queue,
the Actions cache, time limits, flakes and reruns.

Research evidence for docs/research/ci-speedup-check.md, run by hand with python3.
Standard library only. It reads GitHub through `gh` (`gh api` without a method, a GET)
and changes nothing there. It prints Markdown tables for one window of CI runs, so the
same measurement can be repeated after the next change of CI:

    python3 measure.py --since 2026-11-05T21:00Z --until 2026-11-09T12:30Z --job-set old
    python3 measure.py --since 2026-11-09T12:30Z --until 2026-11-13T00:00Z --job-set new
    python3 measure.py --caches          # the Actions cache as it is now

Definitions (those of the baseline of 2026-11-09, the LADO session artifact ci-analysis):
- wait: the last `completed_at` of a run's first-attempt jobs minus the run's
  `created_at`, for runs whose first attempt is green (every job success or skipped);
- queue: a job's `started_at - created_at`; running jobs: the jobs of any workflow of the
  repository started and not completed at a moment (GitHub's limit counts them all);
- a flake: a run whose first attempt failed a job and whose later attempt passed (a
  rerun keeps the run's commit); no runner: a job cancelled with no step and no
  `runner_name`;
- a browser cache hit: the restore step logs "Cache restored from key"; a download: the
  step `Browser` logs `apt-get update` or `Get:` lines (a fast miss and a slow hit look
  alike in timings);
- a Docker layer cache hit: the step `Image` logs `CACHED` layers.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

# Each job's `timeout-minutes` in ci.yml since LAD-248 (before, GitHub's 360), by the job
# name's first word; the step Browser has its own 10 minutes.
TIME_LIMITS = {
    "unit": 15,
    "integration": 15,
    "web": 15,
    "ui": 25,
    "changes": 5,
    "smoke": 20,
    "container": 30,
    "ci-ok": 5,
}
BROWSER_LIMIT = 10

# The tests of the flake tasks closed before the window "after": did they fail again?
# With the commit that fixed each (None: not known), so a failure on a commit without the
# fix is not counted as a recurrence.
KNOWN_FLAKES = {
    "LAD-236": ("aea2ae56", ["test_human_messages.py::test_a_stop_as_the_message_is_typed"]),
    "LAD-246": ("87a4d7bd", ["LoginSheet.test.tsx"]),
    "LAD-188": (
        None,
        [
            "Launch.test.tsx",
            "test_session_model.py::test_a_worker_of_another_cli_runs_its_default_and_says_so",
        ],
    ),
    "LAD-245": (None, ["test_launch_model.py::test_tab_walks_the_list_s_foot_with_the_keyboard"]),
    "LAD-210": ("cb76505d", ["ModelCards.test.tsx"]),
}

QUEUE_BUCKETS = [(0, 9), (10, 19), (20, 29), (30, 39), (40, 59), (60, 10**6)]

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
STAMP = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ?")


def parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def window_time(text: str) -> datetime:
    """`YYYY-MM-DD` (midnight UTC) or an ISO time; a time without a zone is UTC."""
    moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def seconds(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    return (parse_time(end) - parse_time(start)).total_seconds()


def median(values: list[float]) -> float:
    return statistics.median(values) if values else float("nan")


def p90(values: list[float]) -> float:
    """Nearest rank: the smallest value with at least 90% of the values at or below it."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    return ordered[math.ceil(0.9 * len(ordered)) - 1]


def mins(value: float) -> str:
    return "-" if math.isnan(value) else f"{value / 60:.1f}"


def secs(value: float) -> str:
    return "-" if math.isnan(value) else f"{value:.0f}"


def share(part: int, whole: int) -> str:
    return f"{part} ({100 * part / whole:.1f} %)" if whole else f"{part}"


def table(header: list[str], rows: list[list[object]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


class GitHub:
    """Read-only access through `gh`: `gh api` without a method is a GET."""

    def __init__(self, repo: str, cache: str | None):
        self.repo = repo
        self.cache = cache
        if cache:
            os.makedirs(cache, exist_ok=True)

    def _cached(self, key: str) -> str | None:
        if not self.cache:
            return None
        return os.path.join(self.cache, re.sub(r"[^A-Za-z0-9_.-]+", "_", key)[:200])

    def _gh(self, args: list[str]) -> str | None:
        for attempt in range(4):  # GitHub answers a large list with a 502 now and then
            out = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
            if out.returncode == 0:
                return out.stdout
            if "HTTP 404" in out.stderr or "HTTP 410" in out.stderr:
                return None  # a log GitHub no longer keeps
            if "HTTP 5" not in out.stderr and "rate limit" not in out.stderr:
                break
            time.sleep(5 * (attempt + 1))
        sys.exit(f"gh {' '.join(args)} failed: {out.stderr.strip()}")

    def get(self, endpoint: str, keep: bool = True) -> dict:
        path = self._cached(endpoint + ".json") if keep else None
        if path and os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        text = self._gh(["api", f"repos/{self.repo}/{endpoint}"])
        data = json.loads(text) if text else {}
        if path:
            with open(path, "w") as f:
                json.dump(data, f)
        return data

    def log(self, job_id: int) -> str:
        """A job's log, its time stamps and colours removed; empty when GitHub has none."""
        path = self._cached(f"log-{job_id}.txt")
        if path and os.path.exists(path):
            with open(path) as f:
                return f.read()
        text = self._gh(
            ["api", "--allow-escape-sequences", f"repos/{self.repo}/actions/jobs/{job_id}/logs"]
        )
        text = "\n".join(STAMP.sub("", ANSI.sub("", line)) for line in (text or "").splitlines())
        if path:
            with open(path, "w") as f:
                f.write(text)
        return text

    def runs(self, since: datetime, until: datetime) -> list[dict]:
        """Every run of every workflow created in [since, until), a day per query (GitHub
        returns at most 1000 runs for one)."""
        found: dict[int, dict] = {}
        day = since.replace(hour=0, minute=0, second=0, microsecond=0)
        while day < until:
            page = 1
            while True:
                data = self.get(
                    f"actions/runs?created={day:%Y-%m-%d}&per_page=100&page={page}",
                    keep=day + timedelta(days=1) < datetime.now(timezone.utc),
                )
                for run in data.get("workflow_runs", []):
                    if since <= parse_time(run["created_at"]) < until:
                        found[run["id"]] = run
                if len(data.get("workflow_runs", [])) < 100:
                    break
                page += 1
            day += timedelta(days=1)
        return sorted(found.values(), key=lambda run: run["created_at"])

    def jobs(self, run: dict) -> list[dict]:
        """The jobs of all the run's attempts."""
        done = run["status"] == "completed"
        found, page = [], 1
        while True:
            data = self.get(
                f"actions/runs/{run['id']}/jobs?filter=all&per_page=100&page={page}", keep=done
            )
            found += data.get("jobs", [])
            if len(data.get("jobs", [])) < 100:
                return found
            page += 1

    def contains(self, sha: str, commit: str) -> bool:
        """Whether `sha` has `commit` in its history."""
        status = self.get(f"compare/{commit}...{sha}").get("status")
        return status in ("ahead", "identical")

    def caches(self) -> list[dict]:
        found, page = [], 1
        while True:
            data = self.get(f"actions/caches?per_page=100&page={page}", keep=False)
            found += data["actions_caches"]
            if len(data["actions_caches"]) < 100:
                return found
            page += 1


def step(job: dict, name: str) -> dict | None:
    """The step of that name, else the first whose name starts with it."""
    items = job.get("steps") or []
    for item in items:
        if item["name"] == name:
            return item
    for item in items:
        if item["name"].startswith(name):
            return item
    return None


def step_seconds(job: dict, name: str) -> float | None:
    item = step(job, name)
    return seconds(item.get("started_at"), item.get("completed_at")) if item else None


def section(log: str, marker: str) -> list[str]:
    """The lines of the step whose `##[group]Run ...` line holds `marker`, up to the next
    step's."""
    lines, inside = [], False
    for line in log.splitlines():
        if line.startswith("##[group]Run "):
            if inside:
                break
            inside = marker in line
        if inside:
            lines.append(line)
    return lines


def image_section(log: str) -> list[str]:
    """The step Image: `make docker` alone before LAD-249, the cache flags first after it."""
    return section(log, 'write="--cache-to') or section(log, "make docker")


def family(job_name: str) -> str:
    return job_name.split(" ")[0]


def first_attempt(jobs: list[dict]) -> list[dict]:
    return [job for job in jobs if job.get("run_attempt", 1) == 1]


def is_green(jobs: list[dict]) -> bool:
    return bool(jobs) and all(job["conclusion"] in ("success", "skipped") for job in jobs)


def no_runner(job: dict) -> bool:
    return job["conclusion"] == "cancelled" and not job.get("steps") and not job.get("runner_name")


def job_set(jobs: list[dict]) -> str:
    names = {job["name"] for job in jobs}
    if {"web", "ui (1)", "ui (2)", "ui (3)", "ui (4)"} <= names:
        return "new"
    if {"ui (1)", "ui (2)"} <= names and "web" not in names and "ui (3)" not in names:
        return "old"
    return "other"


def ran(job: dict) -> bool:
    return bool(job.get("started_at")) and job["conclusion"] not in ("skipped", None)


def measure(gh: GitHub, args: argparse.Namespace) -> None:
    since, until = window_time(args.since), window_time(args.until)
    # Running jobs at a moment of the window count the runs started a little before it.
    every = gh.runs(since - timedelta(hours=3), until)
    ci_path = f".github/workflows/{args.workflow}"
    with ThreadPoolExecutor(args.workers) as pool:
        all_jobs = {
            run["id"]: jobs for run, jobs in zip(every, pool.map(gh.jobs, every), strict=True)
        }

    runs, left_out = [], Counter()
    for run in every:
        if run["path"] != ci_path or parse_time(run["created_at"]) < since:
            continue
        kind = job_set(first_attempt(all_jobs[run["id"]]))
        if args.job_set != "any" and kind != args.job_set:
            left_out[(run["event"], kind)] += 1
            continue
        runs.append(run)
    jobs_of = {run["id"]: all_jobs[run["id"]] for run in runs}

    print(f"# CI from {since:%Y-%m-%d %H:%M} to {until:%Y-%m-%d %H:%M} UTC\n")
    print(f"Workflow `{args.workflow}`, job set `{args.job_set}`, repository `{gh.repo}`.\n")
    events = Counter(run["event"] for run in runs)
    print(table(["Event", "Runs measured"], [[e, n] for e, n in events.most_common()]))
    if left_out:
        print("\nLeft out for their job set:")
        print(table(["Event", "Job set", "Runs"], [[e, k, n] for (e, k), n in left_out.items()]))

    # 1. The wait for a green first attempt.
    print("\n## 1. Wait for a green first attempt (minutes)\n")
    rows, green = [], {}
    smoke_split = defaultdict(list)
    for event in ["pull_request", "push", "schedule"]:
        waits = []
        for run in runs:
            first = first_attempt(jobs_of[run["id"]])
            if run["event"] != event or not is_green(first):
                continue
            done = [job for job in first if job.get("completed_at")]
            last = max(done, key=lambda job: job["completed_at"])
            waits.append(seconds(run["created_at"], last["completed_at"]))
            green[run["id"]] = first
            if event == "pull_request":
                smoke = any(family(job["name"]) == "smoke" and ran(job) for job in first)
                smoke_split["smoke ran" if smoke else "smoke skipped"].append(waits[-1])
        all_of_event = sum(1 for run in runs if run["event"] == event)
        rows.append(
            [event, f"{len(waits)} of {all_of_event}", mins(median(waits)), mins(p90(waits))]
        )
    for label, waits in sorted(smoke_split.items()):
        rows.append([f"pull_request, {label}", len(waits), mins(median(waits)), mins(p90(waits))])
    print(table(["Event", "Green first attempts", "Median", "p90"], rows))

    # 2. The critical path: the job that ends a green pull request run.
    print("\n## 2. Critical path: the last job of a green pull request run\n")
    last_jobs, durations = Counter(), defaultdict(list)
    for run in runs:
        first = green.get(run["id"])
        if run["event"] != "pull_request" or not first:
            continue
        done = [job for job in first if job["name"] != "ci-ok" and job.get("completed_at")]
        last = max(done, key=lambda job: job["completed_at"])
        last_jobs[last["name"]] += 1
        durations[last["name"]].append(seconds(last["started_at"], last["completed_at"]))
    total = sum(last_jobs.values())
    print(
        table(
            ["Last job", "Runs", "Its median (min)"],
            [
                [name, share(n, total), mins(median(durations[name]))]
                for name, n in last_jobs.most_common()
            ],
        )
    )
    by_family = Counter()
    for name, n in last_jobs.items():
        by_family[family(name)] += n
    print(
        "\nBy job family: "
        + ", ".join(f"{k} {share(n, total)}" for k, n in by_family.most_common())
    )

    print("\n### Jobs of green first attempts, all events (minutes)\n")
    per_job, per_queue = defaultdict(list), defaultdict(list)
    for first in green.values():
        for job in first:
            if ran(job):
                per_job[job["name"]].append(seconds(job["started_at"], job["completed_at"]))
                per_queue[job["name"]].append(seconds(job["created_at"], job["started_at"]))
    order = sorted(per_job, key=lambda name: -median(per_job[name]))
    print(
        table(
            ["Job", "n", "Median", "p90", "Queue median", "Queue p90"],
            [
                [
                    name,
                    len(per_job[name]),
                    mins(median(per_job[name])),
                    mins(p90(per_job[name])),
                    mins(median(per_queue[name])),
                    mins(p90(per_queue[name])),
                ]
                for name in order
            ],
        )
    )

    all_ci_jobs = [job for run in runs for job in jobs_of[run["id"]]]
    event_of = {run["id"]: run["event"] for run in runs}

    # 3. The browser step of the UI jobs.
    print("\n## 3. Browser step of the UI jobs (all attempts, the step ran)\n")
    ui_jobs = [
        job
        for job in all_ci_jobs
        if family(job["name"]) == "ui"
        and (step(job, "Browser") or step(job, "Run uv run playwright install"))
    ]
    ui_logs = logs_of(gh, ui_jobs, args.workers)
    rows = []
    for event in ["pull_request", "push", "schedule"]:
        took, hits, restores, downloads, no_log = [], 0, 0, 0, 0
        for job in ui_jobs:
            if event_of[job["run_id"]] != event:
                continue
            name = "Browser" if step(job, "Browser") else "Run uv run playwright install"
            value = step_seconds(job, name)
            if value is None:
                continue
            took.append(value)
            log = ui_logs[job["id"]]
            if not log:
                no_log += 1
                continue
            if "Cache restored from key: ui-browser-" in log:
                hits += 1
            if "input keys: ui-browser-" in log or "Cache restored from key: ui-browser-" in log:
                restores += 1
            marker = 'if [ "$HIT" = true ]' if name == "Browser" else "playwright install"
            lines = section(log, marker)
            if any("apt-get update" in line or re.match(r"(Get|Hit):\d+ ", line) for line in lines):
                downloads += 1
        if took:
            with_log = len(took) - no_log
            rows.append(
                [
                    event,
                    len(took),
                    f"{hits} of {restores}",
                    f"{downloads} of {with_log}",
                    secs(median(took)),
                    secs(p90(took)),
                    secs(max(took)),
                    share(sum(1 for t in took if t > 60), len(took)),
                    sum(1 for t in took if t >= BROWSER_LIMIT * 60 - 5),
                ]
            )
    print(
        table(
            [
                "Event",
                "Jobs",
                "Cache hit of restores",
                "apt downloads",
                "Median s",
                "p90 s",
                "Max s",
                "Over 60 s",
                f"At its {BROWSER_LIMIT} min limit",
            ],
            rows,
        )
    )

    # 4. The step Image of the container jobs.
    print("\n## 4. Step `Image` of the container jobs (seconds; all attempts, the step ran)\n")
    image_jobs = [
        job for job in all_ci_jobs if family(job["name"]) == "container" and step(job, "Image")
    ]
    image_jobs = [
        job
        for job in image_jobs
        if step(job, "Image")["conclusion"] in ("success", "failure")
        and step_seconds(job, "Image") is not None
    ]
    image_logs = logs_of(gh, image_jobs, args.workers)
    groups = defaultdict(list)
    for job in image_jobs:
        arch = "arm64" if "arm64" in job["name"] else "amd64"
        flags = "yes" if section(image_logs[job["id"]], 'write="--cache-to') else "no"
        groups[(arch, event_of[job["run_id"]], flags)].append(job)
    rows = []
    for (arch, event, flags), group in sorted(groups.items()):
        took = [step_seconds(job, "Image") for job in group]
        cached, misses, slow = [], 0, 0
        for job in group:
            log = image_logs[job["id"]]
            if not log:
                continue
            count = sum(1 for line in image_section(log) if re.match(r"#\d+ CACHED", line))
            cached.append(count)
            misses += count == 0
            slow += step_seconds(job, "Image") > 60
        rows.append(
            [
                arch,
                event,
                flags,
                len(group),
                secs(median(took)),
                secs(p90(took)),
                secs(max(took)),
                f"{secs(median(cached))} ({len(cached)} logs)",
                f"{misses} of {len(cached)}",
                f"{slow} of {len(cached)}",
            ]
        )
    print(
        table(
            [
                "Arch",
                "Event",
                "Cache flags",
                "Jobs",
                "Median",
                "p90",
                "Max",
                "CACHED layers, median",
                "No CACHED layer",
                "Over 60 s",
            ],
            rows,
        )
    )
    print("\nThe daily run (schedule) builds from nothing:\n")
    rows = []
    for job in sorted(image_jobs, key=lambda j: j["started_at"]):
        if event_of[job["run_id"]] == "schedule":
            item = step(job, "Image")
            rows.append(
                [
                    job["started_at"][:16],
                    job["name"],
                    secs(step_seconds(job, "Image")),
                    item["conclusion"],
                ]
            )
    print(table(["Started", "Job", "Image s", "Result"], rows) if rows else "None in the window.")

    # 5. The queue, against the jobs already running (every workflow).
    print("\n## 5. Queue: job created to started, by the jobs running when it was created\n")
    spans = []
    for run_jobs in all_jobs.values():
        for job in run_jobs:
            if job.get("started_at") and job.get("completed_at") and not no_runner(job):
                mac = any("macos" in label for label in job.get("labels") or [])
                spans.append((parse_time(job["started_at"]), parse_time(job["completed_at"]), mac))
    starts = sorted((s, e, m) for s, e, m in spans)
    window_jobs = [
        job
        for run_jobs in all_jobs.values()
        for job in run_jobs
        if job.get("started_at")
        and not no_runner(job)
        and job["conclusion"] != "skipped"
        and since <= parse_time(job["created_at"]) < until
    ]

    # A job runs at t when it started at or before t and completed after it.
    bounds = {
        mac_only: (
            sorted(s for s, _, m in starts if m or not mac_only),
            sorted(e for _, e, m in starts if m or not mac_only),
        )
        for mac_only in (False, True)
    }

    def running(moment: datetime, mac_only: bool = False) -> int:
        begun, ended = bounds[mac_only]
        return bisect.bisect_right(begun, moment) - bisect.bisect_right(ended, moment)

    def on_mac(job: dict) -> bool:
        return any("macos" in label for label in job.get("labels") or [])

    rows, at = [], {}
    for job in window_jobs:
        at[job["id"]] = running(parse_time(job["created_at"]))
    print("Linux jobs (the limit of concurrent jobs; macOS has its own, below):\n")
    for low, high in QUEUE_BUCKETS:
        waits = [
            seconds(job["created_at"], job["started_at"])
            for job in window_jobs
            if low <= at[job["id"]] <= high and not on_mac(job)
        ]
        label = f"{low}+" if high > 10**5 else f"{low}-{high}"
        rows.append(
            [
                label,
                len(waits),
                secs(median(waits)),
                secs(p90(waits)),
                share(sum(1 for w in waits if w > 60), len(waits)) if waits else "-",
            ]
        )
    print(
        table(["Running jobs", "Jobs created", "Queue p50 s", "Queue p90 s", "Waited > 60 s"], rows)
    )
    crowded = sum(1 for job in window_jobs if at[job["id"]] >= 20)
    print(f"\nJobs created with 20 or more running: {share(crowded, len(window_jobs))}.")
    window_spans = [(s, e, m) for s, e, m in spans if since <= s < until]
    peak = max((running(s) for s, _, _ in window_spans), default=0)
    peak_mac = max((running(s, mac_only=True) for s, _, m in window_spans if m), default=0)
    print(f"Peak of running jobs: {peak} (macOS: {peak_mac}).")
    for system, is_mac in (("Linux", False), ("macOS", True)):
        waits = [
            seconds(job["created_at"], job["started_at"])
            for job in window_jobs
            if on_mac(job) == is_mac
        ]
        print(
            f"{system}: {len(waits)} jobs, queue p50 {secs(median(waits))} s, "
            f"p90 {secs(p90(waits))} s, "
            f"waited > 60 s {share(sum(1 for w in waits if w > 60), len(waits))}."
        )

    # 6. Evidence of evicted cache entries in pull request runs (the list: --caches).
    print("\n## 6. Cache misses in pull request runs (an evicted entry shows here)\n")
    # A job whose restore never ran (a branch made before LAD-248's cache step or LAD-249's,
    # a job cancelled before the step) has no cache to miss.
    hit, miss = (
        "Cache restored from key: ui-browser-",
        "Cache not found for input keys: ui-browser-",
    )
    ui_pr = [j for j in ui_jobs if event_of[j["run_id"]] == "pull_request" and ui_logs[j["id"]]]
    ui_step = [j for j in ui_pr if hit in ui_logs[j["id"]] or miss in ui_logs[j["id"]]]
    ui_miss = [j for j in ui_step if miss in ui_logs[j["id"]]]
    img_pr = [
        j for j in image_jobs if event_of[j["run_id"]] == "pull_request" and image_logs[j["id"]]
    ]
    img_step = [
        j
        for j in img_pr
        if section(image_logs[j["id"]], 'write="--cache-to')
        and step(j, "Image")["conclusion"] == "success"
    ]
    img_miss = [
        j
        for j in img_step
        if not any(re.match(r"#\d+ CACHED", line) for line in image_section(image_logs[j["id"]]))
    ]
    print(
        f"Browser cache not restored: {share(len(ui_miss), len(ui_step))} UI jobs with the cache "
        f"restore ({len(ui_pr) - len(ui_step)} more without it: an older branch, or cancelled)."
    )
    keys = Counter(
        line.split("input keys: ")[1]
        for j in ui_miss
        for line in ui_logs[j["id"]].splitlines()
        if miss in line
    )
    for key, n in keys.most_common():
        print(f"- not found: `{key}` {n}")
    print(
        f"No Docker layer CACHED: {share(len(img_miss), len(img_step))} container jobs with the "
        f"cache flags and a built image ({len(img_pr) - len(img_step)} more without them)."
    )
    for label, missed in (("browser", ui_miss), ("Docker", img_miss)):
        if missed:
            days = Counter(j["started_at"][:10] for j in missed)
            print(
                f"{label} misses by day: " + ", ".join(f"{d} {n}" for d, n in sorted(days.items()))
            )

    # 7. Time limits.
    print("\n## 7. Time limits (ci.yml's since LAD-248)\n")
    near, measured = Counter(), Counter()
    suspects = [
        job
        for job in all_ci_jobs
        if ran(job) and job.get("completed_at") and family(job["name"]) in TIME_LIMITS
    ]
    for job in suspects:
        limit = TIME_LIMITS[family(job["name"])] * 60
        took = seconds(job["started_at"], job["completed_at"])
        measured[family(job["name"])] += 1
        if took >= 0.8 * limit:
            near[family(job["name"])] += 1
    failed = [job for job in suspects if job["conclusion"] in ("failure", "cancelled")]
    failed_logs = logs_of(gh, failed, args.workers)
    timed_out = [
        job
        for job in failed
        if "exceeded the maximum execution time" in failed_logs[job["id"]]
        or "has timed out after" in failed_logs[job["id"]]
    ]
    # GitHub keeps no log of a job it cancelled at its limit: the time tells.
    no_log = [
        job
        for job in failed
        if not failed_logs[job["id"]]
        and seconds(job["started_at"], job["completed_at"]) >= TIME_LIMITS[family(job["name"])] * 60
    ]
    print(
        table(
            ["Job family", "Limit min", "Jobs", "Above 80 % of the limit"],
            [
                [name, TIME_LIMITS[name], measured[name], near[name]]
                for name in TIME_LIMITS
                if measured[name]
            ],
        )
    )
    print(
        f"\nJobs ended by a time limit (their log says so): {len(timed_out)}"
        + (
            ": " + ", ".join(f"{j['name']} run {j['run_id']}" for j in timed_out)
            if timed_out
            else "."
        )
    )
    print(
        f"Jobs cancelled at or past their limit with no log kept: {len(no_log)}"
        + (
            ": "
            + ", ".join(
                f"{j['name']} run {j['run_id']} after "
                f"{mins(seconds(j['started_at'], j['completed_at']))} min"
                for j in no_log
            )
            if no_log
            else "."
        )
    )

    # 8. Reruns, flakes and the tests that failed.
    print("\n## 8. Reruns and flakes\n")
    kinds, tests, flaky_runs = Counter(), defaultdict(list), []
    finished = [run for run in runs if run["status"] == "completed"]
    red_first, main_red = Counter(), []
    for run in finished:
        run_jobs = jobs_of[run["id"]]
        attempts = max(job.get("run_attempt", 1) for job in run_jobs)
        # ci-ok only follows the others: its red is never the cause.
        red = [
            job
            for job in first_attempt(run_jobs)
            if job["conclusion"] in ("failure", "cancelled", "timed_out") and job["name"] != "ci-ok"
        ]
        if red and run["conclusion"] != "cancelled":
            red_first[run["event"]] += 1
        if attempts == 1:
            # main is green unless a change broke it: its red without a rerun is listed too.
            failed = [job for job in red if job["conclusion"] == "failure"]
            if failed and run["event"] != "pull_request":
                main_red.append((run, failed))
            continue
        passed = run["conclusion"] == "success"
        failed = [job for job in red if job["conclusion"] == "failure"]
        if red and all(no_runner(job) for job in red):
            kinds["no runner (not acquired, or stuck in the queue)"] += 1
        elif failed and passed:
            kinds["flake: a failed job passed on rerun"] += 1
            flaky_runs.append((run, failed))
        elif red and passed:
            kinds["a job cancelled while running, passed on rerun"] += 1
            cancelled = ", ".join(
                f"{job['name']} after {mins(seconds(job['started_at'], job['completed_at']))} min"
                for job in red
            )
            print(f"Run {run['id']}: {cancelled}, no failed step.")
        elif passed:
            kinds["rerun of a green first attempt"] += 1
        else:
            kinds["rerun still red"] += 1
    reruns = sum(kinds.values())
    print(
        f"Runs with more than one attempt: {share(reruns, len(finished))} of the finished runs.\n"
    )
    print(table(["Why", "Runs"], [[k, n] for k, n in kinds.most_common()]))
    print(
        "\nRuns whose first attempt was red (not cancelled as superseded): "
        + ", ".join(f"{event} {n}" for event, n in red_first.most_common())
    )

    red_jobs = [job for _, red in flaky_runs + main_red for job in red]
    logs = logs_of(gh, red_jobs, args.workers)
    rows = []
    for run, red in flaky_runs + main_red:
        for job in red:
            names = failed_tests(logs[job["id"]])
            for name in names:
                tests[name].append(run)
            failing = next(
                (s["name"] for s in job.get("steps") or [] if s["conclusion"] == "failure"), "-"
            )
            rows.append(
                [
                    run["id"],
                    run["event"],
                    "rerun green" if (run, red) in flaky_runs else "not rerun",
                    job["name"],
                    failing[:50],
                    "; ".join(names) or "(no test named)",
                ]
            )
    if rows:
        print("\nThe failed jobs of the flaky runs and of main's red runs (first attempt):\n")
        print(table(["Run", "Event", "Rerun", "Job", "Failed step", "Failed tests"], rows))
    print("\nKnown flakes of closed tasks, failed again in those runs:\n")
    rows = []
    for task, (fix, patterns) in KNOWN_FLAKES.items():
        for pattern in patterns:
            failed_in = [run for name, found in tests.items() if pattern in name for run in found]
            with_fix = [run for run in failed_in if fix and gh.contains(run["head_sha"], fix)]
            rows.append(
                [
                    task,
                    pattern,
                    len(failed_in),
                    f"{len(with_fix)} (fix {fix})" if fix else "fix commit not known",
                ]
            )
    print(table(["Task", "Test", "Failures", "Of them on a commit with the fix"], rows))


def logs_of(gh: GitHub, jobs: list[dict], workers: int) -> dict[int, str]:
    ids = [job["id"] for job in jobs]
    with ThreadPoolExecutor(workers) as pool:
        return dict(zip(ids, pool.map(gh.log, ids), strict=True))


def failed_tests(log: str) -> list[str]:
    """The tests a job's log names as failed: pytest's summary lines and vitest's FAIL."""
    found = []
    for line in log.splitlines():
        line = line.strip()
        match = re.match(r"(?:FAILED|ERROR) (tests/\S+::\S+)", line)
        if match:
            found.append(match.group(1))
            continue
        match = re.match(r"FAIL\s+(src/\S+\.test\.tsx?)\s+>\s+(.+)", line)
        if match:
            found.append(f"{match.group(1)} > {match.group(2).split(' > ')[0]}")
    return sorted(set(found))


def caches(gh: GitHub) -> None:
    usage = gh.get("actions/cache/usage", keep=False)
    entries = gh.caches()
    print(f"# Actions cache of `{gh.repo}` at {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC\n")
    size = usage["active_caches_size_in_bytes"]
    print(f"Used: {size / 1e9:.2f} GB of 10 GB in {usage['active_caches_count']} entries.\n")

    def kind(key: str) -> str:
        if key.startswith("setup-uv-"):
            return "setup-uv"
        if key.startswith("node-cache-"):
            return "setup-node (npm)"
        if key.startswith("ui-browser-"):
            return "browser (ui)"
        if key.startswith("buildkit-blob-") or key.startswith("index-container-"):
            return "Docker layers (buildkit)"
        return "other"

    groups = defaultdict(list)
    for entry in entries:
        ref = "main" if entry["ref"] == "refs/heads/main" else "pull requests"
        groups[(kind(entry["key"]), ref)].append(entry)
    rows = []
    for (name, ref), group in sorted(
        groups.items(), key=lambda item: -sum(e["size_in_bytes"] for e in item[1])
    ):
        rows.append(
            [
                name,
                ref,
                len(group),
                f"{sum(e['size_in_bytes'] for e in group) / 1e9:.2f}",
                min(e["created_at"] for e in group)[:16],
                min(e["last_accessed_at"] for e in group)[:16],
            ]
        )
    print(table(["Family", "Ref", "Entries", "GB", "Oldest created", "Oldest last access"], rows))
    keys = sorted({e["key"] for e in entries if kind(e["key"]) == "browser (ui)"})
    print("\nBrowser keys: " + (", ".join(f"`{key}`" for key in keys) or "none"))
    scopes = Counter(
        e["key"].split("-")[2] for e in entries if e["key"].startswith("index-container-")
    )
    print(
        "Docker cache indexes per architecture: "
        + ", ".join(f"{k} {n}" for k, n in sorted(scopes.items()))
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--since", help="window start, YYYY-MM-DD or ISO time (UTC)")
    parser.add_argument("--until", help="window end, exclusive, YYYY-MM-DD or ISO time (UTC)")
    parser.add_argument(
        "--job-set",
        choices=["new", "old", "any"],
        default="any",
        help="only runs of the job set after LAD-248 (ui 1-4 and web), before it (ui 1-2, no "
        "web), or any; the runs left out are counted",
    )
    parser.add_argument(
        "--caches", action="store_true", help="print the Actions cache as it is now"
    )
    parser.add_argument("--repo", default="ladohq/lado", help="GitHub repository (owner/name)")
    parser.add_argument("--workflow", default="ci.yml", help="workflow file of the CI")
    parser.add_argument(
        "--cache-dir", help="keep GitHub's answers and job logs here, to run again without fetching"
    )
    parser.add_argument("--workers", type=int, default=8, help="parallel requests to GitHub")
    args = parser.parse_args()
    gh = GitHub(args.repo, args.cache_dir)
    if args.caches:
        caches(gh)
        return
    if not args.since or not args.until:
        parser.error("--since and --until are required unless --caches")
    measure(gh, args)


if __name__ == "__main__":
    main()
