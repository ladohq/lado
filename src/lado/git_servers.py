"""The human's git servers (openspec capability `git-servers`): a GitLab or GitHub Enterprise
server, its kind told by its API, and the token agents and LADO's own git reach it with.

A server is identified by its host and port (`Address.key`), one per host name
(`check_host`: git's ssh addresses carry no port). It is saved in
lado.db (lado.state: `git_servers`) only after its probe: each kind of lado.git_kinds is
asked at once, through lado.model_servers' request path (no redirect followed, each request
cut at its TIMEOUT); `--kind` saves one that cannot be checked. Its token is kept in
`<LADO_HOME>/git-servers/<id>/token` alone, written and removed by the link-refusing writer
of LADO's secrets (lado.project_secrets), never in lado.db, a message or a git config file.

`variables` gives git, through `GIT_CONFIG_*` variables laid over a process's environment, an
empty helper then LADO's own (lado.git_credential) for each saved server's address, and
rewrites the server's ssh addresses to it; an agent gets them at its launch
(lado.runtime), LADO's own network git at each call (lado.agent_env.for_git). git reads
`GIT_CONFIG_COUNT` from 2.31 on: `check_git` refuses an older one where a server is needed.
"""

from __future__ import annotations

import contextlib
import errno
import os
import re
import shlex
import subprocess
import urllib.parse
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from lado import agent_env, git_kinds, interpreter, project_secrets, state
from lado.git_kinds import Kind

if TYPE_CHECKING:  # the HTTP client: loaded by `add` alone, never by a launch or a hook
    from lado import model_servers

TOKENS = "git-servers"  # under LADO_HOME: a folder per server, by its id
TOKEN = "token"  # the token's file in a server's folder
KIND_NAMES = tuple(kind.name for kind in git_kinds.KINDS)
GITHUB_COM = frozenset({"github.com", "www.github.com", "api.github.com"})
HELPER = "lado.git_credential"
ADD = "lado git-server add"
REMOVE = "lado git-server remove"
RESTART = "Agents started from now on reach it; restart running agents to give it to them."
PLAIN_HTTP = (
    "the token goes to {host} over plain http://, unencrypted; use https:// if the server has it"
)


PAGE_KIND_HINT = (
    "If the server is there for git but its API is not reachable from here, choose its kind "
    "to save it without a check."
)
# The fields of Settings → Git servers' form a refusal concerns ("" for none).
ADDRESS_FIELD, TOKEN_FIELD, KIND_FIELD = "address", "token", "kind"


class Refused(Exception):
    """Why a git server is not saved, found or reached, one line; `hint` what the human can
    try ("" for none); `field` the field of the page's form it concerns; `page` and
    `page_hint` the line and the hint for the page, which name no command (None: the same as
    the command's). Never holds a token."""

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


class BadAddress(ValueError):
    """An address LADO does not take; `page` the line for the page."""

    def __init__(self, text: str, page: str | None = None):
        super().__init__(text)
        self.page = text if page is None else page


class Address(NamedTuple):
    """A server's address: `root` its https:// or http:// URL without a trailing `/`, `key`
    its host and a port other than the scheme's (the server's identity), `host` alone."""

    root: str
    key: str
    host: str
    scheme: str


def address(text: str) -> Address:
    """The address of a server from what the human typed, `https://` when it has no scheme;
    BadAddress for one LADO does not take. The text of an error never holds the address: it
    may hold a password."""
    text = text.strip()
    if not text:
        raise BadAddress("no address given")
    if "://" not in text and "@" not in text.split("/", 1)[0]:
        text = "https://" + text
    try:
        parts = urllib.parse.urlsplit(text)
        host = parts.hostname
        port = parts.port
    except ValueError:
        raise BadAddress(
            "not an address of a server (https://host[:port][/path]), or its port is not a "
            "number from 0 to 65535"
        ) from None
    scheme = parts.scheme.lower()
    if scheme not in ("https", "http"):
        raise BadAddress("a git server's address starts with https:// or http://")
    if "@" in parts.netloc:
        no_user = "a git server's address holds no user or password"
        raise BadAddress(f"{no_user}; its token: --token", f"{no_user}; put the token in Token")
    if parts.query:
        raise BadAddress("a git server's address holds no query")
    if parts.fragment:
        raise BadAddress("a git server's address holds no fragment")
    if not host:
        raise BadAddress("the address names no host")
    shown = f"[{host}]" if ":" in host else host
    if port is not None and port != (443 if scheme == "https" else 80):
        shown += f":{port}"
    path = parts.path.rstrip("/")
    return Address(f"{scheme}://{shown}{path}", shown, host, scheme)


