"""The human's model servers, configured models and agent CLIs' default models (openspec
capabilities `model-servers` and `configured-models`): their rules, the servers' key files,
the checks on adding and what a CLI can run. `lado model-server add|list|remove` and `lado
model add|list|remove|default` call it; a launch asks it what an agent starts on (start_model,
for a worker with a model of its own worker_start), whether that can start (check_start) and
which servers go into the agent (agent_servers); list_models asks it what can run (cli_models).

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
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path

from lado import agent_env, model_check, model_servers, project_secrets, providers, state
from lado import text as visible
from lado.providers import base
from lado.providers.base import KEY_VARIABLE

KEYS = "model-servers"  # under LADO_HOME: a folder per server, by its id
KEY = "key"  # the key's file in a server's folder
MAX_NAME = 64
SERVER, MODEL = "model server", "model"  # what a name is of, in its refusals
REFUSED_PEEK = "refused"
NOT_LISTED_PEEK = "not in its list"
# What OpenCode and Kilo CLI substitute in their config's text ({env:…} checked on both, {file:…}
# taken to work the same): text LADO did not write there must hold neither.
EXPANDED = ("{env:", "{file:")
WOULD_EXPAND = f"the agent CLI would expand ({' or '.join(EXPANDED)})"
# Both put a variable's value into their config's text as it is, inside its JSON string (OpenCode
# 1.18.35 then stops and prints the text with the key, Kilo 7.8.8 drops all of the config, checked
# with `debug config`): a key that holds one of these cannot reach them.
BREAKS_CONFIG = ('"', "\\")
# Where a server of a known type sets a model's context, from its own documents (LM Studio's `lms
# load`, Ollama's Context length); "" for any other.
CONTEXT_HOW = {
    "": "load the model with a larger context",
    base.LM_STUDIO: "load the model with a larger context (lms load --context-length)",
    model_servers.OLLAMA: "raise OLLAMA_CONTEXT_LENGTH, or the context in the Ollama app",
}
CONTEXT_PEEK = "context too small"  # the folded Advanced's words for that warning
CONTEXT_UNKNOWN_PEEK = "context unknown"  # and for a public server's unknown context


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
    hint for Settings' pages, which name no command (None: the same as the command's).
    For the launch window: `window` the line under its Model field, `short` the same for a
    line that points there, `peek` a few words for the folded Advanced (None: `page`,
    `window`, REFUSED_PEEK), `retry` whether a new check can help."""

    def __init__(
        self,
        text: str,
        hint: str = "",
        field: str = "",
        page: str | None = None,
        page_hint: str | None = None,
        *,
        window: str | None = None,
        short: str | None = None,
        peek: str = "",
        retry: bool = False,
    ):
        super().__init__(text)
        self.hint = hint
        self.field = field
        self.page = text if page is None else page
        self.page_hint = hint if page_hint is None else page_hint
        self.window = self.page if window is None else window
        self.short = self.window if short is None else short
        self.peek = peek or REFUSED_PEEK
        self.retry = retry


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
        page=f'A model server "{name}" is saved already; its Change sets another address or key',
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
    if late := found.late_warning():
        warn(late)
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
    _check_own_name(provider, model, server)
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
    if len(model_servers.suiting(server.apis, server.kind)[0]) > 1:
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


