"""Each UI test's time limit (LAD-271), given by tests/ui/conftest.py, which imports this
module's hook and fixture: no other layer has a per-test limit.

A test past TEST_TIMEOUT (seconds, its fixtures included) fails and the run goes on. The
limit is in this module, not in the conftest, so that tests/test_ui_time_limit.py runs this
code with a short limit (the conftest brings in the browser tests' fixtures)."""

import faulthandler

import pytest
from _pytest.faulthandler import fault_handler_stderr_fd_key

# A hung test fails instead of hanging its CI cell until the job's own limit cancels it,
# which keeps neither the log nor the junit report; the longest UI test takes ~13 s in CI.
TEST_TIMEOUT = 120
# The stacks of every thread go to the log this many seconds before the limit.
STACKS_BEFORE = 5


def pytest_itemcollected(item):
    """Each test of the conftest that imports this hook gets the time limit. The method
    `thread` ends the test's process: `signal` raises into whatever runs, which in a wait
    of Playwright is its event loop, and the page's teardown then hangs without a limit.
    Under xdist the run names the test as its crashed worker's, and a new worker goes on."""
    item.add_marker(pytest.mark.timeout(TEST_TIMEOUT, method="thread"))


@pytest.fixture(autouse=True)
def stacks_before_the_limit(request):
    """Python's faulthandler writes every thread's stack to the stderr pytest's own
    faulthandler keeps (the log, also from an xdist worker, where the test's own stderr is
    captured) shortly before the limit."""
    file = request.config.stash[fault_handler_stderr_fd_key]
    faulthandler.dump_traceback_later(TEST_TIMEOUT - STACKS_BEFORE, file=file)
    yield
    faulthandler.cancel_dump_traceback_later()
