"""lado.projects: the workspace and projects in it (openspec change projects-in-core)."""

import os
import subprocess
from pathlib import Path

import pytest
from agent_helpers import init_repo

from lado import project_secrets, projects, runtime, state


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


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )
    return done.stdout


# The refusal of a new session inside projects/


def _refused(path) -> tuple[str, str, str | None]:
    problem = projects.refusal(str(path))
    assert problem is not None and problem.kind == "in_project"
    return str(problem), problem.hint.text, problem.hint.command


@pytest.fixture
def shop_repo(home, git_config):
    """The project shop titled Shop, with the repository frontend."""
    projects.create("shop", "Shop")
    return init_repo(projects.folder("shop") / "frontend")


IN_SHOP = "{} belongs to the project Shop: start a session in the project"
START_HINT = ("Start a session in the project:", "lado start --project shop --repo frontend")


@pytest.mark.parametrize("below", ["", "src/app", "missing/deeper"])
def test_below_a_projects_folder_is_refused_naming_the_project(shop_repo, below):
    path = shop_repo / below if below else shop_repo
    assert _refused(path) == (IN_SHOP.format(path), *START_HINT)


SHOW_HINT = ("See the project's repositories:", "lado project show shop")
ADD_HINT = "Add a repository to the project:"


def test_a_folder_without_git_in_a_project_points_at_its_repositories(shop_repo):
    notes = projects.folder("shop") / "notes"
    notes.mkdir()
    assert _refused(notes) == (IN_SHOP.format(notes), *SHOW_HINT)
    assert _refused(notes / "deeper") == (IN_SHOP.format(notes / "deeper"), *SHOW_HINT)


def _hint(path, **given) -> tuple[str, str]:
    problem = projects.refusal(str(path), **given)
    return problem.hint.text, problem.hint.command


def test_a_new_folder_of_a_project_offers_to_add_it(shop_repo):
    web = projects.folder("shop") / "web"
    assert _hint(web) == SHOW_HINT  # a session's start: no way to add
    assert _hint(web, fresh=True) == (ADD_HINT, "lado project repo add shop --new web")
    url = "https://token@github.com/shop/web.git"
    assert _hint(web, url=url) == (
        ADD_HINT,
        "lado project repo add shop https://github.com/shop/web.git",
    )
    site = projects.folder("shop") / "site"
    assert _hint(site, url=url) == (
        ADD_HINT,
        "lado project repo add shop https://github.com/shop/web.git --name site",
    )


def test_only_a_new_folder_with_a_good_name_directly_in_the_project_offers_to_add(shop_repo):
    folder = projects.folder("shop")
    (folder / "notes").mkdir()
    (folder / "file.txt").write_text("x")
    for path in [folder / "notes", folder / "file.txt", folder / "web" / "sub", folder / ".web"]:
        assert _hint(path, fresh=True) == SHOW_HINT
    assert _hint(shop_repo, fresh=True) == START_HINT  # a repository: its session
    assert _hint(folder, fresh=True) == SHOW_HINT


def test_a_project_without_a_title_is_named_by_its_id(home):
    projects.create("acme", None)
    path = projects.folder("acme") / "crm"
    assert (
        _refused(path)[0] == f"{path} belongs to the project acme: start a session in the project"
    )


def test_the_projects_folder_itself_points_at_its_repositories(shop_repo):
    path = projects.folder("shop")
    assert _refused(path) == (
        IN_SHOP.format(path),
        "See the project's repositories:",
        "lado project show shop",
    )


@pytest.mark.parametrize("name", ["", "old", "old/deeper"])
def test_a_folder_of_no_project_points_at_the_projects(shop_repo, name):
    path = projects.projects_folder() / name if name else projects.projects_folder()
    assert _refused(path) == (
        f"{path} is in {projects.projects_folder()}, which holds LADO's projects only: start "
        "a session in a project, or move the folder out of projects/",
        "See the projects:",
        "lado project list",
    )


def test_a_link_is_refused_as_its_target(shop_repo, home):
    link = home / "code" / "front"
    link.parent.mkdir()
    link.symlink_to(shop_repo)
    assert _refused(link) == (IN_SHOP.format(link), *START_HINT)