def plain_http_warning(at: Address) -> str | None:
    return PLAIN_HTTP.format(host=at.host) if at.scheme == "http" else None


def check_not_github(at: Address) -> None:
    """Refuse github.com: it is reached through gh's login, as in LADO's image."""
    if at.host in GITHUB_COM:
        raise Refused(
            "github.com is reached through gh's login (GH_TOKEN or gh auth login); "
            "LADO keeps no token for it",
            field=ADDRESS_FIELD,
        )


def same_host(at: Address, servers: Sequence[state.GitServer]) -> state.GitServer | None:
    """The server of `servers` on the host name of `at` but another port."""
    return next(
        (
            server
            for server in servers
            if server.host != at.key and urllib.parse.urlsplit(server.address).hostname == at.host
        ),
        None,
    )


def _host_taken(at: Address, server: state.GitServer) -> Refused:
    host = f"[{at.host}]" if ":" in at.host else at.host
    return Refused(
        f"{host} already has a git server, {server.address}; LADO keeps one server per host "
        f"name, as git's ssh addresses (git@{host}:…) carry no port",
        f"remove it first: {REMOVE} {server.address}",
        ADDRESS_FIELD,
        page_hint="Remove it first if the server moved to this address.",
    )


def check_host(at: Address) -> None:
    """Refuse `at` when a saved server holds its host name on another port: git rewrites
    the host's ssh addresses to one server only (`_entries`)."""
    server = same_host(at, state.git_servers())
    if server is not None:
        raise _host_taken(at, server)


def check_token(token: str) -> None:
    """Refuse an empty token, one no HTTP header can carry (nor git's credential protocol,
    one line), and one larger than its file may hold."""
    from lado import model_servers

    if not token:
        raise Refused("the token is empty", field=TOKEN_FIELD)
    if not model_servers.carriable(token):
        raise Refused("the token holds a character no HTTP header can carry", field=TOKEN_FIELD)
    if len(project_secrets.stored(token)) > agent_env.MAX_VALUE:
        raise Refused("the token is larger than 64 KiB", field=TOKEN_FIELD)


@dataclass(frozen=True)
class Checked:
    """What the probe found: the kind, the user the token signs in as (None: not checked),
    and why it could not be checked ("" when it was)."""

    kind: Kind
    login: str | None
    unchecked: str = ""

    def line(self) -> str | None:
        """`GitLab, signed in as <login>`; None for a server not checked."""
        return f"{self.kind.title}, signed in as {self.login}" if self.login else None


def _kind_hint(root: str) -> str:
    return (
        "if the server is there for git but its API is not reachable from here, save it "
        f"unchecked: {ADD} {root} --token --kind {'|'.join(KIND_NAMES)}"
    )


def _silent(answer: model_servers.Answer) -> str:
    """Why a request got no HTTP answer, in the human's words."""
    why = answer.why
    if answer.tls:
        if "certificate" in why:
            return f"its certificate is not trusted on this machine ({why})"
        return f"TLS failed ({why})"
    if why == "unknown host":
        return "the name is not found"
    if why == "connection refused":
        return "the connection is refused"
    if why.startswith("no answer in "):
        return "it did not answer in " + why.removeprefix("no answer in ")
    return why


