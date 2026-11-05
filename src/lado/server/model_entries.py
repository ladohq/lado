"""What Settings → Models' routes do (openspec capability model-settings-page): the human's
configured models, model servers and agent CLIs' default models through lado.model_settings,
with its rules and its lines; each refusal a Refusal holding the line, its hint and the
field of the form it concerns, which lado.server.app answers as a 400.

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
from lado.providers import base
from lado.server import launch, models

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
            message=getattr(exc, "page", str(exc)),  # the page's line: no command in it
            hint=getattr(exc, "page_hint", getattr(exc, "hint", "")),
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


def server_info(server: state.ModelServer) -> models.ModelServerInfo:
    return models.ModelServerInfo(
        name=server.name,
        address=server.address,
        kind=server.kind,
        has_key=model_settings.has_key(server),
    )


def probe_info(found: model_servers.Probe) -> models.ProbeInfo:
    suits, _ = model_servers.suiting(found.apis)
    return models.ProbeInfo(
        kind=found.kind,
        address=found.address,
        models=None if found.models is None else list(found.models),
        models_why=found.models_why,
        embeddings=sorted(found.embeddings),
        apis_why=found.apis_why,
        clis=[models.CliApi(name=p.name, title=p.title, api=api) for p, api in suits],
    )


def _model_info(
    model: state.ConfiguredModel, servers: dict[str, str]
) -> models.ConfiguredModelInfo:
    return models.ConfiguredModelInfo(
        id=model.id,
        name=model.name,
        cli=model.cli,
        cli_title=model_settings.cli_title(model.cli),
        model=model.model,
        server=servers.get(model.server, model.server),
    )


def _default_info(default: model_settings.CliDefault) -> models.CliDefault:
    return models.CliDefault(
        cli=default.ref.cli,
        external=default.ref.model_id,
        builtin=default.ref.builtin,
        name=default.name,
        model=default.model,
        server=default.server,
        whole_process=(
            default.ref.cli in providers.names()
            and providers.get(default.ref.cli).external_whole_process
        ),
    )


def listing(has_db: bool = True) -> models.ModelSettings:
    """The configured models, the saved servers and the agent CLIs' default models, asking
    none; empty with no lado.db."""
    if not has_db:
        return models.ModelSettings(models=[], servers=[], defaults=[])
    servers = state.model_servers()
    names = {server.id: server.name for server in servers}
    return models.ModelSettings(
        models=[_model_info(model, names) for model in state.models()],
        servers=[server_info(server) for server in servers],
        defaults=[_default_info(default) for default in model_settings.defaults()],
    )


def _listed(provider: providers.Provider, fresh: bool = False) -> base.ModelList:
    """The launch window's list of `provider`'s CLI, kept a minute (`fresh`: read now); an
    environment that cannot be read is no list, with why."""
    try:
        return launch.model_list(provider, fresh=fresh)
    except runtime.LadoError as exc:
        return base.ModelList(why=str(exc))


def model_choices(
    provider: providers.Provider, model: str = "", fresh: bool = False, has_db: bool = True
) -> models.ModelChoices:
    """What `provider`'s CLI can run, as the core computes it, and the check of the built-in
    model `model` against that list; no lado.db made."""
    listed = _listed(provider, fresh)
    found = model_settings.choices(provider, lambda _: listed, None if has_db else [])
    names = {server.id: server.name for server in state.model_servers()} if has_db else {}
    verdict = model_check.verdict(provider, model, listed)
    return models.ModelChoices(
        check=models.ModelCheck(kind=verdict.kind, text=verdict.page or verdict.text),
        aliases=list(found.aliases),
        models=None if found.models is None else list(found.models),
        why=found.why,
        external=[_model_info(model, names) for model in found.external],
        other_name=found.other_name,
        whole_process=provider.external_whole_process,
        read_again=found.read_again,
    )


def _window_warnings(start: model_settings.StartModel, provider: providers.Provider) -> list[str]:
    """The launch window's warnings of the chosen model and its server's key, the only ones it
    shows; a start warns of every server of the agent's config."""
    server = start.server
    if server is None:
        return []
    key = model_settings.server_key(server)
    warnings = []
    if model_servers.plain_http_warning(server.address, key):
        warnings.append(
            f"The key of {server.name} goes unencrypted (http) to an address outside your machine "
            "and network."
        )
    limit = model_servers.context_limits(server.address, key).get(start.model or "")
    if warning := model_settings.context_warning(start, provider, limit):
        warnings.append(warning)
    return warnings


