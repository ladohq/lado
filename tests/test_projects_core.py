"""lado.projects: the workspace and projects in it (openspec change projects-in-core)."""

import os
import subprocess
from pathlib import Path

import pytest
from agent_helpers import init_repo

from lado import projects, runtime, state


@pytest.fixture
def home(home_workspace, tmp_path, monkeypatch):
    """HOME in tmp_path and no LADO_REPOS: the workspace is <tmp>/workspace."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LADO_REPOS", raising=False)
    return tmp_path


def test_the_workspace_is_lado_repos_when_absolute(home, monkeypatch):
    monkeypatch.setenv("LADO_REPOS", "~/code")
    assert projects.workspace() == home / "code"
    assert projects.workspace_source() == "LADO_REPOS"
    monkeypatch.setenv("LADO_REPOS", "/srv/repos")
    assert projects.workspace() == Path("/srv/repos")


@pytest.mark.parametrize("value", [None, "", "code", "./code"])
def test_else_the_workspace_is_home_workspace(home, monkeypatch, value):
    if value is not None:
        monkeypatch.setenv("LADO_REPOS", value)
    assert projects.workspace() == home / "workspace"
    assert projects.workspace_source() == ("ignored" if value else "default")
    assert not (home / "workspace").exists()  # never made by asking


# Ids, titles and the folder

BAD_ID = (
    "the project id {} is not valid: lowercase Latin letters, digits and -, starting with a "
    "letter or digit, at most 40 characters"
)


@pytest.mark.parametrize("id", ["a", "shop", "shop-eu", "a1", "1a", "x" * 40])
def test_a_good_id(id):
    projects.check_id(id)


@pytest.mark.parametrize("id", ["Shop", "-a", "shop_eu", "ш", "", "x" * 41, "a b", "a/b", ".."])
def test_a_bad_id(id):
    with pytest.raises(projects.ProjectError) as refused:
        projects.check_id(id)
    assert str(refused.value) == BAD_ID.format(id)


def test_create_makes_the_record_and_the_folder(home):
    made = projects.create("shop", "  Shop ")
    folder = home / "workspace" / "projects" / "shop"
    assert folder.is_dir() and list(folder.iterdir()) == []
    assert (made.id, made.title) == ("shop", "Shop")
    assert state.get_project("shop") == made
    assert projects.folder("shop") == folder
    assert projects.create("acme", "acme").title is None  # equal to the id: none
    assert projects.create("site", None).title is None


def _nothing_made(home, id="shop", before=()):
    assert state.get_project(id) is None
    projects_dir = home / "workspace" / "projects"
    if projects_dir.exists():
        assert sorted(p.name for p in projects_dir.iterdir()) == sorted(before)


def test_create_refuses_a_bad_id_a_bad_title_and_a_taken_id(home):
    with pytest.raises(projects.ProjectError, match="is not valid"):
        projects.create("Shop", None)
    with pytest.raises(runtime.LadoError, match="a title is at most"):
        projects.create("shop", "x" * 81)
    _nothing_made(home)
    assert not (home / "workspace").exists()
    projects.create("shop", None)
    with pytest.raises(projects.ProjectError) as refused:
        projects.create("shop", "Again")
    assert str(refused.value) == "project shop exists"
    assert state.get_project("shop").title is None


def test_create_refuses_an_existing_folder(home):
    target = home / "workspace" / "projects" / "shop"
    target.mkdir(parents=True)
    (target / "notes.txt").write_text("mine")
    with pytest.raises(projects.ProjectError) as refused:
        projects.create("shop", None)
    assert str(refused.value) == (
        f"{target} already exists: LADO makes a project's folder itself; choose another id "
        "or move that folder away"
    )
    _nothing_made(home, before=["shop"])
    assert (target / "notes.txt").read_text() == "mine"


def test_create_refuses_a_dangling_link_of_the_name(home):
    folder = home / "workspace" / "projects"
    folder.mkdir(parents=True)
    (folder / "shop").symlink_to(home / "gone")
    with pytest.raises(projects.ProjectError, match="already exists"):
        projects.create("shop", None)
    _nothing_made(home, before=["shop"])


def test_create_refuses_the_humans_own_projects_folder(home):
    folder = home / "workspace" / "projects"
    folder.mkdir(parents=True)
    for name in ("notes", "drafts", "old", "zeta"):
        (folder / name).mkdir()
    with pytest.raises(projects.ProjectError) as refused:
        projects.create("shop", None)
    assert str(refused.value) == (
        f"{folder} is your own folder (it holds drafts, notes, old, …): LADO keeps projects "
        "there only; move it away or set LADO_REPOS to another workspace"
    )
    _nothing_made(home, before=["notes", "drafts", "old", "zeta"])


def test_hidden_entries_do_not_make_projects_the_humans(home):
    folder = home / "workspace" / "projects"
    folder.mkdir(parents=True)
    (folder / ".DS_Store").write_text("")
    assert projects.owned_by_human() is None
    projects.create("shop", None)
    assert (folder / "shop").is_dir()


def test_a_foreign_folder_beside_a_project_does_not_block(home):
    projects.create("shop", None)
    old = home / "workspace" / "projects" / "old"
    old.mkdir()
    (old / "keep.txt").write_text("x")
    assert projects.owned_by_human() is None
    assert projects.foreign() == ["old"]
    projects.create("acme", None)
    assert projects.foreign() == ["old"]
    assert (old / "keep.txt").read_text() == "x"


def test_a_file_in_projects_is_foreign_too(home):
    projects.create("shop", None)
    (home / "workspace" / "projects" / "README").write_text("x")
    assert projects.foreign() == ["README"]


def test_no_foreign_entries_without_projects_or_a_projects_folder(home):
    assert projects.owned_by_human() is None
    assert projects.foreign() == []
    (home / "workspace" / "projects").mkdir(parents=True)
    assert projects.owned_by_human() is None  # empty: not the human's


@pytest.mark.parametrize("kind", ["file", "folder"])
def test_create_refuses_a_workspace_that_is_no_usable_folder(home, monkeypatch, kind):
    target = home / "srv-notes"
    if kind == "file":
        target.write_text("")
        expected = f"LADO_REPOS is not a folder: {target}"
    else:
        target.mkdir()
        (target / "projects").write_text("")  # projects/ itself a file: its mkdir fails
        expected = None
    monkeypatch.setenv("LADO_REPOS", str(target))
    with pytest.raises(projects.ProjectError) as refused:
        projects.create("shop", None)
    if expected:
        assert str(refused.value) == expected
    assert state.get_project("shop") is None


def test_a_failing_mkdir_leaves_no_record(home, monkeypatch):
    mkdir = Path.mkdir

    def refuse(self, *args, **kwargs):
        if self.name != "shop":
            return mkdir(self, *args, **kwargs)
        raise PermissionError(13, "Permission denied", str(self))

    monkeypatch.setattr(Path, "mkdir", refuse)
    with pytest.raises(projects.ProjectError, match="Permission denied"):
        projects.create("shop", None)
    assert state.get_project("shop") is None


def test_rename(home):
    projects.create("shop", "Shop")
    assert projects.rename("shop", "  Shop EU ") == "Shop EU"
    assert state.get_project("shop").title == "Shop EU"
    assert projects.rename("shop", "") is None
    assert projects.rename("shop", "shop") is None
    assert state.get_project("shop").title is None
    assert (home / "workspace" / "projects" / "shop").is_dir()
    with pytest.raises(projects.NoSuchProject) as refused:
        projects.rename("nope", "x")
    assert str(refused.value) == 'unknown project "nope"'


def test_listed_marks_a_folder_not_found(home, monkeypatch):
    projects.create("shop", "Shop")
    projects.create("acme", None)
    (home / "workspace" / "projects" / "acme").rmdir()
    listed = projects.listed()
    assert [(p.id, folder, found) for p, folder, found in listed] == [
        ("acme", home / "workspace" / "projects" / "acme", False),
        ("shop", home / "workspace" / "projects" / "shop", True),
    ]
    monkeypatch.setenv("LADO_REPOS", str(home / "b"))  # another workspace
    assert [found for _, _, found in projects.listed()] == [False, False]
    assert projects.listed()[1][1] == home / "b" / "projects" / "shop"


def test_names_lists_three_then_an_ellipsis():
    assert projects.names(["b", "a"]) == "a, b"
    assert projects.names(["d", "c", "b", "a"]) == "a, b, c, …"


# The unpushed scan and delete


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )
    return done.stdout


@pytest.fixture
def shop(home, git_config):
    """The project shop, its folder holding the repository frontend, pushed and clean."""
    projects.create("shop", "Shop")
    folder = projects.folder("shop")
    remote = home / "frontend.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    repo = init_repo(folder / "frontend")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "-u", "origin", "main")
    return folder


def test_a_pushed_clean_repository_is_nothing_unpushed(shop):
    (shop / "notes").mkdir()  # a folder that is no repository: not looked at
    assert projects.unpushed(shop) == []


def test_uncommitted_changes_and_branches_not_pushed(shop):
    repo = shop / "frontend"
    (repo / "new.txt").write_text("x")  # untracked counts
    _git(repo, "branch", "feature-x")
    assert projects.unpushed(shop) == ["frontend: uncommitted changes; branch feature-x not pushed"]


def test_a_branch_ahead_of_its_upstream(shop):
    repo = shop / "frontend"
    _git(repo, "commit", "-q", "--allow-empty", "-m", "more")
    assert projects.unpushed(shop) == ["frontend: branch main not pushed"]


def test_a_worktree_with_work_of_its_own(shop):
    repo = shop / "frontend"
    tree = repo / ".lado" / "worktrees" / "s" / "w"
    _git(repo, "worktree", "add", "-q", str(tree), "-b", "w")
    (tree / "work.txt").write_text("x")
    assert projects.unpushed(shop) == [
        "frontend: uncommitted changes; branch w not pushed",
        "frontend (worktree frontend/.lado/worktrees/s/w): uncommitted changes",
    ]


def test_a_worktree_outside_the_folder_is_named_by_its_full_path(shop, home):
    repo = shop / "frontend"
    tree = home / "elsewhere"
    _git(repo, "worktree", "add", "-q", "--detach", str(tree))
    (tree / "work.txt").write_text("x")
    assert projects.unpushed(shop) == [f"frontend (worktree {tree}): uncommitted changes"]


def test_a_repository_git_cannot_read(shop):
    broken = shop / "broken"
    broken.mkdir()
    (broken / ".git").write_text("gitdir: /nowhere\n")
    [line] = projects.unpushed(shop)
    assert line.startswith("broken: could not check: fatal: ")


def test_delete_needs_yes(shop):
    with pytest.raises(projects.ProjectError) as refused:
        projects.delete("shop", yes=False)
    assert str(refused.value) == (
        f"deleting project shop removes its folder {shop} with everything in it; "
        "run again with --yes"
    )
    assert shop.is_dir() and state.get_project("shop")


def test_delete_with_yes_removes_the_folder_then_the_record(shop, home):
    projects.create("acme", None)
    (shop / "frontend" / "new.txt").write_text("x")
    outside = home / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("x")
    (shop / "link").symlink_to(outside)  # a link inside: removed as a link
    projects.delete("shop", yes=True)
    assert not os.path.lexists(shop)
    assert state.get_project("shop") is None
    assert (home / "workspace" / "projects" / "acme").is_dir() and state.get_project("acme")
    assert (outside / "keep.txt").read_text() == "x"


def test_a_project_folder_that_is_a_link_loses_the_link_only(home):
    projects.create("shop", None)
    target = projects.folder("shop")
    target.rmdir()
    elsewhere = home / "srv-shop"
    elsewhere.mkdir()
    (elsewhere / "a.txt").write_text("x")
    target.symlink_to(elsewhere)
    projects.delete("shop", yes=True)
    assert not os.path.lexists(target)
    assert (elsewhere / "a.txt").read_text() == "x"
    assert state.get_project("shop") is None


def test_delete_refuses_a_folder_outside_projects(home, monkeypatch):
    projects.create("shop", None)
    elsewhere = home / "workspace" / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setattr(
        projects, "folder", lambda id: projects.projects_folder() / ".." / "elsewhere"
    )
    with pytest.raises(projects.ProjectError, match="LADO removes nothing outside it"):
        projects.delete("shop", yes=True)
    assert elsewhere.is_dir() and state.get_project("shop")


def test_a_project_whose_folder_is_gone_loses_its_record_only(home):
    projects.create("shop", None)
    projects.folder("shop").rmdir()
    projects.delete("shop", yes=True)
    assert state.get_project("shop") is None
    assert (home / "workspace" / "projects").is_dir()


def test_a_folder_not_removed_whole_keeps_the_record(home, monkeypatch):
    projects.create("shop", None)

    def fail(path, *args, **kwargs):
        raise PermissionError(13, "Permission denied", str(Path(path) / "locked"))

    monkeypatch.setattr(projects.shutil, "rmtree", fail)
    with pytest.raises(projects.ProjectError) as refused:
        projects.delete("shop", yes=True)
    assert str(refused.value).startswith(f"could not remove {projects.folder('shop')} whole: ")
    assert "locked" in str(refused.value) and str(refused.value).endswith("; the project stays")
    assert state.get_project("shop")


def test_delete_of_an_unknown_project(home):
    with pytest.raises(projects.NoSuchProject, match='unknown project "nope"'):
        projects.delete("nope", yes=True)