def probe(at: Address, token: str, kind_name: str | None = None) -> Checked:
    """The kind of the server at `at` and the user `token` signs in as, every kind asked at
    once; with `kind_name`, that kind for a server no kind recognises (Checked.unchecked says
    why). Refused for a server that refuses the token, sends elsewhere, answers as two kinds
    without `kind_name` or as another, or cannot be checked without `kind_name`."""
    import urllib.request

    from lado import model_servers

    opener = urllib.request.build_opener(model_servers.NoRedirect())
    asked = []
    for kind in git_kinds.KINDS:
        url, headers = kind.request(at.root, token)
        asked.append((url, "GET", headers))
    answers = model_servers.ask_all(opener, asked, {"User-Agent": "lado"})
    by_kind = list(zip(git_kinds.KINDS, answers, strict=True))
    found = [(kind, login) for kind, answer in by_kind if (login := kind.login(answer))]
    chosen = git_kinds.by_name(kind_name) if kind_name else None
    if len(found) == 1:
        kind, login = found[0]
        if chosen is not None and chosen is not kind:
            raise Refused(
                f"{at.root} answers as {kind.title}, not {chosen.title}", field=KIND_FIELD
            )
        return Checked(kind, login)
    if found:
        if chosen is not None:
            return Checked(chosen, dict(found)[chosen])
        titles = " and as ".join(kind.title for kind, _ in found)
        which = " or ".join(f"--kind {kind.name}" for kind, _ in found)
        raise Refused(
            f"{at.root} answers as {titles}; say which: {which}",
            field=KIND_FIELD,
            page=f"{at.root} answers as {titles}; choose its kind",
        )
    refusals = [(kind, why) for kind, answer in by_kind if (why := kind.refusal(answer))]
    if refusals:
        kind, why = next(((k, w) for k, w in refusals if k is chosen), refusals[0])
        page = kind.token_page(at.root)
        raise Refused(
            f"{kind.title} at {at.root} {why}",
            f"make a token at {page} ({kind.scopes})",
            TOKEN_FIELD,
        )
    unchecked, refusal = _unanswered(at, answers)
    if chosen is None:
        raise refusal
    return Checked(chosen, None, unchecked)


def _unanswered(at: Address, answers: Sequence[model_servers.Answer]) -> tuple[str, Refused]:
    """For answers of no kind: why the server could not be checked, as the end of "could
    not be checked (…)", and the refusal for an add that chose no kind."""
    moved = next((answer.location for answer in answers if answer.location), "")
    if moved:
        refused = Refused(
            f"{at.root} sends to {moved}; give the server's own address", field=ADDRESS_FIELD
        )
        return f"it sends to {moved}", refused
    if all(answer.status is None for answer in answers):
        silent = _silent(answers[0])
        refused = Refused(
            f"{at.key} does not answer: {silent}",
            _kind_hint(at.root),
            ADDRESS_FIELD,
            page_hint=PAGE_KIND_HINT,
        )
        return f"it does not answer: {silent}", refused
    titles = " nor ".join(kind.title for kind in git_kinds.KINDS)
    refused = Refused(
        f"{at.root} answers as neither {titles}",
        _kind_hint(at.root),
        ADDRESS_FIELD,
        page_hint=PAGE_KIND_HINT,
    )
    return f"it answers as neither {titles}", refused


def helper_command(server: state.GitServer) -> str:
    """git's `credential.<url>.helper` value for LADO's helper of `server`: LADO's own Python
    by its absolute path, so no `lado` on the PATH is needed, with all it needs as
    arguments, so it never opens lado.db; no token, only ids (a `ps` line shows them)."""
    kind = git_kinds.by_name(server.kind)
    user = kind.git_user if kind is not None else "token"  # a kind this LADO does not know
    command = interpreter.run_module(
        HELPER,
        "--home", str(state.home_path().absolute()),
        "--server", server.id,
        "--user", user,
        "--address", server.address,
    )  # fmt: skip
    return "!" + shlex.join(command)


def _entries(server: state.GitServer) -> list[tuple[str, str]]:
    """The git config entries of one server, in order: an empty helper for its origin, which
    drops every helper set before it there (the image's, the human's `store`), so none
    other is asked or stores the token; LADO's helper; its ssh addresses rewritten to its
    root (git's rewrite is a fixed prefix: the standard ssh port alone)."""
    parts = urllib.parse.urlsplit(server.address)
    origin = f"{parts.scheme}://{parts.netloc}"
    host = parts.hostname or ""
    host = f"[{host}]" if ":" in host else host
    rewrite = f"url.{server.address}/.insteadOf"
    return [
        (f"credential.{origin}.helper", ""),
        (f"credential.{origin}.helper", helper_command(server)),
        (rewrite, f"git@{host}:"),
        (rewrite, f"ssh://git@{host}/"),
        (rewrite, f"ssh://git@{host}:22/"),
    ]


