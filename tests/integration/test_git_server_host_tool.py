"""The repository's server and its tool for real (openspec capability git-servers): a
session on a repository of a saved GitLab (a local https git server under a test authority)
tells the fake agent its server and `glab`, a github.com repository `gh`, another host
nothing; the agent's glab has its own configuration folder and no GitLab variable of the
shell; a glab missing or too old is said by `lado start` and the agent starts. With a real
glab 1.114.0 or newer on PATH, the agent's glab is signed in to the saved server by LADO's
header, trusts its certificate for that server alone, and sends no token elsewhere."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import agent_helpers
import certificates as made
import fake_provider
import pytest
from fake_git_server import Server

from lado import git_kinds, git_servers, runtime, state

pytestmark = pytest.mark.integration

SESSION = "hosttool"
TOKEN = "glpat-CANARY-5be0f417"
SHELL_TOKEN = "glpat-SHELL-CANARY"


@pytest.fixture
def world(tmp_path, monkeypatch):
    """`listed` at https://localhost:<port> (saved as GitLab with its authority) and `other`
    at https://127.0.0.1:<port>, both under one test authority, wanting TOKEN, with
    team/app.git; git's own configs in files of the test; a folder of the test's tools
    first on the agents' PATH (LADO_AGENT_ENV=inherit: the test's environment)."""
    for name in ("GIT_SSL_CAINFO", "SSL_CERT_FILE", "SSL_CERT_DIR", "GIT_SSL_CAPATH"):
        monkeypatch.delenv(name, raising=False)
    root = made.authority("LADO Test CA", "LADO Tests")
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "global").write_text("[user]\n\tname = LADO test\n\temail = t@lado.invalid\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(configs / "global"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    work = agent_helpers.init_repo(tmp_path / "seed")
    servers = []
    for name, host in (("listed", "localhost"), ("other", "127.0.0.1")):
        chain = made.write_chain(tmp_path / f"{name}-tls", made.server(host, root), root)
        server = Server(tmp_path / name, TOKEN, chain, profile="gitlab-full")
        server.url = server.url.replace("127.0.0.1", host)
        server.authority = root  # the test authority that signed its certificate
        server.repository("team/app.git", work)
        servers.append(server)
    listed, other = servers
    checked = git_servers.Checked(git_kinds.by_name("gitlab"), "ivan.petrov")
    git_servers.save(git_servers.address(listed.url), checked, TOKEN, root.pem)
    tools = tmp_path / "tools"
    tools.mkdir()
    monkeypatch.setenv("PATH", f"{tools}{os.pathsep}{os.environ['PATH']}")
    yield listed, other, tools
    for server in servers:
        server.close()


def fake_tool(tools: Path, name: str, line: str) -> None:
    (tools / name).write_text(f"#!/bin/sh\necho '{line}'\n")
    (tools / name).chmod(0o755)


def no_glab(monkeypatch) -> None:
    """The agents' PATH without the folders that hold a glab."""
    folders = os.environ["PATH"].split(os.pathsep)
    path = os.pathsep.join(f for f in folders if not os.path.exists(os.path.join(f, "glab")))
    monkeypatch.setenv("PATH", path)


def seen(agent: str) -> dict:
    path = agent_helpers.fake_logs(SESSION, agent) / "seen.json"
    return json.loads(path.read_text()) if path.exists() else {}


def wait_idle(agent: str) -> None:
    agent_helpers.wait_for(
        lambda: (a := state.get_agent(SESSION, agent)) and a.status == state.IDLE,
        f"{agent} idle",
        SESSION,
    )


def origin(repo: Path, url: str) -> None:
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", url], check=True)