def _check_own_name(provider: providers.Provider, model: str, server: state.ModelServer) -> None:
    """Refuse a model of `server` whose name `provider`'s CLI reads as its own: no request."""
    if provider.reserved_model(model):
        raise Refused(
            f"{provider.title} reads {model} as its own model, so it would not ask {server.name} "
            "for it; give the model another name on the server",
            field=MODEL_FIELD,
        )


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
    if refusal := _type_refusal(provider, server):
        raise Refused(refusal, field=SERVER_FIELD)
    try:
        found = probe(server) if probe is not None else probe_saved(server)
    except model_servers.ProbeError as exc:
        text = f"{exc}; LADO cannot check {model}"
        if exc.silent:
            raise Refused(
                text,
                exc.hint,
                SERVER_FIELD,
                window=f"{server.name} does not answer ({exc.silent}); {model} is on it. Start "
                "the server or pick another model.",
                short=f"{server.name} does not answer",
                peek="not answering",
                retry=True,
            ) from None
        raise Refused(text, exc.hint, SERVER_FIELD, retry=True) from None
    if api in found.late:
        raise Refused(
            f"{model_servers.late_words([api])} of {server.name} {model_servers.LATE}: try again",
            field=SERVER_FIELD,
            retry=True,
        )
    if api not in found.apis:
        suits = [title for title, _ in found.clis()[0]]
        raise Refused(
            f"{server.name} does not suit {provider.title}: it has no {api}; it suits "
            f"{', '.join(suits) or 'no CLI'}",
            field=SERVER_FIELD,
            retry=True,
        )
    if model in found.embeddings:
        raise Refused(
            f"{model} is an embeddings model on {server.name}; an agent needs a chat model: "
            f"{model_servers.PROBE_COMMAND} {server.address} lists the models",
            field=MODEL_FIELD,
            page=f"{model} is an embeddings model on {server.name}; an agent needs a chat model",
            retry=True,
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
    for no full list, `why` saying so), and its configured models. `other_name`: a name outside
    the list may be given, as no full list can refuse it. `read_again`: reading the list again
    may change the answer."""

    aliases: tuple[str, ...]
    models: tuple[str, ...] | None
    why: str
    external: list[state.ConfiguredModel]
    other_name: bool
    read_again: bool


Listing = Callable[[providers.Provider], base.ModelList]


def choices(
    provider: providers.Provider,
    listing: Listing,
    saved: list[state.ConfiguredModel] | None = None,
) -> Choices:
    """The one place that computes what `provider`'s CLI can run: its list, given by `listing`
    within its command's timeout, and its configured models by name ignoring case, among
    `saved` (None: all in lado.db). Nothing of it is kept here."""
    listed = listing(provider)
    return Choices(
        aliases=listed.aliases,
        models=listed.models,
        why=listed.why,
        external=[
            model
            for model in (state.models() if saved is None else saved)
            if model.cli == provider.name
        ],
        other_name=listed.models is None,
        read_again=not listed.fixed,
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


def _installed(provider: providers.Provider, env: Env) -> bool:
    return shutil.which(provider.command, path=env(provider).get("PATH")) is not None


def _installed_cli(cli: str, env: Env) -> providers.Provider:
    provider = known_cli(cli)
    if not _installed(provider, env):
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


def _one_line(model: str) -> None:
    char = visible.first_hidden(model)
    if char is not None:
        raise Refused(f"a model is one line {visible.refusal(char)}", field=MODEL_FIELD)


def _builtin(
    provider: providers.Provider, model: str, listed: base.ModelList
) -> tuple[state.ModelRef, model_check.Verdict]:
    """`model` as `provider`'s built-in default, by the session model's thresholds: Refused for
    what is no name, or a name `listed` lacks. Saves nothing."""
    if not model:
        raise Refused("the model is empty", field=MODEL_FIELD)
    _one_line(model)
    verdict = model_check.verdict(provider, model, listed)
    if verdict.kind == model_check.REFUSED:
        raise Refused(
            verdict.text,
            field=MODEL_FIELD,
            page=verdict.page or None,
            peek=NOT_LISTED_PEEK,
            retry=not listed.fixed,
        )
    return state.ModelRef(provider.name, None, model), verdict


def check_default(
    cli: str, name: str, env: Env, listing: Listing | None = None
) -> tuple[state.ModelRef, model_check.Verdict | None]:
    """What a name given for the default model of the agent CLI `cli` is, saving nothing: a
    configured model of that CLI by its name ignoring case, else a built-in model; the
    reference and, for a built-in model, the check's verdict (an external one asks no server).
    The list is given by `listing`, else read now with `env(provider)`, the agents'
    environment. Refused for a CLI not known or not installed, a name both a configured and a
    built-in model of the CLI, a name that is only another CLI's configured model, and a
    built-in name refused. The one reading of a typed name: the command and the page's Other
    name take it, and its note."""
    provider = _installed_cli(cli, env)
    name = name.strip()
    listed = listing(provider) if listing is not None else provider.model_list(env(provider))
    own = {*listed.aliases, *(listed.models or ())}
    saved = state.model(name)
    if saved is not None and saved.cli == cli:
        if name in own or saved.name in own:
            raise Refused(
                f'"{saved.name}" is both a saved model of {provider.title} and one of its own; '
                "rename the saved one: Settings → Model servers",
                field=MODEL_FIELD,
            )
        return state.ModelRef(cli, saved.id, None), None
    if saved is not None and name not in own:
        raise _not_its_model(saved, provider)
    return _builtin(provider, name, listed)


def set_default(
    cli: str, name: str, env: Env, listing: Listing | None = None
) -> tuple[state.ModelRef, model_check.Verdict | None]:
    """Make the typed `name` the default model of the agent CLI `cli`, as `check_default` reads
    it; the reference and the check's verdict. Refused as there, nothing changed."""
    ref, verdict = check_default(cli, name, env, listing)
    _save_default(ref)
    return ref, verdict


