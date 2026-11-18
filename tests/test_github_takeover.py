"""The GitHub login taken over once into the github.com git server (lado.github_takeover):
its sources in order, its outcomes, once per LADO_HOME, again after a failure to read the
GitHub CLI's login, and the line it says. The GitHub API is the fake of
tests/fake_git_api.py reached as api.github.com through a local proxy; `gh` is a stub on
PATH."""

from __future__ import annotations

import threading

import fake_git_api as fake
import pytest

from lado import agent_env, git_credential, github_takeover, model_servers, state, telemetry

TOKEN = "ghp_CANARY_takeover_51c2"
GH_LINE = "LADO took your GitHub login ({}) into Settings → Git servers: github.com, signed in as "


@pytest.fixture
def github(monkeypatch, tmp_path):
    """The fake GitHub API as https://api.github.com, taking TOKEN."""
    with fake.reached_as(monkeypatch, tmp_path, "api.github.com", "github-com", token=TOKEN) as s:
        yield s


@pytest.fixture
def gh(tmp_path, monkeypatch):
    """A stub `gh` on PATH: `gh auth token` prints the file `token` of its folder, or exits
    as `fail` says (`status`, a line on stderr), or sleeps `sleep` seconds first."""
    folder = tmp_path / "gh-stub"
    folder.mkdir()
    script = folder / "gh"
    script.write_text(
        "#!/bin/sh\n"
        f'echo "$@" >> "{folder}/calls"\n'
        f'[ -f "{folder}/sleep" ] && sleep "$(cat "{folder}/sleep")"\n'
        f'if [ -f "{folder}/fail" ]; then cat "{folder}/fail" >&2; exit 1; fi\n'
        f'if [ -f "{folder}/token" ]; then cat "{folder}/token"; exit 0; fi\n'
        "echo 'no oauth token found for github.com' >&2; exit 1\n"
    )
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}:/usr/bin:/bin")
    return folder


@pytest.fixture(autouse=True)
def no_login(monkeypatch, lado_home):
    for name in agent_env.GITHUB_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv(agent_env.ENV_DIR_VAR, raising=False)
    monkeypatch.setenv(agent_env.SOURCE_VAR, agent_env.INHERIT)


def outside(monkeypatch, tmp_path, **values) -> str:
    folder = tmp_path / "secrets"
    folder.mkdir(exist_ok=True)
    for name, value in values.items():
        (folder / name).write_text(value + "\n")
    monkeypatch.setenv(agent_env.ENV_DIR_VAR, str(folder))
    return str(folder)


def entry() -> state.GitServer | None:
    return state.git_server_by_host("github.com")


def test_a_token_of_the_outside_folder_is_saved(github, gh, monkeypatch, tmp_path, lado_home):
    folder = outside(monkeypatch, tmp_path, GH_TOKEN=TOKEN)
    monkeypatch.setenv("GH_TOKEN", "ghp_of_the_shell")  # a lower layer
    line = github_takeover.run()
    source = f"GH_TOKEN in {folder}"
    assert line == GH_LINE.format(source) + f"{fake.LOGIN}."
    saved = entry()
    assert (saved.address, saved.kind, saved.login) == ("https://github.com", "github", fake.LOGIN)
    assert git_credential.read_token(saved.id) == TOKEN
    record = state.github_takeover()
    assert (record.outcome, record.source) == ("saved", source)
    assert (tmp_path / "secrets" / "GH_TOKEN").read_text() == TOKEN + "\n"  # untouched
    assert not (gh / "calls").exists()


def test_gh_token_beats_github_token_of_a_higher_layer(github, gh, monkeypatch, tmp_path):
    outside(monkeypatch, tmp_path, GITHUB_TOKEN="ghp_other")
    monkeypatch.setenv("GH_TOKEN", TOKEN)
    assert github_takeover.run() == GH_LINE.format("GH_TOKEN of your shell") + f"{fake.LOGIN}."


