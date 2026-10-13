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


def jobs() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]


def test_the_release_notes_are_checked_before_anything_is_built_or_published():
    check = index(lambda s: "scripts/release_notes.py" in s.get("run", ""))
    assert steps()[check]["run"].strip() == (
        'python3 scripts/release_notes.py "$GITHUB_REF_NAME" > /dev/null'
    )
    assert index(lambda s: "uv version --short" in s.get("run", "")) < check
    assert check < index(lambda s: s.get("run") == "make dist")
    assert check < index(lambda s: s.get("run") == "uv publish")


def test_the_files_published_to_pypi_go_to_the_github_release():
    upload = index(lambda s: s.get("uses", "").startswith("actions/upload-artifact@"))
    assert steps()[upload]["with"]["path"] == "dist/"
    assert steps()[upload]["with"]["if-no-files-found"] == "error"
    assert index(lambda s: s.get("run") == "make dist") < upload
    release = jobs()["github-release"]["steps"]
    (download,) = [s for s in release if s.get("uses", "").startswith("actions/download-artifact@")]
    assert download["with"]["name"] == steps()[upload]["with"]["name"]
    assert download["with"]["path"] == "dist"


def test_the_github_release_comes_only_after_pypi_accepted_the_release():
    job = jobs()["github-release"]
    assert job["needs"] == "pypi"
    assert job["permissions"] == {"contents": "write"}
    assert jobs()["pypi"]["permissions"] == {"id-token": "write"}
    (create,) = [s for s in job["steps"] if "gh release create" in s.get("run", "")]
    run = create["run"]
    assert 'scripts/release_notes.py "$GITHUB_REF_NAME"' in run
    assert 'scripts/release_notes.py --flag "$GITHUB_REF_NAME"' in run
    assert "--verify-tag" in run and "--notes-file" in run and "dist/*" in run
    assert create["env"]["GH_TOKEN"] == "${{ github.token }}"
