"""The GitHub login taken over once into the github.com git server, for real (openspec
capability git-servers): `lado start` on a lado.db an older LADO left takes the GH_TOKEN of
the outside folder, or the GitHub CLI's own login, over and says so; the fake agent then
clones, pushes and runs `gh` with the entry's token, whatever happens to the login outside
LADO afterwards; a removal is never undone by the takeover; with neither github.com is a
host not in the list; a GitHub Enterprise server gives `gh` its token and host.

github.com is tests/fake_git_server.py, api.github.com tests/fake_git_api.py and
ghe.test:8443 another fake git server, each over TLS with a certificate of a test CA only
this test's processes trust, all reached through one local proxy (HTTPS_PROXY): no network.
`gh` is a stub on PATH that writes down each call with its GitHub variables and answers
`auth token` as gh does: GH_TOKEN, else the login of its config folder."""

import json
import os
import subprocess
import sys
from pathlib import Path

import agent_helpers
import fake_git_api
import fake_provider
import pytest
from fake_git_server import Server

from lado import agent_env, git_kinds, git_servers, runtime, state

pytestmark = pytest.mark.integration

SESSION = "ghtake"
TOKEN = "ghp_CANARY_integration_7b1f"
GHE_TOKEN = "ghe_CANARY_integration_29ad"
LINE = "LADO took your GitHub login ({}) into Settings → Git servers: github.com, signed in as "

GH_STUB = """#!{python}
import json, os, sys
from pathlib import Path

names = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GH_HOST", "GH_CONFIG_DIR")
seen = {{"args": sys.argv[1:], "env": {{n: os.environ.get(n) for n in names}}}}
with open({log!r}, "a") as log:
    log.write(json.dumps(seen) + "\\n")
if sys.argv[1:3] == ["auth", "token"]:
    if os.environ.get("GH_TOKEN"):
        print(os.environ["GH_TOKEN"])
        sys.exit(0)
    config = os.environ.get("GH_CONFIG_DIR") or os.path.expanduser("~/.config/gh")
    hosts = Path(config) / "hosts.yml"
    if hosts.exists():
        print(hosts.read_text().split("oauth_token:")[1].split()[0])
        sys.exit(0)
    print("no oauth token found for github.com", file=sys.stderr)
    sys.exit(1)
"""


class World:
    def __init__(self, tmp_path: Path):
        folders = {name: tmp_path / f"ca-{name}" for name in ("gh", "api", "ghe")}
        for folder in folders.values():
            folder.mkdir()
        ca_gh, cert_gh = fake_git_api.make_ca_certificate(folders["gh"], "github.com")
        ca_api, cert_api = fake_git_api.make_ca_certificate(folders["api"], "api.github.com")
        ca_ghe, cert_ghe = fake_git_api.make_ca_certificate(folders["ghe"], "ghe.test")
        self.bundle = tmp_path / "ca-bundle.crt"
        self.bundle.write_text("".join(p.read_text() for p in (ca_gh, ca_api, ca_ghe)))
        work = agent_helpers.init_repo(tmp_path / "seed")
        self.github = Server(tmp_path / "github", TOKEN, cert_gh, profile="github")
        self.github.repository("team/app.git", work)
        self.ghe = Server(tmp_path / "ghe", GHE_TOKEN, cert_ghe, profile="github")
        self.ghe.repository("team/app.git", work)
        self.api = fake_git_api.Server("github-com", token=TOKEN, certificate=cert_api)
        self.proxy = fake_git_api.ConnectProxy(
            {
                "github.com:443": ("127.0.0.1", self.github.port),
                "api.github.com:443": ("127.0.0.1", self.api.port),
                "ghe.test:8443": ("127.0.0.1", self.ghe.port),
            }
        )
        self.gh = tmp_path / "gh-stub"
        self.gh.mkdir()
        self.calls = self.gh / "calls.jsonl"
        (self.gh / "gh").write_text(GH_STUB.format(python=sys.executable, log=str(self.calls)))
        (self.gh / "gh").chmod(0o755)

    def gh_calls(self, *args: str) -> list[dict]:
        if not self.calls.exists():
            return []
        found = [json.loads(line) for line in self.calls.read_text().splitlines()]
        return [c for c in found if c["args"][: len(args)] == list(args)]

    def close(self):
        self.proxy.close()
        self.api.close()
        self.github.close()
        self.ghe.close()


