"""runtime.start_session in a project, and the refusal of a new session without one inside
LADO's projects/ (openspec change sessions-in-projects)."""

import os
from pathlib import Path

import agent_helpers
import pytest
from agent_helpers import init_repo

from lado import kits, projects, runtime, state


@pytest.fixture
def shop(tmp_path, monkeypatch, fake_tmux):
    """The workspace <tmp>/ws with the project shop titled Shop and its repository
    frontend; the folder of the project."""
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    projects.create("shop", "Shop")
    init_repo(projects.folder("shop") / "frontend")
    return projects.folder("shop")


def _start(**kwargs) -> runtime.Started:
    return runtime.start_session(
        kwargs.pop("path", None), kwargs.pop("name", None), None, provider="claude", **kwargs
    )


def test_a_session_in_a_project_takes_its_repository_and_name(shop, fake_tmux):
    started = _start(project="shop", repo_name="frontend")
    assert started.session.name == "shop-frontend"
    stored = state.get_session("shop-frontend")
    assert (stored.repo, stored.project) == (str(shop / "frontend"), "shop")
    [(kind, session, _window, cwd, *_)] = fake_tmux
    assert (kind, session, cwd) == ("new_session", "shop-frontend", str(shop / "frontend"))


def test_the_default_name_of_a_session_in_a_project():
    assert runtime.project_session_name("shop", "Front.End") == "shop-front-end"
    assert runtime.project_session_name("shop", "frontend") == "shop-frontend"


def test_a_given_name_is_kept(shop):
    assert _start(project="shop", repo_name="frontend", name="Fix Login").session.name == (
        "fix-login"
    )
    assert state.get_session("fix-login").project == "shop"


def test_an_unknown_project(shop):
    with pytest.raises(projects.NoSuchProject, match='^unknown project "acme"$'):
        _start(project="acme", repo_name="frontend")
    assert state.list_sessions() == []


def test_an_unknown_repository_names_those_there_are(shop):
    init_repo(shop / "backend")
    with pytest.raises(runtime.LadoError) as refused:
        _start(project="shop", repo_name="web")
    assert (
        str(refused.value)
        == "project shop has no repository web; its repositories: backend, frontend"
    )
    assert state.list_sessions() == []


@pytest.mark.parametrize("entry", ["notes", ".hidden"])
def test_what_is_no_repository_is_refused_as_unknown(shop, entry):
    (shop / entry).mkdir()
    with pytest.raises(
        runtime.LadoError, match=f"has no repository {entry}; its repositories: frontend$"
    ):
        _start(project="shop", repo_name=entry)


def test_a_link_is_named_as_one(shop, tmp_path):
    elsewhere = init_repo(tmp_path / "elsewhere" / "docs")
    (shop / "docs").symlink_to(elsewhere)
    with pytest.raises(runtime.LadoError) as refused:
        _start(project="shop", repo_name="docs")
    assert str(refused.value) == (
        f"docs in project shop is a link to {elsewhere}: clone it into {shop} instead"
    )
    assert state.list_sessions() == []


def test_a_project_without_repositories(shop):
    projects.create("acme", None)
    with pytest.raises(runtime.LadoError) as refused:
        _start(project="acme", repo_name="crm")
    assert str(refused.value) == (
        "project acme has no repositories yet: add one with lado project repo add acme "
        "<git-url> or --new <name>"
    )


def test_a_session_of_the_project_is_resumed_with_it(shop):
    _start(project="shop", repo_name="frontend")
    runtime.stop_session("shop-frontend")
    started = runtime.start_session(
        None, None, None, provider="codex", project="shop", repo_name="frontend"
    )
    assert started.resumed
    assert state.get_session("shop-frontend").project == "shop"


def test_a_resume_without_the_project_keeps_it(shop):
    _start(project="shop", repo_name="frontend")
    runtime.stop_session("shop-frontend")
    started = _start(path=str(shop / "frontend"), name="shop-frontend", resume=True)
    assert started.resumed  # not refused: it is no new session
    assert state.get_session("shop-frontend").project == "shop"


