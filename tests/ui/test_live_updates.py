"""Live updates in a browser: the pages follow the change feed (GET /api/events) without a
reload, whatever process writes the change."""

import os
import subprocess
import sys

import pytest

pytestmark = pytest.mark.ui


def lado_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "lado.cli", *args],
        capture_output=True,
        text=True,
        env=os.environ,
        check=False,
        timeout=30,
    )
