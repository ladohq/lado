import os
import shutil
import subprocess

import agent_helpers
from agent_helpers import init_repo


def _config(repo, key, *scope):
    result = subprocess.run(
        ["git", "-C", str(repo), "config", *scope, "--get", key], capture_output=True, text=True
    )
    return result.stdout.strip()


def test_copies_of_the_template_skip_lock_files_that_vanish(tmp_path, monkeypatch):
    # git's background maintenance holds .git/objects/maintenance.lock in the template for a
    # moment: the copy lists the file, and it is gone when the copy reads it.
    monkeypatch.setattr(agent_helpers, "_template", None)
    init_repo(tmp_path / "first")  # makes a fresh template
    template = agent_helpers._template
    (template / ".git" / "objects" / "maintenance.lock").write_text("")
    copyfile = shutil.copyfile

    def vanishing(src, dst, *args, **kwargs):
        if os.fspath(src).endswith(".lock"):
            (template / ".git" / "objects" / "maintenance.lock").unlink(missing_ok=True)
        return copyfile(src, dst, *args, **kwargs)

    monkeypatch.setattr(shutil, "copyfile", vanishing)
    repo = init_repo(tmp_path / "second")
    assert not (repo / ".git" / "objects" / "maintenance.lock").exists()
    assert _config(repo, "user.name") == "LADO test"


def test_test_repos_never_run_git_maintenance(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_helpers, "_template", None)
    repo = init_repo(tmp_path / "repo")
    # In the repo's own config, so it holds for whatever process runs git there.
    assert _config(repo, "gc.auto", "--local") == "0"
    assert _config(repo, "maintenance.auto", "--local") == "false"
    # And for every other repo the test run makes (bare remotes, kit source clones).
    other = tmp_path / "other.git"
    subprocess.run(["git", "init", "-q", "--bare", str(other)], check=True)
    assert _config(other, "gc.auto") == "0"
    assert _config(other, "maintenance.auto") == "false"
