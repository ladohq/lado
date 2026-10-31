"""Settings → Providers and environment's data (docs/design/ui.md): the last row of each
agent CLI (lado.server.launch.provider_logins), kept for the server's lifetime and
refreshed by one background check at a time, every CLI at once and the login shell once;
a row is kept as soon as its CLI is read, so the section answers at once and its rows
change in place. Nothing is written to disk: a stale login after a restart would be worse
than a short first wait.

`start` begins a check unless one runs, else asks for one more after it (a login window
ended meanwhile); `snapshot` is what the section shows now; `put` keeps a row read after an
action on it (a saved token, a logout), which an older read of the check that runs does
not replace."""

import shutil
import threading
from concurrent.futures import Future, ThreadPoolExecutor

from lado import agent_env, doctor, providers, telemetry
from lado.server import launch, models

_lock = threading.Lock()
_rows: dict[str, models.ProviderLogins] = {}
_puts: dict[str, int] = {}  # per provider, the rows `put` kept: a check's older read loses
_environment = ""  # why the agents' environment could not be read, at the last check
_thread: threading.Thread | None = None  # the check that runs, if one does
_again = False  # a check was asked for while one ran: one more runs after it


def start() -> bool:
    """Begin a check in the background; False when one runs already: it goes on, and one
    more runs after it, so what changed meanwhile (a login window's end) is read too."""
    global _thread, _again
    with _lock:
        if _thread is not None:
            _again = True
            return False
        _thread = threading.Thread(target=_check, name="provider-check", daemon=True)
        _thread.start()
    return True


def snapshot() -> models.ProvidersPage:
    """Each provider's last row, in the registry's order; a provider never read yet gets a
    row with `ready` false, its name and title only."""
    with _lock:
        rows = dict(_rows)
        checking, environment = _thread is not None, _environment
    return models.ProvidersPage(
        providers=[rows.get(name) or _not_ready(providers.get(name)) for name in providers.names()],
        checking=checking,
        environment=environment,
    )


def put(row: models.ProviderLogins) -> None:
    """Keep a row read after an action on its provider (lado.server.app)."""
    with _lock:
        _rows[row.cli.name] = row
        _puts[row.cli.name] = _puts.get(row.cli.name, 0) + 1


def reset() -> None:
    """Forget every row, once the check that runs has ended (tests)."""
    global _environment, _again
    if (running := _thread) is not None:
        running.join()
    with _lock:
        _rows.clear()
        _puts.clear()
        _environment, _again = "", False


def _check() -> None:
    global _thread, _again
    while True:
        try:
            _pass()
        except Exception as error:  # the check ends, and says so, whatever happens
            telemetry.record("server:provider-check", error)
        with _lock:
            if not _again:
                _thread = None
                return
            _again = False


def _pass() -> None:
    """One read of every provider, at once, and of the agents' environment, once."""
    global _environment
    registry = [providers.get(name) for name in providers.names()]
    with _lock:
        puts = dict(_puts)
    with ThreadPoolExecutor(len(registry) + 1) as pool:
        env = pool.submit(launch.environment)
        list(pool.map(lambda p: _one(p, env, puts.get(p.name, 0)), registry))
    problem = env.result()[1]
    with _lock:
        _environment = problem


def _one(
    provider: providers.Provider, env: Future[tuple[agent_env.Layers, str]], puts: int
) -> None:
    """Read one provider and keep its row, unless an action put a newer one meanwhile
    (`puts`, how many there were before the read); a provider whose read fails gets a row
    that says why, and the others go on."""
    status = None
    try:
        status = doctor.provider_status(provider, shutil.which)
        layers, problem = env.result()
        row = launch.provider_logins(
            launch.read(provider, status, layers, problem), launch.provider_info(provider, status)
        )
    except Exception as error:
        telemetry.record("server:provider-check", error, provider=provider.name)
        row = _failed(provider, status, f"{type(error).__name__}: {error}")
    with _lock:
        if _puts.get(provider.name, 0) == puts:
            _rows[provider.name] = row


def _bare_info(provider: providers.Provider, installed: bool) -> models.ProviderInfo:
    return models.ProviderInfo(
        name=provider.name,
        title=provider.title,
        permission_modes=list(provider.permission_modes),
        install_hint=provider.install_hint,
        installed=installed,
        version="",
        detail="",
        tested_version="",
        warning="",
    )


def _row(cli: models.ProviderInfo, provider: providers.Provider, problem: str, ready: bool):
    return models.ProviderLogins(
        cli=cli,
        login=models.LoginInfo(state="unknown", method="", where="", choice="", problem=problem),
        needs_login=provider.capabilities.needs_login,
        actions=[],
        question="",
        choices=[],
        from_lado=False,
        note="",
        waiting=[],
        running=[],
        projects=[],
        window=False,
        ready=ready,
    )


def _not_ready(provider: providers.Provider) -> models.ProviderLogins:
    return _row(_bare_info(provider, installed=False), provider, "", ready=False)


def _failed(
    provider: providers.Provider, status: doctor.ProviderStatus | None, problem: str
) -> models.ProviderLogins:
    """The row of a provider whose read raised: its sign-in unknown with why."""
    cli = launch.provider_info(provider, status) if status else _bare_info(provider, True)
    return _row(cli, provider, problem, ready=True)