@pytest.mark.parametrize(
    ("old_project", "said"),
    [("acme", "is in project acme"), (None, "is not in a project")],
)
def test_a_sessions_project_never_changes(shop, tmp_path, old_project, said):
    if old_project:
        projects.create("acme", None)
        init_repo(projects.folder("acme") / "frontend")
        _start(project="acme", repo_name="frontend", name="site")
    else:
        _start(path=str(init_repo(tmp_path / "site")), name="site")
    runtime.stop_session("site")
    with pytest.raises(runtime.LadoError) as refused:
        _start(project="shop", repo_name="frontend", name="site")
    assert str(refused.value) == (
        f'session "site" {said}; a session\'s project never changes: give another name with --name'
    )
    assert state.get_session("site").project == old_project


def test_a_new_session_without_the_project_is_refused_in_its_repository(shop):
    with pytest.raises(runtime.FolderProblem) as refused:
        _start(path=str(shop / "frontend"))
    assert refused.value.kind == "in_project"
    assert str(refused.value) == (
        f"{shop / 'frontend'} belongs to the project Shop: start a session in the project"
    )
    assert refused.value.hint.command == "lado start --project shop --repo frontend"
    assert state.list_sessions() == []


def test_a_folder_without_git_in_a_project_is_the_projects_refusal(shop):
    (shop / "notes").mkdir()
    with pytest.raises(runtime.FolderProblem) as refused:
        _start(path=str(shop / "notes"))
    assert refused.value.kind == "in_project"  # not not_repo's `git init`


def test_a_missing_folder_in_a_project_is_the_projects_refusal(shop):
    with pytest.raises(runtime.FolderProblem) as refused:
        _start(path=str(shop / "gone"))
    assert refused.value.kind == "in_project"


def test_a_session_from_before_projects_resumes_there(shop):
    """A session started under projects/ before schema 33 has no project and is resumed."""
    repo = str(shop / "frontend")
    state.add_session(state.Session("site", repo, None, provider="claude"))
    state.stop_session("site")
    started = _start(path=repo, name="site")
    assert started.resumed
    assert state.get_session("site").project is None


def test_nothing_is_refused_in_the_humans_own_projects_folder(tmp_path, monkeypatch, fake_tmux):
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    app = init_repo(tmp_path / "ws" / "projects" / "app")
    assert _start(path=str(app)).session.name == "app"
    assert state.get_session("app").project is None


# The project's variables (openspec change project-variables)


@pytest.fixture
def outside(tmp_path, monkeypatch):
    """The outside folder (LADO_ENV_DIR) with BOARD_URL=out and OTHER=o."""
    folder = tmp_path / "secrets"
    folder.mkdir()
    (folder / "BOARD_URL").write_text("out\n")
    (folder / "OTHER").write_text("o")
    monkeypatch.setenv("LADO_ENV_DIR", str(folder))
    return folder


def test_the_agents_of_a_session_in_a_project_get_its_variables(shop, fake_tmux, outside):
    projects.set_variable("shop", "BOARD_URL", "https://a b=c\nd")
    _start(project="shop", repo_name="frontend")
    env, _ = agent_helpers.launched(fake_tmux[0])
    assert (env["BOARD_URL"], env["OTHER"]) == ("https://a b=c\nd", "o")
    projects.set_variable("shop", "MODEL_URL", "http://m")  # read anew at the next launch
    runtime.spawn_worker("shop-frontend", "task", name="w1")
    env, _ = agent_helpers.launched(fake_tmux[-1])
    assert (env["BOARD_URL"], env["MODEL_URL"]) == ("https://a b=c\nd", "http://m")
    projects.unset_variable("shop", "BOARD_URL")
    runtime.spawn_worker("shop-frontend", "task", name="w2")
    env, _ = agent_helpers.launched(fake_tmux[-1])
    assert env["BOARD_URL"] == "out"  # the outside folder's again


def test_a_resume_reads_the_variables_anew(shop, fake_tmux):
    _start(project="shop", repo_name="frontend")
    assert "MODEL_URL" not in agent_helpers.launched(fake_tmux[0])[0]
    runtime.stop_session("shop-frontend")
    projects.set_variable("shop", "MODEL_URL", "http://m")
    assert _start(project="shop", repo_name="frontend").resumed
    assert agent_helpers.launched(fake_tmux[-1])[0]["MODEL_URL"] == "http://m"


