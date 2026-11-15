"""A saved git server inside Codex's sandbox (openspec capability git-servers): git there
calls LADO's credential helper with LADO's Python and reads the token file under LADO_HOME,
as a Codex agent's shell commands do. Real Codex, no model, no network for the helper (git
asks it before any request); the sandbox as LADO gives it to an agent (its permission
profile in the agent's Codex home)."""

import os
import subprocess
import sys

import fake_git_api
import pytest
from agent_helpers import init_repo
from fake_git_server import Server
from real_clis import SANDBOX_ERROR

from lado import git_kinds, git_servers, state
from lado.providers import codex

pytestmark = pytest.mark.smoke

TOKEN = "glpat-CANARY-sandbox-5b2e"


def _in_sandbox(home, cwd, env, *command, given=""):
    return subprocess.run(
        ["codex", "sandbox", "--", *command],
        cwd=cwd,
        env={**env, "CODEX_HOME": str(home)},
        input=given,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize("smoke_provider", ["codex"], indirect=True)
def test_codex_s_sandbox_lets_git_take_a_saved_servers_token(
    smoke_provider, smoke_repo, tmp_path, monkeypatch
):
    certificate = fake_git_api.make_certificate(tmp_path)
    monkeypatch.setenv("GIT_SSL_CAINFO", str(certificate[0]))
    server = Server(tmp_path / "served", TOKEN, certificate)
    try:
        url = server.repository("team/app.git", init_repo(tmp_path / "seed"))
        checked = git_servers.Checked(git_kinds.by_name("gitlab"), "ivan")
        git_servers.save(git_servers.address(server.url), checked, TOKEN)
        env = {**os.environ, **git_servers.variables(os.environ, state.git_servers())}
        home = tmp_path / "agent-codex-home"
        home.mkdir()
        profile = codex._git_profile(smoke_repo)
        codex._write_config(
            home, {"default_permissions": codex.PROFILE, "permissions": {codex.PROFILE: profile}}
        )
        asked = f"protocol=https\nhost=127.0.0.1:{server.port}\npath=team/app.git\n\n"
        error = SANDBOX_ERROR(home, smoke_repo, env) if sys.platform == "linux" else None
        if error is not None:
            # No sandbox here (no user namespaces): Codex then runs an agent's commands
            # outside it (in LADO's container) or asks first (on a host), so git takes the
            # token as anywhere else; this shows that path, and macOS's cell the sandbox's.
            print(f"Codex's sandbox cannot start here ({error}): git checked without it")
            plain = subprocess.run(
                ["git", "credential", "fill"], cwd=smoke_repo, env=env, input=asked,
                capture_output=True, text=True, timeout=60,
            )  # fmt: skip
            assert f"password={TOKEN}\n" in plain.stdout, plain.stderr
            return
        filled = _in_sandbox(home, smoke_repo, env, "git", "credential", "fill", given=asked)
        assert filled.returncode == 0, filled.stderr
        assert "username=oauth2\n" in filled.stdout
        assert f"password={TOKEN}\n" in filled.stdout
        listed = _in_sandbox(home, smoke_repo, env, "git", "ls-remote", url)
        if listed.returncode == 0:
            assert "refs/heads/main" in listed.stdout
            assert {r.password for r in server.git_requests() if r.password} == {TOKEN}
        else:
            # The sandbox's network rule, Codex's own: a push asks to run outside it, as today.
            print(f"git ls-remote in Codex's sandbox: {listed.stderr.strip()[-500:]}")
            assert "lado:" not in listed.stderr
    finally:
        server.close()
