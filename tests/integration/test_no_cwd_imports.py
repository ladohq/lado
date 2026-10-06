"""LADO's own processes never import from the agent's repository (interpreter.run_module)."""

import agent_helpers
import pytest

from lado import loop, runtime, state

pytestmark = pytest.mark.integration

SESSION = "shadow"


def test_a_json_py_in_the_repo_runs_in_none_of_lados_processes(repo, tmp_path, monkeypatch):
    marker = tmp_path / "SHADOWED"
    (repo / "json.py").write_text(
        f"open({str(marker)!r}, 'a').write('json')\nraise SystemExit(7)\n"
    )
    monkeypatch.chdir(repo)  # the session loop starts in the caller's cwd: here the repo's
    runtime.start_session(str(repo), SESSION, None, "fake")
    # The supervisor's window command (lado.agent_env) imports json at its start.
    agent_helpers.wait_for(
        lambda: state.get_agent(SESSION, "supervisor").status == state.IDLE,
        "supervisor to be idle",
        SESSION,
    )
    agent_helpers.wait_for(lambda: loop.running(SESSION), "the session loop", SESSION)
    assert not marker.exists()
