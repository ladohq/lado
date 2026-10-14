#!/usr/bin/env python3
"""Measure the way to a merge into main (LAD-58): CI time, CI runs per pull request,
failures, time from a pull request's opening to its merge, and time per flow state.

Research evidence for docs/research/merge-path.md, run by hand with python3. Standard
library only. It reads GitHub through `gh` (only `gh api` GET calls and `gh pr list`)
and, when given, a copy of LADO's lado.db opened read-only. It changes nothing on GitHub
or in the database, and prints Markdown tables.

    python3 measure.py --since 2026-10-11 --until 2026-10-14 \\
        --split 2026-10-13T16:00:00Z --db /tmp/lado-copy.db
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone


def parse_time(text: str) -> datetime:
    """A GitHub time (`...Z`) or a lado.db time (`YYYY-MM-DD HH:MM:SS.fff`, UTC)."""
    text = text.replace("Z", "+00:00").replace(" ", "T")
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def day(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def window_end(text: str) -> datetime:
    """A day is included whole; an ISO time is the window's exclusive end."""
    if len(text) == len("YYYY-MM-DD"):
        return day(text) + timedelta(days=1)
    return parse_time(text)


def shown(moment: datetime) -> str:
    return f"{moment:%Y-%m-%d %H:%M} UTC"


def minutes(seconds: float) -> str:
    return f"{seconds / 60:.1f}"


def median(values: list[float]) -> float:
    return statistics.median(values) if values else float("nan")


