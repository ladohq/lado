"""The human's model servers, configured models and agent CLIs' default models (openspec
capabilities `model-servers` and `configured-models`): their rules, the servers' key files,
the checks on adding and what a CLI can run. `lado model-server add|list|remove` and `lado
model add|list|remove|default` call it; no session reads the entries yet.

The entries are kept in lado.db (lado.state: `model_servers`, `models`, `cli_defaults`); a
name is taken and found ignoring case. A configured model always lives on a server: a CLI's
own models are read from the CLI (`choices`), never kept. A server's key is kept in
`<LADO_HOME>/model-servers/<id>/key` alone, never in lado.db, written and removed by the
link-refusing writer of LADO's secrets (lado.project_secrets: folders 700, the file 600,
written whole by a rename); a server has a key exactly when its file is there. A server is
saved only when its probe recognises it, a model only when its server's list does not refuse
it, and a server a model uses is not removed. Every refusal is one line (Refused), never
holding a key.
"""

from __future__ import annotations

import contextlib
import errno
import os
import shutil
import sqlite3
import stat
import urllib.parse
import uuid
from collections.abc import Callable, Collection, Mapping
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
# A probe's refusals name model_servers.ADDRESS or model_servers.KEY.
NAME = "name"
KEY_FIELD = model_servers.KEY
CLI = "cli"
SERVER_FIELD = "server"
MODEL_FIELD = "model"


class Refused(Exception):
    """Why a command on the entries changed nothing, one line; `hint` what the human can try
    ("" for none); `field` the field it concerns; `page` and `page_hint` the line and the
    hint for Settings → Models, which names no command (None: the same as the command's)."""

    def __init__(
        self,
        text: str,
        hint: str = "",
        field: str = "",
        page: str | None = None,
        page_hint: str | None = None,
    ):
        super().__init__(text)
        self.hint = hint
        self.field = field
        self.page = text if page is None else page
        self.page_hint = hint if page_hint is None else page_hint


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
        f'no model server "{name}" is saved; lado model-server list names them',
        field=field,
        page=f'no model server "{name}" is saved',
    )


def _server_taken(name: str) -> Refused:
    return Refused(
        f'a model server "{name}" is saved already; to change its address or key: '
        f'lado model-server add "{name}" <address> [--key] --replace',
        field=NAME,
        page=f'a model server "{name}" is saved already; its Change sets another address or key',
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
    name: str,
    *,
    with_models: bool = False,
    confirmed: Collection[str] | None = None,
    removed: Callable[[str], None] = lambda _: None,
    cleared: Callable[[str], None] = lambda _: None,
) -> str:
    """Remove the saved server named `name` and its key file; its name as saved. Refused for
    no such server, or, without `with_models`, one a configured model refers to; with it,
    the models on the server and the defaults on them go first, in the same transaction,
    `removed` getting each model's name, then `cleared` each agent CLI's whose default went.
    With `confirmed` (the models the human was asked about), refused, nothing removed, unless
    the models on the server are those."""
    saved = state.model_server(name)
    if saved is None:
        raise no_server(name)
    if with_models:
        try:
            gone = state.remove_model_server_with_models(saved.id, confirmed)
        except state.ModelsChanged as changed:
            raise Refused(
                f'model server "{saved.name}" has other models now: '
                f"{', '.join(changed.names) or 'none'}; nothing was removed"
            ) from None
        if gone is None:  # removed meanwhile
            raise no_server(name)
        for model in gone.names:
            removed(model)
        for cli in gone.cleared:
            cleared(cli)
        return _remove_folder(saved)
    try:
        if state.models_on(saved.id):
            raise sqlite3.IntegrityError  # refused below, naming them
        state.remove_model_server(saved.id)  # the foreign key: a model added meanwhile
    except sqlite3.IntegrityError:
        used = state.models_on(saved.id)
        if not used:  # added and removed again meanwhile
            raise Refused(
                f'model server "{saved.name}" was used by a model meanwhile; run the command again',
                page=f'model server "{saved.name}" was used by a model meanwhile; try again',
            ) from None
        quoted = " ".join('"' + m.name + '"' for m in used)
        names = ", ".join(m.name for m in used)
        raise Refused(
            f'model server "{saved.name}" is used by the models '
            f"{names}; remove them first: lado model remove {quoted}",
            f'or remove them with it: lado model-server remove "{saved.name}" --with-models',
            page=f'model server "{saved.name}" is used by the models {names}',
            page_hint="",
        ) from None
    return _remove_folder(saved)