def test_a_link_to_the_projects_folder_is_refused_too(shop_repo, home, monkeypatch):
    real = home / "real-workspace"
    (home / "workspace").rename(real)
    (home / "workspace").symlink_to(real)
    assert _refused(real / "projects" / "shop" / "frontend")[2] == START_HINT[1]


def test_nothing_is_refused_outside_projects(shop_repo, home):
    assert projects.refusal(str(home / "workspace" / "app")) is None
    assert projects.refusal(str(home / "workspace" / "projects-old")) is None
    assert projects.refusal(str(home)) is None


def test_nothing_is_refused_in_the_humans_own_projects_folder(home):
    app = init_repo(home / "workspace" / "projects" / "app")
    assert projects.refusal(str(app)) is None


def test_nothing_is_refused_without_a_lado_db(home):
    (home / "workspace" / "projects").mkdir(parents=True)
    assert projects.refusal(str(home / "workspace" / "projects")) is None
    assert state.schema_version() is None  # asking makes none


def test_a_project_whose_folder_lies_in_its_own_projects_folder_still_refuses(shop_repo):
    old = projects.projects_folder() / "old"
    old.mkdir()  # foreign beside the project: projects/ stays LADO's
    assert _refused(shop_repo)[2] == START_HINT[1]


# The project a path is in


def test_place_names_the_project_and_its_repository(shop_repo):
    assert projects.place(str(shop_repo / "src")) == projects.Place("shop", "frontend")
    assert projects.place(str(shop_repo)) == projects.Place("shop", "frontend")
    folder = projects.folder("shop")
    (folder / "notes").mkdir()
    assert projects.place(str(folder)) == projects.Place("shop", None)
    assert projects.place(str(folder / "notes")) == projects.Place("shop", None)  # no git
    assert projects.place(str(folder / "web")) == projects.Place("shop", None)  # missing


def test_place_follows_a_link_to_its_target(shop_repo, home):
    link = home / "code" / "front"
    link.parent.mkdir()
    link.symlink_to(shop_repo)
    assert projects.place(str(link)) == projects.Place("shop", "frontend")


def test_place_is_none_outside_a_projects_folder(shop_repo, home):
    old = projects.projects_folder() / "old"
    old.mkdir()
    assert projects.place(str(old)) is None  # a foreign folder of projects/
    assert projects.place(str(projects.projects_folder())) is None
    assert projects.place(str(home / "workspace" / "app")) is None


def test_place_is_none_in_the_humans_own_projects_folder(home):
    app = init_repo(home / "workspace" / "projects" / "app")
    assert projects.place(str(app)) is None


# The repositories, from the disk


def test_repositories_with_their_branches_and_remotes(home, git_config):
    projects.create("shop", "Shop")
    folder = projects.folder("shop")
    source = init_repo(home / "src" / "frontend")
    subprocess.run(
        ["git", "clone", "-q", str(source), str(folder / "frontend")],
        check=True,
        capture_output=True,
    )
    _git(
        folder / "frontend", "remote", "set-url", "origin", "https://token@github.com/shop/frontend"
    )
    backend = init_repo(folder / "backend")
    _git(backend, "switch", "-q", "-c", "dev")
    _git(backend, "branch", "-q", "-D", "main")
    assert projects.repositories("shop") == [
        projects.Repository("backend", folder / "backend", "dev", None),
        projects.Repository(
            "frontend", folder / "frontend", "main", "https://github.com/shop/frontend"
        ),
    ]
    assert projects.links("shop") == []


def test_what_is_no_repository(home, git_config):
    projects.create("shop", None)
    folder = projects.folder("shop")
    folder.rmdir()
    init_repo(folder)  # the project folder itself is a repository
    (folder / "plain").mkdir()  # inside it, but no root of its own
    (folder / "notes").mkdir()
    init_repo(folder / ".web.clone-x1y2")  # a clone's temporary folder
    (folder / "readme.txt").write_text("x")
    elsewhere = init_repo(home / "elsewhere" / "docs")
    (folder / "docs").symlink_to(elsewhere)
    assert projects.repositories("shop") == []
    assert projects.links("shop") == [("docs", str(elsewhere))]


