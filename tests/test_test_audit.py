"""scripts/test_audit.py: the test audit's logic (openspec capability test-audit); its runs of
pytest across processes are tests/integration/test_test_audit_*.py."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "test_audit.py"

spec = importlib.util.spec_from_file_location("test_audit", SCRIPT)
test_audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(test_audit)


def test_load_coverage_gives_each_test_s_lines_per_file_as_sets(tmp_path):
    path = tmp_path / "coverage-unit.json"
    path.write_text(json.dumps({"t.py::a": {"src/lado/runs.py": [3, 1, 2]}, "t.py::b": {}}))
    assert test_audit.load_coverage(path) == {
        "t.py::a": {"src/lado/runs.py": {1, 2, 3}},
        "t.py::b": {},
    }
