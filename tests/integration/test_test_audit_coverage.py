"""scripts/test_audit.py coverage: the lines a test runs, in the processes it starts too, are
recorded under that test's node id only (openspec capability test-audit)."""

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts" / "test_audit.py"

spec = importlib.util.spec_from_file_location("test_audit", SCRIPT)
test_audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(test_audit)

# A session whose fake agent's hooks run `lado hook`, and the fake agent alone, whose hooks
# only echo but whose `lado mcp` is LADO's.
HOOKED = "tests/integration/test_agents.py::test_message_to_idle_agent_is_pasted_and_confirmed"
PLAIN = "tests/integration/test_fake_agent.py::test_the_agent_ends_its_process_on_exit"


def body_lines(path: Path, name: str) -> set[int]:
    """The lines of the module-level function `name` of `path`, its signature's after the
    first."""
    tree = ast.parse(path.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return set(range(node.body[0].lineno, node.end_lineno + 1))


def test_a_hook_s_lines_belong_to_its_test(tmp_path):
    out = tmp_path / "audit"
    command = [sys.executable, str(SCRIPT), "coverage", "--layer", "integration"]
    result = subprocess.run(
        [*command, "--out", str(out), "--", HOOKED, PLAIN, "-n0"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    records = test_audit.load_coverage(out / "coverage-integration.json")
    handle = body_lines(ROOT / "src" / "lado" / "hooks.py", "handle")
    assert records[HOOKED]["src/lado/hooks.py"] & handle  # run by the agent's hook process
    assert not records[PLAIN].get("src/lado/hooks.py", set()) & handle
    serve = body_lines(ROOT / "src" / "lado" / "mcp_server.py", "main")
    assert records[PLAIN]["src/lado/mcp_server.py"] & serve  # the fake agent's `lado mcp`
