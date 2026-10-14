"""`pytest --shard K/N`: run only the K-th of N shards of the collected tests.

CI splits the integration and UI tests into jobs this way (.github/workflows/ci.yml). A
test is in shard K when the CRC-32 of its node id, modulo N, is K - 1: every test is in
exactly one shard, always the same one, and a new test needs no list. The rest is
deselected, as `-m` deselects. Without the option every test runs. tests/conftest.py
imports these hooks.
"""

import re
import zlib

import pytest

SHARD = re.compile(r"(\d+)/(\d+)")


def parse(value: str) -> tuple[int, int]:
    match = SHARD.fullmatch(value)
    if match:
        k, n = int(match[1]), int(match[2])
        if 1 <= k <= n:
            return k, n
    raise pytest.UsageError(f"--shard {value}: K/N with 1 <= K <= N, e.g. --shard 2/3")


def pytest_addoption(parser):
    parser.addoption(
        "--shard",
        metavar="K/N",
        help="run only shard K of N, split by a stable hash of each test's node id",
    )


def pytest_configure(config):
    value = config.getoption("shard")
    if value is not None:
        parse(value)


def pytest_collection_modifyitems(config, items):
    value = config.getoption("shard")
    if value is None:
        return
    k, n = parse(value)
    kept, deselected = [], []
    for item in items:
        (kept if zlib.crc32(item.nodeid.encode()) % n == k - 1 else deselected).append(item)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = kept