def test_each_project_gives_its_own_value_and_no_project_none(shop, fake_tmux, tmp_path):
    projects.create("acme", None)
    init_repo(projects.folder("acme") / "frontend")
    projects.set_variable("shop", "BOARD_URL", "https://a")
    projects.set_variable("acme", "BOARD_URL", "https://b")
    _start(project="shop", repo_name="frontend")
    _start(project="acme", repo_name="frontend")
    _start(path=str(init_repo(tmp_path / "app")))
    values = [agent_helpers.launched(call)[0].get("BOARD_URL") for call in fake_tmux]
    assert values == ["https://a", "https://b", None]


@pytest.fixture
def board_kit(tmp_path):
    """An installed kit whose worker role `boarder` has an MCP server needing ${BOARD_URL}."""
    kit = tmp_path / "kits" / "board"
    (kit / "agents").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: board\nversion: 1.0.0\n")
    (kit / "agents" / "boarder.md").write_text(
        "---\nname: boarder\ndescription: reads the board\n"
        "mcp:\n  board:\n    command: ['${KIT_DIR}/board.sh']\n    env: {URL: '${BOARD_URL}'}\n"
        "---\nYou read the board.\n"
    )
    agent_helpers.install_kit(kit)
    return kit


def test_a_kit_key_only_in_the_project_passes(shop, fake_tmux, board_kit, tmp_path):
    projects.set_variable("shop", "BOARD_URL", "https://a")
    _start(project="shop", repo_name="frontend", kit_names=["default", "board"])
    runtime.spawn_worker("shop-frontend", "read it", role="boarder")
    env, _ = agent_helpers.launched(fake_tmux[-1])
    assert env["BOARD_URL"] == "https://a"  # lado.mcp_exec takes it from here
    _start(path=str(init_repo(tmp_path / "app")), kit_names=["default", "board"])
    with pytest.raises(kits.KitError, match="BOARD_URL"):
        runtime.spawn_worker("app", "read it", role="boarder")


def test_a_project_variable_with_a_name_lado_sets_keeps_lado_s_value(shop, fake_tmux):
    state.set_project_variable("shop", "KILO_DISABLE_AUTOUPDATE", "0")  # stored before a rule
    line = (
        "project variable KILO_DISABLE_AUTOUPDATE of shop not used: LADO sets "
        "KILO_DISABLE_AUTOUPDATE for kilo"
    )
    started = runtime.start_session(
        None, None, None, provider="kilo", project="shop", repo_name="frontend"
    )
    assert line in started.warnings
    assert agent_helpers.launched(fake_tmux[0])[0]["KILO_DISABLE_AUTOUPDATE"] == "1"
    warnings = []
    runtime.spawn_worker("shop-frontend", "task", name="w1", warnings=warnings)
    assert line in warnings
    warnings = []
    runtime.spawn_worker("shop-frontend", "task", name="w2", provider="claude", warnings=warnings)
    assert not [w for w in warnings if w.startswith("project variable")]  # not Claude's
    runtime.stop_session("shop-frontend")
    resumed = runtime.start_session(
        None, None, None, provider="kilo", project="shop", repo_name="frontend"
    )
    assert line in resumed.warnings


def test_a_link_from_outside_is_refused(shop, tmp_path):
    link = Path(tmp_path / "front")
    os.symlink(shop / "frontend", link)
    with pytest.raises(runtime.FolderProblem, match="belongs to the project Shop"):
        _start(path=str(link))


# The project's secrets (openspec change project-secrets)


def test_the_agents_of_a_session_in_a_project_get_its_secrets(shop, fake_tmux, tmp_path):
    projects.set_secret("shop", "SHOP_TOKEN", "ghp_a\nline2")
    projects.set_variable("shop", "BOARD_URL", "https://a")
    _start(project="shop", repo_name="frontend")
    env, _ = agent_helpers.launched(fake_tmux[0])
    assert (env["SHOP_TOKEN"], env["BOARD_URL"]) == ("ghp_a\nline2", "https://a")
    projects.set_secret("shop", "MODEL_KEY", "m")  # read anew at the next launch
    runtime.spawn_worker("shop-frontend", "task", name="w1")
    assert agent_helpers.launched(fake_tmux[-1])[0]["MODEL_KEY"] == "m"
    projects.unset("shop", "SHOP_TOKEN")
    runtime.spawn_worker("shop-frontend", "task", name="w2")
    assert "SHOP_TOKEN" not in agent_helpers.launched(fake_tmux[-1])[0]
    _start(path=str(init_repo(tmp_path / "app")))  # no project: none of its secrets
    assert "MODEL_KEY" not in agent_helpers.launched(fake_tmux[-1])[0]


