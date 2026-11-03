"""The human's model servers and configured models, set once under names (openspec
capabilities `model-servers` and `configured-models`): their rules, the servers' key files
and the checks on adding. `lado model-server add|list|remove` and `lado model
add|list|remove` call it; no session reads the entries yet.

The entries are kept in lado.db (lado.state: `model_servers`, `models`); a name is taken
and found ignoring case. A server's key is kept in `<LADO_HOME>/model-servers/<id>/key`
alone, never in lado.db, written and removed by the link-refusing writer of LADO's secrets
(lado.project_secrets: folders 700, the file 600, written whole by a rename); a server has a
key exactly when its file is there. A server is saved only when its probe recognises it, a
model only when its CLI's or its server's list does not refuse it, and a server a model
uses is not removed. Every refusal is one line (Refused), never holding a key.
"""

from __future__ import annotations

import contextlib
import errno
import os
import sqlite3
import stat
import urllib.parse
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from lado import agent_env, model_check, model_servers, project_secrets, providers, state
from lado import text as visible
from lado.providers import base

KEYS = "model-servers"  # under LADO_HOME: a folder per server, by its id
KEY = "key"  # the key's file in a server's folder
MAX_NAME = 64
SERVER, MODEL = "model server", "model"  # what a name is of, in its refusals


# The field of a form a refusal concerns, for the UI ("" for none); the CLI ignores it.
NAME, ADDRESS, KEY_FIELD, CLI, SERVER_FIELD, MODEL_FIELD = (
    "name",
    model_servers.ADDRESS,
    model_servers.KEY,
    "cli",
    "server",
    "model",
)


class Refused(Exception):
    """Why a command on the entries changed nothing, one line; `hint` what the human can try
    ("" for none); `field` the field it concerns."""

    def __init__(self, text: str, hint: str = "", field: str = ""):
        super().__init__(text)
        self.hint = hint
        self.field = field


def check_name(name: str, of: str) -> None:
    """Refuse a name of a `of` (SERVER or MODEL) that is not one line of visible text of 1
    to MAX_NAME characters without spaces at its ends."""
    if not name:
        raise Refused(f"a {of}'s name is empty", field=NAME)
    char = visible.first_hidden(name)
    if char is not None:
        raise Refused(f"a {of}'s name is one line {visible.refusal(char)}", field=NAME)
    if name.strip() != name:
        raise Refused(f"a {of}'s name has no spaces at its ends", field=NAME)
    if len(name) > MAX_NAME:
        raise Refused(
            f"a {of}'s name is at most {MAX_NAME} characters (this one has {len(name)})",
            field=NAME,
        )


def key_folder(id: str) -> Path:
    """The folder of the key of the server `id`."""
    return state.home_path() / KEYS / id


def add_command(name: str, replace: bool) -> str:
    """`lado model-server add` as the human ran it, without its address: what a probe's
    message names to run again."""
    return f'lado model-server add "{name}"' + (" --replace" if replace else "")


def no_server(name: str, field: str = "") -> Refused:
    """The refusal of a server name no saved server has."""
    return Refused(
        f'no model server "{name}" is saved; lado model-server list names them', field=field
    )


def _server_taken(name: str) -> Refused:
    return Refused(
        f'a model server "{name}" is saved already; to change its address or key: '
        f'lado model-server add "{name}" <address> [--key] --replace',
        field=NAME,
    )


def server_to_add(name: str, replace: bool) -> state.ModelServer | None:
    """The saved server `add_server` would replace (None for a new one), or Refused for a
    name it refuses: one that is no name, taken without `replace`, not saved with it. A
    command checks it before it asks for a key."""
    check_name(name, SERVER)
    saved = state.model_server(name)
    if saved is not None and not replace:
        raise _server_taken(saved.name)
    if saved is None and replace:
        raise no_server(name, NAME)
    return saved


def same_address(a: str, b: str) -> bool:
    """Whether two probe roots (model_servers.address) are one server's: the same scheme,
    host ignoring case, port with its default filled in, and path."""

    def parts(root: str) -> tuple[str, str, int, str]:
        split = urllib.parse.urlsplit(root)
        port = split.port or (443 if split.scheme == "https" else 80)
        return split.scheme, (split.hostname or "").lower(), port, split.path

    return parts(a) == parts(b)