def variables(env: Mapping[str, str], servers: Sequence[state.GitServer]) -> dict[str, str]:
    """The `GIT_CONFIG_*` variables to lay over `env` for `servers`: the entries of `env`'s
    own `GIT_CONFIG_COUNT` are kept, LADO's coming after them (a count that is no number
    counts as none). Nothing for no server."""
    if not servers:
        return {}
    try:
        n = max(0, int(env.get("GIT_CONFIG_COUNT", "0")))
    except ValueError:
        n = 0
    found = {}
    for server in servers:
        for key, value in _entries(server):
            found[f"GIT_CONFIG_KEY_{n}"] = key
            found[f"GIT_CONFIG_VALUE_{n}"] = value
            n += 1
    found["GIT_CONFIG_COUNT"] = str(n)
    # What a process this one starts gets back once LADO's entries are dropped
    # (agent_env.without_launch).
    found[agent_env.GIT_CONFIG_BASE] = env.get("GIT_CONFIG_COUNT", "")
    return found


def server_for(remote: str, servers: Sequence[state.GitServer]) -> state.GitServer | None:
    """The server of `servers` git reaches for `remote` with `variables`: by its host and
    port for an https:// or http:// URL, by its host for an ssh address it rewrites
    (`git@host:`, `ssh://git@host[:22]/`); None for any other remote."""
    try:
        if "://" in remote:
            parts = urllib.parse.urlsplit(remote)
            scheme = parts.scheme.lower()
            if scheme in ("https", "http"):
                key = address(f"{scheme}://{parts.netloc.rsplit('@', 1)[-1]}").key
                return next((s for s in servers if s.host == key), None)
            if scheme != "ssh" or parts.username != "git" or parts.port not in (None, 22):
                return None
            host = parts.hostname
        else:
            found = re.match(r"git@([^:/]+):", remote)
            if found is None:
                return None
            host = found[1].lower()
    except ValueError:
        return None
    return next((s for s in servers if urllib.parse.urlsplit(s.address).hostname == host), None)


def check_git(env: Mapping[str, str]) -> None:
    """Refuse a git on `env`'s PATH older than 2.31, which reads no `GIT_CONFIG_COUNT`; a
    git that does not run is left to the folder check and git's own error."""
    from lado import runtime  # runtime lays the variables: imported when asked

    try:
        result = subprocess.run(
            ["git", "--version"], env=dict(env), capture_output=True, text=True, check=False
        )
    except OSError:
        return
    line = result.stdout.strip()
    found = runtime.git_numbers(line)
    if result.returncode != 0 or found is None or found >= runtime.GIT_MIN:
        return
    version = line.removeprefix("git version ").split()[0]
    need = ".".join(map(str, runtime.GIT_MIN))
    older = f"git {version} is older than {need}, which git servers need; update git"
    raise Refused(f"{older}, or remove the servers ({REMOVE} <address>)", page=older)


def token_folder(id: str) -> Path:
    return state.home_path() / TOKENS / id


def has_token(server: state.GitServer) -> bool:
    return os.path.lexists(token_folder(server.id) / TOKEN)