def test_a_secret_ending_in_a_line_break_reaches_the_agent_whole(shop, fake_tmux):
    projects.set_secret("shop", "SHOP_TOKEN", "x\n")
    projects.set_secret("shop", "SHOP_KEY", "\n")
    _start(project="shop", repo_name="frontend")
    env, _ = agent_helpers.launched(fake_tmux[0])
    assert (env["SHOP_TOKEN"], env["SHOP_KEY"]) == ("x\n", "\n")


def test_a_resume_reads_the_secrets_anew(shop, fake_tmux):
    _start(project="shop", repo_name="frontend")
    runtime.stop_session("shop-frontend")
    projects.set_secret("shop", "SHOP_TOKEN", "g")
    assert _start(project="shop", repo_name="frontend").resumed
    assert agent_helpers.launched(fake_tmux[-1])[0]["SHOP_TOKEN"] == "g"


def test_two_projects_one_secret_name(shop, fake_tmux):
    projects.create("acme", None)
    init_repo(projects.folder("acme") / "frontend")
    projects.set_secret("shop", "SHOP_TOKEN", "a")
    projects.set_secret("acme", "SHOP_TOKEN", "b")
    _start(project="shop", repo_name="frontend")
    _start(project="acme", repo_name="frontend")
    assert [agent_helpers.launched(call)[0]["SHOP_TOKEN"] for call in fake_tmux] == ["a", "b"]


def test_a_secret_wins_over_the_outside_folder(shop, fake_tmux, outside, tmp_path):
    (outside / "SHOP_TOKEN").write_text("out\n")
    projects.set_secret("shop", "SHOP_TOKEN", "a")
    _start(project="shop", repo_name="frontend")
    _start(path=str(init_repo(tmp_path / "app")))
    assert [agent_helpers.launched(call)[0]["SHOP_TOKEN"] for call in fake_tmux] == ["a", "out"]


def test_a_kit_key_only_a_secret_passes_and_stays_out_of_the_config(
    shop, fake_tmux, board_kit, tmp_path
):
    projects.set_secret("shop", "BOARD_URL", "canary-5b1d")
    _start(project="shop", repo_name="frontend", kit_names=["default", "board"])
    runtime.spawn_worker("shop-frontend", "read it", role="boarder")
    env, argv = agent_helpers.launched(fake_tmux[-1])
    assert env["BOARD_URL"] == "canary-5b1d"  # lado.mcp_exec takes it from here
    assert not [arg for arg in argv if "canary-5b1d" in arg]
    configs = state.home_path() / "agents"
    for path in configs.rglob("*"):
        if path.is_file() and path.name != "env.json":
            assert b"canary-5b1d" not in path.read_bytes(), path
    _start(path=str(init_repo(tmp_path / "app")), kit_names=["default", "board"])
    with pytest.raises(kits.KitError, match="BOARD_URL"):
        runtime.spawn_worker("app", "read it", role="boarder")


def test_a_secret_file_not_given_is_named_at_a_start_and_a_resume(shop, fake_tmux):
    projects.set_secret("shop", "SHOP_TOKEN", "g")
    (projects.project_secrets.folder("shop") / "SHOP_TOKEN").chmod(0o644)
    line = (
        "project secret SHOP_TOKEN of shop not used: readable or writable by others: chmod 600 it"
    )
    started = _start(project="shop", repo_name="frontend")
    assert line in started.warnings
    assert "SHOP_TOKEN" not in agent_helpers.launched(fake_tmux[0])[0]
    warnings = []
    runtime.spawn_worker("shop-frontend", "task", name="w1", warnings=warnings)
    assert line not in warnings  # the folder is the same for every agent: said at the start
    runtime.stop_session("shop-frontend")
    assert line in _start(project="shop", repo_name="frontend").warnings


def test_a_loose_secrets_folder_is_named(shop, fake_tmux):
    projects.set_secret("shop", "SHOP_TOKEN", "g")
    projects.project_secrets.folder("shop").chmod(0o755)
    started = _start(project="shop", repo_name="frontend")
    assert (
        "project secrets folder of shop not used: readable or writable by others: chmod 700 it"
        in started.warnings
    )
    assert "SHOP_TOKEN" not in agent_helpers.launched(fake_tmux[0])[0]