def p90(values: list[float]) -> float:
    """Nearest rank: the smallest value with at least 90% of the values at or below it."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    return ordered[math.ceil(0.9 * len(ordered)) - 1]


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

    def _gh(self, args: list[str]) -> object:
        path = None
        if self.cache:
            key = re.sub(r"[^A-Za-z0-9_.-]+", "_", " ".join(args))[:200]
            path = os.path.join(self.cache, key + ".json")
            if os.path.exists(path):
                with open(path) as f:
                    return json.load(f)
        for attempt in range(3):  # GitHub answers a large job list with a 502 now and then
            out = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
            if out.returncode == 0 or "HTTP 5" not in out.stderr:
                break
            time.sleep(2 * (attempt + 1))
        if out.returncode != 0:
            sys.exit(f"gh {' '.join(args)} failed: {out.stderr.strip()}")
        data = json.loads(out.stdout)
        if path:
            with open(path, "w") as f:
                json.dump(data, f)
        return data

    def get(self, endpoint: str) -> dict:
        return self._gh(["api", f"repos/{self.repo}/{endpoint}"])

    def runs(self, workflow: str, since: datetime, until: datetime) -> list[dict]:
        created = f"{since:%Y-%m-%d}..{(until - timedelta(microseconds=1)):%Y-%m-%d}"
        found, page = [], 1
        while True:
            data = self.get(
                f"actions/workflows/{workflow}/runs?created={created}&per_page=100&page={page}"
            )
            found += data["workflow_runs"]
            if len(data["workflow_runs"]) < 100:
                return found
            page += 1

    def jobs(self, run: dict) -> list[dict]:
        """Every attempt's jobs, one attempt at a time (a long `filter=all` list of a run
        rerun many times gets 502 for its later pages)."""
        found = []
        for attempt in range(1, run["run_attempt"] + 1):
            found += self.get(f"actions/runs/{run['id']}/attempts/{attempt}/jobs?per_page=100")[
                "jobs"
            ]
        return found

    def files(self, number: int) -> list[str]:
        found, page = [], 1
        while True:
            data = self._gh(
                ["api", f"repos/{self.repo}/pulls/{number}/files?per_page=100&page={page}"]
            )
            found += [f["filename"] for f in data]
            if len(data) < 100:
                return found
            page += 1

    def pulls(self) -> list[dict]:
        fields = "number,title,headRefName,createdAt,mergedAt,closedAt,author"
        return self._gh(
            ["pr", "list", "--repo", self.repo, "--state", "all", "--limit", "1000"]
            + ["--json", fields]
        )


def seconds(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    return (parse_time(end) - parse_time(start)).total_seconds()


def first_attempt_wall(run: dict, jobs: list[dict]) -> float | None:
    """From the run's creation to the end of its first attempt's last job."""
    first = [j for j in jobs if j["run_attempt"] == 1]
    if not first or any(not j["completed_at"] for j in first):
        return None
    return seconds(run["created_at"], max(j["completed_at"] for j in first))


def failing_step(job: dict) -> str:
    bad = [s["name"] for s in job.get("steps") or [] if s.get("conclusion") == "failure"]
    return bad[0] if bad else "?"


def ci_section(gh: GitHub, args: argparse.Namespace, since: datetime, until: datetime) -> None:
    runs = [
        r
        for r in gh.runs(args.workflow, since, until)
        if r["status"] == "completed" and since <= parse_time(r["created_at"]) < until
    ]
    runs.sort(key=lambda r: r["created_at"])
    jobs = {r["id"]: gh.jobs(r) for r in runs}
    split = parse_time(args.split) if args.split else None
    window = f"{shown(since)} to {shown(until)}"

    print(f"## CI runs ({args.workflow}, {window})\n")
    print(
        f"{len(runs)} completed runs; {sum(r['run_attempt'] > 1 for r in runs)} with more "
        f"than one attempt ({sum(r['run_attempt'] - 1 for r in runs)} reruns).\n"
    )

    # Wall time of the first attempt, before and after the split.
    periods: dict[str, list[float]] = defaultdict(list)
    for r in runs:
        wall = first_attempt_wall(r, jobs[r["id"]])
        if wall is None or r["conclusion"] == "cancelled":
            continue
        if split is None:
            name = "all"
        elif parse_time(r["created_at"]) < split:
            name = f"before {args.split}"
        else:
            name = f"from {args.split}"
        periods[name].append(wall)
    print("### CI wall time (first attempt: run created to its last job's end)\n")
    print(
        table(
            ["Period", "Runs", "Median, min", "p90, min"],
            [[k, len(v), minutes(median(v)), minutes(p90(v))] for k, v in periods.items()],
        )
    )
    print("\nCancelled runs are left out.\n")

    def after_split(run: dict) -> bool:
        return split is None or parse_time(run["created_at"]) >= split

    late = [r for r in runs if after_split(r)]
    by_job: dict[str, list[dict]] = defaultdict(list)
    for r in late:
        for j in jobs[r["id"]]:
            if j["conclusion"] == "success":
                by_job[j["name"]].append(j)
    since_text = f" from {args.split}" if split else ""
    print(f"### Successful jobs{since_text}, minutes\n")
    rows = []
    for name, found in sorted(by_job.items()):
        run_time = [seconds(j["started_at"], j["completed_at"]) for j in found]
        queue = [seconds(j["created_at"], j["started_at"]) for j in found]
        rows.append(
            [
                name,
                len(found),
                minutes(median(run_time)),
                minutes(p90(run_time)),
                minutes(median(queue)),
                minutes(p90(queue)),
            ]
        )
    print(table(["Job", "Jobs", "Median", "p90", "Queue median", "Queue p90"], rows))

    print(f"\n### Steps of successful jobs{since_text} (median, at least 10 s), seconds\n")
    steps: dict[tuple[str, str], list[float]] = defaultdict(list)
    for name, found in by_job.items():
        group = re.sub(r"^smoke (\S+) .*$", r"smoke \1", name)
        for j in found:
            for s in j.get("steps") or []:
                took = seconds(s.get("started_at"), s.get("completed_at"))
                if took is not None and s.get("conclusion") == "success":
                    steps[(group, s["name"])].append(took)
    step_rows = [
        [group, step, len(v), round(median(v)), round(max(v))]
        for (group, step), v in steps.items()
        if median(v) >= 10
    ]
    step_rows.sort(key=lambda row: (row[0], -row[3]))
    print(table(["Job", "Step", "Samples", "Median", "Max"], step_rows))

    print("\n### Failed jobs by name (all attempts)\n")
    failed: Counter = Counter()
    failed_late: Counter = Counter()
    failed_steps: dict[str, Counter] = defaultdict(Counter)
    total: Counter = Counter()
    for r in runs:
        for j in jobs[r["id"]]:
            total[j["name"]] += 1
            if j["conclusion"] == "failure":
                failed[j["name"]] += 1
                failed_late[j["name"]] += after_split(r)
                failed_steps[j["name"]][failing_step(j)] += 1
    print(
        table(
            ["Job", "Jobs run", "Failed", f"Failed{since_text}", "Failing step"],
            [
                [
                    name,
                    total[name],
                    n,
                    failed_late[name],
                    "; ".join(f"{s} ({c})" for s, c in failed_steps[name].most_common()),
                ]
                for name, n in failed.most_common()
            ],
        )
    )

    print(f"\n### Each failed job{since_text}\n")
    print("Green later: a later attempt of the same run has this job green (a rerun passed).\n")
    rows = []
    for r in late:
        for j in jobs[r["id"]]:
            if j["conclusion"] != "failure":
                continue
            green_later = any(
                o["name"] == j["name"]
                and o["run_attempt"] > j["run_attempt"]
                and o["conclusion"] == "success"
                for o in jobs[r["id"]]
            )
            rows.append(
                [
                    r["created_at"][:16].replace("T", " "),
                    r["display_title"][:50].replace("|", "/"),
                    r["event"],
                    j["name"],
                    j["run_attempt"],
                    failing_step(j),
                    "yes" if green_later else "no",
                ]
            )
    print(table(["Run created", "Run", "Event", "Job", "Attempt", "Step", "Green later"], rows))

    print("\n### Pushes to main\n")
    pushes = [r for r in runs if r["event"] == "push" and r["head_branch"] == "main"]
    red = [r for r in pushes if r["conclusion"] != "success"]
    red_late = [r for r in red if after_split(r)]
    print(
        f"{len(pushes)} runs on pushes to main, {len(red)} not green "
        f"({len(red_late)}{since_text}).\n"
    )

    pr_section(gh, runs, since, until, window, args.docs_paths.split(","))
    review_section(gh, args.review_workflow, since, until, window)


def review_section(
    gh: GitHub, workflow: str, since: datetime, until: datetime, window: str
) -> None:
    """The external reviewer's runs: the workflow is skipped for comments without a request."""
    runs = [
        r
        for r in gh.runs(workflow, since, until)
        if r["status"] == "completed"
        and r["conclusion"] != "skipped"
        and since <= parse_time(r["created_at"]) < until
    ]
    took = [seconds(r["run_started_at"], r["updated_at"]) for r in runs]
    outcome = Counter(r["conclusion"] for r in runs)
    print(f"## External review runs ({workflow}, {window})\n")
    print(
        f"{len(runs)} runs not skipped ({', '.join(f'{k} {v}' for k, v in outcome.items())}); "
        f"run time median {minutes(median(took))} min, p90 {minutes(p90(took))} min.\n"
    )


