"""A project's plain variables: the name rule, set and unset (openspec change
project-variables)."""

import os

import pytest

from lado import agent_env, project_secrets, projects, providers, state
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
        f"SECRET or PASSWORD; set it as a secret with lado project set shop {name} --secret"
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
        with pytest.raises(projects.ProjectError, match="is reserved"):
            projects.check_secret("shop", variable, "x")
        assert project_secrets.reserved(variable) or variable in agent_env.RESERVED


# A project's secrets (openspec change project-secrets): files beside the plain variables.


def secret_file(name, id="shop"):
    return project_secrets.folder(id) / name


@pytest.mark.parametrize("name", ["GH_TOKEN", "DATABASE_URL", "_X", "yougile_api_key"])
def test_any_variable_name_may_be_a_secret(shop, name):
    assert projects.set_secret(shop, name, "v") == []
    assert secret_file(name).read_text() == "v"
    assert projects.secrets(shop) == [name]
    assert state.project_variables(shop) == {}  # no value of a secret in lado.db


@pytest.mark.parametrize("name", ["LADO_HOME", "PATH", "CODEX_HOME", "A-B", "1X"])
def test_a_secrets_name_is_checked_by_the_variables_rule(shop, name):
    with pytest.raises(projects.ProjectError) as refused:
        projects.set_secret(shop, name, "x")
    expected = (
        NOT_A_NAME.format(name)
        if "-" in name or name[0].isdigit()
        else f"{name} is reserved: LADO or the agent CLIs set it"
    )
    assert str(refused.value) == expected
    assert not project_secrets.data_folder(shop).exists()


@pytest.mark.parametrize(
    "value, text",
    [
        ("", "the secret GH_TOKEN is empty; to remove it: lado project unset shop GH_TOKEN"),
        ("x" * 65537, "the value of GH_TOKEN is larger than 64 KiB"),
        ("a\0b", "the value of GH_TOKEN is not UTF-8 text"),
        ("\udcff", "the value of GH_TOKEN is not UTF-8 text"),
    ],
)
def test_a_secrets_value_is_a_non_empty_short_text(shop, value, text):
    with pytest.raises(projects.ProjectError) as refused:
        projects.set_secret(shop, "GH_TOKEN", value)
    assert str(refused.value) == text
    assert projects.secrets(shop) == []