def test_a_detached_head_has_no_branch(home, git_config):
    projects.create("shop", None)
    repo = init_repo(projects.folder("shop") / "frontend")
    _git(repo, "switch", "-q", "--detach")
    [found] = projects.repositories("shop")
    assert (found.name, found.branch, found.remote) == ("frontend", None, None)


def test_a_project_whose_folder_is_gone_has_no_repositories(home):
    projects.create("shop", None)
    projects.folder("shop").rmdir()
    assert projects.repositories("shop") == []
    assert projects.links("shop") == []


# The unpushed scan and delete


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


@pytest.mark.parametrize("count, words", [(1, "1 commit"), (2, "2 commits")])
def test_commits_on_a_detached_head(shop, count, words):
    repo = shop / "frontend"
    _git(repo, "checkout", "-q", "--detach")
    for n in range(count):
        _git(repo, "commit", "-q", "--allow-empty", "-m", f"loose {n}")
    assert projects.unpushed(shop) == [f"frontend: detached HEAD with {words} on no branch"]


def test_a_detached_head_on_a_pushed_commit_is_nothing(shop):
    _git(shop / "frontend", "checkout", "-q", "--detach", "origin/main")
    assert projects.unpushed(shop) == []


@pytest.mark.parametrize("count, words", [(1, "1 stash"), (2, "2 stashes")])
def test_stashes(shop, count, words):
    repo = shop / "frontend"
    for n in range(count):
        (repo / f"wip{n}.txt").write_text("x")
        _git(repo, "stash", "push", "-q", "--include-untracked")
    assert projects.unpushed(shop) == [f"frontend: {words}"]


def test_the_findings_of_one_repository_in_their_order(shop):
    repo = shop / "frontend"
    (repo / "wip.txt").write_text("x")
    _git(repo, "stash", "push", "-q", "--include-untracked")
    _git(repo, "branch", "feature-x")
    _git(repo, "checkout", "-q", "--detach")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "loose")
    (repo / "new.txt").write_text("x")
    assert projects.unpushed(shop) == [
        "frontend: uncommitted changes; branch feature-x not pushed; detached HEAD with 1 "
        "commit on no branch; 1 stash"
    ]


def test_a_worktree_on_a_detached_head_with_a_commit_no_ref_holds(shop):
    repo = shop / "frontend"
    tree = repo / ".lado" / "worktrees" / "s" / "w"
    _git(repo, "worktree", "add", "-q", "--detach", str(tree))
    _git(tree, "commit", "-q", "--allow-empty", "-m", "loose")
    (tree / "work.txt").write_text("x")
    assert projects.unpushed(shop) == [
        "frontend: uncommitted changes",  # .lado is untracked
        "frontend (worktree frontend/.lado/worktrees/s/w): uncommitted changes; detached HEAD "
        "with 1 commit on no branch",
    ]


def test_a_project_folder_that_is_a_repository_comes_first(home, git_config):
    projects.create("shop", "Shop")
    folder = projects.folder("shop")
    folder.rmdir()
    init_repo(folder)  # main has no upstream
    init_repo(folder / "frontend")  # a repository of its own inside it, untracked there
    (folder / "README.md").write_text("x")  # the root's own change
    assert projects.unpushed(folder) == [
        "the project's folder: uncommitted changes; branch main not pushed",
        "frontend: branch main not pushed",
    ]


def test_a_worktree_of_the_project_folder_inside_it_is_listed_once(home, git_config):
    projects.create("shop", "Shop")
    folder = projects.folder("shop")
    folder.rmdir()
    init_repo(folder)
    _git(folder, "worktree", "add", "-q", str(folder / "x"), "-b", "fix")
    (folder / "x" / "work.txt").write_text("x")
    assert projects.unpushed(folder) == [  # x is the worktree's line, not the root's change
        "the project's folder: branch fix not pushed; branch main not pushed",
        "the project's folder (worktree x): uncommitted changes",
    ]