def _remove_folder(saved: state.ModelServer) -> str:
    """Remove the key folder of `saved`, removed from lado.db: its name. Refused when the
    disk refuses it."""
    try:
        _remove_key(saved.id)
    except OSError as exc:
        removed = (
            f'removed model server "{saved.name}", but not its folder '
            f"{key_folder(saved.id)} ({exc.strerror or type(exc).__name__})"
        )
        raise Refused(f"{removed}; lado doctor names it as left over", page=removed) from None
    return saved.name


@dataclass(frozen=True)
class Checked:
    """A model `check_model` lets through: its name (the one given, or its `default_name`),
    its CLI's provider, the model as saved, its server and the check's verdict (OK, or WARN
    for no list to check against)."""

    name: str
    provider: providers.Provider
    model: str
    server: state.ModelServer
    verdict: model_check.Verdict


Prober = Callable[[state.ModelServer], model_servers.Probe]


def check_model(
    name: str | None,
    cli: str,
    model: str,
    server_name: str | None,
    *,
    probe: Prober | None = None,
) -> Checked:
    """The checks of `add_model` on the model `model` of the CLI `cli` under `name` (None:
    no name to check), on the saved server `server_name`, saving nothing. Each check refuses
    before the next (Refused): the name, the CLI, the model, a server given (a CLI's own
    models are no entries), the server saved, its CLI's server API, the server answering with
    its kept key (asked with `probe`, else probed now), the API among the ones it proves, the
    model not one the server types as embeddings, the model against the server's list."""
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
    if server_name is None:
        raise Refused(
            "a CLI's own models need no saving; only a model on a server is added: "
            "--server <server>",
            "to make one its default: lado model default <cli> <model>",
            SERVER_FIELD,
        )
    server = state.model_server(server_name)
    if server is None:
        raise no_server(server_name, SERVER_FIELD)
    verdict = _on_server(provider, model, server, probe)
    if verdict.kind == model_check.REFUSED:
        raise Refused(
            verdict.text,
            field=MODEL_FIELD,
            page=f"{verdict.page}; ↻ Refresh reads the list again" if verdict.page else None,
        )
    if name is None:
        # The name comes from the model: a model no list checked may hold what no name may
        # (a hidden character), refused under the model's field.
        name = default_name(provider, model, server)
        try:
            check_name(name, MODEL)
        except Refused as exc:
            raise Refused(str(exc), field=MODEL_FIELD) from None
    return Checked(name, provider, model, server, verdict)


def default_name(provider: providers.Provider, model: str, server: state.ModelServer) -> str:
    """The name a model gets when the human gives none: `<model> · <server>`, and ` · <CLI
    title>` when the server suits more than one CLI (each name then says its CLI, whatever
    was ticked first). A name taken ignoring case gets ` · <CLI title>`, then ` (2)`, ` (3)`,
    … until free; each try is cut to MAX_NAME characters before its suffix."""
    suffixes = ["", f" · {provider.title}"]
    base_name = f"{model} · {server.name}"
    if len(model_servers.suiting(server.apis)[0]) > 1:
        suffixes = [f" · {provider.title}"]
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
) -> tuple[state.ConfiguredModel, model_check.Verdict]:
    """Check the model as `check_model` does, its server probed now, and save it under
    `name`, or None for its `default_name`: the saved entry and the check's verdict."""
    checked = check_model(name, cli, model, server_name)
    try:
        saved = state.add_model(checked.name, cli, checked.model, checked.server.id)
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
            page=f"{model} is an embeddings model on {server.name}; an agent needs a chat model",
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
    return model_servers.probe(
        server.address,
        server_key(server),
        add_command(server.name, True),
        key_where="Change sets its key",
    )


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


