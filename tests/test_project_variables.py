"""A project's plain variables: the name rule, set and unset (openspec change
project-variables)."""

import pytest

from lado import projects, providers, state
from lado.providers import base


@pytest.fixture
def shop(lado_home):
    projects.create("shop", None)
    return "shop"


NOT_A_NAME = (
    "the name {} is not a variable name: Latin letters, digits and _, not starting with a digit"
)


@pytest.mark.parametrize("name", ["A-B", "1X", "", "A B", "ПУТЬ", "A=B"])
def test_a_name_that_is_no_variable_name(shop, name):
    with pytest.raises(projects.ProjectError) as refused:
        projects.set_variable(shop, name, "x")
    assert str(refused.value) == NOT_A_NAME.format(name)
    assert state.project_variables(shop) == {}


RESERVED = [
    "PATH",
    "HOME",
    "USER",
    "SHELL",
    "TERM",
    "TMUX",
    "PWD",
    "_",
    "LADO_HOME",
    "LADO_ANYTHING",
    "CLAUDE_CONFIG_DIR",
    "CODEX_HOME",
    "OPENCODE_CONFIG",
    "OPENCODE_CONFIG_CONTENT",
    "KILO_CONFIG",
    "KILO_NO_DAEMON",
]


@pytest.mark.parametrize("name", RESERVED)
def test_a_reserved_name(shop, name):
    with pytest.raises(projects.ProjectError) as refused:
        projects.set_variable(shop, name, "x")
    assert str(refused.value) == f"{name} is reserved: LADO or the agent CLIs set it"
    assert state.project_variables(shop) == {}


@pytest.mark.parametrize(
    "name, word",
    [
        ("GH_TOKEN", "TOKEN"),
        ("yougile_api_key", "KEY"),
        ("DB_PASSWORD", "PASSWORD"),
        ("MY_SECRET", "SECRET"),
        ("MONKEY_MODE", "KEY"),  # a substring: the concept's simple rule (#966)
    ],
)
def test_a_name_that_looks_like_a_secret(shop, name, word):
    with pytest.raises(projects.ProjectError) as refused:
        projects.set_variable(shop, name, "x")
    assert str(refused.value) == (
        f"{name} looks like a secret ({word}): a plain variable takes no name with TOKEN, KEY, "
        f"SECRET or PASSWORD; secrets come with lado project set shop {name} --secret "
        "(not built yet)"
    )
    assert state.project_variables(shop) == {}


@pytest.mark.parametrize("name", ["BOARD_URL", "ANTHROPIC_BASE_URL", "_X", "model_url"])
def test_a_plain_name(shop, name):
    projects.set_variable(shop, name, "x")
    assert state.project_variables(shop) == {name: "x"}


def test_a_value_too_large(shop):
    projects.set_variable(shop, "BIG", "é" * (64 * 1024 // 2))  # 64 KiB of UTF-8 exactly
    with pytest.raises(projects.ProjectError) as refused:
        projects.set_variable(shop, "BIG", "x" * (64 * 1024 + 1))
    assert str(refused.value) == "the value of BIG is larger than 64 KiB"
    assert len(state.project_variables(shop)["BIG"]) == 32 * 1024  # the old value stays


@pytest.mark.parametrize("value", ["a\0b", "\udcff"])
def test_a_value_that_is_no_text(shop, value):
    with pytest.raises(projects.ProjectError) as refused:
        projects.set_variable(shop, "BOARD_URL", value)
    assert str(refused.value) == "the value of BOARD_URL is not UTF-8 text"
    assert state.project_variables(shop) == {}


def test_values_kept_as_given(shop):
    for value in ["", "a b = c", "line\nnext\r\n", "ünïcode ✓", "-v"]:
        projects.set_variable(shop, "BOARD_URL", value)
        assert state.project_variables(shop) == {"BOARD_URL": value}


def test_an_unknown_project(lado_home):
    for call in (
        lambda: projects.set_variable("nope", "BOARD_URL", "x"),
        lambda: projects.unset_variable("nope", "BOARD_URL"),
        lambda: projects.variables("nope"),
    ):
        with pytest.raises(projects.NoSuchProject) as refused:
            call()
        assert str(refused.value) == 'unknown project "nope"'


def test_the_project_is_checked_before_the_name(lado_home):
    with pytest.raises(projects.NoSuchProject):
        projects.set_variable("nope", "GH_TOKEN", "x")


def test_unset(shop):
    projects.set_variable(shop, "BOARD_URL", "https://a")
    projects.set_variable(shop, "MODEL_URL", "http://m")
    assert projects.unset_variable(shop, "BOARD_URL") == []
    assert projects.variables(shop) == {"MODEL_URL": "http://m"}
    with pytest.raises(projects.NoSuchVariable) as refused:
        projects.unset_variable(shop, "BOARD_URL")
    assert str(refused.value) == "project shop has no variable BOARD_URL; its variables: MODEL_URL"
    projects.unset_variable(shop, "MODEL_URL")
    with pytest.raises(projects.NoSuchVariable) as refused:
        projects.unset_variable(shop, "MODEL_URL")
    assert str(refused.value) == "project shop has no variable MODEL_URL; its variables: none"


def test_unset_checks_no_name_rule(shop):
    """A row stored before a rule changed can still go."""
    state.set_project_variable(shop, "GH_TOKEN", "old")
    projects.unset_variable(shop, "GH_TOKEN")
    assert state.project_variables(shop) == {}


def test_set_and_unset_answer_the_running_sessions(shop, monkeypatch):
    projects.create("acme", None)
    for name, project in [("b-run", shop), ("a-run", shop), ("stopped", shop), ("other", "acme")]:
        state.add_session(
            state.Session(name, f"/r/{name}", None, provider="claude", project=project)
        )
    state.stop_session("stopped")
    running = {"a-run", "b-run", "other"}
    monkeypatch.setattr(projects.runtime.tmux, "has_session", lambda name: name in running)
    monkeypatch.setattr(projects.runtime.loop, "running", lambda name: True)
    assert projects.running(shop) == ["a-run", "b-run"]
    assert projects.set_variable(shop, "BOARD_URL", "x") == ["a-run", "b-run"]
    assert projects.unset_variable(shop, "BOARD_URL") == ["a-run", "b-run"]
    running.discard("a-run")  # its tmux session is gone: it is not stopped either
    assert projects.running(shop) == ["a-run", "b-run"]


def _launches(repo):
    sess = {name: state.Session("s", str(repo), None, name) for name in providers.names()}
    for name in providers.names():
        agent = state.Agent(
            "s", "w1", "worker", str(repo), None, None, state.STARTING, name, instance="i1"
        )
        spec = providers.AgentSpec("the role", mcp={"lado": base.mcp_server(agent)})
        yield name, providers.get(name).launch_command(agent, sess[name], spec)


def test_every_name_a_provider_sets_is_reserved(repo, lado_home):
    seen = set()
    for name, launch in _launches(repo):
        for variable in launch.env:
            seen.add(variable)
            assert variable in projects.RESERVED_NAMES, (name, variable)
    assert seen  # the providers set some: the check is not empty
    for variable in seen:
        with pytest.raises(projects.ProjectError, match="is reserved"):
            projects.check_variable("shop", variable, None)