def set_default_ref(
    ref: state.ModelRef, env: Env, listing: Listing | None = None
) -> tuple[state.ModelRef, model_check.Verdict | None]:
    """`set_default` for a row picked in a list, by reference, so no name can be taken for
    another; a built-in name is checked by the thresholds alone."""
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
    built_in, verdict = _builtin(provider, (ref.builtin or "").strip(), listed)
    _save_default(built_in)
    return built_in, verdict


def clear_default(cli: str) -> bool:
    """Clear the default model of the agent CLI `cli`, installed or not; False when it had
    none. Refused for a CLI LADO does not know."""
    return state.clear_cli_default(known_cli(cli).name)


@dataclass(frozen=True)
class StartModel:
    """What an agent starts on (start_model): `name` for the human and `model` as its CLI or
    server names it, None for the CLI's own choice; `server` and `entry` for an external
    model; `source` for its record (state.MODEL_SOURCES); `note` the detail of an agent left
    on its CLI's choice by a table of another CLI; `gone` for an entry no longer saved."""

    source: str = state.CLI_DEFAULT
    name: str | None = None
    model: str | None = None
    server: state.ModelServer | None = None
    entry: state.ConfiguredModel | None = None
    note: str | None = None
    gone: bool = False

    def launch_name(self, provider: providers.Provider) -> str | None:
        """The model as `provider`'s CLI is told it."""
        if self.server is not None and self.model is not None:
            return provider.server_model(self.server.id, self.model)
        return self.model


def _way_to_resume(provider: providers.Provider) -> str:
    return (
        f"resume it with --model '' for {provider.title}'s settings or --model <model> for another"
    )


def _external(saved: state.ConfiguredModel, source: str) -> StartModel:
    server = state.model_server_by_id(saved.server)
    return StartModel(source, saved.name, saved.model, server, saved)


def start_model(power: state.PowerTable | None, provider: providers.Provider) -> StartModel:
    """What an agent of `provider`'s CLI in a session with the table `power` starts on, read
    now: its table's row when it is of that CLI, else the CLI's default of Settings → Agent CLIs,
    else the CLI's choice. Reads lado.db only. Refused for a table that cannot be read."""
    note = None
    if power is not None:
        if not power.readable:
            raise Refused(
                f"the session's model cannot be read; {_way_to_resume(provider)}",
                field=MODEL_FIELD,
            )
        row = power.row()
        if row.cli == provider.name:
            if not row.model:
                return StartModel()
            if row.model_id is None:
                return StartModel(state.SESSION, row.model, row.model)
            saved = state.model_by_id(row.model_id)
            if saved is None:
                return StartModel(state.SESSION, row.shown, row.model, gone=True)
            return _external(saved, state.SESSION)
        if row.model:
            note = f"the session's model {row.shown} is for {cli_title(row.cli)}"
    for ref in state.cli_defaults():
        if ref.cli != provider.name:
            continue
        if ref.builtin is not None:
            return StartModel(state.DEFAULT_MODEL, ref.builtin, ref.builtin)
        saved = state.model_by_id(ref.model_id or "")
        if saved is not None:  # else removed since the first read
            return _external(saved, state.DEFAULT_MODEL)
    return StartModel(note=note)


