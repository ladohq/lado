"""The server's check of the agent CLIs (lado.server.provider_check): one background check
at a time, every CLI at once and the login shell once, each row kept as soon as its CLI
is read. The CLIs' reads are replaced by functions that wait for the test."""

import threading
import time

import pytest

from lado import doctor, providers
from lado.server import launch, provider_check

INSTALLED = doctor.ProviderStatus(True, "1.0.0", "1.0.0", "", "")


@pytest.fixture
def reads(monkeypatch):
    """Each provider's read waits until the test releases it (`release(name)`, `release()`
    for all); `raises[name]` makes it fail; `shells` counts the login shell's runs."""
    gates = {name: threading.Event() for name in providers.names()}
    raises: dict[str, Exception] = {}
    shells = []

    def read(provider, status, layers, problem):
        assert gates[provider.name].wait(10), f"{provider.name} never released"
        if provider.name in raises:
            raise raises[provider.name]
        return f"read {provider.name}"

    def environment():
        shells.append(1)
        return launch.NO_LAYERS, ""

    monkeypatch.setattr(doctor, "provider_status", lambda provider, which: INSTALLED)
    monkeypatch.setattr(launch, "read", read)
    monkeypatch.setattr(launch, "environment", environment)
    monkeypatch.setattr(
        launch,
        "provider_logins",
        lambda found, cli: provider_check._row(cli, providers.get(cli.name), found, ready=True),
    )

    class Reads:
        def release(self, *names):
            for name in names or gates:
                gates[name].set()

        def hold(self):
            for gate in gates.values():
                gate.clear()

    found = Reads()
    found.raises, found.shells = raises, shells
    provider_check.reset()
    yield found
    found.release()
    provider_check.reset()


def _until(check, what: str):
    deadline = time.monotonic() + 10
    while not check():
        assert time.monotonic() < deadline, f"timed out waiting for {what}"
        time.sleep(0.01)


def _rows():
    return {row.cli.name: row for row in provider_check.snapshot().providers}


def _done():
    return not provider_check.snapshot().checking


def test_the_first_snapshot_has_every_provider_not_ready_and_checking(reads):
    assert provider_check.start()
    page = provider_check.snapshot()
    assert page.checking and page.environment == ""
    assert [r.cli.name for r in page.providers] == providers.names()
    assert [r.ready for r in page.providers] == [False] * len(providers.names())
    claude = _rows()["claude"]
    assert (claude.cli.title, claude.cli.installed) == ("Claude Code", False)


def test_a_row_is_kept_as_soon_as_its_cli_is_read(reads):
    provider_check.start()
    reads.release("codex")
    _until(lambda: _rows()["codex"].ready, "codex's row")
    rows = _rows()
    assert rows["codex"].login.problem == "read codex"
    assert not rows["claude"].ready and provider_check.snapshot().checking
    reads.release()
    _until(_done, "the check's end")
    assert all(row.ready for row in _rows().values())


def test_the_login_shell_runs_once_per_check(reads):
    reads.release()
    provider_check.start()
    _until(_done, "the check's end")
    assert len(reads.shells) == 1


def test_start_twice_runs_one_check_at_a_time_and_one_more_after_it(reads):
    """What changed while a check ran (a login window's end) is read by the next one: a
    check asked for meanwhile runs once after it, however often it was asked."""
    assert provider_check.start()
    assert not provider_check.start()
    assert not provider_check.start()
    _until(lambda: len(reads.shells) == 1, "the first check's shell")
    reads.release()
    _until(_done, "the checks' end")
    assert len(reads.shells) == 2
    assert provider_check.start()  # the next one, once they ended
    _until(_done, "the last check's end")
    assert len(reads.shells) == 3


def test_a_row_put_during_a_check_is_not_replaced_by_its_older_read(reads):
    """A saved token's row, read after the running check read that CLI, stays."""
    provider_check.start()
    _until(lambda: len(reads.shells) == 1, "the check's start")
    saved = provider_check._row(
        provider_check._bare_info(providers.get("claude"), True),
        providers.get("claude"),
        "saved",
        ready=True,
    )
    provider_check.put(saved)
    reads.release()
    _until(_done, "the check's end")
    assert _rows()["claude"].login.problem == "saved"
    assert _rows()["codex"].login.problem == "read codex"


def test_a_failing_provider_does_not_stop_the_check(reads, monkeypatch):
    recorded = []
    monkeypatch.setattr(
        provider_check.telemetry, "record", lambda where, exc, **k: recorded.append(k)
    )
    reads.raises["kilo"] = RuntimeError("kilo broke")
    reads.release()
    provider_check.start()
    _until(_done, "the check's end")
    rows = _rows()
    assert rows["kilo"].ready and rows["kilo"].login.state == "unknown"
    assert rows["kilo"].login.problem == "RuntimeError: kilo broke"
    assert rows["kilo"].cli.installed  # its version was read
    assert rows["claude"].login.problem == "read claude"
    assert recorded == [{"provider": "kilo"}]


def test_the_last_rows_stay_while_a_new_check_runs(reads):
    reads.release()
    provider_check.start()
    _until(_done, "the first check's end")
    reads.hold()
    reads.raises["claude"] = RuntimeError("read anew")
    provider_check.start()
    page = provider_check.snapshot()
    assert page.checking
    assert all(row.ready for row in page.providers)
    assert _rows()["claude"].login.problem == "read claude"  # the last check's
    reads.release()
    _until(_done, "the second check's end")
    assert _rows()["claude"].login.problem == "RuntimeError: read anew"


def test_the_agents_environment_problem_is_kept(reads, monkeypatch):
    monkeypatch.setattr(launch, "environment", lambda: (launch.NO_LAYERS, "the shell timed out"))
    reads.release()
    provider_check.start()
    _until(_done, "the check's end")
    assert provider_check.snapshot().environment == "the shell timed out"


def test_a_put_row_replaces_the_one_kept(reads):
    reads.release()
    provider_check.start()
    _until(_done, "the check's end")
    row = _rows()["claude"].model_copy(update={"window": True})
    provider_check.put(row)
    assert _rows()["claude"].window