def add_server(
    name: str,
    address: str,
    key: str | None,
    *,
    replace: bool = False,
    warn: Callable[[str], None],
    note: Callable[[str], None],
) -> model_servers.Probe:
    """Probe `address` and save the server it is under `name`, with `key` in its key file;
    with `replace`, replace the saved server's address, type and APIs instead, and its key
    when `key` is given (else the kept key is sent and kept). `warn` gets the plain-http
    warning before anything is sent; `note`, once the probe recognised the server, a line
    for each other saved server at the same address (two names on one address may carry two
    keys: named, not refused). Refused for a name taken or not saved, ValueError for an
    address the probe does not take, model_servers.ProbeError for a server it does not
    recognise; nothing changes then."""
    saved = server_to_add(name, replace)
    if key is not None:
        check_key(key)
    root, _ = model_servers.address(address)
    sent = key if key is not None or saved is None else server_key(saved)
    warning = model_servers.plain_http_warning(root, sent)
    if warning:
        warn(warning)
    found = model_servers.probe(address, sent, add_command(name, replace))
    for other in state.model_servers():
        if (saved is None or other.id != saved.id) and same_address(other.address, found.address):
            note(f'same address as model server "{other.name}"')
    apis = [api for api in base.SERVER_APIS if api in found.apis]
    if saved is not None:
        if key is not None:
            _write_key(saved.id, key)
        if not state.replace_model_server(saved.id, found.address, found.kind, apis):
            raise no_server(name)  # removed meanwhile; its key file is left over (doctor)
        return found
    id = uuid.uuid4().hex[:12]
    if key is not None:
        _write_key(id, key)
    try:
        state.add_model_server(id, name, found.address, found.kind, apis)
    except BaseException as exc:
        # A cleanup that fails leaves the key folder over (doctor names it), never hides why.
        with contextlib.suppress(OSError, Refused):
            _remove_key(id)
        if isinstance(exc, state.NameTaken):
            raise _server_taken(exc.name) from None
        raise
    return found


def remove_server(
    name: str, *, with_models: bool = False, removed: Callable[[str], None] = lambda _: None
) -> str:
    """Remove the saved server named `name` and its key file; its name as saved. Refused for
    no such server, or, without `with_models`, one a configured model refers to; with it,
    the models on the server go first, in the same transaction, `removed` getting each
    one's name."""
    saved = state.model_server(name)
    if saved is None:
        raise no_server(name)
    if with_models:
        models = state.remove_model_server_with_models(saved.id)
        if models is None:  # removed meanwhile
            raise no_server(name)
        for model in models:
            removed(model)
        return _remove_folder(saved)
    try:
        if state.models_on(saved.id):
            raise sqlite3.IntegrityError  # refused below, naming them
        state.remove_model_server(saved.id)  # the foreign key: a model added meanwhile
    except sqlite3.IntegrityError:
        used = state.models_on(saved.id)
        if not used:  # added and removed again meanwhile
            raise Refused(
                f'model server "{saved.name}" was used by a model meanwhile; run the command again'
            ) from None
        quoted = " ".join('"' + m.name + '"' for m in used)
        raise Refused(
            f'model server "{saved.name}" is used by the models '
            f"{', '.join(m.name for m in used)}; remove them first: lado model remove {quoted}",
            f'or remove them with it: lado model-server remove "{saved.name}" --with-models',
        ) from None
    return _remove_folder(saved)


def _remove_folder(saved: state.ModelServer) -> str:
    """Remove the key folder of `saved`, removed from lado.db: its name. Refused when the
    disk refuses it."""
    try:
        _remove_key(saved.id)
    except OSError as exc:
        raise Refused(
            f'removed model server "{saved.name}", but not its folder '
            f"{key_folder(saved.id)} ({exc.strerror or type(exc).__name__}); lado doctor "
            "names it as left over"
        ) from None
    return saved.name


@dataclass(frozen=True)
class Checked:
    """A model `check_model` lets through: its CLI's provider, the model as saved, its
    server (None for none), the check's verdict (OK, or WARN for no list to check against)
    and the CLI's aliases (none for a model on a server)."""

    provider: providers.Provider
    model: str
    server: state.ModelServer | None
    verdict: model_check.Verdict
    aliases: tuple[str, ...]


Prober = Callable[[state.ModelServer], model_servers.Probe]


def check_model(
    name: str | None,
    cli: str,
    model: str,
    server_name: str | None,
    env: Callable[[providers.Provider], Mapping[str, str]],
    *,
    probe: Prober | None = None,
) -> Checked:
    """The checks of `add_model` on the model `model` of the CLI `cli` under `name` (None:
    no name to check), on the saved server `server_name` (None for the CLI's own way to its
    models), saving nothing. Each check refuses before the next (Refused): the name, the CLI,
    the model, the server saved, its CLI's server API, the server answering with its kept key
    (asked with `probe`, else probed now), the API among the ones it proves, the model not one
    the server types as embeddings, the model against the server's list, or for no server
    against the CLI's own list, read with `env(provider)` (the agents' environment)."""
    if name is not None:
        check_name(name, MODEL)
        taken = state.model(name)
        if taken is not None:
            raise _model_taken(taken.name)
    if cli not in providers.names():
        raise Refused(
            f'LADO knows no agent CLI "{cli}"; --cli takes one of {", ".join(providers.names())}',
            field=CLI,
        )
    provider = providers.get(cli)
    model = model.strip()
    if not model:
        raise Refused(
            f"the model is empty: --model takes a model as {provider.title} names it",
            field=MODEL_FIELD,
        )
    aliases: tuple[str, ...] = ()
    if server_name is None:
        server = None
        listed = provider.model_list(env(provider))
        aliases = listed.aliases
        verdict = model_check.verdict(provider, model, listed)
    else:
        server = state.model_server(server_name)
        if server is None:
            raise no_server(server_name, SERVER_FIELD)
        verdict = _on_server(provider, model, server, probe)
    if verdict.kind == model_check.REFUSED:
        raise Refused(verdict.text, field=MODEL_FIELD)
    return Checked(provider, model, server, verdict, aliases)