def session_row(
    name: str, provider: providers.Provider, env: Mapping[str, str], listing: Listing | None = None
) -> state.PowerRow:
    """The table's row of a model given for a session of `provider`'s CLI: "" (or only spaces)
    is the CLI's own settings, any other name is read as `check_default` reads it."""
    name = name.strip()
    if not name:
        return state.PowerRow(provider.name, "")
    ref, _ = check_default(provider.name, name, lambda _: env, listing)
    if ref.model_id is None:
        return state.PowerRow(provider.name, ref.builtin or "")
    saved = state.model_by_id(ref.model_id)
    if saved is None:  # removed since the first read
        raise Refused("that model is no longer saved", field=MODEL_FIELD)
    return state.PowerRow(provider.name, saved.model, saved.id, saved.name)


def _name_cli(
    name: str,
    given: providers.Provider | None,
    session_cli: providers.Provider,
    env: Env,
    listing: Listing,
) -> providers.Provider:
    """The agent CLI whose reading of `name` a worker takes: `given`, or with none the session's,
    else the one other installed CLI that has it. Having it is being its saved model, alias or
    listed model; another CLI's list is read only when the first CLI lacks the name, and one
    that failed has no name. Refused for a name of another CLI than `given`, of several others,
    of a CLI not installed, or of none with no `given`: an agent's typo is not started on, though
    a start would warn."""
    _one_line(name)
    saved = state.model(name)

    def has(provider: providers.Provider) -> bool:
        if saved is not None and saved.cli == provider.name:
            return True
        listed = listing(provider)
        return name in {*listed.aliases, *(listed.models or ())}

    first = given or session_cli
    if has(first):
        return first
    if given is not None and saved is not None:
        raise _not_its_model(saved, given)
    others = [providers.get(cli) for cli in providers.names() if cli != first.name]
    found = [other for other in others if _installed(other, env) and has(other)]
    titles = " and ".join(other.title for other in found)
    if given is not None:
        if found:
            raise Refused(f"{name} is a model of {titles}, not of {given.title}", field=MODEL_FIELD)
        return given  # check_default refuses it, or warns for a CLI of no full list
    if len(found) == 1:
        return found[0]
    if found:
        raise Refused(f"{name} is a model of {titles}; give provider", field=MODEL_FIELD)
    if saved is not None:  # the one CLI that has it is not installed
        raise Refused(f"{cli_title(saved.cli)} is not installed", field=CLI)
    free = ""
    if listing(session_cli).models is None:
        free = (
            f'; {session_cli.title} gives no full list: provider="{session_cli.name}" starts it '
            "with a warning"
        )
    raise Refused(
        f"{name} is in no agent CLI's list of models; list_models shows them{free}",
        field=MODEL_FIELD,
    )


def worker_start(
    name: str,
    given: providers.Provider | None,
    session_cli: providers.Provider,
    env: Env,
    listing: Listing,
) -> tuple[providers.Provider, StartModel]:
    """The CLI and model of a worker spawned with `model` `name`, the provider `given` if any:
    "" (or only spaces) is the CLI's own settings, any other name finds its CLI (_name_cli) and
    is read there as a session's. Refused as those are; nothing is stored."""
    name = name.strip()
    cli = _name_cli(name, given, session_cli, env, listing) if name else given or session_cli
    row = session_row(name, cli, env(cli), listing)
    start = start_model(state.PowerTable.of(row), cli)
    return cli, replace(start, source=state.SUPERVISOR_CHOICE) if name else start


def _starts_on(session: state.Session, provider: providers.Provider) -> str | None:
    try:
        return start_model(session.power, provider).name
    except Refused:  # a table that cannot be read names nothing
        return None


