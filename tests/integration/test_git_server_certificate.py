"""A git server's certificate for real (openspec capability git-servers): a local https git
server signed by a test authority no process of the test trusts (no GIT_SSL_CAINFO, no
SSL_CERT_FILE). Without its certificate the check offers the authority and LADO's clone is
refused for it; trusted with `lado git-server certificate`, LADO's clone and the fake
agent's clone, commit and push reach it, its ssh address too, while another host of the
same authority is still refused; git's configs and the system's trust store stay as they
were, and a launch without the certificate gives git none."""

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import agent_helpers
import certificates as made
import fake_git_api
import fake_provider
import pytest
from fake_git_server import Server

from lado import clone, git_kinds, git_servers, runtime, state

pytestmark = pytest.mark.integration

SESSION = "gitcert"
TOKEN = "glpat-CANARY-ce47b1a2"
TRUST_STORE = Path("/etc/ssl")


def _store_print() -> str:
    """A hash of the system's trust store: each file's path, size and time."""
    found = hashlib.sha256()
    if TRUST_STORE.is_dir():
        for path in sorted(TRUST_STORE.rglob("*")):
            if path.is_file():
                info = path.stat()
                found.update(f"{path}:{info.st_size}:{info.st_mtime_ns}\n".encode())
    return found.hexdigest()