def remove_models(
    names: list[str],
    removed: Callable[[str], None],
    cleared: Callable[[str], None] = lambda _: None,
) -> None:
    """Remove the configured models named `names`, in their order, a name given twice
    (ignoring case) once, each with the default on it; `removed` gets each one's name as
    saved, then `cleared` the agent CLI whose default it was. Every name is found first:
    Refused for any no model has, nothing removed. A model another process removed in between
    is Refused once the others are removed."""
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
        done = state.remove_model(name)
        if done is None:
            gone.append(name)
            continue
        removed(name)
        for cli in done.cleared:
            cleared(cli)
    if gone:
        raise _no_models(gone)


def cli_title(cli: str) -> str:
    """The title of the agent CLI `cli`, the name itself for one LADO does not know."""
    return providers.get(cli).title if cli in providers.names() else cli


@dataclass(frozen=True)
class Choices:
    """What an agent CLI can run: `aliases` and `models` as its list gives them (`models` None
    for no full list, `why` saying so; `command` prints it), and its configured models.
    `other_name`: a name outside the list may be given, as no full list can refuse it."""

    aliases: tuple[str, ...]
    models: tuple[str, ...] | None
    why: str
    command: str
    external: list[state.ConfiguredModel]
    other_name: bool


Listing = Callable[[providers.Provider], base.ModelList]


def choices(provider: providers.Provider, listing: Listing) -> Choices:
    """The one place that computes what `provider`'s CLI can run: its list, given by `listing`
    within its command's timeout, and its configured models by name ignoring case. Nothing of
    it is kept here."""
    listed = listing(provider)
    return Choices(
        aliases=listed.aliases,
        models=listed.models,
        why=listed.why,
        command=listed.command,
        external=[model for model in state.models() if model.cli == provider.name],
        other_name=listed.models is None,
    )


@dataclass(frozen=True)
class CliDefault:
    """An agent CLI's default model as shown: its reference, its name (the configured model's,
    or the built-in model), the model as the CLI names it and the server's name (None for a
    built-in one)."""

    ref: state.ModelRef
    name: str
    model: str
    server: str | None


def defaults() -> list[CliDefault]:
    """Every agent CLI's default model, by CLI, running no CLI and asking no server."""
    models = {model.id: model for model in state.models()}
    servers = {server.id: server.name for server in state.model_servers()}
    shown = []
    for ref in state.cli_defaults():
        if ref.builtin is not None:
            shown.append(CliDefault(ref, ref.builtin, ref.builtin, None))
        elif ref.model_id in models:  # else removed since the first read
            model = models[ref.model_id]
            shown.append(CliDefault(ref, model.name, model.model, servers.get(model.server)))
    return shown


Env = Callable[[providers.Provider], Mapping[str, str]]


def known_cli(cli: str) -> providers.Provider:
    """The provider of the agent CLI `cli`; Refused for one LADO does not know."""
    if cli not in providers.names():
        raise Refused(
            f'LADO knows no agent CLI "{cli}"; it knows {", ".join(providers.names())}',
            field=CLI,
        )
    return providers.get(cli)


def _installed_cli(cli: str, env: Env) -> providers.Provider:
    provider = known_cli(cli)
    if shutil.which(provider.command, path=env(provider).get("PATH")) is None:
        raise Refused(f"{provider.title} is not installed", field=CLI)
    return provider


def _not_its_model(saved: state.ConfiguredModel, provider: providers.Provider) -> Refused:
    return Refused(
        f'"{saved.name}" is a model of {cli_title(saved.cli)}, not of {provider.title}',
        field=MODEL_FIELD,
    )