def test_a_worktree_inside_the_project_folder_is_listed_once(shop, home):
    repo = shop / "frontend"
    _git(repo, "worktree", "add", "-q", str(shop / "frontend-fix"), "-b", "fix")
    _git(shop / "frontend-fix", "push", "-q", "-u", "origin", "fix")
    (shop / "frontend-fix" / "work.txt").write_text("x")
    outside = init_repo(home / "elsewhere" / "docs")  # its worktree inside has a line of its own
    _git(outside, "worktree", "add", "-q", "--detach", str(shop / "docs-tree"))
    (shop / "docs-tree" / "work.txt").write_text("x")
    assert projects.unpushed(shop) == [
        "docs-tree: uncommitted changes; branch main not pushed",
        "frontend (worktree frontend-fix): uncommitted changes",
    ]


@pytest.fixture
def docs_link(shop, home):
    """shop holding docs, a link to a repository elsewhere with an uncommitted file and a
    branch not pushed."""
    target = init_repo(home / "elsewhere" / "docs")
    (target / "new.txt").write_text("x")
    _git(target, "branch", "draft")
    (shop / "docs").symlink_to(target)
    return target


def test_a_link_to_a_repository_is_not_scanned(shop, docs_link):
    assert projects.unpushed(shop) == []  # the delete removes the link, never its target
    assert projects.deletion("shop").unpushed == []


def test_a_repository_beside_a_link_is_still_named(shop, docs_link):
    _git(shop / "frontend", "branch", "feature-x")
    assert projects.unpushed(shop) == ["frontend: branch feature-x not pushed"]


def test_a_worktree_of_the_links_repository_has_a_line_of_its_own(shop, docs_link):
    _git(docs_link, "worktree", "add", "-q", "--detach", str(shop / "docs-fix"))
    (shop / "docs-fix" / "work.txt").write_text("x")
    [line] = projects.unpushed(shop)
    assert line.startswith("docs-fix: ") and "uncommitted changes" in line


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


def test_delete_removes_the_data_folder_and_a_new_project_has_no_secrets(home):
    projects.create("shop", None)
    projects.create("acme", None)
    projects.set_secret("shop", "GH_TOKEN", "g")
    projects.set_secret("acme", "GH_TOKEN", "a")
    projects.delete("shop", yes=True)
    assert not os.path.lexists(project_secrets.data_folder("shop"))
    assert projects.secrets("acme") == ["GH_TOKEN"]
    projects.create("shop", None)
    assert projects.secrets("shop") == []


def test_create_refuses_a_left_data_folder(home):
    left = project_secrets.data_folder("shop")
    left.mkdir(parents=True)
    with pytest.raises(projects.ProjectError) as refused:
        projects.create("shop", None)
    assert (
        str(refused.value) == f"{left} is left from a project shop: remove it or choose another id"
    )
    assert state.get_project("shop") is None
    assert not projects.folder("shop").exists()


@pytest.mark.parametrize("where", ["id", "secrets", "file"])
def test_a_link_in_the_data_folder_makes_delete_refuse_before_anything(home, where):
    projects.create("shop", None)
    projects.set_secret("shop", "GH_TOKEN", "g")
    path = {
        "id": project_secrets.data_folder("shop"),
        "secrets": project_secrets.folder("shop"),
        "file": project_secrets.folder("shop") / "GH_TOKEN",
    }[where]
    target = home / "elsewhere"
    os.rename(path, target)
    path.symlink_to(target)
    with pytest.raises(projects.ProjectError) as refused:
        projects.delete("shop", yes=True)
    assert str(refused.value) == (
        f"{path} is a symbolic link: LADO writes and removes a project's secrets only in its "
        "own folders"
    )
    assert projects.folder("shop").is_dir() and state.get_project("shop")
    assert path.is_symlink() and target.exists()