def save(at: Address, checked: Checked, token: str) -> tuple[state.GitServer, bool]:
    """Save the server at `at` as `checked` with `token`, or replace the one of its host,
    keeping its id: the server as saved, and whether one was replaced. A new server's token
    file comes first and goes again when its row fails; a replaced one's row comes first,
    then its token file is replaced whole, so it holds the old token or the new one."""
    known = state.git_server_by_host(at.key)
    if known is not None:
        try:
            saved = state.save_git_server(
                known.id, at.root, at.key, checked.kind.name, checked.login
            )
        except state.HostTaken as exc:
            raise _host_taken(at, exc.server) from None
        _write_token(saved.id, token)
        return saved, True
    id = uuid.uuid4().hex[:12]
    _write_token(id, token)
    try:
        saved = state.save_git_server(id, at.root, at.key, checked.kind.name, checked.login)
    except BaseException as exc:
        # A cleanup that fails leaves the folder over, never hides why.
        with contextlib.suppress(OSError, Refused):
            _remove_token(id)
        if isinstance(exc, state.HostTaken):  # another port saved since check_host
            raise _host_taken(at, exc.server) from None
        raise
    if saved.id != id:  # saved meanwhile by another add of the host: its row was replaced
        _write_token(saved.id, token)
        with contextlib.suppress(OSError, Refused):
            _remove_token(id)
        return saved, True
    return saved, False


def remove(at: Address) -> state.GitServer:
    """Remove the server of the host of `at` and its token folder: the server removed.
    Refused for no such server, or a folder the disk refuses to remove (the row then gone)."""
    known = state.git_server_by_host(at.key)
    if known is None or not state.remove_git_server(known.id):
        raise Refused(
            f"{at.root} is no saved git server",
            "see them: lado git-server list",
            ADDRESS_FIELD,
            page_hint="",
        )
    try:
        _remove_token(known.id)
    except OSError as exc:
        raise Refused(
            f"removed git server {known.address}, but not its folder {token_folder(known.id)} "
            f"({exc.strerror or type(exc).__name__})"
        ) from None
    return known


def add(
    at: Address, token: Callable[[], str], kind_name: str | None, warn: Callable[[str], None]
) -> tuple[state.GitServer, bool, Checked]:
    """Add the server at `at` as `lado git-server add` does, for the command and the page
    alike: the checks of the address and of git, the plain-http warning through `warn`,
    then `token()` (read only once they pass), its check, the probe (`kind_name`: --kind)
    and the save. The server as saved, whether one was replaced, and the probe's finding."""
    if kind_name is not None and git_kinds.by_name(kind_name) is None:
        raise Refused(
            f"{kind_name} is no kind of git server LADO knows: {' or '.join(KIND_NAMES)}",
            field=KIND_FIELD,
        )
    check_not_github(at)
    check_host(at)
    check_git(os.environ)
    warning = plain_http_warning(at)
    if warning:
        warn(warning)
    value = token()
    check_token(value)
    checked = probe(at, value, kind_name)
    saved, replaced = save(at, checked, value)
    return saved, replaced, checked


def _link(path: Path) -> Refused:
    return Refused(
        f"{path} is a symbolic link: LADO keeps a server's token only in its own folders"
    )


def _write_token(id: str, token: str) -> None:
    state.home()
    try:
        try:
            project_secrets.write_at((TOKENS, id), token_folder(id), TOKEN, token)
        except FileNotFoundError:
            # The last server's removal took git-servers/ between its opening and the
            # making of this server's folder in it (`_remove_token`): once more, made anew.
            project_secrets.write_at((TOKENS, id), token_folder(id), TOKEN, token)
    except project_secrets.LinkRefused as exc:
        raise _link(exc.path) from None
    except OSError as exc:
        raise Refused(
            f"{token_folder(id) / TOKEN} cannot be written ({exc.strerror or type(exc).__name__})"
        ) from None


def _remove_token(id: str) -> None:
    """Remove the token file of the server `id` and its folder, then git-servers/ itself
    once it is empty: no server's folder is left in it; OSError (Refused for a link) when
    the disk refuses it. A server's folder made in it at the same moment keeps it."""
    try:
        project_secrets.remove_at((TOKENS, id), token_folder(id), TOKEN)
        with project_secrets.open_chain((TOKENS,), make=False) as fd:
            if fd is not None:
                with contextlib.suppress(FileNotFoundError):
                    os.rmdir(id, dir_fd=fd)
        with project_secrets.open_chain((), make=False) as fd:
            try:
                os.rmdir(TOKENS, dir_fd=fd)
            except OSError as exc:
                if exc.errno not in (errno.ENOENT, errno.ENOTEMPTY, errno.EEXIST):
                    raise
    except project_secrets.LinkRefused as exc:
        raise _link(exc.path) from None
