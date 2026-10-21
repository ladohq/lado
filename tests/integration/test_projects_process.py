"""`lado project` and the default workspace as the human meets them: the CLI as its own
process, real folders and git, HOME in tmp_path and no LADO_REPOS (openspec change
projects-in-core)."""

import os
import subprocess
import sys

import fake_provider
import pytest
from agent_helpers import bare_remote, init_repo, wait_for

from lado import runtime, state

pytestmark = pytest.mark.integration


@pytest.fixture
def home(tmp_path, monkeypatch):
    """The human's home in tmp_path, without LADO_REPOS: the workspace is <home>/workspace."""
    folder = tmp_path / "home"
    folder.mkdir()
    monkeypatch.setenv("HOME", str(folder))
    monkeypatch.delenv("LADO_REPOS", raising=False)
    return folder


def lado(*args: str, **env: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(fake_provider.LADO), *args],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, **env},
    )


def doctor_line(name: str, **env: str) -> str | None:
    out = lado("doctor", **env).stdout
    return next((line for line in out.splitlines() if f"] {name}: " in line), None)


def test_the_workspace_in_doctor_with_and_without_lado_repos(home, tmp_path):
    ws = home / "workspace"
    assert doctor_line("Workspace") == (
        f"[info] Workspace: {ws} (default), not made yet: the first clone or project makes it"
    )
    assert doctor_line("Projects") is None
    code = tmp_path / "code"
    code.mkdir()
    assert (
        doctor_line("Workspace", LADO_REPOS=str(code)) == f"[ok  ] Workspace: {code} (LADO_REPOS)"
    )
    assert doctor_line("Workspace", LADO_REPOS="code") == (
        f"[warn] Workspace: LADO_REPOS is not an absolute path: code; LADO uses {ws}"
    )
    assert not ws.exists()  # doctor makes nothing


def test_create_list_show_rename_and_delete(home):
    ws = home / "workspace"
    made = lado("project", "create", "shop", "--title", "Shop")
    folder = ws / "projects" / "shop"
    assert (made.returncode, made.stdout) == (0, f'Made project shop "Shop": {folder}\n')
    assert folder.is_dir()
    listed = lado("project", "list")
    assert (listed.returncode, listed.stdout) == (0, f"shop  Shop  {folder}\n")
    shown = lado("project", "show", "shop")
    assert shown.stdout.splitlines()[:2] == ['shop "Shop"', f"  folder:  {folder}"]
    assert lado("project", "rename", "shop", "Shop EU").stdout == 'shop: title "Shop EU"\n'
    assert doctor_line("Projects") == f"[ok  ] Projects: 1 in {ws / 'projects'}"
    assert doctor_line("Workspace") == f"[ok  ] Workspace: {ws} (default)"
    assert lado("project", "delete", "shop").returncode == 1
    assert folder.is_dir()
    deleted = lado("project", "delete", "shop", "--yes")
    assert (deleted.returncode, deleted.stdout) == (0, "Deleted project shop\n")
    assert not folder.exists() and (ws / "projects").is_dir()
    assert (
        lado("project", "list").stdout == "No projects. Make one with: lado project create <id>\n"
    )


def test_every_refusal_of_create_makes_nothing(home):
    projects_dir = home / "workspace" / "projects"
    bad = lado("project", "create", "Shop")
    assert bad.returncode == 1 and "lado: the project id Shop is not valid" in bad.stderr
    assert not (home / "workspace").exists()
    (projects_dir / "notes").mkdir(parents=True)
    own = lado("project", "create", "shop")
    assert own.returncode == 1
    assert own.stderr == (
        f"lado: {projects_dir} is your own folder (it holds notes): LADO keeps projects there "
        "only; move it away or set LADO_REPOS to another workspace\n"
    )
    assert sorted(p.name for p in projects_dir.iterdir()) == ["notes"]
    (projects_dir / "notes").rename(home / "notes")
    (projects_dir / "shop").mkdir()
    exists = lado("project", "create", "shop")
    assert exists.returncode == 1 and exists.stderr.startswith(
        f"lado: {projects_dir / 'shop'} already exists"
    )
    (projects_dir / "shop").rmdir()
    assert lado("project", "create", "shop").returncode == 0
    taken = lado("project", "create", "shop")
    assert (taken.returncode, taken.stderr) == (1, "lado: project shop exists\n")
    assert [p.id for p in state.list_projects()] == ["shop"]