def check_session_model(given: models.SessionModelAsked) -> models.SessionModelCheck:
    """The check a start would make of a model given for a session, saving nothing, in the
    environment of the agents of the project asked for; a refusal is a SessionModelCheck of
    kind refused."""
    start = None
    try:
        provider = model_settings.known_cli(given.cli)
        env = runtime.agents_env(runtime.agent_layers(given.project), provider)

        def listing(asked: providers.Provider) -> base.ModelList:
            return launch.model_list(asked, given.project)

        row = model_settings.session_row(given.model, provider, env, listing)
        start = model_settings.start_model(state.PowerTable.of(row), provider)
        verdict = model_settings.check_start(start, provider, env, listing=listing)
        warnings = _window_warnings(start, provider)
    except REFUSED as exc:
        return models.SessionModelCheck(
            kind=model_check.REFUSED,
            text=getattr(exc, "window", str(exc)),
            field=getattr(exc, "field", ""),
            retry=getattr(exc, "retry", False),
            short=getattr(exc, "short", str(exc)),
            peek=getattr(exc, "peek", model_settings.REFUSED_PEEK),
            server=start.server.name if start and start.server else None,
        )
    server = start.server
    text = verdict.text
    if server is not None and verdict.kind == model_check.OK:
        text = f"{server.name} lists {start.model} among its models."
    return models.SessionModelCheck(
        kind=verdict.kind,
        text=text,
        warnings=warnings,
        server=server.name if server else None,
    )


def set_default(cli: str, given: models.ModelDefaultSet) -> models.ModelDefaultSaved:
    """Set the default model as `lado model default` does: a row picked by reference, so it is
    never taken for another of the same name, a typed name read as the command reads it. The
    list is the one the picker just read, kept a minute."""
    try:
        if given.typed is not None:
            _, verdict = model_settings.set_default(cli, given.typed, _agents_env, _listed)
        else:
            ref = state.ModelRef(cli, given.external, given.builtin)
            _, verdict = model_settings.set_default_ref(ref, _agents_env, _listed)
    except REFUSED as exc:
        raise _refusal(exc) from None
    check = None if verdict is None else models.ModelCheck(kind=verdict.kind, text=verdict.text)
    return models.ModelDefaultSaved(settings=listing(), check=check)


def check_default(cli: str, given: models.ModelDefaultCheck) -> models.ModelCheck:
    """The check `lado model default` would make of a typed name, saving nothing; a refusal is
    a ModelCheck of kind refused with its field."""
    try:
        ref, verdict = model_settings.check_default(cli, given.name, _agents_env, _listed)
    except REFUSED as exc:
        return models.ModelCheck(
            kind=model_check.REFUSED,
            text=getattr(exc, "page", str(exc)),
            field=getattr(exc, "field", ""),
        )
    if verdict is not None:
        return models.ModelCheck(kind=verdict.kind, text=verdict.text)
    saved = state.model_by_id(ref.model_id or "")
    servers = {server.id: server.name for server in state.model_servers()}
    text = f"your model {saved.name}: {saved.model} on {servers.get(saved.server)}" if saved else ""
    return models.ModelCheck(kind=model_check.OK, text=text)


def clear_default(cli: str) -> models.ModelSettings:
    try:
        model_settings.clear_default(cli)
    except REFUSED as exc:
        raise _refusal(exc) from None
    return listing()


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
    )


