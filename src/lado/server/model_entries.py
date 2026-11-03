"""What Settings → Models' routes do (openspec capability model-settings-page): the human's
configured models and model servers through lado.model_settings, with its rules and its
lines; each refusal a Refusal holding the line, its hint and the field of the form it
concerns, which lado.server.app answers as a 400.

Nothing here asks a server but a probe the human asked for: opening a server's source, its
check, a save. The probe of `probe_server` and of a model's live check is kept KEPT seconds
by server (id and address) for the next live check (`check_model`, at each settled
keystroke); a save, a tick and `probe_server` probe now. A server's key comes in only in
`ModelServerAdd` and leaves in no answer: the refusals are the core's lines, which never
hold it.
"""

from __future__ import annotations

import threading
import time

from lado import model_check, model_servers, model_settings, providers, runtime, state
from lado.server import models

KEPT = 60  # seconds a probe is kept for the live check of a model
_probes: dict[tuple[str, str], tuple[float, model_servers.Probe]] = {}
_probes_lock = threading.Lock()


class Refusal(Exception):
    """A refusal of the core, as the 400's detail."""

    def __init__(self, detail: models.EntryRefused):
        super().__init__(detail.message)
        self.detail = detail


def _refusal(exc: Exception, warnings: list[str] | None = None) -> Refusal:
    """A Refused, a ProbeError, an address the probe does not take (ValueError) or an
    environment that cannot be read (LadoError) as a Refusal."""
    field = getattr(exc, "field", model_servers.ADDRESS if isinstance(exc, ValueError) else "")
    return Refusal(
        models.EntryRefused(
            message=str(exc),
            hint=getattr(exc, "hint", ""),
            field=field,
            warnings=warnings or [],
        )
    )


REFUSED = (model_settings.Refused, model_servers.ProbeError, runtime.LadoError)


def forget_probes() -> None:
    with _probes_lock:
        _probes.clear()


def _keep(server: state.ModelServer, found: model_servers.Probe) -> None:
    with _probes_lock:
        _probes[(server.id, server.address)] = (time.monotonic(), found)


def _kept_or_probed(server: state.ModelServer) -> model_servers.Probe:
    """The probe of `server` kept less than KEPT seconds ago, else one made now and kept."""
    with _probes_lock:
        kept = _probes.get((server.id, server.address))
    if kept and time.monotonic() - kept[0] < KEPT:
        return kept[1]
    found = model_settings.probe_saved(server)
    _keep(server, found)
    return found


def _agents_env(provider: providers.Provider) -> dict[str, str]:
    """The environment of the agents of no project, where a CLI's list is read."""
    return runtime.agents_env(runtime.agent_layers(None), provider)


def _cli_title(cli: str) -> str:
    return providers.get(cli).title if cli in providers.names() else cli


def _server_clis(apis) -> list[str]:
    """The providers' names whose API is among `apis`, in model_servers.clis' order."""
    return [name for name, _, _ in _clis(apis)[0]]


def _clis(apis) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """model_servers.clis with each provider's name: (name, title, API)."""
    by_title = {providers.get(name).title: name for name in providers.names()}
    suits, not_suits = model_servers.clis(apis)
    return (
        [(by_title[title], title, api) for title, api in suits],
        [(by_title[title], title, api) for title, api in not_suits],
    )


def server_info(server: state.ModelServer) -> models.ModelServerInfo:
    return models.ModelServerInfo(
        name=server.name,
        address=server.address,
        kind=server.kind,
        clis=_server_clis(server.apis),
        has_key=model_settings.has_key(server),
    )


def probe_info(found: model_servers.Probe) -> models.ProbeInfo:
    suits, not_suits = _clis(found.apis)
    return models.ProbeInfo(
        address=found.address,
        added_scheme=found.added_scheme,
        kind=found.kind,
        models=None if found.models is None else list(found.models),
        models_why=found.models_why,
        embeddings=sorted(found.embeddings),
        apis_why=found.apis_why,
        clis=[models.CliApi(name=n, title=t, api=a) for n, t, a in suits],
        not_clis=[models.CliApi(name=n, title=t, api=a) for n, t, a in not_suits],
    )


