"""Git servers for real (openspec capability git-servers): `lado git-server add` against a
local https git server that wants a token, then an agent of the fake agent and LADO's own
clone reach it with no prompt, its ssh addresses too, while a host not in the list goes as
before; the global and system git configs stay as they were and the token is in its file
alone. The server's certificate is trusted by this test's processes only."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import agent_helpers
import fake_git_api
import fake_provider
import pytest
from fake_git_server import Server

from lado import git_kinds, git_servers, runtime, state

pytestmark = pytest.mark.integration

SESSION = "gitsrv"
TOKEN = "glpat-CANARY-0c7d1e9b"


@pytest.fixture
def world(tmp_path, monkeypatch):
    """Two https git servers wanting TOKEN, each with team/app.git; git's own configs in
    files of the test (a global one whose store helper would keep a token in `stored`)."""
    certificate = fake_git_api.make_certificate(tmp_path)
    configs = tmp_path / "configs"
    configs.mkdir()
    stored = configs / "stored-credentials"
    global_config = configs / "global"
    global_config.write_text(
        "[user]\n\tname = LADO test\n\temail = test@lado.invalid\n"
        f"[credential]\n\thelper = store --file={stored}\n"
    )
    system_config = configs / "system"
    system_config.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(system_config))
    # Apple's git reads a system config of its own besides (osxkeychain, whose keychain a
    # HOME of the test's has not: macOS asks in a window), which only this turns off.
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_SSL_CAINFO", str(certificate[0]))
    monkeypatch.setenv("SSL_CERT_FILE", str(certificate[0]))
    work = agent_helpers.init_repo(tmp_path / "seed")
    servers = []
    for name in ("listed", "other"):
        server = Server(tmp_path / name, TOKEN, certificate)
        server.repository("team/app.git", work)
        servers.append(server)
    before = {path: path.read_bytes() for path in (global_config, system_config)}
    yield servers[0], servers[1], stored, before
    for server in servers:
        server.close()


def lado(*args: str, token: str | None = None, timeout: float = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(fake_provider.LADO), *args],
        input=token,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_in_agent(agent: str, script: Path, out: Path) -> None:
    """Have `agent` run the shell `script` as its shell tool, and wait for it to finish."""
    runtime.send_message(SESSION, "human", agent, f"sh sh {script}")
    agent_helpers.wait_for(lambda: (out / "done").exists(), f"{agent}'s script", SESSION)


def script(path: Path, out: Path, lines: list[str]) -> Path:
    """A shell script whose `run <name> <command>` keeps the command's output and status in
    `out`, then marks `out`/done."""
    out.mkdir(parents=True, exist_ok=True)
    body = [
        "set -u",
        f'OUT="{out}"',
        'run() { name=$1; shift; "$@" > "$OUT/$name.out" 2> "$OUT/$name.err"; '
        'echo $? > "$OUT/$name.code"; }',
        *lines,
        'touch "$OUT/done"',
    ]
    path.write_text("\n".join(body) + "\n")
    return path


def result(out: Path, name: str) -> tuple[int, str, str]:
    return (
        int((out / f"{name}.code").read_text()),
        (out / f"{name}.out").read_text(),
        (out / f"{name}.err").read_text(),
    )


def environ(agent: str) -> dict[str, str]:
    path = agent_helpers.fake_logs(SESSION, agent) / "seen.json"
    return json.loads(path.read_text()).get("environ", {}) if path.exists() else {}


def holding_token(*roots: Path) -> list[str]:
    return sorted(
        str(p)
        for root in roots
        for p in root.rglob("*")
        if p.is_file() and not p.is_symlink() and TOKEN.encode() in p.read_bytes()
    )


def wait_idle(agent: str) -> None:
    agent_helpers.wait_for(
        lambda: (a := state.get_agent(SESSION, agent)) and a.status == state.IDLE,
        f"{agent} idle",
        SESSION,
    )


def test_agents_and_lados_clone_reach_a_listed_server_with_its_token(
    world, repo, tmp_path, lado_home
):
    listed, other, stored, before = world
    added = lado("git-server", "add", listed.url, "--token", token=TOKEN + "\n")
    assert added.returncode == 0, added.stderr
    assert added.stdout.splitlines()[0] == f"GitLab, signed in as {fake_git_api.LOGIN}"
    assert TOKEN not in added.stdout + added.stderr
    [server] = state.git_servers()

    runtime.start_session(str(repo), SESSION, None, "fake")
    wait_idle("supervisor")
    work, out = tmp_path / "agent-work", tmp_path / "agent-out"
    work.mkdir()
    git_dir = os.path.dirname(shutil.which("git"))
    url = f"{listed.url}/team/app.git"
    run_in_agent(
        "supervisor",
        script(
            tmp_path / "agent.sh",
            out,
            [
                f'cd "{work}"',
                f"run clone git clone -q {url} app",
                "cd app",
                "git commit -q --allow-empty -m from-the-agent",
                "run push git push -q origin HEAD:main",
                "run scp git ls-remote git@127.0.0.1:team/app.git",
                "run ssh git ls-remote ssh://git@127.0.0.1/team/app.git",
                f"run nolado env PATH={git_dir}:/usr/bin:/bin git ls-remote {url}",
                f"GIT_TERMINAL_PROMPT=0 run other git ls-remote {other.url}/team/app.git",
            ],
        ),
        out,
    )
    for name in ("clone", "push", "scp", "ssh", "nolado"):
        code, stdout, stderr = result(out, name)
        assert code == 0, f"{name}: {stderr}"
    for name in ("scp", "ssh", "nolado"):
        assert "refs/heads/main" in result(out, name)[1]
    code, _, stderr = result(out, "other")
    assert code != 0 and "lado:" not in stderr  # as without LADO: no helper of its asked

    # The listed server saw the token with GitLab's user, the push among it; the other never.
    authed = [r for r in listed.git_requests() if r.password is not None]
    assert {(r.user, r.password) for r in authed} == {("oauth2", TOKEN)}
    assert any("git-receive-pack" in r.path for r in authed)
    assert all(r.password is None for r in other.git_requests())
    log = subprocess.run(
        ["git", "-C", str(listed.root / "team/app.git"), "log", "-1", "--format=%s", "main"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert log.stdout.strip() == "from-the-agent"

    # LADO's own clone of a session's repository.
    clone_into = tmp_path / "work" / "app2"
    started = lado("start", url, str(clone_into), "--provider", "fake", "--no-attach")
    try:
        assert started.returncode == 0, started.stderr
        assert (clone_into / ".git").is_dir()
    finally:
        if state.get_session("app2"):
            runtime.stop_session("app2")

    # Removed: the running agent's git stops without a prompt, a new agent gets nothing.
    removed = lado("git-server", "remove", listed.url)
    assert removed.returncode == 0, removed.stderr
    out2 = tmp_path / "agent-out-2"
    run_in_agent(
        "supervisor",
        script(tmp_path / "agent2.sh", out2, [f'cd "{work}/app"', "run fetch git fetch -q"]),
        out2,
    )
    code, _, stderr = result(out2, "fetch")
    assert code != 0
    assert (
        f"lado: no token for {listed.url}; add it again: lado git-server add {listed.url} --token"
        in stderr
    )
    runtime.send_message(SESSION, "human", "supervisor", "spawn sleep 0")
    agent_helpers.wait_for(lambda: environ("worker"), "the worker to report", SESSION)
    assert not any(git_servers.HELPER in v for v in environ("worker").values())
    assert any(git_servers.HELPER in v for v in environ("supervisor").values())
    wait_idle("worker")
    runtime.stop_session(SESSION)

    # Nothing written to git's configs, no store kept the token, it is in its file alone
    # (and that file is gone with the server).
    assert {p: p.read_bytes() for p in before} == before
    assert not stored.exists()
    assert holding_token(lado_home, repo, work, clone_into) == []
    assert not (lado_home / "git-servers" / server.id).exists()


def test_an_old_git_on_the_agents_path_refuses_a_start_while_a_server_is_saved(
    repo, tmp_path, monkeypatch
):
    real = shutil.which("git")
    folder = tmp_path / "old-git"
    folder.mkdir()
    (folder / "git").write_text(
        '#!/bin/sh\nif [ "$1" = "--version" ]; then echo "git version 2.30.2"; exit 0; fi\n'
        f'exec {real} "$@"\n'
    )
    (folder / "git").chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")
    checked = git_servers.Checked(git_kinds.by_name("gitlab"), "ivan")
    git_servers.save(git_servers.address("https://gitlab.corp.ru"), checked, TOKEN)
    with pytest.raises(runtime.LadoError) as refused:
        runtime.start_session(str(repo), SESSION, None, "fake")
    assert "git 2.30.2 is older than 2.31" in str(refused.value)
    assert "lado git-server remove" in str(refused.value)
    assert state.get_session(SESSION) is None