def test_a_data_folder_not_removed_whole_keeps_the_record(home, monkeypatch):
    projects.create("shop", None)
    projects.set_secret("shop", "GH_TOKEN", "g")

    real, failed = project_secrets.remove_all, []

    def fail(id):
        if not failed:
            failed.append(id)
            raise PermissionError(13, "Permission denied")
        real(id)

    monkeypatch.setattr(projects.project_secrets, "remove_all", fail)
    with pytest.raises(projects.ProjectError) as refused:
        projects.delete("shop", yes=True)
    assert str(refused.value) == (
        f"could not remove {project_secrets.data_folder('shop')} whole: Permission denied; "
        "the project stays: run lado project delete shop --yes again"
    )
    assert state.get_project("shop")
    projects.delete("shop", yes=True)  # a rerun finishes
    assert state.get_project("shop") is None
    assert not os.path.lexists(project_secrets.data_folder("shop"))


def test_delete_of_an_unknown_project(home):
    with pytest.raises(projects.NoSuchProject, match='unknown project "nope"'):
        projects.delete("nope", yes=True)


# Delete with the project's sessions


def _session(name: str, repo: Path, project: str | None, stopped: bool = True) -> None:
    state.add_session(state.Session(name, str(repo), None, provider="claude", project=project))
    if stopped:
        state.stop_session(name)


def test_delete_refuses_while_a_session_of_the_project_is_not_stopped(shop):
    _session("shop-frontend", shop / "frontend", "shop", stopped=False)
    _session("fix-login", shop / "frontend", "shop")
    for yes in (False, True):
        with pytest.raises(projects.ProjectError) as refused:
            projects.delete("shop", yes=yes)
        assert str(refused.value) == (
            "project shop has sessions not stopped: shop-frontend; stop them first with "
            "lado stop <name>"
        )
    assert shop.is_dir() and state.get_project("shop")
    assert {s.name for s in state.list_sessions()} == {"shop-frontend", "fix-login"}


def test_delete_refuses_while_a_session_runs_in_its_folder_without_the_project(shop, home):
    """A session started there before schema 33 has no project, yet its agents work there."""
    _session("old", shop / "frontend" / "src", None, stopped=False)
    _session("elsewhere", home / "app", None, stopped=False)
    with pytest.raises(projects.ProjectError, match="has sessions not stopped: old;"):
        projects.delete("shop", yes=True)
    assert shop.is_dir() and state.get_project("shop")


def test_the_deletion_names_the_sessions_it_forgets(shop):
    _session("shop-frontend", shop / "frontend", "shop")
    _session("fix-login", shop / "frontend", "shop")
    run = state.Run("shop-frontend", "f/x", "feature", "{}", {}, "do x", "design", "/w", "b")
    state.add_run(run, [], None)
    found = projects.deletion("shop")
    assert (found.id, found.path, found.kind, found.target) == ("shop", shop, "folder", None)
    assert found.sessions == [("fix-login", 0, "shop"), ("shop-frontend", 1, "shop")]
    assert found.unpushed == []
    with pytest.raises(projects.ProjectError) as refused:
        projects.delete("shop", yes=False)
    assert str(refused.value) == (
        f"deleting project shop removes its folder {shop} with everything in it and forgets "
        "its 2 sessions; run again with --yes"
    )
    projects.create("acme", None)
    _session("acme-crm", shop / "x", "acme")  # another project's: never matched by its path
    assert [name for name, _, _ in projects.deletion("shop").sessions] == [
        "fix-login",
        "shop-frontend",
    ]


def test_the_deletion_names_the_variables_and_secrets_without_values(shop):
    projects.set_variable("shop", "BOARD_URL", "https://board.example/value-1")
    projects.set_secret("shop", "GH_TOKEN", "secret-value-2")
    projects.set_secret("shop", "API_KEY", "secret-value-3")
    found = projects.deletion("shop")
    assert (found.variables, found.secrets) == (["BOARD_URL"], ["API_KEY", "GH_TOKEN"])
    assert "value-" not in repr(found)


def test_the_deletion_lists_the_unpushed_work(shop):
    (shop / "frontend" / "new.txt").write_text("x")
    assert projects.deletion("shop").unpushed == ["frontend: uncommitted changes"]


