""".github/workflows/release.yml: a tag's release, checked against its last release candidate
and LADO's telemetry token checked before it is built (scripts/release_check.py,
scripts/check_telemetry.py, docs/release.md)."""

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def steps() -> list[dict]:
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]["pypi"]["steps"]


def index(predicate) -> int:
    return next(i for i, step in enumerate(steps()) if predicate(step))


def test_the_checkout_has_every_tag_and_the_history():
    checkout = steps()[index(lambda s: s.get("uses", "").startswith("actions/checkout@"))]
    assert checkout["with"]["fetch-depth"] == 0


def test_the_release_check_runs_after_the_version_check_and_before_the_build():
    check = index(lambda s: "scripts/release_check.py" in s.get("run", ""))
    assert steps()[check]["run"].strip() == 'python3 scripts/release_check.py "$GITHUB_REF_NAME"'
    assert index(lambda s: "uv version --short" in s.get("run", "")) < check
    assert check < index(lambda s: s.get("run") == "make dist")


def test_the_telemetry_check_runs_after_the_version_check_and_before_the_build():
    check = index(lambda s: "scripts/check_telemetry.py" in s.get("run", ""))
    assert steps()[check]["run"].strip() == "uv run python scripts/check_telemetry.py"
    assert index(lambda s: "uv version --short" in s.get("run", "")) < check
    assert check < index(lambda s: s.get("run") == "make dist")
    assert check < index(lambda s: s.get("run") == "uv publish")