def lado(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(fake_provider.LADO), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def host_of(server: Server) -> str:
    return git_servers.address(server.url).key


def test_an_agent_is_told_its_gitlab_and_glab_gets_its_own_folder(
    world, repo, monkeypatch, lado_home
):
    listed, _, tools = world
    fake_tool(tools, "glab", "glab 1.130.0 (206ebab4f)")
    monkeypatch.setenv("GITLAB_TOKEN", SHELL_TOKEN)
    monkeypatch.setenv("GITLAB_HOST", "gitlab.com")
    origin(repo, f"{listed.url}/team/app.git")
    started = runtime.start_session(str(repo), SESSION, None, "fake")
    assert not [w for w in started.warnings if "glab" in w]
    wait_idle("supervisor")
    given = seen("supervisor")
    assert (
        f"The repository's origin is on GitLab ({host_of(listed)}), a git server LADO signs "
        "you in to: use `glab` for its merge requests; it is logged in already.\n"
    ) in given["prompt"]
    environ = given["environ"]
    folder = lado_home / "agents" / SESSION / "supervisor" / "glab"
    assert environ["GLAB_CONFIG_DIR"] == str(folder)
    assert not {"GITLAB_TOKEN", "GITLAB_HOST"} & environ.keys()
    assert SHELL_TOKEN not in json.dumps(environ)
    assert TOKEN not in (folder / "config.yml").read_text()


@pytest.mark.parametrize(
    ("url", "line"),
    [
        (
            "https://github.com/octo/app.git",
            "The repository's origin is on GitHub (github.com), a git server LADO signs you in "
            "to: use `gh` for its pull requests; it is logged in already.\n",
        ),
        ("https://git.other.example/team/app.git", None),
    ],
)
def test_github_com_gets_gh_and_another_host_no_line(world, repo, url, line):
    _, _, tools = world
    fake_tool(tools, "gh", "gh version 2.83.0 (2026-10-01)")
    checked = git_servers.Checked(git_kinds.by_name("github"), "octo")
    git_servers.save(git_servers.address("github.com"), checked, "ghp_CANARY")
    origin(repo, url)
    runtime.start_session(str(repo), SESSION, None, "fake")
    wait_idle("supervisor")
    prompt = seen("supervisor")["prompt"]
    if line:
        assert line in prompt
    else:
        assert "The repository's origin is on" not in prompt


@pytest.mark.parametrize("which", ["old", "missing"])
def test_lado_start_says_a_glab_missing_or_too_old_and_starts(world, repo, monkeypatch, which):
    listed, _, tools = world
    if which == "old":
        fake_tool(tools, "glab", "glab 1.80.0 (x)")
        said = (
            "glab 1.80.0 is older than 1.114.0, which LADO needs to sign it in to "
            f"{listed.url}; update glab"
        )
    else:
        no_glab(monkeypatch)
        said = (
            "glab is not on the agents' PATH: agents cannot open merge requests on "
            f"{listed.url}; install glab 1.114.0 or newer"
        )
    origin(repo, f"{listed.url}/team/app.git")
    started = lado("start", str(repo), "--provider", "fake", "--no-attach")
    try:
        assert started.returncode == 0, started.stderr
        assert said in started.stdout + started.stderr
        [session] = state.list_sessions()
        assert state.get_agent(session.name, "supervisor") is not None
    finally:
        for session in state.list_sessions():
            runtime.stop_session(session.name)


def real_glab(config: Path) -> str | None:
    """A glab of this computer's that runs and is 1.114.0 or newer; None else. Asked with
    `config` as its configuration folder: glab writes into its configuration at any call."""
    path = shutil.which("glab")
    if path is None:
        return None
    env = {**os.environ, "GLAB_CONFIG_DIR": str(config)}
    try:
        result = subprocess.run(
            [path, "--version"], env=env, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    found = re.search(r"(\d+)\.(\d+)\.(\d+)", result.stdout)
    if result.returncode != 0 or found is None:
        return None
    return path if tuple(map(int, found.groups())) >= (1, 114, 0) else None


def test_a_real_glab_is_signed_in_to_the_saved_server_alone(world, repo, tmp_path, monkeypatch):
    glab = real_glab(tmp_path / "glab-version")
    if glab is None:
        pytest.skip("no glab 1.114.0 or newer on PATH (the container test runs one)")
    listed, other, _ = world
    human = tmp_path / "human"
    (human / ".config" / "glab-cli").mkdir(parents=True)
    own = human / ".config" / "glab-cli" / "config.yml"
    own.write_text("hosts:\n    gitlab.com:\n        token: glpat-HUMANS-OWN\n")
    own.chmod(0o600)
    monkeypatch.setenv("HOME", str(human))
    monkeypatch.setenv("GITLAB_TOKEN", SHELL_TOKEN)
    origin(repo, f"{listed.url}/team/app.git")
    runtime.start_session(str(repo), SESSION, None, "fake")
    wait_idle("supervisor")
    result = run_glab(
        tmp_path,
        [
            f'cd "{repo}"',
            f"run status {glab} auth status",
            f"run user {glab} api user",
            # glab takes no port in --hostname: the other host by its whole URL.
            f"run other {glab} api {other.url}/api/v4/user",
        ],
    )
    code, said = result("status")
    assert code == 0, said
    assert f"Logged in to {host_of(listed)} as ivan.petrov" in said
    code, said = result("user")
    assert code == 0 and '"username": "ivan.petrov"' in said, said
    code, said = result("other")
    assert code != 0 and "x509: certificate signed by unknown authority" in said, said
    assert other.requests == []  # refused at TLS: not even a request without a token
    api = [r for r in listed.requests if r.path.startswith("/api/")]
    assert api and {r.private_token for r in api} == {TOKEN}
    assert own.read_text() == "hosts:\n    gitlab.com:\n        token: glpat-HUMANS-OWN\n"


SECOND_TOKEN = "glpat-CANARY-second-90c4"


def test_each_saved_gitlab_gets_its_own_token_and_no_host_of_the_shell_takes_it(
    world, repo, tmp_path, monkeypatch
):
    """Two saved GitLab servers, and a third host the agents' trust store accepts
    (SSL_CERT_FILE) named by GITLAB_API_HOST and GITLAB_REPO of the shell: each saved server
    gets its own token, the third host nothing."""
    glab = real_glab(tmp_path / "glab-version")
    if glab is None:
        pytest.skip("no glab 1.114.0 or newer on PATH (the container test runs one)")
    listed, other, _ = world
    root = made.authority("LADO Second CA", "LADO Tests")
    chain = made.write_chain(tmp_path / "second-tls", made.server("127.0.0.1", root), root)
    second = Server(tmp_path / "second", SECOND_TOKEN, chain, profile="gitlab-full")
    try:
        checked = git_servers.Checked(git_kinds.by_name("gitlab"), "ivan.petrov")
        git_servers.save(git_servers.address(second.url), checked, SECOND_TOKEN, root.pem)
        # `other` is trusted by the agents' own store, so only LADO's config keeps it out.
        trust = made.write_pem(tmp_path / "trusted.pem", other.authority)
        monkeypatch.setenv("SSL_CERT_FILE", str(trust))
        monkeypatch.setenv("GITLAB_API_HOST", host_of(other))
        monkeypatch.setenv("GITLAB_REPO", f"{host_of(other)}/x/y")
        origin(repo, f"{listed.url}/team/app.git")
        repo2 = agent_helpers.init_repo(tmp_path / "second-repo")
        origin(repo2, f"{second.url}/team/app.git")
        runtime.start_session(str(repo), SESSION, None, "fake")
        wait_idle("supervisor")
        result = run_glab(
            tmp_path,
            [
                f'cd "{repo}"',
                f"run listed {glab} api user",
                f"run mrs {glab} mr list",
                f'cd "{repo2}"',
                f"run second {glab} api user",
            ],
        )
        for name in ("listed", "second"):
            code, said = result(name)
            assert code == 0 and '"username": "ivan.petrov"' in said, f"{name}: {said}"
        assert other.requests == []
        listed_api = [r for r in listed.requests if r.path.startswith("/api/")]
        second_api = [r for r in second.requests if r.path.startswith("/api/")]
        assert listed_api and {r.private_token for r in listed_api} == {TOKEN}
        assert second_api and {r.private_token for r in second_api} == {SECOND_TOKEN}
        assert not [r for r in listed_api if "x%2Fy" in r.path]  # GITLAB_REPO not taken
    finally:
        second.close()


def run_glab(tmp_path: Path, lines: list[str]):
    """Have the supervisor run `lines` in its shell, each `run <name> <command>` keeping
    the command's status and output; a reader of them by name."""
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    body = [
        "set -u",
        f'OUT="{out}"',
        'run() { name=$1; shift; "$@" > "$OUT/$name.out" 2> "$OUT/$name.err"; '
        'echo $? > "$OUT/$name.code"; }',
        *lines,
        'touch "$OUT/done"',
    ]
    script = tmp_path / "glab.sh"
    script.write_text("\n".join(body) + "\n")
    runtime.send_message(SESSION, "human", "supervisor", f"sh sh {script}")
    agent_helpers.wait_for(lambda: (out / "done").exists(), "the agent's glab", SESSION)

    def result(name):
        said = (out / f"{name}.out").read_text() + (out / f"{name}.err").read_text()
        return int((out / f"{name}.code").read_text()), said

    return result