def test_a_secret_of_exactly_64_kib(shop):
    projects.set_secret(shop, "BIG", "é" * (64 * 1024 // 2))
    assert len(secret_file("BIG").read_bytes()) == 64 * 1024


def test_a_secret_ending_in_a_line_break_counts_its_stored_one(shop):
    """Its file keeps one line break more (project_secrets.stored), and the file is what
    the reader limits: a value the agents would not get is refused."""
    projects.set_secret(shop, "EDGE", "a" * (64 * 1024 - 2) + "\n")
    assert project_secrets.read(shop).values["EDGE"].endswith("a\n")
    with pytest.raises(projects.ProjectError) as refused:
        projects.set_secret(shop, "BIG", "a" * (64 * 1024 - 1) + "\n")
    assert str(refused.value) == "the value of BIG is larger than 64 KiB"
    assert "BIG" not in projects.secrets(shop)


@pytest.mark.parametrize("value", ["\n", "\r\n", "x\n", "\n\n"])
def test_a_line_break_is_a_value_the_agents_get_whole(shop, value):
    projects.set_secret(shop, "V", value)
    assert project_secrets.read(shop).values == {"V": value}


def test_a_secret_of_an_unknown_project(lado_home):
    for call in (
        lambda: projects.set_secret("nope", "GH_TOKEN", "x"),
        lambda: projects.set_secret("nope", "A-B", ""),  # the project before the name
        lambda: projects.unset_secret("nope", "GH_TOKEN"),
        lambda: projects.unset("nope", "GH_TOKEN"),
        lambda: projects.secrets("nope"),
    ):
        with pytest.raises(projects.NoSuchProject):
            call()
    assert not (lado_home / "projects").exists()


def test_a_plain_variable_is_not_made_a_secret(shop):
    projects.set_variable(shop, "DATABASE_URL", "postgres://x")
    with pytest.raises(projects.ProjectError) as refused:
        projects.set_secret(shop, "DATABASE_URL", "postgres://y")
    assert str(refused.value) == (
        "DATABASE_URL is a plain variable of shop; remove it first with lado project unset "
        "shop DATABASE_URL"
    )
    assert state.project_variables(shop) == {"DATABASE_URL": "postgres://x"}
    assert projects.secrets(shop) == []


def test_a_secret_is_not_set_as_a_plain_variable(shop):
    projects.set_secret(shop, "DATABASE_URL", "postgres://x")
    with pytest.raises(projects.ProjectError) as refused:
        projects.set_variable(shop, "DATABASE_URL", "postgres://y")
    assert str(refused.value) == (
        "DATABASE_URL is a secret of shop; remove it first with lado project unset shop "
        "DATABASE_URL"
    )
    assert state.project_variables(shop) == {}
    assert secret_file("DATABASE_URL").read_text() == "postgres://x"


@pytest.mark.parametrize("make", ["loose", "link"])
def test_a_secret_file_the_agents_do_not_get_still_holds_its_name(shop, tmp_path, make):
    """One value per name by the file's presence, not by whether the agents get it now: a
    chmod back to 600 would give the name two values."""
    projects.set_secret(shop, "DATABASE_URL", "postgres://s")
    if make == "loose":
        secret_file("DATABASE_URL").chmod(0o644)
    else:
        os.rename(secret_file("DATABASE_URL"), tmp_path / "t")
        secret_file("DATABASE_URL").symlink_to(tmp_path / "t")
    with pytest.raises(projects.ProjectError, match="DATABASE_URL is a secret of shop"):
        projects.set_variable(shop, "DATABASE_URL", "postgres://p")
    assert state.project_variables(shop) == {}


def test_unset_removes_either_kind(shop):
    projects.set_variable(shop, "BOARD_URL", "b")
    projects.set_secret(shop, "GH_TOKEN", "g")
    assert projects.unset(shop, "GH_TOKEN") == []
    assert not secret_file("GH_TOKEN").exists()
    assert projects.unset(shop, "BOARD_URL") == []
    assert state.project_variables(shop) == {}


def test_unset_of_a_name_the_project_lacks_names_both_kinds(shop):
    with pytest.raises(projects.NoSuchVariable) as refused:
        projects.unset(shop, "MODEL_URL")
    assert str(refused.value) == (
        "project shop has no variable or secret MODEL_URL; its variables: none; its secrets: none"
    )
    projects.set_variable(shop, "BOARD_URL", "b")
    projects.set_secret(shop, "GH_TOKEN", "g")
    with pytest.raises(projects.NoSuchVariable) as refused:
        projects.unset(shop, "MODEL_URL")
    assert str(refused.value) == (
        "project shop has no variable or secret MODEL_URL; its variables: BOARD_URL; "
        "its secrets: GH_TOKEN"
    )


def test_the_apis_unsets_take_one_kind_each(shop):
    projects.set_variable(shop, "BOARD_URL", "b")
    projects.set_secret(shop, "GH_TOKEN", "g")
    with pytest.raises(projects.NoSuchVariable) as refused:
        projects.unset_variable(shop, "GH_TOKEN")
    assert str(refused.value) == "project shop has no variable GH_TOKEN; its variables: BOARD_URL"
    with pytest.raises(projects.NoSuchVariable) as refused:
        projects.unset_secret(shop, "BOARD_URL")
    assert str(refused.value) == "project shop has no secret BOARD_URL; its secrets: GH_TOKEN"
    assert secret_file("GH_TOKEN").exists() and projects.variables(shop) == {"BOARD_URL": "b"}
    assert projects.unset_secret(shop, "GH_TOKEN") == []
    assert projects.secrets(shop) == []


def test_set_secret_answers_the_running_sessions(shop, monkeypatch):
    monkeypatch.setattr(projects, "running", lambda id: ["a-run"])
    assert projects.set_secret(shop, "GH_TOKEN", "g") == ["a-run"]
    assert projects.unset(shop, "GH_TOKEN") == ["a-run"]
    projects.set_secret(shop, "GH_TOKEN", "g")
    assert projects.unset_secret(shop, "GH_TOKEN") == ["a-run"]


def test_a_link_on_the_way_is_a_projects_refusal(shop, tmp_path):
    projects.set_secret(shop, "GH_TOKEN", "g")
    folder = project_secrets.folder(shop)
    os.rename(folder, tmp_path / "elsewhere")
    folder.symlink_to(tmp_path / "elsewhere")
    text = (
        f"{folder} is a symbolic link: LADO writes and removes a project's secrets only in "
        "its own folders"
    )
    for call in (
        lambda: projects.set_secret(shop, "GH_TOKEN", "new"),
        lambda: projects.unset(shop, "GH_TOKEN"),
        lambda: projects.unset_secret(shop, "GH_TOKEN"),
    ):
        with pytest.raises(projects.ProjectError) as refused:
            call()
        assert str(refused.value) == text
    assert (tmp_path / "elsewhere" / "GH_TOKEN").read_text() == "g"


def test_a_failed_write_names_the_failure_not_the_value(shop, monkeypatch):
    def full(fd, data):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(project_secrets.os, "write", full)
    with pytest.raises(projects.ProjectError) as refused:
        projects.set_secret(shop, "GH_TOKEN", "canary-91c")
    assert (
        str(refused.value) == "could not write the secret GH_TOKEN of shop: No space left on device"
    )
    assert projects.secrets(shop) == []