def test_github_token_of_the_shell(github, gh, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
    github_takeover.run()
    assert state.github_takeover().source == "GITHUB_TOKEN of your shell"
    assert entry().login == fake.LOGIN


def test_the_github_clis_login(github, gh):
    (gh / "token").write_text(TOKEN + "\n")
    line = github_takeover.run()
    assert line == GH_LINE.format("the GitHub CLI's login") + f"{fake.LOGIN}."
    assert (gh / "calls").read_text() == "auth token --hostname github.com\n"
    assert git_credential.read_token(entry().id) == TOKEN


def test_a_refused_token_is_not_saved(github, gh, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "ghp_wrong")
    assert github_takeover.run() == (
        "GitHub refused the token of GH_TOKEN of your shell: add github.com in Settings → "
        "Git servers."
    )
    assert entry() is None
    record = state.github_takeover()
    assert (record.outcome, record.source) == ("refused", "GH_TOKEN of your shell")


def test_no_answer_saves_it_unchecked(monkeypatch, tmp_path, gh):
    monkeypatch.setattr(model_servers, "TIMEOUT", 1)
    with fake.reached_as(monkeypatch, tmp_path, "api.github.com", "github-com-hangs"):
        monkeypatch.setenv("GH_TOKEN", TOKEN)
        line = github_takeover.run()
    assert line == (
        "LADO took your GitHub login (GH_TOKEN of your shell) into Settings → Git servers: "
        "github.com, not checked yet."
    )
    assert (entry().login, state.github_takeover().outcome) == (None, "unchecked")


def test_nothing_found(gh):
    assert github_takeover.run() is None
    assert entry() is None
    assert (state.github_takeover().outcome, state.github_takeover().source) == ("none", None)


def test_no_gh_installed_is_nothing_found(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert github_takeover.run() is None
    assert state.github_takeover().outcome == "none"


def test_once(github, gh, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", TOKEN)
    github_takeover.run()
    requests = len(github.requests)
    from lado import git_servers

    git_servers.remove(git_servers.address("github.com"))
    assert github_takeover.run() is None
    assert entry() is None
    assert len(github.requests) == requests


def test_an_entry_already_there_is_kept(github, gh, monkeypatch):
    state.save_git_server("g1", "https://github.com", "github.com", "github", "mine")
    state.set_git_server_author("g1", "Me", "me@example.com")
    monkeypatch.setenv("GH_TOKEN", TOKEN)
    assert github_takeover.run() is None
    saved = entry()
    assert (saved.id, saved.login, saved.author_name) == ("g1", "mine", "Me")
    assert state.github_takeover().outcome == "kept"
    assert github.requests == []


@pytest.mark.parametrize(
    ("fail", "sleep", "why"),
    [
        (
            "error connecting to keychain: User interaction is not allowed.\n",
            None,
            "error connecting to keychain: User interaction is not allowed.",
        ),
        (None, "3", "the GitHub CLI did not answer in 1 s"),
    ],
)
def test_a_gh_failure_runs_again(github, gh, monkeypatch, fail, sleep, why):
    monkeypatch.setattr(github_takeover, "GH_WAIT", 1)
    if fail:
        (gh / "fail").write_text(fail)
    if sleep:
        (gh / "sleep").write_text(sleep)
    assert github_takeover.run() is None
    record = state.github_takeover()
    assert (record.outcome, record.source, record.why) == ("pending", "the GitHub CLI's login", why)
    assert entry() is None
    (gh / "fail").unlink(missing_ok=True)
    (gh / "sleep").unlink(missing_ok=True)
    (gh / "token").write_text(TOKEN)
    assert github_takeover.run() == GH_LINE.format("the GitHub CLI's login") + f"{fake.LOGIN}."
    assert state.github_takeover().outcome == "saved"


def test_two_starts_take_over_once(github, gh, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", TOKEN)
    state.git_servers()  # lado.db made, as a start's migration makes it
    lines = []
    threads = [threading.Thread(target=lambda: lines.append(github_takeover.run())) for _ in "ab"]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(lines, key=str) == sorted(
        [GH_LINE.format("GH_TOKEN of your shell") + f"{fake.LOGIN}.", None], key=str
    )
    assert [s.host for s in state.git_servers()] == ["github.com"]


def test_no_token_in_lado_db_or_the_journal(github, gh, monkeypatch, lado_home):
    monkeypatch.setenv("GH_TOKEN", TOKEN)
    github_takeover.run()
    held = [
        str(p.relative_to(lado_home))
        for p in lado_home.rglob("*")
        if p.is_file() and TOKEN.encode() in p.read_bytes()
    ]
    assert held == [f"git-servers/{entry().id}/token"]
    assert (
        not telemetry.journal_path().exists() or TOKEN not in telemetry.journal_path().read_text()
    )


def test_a_look_without_lado_db_makes_none(github, gh, monkeypatch, lado_home):
    monkeypatch.setenv("GH_TOKEN", TOKEN)
    assert github_takeover.run(make=False) is None
    assert not (lado_home / "lado.db").exists()
    assert github.requests == []


def test_lado_start_says_it_before_a_clone(github, gh, monkeypatch, capsys, tmp_path):
    from lado import clone, runtime
    from lado.cli import main

    monkeypatch.setenv("GH_TOKEN", TOKEN)
    monkeypatch.chdir(tmp_path)

    def stop(*args, **kwargs):
        assert entry() is not None  # taken over before the clone is looked at
        raise runtime.LadoError("stopped here")

    monkeypatch.setattr(clone, "check_target", stop)
    assert main(["start", "https://github.com/team/app", "--provider", "claude"]) == 1
    out = capsys.readouterr().out
    assert out == GH_LINE.format("GH_TOKEN of your shell") + f"{fake.LOGIN}.\n"


def test_a_launch_takes_over_too(github, gh, monkeypatch):
    from lado import runtime

    monkeypatch.setenv("GH_TOKEN", TOKEN)
    state.git_servers()
    runtime.agent_layers(None)
    assert entry().login == fake.LOGIN