def _shown_external(saved: state.ConfiguredModel, provider: providers.Provider) -> dict:
    start = _external(saved, state.SUPERVISOR_CHOICE)
    blocked = None
    try:
        check_launch(start, provider)
    except Refused as refused:
        blocked = str(refused)
    server = start.server.name if start.server is not None else None
    return {"name": saved.name, "server": server, "blocked": blocked}


def cli_models(
    session: state.Session, only: providers.Provider | None, env: Env, listing: Listing
) -> list[dict]:
    """What the supervisor of `session` can name, for each installed agent CLI, the session's
    first, or for `only`: `choices` by CLI, a name each, as a CLI may list hundreds. Asks no
    server and holds a server's saved name alone. Refused for `only` not installed."""
    if only is not None:
        chosen = [_installed_cli(only.name, env)]
    else:
        names = sorted(providers.names(), key=lambda cli: cli != session.provider)
        chosen = [p for p in map(providers.get, names) if _installed(p, env)]
    shown = []
    for provider in chosen:
        found = choices(provider, listing)
        shown.append(
            {
                "cli": provider.name,
                "title": provider.title,
                "session": provider.name == session.provider,
                "starts_on": _starts_on(session, provider),
                "note": found.why or None,
                "builtin": list(dict.fromkeys((*found.aliases, *(found.models or ())))),
                "external": [_shown_external(saved, provider) for saved in found.external],
            }
        )
    return shown


def _expands(*texts: str) -> bool:
    return any(mark in text for text in texts for mark in EXPANDED)


def _runs_on(server: state.ModelServer) -> str:
    """Which agent CLIs run on `server`, for a refusal."""
    titles = clis(server)
    if not titles:
        return "no agent CLI runs on it"
    if len(titles) == 1:
        return f"{titles[0]} does"
    return f"{', '.join(titles[:-1])} and {titles[-1]} do"


def _type_refusal(provider: providers.Provider, server: state.ModelServer) -> str:
    """Why `provider`'s CLI cannot use a server of `server`'s type, and who can; "" for none."""
    why = provider.refuses_server(server.kind)
    if not why:
        return ""
    return f"{server.name} does not suit {provider.title}: {why}; {_runs_on(server)}"


def check_launch(start: StartModel, provider: providers.Provider) -> None:
    """What refuses `start` for an agent of `provider`'s CLI with no request and no list: an
    entry no longer saved, a server of a type its CLI refuses, a name its CLI reads as its own,
    text its CLI would expand."""
    if start.gone:
        raise Refused(
            f"the session ran on the model {start.name}, which is no longer saved; "
            f"{_way_to_resume(provider)}",
            field=MODEL_FIELD,
            window=f"The session ran on the model {start.name}, which is no longer in Settings → "
            f"Models. Pick a model or use {provider.title}'s settings.",
            short=f"{start.name} is no longer saved",
            peek="not in Settings",
        )
    if start.server is None or start.entry is None:
        return
    if refusal := _type_refusal(provider, start.server):
        raise Refused(
            f"{start.name} is on the model server {start.server.name}; {refusal}",
            field=MODEL_FIELD,
            short=f"{start.server.name} does not suit {provider.title}",
            peek="does not suit",
        )
    _check_own_name(provider, start.entry.model, start.server)
    if _expands(start.entry.name, start.entry.model, start.server.name, start.server.address):
        raise Refused(
            f"{start.name} cannot start: its name, id or server holds text {WOULD_EXPAND}; rename "
            "it, or pick another model",
            field=MODEL_FIELD,
        )
    _config_key(start.server)


def _config_key(server: state.ModelServer) -> str | None:
    """The kept key of `server` for an agent's config; Refused, naming no part of it, for one
    LADO does not read or one that would break the config."""
    key = server_key(server)
    if key is not None and (
        any(mark in key for mark in BREAKS_CONFIG) or not model_servers.carriable(key)
    ):
        raise Refused(
            f'the key of model server "{server.name}" holds {" or ".join(BREAKS_CONFIG)} or a '
            "control character, which would break the agent CLI's config; give the server "
            "another key",
            field=MODEL_FIELD,
            retry=True,
        )
    return key


