""".github/workflows/release.yml: a tag's release, checked against its last release candidate
and LADO's telemetry token checked before it is built (scripts/release_check.py,
scripts/check_telemetry.py, docs/release.md), and LADO's image tested on each architecture
before anything is published (openspec capability image-release)."""

from pathlib import Path

import yaml

from lado import update

ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def steps() -> list[dict]:
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]["build"]["steps"]


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


def jobs() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]


def test_the_release_notes_are_checked_before_anything_is_built_or_published():
    check = index(lambda s: "scripts/release_notes.py" in s.get("run", ""))
    assert steps()[check]["run"].strip() == (
        'python3 scripts/release_notes.py "$GITHUB_REF_NAME" > /dev/null'
    )
    assert index(lambda s: "uv version --short" in s.get("run", "")) < check
    assert check < index(lambda s: s.get("run") == "make dist")


def test_the_files_published_to_pypi_go_to_the_github_release():
    upload = index(lambda s: s.get("uses", "").startswith("actions/upload-artifact@"))
    assert steps()[upload]["with"]["path"] == "dist/"
    assert steps()[upload]["with"]["if-no-files-found"] == "error"
    assert index(lambda s: s.get("run") == "make dist") < upload
    release = jobs()["github-release"]["steps"]
    (download,) = [s for s in release if s.get("uses", "").startswith("actions/download-artifact@")]
    assert download["with"]["name"] == steps()[upload]["with"]["name"]
    assert download["with"]["path"] == "dist"


def needs(job: str) -> set[str]:
    found = jobs()[job].get("needs", [])
    return {found} if isinstance(found, str) else set(found)


def test_nothing_is_published_before_both_images_passed():
    """A red image cell stops the release: PyPI, the image's tags and the GitHub release all
    wait for it."""
    assert needs("image") == {"build"}
    assert needs("pypi") == {"build", "image"}
    assert needs("image-tags") == {"pypi", "image"}
    assert needs("github-release") == {"image-tags"}
    assert not any("uv publish" in s.get("run", "") for s in jobs()["build"]["steps"])
    assert [s["run"] for s in jobs()["pypi"]["steps"] if "run" in s] == ["uv publish"]


def test_the_image_is_built_on_each_architectures_runner():
    strategy = jobs()["image"]["strategy"]
    assert {(c["arch"], c["runner"]) for c in strategy["matrix"]["include"]} == {
        ("amd64", "ubuntu-24.04"),
        ("arm64", "ubuntu-24.04-arm"),
    }
    assert jobs()["image"]["runs-on"] == "${{ matrix.runner }}"
    assert strategy["fail-fast"] is True


def image_steps() -> list[dict]:
    return jobs()["image"]["steps"]


def at(steps: list[dict], predicate) -> int:
    return next(i for i, step in enumerate(steps) if predicate(step))


def test_the_image_job_tests_the_very_image_it_pushes():
    """One build, two outputs: loaded for the tests and pushed by digest, untagged. Only a
    digest whose cell passed gets a tag (image-tags)."""
    steps = image_steps()
    build = at(steps, lambda s: "docker buildx build" in s.get("run", ""))
    tests = at(steps, lambda s: "scripts/smoke_ci.py container" in s.get("run", ""))
    digest = at(
        steps,
        lambda s: (
            s.get("uses", "").startswith("actions/upload-artifact@")
            and (s["with"]["name"] == "digest-${{ matrix.arch }}")
        ),
    )
    assert build < tests < digest
    run = steps[build]["run"]
    assert run.count("docker buildx build") == 1
    assert '--output "type=docker,name=lado:release"' in run
    assert (
        f'--output "type=image,name={update.IMAGE},push-by-digest=true,name-canonical=true,'
        'push=true"'
    ) in run
    assert "--metadata-file" in run
    assert "--label org.opencontainers.image.source=https://github.com/ladohq/lado" in run
    assert steps[tests]["env"]["LADO_TEST_IMAGE"] == "lado:release"
    assert steps[tests]["run"].strip() == (
        'uv run python scripts/smoke_ci.py container "$RUNNER_TEMP/container"'
    )
    assert any(s.get("run") == "uv sync --locked" for s in steps[:tests])
    download = at(steps, lambda s: s.get("uses", "").startswith("actions/download-artifact@"))
    assert download < build
    assert steps[download]["with"] == {"name": "dist", "path": "dist"}
    evidence = [s for s in steps if s.get("with", {}).get("name") == "container-${{ matrix.arch }}"]
    assert [s.get("if") for s in evidence] == ["always()"]


def test_the_image_gets_its_tags_only_from_the_tested_digests():
    run = "\n".join(s.get("run", "") for s in jobs()["image-tags"]["steps"])
    assert 'scripts/release_notes.py --flag "$GITHUB_REF_NAME"' in run
    assert '= "--latest"' in run and f"{update.IMAGE}:latest" in run
    assert "docker buildx imagetools create" in run
    assert f'"{update.IMAGE}@$(cat "$RUNNER_TEMP/digests/amd64")"' in run
    assert f'"{update.IMAGE}@$(cat "$RUNNER_TEMP/digests/arm64")"' in run
    assert "imagetools inspect" in run
    assert "linux/amd64" in run and "linux/arm64" in run
    downloads = [
        s for s in jobs()["image-tags"]["steps"]
        if s.get("uses", "").startswith("actions/download-artifact@")
    ]  # fmt: skip
    assert [d["with"] for d in downloads] == [
        {"pattern": "digest-*", "merge-multiple": True, "path": "${{ runner.temp }}/digests"}
    ]


def test_the_image_tag_is_the_version_of_the_git_tag():
    for job in ("image", "image-tags"):
        run = "\n".join(s.get("run", "") for s in jobs()[job]["steps"])
        assert 'version="${GITHUB_REF_NAME#v}"' in run, job


def test_the_image_is_lados_by_name_everywhere_in_the_workflow():
    text = WORKFLOW.read_text()
    assert text.count("ghcr.io/") == text.count(update.IMAGE) > 0


def test_only_the_job_token_and_packages_write_only_where_it_pushes():
    text = WORKFLOW.read_text()
    assert "secrets." not in text
    for job in ("image", "image-tags"):
        assert jobs()[job]["permissions"] == {"contents": "read", "packages": "write"}, job
        logins = [s for s in jobs()[job]["steps"] if "docker login" in s.get("run", "")]
        assert len(logins) == 1, job
        assert 'docker login ghcr.io -u "$GITHUB_ACTOR" --password-stdin' in logins[0]["run"]
        assert logins[0]["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert jobs()["build"]["permissions"] == {"contents": "read"}
    assert "packages" not in str(jobs()["pypi"]) + str(jobs()["github-release"])


def test_the_github_release_comes_only_after_pypi_accepted_the_release():
    job = jobs()["github-release"]
    assert job["needs"] == "image-tags"
    assert job["permissions"] == {"contents": "write"}
    assert jobs()["pypi"]["permissions"] == {"id-token": "write"}
    (create,) = [s for s in job["steps"] if "gh release create" in s.get("run", "")]
    run = create["run"]
    assert 'scripts/release_notes.py "$GITHUB_REF_NAME"' in run
    assert 'scripts/release_notes.py --flag "$GITHUB_REF_NAME"' in run
    assert "--verify-tag" in run and "--notes-file" in run and "dist/*" in run
    assert create["env"]["GH_TOKEN"] == "${{ github.token }}"