def test_a_stopped_session_without_a_project_in_the_folder_is_forgotten(shop, home):
    _session("shop-frontend", shop / "frontend", "shop")
    _session("old-site", shop / "site", None)  # from before projects: its folder goes
    _session("elsewhere", home / "app", None)
    assert projects.deletion("shop").sessions == [
        ("old-site", 0, None),
        ("shop-frontend", 0, "shop"),
    ]
    with pytest.raises(projects.ProjectError, match="and forgets its 2 sessions; run again"):
        projects.delete("shop", yes=False)
    projects.delete("shop", yes=True)
    assert not os.path.lexists(shop) and state.get_project("shop") is None
    assert [s.name for s in state.list_sessions()] == ["elsewhere"]


def test_delete_with_yes_forgets_the_stopped_sessions(shop, home):
    _session("shop-frontend", shop / "frontend", "shop")
    _session("old", home / "app", None)  # no project, elsewhere: kept
    projects.delete("shop", yes=True)
    assert not os.path.lexists(shop) and state.get_project("shop") is None
    assert [s.name for s in state.list_sessions()] == ["old"]


@pytest.fixture
def linked(home, git_config):
    """The project shop whose folder is a link to <tmp>/srv-shop, which holds a repository
    with work not pushed."""
    projects.create("shop", None)
    link = projects.folder("shop")
    link.rmdir()
    target = home / "srv-shop"
    repo = init_repo(target / "app")
    (repo / "new.txt").write_text("x")
    link.symlink_to(target)
    return link, target


def test_a_link_folder_is_announced_as_a_link(linked):
    link, target = linked
    found = projects.deletion("shop")
    assert (found.path, found.kind, found.target) == (link, "link", str(target))
    assert found.unpushed == []  # its target is not deleted: nothing of it is lost
    with pytest.raises(projects.ProjectError) as refused:
        projects.delete("shop", yes=False)
    assert str(refused.value) == (
        f"deleting project shop removes the link {link} only, not its target {target}; run "
        "again with --yes"
    )
    assert link.is_symlink() and state.get_project("shop")


def test_a_session_in_a_link_folders_target_is_neither_in_the_way_nor_forgotten(linked):
    link, target = linked
    _session("srv", target / "app", None, stopped=False)
    _session("srv-old", target / "app", None)
    _session("shop-app", link / "app", "shop")
    assert [name for name, _, _ in projects.deletion("shop").sessions] == ["shop-app"]
    projects.delete("shop", yes=True)
    assert not os.path.lexists(link) and (target / "app" / "new.txt").is_file()
    assert sorted(s.name for s in state.list_sessions()) == ["srv", "srv-old"]


def test_a_link_folders_own_running_session_still_refuses(linked):
    link, _ = linked
    _session("shop-app", link / "app", "shop", stopped=False)
    with pytest.raises(projects.ProjectError, match="has sessions not stopped: shop-app;"):
        projects.deletion("shop")
    with pytest.raises(projects.ProjectError, match="has sessions not stopped: shop-app;"):
        projects.delete("shop", yes=True)
    assert link.is_symlink() and state.get_project("shop")


def test_a_link_to_another_projects_folder_leaves_that_project_whole(home, git_config):
    projects.create("acme", None)
    acme = projects.folder("acme")
    init_repo(acme / "crm")
    _session("acme-crm", acme / "crm", "acme", stopped=False)
    projects.create("shop", None)
    link = projects.folder("shop")
    link.rmdir()
    link.symlink_to(acme)
    assert projects.deletion("shop").sessions == []
    projects.delete("shop", yes=True)
    assert not os.path.lexists(link) and state.get_project("shop") is None
    assert (acme / "crm" / ".git").is_dir() and state.get_project("acme")
    assert [s.name for s in state.list_sessions()] == ["acme-crm"]