def default_name(
    provider: providers.Provider,
    model: str,
    server: state.ModelServer | None,
    aliases: tuple[str, ...],
) -> str:
    """The name a model gets when the human gives none: for an alias of the CLI (`aliases`),
    the first word of the CLI's title and the alias capitalised (`Claude Sonnet`); for a
    model on `server`, `<model> · <server>`; else the model. A name taken ignoring case gets
    ` · <CLI title>`, then ` (2)`, ` (3)`, … until free; each try is cut to MAX_NAME
    characters before its suffix."""
    if server is not None:
        base_name = f"{model} · {server.name}"
    elif model in aliases:
        base_name = f"{provider.title.split()[0]} {model[:1].upper()}{model[1:]}"
    else:
        base_name = model
    suffixes = ["", f" · {provider.title}"]
    number = 2
    while True:
        for suffix in suffixes:
            name = base_name[: MAX_NAME - len(suffix)].rstrip() + suffix
            if state.model(name) is None:
                return name
        suffixes = [f" · {provider.title} ({number})"]
        number += 1


def add_model(
    name: str | None,
    cli: str,
    model: str,
    server_name: str | None,
    env: Callable[[providers.Provider], Mapping[str, str]],
) -> tuple[state.ConfiguredModel, model_check.Verdict]:
    """Check the model as `check_model` does, its server probed now, and save it under
    `name`, or None for its `default_name`: the saved entry and the check's verdict."""
    checked = check_model(name, cli, model, server_name, env)
    server = checked.server
    if name is None:
        name = default_name(checked.provider, checked.model, server, checked.aliases)
    try:
        saved = state.add_model(name, cli, checked.model, server.id if server else None)
    except state.NameTaken as exc:  # added meanwhile
        raise _model_taken(exc.name) from None
    except sqlite3.IntegrityError:  # its server removed meanwhile
        raise no_server(server_name or "", SERVER_FIELD) from None
    return saved, checked.verdict


def _on_server(
    provider: providers.Provider,
    model: str,
    server: state.ModelServer,
    probe: Prober | None = None,
) -> model_check.Verdict:
    """The verdict on `model` of `provider` on `server`, asked with `probe`, else probed now
    with its kept key: the server may have changed since it was saved."""
    api = provider.server_api
    if not api:
        raise Refused(
            f"{server.name} does not suit {provider.title}: {provider.title} speaks no model "
            "server's API",
            field=SERVER_FIELD,
        )
    try:
        found = probe(server) if probe is not None else probe_saved(server)
    except model_servers.ProbeError as exc:
        raise Refused(f"{exc}; LADO cannot check {model}", exc.hint, SERVER_FIELD) from None
    if api not in found.apis:
        suits = [title for title, _ in found.clis()[0]]
        raise Refused(
            f"{server.name} does not suit {provider.title}: it has no {api}; it suits "
            f"{', '.join(suits) or 'no CLI'}",
            field=SERVER_FIELD,
        )
    if model in found.embeddings:
        raise Refused(
            f"{model} is an embeddings model on {server.name}; an agent needs a chat model: "
            f"{model_servers.PROBE_COMMAND} {server.address} lists the models",
            field=MODEL_FIELD,
        )
    listed = base.ModelList(
        models=found.models,
        command=f"{model_servers.PROBE_COMMAND} {server.address}",
        why=found.models_why,
    )
    return model_check.verdict(provider, model, listed, whose=server.name)


def probe_saved(server: state.ModelServer) -> model_servers.Probe:
    """`server` probed now with its kept key (Refused for a key file LADO does not read,
    model_servers.ProbeError for a probe that fails)."""
    return model_servers.probe(server.address, server_key(server), add_command(server.name, True))