def _model_info(
    model: state.ConfiguredModel, servers: dict[str, str]
) -> models.ConfiguredModelInfo:
    return models.ConfiguredModelInfo(
        name=model.name,
        cli=model.cli,
        cli_title=_cli_title(model.cli),
        model=model.model,
        server=servers.get(model.server, model.server) if model.server else None,
    )


def listing(has_db: bool = True) -> models.ModelSettings:
    """The configured models and the saved servers, asking none; empty with no lado.db."""
    if not has_db:
        return models.ModelSettings(models=[], servers=[])
    servers = state.model_servers()
    names = {server.id: server.name for server in servers}
    return models.ModelSettings(
        models=[_model_info(model, names) for model in state.models()],
        servers=[server_info(server) for server in servers],
    )


def add_server(given: models.ModelServerAdd) -> models.ModelServerAdded:
    """Save the server as `lado model-server add` does, or replace it as `--replace` does
    (`given.key` None: the kept key)."""
    warnings: list[str] = []
    notes: list[str] = []
    try:
        found = model_settings.add_server(
            given.name,
            given.address,
            given.key,
            replace=given.replace,
            warn=warnings.append,
            note=notes.append,
        )
    except (*REFUSED, ValueError) as exc:
        raise _refusal(exc, warnings) from None
    server = _saved_server(given.name)  # removed meanwhile: refused
    _keep(server, found)
    return models.ModelServerAdded(
        server=server_info(server),
        probe=probe_info(found),
        notes=notes,
        warnings=warnings,
        replaced=given.replace,
    )


def _saved_server(name: str) -> state.ModelServer:
    server = state.model_server(name)
    if server is None:
        raise _refusal(model_settings.no_server(name))
    return server


def probe_server(name: str) -> models.ProbeInfo:
    """The saved server `name` probed now with its kept key, and kept."""
    server = _saved_server(name)
    try:
        found = model_settings.probe_saved(server)
    except REFUSED as exc:
        raise _refusal(exc) from None
    _keep(server, found)
    return probe_info(found)


def remove_server(name: str, with_models: bool) -> models.ModelSettings:
    try:
        model_settings.remove_server(name, with_models=with_models)
    except REFUSED as exc:
        raise _refusal(exc) from None
    return listing()


def check_model(given: models.ModelAdd) -> models.ModelCheck:
    """The check `lado model add` would make, saving nothing, a server's probe kept; a
    refusal is a ModelCheck of kind refused with its field."""
    try:
        checked = model_settings.check_model(
            given.name, given.cli, given.model, given.server, _agents_env, probe=_kept_or_probed
        )
    except REFUSED as exc:
        return models.ModelCheck(
            kind=model_check.REFUSED, text=str(exc), field=getattr(exc, "field", "")
        )
    return models.ModelCheck(kind=checked.verdict.kind, text=checked.verdict.text)


def add_model(given: models.ModelAdd) -> models.ModelAdded:
    """Save the model as `lado model add` does, its server probed now; named by default
    when `given.name` is None."""
    try:
        saved, verdict = model_settings.add_model(
            given.name, given.cli, given.model, given.server, _agents_env
        )
    except REFUSED as exc:
        raise _refusal(exc) from None
    names = {server.id: server.name for server in state.model_servers()}
    return models.ModelAdded(
        model=_model_info(saved, names),
        check=models.ModelCheck(kind=verdict.kind, text=verdict.text),
    )


def rename_model(name: str, given: models.ModelRename) -> models.ModelSettings:
    try:
        model_settings.rename_model(name, given.name)
    except REFUSED as exc:
        raise _refusal(exc) from None
    return listing()


def remove_model(name: str) -> models.ModelSettings:
    try:
        model_settings.remove_models([name], lambda _: None)
    except REFUSED as exc:
        raise _refusal(exc) from None
    return listing()