def pr_section(
    gh: GitHub,
    runs: list[dict],
    since: datetime,
    until: datetime,
    window: str,
    docs_paths: list[str],
) -> None:
    pulls = [p for p in gh.pulls() if since <= parse_time(p["createdAt"]) < until]
    pulls.sort(key=lambda p: p["number"])
    by_branch: dict[str, list[dict]] = defaultdict(list)
    for r in runs:
        if r["event"] == "pull_request":
            by_branch[r["head_branch"]].append(r)
    print(f"## Pull requests opened {window}\n")
    rows, counts, docs_only = [], [], []
    for p in pulls:
        mine = by_branch.get(p["headRefName"], [])
        counts.append(len(mine))
        only_docs = all(f.startswith(tuple(docs_paths)) for f in gh.files(p["number"]))
        if only_docs:
            docs_only.append(f"#{p['number']}")
        open_min = seconds(p["createdAt"], p["mergedAt"])
        rows.append(
            [
                f"#{p['number']}",
                p["title"][:60].replace("|", "/"),
                p["author"]["login"] if p["author"]["is_bot"] else "human",
                len(mine),
                sum(r["run_attempt"] - 1 for r in mine),
                round(open_min / 60) if open_min is not None else "not merged",
                "yes" if only_docs else "",
            ]
        )
    print(
        f"{len(pulls)} pull requests; CI runs per pull request: median "
        f"{median(counts):g}, max {max(counts, default=0)}. Only paths of the docs-only "
        f"list ({', '.join(docs_paths)}): {len(docs_only)} ({', '.join(docs_only)}).\n"
    )
    human = [
        seconds(p["createdAt"], p["mergedAt"]) / 60
        for p in pulls
        if p["mergedAt"] and not p["author"]["is_bot"]
    ]
    tasks = [
        seconds(p["createdAt"], p["mergedAt"]) / 60
        for p in pulls
        if p["mergedAt"] and re.search(r"\bLAD-\d+", p["title"])
    ]
    print(
        f"Open to merge, merged pull requests not by a bot: {len(human)}, median "
        f"{median(human):.0f} min; of them naming a LAD task: {len(tasks)}, median "
        f"{median(tasks):.0f} min.\n"
    )
    print(
        table(
            ["PR", "Title", "Author", "CI runs", "Reruns", "Open to merge, min", "Docs only"],
            rows,
        )
    )
    print()