@pytest.fixture
def world(tmp_path, monkeypatch):
    found = World(tmp_path)
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "global").write_text("[user]\n\tname = LADO test\n\temail = test@lado.invalid\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(configs / "global"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for name in ("http_proxy", "HTTP_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.delenv(name, raising=False)
    for name in ("https_proxy", "HTTPS_PROXY"):
        monkeypatch.setenv(name, found.proxy.url)
    for name in ("no_proxy", "NO_PROXY"):
        monkeypatch.setenv(name, "127.0.0.1,localhost")
    monkeypatch.setenv("SSL_CERT_FILE", str(found.bundle))
    monkeypatch.setenv("GIT_SSL_CAINFO", str(found.bundle))
    monkeypatch.setenv("PATH", f"{found.gh}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.delenv(agent_env.ENV_DIR_VAR, raising=False)
    yield found
    for name in (SESSION,):
        if state.get_session(name) and not state.get_session(name).stopped_at:
            runtime.stop_session(name)
    found.close()


def lado(*args: str, timeout: float = 90) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(fake_provider.LADO), *args],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=timeout,
    )


def older_lado_db() -> None:
    """lado.db as the LADO before this one left it: no takeover yet."""
    state.git_servers()
    agent_helpers.previous_schema()


def wait_idle(agent: str) -> None:
    agent_helpers.wait_for(
        lambda: (a := state.get_agent(SESSION, agent)) and a.status == state.IDLE,
        f"{agent} idle",
        SESSION,
    )


def run_in_agent(agent: str, tmp_path: Path, name: str, lines: list[str]) -> Path:
    """Have `agent` run `lines` as a shell script; each `run <name> <command>` keeps its
    output and status in the folder returned."""
    out = tmp_path / f"out-{name}"
    out.mkdir()
    script = tmp_path / f"{name}.sh"
    script.write_text(
        "\n".join(
            [
                "set -u",
                f'OUT="{out}"',
                'run() { n=$1; shift; "$@" > "$OUT/$n.out" 2> "$OUT/$n.err"; '
                'echo $? > "$OUT/$n.code"; }',
                *lines,
                'touch "$OUT/done"',
            ]
        )
        + "\n"
    )
    runtime.send_message(SESSION, "human", agent, f"sh sh {script}")
    agent_helpers.wait_for(lambda: (out / "done").exists(), f"{agent}'s script", SESSION)
    return out


def code(out: Path, name: str) -> tuple[int, str]:
    return int((out / f"{name}.code").read_text()), (out / f"{name}.err").read_text()


def environ(agent: str) -> dict[str, str]:
    path = agent_helpers.fake_logs(SESSION, agent) / "seen.json"
    return json.loads(path.read_text()).get("environ", {}) if path.exists() else {}


def test_an_outside_token_is_taken_over_once_and_then_not_used(
    world, repo, tmp_path, lado_home, monkeypatch
):
    outside = tmp_path / "secrets"
    outside.mkdir()
    (outside / "GH_TOKEN").write_text(TOKEN + "\n")
    monkeypatch.setenv(agent_env.ENV_DIR_VAR, str(outside))
    older_lado_db()

    started = lado("start", str(repo), "--name", SESSION, "--provider", "fake", "--no-attach")
    assert started.returncode == 0, started.stderr
    source = f"GH_TOKEN in {outside}"
    assert LINE.format(source) + f"{fake_git_api.LOGIN}." in started.stdout.splitlines()
    assert TOKEN not in started.stdout + started.stderr
    record = state.github_takeover()
    assert (record.outcome, record.source) == ("saved", source)
    checked = lado("git-server", "check", "github.com")
    assert checked.returncode == 0, checked.stderr
    assert "Works: GitHub, signed in as" in checked.stdout

    wait_idle("supervisor")
    out = run_in_agent(
        "supervisor",
        tmp_path,
        "first",
        [
            f'cd "{tmp_path}"',
            "run clone git clone -q https://github.com/team/app.git agent-app",
            "cd agent-app",
            "git commit -q --allow-empty -m from-the-agent",
            "run push git push -q origin HEAD:main",
            "run gh gh api user",
        ],
    )
    for name in ("clone", "push", "gh"):
        assert code(out, name)[0] == 0, code(out, name)
    authed = {(r.user, r.password) for r in world.github.git_requests() if r.password}
    assert authed == {("x-access-token", TOKEN)}
    [api] = world.gh_calls("api", "user")
    assert api["env"]["GH_TOKEN"] == TOKEN
    assert api["env"]["GH_CONFIG_DIR"].startswith(str(lado_home / "agents" / SESSION))
    assert (api["env"]["GITHUB_TOKEN"], api["env"]["GH_HOST"]) == (None, None)

    doctor = lado("doctor").stdout
    assert f"[warn] GitHub login outside LADO: GH_TOKEN in {outside} set but not used" in doctor
    assert f"[info] GitHub login: taken over from {source} on " in doctor

    # The outside token changed: a new agent still gets the entry's, git and gh alike.
    (outside / "GH_TOKEN").write_text("ghp_garbage_outside\n")
    runtime.send_message(SESSION, "human", "supervisor", "spawn sleep 0")
    agent_helpers.wait_for(lambda: environ("worker"), "the worker to report", SESSION)
    assert environ("worker")["GH_TOKEN"] == TOKEN
    out = run_in_agent(
        "supervisor", tmp_path, "again", ["run ls git ls-remote https://github.com/team/app.git"]
    )
    assert code(out, "ls")[0] == 0, code(out, "ls")

    # Removed: nothing changes but doctor's line; the takeover never runs again.
    (outside / "GH_TOKEN").unlink()
    doctor = lado("doctor").stdout
    assert "GitHub login outside LADO" not in doctor
    assert state.github_takeover() == record
    assert [s.host for s in state.git_servers()] == ["github.com"]
    runtime.stop_session(SESSION)