def test_doctor_names_foreign_and_missing_folders_and_the_humans_projects(home):
    projects_dir = home / "workspace" / "projects"
    (projects_dir / "notes").mkdir(parents=True)
    assert doctor_line("Projects") == (
        f"[warn] Projects: {projects_dir} is your own folder (it holds notes): LADO cannot make "
        "projects there"
    )
    (projects_dir / "notes").rename(home / "notes")
    assert lado("project", "create", "shop").returncode == 0
    assert lado("project", "create", "acme").returncode == 0
    (projects_dir / "acme").rmdir()
    (projects_dir / "old").mkdir()
    assert doctor_line("Projects") == (
        f"[warn] Projects: acme: folder not found {projects_dir / 'acme'}; foreign folder in "
        "projects/: old"
    )
    listed = lado("project", "list").stdout.splitlines()
    assert listed[0].endswith(f"{projects_dir / 'acme'}  (folder not found)")


def test_an_agent_reads_projects_but_cannot_change_them(home):
    assert lado("project", "create", "shop").returncode == 0
    agent = {"LADO_SESSION": "s", "LADO_AGENT": "w1"}
    for args in (["create", "acme"], ["rename", "shop", "X"], ["delete", "shop", "--yes"]):
        refused = lado("project", *args, **agent)
        assert refused.returncode == 1
        assert (
            refused.stderr
            == f'lado: lado project {args[0]} is for the human; agent "w1" cannot use it\n'
        )
    assert lado("project", "list", **agent).returncode == 0
    assert lado("project", "show", "shop", **agent).returncode == 0
    assert [(p.id, p.title) for p in state.list_projects()] == [("shop", None)]
    assert (home / "workspace" / "projects" / "shop").is_dir()


def test_delete_shows_unpushed_work_and_needs_yes(home):
    assert lado("project", "create", "shop").returncode == 0
    folder = home / "workspace" / "projects" / "shop"
    repo = init_repo(folder / "frontend")
    (repo / "new.txt").write_text("x")
    subprocess.run(["git", "-C", str(repo), "branch", "feature-x"], check=True)
    (home / "workspace" / "projects" / "acme").mkdir()  # a sibling: never touched
    refused = lado("project", "delete", "shop")
    assert refused.returncode == 1
    assert refused.stdout.splitlines() == [
        f"Unpushed work in {folder}:",
        "  frontend: uncommitted changes; branch feature-x not pushed; branch main not pushed",
    ]
    assert "run again with --yes" in refused.stderr
    assert (repo / "new.txt").exists() and state.get_project("shop")
    assert lado("project", "delete", "shop", "--yes").returncode == 0
    assert not folder.exists() and state.get_project("shop") is None
    assert (home / "workspace" / "projects" / "acme").is_dir()


def test_a_clone_with_no_folder_goes_into_the_default_workspace(home, tmp_path):
    url = bare_remote(tmp_path)
    started = lado("start", url, "--provider", "fake", "--no-attach")
    folder = home / "workspace" / "app"
    try:
        assert started.returncode == 0, started.stderr
        assert runtime.branch(str(folder)) == "main"
        sess = state.get_session("app")
        assert sess is not None and sess.repo == os.path.realpath(folder)

        def idle():
            agent = state.get_agent("app", "supervisor")
            return agent is not None and agent.status == state.IDLE

        wait_for(idle, "the supervisor idle in the clone", "app")
    finally:
        if state.get_session("app"):
            runtime.stop_session("app")