def _save_default(ref: state.ModelRef) -> None:
    try:
        state.set_cli_default(ref)
    except sqlite3.IntegrityError:  # its model removed meanwhile
        raise Refused("that model is no longer saved", field=MODEL_FIELD) from None


def _set_builtin(
    provider: providers.Provider, model: str, listed: base.ModelList
) -> tuple[state.ModelRef, model_check.Verdict]:
    """Set `model` as `provider`'s built-in default by the session model's thresholds: Refused
    for what is no name, or a name `listed` lacks."""
    if not model:
        raise Refused("the model is empty", field=MODEL_FIELD)
    char = visible.first_hidden(model)
    if char is not None:
        raise Refused(f"a model is one line {visible.refusal(char)}", field=MODEL_FIELD)
    verdict = model_check.verdict(provider, model, listed)
    if verdict.kind == model_check.REFUSED:
        raise Refused(verdict.text, field=MODEL_FIELD, page=verdict.page or None)
    ref = state.ModelRef(provider.name, None, model)
    _save_default(ref)
    return ref, verdict


def set_default(
    cli: str, name: str, env: Env, listing: Listing | None = None
) -> tuple[state.ModelRef, model_check.Verdict | None]:
    """Make `name` the default model of the agent CLI `cli`: a configured model of that CLI by
    its name ignoring case, else a built-in model; the reference and, for a built-in model,
    the check's verdict (an external one asks no server). Its list is given by `listing`, else
    read now with `env(provider)`, the agents' environment. Refused, nothing changed, for a
    CLI not known or not installed, a name both a configured and a built-in model of the CLI,
    a name that is only another CLI's configured model, and a built-in name refused."""
    provider = _installed_cli(cli, env)
    name = name.strip()
    listed = listing(provider) if listing is not None else provider.model_list(env(provider))
    saved = state.model(name)
    built_in = name in listed.aliases or name in (listed.models or ())
    if saved is not None and saved.cli == cli:
        if built_in or saved.name in listed.aliases or saved.name in (listed.models or ()):
            raise Refused(
                f'"{saved.name}" is both a saved model of {provider.title} and one of its own; '
                "rename the saved one: Settings → Models",
                field=MODEL_FIELD,
            )
        ref = state.ModelRef(cli, saved.id, None)
        _save_default(ref)
        return ref, None
    if saved is not None and not built_in:
        raise _not_its_model(saved, provider)
    return _set_builtin(provider, name, listed)


def set_default_ref(
    ref: state.ModelRef, env: Env, listing: Listing | None = None
) -> tuple[state.ModelRef, model_check.Verdict | None]:
    """`set_default` for a model picked on the page, by reference, so no name can be taken for
    another; a built-in name is checked as there."""
    provider = _installed_cli(ref.cli, env)
    if ref.model_id is not None:
        saved = state.model_by_id(ref.model_id)
        if saved is None:
            raise Refused("that model is no longer saved", field=MODEL_FIELD)
        if saved.cli != ref.cli:
            raise _not_its_model(saved, provider)
        _save_default(ref)
        return ref, None
    listed = listing(provider) if listing is not None else provider.model_list(env(provider))
    return _set_builtin(provider, (ref.builtin or "").strip(), listed)


def clear_default(cli: str) -> bool:
    """Clear the default model of the agent CLI `cli`, installed or not; False when it had
    none. Refused for a CLI LADO does not know."""
    return state.clear_cli_default(known_cli(cli).name)


def _no_models(names: list[str]) -> Refused:
    quoted = ", ".join(f'"{name}"' for name in names)
    if len(names) == 1:
        return Refused(
            f"no model {quoted} is saved; lado model list names them",
            page=f"no model {quoted} is saved",
        )
    return Refused(
        f"no models {quoted} are saved; lado model list names them",
        page=f"no models {quoted} are saved",
    )


def _model_taken(name: str) -> Refused:
    return Refused(
        f'a model "{name}" is saved already; remove it first: lado model remove "{name}"',
        field=NAME,
        page=f'the name is taken by the model "{name}"',
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
