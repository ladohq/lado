"""The test audit's pytest plugin (scripts/test_audit.py coverage loads it with `-p`).

While a test runs, every process it starts measures its lines with coverage: the plugin puts
the audit's `sitecustomize.py` (folder LADO_AUDIT_SITE) first on PYTHONPATH and its config
(LADO_AUDIT_RC) in COVERAGE_PROCESS_START. The config's static context is `LADO_TEST_ID`,
which tests/conftest.py sets to the test's node id for the same time, so a hook, `lado mcp`
or the UI server records its lines under the test that started it. pytest's own process is
measured by pytest-cov (`--cov-context=test`); outside a test nothing is set.
"""

import os

import pytest

NAMES = ("COVERAGE_PROCESS_START", "PYTHONPATH")


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item, nextitem):
    saved = {name: os.environ.get(name) for name in NAMES}
    os.environ["COVERAGE_PROCESS_START"] = os.environ["LADO_AUDIT_RC"]
    path = [os.environ["LADO_AUDIT_SITE"], saved["PYTHONPATH"]]
    os.environ["PYTHONPATH"] = os.pathsep.join(p for p in path if p)
    try:
        return (yield)
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
