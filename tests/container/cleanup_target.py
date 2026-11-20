"""The run test_cleanup.py starts and stops from outside: not a test file pytest collects by
itself (no `test_` in its name), so a normal run neither runs nor skips it; a path given on
the command line is collected."""

import os
import time
from pathlib import Path

import pytest
from container_helpers import PREFIX

pytestmark = pytest.mark.container


def test_waits_with_a_container_a_compose_project_and_a_tag(start, compose, folder):
    """A container of `start` with its home volume, a compose project's container, volume
    and network, a tag of `folder`; then the run's prefix in LADO_CLEANUP_READY, and a wait
    for the signal."""
    start(0)
    compose.run("up", "-d")
    folder("tagged")
    Path(os.environ["LADO_CLEANUP_READY"]).write_text(PREFIX)
    time.sleep(600)
