"""The test audit's deadline for a test under a mutant (scripts/test_audit.py mutation loads it
with `-p` in mutmut's runs).

mutmut limits a mutant's CPU time, and a test that waits for a timeout of its own (a process,
a poll, a socket) spends none: such a mutant ran for up to half an hour. With a mutant active
(MUTANT_UNDER_TEST names one), a test still running after LADO_AUDIT_TEST_SECONDS ends its
process with exit code 36, mutmut's "timeout", which counts as killed. mutmut's own passes
without a mutant run every test to its end.
"""

import os
import signal

import pytest


def _over(signum, frame):
    os._exit(36)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item, nextitem):
    if "__mutmut_" not in os.environ.get("MUTANT_UNDER_TEST", ""):
        return (yield)
    previous = signal.signal(signal.SIGALRM, _over)
    signal.setitimer(signal.ITIMER_REAL, float(os.environ["LADO_AUDIT_TEST_SECONDS"]))
    try:
        return (yield)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