def test_a_missing_folder_is_announced_as_missing(home):
    projects.create("shop", None)
    where = projects.folder("shop")
    where.rmdir()
    _session("shop-x", where / "x", "shop")
    found = projects.deletion("shop")
    assert (found.kind, found.target, found.unpushed) == ("missing", None, [])
    assert found.sessions == [("shop-x", 0, "shop")]
    with pytest.raises(projects.ProjectError) as refused:
        projects.delete("shop", yes=False)
    assert str(refused.value) == (
        f"deleting project shop removes its record (its folder {where} is not found) and "
        "forgets its 1 session; run again with --yes"
    )


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any folder")
def test_an_unreadable_project_folder_is_a_line_not_a_traceback(shop):
    shop.chmod(0)
    try:
        assert projects.deletion("shop").unpushed == [
            "the project's folder: could not check: Permission denied"
        ]
    finally:
        shop.chmod(0o755)


def test_the_deletion_of_an_unknown_project(home):
    with pytest.raises(projects.NoSuchProject, match='unknown project "nope"'):
        projects.deletion("nope")


def test_a_folder_not_removed_keeps_the_sessions(shop, monkeypatch):
    _session("shop-frontend", shop / "frontend", "shop")

    def fail(path, *args, **kwargs):
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(projects.shutil, "rmtree", fail)
    with pytest.raises(projects.ProjectError, match="the project stays"):
        projects.delete("shop", yes=True)
    assert state.get_session("shop-frontend") and state.get_project("shop")


def test_a_session_not_forgotten_keeps_the_record(shop, monkeypatch):
    _session("shop-frontend", shop / "frontend", "shop")

    def fail(name, force=False):
        raise runtime.LadoError("the disk is gone")

    monkeypatch.setattr(runtime, "forget_session", fail)
    with pytest.raises(projects.ProjectError) as refused:
        projects.delete("shop", yes=True)
    assert str(refused.value) == (
        "could not forget session shop-frontend: the disk is gone; the project stays: run "
        "lado project delete shop --yes again"
    )
    assert not os.path.lexists(shop) and state.get_project("shop")


# check_new and suggest_id: what New project of the UI asks before it makes anything


def _taken(home):
    projects.create("shop", None)


def _folder_of_the_name(home):
    (home / "workspace" / "projects" / "shop").mkdir(parents=True)


def _left_data_folder(home):
    project_secrets.data_folder("shop").mkdir(parents=True)


def _humans_folder(home):
    (home / "workspace" / "projects" / "notes").mkdir(parents=True)


def _workspace_a_file(home):
    (home / "workspace").write_text("")


@pytest.mark.parametrize(
    "make", [_taken, _folder_of_the_name, _left_data_folder, _humans_folder, _workspace_a_file]
)
def test_check_new_refuses_as_create_does_and_makes_nothing(home, make):
    make(home)
    before = sorted(os.listdir(home))
    with pytest.raises(projects.ProjectError) as checked:
        projects.check_new("shop")
    assert sorted(os.listdir(home)) == before
    with pytest.raises(projects.ProjectError) as created:
        projects.create("shop", None)
    assert str(checked.value) == str(created.value)


def test_check_new_refuses_a_bad_id_and_passes_a_free_one_making_nothing(home, lado_home):
    with pytest.raises(projects.ProjectError) as refused:
        projects.check_new("Shop")
    assert str(refused.value) == BAD_ID.format("Shop")
    projects.check_new("shop")
    assert not (home / "workspace").exists()
    assert not (lado_home / "lado.db").exists()


@pytest.mark.parametrize(
    ("title", "id"),
    [
        ("Магазин EU", "magazin-eu"),
        ("ACME_crm", "acme-crm"),
        ("  Shop  ", "shop"),
        ("Crème brûlée", "creme-brulee"),
        ("a" * 39 + "-b" + "c" * 19, "a" * 39),
        ("_x_", "x"),
    ],
)
def test_suggest_id_makes_an_id_of_a_title(title, id):
    assert projects.suggest_id(title) == id
    projects.check_id(id)


@pytest.mark.parametrize(
    ("title", "problem"),
    [
        ("日本", "the name needs a Latin letter or digit for its folder: type one"),
        ("", "type a name"),
        ("x" * 81, "a name is at most 80 characters"),
    ],
)
def test_suggest_id_refuses_with_the_fresh_starts_text(title, problem):
    with pytest.raises(runtime.LadoError) as refused:
        projects.suggest_id(title)
    assert str(refused.value) == problem
