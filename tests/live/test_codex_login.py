"""Codex agents share a real ChatGPT login (openspec change codex-shared-login): a Codex
session with a worker on OpenAI's model, each agent's auth.json a link to the login file of
a Codex home the human logged in to; that file made stale so each agent refreshes it; both
answer again, the links stay, and the home is still logged in.

Only at a release, with the human: it needs a ChatGPT account, which CI has none of, and it
spends a few of its requests. Log a throwaway Codex home in once, then name it:

    CODEX_HOME=/tmp/lado-codex-live codex login --device-auth
    LADO_LIVE_CODEX_HOME=/tmp/lado-codex-live make test-live PROVIDER=codex

Skipped without it. Afterwards `CODEX_HOME=/tmp/lado-codex-live codex logout` revokes it."""

import datetime
import json
import os
import subprocess
from pathlib import Path

import agent_helpers
import pytest
from agent_helpers import init_repo
from real_clis import answer_dialogs

from lado import providers, runtime, state

pytestmark = pytest.mark.live

SESSION = "live-codex-login"
HOME_VARIABLE = "LADO_LIVE_CODEX_HOME"
FILE_STORE = ["-c", 'cli_auth_credentials_store="file"']


def _status(home: Path) -> str:
    done = subprocess.run(
        ["codex", "login", "status", *FILE_STORE],
        env={**os.environ, "CODEX_HOME": str(home)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    return done.stdout + done.stderr


@pytest.fixture
def chatgpt_home(monkeypatch) -> Path:
    """The Codex home the human logged in to with ChatGPT: the user's own Codex here."""
    named = os.environ.get(HOME_VARIABLE)
    if not named:
        pytest.skip(f"{HOME_VARIABLE} names no Codex home logged in with ChatGPT")
    home = Path(named)
    if "Logged in using ChatGPT" not in _status(home):
        pytest.skip(f"the Codex home {home} is not logged in with ChatGPT")
    monkeypatch.setenv("CODEX_HOME", str(home))
    for name in ("OPENAI_API_KEY", "CODEX_ACCESS_TOKEN"):
        monkeypatch.delenv(name, raising=False)  # the shared file is the login
    return home


def wait_for(check, what: str, timeout: float):
    return agent_helpers.wait_for(check, what, SESSION, timeout, interval=0.5)


def idle(agent: str):
    def check() -> bool:
        answer_dialogs("codex", SESSION, agent)
        found = state.get_agent(SESSION, agent)
        return found is not None and found.status == state.IDLE

    return check


def linked(agent: str, target: Path) -> None:
    auth = providers.base.config_path(state.get_agent(SESSION, agent)) / "auth.json"
    assert auth.is_symlink() and os.readlink(auth) == str(target), auth


def last_refresh(target: Path) -> str:
    return json.loads(target.read_text())["last_refresh"]


def test_codex_agents_share_a_chatgpt_login_and_its_refresh(chatgpt_home, tmp_path):
    target = chatgpt_home / "auth.json"
    repo = init_repo(tmp_path / "repo")
    runtime.start_session(str(repo), SESSION, "bypassPermissions", "codex")
    wait_for(idle("supervisor"), "the supervisor's first turn on its ChatGPT login", 300)
    runtime.spawn_worker(SESSION, "Reply with the word ready, nothing else.", name="w1")
    wait_for(idle("w1"), "the worker's first turn", 300)
    for agent in ("supervisor", "w1"):
        linked(agent, target)

    # Stale: each agent refreshes the shared tokens before its next request.
    data = json.loads(target.read_text())
    month_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
    data["last_refresh"] = month_ago.isoformat().replace("+00:00", "Z")
    inode = target.stat().st_ino
    with target.open("w") as file:  # in place, as Codex writes it
        json.dump(data, file)
    stale = last_refresh(target)
    for agent in ("supervisor", "w1"):
        runtime.send_message(SESSION, "human", agent, "Reply with the word again, nothing else.")
    for agent in ("supervisor", "w1"):
        wait_for(
            lambda a=agent: (
                [m for m in state.list_messages(SESSION) if m.recipient == a][-1].state
                in (state.DELIVERED, state.READ)
            ),
            f"{agent}'s message delivered",
            300,
        )
        wait_for(idle(agent), f"{agent}'s turn after the refresh", 300)
    assert last_refresh(target) != stale  # refreshed through a link
    assert target.stat().st_ino == inode  # written in place
    for agent in ("supervisor", "w1"):
        linked(agent, target)
    assert "Logged in using ChatGPT" in _status(chatgpt_home)
    runtime.stop_session(SESSION)