def check_start(
    start: StartModel,
    provider: providers.Provider,
    env: Mapping[str, str],
    probe: Prober | None = None,
    listing: Listing | None = None,
) -> model_check.Verdict:
    """The check of `start` before a session starts or resumes on it: `check_launch`, then a
    built-in model against its CLI's list (given by `listing`, else read now with `env`), an
    external one against its server, by the probe of saving a model; no model asks nothing.
    The verdict (DEFAULT, OK, or WARN for no list to check against); Refused otherwise."""
    check_launch(start, provider)
    if not start.model:
        return model_check.verdict(provider, "", base.ModelList())
    if start.server is not None:
        verdict = _on_server(provider, start.model, start.server, probe)
        retry = True
    else:
        listed = listing(provider) if listing is not None else provider.model_list(env)
        verdict = model_check.verdict(provider, start.model, listed)
        retry = not listed.fixed
    if verdict.kind == model_check.REFUSED:
        raise Refused(
            verdict.text,
            field=MODEL_FIELD,
            page=verdict.page or None,
            peek=NOT_LISTED_PEEK,
            retry=retry,
        )
    return verdict


# What a spawn's refusal of a model not given adds: an agent has no --model (way_out).
WORKER_WAY_OUT = '; list_models shows the others, model="" is the CLI\'s own settings'


def way_out(start: StartModel, provider: providers.Provider, *, given: bool) -> str:
    """What a refusal of `start` adds at a start or resume: how to leave a model the human did
    not give now (`given` False): the one a session kept, or its CLI's default."""
    if given or start.gone or not start.model:
        return ""
    if start.source == state.DEFAULT_MODEL:
        return (
            f"; it is {provider.title}'s default model: start with --model '' for its settings, "
            f"or change it with lado model default {provider.name}"
        )
    return f"; the session ran on it before: {_way_to_resume(provider)}"


def agent_servers(
    provider: providers.Provider, start: StartModel | None = None
) -> tuple[tuple[base.ServerEntry, ...], list[str]]:
    """The model servers for the config of an agent of `provider`'s CLI, with the models ticked
    for that CLI, whatever it starts on, and the warnings of a launch: a key sent over plain
    http, what is left out, a context too small for `start`. For a CLI that holds one model per
    process, the server of `start` with that model alone, none on any other start. A key LADO
    does not read, or that would break the config, leaves its server out, but is Refused for
    the server of `start`. Asks each server of the config for its limits."""
    if not provider.external_whole_process:
        ticked = [model for model in state.models() if model.cli == provider.name]
    elif start is not None and start.entry is not None:
        ticked = [start.entry]
    else:
        return (), []
    entries, warnings = [], []
    for server in state.model_servers():
        models = [model for model in ticked if model.server == server.id]
        if not models:
            continue
        if _expands(server.name, server.address):
            warnings.append(
                f'model server "{server.name}" is left out of the agent\'s config: it holds text '
                f"{WOULD_EXPAND}"
            )
            continue
        kept: dict[str, str] = {}  # by model: two entries of one model are one row of the config
        for model in models:
            if _expands(model.name, model.model):
                warnings.append(
                    f'model "{model.name}" is left out of the agent\'s config: it holds text '
                    f"{WOULD_EXPAND}"
                )
            elif start is not None and start.entry is not None and start.entry.id == model.id:
                kept[model.model] = model.name  # under the name the agent starts on
            else:
                kept.setdefault(model.model, model.name)
        if not kept:
            continue
        try:
            key = _config_key(server)
        except Refused as exc:
            if start is not None and start.server is not None and start.server.id == server.id:
                raise
            warnings.append(f'the models of model server "{server.name}" are left out: {exc}')
            continue
        if warning := model_servers.plain_http_warning(server.address, key):
            warnings.append(warning)
        entries.append(
            base.ServerEntry(
                server.id,
                server.name,
                model_servers.base_url(server.address),
                server.address,
                f"{KEY_VARIABLE}{server.id.upper()}" if key is not None else "",
                key,
                tuple(kept.items()),
            )
        )
    entries = _with_limits(entries)
    if start is not None and start.server is not None:
        for entry in entries:
            if entry.id == start.server.id:
                limit = entry.limits.get(start.model or "")
                if warning := context_warning(start, provider, limit):
                    warnings.append(warning)
    return tuple(entries), warnings