def test_the_github_clis_login_is_taken_once_and_a_removal_stays(
    world, repo, tmp_path, monkeypatch
):
    config = tmp_path / "gh-config"
    config.mkdir()
    (config / "hosts.yml").write_text(f"github.com:\n    oauth_token: {TOKEN}\n    user: me\n")
    monkeypatch.setenv("GH_CONFIG_DIR", str(config))
    older_lado_db()

    started = lado("start", str(repo), "--name", SESSION, "--provider", "fake", "--no-attach")
    assert started.returncode == 0, started.stderr
    assert LINE.format("the GitHub CLI's login") + f"{fake_git_api.LOGIN}." in started.stdout
    [taken] = world.gh_calls("auth", "token")
    assert (taken["env"]["GH_CONFIG_DIR"], taken["env"]["GH_TOKEN"]) == (str(config), None)

    removed = lado("git-server", "remove", "github.com")
    assert removed.returncode == 0, removed.stderr
    runtime.stop_session(SESSION)
    again = lado("start", str(repo), "--name", SESSION, "--provider", "fake", "--no-attach")
    assert again.returncode == 0, again.stderr
    assert "LADO took" not in again.stdout
    assert state.git_servers() == []
    assert len(world.gh_calls("auth", "token")) == 1  # not asked again
    wait_idle("supervisor")
    assert "GH_TOKEN" not in environ("supervisor")
    out = run_in_agent("supervisor", tmp_path, "nologin", ["run gh gh auth token"])
    assert code(out, "gh")[0] == 1  # its own config folder holds no login
    runtime.stop_session(SESSION)


def test_no_entry_and_no_login_is_a_host_not_in_the_list(world, tmp_path):
    older_lado_db()
    folder = tmp_path / "work" / "app"
    done = lado("start", "https://github.com/team/app.git", str(folder), "--provider", "fake")
    assert done.returncode == 1
    assert "github.com asks for a login" in done.stderr
    assert (
        "lado: Add it as a git server with a token: lado git-server add https://github.com --token"
        in done.stderr.splitlines()
    )
    assert state.github_takeover().outcome == "none"
    assert all(r.password is None for r in world.github.git_requests())


def test_github_enterprise_gives_gh_its_token_and_host(world, tmp_path, lado_home):
    repo = agent_helpers.init_repo(tmp_path / "ghe-app")
    url = "https://ghe.test:8443/team/app.git"
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", url], check=True)
    checked = git_servers.Checked(git_kinds.by_name("github"), fake_git_api.LOGIN)
    git_servers.save(git_servers.address("https://ghe.test:8443"), checked, GHE_TOKEN)
    runtime.start_session(str(repo), SESSION, None, "fake")
    wait_idle("supervisor")
    out = run_in_agent(
        "supervisor",
        tmp_path,
        "ghe",
        [
            f'cd "{repo}"',
            "run ls git ls-remote origin",
            "run pr gh api -X POST repos/team/app/pulls -f title=t -f head=x -f base=main",
        ],
    )
    assert code(out, "ls")[0] == 0, code(out, "ls")
    [pr] = world.gh_calls("api", "-X", "POST")
    assert (pr["env"]["GH_ENTERPRISE_TOKEN"], pr["env"]["GH_HOST"]) == (GHE_TOKEN, "ghe.test:8443")
    assert pr["env"]["GH_TOKEN"] is None
    authed = {(r.user, r.password) for r in world.ghe.git_requests() if r.password}
    assert authed == {("x-access-token", GHE_TOKEN)}
    runtime.stop_session(SESSION)