def rename_model(name: str, new: str) -> state.ConfiguredModel:
    """Rename the configured model named `name` to `new`, its CLI, model and server kept;
    the model renamed. Refused for no such model, a new name that is no name, or one another
    model has ignoring case."""
    check_name(new, MODEL)
    try:
        renamed = state.rename_model(name, new)
    except state.NameTaken as exc:
        raise _model_taken(exc.name) from None
    saved = state.model(new) if renamed else None
    if saved is None:
        raise _no_models([name])
    return saved


def remove_models(names: list[str], removed: Callable[[str], None]) -> None:
    """Remove the configured models named `names`, in their order, a name given twice
    (ignoring case) once; `removed` gets each one's name as saved. Every name is found
    first: Refused for any no model has, nothing removed. A model another process removed
    in between is Refused once the others are removed."""
    found: dict[str, None] = {}  # the names as saved, in order, once each
    unknown: dict[str, str] = {}
    for name in names:
        saved = state.model(name)
        if saved is None:
            unknown.setdefault(name.casefold(), name)
        else:
            found.setdefault(saved.name)
    if unknown:
        raise _no_models(list(unknown.values()))
    gone = []
    for name in found:
        if state.remove_model(name):
            removed(name)
        else:
            gone.append(name)
    if gone:
        raise _no_models(gone)


def _no_models(names: list[str]) -> Refused:
    quoted = ", ".join(f'"{name}"' for name in names)
    if len(names) == 1:
        return Refused(f"no model {quoted} is saved; lado model list names them")
    return Refused(f"no models {quoted} are saved; lado model list names them")


def _model_taken(name: str) -> Refused:
    return Refused(
        f'a model "{name}" is saved already; remove it first: lado model remove "{name}"',
        field=NAME,
    )


def server_key(server: state.ModelServer) -> str | None:
    """The kept key of `server`, None for none; Refused for a key file LADO does not read (a
    link, not a regular file, larger than the limit, or one the disk refuses)."""
    path = key_folder(server.id) / KEY
    try:
        with project_secrets.open_chain((KEYS, server.id), make=False) as fd:
            if fd is None:
                return None
            try:
                out = os.open(KEY, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                return None
            except OSError as exc:
                if exc.errno == errno.ELOOP:
                    raise _link(path) from None
                raise
            with os.fdopen(out, "rb") as file:
                if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
                    raise Refused(f"{path} is not a regular file")
                data = file.read(agent_env.MAX_VALUE + 1)
    except project_secrets.LinkRefused as exc:
        raise _link(exc.path) from None
    except OSError as exc:
        raise Refused(f"{path} cannot be read ({exc.strerror or type(exc).__name__})") from None
    if len(data) > agent_env.MAX_VALUE:  # never a key cut to the limit
        raise Refused(f"{path} is larger than 64 KiB")
    text = data.decode("utf-8", "surrogateescape")
    return text[:-1] if text.endswith("\n") else text  # project_secrets.stored's line break


def clis(server: state.ModelServer) -> list[str]:
    """The titles of the CLIs that can use `server`, by the APIs it proved when saved."""
    suits, _ = model_servers.clis(server.apis)
    return [title for title, _ in suits]


def has_key(server: state.ModelServer) -> bool:
    return os.path.lexists(key_folder(server.id) / KEY)


def _link(path: Path) -> Refused:
    return Refused(f"{path} is a symbolic link: LADO keeps a server's key only in its own folders")


def _write_key(id: str, key: str) -> None:
    try:
        project_secrets.write_at((KEYS, id), key_folder(id), KEY, key)
    except project_secrets.LinkRefused as exc:
        raise _link(exc.path) from None
    except OSError as exc:
        raise Refused(
            f"{key_folder(id) / KEY} cannot be written ({exc.strerror or type(exc).__name__})"
        ) from None


def check_key(key: str) -> None:
    """Refuse an empty key, one no HTTP header can carry (a byte of no UTF-8 on stdin among
    them, which could not be stored either), and one larger than its file may hold
    (agent_env.MAX_VALUE, its stored form), rather than keep or send it cut."""
    if not key:
        raise Refused("the key is empty", field=KEY_FIELD)
    if not model_servers.carriable(key):
        raise Refused(model_servers.NOT_CARRIABLE, field=KEY_FIELD)
    if len(project_secrets.stored(key)) > agent_env.MAX_VALUE:
        raise Refused("the key is larger than 64 KiB", field=KEY_FIELD)


def _remove_key(id: str) -> None:
    """Remove the key file of the server `id` and its folder; OSError (Refused for a link)
    when the disk refuses it."""
    try:
        project_secrets.remove_at((KEYS, id), key_folder(id), KEY)
        with project_secrets.open_chain((KEYS,), make=False) as fd:
            if fd is not None:
                try:
                    os.rmdir(id, dir_fd=fd)
                except FileNotFoundError:
                    pass
    except project_secrets.LinkRefused as exc:
        raise _link(exc.path) from None