def _with_limits(entries: list[base.ServerEntry]) -> list[base.ServerEntry]:
    """`entries` with what their servers report: all read at once, so a start waits for one
    ceiling however many servers are silent."""
    if not entries:
        return entries
    with ThreadPoolExecutor(len(entries)) as pool:
        limits = pool.map(lambda e: model_servers.context_limits(e.root, e.key), entries)
        return [replace(e, limits=found) for e, found in zip(entries, limits, strict=True)]


def context_warning(
    start: StartModel, provider: providers.Provider, limit: base.Limit | None
) -> str | None:
    """The warning for `start`, a model reported at `limit`, when its context is below what
    `provider`'s CLI needs to take a turn, or is not known on a server outside the human's
    machine and network, where a late compaction costs money; None otherwise: an Ollama model
    not yet running has no known context either."""
    if limit is None:
        if start.server is None or model_servers.in_network(start.server.address):
            return None
        return (
            f"{start.name} on {start.server.name}: the server reports no context for it, so the "
            'agent compacts late and its answers have no limit; see "A cloud provider" in '
            "docs/install.md"
        )
    if limit.context >= provider.min_context:
        return None
    where = f" on {start.server.name}" if start.server is not None else ""
    how = CONTEXT_HOW.get(start.server.kind if start.server else "", CONTEXT_HOW[""])
    return (
        f"{start.name}{where} has a context of {limit.context:,} tokens; {provider.title} needs "
        f'about {provider.min_context:,} for its instructions and tools: {how}; see "What to '
        'expect of a small model" in docs/install.md'
    )


@dataclass(frozen=True)
class Shown:
    """A model of a server as the human reads it: its saved name (its id with no entry), the
    model, and its server's name and address."""

    name: str
    model: str
    server: str
    address: str


def shown(
    provider: providers.Provider,
    reported: str,
    chosen: state.ConfiguredModel | None = None,
) -> Shown | None:
    """`reported`, a model as `provider`'s CLI names it, when it is one of LADO's servers, read
    now; None for any other, and for a server removed since. Two entries may hold one model of a
    server: `chosen`, when it is that model, gives the name, else the entries are looked up."""
    found = provider.on_server(reported)
    return None if found is None else _shown_on(provider, *found, chosen)


def _shown_on(
    provider: providers.Provider,
    server_id: str,
    model: str,
    chosen: state.ConfiguredModel | None,
) -> Shown | None:
    server = state.model_server_by_id(server_id)
    if server is None:
        return None
    if chosen is not None and (chosen.server, chosen.model) == (server_id, model):
        return Shown(chosen.name, model, server.name, server.address)
    saved = {m.model: m.name for m in state.models_on(server_id) if m.cli == provider.name}
    return Shown(saved.get(model, model), model, server.name, server.address)


def agent_shown(agent: state.Agent) -> Shown | None:
    """The agent's model as `shown` reads it, or on the server its launch says for a CLI whose
    names of a model say none, under the name it started on, as long as its CLI has not changed
    the model; a table that cannot be read names none."""
    if not agent.model or agent.provider not in providers.names():
        return None
    provider = providers.get(agent.provider)
    found = provider.on_server(agent.model)
    if found is None and (server := provider.launched_on(agent)) is not None:
        found = server, agent.model
    if found is None:
        return None
    chosen = None
    if agent.model_source in (state.SESSION, state.DEFAULT_MODEL):
        session = state.get_session(agent.session)
        with contextlib.suppress(Refused):
            chosen = start_model(session.power if session else None, provider).entry
    return _shown_on(provider, *found, chosen)


def model_name(agent: state.Agent) -> str | None:
    """The agent's model for a list: the saved name of a model of LADO's servers, else as its
    record has it."""
    found = agent_shown(agent)
    return found.name if found is not None else agent.model


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
        page=f'The name is taken by the model "{name}"',
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
    suits, _ = model_servers.clis(server.apis, server.kind)
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