def check_server(given: models.ModelServerCheck, has_db: bool = True) -> models.ServerCheck:
    """What the server form says before Add, as the human types, saving nothing: the
    refusals `add_server` would meet for the name and the address, the plain-http warning
    while a key is typed, and the probe of the address (the command's, 5 s a request),
    with `given.key` only when the human pressed Check key; then the notes of each saved
    server at the address it found. With `given.replace` (Change) the name must be a saved
    server's, which is no other server at its address, and with no new key typed the probe
    sends its kept key, as Save does (never in the answer). An empty name or address is not
    checked yet."""
    refusals: list[models.EntryRefused] = []
    warnings: list[str] = []
    notes: list[str] = []
    saved: state.ModelServer | None = None

    def refuse(exc: Exception) -> None:
        refusals.append(_refusal(exc).detail)

    if given.name:
        try:
            if has_db:
                saved = model_settings.server_to_add(given.name, given.replace)
            else:
                model_settings.check_name(given.name, model_settings.SERVER)
        except model_settings.Refused as exc:
            refuse(exc)
    key = given.key
    if key is None and saved is not None and not given.key_typed:
        try:
            key = model_settings.server_key(saved)
        except model_settings.Refused as exc:
            refuse(exc)
            return models.ServerCheck(probe=None, refusals=refusals, warnings=[], notes=[])
    if given.key is not None:
        try:
            model_settings.check_key(given.key)
        except model_settings.Refused as exc:
            refuse(exc)
            return models.ServerCheck(probe=None, refusals=refusals, warnings=[], notes=[])
    if not given.address.strip():
        return models.ServerCheck(probe=None, refusals=refusals, warnings=[], notes=[])
    try:
        root, _ = model_servers.address(given.address)
    except ValueError as exc:
        refuse(exc)
        return models.ServerCheck(probe=None, refusals=refusals, warnings=[], notes=[])
    sent = key if key is not None else ("" if given.key_typed else None)
    warning = model_servers.plain_http_warning(root, sent)
    if warning:
        warnings.append(warning)
    try:
        found = model_servers.probe(
            given.address, key, model_settings.add_command(given.name, given.replace)
        )
    except (model_servers.ProbeError, ValueError) as exc:
        refuse(exc)
        return models.ServerCheck(probe=None, refusals=refusals, warnings=warnings, notes=[])
    for other in state.model_servers() if has_db else []:
        if given.replace and other.name.lower() == given.name.lower():
            continue
        if model_settings.same_address(other.address, found.address):
            notes.append(f'same address as model server "{other.name}"')
    return models.ServerCheck(
        probe=probe_info(found), refusals=refusals, warnings=warnings, notes=notes
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


def remove_server(name: str, with_models: bool, confirmed: list[str]) -> models.ModelSettings:
    """Remove the server, with its models only when they are `confirmed`."""
    try:
        model_settings.remove_server(
            name, with_models=with_models, confirmed=confirmed if with_models else None
        )
    except REFUSED as exc:
        raise _refusal(exc) from None
    return listing()


def check_model(given: models.ModelAdd) -> models.ModelCheck:
    """The check `lado model add` would make, saving nothing, a server's probe kept; a
    refusal is a ModelCheck of kind refused with its field."""
    try:
        checked = model_settings.check_model(
            given.name, given.cli, given.model, given.server, probe=_kept_or_probed
        )
    except REFUSED as exc:
        return models.ModelCheck(
            kind=model_check.REFUSED,
            text=getattr(exc, "page", str(exc)),
            field=getattr(exc, "field", ""),
        )
    return models.ModelCheck(
        kind=checked.verdict.kind, text=checked.verdict.text, name=checked.name
    )


def add_model(given: models.ModelAdd) -> models.ModelAdded:
    """Save the model as `lado model add` does, its server probed now; named by default
    when `given.name` is None."""
    try:
        saved, verdict = model_settings.add_model(given.name, given.cli, given.model, given.server)
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


def remove_model(name: str) -> models.ModelRemoved:
    cleared: list[str] = []
    try:
        model_settings.remove_models([name], lambda _: None, cleared.append)
    except REFUSED as exc:
        raise _refusal(exc) from None
    return models.ModelRemoved(**listing().model_dump(), cleared=cleared)
