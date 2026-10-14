"""`--shard K/N` (tests/shard.py): CI's integration and UI shards (ci.yml)."""

import pytest

pytest_plugins = "pytester"

TESTS = 40


@pytest.fixture
def suite(pytester):
    pytester.makeconftest(
        "from shard import pytest_addoption, pytest_collection_modifyitems, pytest_configure"
    )
    pytester.makepyfile(
        test_many="\n".join(f"def test_{i}():\n    pass\n" for i in range(TESTS)),
        test_more="import pytest\n\n@pytest.mark.parametrize('n', range(7))\n"
        "def test_param(n):\n    pass\n",
    )
    return pytester


def collected(suite, *args) -> set[str]:
    """The node ids a run would run (collected, not run: pytest-playwright's soft
    assertions refuse a test run inside a test)."""
    recorder = suite.inline_run("--collect-only", *args)
    (finish,) = recorder.getcalls("pytest_collection_finish")
    return {item.nodeid for item in finish.session.items}


def test_the_shards_hold_every_test_once_and_always_the_same(suite):
    runs = [collected(suite, f"--shard={k}/3") for k in (1, 2, 3)]
    everything = collected(suite)
    assert len(everything) == TESTS + 7
    assert all(runs)
    assert sum(len(r) for r in runs) == len(everything)
    assert set().union(*runs) == everything
    assert collected(suite, "--shard=2/3") == runs[1]


def test_a_tests_shard_is_the_same_in_every_process(suite):
    """By CRC-32, not Python's hash(), which changes with each process (PYTHONHASHSEED)."""
    assert "test_many.py::test_0" in collected(suite, "--shard=1/3")
    assert "test_many.py::test_2" in collected(suite, "--shard=3/3")


def test_the_rest_is_deselected(suite):
    result = suite.runpytest("--collect-only", "--shard=1/3")
    deselected = TESTS + 7 - len(collected(suite, "--shard=1/3"))
    result.stdout.fnmatch_lines([f"*{deselected} deselected*"])


def test_one_shard_is_everything(suite):
    assert len(collected(suite, "--shard=1/1")) == TESTS + 7


@pytest.mark.parametrize("value", ["0/3", "4/3", "1/0", "x", "1/", "-1/3", "1/3/2"])
def test_a_bad_shard_is_a_usage_error(suite, value):
    result = suite.runpytest(f"--shard={value}")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines([f"*--shard {value}: K/N with 1 <= K <= N*"])