@pytest.fixture
def world(tmp_path, monkeypatch):
    """`listed` at https://localhost:<port> and `other` at https://127.0.0.1:<port>, both
    wanting TOKEN with team/app.git, signed by one test authority; git's own configs in
    files of the test."""
    for name in ("GIT_SSL_CAINFO", "SSL_CERT_FILE", "SSL_CERT_DIR", "GIT_SSL_CAPATH"):
        monkeypatch.delenv(name, raising=False)
    root = made.authority("LADO Test CA", "LADO Tests")
    configs = tmp_path / "configs"
    configs.mkdir()
    global_config = configs / "global"
    global_config.write_text("[user]\n\tname = LADO test\n\temail = test@lado.invalid\n")
    system_config = configs / "system"
    system_config.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(system_config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    work = agent_helpers.init_repo(tmp_path / "seed")
    servers = []
    for name, host in (("listed", "localhost"), ("other", "127.0.0.1")):
        chain = made.write_chain(tmp_path / f"{name}-tls", made.server(host, root), root)
        server = Server(tmp_path / name, TOKEN, chain)
        server.url = server.url.replace("127.0.0.1", host)
        server.repository("team/app.git", work)
        servers.append(server)
    ca = made.write_pem(tmp_path / "company-ca.pem", root)
    before = {path: path.read_bytes() for path in (global_config, system_config)}
    yield servers[0], servers[1], root, ca, before
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
    runtime.send_message(SESSION, "human", agent, f"sh sh {script}")
    agent_helpers.wait_for(lambda: (out / "done").exists(), f"{agent}'s script", SESSION)


def script(path: Path, out: Path, lines: list[str]) -> Path:
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


def wait_idle(agent: str) -> None:
    agent_helpers.wait_for(
        lambda: (a := state.get_agent(SESSION, agent)) and a.status == state.IDLE,
        f"{agent} idle",
        SESSION,
    )


def _fingerprint(root: made.Made) -> str:
    return ":".join(f"{b:02X}" for b in root.certificate.fingerprint(made.hashes.SHA256()))


def test_a_trusted_certificate_lets_lado_and_agents_reach_the_server_alone(
    world, repo, tmp_path, lado_home
):
    listed, other, root, ca, before = world
    store = _store_print()
    url = f"{listed.url}/team/app.git"

    # Not trusted: add refuses with the authority's fingerprint and saves nothing.
    refused = lado("git-server", "add", listed.url, "--token", token=TOKEN + "\n")
    assert refused.returncode == 1
    assert f"lado: the certificate of {listed.url} is not trusted" in refused.stderr
    assert f"  SHA-256    {_fingerprint(root)}" in refused.stderr
    assert state.git_servers() == []

    # Saved unchecked: LADO's listing is refused for the certificate, pointing to the check.
    added = lado("git-server", "add", listed.url, "--token", "--kind", "gitlab", token=TOKEN)
    assert added.returncode == 0, added.stderr
    with pytest.raises(clone.CloneError) as untrusted:
        clone.list_branches(url)
    assert untrusted.value.kind == "cert_untrusted", str(untrusted.value)  # git's own words
    assert str(untrusted.value).startswith(
        f"cannot read {url}: the certificate of localhost is not trusted ("
    )
    assert untrusted.value.hint.command == f"lado git-server check {listed.url}"
    checked = lado("git-server", "check", listed.url)
    assert checked.returncode == 1
    assert f"  SHA-256    {_fingerprint(root)}" in checked.stderr
    assert not git_servers.certificate_file(state.git_servers()[0].id).exists()

    # Trusted from the file.
    trusted = lado("git-server", "certificate", listed.url, str(ca))
    assert trusted.returncode == 0, trusted.stderr
    assert trusted.stdout.splitlines()[:2] == [
        f"Trusted LADO Test CA for {listed.url}.",
        f"Works: GitLab, signed in as {fake_git_api.LOGIN}; the token's rights are not checked.",
    ]
    assert "main" in clone.list_branches(url).branches

    runtime.start_session(str(repo), SESSION, None, "fake")
    wait_idle("supervisor")
    work, out = tmp_path / "agent-work", tmp_path / "agent-out"
    work.mkdir()
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
                "run ssh git ls-remote git@localhost:team/app.git",
                f"GIT_TERMINAL_PROMPT=0 run other git ls-remote {other.url}/team/app.git",
            ],
        ),
        out,
    )
    for name in ("clone", "push", "ssh"):
        code, _, stderr = result(out, name)
        assert code == 0, f"{name}: {stderr}"
    code, _, stderr = result(out, "other")
    # The same authority, another host: git's curl (OpenSSL or GnuTLS) refuses it.
    assert code != 0 and clone.kind_of(stderr) == "cert_untrusted", stderr
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

    # Cleared: a new agent's git gets no certificate and is refused as before.
    cleared = lado("git-server", "certificate", listed.url, "--clear")
    assert cleared.returncode == 0, cleared.stderr
    out2 = tmp_path / "agent-out-2"
    runtime.send_message(SESSION, "human", "supervisor", "spawn sleep 0")
    agent_helpers.wait_for(
        lambda: (agent_helpers.fake_logs(SESSION, "worker") / "seen.json").exists(),
        "the worker to report",
        SESSION,
    )
    worker = (agent_helpers.fake_logs(SESSION, "worker") / "seen.json").read_text()
    assert "sslCAInfo" not in worker
    wait_idle("worker")
    run_in_agent(
        "worker",
        script(
            tmp_path / "agent2.sh",
            out2,
            [f'cd "{work}"', f"GIT_TERMINAL_PROMPT=0 run again git ls-remote {url}"],
        ),
        out2,
    )
    code, _, stderr = result(out2, "again")
    assert code != 0 and clone.kind_of(stderr) == "cert_untrusted", stderr
    runtime.stop_session(SESSION)

    # Nothing written to git's configs or the system's trust store.
    assert {p: p.read_bytes() for p in before} == before
    assert _store_print() == store
    assert not os.environ.get("GIT_SSL_CAINFO")


def test_a_launch_without_a_certificate_gives_git_none(world, repo, lado_home):
    listed, _, _, _, _ = world
    checked = git_servers.Checked(git_kinds.by_name("gitlab"), fake_git_api.LOGIN)
    git_servers.save(git_servers.address(listed.url), checked, TOKEN)
    runtime.start_session(str(repo), SESSION, None, "fake")
    try:
        wait_idle("supervisor")
        seen = (agent_helpers.fake_logs(SESSION, "supervisor") / "seen.json").read_text()
        assert git_servers.HELPER in seen
        assert "sslCAInfo" not in seen
    finally:
        runtime.stop_session(SESSION)