# Recommendation R2's list of paths no test reads (docs/research/merge-path.md).
DOCS_PATHS = "docs/research/,docs/superpowers/,openspec/,BACKLOG.md,ROADMAP.md"

FLOW = re.compile(r"^(\S+) -(\S+)-> (\S+)$")


def flow_section(db: str, prefix: str, since: datetime, until: datetime) -> None:
    """Minutes per state of each flow run that started in the window and ended."""
    conn = sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True)
    rows = conn.execute(
        "SELECT run, kind, detail, created_at FROM events"
        " WHERE run LIKE ? AND kind IN ('flow_start', 'flow', 'flow_end', 'flow_cancel')"
        " ORDER BY id",
        (prefix + "%",),
    ).fetchall()
    conn.close()
    runs: dict[str, list[tuple[str, str, datetime]]] = defaultdict(list)
    for run, kind, detail, created in rows:
        runs[run].append((kind, detail, parse_time(created)))
    states: list[str] = []
    table_rows, totals = [], Counter()
    for run, events in sorted(runs.items(), key=lambda item: item[1][0][2]):
        start = events[0]
        if start[0] != "flow_start" or not since <= start[2] < until:
            continue
        if events[-1][0] != "flow_end":
            continue
        spent: Counter = Counter()
        at = start[2]
        for kind, detail, moment in events[1:]:
            match = FLOW.match(detail) if kind == "flow" else None
            if match:
                spent[match.group(1)] += (moment - at).total_seconds()
                at = moment
                if match.group(1) not in states:
                    states.append(match.group(1))
        totals.update(spent)
        table_rows.append((run, spent))
    if not table_rows:
        print(f"## Time per flow state\n\nNo ended run of {prefix}* started in the window.\n")
        return
    print(f"## Time per flow state ({len(table_rows)} ended runs of {prefix}*), minutes\n")
    whole = sum(totals.values())
    body = [
        [run.split("/")[-1]]
        + [round(spent[s] / 60) for s in states]
        + [round(sum(spent.values()) / 60)]
        for run, spent in table_rows
    ]
    body.append(["share"] + [f"{100 * totals[s] / whole:.0f}%" for s in states] + [""])
    print(table(["Run"] + states + ["total"], body))
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print the merge-path measurements of LAD-58 as Markdown tables.",
    )
    parser.add_argument("--since", required=True, help="first day, YYYY-MM-DD (UTC)")
    parser.add_argument(
        "--until",
        required=True,
        help="last day, YYYY-MM-DD (UTC), included; or an ISO time, the exclusive end",
    )
    parser.add_argument("--repo", default="ladohq/lado", help="GitHub repository (owner/name)")
    parser.add_argument("--workflow", default="ci.yml", help="workflow file of the CI")
    parser.add_argument(
        "--review-workflow", default="claude.yml", help="workflow file of the external reviewer"
    )
    parser.add_argument(
        "--split", help="ISO time (e.g. 2026-10-13T16:00:00Z): CI tables before and from it"
    )
    parser.add_argument(
        "--db", help="a copy of lado.db, opened read-only; without it no flow table"
    )
    parser.add_argument(
        "--docs-paths",
        default=DOCS_PATHS,
        help="comma-separated path prefixes a docs-only pull request changes only",
    )
    parser.add_argument("--run-prefix", default="task/lad-", help="flow runs to measure")
    parser.add_argument(
        "--cache", help="folder that keeps GitHub's answers, so a second run asks nothing"
    )
    args = parser.parse_args()
    since, until = day(args.since), window_end(args.until)
    ci_section(GitHub(args.repo, args.cache), args, since, until)
    if args.db:
        flow_section(args.db, args.run_prefix, since, until)


if __name__ == "__main__":
    main()
